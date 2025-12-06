---
name: work
description: Execute work instructions with parallel analysis, issue creation, and strict validation
---

# /work - 작업 지시 실행

작업 지시를 받아 **병렬 분석 → 이슈/문서 → Todo → E2E → TDD 보고**까지 자동 수행합니다.

## 사용법

```
/work <작업 지시 내용>
/work "API 성능 개선"
/work "인증 시스템 리팩토링"
```

## 실행 흐름

```
/work 실행
    │
    ├─ Phase 1: 병렬 분석 ─────────────────────────────────┐
    │      │                                               │
    │      ├─ [Agent 1] 문서 분석 (PRD, CLAUDE.md, docs/)  │
    │      │      └─ 관련 문서 식별 및 요약                │
    │      │                                               │ 병렬
    │      └─ [Agent 2] 이슈 분석 (gh issue list)          │
    │             └─ 관련 이슈 식별 및 상태 확인           │
    │                                               ───────┘
    │
    ├─ Phase 2: 이슈 생성 + 문서 업데이트
    │      │
    │      ├─ 분석 결과 통합
    │      ├─ 새 이슈 생성 (필요 시)
    │      └─ 관련 문서 업데이트
    │
    ├─ Phase 3: Todo 작성
    │      │
    │      └─ TodoWrite로 작업 목록 생성
    │           ├─ 구현 태스크
    │           ├─ 테스트 태스크
    │           └─ 검증 태스크
    │
    ├─ Phase 4: E2E 엄격 검증
    │      │
    │      ├─ Playwright 테스트 실행
    │      ├─ 실패 시 자동 수정 (최대 2회)
    │      └─ 3회 실패 → /issue-failed
    │
    └─ Phase 5: TDD 검증 + 보고
           │
           ├─ 단위 테스트 실행
           ├─ 커버리지 확인
           └─ 최종 보고서 출력
```

## Phase 1: 병렬 분석

### 문서 분석 에이전트

```python
Task(
    subagent_type="Explore",
    prompt="""
    작업 지시: {instruction}

    다음을 분석하세요:
    1. CLAUDE.md - 관련 규칙/워크플로우
    2. tasks/prds/ - 관련 PRD
    3. docs/ - 관련 문서
    4. 영향받는 파일 목록

    JSON 형식으로 반환:
    {
        "related_docs": [...],
        "affected_files": [...],
        "recommendations": [...]
    }
    """,
    description="문서 분석"
)
```

### 이슈 분석 에이전트

```python
Task(
    subagent_type="Explore",
    prompt="""
    작업 지시: {instruction}

    다음을 분석하세요:
    1. gh issue list - 관련 이슈 검색
    2. gh pr list - 관련 PR 검색
    3. 중복 이슈 확인
    4. 의존성 이슈 파악

    JSON 형식으로 반환:
    {
        "related_issues": [...],
        "related_prs": [...],
        "duplicates": [...],
        "dependencies": [...]
    }
    """,
    description="이슈 분석"
)
```

## Phase 2: 이슈 생성 + 문서 업데이트

### 이슈 생성 기준

| 조건 | 동작 |
|------|------|
| 관련 이슈 없음 | 새 이슈 생성 |
| 관련 이슈 있음 (Open) | 기존 이슈에 코멘트 추가 |
| 관련 이슈 있음 (Closed) | 새 이슈 생성 + 참조 링크 |

### 문서 업데이트

```bash
# 자동 업데이트 대상
- tasks/prds/NNNN-prd-*.md  # PRD 생성/업데이트
- docs/*.md                  # 관련 문서 수정
- CHANGELOG.md               # 변경 로그 추가
```

## Phase 3: Todo 작성

### Todo 구조

```python
TodoWrite(todos=[
    {"content": "Phase 1: 문서/이슈 분석 완료", "status": "completed", "activeForm": "분석 중"},
    {"content": "Phase 2: 이슈 생성 및 문서 업데이트", "status": "completed", "activeForm": "업데이트 중"},
    {"content": "구현: <핵심 구현 항목>", "status": "in_progress", "activeForm": "구현 중"},
    {"content": "테스트: 단위 테스트 작성", "status": "pending", "activeForm": "테스트 작성 중"},
    {"content": "테스트: E2E 테스트 작성", "status": "pending", "activeForm": "E2E 작성 중"},
    {"content": "검증: TDD 검증", "status": "pending", "activeForm": "TDD 검증 중"},
    {"content": "보고: 최종 결과 보고", "status": "pending", "activeForm": "보고서 작성 중"}
])
```

