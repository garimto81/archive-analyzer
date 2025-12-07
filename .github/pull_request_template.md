# Pull Request

## 📋 Summary

<!-- PR의 목적과 주요 변경사항을 간략히 설명해주세요 -->

**Phase**: <!-- Phase 1-6 중 해당하는 번호 -->
**PRD**: <!-- PRD-0001 형식 -->
**Version**: <!-- v1.2.3 형식 -->

---

## 🛤️ 여정 (Journey)

<!-- 세션 작업 흐름 (/journey export로 자동 생성) -->

### 작업 흐름
<!--
1. HH:MM - 작업 시작 (context: N%)
2. HH:MM - 주요 마일스톤
-->

### 주요 결정
<!--
- **선택 1**: A 선택 (이유: ...)
-->

### 참고사항
<!-- 장애물, 특이사항 등 -->

---

## 🔄 Changes

<!-- 주요 변경사항을 나열해주세요 -->

-
-
-

---

## 📝 Related Documents

<!-- 관련 문서 링크 (자동 생성 시 채워짐) -->

- [ ] PRD: `tasks/prds/NNNN-prd-*.md`
- [ ] Task List: `tasks/NNNN-tasks-*.md`
- [ ] Design Doc (있는 경우)

---

## ✅ Checklist

### 코드 품질
- [ ] 코드 구현 완료
- [ ] 주석 및 문서화 완료
- [ ] 린트 에러 없음
- [ ] 타입 에러 없음 (TypeScript)

### 테스트
- [ ] 단위 테스트 작성
- [ ] 통합 테스트 작성 (필요 시)
- [ ] E2E 테스트 통과 (Playwright)
- [ ] 모든 테스트 통과 확인

### 문서
- [ ] README 업데이트 (필요 시)
- [ ] CHANGELOG 업데이트 (필요 시)
- [ ] API 문서 업데이트 (필요 시)

### 보안
- [ ] 환경 변수 사용 (.env)
- [ ] 민감 정보 하드코딩 없음
- [ ] SQL Injection 방지
- [ ] XSS 방지
- [ ] CSRF 방지 (웹 앱)

### Phase 별 체크리스트

#### Phase 1: 코드 작성
- [ ] PRD 요구사항 구현 완료
- [ ] 코드 주석 및 문서화
- [ ] 에러 핸들링 구현

#### Phase 2: 테스트
- [ ] 테스트 코드 작성
- [ ] 테스트 커버리지 확인
- [ ] 엣지 케이스 테스트

#### Phase 3: 버전 관리
- [ ] 버전 번호 업데이트
- [ ] CHANGELOG 작성
- [ ] README 업데이트

#### Phase 4: Git
- [ ] 커밋 메시지 규칙 준수
- [ ] PRD 참조 포함 [PRD-NNNN]
- [ ] 버전 태그 (vX.Y.Z)

#### Phase 5: 검증
- [ ] Playwright E2E 테스트 통과
- [ ] 실제 환경에서 작동 확인
- [ ] 성능 테스트 (필요 시)

#### Phase 6: 캐시 및 배포
- [ ] 브라우저 캐시 처리
- [ ] CDN 캐시 무효화 (필요 시)
- [ ] 배포 준비 완료

---

## 🧪 Testing

### 테스트 방법

<!-- 로컬에서 테스트하는 방법을 설명해주세요 -->

```bash
# Python
pytest tests/ -v --cov=src

# Node.js
npm test

# E2E
npx playwright test
```

### 테스트 결과

<!-- 테스트 실행 결과 또는 스크린샷 첨부 -->

```
# 테스트 결과 붙여넣기
```

---

## 📸 Screenshots (선택사항)

<!-- UI 변경 시 Before/After 스크린샷 첨부 -->

### Before
<!-- 변경 전 -->

### After
<!-- 변경 후 -->

---

## 🔗 References

<!-- 관련 이슈, PR, 외부 문서 링크 -->

- Issue: #
- Related PR: #
- External docs:

---

## 🤖 Auto-generated Information

<!-- 자동 생성된 정보 (수동 수정 불필요) -->

**Branch**: `feature/PRD-NNNN-*`
**Base**: `master`
**Auto-merge**: Enabled (테스트 통과 시 자동 머지)

---

## 📌 Notes

<!-- 추가 설명이나 주의사항 -->

---

**Generated with**: [Claude Code](https://claude.com/claude-code)
