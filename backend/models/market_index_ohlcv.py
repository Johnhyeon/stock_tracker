"""시장 지수 일봉 OHLCV 데이터 모델."""
from datetime import datetime, date

from sqlalchemy import Column, String, DateTime, BigInteger, Date, Index, Float

from core.database import Base


class MarketIndexOHLCV(Base):
    """시장 지수 일봉 OHLCV 데이터.

    KOSPI/KOSDAQ 지수의 일봉 데이터를 저장하여
    시장 급락 구간 탐지 및 회복 분석에 활용.
    """
    __tablename__ = "market_index_ohlcv"

    # 복합 기본키: index_code + trade_date
    index_code = Column(String(10), primary_key=True, nullable=False)  # "0001"=KOSPI, "1001"=KOSDAQ
    trade_date = Column(Date, primary_key=True, nullable=False)

    index_name = Column(String(50))
    open_value = Column(Float)
    high_value = Column(Float)
    low_value = Column(Float)
    close_value = Column(Float)
    volume = Column(BigInteger)
    trading_value = Column(BigInteger)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_market_index_ohlcv_date", "trade_date"),
        Index("ix_market_index_ohlcv_code", "index_code"),
    )

    def __repr__(self):
        return f"<MarketIndexOHLCV {self.index_code} {self.trade_date} C:{self.close_value}>"
