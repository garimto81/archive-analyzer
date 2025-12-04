"""NAS 자동 동기화 테스트

Issue #17: NAS 신규 데이터 자동 감지 및 DB 등록
"""

import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# smbclient 의존성 Mock (모든 서브모듈 포함)
_mock_smbclient = MagicMock()
sys.modules["smbclient"] = _mock_smbclient
sys.modules["smbclient.shutil"] = MagicMock()
sys.modules["smbclient.path"] = MagicMock()
sys.modules["smbprotocol"] = MagicMock()
sys.modules["smbprotocol.exceptions"] = MagicMock()

from archive_analyzer.nas_auto_sync import (
    AutoSyncConfig,
    IncrementalScanResult,
    NASAutoSync,
)


class TestAutoSyncConfig:
    """AutoSyncConfig 테스트"""

    def test_default_values(self):
        """기본값 확인"""
        config = AutoSyncConfig()

        assert config.smb_server == "10.10.100.122"
        assert config.smb_share == "docker"
        assert config.archive_path == "GGPNAs/ARCHIVE"
        assert config.sync_interval_seconds == 1800

    def test_env_override(self, monkeypatch):
        """환경변수 오버라이드"""
        monkeypatch.setenv("SMB_SERVER", "192.168.1.100")
        monkeypatch.setenv("SYNC_INTERVAL", "600")

        config = AutoSyncConfig()

        assert config.smb_server == "192.168.1.100"
        assert config.sync_interval_seconds == 600


class TestIncrementalScanResult:
    """IncrementalScanResult 테스트"""

    def test_default_values(self):
        """기본값 확인"""
        result = IncrementalScanResult()

        assert result.new_files == 0
        assert result.updated_files == 0
        assert result.skipped_files == 0
        assert result.errors == []

    def test_str_format(self):
        """문자열 포맷"""
        result = IncrementalScanResult(
            new_files=10, skipped_files=100, duration_seconds=5.5
        )

        str_result = str(result)
        assert "New: 10" in str_result
        assert "Skipped: 100" in str_result
        assert "5.5s" in str_result


class TestNASAutoSync:
    """NASAutoSync 테스트"""

    def test_normalize_path(self):
        """경로 정규화"""
        config = AutoSyncConfig()
        sync = NASAutoSync(config)

        # 백슬래시 → 슬래시
        assert sync._normalize_path("path\\to\\file") == "path/to/file"

        # 소문자 변환
        assert sync._normalize_path("PATH/TO/FILE") == "path/to/file"

    @patch("archive_analyzer.nas_auto_sync.SMBConnector")
    @patch("archive_analyzer.nas_auto_sync.Database")
    def test_connect(self, mock_db, mock_smb):
        """연결 테스트"""
        config = AutoSyncConfig()
        sync = NASAutoSync(config)

        # Mock 설정
        mock_connector = MagicMock()
        mock_connector.is_connected = False
        mock_smb.return_value = mock_connector

        mock_database = MagicMock()
        mock_db.return_value = mock_database

        # 연결
        sync._connect()

        # SMB 연결 확인
        mock_connector.connect.assert_called_once()

    @patch("archive_analyzer.nas_auto_sync.SMBConnector")
    @patch("archive_analyzer.nas_auto_sync.Database")
    def test_load_existing_paths(self, mock_db, mock_smb):
        """기존 경로 로드 테스트"""
        config = AutoSyncConfig()
        sync = NASAutoSync(config)

        # Mock DB 설정
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("/path/to/file1.mp4",),
            ("/path/to/file2.mp4",),
        ]
        mock_connection.execute.return_value = mock_cursor

        mock_database = MagicMock()
        mock_database._get_connection.return_value = mock_connection
        sync.database = mock_database

        # 실행
        paths = sync._load_existing_paths()

        # 검증
        assert len(paths) == 2
        assert "/path/to/file1.mp4" in paths

    def test_incremental_scan_result_aggregation(self):
        """증분 스캔 결과 집계"""
        result = IncrementalScanResult()

        result.new_files = 5
        result.skipped_files = 95
        result.errors.append("Error 1")
        result.duration_seconds = 10.0

        assert result.new_files == 5
        assert len(result.errors) == 1


class TestIntegration:
    """통합 테스트"""

    @pytest.fixture
    def temp_db(self):
        """임시 DB 생성"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        # 스키마 생성
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE files (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE,
                filename TEXT,
                extension TEXT,
                size_bytes INTEGER,
                modified_at TEXT,
                file_type TEXT,
                parent_folder TEXT,
                scan_status TEXT
            )
        """
        )
        conn.commit()
        conn.close()

        yield db_path

        # 정리 (Windows에서 파일 잠금 대기)
        import gc
        import time

        gc.collect()
        time.sleep(0.1)
        try:
            Path(db_path).unlink(missing_ok=True)
        except PermissionError:
            pass  # Windows에서 파일 잠금 시 무시

    def test_save_batch(self, temp_db):
        """배치 저장 테스트"""
        from archive_analyzer.database import Database

        config = AutoSyncConfig(archive_db=temp_db)
        sync = NASAutoSync(config)
        sync.database = Database(temp_db)

        batch = [
            {
                "path": "/test/file1.mp4",
                "filename": "file1.mp4",
                "extension": ".mp4",
                "size_bytes": 1000,
                "modified_at": None,
                "file_type": "video",
                "parent_folder": "/test",
                "scan_status": "scanned",
            },
            {
                "path": "/test/file2.mp4",
                "filename": "file2.mp4",
                "extension": ".mp4",
                "size_bytes": 2000,
                "modified_at": None,
                "file_type": "video",
                "parent_folder": "/test",
                "scan_status": "scanned",
            },
        ]

        sync._save_batch(batch)

        # 검증
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT COUNT(*) FROM files")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
