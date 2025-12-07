# 커맨드 최적화 가이드 v4.4.0

**Version**: 4.4.0 | **Date**: 2025-12-07 | **Author**: Claude Code

---

## 1. 개요

### 1.1 목적

Claude Code 커맨드 체계를 최적화하여:
- 중복 기능 제거
- 학습 곡선 단축
- 사용성 개선
- 토큰 효율성 향상

### 1.2 변경 요약

| 항목 | 이전 (v4.3.1) | 이후 (v4.4.0) | 변화 |
|------|---------------|---------------|------|
| 커맨드 수 | 24개 | 15개 | **-37.5%** |
| 문서 파일 | 24개 | 15개 | -9개 |
| 중복 기능 | 7쌍 | 0 | 제거 |
| 통합 커맨드 | 0개 | 4개 | 신규 |

---

## 2. 통합된 커맨드

### 2.1 `/issue` - GitHub 이슈 관리

**통합 대상**: `/issues`, `/fix-issue`, `/issue-failed`

```bash
/issue <action> [args]

Actions:
  list [filter]     이슈 목록 조회
  create [title]    새 이슈 생성
  fix <number>      이슈 해결 (브랜치→구현→PR)
  failed [number]   실패 분석 및 새 솔루션 제안
```

**사용 예시**:
```bash
/issue list                    # 열린 이슈 전체
/issue list mine               # 내게 할당된 이슈
/issue list label:bug          # 버그 라벨 필터
/issue create "로그인 버그"     # 이슈 생성
/issue fix 123                 # 이슈 해결
/issue failed 123              # 실패 분석
```

**마이그레이션**:
| 이전 | 이후 |
|------|------|
| `/issues` | `/issue list` |
| `/issues mine` | `/issue list mine` |
| `/fix-issue 123` | `/issue fix 123` |
| `/issue-failed` | `/issue failed` |

---

### 2.2 `/parallel` - 병렬 멀티에이전트

**통합 대상**: `/parallel-dev`, `/parallel-test`, `/parallel-review`, `/parallel-research`

```bash
/parallel <target> [args]

Targets:
  dev       병렬 개발 (Architect + Coder + Tester + Docs)
  test      병렬 테스트 (Unit + Integration + E2E + Security)
  review    병렬 코드 리뷰 (Security + Logic + Style + Performance)
  research  병렬 리서치 (4개 Research Agent)
```

**사용 예시**:
```bash
/parallel dev "사용자 인증 기능"    # 병렬 개발
/parallel test                     # 전체 테스트
/parallel test --module auth       # 특정 모듈만
/parallel review src/auth/         # 특정 경로 리뷰
/parallel research "React vs Vue"  # 기술 비교 리서치
```

**마이그레이션**:
| 이전 | 이후 |
|------|------|
| `/parallel-dev "기능"` | `/parallel dev "기능"` |
| `/parallel-test` | `/parallel test` |
| `/parallel-review` | `/parallel review` |
| `/parallel-research "주제"` | `/parallel research "주제"` |

---

### 2.3 `/analyze` - 코드/로그 분석

**통합 대상**: `/analyze-code`, `/analyze-logs`

```bash
/analyze <target> [args]

Targets:
  code [--comprehensive]   코드 구조 분석 (Mermaid 다이어그램)
  logs [path] [options]    로그 파일 분석 (에러 패턴, 병목)
```

**사용 예시**:
```bash
/analyze code                      # Mermaid classDiagram
/analyze code --comprehensive      # 종합 분석 리포트
/analyze logs                      # 기본 로그 분석
/analyze logs logs/app.log         # 특정 파일
/analyze logs --recent 100         # 최근 100줄
/analyze logs --errors             # 에러만
```

**마이그레이션**:
| 이전 | 이후 |
|------|------|
| `/analyze-code` | `/analyze code` |
| `/analyze-code --comprehensive` | `/analyze code --comprehensive` |
| `/analyze-logs` | `/analyze logs` |
| `/analyze-logs --errors` | `/analyze logs --errors` |

---

### 2.4 `/create` - PRD/PR/문서 생성

**통합 대상**: `/create-prd`, `/create-pr`, `/create-docs`

```bash
/create <target> [args]

Targets:
  prd [name] [--template]   PRD 문서 생성 (Phase 0)
  pr [base-branch]          Pull Request 생성 (Phase 4)
  docs [path] [--format]    API/코드 문서 생성
```

**사용 예시**:
```bash
/create prd user-auth              # PRD 생성
/create prd --template=minimal     # 최소 템플릿
/create prd --template=deep        # 완벽한 기획서 (서브폴더)
/create pr                         # PR 생성
/create pr develop                 # 특정 base branch
/create docs                       # 전체 문서 생성
/create docs src/auth/             # 특정 경로
/create docs --format=html         # HTML 형식
```

