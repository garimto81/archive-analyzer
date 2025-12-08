# Google Sheets 연동 설계 - NAS 모니터링 앱

**버전**: 1.0.0
**작성일**: 2025-12-08
**원칙**: 독립적 모듈, 최소 결합, 기존 클래스 재사용

---

## 1. 현재 아키텍처

### 1.1 기존 컴포넌트

```
┌─────────────────────────────────────────────────────────────────────┐
│                        현재 시스템 구조                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [NAS Monitoring Web App]          [Sheets Sync Services]           │
│  ─────────────────────────         ─────────────────────            │
│  web/app.py                        sheets_sync.py                   │
│    └── ServiceState                  ├── SheetsClient              │
│    └── WebConfig                     ├── DatabaseClient            │
│    └── run_sync_task()               └── SheetsSyncService         │
│           │                                                         │
│           └──────────────┐         archive_hands_sync.py            │
│                          │           └── ArchiveHandsSync           │
│  [NAS Auto Sync]         │                                          │
│  ─────────────────       │                                          │
│  nas_auto_sync.py        │                                          │
│    └── NASAutoSync  ◄────┘                                          │
│    └── AutoSyncConfig                                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 기존 클래스 (재사용 대상)

| 클래스 | 파일 | 역할 | 재사용 방법 |
|--------|------|------|-------------|
| `SheetsClient` | sheets_sync.py:120-205 | Google Auth, Rate Limit, Retry | 그대로 사용 |
| `SheetsSyncService` | sheets_sync.py:358-716 | DB ↔ Sheets 양방향 동기화 | 인스턴스 주입 |
| `ArchiveHandsSync` | archive_hands_sync.py:150-793 | Archive Sheet → hands 동기화 | 인스턴스 주입 |
| `SyncConfig` | sheets_sync.py:43-113 | Sheets 설정 | 환경변수 로드 활용 |

---

## 2. 설계 원칙

### 2.1 핵심 제약

```
┌────────────────────────────────────────────────────────────────┐
│  ⚠️ 절대 금지                                                   │
├────────────────────────────────────────────────────────────────┤
│  ❌ 새로운 Sheets 클라이언트 클래스 생성                         │
│  ❌ SheetsClient/SheetsSyncService 내부 수정                    │
│  ❌ web/app.py에서 sheets 모듈 직접 import                      │
│  ❌ 기존 클래스에 web 의존성 추가                                │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 설계 패턴

| 패턴 | 적용 방법 |
|------|----------|
| **Dependency Injection** | 서비스 인스턴스를 외부에서 주입 |
| **Protocol/Interface** | ABC 또는 Protocol로 계약 정의 |
| **Event-Driven** | 콜백 함수로 상태 변경 통지 |
| **Adapter Pattern** | 기존 클래스를 감싸는 어댑터 생성 |

---

## 3. 제안 아키텍처

### 3.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────────┐
│                      신규 연동 아키텍처                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                      web/app.py                            │    │
│  │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │    │
│  │  │ ServiceState │   │ WebConfig    │   │ FastAPI App  │   │    │
│  │  └──────────────┘   └──────────────┘   └──────────────┘   │    │
│  │          │                                    │            │    │
│  │          │  (Optional DI)                     │            │    │
│  │          ▼                                    │            │    │
│  │  ┌─────────────────────────┐                  │            │    │
│  │  │ sheets_service: ISheetsSync │◄─────────────┘            │    │
│  │  │ (Protocol/Interface)       │  API 호출                  │    │
│  │  └─────────────────────────┘                               │    │
│  └────────────────────────────────────────────────────────────┘    │
│           │                                                         │
│           │ (인터페이스만 의존)                                      │
│           ▼                                                         │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │               sheets_adapter.py (신규)                      │    │
│  │  ┌──────────────────────────────────────────────────────┐  │    │
│  │  │                 SheetsSyncAdapter                    │  │    │
│  │  │  implements ISheetsSync                              │  │    │
│  │  │  ─────────────────────────────────                   │  │    │
│  │  │  - sheets_service: SheetsSyncService  (주입)         │  │    │
│  │  │  - hands_sync: ArchiveHandsSync       (주입)         │  │    │
│  │  │  - on_sync_complete: Callable         (콜백)         │  │    │
│  │  │                                                      │  │    │
│  │  │  + get_sync_status() -> SyncStatus                   │  │    │
│  │  │  + trigger_sheets_sync(direction) -> Result          │  │    │
│  │  │  + trigger_hands_sync() -> Result                    │  │    │
│  │  └──────────────────────────────────────────────────────┘  │    │
│  └────────────────────────────────────────────────────────────┘    │
│           │                        │                                │
│           │ (합성)                 │ (합성)                         │
│           ▼                        ▼                                │
│  ┌────────────────────┐   ┌─────────────────────┐                  │
│  │  SheetsSyncService │   │  ArchiveHandsSync   │                  │
│  │  (기존 그대로)      │   │  (기존 그대로)      │                  │
│  └────────────────────┘   └─────────────────────┘                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 의존성 방향

