"""관심종목 서비스."""
from typing import Optional

from sqlalchemy.orm import Session

from models.watchlist import WatchlistItem
from models.watchlist_group import WatchlistGroup


def get_watchlist_codes(db: Session) -> list[str]:
    """관심종목 코드 목록만 반환."""
    rows = db.query(WatchlistItem.stock_code).order_by(WatchlistItem.created_at.desc()).all()
    return [r[0] for r in rows]


def get_watchlist_items(db: Session) -> list[WatchlistItem]:
    """관심종목 전체 목록 반환."""
    return db.query(WatchlistItem).order_by(WatchlistItem.created_at.desc()).all()


def toggle_watchlist(db: Session, stock_code: str, stock_name: Optional[str] = None, group_id: Optional[int] = None) -> bool:
    """관심종목 토글. 반환값: is_watched (추가=True, 삭제=False)."""
    existing = db.query(WatchlistItem).filter(WatchlistItem.stock_code == stock_code).first()
    if existing:
        db.delete(existing)
        db.commit()
        return False
    else:
        item = WatchlistItem(stock_code=stock_code, stock_name=stock_name, group_id=group_id)
        db.add(item)
        db.commit()
        return True


def delete_watchlist_item(db: Session, stock_code: str) -> bool:
    """관심종목 삭제. 반환값: 삭제 성공 여부."""
    item = db.query(WatchlistItem).filter(WatchlistItem.stock_code == stock_code).first()
    if item:
        db.delete(item)
        db.commit()
        return True
    return False


# --- 그룹 관련 함수 ---

def get_groups(db: Session) -> list[WatchlistGroup]:
    """관심종목 그룹 목록 반환."""
    return db.query(WatchlistGroup).order_by(WatchlistGroup.order, WatchlistGroup.id).all()


def create_group(db: Session, name: str, color: str = "#6366f1") -> WatchlistGroup:
    """관심종목 그룹 생성."""
    max_order = db.query(WatchlistGroup.order).order_by(WatchlistGroup.order.desc()).first()
    new_order = (max_order[0] + 1) if max_order else 0
    group = WatchlistGroup(name=name, color=color, order=new_order)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def update_group(db: Session, group_id: int, name: str = None, color: str = None) -> WatchlistGroup | None:
    """관심종목 그룹 수정."""
    group = db.query(WatchlistGroup).filter(WatchlistGroup.id == group_id).first()
    if not group:
        return None
    if name is not None:
        group.name = name
    if color is not None:
        group.color = color
    db.commit()
    db.refresh(group)
    return group


def delete_group(db: Session, group_id: int) -> bool:
    """관심종목 그룹 삭제. 그룹 내 종목은 미분류로 변경."""
    group = db.query(WatchlistGroup).filter(WatchlistGroup.id == group_id).first()
    if not group:
        return False
    # Ungroup items in this group
    db.query(WatchlistItem).filter(WatchlistItem.group_id == group_id).update({WatchlistItem.group_id: None})
    db.delete(group)
    db.commit()
    return True


def move_items_to_group(db: Session, stock_codes: list[str], group_id: int | None) -> int:
    """종목들을 특정 그룹으로 이동. group_id=None이면 미분류."""
    count = db.query(WatchlistItem).filter(WatchlistItem.stock_code.in_(stock_codes)).update(
        {WatchlistItem.group_id: group_id}, synchronize_session=False
    )
    db.commit()
    return count


def reorder_groups(db: Session, group_ids: list[int]) -> None:
    """그룹 순서 재정렬."""
    for i, gid in enumerate(group_ids):
        db.query(WatchlistGroup).filter(WatchlistGroup.id == gid).update({WatchlistGroup.order: i})
    db.commit()


def get_grouped_watchlist(db: Session) -> dict:
    """그룹별로 분류된 관심종목 반환."""
    groups = get_groups(db)
    items = get_watchlist_items(db)

    result = {
        "groups": groups,
        "items": items,
        "ungrouped": [i for i in items if i.group_id is None],
    }
    return result
