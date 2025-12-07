---
name: create
description: Create PRD, PR, or documentation (prd, pr, docs)
---

# /create - 생성 통합 커맨드

PRD, PR, 문서를 생성합니다.

## Usage

```
/create <target> [args]

Targets:
  prd [name] [--template]   PRD 문서 생성 (Phase 0)
  pr [base-branch]          Pull Request 생성 (Phase 4)
  docs [path] [--format]    API/코드 문서 생성
```

---

## /create prd - PRD 생성

```bash
/create prd user-authentication
/create prd "검색 기능" --template=minimal
/create prd --template=deep
```

### 대화형 워크플로우

Claude Code가 3-8개 명확화 질문 (A/B/C/D 형식):

```
/create prd user-authentication

Let's create a PRD. I'll ask some questions:

A. Target Users
   A) End users only
   B) Admins only
   C) Both
   D) External API consumers

B. Authentication Method
   A) Email/Password
   B) OAuth2
   C) SSO
   D) No auth needed

...
```

### 템플릿 옵션

| 템플릿 | 소요 시간 | 토큰 | 대상 |
|--------|----------|------|------|
| `minimal` | 10분 | ~1270 | 숙련 개발자 |
| `standard` | 20-30분 | ~2500 | 일반 프로젝트 |
| `junior` | 40-60분 | ~4500 | 초보자 |
| `deep` | 60+분 | ~6000 | 완벽한 기획서 |

### DEEP 템플릿 출력 구조

```
tasks/prds/NNNN-feature-name/
├── README.md              # 전체 기획서
├── 01-requirements.md     # 요구사항 상세
├── 02-architecture.md     # 아키텍처 설계
├── 03-implementation.md   # 구현 계획
├── 04-testing.md          # 테스트 전략
└── 05-deployment.md       # 배포 계획
```

### PRD 출력 형식

```markdown
# PRD: [Feature Name]

**Version**: 1.0
**Date**: 2025-01-18
**Status**: Draft

---

## 1. Purpose
[자동 생성]

## 2. Target Users
- Primary: [From question A]

## 3. Core Features

### 3.1 [Feature 1]
**Priority**: High
**Effort**: Medium

## 4. Technical Requirements

### 4.1 Authentication
- Method: [From question B]

## 5. Success Metrics
[자동 생성 KPIs]

## 6. Timeline
- Phase 0: Requirements (1-2 days)
- Phase 1: Implementation
...

---

**Next Steps**: Run `/todo` to generate task list
```

### 자동 번호 지정

```bash
# 기존 PRDs:
tasks/prds/0001-prd-auth.md
tasks/prds/0002-prd-dashboard.md

# 새 PRD:
/create prd search-feature
→ 0003-prd-search-feature.md
```

---

## /create pr - Pull Request 생성

```bash
/create pr              # 기본 (main 대상)
/create pr develop      # 특정 base branch
/create pr --draft      # Draft PR
```

### Workflow

1. **Verify Git State**
   - 현재 브랜치 확인
   - 클린 워킹 디렉토리 확인
   - 커밋 존재 확인

2. **Push Changes**
   ```bash
   git push -u origin <branch>
   ```

3. **Generate PR Description**
   - `git log`에서 변경 사항 분석
   - 템플릿 적용:

   ```markdown
   ## Summary
   - Key changes

   ## Test Plan
   - [ ] Testing checklist

   ## Related
   - PRD reference
   ```

4. **Create PR**
   ```bash
   gh pr create --title "..." --body "..."
   ```
   - 자동 라벨 적용
   - 이슈 연결

### Phase Integration

- **Phase 4**: Primary use case
- `[PRD-NNNN]` 또는 `[#issue]` 참조
- Auto-merge 워크플로우 연동

### 출력 예시

```bash
/create pr

# Output:
# ✓ Pushing to origin/feature/PRD-0001-auth
# ✓ Analyzing 3 commits
# ✓ Creating PR #42: Add OAuth2 authentication
# → https://github.com/user/repo/pull/42
```

---

## /create docs - 문서 생성

```bash
/create docs                         # 전체 프로젝트
/create docs src/auth/               # 특정 경로
/create docs --format=html           # HTML 형식
/create docs --format=sphinx         # Sphinx 형식
```

### 문서 유형

#### 1. API Documentation

```markdown
## `login(email: str, password: str) -> User`

Authenticates user with email and password.

### Parameters
- `email` (str): User email address
- `password` (str): Plain text password

### Returns
- `User`: Authenticated user object

### Raises
- `AuthenticationError`: Invalid credentials

### Example
```python
user = login("test@example.com", "password123")
```

### Edge Cases
- Empty email/password → raises ValueError
```

#### 2. Class Documentation

```markdown
## Class: `UserManager`

Manages user accounts and authentication.

### Attributes
- `session`: Database session
- `cache`: Redis cache instance

### Methods
- `create_user()`: Create new user
- `authenticate()`: Verify credentials

### Usage
```python
manager = UserManager(session=db.session)
user = manager.create_user(email="test@example.com")
```
```

#### 3. Module Documentation

```markdown
# auth Module

User authentication and session management.

## Overview
Provides OAuth2 and email/password authentication.

## Quick Start
```python
from auth import login, logout
user = login("test@example.com", "password")
```

## Components
- `login()`: User authentication
- `logout()`: Session termination
```

### 출력 구조

```
docs/
├── api/
│   ├── auth.md
│   ├── users.md
│   └── sessions.md
├── guides/
│   ├── quickstart.md
│   └── authentication.md
├── reference/
│   └── configuration.md
└── index.md
```

### Auto-Generated Content

- **입출력 분석**: 함수 시그니처, 타입 힌트
- **Edge Cases**: None 처리, 빈 문자열, 경계 조건
- **Code Examples**: 기본 사용, 고급 패턴, 에러 처리

---

## Related

- `/commit` - 커밋 생성
- `/changelog` - CHANGELOG 업데이트
- `/todo` - PRD에서 Task 생성