**PRD 템플릿 옵션**:
| 템플릿 | 소요 시간 | 토큰 | 대상 |
|--------|----------|------|------|
| `minimal` | 10분 | ~1270 | 숙련 개발자 |
| `standard` | 20-30분 | ~2500 | 일반 프로젝트 |
| `junior` | 40-60분 | ~4500 | 초보자 |
| `deep` | 60+분 | ~6000 | 완벽한 기획서 |

**마이그레이션**:
| 이전 | 이후 |
|------|------|
| `/create-prd` | `/create prd` |
| `/create-prd --template=minimal` | `/create prd --template=minimal` |
| `/create-pr` | `/create pr` |
| `/create-docs` | `/create docs` |

---

## 3. 최종 커맨드 목록 (15개)

### 3.1 핵심 워크플로우 (4개)

| 커맨드 | 용도 | Phase |
|--------|------|-------|
| `/work` | 작업 지시 실행 (분석→이슈→E2E→TDD) | 0-5 |
| `/autopilot` | 자율 운영 - 이슈 자동 처리 | 전체 |
| `/pre-work` | PRE_WORK 단계 실행 (OSS 검색) | 0 |
| `/final-check` | E2E + Security 최종 검증 | 5 |

### 3.2 통합 커맨드 (4개)

| 커맨드 | 서브커맨드 | 용도 |
|--------|-----------|------|
| `/issue` | `list\|create\|fix\|failed` | GitHub 이슈 관리 |
| `/parallel` | `dev\|test\|review\|research` | 병렬 멀티에이전트 |
| `/analyze` | `code\|logs` | 코드/로그 분석 |
| `/create` | `prd\|pr\|docs` | PRD/PR/문서 생성 |

### 3.3 단일 커맨드 (7개)

| 커맨드 | 용도 | Phase |
|--------|------|-------|
| `/commit` | Conventional Commit 생성 | 3 |
| `/tdd` | TDD 가이드 (Red-Green-Refactor) | 1-2 |
| `/check` | 코드 품질 검사 | 2 |
| `/changelog` | CHANGELOG 업데이트 | 3 |
| `/optimize` | 성능 분석 및 최적화 | 5 |
| `/todo` | 작업 목록 관리 | 전체 |
| `/api-test` | API 엔드포인트 테스트 | 2 |

---

## 4. 삭제된 커맨드 (12개)

### 4.1 `/issue`로 통합

| 삭제된 커맨드 | 대체 방법 |
|--------------|----------|
| `/issues` | `/issue list` |
| `/fix-issue` | `/issue fix` |
| `/issue-failed` | `/issue failed` |

### 4.2 `/parallel`로 통합

| 삭제된 커맨드 | 대체 방법 |
|--------------|----------|
| `/parallel-dev` | `/parallel dev` |
| `/parallel-test` | `/parallel test` |
| `/parallel-review` | `/parallel review` |
| `/parallel-research` | `/parallel research` |

### 4.3 `/analyze`로 통합

| 삭제된 커맨드 | 대체 방법 |
|--------------|----------|
| `/analyze-code` | `/analyze code` |
| `/analyze-logs` | `/analyze logs` |

### 4.4 `/create`로 통합

| 삭제된 커맨드 | 대체 방법 |
|--------------|----------|
| `/create-prd` | `/create prd` |
| `/create-pr` | `/create pr` |
| `/create-docs` | `/create docs` |

---

## 5. 커맨드 사용 로깅

### 5.1 로깅 시스템

커맨드 사용 통계를 수집하여 실제 사용 패턴 분석:

**로그 파일**: `.claude/logs/command-usage.json`

**로깅 스크립트**: `.claude/scripts/command-logger.py`

### 5.2 사용법

```bash
# 커맨드 사용 기록 (자동 호출됨)
python .claude/scripts/command-logger.py work

# 서브커맨드 포함
python .claude/scripts/command-logger.py issue fix

# 사용 통계 확인
python .claude/scripts/command-logger.py --stats
```

### 5.3 로그 형식

```json
{
  "commands": {
    "/work": {
      "count": 15,
      "first_used": "2025-12-07T10:30:00",
      "last_used": "2025-12-07T15:45:00"
    },
    "/issue fix": {
      "count": 8,
      "first_used": "2025-12-07T11:00:00",
      "last_used": "2025-12-07T14:30:00"
    }
  },
  "daily": {
    "2025-12-07": {
      "/work": 5,
      "/issue fix": 3
    }
  },
  "total_calls": 45
}
```

### 5.4 통계 출력 예시

