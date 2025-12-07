# PRD-0029: GitHub Actions 통합

**Version**: 1.0.0 | **Date**: 2025-12-06 | **Status**: Draft
**Parent**: [PRD-0025](./PRD-0025-master-workflow-optimization.md)
**Priority**: P1

---

## 1. 목적

Claude Code Action을 활용하여 **PR 자동 리뷰**, **이슈 자동 분류**, **CI 실패 자동 수정**을 구현합니다.

---

## 2. 신규 워크플로우 (3개)

| 워크플로우 | 트리거 | 효과 |
|------------|--------|------|
| `claude-pr-review.yml` | PR opened/sync | 리뷰 시간 50% 감소 |
| `claude-issue-triage.yml` | Issue opened | 분류 100% 자동화 |
| `claude-ci-fix.yml` | CI failure | 단순 오류 자동 수정 |

---

## 3. claude-pr-review.yml

### 3.1 워크플로우 정의

```yaml
name: Claude Auto PR Review
on:
  pull_request:
    types: [opened, synchronize]
    branches: [main, develop]

permissions:
  contents: read
  pull-requests: write

jobs:
  claude-review:
    runs-on: ubuntu-22.04
    if: contains(github.event.pull_request.title, 'Phase 2')
    steps:
      - uses: actions/checkout@v4
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: |
            CLAUDE.md 규칙에 따라 리뷰:
            1. TDD 1:1 페어링 확인
            2. 보안 취약점 검사
            3. Phase Pipeline 준수 여부
```

### 3.2 리뷰 초점

- TDD 1:1 테스트 페어링
- Conventional Commits 준수
- 보안 취약점 (API 키, SQL Injection)
- Phase Pipeline 정합성

---

## 4. claude-issue-triage.yml

### 4.1 워크플로우 정의

```yaml
name: Claude Issue Triage
on:
  issues:
    types: [opened]

permissions:
  contents: read
  issues: write

jobs:
  triage:
    runs-on: ubuntu-22.04
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: |
            이슈 분석 및 라벨 분류:
            - bug, enhancement, documentation
            - priority-critical/high/medium/low
            - phase-X (해당 시)
```

### 4.2 분류 규칙

| 라벨 유형 | 값 |
|----------|---|
| 종류 | bug, enhancement, documentation, question |
| 우선순위 | priority-critical/high/medium/low |
| Phase | phase-0 ~ phase-6 |

---

## 5. claude-ci-fix.yml

### 5.1 워크플로우 정의

```yaml
name: Claude CI Auto-Fix
on:
  workflow_run:
    workflows: ["CI/CD Pipeline"]
    types: [completed]
    branches: [feature/PRD-*]

permissions:
  contents: write
  pull-requests: write

jobs:
  auto-fix:
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          prompt: |
            CI 실패 분석 및 자동 수정:
            - 단순 오류: 즉시 수정 후 커밋
            - 복잡한 버그: 분석 코멘트만
            - 3회 연속 실패: STOP
```

### 5.2 수정 범위

| 오류 유형 | 자동 수정 | 수동 개입 |
|----------|----------|----------|
| Import 오류 | ✅ | - |
| Lint 오류 | ✅ | - |
| Type 오류 | ✅ | - |
| 로직 버그 | - | ✅ |
| 테스트 실패 | - | ✅ (분석만) |

---

## 6. 보안 설정

### 6.1 필수 Secrets

```bash
# GitHub Repository Settings → Secrets
ANTHROPIC_API_KEY  # Claude API 키
```

### 6.2 권장 브랜치 보호

```yaml
Branch: main, master
Rules:
- Require PR before merging
- Require 1 approval
- Require status checks:
  - Claude Auto PR Review
  - CI/CD Pipeline
```

---

## 7. 구현 Task

- [ ] Task 1: `ANTHROPIC_API_KEY` Secrets 설정
- [ ] Task 2: `claude-pr-review.yml` 생성 및 테스트
- [ ] Task 3: `claude-issue-triage.yml` 생성 및 테스트
- [ ] Task 4: `claude-ci-fix.yml` 생성 (실험적)
- [ ] Task 5: 브랜치 보호 규칙 업데이트

---

## 8. 성공 지표

| 지표 | 현재 | 목표 |
|------|------|------|
| PR 리뷰 자동화율 | 0% | 100% |
| 이슈 분류 시간 | 수동 | < 30초 |
| CI 자동 수정율 | 0% | 단순 오류 80% |

---

**Dependencies**: PRD-0027 (Skills 완료 후 권장)
**Next**: 모니터링 및 최적화
