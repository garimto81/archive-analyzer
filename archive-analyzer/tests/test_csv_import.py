"""CSV Import/Export 스크립트 테스트

Issue #13 - 로컬 환경 데이터 추가 로직
"""

import csv
import sqlite3
import tempfile
from pathlib import Path

import pytest

# 스크립트 모듈 임포트를 위한 경로 추가
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from import_csv import (
    ImportStats,
    parse_csv_row,
    TABLE_SCHEMAS,
    get_existing_ids,
)


class TestParseCSVRow:
    """CSV 행 파싱 테스트"""

    def test_parse_valid_hands_row(self):
        """유효한 hands 행 파싱"""
        row = {
            "id": "1001",
            "file_id": "file_001",
            "start_sec": "120",
            "end_sec": "180",
            "highlight_score": "3",
            "players": '["Phil Ivey", "Tom Dwan"]',
            "tags": "hero_call,bluff",
            "winner": "Phil Ivey",
        }

        schema = TABLE_SCHEMAS["hands"]
        result, error = parse_csv_row(row, schema, 1)

        assert error is None
        assert result is not None
        assert result["id"] == 1001
        assert result["file_id"] == "file_001"
        assert result["start_sec"] == 120.0
        assert result["end_sec"] == 180.0
        assert result["highlight_score"] == 3.0
        assert '"Phil Ivey"' in result["players"]
        assert '"hero_call"' in result["tags"]

    def test_parse_missing_required_field(self):
        """필수 필드 누락 시 에러"""
        row = {
            "id": "1001",
            "file_id": "",  # 필수 필드 누락
            "start_sec": "120",
            "end_sec": "180",
        }

        schema = TABLE_SCHEMAS["hands"]
        result, error = parse_csv_row(row, schema, 1)

        assert result is None
        assert error is not None
        assert "Missing required field" in error

    def test_parse_invalid_number(self):
        """잘못된 숫자 형식"""
        row = {
            "id": "not_a_number",
            "file_id": "file_001",
            "start_sec": "120",
            "end_sec": "180",
        }

        schema = TABLE_SCHEMAS["hands"]
        result, error = parse_csv_row(row, schema, 1)

        assert result is None
        assert error is not None
        assert "Invalid INTEGER" in error

    def test_parse_invalid_highlight_score(self):
        """유효하지 않은 highlight_score (범위 초과)"""
        row = {
            "id": "1001",
            "file_id": "file_001",
            "start_sec": "120",
            "end_sec": "180",
            "highlight_score": "5",  # 1-3 범위 초과
        }

        schema = TABLE_SCHEMAS["hands"]
        result, error = parse_csv_row(row, schema, 1)

        assert result is None
        assert error is not None
        assert "Validation failed" in error

    def test_parse_empty_optional_fields(self):
        """선택 필드가 비어있을 때"""
        row = {
            "id": "1001",
            "file_id": "file_001",
            "start_sec": "120",
            "end_sec": "180",
            "highlight_score": "",
            "players": "",
            "tags": "",
        }

        schema = TABLE_SCHEMAS["hands"]
        result, error = parse_csv_row(row, schema, 1)

        assert error is None
        assert result is not None
        assert result["highlight_score"] is None
        assert result["players"] == "[]"
        assert result["tags"] == "[]"


class TestPlayersSchema:
    """Players 테이블 파싱 테스트"""

    def test_parse_valid_player(self):
        """유효한 플레이어 행 파싱"""
        row = {
            "id": "1",
            "name": "Phil Ivey",
            "display_name": "Phil Ivey",
            "name_kr": "필 아이비",
            "country": "USA",
            "total_hands": "1000",
            "career_earnings": "43000000",
            "wsop_bracelets": "10",
        }

        schema = TABLE_SCHEMAS["players"]
        result, error = parse_csv_row(row, schema, 1)

        assert error is None
        assert result["id"] == 1
        assert result["name"] == "Phil Ivey"
        assert result["name_kr"] == "필 아이비"
        assert result["total_hands"] == 1000


class TestFilesSchema:
    """Files 테이블 파싱 테스트"""

    def test_parse_valid_file(self):
        """유효한 파일 행 파싱"""
        row = {
            "id": "101",
            "nas_path": "/ARCHIVE/WSOP/2024/main_event_d1.mp4",
            "filename": "main_event_d1.mp4",
            "codec": "h264",
            "resolution": "1920x1080",
            "duration_sec": "7200",
        }

        schema = TABLE_SCHEMAS["files"]
        result, error = parse_csv_row(row, schema, 1)

        assert error is None
        assert result["id"] == 101
        assert result["nas_path"] == "/ARCHIVE/WSOP/2024/main_event_d1.mp4"
        assert result["duration_sec"] == 7200.0


class TestContentsSchema:
    """Contents 테이블 파싱 테스트"""

    def test_parse_valid_content(self):
        """유효한 콘텐츠 행 파싱"""
        row = {
            "id": "1",
            "series_id": "1",
            "title": "WSOP 2024 Main Event Day 1",
            "episode_num": "1",
            "air_date": "2024-07-01",
            "duration_sec": "7200",
            "description": "Day 1 coverage",
        }

        schema = TABLE_SCHEMAS["contents"]
        result, error = parse_csv_row(row, schema, 1)

        assert error is None
        assert result["id"] == 1
        assert result["series_id"] == 1
        assert result["title"] == "WSOP 2024 Main Event Day 1"

    def test_parse_invalid_date(self):
        """잘못된 날짜 형식"""
        row = {
            "id": "1",
            "series_id": "1",
            "title": "Test",
            "air_date": "07-01-2024",  # 잘못된 형식
        }

        schema = TABLE_SCHEMAS["contents"]
        result, error = parse_csv_row(row, schema, 1)

        assert result is None
        assert error is not None
        assert "Validation failed" in error


class TestGetExistingIds:
    """기존 ID 조회 테스트"""

    def test_get_existing_ids_from_empty_table(self):
        """빈 테이블에서 ID 조회"""
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")

        ids = get_existing_ids(conn, "test")
        assert ids == set()

    def test_get_existing_ids_from_populated_table(self):
        """데이터가 있는 테이블에서 ID 조회"""
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'a'), (2, 'b'), (3, 'c')")

        ids = get_existing_ids(conn, "test")
        assert ids == {1, 2, 3}

    def test_get_existing_ids_nonexistent_table(self):
        """존재하지 않는 테이블"""
        conn = sqlite3.connect(":memory:")

        ids = get_existing_ids(conn, "nonexistent")
        assert ids == set()


class TestImportStats:
    """ImportStats 테스트"""

    def test_default_values(self):
        """기본값 확인"""
        stats = ImportStats()
        assert stats.total_rows == 0
        assert stats.imported == 0
        assert stats.skipped == 0
        assert stats.errors == 0
        assert stats.error_details == []
        assert stats.skipped_details == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
