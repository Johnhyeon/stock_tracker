"""DART 고유번호 ↔ 종목코드 매핑 모델."""
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Index
from core.database import Base


class DartCorpCode(Base):
    """DART 고유번호(8자리) ↔ 종목코드(6자리) 매핑 테이블."""

    __tablename__ = "dart_corp_codes"

    corp_code = Column(String(8), primary_key=True, comment="DART 고유번호")
    corp_name = Column(String(200), nullable=False, comment="회사명")
    stock_code = Column(String(6), nullable=True, comment="종목코드 (상장사만)")
    modify_date = Column(String(8), nullable=True, comment="최종변경일 (YYYYMMDD)")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_dart_corp_codes_stock_code", "stock_code"),
    )

    def __repr__(self):
        return f"<DartCorpCode {self.corp_code} ({self.corp_name}) stock={self.stock_code}>"
