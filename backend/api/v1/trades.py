"""매매 기록 API."""
import re
import csv
import io
import logging
import uuid as uuid_mod
from collections import defaultdict
from datetime import date as date_cls, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, extract

from core.database import get_db
from models import Trade, TradeType, Position, InvestmentIdea, IdeaStatus, Stock

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_stock_name(db: Session, ticker: str) -> str | None:
    """종목코드로 종목명 조회."""
    stock = db.query(Stock).filter(Stock.code == ticker).first()
    return stock.name if stock else None


def _trade_to_dict(trade: Trade) -> dict:
    price = round(trade.price) if trade.price is not None else 0
    return {
        "id": str(trade.id),
        "position_id": str(trade.position_id),
        "trade_type": trade.trade_type.value if trade.trade_type else None,
        "trade_date": trade.trade_date.isoformat() if trade.trade_date else None,
        "price": price,
        "quantity": trade.quantity,
        "total_amount": price * trade.quantity,
        "realized_profit": round(trade.realized_profit) if trade.realized_profit is not None else None,
        "realized_return_pct": float(trade.realized_return_pct) if trade.realized_return_pct is not None else None,
        "avg_price_after": round(trade.avg_price_after) if trade.avg_price_after else None,
        "quantity_after": trade.quantity_after,
        "reason": trade.reason,
        "notes": trade.notes,
        "created_at": trade.created_at.isoformat() if trade.created_at else None,
        "stock_code": trade.stock_code,
        "stock_name": trade.stock_name,
    }


