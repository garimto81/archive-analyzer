# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Version**: 4.4.0 | **Updated**: 2025-12-07 | **Context**: Windows 10/11, PowerShell, Root: `D:\AI\claude01`

## 1. Critical Rules

0. **Conflict Resolution**: 지침과 컨텍스트 충돌 시 → **사용자에게 질문** (임의 판단 금지)
1. **Language**: 한글 출력. 기술 용어(code, GitHub)는 영어.
2. **Path**: 절대 경로만 사용. `D:\AI\claude01\...`
3. **Validation**: Phase 검증 필수. 실패 시 STOP.
4. **TDD**: Red → Green → Refactor. 테스트 없이 구현 완료 불가.
5. **Git**: 코드 수정은 브랜치 → PR 필수. main 직접 커밋 금지.

---

## 2. Build & Test

```powershell
# 테스트
pytest tests/ -v                              # 전체
pytest tests/test_file.py -v                  # 단일 파일
pytest tests/test_file.py::test_func -v       # 단일 함수
pytest tests/ -v -m unit                      # 마커별
pytest tests/ -v --cov=src --cov-report=term  # 커버리지

# Lint & Format
ruff check src/                               # 린트
black --check src/                            # 포맷 검사
mypy src/                                     # 타입 검사

# E2E (Browser)
npx playwright test                           # 전체 E2E
npx playwright test --ui                      # UI 모드 (디버깅)
npx playwright test tests/e2e/flow.spec.ts    # 단일 파일

# 에이전트 실행
python src/agents/parallel_workflow.py "태스크"
python src/agents/dev_workflow.py "기능 구현"

# Phase 상태
.\scripts\phase-status.ps1
.\scripts\validate-phase-5.ps1                # E2E + Security

# E2E (실패 시: 1-2회 자동 수정 → 3회 실패 시 /issue-failed)
```

### archive-analyzer (서브프로젝트)

```powershell
cd D:\AI\claude01\archive-analyzer
pip install -e ".[dev,media,search]"
pytest tests/ -v
ruff check src/ && black --check src/ && mypy src/archive_analyzer/
uvicorn src.archive_analyzer.api:app --reload --port 8000
```

> 상세: `D:\AI\claude01\archive-analyzer\CLAUDE.md`

---

## 3. Workflow

| 요청 유형 | 자동 실행 |
|-----------|-----------|
| 신규 기능 / 리팩토링 | PRE_WORK → IMPL → FINAL_CHECK |
| 버그 수정 | PRE_WORK(light) → IMPL → FINAL_CHECK |
| 문서 수정 | 이슈 → 직접 커밋 |
| 단순 질문 | 직접 응답 |

### PRE_WORK
1. 오픈소스 검색 (MIT/Apache/BSD, Stars>500)
2. 중복 확인 (`gh issue/pr list`)
3. Make vs Buy 분석 → 사용자 승인

### IMPL
1. GitHub 이슈/브랜치 생성: `<type>/issue-<num>-<desc>`
2. TDD 구현
3. 커밋: `fix(scope): Resolve #123 🐛` / `feat(scope): Add feature ✨`

### FINAL_CHECK
E2E 테스트 → Phase 3~5 자동 진행 → Phase 6(배포)은 사용자 확인

---

## 4. Problem Solving Philosophy

### 핵심 원칙: 즉시 수정 금지 (No Quick Fix)

```
문제 발견 → WHY(근본 원인) → WHERE(전체 영향) → HOW(구조적 해결) → 수정
```

| 단계 | 질문 | 확인 사항 |
|------|------|----------|
| **WHY** | 왜 발생? | 직접 원인 + 근본 원인 |
| **WHERE** | 어디에 영향? | 유사 패턴 전체 검색 (`grep -r`) |
| **HOW** | 어떻게 수정? | 국소 vs 구조적, 재발 방지 포함 |

### 사고 프레임워크

| 질문 | 잘못된 접근 | 올바른 접근 |
|------|------------|------------|
| 버그 발견 시 | "이 버그를 고치면 끝" | "왜 이런 버그가 가능했는가?" |
| 테스트 실패 시 | "테스트만 통과시키자" | "시스템의 어떤 결함인가?" |
| 에러 로그 시 | "에러 메시지만 해결" | "같은 결함이 다른 곳에도?" |

### 수정 전 체크리스트

- [ ] 근본 원인 이해 / 유사 패턴 검색 / 영향 범위 파악 / 재발 방지책 포함

**금지**: 증상만 수정 ❌ | 단일 파일만 ❌ | "일단 되게" ❌

