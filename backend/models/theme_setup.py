"""테마 셋업 종합 점수 모델."""
import uuid
from datetime import datetime, date

from sqlalchemy import Column, String, DateTime, Integer, Date, Index, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB

from core.database import Base


class ThemeSetup(Base):
    """테마의 종합 셋업 점수 (자리 잡는 테마 감지용)."""
    __tablename__ = "theme_setups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 테마 및 날짜
    theme_name = Column(String(100), nullable=False)
    setup_date = Column(Date, nullable=False)

    # 순위
    rank = Column(Integer, nullable=True)  # 전체 테마 중 순위

    # 개별 점수 (각 항목 100점 만점 기준으로 환산 후 가중합)
    news_momentum_score = Column(Float, default=0.0, nullable=False)  # 뉴스 모멘텀 (25%)
    chart_pattern_score = Column(Float, default=0.0, nullable=False)  # 차트 패턴 (30%)
    mention_score = Column(Float, default=0.0, nullable=False)  # 기존 언급 점수 (20%)
    price_action_score = Column(Float, default=0.0, nullable=False)  # 가격 액션 (10%)
    investor_flow_score = Column(Float, default=0.0, nullable=False)  # 수급 점수 (15%)

    # 종합 점수 (0-100)
    total_setup_score = Column(Float, default=0.0, nullable=False)

    # 세부 데이터
    score_breakdown = Column(JSONB, default=dict)  # 점수 산출 근거
    # {
    #   "news": {"7d_count": 15, "wow_change": 50, "source_diversity": 5},
    #   "chart": {"pattern_ratio": 0.4, "avg_confidence": 75, "patterns": ["double_bottom", "converging"]},
    #   "mention": {"youtube_count": 3, "expert_count": 2},
    #   "price": {"7d_avg_change": 2.5, "volume_change": 30},
    #   "flow": {"foreign_net_sum": 1000000, "institution_net_sum": 500000, "positive_stocks": 5, "total_stocks": 10}
    # }

    # 대표 종목 (셋업 상태인 종목들)
    top_stocks = Column(JSONB, default=list)  # 상위 종목 리스트
    # [{"code": "005930", "name": "삼성전자", "pattern": "double_bottom", "confidence": 85}, ...]

    # 추가 메타데이터
    total_stocks_in_theme = Column(Integer, default=0)  # 테마 내 전체 종목 수
    stocks_with_pattern = Column(Integer, default=0)  # 패턴 감지된 종목 수
    is_emerging = Column(Integer, default=0)  # 이머징 테마 여부 (0: 일반, 1: 이머징)

    __table_args__ = (
        Index("ix_theme_setup_date", "setup_date"),
        Index("ix_theme_setup_theme_date", "theme_name", "setup_date", unique=True),
        Index("ix_theme_setup_total_score", "total_setup_score"),
        Index("ix_theme_setup_rank", "setup_date", "rank"),
        Index("ix_theme_setup_emerging", "setup_date", "is_emerging", "total_setup_score"),
    )

    def __repr__(self):
        return f"<ThemeSetup {self.theme_name} {self.setup_date} - {self.total_setup_score:.1f}점 (#{self.rank})>"