@router.get("")
def list_trades(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    trade_type: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    stock_code: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """매매 기록 목록 조회."""
    query = db.query(Trade).order_by(desc(Trade.trade_date), desc(Trade.created_at))

    if trade_type:
        query = query.filter(Trade.trade_type == trade_type)
    if start_date:
        query = query.filter(Trade.trade_date >= start_date)
    if end_date:
        query = query.filter(Trade.trade_date <= end_date)
    if stock_code:
        query = query.filter(Trade.stock_code == stock_code)

    total_count = query.count()
    trades = query.offset(offset).limit(limit).all()

    return {
        "trades": [_trade_to_dict(t) for t in trades],
        "total_count": total_count,
    }


@router.get("/analysis")
def get_analysis(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """매매 분석 통계."""
    query = db.query(Trade).order_by(Trade.trade_date, Trade.created_at)
    if start_date:
        query = query.filter(Trade.trade_date >= start_date)
    if end_date:
        query = query.filter(Trade.trade_date <= end_date)
    trades = query.all()

    # 요약
    buy_types = {TradeType.BUY, TradeType.ADD_BUY}
    sell_types = {TradeType.SELL, TradeType.PARTIAL_SELL}

    buy_trades = [t for t in trades if t.trade_type in buy_types]
    sell_trades = [t for t in trades if t.trade_type in sell_types]

    # 실현손익이 있는 매도 거래
    realized_trades = [t for t in sell_trades if t.realized_profit is not None]
    winning = [t for t in realized_trades if float(t.realized_profit) > 0]
    losing = [t for t in realized_trades if float(t.realized_profit) <= 0]

    total_realized = sum(float(t.realized_profit) for t in realized_trades) if realized_trades else 0
    avg_return = (
        sum(float(t.realized_return_pct) for t in realized_trades) / len(realized_trades)
        if realized_trades else 0
    )

    summary = {
        "total_trades": len(trades),
        "buy_count": len(buy_trades),
        "sell_count": len(sell_trades),
        "total_buy_amount": round(sum(float(t.price) * t.quantity for t in buy_trades)),
        "total_sell_amount": round(sum(float(t.price) * t.quantity for t in sell_trades)),
        "total_realized_profit": round(total_realized),
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate": (len(winning) / len(realized_trades) * 100) if realized_trades else 0,
        "avg_profit_per_trade": round(total_realized / len(realized_trades)) if realized_trades else 0,
        "avg_return_pct": avg_return,
    }

    # 월별 통계
    monthly = defaultdict(lambda: {
        "trade_count": 0, "buy_count": 0, "sell_count": 0,
        "realized_profit": 0, "wins": 0, "total_realized": 0,
    })

    for t in trades:
        month_key = t.trade_date.strftime("%Y-%m")
        monthly[month_key]["trade_count"] += 1
        if t.trade_type in buy_types:
            monthly[month_key]["buy_count"] += 1
        else:
            monthly[month_key]["sell_count"] += 1
            if t.realized_profit is not None:
                profit = float(t.realized_profit)
                monthly[month_key]["realized_profit"] += profit
                monthly[month_key]["total_realized"] += 1
                if profit > 0:
                    monthly[month_key]["wins"] += 1

    monthly_stats = []
    for month in sorted(monthly.keys(), reverse=True):
        m = monthly[month]
        monthly_stats.append({
            "month": month,
            "trade_count": m["trade_count"],
            "buy_count": m["buy_count"],
            "sell_count": m["sell_count"],
            "realized_profit": round(m["realized_profit"]),
            "win_rate": (m["wins"] / m["total_realized"] * 100) if m["total_realized"] else 0,
        })

    # 종목별 통계
    ticker_data = defaultdict(lambda: {
        "stock_name": None, "trade_count": 0,
        "total_buy_amount": 0, "total_sell_amount": 0,
        "realized_profit": 0, "return_pcts": [],
        "wins": 0, "losses": 0,
    })

    for t in trades:
        ticker = t.stock_code or "UNKNOWN"
        td = ticker_data[ticker]
        td["trade_count"] += 1
        if t.stock_name:
            td["stock_name"] = t.stock_name

        if t.trade_type in buy_types:
            td["total_buy_amount"] += float(t.price) * t.quantity
        else:
            td["total_sell_amount"] += float(t.price) * t.quantity
            if t.realized_profit is not None:
                profit = float(t.realized_profit)
                td["realized_profit"] += profit
                if t.realized_return_pct is not None:
                    td["return_pcts"].append(float(t.realized_return_pct))
                if profit > 0:
                    td["wins"] += 1
                else:
                    td["losses"] += 1

    ticker_stats = []
    for ticker in sorted(ticker_data.keys(), key=lambda k: ticker_data[k]["realized_profit"], reverse=True):
        td = ticker_data[ticker]
        ticker_stats.append({
            "ticker": ticker,
            "stock_name": td["stock_name"],
            "trade_count": td["trade_count"],
            "total_buy_amount": round(td["total_buy_amount"]),
            "total_sell_amount": round(td["total_sell_amount"]),
            "realized_profit": round(td["realized_profit"]),
            "avg_return_pct": sum(td["return_pcts"]) / len(td["return_pcts"]) if td["return_pcts"] else 0,
            "winning_trades": td["wins"],
            "losing_trades": td["losses"],
            "win_rate": (td["wins"] / (td["wins"] + td["losses"]) * 100) if (td["wins"] + td["losses"]) else 0,
        })

    # 최근 거래
    recent = trades[-50:][::-1]

    return {
        "summary": summary,
        "monthly_stats": monthly_stats,
        "ticker_stats": ticker_stats,
        "recent_trades": [_trade_to_dict(t) for t in recent],
    }


@router.get("/position/{position_id}")
def get_trades_by_position(
    position_id: UUID,
    db: Session = Depends(get_db),
):
    """특정 포지션의 매매 기록."""
    trades = (
        db.query(Trade)
        .filter(Trade.position_id == position_id)
        .order_by(Trade.trade_date, Trade.created_at)
        .all()
    )

    return {
        "trades": [_trade_to_dict(t) for t in trades],
        "total_count": len(trades),
    }


@router.put("/{trade_id}")
def update_trade(trade_id: UUID, data: dict, db: Session = Depends(get_db)):
    """매매 기록 수정."""
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="매매 기록을 찾을 수 없습니다.")

    allowed_fields = {"price", "quantity", "trade_date", "reason", "notes"}
    for field, value in data.items():
        if field in allowed_fields and value is not None:
            if field == "price":
                from decimal import Decimal
                value = Decimal(str(value))
            elif field == "trade_date":
                from datetime import date as date_cls
                value = date_cls.fromisoformat(value)
            setattr(trade, field, value)

    db.commit()
    db.refresh(trade)
    return _trade_to_dict(trade)


@router.delete("/{trade_id}")
def delete_trade(trade_id: UUID, db: Session = Depends(get_db)):
    """매매 기록 삭제."""
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="매매 기록을 찾을 수 없습니다.")

    db.delete(trade)
    db.commit()
    return {"message": "삭제 완료"}