## Phase 4: E2E 엄격 검증

### 검증 프로세스

```
npx playwright test
    │
    ├─ 성공 → Phase 5 진행
    │
    └─ 실패 → 자동 수정 시도 (최대 2회)
               │
               ├─ 수정 성공 → 재실행
               │
               └─ 3회 실패 → /issue-failed 호출
                              └─ 수동 개입 요청
```

### 검증 기준

| 항목 | 기준 | 실패 시 |
|------|------|---------|
| E2E 테스트 | 100% 통과 | 자동 수정 |
| 성능 | 응답 시간 <3s | 경고 |
| 접근성 | a11y 오류 0 | 경고 |

## Phase 5: TDD 검증 + 보고

### TDD 검증

```bash
# 단위 테스트
pytest tests/ -v --cov=src --cov-report=term

# 커버리지 기준
- 신규 코드: 80% 이상
- 전체: 기존 대비 감소 불가
```

### 최종 보고서

```markdown
# 작업 완료 보고서

## 요약
- **작업 지시**: {instruction}
- **소요 시간**: XX분
- **생성 이슈**: #NNN
- **생성 PR**: #NNN

## Phase 1: 분석 결과
- 관련 문서: N개
- 관련 이슈: N개
- 영향 파일: N개

## Phase 2: 변경 사항
- 생성된 이슈: #NNN - {title}
- 업데이트된 문서: docs/XXX.md

## Phase 3: 구현 내역
| 파일 | 변경 | 설명 |
|------|------|------|
| src/xxx.py | +50/-10 | 기능 구현 |

## Phase 4: E2E 검증
- 테스트: NN개 통과
- 실패: 0개
- 성능: OK

## Phase 5: TDD 검증
- 단위 테스트: NN개 통과
- 커버리지: XX% (기준 80%)

## 다음 단계
1. PR 리뷰 요청
2. 배포 준비
```

## 예시

```bash
$ /work API 응답 캐싱 추가

🔍 Phase 1: 병렬 분석 중...
   [Agent 1] 문서 분석...
      - CLAUDE.md: 캐싱 관련 규칙 없음
      - docs/API.md: 캐싱 미언급
      - 영향 파일: src/api/*.py (5개)

   [Agent 2] 이슈 분석...
      - 관련 이슈: #45 (Closed), #67 (Open)
      - 중복: 없음

📝 Phase 2: 이슈 생성 + 문서 업데이트
   - 이슈 #67에 코멘트 추가
   - docs/API.md 캐싱 섹션 추가

✅ Phase 3: Todo 작성 완료 (7개 항목)

🧪 Phase 4: E2E 검증
   - playwright test: 15/15 통과

📊 Phase 5: TDD 검증
   - pytest: 42/42 통과
   - 커버리지: 85% (기준 80% 충족)

📋 최종 보고서 출력...
```

## 연동 커맨드

| 커맨드 | 연동 시점 |
|--------|----------|
| `/pre-work` | Phase 1 전 (선택) |
| `/tdd` | Phase 5 |
| `/issue-failed` | E2E 3회 실패 시 |
| `/commit` | 완료 후 |
| `/create-pr` | 완료 후 |

## 연동 에이전트

| Phase | 에이전트 | 역할 |
|-------|----------|------|
| 1 | `Explore` x2 | 병렬 분석 |
| 2 | `general-purpose` | 이슈/문서 처리 |
| 4 | `playwright-engineer` | E2E 테스트 |
| 5 | `test-automator` | TDD 검증 |

## 옵션

| 옵션 | 설명 | 예시 |
|------|------|------|
| `--skip-analysis` | Phase 1 스킵 | `/work --skip-analysis "빠른 수정"` |
| `--no-issue` | 이슈 생성 안함 | `/work --no-issue "내부 리팩토링"` |
| `--strict` | 엄격 모드 (E2E 1회 실패 시 중단) | `/work --strict "프로덕션 배포"` |

---

**작업 지시를 입력해 주세요.**
