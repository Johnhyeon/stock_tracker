"""상승 차트 패턴 라이브러리 모델."""
import uuid
from datetime import datetime, date
from enum import Enum

from sqlalchemy import Column, String, DateTime, Date, Float, Integer, Boolean, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB

from core.database import Base


class RisingPatternType(str, Enum):
    SURGE = "surge"                   # 급등형: 단기간 폭발적 상승
    BREAKOUT = "breakout"             # 돌파형: 횡보 후 저항선 돌파
    STAIRCASE = "staircase"           # 계단식: 상승→횡보 반복
    STEADY_UPTREND = "steady_uptrend" # 완만한 추세: 장기간 꾸준한 상승
    V_RECOVERY = "v_recovery"         # V자 반등: 급락 후 빠른 회복


class RisingChartPattern(Base):
    """감지된 상승 차트 패턴."""
    __tablename__ = "rising_chart_patterns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 종목 정보
    stock_code = Column(String(10), nullable=False)
    stock_name = Column(String(100), nullable=False)

    # 패턴 분류
    pattern_type = Column(String(20), nullable=False)  # RisingPatternType 값
    confidence = Column(Float, default=0.0)             # 신뢰도 0-100
    grade = Column(String(1), default="D")              # A/B/C/D

    # 기간
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    duration_days = Column(Integer, nullable=False)

    # 수익
    start_price = Column(Float, nullable=False)
    end_price = Column(Float, nullable=False)
    total_return_pct = Column(Float, nullable=False)

    # 패턴 상세 데이터 (JSONB)
    pattern_data = Column(JSONB, default=dict)

    # 공통 지표
    avg_volume_change_pct = Column(Float, default=0.0)      # 평균 거래량 변화율
    ma_alignment_at_start = Column(String(20), default="")  # 정배열/역배열/혼합
    foreign_net_during = Column(Float, default=0.0)         # 기간 중 외국인 순매수
    institution_net_during = Column(Float, default=0.0)     # 기간 중 기관 순매수

    # 상승 전 차트 분석 (JSONB)
    pre_analysis = Column(JSONB, default=dict)
    # 촉발 요인 (JSONB)
    trigger_info = Column(JSONB, default=dict)

    # 메타
    analysis_date = Column(Date, default=date.today)
    is_active = Column(Boolean, default=True)
    user_note = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_rcp_stock_code", "stock_code"),
        Index("ix_rcp_pattern_type", "pattern_type"),
        Index("ix_rcp_grade", "grade"),
        Index("ix_rcp_total_return", "total_return_pct"),
        Index("ix_rcp_date_range", "start_date", "end_date"),
    )

    def __repr__(self):
        return f"<RisingChartPattern {self.stock_code} {self.pattern_type} {self.total_return_pct:+.1f}%>"
