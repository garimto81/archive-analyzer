# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Version**: 5.0.0 | **Context**: Windows, PowerShell, Root: `D:\AI\claude01`

---

## 기본 규칙

| 규칙 | 내용 |
|------|------|
| **언어** | 한글 출력. 기술 용어(code, GitHub)는 영어 |
| **경로** | 절대 경로만. `D:\AI\claude01\...` |
| **충돌** | 지침 충돌 시 → **사용자에게 질문** (임의 판단 금지) |

---

## 출력 스타일

**코드 수정**: 내용 보여주지 않음. 요약만.

```
✅ 파일: src/auth.py (+15/-3)
   - 토큰 검증 로직 추가
   - 만료 시간 체크
```

**응답 구조**: 논리 중심

```
1. 문제/목표 (무엇을)
2. 접근법 (어떻게)
3. 결과 (완료/다음 단계)
```

---

## 작업 방법

```
사용자 요청 → /work "요청 내용" → 자동 완료
```

| 요청 유형 | 처리 |
|-----------|------|
| 기능/리팩토링 | `/work` → 이슈 → 브랜치 → TDD → PR |
| 버그 수정 | `/issue fix #N` |
| 문서 수정 | 직접 수정 (브랜치 불필요) |
| 질문 | 직접 응답 |

---

## 핵심 규칙 (Hook 강제)

| 규칙 | 위반 시 | 해결 |
|------|---------|------|
| main 브랜치 수정 금지 | **차단** | `git checkout -b feat/issue-N-desc` |
| 테스트 먼저 (TDD) | 경고 | Red → Green → Refactor |
| 상대 경로 금지 | 경고 | 절대 경로 사용 |

---

## 문제 해결

```
문제 → WHY(원인) → WHERE(영향 범위) → HOW(해결) → 수정
```

**즉시 수정 금지.** 원인 파악 → 유사 패턴 검색 → 구조적 해결.

---

## 커맨드

| 커맨드 | 용도 |
|--------|------|
| `/work "내용"` | 전체 워크플로우 |
| `/issue fix #N` | 이슈 해결 |
| `/issue create` | 이슈 생성 |
| `/commit` | 커밋 |
| `/tdd` | TDD 워크플로우 |
| `/check` | 린트 + 테스트 |
| `/parallel dev` | 병렬 개발 |

전체: `.claude/commands/`

---

## 빌드 & 테스트

```powershell
pytest tests/test_file.py -v          # 단일 테스트
ruff check src/ && black --check src/ # 린트
npx playwright test                   # E2E
```

---

## 안전 규칙

### Crash Prevention (필수)

```powershell
# ❌ 금지 (120초 초과 → 크래시)
pytest tests/ -v --cov                # 대규모 테스트
npm install && npm run build          # 체인 명령

# ✅ 권장
pytest tests/test_a.py -v             # 개별 실행
# 또는 run_in_background: true
```

### 보호 대상

- `pokervod.db` 스키마 변경 금지 (`qwen_hand_analysis` 소유)

---

## 참조

| 문서 | 용도 |
|------|------|
| `docs/WORKFLOW_REFERENCE.md` | 상세 워크플로우 |
| `docs/AGENTS_REFERENCE.md` | 에이전트 목록 |
| `.claude/commands/` | 커맨드 상세 |
| `.claude/skills/` | 스킬 (자동 트리거) |

---

## 서브프로젝트

```powershell
cd D:\AI\claude01\archive-analyzer
pip install -e ".[dev]" && pytest tests/ -v
```

상세: `archive-analyzer/CLAUDE.md`
