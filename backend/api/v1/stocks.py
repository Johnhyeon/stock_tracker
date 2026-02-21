from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from pydantic import BaseModel

from core.database import get_db
from models import Stock
from utils.korean import is_chosung_only, extract_chosung

router = APIRouter()


class StockResponse(BaseModel):
    code: str
    name: str
    market: str
    stock_type: Optional[str]
    name_chosung: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/search", response_model=List[StockResponse])
def search_stocks(
    q: str = Query(..., min_length=1, description="검색어 (종목명, 코드, 또는 초성)"),
    limit: int = Query(default=15, le=50),
    db: Session = Depends(get_db),
):
    """
    종목 검색 API - 종목명, 코드, 또는 초성으로 검색

    Examples:
        - q=삼성 → 삼성전자, 삼성SDI 등
        - q=005930 → 삼성전자
        - q=ㅅㅅ → 삼성전자, 삼성SDI 등 (초성 검색)
        - q=ㅎㅇㄴㅅ → SK하이닉스
    """
    query = q.strip()
    # 와일드카드 이스케이프 (%, _ 문자를 리터럴로 처리)
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    # 초성 검색인지 확인
    if is_chosung_only(query):
        # 초성 검색: name_chosung 필드에서 검색
        results = (
            db.query(Stock)
            .filter(Stock.name_chosung.contains(query))
            .order_by(
                # 초성으로 시작하는 것 우선
                ~Stock.name_chosung.startswith(query),
                Stock.name,
            )
            .limit(limit)
            .all()
        )
    else:
        # 일반 검색: 코드 또는 이름으로 검색 (대소문자 무시)
        query_lower = query.lower()
        results = (
            db.query(Stock)
            .filter(
                or_(
                    Stock.code.ilike(f"%{escaped}%"),
                    Stock.name.ilike(f"%{escaped}%"),
                )
            )
            .order_by(
                # 정확히 일치하는 것 우선 (대소문자 무시)
                func.lower(Stock.code) != query_lower,
                func.lower(Stock.name) != query_lower,
                # 코드로 시작하는 것 우선
                ~Stock.code.ilike(f"{escaped}%"),
                # 이름순
                Stock.name,
            )
            .limit(limit)
            .all()
        )

    return results


@router.get("/count")
def get_stock_count(db: Session = Depends(get_db)):
    """등록된 종목 수 조회"""
    total = db.query(Stock).count()
    kospi = db.query(Stock).filter(Stock.market == 'KOSPI').count()
    kosdaq = db.query(Stock).filter(Stock.market == 'KOSDAQ').count()
    etf = db.query(Stock).filter(Stock.market == 'ETF').count()

    return {
        "total": total,
        "kospi": kospi,
        "kosdaq": kosdaq,
        "etf": etf,
    }