```
                    의존성 흐름 (의존성 역전 원칙)

web/app.py ──────► ISheetsSync (Protocol)
     │                    ▲
     │                    │ implements
     │                    │
     └─────────────► SheetsSyncAdapter
                          │
                          │ 합성 (Composition)
                          ▼
              ┌─────────────────────────┐
              │   SheetsSyncService     │
              │   ArchiveHandsSync      │
              │   (기존 클래스)          │
              └─────────────────────────┘
```

---

## 4. 인터페이스 정의

### 4.1 Protocol 정의 (sheets_protocol.py)

```python
# src/archive_analyzer/sheets_protocol.py
"""Google Sheets 연동 프로토콜 - 의존성 역전을 위한 인터페이스"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol


class SyncDirection(Enum):
    """동기화 방향"""
    DB_TO_SHEETS = "db_to_sheets"
    SHEETS_TO_DB = "sheets_to_db"
    BIDIRECTIONAL = "bidirectional"


@dataclass
class SyncStatus:
    """동기화 상태"""
    is_connected: bool = False
    last_sync_time: Optional[datetime] = None
    last_sync_direction: Optional[SyncDirection] = None
    pending_changes: int = 0
    error_message: Optional[str] = None
    sheets_api_quota_remaining: int = 60  # per minute


@dataclass
class SyncResult:
    """동기화 결과"""
    success: bool
    direction: SyncDirection
    records_synced: int = 0
    records_failed: int = 0
    duration_seconds: float = 0.0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


# 콜백 타입 정의
SyncCallback = Callable[[SyncResult], None]
ErrorCallback = Callable[[Exception], None]


class ISheetsSync(Protocol):
    """Google Sheets 동기화 인터페이스

    web/app.py는 이 Protocol에만 의존합니다.
    구체적인 구현(SheetsSyncAdapter)은 런타임에 주입됩니다.
    """

    def get_status(self) -> SyncStatus:
        """현재 동기화 상태 조회"""
        ...

    def sync_to_sheets(self, tables: List[str] = None) -> SyncResult:
        """DB → Sheets 동기화"""
        ...

    def sync_from_sheets(self, tables: List[str] = None) -> SyncResult:
        """Sheets → DB 동기화"""
        ...

    def sync_hands(self) -> SyncResult:
        """Archive Sheet → hands 테이블 동기화"""
        ...

    def set_on_complete(self, callback: SyncCallback) -> None:
        """동기화 완료 콜백 등록"""
        ...

    def set_on_error(self, callback: ErrorCallback) -> None:
        """에러 콜백 등록"""
        ...
```

### 4.2 Adapter 구현 (sheets_adapter.py)

