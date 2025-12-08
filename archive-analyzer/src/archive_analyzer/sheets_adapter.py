"""Google Sheets 동기화 어댑터 - 기존 클래스 합성

Issue #49: Google Sheets 동기화 웹 대시보드 연동

기존 SheetsSyncService, ArchiveHandsSync를 합성하여
ISheetsSync 인터페이스를 구현합니다.

설계 원칙:
    - 기존 클래스 수정 없음 (Composition over Inheritance)
    - 선택적 서비스 주입 (None이면 graceful 처리)
    - 콜백 기반 상태 통지

Usage:
    from archive_analyzer.sheets_sync import SyncConfig, SheetsSyncService
    from archive_analyzer.archive_hands_sync import ArchiveHandsSync
    from archive_analyzer.sheets_adapter import SheetsSyncAdapter

    # 기존 서비스 인스턴스 생성
    sheets_service = SheetsSyncService(SyncConfig())
    hands_sync = ArchiveHandsSync()

    # 어댑터 생성 (합성)
    adapter = SheetsSyncAdapter(
        sheets_service=sheets_service,
        hands_sync=hands_sync,
    )

    # ISheetsSync 인터페이스 사용
    status = adapter.get_status()
    result = adapter.sync_to_sheets()
"""

import logging
from datetime import datetime
from typing import Any, List, Optional

from archive_analyzer.sheets_protocol import (
    ErrorCallback,
    SyncCallback,
    SyncDirection,
    SyncResult,
    SyncStatus,
)

logger = logging.getLogger(__name__)


