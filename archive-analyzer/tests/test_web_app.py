"""Web App 테스트 (Issue #43)

FastAPI 기반 모니터링 대시보드 테스트입니다.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """헬스 체크 엔드포인트 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트 생성"""
        from archive_analyzer.web.app import app
        return TestClient(app)

    def test_health_returns_200(self, client):
        """헬스 엔드포인트가 200을 반환"""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_status_field(self, client):
        """헬스 엔드포인트가 status 필드 반환"""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        # healthy 또는 unhealthy 중 하나
        assert data["status"] in ("healthy", "unhealthy")


class TestAPIStatusEndpoint:
    """API 상태 엔드포인트 테스트"""

    @pytest.fixture
    def client(self):
        from archive_analyzer.web.app import app
        return TestClient(app)

    def test_status_returns_200(self, client):
        """/api/status가 200을 반환"""
        response = client.get("/api/status")
        assert response.status_code == 200

    def test_status_contains_running_info(self, client):
        """/api/status가 실행 상태 정보 포함"""
        response = client.get("/api/status")
        data = response.json()
        # is_running 또는 config 정보 확인
        assert "is_running" in data or "config" in data


class TestAPIStatsEndpoint:
    """API 통계 엔드포인트 테스트"""

    @pytest.fixture
    def client(self):
        from archive_analyzer.web.app import app
        return TestClient(app)

    def test_stats_returns_200(self, client):
        """/api/stats가 200을 반환"""
        response = client.get("/api/stats")
        assert response.status_code == 200

    def test_stats_returns_dict(self, client):
        """/api/stats가 딕셔너리 반환"""
        response = client.get("/api/stats")
        data = response.json()
        assert isinstance(data, dict)
        # archive 또는 pokervod 키 확인
        assert "archive" in data or "pokervod" in data or len(data) > 0


class TestAPISyncEndpoint:
    """동기화 API 엔드포인트 테스트"""

    @pytest.fixture
    def client(self):
        from archive_analyzer.web.app import app
        return TestClient(app)

    def test_sync_endpoint_exists(self, client):
        """/api/sync 엔드포인트 존재 확인"""
        response = client.post("/api/sync")
        # 405 Method Not Allowed가 아니면 엔드포인트 존재
        assert response.status_code != 405


class TestAPILogsEndpoint:
    """로그 API 엔드포인트 테스트"""

    @pytest.fixture
    def client(self):
        from archive_analyzer.web.app import app
        return TestClient(app)

    def test_logs_endpoint_exists(self, client):
        """/api/logs 엔드포인트 존재 확인"""
        response = client.get("/api/logs")
        # 404가 아니면 엔드포인트 존재
        assert response.status_code != 404


# =============================================================================
# Issue #45: 1:1 매칭 API 테스트
# =============================================================================


class TestAPIMatchingEndpoint:
    """1:1 매칭 API 엔드포인트 테스트 (Issue #45)"""

    @pytest.fixture
    def client(self):
        from archive_analyzer.web.app import app
        return TestClient(app)

    def test_matching_endpoint_returns_200(self, client):
        """/api/matching이 200을 반환"""
        response = client.get("/api/matching")
        assert response.status_code == 200

    def test_matching_returns_required_fields(self, client):
        """/api/matching이 필수 필드 반환"""
        response = client.get("/api/matching")
        data = response.json()
        # 필수 필드 확인
        assert "total" in data
        assert "items" in data
        assert "summary" in data

    def test_matching_items_have_status(self, client):
        """/api/matching의 각 아이템이 status 필드 보유"""
        response = client.get("/api/matching")
        data = response.json()
        # items가 리스트이면 첫 번째 항목 확인
        if data.get("items") and len(data["items"]) > 0:
            item = data["items"][0]
            assert "status" in item
            assert item["status"] in ("synced", "not_synced", "synced_with_duplicates")

    def test_matching_pagination(self, client):
        """/api/matching 페이지네이션 파라미터"""
        response = client.get("/api/matching?page=1&per_page=10")
        assert response.status_code == 200
        data = response.json()
        assert "page" in data
        assert "per_page" in data

    def test_matching_filter_by_status(self, client):
        """/api/matching 상태별 필터링"""
        response = client.get("/api/matching?status=synced")
        assert response.status_code == 200


class TestAPIMatchingTreeEndpoint:
    """트리 구조 매칭 API 테스트 (Issue #45)"""

    @pytest.fixture
    def client(self):
        from archive_analyzer.web.app import app
        return TestClient(app)

    def test_matching_tree_returns_200(self, client):
        """/api/matching/tree가 200을 반환"""
        response = client.get("/api/matching/tree")
        assert response.status_code == 200

    def test_matching_tree_returns_catalogs(self, client):
        """/api/matching/tree가 catalogs 필드 반환"""
        response = client.get("/api/matching/tree")
        data = response.json()
        assert "catalogs" in data
        assert isinstance(data["catalogs"], list)

    def test_matching_tree_catalog_has_name(self, client):
        """각 카탈로그가 name 필드 보유"""
        response = client.get("/api/matching/tree")
        data = response.json()
        if data.get("catalogs") and len(data["catalogs"]) > 0:
            catalog = data["catalogs"][0]
            assert "name" in catalog


class TestAPIDashboardEndpoint:
    """통합 대시보드 API 테스트 (Issue #45)"""

    @pytest.fixture
    def client(self):
        from archive_analyzer.web.app import app
        return TestClient(app)

    def test_dashboard_returns_200(self, client):
        """/api/dashboard가 200을 반환"""
        response = client.get("/api/dashboard")
        assert response.status_code == 200

    def test_dashboard_has_source_and_target(self, client):
        """/api/dashboard가 source, target 필드 반환"""
        response = client.get("/api/dashboard")
        data = response.json()
        assert "source" in data
        assert "target" in data

    def test_dashboard_has_sync_status(self, client):
        """/api/dashboard가 sync_status 필드 반환"""
        response = client.get("/api/dashboard")
        data = response.json()
        assert "sync_status" in data