---

## 5. Phase Pipeline

| Phase | 핵심 | Validator |
|-------|------|-----------|
| 0 | PRD 생성 | `validate-phase-0.ps1` |
| 0.5 | Task 분해 | `validate-phase-0.5.ps1` |
| 1 | 구현 + 테스트 | `validate-phase-1.ps1` |
| 2 | 테스트 통과 | `validate-phase-2.ps1` |
| 2.5 | 코드 리뷰 | `/parallel-review` |
| 3 | 버전 결정 | Conventional Commits |
| 4 | PR 생성 | `validate-phase-4.ps1` |
| 5 | E2E + Security | `validate-phase-5.ps1` |
| 6 | 배포 | 사용자 확인 필수 |

**자동 진행 중지**: MAJOR 버전, Critical 보안 취약점, 배포, 3회 실패

### 실패 시 디버깅

```
실패 → 디버그 로그 추가 → 로그 분석 → 예측 검증
         ↓
       3회 실패 → /issue-failed → 수동 개입
```

**원칙**: 로그 없이 수정 금지 | 문제 파악 > 해결 | 예측 검증 필수

> 상세: `docs/DEBUGGING_STRATEGY.md`

---

## 6. Commands (15개)

### 핵심 워크플로우

| 커맨드 | 용도 |
|--------|------|
| `/work` | 작업 지시 실행 (분석→이슈→E2E→TDD) |
| `/autopilot` | 자율 운영 - 이슈 자동 처리 |
| `/pre-work` | PRE_WORK 단계 실행 (OSS 검색) |
| `/final-check` | E2E + Security 최종 검증 |

### 통합 커맨드 (서브커맨드 지원)

| 커맨드 | 서브커맨드 | 용도 |
|--------|-----------|------|
| `/issue` | `list\|create\|fix\|failed` | GitHub 이슈 관리 |
| `/parallel` | `dev\|test\|review\|research` | 병렬 멀티에이전트 |
| `/analyze` | `code\|logs` | 코드/로그 분석 |
| `/create` | `prd\|pr\|docs` | PRD/PR/문서 생성 |

### 단일 커맨드

| 커맨드 | 용도 |
|--------|------|
| `/commit` | Conventional Commit 생성 |
| `/tdd` | TDD 가이드 (Red-Green-Refactor) |
| `/check` | 코드 품질 검사 |
| `/changelog` | CHANGELOG 업데이트 |
| `/optimize` | 성능 분석 및 최적화 |
| `/todo` | 작업 목록 관리 |
| `/api-test` | API 엔드포인트 테스트 |

### 사용 예시

```bash
# 이슈 관리
/issue list                    # 이슈 목록
/issue fix 123                 # 이슈 해결

# 병렬 실행
/parallel dev "인증 기능"       # 병렬 개발
/parallel test                 # 병렬 테스트

# 분석
/analyze code --comprehensive  # 종합 분석
/analyze logs --errors         # 에러 로그

# 생성
/create prd --template=minimal # PRD 생성
/create pr                     # PR 생성
```

> 커맨드 사용 통계: `.claude/logs/command-usage.json`

---

## 7. Skills

자동 트리거 워크플로우. `.claude/skills/`에 정의 (10개).

| Skill | 트리거 | Phase |
|-------|--------|-------|
| `debugging-workflow` | "로그 분석", "debug", "실패" | 문제 시 |
| `pre-work-research` | "신규 기능", "오픈소스" | PRE_WORK |
| `final-check-automation` | "E2E", "Phase 5" | FINAL_CHECK |
| `tdd-workflow` | "TDD", "Red-Green" | 1, 2 |
| `code-quality-checker` | "린트", "품질 검사" | 2, 2.5 |
| `phase-validation` | "Phase 검증", "validate" | 전체 |
| `parallel-agent-orchestration` | "병렬 개발", "multi-agent" | 1, 2 |
| `issue-resolution` | "이슈 해결", "fix issue" | 1, 2 |
| `webapp-testing` | "브라우저 테스트", "Playwright" | 2, 5 |
| `skill-creator` | "skill 생성", "새 워크플로우" | - |

**사용법**: 트리거 키워드 언급 시 자동 로드. 상세: `.claude/skills/<skill-name>/SKILL.md`

---

## 8. Agents

### 내장 Subagent

| 에이전트 | 용도 |
|----------|------|
| `Explore` | 코드베이스 빠른 탐색 |
| `Plan` | 구현 계획 설계 |
| `debugger` | 버그 분석/수정 |
| `general-purpose` | 복잡한 다단계 작업 |

