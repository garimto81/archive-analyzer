"""NAS 자동 동기화 데몬

Issue #17: NAS 신규 데이터 자동 감지 및 DB 등록

NAS에 새로운 파일이 추가되면 자동으로 감지하여 DB에 등록합니다.
폴링 방식으로 주기적으로 NAS를 스캔하고, 신규 파일만 처리합니다.

Usage:
    # 기본 실행 (30분 간격)
    python -m archive_analyzer.nas_auto_sync

    # 간격 지정 (초)
    python -m archive_analyzer.nas_auto_sync --interval 1800

    # 1회 실행
    python -m archive_analyzer.nas_auto_sync --once

    # Dry-run (DB 변경 없음)
    python -m archive_analyzer.nas_auto_sync --once --dry-run
"""

import logging
import os
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

# 프로젝트 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from archive_analyzer.config import SMBConfig
from archive_analyzer.database import Database
from archive_analyzer.file_classifier import classify_file
from archive_analyzer.smb_connector import SMBConnector
from archive_analyzer.sync import SyncConfig, SyncService

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class AutoSyncConfig:
    """자동 동기화 설정"""

    # SMB 설정
    smb_server: str = "10.10.100.122"
    smb_share: str = "docker"
    smb_username: str = "GGP"
    smb_password: str = ""
    archive_path: str = "GGPNAs/ARCHIVE"

    # DB 경로
    archive_db: str = "data/output/archive.db"
    pokervod_db: str = "D:/AI/claude01/shared-data/pokervod.db"

    # 동기화 설정
    sync_interval_seconds: int = 1800  # 30분
    batch_size: int = 50

    def __post_init__(self):
        # 환경변수에서 로드
        self.smb_server = os.environ.get("SMB_SERVER", self.smb_server)
        self.smb_share = os.environ.get("SMB_SHARE", self.smb_share)
        self.smb_username = os.environ.get("SMB_USERNAME", self.smb_username)
        self.smb_password = os.environ.get("SMB_PASSWORD", self.smb_password or "!@QW12qw")
        self.archive_path = os.environ.get("ARCHIVE_PATH", self.archive_path)
        self.archive_db = os.environ.get("ARCHIVE_DB", self.archive_db)
        self.pokervod_db = os.environ.get("POKERVOD_DB", self.pokervod_db)

        if env_interval := os.environ.get("SYNC_INTERVAL"):
            self.sync_interval_seconds = int(env_interval)


@dataclass
class IncrementalScanResult:
    """증분 스캔 결과"""

    new_files: int = 0
    updated_files: int = 0
    skipped_files: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def __str__(self) -> str:
        return (
            f"New: {self.new_files}, Updated: {self.updated_files}, "
            f"Skipped: {self.skipped_files}, Errors: {len(self.errors)}, "
            f"Duration: {self.duration_seconds:.1f}s"
        )


