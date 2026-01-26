"""공시 API 엔드포인트."""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy.orm import Session

from core.database import get_db
from models.disclosure import DisclosureType, DisclosureImportance
from services.disclosure_service import DisclosureService
from schemas.disclosure import (
    DisclosureResponse,
    DisclosureListResponse,
    DisclosureCollectRequest,
    DisclosureCollectResponse,
    DisclosureStatsResponse,
)

router = APIRouter()


@router.get("", response_model=DisclosureListResponse)
def list_disclosures(
    stock_code: Optional[str] = Query(default=None, description="종목코드 필터"),
    importance: Optional[DisclosureImportance] = Query(default=None, description="중요도 필터"),
    disclosure_type: Optional[DisclosureType] = Query(default=None, description="유형 필터"),
    unread_only: bool = Query(default=False, description="읽지 않은 것만"),
    my_ideas_only: bool = Query(default=False, description="내 아이디어 종목만"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db),
):
    """공시 목록 조회.

    my_ideas_only=true로 설정하면 활성/관찰 중인 아이디어의 종목만 조회합니다.
    """
    service = DisclosureService(db)
    disclosures = service.get_all(
        stock_code=stock_code,
        importance=importance,
        disclosure_type=disclosure_type,
        unread_only=unread_only,
        my_ideas_only=my_ideas_only,
        skip=skip,
        limit=limit,
    )

    return DisclosureListResponse(
        items=[DisclosureResponse.model_validate(d) for d in disclosures],
        total=len(disclosures),
        skip=skip,
        limit=limit,
    )


@router.get("/stats", response_model=DisclosureStatsResponse)
def get_disclosure_stats(
    stock_code: Optional[str] = Query(default=None, description="종목코드 필터"),
    db: Session = Depends(get_db),
):
    """공시 통계 조회."""
    service = DisclosureService(db)
    stats = service.get_stats(stock_code=stock_code)
    return DisclosureStatsResponse(**stats)


@router.get("/{disclosure_id}", response_model=DisclosureResponse)
def get_disclosure(
    disclosure_id: UUID,
    db: Session = Depends(get_db),
):
    """공시 상세 조회."""
    service = DisclosureService(db)
    disclosure = service.get(disclosure_id)
    if not disclosure:
        raise HTTPException(status_code=404, detail="Disclosure not found")
    return DisclosureResponse.model_validate(disclosure)


@router.post("/{disclosure_id}/read", response_model=DisclosureResponse)
def mark_disclosure_read(
    disclosure_id: UUID,
    db: Session = Depends(get_db),
):
    """공시 읽음 처리."""
    service = DisclosureService(db)
    disclosure = service.mark_as_read(disclosure_id)
    if not disclosure:
        raise HTTPException(status_code=404, detail="Disclosure not found")
    return DisclosureResponse.model_validate(disclosure)


@router.post("/read-all")
def mark_all_disclosures_read(
    stock_code: Optional[str] = Query(default=None, description="종목코드 필터"),
    db: Session = Depends(get_db),
):
    """모든 공시 읽음 처리."""
    service = DisclosureService(db)
    count = service.mark_all_as_read(stock_code=stock_code)
    return {"marked_count": count}


@router.post("/collect", response_model=DisclosureCollectResponse)
async def collect_disclosures(
    request: DisclosureCollectRequest,
    db: Session = Depends(get_db),
):
    """공시 수집 (수동 트리거).

    DART API에서 공시를 수집하여 DB에 저장합니다.
    """
    service = DisclosureService(db)
    try:
        result = await service.collect_disclosures(
            bgn_de=request.bgn_de,
            end_de=request.end_de,
            stock_codes=request.stock_codes,
            min_importance=request.min_importance,
        )
        return DisclosureCollectResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"공시 수집 실패: {str(e)}")
