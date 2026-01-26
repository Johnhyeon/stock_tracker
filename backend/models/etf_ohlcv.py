"""ETF 일봉 OHLCV 데이터 모델."""
from datetime import datetime, date

from sqlalchemy import Column, String, DateTime, BigInteger, Date, Index, Float

from core.database import Base


class EtfOHLCV(Base):
    """ETF 일봉 OHLCV 데이터.

    테마별 대표 ETF의 일봉 시세 데이터를 저장하여:
    - 섹터 순환매 분석
    - 테마별 자금 흐름 파악
    - 등락률/거래대금 히트맵
    """
    __tablename__ = "etf_ohlcv"

    # 복합 기본키: etf_code + trade_date
    etf_code = Column(String(10), primary_key=True, nullable=False)
    trade_date = Column(Date, primary_key=True, nullable=False)

    # ETF 정보
    etf_name = Column(String(100), nullable=True)

    # OHLCV 데이터
    open_price = Column(BigInteger, nullable=False)
    high_price = Column(BigInteger, nullable=False)
    low_price = Column(BigInteger, nullable=False)
    close_price = Column(BigInteger, nullable=False)
    volume = Column(BigInteger, nullable=False, default=0)

    # 거래대금 (원)
    trading_value = Column(BigInteger, nullable=True)

    # 등락률 (전일 대비, %)
    change_rate = Column(Float, nullable=True)

    # 메타 정보
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_etf_ohlcv_date", "trade_date"),
        Index("ix_etf_ohlcv_code", "etf_code"),
    )

    def __repr__(self):
        return f"<EtfOHLCV {self.etf_code} {self.trade_date} C:{self.close_price}>"

    def to_dict(self) -> dict:
        """딕셔너리로 변환."""
        return {
            "etf_code": self.etf_code,
            "etf_name": self.etf_name,
            "trade_date": self.trade_date.isoformat() if self.trade_date else None,
            "open": self.open_price,
            "high": self.high_price,
            "low": self.low_price,
            "close": self.close_price,
            "volume": self.volume,
            "trading_value": self.trading_value,
            "change_rate": self.change_rate,
        }
