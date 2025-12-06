# PRD-0027 Tasks: Skills 마이그레이션

**PRD**: [PRD-0027](./prds/PRD-0027-skills-migration.md)
**Priority**: P0
**Status**: Pending

---

## Task List

### Task 0.0: Feature Branch 생성
- [ ] `feature/PRD-0027-skills-migration` 브랜치 생성
- [ ] GitHub Issue 생성

### Phase 1: P0 Skills (Week 1)

#### Task 1: debugging-workflow Skill
- [ ] `init_skill.py debugging-workflow` 실행
- [ ] SKILL.md 작성 (~300줄)
  - DEBUGGING_STRATEGY.md 통합
  - 자동 트리거 키워드 설정
- [ ] `scripts/analyze_logs.py` 구현
- [ ] `scripts/add_debug_logs.py` 구현
- [ ] `references/log-patterns.md` 작성
- **Test**: 자동 트리거 테스트 ("로그 분석" 키워드)

#### Task 2: pre-work-research Skill
- [ ] SKILL.md 작성
- [ ] `scripts/github_search.py` 구현
- [ ] `references/oss-evaluation.md` 작성
- **Test**: 자동 트리거 테스트 ("오픈소스 검색")

#### Task 3: final-check-automation Skill
- [ ] SKILL.md 작성
- [ ] `scripts/run_final_check.py` 구현
- **Test**: E2E 통합 테스트

### Phase 2: P1 Skills (Week 2)

#### Task 4: tdd-workflow Skill
- [ ] SKILL.md 작성
- [ ] `scripts/validate_red_phase.py` 구현
- [ ] `scripts/tdd_auto_cycle.py` 구현
- [ ] `assets/test-templates/` 생성
- **Test**: Red Phase 검증 테스트

#### Task 5: code-quality-checker Skill
- [ ] SKILL.md 작성
- [ ] `scripts/run_quality_check.py` 구현
- **Test**: ruff, black, mypy 통합 테스트

#### Task 6: phase-validation Skill
- [ ] SKILL.md 작성
- [ ] `scripts/validate_phase.py` 구현
- **Test**: Phase 0-6 검증 테스트

### Phase 3: P2 Skills (Week 3)

#### Task 7: parallel-agent-orchestration Skill
- [ ] SKILL.md 작성
- [ ] `references/agent-combinations.md` 작성
- **Test**: 병렬 에이전트 호출 테스트

#### Task 8: issue-resolution Skill
- [ ] SKILL.md 작성
- [ ] `scripts/fix_issue_flow.py` 구현
- **Test**: GitHub 이슈 → PR 플로우 테스트

### Phase 4: Commands Deprecation

#### Task 9: 기존 Commands deprecated 표시
- [ ] `/analyze-logs` → deprecated 경고 추가
- [ ] `/pre-work` → deprecated 경고 추가
- [ ] `/tdd` → deprecated 경고 추가
- [ ] `/check` → deprecated 경고 추가
- **Test**: 경고 메시지 출력 확인

---

## Acceptance Criteria

- [ ] 8개 신규 Skills 생성 완료
- [ ] 자동 트리거율 80% 이상
- [ ] 기존 Commands deprecated 표시 완료

---

## Dependencies

- PRD-0026 (토큰 전략 확정)

## Next

- PRD-0028 (TDD 강화)
- PRD-0029 (GitHub Actions)
