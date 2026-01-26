"""종목별 일봉 OHLCV 데이터 모델."""
from datetime import datetime, date

from sqlalchemy import Column, String, DateTime, BigInteger, Date, Index, Float

from core.database import Base


class StockOHLCV(Base):
    """종목별 일봉 OHLCV 데이터.

    일봉 시세 데이터를 DB에 저장하여:
    - KIS API 호출 최소화
    - 장기 이평선 계산 가능 (120일, 200일 등)
    - 과거 데이터 누적
    """
    __tablename__ = "stock_ohlcv"

    # 복합 기본키: stock_code + trade_date
    stock_code = Column(String(10), primary_key=True, nullable=False)
    trade_date = Column(Date, primary_key=True, nullable=False)

    # OHLCV 데이터
    open_price = Column(BigInteger, nullable=False)
    high_price = Column(BigInteger, nullable=False)
    low_price = Column(BigInteger, nullable=False)
    close_price = Column(BigInteger, nullable=False)
    volume = Column(BigInteger, nullable=False, default=0)

    # 메타 정보
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_stock_ohlcv_date", "trade_date"),
        Index("ix_stock_ohlcv_code", "stock_code"),
    )

    def __repr__(self):
        return f"<StockOHLCV {self.stock_code} {self.trade_date} C:{self.close_price}>"

    def to_chart_dict(self) -> dict:
        """lightweight-charts 형식으로 변환."""
        from datetime import datetime as dt
        timestamp = int(dt.combine(self.trade_date, dt.min.time()).timestamp())
        return {
            "time": timestamp,
            "open": float(self.open_price),
            "high": float(self.high_price),
            "low": float(self.low_price),
            "close": float(self.close_price),
            "volume": float(self.volume),
        }
