"""기업 프로필 모델."""
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime

from core.database import Base


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    stock_code = Column(String(10), primary_key=True)
    stock_name = Column(String(100))
    ceo_name = Column(String(200))
    industry_name = Column(String(100))
    website = Column(String(500))
    business_summary = Column(Text)       # AI 생성 2~3문장
    main_products = Column(String(500))   # 쉼표 구분
    sector = Column(String(100))          # 반도체, 바이오 등
    report_source = Column(String(200))   # "분기보고서 (2024.09)" 등
    report_rcept_no = Column(String(20))  # DART 접수번호 (URL 생성용)
    last_updated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
