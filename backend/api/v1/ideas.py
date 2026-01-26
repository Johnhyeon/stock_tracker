import re
from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from core.database import get_db
from models import IdeaStatus, IdeaType, Stock
from schemas import (
    IdeaCreate,
    IdeaUpdate,
    IdeaResponse,
    IdeaWithPositions,
    ExitCheckResult,
    PositionCreate,
    PositionResponse,
)
from services import IdeaService, PositionService


class IdeaStockItem(BaseModel):
    code: str
    name: str
    ticker_label: str  # 원래 tickers 형식 (예: "삼성전자(005930)")

router = APIRouter()


@router.post("", response_model=IdeaResponse, status_code=201)
def create_idea(data: IdeaCreate, db: Session = Depends(get_db)):
    service = IdeaService(db)
    idea = service.create(data)
    return idea


@router.get("", response_model=List[IdeaResponse])
def list_ideas(
    status: Optional[IdeaStatus] = None,
    type: Optional[IdeaType] = Query(None, alias="type"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    service = IdeaService(db)
    return service.get_all(status=status, idea_type=type, skip=skip, limit=limit)


@router.get("/stocks/all", response_model=List[IdeaStockItem])
def get_all_idea_stocks(db: Session = Depends(get_db)):
    """아이디어에 등록된 모든 종목 목록 반환 (중복 제거)"""
    service = IdeaService(db)
    ideas = service.get_all()

    # 모든 tickers 수집 및 종목코드 추출
    stock_codes_map = {}  # code -> ticker_label
    for idea in ideas:
        for ticker in idea.tickers:
            match = re.search(r'\((\d{6})\)', ticker)
            if match:
                code = match.group(1)
                if code not in stock_codes_map:
                    stock_codes_map[code] = ticker

    # Stock 테이블에서 종목명 조회
    if not stock_codes_map:
        return []

    stocks = db.query(Stock).filter(Stock.code.in_(stock_codes_map.keys())).all()
    stock_names = {s.code: s.name for s in stocks}

    result = []
    for code, ticker_label in stock_codes_map.items():
        name = stock_names.get(code, "")
        # ticker_label에서 이름 추출 (괄호 앞 부분)
        if not name:
            name_match = re.match(r'(.+?)\(\d{6}\)', ticker_label)
            name = name_match.group(1) if name_match else code
        result.append(IdeaStockItem(code=code, name=name, ticker_label=ticker_label))

    return sorted(result, key=lambda x: x.name)


@router.get("/{idea_id}", response_model=IdeaWithPositions)
def get_idea(idea_id: UUID, db: Session = Depends(get_db)):
    import asyncio
    from decimal import Decimal
    from services.price_service import get_price_service

    service = IdeaService(db)
    idea = service.get(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="아이디어를 찾을 수 없습니다.")

    # 열린 포지션의 종목코드 수집
    open_positions = [p for p in idea.positions if p.is_open]
    stock_codes = set()
    for p in open_positions:
        code = service._extract_stock_code_from_ticker(p.ticker)
        if code:
            stock_codes.add(code)

    # 현재가 조회
    current_prices = {}
    if stock_codes:
        try:
            price_service = get_price_service()
            current_prices = asyncio.run(price_service.get_multiple_prices(list(stock_codes)))
        except Exception:
            pass

    # 종목명 조회
    stock_names = {}
    if stock_codes:
        stocks = db.query(Stock).filter(Stock.code.in_(stock_codes)).all()
        stock_names = {s.code: s.name for s in stocks}

    positions = []
    total_invested = Decimal("0")
    total_return_pcts = []

    for p in idea.positions:
        invested = p.entry_price * p.quantity
        code = service._extract_stock_code_from_ticker(p.ticker)

        current_price = None
        unrealized_profit = None
        unrealized_return_pct = None
        stock_name = stock_names.get(code) if code else None

        if p.is_open:
            total_invested += invested
            if code and code in current_prices:
                price_data = current_prices[code]
                cp = price_data.get("current_price")
                if cp is not None:
                    current_price = Decimal(str(cp))
                    current_value = current_price * p.quantity
                    unrealized_profit = float(current_value - invested)
                    unrealized_return_pct = float((current_value - invested) / invested * 100)
                    total_return_pcts.append(unrealized_return_pct)
                    if not stock_name:
                        stock_name = price_data.get("stock_name")

        positions.append({
            "id": p.id,
            "ticker": p.ticker,
            "stock_name": stock_name,
            "entry_price": p.entry_price,
            "entry_date": p.entry_date,
            "quantity": p.quantity,
            "exit_price": p.exit_price,
            "exit_date": p.exit_date,
            "exit_reason": p.exit_reason,
            "days_held": p.days_held,
            "is_open": p.is_open,
            "current_price": current_price,
            "unrealized_profit": unrealized_profit,
            "unrealized_return_pct": unrealized_return_pct,
            "realized_return_pct": p.realized_return_pct,
        })

    total_return_pct = sum(total_return_pcts) / len(total_return_pcts) if total_return_pcts else None

    return {
        **idea.__dict__,
        "metadata": idea.metadata_,
        "positions": positions,
        "total_invested": float(total_invested),
        "total_return_pct": total_return_pct,
    }


@router.put("/{idea_id}", response_model=IdeaResponse)
@router.patch("/{idea_id}", response_model=IdeaResponse)
def update_idea(idea_id: UUID, data: IdeaUpdate, db: Session = Depends(get_db)):
    service = IdeaService(db)
    idea = service.update(idea_id, data)
    if not idea:
        raise HTTPException(status_code=404, detail="아이디어를 찾을 수 없습니다.")
    return idea


@router.delete("/{idea_id}", status_code=204)
def delete_idea(idea_id: UUID, db: Session = Depends(get_db)):
    service = IdeaService(db)
    if not service.delete(idea_id):
        raise HTTPException(status_code=404, detail="아이디어를 찾을 수 없습니다.")


@router.post("/{idea_id}/positions", response_model=PositionResponse, status_code=201)
def create_position(idea_id: UUID, data: PositionCreate, db: Session = Depends(get_db)):
    service = PositionService(db)
    position = service.create(idea_id, data)
    if not position:
        raise HTTPException(status_code=404, detail="아이디어를 찾을 수 없습니다.")
    return position


@router.get("/{idea_id}/exit-check", response_model=ExitCheckResult)
def check_exit_criteria(idea_id: UUID, db: Session = Depends(get_db)):
    service = IdeaService(db)
    result = service.check_exit_criteria(idea_id)
    if not result:
        raise HTTPException(status_code=404, detail="아이디어를 찾을 수 없습니다.")
    return result
