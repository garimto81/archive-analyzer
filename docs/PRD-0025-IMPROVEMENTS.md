# PRD-0025 권장 개선안

PRD-0025 전역 워크플로우 최적화 검증 결과에서 발견된 개선 사항입니다.

**생성일**: 2025-12-06
**관련 PR**: #26
**검증 점수**: 98.5/100

---

## 1. 즉시 조치 필요 (High Priority)

### 없음 ✅

모든 핵심 기능이 정상 동작합니다.

---

## 2. 권장 개선 (Medium Priority)

### 2.1 ci.yml permissions 필드 추가

**파일**: `.github/workflows/ci.yml`
**문제**: `permissions` 필드 누락으로 보안 권한 명시 안됨
**영향**: GitHub Actions 최소 권한 원칙 미준수

**현재 상태**:
```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: "3.11"

jobs:
  # ...
```

**권장 수정**:
```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

permissions:
  contents: read
  pull-requests: read

env:
  PYTHON_VERSION: "3.11"

jobs:
  # ...
```

**적용 방법**:
```bash
# 파일 편집
code .github/workflows/ci.yml

# 커밋
git add .github/workflows/ci.yml
git commit -m "fix(ci): Add permissions field for security best practice"
git push
```

---

### 2.2 tdd-workflow 템플릿 파일 추가

**파일**: `.claude/skills/tdd-workflow/assets/test-templates/`
**문제**: 디렉토리는 존재하나 템플릿 파일 없음
**영향**: SKILL.md 문서와 실제 구현 불일치

**권장 추가 파일**:

#### pytest_template.py
```python
"""
pytest 테스트 템플릿

Usage:
    cp pytest_template.py tests/test_<module>.py
"""
import pytest


class TestClassName:
    """테스트 클래스 설명"""

    @pytest.fixture
    def setup_data(self):
        """테스트 데이터 설정"""
        return {"key": "value"}

    def test_should_do_something_when_condition(self, setup_data):
        """Given-When-Then 패턴 사용"""
        # Given
        input_data = setup_data

        # When
        result = function_under_test(input_data)

        # Then
        assert result == expected_value

    def test_should_raise_error_when_invalid_input(self):
        """예외 테스트"""
        with pytest.raises(ValueError):
            function_under_test(invalid_input)
```

#### jest_template.ts
```typescript
/**
 * Jest 테스트 템플릿
 *
 * Usage:
 *   cp jest_template.ts src/__tests__/<module>.test.ts
 */
import { functionUnderTest } from '../module';

describe('ModuleName', () => {
  beforeEach(() => {
    // 테스트 전 설정
  });

  afterEach(() => {
    // 테스트 후 정리
  });

  describe('functionUnderTest', () => {
    it('should return expected value when valid input', () => {
      // Given
      const input = 'test';

      // When
      const result = functionUnderTest(input);

      // Then
      expect(result).toBe('expected');
    });

    it('should throw error when invalid input', () => {
      expect(() => functionUnderTest(null)).toThrow('Invalid input');
    });
  });
});
```

**적용 방법**:
```bash
# 템플릿 파일 생성
mkdir -p .claude/skills/tdd-workflow/assets/test-templates
# 위 내용을 각 파일로 저장

# 커밋
git add .claude/skills/tdd-workflow/assets/test-templates/
git commit -m "feat(tdd): Add pytest and jest test templates"
git push
```

---

### 2.3 parallel-agent-orchestration 참조 문서 추가

**파일**: `.claude/skills/parallel-agent-orchestration/references/`
**문제**: 디렉토리는 존재하나 참조 문서 없음
**영향**: 에이전트 그룹 정의 문서화 부족

**권장 추가 파일**: `agent-groups.md`

```markdown
# Agent Groups Reference

병렬 에이전트 오케스트레이션에서 사용하는 에이전트 그룹 정의입니다.

## 1. Dev Group (개발)

| Agent | 역할 | Model |
|-------|------|-------|
| architect | 설계 및 구조 분석 | sonnet |
| coder | 코드 구현 | sonnet |
| tester | 테스트 작성 | sonnet |
| docs | 문서화 | haiku |

**사용 시점**: 새 기능 구현, 리팩토링

## 2. Test Group (테스트)

| Agent | 역할 | Model |
|-------|------|-------|
| unit | 단위 테스트 | haiku |
| integration | 통합 테스트 | sonnet |
| e2e | E2E 테스트 | sonnet |
| security | 보안 테스트 | sonnet |

**사용 시점**: Phase 2 테스트, FINAL_CHECK

## 3. Review Group (리뷰)

| Agent | 역할 | Model |
|-------|------|-------|
| code-reviewer | 코드 리뷰 | sonnet |
| security-auditor | 보안 리뷰 | sonnet |
| architect-reviewer | 아키텍처 리뷰 | opus |

**사용 시점**: Phase 2.5 코드 리뷰, PR 리뷰

## 에이전트 선택 가이드

| 작업 유형 | 권장 그룹 |
|----------|----------|
| 새 기능 | dev |
| 버그 수정 | dev (coder + tester) |
| 테스트 추가 | test |
| PR 생성 전 | review |
| 배포 전 | test + review |
```

---

## 3. 장기 개선 (Low Priority)

### 3.1 Skills 통합 문서 생성

**제안**: 모든 Skills를 한눈에 볼 수 있는 통합 문서 생성

**파일**: `docs/SKILLS_REFERENCE.md`

```markdown
# Skills Reference

## Quick Reference

| Skill | Trigger | Phase | Token |
|-------|---------|-------|-------|
| debugging-workflow | 로그 분석, debug | 1,2,5 | 2500 |
| pre-work-research | 신규 기능, 오픈소스 | 0 | 1800 |
| final-check-automation | E2E, Phase 5 | 5 | 2000 |
| tdd-workflow | TDD, Red-Green | 1,2 | 1200 |
| code-quality-checker | 린트, 품질 검사 | 2,2.5 | 1400 |
| phase-validation | Phase 검증 | 전체 | 1000 |
| parallel-agent-orchestration | 병렬 개발 | 1,2 | 1200 |
| issue-resolution | 이슈 해결 | 1,2 | 1500 |

## Skill Dependencies Graph

[의존성 다이어그램]

## Usage Examples

[각 Skill별 사용 예제]
```

### 3.2 GitHub Actions 테스트 워크플로우 추가

**제안**: PR에서 워크플로우 문법 자동 검증

```yaml
# .github/workflows/validate-workflows.yml
name: Validate Workflows

on:
  pull_request:
    paths:
      - '.github/workflows/*.yml'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate workflow files
        run: |
          for file in .github/workflows/*.yml; do
            echo "Validating $file..."
            yq eval '.' "$file" > /dev/null
          done
```

---

## 4. 적용 체크리스트

### 즉시 (High)
- [x] 해당 없음

### 권장 (Medium)
- [ ] ci.yml permissions 추가
- [ ] tdd-workflow 템플릿 파일 추가
- [ ] parallel-agent-orchestration 참조 문서 추가

### 장기 (Low)
- [ ] Skills 통합 문서 생성
- [ ] GitHub Actions 검증 워크플로우 추가

---

## 5. 참조

- **PR**: https://github.com/garimto81/archive-analyzer/pull/26
- **관련 PRD**: PRD-0025, PRD-0027, PRD-0029
- **검증 보고서**: 병렬 리서치 결과 (2025-12-06)
