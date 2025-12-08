# Google Sheets Schema Documentation

> **Version**: 1.1.0
> **Updated**: 2025-12-08
> **Related Code**: `nas_auto_sync.py`, `sheets_sync.py`, `archive_hands_sync.py`
> **Related PRD**: `docs/PRD_NAS_MONITOR.md`

---

## Overview

### NASAutoSync 시스템

DB 구축은 **2가지 데이터 소스**에서 트리거됩니다:

| # | 소스 | 트리거 | 처리 모듈 | 대상 |
|---|------|--------|----------|------|
| 1 | **NAS 파일 변경** | 파일 추가/삭제/이동 | `nas_auto_sync.py` | files 테이블 |
| 2 | **아카이브팀 시트 수정** | Hand 입력/수정 | `archive_hands_sync.py` | hands 테이블 |

### Google Sheets

| 시트 | ID | 용도 |
|------|----|----|
| **Archive Team Sheet** | `1_RN_W_ZQclSZA0Iez6XniCXVtjkkd5HNZwiT6l-z6d4` | 아카이브팀 Hand 입력 |
| **Pokervod Database Sheet** | `1TW2ON5CQyIrL8aGQNYJ4OWkbZMaGmY9DoDG9VFXU60I` | DB 마스터 데이터 관리 |

---

## Data Flow (전체 아키텍처)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          NASAutoSync 시스템                                  │
│                                                                             │
│  ┌─────────────────────┐              ┌─────────────────────┐               │
│  │   [소스 1] NAS      │              │  [소스 2] 시트       │               │
│  │   10.10.100.122     │              │  Archive Team       │               │
│  │   /ARCHIVE/         │              │  Google Sheets      │               │
│  │                     │              │                     │               │
│  │  파일 추가/삭제/이동  │              │  Hand 입력/수정      │               │
│  └──────────┬──────────┘              └──────────┬──────────┘               │
│             │                                    │                          │
│             │ nas_auto_sync.py                   │ archive_hands_sync.py    │
│             │ (30분 폴링)                         │ (1시간 폴링)              │
│             │                                    │                          │
│             ▼                                    ▼                          │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │                      pokervod.db (통합 DB)                        │      │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │      │
│  │  │ files   │ │ hands   │ │ players │ │contents │ │ series  │    │      │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘    │      │
│  └──────────────────────────────┬───────────────────────────────────┘      │
│                                 │                                          │
│                                 │ sheets_sync.py (양방향, 5분 간격)         │
│                                 ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │                   Pokervod Database Sheet                         │      │
│  │                   (DB 테이블 미러링: 13개 탭)                       │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 동기화 흐름 요약

| 방향 | 소스 | 대상 | 모듈 | 주기 |
|------|------|------|------|------|
| NAS → DB | NAS 파일 | pokervod.db:files | `nas_auto_sync.py` | 30분 |
| 시트 → DB | Archive Team Sheet | pokervod.db:hands | `archive_hands_sync.py` | 1시간 |
| DB ↔ 시트 | pokervod.db | Pokervod Sheet | `sheets_sync.py` | 5분 (양방향) |

---

## NAS Auto Sync 상세

### 처리 로직

| 상황 | archive.db | pokervod.db | 동작 |
|------|------------|-------------|------|
| **신규 파일** | 있음 | 없음 | → INSERT |
| **삭제된 파일** | 없음 | 있음 | → DELETE 또는 status='deleted' |
| **이동된 파일** | 경로 변경 | 이전 경로 | → UPDATE nas_path |
| **기존 파일** | 동일 | 동일 | → SKIP |

### 실행 명령어

```powershell
# 데몬 모드 (30분 간격)
python -m archive_analyzer.nas_auto_sync

# 1회 실행
python -m archive_analyzer.nas_auto_sync --once

# 테스트 (DB 미변경)
python -m archive_analyzer.nas_auto_sync --once --dry-run

# 간격 지정 (10분)
python -m archive_analyzer.nas_auto_sync --interval 600
```

---

## 1. Archive Team Sheet (Hand 입력용)

