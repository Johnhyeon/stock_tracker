"""아이디어 API 테스트."""
import pytest


class TestIdeaAPI:
    """아이디어 CRUD 테스트."""

    def test_create_idea(self, client):
        """아이디어 생성 테스트."""
        response = client.post(
            "/api/v1/ideas",
            json={
                "type": "research",
                "tickers": ["삼성전자"],
                "thesis": "테스트 투자 논리입니다.",
                "expected_timeframe_days": 30,
                "target_return_pct": 15,
                "sector": "반도체",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "research"
        assert data["tickers"] == ["삼성전자"]
        assert data["thesis"] == "테스트 투자 논리입니다."
        assert data["status"] == "watching"  # 기본값
        assert data["fundamental_health"] == "healthy"  # 기본값
        assert "id" in data

    def test_get_idea(self, client):
        """아이디어 조회 테스트."""
        # 먼저 생성
        create_response = client.post(
            "/api/v1/ideas",
            json={
                "type": "chart",
                "tickers": ["SK하이닉스"],
                "thesis": "차트 기반 분석",
                "expected_timeframe_days": 14,
                "target_return_pct": 10,
            },
        )
        idea_id = create_response.json()["id"]

        # 조회
        response = client.get(f"/api/v1/ideas/{idea_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == idea_id
        assert data["type"] == "chart"

    def test_list_ideas(self, client):
        """아이디어 목록 조회 테스트."""
        # 여러 개 생성
        for i in range(3):
            client.post(
                "/api/v1/ideas",
                json={
                    "type": "research" if i % 2 == 0 else "chart",
                    "tickers": [f"종목{i}"],
                    "thesis": f"테스트 {i}",
                    "expected_timeframe_days": 30,
                    "target_return_pct": 10,
                },
            )

        response = client.get("/api/v1/ideas")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_list_ideas_filter_by_status(self, client):
        """상태별 필터링 테스트."""
        # watching 상태로 생성
        client.post(
            "/api/v1/ideas",
            json={
                "type": "research",
                "tickers": ["A"],
                "thesis": "테스트",
                "expected_timeframe_days": 30,
                "target_return_pct": 10,
            },
        )

        # active 상태로 변경할 아이디어
        response = client.post(
            "/api/v1/ideas",
            json={
                "type": "research",
                "tickers": ["B"],
                "thesis": "테스트2",
                "expected_timeframe_days": 30,
                "target_return_pct": 10,
            },
        )
        idea_id = response.json()["id"]
        client.patch(f"/api/v1/ideas/{idea_id}", json={"status": "active"})

        # watching만 조회
        response = client.get("/api/v1/ideas?status=watching")
        assert response.status_code == 200
        assert len(response.json()) == 1

        # active만 조회
        response = client.get("/api/v1/ideas?status=active")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_update_idea(self, client):
        """아이디어 수정 테스트."""
        # 생성
        create_response = client.post(
            "/api/v1/ideas",
            json={
                "type": "research",
                "tickers": ["테스트"],
                "thesis": "원본",
                "expected_timeframe_days": 30,
                "target_return_pct": 10,
            },
        )
        idea_id = create_response.json()["id"]

        # 수정
        response = client.patch(
            f"/api/v1/ideas/{idea_id}",
            json={
                "thesis": "수정된 논리",
                "status": "active",
                "fundamental_health": "deteriorating",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["thesis"] == "수정된 논리"
        assert data["status"] == "active"
        assert data["fundamental_health"] == "deteriorating"

    def test_delete_idea(self, client):
        """아이디어 삭제 테스트."""
        # 생성
        create_response = client.post(
            "/api/v1/ideas",
            json={
                "type": "research",
                "tickers": ["삭제테스트"],
                "thesis": "삭제될 아이디어",
                "expected_timeframe_days": 30,
                "target_return_pct": 10,
            },
        )
        idea_id = create_response.json()["id"]

        # 삭제
        response = client.delete(f"/api/v1/ideas/{idea_id}")
        assert response.status_code == 204

        # 조회 시 404
        response = client.get(f"/api/v1/ideas/{idea_id}")
        assert response.status_code == 404
