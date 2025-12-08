# PRD: NAS 경로 변경 실시간 감지 및 DB 자동 동기화 시스템

**Version**: 1.0
**Date**: 2025-12-08
**Author**: Claude Code
**Status**: Draft
**Issue**: #41

---

## 1. Purpose

NAS 파일 시스템의 경로 변경(이동, 이름 변경, 삭제)을 실시간으로 감지하고 DB에 자동 반영하는 시스템 구현.
기존 폴링 기반 `nas_auto_sync.py`의 한계를 보완하여 데이터 일관성을 유지한다.

### 1.1 현재 문제점

| 문제 | 영향 | 심각도 |
|------|------|--------|
| 파일 이동 미감지 | 기존 경로 레코드가 고아(orphan)로 남음 | High |
| 이름 변경 미감지 | 새 파일로 인식되어 중복 등록 | High |
| 삭제 미감지 | DB에 존재하지 않는 파일 레코드 유지 | Medium |
| DB 경로 불일치 | `shared-data` vs `qwen_hand_analysis` 분리 | High |

### 1.2 목표

1. 파일 이동/이름 변경 시 기존 레코드의 경로만 업데이트 (ID 유지)
2. 삭제된 파일 Soft Delete 처리 (데이터 보존)
3. 모든 변경 이력 추적 (감사 로그)
4. Windows Service로 백그라운드 실행

---

## 2. Target Users

- **Primary**: 시스템 관리자 (자동화된 데이터 일관성 유지)
- **Secondary**: 편집팀 (NAS 파일 정리 시 DB 자동 반영)

---

## 3. Technical Requirements

### 3.1 변경 감지 방식

**선택: Hybrid Polling (30초) + Hash-based Change Detection**

| 방식 | 장점 | 단점 | 채택 |
|------|------|------|------|
| watchdog inotify | 실시간 | SMB에서 불안정 | ❌ |
| PollingObserver 10초 | 빠른 반응 | 네트워크 부하 | ❌ |
| **PollingObserver 30초** | 안정성 + 적절한 반응 | - | ✅ |
| SMB CHANGE_NOTIFY | 네이티브 | 버퍼 오버플로우, 이벤트 손실 | ❌ |