**Spreadsheet ID**: `1_RN_W_ZQclSZA0Iez6XniCXVtjkkd5HNZwiT6l-z6d4`
**Title**: Metadata Archive

### Tab Structure

모든 탭이 동일한 컬럼 구조를 가지며, 이벤트/토너먼트별로 분리:

| 탭 예시 | 내용 |
|---------|------|
| WSOP Super Circuit | WSOP Circuit LA 핸드 |
| HCL | Hustler Casino Live 핸드 |
| PAD | Poker After Dark 핸드 |
| MPP | Mediterranean Poker Party 핸드 |

### Column Schema (33 columns)

| # | Column | Type | Required | Description | Example |
|---|--------|------|----------|-------------|---------|
| 1 | `File No.` | Integer | Yes | Hand 순번 | 1, 2, 3 |
| 2 | `File Name` | Text | Yes | 파일명/이벤트명 | 2024 WSOP Circuit LA - House Warming NL Hold'em [Day 2] |
| 3 | `Nas Folder Link` | URL | No | NAS 폴더 경로 | //10.10.100.122/ARCHIVE/... |
| 4 | `In` | Timecode | Yes | 시작 시간 | 6:58:55 |
| 5 | `Out` | Timecode | Yes | 종료 시간 | 7:00:47 |
| 6 | `Hand Grade` | Stars | No | 하이라이트 점수 (1-3) | ★★★ |
| 7 | `Winner` | Text | No | 승리 핸드 | JJ, QQ, AA |
| 8 | `Hands` | Text | No | 핸드 매치업 | 88 vs JJ, AKo vs KK vs QQ |
| 9-11 | `Tag (Player)` | Text | No | 플레이어명 (최대 3명) | Christina Gollins, Phil Ivey |
| 12-18 | `Tag (Poker Play)` | Text | No | 플레이 태그 (최대 7개) | Preflop All-in, Cooler, Quads |
| 19-20 | `Tag (Emotion)` | Text | No | 감정 태그 (최대 2개) | Luckbox, Stressed, Absurd |
| 21-33 | (Empty) | - | - | 예비 컬럼 | - |

### Row Structure

- **Row 1-2**: 제목/메타 정보 (무시됨)
- **Row 3**: 헤더 행
- **Row 4+**: 데이터 행

### Timecode Format

```
H:MM:SS 또는 HH:MM:SS
예: 6:58:55 → 25135초
    0:12:47 → 767초
```

### Hand Grade

| 입력 | 변환 값 |
|------|--------|
| ★ | 1 |
| ★★ | 2 |
| ★★★ | 3 |
| (빈 값) | 0 |

### Tag Normalization

입력된 태그는 정규화되어 DB에 저장됩니다:

| 입력 | 정규화 |
|------|--------|
| preflop all-in | preflop_allin |
| bad beat | badbeat |
| hero fold | hero_fold |
| 4-way all-in | multiway_allin |
| AA vs KK | premium_vs_premium |
| straight flush | straight_flush |

---

## 2. Pokervod Database Sheet (DB 미러링)

**Spreadsheet ID**: `1TW2ON5CQyIrL8aGQNYJ4OWkbZMaGmY9DoDG9VFXU60I`
**Title**: pokervod-database

### Tab List (13 tabs)

| Tab | Table | Records | Description |
|-----|-------|---------|-------------|
| `catalogs` | catalogs | ~10 | 카탈로그 (WSOP, HCL, PAD, MPP...) |
| `series` | series | ~100+ | 시리즈 (연도/시즌별) |
| `contents` | contents | ~2000+ | 콘텐츠 (에피소드, 클립) |
| `hands` | hands | ~500+ | 하이라이트 핸드 |
| `players` | players | ~500+ | 플레이어 마스터 |
| `tags` | tags | ~10 | 태그 마스터 |
| `files` | files | ~2000+ | 파일 메타데이터 |
| `events` | events | ~200+ | 이벤트 (레거시) |
| `tournaments` | tournaments | ~100+ | 토너먼트 (레거시) |
| `subcatalogs` | subcatalogs | ~50+ | 서브카탈로그 (레거시) |
| `content_players` | content_players | ~3000+ | 콘텐츠-플레이어 연결 |
| `content_tags` | content_tags | ~3000+ | 콘텐츠-태그 연결 |
| `wsoptv_player_aliases` | wsoptv_player_aliases | ~100+ | 플레이어 한글 별칭 |

