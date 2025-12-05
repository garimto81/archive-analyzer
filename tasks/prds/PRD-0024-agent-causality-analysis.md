# PRD-0024: 에이전트 인과관계 분석 및 정리

**Version**: 1.0.0 | **Created**: 2025-12-05 | **Status**: Draft
**Issue**: [#24](https://github.com/garimto81/archive-analyzer/issues/24)

---

## 1. 개요

### 1.1 목적
CLAUDE.md 및 워크플로우에 기록된 에이전트와 실제 존재하는 에이전트 간의 **인과관계 분석** 및 **미사용 에이전트 처리 방안** 수립

### 1.2 배경
| 구분 | 개수 | 위치 |
|------|------|------|
| 내장 subagent | 4개 (공식) | Claude Code 시스템 |
| 로컬 에이전트 | 56개 (유니크) | `.claude/plugins/*/agents/*.md` |
| CLAUDE.md 언급 | 33개 | `docs/AGENTS_REFERENCE.md` |
| 워크플로우 참조 | 12개 | `.claude/commands/*.md` |

### 1.3 문제점
1. **혼동**: "내장 subagent 37개"라고 명시했으나 실제 내장은 4개
2. **미사용**: 56개 로컬 에이전트 중 워크플로우에서 호출되는 것은 12개
3. **중복**: 동일 에이전트가 여러 플러그인에 중복 정의 (예: `code-reviewer` 3곳)

---

## 2. 분석 결과

### 2.1 Claude Code 공식 내장 Subagent (4개)

| 에이전트 | 기능 | 도구 | 특성 |
|---------|------|------|------|
| `general-purpose` | 복잡한 다단계 작업 | 모든 도구 | 범용 |
| `Explore` | 코드베이스 탐색 | Glob, Grep, Read | 읽기 전용, Haiku |
| `Plan` | 계획 수립 | 읽기 도구만 | Plan Mode 전용 |
| `debugger` | 버그 분석/수정 | Read, Edit, Bash, Grep | 순차 필수 |

> **참고**: `claude-code-guide`, `statusline-setup`은 **슬래시 커맨드**이며 subagent가 아님

### 2.2 로컬 에이전트 분류

#### A. 워크플로우에서 참조되는 에이전트 (12개) - **활성**

| 에이전트 | 참조 위치 | Phase |
|---------|----------|-------|
| `frontend-developer` | CLAUDE.md | 1 |
| `backend-architect` | CLAUDE.md, api-test.md | 1 |
| `test-automator` | CLAUDE.md, tdd.md, fix-issue.md | 2 |
| `playwright-engineer` | CLAUDE.md, final-check.md | 2, 5 |
| `security-auditor` | api-test.md, check.md | 5 |
| `code-reviewer` | tdd.md, check.md, fix-issue.md, optimize.md | 1 후 |
| `debugger` | analyze-logs.md, fix-issue.md, final-check.md | 문제 시 |
| `seq-engineer` | - | 0 |
| `context7-engineer` | pre-work.md | 0, 1 |
| `exa-search-specialist` | pre-work.md | 0 |
| `architect-reviewer` | - | 0, 1 |
| `deployment-engineer` | - | 6 |

#### B. CLAUDE.md에만 언급 (21개) - **대기**

문서에 언급되었으나 슬래시 커맨드에서 직접 호출되지 않음:
```
python-pro, fullstack-developer, typescript-expert, mobile-developer,
graphql-architect, supabase-engineer, performance-engineer,
devops-troubleshooter, cloud-architect, github-engineer,
database-architect, database-optimizer, data-engineer, data-scientist,
ai-engineer, ml-engineer, UI_UX-Designer, prompt-engineer,
taskmanager-planner, task-decomposition-expert, context-manager
```

#### C. 정의만 존재 (23개) - **미사용**

`.claude/plugins/`에 정의되어 있으나 어디서도 참조되지 않음:
```
agent-expert, api-documenter, cli-ui-designer, command-expert,
django-pro, docs-architect, docusaurus-expert, dx-optimizer,
fastapi-pro, hybrid-cloud-architect, javascript-pro,
kubernetes-architect, legacy-modernizer, mcp-expert, network-engineer,
observability-engineer, tdd-orchestrator, temporal-python-pro,
terraform-specialist, tutorial-engineer, typescript-pro,
design-review, pragmatic-code-review
```

### 2.3 중복 에이전트

| 에이전트 | 중복 위치 |
|---------|----------|
| `code-reviewer` | code-documentation, code-refactoring, git-pr-workflows, phase-2-testing |
| `cloud-architect` | cicd-automation, cloud-infrastructure, phase-6-deployment |
| `deployment-engineer` | cicd-automation, full-stack-orchestration, phase-6-deployment |
| `frontend-developer` | application-performance, meta-development, phase-1-development |
| `security-auditor` | full-stack-orchestration, phase-2-testing, security-scanning |

### 2.4 MCP 연동 에이전트

| 로컬 에이전트 | MCP 도구 | 상태 |
|--------------|---------|------|
| `exa-search-specialist` | `mcp__exa__search` | 활성 |
| `context-manager` | `mcp__mem0__*` | 대기 |
| `context7-engineer` | `mcp__ref__search` | 활성 |

---

## 3. 제안 방안

### 3.1 CLAUDE.md 섹션 4 수정

**기존**:
```markdown
## 4. Agents (내장 Subagent 중심)
Claude Code **내장 subagent 37개**를 활용.
```

**변경**:
```markdown
## 4. Agents

### 4.1 내장 Subagent (4개)
| 에이전트 | 용도 | 호출 |
|---------|------|------|
| `general-purpose` | 복잡한 다단계 작업 | Task(subagent_type="general-purpose") |
| `Explore` | 코드베이스 탐색 | Task(subagent_type="Explore") |
| `Plan` | 계획 수립 | 자동 (Plan Mode) |
| `debugger` | 버그 분석/수정 | Task(subagent_type="debugger") |

### 4.2 로컬 에이전트 (12개 활성)
`.claude/plugins/*/agents/*.md`에 정의된 프로젝트 맞춤형 에이전트.

| 에이전트 | Phase | 용도 |
|---------|-------|------|
| `frontend-developer` | 1 | React/Next.js 컴포넌트 |
| `backend-architect` | 1 | API 설계 |
| ... |

> 전체 목록: `docs/AGENTS_REFERENCE.md`

### 4.3 MCP 연동 에이전트 (3개)
| 에이전트 | MCP 도구 |
|---------|---------|
| `exa-search-specialist` | `mcp__exa__search` |
| `context7-engineer` | `mcp__ref__search` |
| `context-manager` | `mcp__mem0__*` |
```

### 3.2 로컬 에이전트 정리

#### Phase 1: 중복 제거
- 중복 정의된 5개 에이전트 → 대표 위치 1곳만 유지
- 나머지 → 심볼릭 링크 또는 삭제

#### Phase 2: 미사용 아카이브
```powershell
# 미사용 23개 → .claude/plugins.archive/로 이동
mkdir .claude/plugins.archive
mv .claude/plugins/meta-development/agents/agent-expert.md .claude/plugins.archive/
...
```

#### Phase 3: 활성 에이전트 문서화
- `docs/AGENTS_REFERENCE.md` 재구성
- 활성 12개 + 대기 21개 = 33개 문서화
- Phase별 권장 에이전트 테이블

### 3.3 워크플로우 인과관계 다이어그램

```
                    ┌─────────────────┐
                    │   사용자 요청    │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            ↓                ↓                ↓
    ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
    │   PRE_WORK    │ │     IMPL      │ │  FINAL_CHECK  │
    │   (Phase 0)   │ │  (Phase 1-2)  │ │  (Phase 3-6)  │
    └───────┬───────┘ └───────┬───────┘ └───────┬───────┘
            │                 │                 │
    ┌───────┴───────┐ ┌───────┴───────┐ ┌───────┴───────┐
    │ 내장          │ │ 로컬          │ │ 로컬          │
    │ - Explore     │ │ - frontend-   │ │ - playwright- │
    │ - Plan        │ │   developer   │ │   engineer    │
    │               │ │ - backend-    │ │ - security-   │
    │ 로컬          │ │   architect   │ │   auditor     │
    │ - context7-   │ │ - test-       │ │               │
    │   engineer    │ │   automator   │ │ 내장          │
    │ - exa-search- │ │               │ │ - debugger    │
    │   specialist  │ │ 내장          │ │               │
    │               │ │ - debugger    │ │               │
    │               │ │ - general-    │ │               │
    │               │ │   purpose     │ │               │
    └───────────────┘ └───────────────┘ └───────────────┘
```

---

## 4. 작업 항목

### 4.1 Phase 1: 문서 수정

- [ ] CLAUDE.md 섹션 4 재구성 (내장/로컬/MCP 분리)
- [ ] "내장 subagent 37개" → "내장 4개 + 로컬 12개 + MCP 3개" 수정
- [ ] `docs/AGENTS_REFERENCE.md` 활성/대기/미사용 분류 추가

### 4.2 Phase 2: 중복 제거

- [ ] 중복 에이전트 5개 대표 위치 결정
- [ ] 중복 파일 삭제 또는 심볼릭 링크 변환
- [ ] 플러그인 구조 정리

### 4.3 Phase 3: 미사용 아카이브

- [ ] `.claude/plugins.archive/` 디렉토리 생성
- [ ] 미사용 에이전트 23개 이동
- [ ] `.gitignore`에 아카이브 추가 (선택)

### 4.4 Phase 4: 검증

- [ ] 슬래시 커맨드 동작 테스트
- [ ] CLAUDE.md 정확성 검증
- [ ] PR 생성 및 리뷰

---

## 5. 성공 기준

| 기준 | 현재 | 목표 |
|------|------|------|
| 내장 에이전트 명시 | "37개" (오류) | "4개" (정확) |
| 로컬 에이전트 | 56개 (중복 포함) | 33개 (유니크) |
| 미사용 에이전트 | 혼재 | 아카이브 분리 |
| 문서 정확성 | ~70% | 100% |

---

## 6. 위험 및 완화

| 위험 | 영향 | 완화 방안 |
|------|------|----------|
| 아카이브 후 필요한 에이전트 발견 | 중 | 아카이브에서 복원 가능 |
| 심볼릭 링크 Windows 호환성 | 낮 | 직접 복사로 대체 |
| 기존 워크플로우 중단 | 높 | 활성 에이전트는 위치 유지 |

---

## 7. 참고 자료

- [Claude Code Subagents Documentation](https://code.claude.com/docs/en/sub-agents.md)
- [CLAUDE.md v3.5.0](D:\AI\claude01\CLAUDE.md)
- [docs/AGENTS_REFERENCE.md](D:\AI\claude01\docs\AGENTS_REFERENCE.md)
