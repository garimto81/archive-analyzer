# 로컬 데이터 추가 시스템 설계

> **Issue**: #13 - 로컬 환경 데이터 추가 로직 설계
> **Version**: 1.0.0
> **Date**: 2025-12-04
> **Status**: 설계 완료

---

## 1. 개요

클라우드 의존성 없이 **완전 로컬 환경**에서 데이터를 추가하고 관리하는 시스템.

### 1.1 설계 원칙

| 원칙 | 설명 |
|------|------|
| **로컬 우선** | 모든 데이터는 로컬 SQLite에 저장 |
| **비용 제로** | 외부 API/클라우드 서비스 미사용 |
| **단순함** | CSV 기반 임포트/익스포트 |
| **독립성** | 네트워크 없이 동작 가능 |

---

## 2. 데이터 흐름

```
┌─────────────────────────────────────────────────────────────┐
│                    로컬 데이터 시스템                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────────┐    ┌───────────────┐                    │
│  │   CSV 파일     │    │   Admin UI    │                    │
│  │               │    │  (localhost)  │                    │
│  │ - hands.csv   │    │               │                    │
│  │ - contents.csv│    │ - CRUD 폼     │                    │
│  │ - players.csv │    │ - 벌크 업로드  │                    │
│  └───────┬───────┘    └───────┬───────┘                    │
│          │                    │                             │
│          │   import_csv.py    │  FastAPI                    │
│          └────────┬───────────┘                             │
│                   ▼                                         │
│          ┌───────────────────┐                              │
│          │   pokervod.db     │                              │
│          │   (SQLite WAL)    │                              │
│          │                   │                              │
│          │ - hands           │                              │
│          │ - contents        │                              │
│          │ - files           │                              │
│          │ - players         │                              │
│          │ - catalogs        │                              │
│          └───────────────────┘                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. CSV 템플릿

### 3.1 hands.csv

핸드 태깅 데이터.

| 컬럼 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `hand_id` | INTEGER | ✅ | 핸드 고유 ID |
| `file_id` | INTEGER | ✅ | 연결된 파일 ID |
| `start_sec` | INTEGER | ✅ | 시작 시간(초) |
| `end_sec` | INTEGER | ✅ | 종료 시간(초) |
| `highlight_score` | INTEGER | | 하이라이트 점수 (1-3) |
| `players` | TEXT | | JSON 배열 `["Player1", "Player2"]` |
| `tags` | TEXT | | 쉼표 구분 `hero_call,bluff` |
| `notes` | TEXT | | 메모 |

```csv
hand_id,file_id,start_sec,end_sec,highlight_score,players,tags,notes
1001,101,120,180,3,"[""Phil Ivey"",""Tom Dwan""]","hero_call,bluff","Amazing bluff"
1002,101,240,300,2,"[""Daniel Negreanu""]","value_bet",""
```

### 3.2 contents.csv

콘텐츠/에피소드 메타데이터.

| 컬럼 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `content_id` | INTEGER | ✅ | 콘텐츠 고유 ID |
| `title` | TEXT | ✅ | 제목 |
| `catalog_id` | INTEGER | ✅ | 카탈로그 ID |
| `program_type` | TEXT | | episode/special/highlight |
| `episode_num` | INTEGER | | 에피소드 번호 |
| `air_date` | TEXT | | 방영일 (YYYY-MM-DD) |
| `duration_sec` | INTEGER | | 재생시간(초) |
| `description` | TEXT | | 설명 |

```csv
content_id,title,catalog_id,program_type,episode_num,air_date,duration_sec,description
1,"WSOP 2024 Main Event Day 1",1,episode,1,2024-07-01,7200,"Day 1 coverage"
2,"WSOP 2024 Main Event Day 2",1,episode,2,2024-07-02,7200,"Day 2 coverage"
```

### 3.3 players.csv

플레이어 프로필.

| 컬럼 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `player_id` | INTEGER | ✅ | 플레이어 고유 ID |
| `name_display` | TEXT | ✅ | 표시 이름 |
| `name_kr` | TEXT | | 한글 이름 |
| `nationality` | TEXT | | 국적 |
| `career_earnings` | INTEGER | | 통산 상금 |
| `wsop_bracelets` | INTEGER | | WSOP 브레이슬릿 수 |

```csv
player_id,name_display,name_kr,nationality,career_earnings,wsop_bracelets
1,"Phil Ivey","필 아이비","USA",43000000,10
2,"Daniel Negreanu","다니엘 네그라누","Canada",50000000,6
```

### 3.4 files.csv

미디어 파일 메타데이터.

| 컬럼 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `file_id` | INTEGER | ✅ | 파일 고유 ID |
| `nas_path` | TEXT | ✅ | NAS 경로 |
| `filename` | TEXT | ✅ | 파일명 |
| `content_id` | INTEGER | | 연결된 콘텐츠 ID |
| `codec` | TEXT | | 비디오 코덱 |
| `resolution` | TEXT | | 해상도 (예: 1920x1080) |
| `duration_sec` | INTEGER | | 재생시간(초) |
| `file_size` | INTEGER | | 파일 크기(bytes) |

```csv
file_id,nas_path,filename,content_id,codec,resolution,duration_sec,file_size
101,"/ARCHIVE/WSOP/2024/main_event_d1.mp4","main_event_d1.mp4",1,"h264","1920x1080",7200,5368709120
```

---

## 4. 임포트 스크립트

### 4.1 사용법

```bash
# 단일 파일 임포트
python scripts/import_csv.py --file hands.csv --table hands

