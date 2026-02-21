"""재무제표 관련 스키마."""
from typing import Optional
from pydantic import BaseModel


class FinancialStatementItem(BaseModel):
    """개별 재무제표 계정 항목."""
    sj_div: str  # BS/IS/CF
    sj_nm: Optional[str] = None
    account_id: str
    account_nm: str
    account_detail: Optional[str] = None
    thstrm_amount: Optional[int] = None
    frmtrm_amount: Optional[int] = None
    bfefrmtrm_amount: Optional[int] = None
    thstrm_nm: Optional[str] = None
    frmtrm_nm: Optional[str] = None
    bfefrmtrm_nm: Optional[str] = None
    ord: Optional[int] = None


class FinancialStatementResponse(BaseModel):
    """특정 기간 재무제표."""
    stock_code: str
    bsns_year: str
    reprt_code: str
    fs_div: str
    items: list[FinancialStatementItem] = []
    bs_items: list[FinancialStatementItem] = []  # 재무상태표
    is_items: list[FinancialStatementItem] = []  # 손익계산서
    cf_items: list[FinancialStatementItem] = []  # 현금흐름표


class FinancialRatios(BaseModel):
    """계산된 재무비율."""
    per: Optional[float] = None
    pbr: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    operating_margin: Optional[float] = None  # 영업이익률
    net_margin: Optional[float] = None  # 순이익률
    debt_ratio: Optional[float] = None  # 부채비율
    current_ratio: Optional[float] = None  # 유동비율
    revenue_growth: Optional[float] = None  # 매출성장률
    bsns_year: Optional[str] = None
    reprt_code: Optional[str] = None


class AnnualFinancialData(BaseModel):
    """연간 재무 데이터."""
    bsns_year: str
    reprt_code: str
    reprt_name: str  # "연간", "반기", "1분기", "3분기"
    revenue: Optional[int] = None
    operating_income: Optional[int] = None
    net_income: Optional[int] = None
    total_assets: Optional[int] = None
    total_liabilities: Optional[int] = None
    total_equity: Optional[int] = None
    ratios: Optional[FinancialRatios] = None


class FinancialSummaryResponse(BaseModel):
    """3개년 재무 요약 통합."""
    stock_code: str
    corp_code: Optional[str] = None
    annual_data: list[AnnualFinancialData] = []
    quarterly_data: list[AnnualFinancialData] = []
    latest_ratios: Optional[FinancialRatios] = None
    has_data: bool = False


class FinancialCollectRequest(BaseModel):
    """재무제표 수집 요청."""
    years: int = 3


class FinancialCollectResponse(BaseModel):
    """재무제표 수집 결과."""
    stock_code: str
    collected_count: int = 0
    years_collected: list[str] = []
    message: str = ""
