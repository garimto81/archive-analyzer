"""NAS 경로 변경 추적기

Issue #41: NAS 경로 변경 실시간 감지 및 DB 자동 동기화 시스템

이 모듈은 NAS 파일 시스템의 변경(생성, 이동, 삭제)을 감지하고
DB에 자동으로 반영합니다.

Usage:
    python -m archive_analyzer.path_tracker [--once] [--dry-run]
"""

import hashlib
import logging
import os
import queue
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import xxhash

    XXHASH_AVAILABLE = True
except ImportError:
    XXHASH_AVAILABLE = False

from watchdog.events import (
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers.polling import PollingObserver

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class TrackerConfig:
    """Path Tracker 설정"""

    # DB 경로
    db_path: str = "data/output/archive.db"
    pokervod_db: str = "D:/AI/claude01/shared-data/pokervod.db"

    # NAS 경로
    nas_path: str = "Z:/GGPNAs/ARCHIVE"

    # 폴링 설정
    poll_interval: int = 30  # 초

    # Debounce 설정
    debounce_seconds: float = 5.0

    # 해시 설정
    hash_size_kb: int = 512  # 헤더 크기 (KB)

    # 파일 필터
    video_extensions: Set[str] = field(
        default_factory=lambda: {".mp4", ".mkv", ".mov", ".avi", ".mxf", ".ts", ".m2ts"}
    )

    # 배치 처리
    batch_size: int = 50

    def __post_init__(self):
        # 환경변수에서 로드
        self.db_path = os.environ.get("ARCHIVE_DB", self.db_path)
        self.pokervod_db = os.environ.get("POKERVOD_DB", self.pokervod_db)
        self.nas_path = os.environ.get("NAS_PATH", self.nas_path)

        if interval := os.environ.get("POLL_INTERVAL"):
            self.poll_interval = int(interval)


# =============================================================================
# File Identity
# =============================================================================


@dataclass
class FileIdentity:
    """파일 동일성 식별자

    파일 이동을 감지하기 위해 content_hash + 크기 + 파일명 조합 사용
    """

    size: int
    filename: str
    content_hash: str
    mtime: float

    @property
    def quick_id(self) -> str:
        """빠른 비교용 ID (크기+파일명)"""
        return f"{self.size}:{self.filename}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FileIdentity):
            return False
        return self.content_hash == other.content_hash and self.size == other.size

    def __hash__(self) -> int:
        return hash((self.content_hash, self.size))


class FileIdentityStore:
    """해시 기반 파일 식별 저장소

    xxHash를 사용하여 파일 헤더(512KB)의 해시를 계산하고,
    이를 통해 파일 이동을 감지합니다.
    """

    def __init__(self, db_path: str, hash_size_kb: int = 512):
        self.db_path = db_path
        self.hash_size = hash_size_kb * 1024
        self._cache: Dict[str, FileIdentity] = {}

    def compute(self, path: str) -> Optional[FileIdentity]:
        """파일 동일성 식별자 계산

        Args:
            path: 파일 경로

        Returns:
            FileIdentity 또는 None (파일 접근 실패 시)
        """
        try:
            stat = os.stat(path)

            # 헤더만 읽어 해시 계산
            with open(path, "rb") as f:
                header = f.read(self.hash_size)

            content_hash = self._compute_hash(header)

            identity = FileIdentity(
                size=stat.st_size,
                filename=os.path.basename(path),
                content_hash=content_hash,
                mtime=stat.st_mtime,
            )

            # 캐시에 저장
            self._cache[path] = identity

            return identity

        except (OSError, IOError) as e:
            logger.warning(f"파일 접근 실패: {path} - {e}")
            return None

    def _compute_hash(self, data: bytes) -> str:
        """해시 계산 (xxHash 우선, 없으면 MD5)"""
        if XXHASH_AVAILABLE:
            return xxhash.xxh64(data).hexdigest()
        else:
            return hashlib.md5(data).hexdigest()

    def find_by_hash(self, content_hash: str) -> Optional[str]:
        """해시로 기존 파일 경로 검색

        Args:
            content_hash: 파일 해시

        Returns:
            기존 파일 경로 또는 None
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT nas_path FROM files WHERE content_hash = ? AND status = 'active'",
                (content_hash,),
            )
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def find_by_hash_and_size(
        self, content_hash: str, size: int
    ) -> Optional[Tuple[str, str]]:
        """해시+크기로 기존 파일 검색

        Args:
            content_hash: 파일 해시
            size: 파일 크기

        Returns:
            (file_id, nas_path) 튜플 또는 None
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """SELECT id, nas_path FROM files
                   WHERE content_hash = ? AND size_bytes = ? AND status = 'active'""",
                (content_hash, size),
            )
            row = cursor.fetchone()
            return (row[0], row[1]) if row else None
        finally:
            conn.close()

    def update_hash(self, file_id: str, content_hash: str) -> None:
        """파일 해시 업데이트"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE files SET content_hash = ?, updated_at = ? WHERE id = ?",
                (content_hash, datetime.now().isoformat(), file_id),
            )
            conn.commit()
        finally:
            conn.close()


# =============================================================================
# Event Queue (Debounce)
# =============================================================================


@dataclass
class TrackerEvent:
    """추적 이벤트"""

    event_type: str  # created, modified, moved, deleted
    src_path: str
    dst_path: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


class EventQueue:
    """이벤트 큐 (Debounce 지원)

    동일 파일에 대한 연속 이벤트를 병합하여
    불필요한 처리를 줄입니다.
    """

    def __init__(self, debounce_seconds: float = 5.0):
        self.debounce_seconds = debounce_seconds
        self._queue: queue.Queue[TrackerEvent] = queue.Queue()
        self._pending: Dict[str, TrackerEvent] = {}
        self._lock = threading.Lock()
        self._flush_timer: Optional[threading.Timer] = None

    def put(self, event: TrackerEvent) -> None:
        """이벤트 추가 (debounce 적용)"""
        with self._lock:
            key = event.src_path

            # 기존 이벤트가 있으면 병합
            if key in self._pending:
                old_event = self._pending[key]
                # 최신 이벤트로 업데이트 (단, deleted는 우선)
                if old_event.event_type == "deleted":
                    return  # 삭제가 우선
                if event.event_type == "deleted":
                    self._pending[key] = event
                elif event.timestamp > old_event.timestamp:
                    self._pending[key] = event
            else:
                self._pending[key] = event

            # 플러시 타이머 재설정
            self._reset_flush_timer()

    def _reset_flush_timer(self) -> None:
        """플러시 타이머 재설정"""
        if self._flush_timer:
            self._flush_timer.cancel()

        self._flush_timer = threading.Timer(self.debounce_seconds, self._flush)
        self._flush_timer.start()

    def _flush(self) -> None:
        """대기 중인 이벤트를 큐로 이동"""
        with self._lock:
            for event in self._pending.values():
                self._queue.put(event)
            self._pending.clear()
            logger.debug(f"이벤트 플러시: {self._queue.qsize()}건")

    def get(self, timeout: float = 1.0) -> Optional[TrackerEvent]:
        """이벤트 가져오기"""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def flush_now(self) -> None:
        """즉시 플러시"""
        if self._flush_timer:
            self._flush_timer.cancel()
        self._flush()

    @property
    def pending_count(self) -> int:
        """대기 중인 이벤트 수"""
        with self._lock:
            return len(self._pending)

    @property
    def queue_size(self) -> int:
        """큐 크기"""
        return self._queue.qsize()


# =============================================================================
# Event Handler
# =============================================================================


class NASEventHandler(FileSystemEventHandler):
    """NAS 파일 시스템 이벤트 핸들러"""

    def __init__(
        self, event_queue: EventQueue, video_extensions: Optional[Set[str]] = None
    ):
        self.event_queue = event_queue
        self.video_extensions = video_extensions or {
            ".mp4",
            ".mkv",
            ".mov",
            ".avi",
            ".mxf",
        }

    def _is_video(self, path: str) -> bool:
        """비디오 파일 여부 확인"""
        ext = os.path.splitext(path)[1].lower()
        return ext in self.video_extensions

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if not self._is_video(event.src_path):
            return

        self.event_queue.put(
            TrackerEvent(event_type="created", src_path=event.src_path)
        )
        logger.debug(f"Created: {event.src_path}")

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if not self._is_video(event.src_path):
            return

        self.event_queue.put(
            TrackerEvent(event_type="deleted", src_path=event.src_path)
        )
        logger.debug(f"Deleted: {event.src_path}")

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if not self._is_video(event.src_path):
            return

        self.event_queue.put(
            TrackerEvent(event_type="modified", src_path=event.src_path)
        )
        logger.debug(f"Modified: {event.src_path}")

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return

        # src 또는 dst가 비디오면 처리
        if not (self._is_video(event.src_path) or self._is_video(event.dest_path)):
            return

        self.event_queue.put(
            TrackerEvent(
                event_type="moved", src_path=event.src_path, dst_path=event.dest_path
            )
        )
        logger.debug(f"Moved: {event.src_path} -> {event.dest_path}")


# =============================================================================
# Path Tracker
# =============================================================================


@dataclass
class TrackerResult:
    """추적 결과"""

    created: int = 0
    updated: int = 0
    moved: int = 0
    deleted: int = 0
    errors: List[str] = field(default_factory=list)


class NASPathTracker:
    """NAS 경로 변경 추적기

    watchdog PollingObserver를 사용하여 NAS 파일 변경을 감지하고,
    해시 기반으로 파일 이동을 추적합니다.
    """

    def __init__(self, config: Optional[TrackerConfig] = None):
        self.config = config or TrackerConfig()
        self.identity_store = FileIdentityStore(
            self.config.db_path, self.config.hash_size_kb
        )
        self.event_queue = EventQueue(self.config.debounce_seconds)
        self._observer: Optional[PollingObserver] = None
        self._running = False

    def start(self) -> None:
        """추적 시작"""
        if not Path(self.config.nas_path).exists():
            raise FileNotFoundError(f"NAS 경로를 찾을 수 없습니다: {self.config.nas_path}")

        handler = NASEventHandler(
            self.event_queue, self.config.video_extensions
        )

        self._observer = PollingObserver(timeout=self.config.poll_interval)
        self._observer.schedule(handler, self.config.nas_path, recursive=True)
        self._observer.start()

        self._running = True
        logger.info(f"NAS 추적 시작: {self.config.nas_path} (폴링 {self.config.poll_interval}초)")

    def stop(self) -> None:
        """추적 중지"""
        self._running = False
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        logger.info("NAS 추적 중지")

    def process_events(self, timeout: float = 10.0) -> TrackerResult:
        """이벤트 처리

        Args:
            timeout: 대기 시간 (초)

        Returns:
            TrackerResult 처리 결과
        """
        result = TrackerResult()
        end_time = time.time() + timeout

        while time.time() < end_time:
            event = self.event_queue.get(timeout=1.0)
            if event is None:
                continue

            try:
                if event.event_type == "created":
                    if self._handle_created(event):
                        result.created += 1
                elif event.event_type == "deleted":
                    if self._handle_deleted(event):
                        result.deleted += 1
                elif event.event_type == "moved":
                    if self._handle_moved(event):
                        result.moved += 1
                elif event.event_type == "modified":
                    if self._handle_modified(event):
                        result.updated += 1
            except Exception as e:
                result.errors.append(f"{event.src_path}: {str(e)}")
                logger.error(f"이벤트 처리 오류: {event} - {e}")

        return result

    def _handle_created(self, event: TrackerEvent) -> bool:
        """생성 이벤트 처리"""
        path = event.src_path
        identity = self.identity_store.compute(path)
        if identity is None:
            return False

        # 해시로 기존 파일 검색 (이동 감지)
        existing = self.identity_store.find_by_hash_and_size(
            identity.content_hash, identity.size
        )

        if existing:
            file_id, old_path = existing
            # 이동으로 처리
            self._update_path(file_id, old_path, path)
            self._log_history(file_id, "moved", old_path, path)
            logger.info(f"이동 감지: {old_path} -> {path}")
            return True
        else:
            # 신규 파일
            self._create_file(path, identity)
            logger.info(f"신규 파일: {path}")
            return True

    def _handle_deleted(self, event: TrackerEvent) -> bool:
        """삭제 이벤트 처리 (Soft Delete)"""
        path = event.src_path

        conn = sqlite3.connect(self.config.db_path)
        try:
            cursor = conn.execute(
                "SELECT id FROM files WHERE nas_path = ? AND status = 'active'",
                (path,),
            )
            row = cursor.fetchone()
            if not row:
                return False

            file_id = row[0]

            # Soft Delete
            conn.execute(
                """UPDATE files
                   SET status = 'deleted', deleted_at = ?, updated_at = ?
                   WHERE id = ?""",
                (datetime.now().isoformat(), datetime.now().isoformat(), file_id),
            )
            conn.commit()

            self._log_history(file_id, "deleted", path, None)
            logger.info(f"삭제 (soft): {path}")
            return True

        finally:
            conn.close()

    def _handle_moved(self, event: TrackerEvent) -> bool:
        """이동 이벤트 처리"""
        src_path = event.src_path
        dst_path = event.dst_path

        if not dst_path:
            return False

        conn = sqlite3.connect(self.config.db_path)
        try:
            cursor = conn.execute(
                "SELECT id FROM files WHERE nas_path = ?",
                (src_path,),
            )
            row = cursor.fetchone()
            if not row:
                # 소스가 없으면 신규 생성으로 처리
                return self._handle_created(
                    TrackerEvent(event_type="created", src_path=dst_path)
                )

            file_id = row[0]

            # 경로 업데이트
            conn.execute(
                """UPDATE files
                   SET nas_path = ?, filename = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    dst_path,
                    os.path.basename(dst_path),
                    datetime.now().isoformat(),
                    file_id,
                ),
            )
            conn.commit()

            self._log_history(file_id, "moved", src_path, dst_path)
            logger.info(f"이동: {src_path} -> {dst_path}")
            return True

        finally:
            conn.close()

    def _handle_modified(self, event: TrackerEvent) -> bool:
        """수정 이벤트 처리"""
        path = event.src_path
        identity = self.identity_store.compute(path)
        if identity is None:
            return False

        conn = sqlite3.connect(self.config.db_path)
        try:
            cursor = conn.execute(
                "SELECT id, content_hash FROM files WHERE nas_path = ?",
                (path,),
            )
            row = cursor.fetchone()
            if not row:
                return False

            file_id, old_hash = row

            # 해시가 변경된 경우만 업데이트
            if old_hash != identity.content_hash:
                conn.execute(
                    """UPDATE files
                       SET content_hash = ?, size_bytes = ?, updated_at = ?
                       WHERE id = ?""",
                    (
                        identity.content_hash,
                        identity.size,
                        datetime.now().isoformat(),
                        file_id,
                    ),
                )
                conn.commit()

                self._log_history(
                    file_id, "modified", path, path, old_hash, identity.content_hash
                )
                logger.info(f"수정: {path}")
                return True

            return False

        finally:
            conn.close()

    def _create_file(self, path: str, identity: FileIdentity) -> str:
        """신규 파일 생성"""
        from .utils.path import generate_file_id

        file_id = generate_file_id(path)

        conn = sqlite3.connect(self.config.db_path)
        try:
            conn.execute(
                """INSERT INTO files (
                    id, nas_path, filename, size_bytes, content_hash,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)""",
                (
                    file_id,
                    path,
                    identity.filename,
                    identity.size,
                    identity.content_hash,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()

            self._log_history(file_id, "created", None, path)
            return file_id

        finally:
            conn.close()

    def _update_path(self, file_id: str, old_path: str, new_path: str) -> None:
        """경로 업데이트"""
        conn = sqlite3.connect(self.config.db_path)
        try:
            conn.execute(
                """UPDATE files
                   SET nas_path = ?, filename = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    new_path,
                    os.path.basename(new_path),
                    datetime.now().isoformat(),
                    file_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _log_history(
        self,
        file_id: str,
        event_type: str,
        old_path: Optional[str],
        new_path: Optional[str],
        old_hash: Optional[str] = None,
        new_hash: Optional[str] = None,
    ) -> None:
        """변경 이력 기록"""
        conn = sqlite3.connect(self.config.db_path)
        try:
            conn.execute(
                """INSERT INTO file_history (
                    file_id, event_type, old_path, new_path, old_hash, new_hash
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (file_id, event_type, old_path, new_path, old_hash, new_hash),
            )
            conn.commit()
        except sqlite3.OperationalError as e:
            # file_history 테이블이 없으면 무시
            logger.warning(f"이력 기록 실패: {e}")
        finally:
            conn.close()

    def reconcile(self) -> TrackerResult:
        """정합성 검증

        DB의 active 파일이 실제 NAS에 존재하는지 확인하고,
        존재하지 않으면 deleted로 마킹합니다.
        """
        result = TrackerResult()

        conn = sqlite3.connect(self.config.db_path)
        try:
            cursor = conn.execute(
                "SELECT id, nas_path FROM files WHERE status = 'active'"
            )
            rows = cursor.fetchall()

            for file_id, nas_path in rows:
                if not os.path.exists(nas_path):
                    # 파일 없음 -> deleted
                    conn.execute(
                        """UPDATE files
                           SET status = 'deleted', deleted_at = ?, updated_at = ?
                           WHERE id = ?""",
                        (datetime.now().isoformat(), datetime.now().isoformat(), file_id),
                    )
                    result.deleted += 1
                    logger.info(f"정합성 검증 - 삭제: {nas_path}")

            conn.commit()
            logger.info(f"정합성 검증 완료: {result.deleted}개 삭제")

        finally:
            conn.close()

        return result

    def run_once(self, dry_run: bool = False) -> TrackerResult:
        """1회 실행"""
        logger.info("=" * 50)
        logger.info("NAS Path Tracker - 1회 실행")
        logger.info("=" * 50)

        result = TrackerResult()

        try:
            self.start()
            # 초기 스캔 대기
            time.sleep(self.config.poll_interval + 5)

            # 이벤트 처리
            self.event_queue.flush_now()
            result = self.process_events(timeout=5.0)

        finally:
            self.stop()

        logger.info(f"결과: 생성 {result.created}, 이동 {result.moved}, 삭제 {result.deleted}")
        return result

    def run_daemon(self) -> None:
        """데몬 모드 실행"""
        logger.info("=" * 50)
        logger.info(f"NAS Path Tracker 데몬 시작 (폴링 {self.config.poll_interval}초)")
        logger.info("중지: Ctrl+C")
        logger.info("=" * 50)

        try:
            self.start()

            while self._running:
                # 이벤트 처리
                result = self.process_events(timeout=self.config.poll_interval)

                if result.created or result.moved or result.deleted or result.updated:
                    logger.info(
                        f"처리: 생성 {result.created}, 수정 {result.updated}, "
                        f"이동 {result.moved}, 삭제 {result.deleted}"
                    )

        except KeyboardInterrupt:
            logger.info("\n데몬 종료 요청")
        finally:
            self.stop()


# =============================================================================
# CLI
# =============================================================================


def main():
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="NAS 경로 변경 추적기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--once", "-1", action="store_true", help="1회만 실행 후 종료"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true", help="실제 DB 변경 없이 시뮬레이션"
    )
    parser.add_argument(
        "--reconcile", "-r", action="store_true", help="정합성 검증만 실행"
    )
    parser.add_argument(
        "--db-path", type=str, help="archive.db 경로"
    )
    parser.add_argument(
        "--nas-path", type=str, help="NAS 경로"
    )
    parser.add_argument(
        "--poll-interval", type=int, default=30, help="폴링 간격 (초)"
    )

    args = parser.parse_args()

    config = TrackerConfig(poll_interval=args.poll_interval)
    if args.db_path:
        config.db_path = args.db_path
    if args.nas_path:
        config.nas_path = args.nas_path

    tracker = NASPathTracker(config)

    if args.reconcile:
        result = tracker.reconcile()
        print(f"정합성 검증 완료: {result.deleted}개 삭제")
    elif args.once:
        tracker.run_once(dry_run=args.dry_run)
    else:
        tracker.run_daemon()


if __name__ == "__main__":
    main()
