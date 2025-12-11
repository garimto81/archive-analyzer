# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Version**: 8.0.0 | **Context**: Windows, PowerShell, Root: `D:\AI\claude01`

**GitHub**: `garimto81/claude-code-config`

---

## 기본 규칙

| 규칙 | 내용 |
|------|------|
| **언어** | 한글 출력. 기술 용어(code, GitHub)는 영어 |
| **경로** | 절대 경로만. `D:\AI\claude01\...` |
| **충돌** | 지침 충돌 시 → **사용자에게 질문** (임의 판단 금지) |

---

## 프로젝트 구조

Claude Code 전역 워크플로우 설정 저장소:

```
D:\AI\claude01\
├── .claude/
│   ├── commands/        # 커스텀 슬래시 커맨드 (20개)
│   └── skills/          # 커스텀 스킬 (13개)
│       ├── tdd-workflow/
│       ├── debugging-workflow/
│       ├── code-quality-checker/
│       ├── final-check-automation/
│       ├── phase-validation/
│       ├── pre-work-research/
│       ├── issue-resolution/
│       ├── parallel-agent-orchestration/
│       ├── journey-sharing/
│       ├── webapp-testing/
│       ├── pr-review-agent/
│       ├── command-analytics/
│       └── skill-creator/
├── docs/                # 워크플로우 문서
├── src/agents/          # AI 워크플로우 에이전트 (Python)
│   ├── config.py              # 모델 티어링 (Sonnet/Haiku)
│   ├── parallel_workflow.py   # Fan-Out/Fan-In 병렬 실행
│   ├── dev_workflow.py        # 4-에이전트 병렬 개발
│   ├── test_workflow.py       # 4-에이전트 병렬 테스트
│   ├── phase_validator.py     # Phase 0-6 검증
│   └── utils.py               # 유틸리티
└── tasks/prds/          # PRD 문서
```

---

## 핵심 규칙 (Hook 강제)

| 규칙 | 위반 시 | 해결 |
|------|---------|------|
| main 브랜치 수정 금지 | **차단** | `git checkout -b feat/issue-N-desc` |
| 테스트 먼저 (TDD) | 경고 | Red → Green → Refactor |
| 상대 경로 금지 | 경고 | 절대 경로 사용 |

---

## 작업 방법

```
사용자 요청 → /work "요청 내용" → 자동 완료
```

| 요청 유형 | 처리 |
|-----------|------|
| 기능/리팩토링 | `/work` → 이슈 → 브랜치 → TDD → PR |
| 버그 수정 | `/issue fix #N` |
| 문서 수정 | 직접 수정 (브랜치 불필요) |
| 질문 | 직접 응답 |

---

## 커맨드 (20개)

### 핵심 워크플로우 (4개)

| 커맨드 | 용도 | 옵션 |
|--------|------|------|
| `/work "내용"` | 전체 워크플로우 | `--auto`, `--skip-analysis`, `--no-issue`, `--strict` |
| `/work-auto "내용"` | 완전 자동화 | 최종 보고서만 확인 |
| `/parallel <mode>` | 병렬 실행 | `dev`, `test`, `review`, `research`, `check` |
| `/issue <action>` | 이슈 관리 | `list`, `create`, `edit`, `fix`, `failed` |

### 사전 작업 (2개)

| 커맨드 | 용도 |
|--------|------|
| `/pre-work` | 솔루션 검색 + 중복 확인 + Make vs Buy |
| `/research` | 코드베이스 분석 (RPI Phase 1) |

### 개발 (3개)

| 커맨드 | 용도 |
|--------|------|
| `/plan` | 구현 계획 수립 (RPI Phase 2) |
| `/tdd` | Red-Green-Refactor 가이드 |
| `/create <type>` | PRD/PR/문서 생성 (`prd`, `pr`, `docs`) |

### 검증 (5개)

| 커맨드 | 용도 |
|--------|------|
| `/check` | 린트 + 타입 + 보안 |
| `/optimize` | 성능 분석 |
| `/api-test` | API 엔드포인트 테스트 |
| `/final-check` | E2E 엄격 검증 |
| `/analyze <type>` | 코드/로그 분석 (`code`, `logs`) |

### 문서 & 커밋 (3개)

| 커맨드 | 용도 |
|--------|------|
| `/commit` | Conventional Commits |
| `/changelog` | CHANGELOG 자동 생성 |
| `/pr <action>` | PR 리뷰/머지 (`review`, `improve`, `auto`) |

### 세션 관리 (3개)

