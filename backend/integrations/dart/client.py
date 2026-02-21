"""DART (전자공시시스템) API 클라이언트."""
import io
import logging
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional
from datetime import datetime, timedelta

from integrations.base_client import BaseAPIClient
from core.config import get_settings
from core.timezone import now_kst

logger = logging.getLogger(__name__)


class DARTRateLimitError(Exception):
    """DART 일일 사용한도 초과."""
    pass


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
        self._rate_limited_until: Optional[datetime] = None

    def _check_rate_limit(self):
        """일일 한도 초과 상태면 요청을 차단."""
        if self._rate_limited_until:
            now = now_kst()
            if now < self._rate_limited_until:
                remaining = (self._rate_limited_until - now).total_seconds() / 3600
                raise DARTRateLimitError(
                    f"DART 일일 사용한도 초과. {remaining:.1f}시간 후 리셋 예정"
                )
            else:
                self._rate_limited_until = None
                logger.info("DART API 일일 한도 리셋됨")

    def _handle_status(self, data: dict, context: str = ""):
        """DART API 응답 상태 코드 처리."""
        status = data.get("status")
        message = data.get("message", "")

        if status == "000":
            return  # 정상

        if status == "013":
            return  # 데이터 없음 (정상 케이스)

        if status in ("020", "011") or "사용한도" in message:
            # 일일 한도(020) 또는 초당 한도(011) 초과
            # 자정까지 쿨다운 설정
            now = now_kst()
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
            self._rate_limited_until = tomorrow
            logger.warning(f"DART API 일일 한도 초과 → {tomorrow.strftime('%H:%M')}까지 대기")
            raise DARTRateLimitError(f"DART 일일 사용한도 초과 ({context})")

        raise ValueError(f"DART API error: {message}")

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
        self._check_rate_limit()

        # 기본 날짜 설정 (오늘부터 7일 전)
        if not end_de:
            end_de = now_kst().strftime("%Y%m%d")
        if not bgn_de:
            bgn_de = (now_kst() - timedelta(days=7)).strftime("%Y%m%d")

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
        self._handle_status(data, "공시검색")

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
        self._check_rate_limit()

        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
        }

        data = await self.get("/company.json", params=params)
        self._handle_status(data, "기업개황")

        return data

    async def get_financial_statement(
        self,
        corp_code: str,
        bsns_year: str,
        reprt_code: str,
        fs_div: str = "CFS",
    ) -> list[dict]:
        """재무제표 전체 계정 조회 (단일회사 전체 재무제표).

        Args:
            corp_code: 고유번호 (8자리)
            bsns_year: 사업연도 (YYYY)
            reprt_code: 보고서코드 (11011=연간, 11012=반기, 11013=1분기, 11014=3분기)
            fs_div: 개별/연결 (CFS=연결, OFS=개별)

        Returns:
            계정 항목 리스트. 데이터 없으면 빈 리스트.
        """
        if not self.api_key:
            raise ValueError("DART API key not configured")
        self._check_rate_limit()

        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bsns_year": bsns_year,
            "reprt_code": reprt_code,
            "fs_div": fs_div,
        }

        data = await self.get("/fnlttSinglAcntAll.json", params=params)

        status = data.get("status")
        if status == "013":
            return []

        self._handle_status(data, f"재무제표 {corp_code} {bsns_year}")

        return data.get("list", [])

    async def download_corp_codes(self) -> list[dict]:
        """DART 고유번호 전체 다운로드 (corpCode.xml).

        ZIP 파일로 반환되며, 내부에 XML이 포함되어 있음.

        Returns:
            [{"corp_code": "00126380", "corp_name": "삼성전자",
              "stock_code": "005930", "modify_date": "20230101"}, ...]
        """
        if not self.api_key:
            raise ValueError("DART API key not configured")
        self._check_rate_limit()

        params = {"crtfc_key": self.api_key}

        binary_data = await self._request_binary("GET", "/corpCode.xml", params=params)

        # ZIP 해제 → XML 파싱
        with zipfile.ZipFile(io.BytesIO(binary_data)) as zf:
            xml_filename = zf.namelist()[0]
            xml_data = zf.read(xml_filename)

        root = ET.fromstring(xml_data)
        result = []
        for corp in root.findall("list"):
            corp_code = corp.findtext("corp_code", "").strip()
            corp_name = corp.findtext("corp_name", "").strip()
            stock_code = corp.findtext("stock_code", "").strip()
            modify_date = corp.findtext("modify_date", "").strip()

            if corp_code:
                result.append({
                    "corp_code": corp_code,
                    "corp_name": corp_name,
                    "stock_code": stock_code if stock_code else None,
                    "modify_date": modify_date if modify_date else None,
                })

        logger.info(f"Downloaded {len(result)} corp codes from DART")
        return result

    async def find_latest_report(self, corp_code: str) -> Optional[dict]:
        """최신 정기보고서(분기/반기/연간) 조회.

        search_disclosures(pblntf_ty="A", 최근 1년)에서
        '분기보고서','반기보고서','사업보고서' 포함하는 가장 최신 건을 반환.

        Returns:
            {"rcept_no": "...", "report_nm": "분기보고서 (2024.09)", ...} 또는 None
        """
        try:
            end_de = now_kst().strftime("%Y%m%d")
            bgn_de = (now_kst() - timedelta(days=365)).strftime("%Y%m%d")

            data = await self.search_disclosures(
                corp_code=corp_code,
                bgn_de=bgn_de,
                end_de=end_de,
                pblntf_ty="A",  # 정기공시
                page_count=100,
            )

            report_keywords = ["분기보고서", "반기보고서", "사업보고서"]
            for item in data.get("list", []):
                report_nm = item.get("report_nm", "")
                if any(kw in report_nm for kw in report_keywords):
                    # [정정] 등 제외, 원본 보고서 우선
                    if "[정정]" not in report_nm:
                        return item

            # 정정본밖에 없으면 첫 번째라도 반환
            for item in data.get("list", []):
                report_nm = item.get("report_nm", "")
                if any(kw in report_nm for kw in report_keywords):
                    return item

            return None
        except Exception as e:
            logger.warning(f"DART 최신 보고서 조회 실패 ({corp_code}): {e}")
            return None

    async def get_business_section_text(self, rcept_no: str) -> str:
        """보고서 원문 ZIP에서 '사업의 내용' 섹션 텍스트 추출.

        1. /document.xml → ZIP bytes
        2. ZIP 내 XML/HTML 파일 순회하며 '사업의 내용' 탐색
        3. HTML/XML 태그 제거 → 순수 텍스트
        4. 최대 4000자로 truncate

        실패 시 빈 문자열 반환.
        """
        try:
            self._check_rate_limit()

            params = {
                "crtfc_key": self.api_key,
                "rcept_no": rcept_no,
            }

            binary_data = await self._request_binary(
                "GET", "/document.xml", params=params
            )

            with zipfile.ZipFile(io.BytesIO(binary_data)) as zf:
                # ZIP 내 파일 순회: '사업의 내용' 포함 파일 찾기
                target_text = ""
                for name in zf.namelist():
                    if not name.lower().endswith((".xml", ".html", ".htm")):
                        continue
                    try:
                        content = zf.read(name).decode("utf-8", errors="ignore")
                    except Exception:
                        continue

                    if "사업의 내용" in content:
                        target_text = content
                        break

                if not target_text:
                    logger.info(f"보고서 {rcept_no}: '사업의 내용' 섹션 미발견")
                    return ""

                # HTML/XML 태그 제거
                text = re.sub(r"<[^>]+>", " ", target_text)
                # 연속 공백 정리
                text = re.sub(r"\s+", " ", text).strip()

                # 4000자 truncate
                if len(text) > 4000:
                    text = text[:4000] + "..."

                return text

        except Exception as e:
            logger.warning(f"DART 보고서 원문 추출 실패 ({rcept_no}): {e}")
            return ""

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