class SheetsSyncAdapter:
    """Google Sheets 동기화 어댑터

    기존 SheetsSyncService, ArchiveHandsSync를 합성하여
    ISheetsSync 인터페이스를 구현합니다.

    Attributes:
        _sheets_service: SheetsSyncService 인스턴스 (Optional)
        _hands_sync: ArchiveHandsSync 인스턴스 (Optional)
        _on_complete: 동기화 완료 콜백
        _on_error: 에러 콜백
    """

    def __init__(
        self,
        sheets_service: Optional[Any] = None,  # SheetsSyncService
        hands_sync: Optional[Any] = None,  # ArchiveHandsSync
    ):
        """어댑터 초기화

        Args:
            sheets_service: SheetsSyncService 인스턴스 (Optional)
            hands_sync: ArchiveHandsSync 인스턴스 (Optional)

        Note:
            두 서비스 모두 Optional입니다. 서비스가 주입되지 않으면
            해당 기능은 graceful하게 비활성화됩니다.
        """
        self._sheets_service = sheets_service
        self._hands_sync = hands_sync
        self._on_complete: Optional[SyncCallback] = None
        self._on_error: Optional[ErrorCallback] = None
        self._last_sync_time: Optional[datetime] = None
        self._last_direction: Optional[SyncDirection] = None
        self._error_message: Optional[str] = None

    # =========================================================================
    # ISheetsSync 구현
    # =========================================================================

    def get_status(self) -> SyncStatus:
        """현재 동기화 상태 조회

        Returns:
            SyncStatus: 연결 상태, 마지막 동기화 시간 등
        """
        return SyncStatus(
            is_connected=self._is_connected(),
            last_sync_time=self._last_sync_time,
            last_sync_direction=self._last_direction,
            pending_changes=0,  # 필요시 구현
            error_message=self._error_message,
            sheets_api_quota_remaining=self._get_quota_remaining(),
        )

    def sync_to_sheets(self, tables: Optional[List[str]] = None) -> SyncResult:
        """DB → Sheets 동기화

        Args:
            tables: 동기화할 테이블 목록 (None이면 전체)

        Returns:
            SyncResult: 동기화 결과
        """
        if not self._sheets_service:
            return self._no_service_result(SyncDirection.DB_TO_SHEETS)

        start = datetime.now()
        try:
            logger.info(
                f"DB → Sheets 동기화 시작: {tables if tables else '전체 테이블'}"
            )

            # 기존 SheetsSyncService 사용
            # sync_all() 또는 sync_table() 호출
            if tables:
                for table in tables:
                    self._sheets_service.sync_table(table, direction="db_to_sheet")
            else:
                self._sheets_service.sync_all(direction="db_to_sheet")

            result = SyncResult(
                success=True,
                direction=SyncDirection.DB_TO_SHEETS,
                duration_seconds=(datetime.now() - start).total_seconds(),
                tables_synced=tables
                if tables
                else self._get_synced_tables(),
            )
            self._update_state(result)
            logger.info(f"DB → Sheets 동기화 완료: {result.duration_seconds:.1f}초")
            return result

        except Exception as e:
            return self._error_result(SyncDirection.DB_TO_SHEETS, e, start)

    def sync_from_sheets(self, tables: Optional[List[str]] = None) -> SyncResult:
        """Sheets → DB 동기화

        Args:
            tables: 동기화할 테이블 목록 (None이면 전체)

        Returns:
            SyncResult: 동기화 결과
        """
        if not self._sheets_service:
            return self._no_service_result(SyncDirection.SHEETS_TO_DB)

        start = datetime.now()
        try:
            logger.info(
                f"Sheets → DB 동기화 시작: {tables if tables else '전체 테이블'}"
            )

            # 기존 SheetsSyncService 사용
            if tables:
                for table in tables:
                    self._sheets_service.sync_table(table, direction="sheet_to_db")
            else:
                self._sheets_service.sync_all(direction="sheet_to_db")

            result = SyncResult(
                success=True,
                direction=SyncDirection.SHEETS_TO_DB,
                duration_seconds=(datetime.now() - start).total_seconds(),
                tables_synced=tables
                if tables
                else self._get_synced_tables(),
            )
            self._update_state(result)
            logger.info(f"Sheets → DB 동기화 완료: {result.duration_seconds:.1f}초")
            return result

        except Exception as e:
            return self._error_result(SyncDirection.SHEETS_TO_DB, e, start)

    def sync_hands(self) -> SyncResult:
        """Archive Sheet → hands 테이블 동기화

        Returns:
            SyncResult: 동기화 결과
        """
        if not self._hands_sync:
            return self._no_service_result(SyncDirection.HANDS_SYNC)

        start = datetime.now()
        try:
            logger.info("Archive Sheet → hands 동기화 시작")

            # 기존 ArchiveHandsSync 사용
            sync_result = self._hands_sync.sync_all()

            # 결과 파싱
            total_synced = 0
            if isinstance(sync_result, dict):
                total_synced = sync_result.get("total_synced", 0)
            elif isinstance(sync_result, int):
                total_synced = sync_result

            result = SyncResult(
                success=True,
                direction=SyncDirection.HANDS_SYNC,
                records_synced=total_synced,
                duration_seconds=(datetime.now() - start).total_seconds(),
                tables_synced=["hands", "hand_players", "hand_tags"],
            )
            self._update_state(result)
            logger.info(
                f"Archive Sheet → hands 동기화 완료: "
                f"{total_synced}건, {result.duration_seconds:.1f}초"
            )
            return result

        except Exception as e:
            return self._error_result(SyncDirection.HANDS_SYNC, e, start)

    def set_on_complete(self, callback: SyncCallback) -> None:
        """동기화 완료 콜백 등록

        Args:
            callback: 동기화 완료 시 호출될 콜백 함수
        """
        self._on_complete = callback

    def set_on_error(self, callback: ErrorCallback) -> None:
        """에러 콜백 등록

        Args:
            callback: 에러 발생 시 호출될 콜백 함수
        """
        self._on_error = callback

    # =========================================================================
    # 추가 편의 메서드
    # =========================================================================

    def sync_bidirectional(self, tables: Optional[List[str]] = None) -> SyncResult:
        """양방향 동기화 (Sheets 우선)

        1. Sheets → DB 동기화
        2. DB → Sheets 동기화

        Args:
            tables: 동기화할 테이블 목록 (None이면 전체)

        Returns:
            SyncResult: 통합 동기화 결과
        """
        if not self._sheets_service:
            return self._no_service_result(SyncDirection.BIDIRECTIONAL)

        start = datetime.now()
        total_synced = 0
        all_tables: List[str] = []

        try:
            logger.info("양방향 동기화 시작 (Sheets 우선)")

            # 1. Sheets → DB
            result1 = self.sync_from_sheets(tables)
            total_synced += result1.records_synced
            all_tables.extend(result1.tables_synced)

            # 2. DB → Sheets
            result2 = self.sync_to_sheets(tables)
            total_synced += result2.records_synced
            all_tables.extend(result2.tables_synced)

            result = SyncResult(
                success=result1.success and result2.success,
                direction=SyncDirection.BIDIRECTIONAL,
                records_synced=total_synced,
                duration_seconds=(datetime.now() - start).total_seconds(),
                tables_synced=list(set(all_tables)),
                errors=result1.errors + result2.errors,
            )
            self._update_state(result)
            return result

        except Exception as e:
            return self._error_result(SyncDirection.BIDIRECTIONAL, e, start)

    def is_available(self) -> bool:
        """서비스 사용 가능 여부

        Returns:
            bool: 하나 이상의 서비스가 주입되었으면 True
        """
        return self._sheets_service is not None or self._hands_sync is not None

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _is_connected(self) -> bool:
        """연결 상태 확인"""
        if self._sheets_service:
            try:
                # SheetsSyncService의 sheets_client 속성 확인
                client = getattr(self._sheets_service, "sheets_client", None)
                if client:
                    spreadsheet = getattr(client, "spreadsheet", None)
                    return spreadsheet is not None
            except Exception:
                pass
        return False

    def _get_quota_remaining(self) -> int:
        """API 쿼터 잔여량 조회 (추정치)"""
        if self._sheets_service:
            try:
                client = getattr(self._sheets_service, "sheets_client", None)
                if client:
                    # _request_count 속성 사용 (SheetsClient 내부)
                    request_count = getattr(client, "_request_count", 0)
                    return max(0, 60 - request_count)
            except Exception:
                pass
        return 60  # 기본값

    def _get_synced_tables(self) -> List[str]:
        """동기화 대상 테이블 목록"""
        if self._sheets_service:
            try:
                config = getattr(self._sheets_service, "config", None)
                if config:
                    return getattr(config, "tables_to_sync", [])
            except Exception:
                pass
        return []

    def _update_state(self, result: SyncResult) -> None:
        """상태 업데이트 및 콜백 호출"""
        self._last_sync_time = datetime.now()
        self._last_direction = result.direction
        self._error_message = None if result.success else (result.errors[0] if result.errors else None)

        if self._on_complete:
            try:
                self._on_complete(result)
            except Exception as e:
                logger.warning(f"콜백 실행 오류: {e}")

    def _no_service_result(self, direction: SyncDirection) -> SyncResult:
        """서비스 미설정 결과"""
        error_msg = "Service not configured"
        self._error_message = error_msg
        logger.warning(f"Sheets 동기화 스킵: {error_msg}")

        return SyncResult(
            success=False,
            direction=direction,
            errors=[error_msg],
        )

    def _error_result(
        self, direction: SyncDirection, error: Exception, start: datetime
    ) -> SyncResult:
        """에러 결과 생성"""
        error_msg = str(error)
        self._error_message = error_msg
        logger.error(f"Sheets 동기화 오류: {error_msg}")

        if self._on_error:
            try:
                self._on_error(error)
            except Exception as e:
                logger.warning(f"에러 콜백 실행 오류: {e}")

        return SyncResult(
            success=False,
            direction=direction,
            duration_seconds=(datetime.now() - start).total_seconds(),
            errors=[error_msg],
        )