```python
# src/archive_analyzer/sheets_adapter.py
"""Google Sheets 동기화 어댑터 - 기존 클래스 합성"""

import logging
from datetime import datetime
from typing import List, Optional

from archive_analyzer.sheets_protocol import (
    ErrorCallback,
    ISheetsSync,
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

    Usage:
        from archive_analyzer.sheets_sync import SyncConfig, SheetsSyncService
        from archive_analyzer.archive_hands_sync import ArchiveHandsSync

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

    def __init__(
        self,
        sheets_service=None,  # SheetsSyncService
        hands_sync=None,      # ArchiveHandsSync
    ):
        """
        Args:
            sheets_service: SheetsSyncService 인스턴스 (Optional)
            hands_sync: ArchiveHandsSync 인스턴스 (Optional)
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
        """현재 동기화 상태 조회"""
        return SyncStatus(
            is_connected=self._is_connected(),
            last_sync_time=self._last_sync_time,
            last_sync_direction=self._last_direction,
            pending_changes=0,  # 필요시 구현
            error_message=self._error_message,
        )

    def sync_to_sheets(self, tables: List[str] = None) -> SyncResult:
        """DB → Sheets 동기화"""
        if not self._sheets_service:
            return self._no_service_result(SyncDirection.DB_TO_SHEETS)

        start = datetime.now()
        try:
            # 기존 SheetsSyncService 사용
            self._sheets_service.sync_db_to_sheets(tables)

            result = SyncResult(
                success=True,
                direction=SyncDirection.DB_TO_SHEETS,
                duration_seconds=(datetime.now() - start).total_seconds(),
            )
            self._update_state(result)
            return result

        except Exception as e:
            return self._error_result(SyncDirection.DB_TO_SHEETS, e, start)

    def sync_from_sheets(self, tables: List[str] = None) -> SyncResult:
        """Sheets → DB 동기화"""
        if not self._sheets_service:
            return self._no_service_result(SyncDirection.SHEETS_TO_DB)

        start = datetime.now()
        try:
            # 기존 SheetsSyncService 사용
            self._sheets_service.sync_sheets_to_db(tables)

            result = SyncResult(
                success=True,
                direction=SyncDirection.SHEETS_TO_DB,
                duration_seconds=(datetime.now() - start).total_seconds(),
            )
            self._update_state(result)
            return result

        except Exception as e:
            return self._error_result(SyncDirection.SHEETS_TO_DB, e, start)

    def sync_hands(self) -> SyncResult:
        """Archive Sheet → hands 테이블 동기화"""
        if not self._hands_sync:
            return self._no_service_result(SyncDirection.SHEETS_TO_DB)

        start = datetime.now()
        try:
            # 기존 ArchiveHandsSync 사용
            sync_result = self._hands_sync.sync_all_worksheets()

            result = SyncResult(
                success=True,
                direction=SyncDirection.SHEETS_TO_DB,
                records_synced=sync_result.get("total_synced", 0),
                duration_seconds=(datetime.now() - start).total_seconds(),
            )
            self._update_state(result)
            return result

        except Exception as e:
            return self._error_result(SyncDirection.SHEETS_TO_DB, e, start)

    def set_on_complete(self, callback: SyncCallback) -> None:
        """동기화 완료 콜백 등록"""
        self._on_complete = callback

    def set_on_error(self, callback: ErrorCallback) -> None:
        """에러 콜백 등록"""
        self._on_error = callback

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _is_connected(self) -> bool:
        """연결 상태 확인"""
        if self._sheets_service:
            try:
                return self._sheets_service.sheets_client.spreadsheet is not None
            except Exception:
                pass
        return False

    def _update_state(self, result: SyncResult) -> None:
        """상태 업데이트 및 콜백 호출"""
        self._last_sync_time = datetime.now()
        self._last_direction = result.direction
        self._error_message = None

        if self._on_complete:
            self._on_complete(result)

    def _no_service_result(self, direction: SyncDirection) -> SyncResult:
        """서비스 미설정 결과"""
        return SyncResult(
            success=False,
            direction=direction,
            errors=["Service not configured"],
        )

    def _error_result(
        self, direction: SyncDirection, error: Exception, start: datetime
    ) -> SyncResult:
        """에러 결과 생성"""
        self._error_message = str(error)
        logger.error(f"Sheets sync error: {error}")

        if self._on_error:
            self._on_error(error)

        return SyncResult(
            success=False,
            direction=direction,
            duration_seconds=(datetime.now() - start).total_seconds(),
            errors=[str(error)],
        )
```

---

## 5. web/app.py 연동 방법

### 5.1 연동 코드 (Optional 패턴)

```python
# web/app.py 수정 부분 (최소 변경)

from typing import Optional
from archive_analyzer.sheets_protocol import ISheetsSync, SyncStatus

@dataclass
class ServiceState:
    """서비스 상태 관리"""
    # ... 기존 필드 ...

    # Sheets 연동 (Optional - 주입되지 않으면 None)
    sheets_sync: Optional[ISheetsSync] = None


# Factory 함수로 분리 (선택적 초기화)
def create_sheets_adapter() -> Optional[ISheetsSync]:
    """Sheets 어댑터 생성 (설정이 있을 때만)"""
    try:
        # 환경변수로 활성화 여부 확인
        if not os.environ.get("SHEETS_SYNC_ENABLED"):
            return None

        from archive_analyzer.sheets_sync import SyncConfig, SheetsSyncService
        from archive_analyzer.archive_hands_sync import ArchiveHandsSync
        from archive_analyzer.sheets_adapter import SheetsSyncAdapter

        sheets_service = SheetsSyncService(SyncConfig())
        hands_sync = ArchiveHandsSync()

        return SheetsSyncAdapter(
            sheets_service=sheets_service,
            hands_sync=hands_sync,
        )
    except Exception as e:
        logger.warning(f"Sheets adapter not available: {e}")
        return None
```