class NASAutoSync:
    """NAS 자동 동기화 서비스

    폴링 방식으로 NAS를 주기적으로 스캔하고,
    신규/변경된 파일만 DB에 등록합니다.
    """

    def __init__(self, config: Optional[AutoSyncConfig] = None):
        self.config = config or AutoSyncConfig()
        self.connector: Optional[SMBConnector] = None
        self.database: Optional[Database] = None
        self._existing_paths: Set[str] = set()

    def _connect(self) -> None:
        """SMB 및 DB 연결"""
        if self.connector is None or not self.connector.is_connected:
            smb_config = SMBConfig(
                server=self.config.smb_server,
                share=self.config.smb_share,
                username=self.config.smb_username,
                password=self.config.smb_password,
            )
            self.connector = SMBConnector(smb_config)
            self.connector.connect()
            logger.info(f"SMB 연결 완료: {self.config.smb_server}")

        if self.database is None:
            # archive.db 디렉토리 생성
            db_path = Path(self.config.archive_db)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.database = Database(str(db_path))
            logger.info(f"DB 연결 완료: {db_path}")

    def _disconnect(self) -> None:
        """연결 종료"""
        if self.connector:
            self.connector.disconnect()
            self.connector = None
        if self.database:
            self.database.close()
            self.database = None

    def _load_existing_paths(self) -> Set[str]:
        """기존 DB에 등록된 파일 경로 로드"""
        if self.database is None:
            return set()

        conn = self.database._get_connection()
        cursor = conn.execute("SELECT path FROM files")
        paths = {row[0] for row in cursor.fetchall()}
        logger.info(f"기존 파일 수: {len(paths)}")
        return paths

    def _normalize_path(self, path: str) -> str:
        """경로 정규화"""
        return path.replace("\\", "/").lower()

    def incremental_scan(self, dry_run: bool = False) -> IncrementalScanResult:
        """증분 스캔 실행

        기존 DB에 없는 새 파일만 등록합니다.

        Args:
            dry_run: True면 실제 DB 변경 없이 시뮬레이션

        Returns:
            IncrementalScanResult 객체
        """
        result = IncrementalScanResult()
        start_time = datetime.now()

        try:
            self._connect()

            # 기존 경로 로드
            self._existing_paths = self._load_existing_paths()
            existing_normalized = {self._normalize_path(p) for p in self._existing_paths}

            logger.info(f"증분 스캔 시작: {self.config.archive_path}")

            batch = []

            for info in self.connector.scan_directory(self.config.archive_path, recursive=True):
                if info.is_dir:
                    continue

                normalized_path = self._normalize_path(info.path)

                # 이미 존재하면 스킵
                if normalized_path in existing_normalized:
                    result.skipped_files += 1
                    continue

                try:
                    # 새 파일 발견
                    file_type = classify_file(info.name)
                    parent = os.path.dirname(info.path)

                    record = {
                        "path": info.path,
                        "filename": info.name,
                        "extension": info.extension,
                        "size_bytes": info.size,
                        "modified_at": datetime.fromtimestamp(info.modified_time)
                        if info.modified_time
                        else None,
                        "file_type": file_type.value,
                        "parent_folder": parent,
                        "scan_status": "scanned",
                    }

                    if not dry_run:
                        batch.append(record)

                    result.new_files += 1
                    logger.debug(f"새 파일: {info.path}")

                    # 배치 저장
                    if len(batch) >= self.config.batch_size:
                        self._save_batch(batch)
                        batch = []

                except Exception as e:
                    result.errors.append(f"{info.path}: {str(e)}")
                    logger.warning(f"파일 처리 오류: {info.path} - {e}")

            # 남은 배치 저장
            if batch and not dry_run:
                self._save_batch(batch)

        except Exception as e:
            result.errors.append(f"스캔 오류: {str(e)}")
            logger.error(f"스캔 실패: {e}")
            raise

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        logger.info(f"증분 스캔 완료: {result}")

        return result

    def _save_batch(self, batch: List[dict]) -> None:
        """배치 저장"""
        if not self.database or not batch:
            return

        conn = self.database._get_connection()
        cursor = conn.cursor()

        for record in batch:
            try:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO files (
                        path, filename, extension, size_bytes,
                        modified_at, file_type, parent_folder, scan_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        record["path"],
                        record["filename"],
                        record["extension"],
                        record["size_bytes"],
                        record["modified_at"].isoformat() if record["modified_at"] else None,
                        record["file_type"],
                        record["parent_folder"],
                        record["scan_status"],
                    ),
                )
            except Exception as e:
                logger.warning(f"배치 저장 오류: {record['path']} - {e}")

        conn.commit()
        logger.debug(f"배치 저장: {len(batch)}건")

    def sync_to_pokervod(self, dry_run: bool = False) -> dict:
        """pokervod.db로 동기화

        archive.db의 데이터를 pokervod.db로 동기화합니다.

        Args:
            dry_run: True면 실제 DB 변경 없이 시뮬레이션

        Returns:
            동기화 결과 딕셔너리
        """
        sync_config = SyncConfig(
            archive_db=self.config.archive_db,
            pokervod_db=self.config.pokervod_db,
        )

        try:
            sync_service = SyncService(sync_config)
            results = sync_service.run_full_sync(dry_run=dry_run)

            return {
                "catalogs": {
                    "inserted": results["catalogs"].inserted,
                    "updated": results["catalogs"].updated,
                    "errors": len(results["catalogs"].errors),
                },
                "files": {
                    "inserted": results["files"].inserted,
                    "updated": results["files"].updated,
                    "errors": len(results["files"].errors),
                },
            }
        except FileNotFoundError as e:
            logger.warning(f"동기화 스킵: {e}")
            return {"error": str(e)}

    def run_once(self, dry_run: bool = False) -> dict:
        """1회 실행

        1. 증분 스캔 (NAS → archive.db)
        2. 동기화 (archive.db → pokervod.db)

        Args:
            dry_run: True면 실제 DB 변경 없이 시뮬레이션

        Returns:
            실행 결과 딕셔너리
        """
        logger.info("=" * 50)
        logger.info("NAS 자동 동기화 실행")
        logger.info("=" * 50)

        results = {}

        try:
            # 1. 증분 스캔
            logger.info("[1/2] 증분 스캔...")
            scan_result = self.incremental_scan(dry_run=dry_run)
            results["scan"] = {
                "new_files": scan_result.new_files,
                "skipped": scan_result.skipped_files,
                "errors": len(scan_result.errors),
                "duration": scan_result.duration_seconds,
            }

            # 신규 파일이 있으면 pokervod 동기화
            if scan_result.new_files > 0 or not dry_run:
                logger.info("[2/2] pokervod.db 동기화...")
                sync_result = self.sync_to_pokervod(dry_run=dry_run)
                results["sync"] = sync_result
            else:
                logger.info("[2/2] 신규 파일 없음, 동기화 스킵")
                results["sync"] = {"skipped": True}

        finally:
            self._disconnect()

        logger.info("=" * 50)
        logger.info(f"완료: {results}")
        logger.info("=" * 50)

        return results

    def run_daemon(self) -> None:
        """데몬 모드 실행

        지정된 간격으로 증분 스캔 및 동기화를 반복합니다.
        """
        interval = self.config.sync_interval_seconds
        logger.info(f"NAS 자동 동기화 데몬 시작 (간격: {interval}초 = {interval//60}분)")
        logger.info("중지: Ctrl+C")
        logger.info("")

        try:
            while True:
                try:
                    self.run_once()
                except Exception as e:
                    logger.error(f"동기화 오류: {e}")

                logger.info(f"다음 동기화까지 {interval//60}분 대기...")
                time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("\n데몬 종료")
        finally:
            self._disconnect()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="NAS 자동 동기화 데몬",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m archive_analyzer.nas_auto_sync              # 데몬 모드 (30분 간격)
  python -m archive_analyzer.nas_auto_sync --interval 600  # 10분 간격
  python -m archive_analyzer.nas_auto_sync --once          # 1회 실행
  python -m archive_analyzer.nas_auto_sync --once --dry-run  # 시뮬레이션
        """,
    )

    parser.add_argument(
        "--interval",
        "-i",
        type=int,
        default=1800,
        help="동기화 간격 (초, 기본: 1800 = 30분)",
    )
    parser.add_argument(
        "--once",
        "-1",
        action="store_true",
        help="1회만 실행 후 종료",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="실제 DB 변경 없이 시뮬레이션",
    )
    parser.add_argument(
        "--archive-db",
        type=str,
        help="archive.db 경로",
    )
    parser.add_argument(
        "--pokervod-db",
        type=str,
        help="pokervod.db 경로",
    )

    args = parser.parse_args()

    # 설정 생성
    config = AutoSyncConfig(sync_interval_seconds=args.interval)

    if args.archive_db:
        config.archive_db = args.archive_db
    if args.pokervod_db:
        config.pokervod_db = args.pokervod_db

    # 서비스 실행
    service = NASAutoSync(config)

    if args.once:
        service.run_once(dry_run=args.dry_run)
    else:
        service.run_daemon()


if __name__ == "__main__":
    main()