@router.post("/backfill")
def backfill_trades(db: Session = Depends(get_db)):
    """기존 포지션 데이터로부터 매매 기록 생성 (1회성).

    이미 Trade 기록이 있는 포지션은 건너뜁니다.
    """
    positions = db.query(Position).all()
    created_count = 0

    for pos in positions:
        # 이미 기록이 있으면 스킵
        existing = db.query(Trade).filter(Trade.position_id == pos.id).first()
        if existing:
            continue

        # 종목명 조회
        stock_name = _resolve_stock_name(db, pos.ticker)

        # 최초 매수 기록
        # notes에서 추가매수/부분매도 파싱하여 원래 수량 역산
        original_qty = pos.quantity
        original_price = pos.entry_price
        add_buys = []
        partial_sells = []

        if pos.notes:
            # 추가매수 파싱: [추가매수] 2025-01-15: 100주 @ 50,000원
            for m in re.finditer(
                r'\[추가매수\]\s*(\d{4}-\d{2}-\d{2}):\s*(\d+)주\s*@\s*([\d,]+)원', pos.notes
            ):
                add_buys.append({
                    "date": m.group(1),
                    "quantity": int(m.group(2)),
                    "price": float(m.group(3).replace(",", "")),
                })

            # 부분매도 파싱: [부분매도] 2025-01-20: 50주 @ 55,000원 (수익률: +10.00%, 손익: +250,000원)
            for m in re.finditer(
                r'\[부분매도\]\s*(\d{4}-\d{2}-\d{2}):\s*(\d+)주\s*@\s*([\d,]+)원\s*\(수익률:\s*([+-]?[\d.]+)%,\s*손익:\s*([+-]?[\d,.]+)원\)',
                pos.notes,
            ):
                partial_sells.append({
                    "date": m.group(1),
                    "quantity": int(m.group(2)),
                    "price": float(m.group(3).replace(",", "")),
                    "return_pct": float(m.group(4)),
                    "profit": float(m.group(5).replace(",", "")),
                })

        # BUY 기록 생성
        buy_trade = Trade(
            position_id=pos.id,
            trade_type=TradeType.BUY,
            trade_date=pos.entry_date,
            price=original_price,
            quantity=original_qty if not add_buys else original_qty,  # 역산 어려우므로 현재 수량 사용
            stock_code=pos.ticker,
            stock_name=stock_name,
        )
        db.add(buy_trade)
        created_count += 1

        # ADD_BUY 기록
        for ab in add_buys:
            from datetime import date as date_cls
            trade = Trade(
                position_id=pos.id,
                trade_type=TradeType.ADD_BUY,
                trade_date=date_cls.fromisoformat(ab["date"]),
                price=ab["price"],
                quantity=ab["quantity"],
                stock_code=pos.ticker,
                stock_name=stock_name,
            )
            db.add(trade)
            created_count += 1

        # PARTIAL_SELL 기록
        for ps in partial_sells:
            from datetime import date as date_cls
            trade = Trade(
                position_id=pos.id,
                trade_type=TradeType.PARTIAL_SELL,
                trade_date=date_cls.fromisoformat(ps["date"]),
                price=ps["price"],
                quantity=ps["quantity"],
                realized_profit=ps["profit"],
                realized_return_pct=ps["return_pct"],
                stock_code=pos.ticker,
                stock_name=stock_name,
            )
            db.add(trade)
            created_count += 1

        # SELL 기록 (청산된 포지션)
        if pos.exit_price is not None:
            realized_profit = float(pos.exit_price - pos.entry_price) * pos.quantity
            realized_pct = float((pos.exit_price - pos.entry_price) / pos.entry_price * 100)
            trade = Trade(
                position_id=pos.id,
                trade_type=TradeType.SELL,
                trade_date=pos.exit_date,
                price=pos.exit_price,
                quantity=pos.quantity,
                realized_profit=realized_profit,
                realized_return_pct=realized_pct,
                reason=pos.exit_reason,
                stock_code=pos.ticker,
                stock_name=stock_name,
            )
            db.add(trade)
            created_count += 1

    db.commit()

    return {
        "message": f"백필 완료: {created_count}건 생성",
        "created_count": created_count,
    }


# ===== 증권사 CSV 임포트 =====


def _settlement_to_trade_date(settlement: date_cls) -> date_cls:
    """결제일 → 체결일 변환 (영업일 2일 전, 주말 스킵)."""
    d = settlement
    bdays = 0
    while bdays < 2:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            bdays += 1
    return d


MANUAL_NAME_MAP = {
    'HD현대미포': '010620',
    '비올': '335890',
    'HD현대중공업': '329180',
}