### 5.2 API 엔드포인트 추가

```python
# web/app.py - API 엔드포인트 추가

@app.get("/api/sheets/status")
async def get_sheets_status():
    """Sheets 동기화 상태"""
    if not state.sheets_sync:
        return {"enabled": False, "message": "Sheets sync not configured"}

    status = state.sheets_sync.get_status()
    return {
        "enabled": True,
        "is_connected": status.is_connected,
        "last_sync_time": status.last_sync_time.isoformat() if status.last_sync_time else None,
        "error": status.error_message,
    }


@app.post("/api/sheets/sync")
async def trigger_sheets_sync(
    background_tasks: BackgroundTasks,
    direction: str = "db_to_sheets",
):
    """Sheets 동기화 트리거"""
    if not state.sheets_sync:
        return JSONResponse(
            status_code=400,
            content={"error": "Sheets sync not configured"},
        )

    def run_sheets_sync():
        if direction == "db_to_sheets":
            state.sheets_sync.sync_to_sheets()
        elif direction == "sheets_to_db":
            state.sheets_sync.sync_from_sheets()
        elif direction == "hands":
            state.sheets_sync.sync_hands()

    background_tasks.add_task(run_sheets_sync)
    return {"message": "Sheets sync started", "direction": direction}
```

---

## 6. 설정 구조

### 6.1 환경변수

```bash
# .env 또는 docker-compose.yml

# Sheets 동기화 활성화
SHEETS_SYNC_ENABLED=true

# 기존 sheets_sync.py 설정 (변경 없음)
CREDENTIALS_PATH=config/gcp-service-account.json
SPREADSHEET_ID=1TW2ON5CQyIrL8aGQNYJ4OWkbZMaGmY9DoDG9VFXU60I
DB_PATH=D:/AI/claude01/shared-data/pokervod.db

# Archive Hands Sync 설정
ARCHIVE_SHEET_ID=1_RN_W_ZQclSZA0Iez6XniCXVtjkkd5HNZwiT6l-z6d4
```

### 6.2 Docker Compose

```yaml
# docker-compose.sync.yml 수정
services:
  web-monitor:
    environment:
      - SHEETS_SYNC_ENABLED=true
      - CREDENTIALS_PATH=/app/config/gcp-service-account.json
      - SPREADSHEET_ID=${SPREADSHEET_ID}
    volumes:
      - ./config:/app/config:ro
```

---

## 7. 데이터 흐름

### 7.1 NAS 변경 → Sheets 반영

```
┌─────────────────────────────────────────────────────────────────────┐
│  NAS 파일 변경 → Google Sheets 반영                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ① NAS 파일 변경 감지                                               │
│     │                                                               │
│     ▼                                                               │
│  ┌─────────────────┐                                                │
│  │  NASAutoSync    │ incremental_scan()                            │
│  │  (기존)         │────────────────────┐                           │
│  └─────────────────┘                    │                           │
│                                         ▼                           │
│                              ┌─────────────────┐                    │
│                              │  archive.db     │                    │
│                              │  (files 테이블)  │                    │
│                              └─────────────────┘                    │
│                                         │                           │
│                                         │ sync_to_pokervod()        │
│                                         ▼                           │
│                              ┌─────────────────┐                    │
│                              │  pokervod.db    │                    │
│                              │  (files 테이블)  │                    │
│                              └─────────────────┘                    │
│                                         │                           │
│  ② DB → Sheets 동기화                   │                           │
│                                         ▼                           │
│  ┌─────────────────┐        ┌─────────────────────┐                 │
│  │ SheetsSyncAdapter│◄──────│ WebApp: POST /api/  │                 │
│  │   .sync_to_sheets()      │ sheets/sync         │                 │
│  └─────────────────┘        └─────────────────────┘                 │
│           │                                                         │
│           │ 위임                                                    │
│           ▼                                                         │
│  ┌─────────────────┐                                                │
│  │SheetsSyncService│ sync_db_to_sheets()                           │
│  │  (기존)         │────────────────────┐                           │
│  └─────────────────┘                    │                           │
│                                         ▼                           │
│                              ┌─────────────────┐                    │
│                              │  Google Sheets   │                    │
│                              │  (Pokervod DB)   │                    │
│                              └─────────────────┘                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Archive 시트 변경 → DB 반영

```
┌─────────────────────────────────────────────────────────────────────┐
│  Archive 시트 변경 → hands 테이블 반영                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐                                                │
│  │  Google Sheets   │  아카이브팀 수동 편집                          │
│  │  (Archive Team)  │                                               │
│  │  ID: 1_RN_W_...  │                                               │
│  └─────────────────┘                                                │
│           │                                                         │
│           │ ① API 호출                                              │
│           ▼                                                         │
│  ┌─────────────────────┐        ┌─────────────────────┐            │
│  │ SheetsSyncAdapter   │◄───────│ WebApp: POST /api/  │            │
│  │   .sync_hands()     │        │ sheets/sync?dir=hands│            │
│  └─────────────────────┘        └─────────────────────┘            │
│           │                                                         │
│           │ 위임                                                    │
│           ▼                                                         │
│  ┌─────────────────┐                                                │
│  │ ArchiveHandsSync │  sync_all_worksheets()                       │
│  │  (기존)          │                                               │
│  └─────────────────┘                                                │
│           │                                                         │
│           │ ② 데이터 변환 & 저장                                    │
│           ▼                                                         │
│  ┌─────────────────┐                                                │
│  │  pokervod.db    │                                                │
│  │  (hands 테이블)  │                                                │
│  └─────────────────┘                                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 8. 구현 체크리스트