### 활성 로컬 에이전트 (7개)

| 에이전트 | Phase |
|----------|-------|
| `debugger` | 문제 시 |
| `backend-architect` | 1 |
| `code-reviewer` | 2.5 |
| `test-automator` | 2 |
| `security-auditor` | 5 |
| `playwright-engineer` | 2, 5 |
| `context7-engineer` | 0, 1 |

### Model Tiering

| Role | Tier | Model ID |
|------|------|----------|
| supervisor / lead / coder / reviewer | sonnet | `claude-sonnet-4-20250514` |
| validator / tester | haiku | `claude-haiku-3-20240307` |

> 설정: `src/agents/config.py` - `AGENT_MODEL_TIERS`

### 병렬 호출

```python
# 단일 메시지에 여러 Task = 병렬 실행
Task(subagent_type="frontend-developer", prompt="UI 구현", description="프론트")
Task(subagent_type="backend-architect", prompt="API 구현", description="백엔드")

# 의존성 있는 경우 순차 실행
result = Task(subagent_type="database-architect", prompt="스키마 설계")
Task(subagent_type="backend-architect", prompt=f"API 구현, 스키마: {result}")
```

> 전체 에이전트 목록 (28개): `docs/AGENTS_REFERENCE.md`

---

## 9. Architecture

```
D:\AI\claude01\
├── .claude/
│   ├── commands/      # 슬래시 커맨드 (29개)
│   ├── plugins/       # 로컬 에이전트 정의 (50개)
│   ├── skills/        # 자동 트리거 워크플로우 (10개)
│   └── hooks/         # 프롬프트 검증
├── src/agents/        # LangGraph 멀티에이전트
├── scripts/           # Phase Validators (PowerShell)
├── tasks/prds/        # PRD 문서
├── tests/             # pytest 테스트
└── archive-analyzer/  # 서브프로젝트 (별도 CLAUDE.md)
```

### LangGraph Multi-Agent (Fan-Out/Fan-In)

```
┌─────────────────────────────────────────────────────────┐
│                    Supervisor (sonnet)                   │
│              태스크 분석 및 서브태스크 분배              │
└─────────────────────┬───────────────────────────────────┘
                      │ Fan-Out
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │ Agent 0 │   │ Agent 1 │   │ Agent 2 │  (병렬 실행)
   │ (coder) │   │(tester) │   │ (docs)  │
   └────┬────┘   └────┬────┘   └────┬────┘
        │             │             │
        └─────────────┼─────────────┘
                      │ Fan-In
                      ▼
┌─────────────────────────────────────────────────────────┐
│                   Aggregator (sonnet)                    │
│                  결과 통합 및 검증                       │
└─────────────────────────────────────────────────────────┘
```

**Phase별 에이전트 매핑** (`src/agents/config.py` - `PHASE_AGENTS`):

| Phase | 에이전트 |
|-------|----------|
| 0 | requirements_agent, stakeholder_agent |
| 0.5 | task_decomposer, dependency_analyzer |
| 1 | code_agent, test_agent, docs_agent |
| 2 | unit_test_runner, integration_test_runner, security_scanner |
| 2.5 | code_reviewer, design_reviewer, security_auditor |

---

## 10. MCP Tools

`.mcp.json`에 설정. `mcp__<server>__<tool>` 형태로 호출.

| MCP | 용도 | 연동 에이전트 |
|-----|------|--------------|
| **exa** | 웹 검색 (exa.ai) | `exa-search-specialist` |
| **mem0** | 대화 메모리 | `context-manager` |
| **ref** | 문서 검색 (ref.tools) | `context7-engineer` |
| **docfork** | 문서 포크 | - |

---

## 11. Environment

| 변수 | 용도 |
|------|------|
| `ANTHROPIC_API_KEY` | Claude API |
| `GITHUB_TOKEN` | GitHub CLI |
| `SMB_SERVER` / `SMB_USERNAME` / `SMB_PASSWORD` | NAS 접속 |
| `EXA_API_KEY` / `MEM0_API_KEY` / `REF_API_KEY` | MCP 서버 |

> 설정: `.mcp.json.example` → `.mcp.json` 복사 후 환경변수 설정

---

## 12. Do Not

- ❌ Phase validator 없이 다음 Phase 진행
- ❌ 상대 경로 사용 (`./`, `../`)
- ❌ PR 없이 main 직접 커밋
- ❌ 테스트 없이 구현 완료
- ❌ `pokervod.db` 스키마 무단 변경 (`qwen_hand_analysis` 소유)
