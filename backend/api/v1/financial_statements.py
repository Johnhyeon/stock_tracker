"""재무제표 API 라우터."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from services.financial_statement_service import FinancialStatementService
from schemas.financial_statement import (
    FinancialStatementResponse,
    FinancialStatementItem,
    FinancialSummaryResponse,
    FinancialRatios,
    FinancialCollectRequest,
    FinancialCollectResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{stock_code}/statements", response_model=FinancialStatementResponse)
async def get_financial_statements(
    stock_code: str,
    bsns_year: Optional[str] = Query(None, description="사업연도 (YYYY)"),
    reprt_code: Optional[str] = Query(None, description="보고서코드"),
    fs_div: Optional[str] = Query(None, description="CFS/OFS"),
    db: AsyncSession = Depends(get_async_db),
):
    """재무제표 원시 데이터 조회."""
    service = FinancialStatementService(db)
    data = await service.get_financial_data(stock_code, bsns_year, reprt_code, fs_div)

    items = [FinancialStatementItem(**d) for d in data]
    bs_items = [i for i in items if i.sj_div == "BS"]
    is_items = [i for i in items if i.sj_div == "IS"]
    cf_items = [i for i in items if i.sj_div == "CF"]

    return FinancialStatementResponse(
        stock_code=stock_code,
        bsns_year=bsns_year or "",
        reprt_code=reprt_code or "",
        fs_div=fs_div or "",
        items=items,
        bs_items=bs_items,
        is_items=is_items,
        cf_items=cf_items,
    )


@router.get("/{stock_code}/ratios", response_model=FinancialRatios)
async def get_financial_ratios(
    stock_code: str,
    bsns_year: Optional[str] = Query(None, description="사업연도"),
    reprt_code: str = Query("11011", description="보고서코드 (기본: 연간)"),
    db: AsyncSession = Depends(get_async_db),
):
    """재무비율 조회."""
    service = FinancialStatementService(db)

    if not bsns_year:
        from core.timezone import now_kst
        bsns_year = str(now_kst().year - 1)

    data = await service.get_financial_data(stock_code, bsns_year, reprt_code)
    if not data:
        raise HTTPException(status_code=404, detail="재무 데이터가 없습니다")

    ratios = service.compute_ratios(data)
    ratios.bsns_year = bsns_year
    ratios.reprt_code = reprt_code
    return ratios


@router.get("/{stock_code}/earnings-dates")
async def get_earnings_dates(
    stock_code: str,
    db: AsyncSession = Depends(get_async_db),
):
    """실적발표일 목록 조회 (차트 마커용)."""
    service = FinancialStatementService(db)
    return await service.get_earnings_dates(stock_code)


@router.get("/{stock_code}/summary", response_model=FinancialSummaryResponse)
async def get_financial_summary(
    stock_code: str,
    db: AsyncSession = Depends(get_async_db),
):
    """3개년 재무 통합 요약."""
    service = FinancialStatementService(db)
    return await service.get_financial_summary(stock_code)


@router.post("/{stock_code}/collect", response_model=FinancialCollectResponse)
async def collect_financial_statements(
    stock_code: str,
    request: FinancialCollectRequest = FinancialCollectRequest(),
    db: AsyncSession = Depends(get_async_db),
):
    """재무제표 수동 수집 트리거."""
    service = FinancialStatementService(db)
    result = await service.collect_financial_statements(stock_code, years=request.years)
    return FinancialCollectResponse(
        stock_code=stock_code,
        collected_count=result["collected_count"],
        years_collected=result.get("years_collected", []),
        message=result["message"],
    )


@router.post("/corp-codes/sync")
async def sync_corp_codes(
    db: AsyncSession = Depends(get_async_db),
):
    """DART 고유번호 매핑 동기화."""
    service = FinancialStatementService(db)
    count = await service.sync_corp_codes()
    return {"synced_count": count, "message": f"{count}개 고유번호 동기화 완료"}
