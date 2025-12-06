# PRD-0026 Tasks: 토큰 관리 계획

**PRD**: [PRD-0026](./prds/PRD-0026-token-management.md)
**Priority**: P0
**Status**: In Progress

---

## Task List

### Task 0.0: Feature Branch 생성
- [ ] `feature/PRD-0026-token-management` 브랜치 생성
- [ ] GitHub Issue 생성

### Task 1: CLAUDE.md v4.0.0 초안 작성
- [ ] 현재 257줄 → 150줄 목표
- [ ] Skills Index 섹션 추가
- [ ] 외부 참조로 대체할 섹션 식별
- **Test**: `wc -l CLAUDE.md` → 150줄 이하

### Task 2: 외부 참조 문서 정리
- [ ] Phase Pipeline 상세 → `docs/PHASE_VALIDATION_GUIDE.md`
- [ ] Agents 목록 → `docs/AGENTS_REFERENCE.md` (완료)
- [ ] Browser Testing → Skills 참조
- **Test**: 모든 외부 링크 유효성 검증

### Task 3: 토큰 모니터링 스크립트 (선택)
- [ ] `scripts/token_monitor.py` 생성
- [ ] 세션별 토큰 사용량 추적
- [ ] 경고 임계값 설정 (25K/30K)
- **Test**: 스크립트 실행 테스트

---

## Acceptance Criteria

- [ ] CLAUDE.md 150줄 이하
- [ ] 모든 외부 참조 링크 유효
- [ ] 토큰 예산 모델 문서화 완료

---

## Dependencies

- 없음 (독립 실행 가능)

## Next

- PRD-0027 (Skills 마이그레이션)
