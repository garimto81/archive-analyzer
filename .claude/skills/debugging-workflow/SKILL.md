---
name: debugging-workflow
description: >
  디버깅 실패 시 자동 트리거되는 체계적 문제 해결 워크플로우.
  DEBUGGING_STRATEGY.md 기반 Phase 0-3 디버깅 프로세스 자동화.
  트리거: "로그 분석", "debug", "실패", "오류", "버그", "3회 실패"
version: 1.0.0
phase: [1, 2, 5]
auto_trigger: true
dependencies:
  - debugger (subagent)
token_budget: 2500
---

# Debugging Workflow

문제 해결 실패 시 체계적인 디버깅 워크플로우입니다.

## Quick Start

```bash
# 로그 분석 실행
python .claude/skills/debugging-workflow/scripts/analyze_logs.py <log_file>

# 디버그 로그 자동 삽입
python .claude/skills/debugging-workflow/scripts/add_debug_logs.py <source_file>
```

## 핵심 원칙

1. **로그 없이 수정 금지**: 추측 기반 수정은 새 버그 유발
2. **문제 파악 > 해결**: 문제를 정확히 알면 해결은 쉬움
3. **예측 검증 필수**: "내 예측이 로그로 확인되었는가?"

## Phase 0: 디버그 로그 추가

### 로그 패턴

```python
logger.debug(f"[ENTRY] input: {input}")
logger.debug(f"[STATE] current: {state}")
logger.debug(f"[RESULT] output: {result}")
```

### 분석 체크리스트

- [ ] 예상 입력 = 실제 입력?
- [ ] 중간 상태가 예상과 일치?
- [ ] 출력 불일치 지점 확인?
- [ ] **내 예측이 로그로 검증됨?**

> 예측 불일치 시 → Phase 0 재시작

## Phase 1: 문제 영역 분류

```
Q: 이 코드는 언제 작성되었는가?

A) 이번 작업에서 새로 작성 → Phase 2 (신규 기능)
B) 기존에 있던 로직       → Phase 3 (기존 로직)
```

```bash
# Git blame으로 확인
git blame <file_path> | grep "<line_number>"
```

## Phase 2: 신규 기능 문제

**PRD 검토**:
- [ ] 요구사항 모호한 부분?
- [ ] Edge case 정의됨?
- [ ] 에러 처리 명시됨?

**리팩토링 판단** (2개 이상 해당 시):
- [ ] 동일 버그 3회+ 반복
- [ ] 수정 시 Side effect 발생
- [ ] 테스트 커버리지 < 50%
- [ ] "이해하기 어렵다"

## Phase 3: 기존 로직 문제

### 예측 검증 템플릿

```markdown
**가설**: [원인 추정]
**검증 방법**: [확인 방법]
**예상 결과**: [가설 맞으면 기대값]
**실제 결과**: [실험 결과]
**결론**: ✅ 일치 → 해결 / ❌ 불일치 → 새 가설
```

### 해결 전 체크리스트

- [ ] 문제를 한 문장으로 설명 가능?
- [ ] 문제를 재현 가능?
- [ ] 발생 조건 파악?
- [ ] 비발생 조건 파악?
- [ ] 예측이 검증됨?

> **모든 항목 체크 후** 해결 진행

## 실패 시 워크플로우

```
실패 → Phase 0 (로그) → Phase 1 (분류)
         ↓
    ┌────┴────┐
    ↓         ↓
 Phase 2   Phase 3
 (신규)    (기존)
    ↓         ↓
 PRD 검토  예측 검증
    ↓         ↓
 리팩토링? 가설 실험
    ↓
 3회 실패 → /issue-failed
```

## Anti-Patterns

| 금지 | 이유 |
|------|------|
| ❌ 로그 없이 수정 | 추측 = 새 버그 |
| ❌ 문제 파악 전 해결 | 시간 낭비 |
| ❌ 여러 곳 동시 수정 | 원인 파악 불가 |
| ❌ "아마 이거겠지" | 반드시 검증 |

## 관련 도구

| 도구 | 용도 |
|------|------|
| `scripts/analyze_logs.py` | 로그 파일 분석 |
| `scripts/add_debug_logs.py` | 디버그 로그 삽입 |
| `references/log-patterns.md` | 로그 패턴 사전 |
| `/issue-failed` | 3회 실패 시 호출 |

---

> 상세 전략: `docs/DEBUGGING_STRATEGY.md`
