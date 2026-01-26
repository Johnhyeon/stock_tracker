"""DART (전자공시시스템) API 클라이언트."""
import logging
from typing import Optional
from datetime import datetime, timedelta

from integrations.base_client import BaseAPIClient
from core.config import get_settings

logger = logging.getLogger(__name__)


class DARTClient(BaseAPIClient):
    """DART Open API 클라이언트.

    지원 기능:
    - 공시검색 (최근 공시 목록)
    - 기업개황 조회
    """

    BASE_URL = "https://opendart.fss.or.kr/api"

    def __init__(self):
        settings = get_settings()
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit=5.0,  # 초당 5회 제한
            timeout=30.0,
        )
        self.api_key = settings.dart_api_key

    def get_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
        }

    async def search_disclosures(
        self,
        corp_code: Optional[str] = None,
        bgn_de: Optional[str] = None,
        end_de: Optional[str] = None,
        pblntf_ty: Optional[str] = None,
        page_no: int = 1,
        page_count: int = 100,
    ) -> dict:
        """공시검색.

        Args:
            corp_code: 고유번호 (8자리) - 없으면 전체
            bgn_de: 시작일 (YYYYMMDD)
            end_de: 종료일 (YYYYMMDD)
            pblntf_ty: 공시유형 (A:정기공시, B:주요사항보고, C:발행공시,
                       D:지분공시, E:기타공시, F:외부감사관련, G:펀드공시,
                       H:자산유동화, I:거래소공시, J:공정위공시)
            page_no: 페이지 번호
            page_count: 페이지당 건수 (최대 100)

        Returns:
            {
                "status": "000",
                "message": "정상",
                "page_no": 1,
                "page_count": 100,
                "total_count": 1234,
                "total_page": 13,
                "list": [
                    {
                        "corp_code": "00126380",
                        "corp_name": "삼성전자",
                        "stock_code": "005930",
                        "corp_cls": "Y",  # Y:유가, K:코스닥, N:코넥스, E:기타
                        "report_nm": "분기보고서 (2024.03)",
                        "rcept_no": "20240515000123",
                        "flr_nm": "삼성전자",
                        "rcept_dt": "20240515",
                        "rm": ""
                    },
                    ...
                ]
            }
        """
        if not self.api_key:
            raise ValueError("DART API key not configured")

        # 기본 날짜 설정 (오늘부터 7일 전)
        if not end_de:
            end_de = datetime.now().strftime("%Y%m%d")
        if not bgn_de:
            bgn_de = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")

        params = {
            "crtfc_key": self.api_key,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "page_no": page_no,
            "page_count": page_count,
        }

        if corp_code:
            params["corp_code"] = corp_code
        if pblntf_ty:
            params["pblntf_ty"] = pblntf_ty

        data = await self.get("/list.json", params=params)

        if data.get("status") != "000":
            logger.error(f"DART API error: {data.get('message')}")
            raise ValueError(f"DART API error: {data.get('message')}")

        return data

    async def get_company_info(self, corp_code: str) -> dict:
        """기업개황 조회.

        Args:
            corp_code: 고유번호 (8자리)

        Returns:
            {
                "status": "000",
                "corp_name": "삼성전자",
                "corp_name_eng": "SAMSUNG ELECTRONICS CO., LTD.",
                "stock_name": "삼성전자",
                "stock_code": "005930",
                "ceo_nm": "한종희, 경계현",
                "corp_cls": "Y",
                "induty_code": "264",
                ...
            }
        """
        if not self.api_key:
            raise ValueError("DART API key not configured")

        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
        }

        data = await self.get("/company.json", params=params)

        if data.get("status") != "000":
            raise ValueError(f"DART API error: {data.get('message')}")

        return data

    async def get_corp_code_by_stock(self, stock_code: str) -> Optional[str]:
        """종목코드로 고유번호 조회.

        참고: DART는 고유번호 목록을 별도 XML/ZIP으로 제공하므로,
        실제 구현시에는 미리 다운받아 매핑 테이블로 관리하는 것이 좋습니다.
        여기서는 공시검색 결과에서 추출하는 간단한 방식을 사용합니다.

        Args:
            stock_code: 종목코드 (6자리)

        Returns:
            고유번호 (8자리) 또는 None
        """
        try:
            # 최근 공시에서 해당 종목 찾기
            data = await self.search_disclosures(page_count=100)
            for item in data.get("list", []):
                if item.get("stock_code") == stock_code:
                    return item.get("corp_code")
            return None
        except Exception as e:
            logger.error(f"Failed to find corp_code for {stock_code}: {e}")
            return None


# 싱글톤 인스턴스
_dart_client: Optional[DARTClient] = None


def get_dart_client() -> DARTClient:
    """DART 클라이언트 싱글톤 반환."""
    global _dart_client
    if _dart_client is None:
        _dart_client = DARTClient()
    return _dart_client
