"""관심종목 API 라우터."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from schemas.watchlist import (
    WatchlistToggleRequest, WatchlistToggleResponse, WatchlistItemResponse,
    WatchlistGroupCreate, WatchlistGroupUpdate, WatchlistGroupResponse,
    WatchlistMoveRequest, WatchlistGroupReorderRequest,
)
from services.watchlist_service import (
    get_watchlist_codes, get_watchlist_items, toggle_watchlist, delete_watchlist_item,
    get_groups, create_group, update_group, delete_group,
    move_items_to_group, reorder_groups, get_grouped_watchlist,
)

router = APIRouter()


@router.get("/codes", response_model=list[str])
def list_codes(db: Session = Depends(get_db)):
    """관심종목 코드 목록만 반환 (경량 조회)."""
    return get_watchlist_codes(db)


@router.get("", response_model=list[WatchlistItemResponse])
def list_items(db: Session = Depends(get_db)):
    """관심종목 전체 목록."""
    return get_watchlist_items(db)


@router.post("/toggle", response_model=WatchlistToggleResponse)
def toggle(req: WatchlistToggleRequest, db: Session = Depends(get_db)):
    """관심종목 토글 (있으면 삭제, 없으면 추가)."""
    is_watched = toggle_watchlist(db, req.stock_code, req.stock_name, req.group_id)
    return WatchlistToggleResponse(stock_code=req.stock_code, is_watched=is_watched)


@router.delete("/{stock_code}")
def delete(stock_code: str, db: Session = Depends(get_db)):
    """관심종목 명시적 삭제."""
    deleted = delete_watchlist_item(db, stock_code)
    return {"deleted": deleted}


# --- 그룹 엔드포인트 ---

@router.get("/groups", response_model=list[WatchlistGroupResponse])
def list_groups(db: Session = Depends(get_db)):
    """관심종목 그룹 목록."""
    return get_groups(db)


@router.post("/groups", response_model=WatchlistGroupResponse)
def create_group_endpoint(req: WatchlistGroupCreate, db: Session = Depends(get_db)):
    """관심종목 그룹 생성."""
    return create_group(db, req.name, req.color)


@router.put("/groups/{group_id}", response_model=WatchlistGroupResponse)
def update_group_endpoint(group_id: int, req: WatchlistGroupUpdate, db: Session = Depends(get_db)):
    """관심종목 그룹 수정."""
    result = update_group(db, group_id, req.name, req.color)
    if not result:
        raise HTTPException(status_code=404, detail="Group not found")
    return result


@router.delete("/groups/{group_id}")
def delete_group_endpoint(group_id: int, db: Session = Depends(get_db)):
    """관심종목 그룹 삭제. 그룹 내 종목은 미분류로 변경."""
    deleted = delete_group(db, group_id)
    return {"deleted": deleted}


@router.post("/move")
def move_to_group(req: WatchlistMoveRequest, db: Session = Depends(get_db)):
    """종목들을 특정 그룹으로 이동."""
    count = move_items_to_group(db, req.stock_codes, req.group_id)
    return {"moved": count}


@router.post("/groups/reorder")
def reorder(req: WatchlistGroupReorderRequest, db: Session = Depends(get_db)):
    """그룹 순서 재정렬."""
    reorder_groups(db, req.group_ids)
    return {"ok": True}


@router.get("/grouped")
def grouped(db: Session = Depends(get_db)):
    """그룹별로 분류된 관심종목 반환."""
    result = get_grouped_watchlist(db)
    return {
        "groups": [WatchlistGroupResponse.model_validate(g) for g in result["groups"]],
        "items": [WatchlistItemResponse.model_validate(i) for i in result["items"]],
    }
