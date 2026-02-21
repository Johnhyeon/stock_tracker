"""기업 프로필 서비스."""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from core.timezone import now_kst

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models.company_profile import CompanyProfile
from models.dart_corp_code import DartCorpCode
from models.financial_statement import FinancialStatement

logger = logging.getLogger(__name__)

# 보고서명 → reprt_code 매핑
_REPRT_CODE_MAP = {
    "사업보고서": "11011",
    "반기보고서": "11012",
    "1분기": "11013",
    "3분기": "11014",
}


class CompanyProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_profile(self, stock_code: str) -> Optional[CompanyProfile]:
        stmt = select(CompanyProfile).where(CompanyProfile.stock_code == stock_code)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def get_report_url(self, stock_code: str, profile: CompanyProfile) -> Optional[str]:
        """report_rcept_no로 DART 보고서 URL 생성."""
        if profile.report_rcept_no:
            return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={profile.report_rcept_no}"
        return None

    async def generate_profile(self, stock_code: str, force: bool = False) -> Optional[CompanyProfile]:
        """DART 보고서 + 재무제표 + Gemini로 기업 프로필 생성/갱신."""
        # 캐시 확인 (30일 이내 + 실제 내용이 있는 경우만 스킵)
        if not force:
            existing = await self.get_profile(stock_code)
            if existing and existing.last_updated and existing.business_summary:
                if now_kst().replace(tzinfo=None) - existing.last_updated < timedelta(days=30):
                    return existing

        # 1. DART corp_code 조회
        corp_stmt = select(DartCorpCode).where(DartCorpCode.stock_code == stock_code)
        corp_result = await self.db.execute(corp_stmt)
        corp = corp_result.scalar_one_or_none()

        company_info = {}
        report_text = ""
        report_nm = ""
        rcept_no = ""
        financial_text = ""

        if corp:
            try:
                from integrations.dart.client import get_dart_client
                dart = get_dart_client()
                company_info = await dart.get_company_info(corp.corp_code)
            except Exception as e:
                logger.warning(f"DART 기업개황 조회 실패 ({stock_code}): {e}")

            # 2. 최신 보고서에서 '사업의 내용' 추출
            try:
                from integrations.dart.client import get_dart_client
                dart = get_dart_client()
                report = await dart.find_latest_report(corp.corp_code)
                if report:
                    rcept_no = report.get("rcept_no", "")
                    report_nm = report.get("report_nm", "")
                    report_text = await dart.get_business_section_text(rcept_no)
                    logger.info(
                        f"보고서 원문 추출 ({stock_code}): {report_nm}, "
                        f"{len(report_text)}자"
                    )
            except Exception as e:
                logger.warning(f"DART 보고서 원문 추출 실패 ({stock_code}): {e}")

            # 3. 재무제표 핵심 지표 추출
            try:
                financial_text = await self._get_financial_summary(stock_code, report_nm)
            except Exception as e:
                logger.warning(f"재무제표 조회 실패 ({stock_code}): {e}")

        # 4. Gemini로 요약 생성
        stock_name = (
            company_info.get("stock_name")
            or company_info.get("corp_name")
            or (corp.corp_name if corp else stock_code)
        )
        ceo_name = company_info.get("ceo_nm", "")
        industry = company_info.get("induty_code", "")

        summary_data = await self._generate_summary(
            stock_name=stock_name,
            ceo_name=ceo_name,
            industry=industry,
            report_text=report_text,
            financial_text=financial_text,
        )

        # 5. 요약 생성 실패 시 DB 저장 스킵
        if not summary_data.get("summary"):
            logger.warning(f"기업 프로필 생성 실패 ({stock_code}): 요약 내용 없음")
            return await self.get_profile(stock_code)

        # 6. DB upsert
        now = now_kst().replace(tzinfo=None)
        values = {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "ceo_name": ceo_name,
            "industry_name": industry,
            "website": company_info.get("hm_url", ""),
            "business_summary": summary_data.get("summary", ""),
            "main_products": summary_data.get("main_products", ""),
            "sector": summary_data.get("sector", ""),
            "report_source": report_nm if report_nm else None,
            "report_rcept_no": rcept_no if rcept_no else None,
            "last_updated": now,
            "created_at": now,
        }

        stmt = pg_insert(CompanyProfile).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_code"],
            set_={k: v for k, v in values.items() if k != "created_at"},
        )
        await self.db.execute(stmt)
        await self.db.commit()

        return await self.get_profile(stock_code)

    async def _get_financial_summary(self, stock_code: str, report_nm: str) -> str:
        """DB에서 재무제표 매출/영업이익/순이익 추출."""
        # 보고서명에서 연도와 보고서코드 추출
        bsns_year, reprt_code = self._parse_report_period(report_nm)
        if not bsns_year or not reprt_code:
            bsns_year = str(now_kst().year - 1)
            reprt_code = "11011"

        # DB에서 재무제표 조회 (CFS 우선, OFS 폴백)
        for fs_div in ("CFS", "OFS"):
            stmt = (
                select(FinancialStatement)
                .where(
                    FinancialStatement.stock_code == stock_code,
                    FinancialStatement.bsns_year == bsns_year,
                    FinancialStatement.reprt_code == reprt_code,
                    FinancialStatement.fs_div == fs_div,
                )
            )
            result = await self.db.execute(stmt)
            rows = result.scalars().all()
            if rows:
                items = [
                    {"account_nm": r.account_nm, "thstrm_amount": str(r.thstrm_amount) if r.thstrm_amount is not None else ""}
                    for r in rows
                ]
                return self._format_financial(items)

        return ""

    def _parse_report_period(self, report_nm: str) -> tuple[Optional[str], Optional[str]]:
        """보고서명에서 사업연도와 reprt_code 추출.

        예: "분기보고서 (2024.09)" → ("2024", "11014")
             "사업보고서 (2023.12)" → ("2023", "11011")
        """
        if not report_nm:
            return None, None

        # 연도 추출
        import re
        year_match = re.search(r"\((\d{4})\.", report_nm)
        if not year_match:
            return None, None
        year = year_match.group(1)

        # 월 추출하여 분기 판별
        month_match = re.search(r"\.(\d{2})\)", report_nm)
        month = month_match.group(1) if month_match else ""

        # 보고서 유형으로 reprt_code 결정
        if "사업보고서" in report_nm:
            return year, "11011"
        elif "반기보고서" in report_nm:
            return year, "11012"
        elif "분기보고서" in report_nm:
            if month in ("03", "01", "02"):
                return year, "11013"  # 1분기
            else:
                return year, "11014"  # 3분기
        return None, None

    def _format_financial(self, items: list[dict]) -> str:
        """재무제표 항목에서 핵심 지표만 포맷팅."""
        target_accounts = {
            "매출액": None,
            "영업이익": None,
            "당기순이익": None,
            "수익(매출액)": None,  # IFRS 표기 변형
        }

        for item in items:
            account_nm = item.get("account_nm", "")
            if account_nm in target_accounts:
                # thstrm_amount = 당기 금액
                amount = item.get("thstrm_amount", "")
                if amount and amount != "-":
                    target_accounts[account_nm] = amount

        # "수익(매출액)" fallback
        revenue = target_accounts.get("매출액") or target_accounts.get("수익(매출액)")
        operating = target_accounts.get("영업이익")
        net_income = target_accounts.get("당기순이익")

        lines = []
        if revenue:
            lines.append(f"매출액: {revenue}원")
        if operating:
            lines.append(f"영업이익: {operating}원")
        if net_income:
            lines.append(f"당기순이익: {net_income}원")

        return "\n".join(lines)

    async def _generate_summary(
        self,
        stock_name: str,
        ceo_name: str,
        industry: str,
        report_text: str,
        financial_text: str,
    ) -> dict:
        """Gemini AI로 기업 요약 생성 (DART 보고서 기반)."""
        try:
            from integrations.gemini.client import get_gemini_client
            gemini = get_gemini_client()
            if not gemini.is_configured:
                return {"summary": "", "main_products": "", "sector": ""}
        except Exception:
            return {"summary": "", "main_products": "", "sector": ""}

        # 보고서 텍스트가 있으면 보고서 기반 프롬프트
        if report_text:
            prompt = f"""다음 한국 상장기업의 DART 공시 보고서를 기반으로 기업 프로필을 작성해주세요.

기업명: {stock_name}
대표이사: {ceo_name}
업종: {industry}

[DART 공시 보고서 - 사업의 내용]
{report_text}

[주요 재무지표]
{financial_text if financial_text else "조회 불가"}

다음 JSON 형식으로 응답해주세요:
{{
  "summary": "이 기업이 실제로 무엇을 하는 회사인지 보고서 내용 기반으로 3~4문장으로 설명. 구체적인 사업 내용, 주력 분야, 매출 구조를 포함. 뉴스나 추측이 아닌 사실 기반으로 서술.",
  "main_products": "주요 제품/서비스를 쉼표로 구분 (보고서에 기재된 것 기준, 최대 5개)",
  "sector": "해당 섹터 한 단어 (예: 반도체, 바이오, 2차전지, 방산, IT서비스, 소프트웨어 등)"
}}

JSON만 응답하세요."""
        else:
            # fallback: 보고서 없을 때 기존 기업개황 기반
            prompt = f"""다음 한국 상장기업의 프로필을 분석해주세요.

기업명: {stock_name}
대표이사: {ceo_name}
업종코드: {industry}

{f"[주요 재무지표]{chr(10)}{financial_text}" if financial_text else ""}

다음 JSON 형식으로 응답해주세요:
{{
  "summary": "이 기업이 무엇을 하는 회사인지 2~3문장으로 설명. 핵심 사업과 시장에서의 위치를 포함.",
  "main_products": "주요 제품/서비스를 쉼표로 구분 (최대 5개)",
  "sector": "해당 섹터 한 단어 (예: 반도체, 바이오, 2차전지, 방산, IT서비스, 소프트웨어 등)"
}}

JSON만 응답하세요."""

        try:
            response = await gemini._generate(prompt)
            if not response:
                return {"summary": "", "main_products": "", "sector": ""}

            # JSON 파싱
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                text = text.rsplit("```", 1)[0]

            return json.loads(text)
        except Exception as e:
            logger.warning(f"기업 프로필 AI 생성 실패 ({stock_name}): {e}")
            return {"summary": "", "main_products": "", "sector": ""}
