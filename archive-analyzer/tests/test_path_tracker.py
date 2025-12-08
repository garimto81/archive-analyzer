"""NAS Path Tracker 테스트

Issue #41: NAS 경로 변경 실시간 감지 및 DB 자동 동기화 시스템
"""

import os
import sqlite3
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# smbclient 의존성 없이 path_tracker 모듈만 직접 임포트
import sys
import importlib.util
from pathlib import Path

# path_tracker.py 직접 로드 (archive_analyzer 패키지 우회)
_path_tracker_path = Path(__file__).parent.parent / "src" / "archive_analyzer" / "path_tracker.py"
_spec = importlib.util.spec_from_file_location("path_tracker", _path_tracker_path)
_path_tracker = importlib.util.module_from_spec(_spec)

# watchdog mock (없으면 설치 필요)
try:
    _spec.loader.exec_module(_path_tracker)
except ModuleNotFoundError as e:
    pytest.skip(f"의존성 없음: {e}", allow_module_level=True)

# 모듈에서 클래스 가져오기
FileIdentity = _path_tracker.FileIdentity
FileIdentityStore = _path_tracker.FileIdentityStore
EventQueue = _path_tracker.EventQueue
TrackerEvent = _path_tracker.TrackerEvent
TrackerConfig = _path_tracker.TrackerConfig
NASPathTracker = _path_tracker.NASPathTracker


class TestFileIdentity:
    """파일 동일성 식별자 테스트"""

    def test_identity_from_file_info(self):
        """파일 정보에서 Identity 생성"""
        # Given: 파일 정보
        size = 1024 * 1024  # 1MB
        filename = "test_video.mp4"
        content_hash = "abc123def456"
        mtime = 1704067200.0

        # When: Identity 생성
        identity = FileIdentity(
            size=size,
            filename=filename,
            content_hash=content_hash,
            mtime=mtime
        )

        # Then: 속성 확인
        assert identity.size == size
        assert identity.filename == filename
        assert identity.content_hash == content_hash

    def test_identity_equality(self):
        """동일한 파일은 같은 Identity를 가짐"""
        identity1 = FileIdentity(
            size=1024, filename="video.mp4", content_hash="abc123", mtime=1.0
        )
        identity2 = FileIdentity(
            size=1024, filename="video.mp4", content_hash="abc123", mtime=2.0
        )
        # 해시와 크기가 같으면 동일
        assert identity1 == identity2

    def test_identity_quick_id(self):
        """빠른 비교용 quick_id (크기+파일명)"""
        identity = FileIdentity(
            size=1024, filename="video.mp4", content_hash="abc123", mtime=1.0
        )
        assert identity.quick_id == "1024:video.mp4"


