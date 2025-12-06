# PRD-0025: 전역 워크플로우 최적화 (Master)

**Version**: 1.0.0 | **Date**: 2025-12-06 | **Status**: Draft

---

## 1. Executive Summary

Claude Code의 전역 지침과 워크플로우를 최적화하여 **토큰 효율성 56% 향상**, **개발 자동화 확대**, **코드 품질 강화**를 달성합니다.

### 핵심 목표

| 목표 | 현재 | 목표 | 개선율 |
|------|------|------|--------|
| 초기 컨텍스트 | ~8000 토큰 | ~3500 토큰 | **-56%** |
| CLAUDE.md | 257줄 | ~150줄 | **-42%** |
| Skills | 2개 | 8개 | +300% |
| PR 리뷰 | 수동 | 자동화 | **-50%** |

### ROI 예측

| 항목 | 연간 절감 |
|------|----------|
| 토큰 비용 | ~$150/년 |
| 개발 시간 | ~200시간/년 |

---

## 2. 하위 PRD 목록

| PRD | 제목 | 우선순위 | 상태 |
|-----|------|----------|------|
| [PRD-0026](./PRD-0026-token-management.md) | 토큰 관리 계획 | P0 | Draft |
| [PRD-0027](./PRD-0027-skills-migration.md) | Skills 마이그레이션 | P0 | Draft |
| [PRD-0028](./PRD-0028-tdd-enhancement.md) | TDD 워크플로우 강화 | P1 | Draft |
| [PRD-0029](./PRD-0029-github-actions.md) | GitHub Actions 통합 | P1 | Draft |

---

## 3. 구현 로드맵

### Phase 1: 기반 구축 (Week 1)
- [ ] PRD-0026: 토큰 예산 모델 확정
- [ ] PRD-0027: `debugging-workflow` Skill 생성
- [ ] MCP 서버 추가 (filesystem, github)

### Phase 2: Skills 마이그레이션 (Week 2-3)
- [ ] PRD-0027: 8개 Skills 생성
- [ ] PRD-0028: TDD 스크립트 구현
- [ ] 기존 Commands deprecated 표시

### Phase 3: 자동화 통합 (Week 3-4)
- [ ] PRD-0029: GitHub Actions 배포
- [ ] CLAUDE.md v4.0.0 리팩토링

### Phase 4: 최적화 (Week 5+)
- [ ] 토큰 모니터링 구현
- [ ] 프롬프트 최적화

---

## 4. 성공 지표

| 지표 | 현재 | 목표 |
|------|------|------|
| 초기 컨텍스트 | ~8000 토큰 | ~3500 토큰 |
| Skills 자동 트리거율 | 0% | 80% |
| PR 리뷰 자동화율 | 0% | 100% |
| TDD Red Phase 준수율 | - | 95% |

---

## 5. 리스크

| 리스크 | 완화 방안 |
|--------|----------|
| Skills 마이그레이션 실패 | Commands 백업 유지 |
| GitHub Actions 비용 초과 | 월별 예산 설정 |
| 토큰 예산 초과 | 경고 임계값 설정 |

---

**Next**: PRD-0026 (토큰 관리) → PRD-0027 (Skills) 순서로 구현
