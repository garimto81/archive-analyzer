# Command Selector Guide

**목적**: 시나리오별 최적 커맨드 추천

**버전**: 1.0.0 | **업데이트**: 2025-12-11 | **동기화**: CLAUDE.md v8.0.0

---

## 빠른 선택

### "무엇을 해야 할지 모르겠다"

```
/work "요청 내용"
```

`/work`는 분석 → 이슈 → 구현 → 테스트 → 보고까지 전체 워크플로우를 자동 실행합니다.

---

## 시나리오별 커맨드

### 1. 새 기능 개발

| 상황 | 추천 커맨드 | 설명 |
|------|------------|------|
| 요구사항 불명확 | `/create prd` | PRD 먼저 작성 |
| 요구사항 명확 | `/work "기능 설명"` | 전체 자동화 |
| 대규모 기능 | `/plan` → `/work` | 계획 후 실행 |
| 완전 자동화 | `/work-auto "기능 설명"` | 중간 확인 없이 |

### 2. 버그 수정

| 상황 | 추천 커맨드 | 설명 |
|------|------------|------|
| 이슈 있음 | `/issue fix #N` | 이슈 기반 수정 |
| 이슈 없음 | `/work "버그 설명"` | 이슈 자동 생성 |
| 원인 불명 | `/analyze logs` | 로그 분석 후 |
| 긴급 수정 | `/tdd` | TDD로 빠른 수정 |

### 3. 리팩토링

| 상황 | 추천 커맨드 | 설명 |
|------|------------|------|
| 성능 개선 | `/optimize` → `/work` | 분석 후 개선 |
| 코드 품질 | `/check` → `/work` | 린트 후 수정 |
| 대규모 변경 | `/plan` → `/parallel dev` | 계획 후 병렬 |

### 4. 코드 리뷰

| 상황 | 추천 커맨드 | 설명 |
|------|------------|------|
| PR 리뷰 | `/pr review #N` | PR 분석 |
| 코드 분석 | `/analyze code` | 코드 품질 분석 |
| 병렬 리뷰 | `/parallel review` | 여러 파일 동시 |

### 5. 문서 작업

| 상황 | 추천 커맨드 | 설명 |
|------|------------|------|
| PRD 생성 | `/create prd` | 기획 문서 |
| PR 생성 | `/create pr` | Pull Request |
| 문서 생성 | `/create docs` | 일반 문서 |
| 변경 기록 | `/changelog` | CHANGELOG 추가 |

### 6. 테스트

| 상황 | 추천 커맨드 | 설명 |
|------|------------|------|
| TDD 개발 | `/tdd` | Red-Green-Refactor |
| 전체 검증 | `/check` | 린트 + 테스트 |
| E2E 검증 | `/final-check` | Playwright 테스트 |
| 병렬 테스트 | `/parallel test` | 여러 테스트 동시 |

### 7. 조사/분석

| 상황 | 추천 커맨드 | 설명 |
|------|------------|------|
| 코드베이스 이해 | `/research` | RPI Phase 1 |
| 구현 계획 | `/plan` | RPI Phase 2 |
| 기술 검증 | `/pre-work` | 사전 리서치 |
| 병렬 조사 | `/parallel research` | 여러 주제 동시 |

---

## 워크플로우 조합

### 표준 기능 개발

```
/create prd → /work "PRD 기반 구현" → /commit → /create pr
```

### 대규모 리팩토링

```
/research → /plan → /parallel dev --branch → /parallel check → /create pr
```

### 버그 긴급 수정

```
/issue fix #N → /check → /commit → /create pr
```

### 성능 최적화

```
/optimize → /work "최적화 구현" → /final-check → /create pr
```

---

## 커맨드 의존성

```
/pre-work ──┐
            ├──→ /work ──→ /commit ──→ /create pr
/research ──┘       │
                    ↓
               /tdd, /check, /final-check
```

---

## 병렬 vs 순차

### 병렬 실행 (`/parallel`)

- 독립적인 파일/모듈 작업
- 여러 테스트 동시 실행
- 여러 리뷰 동시 수행

### 순차 실행

- 의존성 있는 작업 (A 결과가 B 입력)
- Phase 간 전환
- 같은 파일 수정

---

## 자동화 레벨

| 레벨 | 커맨드 | 특징 |
|------|--------|------|
| 완전 자동 | `/work-auto` | 최종 보고서만 확인 |
| 반자동 | `/work` | Phase별 확인 가능 |
| 수동 | 개별 커맨드 | 단계별 직접 실행 |

---

## 참조

- [CLAUDE.md](../CLAUDE.md) - 전체 커맨드 목록
- [AGENTS_REFERENCE.md](./AGENTS_REFERENCE.md) - 에이전트 활용
- [WORKFLOW_REFERENCE.md](./WORKFLOW_REFERENCE.md) - 상세 워크플로우

---

**관리**: Claude Code
**업데이트**: 2025-12-11
**버전**: 1.0.0
