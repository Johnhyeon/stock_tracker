"""삼성증권 매매내역 CSV 마이그레이션 스크립트.

사용법:
    cd backend
    python scripts/migrate_trades_csv.py [--dry-run] [--csv PATH]

기능:
    1. 기존 Trade, Position 전부 삭제
    2. CSV 파싱 (cp949 인코딩, 삼성증권 양식)
    3. 종목명 → Stock 테이블에서 종목코드 매핑
    4. 종목별 순차 처리: 매수 → Position 생성, 매도 → Position 청산/부분매도
    5. 보유 중 종목 → Idea 자동 생성 (chart 타입)
    6. 매수_NXT / 매도_NXT (D+2 결제) 도 동일하게 처리
"""
import sys
import os
import csv
import io
import uuid
import re
import logging
from datetime import date as date_cls, datetime, timedelta
from decimal import Decimal
from collections import defaultdict
from typing import Optional

# backend 디렉토리를 path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text
from core.database import SessionLocal
from models import Stock, InvestmentIdea, IdeaStatus, Position
from models.trade import Trade, TradeType

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

DEFAULT_CSV = r'C:\Users\whdqj\Downloads\삼증_매매내역.csv'


def _settlement_to_trade_date(settlement: date_cls) -> date_cls:
    """결제일 → 체결일 변환 (영업일 2일 전으로 되돌림).

    한국 주식시장 T+2 결제: 체결일 + 영업일 2일 = 결제일
    따라서 결제일에서 영업일 2일을 빼면 체결일.
    (공휴일은 미반영, 주말만 스킵)
    """
    d = settlement
    bdays = 0
    while bdays < 2:
        d -= timedelta(days=1)
        if d.weekday() < 5:  # 월~금
            bdays += 1
    return d


def parse_csv(csv_path: str) -> list[dict]:
    """삼성증권 CSV 파싱."""
    with open(csv_path, 'rb') as f:
        raw = f.read()

    text_content = raw.decode('cp949', errors='replace')
    lines = text_content.strip().split('\n')

    data_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 메타데이터/헤더 스킵
        if line.startswith(('계좌', '[', '조회', '거래일자,거래명')):
            continue
        # 페이지 번호 스킵 (예: 1/42)
        if re.match(r'^\d+/\d+$', line):
            continue
        data_lines.append(line)

    reader = csv.reader(io.StringIO('\n'.join(data_lines)))
    trades = []
    for row in reader:
        if len(row) < 6:
            continue

        date_str, trade_type, stock_name = row[0].strip(), row[1].strip(), row[2].strip()
        qty = int(row[3].replace(',', '').strip()) if row[3].strip() else 0
        price = int(row[4].replace(',', '').replace('"', '').strip()) if row[4].strip() else 0
        amount = int(row[5].replace(',', '').replace('"', '').strip()) if row[5].strip() else 0
        fee = int(row[6].replace(',', '').replace('"', '').strip()) if len(row) > 6 and row[6].strip() else 0
        tax = int(row[7].replace(',', '').replace('"', '').strip()) if len(row) > 7 and row[7].strip() else 0

        # 매수_NXT / 매도_NXT → 매수 / 매도 (D+2 결제 정상 처리)
        is_buy = '매수' in trade_type

        # CSV 날짜는 결제일 → 영업일 2일 전(체결일)으로 보정
        settlement_date = date_cls.fromisoformat(date_str)
        trade_date = _settlement_to_trade_date(settlement_date)

        trades.append({
            'date': trade_date,
            'type_raw': trade_type,
            'is_buy': is_buy,
            'stock_name': stock_name,
            'qty': qty,
            'price': price,
            'amount': amount,
            'fee': fee,
            'tax': tax,
        })

    # 날짜 오름차순 (오래된 것부터)
    trades.sort(key=lambda t: (t['date'], 0 if t['is_buy'] else 1))
    return trades