---

### 2.1 catalogs

카탈로그 마스터 (최상위 분류)

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `id` | Text | PK (slug) | wsop, hcl, mpp |
| `name` | Text | 이름 | WSOP, HCL |
| `description` | Text | 설명 (한글) | World Series of Poker |
| `display_title` | Text | 표시 제목 | World Series of Poker |
| `title_source` | Text | 제목 출처 | rule_based |
| `title_verified` | Boolean | 검증 여부 | TRUE |
| `created_at` | Datetime | 생성일 | 2025-12-03 05:02:32 |
| `updated_at` | Datetime | 수정일 | 2025-12-03 05:02:32 |

---

### 2.2 series

시리즈 (카탈로그 하위)

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `id` | Integer | PK | 1, 2, 3 |
| `catalog_id` | Text | FK → catalogs | wsop, mpp |
| `slug` | Text | URL slug | wsop-2024-main-event |
| `title` | Text | 제목 | WSOP 2024 Main Event |
| `subtitle` | Text | 부제목 | |
| `year` | Integer | 연도 | 2024 |
| `season` | Integer | 시즌 | |
| `location` | Text | 장소 | Las Vegas |
| `event_type` | Text | 이벤트 유형 | tournament |
| `episode_count` | Integer | 에피소드 수 | 8 |
| `clip_count` | Integer | 클립 수 | 21 |
| `total_duration_sec` | Integer | 총 재생시간 (초) | 326725 |
| `sort_order` | Integer | 정렬 순서 | 1 |
| `is_featured` | Boolean | 추천 여부 | FALSE |
| `legacy_*` | Various | 레거시 ID 매핑 | |

---

### 2.3 contents

콘텐츠 (에피소드/클립)

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `id` | Integer | PK | 2525 |
| `series_id` | Integer | FK → series | 1 |
| `content_type` | Text | 유형 | episode, clip |
| `headline` | Text | 제목 | $1M GTD Mystery Bounty |
| `subline` | Text | 부제목 | Day 1A |
| `duration_sec` | Float | 재생시간 (초) | 29549.73 |
| `resolution` | Text | 해상도 | 1920x1080 |
| `codec` | Text | 코덱 | h264 |
| `episode_number` | Integer | 에피소드 번호 | 1 |
| `hand_count` | Integer | 핸드 수 | 5 |
| `nas_path` | Text | NAS 경로 | //10.10.100.122/... |
| `file_size_bytes` | Integer | 파일 크기 | 12800000000 |

---

### 2.4 hands

하이라이트 핸드

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `id` | Integer | PK | 1 |
| `file_id` | Integer | FK → files | 99 |
| `phh_hand_id` | Text | PHH Hand ID | 24W-R1 |
| `hand_number` | Integer | 핸드 번호 | 1 |
| `start_sec` | Float | 시작 시간 (초) | 25135.0 |
| `end_sec` | Float | 종료 시간 (초) | 25247.0 |
| `winner` | Text | 승자 | NEGREANU |
| `pot_size_bb` | Float | 팟 크기 (BB) | 150.5 |
| `is_all_in` | Boolean | 올인 여부 | TRUE |
| `is_showdown` | Boolean | 쇼다운 여부 | TRUE |
| `players` | JSON | 플레이어 목록 | ["NEGREANU", "COLEMAN"] |
| `cards_shown` | JSON | 카드 정보 | {"raw": "AA vs KK"} |
| `board` | Text | 보드 카드 | Ah Kd 5c 2s 9h |
| `highlight_score` | Float | 하이라이트 점수 | 1.0 |
| `tags` | JSON | 태그 목록 | ["preflop_allin", "cooler"] |
| `display_title` | Text | 표시 제목 | |
| `title_source` | Text | 제목 출처 | archive_team |

