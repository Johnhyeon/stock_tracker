"""종목별 투자자 수급 데이터 모델."""
import uuid
from datetime import datetime, date

from sqlalchemy import Column, String, DateTime, BigInteger, Date, Index, Float
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class StockInvestorFlow(Base):
    """종목별 일자별 투자자 수급 데이터."""
    __tablename__ = "stock_investor_flows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 종목 정보
    stock_code = Column(String(10), nullable=False)
    stock_name = Column(String(100), nullable=True)
    flow_date = Column(Date, nullable=False)

    # 투자자별 순매수량 (양수: 순매수, 음수: 순매도)
    foreign_net = Column(BigInteger, default=0, nullable=False)      # 외국인 순매수
    institution_net = Column(BigInteger, default=0, nullable=False)  # 기관 순매수
    individual_net = Column(BigInteger, default=0, nullable=False)   # 개인 순매수

    # 투자자별 순매수금액 (단위: 원)
    foreign_net_amount = Column(BigInteger, default=0, nullable=False)      # 외국인 순매수금액
    institution_net_amount = Column(BigInteger, default=0, nullable=False)  # 기관 순매수금액
    individual_net_amount = Column(BigInteger, default=0, nullable=False)   # 개인 순매수금액

    # 수급 점수 (계산된 값, 0-100)
    flow_score = Column(Float, default=0.0, nullable=False)

    __table_args__ = (
        Index("ix_stock_flow_code_date", "stock_code", "flow_date", unique=True),
        Index("ix_stock_flow_date", "flow_date"),
    )

    def __repr__(self):
        return f"<StockInvestorFlow {self.stock_code} {self.flow_date} 외인:{self.foreign_net_amount/100000000:+.1f}억 기관:{self.institution_net_amount/100000000:+.1f}억>"
