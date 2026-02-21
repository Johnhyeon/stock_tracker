"""기업 프로필 API."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from services.company_profile_service import CompanyProfileService
from schemas.company_profile import CompanyProfileResponse

router = APIRouter(prefix="/company-profile", tags=["company-profile"])

DART_REPORT_BASE_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="


def _to_response(profile) -> CompanyProfileResponse:
    """CompanyProfile 모델 → 응답 스키마 변환."""
    report_url = None
    if profile.report_rcept_no:
        report_url = f"{DART_REPORT_BASE_URL}{profile.report_rcept_no}"

    return CompanyProfileResponse(
        stock_code=profile.stock_code,
        stock_name=profile.stock_name,
        ceo_name=profile.ceo_name,
        industry_name=profile.industry_name,
        website=profile.website,
        business_summary=profile.business_summary,
        main_products=profile.main_products,
        sector=profile.sector,
        report_source=profile.report_source,
        report_url=report_url,
        last_updated=profile.last_updated.isoformat() if profile.last_updated else None,
    )


@router.get("/{stock_code}", response_model=CompanyProfileResponse)
async def get_profile(
    stock_code: str,
    db: AsyncSession = Depends(get_async_db),
):
    """기업 프로필 조회."""
    service = CompanyProfileService(db)
    profile = await service.get_profile(stock_code)
    if profile:
        return _to_response(profile)
    return CompanyProfileResponse(stock_code=stock_code)


@router.post("/{stock_code}/generate", response_model=CompanyProfileResponse)
async def generate_profile(
    stock_code: str,
    force: bool = False,
    db: AsyncSession = Depends(get_async_db),
):
    """기업 프로필 생성/갱신."""
    service = CompanyProfileService(db)
    profile = await service.generate_profile(stock_code, force=force)
    if profile:
        return _to_response(profile)
    return CompanyProfileResponse(stock_code=stock_code)
