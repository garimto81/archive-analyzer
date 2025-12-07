# API 테스트 (/api-test)

REST/GraphQL API 엔드포인트를 체계적으로 테스트합니다.

## Usage

```
/api-test [endpoint-path]
/api-test /api/users
/api-test --all
```

## 연동 에이전트

| 영역 | 에이전트 | 역할 |
|------|----------|------|
| API 설계 | `backend-architect` | 엔드포인트 검증 |
| 스키마 검증 | `graphql-architect` | GraphQL 테스트 |
| 보안 검사 | `security-auditor` | API 보안 테스트 |

## 테스트 유형

### 1. 기본 테스트

```bash
# REST API 테스트
curl -X GET http://localhost:3000/api/users
curl -X POST http://localhost:3000/api/users -d '{"name":"test"}'

# GraphQL 테스트
curl -X POST http://localhost:3000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ users { id name } }"}'
```

### 2. 자동화된 테스트

**Python (pytest + requests)**:
```python
import pytest
import requests

def test_get_users():
    response = requests.get("http://localhost:3000/api/users")
    assert response.status_code == 200
    assert "users" in response.json()
```

**Node.js (Jest + supertest)**:
```javascript
const request = require('supertest');
const app = require('../app');

test('GET /api/users', async () => {
  const res = await request(app).get('/api/users');
  expect(res.statusCode).toBe(200);
});
```

### 3. 테스트 항목

| 카테고리 | 검사 항목 |
|----------|-----------|
| **상태 코드** | 200, 201, 400, 401, 404, 500 |
| **응답 형식** | JSON 구조, 필수 필드 |
| **인증** | 토큰 검증, 권한 확인 |
| **입력 검증** | 필수 파라미터, 타입 체크 |
| **에러 처리** | 에러 메시지, 에러 코드 |
| **성능** | 응답 시간 < 200ms |

## 테스트 보고서

```markdown
## API 테스트 결과

### 요약
- **총 엔드포인트**: 15개
- **테스트 통과**: 14개 ✅
- **테스트 실패**: 1개 ❌
- **커버리지**: 93%

### 상세 결과

| 엔드포인트 | 메서드 | 상태 | 응답 시간 |
|------------|--------|------|-----------|
| /api/users | GET | ✅ | 45ms |
| /api/users | POST | ✅ | 120ms |
| /api/users/:id | GET | ✅ | 38ms |
| /api/auth/login | POST | ❌ | 350ms |

### 실패 상세

#### /api/auth/login (POST)
- **기대**: 200 OK
- **실제**: 500 Internal Server Error
- **원인**: DB 연결 타임아웃
- **권장 조치**: 연결 풀 크기 증가
```

## 보안 테스트 포함

```bash
# SQL Injection 테스트
curl "/api/users?id=1' OR '1'='1"

# XSS 테스트
curl "/api/users?name=<script>alert(1)</script>"

# 인증 우회 테스트
curl "/api/admin" -H "Authorization: Bearer invalid"
```

## 관련 커맨드

| 커맨드 | 역할 | 차이점 |
|--------|------|--------|
| `/api-test` | API 전용 테스트 | HTTP 엔드포인트 검증 |
| `/parallel-test` | 전체 테스트 | Unit + Integration + E2E |
| `/final-check` | 최종 검증 | E2E + 보고서 |
| `/check` | 코드 품질 | 정적 분석 |
