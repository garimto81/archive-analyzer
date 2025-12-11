# Planned Agents (미구현)

**목적**: 향후 구현 예정 에이전트 목록

**버전**: 1.0.0 | **업데이트**: 2025-12-11 | **동기화**: CLAUDE.md v8.0.0

---

## 개요

현재 활성화된 에이전트: **11개** (내장 4 + 로컬 7)

미구현 계획 에이전트: **21개**

---

## 개발 에이전트 (6개)

| Agent | 용도 | 우선순위 |
|-------|------|----------|
| `python-pro` | Python 전문 개발 | 높음 |
| `frontend-developer` | 프론트엔드 개발 | 높음 |
| `fullstack-developer` | 풀스택 개발 | 중간 |
| `typescript-expert` | TypeScript 전문 | 중간 |
| `mobile-developer` | 모바일 앱 개발 | 낮음 |
| `graphql-architect` | GraphQL API 설계 | 낮음 |

### 예상 활용

```python
# python-pro
Task(
    subagent_type="python-pro",
    prompt="Python 3.12 최신 기능으로 비동기 처리 구현",
    description="Python 전문 개발"
)

# frontend-developer
Task(
    subagent_type="frontend-developer",
    prompt="React 컴포넌트 최적화 및 성능 개선",
    description="프론트엔드 개발"
)
```

---

## 인프라/DevOps 에이전트 (4개)

| Agent | 용도 | 우선순위 |
|-------|------|----------|
| `deployment-engineer` | 배포 자동화 | 높음 |
| `devops-troubleshooter` | DevOps 문제 해결 | 높음 |
| `cloud-architect` | 클라우드 아키텍처 | 중간 |
| `architect-reviewer` | 아키텍처 리뷰 | 중간 |

### 예상 활용

```python
# deployment-engineer
Task(
    subagent_type="deployment-engineer",
    prompt="GitHub Actions CI/CD 파이프라인 구축",
    description="배포 자동화"
)
```

---

## 데이터 에이전트 (3개)

| Agent | 용도 | 우선순위 |
|-------|------|----------|
| `database-architect` | DB 설계 | 높음 |
| `database-optimizer` | DB 성능 최적화 | 중간 |
| `supabase-engineer` | Supabase 전문 | 낮음 |

### 예상 활용

```python
# database-architect
Task(
    subagent_type="database-architect",
    prompt="PostgreSQL 스키마 설계 및 인덱스 최적화",
    description="DB 설계"
)
```

---

## 지원/계획 에이전트 (5개)

| Agent | 용도 | 우선순위 |
|-------|------|----------|
| `seq-engineer` | 시퀀스 다이어그램 | 중간 |
| `taskmanager-planner` | 작업 계획 수립 | 중간 |
| `task-decomposition-expert` | 작업 분해 | 중간 |
| `exa-search-specialist` | 고급 검색 | 낮음 |
| `context-manager` | 컨텍스트 관리 | 낮음 |

---

## 기타 에이전트 (3개)

| Agent | 용도 | 우선순위 |
|-------|------|----------|
| `github-engineer` | GitHub 고급 기능 | 중간 |
| `performance-engineer` | 성능 엔지니어링 | 중간 |
| `documentation-writer` | 문서 작성 | 낮음 |

---

## 구현 로드맵

### Phase 1: 높은 우선순위 (6개)

```
python-pro
frontend-developer
deployment-engineer
devops-troubleshooter
database-architect
```

### Phase 2: 중간 우선순위 (9개)

```
fullstack-developer
typescript-expert
cloud-architect
architect-reviewer
database-optimizer
seq-engineer
taskmanager-planner
task-decomposition-expert
github-engineer
performance-engineer
```

### Phase 3: 낮은 우선순위 (6개)

```
mobile-developer
graphql-architect
supabase-engineer
exa-search-specialist
context-manager
documentation-writer
```

---

## 구현 시 필요 작업

### 1. 에이전트 정의 파일 생성

```
src/agents/<agent-name>/
├── __init__.py
├── config.py      # 에이전트 설정
├── prompts.py     # 시스템 프롬프트
└── tools.py       # 사용 도구 정의
```

### 2. 스킬 연동 (선택)

```
.claude/skills/<skill-name>/
├── SKILL.md       # 스킬 정의
└── examples/      # 사용 예시
```

### 3. 커맨드 연동 (선택)

```
.claude/commands/<command>.md
# 에이전트 호출 코드 추가
```

---

## 아카이브된 에이전트 (6개)

`.claude/plugins.archive/`로 이동됨:

| Agent | 이유 |
|-------|------|
| `cli-ui-designer` | 사용 빈도 낮음 |
| `django-pro` | 프로젝트 미사용 |
| `docusaurus-expert` | 프로젝트 미사용 |
| `hybrid-cloud-architect` | 범위 과도 |
| `temporal-python-pro` | 프로젝트 미사용 |
| `tutorial-engineer` | 사용 빈도 낮음 |

---

## 참조

- [AGENTS_REFERENCE.md](./AGENTS_REFERENCE.md) - 활성 에이전트
- [CLAUDE.md](../CLAUDE.md) - 핵심 워크플로우
- `.claude/plugins.archive/` - 아카이브 에이전트

---

**관리**: Claude Code
**업데이트**: 2025-12-11
**버전**: 1.0.0
