"""장중 갭다운 회복 분석 스키마."""
from typing import Optional
from pydantic import BaseModel


class GapRecoveryStock(BaseModel):
    """갭다운 후 장중 회복 종목."""
    stock_code: str
    stock_name: str
    themes: list[str] = []

    # 가격
    prev_close: float
    open_price: float
    current_price: float
    high_price: float
    low_price: float
    volume: int

    # 갭 지표
    gap_pct: float               # 시가 갭 (음수 = 갭다운)
    change_from_open_pct: float  # 시가 대비 현재가 변동률

    # 회복 지표
    gap_fill_pct: float          # 갭 메움 비율 (100=완전 메움, >100=전일종가 상회)
    recovery_from_low_pct: float # 저가 대비 회복률 (고-저 레인지 중 현재 위치)
    is_above_prev_close: bool    # 전일종가 상회 여부

    # 종합 점수
    recovery_score: float        # 0~100 회복 점수


class GapRecoveryResponse(BaseModel):
    """갭다운 회복 응답."""
    stocks: list[GapRecoveryStock]
    count: int
    total_gap_down: int          # 갭다운 종목 총 수
    total_scanned: int           # 스캔한 종목 총 수
    market_status: str           # open / closed
    min_gap_pct: float
    generated_at: str