| 커맨드 | 용도 |
|--------|------|
| `/todo <action>` | 작업 관리 (`list`, `add`, `done`, `clear`) |
| `/journey <action>` | 세션 여정 (`save`, `load`, `link`) |
| `/compact` | 컨텍스트 압축 |

전체: `.claude/commands/`

---

## 커맨드 선택 가이드

| 작업 유형 | 추천 커맨드 | 순서 |
|----------|------------|------|
| 신규 기능 추가 | `/work` | pre-work → 구현 → E2E → PR |
| 버그 수정 | `/issue fix #N` | 분석 → 수정 → 테스트 |
| 성능 최적화 | `/optimize` → `/tdd` | 병목 분석 → TDD 구현 |
| 코드 리팩토링 | `/parallel review` → `/check` | 리뷰 → 품질 검사 |
| PR 리뷰 | `/pr review` → `/pr auto` | 리뷰 → 자동 머지 |
| E2E 검증 | `/final-check` | 테스트 → 자동 수정 |

---

## 스킬 (13개)

자동 트리거되는 스킬 목록:

| 스킬 | Phase | 트리거 조건 |
|------|-------|-----------|
| `tdd-workflow` | 1, 2 | "TDD", "테스트 먼저" |
| `debugging-workflow` | 1, 2, 5 | "debug", "3회 실패" |
| `code-quality-checker` | 2, 2.5 | "린트", "품질 검사" |
| `final-check-automation` | 5 | "E2E", "최종 검증" |
| `phase-validation` | 0-6 | "Phase 검증" |
| `pre-work-research` | 0 | "신규 기능", "오픈소스" |
| `issue-resolution` | 1, 2 | "이슈 해결" |
| `parallel-agent-orchestration` | 1, 2 | "병렬 개발" |
| `journey-sharing` | 4 | "여정 저장" |

수동 호출 스킬: `webapp-testing`, `pr-review-agent`, `command-analytics`, `skill-creator`

---

## 안전 규칙

### Crash Prevention (필수)

```powershell
# 금지 (120초 초과 → 크래시)
pytest tests/ -v --cov                # 대규모 테스트
npm install && npm run build          # 체인 명령

# 권장
pytest tests/test_a.py -v             # 개별 실행
# 또는 run_in_background: true
```

---

## 문제 해결

```
문제 → WHY(원인) → WHERE(영향 범위) → HOW(해결) → 수정
```

**즉시 수정 금지.** 원인 파악 → 유사 패턴 검색 → 구조적 해결.

---

## 버전 관리 (필수)

### PR/Issue 생성·업데이트 시 필수 항목

| 항목 | 형식 | 예시 |
|------|------|------|
| **버전** | Semantic Versioning | `v1.2.3` |
| **커밋 해시** | 7자리 short hash | `abc1234` |
| **이슈/PR 태그** | `#번호` 또는 `Closes #번호` | `#181`, `Closes #179` |

### 버전 업데이트 규칙

```
MAJOR.MINOR.PATCH (Semantic Versioning)
├── MAJOR: 호환성 깨지는 변경
├── MINOR: 새 기능 추가 (하위 호환)
└── PATCH: 버그 수정
```

### 워크플로우

```
1. Issue 생성 → 이슈 번호 발급 (#N)
2. 브랜치 생성 → feat/issue-N-desc
3. 작업 완료 → 커밋 (해시 생성)
4. PR 생성 → 이슈 태그 연결 (Closes #N)
5. 머지 전 → /changelog 실행, 버전 범프
6. 머지 후 → git tag vX.Y.Z
```

### 커밋 메시지 형식

```
<type>(<scope>): <subject> (#issue)

- 변경 내용 설명

Refs: #issue1, #issue2
Closes #issue (PR에서 이슈 자동 종료 시)

Generated with [Claude Code](https://claude.com/claude-code)
```

### 코멘트 태깅 규칙

| 상황 | 태그 형식 |
|------|-----------|
| 이슈 참조 | `Refs: #123` |
| 이슈 종료 | `Closes #123`, `Fixes #123` |
| PR 참조 | `PR #456` |
| 커밋 참조 | `abc1234` (7자리 해시) |

---

## 참조

| 문서 | 용도 |
|------|------|
| `docs/WORKFLOW_REFERENCE.md` | 상세 워크플로우 |
| `docs/AGENTS_REFERENCE.md` | 에이전트 목록 |
| `docs/COMMAND_SELECTOR.md` | 커맨드 선택 가이드 |
| `docs/PLANNED_AGENTS.md` | 계획 에이전트 목록 |
| `.claude/commands/` | 커맨드 상세 |
| `.claude/skills/` | 스킬 상세 |