---

### 2.5 players

플레이어 마스터

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `name` | Text | PK (대문자) | NEGREANU |
| `display_name` | Text | 표시명 | Negreanu |
| `country` | Text | 국가 | USA |
| `total_hands` | Integer | 총 핸드 수 | 14 |
| `total_wins` | Integer | 승리 수 | 12 |
| `total_all_ins` | Integer | 올인 횟수 | 3 |
| `avg_pot_bb` | Float | 평균 팟 (BB) | 85.5 |
| `first_seen_at` | Datetime | 첫 등장 | 2025-11-29 |
| `last_seen_at` | Datetime | 마지막 등장 | 2025-11-29 |

---

### 2.6 tags

태그 마스터

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `id` | Integer | PK | 1 |
| `name` | Text | 태그명 | high, low, medium |
| `category` | Text | 카테고리 | (빈 값) |
| `created_at` | Datetime | 생성일 | 2025-12-03 |

---

### 2.7 files

파일 메타데이터

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `id` | Integer | PK | 1420 |
| `event_id` | Text | FK → events | mpp-1m-unknown-... |
| `nas_path` | Text | NAS 전체 경로 | //10.10.100.122/... |
| `filename` | Text | 파일명 | WSOP_2024_EP1.mp4 |
| `size_bytes` | Integer | 파일 크기 | 12800000000 |
| `duration_sec` | Float | 재생시간 (초) | 29549.73 |
| `resolution` | Text | 해상도 | 1920x1080 |
| `codec` | Text | 코덱 | h264 |
| `fps` | Float | 프레임레이트 | 59.94 |
| `bitrate_kbps` | Integer | 비트레이트 | 8000 |
| `analysis_status` | Text | 분석 상태 | pending, completed |
| `hands_count` | Integer | 핸드 수 | 5 |
| `view_count` | Integer | 조회수 | 2 |
| `display_title` | Text | 표시 제목 | |
| `display_subtitle` | Text | 표시 부제목 | |

---

### 2.8 wsoptv_player_aliases

플레이어 한글 별칭

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `id` | Integer | PK | 1 |
| `player_id` | Integer | FK → players | 3192 |
| `canonical_name` | Text | 영문 이름 | Phil Hellmuth |
| `alias` | Text | 별칭 (한글) | 필 헬무스 |
| `alias_type` | Text | 별칭 유형 | korean |
| `confidence` | Float | 신뢰도 | 1.0 |
| `is_verified` | Boolean | 검증 여부 | TRUE |

---

## 3. Sync Commands

### Archive Team → DB

```powershell
# 전체 동기화
python -m archive_analyzer.archive_hands_sync --sync

# 특정 워크시트만
python -m archive_analyzer.archive_hands_sync --sync --sheet "WSOP Super Circuit"

# 테스트 (DB 미변경)
python -m archive_analyzer.archive_hands_sync --dry-run

# 데몬 모드 (1시간 간격)
python -m archive_analyzer.archive_hands_sync --daemon
```

### DB ↔ Pokervod Sheet

```powershell
# 초기 동기화 (DB → Sheet)
python -m archive_analyzer.sheets_sync --init

# 양방향 동기화
python -m archive_analyzer.sheets_sync --sync

# Sheet → DB (역방향)
python -m archive_analyzer.sheets_sync --reverse

# 데몬 모드 (5분 간격)
python -m archive_analyzer.sheets_sync --daemon
```

---

## 4. API Rate Limits

Google Sheets API 제한:

| 제한 | 값 |
|------|-----|
| 읽기 요청 | 60회/분/유저 |
| 쓰기 요청 | 60회/분/유저 |
| 프로젝트 전체 | 300회/분 |

**대응 전략**:
- 요청 간 1.2초 딜레이
- Exponential backoff (최대 64초)
- 배치 처리 (500개 단위)

---

## Change History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-08 | Initial documentation |