def build_stock_name_map(db) -> dict[str, str]:
    """Stock 테이블에서 종목명 → 종목코드 매핑."""
    stocks = db.query(Stock).all()
    name_map = {}
    for s in stocks:
        name_map[s.name] = s.code
        # 공백 제거 버전도
        name_map[s.name.replace(' ', '')] = s.code
    return name_map


MANUAL_NAME_MAP = {
    'HD현대미포': '010620',    # 합병 → HD현대중공업(329180)으로 전환. 과거 매매 기록용
    '비올': '335890',          # 자진 상폐. 과거 매매 기록용
    'HD현대중공업': '329180',  # HD현대미포 합병 후 전환 주식 매도분
}


def resolve_stock_code(stock_name: str, name_map: dict) -> Optional[str]:
    """종목명으로 종목코드 찾기."""
    # 수동 매핑 우선
    if stock_name in MANUAL_NAME_MAP:
        return MANUAL_NAME_MAP[stock_name]
    # 직접 매핑
    if stock_name in name_map:
        return name_map[stock_name]
    # 공백 제거
    cleaned = stock_name.replace(' ', '')
    if cleaned in name_map:
        return name_map[cleaned]
    return None


def migrate(csv_path: str, dry_run: bool = False):
    """메인 마이그레이션."""
    logger.info("=" * 60)
    logger.info("삼성증권 매매내역 CSV 마이그레이션")
    logger.info("=" * 60)

    # 1. CSV 파싱
    logger.info(f"\n[1/5] CSV 파싱: {csv_path}")
    csv_trades = parse_csv(csv_path)
    logger.info(f"  총 {len(csv_trades)}건 파싱 완료")
    logger.info(f"  기간: {csv_trades[0]['date']} ~ {csv_trades[-1]['date']}")

    # 종목별 그룹
    stock_trades = defaultdict(list)
    for t in csv_trades:
        stock_trades[t['stock_name']].append(t)

    logger.info(f"  종목 수: {len(stock_trades)}")

    db = SessionLocal()
    try:
        # 2. 종목코드 매핑
        logger.info("\n[2/5] 종목코드 매핑")
        name_map = build_stock_name_map(db)

        mapped = {}
        unmapped = []
        for name in stock_trades.keys():
            code = resolve_stock_code(name, name_map)
            if code:
                mapped[name] = code
            else:
                unmapped.append(name)

        logger.info(f"  매핑 성공: {len(mapped)}종목")
        if unmapped:
            logger.info(f"  매핑 실패: {len(unmapped)}종목")
            for u in unmapped:
                logger.info(f"    - {u}")

        if dry_run:
            logger.info("\n[DRY RUN] 실제 DB 변경 없이 분석만 수행합니다.")

        # 3. 기존 데이터 삭제
        logger.info("\n[3/5] 기존 데이터 삭제")
        existing_trades = db.query(Trade).count()
        existing_positions = db.query(Position).count()
        # CSV 임포트로 자동 생성된 아이디어 (thesis에 'CSV 임포트' 포함)
        csv_ideas = db.query(InvestmentIdea).filter(
            InvestmentIdea.thesis.like('%CSV 임포트%')
        ).all()
        logger.info(f"  기존 Trade: {existing_trades}건")
        logger.info(f"  기존 Position: {existing_positions}건")
        logger.info(f"  CSV 임포트 Idea: {len(csv_ideas)}건 (삭제 대상)")

        if not dry_run:
            db.query(Trade).delete()
            db.query(Position).delete()
            # CSV 임포트로 생성된 아이디어만 삭제 (수동 생성 아이디어 보존)
            for idea in csv_ideas:
                db.delete(idea)
            db.commit()
            logger.info("  삭제 완료")

        # 4. 종목별 포지션/거래 생성
        logger.info("\n[4/5] 포지션/거래 생성")

        created_ideas = 0
        created_positions = 0
        created_trades = 0
        skipped_stocks = []

        for stock_name, trades in sorted(stock_trades.items()):
            stock_code = mapped.get(stock_name)
            if not stock_code:
                skipped_stocks.append(stock_name)
                continue

            # 순 포지션 계산 (매수/매도 히스토리 추적)
            positions_data = _build_positions_from_trades(stock_name, stock_code, trades)

            for pos_data in positions_data:
                if dry_run:
                    created_positions += 1
                    created_trades += len(pos_data['trades'])
                    if pos_data['is_open']:
                        created_ideas += 1
                    continue

                # 오픈/클로즈 모두에 대해 Idea 찾거나 생성
                idea = _find_or_create_idea(db, stock_code, stock_name, pos_data)
                if idea and idea.id not in [i.id for i in db.new]:
                    created_ideas += 0  # 기존 아이디어
                else:
                    created_ideas += 1

                # open 포지션이면 아이디어 status를 active로 갱신
                if pos_data['is_open'] and idea.status != IdeaStatus.ACTIVE:
                    idea.status = IdeaStatus.ACTIVE

                # Position 생성
                position = Position(
                    id=uuid.uuid4(),
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

                # Trade 레코드 생성
                for td in pos_data['trades']:
                    trade = Trade(
                        id=uuid.uuid4(),
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
                    created_trades += 1

        if not dry_run:
            db.commit()

        logger.info(f"\n  생성 결과:")
        logger.info(f"    Idea: {created_ideas}건")
        logger.info(f"    Position: {created_positions}건")
        logger.info(f"    Trade: {created_trades}건")

        if skipped_stocks:
            logger.info(f"\n  종목코드 미매핑으로 스킵: {len(skipped_stocks)}종목")
            for s in skipped_stocks:
                logger.info(f"    - {s}")

        # 5. 결과 요약
        logger.info("\n[5/5] 마이그레이션 완료!")

        if not dry_run:
            # 보유 중 종목 확인
            open_positions = db.query(Position).filter(Position.exit_date.is_(None)).all()
            logger.info(f"\n  현재 보유 포지션: {len(open_positions)}건")
            for p in open_positions:
                logger.info(f"    {p.ticker} ({stock_name}): {p.quantity}주 @ {p.entry_price}원")

    finally:
        db.close()


def _build_positions_from_trades(stock_name: str, stock_code: str, trades: list[dict]) -> list[dict]:
    """한 종목의 거래 리스트에서 Position 데이터 구축.

    매수/매도를 순차 처리하며, 전량 매도 시 Position을 닫고 새 Position 시작.
    """
    positions = []
    current_pos = None

    for t in trades:
        if t['is_buy']:
            if current_pos is None:
                # 새 포지션 시작
                current_pos = {
                    'entry_price': Decimal(str(t['price'])),
                    'entry_date': t['date'],
                    'current_qty': t['qty'],
                    'total_buy_qty': t['qty'],
                    'total_buy_amount': Decimal(str(t['amount'])),
                    'is_open': True,
                    'trades': [{
                        'trade_type': TradeType.BUY,
                        'date': t['date'],
                        'price': Decimal(str(t['price'])),
                        'qty': t['qty'],
                        'avg_price_after': Decimal(str(t['price'])),
                        'quantity_after': t['qty'],
                    }],
                    'notes': None,
                }
            else:
                # 추가매수
                old_total = current_pos['entry_price'] * current_pos['current_qty']
                new_total = Decimal(str(t['price'])) * t['qty']
                new_qty = current_pos['current_qty'] + t['qty']
                new_avg = (old_total + new_total) / new_qty

                current_pos['current_qty'] = new_qty
                current_pos['total_buy_qty'] += t['qty']
                current_pos['total_buy_amount'] += Decimal(str(t['amount']))
                current_pos['entry_price'] = round(new_avg, 2)

                current_pos['trades'].append({
                    'trade_type': TradeType.ADD_BUY,
                    'date': t['date'],
                    'price': Decimal(str(t['price'])),
                    'qty': t['qty'],
                    'avg_price_after': round(new_avg, 2),
                    'quantity_after': new_qty,
                })
        else:
            # 매도
            if current_pos is None:
                # 음수 포지션: 매도 기록만 Trade에 남김 (Position 없이)
                # → 별도 Position으로 처리 (exit만 있는 상태)
                realized_profit = None  # 매입가 모르므로 계산 불가
                positions.append({
                    'entry_price': Decimal(str(t['price'])),  # 매도가를 대체로 사용
                    'entry_date': t['date'],
                    'current_qty': 0,
                    'exit_price': Decimal(str(t['price'])),
                    'exit_date': t['date'],
                    'exit_reason': 'CSV범위외매수',
                    'is_open': False,
                    'notes': f'매수 기록이 CSV 조회 범위 밖에 있음 (매도만 기록)',
                    'trades': [{
                        'trade_type': TradeType.SELL,
                        'date': t['date'],
                        'price': Decimal(str(t['price'])),
                        'qty': t['qty'],
                        'quantity_after': 0,
                    }],
                })
                continue

            sell_qty = t['qty']
            sell_price = Decimal(str(t['price']))

            # 실현손익 계산
            entry_price = current_pos['entry_price']
            realized_profit = float(sell_price - entry_price) * sell_qty
            realized_pct = float((sell_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

            remaining = current_pos['current_qty'] - sell_qty

            if remaining <= 0:
                # 전량 매도
                current_pos['trades'].append({
                    'trade_type': TradeType.SELL,
                    'date': t['date'],
                    'price': sell_price,
                    'qty': sell_qty,
                    'realized_profit': round(realized_profit, 2),
                    'realized_return_pct': round(realized_pct, 2),
                    'avg_price_after': None,
                    'quantity_after': 0,
                })
                current_pos['exit_price'] = sell_price
                current_pos['exit_date'] = t['date']
                current_pos['exit_reason'] = None
                current_pos['is_open'] = False
                current_pos['current_qty'] = 0
                positions.append(current_pos)
                current_pos = None
            else:
                # 부분매도
                current_pos['current_qty'] = remaining
                current_pos['trades'].append({
                    'trade_type': TradeType.PARTIAL_SELL,
                    'date': t['date'],
                    'price': sell_price,
                    'qty': sell_qty,
                    'realized_profit': round(realized_profit, 2),
                    'realized_return_pct': round(realized_pct, 2),
                    'avg_price_after': entry_price,
                    'quantity_after': remaining,
                })

    # 마지막 포지션이 아직 열려있으면 추가
    if current_pos is not None:
        positions.append(current_pos)

    return positions


def _find_or_create_idea(db, stock_code: str, stock_name: str, pos_data: dict) -> InvestmentIdea:
    """종목에 맞는 Idea 찾거나 생성.

    기존 아이디어의 tickers 형식: ['종목명(코드)'] 또는 ['코드']
    둘 다 매칭하도록 코드 추출 후 비교.
    """
    existing_ideas = db.query(InvestmentIdea).all()
    for idea in existing_ideas:
        for ticker in (idea.tickers or []):
            # '가온칩스(399720)' → '399720' 또는 '399720' 그대로
            match = re.search(r'\(([A-Za-z0-9]{6})\)', ticker)
            extracted = match.group(1) if match else ticker
            if extracted == stock_code:
                return idea

    # 없으면 새로 생성 (이름(코드) 형식)
    ticker_label = f'{stock_name}({stock_code})'
    status = IdeaStatus.ACTIVE if pos_data['is_open'] else IdeaStatus.EXITED
    idea = InvestmentIdea(
        id=uuid.uuid4(),
        type='chart',
        tickers=[ticker_label],
        thesis=f'{stock_name} 매매 (CSV 임포트)',
        expected_timeframe_days=90,
        target_return_pct=10.0,
        status=status,
    )
    db.add(idea)
    db.flush()
    return idea


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='삼성증권 매매내역 CSV 마이그레이션')
    parser.add_argument('--csv', default=DEFAULT_CSV, help='CSV 파일 경로')
    parser.add_argument('--dry-run', action='store_true', help='실제 DB 변경 없이 분석만')
    args = parser.parse_args()

    migrate(args.csv, dry_run=args.dry_run)
