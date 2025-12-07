---
name: journey
description: 세션 여정 기록 및 PR 연동
---

# /journey - 세션 여정 관리

현재 세션의 작업 여정을 기록하고 PR에 첨부합니다.

## Usage

```
/journey [subcommand]

Subcommands:
  save      현재 세션 여정 저장
  show      저장된 여정 목록
  export    PR용 마크다운 생성
  clear     세션 기록 초기화
```

---

## 여정 데이터 구조

```json
{
  "session_id": "2025-12-07T19:00:00",
  "issue": "#30",
  "branch": "feature/issue-30-journey-sharing",
  "milestones": [
    {
      "time": "19:00",
      "action": "Plan 시작",
      "context_usage": "12%"
    },
    {
      "time": "19:30",
      "action": "구현 완료",
      "files_changed": ["file1.py", "file2.md"]
    }
  ],
  "decisions": [
    {
      "question": "A vs B 중 어떤 접근법?",
      "choice": "A",
      "reason": "성능 우선"
    }
  ],
  "blockers": [],
  "final_status": "completed"
}
```

---

## /journey save

현재 세션 상태를 `.claude/sessions/`에 저장합니다.

```bash
/journey save
# Output: 세션 저장됨 → .claude/sessions/2025-12-07-session.json
```

### 자동 수집 항목

| 항목 | 설명 |
|------|------|
| `milestones` | 주요 작업 단계 |
| `decisions` | 의사결정 기록 |
| `files_changed` | 변경된 파일 목록 |
| `context_usage` | 컨텍스트 사용량 |
| `blockers` | 발견된 장애물 |

---

## /journey show

저장된 세션 목록을 표시합니다.

```bash
/journey show
# Output:
# Sessions:
# - 2025-12-07-session.json (issue #30, completed)
# - 2025-12-06-session.json (issue #28, in_progress)
```

---

## /journey export

PR용 마크다운을 생성합니다.

```bash
/journey export
# Output: PR Journey 섹션 마크다운 생성
```

### 생성 형식

```markdown
## 여정 (Journey)

### 작업 흐름
1. 19:00 - Plan 시작 (context: 12%)
2. 19:15 - 코드베이스 분석
3. 19:30 - 구현 완료

### 주요 결정
- **A vs B**: A 선택 (이유: 성능 우선)

### 변경 파일
- `file1.py` - 핵심 로직
- `file2.md` - 문서

### 참고사항
- 장애물 없음
```

---

## /journey clear

현재 세션 기록을 초기화합니다.

```bash
/journey clear
# Output: 세션 기록 초기화됨
```

---

## PR 템플릿 연동

`/create pr` 실행 시 자동으로 여정 섹션이 포함됩니다.

```
1. /journey save        # 세션 저장
2. /create pr           # PR 생성 (여정 자동 포함)
```

---

## 저장 위치

```
.claude/
└── sessions/
    ├── 2025-12-07-session.json
    ├── 2025-12-06-session.json
    └── ...
```

---

## Related

- `/create pr` - PR 생성 시 여정 첨부
- `/todo` - 작업 목록 관리
- `/commit` - 커밋 생성
