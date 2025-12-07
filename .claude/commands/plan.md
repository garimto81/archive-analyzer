---
name: plan
description: RPI Phase 2 - 구현 계획 수립
---

# /plan - Plan Phase (RPI Step 2)

리서치 결과를 바탕으로 상세 구현 계획을 수립합니다.

## Usage

```
/plan <target> [options]

Targets:
  <issue-num>     특정 이슈 구현 계획
  <feature>       기능 구현 계획

Options:
  --save          결과를 .claude/plans/에 저장
  --detailed      상세 계획 (파일별 변경사항)
  --tdd           TDD 기반 계획 (테스트 우선)
```

---

## RPI 워크플로우

```
┌─────────────────────────────────────────────────────────┐
│  [R] Research → [P] Plan → [I] Implement                │
│                    ↑                                    │
│                 현재 단계                               │
└─────────────────────────────────────────────────────────┘
```

**전제조건**: `/research` 완료 후 실행

---

## /plan 123

이슈 #123 구현 계획을 수립합니다.

```bash
/plan 123
# Output:
# 📋 Implementation Plan: Issue #123
#
# ## 요약
# - 목표: 사용자 인증 기능 추가
# - 예상 파일: 5개
# - 예상 테스트: 12개
#
# ## 구현 단계
#
# ### Step 1: 데이터 모델
# - [ ] src/models/user.py 생성
# - [ ] tests/test_user_model.py 생성
#
# ### Step 2: 인증 로직
# - [ ] src/auth/service.py 수정
# - [ ] tests/test_auth_service.py 생성
#
# ### Step 3: API 엔드포인트
# - [ ] src/api/auth.py 생성
# - [ ] tests/test_auth_api.py 생성
#
# ### Step 4: 통합 테스트
# - [ ] tests/integration/test_auth_flow.py
#
# ## 의존성
# - Step 2는 Step 1 완료 후
# - Step 3은 Step 2 완료 후
#
# → 다음: 구현 시작 (Step 1부터)
```

---

## /plan --tdd

TDD 기반 계획을 수립합니다.

```bash
/plan 123 --tdd
# Output:
# 🔴 TDD Implementation Plan: Issue #123
#
# ## Red-Green-Refactor Cycle
#
# ### Cycle 1: User Model
# 1. 🔴 test_user_creation() 작성 → FAIL
# 2. 🟢 User 클래스 구현 → PASS
# 3. 🔵 리팩토링
#
# ### Cycle 2: Password Hashing
# 1. 🔴 test_password_hash() 작성 → FAIL
# 2. 🟢 hash_password() 구현 → PASS
# 3. 🔵 리팩토링
#
# ### Cycle 3: JWT Token
# ...
```

---

## /plan --detailed

파일별 상세 변경사항을 포함합니다.

```bash
/plan 123 --detailed
# Output:
# 📋 Detailed Plan: Issue #123
#
# ## 파일별 변경사항
#
# ### src/models/user.py (신규)
# ```python
# @dataclass
# class User:
#     id: str
#     email: str
#     password_hash: str
#     created_at: datetime
# ```
#
# ### src/auth/service.py (수정)
# - Line 45-60: authenticate() 함수 추가
# - Line 70-85: create_token() 함수 추가
#
# ...
```

---

## 계획 저장

`--save` 옵션으로 결과를 저장합니다.

```bash
/plan 123 --save
# Output: 저장됨 → .claude/plans/issue-123-plan.md
```

### 저장 형식

```markdown
# Implementation Plan: Issue #123

**Date**: 2025-12-07
**Issue**: 사용자 인증 기능 추가
**Research**: .claude/research/issue-123-research.md

## 구현 단계

### Step 1: 데이터 모델
- [ ] src/models/user.py
- [ ] tests/test_user_model.py

### Step 2: 인증 로직
...

## 체크리스트
- [ ] 모든 테스트 통과
- [ ] 코드 리뷰 완료
- [ ] 문서 업데이트
```

---

## 저장 위치

```
.claude/
└── plans/
    ├── issue-123-plan.md
    ├── feature-auth-plan.md
    └── ...
```

---

## 계획 검증

계획 품질 체크리스트:

| 항목 | 확인 |
|------|------|
| 테스트 파일 포함 | 1:1 페어링 |
| 의존성 순서 | 명확한 순서 |
| 영향 범위 | 모든 관련 파일 |
| 리스크 식별 | 잠재적 문제점 |

---

## Best Practices

1. **리서치 후 계획**: `/research` → `/plan` 순서
2. **TDD 우선**: `--tdd` 옵션 권장
3. **계획 저장**: `--save`로 기록
4. **계획대로 구현**: 계획 체크리스트 활용

---

## Related

- `/research` - 코드베이스 분석 (RPI Step 1)
- `/tdd` - TDD 가이드
- `/work` - 전체 워크플로우 실행
