---
name: compact
description: 컨텍스트 압축 및 세션 요약 저장
---

# /compact - Intentional Compaction

컨텍스트 사용량이 높을 때 의도적으로 압축하여 성능을 유지합니다.

## Usage

```
/compact [subcommand]

Subcommands:
  now       현재 세션 즉시 압축
  save      압축 결과를 파일로 저장
  load      저장된 압축 로드
  status    현재 컨텍스트 상태 확인
```

---

## Context Engineering 임계값

| 사용량 | 상태 | 권장 조치 |
|--------|------|-----------|
| 0-40% | 🟢 Safe | 정상 작업 |
| 40-60% | 🟡 DUMB | 주의 - 성능 저하 시작 |
| 60-80% | 🟠 COMPRESS | `/compact now` 권장 |
| 80%+ | 🚨 CRITICAL | 즉시 `/compact now` |

---

## /compact now

현재 세션을 압축합니다.

```bash
/compact now
# Output:
# 🗜️ Compacting session...
# - 이전 컨텍스트: 65%
# - 현재 컨텍스트: 15%
# - 압축률: 77%
# ✅ 압축 완료
```

### 압축 대상

| 항목 | 압축 방법 |
|------|----------|
| 완료된 태스크 | 요약으로 대체 |
| 탐색된 파일 | 경로만 보존 |
| 에러 로그 | 핵심 메시지만 |
| 서브에이전트 결과 | 요약으로 대체 |

### 보존 항목

| 항목 | 이유 |
|------|------|
| 현재 진행 중 태스크 | 작업 연속성 |
| 핵심 의사결정 | 일관성 유지 |
| 미해결 이슈 | 추적 필요 |

---

## /compact save

압축 결과를 파일로 저장합니다.

```bash
/compact save
# Output: 저장됨 → .claude/compacts/2025-12-07-session.md
```

### 저장 형식

```markdown
# Session Compact: 2025-12-07

## 작업 요약
- Issue #30 구현 완료
- 3개 파일 생성, 1개 수정

## 핵심 결정
- 여정 섹션을 PR 템플릿 상단에 배치

## 미해결 사항
- 없음

## 파일 변경
- .claude/commands/journey.md (신규)
- .github/pull_request_template.md (수정)

## 컨텍스트
- 시작: 12%
- 최대: 65%
- 압축 후: 15%
```

---

## /compact load

저장된 압축을 로드합니다.

```bash
/compact load 2025-12-07
# Output: 세션 컨텍스트 로드됨
```

---

## /compact status

현재 컨텍스트 상태를 확인합니다.

```bash
/compact status
# Output:
# 🧠 Context Status
# ├── 사용량: 45% (DUMB ZONE)
# ├── 토큰: ~90,000 / 200,000
# ├── 세션 시간: 25분
# └── 권장: 40분 후 /compact now
```

---

## 자동 트리거

상태줄에서 경고 표시:

| 표시 | 의미 |
|------|------|
| `🟡 45% DUMB` | Dumb Zone 진입 |
| `🟠 65% COMPRESS` | 압축 권장 |
| `🚨 85% CRITICAL` | 즉시 압축 필요 |

---

## 저장 위치

```
.claude/
└── compacts/
    ├── 2025-12-07-session.md
    ├── 2025-12-06-session.md
    └── ...
```

---

## Best Practices

1. **40% 도달 시**: 현재 태스크 완료 후 압축 계획
2. **60% 도달 시**: 현재 태스크 완료 즉시 압축
3. **80% 도달 시**: 즉시 압축 (작업 중단 감수)
4. **세션 종료 시**: `/compact save`로 기록 보존

---

## Related

- `/journey` - 세션 여정 관리
- `/todo` - 작업 목록
- 상태줄 - 실시간 컨텍스트 모니터링