**근거**: [watchdog 공식 문서](https://pypi.org/project/watchdog/)에 따르면 SMB/CIFS에서는 `PollingObserver`가 유일하게 안정적인 방식

### 3.2 파일 동일성 검증

**선택: xxHash (헤더 512KB) + 파일명 + 크기**

```python
def compute_file_identity(path: str) -> FileIdentity:
    """파일 동일성 식별자 생성"""
    stat = os.stat(path)

    # 1차: 크기 + 파일명 (빠른 필터)
    quick_id = f"{stat.st_size}:{os.path.basename(path)}"

    # 2차: xxHash (512KB 헤더만, 네트워크 부하 최소화)
    with open(path, 'rb') as f:
        header = f.read(512 * 1024)
    content_hash = xxhash.xxh64(header).hexdigest()

    return FileIdentity(
        size=stat.st_size,
        filename=os.path.basename(path),
        content_hash=content_hash,
        mtime=stat.st_mtime
    )
```

**해시 알고리즘 비교**:

| 알고리즘 | 속도 | 보안 | 용도 |
|----------|------|------|------|
| **xxHash** | 최고 (10GB/s) | 비암호화 | ✅ 파일 변경 감지 |
| BLAKE3 | 높음 (병렬화) | 암호화 | 보안 필요 시 |
| MD5/SHA256 | 느림 | 암호화 | ❌ 과도함 |

**참고**: [xxHash vs BLAKE3 비교](https://compile7.org/compare-hashing-algorithms/what-is-difference-between-xxhash-vs-blake3/)

### 3.3 삭제 정책

**선택: Soft Delete (status='deleted')**

```sql
-- 삭제 시 실행
UPDATE files
SET status = 'deleted',
    deleted_at = CURRENT_TIMESTAMP
WHERE nas_path = ?;

-- 조회 시 기본 필터
SELECT * FROM files WHERE status != 'deleted';
```

| 정책 | 장점 | 단점 | 채택 |
|------|------|------|------|
| Hard Delete | 깔끔함 | 복구 불가 | ❌ |
| **Soft Delete** | 복구 가능, 이력 유지 | 스토리지 증가 | ✅ |
| Archive Table | 분리 관리 | 복잡성 증가 | ❌ |
| Grace Period | 자동 정리 | 구현 복잡 | Phase 2 |

### 3.4 배포 환경

**선택: Windows Service (pywin32)**

```python
import win32serviceutil
import win32service

class NASTrackerService(win32serviceutil.ServiceFramework):
    _svc_name_ = "NASPathTracker"
    _svc_display_name_ = "NAS Path Tracker Service"
    _svc_description_ = "Monitors NAS for file changes and syncs to database"

    def SvcDoRun(self):
        self.tracker = NASPathTracker()
        self.tracker.run_daemon()
```

**설치/관리**:
```powershell
# 설치
python nas_tracker_service.py install

# 시작/중지
sc start NASPathTracker
sc stop NASPathTracker

# 로그 확인
Get-EventLog -LogName Application -Source NASPathTracker
```

---

## 4. Database Schema

### 4.1 새 테이블: file_history

```sql
CREATE TABLE file_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT NOT NULL,           -- files.id 참조
    event_type TEXT NOT NULL,        -- created, moved, renamed, deleted, restored
    old_path TEXT,                   -- 이전 경로 (moved/renamed 시)
    new_path TEXT,                   -- 새 경로
    old_hash TEXT,                   -- 이전 해시 (내용 변경 시)
    new_hash TEXT,                   -- 새 해시
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP,             -- pokervod.db 동기화 시점
    metadata JSON,                   -- 추가 정보 (사용자, 이유 등)

    FOREIGN KEY (file_id) REFERENCES files(id)
);

CREATE INDEX idx_file_history_file_id ON file_history(file_id);
CREATE INDEX idx_file_history_detected_at ON file_history(detected_at);
CREATE INDEX idx_file_history_event_type ON file_history(event_type);
```

### 4.2 files 테이블 수정

```sql
-- 기존 컬럼에 추가
ALTER TABLE files ADD COLUMN status TEXT DEFAULT 'active';  -- active, deleted, moved
ALTER TABLE files ADD COLUMN deleted_at TIMESTAMP;
ALTER TABLE files ADD COLUMN content_hash TEXT;             -- xxHash 값
ALTER TABLE files ADD COLUMN last_verified_at TIMESTAMP;    -- 마지막 검증 시점

CREATE INDEX idx_files_status ON files(status);
CREATE INDEX idx_files_content_hash ON files(content_hash);
```

---

## 5. Architecture

### 5.1 시스템 구조

```
┌─────────────────────────────────────────────────────────────┐
│                    NAS Path Tracker Service                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────────┐  │
│  │   Watcher    │────▶│  EventQueue  │────▶│  Processor  │  │
│  │ (Polling 30s)│     │  (Debounce)  │     │  (Handler)  │  │
│  └──────────────┘     └──────────────┘     └──────┬──────┘  │
│         │                                         │         │
│         │ SMB                                     │         │
│         ▼                                         ▼         │
│  ┌──────────────┐                         ┌─────────────┐   │
│  │     NAS      │                         │IdentityStore│   │
│  │ (10.10.100.  │                         │(Hash Cache) │   │
│  │    122)      │                         └──────┬──────┘   │
│  └──────────────┘                                │         │
│                                                  ▼         │
│                                          ┌─────────────┐   │
│                                          │ archive.db  │   │
│                                          └──────┬──────┘   │
│                                                 │          │
│                                                 ▼          │
│                                          ┌─────────────┐   │
│                                          │pokervod.db  │   │
│                                          │(shared-data)│   │
│                                          └─────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 이벤트 처리 흐름

```
[File Event Detected]
        │
        ▼
┌───────────────────┐
│ Debounce (5초)    │ ← 동일 파일 이벤트 병합
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Compute Identity  │ ← xxHash + 파일명 + 크기
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐     ┌─────────────────┐
│ Lookup by Hash    │────▶│ Found: MOVE     │ ← 해시 동일, 경로 다름
└─────────┬─────────┘     └─────────────────┘
          │
          │ Not Found
          ▼
┌───────────────────┐     ┌─────────────────┐
│ Lookup by Path    │────▶│ Found: UPDATE   │ ← 경로 동일, 내용 변경
└─────────┬─────────┘     └─────────────────┘
          │
          │ Not Found
          ▼
┌───────────────────┐
│ CREATE new record │
└───────────────────┘
```

---

## 6. Core Classes

### 6.1 NASPathTracker

```python
class NASPathTracker:
    """NAS 경로 변경 추적기"""

    def __init__(self, config: TrackerConfig):
        self.config = config
        self.watcher = PollingObserver(timeout=config.poll_interval)
        self.identity_store = FileIdentityStore(config.db_path)
        self.event_queue = EventQueue(debounce_seconds=5)

    def start(self) -> None:
        """추적 시작"""
        handler = NASEventHandler(self.event_queue)
        self.watcher.schedule(handler, self.config.nas_path, recursive=True)
        self.watcher.start()
        self._process_events()

    def on_created(self, path: str) -> None:
        """신규 파일 처리"""
        identity = self.identity_store.compute(path)

        # 해시로 기존 파일 검색 (이동 감지)
        existing = self.identity_store.find_by_hash(identity.content_hash)
        if existing:
            self._handle_move(existing, path)
        else:
            self._handle_create(path, identity)

    def on_deleted(self, path: str) -> None:
        """삭제 처리 (Soft Delete)"""
        self.db.execute("""
            UPDATE files
            SET status = 'deleted', deleted_at = ?
            WHERE nas_path = ?
        """, (datetime.now(), path))

        self._log_history(path, 'deleted')

    def reconcile(self) -> ReconcileResult:
        """정합성 검증 (주기적 실행)"""
        # DB의 모든 active 파일이 NAS에 존재하는지 확인
        # 존재하지 않으면 deleted로 마킹
        ...
```

### 6.2 FileIdentityStore

```python
@dataclass
class FileIdentity:
    """파일 동일성 식별자"""
    size: int
    filename: str
    content_hash: str  # xxHash of first 512KB
    mtime: float

class FileIdentityStore:
    """해시 기반 파일 식별 저장소"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._cache: Dict[str, FileIdentity] = {}

    def compute(self, path: str) -> FileIdentity:
        """파일 동일성 식별자 계산"""
        stat = os.stat(path)

        # 512KB 헤더만 읽어 해시 계산 (네트워크 부하 최소화)
        with SMBConnector.open(path, 'rb') as f:
            header = f.read(512 * 1024)

        return FileIdentity(
            size=stat.st_size,
            filename=os.path.basename(path),
            content_hash=xxhash.xxh64(header).hexdigest(),
            mtime=stat.st_mtime
        )

    def find_by_hash(self, content_hash: str) -> Optional[str]:
        """해시로 기존 파일 경로 검색"""
        cursor = self.db.execute(
            "SELECT nas_path FROM files WHERE content_hash = ? AND status = 'active'",
            (content_hash,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
```

---

## 7. Configuration

### 7.1 환경변수

```bash
# 필수
SMB_SERVER=10.10.100.122
SMB_SHARE=docker
SMB_USERNAME=GGP
SMB_PASSWORD=xxxx
ARCHIVE_PATH=GGPNAs/ARCHIVE

# 선택
POLL_INTERVAL=30          # 폴링 간격 (초)
DEBOUNCE_SECONDS=5        # 이벤트 병합 대기 시간
HASH_SIZE_KB=512          # 해시 계산용 읽기 크기
RECONCILE_INTERVAL=3600   # 정합성 검증 주기 (초)

# DB
ARCHIVE_DB=data/output/archive.db
POKERVOD_DB=D:/AI/claude01/shared-data/pokervod.db
```

### 7.2 설정 파일

```yaml
# config/tracker.yaml
watcher:
  poll_interval: 30
  debounce_seconds: 5
  recursive: true

identity:
  hash_algorithm: xxhash
  hash_size_kb: 512

sync:
  reconcile_interval: 3600
  batch_size: 100

logging:
  level: INFO
  file: logs/tracker.log
  max_size_mb: 10
  backup_count: 5
```

---

## 8. Implementation Plan

### Phase 1: 스키마 마이그레이션 (1일)
- [ ] `file_history` 테이블 생성
- [ ] `files` 테이블에 status, content_hash 컬럼 추가
- [ ] 마이그레이션 스크립트 작성

### Phase 2: Core 클래스 구현 (3일)
- [ ] `FileIdentityStore` 구현 (xxHash 기반)
- [ ] `NASPathTracker` 구현
- [ ] `EventQueue` (debounce) 구현

### Phase 3: 이벤트 핸들러 (2일)
- [ ] created/modified/deleted 핸들러
- [ ] moved 감지 로직 (해시 기반)
- [ ] file_history 로깅

### Phase 4: 기존 시스템 통합 (1일)
- [ ] `nas_auto_sync.py`와 통합
- [ ] `SyncService` 연동

### Phase 5: Windows Service (1일)
- [ ] pywin32 서비스 래퍼
- [ ] 설치/제거 스크립트

### Phase 6: 테스트 및 문서화 (2일)
- [ ] 단위 테스트 (이동, 삭제, 생성)
- [ ] 통합 테스트 (실제 NAS 연동)
- [ ] 운영 문서 작성

**총 예상 기간**: 10일

---

## 9. Success Metrics

| 지표 | 현재 | 목표 |
|------|------|------|
| 고아 레코드 비율 | ~5% | <0.1% |
| 중복 레코드 비율 | ~2% | 0% |
| 변경 감지 지연 | N/A (수동) | <60초 |
| DB 정합성 | 수동 검증 | 자동 검증 |

---

## 10. Risks & Mitigations

| 리스크 | 영향 | 완화 방안 |
|--------|------|----------|
| 대량 파일 이동 시 부하 | High | Debounce + 배치 처리 |
| 네트워크 불안정 | Medium | 재연결 로직 + 큐 보존 |
| 해시 충돌 (이론적) | Low | 해시 + 크기 + 파일명 조합 |
| SMB 연결 끊김 | Medium | 자동 재연결 (3회 재시도) |

---

## 11. Dependencies

### Python 패키지

```
watchdog>=4.0.0          # 파일 시스템 모니터링
xxhash>=3.4.0            # 빠른 해시 계산
pywin32>=306             # Windows Service
smbprotocol>=1.10.0      # SMB 연결 (기존)
```

### 시스템 요구사항

- Python 3.10+
- Windows 10/11 또는 Windows Server 2019+
- 네트워크: NAS 접근 가능

---

## 12. References

- [watchdog - Python filesystem monitoring](https://pypi.org/project/watchdog/)
- [xxHash vs BLAKE3 비교](https://compile7.org/compare-hashing-algorithms/what-is-difference-between-xxhash-vs-blake3/)
- [SMB에서 watchdog 사용하기](https://github.com/gorakhargosh/watchdog/issues/458)
- Issue #41: NAS 경로 변경 실시간 감지
- Issue #17: NAS 신규 데이터 자동 감지
- `docs/DATA_FLOW.md`: 데이터 플로우 문서
- `docs/DATABASE_UNIFICATION.md`: 통합 DB 가이드

---

**Next Steps**:
1. `/issue fix #41` - 구현 시작
2. 스키마 마이그레이션 스크립트 작성
3. 단위 테스트 먼저 작성 (TDD)
