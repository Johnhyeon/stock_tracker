"""공시 API 테스트."""
import pytest
from sqlalchemy.orm import Session

from models import Disclosure, DisclosureType, DisclosureImportance, Stock


class TestDisclosureAPI:
    """공시 API 테스트."""

    def _create_test_disclosure(self, db: Session, stock_code: str, corp_name: str):
        """테스트용 공시 생성."""
        disclosure = Disclosure(
            rcept_no=f"20240101000{stock_code}",
            rcept_dt="20240101",
            corp_code=f"00{stock_code}",
            corp_name=corp_name,
            stock_code=stock_code,
            report_nm="테스트 공시",
            disclosure_type=DisclosureType.PERFORMANCE,
            importance=DisclosureImportance.HIGH,
            url=f"https://dart.fss.or.kr/test/{stock_code}",
        )
        db.add(disclosure)
        db.commit()
        return disclosure

    def _create_test_stock(self, db: Session, code: str, name: str):
        """테스트용 종목 생성."""
        stock = Stock(
            code=code,
            name=name,
            market="KOSPI",
        )
        db.add(stock)
        db.commit()
        return stock

    def test_list_disclosures_empty(self, client):
        """빈 공시 목록 테스트."""
        response = client.get("/api/v1/disclosures")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_disclosures_with_data(self, client, db):
        """공시 목록 조회 테스트."""
        # 테스트 공시 생성
        self._create_test_disclosure(db, "005930", "삼성전자")
        self._create_test_disclosure(db, "000660", "SK하이닉스")

        response = client.get("/api/v1/disclosures")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_disclosures_filter_by_stock_code(self, client, db):
        """종목코드 필터링 테스트."""
        self._create_test_disclosure(db, "005930", "삼성전자")
        self._create_test_disclosure(db, "000660", "SK하이닉스")

        response = client.get("/api/v1/disclosures?stock_code=005930")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["stock_code"] == "005930"

    def test_list_disclosures_my_ideas_only_no_ideas(self, client, db):
        """내 아이디어 필터링 - 아이디어 없을 때."""
        self._create_test_disclosure(db, "005930", "삼성전자")

        response = client.get("/api/v1/disclosures?my_ideas_only=true")
        assert response.status_code == 200
        data = response.json()
        # 아이디어가 없으면 빈 목록
        assert data["items"] == []

    def test_list_disclosures_my_ideas_only_with_ideas(self, client, db):
        """내 아이디어 필터링 - 아이디어 있을 때."""
        # 종목 생성
        self._create_test_stock(db, "005930", "삼성전자")
        self._create_test_stock(db, "000660", "SK하이닉스")

        # 공시 생성
        self._create_test_disclosure(db, "005930", "삼성전자")
        self._create_test_disclosure(db, "000660", "SK하이닉스")

        # 삼성전자만 아이디어에 추가 (watching 상태)
        client.post(
            "/api/v1/ideas",
            json={
                "type": "research",
                "tickers": ["삼성전자"],
                "thesis": "테스트",
                "expected_timeframe_days": 30,
                "target_return_pct": 10,
            },
        )

        # my_ideas_only=true로 조회
        response = client.get("/api/v1/disclosures?my_ideas_only=true")
        assert response.status_code == 200
        data = response.json()
        # 삼성전자 공시만 조회되어야 함
        assert data["total"] == 1
        assert data["items"][0]["stock_code"] == "005930"

    def test_list_disclosures_my_ideas_only_active_and_watching(self, client, db):
        """내 아이디어 필터링 - active와 watching 모두 포함."""
        # 종목 생성
        self._create_test_stock(db, "005930", "삼성전자")
        self._create_test_stock(db, "000660", "SK하이닉스")
        self._create_test_stock(db, "373220", "LG에너지솔루션")

        # 공시 생성
        self._create_test_disclosure(db, "005930", "삼성전자")
        self._create_test_disclosure(db, "000660", "SK하이닉스")
        self._create_test_disclosure(db, "373220", "LG에너지솔루션")

        # 삼성전자: watching 상태
        client.post(
            "/api/v1/ideas",
            json={
                "type": "research",
                "tickers": ["삼성전자"],
                "thesis": "테스트",
                "expected_timeframe_days": 30,
                "target_return_pct": 10,
            },
        )

        # SK하이닉스: active 상태
        response = client.post(
            "/api/v1/ideas",
            json={
                "type": "chart",
                "tickers": ["SK하이닉스"],
                "thesis": "테스트",
                "expected_timeframe_days": 14,
                "target_return_pct": 5,
            },
        )
        client.patch(f"/api/v1/ideas/{response.json()['id']}", json={"status": "active"})

        # LG에너지솔루션: exited 상태 (제외되어야 함)
        response = client.post(
            "/api/v1/ideas",
            json={
                "type": "research",
                "tickers": ["LG에너지솔루션"],
                "thesis": "테스트",
                "expected_timeframe_days": 30,
                "target_return_pct": 10,
            },
        )
        client.patch(f"/api/v1/ideas/{response.json()['id']}", json={"status": "exited"})

        # my_ideas_only=true로 조회
        response = client.get("/api/v1/disclosures?my_ideas_only=true")
        data = response.json()

        # 삼성전자, SK하이닉스만 (active + watching)
        assert data["total"] == 2
        stock_codes = [item["stock_code"] for item in data["items"]]
        assert "005930" in stock_codes  # 삼성전자
        assert "000660" in stock_codes  # SK하이닉스
        assert "373220" not in stock_codes  # LG에너지솔루션 (exited)

    def test_disclosure_stats(self, client, db):
        """공시 통계 테스트."""
        self._create_test_disclosure(db, "005930", "삼성전자")

        response = client.get("/api/v1/disclosures/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "unread" in data
        assert "by_importance" in data

    def test_mark_disclosure_as_read(self, client, db):
        """공시 읽음 처리 테스트."""
        disclosure = self._create_test_disclosure(db, "005930", "삼성전자")
        disclosure_id = str(disclosure.id)

        # 읽음 처리
        response = client.post(f"/api/v1/disclosures/{disclosure_id}/read")
        assert response.status_code == 200
        data = response.json()
        assert data["is_read"] == True
