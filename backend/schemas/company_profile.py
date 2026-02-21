"""기업 프로필 스키마."""
from typing import Optional

from pydantic import BaseModel


class CompanyProfileResponse(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    ceo_name: Optional[str] = None
    industry_name: Optional[str] = None
    website: Optional[str] = None
    business_summary: Optional[str] = None
    main_products: Optional[str] = None
    sector: Optional[str] = None
    report_source: Optional[str] = None
    report_url: Optional[str] = None
    last_updated: Optional[str] = None

    class Config:
        from_attributes = True
