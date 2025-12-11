# Agent 완전 참조 가이드

**목적**: 에이전트 분류 및 활용법

**버전**: 3.0.0 | **업데이트**: 2025-12-11 | **동기화**: CLAUDE.md v8.0.0

---

## 에이전트 분류 요약

| 구분 | 개수 | 설명 |
|------|------|------|
| 내장 Subagent | 4개 | Claude Code 공식 내장 |
| 로컬 - 활성 | 7개 | Commands/Skills에서 직접 참조 |
| 계획 에이전트 | 21개 | 미구현 (docs/PLANNED_AGENTS.md) |
| 아카이브 | 6개 | `.claude/plugins.archive/` |

---

## 내장 Subagent (4개) - 직접 호출 가능

| Agent | 용도 | 도구 | 호출 |
|-------|------|------|------|
| `general-purpose` | 복잡한 다단계 작업 | 모든 도구 | `Task(subagent_type="general-purpose")` |
| `Explore` | 코드베이스 빠른 탐색 | Glob, Grep, Read | `Task(subagent_type="Explore")` |
| `Plan` | 구현 계획 설계 | 읽기 도구만 | 자동 (Plan Mode) |
| `debugger` | 버그 분석/수정 | Read, Edit, Bash, Grep | `Task(subagent_type="debugger")` |

> **참고**: `claude-code-guide`, `statusline-setup`은 슬래시 커맨드이며 subagent 아님

---

## 로컬 에이전트 - 활성 (7개)

Commands/Skills에서 직접 참조되는 에이전트:

| Agent | 참조 위치 | Phase | 연동 스킬 |
|-------|----------|-------|----------|
| `debugger` | analyze, fix-issue, tdd | 1, 2, 5 | debugging-workflow |
| `backend-architect` | api-test | 1 | - |
| `code-reviewer` | check, optimize, tdd | 2.5 | code-quality-checker |
| `test-automator` | fix-issue, tdd | 2 | tdd-workflow |
| `security-auditor` | check, api-test, final-check | 5 | final-check-automation |
| `playwright-engineer` | final-check | 2, 5 | final-check-automation, webapp-testing |
| `context7-engineer` | pre-work | 0, 1 | pre-work-research |

---

## 스킬-에이전트 매핑

| 스킬 | 사용 에이전트 | Phase |
|------|-------------|-------|
| `tdd-workflow` | test-automator, debugger | 1, 2 |
| `debugging-workflow` | debugger (subagent) | 1, 2, 5 |
| `code-quality-checker` | code-reviewer, security-auditor | 2, 2.5 |
| `final-check-automation` | playwright-engineer, security-auditor | 5 |
| `phase-validation` | (내장 로직) | 0-6 |
| `pre-work-research` | context7-engineer | 0 |
| `issue-resolution` | debugging-workflow, tdd-workflow | 1, 2 |
| `parallel-agent-orchestration` | debugger, code-reviewer | 1, 2 |
| `journey-sharing` | (내장 로직) | 4 |
| `pr-review-agent` | general-purpose | - |

---

## 계획 에이전트 (21개)

**상세 목록**: [docs/PLANNED_AGENTS.md](./PLANNED_AGENTS.md) 참조

### 개발 (6개)
`python-pro`, `frontend-developer`, `fullstack-developer`, `typescript-expert`, `mobile-developer`, `graphql-architect`

### 인프라/DevOps (4개)
`deployment-engineer`, `devops-troubleshooter`, `cloud-architect`, `architect-reviewer`

### 데이터 (3개)
`database-architect`, `database-optimizer`, `supabase-engineer`

### 지원/계획 (5개)
`seq-engineer`, `taskmanager-planner`, `task-decomposition-expert`, `exa-search-specialist`, `context-manager`

### 기타 (3개)
`github-engineer`, `performance-engineer`

---

## 아카이브 (6개)

`.claude/plugins.archive/`로 이동됨:

```
cli-ui-designer, django-pro, docusaurus-expert,
hybrid-cloud-architect, temporal-python-pro, tutorial-engineer
```

---

## 병렬 실행 패턴

### 패턴 1: Phase 0 병렬 분석
```
context7-engineer (기술 스택 검증)
  ∥
Explore (코드베이스 탐색)
```

### 패턴 2: Phase 2 병렬 테스트
```
test-automator (단위 테스트)
  ∥
playwright-engineer (E2E 테스트)
  ∥
security-auditor (보안 스캔)
```

### 패턴 3: Phase 5 병렬 검증
```
playwright-engineer (E2E 최종 검증)
  ∥
security-auditor (보안 점검)
```

---

## 병렬 실행 원칙

### 병렬 가능한 경우
1. **독립적 작업**: 서로 다른 파일/모듈 작업
2. **같은 Phase**: 동일 Phase 내 여러 작업
3. **Read-only 분석**: 여러 분석 작업 동시 수행

### 순차 필수 경우
1. **의존성 존재**: A의 출력이 B의 입력
2. **Phase 간**: Phase 1 완료 후 Phase 2 시작
3. **공유 리소스**: 같은 파일 동시 수정

---

## Agent 선택 가이드

### 작업 유형별

| 작업 | 추천 Agent | 연동 스킬 |
|------|-----------|----------|
| 기술 검증 | `context7-engineer` | pre-work-research |
| 버그 분석 | `debugger` | debugging-workflow |
| 테스트 작성 | `test-automator` | tdd-workflow |
| 코드 리뷰 | `code-reviewer` | code-quality-checker |
| 보안 검사 | `security-auditor` | code-quality-checker |
| E2E 테스트 | `playwright-engineer` | final-check-automation |
| API 테스트 | `backend-architect` | - |

---

## 참조

- [CLAUDE.md](../CLAUDE.md) - 핵심 워크플로우 (v8.0.0)
- [PLANNED_AGENTS.md](./PLANNED_AGENTS.md) - 계획 에이전트 목록
- [COMMAND_SELECTOR.md](./COMMAND_SELECTOR.md) - 커맨드 선택 가이드
- `.claude/skills/` - 스킬 상세

---

**관리**: Claude Code
**업데이트**: 2025-12-11
**버전**: 3.0.0
