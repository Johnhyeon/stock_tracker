from sqlalchemy import Column, String, Index
from sqlalchemy.orm import validates
from core.database import Base
from utils.korean import extract_chosung


class Stock(Base):
    __tablename__ = "stocks"

    code = Column(String(10), primary_key=True)
    name = Column(String(100), nullable=False)
    market = Column(String(20), nullable=False)  # KOSPI, KOSDAQ, ETF
    stock_type = Column(String(20), nullable=True)  # 보통주, 우선주, ETF 등
    name_chosung = Column(String(100), nullable=True)  # 초성 검색용 (예: "ㅅㅅㅈㅈ")

    __table_args__ = (
        Index('ix_stocks_name', 'name'),
        Index('ix_stocks_chosung', 'name_chosung'),
    )

    @validates('name')
    def validate_name(self, key, name):
        """이름 설정 시 초성도 자동 생성."""
        self.name_chosung = extract_chosung(name)
        return name

    def __repr__(self):
        return f"<Stock {self.code} - {self.name}>"