# =============================================================================
# Factory 함수
# =============================================================================


def create_sheets_adapter(
    enable_sheets_sync: bool = True,
    enable_hands_sync: bool = True,
) -> Optional[SheetsSyncAdapter]:
    """SheetsSyncAdapter 팩토리 함수

    환경 설정에 따라 어댑터를 생성합니다.
    서비스 초기화 실패 시 None을 반환합니다.

    Args:
        enable_sheets_sync: SheetsSyncService 활성화 여부
        enable_hands_sync: ArchiveHandsSync 활성화 여부

    Returns:
        SheetsSyncAdapter: 성공 시 어댑터 인스턴스
        None: 모든 서비스 초기화 실패 시

    Usage:
        adapter = create_sheets_adapter()
        if adapter:
            status = adapter.get_status()
    """
    sheets_service = None
    hands_sync = None

    # SheetsSyncService 초기화 시도
    if enable_sheets_sync:
        try:
            from archive_analyzer.sheets_sync import SheetsSyncService, SyncConfig

            config = SyncConfig()
            sheets_service = SheetsSyncService(config)
            logger.info("SheetsSyncService 초기화 성공")
        except Exception as e:
            logger.warning(f"SheetsSyncService 초기화 실패: {e}")

    # ArchiveHandsSync 초기화 시도
    if enable_hands_sync:
        try:
            from archive_analyzer.archive_hands_sync import ArchiveHandsSync

            hands_sync = ArchiveHandsSync()
            logger.info("ArchiveHandsSync 초기화 성공")
        except Exception as e:
            logger.warning(f"ArchiveHandsSync 초기화 실패: {e}")

    # 하나 이상 성공하면 어댑터 반환
    if sheets_service or hands_sync:
        return SheetsSyncAdapter(
            sheets_service=sheets_service,
            hands_sync=hands_sync,
        )

    logger.warning("모든 Sheets 서비스 초기화 실패, 어댑터 생성 안함")
    return None
