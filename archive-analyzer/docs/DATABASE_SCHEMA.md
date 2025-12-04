# Database Schema Documentation

> **Last Updated**: 2025-12-04
> **Version**: 3.0.0
> **Related Issues**: #59, #61, #67

이 문서는 archive-analyzer와 연동 레포지토리 간 DB 스키마를 정의합니다.
**스키마 변경 시 반드시 이 문서를 업데이트하고 관련 레포에 공유해야 합니다.**

---

## 시스템 아키텍처 (V3.0)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Archive Analyzer System                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌──────────┐ │
│  │    NAS      │    │   Scanner   │    │   SQLite    │    │ Firestore│ │
│  │  (Storage)  │───→│  (Polling)  │───→│  (Local)    │───→│ (Cloud)  │ │
│  │  18TB       │    │  watchdog   │    │ pokervod.db │    │ gg-poker │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └──────────┘ │
│                                                                  │      │
│                                                                  ▼      │
│                                                          ┌──────────┐   │
│                                                          │  Web App │   │
│                                                          │  (OTT)   │   │
│                                                          └──────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 데이터 저장소 역할

| 저장소 | 역할 | 기술 스택 |
|--------|------|-----------|
| **Firestore** | 프로덕션 클라우드 DB (Primary) | Firebase `gg-poker-prod` |
| **SQLite** | 로컬 캐시/동기화 원본 | `pokervod.db` (WAL 모드) |
| **archive.db** | 스캔 전용 로컬 DB | `archive-analyzer` 내부 |

---

## 스키마 요약

### Firestore 컬렉션 (7개)

| 컬렉션 | 문서 수 | 설명 |
|--------|--------|------|
| `catalogs` | 10 | 최상위 카탈로그 (WSOP, HCL, PAD...) |
| `series` | 12 | 시리즈 (WSOP 2024, HCL Season 1...) |
| `contents` | 2,938 | 개별 콘텐츠/에피소드 |
| `files` | 2,139 | 미디어 파일 메타데이터 |
| `players` | 386 | 포커 플레이어 |
| `tags` | 5 | 콘텐츠 분류 태그 |
| `users` | 2 | 사용자 |

