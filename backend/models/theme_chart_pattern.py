"""테마 종목 차트 패턴 모델."""
import uuid
from datetime import datetime, date
from enum import Enum

from sqlalchemy import Column, String, DateTime, Integer, Date, Index, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB

from core.database import Base


class ChartPatternType(str, Enum):
    """차트 패턴 유형."""
    RANGE_BOUND = "range_bound"  # 횡보/박스권
    DOUBLE_BOTTOM = "double_bottom"  # 쌍바닥
    TRIPLE_BOTTOM = "triple_bottom"  # 삼중바닥
    CONVERGING = "converging"  # 수렴
    PRE_BREAKOUT = "pre_breakout"  # 돌파 직전


class ThemeChartPattern(Base):
    """테마 종목의 차트 패턴 감지 결과."""
    __tablename__ = "theme_chart_patterns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 테마 및 종목 정보
    theme_name = Column(String(100), nullable=False)
    stock_code = Column(String(20), nullable=False)
    stock_name = Column(String(100), nullable=False)

    # 패턴 정보
    pattern_type = Column(String(30), nullable=False)  # ChartPatternType 값
    confidence = Column(Integer, nullable=False)  # 신뢰도 0-100

    # 패턴 상세 데이터
    pattern_data = Column(JSONB, default=dict)  # 패턴별 상세 데이터
    # range_bound: {"support": 10000, "resistance": 12000, "touch_count": 5}
    # double_bottom: {"bottom1_price": 10000, "bottom1_date": "2024-01-01", "bottom2_price": 10100, ...}
    # converging: {"high_slope": -0.5, "low_slope": 0.3, "apex_date": "2024-03-01"}
    # pre_breakout: {"resistance": 12000, "current_price": 11500, "volume_ratio": 1.5}

    # 분석 날짜 및 상태
    analysis_date = Column(Date, nullable=False)  # 분석 수행일
    is_active = Column(Boolean, default=True, nullable=False)  # 패턴 유효 여부

    # 가격 정보 (분석 시점)
    current_price = Column(Integer, nullable=True)  # 현재가
    price_from_support_pct = Column(Float, nullable=True)  # 지지선 대비 %
    price_from_resistance_pct = Column(Float, nullable=True)  # 저항선 대비 %

    __table_args__ = (
        Index("ix_theme_chart_pattern_theme", "theme_name"),
        Index("ix_theme_chart_pattern_stock", "stock_code"),
        Index("ix_theme_chart_pattern_type", "pattern_type"),
        Index("ix_theme_chart_pattern_active", "is_active", "analysis_date"),
        Index("ix_theme_chart_pattern_theme_stock_date", "theme_name", "stock_code", "analysis_date"),
    )

    def __repr__(self):
        return f"<ThemeChartPattern {self.theme_name}/{self.stock_name} - {self.pattern_type}({self.confidence}%)>"