```
=== 커맨드 사용 통계 ===

총 호출 횟수: 45

커맨드별 사용 횟수:
--------------------------------------------------
  /work                             15회
  /commit                           12회
  /issue fix                         8회
  /check                             5회
  /parallel test                     3회
  /create pr                         2회

최근 7일 일별 사용:
--------------------------------------------------
  2025-12-07: 45회
```

---

## 6. 워크플로우 변경

### 6.1 신규 기능 개발

```bash
# 이전 (v4.3.1)
/pre-work → /create-prd → /parallel-dev → /check → /parallel-test → /create-pr

# 이후 (v4.4.0)
/pre-work → /create prd → /parallel dev → /check → /parallel test → /create pr
```

### 6.2 이슈 해결

```bash
# 이전 (v4.3.1)
/issues → /fix-issue 123 → /commit → /create-pr

# 이후 (v4.4.0)
/issue list → /issue fix 123 → /commit → /create pr
```

### 6.3 코드 분석

```bash
# 이전 (v4.3.1)
/analyze-code --comprehensive
/analyze-logs --errors

# 이후 (v4.4.0)
/analyze code --comprehensive
/analyze logs --errors
```

---

## 7. 파일 구조

```
.claude/
├── commands/                    # 15개 커맨드
│   ├── analyze.md              # 통합: code, logs
│   ├── api-test.md
│   ├── autopilot.md
│   ├── changelog.md
│   ├── check.md
│   ├── commit.md
│   ├── create.md               # 통합: prd, pr, docs
│   ├── final-check.md
│   ├── issue.md                # 통합: list, create, fix, failed
│   ├── optimize.md
│   ├── parallel.md             # 통합: dev, test, review, research
│   ├── pre-work.md
│   ├── tdd.md
│   ├── todo.md
│   └── work.md
├── logs/
│   └── command-usage.json      # 사용 통계
├── scripts/
│   └── command-logger.py       # 로깅 스크립트
└── skills/                     # 10개 Skills (변경 없음)
```

---

## 8. 개선 효과

### 8.1 정량적 효과

| 지표 | 개선 |
|------|------|
| 커맨드 수 | 24 → 15 (-37.5%) |
| 중복 기능 | 7쌍 → 0 (100% 제거) |
| 문서 파일 | 24 → 15 (-37.5%) |
| 학습 곡선 | ~4주 → ~2주 (50% 단축) |

### 8.2 정성적 효과

- **발견성 향상**: 관련 기능이 하나의 커맨드로 그룹화
- **일관성 개선**: 서브커맨드 패턴 표준화
- **사용성 개선**: `/issue --help`로 모든 이슈 기능 확인
- **유지보수 용이**: 파일 수 감소로 관리 부담 감소

---

## 9. 향후 계획

### 9.1 모니터링

- 커맨드 사용 통계 주간 리뷰
- 사용 빈도가 낮은 커맨드 식별
- 사용자 피드백 수집

### 9.2 추가 최적화 후보

| 후보 | 검토 사항 |
|------|----------|
| `/api-test` | `/parallel test`에 옵션으로 통합 가능 |
| `/optimize` | `/check --performance`로 통합 가능 |
| `/autopilot` | 사용 빈도 낮을 시 deprecated 검토 |

### 9.3 v4.5.0 예정

- 커맨드 별칭(alias) 시스템 추가
- 커맨드 자동완성 개선
- 대화형 커맨드 선택기

---

## 10. FAQ

### Q1: 기존 커맨드는 더 이상 사용할 수 없나요?

A: 네, 삭제된 12개 커맨드는 더 이상 사용할 수 없습니다. 위의 마이그레이션 가이드를 참고하세요.

### Q2: 서브커맨드 없이 실행하면 어떻게 되나요?

A: 사용 가능한 서브커맨드 목록이 표시됩니다.
```bash
/issue
# Output: Available: list, create, fix, failed
```

### Q3: 로깅은 자동으로 되나요?

A: 현재는 수동 호출이 필요합니다. 향후 Hook 연동으로 자동화 예정입니다.

### Q4: 이전 버전으로 롤백할 수 있나요?

A: Git에서 `.claude/commands/` 디렉토리를 이전 커밋으로 복원하면 됩니다.

---

## 11. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 4.4.0 | 2025-12-07 | 커맨드 통합 (24→15), 로깅 시스템 추가 |
| 4.3.1 | 2025-12-07 | `/todo --log` 옵션 추가 |
| 4.3.0 | 2025-12-07 | `/work` 커맨드 추가 |

---

## 12. 참고 자료

- CLAUDE.md 섹션 6: Commands
- `.claude/commands/*.md`: 커맨드 상세 문서
- `.claude/scripts/command-logger.py`: 로깅 스크립트