> **마이그레이션 완료**: 2025-12-04, 5,492 documents (Issue #59, #61)

### SQLite 테이블 (pokervod.db: 23개)

| 카테고리 | 테이블 | 설명 |
|----------|--------|------|
| **Core** | catalogs, files, players | 콘텐츠 기본 구조 |
| **V3.0 ✅** | series, contents, content_players, content_tags, tags | Video Card 중심 통합 스키마 |
| **User** | users, user_sessions, user_preferences, watch_progress, view_events | 사용자 및 시청 기록 |
| **Recommendation** | recommendation_cache, trending_scores, home_rows, user_home_rows | 추천 시스템 |
| **Artwork** | artwork_variants, artwork_selections | 썸네일 개인화 |
| **Multi-Catalog** | file_catalogs, catalog_collections, collection_items | N:N 카탈로그 |
| **Experiment** | experiments, experiment_assignments | A/B 테스트 |
| **Embedding** | user_embeddings, item_embeddings | ML 임베딩 |
| **Search** | wsoptv_search_index, wsoptv_search_history, wsoptv_popular_searches, wsoptv_player_aliases, wsoptv_choseong_index | 검색 시스템 |

---

## 연동 레포지토리

| 레포지토리 | 저장소 | 역할 |
|-----------|---------|------|
| `archive-analyzer` | `archive.db` (로컬) | 아카이브 스캔/메타데이터 |
| `shared-data` | `pokervod.db` | 로컬 캐시/동기화 원본 (WAL 모드) |
| `gg-poker-prod` | Firestore | **프로덕션 클라우드 DB** |

> 📌 데이터 플로우 상세: `docs/DATA_FLOW.md` 참조

---

## 1. Firestore (프로덕션 클라우드 DB)

**프로젝트**: `gg-poker-prod`
**리전**: `asia-northeast3` (Seoul)
**마이그레이션 완료**: 2025-12-04 (Issue #59, #61)

### 1.1 컬렉션 구조

```
firestore/
├── catalogs/{catalog_id}           # WSOP, HCL, PAD...
│   └── (subcollection 없음 - flat structure)
├── series/{series_id}              # WSOP 2024, HCL Season 1...
├── contents/{content_id}           # 개별 에피소드
├── files/{file_id}                 # 미디어 파일
├── players/{player_name}           # 플레이어 정보
├── tags/{tag_id}                   # 분류 태그
├── users/{user_id}                 # 사용자
└── _sync_metadata/                 # 동기화 메타데이터 (내부용)
```

### 1.2 컬렉션 상세

#### catalogs
최상위 카탈로그 (WSOP, HCL, PAD 등)

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 카탈로그 ID (document ID와 동일) |
| `name` | string | 카탈로그명 |
| `description` | string | 설명 |
| `display_title` | string | 시청자용 표시 제목 |
| `title_source` | string | 제목 생성 방식 (rule_based/ai_generated/manual) |
| `title_verified` | boolean | 수동 검수 완료 여부 |
| `created_at` | timestamp | 생성일시 |
| `updated_at` | timestamp | 수정일시 |

#### series
시리즈: 카탈로그 내 콘텐츠 시리즈

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | number | 시리즈 ID |
| `catalog_id` | string | 소속 카탈로그 ID |
| `title` | string | 시리즈 제목 |
| `season_num` | number | 시즌 번호 |
| `year` | number | 연도 |
| `description` | string | 설명 |
| `episode_count` | number | 에피소드 수 |
| `created_at` | timestamp | 생성일시 |

#### contents
개별 콘텐츠 (에피소드/영상)

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | number | 콘텐츠 ID |
| `series_id` | number | 소속 시리즈 ID |
| `file_id` | string | 연결된 파일 ID |
| `episode_num` | number | 에피소드 번호 |
| `title` | string | 제목 |
| `duration_sec` | number | 재생 시간 (초) |
| `description` | string | 설명 |
| `players` | array<string> | 출연 플레이어 목록 |
| `tags` | array<string> | 태그 목록 |
| `created_at` | timestamp | 생성일시 |

#### files
미디어 파일 메타데이터

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 파일 ID (NAS 경로 해시) |
| `nas_path` | string | NAS 전체 경로 |
| `filename` | string | 파일명 |
| `size_bytes` | number | 파일 크기 |
| `duration_sec` | number | 재생 시간 (초) |
| `resolution` | string | 해상도 (예: "1920x1080") |
| `codec` | string | 비디오 코덱 |
| `fps` | number | 프레임레이트 |
| `bitrate_kbps` | number | 비트레이트 |
| `analysis_status` | string | 분석 상태 (pending/completed/failed) |
| `display_title` | string | 시청자용 제목 |
| `created_at` | timestamp | 생성일시 |
| `updated_at` | timestamp | 수정일시 |

#### players
포커 플레이어 정보

| 필드 | 타입 | 설명 |
|------|------|------|
| `name` | string | 이름 (document ID) |
| `display_name` | string | 표시 이름 |
| `country` | string | 국가 |
| `total_hands` | number | 총 핸드 수 |
| `total_wins` | number | 총 승리 수 |
| `first_seen_at` | timestamp | 첫 등장 시간 |
| `last_seen_at` | timestamp | 마지막 활동 시간 |

#### tags
콘텐츠 분류 태그

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | number | 태그 ID |
| `name` | string | 태그명 |
| `type` | string | 태그 유형 (player, event, action 등) |
| `created_at` | timestamp | 생성일시 |

#### users
사용자 정보

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 사용자 ID |
| `email` | string | 이메일 |
| `display_name` | string | 표시 이름 |
| `role` | string | 역할 (admin/user) |
| `provider` | string | 인증 제공자 (google) |
| `created_at` | timestamp | 생성일시 |
| `last_login_at` | timestamp | 마지막 로그인 |

### 1.3 인덱스

```
// firestore.indexes.json
{
  "indexes": [
    {
      "collectionGroup": "contents",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "series_id", "order": "ASCENDING" },
        { "fieldPath": "episode_num", "order": "ASCENDING" }
      ]
    },
    {
      "collectionGroup": "files",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "analysis_status", "order": "ASCENDING" },
        { "fieldPath": "updated_at", "order": "DESCENDING" }
      ]
    }
  ]
}
```

### 1.4 보안 규칙

```javascript
// firestore.rules
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // 읽기: 인증된 사용자
    // 쓰기: 관리자만 (server-side)
    match /{document=**} {
      allow read: if request.auth != null;
      allow write: if false;  // Admin SDK only
    }
  }
}
```

---

## 2. SQLite ↔ Firestore 동기화

### 2.1 매핑 테이블

| SQLite (pokervod.db) | Firestore | 동기화 방향 | 키 |
|---------------------|-----------|-------------|-----|
| `catalogs` | `catalogs/{id}` | SQLite → Firestore | `id` |
| `series` | `series/{id}` | SQLite → Firestore | `id` |
| `contents` | `contents/{id}` | SQLite → Firestore | `id` |
| `files` | `files/{id}` | SQLite → Firestore | `id` (nas_path 해시) |
| `players` | `players/{name}` | SQLite → Firestore | `name` |
| `tags` | `tags/{id}` | SQLite → Firestore | `id` |
| `users` | `users/{id}` | SQLite → Firestore | `id` |

### 2.2 동기화 전략

```
┌──────────────┐                      ┌──────────────┐
│    SQLite    │                      │   Firestore  │
│  pokervod.db │                      │  gg-poker    │
├──────────────┤                      ├──────────────┤
│ updated_at   │ ──── Incremental ──→ │ updated_at   │
│              │     (Batch 500)      │              │
└──────────────┘                      └──────────────┘
         ↑                                    │
         │                                    │
    NAS Scanner                          Web App
    (archive.db)                         (OTT)
```

**증분 동기화:**
```python
# 마지막 동기화 이후 변경된 레코드만
changed = SELECT * FROM files WHERE updated_at > last_sync

# 500개씩 Batch Write
for batch in chunks(changed, 500):
    firestore.batch().set(batch).commit()
```

### 2.3 데이터 타입 변환

| SQLite 타입 | Firestore 타입 | 변환 규칙 |
|------------|----------------|----------|
| `INTEGER` | `number` | 직접 변환 |
| `TEXT` | `string` | 직접 변환 |
| `REAL` | `number` | 직접 변환 |
| `BLOB` | `bytes` | Base64 인코딩 |
| `TIMESTAMP` | `timestamp` | ISO 8601 → Firestore Timestamp |
| `JSON (TEXT)` | `array` / `map` | JSON.parse() |

---

## 3. pokervod.db (로컬 캐시 DB)

**경로**: `D:/AI/claude01/shared-data/pokervod.db`
**관리**: 모든 프로젝트 공유 (WAL 모드)

### 1.1 ERD (V3.0 Video Card 스키마)

```
┌─────────────┐
│  catalogs   │
│─────────────│
│ id (PK)     │
│ name        │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│   series    │     │    tags     │
│─────────────│     │─────────────│
│ id (PK)     │     │ id (PK)     │
│ catalog_id  │     │ name        │
│ title       │     │ type        │
│ season_num  │     └──────┬──────┘
└──────┬──────┘            │
       │                   │
       ▼                   │
┌─────────────────┐        │
│    contents     │        │
│─────────────────│        │
│ id (PK)         │        │
│ series_id (FK)  │        │
│ file_id (FK)    │────────│──→ files.id
│ episode_num     │        │
│ title           │        │
│ duration_sec    │        │
└────────┬────────┘        │
         │                 │
    ┌────┴────┐            │
    ▼         ▼            │
┌──────────────┐  ┌──────────────┐
│content_players│ │ content_tags │
│──────────────│  │──────────────│
│ content_id   │  │ content_id   │
│ player_id    │  │ tag_id ──────│──┘
│ role         │  └──────────────┘
└──────────────┘
       │
       ▼
┌─────────────┐
│   players   │
│─────────────│
│ id (PK)     │
│ name        │
│ display_name│
└─────────────┘
```

**V3.0 데이터 현황**: series 12개, contents 2,938개, content_players 833개, content_tags 828개, tags 5개

> **Legacy 스키마**: `DATABASE_SCHEMA_LEGACY.md` 참조 (subcatalogs, tournaments, events, hands 등)

### 1.2 테이블 상세

#### catalogs
카탈로그 (최상위 분류): WSOP, HCL, PAD 등

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR(50) PK | 고유 식별자 |
| name | VARCHAR(200) | 카탈로그명 |
| description | TEXT | 설명 |
| created_at | TIMESTAMP | 생성일시 |
| updated_at | TIMESTAMP | 수정일시 |
| **display_title** | VARCHAR(300) | **시청자용 표시 제목** |
| **title_source** | VARCHAR(20) | **제목 생성 방식 (rule_based/ai_generated/manual)** |
| **title_verified** | BOOLEAN | **수동 검수 완료 여부** |
| **varchar_id** | VARCHAR(50) | **원본 VARCHAR PK (정수 PK 마이그레이션용)** |

#### series
시리즈: 카탈로그 내 콘텐츠 시리즈 (예: WSOP 2024, HCL Season 1)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 고유 식별자 |
| catalog_id | VARCHAR(50) FK | 카탈로그 |
| title | VARCHAR(300) | 시리즈 제목 |
| season_num | INTEGER | 시즌 번호 |
| year | INTEGER | 연도 |
| description | TEXT | 설명 |
| episode_count | INTEGER | 에피소드 수 |
| created_at | TIMESTAMP | 생성일시 |

#### contents
콘텐츠: 개별 에피소드/영상

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 고유 식별자 |
| series_id | INTEGER FK | 시리즈 |
| file_id | VARCHAR(200) FK | 파일 (files.id) |
| episode_num | INTEGER | 에피소드 번호 |
| title | VARCHAR(300) | 제목 |
| duration_sec | FLOAT | 재생 시간 (초) |
| description | TEXT | 설명 |
| created_at | TIMESTAMP | 생성일시 |

#### tags
태그: 콘텐츠 분류용 태그

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 고유 식별자 |
| name | VARCHAR(100) UNIQUE | 태그명 |
| type | VARCHAR(50) | 태그 유형 (player, event, action 등) |
| created_at | TIMESTAMP | 생성일시 |

#### content_players
콘텐츠-플레이어 관계 (N:N)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 고유 식별자 |
| content_id | INTEGER FK | 콘텐츠 ID |
| player_id | INTEGER FK | 플레이어 ID |
| role | VARCHAR(50) | 역할 (main, guest 등) |
| created_at | TIMESTAMP | 생성일시 |

#### content_tags
콘텐츠-태그 관계 (N:N)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 고유 식별자 |
| content_id | INTEGER FK | 콘텐츠 ID |
| tag_id | INTEGER FK | 태그 ID |
| created_at | TIMESTAMP | 생성일시 |

#### files
파일: 실제 미디어 파일

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR(200) PK | 고유 식별자 |
| event_id | VARCHAR(150) FK | 이벤트 |
| **nas_path** | TEXT UNIQUE | **NAS 경로 (archive-analyzer 연동 키)** |
| filename | VARCHAR(500) | 파일명 |
| size_bytes | BIGINT | 파일 크기 |
| duration_sec | FLOAT | 재생 시간 (초) |
| resolution | VARCHAR(20) | 해상도 |
| codec | VARCHAR(50) | 코덱 |
| fps | FLOAT | 프레임레이트 |
| bitrate_kbps | INTEGER | 비트레이트 |
| analysis_status | VARCHAR(20) | 분석 상태 (pending/analyzing/completed/failed) |
| analysis_error | TEXT | 분석 오류 메시지 |
| analyzed_at | TIMESTAMP | 분석 일시 |
| hands_count | INTEGER | 핸드 수 |
| view_count | INTEGER | 조회수 |
| last_viewed_at | TIMESTAMP | 마지막 조회 일시 |
| created_at | TIMESTAMP | 생성일시 |
| updated_at | TIMESTAMP | 수정일시 |
| search_vector | TEXT | 검색용 벡터 |
| **display_title** | VARCHAR(300) | **시청자용 표시 제목** |
| **display_subtitle** | VARCHAR(300) | **시청자용 부제목** |
| **title_source** | VARCHAR(20) | **제목 생성 방식 (rule_based/ai_generated/manual)** |
| **title_verified** | BOOLEAN | **수동 검수 완료 여부** |
| **varchar_id** | VARCHAR(200) | **원본 VARCHAR PK (정수 PK 마이그레이션용)** |

#### players
플레이어: 포커 플레이어 정보

| 컬럼 | 타입 | 설명 |
|------|------|------|
| name | VARCHAR(100) PK | 이름 |
| display_name | VARCHAR(200) | 표시 이름 |
| country | VARCHAR(50) | 국가 |
| total_hands | INTEGER | 총 핸드 수 |
| total_wins | INTEGER | 총 승리 수 |
| total_all_ins | INTEGER | 총 올인 수 |
| avg_pot_bb | FLOAT | 평균 팟 크기 |
| first_seen_at | TIMESTAMP | 플레이어 첫 등록 시간 |
| last_seen_at | TIMESTAMP | 마지막 활동 시간 |
| search_vector | TEXT | 검색용 벡터 |

---

## 4. archive.db (아카이브 스캔 DB)

**경로**: `d:/AI/claude01/archive-analyzer/data/output/archive.db`
**소유자**: `archive-analyzer` 레포

### 2.1 테이블 목록

| 테이블 | 용도 | pokervod.db 연동 |
|--------|------|------------------|
| files | 파일 경로/크기/유형 | → `files.nas_path` |
| media_info | 미디어 메타데이터 | → `files.codec/resolution` |
| scan_checkpoints | 스캔 재개용 | 내부 전용 |
| scan_stats | 스캔 통계 | 내부 전용 |
| clip_metadata | iconik 클립 메타데이터 | → `hands.tags` |
| media_files | 경로 기반 매칭용 | 내부 전용 |

### 2.2 데이터 동기화 흐름

```
archive-analyzer                              qwen_hand_analysis
─────────────────                             ──────────────────
    files                                          files
    ├─ path ──────────────────────────────────→ nas_path
    ├─ size_bytes ────────────────────────────→ size_bytes
    └─ file_type

    media_info                                     files
    ├─ video_codec ───────────────────────────→ codec
    ├─ width/height ──────────────────────────→ resolution
    ├─ duration_seconds ──────────────────────→ duration_sec
    └─ framerate ─────────────────────────────→ fps

    clip_metadata                                  hands
    ├─ players_tags ──────────────────────────→ players (JSON)
    ├─ hand_grade ────────────────────────────→ tags (JSON)
    └─ is_badbeat/bluff/... ──────────────────→ tags (JSON)
```

---

## 5. 스키마 변경 관리

### 3.1 변경 절차

1. **변경 제안**: 이슈 생성 (양쪽 레포에 링크)
2. **영향 분석**: 연동 테이블/컬럼 확인
3. **문서 업데이트**: 이 파일 수정
4. **마이그레이션 스크립트**: 필요시 작성
5. **PR 생성**: 양쪽 레포에 동시 반영

### 3.2 변경 이력

| 날짜 | 버전 | 변경 내용 | 영향 범위 |
|------|------|----------|----------|
| 2025-12-03 | 2.7.0 | **레거시 테이블 삭제**: pokervod.db에서 subcatalogs, tournaments, events, hands 등 7개 테이블 삭제 (백업: `legacy_backup_*.json`) | pokervod.db |
| 2025-12-03 | 2.6.0 | **레거시 스키마 분리**: subcatalogs, tournaments, events, hands, hand_players, hand_tags, id_mapping → `DATABASE_SCHEMA_LEGACY.md` | 문서 정리 |
| 2025-12-03 | 2.0.0 | **추천 시스템 스키마 설계** (Section 8): recommendation_cache, trending_scores, home_rows, user_home_rows, artwork_variants, artwork_selections, experiments, experiment_assignments, user_embeddings, item_embeddings | Phase 3 구현 예정 |
| 2025-12-02 | 1.5.0 | **스키마 정리**: display_names 테이블 폐기 (display_title은 각 테이블에 직접 저장), subcatalogs에서 level1/2/3_name 컬럼 제거 (sub1/2/3와 중복) | sheets_sync.py, pokervod.db |
| 2025-12-02 | 1.4.0 | **Archive Team Google Sheet 동기화** 섹션 추가, 태그 정규화 매핑, 워크시트 자동 처리 문서화 | archive_hands_sync.py |
| 2025-12-02 | 1.3.0 | **display_title 컬럼 추가** (catalogs, subcatalogs, files, hands), title_generator.py 구현 | sheets_sync.py, Google Sheets |
| 2025-12-02 | 1.2.0 | display_names 테이블, 시청자 친화적 네이밍 설계 | Phase 3 구현 예정 |
| 2025-12-02 | 1.1.0 | subcatalogs 다단계 구조 (parent_id, depth, path, sub1/sub2/sub3, full_path_name) | sync.py, 마이그레이션 |
| 2025-12-01 | 1.0.0 | 최초 문서 작성 | - |

### 3.3 마이그레이션 예시

```python
# scripts/migrate_to_pokervod.py
"""archive.db → pokervod.db 데이터 동기화"""

import sqlite3

ARCHIVE_DB = "D:/AI/claude01/archive-analyzer/archive.db"
POKERVOD_DB = "D:/AI/claude01/shared-data/pokervod.db"

def sync_files():
    """files 테이블 동기화"""
    src = sqlite3.connect(ARCHIVE_DB)
    dst = sqlite3.connect(POKERVOD_DB)

    # archive.db에서 미디어 파일 조회
    files = src.execute("""
        SELECT f.path, f.size_bytes, m.video_codec,
               m.width || 'x' || m.height as resolution,
               m.duration_seconds, m.framerate
        FROM files f
        LEFT JOIN media_info m ON f.id = m.file_id
        WHERE f.file_type = 'video'
    """).fetchall()

    # pokervod.db에 upsert
    for path, size, codec, res, dur, fps in files:
        dst.execute("""
            INSERT INTO files (id, nas_path, filename, size_bytes,
                               codec, resolution, duration_sec, fps, analysis_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(nas_path) DO UPDATE SET
                size_bytes = excluded.size_bytes,
                codec = excluded.codec,
                resolution = excluded.resolution,
                duration_sec = excluded.duration_sec,
                fps = excluded.fps
        """, (generate_id(path), path, os.path.basename(path),
              size, codec, res, dur, fps))

    dst.commit()
    dst.close()
    src.close()
```

---

## 6. 연동 키 규칙

### 4.1 파일 ID 생성

```python
import hashlib

def generate_file_id(nas_path: str) -> str:
    """NAS 경로로 고유 ID 생성"""
    # 경로 정규화 (Windows/Unix 호환)
    normalized = nas_path.replace("\\", "/").lower()
    return hashlib.md5(normalized.encode()).hexdigest()[:16]
```

### 4.2 경로 변환

```python
# NAS 경로 패턴
NAS_PREFIX = "//10.10.100.122/docker/GGPNAs/ARCHIVE"
LOCAL_PREFIX = "Z:/GGPNAs/ARCHIVE"

def nas_to_local(nas_path: str) -> str:
    return nas_path.replace(NAS_PREFIX, LOCAL_PREFIX)

def local_to_nas(local_path: str) -> str:
    return local_path.replace(LOCAL_PREFIX, NAS_PREFIX)
```

---

## 7. 카테고리/서브카테고리 매핑

### 5.1 다단계 분류 규칙

경로 패턴에서 자동으로 catalog, subcatalog, depth를 추출합니다.

| 경로 패턴 | catalog_id | subcatalog_id | depth |
|-----------|------------|---------------|-------|
| `WSOP/WSOP-BR` | WSOP | wsop-br | 1 |
| `WSOP/WSOP-BR/WSOP-EUROPE` | WSOP | wsop-europe | 2 |
| `WSOP/WSOP-BR/WSOP-EUROPE/2024` | WSOP | wsop-europe-2024 | 3 |
| `WSOP/WSOP-BR/WSOP-PARADISE` | WSOP | wsop-paradise | 2 |
| `WSOP/WSOP-BR/WSOP-PARADISE/2023` | WSOP | wsop-paradise-2023 | 3 |
| `WSOP/WSOP-BR/WSOP-LAS VEGAS` | WSOP | wsop-las-vegas | 2 |
| `WSOP/WSOP ARCHIVE` | WSOP | wsop-archive | 1 |
| `WSOP/WSOP ARCHIVE/1995` | WSOP | wsop-archive-1973-2002 | 2 |
| `WSOP/WSOP ARCHIVE/2008` | WSOP | wsop-archive-2003-2010 | 2 |
| `WSOP/WSOP ARCHIVE/2015` | WSOP | wsop-archive-2011-2016 | 2 |
| `WSOP/WSOP-C` | WSOP | wsop-circuit | 1 |
| `WSOP/WSOP-SC` | WSOP | wsop-super-circuit | 1 |
| `HCL/2025` | HCL | hcl-2025 | 1 |
| `HCL/Poker Clips` | HCL | hcl-clips | 1 |
| `PAD/Season 12` | PAD | pad-s12 | 1 |
| `PAD/Season 13` | PAD | pad-s13 | 1 |
| `MPP/5M GTD` | MPP | mpp-5m | 1 |
| `GGMillions/` | GGMillions | ggmillions-main | 1 |

### 5.2 다단계 분류 함수

```python
import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class SubcatalogMatch:
    """다단계 서브카탈로그 매칭 결과"""
    catalog_id: str
    subcatalog_id: Optional[str]
    depth: int
    year: Optional[str] = None

    @property
    def full_subcatalog_id(self) -> Optional[str]:
        """연도가 포함된 전체 서브카탈로그 ID"""
        if self.subcatalog_id and self.year and "{year}" in self.subcatalog_id:
            return self.subcatalog_id.replace("{year}", self.year)
        return self.subcatalog_id

# 다단계 패턴: (regex, catalog_id, subcatalog_template, depth)
MULTILEVEL_PATTERNS = [
    # WSOP-BR 하위 (depth=2~3)
    (r"WSOP/WSOP-BR/WSOP-EUROPE/(\d{4})", "WSOP", "wsop-europe-{year}", 3),
    (r"WSOP/WSOP-BR/WSOP-PARADISE/(\d{4})", "WSOP", "wsop-paradise-{year}", 3),
    (r"WSOP/WSOP-BR/WSOP-LAS\s?VEGAS/(\d{4})", "WSOP", "wsop-las-vegas-{year}", 3),
    (r"WSOP/WSOP-BR/WSOP-EUROPE", "WSOP", "wsop-europe", 2),
    (r"WSOP/WSOP-BR/WSOP-PARADISE", "WSOP", "wsop-paradise", 2),
    (r"WSOP/WSOP-BR/WSOP-LAS\s?VEGAS", "WSOP", "wsop-las-vegas", 2),
    (r"WSOP/WSOP-BR", "WSOP", "wsop-br", 1),
    # WSOP Archive (연대별)
    (r"WSOP/WSOP\s?ARCHIVE/(1973|19[789]\d|200[0-2])", "WSOP", "wsop-archive-1973-2002", 2),
    (r"WSOP/WSOP\s?ARCHIVE/(200[3-9]|2010)", "WSOP", "wsop-archive-2003-2010", 2),
    (r"WSOP/WSOP\s?ARCHIVE/(201[1-6])", "WSOP", "wsop-archive-2011-2016", 2),
    (r"WSOP/WSOP\s?ARCHIVE", "WSOP", "wsop-archive", 1),
    # 기타
    (r"WSOP/WSOP-C", "WSOP", "wsop-circuit", 1),
    (r"WSOP/WSOP-SC", "WSOP", "wsop-super-circuit", 1),
    (r"HCL/(\d{4})", "HCL", "hcl-{year}", 1),
    (r"HCL/.*[Cc]lip", "HCL", "hcl-clips", 1),
    (r"PAD/[Ss](?:eason\s?)?12", "PAD", "pad-s12", 1),
    (r"PAD/[Ss](?:eason\s?)?13", "PAD", "pad-s13", 1),
    (r"MPP/.*5\s?[Mm]", "MPP", "mpp-5m", 1),
    (r"GGMillions/", "GGMillions", "ggmillions-main", 1),
]

def classify_path_multilevel(path: str) -> SubcatalogMatch:
    """경로에서 다단계 서브카탈로그 정보 추출"""
    normalized = path.replace("\\", "/")

    for pattern, catalog, subcatalog_template, depth in MULTILEVEL_PATTERNS:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            year = None
            if match.groups() and match.group(1).isdigit():
                year = match.group(1)

            return SubcatalogMatch(
                catalog_id=catalog,
                subcatalog_id=subcatalog_template,
                depth=depth,
                year=year,
            )

    return SubcatalogMatch(catalog_id="OTHER", subcatalog_id=None, depth=0)
```

### 5.3 사용 예시

```python
# WSOP Europe 2024 파일
match = classify_path_multilevel("WSOP/WSOP-BR/WSOP-EUROPE/2024/main_event.mp4")
print(match.catalog_id)           # "WSOP"
print(match.full_subcatalog_id)   # "wsop-europe-2024"
print(match.depth)                # 3
print(match.year)                 # "2024"

# WSOP Archive 2008 파일
match = classify_path_multilevel("WSOP/WSOP ARCHIVE/2008/final_table.mp4")
print(match.full_subcatalog_id)   # "wsop-archive-2003-2010"
print(match.depth)                # 2
```

---

## 8. Viewer-Friendly Naming Design

### 6.1 Problem Statement

Current archive uses **internal management folder/file naming conventions** which are unsuitable for viewers:

| Problem | Current Example | Improvement Needed |
|---------|-----------------|-------------------|
| Abbreviations | `WSOP-BR`, `PAD S12` | Full names or familiar expressions |
| Internal codes | `WSOP-C LA`, `WSOP-SC` | Meaningful names |
| Inconsistency | `2024 WSOP-Europe` vs `WSOP-LAS VEGAS 2024` | Unified year position |
| Insufficient info | `main_event.mp4` | Add specific descriptions |
| Technical terms | `D1A`, `FT` | Viewer-understandable expressions |

### 6.2 Display Title 저장 방식

> **Note (v1.5.0)**: `display_names` 테이블은 **폐기**되었습니다.
> 대신 `display_title`, `title_source`, `title_verified` 컬럼이 각 엔티티 테이블
> (catalogs, subcatalogs, files, hands)에 직접 저장됩니다.

#### 각 테이블의 display_title 관련 컬럼

| Column | Type | Description |
|--------|------|-------------|
| display_title | VARCHAR(300) | 시청자용 표시 제목 |
| title_source | VARCHAR(20) | 제목 생성 방식: `manual`, `ai_generated`, `rule_based`, `archive_team` |
| title_verified | BOOLEAN | 수동 검수 완료 여부 |

### 6.3 Catalog Display Name Mapping

#### Catalogs

| catalog_id | internal_name | display_name | display_name_ko |
|------------|---------------|--------------|-----------------|
| WSOP | WSOP | World Series of Poker | World Series of Poker |
| HCL | HCL | Hustler Casino Live | Hustler Casino Live |
| PAD | PAD | Poker After Dark | Poker After Dark |
| MPP | MPP | MILLIONS Poker Party | MILLIONS Poker Party |
| GGMillions | GGMillions | GG MILLIONS | GG MILLIONS |

#### Subcatalogs

| subcatalog_id | internal_name | display_name | display_name_ko |
|---------------|---------------|--------------|-----------------|
| wsop-br | WSOP-BR | WSOP Bracelet Series | WSOP Bracelet Series |
| wsop-europe | WSOP-EUROPE | WSOP Europe | WSOP Europe |
| wsop-paradise | WSOP-PARADISE | WSOP Paradise | WSOP Paradise |
| wsop-las-vegas | WSOP-LAS VEGAS | WSOP Las Vegas | WSOP Las Vegas |
| wsop-archive | WSOP ARCHIVE | WSOP Classic Archive | WSOP Classic Archive |
| wsop-circuit | WSOP-C | WSOP Circuit | WSOP Circuit |
| wsop-super-circuit | WSOP-SC | WSOP Super Circuit | WSOP Super Circuit |
| hcl-2025 | 2025 | HCL Season 2025 | HCL Season 2025 |
| hcl-clips | Poker Clip | HCL Best Moments | HCL Best Moments |
| pad-s12 | PAD S12 | Poker After Dark Season 12 | Poker After Dark Season 12 |
| pad-s13 | PAD S13 | Poker After Dark Season 13 | Poker After Dark Season 13 |

### 6.4 Event/File Naming Rules

#### Event Type Display Names

| Internal Code | display_name |
|---------------|--------------|
| ME | Main Event |
| FT | Final Table |
| D1, D1A, D1B | Day 1, Day 1A, Day 1B |
| D2, D3... | Day 2, Day 3... |
| HU | Heads-Up |
| SE | Side Event |

#### File Name → Display Name Conversion Rules

```python
# Rule-based conversion examples
FILE_NAME_PATTERNS = {
    # WSOP patterns
    r"WSOP (\d{4}) Main Event.*Day (\d+)([A-Z]?)":
        "WSOP {1} Main Event Day {2}{3}",
    r"WSOP (\d{4}).*Event #(\d+).*\$(\d+[KM]?) (.+)":
        "WSOP {1} Event #{2} - ${3} {4}",

    # HCL patterns
    r"HCL.*(\d{4}-\d{2}-\d{2}).*(.+)":
        "Hustler Casino Live - {2} ({1})",

    # PAD patterns
    r"PAD S(\d+) EP(\d+)":
        "Poker After Dark S{1} Episode {2}",
}
```

### 6.5 AI-Based Naming Generation (Phase 3 Planned)

#### Process

```
1. Analyze file path/name
   ↓
2. Attempt rule-based matching
   ↓ (If matching fails or info insufficient)
3. Request AI analysis (Gemini/GPT)
   - Pass filename, folder structure, metadata
   - Request viewer-friendly title generation
   ↓
4. Save result (source_type='ai_generated', confidence=0.8)
   ↓
5. Await manual review (verified=false)
   ↓
6. Admin approval → verified=true
```

#### AI Prompt Template

```
Generate a viewer-friendly content title based on the following information:

File path: {file_path}
Filename: {filename}
Folder: {parent_folder}
Content type: {content_type}
Metadata: {metadata}

Requirements:
1. Provide both English and Korean titles
2. Use full names instead of abbreviations
3. Include event day and table information
4. Highlight player information if available
5. Concise title within 100 characters

Output format:
{
  "display_name": "...",
  "display_name_ko": "...",
  "short_name": "...",
  "description": "...",
  "confidence": 0.85
}
```

### 6.6 Consistency Management

#### Patterns Requiring Unification

| Inconsistent Pattern | Unified Rule | Example |
|---------------------|--------------|---------|
| Year position | `{Series} {Year} {Event}` | WSOP 2024 Main Event |
| Day notation | `Day {number}` | Day 1, Day 2 |
| Season notation | `Season {number}` | Season 12 |
| Episode | `Episode {number}` or `EP{number}` | Episode 5 / EP5 |

#### Synonym Dictionary

```python
SYNONYMS = {
    # Abbreviation → Standard English
    "ME": "Main Event",
    "FT": "Final Table",
    "HU": "Heads-Up",
    "EP": "Episode",
    "S": "Season",
    "D1": "Day 1",
    "D2": "Day 2",
}
```

### 6.7 Updated ERD (v1.5.0)

> display_names 테이블 폐기 후, display_title은 각 테이블에 직접 저장됩니다.

```
┌─────────────────────────┐
│       catalogs          │
│─────────────────────────│
│ id (PK)                 │
│ name                    │
│ display_title           │  ← 시청자용 제목
│ title_source            │
│ title_verified          │
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│      subcatalogs        │
│─────────────────────────│
│ id (PK)                 │
│ catalog_id (FK)         │
│ sub1, sub2, sub3        │
│ display_title           │  ← 시청자용 제목
│ title_source            │
│ title_verified          │
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│         files           │
│─────────────────────────│
│ id (PK)                 │
│ filename                │
│ nas_path                │
│ display_title           │  ← 시청자용 제목
│ display_subtitle        │
│ title_source            │
│ title_verified          │
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│         hands           │
│─────────────────────────│
│ id (PK)                 │
│ file_id (FK)            │
│ display_title           │  ← 시청자용 제목
│ title_source            │
│ title_verified          │
└─────────────────────────┘
```

---

## 9. Archive Team Google Sheet 동기화

### 7.1 개요

아카이브 팀이 핸드 태깅 작업을 수행하는 Google Sheet를 pokervod.db hands 테이블과 동기화합니다.

**스프레드시트**: [Metadata Archive](https://docs.google.com/spreadsheets/d/1_RN_W_ZQclSZA0Iez6XniCXVtjkkd5HNZwiT6l-z6d4)

### 7.2 워크시트 구조

각 워크시트는 하나의 이벤트/파일에 대한 핸드 정보를 포함합니다.

| 행 | 내용 |
|----|------|
| 1-2행 | 메타데이터 (무시) |
| 3행 | 헤더 |
| 4행~ | 데이터 |

#### 헤더 컬럼 (3행)

| 컬럼 | 타입 | DB 매핑 | 설명 |
|------|------|---------|------|
| File No. | INTEGER | `hand_number` | 핸드 번호 |
| File Name | TEXT | - | 파일명 (매칭용) |
| Nas Folder Link | TEXT | → `file_id` | NAS 경로 (파일 매칭 키) |
| In | TIME (H:MM:SS) | `start_sec` | 시작 타임코드 |
| Out | TIME (H:MM:SS) | `end_sec` | 종료 타임코드 |
| Hand Grade | TEXT (★~★★★) | `highlight_score` | 하이라이트 등급 (1-3) |
| Hands | TEXT | `cards_shown` | 공개 카드 (예: "AA vs KK") |
| Tag (Player) | TEXT (다중) | `players` | 플레이어 태그 (JSON 배열) |
| Tag (Poker Play) | TEXT (다중) | `tags` | 포커 플레이 태그 (정규화) |
| Tag (Emotion) | TEXT (다중) | `tags` | 감정 태그 (정규화) |

### 7.3 워크시트 자동 처리

워크시트 수가 **동적으로 증가**합니다. 동기화 스크립트는 모든 워크시트를 자동으로 순회합니다.

```python
# 모든 워크시트 동기화
for ws in spreadsheet.worksheets():
    sync_worksheet(ws.title)
```

#### 워크시트 명명 규칙

| 패턴 | 예시 |
|------|------|
| `{Year} {Event}` | "2024 WSOPC LA" |
| `{Year} {Series} {Event} {Day}` | "2025 WSOP Main Event Day 1A" |

### 7.4 태그 정규화 매핑

Google Sheet의 태그를 DB 저장용 정규화된 형태로 변환합니다.

#### Poker Play 태그

| 원본 (시트) | 정규화 (DB) |
|------------|-------------|
| Preflop All-in | `preflop_allin` |
| 4-way All-in | `multiway_allin` |
| Hero Fold | `hero_fold` |
| Nice Fold | `nice_fold` |
| Hero Call | `hero_call` |
| Cooler | `cooler` |
| Badbeat | `badbeat` |
| Suckout | `suckout` |
| Bluff | `bluff` |
| Epic Hand | `epic_hand` |
| Crazy Runout | `crazy_runout` |
| Reversal over Reversal | `reversal` |
| Quads | `quads` |
| Straight Flush | `straight_flush` |
| Royal Flush | `royal_flush` |
| Flush vs Flush | `flush_vs_flush` |
| Set over Set | `set_over_set` |
| KK vs QQ, AA vs KK | `premium_vs_premium` |

#### Emotion 태그

| 원본 (시트) | 정규화 (DB) |
|------------|-------------|
| Absurd | `absurd` |
| Luckbox | `luckbox` |
| Insane | `insane` |
| Brutal | `brutal` |

### 7.5 동기화 흐름

```
┌────────────────────────────────┐
│  Archive Team Google Sheet     │
│  (Metadata Archive)            │
│  ├── 2024 WSOPC LA            │
│  ├── 2025 WSOP Main Event     │
│  ├── 2023 WSOP Paradise       │
│  └── ... (동적 증가)           │
└────────────────┬───────────────┘
                 │ archive_hands_sync.py --sync
                 ▼
┌────────────────────────────────┐
│       pokervod.db hands        │
│  ├── title_source='archive_team'
│  ├── tags (정규화 JSON)        │
│  ├── players (JSON 배열)       │
│  └── highlight_score (1-3)     │
└────────────────┬───────────────┘
                 │ sheets_sync.py --daemon
                 ▼
┌────────────────────────────────┐
│   NAS 관리 Google Sheet        │
│   (pokervod DB Sync)           │
│   └── hands 워크시트           │
└────────────────────────────────┘
```

### 7.6 CLI 사용법

```bash
# 정방향 동기화 (Archive Sheet → DB)
python src/archive_analyzer/archive_hands_sync.py --sync

# 역방향 동기화 (DB → Archive Sheet)
python src/archive_analyzer/archive_hands_sync.py --reverse

# 미리보기 (dry-run)
python src/archive_analyzer/archive_hands_sync.py --dry-run

# 특정 워크시트만
python src/archive_analyzer/archive_hands_sync.py --sheet "2024 WSOPC LA" --sync
```

### 7.7 NAS 경로 → file_id 매칭

워크시트의 `Nas Folder Link` 컬럼으로 DB의 `files.nas_path`와 매칭하여 `file_id`를 찾습니다.

```python
def find_file_id(nas_path: str, filename: str) -> Optional[str]:
    # 1. NAS 경로 정규화 후 정확 매칭
    normalized = normalize_nas_path(nas_path)
    if normalized in file_mapping:
        return file_mapping[normalized]

    # 2. 부분 매칭 (폴더 경로)
    for path, file_id in file_mapping.items():
        if normalized in path or path in normalized:
            return file_id

    # 3. 파일명 검색 (fallback)
    cursor.execute(
        "SELECT id FROM files WHERE LOWER(filename) LIKE ?",
        (f"%{filename.lower()}%",)
    )
```

### 7.8 타임코드 변환

| 형식 | 변환 |
|------|------|
| `H:MM:SS` → `float` | "6:58:55" → 25135.0 |
| `float` → `H:MM:SS` | 25135.0 → "6:58:55" |

```python
def parse_timecode(timecode: str) -> float:
    h, m, s = timecode.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)

def seconds_to_timecode(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}"
```

### 7.9 Hand Grade 변환

| 시트 | DB |
|------|-----|
| ★ | 1 |
| ★★ | 2 |
| ★★★ | 3 |

```python
def parse_hand_grade(grade: str) -> int:
    return grade.count("★")

def grade_to_stars(score: int) -> str:
    return "★" * score
```

---

## 10. 추천 시스템 스키마 (Phase 3)

> **Status**: ✅ 스키마 구현 완료 (마이그레이션: `scripts/migrate_recommendation_schema.py`)
> **목표**: Netflix/Disney+ 스타일 동적 카탈로그 및 개인화 추천
> **다음 단계**: Gorse 연동, API 엔드포인트 구현

### 8.1 개요

| 기능 | 테이블 | 설명 |
|------|--------|------|
| 시청 이력 추적 | `view_events`, `watch_progress` | 이미 존재 ✅ |
| 사용자 선호도 | `user_preferences` | 이미 존재 ✅ |
| 추천 결과 캐싱 | `recommendation_cache` | 신규 |
| 트렌딩/인기 집계 | `trending_scores` | 신규 |
| 홈 화면 Row 설정 | `home_rows`, `user_home_rows` | 신규 |
| 썸네일 개인화 | `artwork_variants`, `artwork_selections` | 신규 |
| A/B 테스트 | `experiments`, `experiment_assignments` | 신규 |
| 사용자 임베딩 | `user_embeddings`, `item_embeddings` | 신규 |

### 8.2 ERD (추천 시스템)

```
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────┐
│     users       │────<│   user_preferences  │     │    files        │
│─────────────────│     │─────────────────────│     │─────────────────│
│ id (PK)         │     │ user_id (FK)        │     │ id (PK)         │
│ username        │     │ item_type           │     │ display_title   │
└────────┬────────┘     │ item_id (FK)        │     └────────┬────────┘
         │              │ feedback_type       │              │
         │              │ score               │              │
         │              └─────────────────────┘              │
         │                                                   │
         ├──────────────────────────────┐                   │
         │                              │                   │
         ▼                              ▼                   │
┌─────────────────────┐     ┌─────────────────────┐        │
│    watch_progress   │     │    view_events      │        │
│─────────────────────│     │─────────────────────│        │
│ user_id (FK)        │     │ user_id (FK)        │        │
│ file_id (FK) ───────┼─────│ file_id (FK) ───────┼────────┘
│ current_position    │     │ hand_id (FK)        │
│ progress_percent    │     │ event_type          │
│ is_completed        │     │ position_sec        │
└─────────────────────┘     │ session_id          │
                            └─────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐
│ recommendation_cache│     │   trending_scores   │
│─────────────────────│     │─────────────────────│
│ user_id (FK)        │     │ file_id (FK)        │
│ rec_type            │     │ time_bucket         │
│ items (JSON)        │     │ view_count          │
│ algorithm           │     │ unique_viewers      │
│ expires_at          │     │ avg_completion      │
│ created_at          │     │ trending_score      │
└─────────────────────┘     └─────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐
│     home_rows       │     │   user_home_rows    │
│─────────────────────│     │─────────────────────│
│ id (PK)             │     │ user_id (FK)        │
│ row_type            │◀────│ row_id (FK)         │
│ title               │     │ position            │
│ algorithm           │     │ is_visible          │
│ default_position    │     │ is_personalized     │
└─────────────────────┘     └─────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐
│  artwork_variants   │     │ artwork_selections  │
│─────────────────────│     │─────────────────────│
│ id (PK)             │     │ user_id (FK)        │
│ file_id (FK)        │     │ file_id (FK)        │
│ variant_type        │     │ artwork_id (FK)     │
│ image_url           │     │ impressions         │
│ focus_player        │     │ clicks              │
│ emotion             │     │ selected_at         │
└─────────────────────┘     └─────────────────────┘
```

### 8.3 신규 테이블 상세

#### recommendation_cache
추천 결과 캐싱 (Gorse/Implicit 연동)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| user_id | VARCHAR(50) FK | 사용자 ID |
| rec_type | VARCHAR(50) | 추천 유형: `personalized`, `similar`, `because_watched`, `trending` |
| context_item_id | VARCHAR(200) NULL | 컨텍스트 아이템 (예: "Because you watched X"의 X) |
| items | JSON | 추천 아이템 리스트 `[{id, score, reason}]` |
| algorithm | VARCHAR(50) | 사용 알고리즘: `gorse`, `implicit`, `lightfm`, `rule_based` |
| model_version | VARCHAR(50) | 모델 버전 |
| expires_at | TIMESTAMP | 만료 시각 |
| created_at | TIMESTAMP | 생성 시각 |

```sql
CREATE TABLE recommendation_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(50) NOT NULL,
    rec_type VARCHAR(50) NOT NULL,
    context_item_id VARCHAR(200),
    items JSON NOT NULL,
    algorithm VARCHAR(50) NOT NULL DEFAULT 'gorse',
    model_version VARCHAR(50),
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, rec_type, context_item_id)
);
CREATE INDEX idx_rec_cache_user ON recommendation_cache(user_id);
CREATE INDEX idx_rec_cache_expires ON recommendation_cache(expires_at);
```

#### trending_scores
실시간 트렌딩/인기도 집계 (Netflix Top 10 재현)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| file_id | VARCHAR(200) FK | 파일 ID |
| catalog_id | VARCHAR(50) FK | 카탈로그 (WSOP, HCL 등) |
| time_bucket | TIMESTAMP | 집계 시간 구간 (1시간 단위) |
| view_count | INTEGER | 조회수 |
| unique_viewers | INTEGER | 고유 시청자 수 |
| avg_completion_rate | FLOAT | 평균 완료율 (0-1) |
| avg_watch_duration | FLOAT | 평균 시청 시간 (초) |
| trending_score | FLOAT | 트렌딩 점수 (가중 합산) |
| created_at | TIMESTAMP | 생성 시각 |

```sql
CREATE TABLE trending_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id VARCHAR(200) NOT NULL,
    catalog_id VARCHAR(50),
    time_bucket TIMESTAMP NOT NULL,
    view_count INTEGER DEFAULT 0,
    unique_viewers INTEGER DEFAULT 0,
    avg_completion_rate FLOAT DEFAULT 0,
    avg_watch_duration FLOAT DEFAULT 0,
    trending_score FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(file_id, time_bucket),
    FOREIGN KEY (file_id) REFERENCES files(id),
    FOREIGN KEY (catalog_id) REFERENCES catalogs(id)
);
CREATE INDEX idx_trending_bucket ON trending_scores(time_bucket);
CREATE INDEX idx_trending_score ON trending_scores(trending_score DESC);
CREATE INDEX idx_trending_catalog ON trending_scores(catalog_id, time_bucket);
```

#### home_rows
홈 화면 Row 정의 (Netflix 스타일)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR(50) PK | Row 식별자: `continue_watching`, `trending_wsop`, `because_watched` |
| row_type | VARCHAR(50) | 유형: `continue`, `trending`, `personalized`, `category`, `curated` |
| title | VARCHAR(200) | 표시 제목: "계속 시청하기", "WSOP 인기 영상" |
| title_template | VARCHAR(200) | 동적 제목: "Because you watched {title}" |
| algorithm | VARCHAR(50) | 사용 알고리즘 |
| query_params | JSON | 쿼리 파라미터: `{catalog_id: "WSOP", limit: 20}` |
| default_position | INTEGER | 기본 순서 |
| is_active | BOOLEAN | 활성화 여부 |
| requires_history | BOOLEAN | 시청 기록 필요 여부 |
| min_items | INTEGER | 최소 표시 아이템 수 |
| created_at | TIMESTAMP | 생성 시각 |

```sql
CREATE TABLE home_rows (
    id VARCHAR(50) PRIMARY KEY,
    row_type VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    title_template VARCHAR(200),
    algorithm VARCHAR(50),
    query_params JSON,
    default_position INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    requires_history BOOLEAN DEFAULT FALSE,
    min_items INTEGER DEFAULT 5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 기본 Row 데이터
INSERT INTO home_rows (id, row_type, title, algorithm, default_position, requires_history) VALUES
    ('continue_watching', 'continue', '계속 시청하기', 'watch_progress', 1, TRUE),
    ('trending_all', 'trending', '지금 인기 있는 영상', 'trending_24h', 2, FALSE),
    ('trending_wsop', 'trending', 'WSOP 인기 영상', 'trending_24h', 3, FALSE),
    ('trending_hcl', 'trending', 'HCL 인기 영상', 'trending_24h', 4, FALSE),
    ('new_releases', 'category', '새로 추가된 영상', 'recent', 5, FALSE),
    ('personalized_for_you', 'personalized', '당신을 위한 추천', 'gorse_hybrid', 6, TRUE),
    ('because_watched', 'personalized', '{title} 시청 후 추천', 'similar_items', 7, TRUE),
    ('top_hands', 'curated', '베스트 핸드 모음', 'highlight_score', 8, FALSE),
    ('favorite_players', 'personalized', '즐겨찾는 플레이어', 'player_based', 9, TRUE);
```

#### user_home_rows
사용자별 홈 화면 Row 설정

| 컬럼 | 타입 | 설명 |
|------|------|------|
| user_id | VARCHAR(50) FK | 사용자 ID |
| row_id | VARCHAR(50) FK | Row ID |
| position | INTEGER | 사용자 설정 순서 |
| is_visible | BOOLEAN | 표시 여부 |
| is_personalized | BOOLEAN | 개인화 적용 여부 |
| context_item_id | VARCHAR(200) | 컨텍스트 (예: "Because you watched X"의 X) |
| updated_at | TIMESTAMP | 수정 시각 |

```sql
CREATE TABLE user_home_rows (
    user_id VARCHAR(50) NOT NULL,
    row_id VARCHAR(50) NOT NULL,
    position INTEGER,
    is_visible BOOLEAN DEFAULT TRUE,
    is_personalized BOOLEAN DEFAULT TRUE,
    context_item_id VARCHAR(200),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, row_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (row_id) REFERENCES home_rows(id)
);
```

#### artwork_variants
파일별 썸네일 변형 (Netflix Artwork Personalization)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| file_id | VARCHAR(200) FK | 파일 ID |
| variant_type | VARCHAR(50) | 유형: `default`, `player_focused`, `action`, `emotion` |
| image_url | TEXT | 이미지 URL |
| thumbnail_time_sec | FLOAT | 썸네일 추출 시간 (초) |
| focus_player | VARCHAR(100) | 강조 플레이어 |
| dominant_emotion | VARCHAR(50) | 주요 감정: `excitement`, `tension`, `celebration` |
| tags | JSON | 추가 태그: `["all_in", "showdown"]` |
| generated_by | VARCHAR(50) | 생성 방식: `ffmpeg`, `ai_generated`, `manual` |
| created_at | TIMESTAMP | 생성 시각 |

```sql
CREATE TABLE artwork_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id VARCHAR(200) NOT NULL,
    variant_type VARCHAR(50) NOT NULL DEFAULT 'default',
    image_url TEXT NOT NULL,
    thumbnail_time_sec FLOAT,
    focus_player VARCHAR(100),
    dominant_emotion VARCHAR(50),
    tags JSON,
    generated_by VARCHAR(50) DEFAULT 'ffmpeg',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES files(id)
);
CREATE INDEX idx_artwork_file ON artwork_variants(file_id);
CREATE INDEX idx_artwork_player ON artwork_variants(focus_player);
```

#### artwork_selections
사용자별 썸네일 선택 기록 (Contextual Bandit 학습용)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| user_id | VARCHAR(50) FK | 사용자 ID |
| file_id | VARCHAR(200) FK | 파일 ID |
| artwork_id | INTEGER FK | 선택된 썸네일 ID |
| impressions | INTEGER | 노출 횟수 |
| clicks | INTEGER | 클릭 횟수 |
| context | JSON | 컨텍스트: `{row_id, position, device}` |
| selected_at | TIMESTAMP | 마지막 선택 시각 |

```sql
CREATE TABLE artwork_selections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(50) NOT NULL,
    file_id VARCHAR(200) NOT NULL,
    artwork_id INTEGER NOT NULL,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    context JSON,
    selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, file_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (file_id) REFERENCES files(id),
    FOREIGN KEY (artwork_id) REFERENCES artwork_variants(id)
);
```

#### experiments
A/B 테스트 실험 정의

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR(50) PK | 실험 ID: `rec_algo_v2`, `artwork_personalization` |
| name | VARCHAR(200) | 실험명 |
| description | TEXT | 설명 |
| variants | JSON | 변형: `[{id: "control", weight: 50}, {id: "treatment", weight: 50}]` |
| target_metric | VARCHAR(100) | 목표 지표: `ctr`, `watch_time`, `completion_rate` |
| start_date | TIMESTAMP | 시작일 |
| end_date | TIMESTAMP | 종료일 |
| status | VARCHAR(20) | 상태: `draft`, `running`, `paused`, `completed` |
| created_at | TIMESTAMP | 생성 시각 |

```sql
CREATE TABLE experiments (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    variants JSON NOT NULL,
    target_metric VARCHAR(100),
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    status VARCHAR(20) DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### experiment_assignments
사용자별 실험 할당

| 컬럼 | 타입 | 설명 |
|------|------|------|
| user_id | VARCHAR(50) FK | 사용자 ID |
| experiment_id | VARCHAR(50) FK | 실험 ID |
| variant_id | VARCHAR(50) | 할당된 변형 ID |
| assigned_at | TIMESTAMP | 할당 시각 |

```sql
CREATE TABLE experiment_assignments (
    user_id VARCHAR(50) NOT NULL,
    experiment_id VARCHAR(50) NOT NULL,
    variant_id VARCHAR(50) NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, experiment_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
);
```

#### user_embeddings
사용자 임베딩 벡터 (Gorse/Implicit 연동)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| user_id | VARCHAR(50) PK | 사용자 ID |
| embedding | BLOB | 임베딩 벡터 (numpy array serialized) |
| algorithm | VARCHAR(50) | 알고리즘: `implicit_als`, `lightfm`, `gorse` |
| model_version | VARCHAR(50) | 모델 버전 |
| updated_at | TIMESTAMP | 갱신 시각 |

```sql
CREATE TABLE user_embeddings (
    user_id VARCHAR(50) PRIMARY KEY,
    embedding BLOB NOT NULL,
    algorithm VARCHAR(50) NOT NULL,
    model_version VARCHAR(50),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

#### item_embeddings
아이템 임베딩 벡터

| 컬럼 | 타입 | 설명 |
|------|------|------|
| item_id | VARCHAR(200) PK | 아이템 ID (file_id 또는 hand_id) |
| item_type | VARCHAR(50) | 아이템 유형: `file`, `hand` |
| embedding | BLOB | 임베딩 벡터 |
| algorithm | VARCHAR(50) | 알고리즘 |
| model_version | VARCHAR(50) | 모델 버전 |
| updated_at | TIMESTAMP | 갱신 시각 |

```sql
CREATE TABLE item_embeddings (
    item_id VARCHAR(200) NOT NULL,
    item_type VARCHAR(50) NOT NULL,
    embedding BLOB NOT NULL,
    algorithm VARCHAR(50) NOT NULL,
    model_version VARCHAR(50),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (item_id, item_type)
);
```

### 8.4 기존 테이블 활용

#### view_events (이미 존재)
```sql
-- 사용 예시: 추천 시스템 학습 데이터
SELECT user_id, file_id, event_type, position_sec
FROM view_events
WHERE event_type IN ('play', 'pause', 'complete', 'skip')
ORDER BY created_at;
```

#### watch_progress (이미 존재)
```sql
-- 사용 예시: "계속 시청하기" Row
SELECT file_id, current_position_sec, progress_percent
FROM watch_progress
WHERE user_id = ? AND is_completed = FALSE
ORDER BY last_watched_at DESC
LIMIT 20;
```

#### user_preferences (이미 존재)
```sql
-- 사용 예시: 좋아요/싫어요 피드백
SELECT item_type, item_id, feedback_type, score
FROM user_preferences
WHERE user_id = ?;
```

### 8.5 트렌딩 점수 계산

```python
def calculate_trending_score(
    view_count: int,
    unique_viewers: int,
    avg_completion_rate: float,
    hours_since_upload: float
) -> float:
    """Netflix 스타일 트렌딩 점수 계산

    공식: (views * completion * decay) / time_factor
    """
    # 가중치
    VIEW_WEIGHT = 1.0
    VIEWER_WEIGHT = 2.0  # 고유 시청자 더 중요
    COMPLETION_WEIGHT = 3.0  # 완료율 가장 중요

    # 시간 감쇠 (24시간 반감기)
    time_decay = 0.5 ** (hours_since_upload / 24)

    # 트렌딩 점수
    score = (
        view_count * VIEW_WEIGHT +
        unique_viewers * VIEWER_WEIGHT +
        avg_completion_rate * 100 * COMPLETION_WEIGHT
    ) * time_decay

    return round(score, 2)
```

### 8.6 홈 화면 API 예시

```python
# FastAPI 엔드포인트
@app.get("/api/home/{user_id}")
async def get_home_rows(user_id: str):
    """Netflix 스타일 홈 화면 Row 반환"""
    rows = []

    # 1. 계속 시청하기
    continue_watching = await get_continue_watching(user_id)
    if len(continue_watching) >= 1:
        rows.append({
            "id": "continue_watching",
            "title": "계속 시청하기",
            "items": continue_watching
        })

    # 2. 트렌딩 (전체)
    trending = await get_trending(catalog_id=None, hours=24)
    rows.append({
        "id": "trending_all",
        "title": "지금 인기 있는 영상",
        "items": trending
    })

    # 3. 개인화 추천 (Gorse)
    personalized = await gorse_client.get_recommend(user_id, n=20)
    if personalized:
        rows.append({
            "id": "personalized_for_you",
            "title": "당신을 위한 추천",
            "items": personalized
        })

    # 4. "Because you watched X"
    recent_watch = await get_recent_completed(user_id, limit=1)
    if recent_watch:
        similar = await get_similar_items(recent_watch[0].file_id)
        rows.append({
            "id": "because_watched",
            "title": f"'{recent_watch[0].title}' 시청 후 추천",
            "items": similar
        })

    return {"rows": rows}
```

### 8.7 마이그레이션 계획

| Phase | 작업 | 테이블 | 예상 시간 |
|-------|------|--------|----------|
| 1 | 기본 추천 인프라 | `recommendation_cache`, `trending_scores` | 1주 |
| 2 | 홈 화면 Row | `home_rows`, `user_home_rows` | 1주 |
| 3 | 썸네일 개인화 | `artwork_variants`, `artwork_selections` | 2주 |
| 4 | A/B 테스트 | `experiments`, `experiment_assignments` | 1주 |
| 5 | 임베딩 저장 | `user_embeddings`, `item_embeddings` | 1주 |

### 8.8 Gorse 연동

```yaml
# docker-compose.gorse.yml
services:
  gorse:
    image: zhenghaoz/gorse-in-one:latest
    ports:
      - "8086:8086"  # REST API
      - "8088:8088"  # Dashboard
    environment:
      GORSE_CACHE_STORE: redis://redis:6379/0
      GORSE_DATA_STORE: sqlite:///var/lib/gorse/data.db
    volumes:
      - gorse_data:/var/lib/gorse

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
```

```python
# Gorse 클라이언트 연동
from gorse import Gorse

gorse = Gorse("http://localhost:8086", "api_key")

# 사용자 피드백 전송
async def send_feedback(user_id: str, file_id: str, feedback_type: str):
    await gorse.insert_feedback(feedback_type, user_id, file_id)

# 추천 요청
async def get_recommendations(user_id: str, n: int = 20):
    return await gorse.get_recommend(user_id, n=n)
```

---

## 11. 멀티 카탈로그 시스템 (Phase 3)

> **Status**: 구현 완료
> **목표**: 하나의 콘텐츠가 여러 카탈로그/컬렉션에 속할 수 있도록 N:N 관계 지원

### 9.1 개요

기존에는 `files → events → tournaments → subcatalogs → catalogs` 단방향 계층 구조로,
하나의 파일은 하나의 카탈로그에만 속할 수 있었습니다.

멀티 카탈로그 시스템은 다음을 지원합니다:
- **플레이어 컬렉션**: Phil Ivey가 등장하는 모든 영상
- **태그 컬렉션**: 블러프, 쿨러, 올인 등 태그별 영상
- **큐레이션 컬렉션**: 베스트 핸드, 역대급 핸드 등
- **동적 컬렉션**: 이번 주 업로드, 가장 많이 본 영상 등

### 9.2 ERD (멀티 카탈로그)

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   files     │────<│  file_catalogs   │>────│  catalogs   │
│─────────────│     │──────────────────│     │─────────────│
│ id (PK)     │     │ file_id (FK)     │     │ id (PK)     │
│ event_id    │     │ catalog_id (FK)  │     │ name        │
│ ...         │     │ subcatalog_id    │     │ ...         │
└─────────────┘     │ is_primary       │     └─────────────┘
                    │ added_by         │
                    │ added_reason     │
                    └──────────────────┘

┌───────────────────────┐     ┌──────────────────┐
│  catalog_collections  │────<│ collection_items │
│───────────────────────│     │──────────────────│
│ id (PK)               │     │ collection_id    │
│ name                  │     │ file_id (FK)     │
│ collection_type       │     │ display_order    │
│ is_dynamic            │     │ added_at         │
│ filter_query          │     └──────────────────┘
│ display_order         │
└───────────────────────┘
```

### 9.3 테이블 상세

#### file_catalogs
파일-카탈로그 N:N 연결 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| file_id | VARCHAR(200) FK | 파일 ID |
| catalog_id | VARCHAR(50) FK | 카탈로그 ID |
| subcatalog_id | VARCHAR(100) FK | 서브카탈로그 ID (선택) |
| is_primary | BOOLEAN | 원본 카탈로그 여부 (TRUE=계층 구조에서 자동 설정) |
| display_order | INTEGER | 표시 순서 |
| added_by | VARCHAR(50) | 추가자: `system`, `migration`, `admin`, `ai` |
| added_reason | VARCHAR(200) | 추가 사유 |
| created_at | TIMESTAMP | 생성 시각 |

```sql
CREATE TABLE file_catalogs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id VARCHAR(200) NOT NULL,
    catalog_id VARCHAR(50) NOT NULL,
    subcatalog_id VARCHAR(100),
    is_primary BOOLEAN DEFAULT FALSE,
    display_order INTEGER DEFAULT 0,
    added_by VARCHAR(50) DEFAULT 'system',
    added_reason VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(file_id, catalog_id),
    FOREIGN KEY (file_id) REFERENCES files(id),
    FOREIGN KEY (catalog_id) REFERENCES catalogs(id),
    FOREIGN KEY (subcatalog_id) REFERENCES subcatalogs(id)
);
CREATE INDEX idx_file_catalogs_file ON file_catalogs(file_id);
CREATE INDEX idx_file_catalogs_catalog ON file_catalogs(catalog_id);
CREATE INDEX idx_file_catalogs_subcatalog ON file_catalogs(subcatalog_id);
CREATE INDEX idx_file_catalogs_primary ON file_catalogs(is_primary);
```

#### catalog_collections
컬렉션 정의 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR(100) PK | 컬렉션 ID: `highlights`, `player-phil-ivey`, `tag-bluff` |
| name | VARCHAR(200) | 표시 이름 |
| description | TEXT | 설명 |
| collection_type | VARCHAR(50) | 유형: `curated`, `player`, `tag`, `dynamic` |
| cover_image_url | TEXT | 커버 이미지 URL |
| is_dynamic | BOOLEAN | 동적 컬렉션 여부 (자동 업데이트) |
| filter_query | JSON | 동적 필터 조건: `{"player": "Phil Ivey"}`, `{"tag": "bluff"}` |
| display_order | INTEGER | 표시 순서 |
| is_active | BOOLEAN | 활성화 여부 |
| created_by | VARCHAR(50) | 생성자 |
| created_at | TIMESTAMP | 생성 시각 |
| updated_at | TIMESTAMP | 수정 시각 |

```sql
CREATE TABLE catalog_collections (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    collection_type VARCHAR(50) NOT NULL DEFAULT 'curated',
    cover_image_url TEXT,
    is_dynamic BOOLEAN DEFAULT FALSE,
    filter_query JSON,
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### collection_items
컬렉션-파일 연결 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| collection_id | VARCHAR(100) FK | 컬렉션 ID |
| file_id | VARCHAR(200) FK | 파일 ID |
| display_order | INTEGER | 컬렉션 내 표시 순서 |
| added_at | TIMESTAMP | 추가 시각 |

```sql
CREATE TABLE collection_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id VARCHAR(100) NOT NULL,
    file_id VARCHAR(200) NOT NULL,
    display_order INTEGER DEFAULT 0,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(collection_id, file_id),
    FOREIGN KEY (collection_id) REFERENCES catalog_collections(id),
    FOREIGN KEY (file_id) REFERENCES files(id)
);
CREATE INDEX idx_collection_items_collection ON collection_items(collection_id);
CREATE INDEX idx_collection_items_file ON collection_items(file_id);
```

### 9.4 기본 컬렉션

| ID | 이름 | 유형 | 동적 | 필터 |
|----|------|------|------|------|
| `highlights` | 베스트 핸드 | curated | ❌ | - |
| `epic-hands` | 역대급 핸드 | curated | ❌ | - |
| `player-phil-ivey` | Phil Ivey | player | ✅ | `{"player": "Phil Ivey"}` |
| `player-tom-dwan` | Tom Dwan | player | ✅ | `{"player": "Tom Dwan"}` |
| `player-daniel-negreanu` | Daniel Negreanu | player | ✅ | `{"player": "Daniel Negreanu"}` |
| `tag-bluff` | 블러프 명장면 | tag | ✅ | `{"tag": "bluff"}` |
| `tag-cooler` | 쿨러 핸드 | tag | ✅ | `{"tag": "cooler"}` |
| `tag-allin` | 올인 명승부 | tag | ✅ | `{"tags": ["preflop_allin", "multiway_allin"]}` |
| `recent-week` | 이번 주 업로드 | dynamic | ✅ | `{"days": 7}` |
| `most-viewed` | 가장 많이 본 영상 | dynamic | ✅ | `{"sort": "view_count", "limit": 100}` |

### 9.5 사용 예시

#### 파일의 모든 카탈로그 조회
```sql
SELECT fc.catalog_id, c.name, fc.is_primary, fc.added_reason
FROM file_catalogs fc
JOIN catalogs c ON fc.catalog_id = c.id
WHERE fc.file_id = '1231';
```

#### 멀티 카탈로그 파일 찾기
```sql
SELECT file_id, GROUP_CONCAT(catalog_id) as catalogs, COUNT(*) as cnt
FROM file_catalogs
GROUP BY file_id
HAVING cnt > 1;
```

#### 플레이어 컬렉션에 파일 추가
```sql
-- 수동 추가 (curated 컬렉션)
INSERT INTO collection_items (collection_id, file_id, display_order)
VALUES ('player-phil-ivey', '1231', 1);

-- 또는 file_catalogs로 가상 카탈로그 추가
INSERT INTO file_catalogs (file_id, catalog_id, added_by, added_reason)
VALUES ('1231', 'highlights', 'admin', 'Selected as best hand');
```

#### 동적 컬렉션 쿼리 예시
```python
# 플레이어 컬렉션 (is_dynamic=TRUE)
async def get_player_collection_items(player_name: str):
    return await db.execute('''
        SELECT f.* FROM files f
        JOIN hands h ON h.file_id = f.id
        WHERE JSON_EXTRACT(h.players, '$') LIKE ?
        ORDER BY f.created_at DESC
    ''', (f'%{player_name}%',))

# 태그 컬렉션
async def get_tag_collection_items(tag: str):
    return await db.execute('''
        SELECT DISTINCT f.* FROM files f
        JOIN hands h ON h.file_id = f.id
        WHERE JSON_EXTRACT(h.tags, '$') LIKE ?
        ORDER BY h.highlight_score DESC
    ''', (f'%{tag}%',))
```

### 9.6 마이그레이션

기존 계층 구조에서 `file_catalogs`로 자동 마이그레이션:

```bash
# 시뮬레이션
python scripts/migrate_multi_catalog.py --dry-run

# 실행
python scripts/migrate_multi_catalog.py

# 검증
python scripts/migrate_multi_catalog.py --verify

# 통계
python scripts/migrate_multi_catalog.py --stats

# 롤백
python scripts/migrate_multi_catalog.py --rollback
```

### 9.7 API 연동

```python
# FastAPI 엔드포인트 예시
@app.get("/api/files/{file_id}/catalogs")
async def get_file_catalogs(file_id: str):
    """파일이 속한 모든 카탈로그 조회"""
    catalogs = await db.execute('''
        SELECT c.id, c.name, fc.is_primary
        FROM file_catalogs fc
        JOIN catalogs c ON fc.catalog_id = c.id
        WHERE fc.file_id = ?
    ''', (file_id,))
    return {"catalogs": catalogs}

@app.post("/api/files/{file_id}/catalogs")
async def add_file_to_catalog(file_id: str, catalog_id: str, reason: str = None):
    """파일을 카탈로그에 추가"""
    await db.execute('''
        INSERT OR IGNORE INTO file_catalogs
        (file_id, catalog_id, added_by, added_reason)
        VALUES (?, ?, 'admin', ?)
    ''', (file_id, catalog_id, reason))
    return {"status": "success"}

@app.get("/api/collections/{collection_id}/items")
async def get_collection_items(collection_id: str, limit: int = 50):
    """컬렉션 아이템 조회"""
    collection = await db.execute(
        "SELECT * FROM catalog_collections WHERE id = ?",
        (collection_id,)
    )

    if collection['is_dynamic']:
        # 동적 컬렉션: filter_query로 실시간 조회
        return await execute_dynamic_filter(collection['filter_query'], limit)
    else:
        # 정적 컬렉션: collection_items에서 조회
        items = await db.execute('''
            SELECT f.* FROM collection_items ci
            JOIN files f ON ci.file_id = f.id
            WHERE ci.collection_id = ?
            ORDER BY ci.display_order
            LIMIT ?
        ''', (collection_id, limit))
        return {"items": items}
```

---

## 12. 사용자 및 인증 시스템

### 10.1 users
사용자 계정 정보 (Google OAuth 지원)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR(50) PK | 사용자 ID |
| username | VARCHAR(100) NOT NULL | 사용자명 |
| email | VARCHAR(200) | 이메일 |
| hashed_password | VARCHAR(255) | 비밀번호 해시 (로컬 인증) |
| display_name | VARCHAR(100) | 표시 이름 |
| avatar_url | TEXT | 프로필 이미지 URL |
| preferred_language | VARCHAR(10) | 선호 언어 |
| autoplay_enabled | BOOLEAN | 자동재생 설정 |
| is_active | BOOLEAN | 활성 상태 |
| is_admin | BOOLEAN | 관리자 여부 |
| created_at | TIMESTAMP | 생성일시 |
| last_login_at | TIMESTAMP | 마지막 로그인 |
| is_approved | BOOLEAN | 승인 상태 (기본: 0) |
| approved_by | VARCHAR(50) | 승인자 |
| approved_at | TIMESTAMP | 승인일시 |
| rejection_reason | TEXT | 거절 사유 |
| google_id | VARCHAR(100) | Google OAuth ID |
| google_email | VARCHAR(200) | Google 이메일 |
| google_picture | TEXT | Google 프로필 이미지 |
| auth_provider | VARCHAR(20) | 인증 방식 (local/google) |

### 10.2 user_sessions
사용자 세션 관리

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR(100) PK | 세션 ID |
| user_id | VARCHAR(50) FK | 사용자 ID |
| device_type | VARCHAR(50) | 디바이스 유형 |
| browser | VARCHAR(100) | 브라우저 |
| os | VARCHAR(100) | OS |
| ip_address | VARCHAR(45) | IP 주소 |
| refresh_token_hash | VARCHAR(255) | 리프레시 토큰 해시 |
| expires_at | TIMESTAMP NOT NULL | 만료일시 |
| is_active | BOOLEAN | 활성 상태 |
| revoked_at | TIMESTAMP | 폐기일시 |
| created_at | TIMESTAMP | 생성일시 |
| last_activity_at | TIMESTAMP | 마지막 활동일시 |

### 10.3 user_preferences
사용자 선호도/피드백 (좋아요/싫어요)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| user_id | VARCHAR(50) FK | 사용자 ID |
| item_type | VARCHAR(50) | 아이템 유형 (file/hand/player) |
| item_id | VARCHAR(200) | 아이템 ID |
| feedback_type | VARCHAR(20) | 피드백 유형 (like/dislike/bookmark) |
| score | FLOAT | 점수 |
| created_at | TIMESTAMP | 생성일시 |

### 10.4 view_events
시청 이벤트 로그

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| user_id | VARCHAR(50) | 사용자 ID |
| file_id | VARCHAR(200) | 파일 ID |
| hand_id | INTEGER | 핸드 ID |
| event_type | VARCHAR(50) NOT NULL | 이벤트 유형 (play/pause/seek/complete) |
| position_sec | FLOAT | 재생 위치 (초) |
| session_id | VARCHAR(100) | 세션 ID |
| device_type | VARCHAR(50) | 디바이스 유형 |
| referrer | TEXT | 유입 경로 |
| created_at | TIMESTAMP | 생성일시 |

### 10.5 watch_progress
시청 진행 상태 (계속 시청하기)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| user_id | VARCHAR(50) FK | 사용자 ID |
| file_id | VARCHAR(200) FK | 파일 ID |
| current_position_sec | FLOAT | 현재 위치 (초) |
| duration_sec | FLOAT | 전체 길이 (초) |
| progress_percent | FLOAT | 진행률 (0-100) |
| is_completed | BOOLEAN | 완료 여부 |
| started_at | TIMESTAMP | 시작일시 |
| last_watched_at | TIMESTAMP | 마지막 시청일시 |
| completed_at | TIMESTAMP | 완료일시 |

---

## 13. 검색 시스템 (wsoptv_*)

### 11.1 wsoptv_search_index
통합 검색 인덱스

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| entity_type | VARCHAR(20) NOT NULL | 엔티티 유형 (player/hand/file) |
| entity_id | INTEGER NOT NULL | 엔티티 ID |
| search_vector | TEXT | 검색용 텍스트 |
| normalized_text | TEXT | 정규화된 텍스트 |
| player_ids | JSON | 관련 플레이어 ID 배열 |
| tournament_id | VARCHAR(100) | 토너먼트 ID |
| pot_size | FLOAT | 팟 크기 |
| action_types | JSON | 액션 유형 배열 |
| title | VARCHAR(500) | 제목 |
| description | TEXT | 설명 |
| thumbnail_url | VARCHAR(500) | 썸네일 URL |
| source_updated_at | TIMESTAMP | 원본 수정일시 |
| indexed_at | TIMESTAMP | 인덱싱일시 |

### 11.2 wsoptv_search_history
검색 기록

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| user_id | VARCHAR(100) | 사용자 ID |
| session_id | VARCHAR(100) | 세션 ID |
| query | TEXT NOT NULL | 검색어 |
| parsed_query | JSON | 파싱된 쿼리 |
| results_count | INTEGER | 결과 수 |
| clicked_entity_type | VARCHAR(20) | 클릭된 엔티티 유형 |
| clicked_entity_id | INTEGER | 클릭된 엔티티 ID |
| search_latency_ms | INTEGER | 검색 소요시간 (ms) |
| created_at | TIMESTAMP | 생성일시 |

### 11.3 wsoptv_popular_searches
인기 검색어

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| query | TEXT NOT NULL | 검색어 |
| normalized_query | TEXT | 정규화된 검색어 |
| search_count | INTEGER | 검색 횟수 |
| click_count | INTEGER | 클릭 횟수 |
| first_searched_at | TIMESTAMP | 최초 검색일시 |
| last_searched_at | TIMESTAMP | 마지막 검색일시 |

### 11.4 wsoptv_player_aliases
플레이어 별칭/별명

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| player_id | INTEGER NOT NULL | 플레이어 ID |
| canonical_name | VARCHAR(200) NOT NULL | 정식 이름 |
| alias | VARCHAR(100) NOT NULL | 별칭 |
| alias_type | VARCHAR(20) | 별칭 유형 (nickname/typo/variant) |
| confidence | FLOAT | 신뢰도 |
| created_at | TIMESTAMP | 생성일시 |
| is_verified | BOOLEAN | 검증 여부 |

### 11.5 wsoptv_choseong_index
한글 초성 검색 인덱스

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| player_id | INTEGER NOT NULL | 플레이어 ID |
| korean_name | VARCHAR(100) | 한글 이름 |
| choseong | VARCHAR(50) | 초성 (ㄴㄱㄹㄴ) |
| romanization | VARCHAR(100) | 로마자 표기 |

---

## 14. V3.0 스키마 설계 (Video Card 중심)

> ✅ **구현 상태**: 마이그레이션 스크립트 구현 완료
>
> 구현 항목:
> - [x] `scripts/migrate_v3_schema.py` 마이그레이션 스크립트
> - [x] 새 테이블 DDL (series, contents, content_players, content_tags, tags)
> - [x] 기존 데이터 마이그레이션 (subcatalogs+tournaments+events → series)
> - [x] 호환성 뷰 (v_files, v_hands)
> - [x] Headline 자동 생성 로직

### 12.1 설계 배경

#### 현재 문제점

1. **5단계 계층 구조의 복잡성**
   ```
   catalogs → subcatalogs → tournaments → events → files/hands
   ```
   - subcatalogs vs tournaments 역할 중복 (둘 다 연도별 분류)
   - events 테이블 용도 불명확
   - 파일 조회 시 5개 테이블 JOIN 필요

2. **Video Card 표시 문제**
   - 현재: `"Hand #1 | Winner: NEGREANU"` - 기계적, 스토리 없음
   - 시청자 관심 유발 실패
   - CTR 최적화 불가

3. **연구 결과** (OTT 플랫폼 분석)
   - Netflix/YouTube: 3단계 계층 (채널/시리즈/에피소드)
   - Jellyfin/Kodi: `tvshow → season → episode` 패턴
   - PokerGO: 토너먼트/시즌 기반 + 클립 하이라이트

### 12.2 제안: 3단계 계층 구조

```
catalogs → series → contents
   ↓         ↓         ↓
 브랜드    시리즈    콘텐츠(에피소드+클립)
```

#### 핵심 변경

| 현재 | V3.0 | 설명 |
|------|------|------|
| catalogs | catalogs | 유지 (WSOP, HCL, PAD) |
| subcatalogs + tournaments + events | **series** | 통합 (연도/시즌/이벤트) |
| files + hands | **contents** | 통합 (에피소드/클립 구분) |

### 12.3 새로운 테이블 정의

#### 12.3.1 catalogs (간소화)

```sql
CREATE TABLE catalogs (
    id INTEGER PRIMARY KEY,
    slug VARCHAR(50) UNIQUE NOT NULL,        -- 'wsop', 'hcl', 'pad'
    name VARCHAR(100) NOT NULL,              -- 'World Series of Poker'
    display_title VARCHAR(200),              -- 카드 표시용
    logo_url TEXT,
    banner_url TEXT,
    series_count INTEGER DEFAULT 0,          -- 캐시된 시리즈 수
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 12.3.2 series (통합)

subcatalogs + tournaments + events를 하나로 통합:

```sql
CREATE TABLE series (
    id INTEGER PRIMARY KEY,
    catalog_id INTEGER NOT NULL REFERENCES catalogs(id),
    slug VARCHAR(100) UNIQUE NOT NULL,       -- 'wsop-main-event-2024'

    -- 표시 정보
    title VARCHAR(300) NOT NULL,             -- 'WSOP Main Event 2024'
    subtitle VARCHAR(200),                   -- '$10,000 No-Limit Hold'em'
    description TEXT,

    -- 분류 정보
    year INTEGER,                            -- 2024
    season INTEGER,                          -- 시즌 번호 (HCL S12 등)
    location VARCHAR(100),                   -- 'Las Vegas'
    event_type VARCHAR(50),                  -- 'main_event', 'side_event', 'cash_game'

    -- 메타 정보
    thumbnail_url TEXT,
    banner_url TEXT,
    episode_count INTEGER DEFAULT 0,         -- 캐시된 에피소드 수
    clip_count INTEGER DEFAULT 0,            -- 캐시된 클립 수
    total_duration_sec FLOAT DEFAULT 0,      -- 총 재생 시간

    -- 정렬/표시
    sort_order INTEGER DEFAULT 0,
    is_featured BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_series_catalog ON series(catalog_id);
CREATE INDEX idx_series_year ON series(year);
CREATE INDEX idx_series_featured ON series(is_featured);
```

#### 12.3.3 contents (통합)

files + hands를 단일 테이블로 통합 (content_type으로 구분):

```sql
CREATE TABLE contents (
    id INTEGER PRIMARY KEY,
    series_id INTEGER NOT NULL REFERENCES series(id),
    content_type VARCHAR(20) NOT NULL,       -- 'episode' | 'clip'

    -- Video Card 핵심 필드 (스토리텔링)
    headline VARCHAR(300) NOT NULL,          -- "Negreanu의 역대급 블러프"
    subline VARCHAR(300),                    -- "Main Event Day 7 | $2.5M Pot"
    thumbnail_url TEXT,
    thumbnail_text VARCHAR(50),              -- 썸네일 오버레이 텍스트 (0-3 단어)

    -- 미디어 정보
    duration_sec FLOAT,
    resolution VARCHAR(20),                  -- '1080p', '4K'
    codec VARCHAR(50),

    -- 표시 요소
    featured_text VARCHAR(200),              -- "역대 최대 팟" 배지
    badges JSON,                             -- ["FINAL TABLE", "ALL-IN"]

    -- Episode 전용 필드
    episode_number INTEGER,                  -- 에피소드 번호
    hand_count INTEGER,                      -- 포함된 핸드 수

    -- Clip 전용 필드
    parent_episode_id INTEGER REFERENCES contents(id),
    start_sec FLOAT,                         -- 클립 시작 시간
    end_sec FLOAT,                           -- 클립 종료 시간
    winner VARCHAR(100),                     -- 승자
    pot_size_bb FLOAT,                       -- 팟 크기 (BB 단위)
    action_type VARCHAR(50),                 -- 'bluff', 'hero_call', 'cooler', 'bad_beat'

    -- 파일 참조
    nas_path TEXT UNIQUE,                    -- NAS 파일 경로
    file_size_bytes BIGINT,

    -- 통계
    view_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,

    -- 시간 정보
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_content_type CHECK (content_type IN ('episode', 'clip'))
);

CREATE INDEX idx_contents_series ON contents(series_id);
CREATE INDEX idx_contents_type ON contents(content_type);
CREATE INDEX idx_contents_action ON contents(action_type);
CREATE INDEX idx_contents_winner ON contents(winner);
```

#### 12.3.4 content_players (N:N 링크)

Kodi 패턴 적용 - 콘텐츠와 플레이어 다대다 관계:

```sql
CREATE TABLE content_players (
    content_id INTEGER NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'participant',  -- 'winner', 'loser', 'participant'
    position INTEGER,                         -- 표시 순서
    PRIMARY KEY (content_id, player_id)
);

CREATE INDEX idx_content_players_player ON content_players(player_id);
```

#### 12.3.5 content_tags (N:N 링크)

```sql
CREATE TABLE content_tags (
    content_id INTEGER NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (content_id, tag_id)
);

CREATE INDEX idx_content_tags_tag ON content_tags(tag_id);
```

### 12.4 Headline 생성 규칙

Video Card의 핵심은 **스토리텔링 기반 헤드라인**입니다.

#### 12.4.1 액션 타입별 템플릿

```python
HEADLINE_TEMPLATES = {
    'bluff': [
        "{winner}의 역대급 블러프",
        "{winner}, 에어로 {pot}BB 스틸",
        "과감한 블러프! {winner}의 승부수",
    ],
    'hero_call': [
        "{winner}의 소름돋는 히어로콜",
        "믿기 힘든 콜! {winner}의 직감",
        "{winner}, 블러프 간파하다",
    ],
    'bad_beat': [
        "{loser}의 악몽 같은 순간",
        "99% 승률에서 역전당한 {loser}",
        "리버에서 무너진 {loser}",
    ],
    'cooler': [
        "풀하우스 vs 풀하우스! {pot}BB 팟",
        "쿨러 대결! {winner} vs {loser}",
        "피할 수 없는 운명의 대결",
    ],
    'all_in': [
        "{winner} vs {loser}, {pot}BB 올인 대결",
        "올인 쇼다운! 누가 승자인가",
        "{pot}BB를 건 올인 승부",
    ],
    'final_hand': [
        "파이널 핸드! {winner} 우승 확정",
        "{winner}, 마지막 핸드에서 승리",
        "대단원의 막! {winner} 챔피언 등극",
    ],
}
```

#### 12.4.2 Subline 생성 규칙

```python
def generate_subline(content: dict) -> str:
    parts = []

    # 시리즈 컨텍스트
    if content.get('series_title'):
        parts.append(content['series_title'])

    # 진행 상황
    if content.get('episode_number'):
        parts.append(f"Day {content['episode_number']}")

    # 팟 크기 (클립인 경우)
    if content.get('pot_size_bb'):
        pot = content['pot_size_bb']
        if pot >= 1000:
            parts.append(f"${pot/1000:.1f}K Pot")
        else:
            parts.append(f"{pot}BB Pot")

    # 플레이어 수
    if content.get('player_count'):
        parts.append(f"{content['player_count']} Players")

    return " | ".join(parts)
```

#### 12.4.3 Before/After 비교

| 상태 | 현재 (V2) | 제안 (V3) |
|------|-----------|-----------|
| **Headline** | Hand #1 \| Winner: NEGREANU | Negreanu의 역대급 블러프 |
| **Subline** | (없음) | WSOP Main Event Day 7 \| $2.5M Pot |
| **Badge** | (없음) | FINAL TABLE, ALL-IN |
| **Thumbnail Text** | (없음) | "$2.5M" |

### 12.5 Video Card UI 구조

#### 12.5.1 Episode Card

```
┌─────────────────────────────────────┐
│  ┌───────────────────────────────┐  │
│  │                               │  │
│  │         THUMBNAIL             │  │
│  │                               │  │
│  │  ┌──────────┐                 │  │
│  │  │ 8:32:15  │                 │  │
│  │  └──────────┘                 │  │
│  └───────────────────────────────┘  │
│                                     │
│  WSOP Main Event 2024 - Day 7       │  ← headline
│  Final Table | 9 Players            │  ← subline
│                                     │
│  [LIVE] [FINAL TABLE]               │  ← badges
└─────────────────────────────────────┘
```

#### 12.5.2 Clip Card

```
┌─────────────────────────────────────┐
│  ┌───────────────────────────────┐  │
│  │           $2.5M               │  ← thumbnail_text
│  │         THUMBNAIL             │  │
│  │                               │  │
│  │  ┌──────────┐  ┌──────────┐   │  │
│  │  │  3:42    │  │  ALL-IN  │   │  ← duration + badge
│  │  └──────────┘  └──────────┘   │  │
│  └───────────────────────────────┘  │
│                                     │
│  Negreanu의 역대급 블러프           │  ← headline (storytelling)
│  WSOP Main Event Day 7              │  ← subline (context)
│                                     │
│  👤 Negreanu, Ivey                  │  ← featured players
└─────────────────────────────────────┘
```

### 12.6 마이그레이션 전략

#### 12.6.1 단계별 계획

| 단계 | 작업 | 위험도 |
|------|------|--------|
| 1 | series 테이블 생성 + 데이터 마이그레이션 | 낮음 |
| 2 | contents 테이블 생성 + files/hands 통합 | 중간 |
| 3 | content_players, content_tags 생성 | 낮음 |
| 4 | 기존 API 어댑터 레이어 추가 | 낮음 |
| 5 | Headline 생성 배치 작업 | 낮음 |
| 6 | 기존 테이블 deprecation (6개월 후) | - |

#### 12.6.2 마이그레이션 SQL (예시)

```sql
-- 1. subcatalogs + tournaments → series 마이그레이션
INSERT INTO series (catalog_id, slug, title, year, event_type)
SELECT
    c.id,
    LOWER(REPLACE(t.name, ' ', '-')) || '-' || t.year,
    t.name,
    t.year,
    CASE
        WHEN t.name LIKE '%Main Event%' THEN 'main_event'
        WHEN t.name LIKE '%High Roller%' THEN 'high_roller'
        ELSE 'side_event'
    END
FROM tournaments t
JOIN subcatalogs s ON t.subcatalog_id = s.id
JOIN catalogs c ON s.catalog_id = c.id;

-- 2. files → contents (episode) 마이그레이션
INSERT INTO contents (
    series_id, content_type, headline, subline,
    duration_sec, nas_path, file_size_bytes
)
SELECT
    s.id,
    'episode',
    f.display_title,  -- 임시, 추후 Headline 생성
    NULL,
    m.duration_seconds,
    f.nas_path,
    f.file_size
FROM files f
JOIN media_info m ON f.id = m.file_id
JOIN events e ON f.event_id = e.id
JOIN series s ON s.slug = e.series_slug;  -- 매핑 필요

-- 3. hands → contents (clip) 마이그레이션
INSERT INTO contents (
    series_id, content_type, headline, subline,
    parent_episode_id, start_sec, end_sec,
    winner, pot_size_bb, action_type
)
SELECT
    c.series_id,
    'clip',
    h.display_title,  -- 임시, 추후 Headline 생성
    NULL,
    c.id,  -- parent episode
    h.timecode_start_seconds,
    h.timecode_end_seconds,
    h.winner,
    h.pot_bb,
    h.action_types  -- JSON에서 첫 번째 추출
FROM hands h
JOIN contents c ON c.nas_path = h.file_path AND c.content_type = 'episode';
```

### 12.7 호환성 레이어

기존 API 호환을 위한 뷰 제공:

```sql
-- files 테이블 호환 뷰
CREATE VIEW v_files AS
SELECT
    id,
    nas_path,
    headline AS display_title,
    duration_sec AS duration_seconds,
    file_size_bytes AS file_size,
    series_id
FROM contents
WHERE content_type = 'episode';

-- hands 테이블 호환 뷰
CREATE VIEW v_hands AS
SELECT
    c.id,
    c.parent_episode_id AS file_id,
    c.headline AS display_title,
    c.winner,
    c.pot_size_bb AS pot_bb,
    c.action_type,
    c.start_sec AS timecode_start_seconds,
    c.end_sec AS timecode_end_seconds,
    GROUP_CONCAT(p.name) AS players
FROM contents c
LEFT JOIN content_players cp ON c.id = cp.content_id
LEFT JOIN players p ON cp.player_id = p.id
WHERE c.content_type = 'clip'
GROUP BY c.id;
```

### 12.8 CTR 최적화 가이드라인

연구 기반 Video Card 최적화 지침:

| 요소 | 권장 사항 | CTR 영향 |
|------|----------|----------|
| **Thumbnail Text** | 0-3 단어, 금액/숫자 강조 | +20-30% |
| **Headline** | 50-60자, 감정 표현 포함 | +30% |
| **Subline** | 시리즈 컨텍스트 + 핵심 수치 | +15% |
| **Badges** | 최대 2개, 긴급성 표현 | +10% |
| **플레이어 노출** | 유명 플레이어 이름 전면 배치 | +25% |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2025-12-04 | 3.0.0 | **Firestore 마이그레이션 완료** (#59, #61): 프로덕션 클라우드 DB 추가, 7개 컬렉션 5,492 docs, SQLite↔Firestore 동기화 전략 문서화 |
| 2025-12-03 | 2.7.0 | **레거시 테이블 삭제**: pokervod.db에서 7개 레거시 테이블 삭제, DB 크기 5.73MB→4.84MB |
| 2025-12-03 | 2.6.0 | **레거시 스키마 분리**: subcatalogs, tournaments, events, hands, hand_players, hand_tags, id_mapping → `DATABASE_SCHEMA_LEGACY.md` |
| 2025-12-03 | 2.5.1 | **V3.0 스키마 설계 문서 추가** (미구현): 3단계 계층 구조, contents 통합, Headline 생성 규칙 - Section 12 |
| 2025-12-03 | 2.5.0 | **스키마 통합 업데이트**: #12 JSON 정규화 + #13 정수 PK 문서 통합 |
| 2025-12-03 | 2.4.0 | **정수 PK 마이그레이션 1단계**: `varchar_id` 컬럼 추가 (catalogs, subcatalogs, files), `id_mapping` 테이블 |
| 2025-12-03 | 2.3.0 | **JSON 정규화 테이블 추가**: `hand_players`, `hand_tags` 테이블 (hands.players/tags JSON → 관계형) |
| 2025-12-03 | 2.2.0 | 사용자/인증/검색 시스템 테이블 문서화 (Section 10, 11), players 테이블 컬럼 추가 |
| 2025-12-03 | 2.1.0 | 멀티 카탈로그 시스템 추가 (Section 9) |
| 2025-12-03 | 2.0.0 | 추천 시스템 스키마 추가 (Section 8) |
| 2025-11-29 | 1.5.0 | display_names 테이블 폐기, display_title 직접 저장 |
| 2025-11-28 | 1.4.0 | Archive Team Google Sheet 동기화 추가 |
| 2025-11-27 | 1.3.0 | 다단계 서브카탈로그 분류 추가 |
| 2025-11-26 | 1.2.0 | 검색 인덱스 테이블 추가 |
| 2025-11-25 | 1.1.0 | 사용자/시청 기록 테이블 추가 |
| 2025-11-24 | 1.0.0 | 초기 스키마 정의 |