### Phase 1: 인터페이스 정의 (우선)

- [ ] `sheets_protocol.py` 생성
  - [ ] `SyncDirection` Enum
  - [ ] `SyncStatus` dataclass
  - [ ] `SyncResult` dataclass
  - [ ] `ISheetsSync` Protocol

### Phase 2: Adapter 구현

- [ ] `sheets_adapter.py` 생성
  - [ ] `SheetsSyncAdapter` 클래스
  - [ ] 기존 서비스 합성
  - [ ] ISheetsSync 구현

### Phase 3: web/app.py 연동

- [ ] `ServiceState`에 `sheets_sync` 필드 추가
- [ ] `create_sheets_adapter()` 팩토리 추가
- [ ] API 엔드포인트 추가
  - [ ] `GET /api/sheets/status`
  - [ ] `POST /api/sheets/sync`

### Phase 4: UI 연동

- [ ] 대시보드에 Sheets 상태 표시
- [ ] 동기화 버튼 추가

---

## 9. 테스트 전략

### 9.1 단위 테스트

```python
# tests/test_sheets_adapter.py

def test_adapter_without_services():
    """서비스 없이 어댑터 생성 시 graceful 처리"""
    adapter = SheetsSyncAdapter()
    status = adapter.get_status()
    assert not status.is_connected

    result = adapter.sync_to_sheets()
    assert not result.success
    assert "not configured" in result.errors[0].lower()


def test_adapter_with_mock_services():
    """Mock 서비스로 어댑터 테스트"""
    mock_sheets = MagicMock()
    mock_hands = MagicMock()

    adapter = SheetsSyncAdapter(
        sheets_service=mock_sheets,
        hands_sync=mock_hands,
    )

    adapter.sync_to_sheets()
    mock_sheets.sync_db_to_sheets.assert_called_once()
```

### 9.2 통합 테스트

```python
# tests/test_sheets_integration.py

@pytest.mark.integration
def test_full_sync_flow():
    """전체 동기화 흐름 테스트"""
    # 실제 서비스 인스턴스 (테스트 시트 사용)
    adapter = SheetsSyncAdapter(
        sheets_service=SheetsSyncService(test_config),
        hands_sync=ArchiveHandsSync(test_config),
    )

    result = adapter.sync_to_sheets(tables=["files"])
    assert result.success
```

---

## 10. 장점

| 항목 | 설명 |
|------|------|
| **기존 코드 재사용** | SheetsSyncService, ArchiveHandsSync 수정 없음 |
| **느슨한 결합** | Protocol 기반으로 web/app.py와 sheets 모듈 분리 |
| **선택적 활성화** | SHEETS_SYNC_ENABLED=false로 완전 비활성화 가능 |
| **테스트 용이성** | Mock 주입으로 단위 테스트 가능 |
| **확장성** | 새로운 시트 서비스 추가 시 어댑터만 수정 |

---

## 11. 참조

- `sheets_sync.py`: 기존 Sheets 동기화 서비스
- `archive_hands_sync.py`: 기존 Hands 동기화 서비스
- `web/app.py`: NAS 모니터링 웹 대시보드
- `docs/SHEETS_SCHEMA.md`: Google Sheets 구조 문서
