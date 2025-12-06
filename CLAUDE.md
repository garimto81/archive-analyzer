# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Version**: 4.0.0 | **Updated**: 2025-12-06 | **Context**: Windows 10/11, PowerShell, Root: `D:\AI\claude01`

## 1. Critical Rules

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

## 4. Phase Pipeline

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

## 5. Commands

### 핵심 커맨드

| 커맨드 | 용도 |
|--------|------|
| `/autopilot` | 자율 운영 - 이슈 자동 처리 |
| `/fix-issue` | GitHub 이슈 분석 및 수정 |
| `/commit` | Conventional Commit 생성 |
| `/create-pr` | PR 생성 |
| `/tdd` | TDD 가이드 |
| `/check` | 코드 품질 검사 |
| `/issue-failed` | 실패 분석 + 새 솔루션 제안 |

### 병렬 커맨드

| 커맨드 | 호출 Agent |
|--------|------------|
| `/parallel-dev` | architect + coder + tester + docs |
| `/parallel-test` | unit + integration + e2e + security |
| `/parallel-review` | code-reviewer + security-auditor + architect-reviewer |

> 전체 목록 (28개): `.claude/commands/`

---

## 6. Skills

자동 트리거 워크플로우. `.claude/skills/` 에 정의.

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

**사용법**: 트리거 키워드 언급 시 자동 로드 또는 직접 호출

```bash
# 전체 Phase 상태 확인
python .claude/skills/phase-validation/scripts/validate_phase.py --status

# TDD 자동 사이클
python .claude/skills/tdd-workflow/scripts/tdd_auto_cycle.py tests/test_file.py

# 품질 검사
python .claude/skills/code-quality-checker/scripts/run_quality_check.py --fix
```

> 상세: `.claude/skills/<skill-name>/SKILL.md`

---

## 7. Agents

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

### 병렬 호출

```python
# 단일 메시지에 여러 Task = 병렬 실행
Task(subagent_type="frontend-developer", prompt="UI 구현", description="프론트")
Task(subagent_type="backend-architect", prompt="API 구현", description="백엔드")
```

> 전체 에이전트 목록 (28개): `docs/AGENTS_REFERENCE.md`

---

## 8. Architecture

```
D:\AI\claude01\
├── .claude/
│   ├── commands/      # 슬래시 커맨드 (28개)
│   ├── plugins/       # 로컬 에이전트 정의 (49개)
│   ├── skills/        # webapp-testing, skill-creator
│   └── hooks/         # 프롬프트 검증
├── src/agents/        # LangGraph 멀티에이전트
├── scripts/           # Phase Validators (PowerShell)
├── tasks/prds/        # PRD 문서
├── tests/             # pytest 테스트
└── archive-analyzer/  # 서브프로젝트 (별도 CLAUDE.md)
```

### LangGraph Multi-Agent (Fan-Out/Fan-In)

```
Supervisor (sonnet) → [Agent 0, Agent 1, Agent 2] (병렬) → Aggregator (sonnet)
```

**Model Tiering** (`src/agents/config.py`):
- supervisor/researcher: sonnet (복잡한 의사결정)
- validator: haiku (간단한 검증, 비용 최적화)

---

## 9. Browser Testing & E2E

**모든 Phase에서** 브라우저 테스트 가능.

```powershell
# Playwright 직접 실행
npx playwright test tests/e2e/flow.spec.ts

# webapp-testing 스킬 (서버 자동 관리)
python .claude/skills/webapp-testing/scripts/with_server.py \
  --server "npm run dev" --port 3000 -- python your_test.py

# playwright-engineer 에이전트
Task(subagent_type="playwright-engineer", prompt="로그인 플로우 테스트", description="E2E")
```

**E2E 실패 처리**: 1-2회 자동 수정 시도 → 3회 실패 시 `/issue-failed` → 수동 개입

> 상세: `.claude/skills/webapp-testing/SKILL.md`

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
