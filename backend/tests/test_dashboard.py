"""대시보드 API 테스트."""
import pytest


class TestDashboardAPI:
    """대시보드 API 테스트."""

    def test_dashboard_empty(self, client):
        """빈 대시보드 테스트."""
        response = client.get("/api/v1/dashboard")
        assert response.status_code == 200
        data = response.json()

        # 기본 구조 확인
        assert "stats" in data
        assert "research_ideas" in data
        assert "chart_ideas" in data
        assert "watching_ideas" in data  # 새로 추가된 필드

        # 통계 확인
        assert data["stats"]["total_ideas"] == 0
        assert data["stats"]["active_ideas"] == 0
        assert data["stats"]["watching_ideas"] == 0

    def test_dashboard_with_watching_ideas(self, client):
        """WATCHING 상태 아이디어 대시보드 표시 테스트."""
        # WATCHING 상태로 아이디어 생성 (기본값)
        client.post(
            "/api/v1/ideas",
            json={
                "type": "research",
                "tickers": ["삼성전자"],
                "thesis": "관찰 중인 아이디어",
                "expected_timeframe_days": 30,
                "target_return_pct": 15,
            },
        )

        response = client.get("/api/v1/dashboard")
        assert response.status_code == 200
        data = response.json()

        # watching_ideas에 포함되어야 함
        assert data["stats"]["watching_ideas"] == 1
        assert data["stats"]["active_ideas"] == 0
        assert len(data["watching_ideas"]) == 1
        assert data["watching_ideas"][0]["tickers"] == ["삼성전자"]

    def test_dashboard_with_active_ideas(self, client):
        """ACTIVE 상태 아이디어 대시보드 표시 테스트."""
        # 리서치 아이디어 생성 후 활성화
        response = client.post(
            "/api/v1/ideas",
            json={
                "type": "research",
                "tickers": ["SK하이닉스"],
                "thesis": "활성 리서치 아이디어",
                "expected_timeframe_days": 60,
                "target_return_pct": 20,
            },
        )
        idea_id = response.json()["id"]
        client.patch(f"/api/v1/ideas/{idea_id}", json={"status": "active"})

        # 차트 아이디어 생성 후 활성화
        response = client.post(
            "/api/v1/ideas",
            json={
                "type": "chart",
                "tickers": ["LG에너지솔루션"],
                "thesis": "활성 차트 아이디어",
                "expected_timeframe_days": 14,
                "target_return_pct": 10,
            },
        )
        idea_id = response.json()["id"]
        client.patch(f"/api/v1/ideas/{idea_id}", json={"status": "active"})

        response = client.get("/api/v1/dashboard")
        assert response.status_code == 200
        data = response.json()

        # 각각 해당 섹션에 표시
        assert data["stats"]["active_ideas"] == 2
        assert len(data["research_ideas"]) == 1
        assert len(data["chart_ideas"]) == 1
        assert data["research_ideas"][0]["tickers"] == ["SK하이닉스"]
        assert data["chart_ideas"][0]["tickers"] == ["LG에너지솔루션"]

    def test_dashboard_mixed_status(self, client):
        """여러 상태 혼합 테스트."""
        # WATCHING 아이디어
        client.post(
            "/api/v1/ideas",
            json={
                "type": "research",
                "tickers": ["관찰종목"],
                "thesis": "관찰 중",
                "expected_timeframe_days": 30,
                "target_return_pct": 10,
            },
        )

        # ACTIVE 아이디어
        response = client.post(
            "/api/v1/ideas",
            json={
                "type": "research",
                "tickers": ["활성종목"],
                "thesis": "활성 중",
                "expected_timeframe_days": 30,
                "target_return_pct": 10,
            },
        )
        client.patch(f"/api/v1/ideas/{response.json()['id']}", json={"status": "active"})

        # EXITED 아이디어 (대시보드에 미표시)
        response = client.post(
            "/api/v1/ideas",
            json={
                "type": "chart",
                "tickers": ["청산종목"],
                "thesis": "청산됨",
                "expected_timeframe_days": 30,
                "target_return_pct": 10,
            },
        )
        client.patch(f"/api/v1/ideas/{response.json()['id']}", json={"status": "exited"})

        response = client.get("/api/v1/dashboard")
        data = response.json()

        # EXITED는 대시보드에 안 나옴
        assert data["stats"]["total_ideas"] == 2  # active + watching
        assert data["stats"]["active_ideas"] == 1
        assert data["stats"]["watching_ideas"] == 1
        assert len(data["research_ideas"]) == 1  # active research만
        assert len(data["watching_ideas"]) == 1

    def test_dashboard_stats_structure(self, client):
        """대시보드 통계 구조 테스트."""
        response = client.get("/api/v1/dashboard")
        data = response.json()

        stats = data["stats"]
        # 모든 필수 필드 확인
        assert "total_ideas" in stats
        assert "active_ideas" in stats
        assert "watching_ideas" in stats
        assert "research_ideas" in stats
        assert "chart_ideas" in stats
        assert "total_invested" in stats
        assert "avg_return_pct" in stats