def _parse_brokerage_csv(content: str) -> list[dict]:
    """증권사 CSV 파싱 (삼성증권 양식)."""
    lines = content.strip().split('\n')
    data_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith(('계좌', '[', '조회', '거래일자,거래명')):
            continue
        if re.match(r'^\d+/\d+$', line):
            continue
        data_lines.append(line)

    reader = csv.reader(io.StringIO('\n'.join(data_lines)))
    trades = []
    for row in reader:
        if len(row) < 6:
            continue
        date_str = row[0].strip()
        trade_type = row[1].strip()
        stock_name = row[2].strip()
        qty = int(row[3].replace(',', '').strip()) if row[3].strip() else 0
        price = int(row[4].replace(',', '').replace('"', '').strip()) if row[4].strip() else 0
        amount = int(row[5].replace(',', '').replace('"', '').strip()) if row[5].strip() else 0
        fee = int(row[6].replace(',', '').replace('"', '').strip()) if len(row) > 6 and row[6].strip() else 0
        tax = int(row[7].replace(',', '').replace('"', '').strip()) if len(row) > 7 and row[7].strip() else 0

        is_buy = '매수' in trade_type

        # CSV 날짜는 결제일 → 영업일 2일 전(체결일)으로 보정
        settlement_date = date_cls.fromisoformat(date_str)
        trade_date = _settlement_to_trade_date(settlement_date)

        trades.append({
            'date': trade_date,
            'is_buy': is_buy,
            'stock_name': stock_name,
            'qty': qty,
            'price': price,
            'amount': amount,
            'fee': fee,
            'tax': tax,
        })

    trades.sort(key=lambda t: (t['date'], 0 if t['is_buy'] else 1))
    return trades


def _resolve_code(stock_name: str, db: Session) -> str | None:
    """종목명 → 종목코드."""
    if stock_name in MANUAL_NAME_MAP:
        return MANUAL_NAME_MAP[stock_name]
    stock = db.query(Stock).filter(Stock.name == stock_name).first()
    if stock:
        return stock.code
    stock = db.query(Stock).filter(Stock.name == stock_name.replace(' ', '')).first()
    return stock.code if stock else None


