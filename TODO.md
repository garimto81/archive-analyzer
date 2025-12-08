# TODO - 점진적 개선 계획

**생성일**: 2025-12-08
**기반**: Backend/Frontend 코드베이스 분석

---

## 완료 항목

### [x] `eval()` 보안 취약점 제거 ✅
- **파일**: `backend/src/services/gcs_streaming.py:367-369`
- **수정 완료**: `fractions.Fraction` 사용으로 안전하게 변경
- **완료일**: 2025-12-08

### [x] CLAUDE.md 업데이트 (v6.0.0) ✅
- 경로 수정: `D:\AI\claude01` → `D:\AI\archive-analyzer`
- 프로젝트 구조 섹션 추가
- 빌드/테스트 명령어 컴포넌트별 분리
- **완료일**: 2025-12-08

---

## 추후 구현 (우선순위 낮음)

> 현재 기능이 정상 동작하므로 필요 시 구현

| 항목 | 비고 |
|------|------|
| Clips 페이지 완성 | GCS 클립 생성은 GCSVideosPage에서 가능 |
| GCSVideosPage 컴포넌트 분리 | 현재 동작에 문제 없음 |
| FastAPI lifespan 마이그레이션 | deprecated 경고만, 기능 정상 |
| OpenAPI → TypeScript 자동 생성 | 수동 타입 동기화로 충분 |
| 에러 바운더리 추가 | 각 페이지에서 처리 중 |
| 상태 관리 라이브러리 도입 | 현재 규모에서 불필요 |
| API 버저닝 | 단일 버전 운영 중 |
| 테스트 커버리지 확대 | 핵심 기능 테스트 완료 |

---

## 관련 이슈

| 이슈 | 상태 | 설명 |
|------|------|------|
| #43 | Open | Docker 서버 배포 + GUI 모니터링 |
| #41 | Open | NAS 경로 변경 실시간 감지 |
| #23 | Open | Archive MAM 병렬 개발 구조 |