# 전체 임포트 (data/ 폴더 내 모든 CSV)
python scripts/import_csv.py --all

# Dry-run (변경 없이 검증만)
python scripts/import_csv.py --file hands.csv --dry-run

# 에러 리포트 생성
python scripts/import_csv.py --file hands.csv --report errors.txt
```

### 4.2 검증 규칙

| 규칙 | 설명 |
|------|------|
| **필수 필드** | 비어있으면 에러 |
| **중복 ID** | 기존 ID와 충돌 시 경고/스킵 |
| **참조 무결성** | file_id, catalog_id 등 외래키 검증 |
| **타입 검증** | 숫자 필드에 문자열 불허 |
| **날짜 형식** | YYYY-MM-DD 형식 검증 |

### 4.3 에러 처리

```
=== Import Report ===
File: hands.csv
Total rows: 100
Imported: 95
Skipped: 3
Errors: 2

Errors:
  Row 45: Invalid file_id '999' - not found in files table
  Row 67: Missing required field 'start_sec'

Skipped (duplicates):
  Row 12: hand_id 1001 already exists
  Row 23: hand_id 1002 already exists
  Row 56: hand_id 1003 already exists
```

---

## 5. Admin UI 확장

### 5.1 새로운 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/admin/hands` | GET | 핸드 목록 |
| `/admin/hands/new` | POST | 핸드 추가 |
| `/admin/hands/{id}` | PUT | 핸드 수정 |
| `/admin/hands/{id}` | DELETE | 핸드 삭제 |
| `/admin/hands/import` | POST | CSV 벌크 임포트 |
| `/admin/hands/export` | GET | CSV 익스포트 |

### 5.2 UI 기능

- **CRUD 폼**: 단일 레코드 추가/수정/삭제
- **벌크 업로드**: CSV 파일 드래그앤드롭
- **검색/필터**: 다양한 조건으로 데이터 검색
- **익스포트**: 현재 필터 결과를 CSV로 다운로드

---

## 6. 마이그레이션

### 6.1 기존 sheets_sync 제거

```bash
# 더 이상 사용하지 않음
# python -m archive_analyzer.sheets_sync --daemon  ← 제거

# 대신 로컬 임포트 사용
python scripts/import_csv.py --all
```

### 6.2 기존 데이터 익스포트

기존 Google Sheets 데이터가 있다면:

```bash
# 1. 기존 데이터 CSV 익스포트
python scripts/export_from_sheets.py --output data/

# 2. 로컬 DB로 임포트
python scripts/import_csv.py --all
```

---

## 7. 디렉토리 구조

```
archive-analyzer/
├── data/
│   ├── templates/           # CSV 템플릿 (빈 파일)
│   │   ├── hands_template.csv
│   │   ├── contents_template.csv
│   │   ├── players_template.csv
│   │   └── files_template.csv
│   └── imports/             # 임포트할 CSV 파일
│       ├── hands.csv
│       └── ...
├── scripts/
│   ├── import_csv.py        # CSV 임포트 스크립트
│   └── export_csv.py        # CSV 익스포트 스크립트
└── docs/
    └── LOCAL_DATA_DESIGN.md # 이 문서
```

---

## 8. 비용 비교

| 항목 | 이전 (클라우드) | 이후 (로컬) | 절감 |
|------|----------------|-------------|------|
| Google Sheets API | 호출당 비용 | $0 | 100% |
| Firestore | R/W 비용 | $0 | 100% |
| 네트워크 | 데이터 전송 | $0 | 100% |
| **총 운영비** | 변동 | **$0** | **100%** |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2025-12-04 | 1.0.0 | 초기 설계 문서 작성 |