def _build_positions(stock_name: str, stock_code: str, trades: list[dict]) -> list[dict]:
    """한 종목의 거래 리스트 → Position 데이터 구축."""
    positions = []
    cur = None

    for t in trades:
        if t['is_buy']:
            if cur is None:
                cur = {
                    'entry_price': Decimal(str(t['price'])),
                    'entry_date': t['date'],
                    'current_qty': t['qty'],
                    'is_open': True,
                    'trades': [{
                        'trade_type': TradeType.BUY,
                        'date': t['date'],
                        'price': Decimal(str(t['price'])),
                        'qty': t['qty'],
                        'avg_price_after': Decimal(str(t['price'])),
                        'quantity_after': t['qty'],
                    }],
                }
            else:
                old_total = cur['entry_price'] * cur['current_qty']
                new_total = Decimal(str(t['price'])) * t['qty']
                new_qty = cur['current_qty'] + t['qty']
                new_avg = (old_total + new_total) / new_qty
                cur['current_qty'] = new_qty
                cur['entry_price'] = round(new_avg, 2)
                cur['trades'].append({
                    'trade_type': TradeType.ADD_BUY,
                    'date': t['date'],
                    'price': Decimal(str(t['price'])),
                    'qty': t['qty'],
                    'avg_price_after': round(new_avg, 2),
                    'quantity_after': new_qty,
                })
        else:
            if cur is None:
                positions.append({
                    'entry_price': Decimal(str(t['price'])),
                    'entry_date': t['date'],
                    'current_qty': 0,
                    'exit_price': Decimal(str(t['price'])),
                    'exit_date': t['date'],
                    'exit_reason': 'CSV범위외매수',
                    'is_open': False,
                    'notes': '매수 기록이 CSV 조회 범위 밖에 있음',
                    'trades': [{
                        'trade_type': TradeType.SELL,
                        'date': t['date'],
                        'price': Decimal(str(t['price'])),
                        'qty': t['qty'],
                        'quantity_after': 0,
                    }],
                })
                continue

            sell_price = Decimal(str(t['price']))
            entry_price = cur['entry_price']
            realized_profit = float(sell_price - entry_price) * t['qty']
            realized_pct = float((sell_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
            remaining = cur['current_qty'] - t['qty']

            if remaining <= 0:
                cur['trades'].append({
                    'trade_type': TradeType.SELL,
                    'date': t['date'],
                    'price': sell_price,
                    'qty': t['qty'],
                    'realized_profit': round(realized_profit, 2),
                    'realized_return_pct': round(realized_pct, 2),
                    'quantity_after': 0,
                })
                cur['exit_price'] = sell_price
                cur['exit_date'] = t['date']
                cur['is_open'] = False
                cur['current_qty'] = 0
                positions.append(cur)
                cur = None
            else:
                cur['current_qty'] = remaining
                cur['trades'].append({
                    'trade_type': TradeType.PARTIAL_SELL,
                    'date': t['date'],
                    'price': sell_price,
                    'qty': t['qty'],
                    'realized_profit': round(realized_profit, 2),
                    'realized_return_pct': round(realized_pct, 2),
                    'avg_price_after': entry_price,
                    'quantity_after': remaining,
                })

    if cur is not None:
        positions.append(cur)
    return positions


@router.post("/import/csv")
def import_brokerage_csv(
    file: UploadFile = File(...),
    clear_existing: bool = Query(default=True, description="기존 데이터 삭제 여부"),
    db: Session = Depends(get_db),
):
    """증권사 매매내역 CSV 임포트.

    삼성증권 양식 (cp949 인코딩) 지원.
    기존 Trade/Position을 삭제하고 CSV 데이터로 대체합니다.
    """
    raw = file.file.read()
    try:
        content = raw.decode('cp949')
    except UnicodeDecodeError:
        try:
            content = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            content = raw.decode('utf-8', errors='replace')

    csv_trades = _parse_brokerage_csv(content)
    if not csv_trades:
        raise HTTPException(status_code=400, detail="유효한 거래 데이터를 찾을 수 없습니다.")

    # 종목별 그룹
    stock_groups = defaultdict(list)
    for t in csv_trades:
        stock_groups[t['stock_name']].append(t)

    # 기존 데이터 삭제
    deleted_trades = 0
    deleted_positions = 0
    if clear_existing:
        deleted_trades = db.query(Trade).delete()
        deleted_positions = db.query(Position).delete()

    created_ideas = 0
    created_positions = 0
    created_trades_count = 0
    skipped = []

    for stock_name, trades in stock_groups.items():
        stock_code = _resolve_code(stock_name, db)
        if not stock_code:
            skipped.append(stock_name)
            continue

        positions_data = _build_positions(stock_name, stock_code, trades)

        for pos_data in positions_data:
            # Idea 찾기 또는 생성 (이름(코드) 형식 매칭)
            idea = None
            all_ideas = db.query(InvestmentIdea).all()
            for i in all_ideas:
                for tk in (i.tickers or []):
                    match = re.search(r'\(([A-Za-z0-9]{6})\)', tk)
                    extracted = match.group(1) if match else tk
                    if extracted == stock_code:
                        idea = i
                        break
                if idea:
                    break

            if not idea:
                ticker_label = f'{stock_name}({stock_code})'
                status = IdeaStatus.ACTIVE if pos_data['is_open'] else IdeaStatus.EXITED
                idea = InvestmentIdea(
                    id=uuid_mod.uuid4(),
                    type='chart',
                    tickers=[ticker_label],
                    thesis=f'{stock_name} 매매 (CSV 임포트)',
                    expected_timeframe_days=90,
                    target_return_pct=10.0,
                    status=status,
                )
                db.add(idea)
                db.flush()
                created_ideas += 1

            # Position 생성
            position = Position(
                id=uuid_mod.uuid4(),
                idea_id=idea.id,
                ticker=stock_code,
                entry_price=pos_data['entry_price'],
                entry_date=pos_data['entry_date'],
                quantity=pos_data['current_qty'],
                exit_price=pos_data.get('exit_price'),
                exit_date=pos_data.get('exit_date'),
                exit_reason=pos_data.get('exit_reason'),
                notes=pos_data.get('notes'),
            )
            db.add(position)
            db.flush()
            created_positions += 1

            # Trade 생성
            for td in pos_data['trades']:
                trade = Trade(
                    id=uuid_mod.uuid4(),
                    position_id=position.id,
                    trade_type=td['trade_type'],
                    trade_date=td['date'],
                    price=td['price'],
                    quantity=td['qty'],
                    realized_profit=td.get('realized_profit'),
                    realized_return_pct=td.get('realized_return_pct'),
                    avg_price_after=td.get('avg_price_after'),
                    quantity_after=td.get('quantity_after'),
                    stock_code=stock_code,
                    stock_name=stock_name,
                )
                db.add(trade)
                created_trades_count += 1

    db.commit()

    return {
        "message": "CSV 임포트 완료",
        "summary": {
            "csv_trades_parsed": len(csv_trades),
            "date_range": f"{csv_trades[0]['date']} ~ {csv_trades[-1]['date']}",
            "stocks_count": len(stock_groups),
            "deleted_trades": deleted_trades,
            "deleted_positions": deleted_positions,
            "created_ideas": created_ideas,
            "created_positions": created_positions,
            "created_trades": created_trades_count,
            "skipped_stocks": skipped,
        },
    }
