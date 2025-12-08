"""Google Sheets 연동 프로토콜 - 의존성 역전을 위한 인터페이스

Issue #49: Google Sheets 동기화 웹 대시보드 연동

web/app.py가 sheets 모듈에 직접 의존하지 않도록
Protocol 기반 인터페이스를 정의합니다.

Usage:
    from archive_analyzer.sheets_protocol import ISheetsSync, SyncStatus

    # web/app.py에서 Protocol 타입만 사용
    sheets_sync: Optional[ISheetsSync] = None

    # 구체적인 구현은 SheetsSyncAdapter에서 제공
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, List, Optional, Protocol, runtime_checkable


class SyncDirection(Enum):
    """동기화 방향"""

    DB_TO_SHEETS = "db_to_sheets"
    SHEETS_TO_DB = "sheets_to_db"
    BIDIRECTIONAL = "bidirectional"
    HANDS_SYNC = "hands_sync"  # Archive Sheet → hands 테이블


@dataclass
class SyncStatus:
    """동기화 상태

    Attributes:
        is_connected: Google Sheets 연결 상태
        last_sync_time: 마지막 동기화 시간
        last_sync_direction: 마지막 동기화 방향
        pending_changes: 대기 중인 변경 사항 수
        error_message: 에러 메시지 (있을 경우)
        sheets_api_quota_remaining: API 쿼터 잔여량 (분당 60회)
    """

    is_connected: bool = False
    last_sync_time: Optional[datetime] = None
    last_sync_direction: Optional[SyncDirection] = None
    pending_changes: int = 0
    error_message: Optional[str] = None
    sheets_api_quota_remaining: int = 60

    def to_dict(self) -> dict:
        """JSON 직렬화용 딕셔너리 변환"""
        return {
            "is_connected": self.is_connected,
            "last_sync_time": self.last_sync_time.isoformat()
            if self.last_sync_time
            else None,
            "last_sync_direction": self.last_sync_direction.value
            if self.last_sync_direction
            else None,
            "pending_changes": self.pending_changes,
            "error_message": self.error_message,
            "sheets_api_quota_remaining": self.sheets_api_quota_remaining,
        }


@dataclass
class SyncResult:
    """동기화 결과

    Attributes:
        success: 성공 여부
        direction: 동기화 방향
        records_synced: 동기화된 레코드 수
        records_failed: 실패한 레코드 수
        duration_seconds: 소요 시간 (초)
        errors: 에러 목록
        tables_synced: 동기화된 테이블 목록
    """

    success: bool
    direction: SyncDirection
    records_synced: int = 0
    records_failed: int = 0
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)
    tables_synced: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """JSON 직렬화용 딕셔너리 변환"""
        return {
            "success": self.success,
            "direction": self.direction.value,
            "records_synced": self.records_synced,
            "records_failed": self.records_failed,
            "duration_seconds": round(self.duration_seconds, 2),
            "errors": self.errors,
            "tables_synced": self.tables_synced,
        }


# 콜백 타입 정의
SyncCallback = Callable[[SyncResult], None]
ErrorCallback = Callable[[Exception], None]


@runtime_checkable
class ISheetsSync(Protocol):
    """Google Sheets 동기화 인터페이스

    web/app.py는 이 Protocol에만 의존합니다.
    구체적인 구현(SheetsSyncAdapter)은 런타임에 주입됩니다.

    설계 원칙:
        - web/app.py는 sheets_sync, archive_hands_sync를 직접 import하지 않음
        - 모든 Sheets 연동은 이 Protocol을 통해 이루어짐
        - Protocol은 @runtime_checkable로 isinstance() 체크 가능

    Usage:
        def handle_sheets(sync: ISheetsSync):
            status = sync.get_status()
            if status.is_connected:
                result = sync.sync_to_sheets()
    """

    def get_status(self) -> SyncStatus:
        """현재 동기화 상태 조회

        Returns:
            SyncStatus: 연결 상태, 마지막 동기화 시간 등
        """
        ...

    def sync_to_sheets(self, tables: Optional[List[str]] = None) -> SyncResult:
        """DB → Sheets 동기화

        pokervod.db의 데이터를 Google Sheets로 동기화합니다.

        Args:
            tables: 동기화할 테이블 목록 (None이면 전체)

        Returns:
            SyncResult: 동기화 결과
        """
        ...

    def sync_from_sheets(self, tables: Optional[List[str]] = None) -> SyncResult:
        """Sheets → DB 동기화

        Google Sheets의 변경사항을 pokervod.db로 동기화합니다.

        Args:
            tables: 동기화할 테이블 목록 (None이면 전체)

        Returns:
            SyncResult: 동기화 결과
        """
        ...

    def sync_hands(self) -> SyncResult:
        """Archive Sheet → hands 테이블 동기화

        아카이브팀 Google Sheet의 데이터를 hands 테이블로 동기화합니다.

        Returns:
            SyncResult: 동기화 결과
        """
        ...

    def set_on_complete(self, callback: SyncCallback) -> None:
        """동기화 완료 콜백 등록

        Args:
            callback: 동기화 완료 시 호출될 콜백 함수
        """
        ...

    def set_on_error(self, callback: ErrorCallback) -> None:
        """에러 콜백 등록

        Args:
            callback: 에러 발생 시 호출될 콜백 함수
        """
        ...


# 타입 별칭 (편의성)
SheetsSyncProtocol = ISheetsSync
