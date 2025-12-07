---
name: issue
description: GitHub issue lifecycle management (list, create, fix, failed)
---

# /issue - GitHub Issue 통합 관리

이슈의 전체 생명주기를 관리합니다: 조회, 생성, 해결, 실패 분석

## Usage

```
/issue <action> [args]

Actions:
  list [filter]     이슈 목록 조회
  create [title]    새 이슈 생성
  fix <number>      이슈 해결 (브랜치→구현→PR)
  failed [number]   실패 분석 및 새 솔루션 제안
```

---

## /issue list - 이슈 조회

```bash
/issue list              # 열린 이슈 전체
/issue list mine         # 내게 할당된 이슈
/issue list open         # 열린 이슈
/issue list closed       # 닫힌 이슈
/issue list label:bug    # 라벨별 필터
/issue list 123          # 특정 이슈 상세
```

### 실행 명령어

```bash
gh issue list                      # 기본
gh issue list --assignee @me       # 내 이슈
gh issue list --label bug          # 라벨 필터
gh issue view <number>             # 상세 보기
gh issue view <number> --comments  # 코멘트 포함
```

### 출력 형식

```
📋 Open Issues (5)

#123 [bug] Login timeout on slow connections
     Labels: bug, high-priority
     Assignee: @user
     Created: 2025-01-15

#124 [feature] Add OAuth2 support
     Labels: enhancement
     Created: 2025-01-16
```

---

## /issue create - 이슈 생성

```bash
/issue create "로그인 타임아웃 버그"
/issue create "새 기능 요청" --labels=enhancement
```

### 입력 정보

1. **제목**: 간결한 이슈 제목
2. **유형**: bug | feature | docs | refactor
3. **설명**: 상세 설명 (재현 방법, 기대 동작 등)
4. **라벨**: 자동 추천 (유형 기반)

### 이슈 템플릿

**Bug Report**:
```markdown
## 버그 설명
[문제 상황]

## 재현 방법
1.
2.

## 기대 동작
[예상되는 정상 동작]

## 실제 동작
[현재 발생하는 문제]
```

**Feature Request**:
```markdown
## 기능 설명
[구현하고자 하는 기능]

## 배경/동기
[왜 이 기능이 필요한지]

## 제안 구현 방식
[구현 방법 아이디어]
```

### 실행 명령어

```bash
gh issue create --title "[제목]" --body "[본문]" --label "[라벨]"
gh issue create --title "[제목]" --assignee @me
```

---

## /issue fix - 이슈 해결

```bash
/issue fix 123
/issue fix 123 --skip-pre-work
```

### Workflow

1. **Fetch Issue**
   ```bash
   gh issue view <number>
   ```
   - 이슈 설명 읽기
   - 요구사항 추출
   - 라벨/마일스톤 확인

2. **Analyze Context**
   - 관련 코드 리뷰
   - 유사 이슈 확인
   - 근본 원인 파악

3. **Create Branch**
   ```bash
   git checkout -b fix/issue-<number>-<description>
   ```

4. **Implement Fix**
   - Phase 0-6 워크플로우 따름
   - 테스트 작성 (Phase 2)
   - 문서 업데이트

5. **Create PR**
   - `Fixes #<number>` 참조
   - GitHub 자동 연결

### Phase Integration

| Phase | 역할 |
|-------|------|
| 0 | Issue description = PRD |
| 1 | Fix implementation |
| 2 | Test verification |
| 4 | Auto-reference issue in PR |

### 연동 에이전트

| 단계 | 에이전트 | 역할 |
|------|----------|------|
| 원인 분석 | `debugger` | 근본 원인 파악 |
| 코드 수정 | `code-reviewer` | 코드 품질 확인 |
| 테스트 | `test-automator` | 테스트 작성 |

---

## /issue failed - 실패 분석

```bash
/issue failed 123
/issue failed      # 대화형으로 정보 수집
```

이전 해결 시도가 실패한 경우 분석 및 새 솔루션 제안

### 입력 정보 수집

1. **이슈 번호/제목**: 기존 이슈 식별
2. **시도한 솔루션**: 어떤 해결책을 시도했는지
3. **실패 증상**: 에러 메시지, 예상과 다른 동작
4. **환경 정보**: OS, 버전, 설정

### 분석 보고서 형식

```markdown
## 시도한 솔루션: [솔루션명]

**시도 일시**: YYYY-MM-DD
**수행한 작업**:
1. [작업 1]
2. [작업 2]

**변경된 파일**:
- `path/to/file.ts`: [변경 내용]

## 실패 분석

**증상**: [관찰된 문제점]
**1차 원인**: [직접적 원인]
**근본 원인**: [underlying 문제]

## 새로운 솔루션 제안

### 솔루션 A: [수정된 접근법]
**변경점**: 이전 시도 대비 무엇이 다른지
**예상 성공률**: 높음 | 중간 | 낮음

### 솔루션 B: [대안적 접근법]
**접근 방식**: 완전히 다른 방향
```

### GitHub 업데이트

```bash
gh issue comment <number> --body "## 해결 시도 실패 보고..."
gh issue edit <number> --add-label "blocked,needs-investigation"
```

---

## 워크플로우 예시

```bash
# 1. 이슈 목록 확인
/issue list

# 2. 특정 이슈 상세 확인
/issue list 123

# 3. 이슈 작업 시작
/issue fix 123

# 4. (실패 시) 분석
/issue failed 123

# 5. PR 생성 (자동)
# → /create pr
```

---

## Related

- `/create pr` - PR 생성
- `/commit` - 커밋 생성
- `scripts/github-issue-dev.ps1`
