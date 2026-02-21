"""시그널 스캐너 스키마."""
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ABCDPhase(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    UNKNOWN = "unknown"


class GapType(str, Enum):
    COMMON = "common"
    BREAKAWAY = "breakaway"
    RUNAWAY = "runaway"
    EXHAUSTION = "exhaustion"
    NONE = "none"


class MAAlignment(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    MIXED = "mixed"


class ChecklistItem(BaseModel):
    name: str
    label: str
    passed: bool
    score: float
    max_score: float
    detail: str = ""


class ScannerSignal(BaseModel):
    stock_code: str
    stock_name: str
    current_price: int
    total_score: float = 0.0
    grade: str = "D"
    abcd_phase: ABCDPhase = ABCDPhase.UNKNOWN
    ma_alignment: MAAlignment = MAAlignment.MIXED
    gap_type: GapType = GapType.NONE
    score_breakdown: dict = {}
    themes: list[str] = []
    # MA 값
    ma5: Optional[int] = None
    ma20: Optional[int] = None
    ma60: Optional[int] = None
    ma120: Optional[int] = None
    # 지표
    volume_ratio: Optional[float] = None
    has_record_volume: bool = False
    has_kkandolji: bool = False
    pullback_quality: Optional[float] = None
    ma20_distance_pct: Optional[float] = None
    bb_position: Optional[float] = None  # 0~1, 볼린저밴드 내 위치


class ScannerSignalResponse(BaseModel):
    signals: list[ScannerSignal]
    count: int
    generated_at: str


class ScannerDetailResponse(BaseModel):
    signal: ScannerSignal
    checklist: list[ChecklistItem]
    price_history: list[dict]
    generated_at: str


class ScannerAIAdviceResponse(BaseModel):
    stock_code: str
    stock_name: str
    advice: dict
    generated_at: str