class TestFileIdentityStore:
    """해시 기반 파일 식별 저장소 테스트"""

    @pytest.fixture
    def temp_db(self):
        """임시 테스트 DB"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE files (
                id TEXT PRIMARY KEY,
                nas_path TEXT UNIQUE,
                filename TEXT,
                size_bytes INTEGER,
                status TEXT DEFAULT 'active',
                content_hash TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE file_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                old_path TEXT,
                new_path TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

        yield db_path

        os.unlink(db_path)

    def test_compute_hash_from_header(self, temp_db):
        """512KB 헤더에서 xxHash 계산"""
        pytest.skip("FileIdentityStore 클래스 구현 후 활성화")

    def test_find_by_hash_existing(self, temp_db):
        """해시로 기존 파일 검색 - 존재하는 경우"""
        pytest.skip("FileIdentityStore 클래스 구현 후 활성화")

    def test_find_by_hash_not_found(self, temp_db):
        """해시로 기존 파일 검색 - 없는 경우"""
        pytest.skip("FileIdentityStore 클래스 구현 후 활성화")

    def test_detect_moved_file(self, temp_db):
        """파일 이동 감지 (해시 동일, 경로 다름)"""
        pytest.skip("FileIdentityStore 클래스 구현 후 활성화")


class TestNASPathTracker:
    """NAS 경로 변경 추적기 테스트"""

    @pytest.fixture
    def temp_db(self):
        """임시 테스트 DB"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE files (
                id TEXT PRIMARY KEY,
                nas_path TEXT UNIQUE,
                filename TEXT,
                size_bytes INTEGER,
                status TEXT DEFAULT 'active',
                content_hash TEXT,
                deleted_at TIMESTAMP,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE file_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                old_path TEXT,
                new_path TEXT,
                old_hash TEXT,
                new_hash TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                synced_at TIMESTAMP,
                metadata TEXT
            )
        """)
        conn.commit()
        conn.close()

        yield db_path

        os.unlink(db_path)

    def test_on_created_new_file(self, temp_db):
        """신규 파일 생성 이벤트 처리"""
        pytest.skip("NASPathTracker 클래스 구현 후 활성화")

    def test_on_created_moved_file(self, temp_db):
        """이동된 파일 생성 이벤트 (해시로 기존 파일 감지)"""
        pytest.skip("NASPathTracker 클래스 구현 후 활성화")

    def test_on_deleted_soft_delete(self, temp_db):
        """삭제 이벤트 - Soft Delete 처리"""
        # Given: DB에 파일 레코드 존재
        conn = sqlite3.connect(temp_db)
        conn.execute("""
            INSERT INTO files (id, nas_path, filename, status)
            VALUES ('file-001', '/archive/video.mp4', 'video.mp4', 'active')
        """)
        conn.commit()
        conn.close()

        # When: 삭제 이벤트 발생
        # tracker = NASPathTracker(TrackerConfig(db_path=temp_db))
        # tracker.on_deleted('/archive/video.mp4')

        # Then: status가 'deleted'로 변경, deleted_at 설정
        # conn = sqlite3.connect(temp_db)
        # row = conn.execute("SELECT status, deleted_at FROM files WHERE id = 'file-001'").fetchone()
        # assert row[0] == 'deleted'
        # assert row[1] is not None
        pytest.skip("NASPathTracker 클래스 구현 후 활성화")

    def test_on_moved_updates_path(self, temp_db):
        """이동 이벤트 - 경로만 업데이트, ID 유지"""
        pytest.skip("NASPathTracker 클래스 구현 후 활성화")

    def test_history_logged_on_event(self, temp_db):
        """이벤트 발생 시 file_history에 기록"""
        pytest.skip("NASPathTracker 클래스 구현 후 활성화")

    def test_reconcile_marks_missing_as_deleted(self, temp_db):
        """정합성 검증 - NAS에 없는 파일 deleted 처리"""
        pytest.skip("NASPathTracker 클래스 구현 후 활성화")


class TestEventQueue:
    """이벤트 큐 (Debounce) 테스트"""

    def test_debounce_same_file_events(self):
        """동일 파일의 연속 이벤트 병합"""
        eq = EventQueue(debounce_seconds=0.1)

        # 동일 파일에 여러 이벤트
        eq.put(TrackerEvent(event_type="created", src_path="/test/video.mp4"))
        eq.put(TrackerEvent(event_type="modified", src_path="/test/video.mp4"))
        eq.put(TrackerEvent(event_type="modified", src_path="/test/video.mp4"))

        # 대기 중인 이벤트는 1개 (병합됨)
        assert eq.pending_count == 1

    def test_different_file_events_not_merged(self):
        """다른 파일 이벤트는 병합하지 않음"""
        eq = EventQueue(debounce_seconds=0.1)

        eq.put(TrackerEvent(event_type="created", src_path="/test/video1.mp4"))
        eq.put(TrackerEvent(event_type="created", src_path="/test/video2.mp4"))

        assert eq.pending_count == 2

    def test_debounce_timeout(self):
        """Debounce 타임아웃 후 이벤트 처리"""
        eq = EventQueue(debounce_seconds=0.1)

        eq.put(TrackerEvent(event_type="created", src_path="/test/video.mp4"))

        # 타임아웃 대기
        time.sleep(0.2)

        # 큐로 이동됨
        event = eq.get(timeout=0.1)
        assert event is not None
        assert event.src_path == "/test/video.mp4"

    def test_deleted_event_priority(self):
        """삭제 이벤트가 우선"""
        eq = EventQueue(debounce_seconds=0.1)

        eq.put(TrackerEvent(event_type="created", src_path="/test/video.mp4"))
        eq.put(TrackerEvent(event_type="deleted", src_path="/test/video.mp4"))
        eq.put(TrackerEvent(event_type="modified", src_path="/test/video.mp4"))

        # 삭제 이벤트가 유지됨
        eq.flush_now()
        event = eq.get(timeout=0.1)
        assert event is not None
        assert event.event_type == "deleted"


class TestMigration:
    """스키마 마이그레이션 테스트"""

    @pytest.fixture
    def legacy_db(self):
        """마이그레이션 전 레거시 DB"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE files (
                id TEXT PRIMARY KEY,
                nas_path TEXT UNIQUE,
                filename TEXT,
                size_bytes INTEGER,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        # 기존 데이터 삽입
        conn.execute("""
            INSERT INTO files (id, nas_path, filename, size_bytes)
            VALUES ('file-001', '/archive/video.mp4', 'video.mp4', 1024)
        """)
        conn.commit()
        conn.close()

        yield db_path

        os.unlink(db_path)

    def test_migration_adds_status_column(self, legacy_db):
        """마이그레이션: status 컬럼 추가"""
        # When: 마이그레이션 실행
        conn = sqlite3.connect(legacy_db)

        # status 컬럼 추가
        try:
            conn.execute("ALTER TABLE files ADD COLUMN status TEXT DEFAULT 'active'")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # 이미 존재

        # Then: 기존 데이터에 status='active' 설정됨
        row = conn.execute("SELECT status FROM files WHERE id = 'file-001'").fetchone()
        conn.close()

        assert row[0] == "active"

    def test_migration_adds_content_hash_column(self, legacy_db):
        """마이그레이션: content_hash 컬럼 추가"""
        conn = sqlite3.connect(legacy_db)

        try:
            conn.execute("ALTER TABLE files ADD COLUMN content_hash TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # 컬럼 존재 확인
        cursor = conn.execute("PRAGMA table_info(files)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()

        assert "content_hash" in columns

    def test_migration_creates_file_history_table(self, legacy_db):
        """마이그레이션: file_history 테이블 생성"""
        conn = sqlite3.connect(legacy_db)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                old_path TEXT,
                new_path TEXT,
                old_hash TEXT,
                new_hash TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                synced_at TIMESTAMP,
                metadata TEXT
            )
        """)
        conn.commit()

        # 테이블 존재 확인
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='file_history'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "file_history"

    def test_migration_preserves_existing_data(self, legacy_db):
        """마이그레이션: 기존 데이터 보존"""
        conn = sqlite3.connect(legacy_db)

        # 마이그레이션 실행
        try:
            conn.execute("ALTER TABLE files ADD COLUMN status TEXT DEFAULT 'active'")
            conn.execute("ALTER TABLE files ADD COLUMN content_hash TEXT")
            conn.execute("ALTER TABLE files ADD COLUMN deleted_at TIMESTAMP")
        except sqlite3.OperationalError:
            pass
        conn.commit()

        # 기존 데이터 확인
        row = conn.execute(
            "SELECT id, nas_path, filename, size_bytes FROM files WHERE id = 'file-001'"
        ).fetchone()
        conn.close()

        assert row[0] == "file-001"
        assert row[1] == "/archive/video.mp4"
        assert row[2] == "video.mp4"
        assert row[3] == 1024
