"""재무 저평가 스크리너 스키마."""
from typing import Optional
from pydantic import BaseModel


class ValueMetrics(BaseModel):
    """개별 종목의 재무 지표 + 점수."""
    stock_code: str
    stock_name: str
    sector: Optional[str] = None
    current_price: Optional[int] = None
    # 재무 비율
    per: Optional[float] = None
    pbr: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    debt_ratio: Optional[float] = None
    current_ratio: Optional[float] = None
    revenue_growth: Optional[float] = None
    # 항목별 점수
    per_score: int = 0
    pbr_score: int = 0
    roe_score: int = 0
    margin_score: int = 0
    growth_score: int = 0
    safety_score: int = 0  # 부채 + 유동
    total_score: int = 0
    grade: str = "D"  # A/B/C/D
    comment: str = ""  # 저평가 이유 코멘트
    # 적정가치
    fair_value: Optional[int] = None  # 적정가치 (원)
    upside_pct: Optional[float] = None  # 괴리율 (%)
    valuation_method: Optional[str] = None  # 산출 방법
    # 기준 연도
    bsns_year: Optional[str] = None
    reprt_code: Optional[str] = None


class ValueScreenerSummary(BaseModel):
    """스크리너 요약 통계."""
    grade_counts: dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0}
    avg_per: Optional[float] = None
    avg_pbr: Optional[float] = None
    avg_roe: Optional[float] = None
    total_screened: int = 0


class ValueScreenerResponse(BaseModel):
    """스크리너 응답."""
    stocks: list[ValueMetrics] = []
    summary: ValueScreenerSummary = ValueScreenerSummary()
    generated_at: str = ""
