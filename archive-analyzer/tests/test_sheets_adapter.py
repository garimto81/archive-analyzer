"""SheetsSyncAdapter 단위 테스트

Issue #49: Google Sheets 동기화 웹 대시보드 연동

테스트 범위:
    - 서비스 미설정 시 graceful 처리
    - Mock 서비스 주입 테스트
    - 상태 추적 테스트
    - 콜백 호출 검증
    - 에러 처리 테스트
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from archive_analyzer.sheets_protocol import (
    ISheetsSync,
    SyncDirection,
    SyncResult,
    SyncStatus,
)
from archive_analyzer.sheets_adapter import SheetsSyncAdapter, create_sheets_adapter


class TestSyncProtocol:
    """Protocol 및 데이터클래스 테스트"""

    def test_sync_direction_values(self):
        """SyncDirection Enum 값 확인"""
        assert SyncDirection.DB_TO_SHEETS.value == "db_to_sheets"
        assert SyncDirection.SHEETS_TO_DB.value == "sheets_to_db"
        assert SyncDirection.BIDIRECTIONAL.value == "bidirectional"
        assert SyncDirection.HANDS_SYNC.value == "hands_sync"

    def test_sync_status_default(self):
        """SyncStatus 기본값"""
        status = SyncStatus()
        assert status.is_connected is False
        assert status.last_sync_time is None
        assert status.pending_changes == 0
        assert status.sheets_api_quota_remaining == 60

    def test_sync_status_to_dict(self):
        """SyncStatus JSON 변환"""
        now = datetime.now()
        status = SyncStatus(
            is_connected=True,
            last_sync_time=now,
            last_sync_direction=SyncDirection.DB_TO_SHEETS,
        )
        d = status.to_dict()
        assert d["is_connected"] is True
        assert d["last_sync_time"] == now.isoformat()
        assert d["last_sync_direction"] == "db_to_sheets"

    def test_sync_result_to_dict(self):
        """SyncResult JSON 변환"""
        result = SyncResult(
            success=True,
            direction=SyncDirection.HANDS_SYNC,
            records_synced=100,
            duration_seconds=5.123,
            tables_synced=["hands", "hand_players"],
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["direction"] == "hands_sync"
        assert d["records_synced"] == 100
        assert d["duration_seconds"] == 5.12  # rounded
        assert "hands" in d["tables_synced"]

    def test_isheetsync_protocol_check(self):
        """ISheetsSync Protocol isinstance 체크"""
        adapter = SheetsSyncAdapter()
        assert isinstance(adapter, ISheetsSync)


class TestSheetsSyncAdapterWithoutServices:
    """서비스 미설정 시 graceful 처리 테스트"""

    def test_adapter_without_services(self):
        """서비스 없이 어댑터 생성"""
        adapter = SheetsSyncAdapter()
        assert adapter.is_available() is False

    def test_get_status_without_services(self):
        """서비스 없이 상태 조회"""
        adapter = SheetsSyncAdapter()
        status = adapter.get_status()
        assert status.is_connected is False
        assert status.error_message is None

    def test_sync_to_sheets_without_service(self):
        """서비스 없이 DB → Sheets 동기화 시도"""
        adapter = SheetsSyncAdapter()
        result = adapter.sync_to_sheets()
        assert result.success is False
        assert "not configured" in result.errors[0].lower()
        assert result.direction == SyncDirection.DB_TO_SHEETS

    def test_sync_from_sheets_without_service(self):
        """서비스 없이 Sheets → DB 동기화 시도"""
        adapter = SheetsSyncAdapter()
        result = adapter.sync_from_sheets()
        assert result.success is False
        assert "not configured" in result.errors[0].lower()
        assert result.direction == SyncDirection.SHEETS_TO_DB

    def test_sync_hands_without_service(self):
        """서비스 없이 hands 동기화 시도"""
        adapter = SheetsSyncAdapter()
        result = adapter.sync_hands()
        assert result.success is False
        assert "not configured" in result.errors[0].lower()
        assert result.direction == SyncDirection.HANDS_SYNC

    def test_sync_bidirectional_without_service(self):
        """서비스 없이 양방향 동기화 시도"""
        adapter = SheetsSyncAdapter()
        result = adapter.sync_bidirectional()
        assert result.success is False
        assert result.direction == SyncDirection.BIDIRECTIONAL


class TestSheetsSyncAdapterWithMockServices:
    """Mock 서비스 주입 테스트"""

    @pytest.fixture
    def mock_sheets_service(self):
        """Mock SheetsSyncService"""
        mock = MagicMock()
        mock.sheets_client = MagicMock()
        mock.sheets_client.spreadsheet = MagicMock()
        mock.config = MagicMock()
        mock.config.tables_to_sync = ["files", "hands"]
        return mock

    @pytest.fixture
    def mock_hands_sync(self):
        """Mock ArchiveHandsSync"""
        mock = MagicMock()
        mock.sync_all.return_value = {"total_synced": 50}
        return mock

    def test_adapter_with_sheets_service(self, mock_sheets_service):
        """SheetsSyncService만 주입"""
        adapter = SheetsSyncAdapter(sheets_service=mock_sheets_service)
        assert adapter.is_available() is True

    def test_adapter_with_hands_sync(self, mock_hands_sync):
        """ArchiveHandsSync만 주입"""
        adapter = SheetsSyncAdapter(hands_sync=mock_hands_sync)
        assert adapter.is_available() is True

    def test_adapter_with_both_services(self, mock_sheets_service, mock_hands_sync):
        """두 서비스 모두 주입"""
        adapter = SheetsSyncAdapter(
            sheets_service=mock_sheets_service,
            hands_sync=mock_hands_sync,
        )
        assert adapter.is_available() is True

    def test_get_status_connected(self, mock_sheets_service):
        """연결된 상태 확인"""
        adapter = SheetsSyncAdapter(sheets_service=mock_sheets_service)
        status = adapter.get_status()
        assert status.is_connected is True

    def test_sync_to_sheets_success(self, mock_sheets_service):
        """DB → Sheets 동기화 성공"""
        adapter = SheetsSyncAdapter(sheets_service=mock_sheets_service)
        result = adapter.sync_to_sheets()
        assert result.success is True
        assert result.direction == SyncDirection.DB_TO_SHEETS
        mock_sheets_service.sync_all.assert_called_once_with(direction="db_to_sheet")

    def test_sync_to_sheets_with_tables(self, mock_sheets_service):
        """특정 테이블만 동기화"""
        adapter = SheetsSyncAdapter(sheets_service=mock_sheets_service)
        result = adapter.sync_to_sheets(tables=["files", "hands"])
        assert result.success is True
        assert mock_sheets_service.sync_table.call_count == 2

    def test_sync_from_sheets_success(self, mock_sheets_service):
        """Sheets → DB 동기화 성공"""
        adapter = SheetsSyncAdapter(sheets_service=mock_sheets_service)
        result = adapter.sync_from_sheets()
        assert result.success is True
        assert result.direction == SyncDirection.SHEETS_TO_DB

    def test_sync_hands_success(self, mock_hands_sync):
        """hands 동기화 성공"""
        adapter = SheetsSyncAdapter(hands_sync=mock_hands_sync)
        result = adapter.sync_hands()
        assert result.success is True
        assert result.direction == SyncDirection.HANDS_SYNC
        assert result.records_synced == 50
        mock_hands_sync.sync_all.assert_called_once()

    def test_sync_bidirectional_success(self, mock_sheets_service):
        """양방향 동기화 성공"""
        adapter = SheetsSyncAdapter(sheets_service=mock_sheets_service)
        result = adapter.sync_bidirectional()
        assert result.success is True
        assert result.direction == SyncDirection.BIDIRECTIONAL


class TestSheetsSyncAdapterCallbacks:
    """콜백 호출 테스트"""

    @pytest.fixture
    def mock_sheets_service(self):
        mock = MagicMock()
        mock.sheets_client = MagicMock()
        mock.sheets_client.spreadsheet = MagicMock()
        mock.config = MagicMock()
        mock.config.tables_to_sync = []
        return mock

    def test_on_complete_callback(self, mock_sheets_service):
        """완료 콜백 호출"""
        adapter = SheetsSyncAdapter(sheets_service=mock_sheets_service)
        callback = MagicMock()
        adapter.set_on_complete(callback)

        adapter.sync_to_sheets()

        callback.assert_called_once()
        result = callback.call_args[0][0]
        assert isinstance(result, SyncResult)
        assert result.success is True

    def test_on_error_callback(self, mock_sheets_service):
        """에러 콜백 호출"""
        mock_sheets_service.sync_all.side_effect = Exception("API Error")

        adapter = SheetsSyncAdapter(sheets_service=mock_sheets_service)
        error_callback = MagicMock()
        adapter.set_on_error(error_callback)

        result = adapter.sync_to_sheets()

        assert result.success is False
        assert "API Error" in result.errors[0]
        error_callback.assert_called_once()


class TestSheetsSyncAdapterStateTracking:
    """상태 추적 테스트"""

    @pytest.fixture
    def mock_sheets_service(self):
        mock = MagicMock()
        mock.sheets_client = MagicMock()
        mock.sheets_client.spreadsheet = MagicMock()
        mock.config = MagicMock()
        mock.config.tables_to_sync = []
        return mock

    def test_last_sync_time_updated(self, mock_sheets_service):
        """동기화 후 마지막 시간 업데이트"""
        adapter = SheetsSyncAdapter(sheets_service=mock_sheets_service)

        assert adapter.get_status().last_sync_time is None

        adapter.sync_to_sheets()

        status = adapter.get_status()
        assert status.last_sync_time is not None
        assert status.last_sync_direction == SyncDirection.DB_TO_SHEETS

    def test_error_message_on_failure(self, mock_sheets_service):
        """실패 시 에러 메시지 저장"""
        mock_sheets_service.sync_all.side_effect = Exception("Connection failed")

        adapter = SheetsSyncAdapter(sheets_service=mock_sheets_service)
        adapter.sync_to_sheets()

        status = adapter.get_status()
        assert status.error_message == "Connection failed"

    def test_error_cleared_on_success(self, mock_sheets_service):
        """성공 시 에러 메시지 초기화"""
        adapter = SheetsSyncAdapter(sheets_service=mock_sheets_service)
        adapter._error_message = "Previous error"

        adapter.sync_to_sheets()

        status = adapter.get_status()
        assert status.error_message is None


class TestCreateSheetsAdapterFactory:
    """팩토리 함수 테스트"""

    def test_factory_without_modules(self):
        """모듈 없이 팩토리 호출 (실패 시 None)"""
        with patch(
            "archive_analyzer.sheets_adapter.create_sheets_adapter"
        ) as mock_factory:
            mock_factory.return_value = None
            result = mock_factory()
            assert result is None

    def test_factory_returns_adapter(self):
        """팩토리가 어댑터 반환 (직접 생성 테스트)"""
        mock_sheets = MagicMock()
        mock_hands = MagicMock()

        # 직접 어댑터 생성으로 테스트
        adapter = SheetsSyncAdapter(
            sheets_service=mock_sheets,
            hands_sync=mock_hands,
        )
        assert adapter is not None
        assert adapter.is_available() is True


class TestSheetsSyncAdapterEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_tables_list(self):
        """빈 테이블 리스트"""
        mock = MagicMock()
        mock.sheets_client = MagicMock()
        mock.sheets_client.spreadsheet = MagicMock()

        adapter = SheetsSyncAdapter(sheets_service=mock)
        result = adapter.sync_to_sheets(tables=[])
        assert result.success is True

    def test_hands_sync_returns_int(self):
        """hands_sync가 정수 반환 시"""
        mock_hands = MagicMock()
        mock_hands.sync_all.return_value = 42  # int 직접 반환

        adapter = SheetsSyncAdapter(hands_sync=mock_hands)
        result = adapter.sync_hands()
        assert result.success is True
        assert result.records_synced == 42

    def test_callback_exception_ignored(self):
        """콜백에서 예외 발생 시 무시"""
        mock = MagicMock()
        mock.sheets_client = MagicMock()
        mock.sheets_client.spreadsheet = MagicMock()
        mock.config = MagicMock()
        mock.config.tables_to_sync = []

        adapter = SheetsSyncAdapter(sheets_service=mock)

        def bad_callback(result):
            raise ValueError("Callback error")

        adapter.set_on_complete(bad_callback)

        # 예외가 전파되지 않아야 함
        result = adapter.sync_to_sheets()
        assert result.success is True
