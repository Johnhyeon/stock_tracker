"""대시보드 V2 서비스 - 포트폴리오 중심 통합 대시보드."""
import asyncio
import logging
import re
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from core.cache import api_cache
from core.database import async_session_maker
from core.timezone import today_kst
from models import (
    InvestmentIdea, Position, IdeaStatus, IdeaType, Stock,
    StockOHLCV, TrackingSnapshot,
)
logger = logging.getLogger(__name__)


def _extract_stock_code(ticker: str) -> Optional[str]:
    match = re.search(r'\(([A-Za-z0-9]{6})\)', ticker)
    if match:
        return match.group(1)
    if re.match(r'^[A-Za-z0-9]{6}$', ticker):
        return ticker
    return None


class DashboardV2Service:
    def __init__(self, db: Session):
        self.db = db

    async def get_portfolio_dashboard(self) -> dict:
        # 1) 아이디어 조회 (리서치/차트 구분 없이 통합)
        active_ideas = (
            self.db.query(InvestmentIdea)
            .filter(InvestmentIdea.status == IdeaStatus.ACTIVE)
            .all()
        )
        watching_ideas = (
            self.db.query(InvestmentIdea)
            .filter(InvestmentIdea.status == IdeaStatus.WATCHING)
            .all()
        )

        # 모든 열린 포지션의 종목 코드 수집
        all_stock_codes = set()
        for idea in active_ideas + watching_ideas:
            for pos in idea.positions:
                if pos.is_open:
                    code = _extract_stock_code(pos.ticker)
                    if code:
                        all_stock_codes.add(code)

        # 종목명 조회 (동기, 빠름)
        stock_names = {}
        if all_stock_codes:
            stocks = self.db.query(Stock).filter(Stock.code.in_(all_stock_codes)).all()
            for stock in stocks:
                stock_names[stock.code] = stock.name

        # 스파크라인 + 포트폴리오 추이 (동기 DB, 빠름 - 먼저 실행)
        sparklines = {}
        if all_stock_codes:
            try:
                sparklines = await self._fetch_sparklines(all_stock_codes)
            except Exception as e:
                logger.warning(f"스파크라인 조회 실패: {e}")

        portfolio_trend = await self._fetch_portfolio_trend()

        # 현재가 (DB stock_ohlcv 기본 + 실시간 캐시 머지) + SmartScore 조회
        current_prices = {}
        if all_stock_codes:
            try:
                current_prices = self._get_db_prices(list(all_stock_codes))
            except Exception as e:
                logger.warning(f"DB 현재가 조회 실패: {e}")

            # 실시간 가격 캐시 머지 (장중 price_update가 저장한 데이터)
            try:
                from services.price_service import get_price_service
                price_service = get_price_service()
                live_prices = await price_service.get_multiple_prices(
                    list(all_stock_codes), use_cache=True
                )
                for code, live_data in live_prices.items():
                    cp = live_data.get("current_price")
                    if cp is not None:
                        cp_int = int(Decimal(str(cp)))
                        prev = current_prices.get(code, {}).get("prev_close")
                        if prev is None:
                            prev = int(Decimal(str(live_data.get("prev_close", cp))))
                        change = cp_int - prev
                        change_rate = round(change / prev * 100, 2) if prev else 0.0
                        current_prices[code] = {
                            "current_price": cp_int,
                            "change": change,
                            "change_rate": change_rate,
                            "volume": live_data.get("volume", 0),
                            "prev_close": prev,
                        }
            except Exception as e:
                logger.debug(f"실시간 가격 머지 실패, DB 가격 사용: {e}")

        smart_scores = {}
        try:
            smart_scores = await asyncio.wait_for(
                self._fetch_smart_scores(all_stock_codes),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.warning("SmartScore 조회 타임아웃 (5초)")
        except Exception as e:
            logger.warning(f"SmartScore 조회 실패: {e}")

        # 6) 포지션 데이터 조립 + best/worst 계산
        all_performers = []
        total_invested = Decimal("0")
        total_eval = Decimal("0")
        all_return_pcts = []

        formatted_active = self._format_ideas(
            active_ideas, current_prices, stock_names, smart_scores, sparklines,
            all_performers, all_return_pcts,
        )
        formatted_watching = self._format_ideas(
            watching_ideas, current_prices, stock_names, smart_scores, sparklines,
            all_performers, all_return_pcts,
        )

        # 전체 투자금/평가금 합산
        for idea_data in formatted_active:
            total_invested += Decimal(str(idea_data["total_invested"]))
            if idea_data["total_eval"] is not None:
                total_eval += Decimal(str(idea_data["total_eval"]))

        total_unrealized = total_eval - total_invested if total_eval > 0 else Decimal("0")
        total_return_pct = (
            float(total_unrealized / total_invested * 100)
            if total_invested > 0 and total_eval > 0
            else None
        )
        avg_return_pct = (
            sum(all_return_pcts) / len(all_return_pcts)
            if all_return_pcts
            else None
        )

        # best/worst performer
        best = None
        worst = None
        if all_performers:
            sorted_perf = sorted(all_performers, key=lambda x: x["return_pct"], reverse=True)
            best = sorted_perf[0]
            worst = sorted_perf[-1]

        # 스냅샷이 부족하면 현재 데이터를 오늘 포인트로 추가
        if total_invested > 0 and total_eval > 0:
            today_point = {
                "date": today_kst(),
                "total_invested": round(total_invested),
                "total_eval": round(total_eval),
                "unrealized_profit": round(total_unrealized),
                "return_pct": round(total_return_pct, 2) if total_return_pct else 0.0,
            }
            # 오늘 데이터가 이미 있으면 교체, 없으면 추가
            if portfolio_trend and str(portfolio_trend[-1]["date"]) == str(today_kst()):
                portfolio_trend[-1] = today_point
            else:
                portfolio_trend.append(today_point)

        return {
            "stats": {
                "total_ideas": len(active_ideas) + len(watching_ideas),
                "active_ideas": len(active_ideas),
                "watching_ideas": len(watching_ideas),
                "total_invested": round(total_invested),
                "total_eval": round(total_eval) if total_eval > 0 else None,
                "total_unrealized_profit": round(total_unrealized) if total_eval > 0 else None,
                "total_return_pct": total_return_pct,
                "avg_return_pct": avg_return_pct,
                "best_performer": best,
                "worst_performer": worst,
            },
            "active_ideas": formatted_active,
            "watching_ideas": formatted_watching,
            "portfolio_trend": portfolio_trend,
        }

    def _get_db_prices(self, stock_codes: list[str]) -> dict:
        """DB(stock_ohlcv)에서 최신 종가/거래량 조회 (벌크)."""
        if not stock_codes:
            return {}

        # 최근 5거래일치 데이터를 한 번에 조회 (N+1 → 1회 쿼리)
        cutoff = today_kst() - timedelta(days=10)
        rows = (
            self.db.query(StockOHLCV)
            .filter(
                and_(
                    StockOHLCV.stock_code.in_(stock_codes),
                    StockOHLCV.trade_date >= cutoff,
                )
            )
            .order_by(StockOHLCV.stock_code, StockOHLCV.trade_date.desc())
            .all()
        )

        # 종목별 최근 2개 레코드만 추출
        grouped = defaultdict(list)
        for row in rows:
            if len(grouped[row.stock_code]) < 2:
                grouped[row.stock_code].append(row)

        result = {}
        for code, code_rows in grouped.items():
            if not code_rows:
                continue
            latest = code_rows[0]
            prev_close = code_rows[1].close_price if len(code_rows) >= 2 else latest.close_price
            change = latest.close_price - prev_close
            change_rate = round(change / prev_close * 100, 2) if prev_close else 0.0
            result[code] = {
                "current_price": latest.close_price,
                "change": change,
                "change_rate": change_rate,
                "volume": latest.volume,
                "prev_close": prev_close,
            }
        return result

    def _format_ideas(
        self,
        ideas: list,
        current_prices: dict,
        stock_names: dict,
        smart_scores: dict,
        sparklines: dict,
        all_performers: list,
        all_return_pcts: list,
    ) -> list[dict]:
        result = []
        for idea in ideas:
            open_positions = [p for p in idea.positions if p.is_open]
            idea_invested = Decimal("0")
            idea_eval = Decimal("0")
            idea_has_eval = False
            days_active = (today_kst() - idea.created_at.date()).days
            time_remaining = idea.expected_timeframe_days - days_active

            formatted_positions = []
            for p in open_positions:
                code = _extract_stock_code(p.ticker)
                invested = p.entry_price * p.quantity
                idea_invested += invested

                current_price = None
                unrealized_profit = None
                unrealized_return_pct = None
                stock_name = stock_names.get(code) if code else None
                eval_value = None

                if code and code in current_prices:
                    price_data = current_prices[code]
                    cp = price_data.get("current_price")
                    if cp is not None:
                        current_price = Decimal(str(cp))
                        eval_value = current_price * p.quantity
                        unrealized_profit = eval_value - invested
                        unrealized_return_pct = float(unrealized_profit / invested * 100)
                        idea_eval += eval_value
                        idea_has_eval = True

                        all_return_pcts.append(unrealized_return_pct)
                        all_performers.append({
                            "stock_code": code,
                            "stock_name": stock_name or code,
                            "return_pct": round(unrealized_return_pct, 2),
                        })

                        if not stock_name:
                            stock_name = price_data.get("stock_name")

                # SmartScore 배지
                score_badge = None
                if code and code in smart_scores:
                    score_badge = smart_scores[code]

                # 스파크라인
                trend_7d = sparklines.get(code, []) if code else []

                formatted_positions.append({
                    "id": p.id,
                    "ticker": p.ticker,
                    "stock_code": code,
                    "stock_name": stock_name,
                    "entry_price": round(p.entry_price),
                    "entry_date": p.entry_date,
                    "quantity": p.quantity,
                    "days_held": p.days_held,
                    "current_price": round(current_price) if current_price is not None else None,
                    "unrealized_profit": round(unrealized_profit) if unrealized_profit is not None else None,
                    "unrealized_return_pct": round(unrealized_return_pct, 2) if unrealized_return_pct is not None else None,
                    "invested": round(invested),
                    "smart_score": score_badge,
                    "price_trend_7d": trend_7d,
                })

            # 아이디어 전체 평가
            total_idea_unrealized = None
            total_idea_return_pct = None
            total_idea_eval = None
            if idea_has_eval and idea_invested > 0:
                total_idea_eval = round(idea_eval)
                total_idea_unrealized = round(idea_eval - idea_invested)
                total_idea_return_pct = round(
                    float((idea_eval - idea_invested) / idea_invested * 100), 2
                )

            result.append({
                "id": idea.id,
                "type": idea.type,
                "sector": idea.sector,
                "tickers": idea.tickers,
                "thesis": idea.thesis,
                "status": idea.status,
                "fundamental_health": idea.fundamental_health,
                "expected_timeframe_days": idea.expected_timeframe_days,
                "target_return_pct": idea.target_return_pct,
                "created_at": idea.created_at,
                "positions": formatted_positions,
                "total_invested": round(idea_invested),
                "total_eval": total_idea_eval,
                "total_unrealized_profit": total_idea_unrealized,
                "total_unrealized_return_pct": total_idea_return_pct,
                "days_active": days_active,
                "time_remaining_days": time_remaining,
            })

        return result

    async def _fetch_smart_scores(self, stock_codes: set) -> dict:
        """SmartScore를 비동기 DB로 조회. 5분 캐시 활용."""
        if not stock_codes:
            return {}

        # 캐시에서 전체 SmartScore 결과 조회 (5분 TTL)
        cache_key = "smart_scores_all"
        cached_all = api_cache.get(cache_key)

        if cached_all is not None:
            # 캐시에서 보유 종목만 필터링
            return {k: v for k, v in cached_all.items() if k in stock_codes}

        from services.smart_scanner_service import SmartScannerService

        all_scores = {}
        try:
            async with async_session_maker() as session:
                scanner = SmartScannerService(session)
                results = await scanner.scan_all(min_score=0, limit=500)
                for item in results:
                    all_scores[item.stock_code] = {
                        "composite_score": item.composite_score,
                        "composite_grade": item.composite_grade,
                        "chart_grade": item.chart.grade,
                        "narrative_grade": item.narrative.grade,
                        "flow_grade": item.flow.grade,
                        "social_grade": item.social.grade,
                    }
            # 전체 결과를 5분간 캐시
            api_cache.set(cache_key, all_scores, ttl=300)
        except Exception as e:
            logger.warning(f"SmartScore scan 실패: {e}")

        return {k: v for k, v in all_scores.items() if k in stock_codes}

    async def _fetch_sparklines(self, stock_codes: set) -> dict:
        """최근 7거래일 종가 데이터 조회."""
        if not stock_codes:
            return {}

        cutoff = today_kst() - timedelta(days=15)  # 여유있게 15일치 조회
        results = {}

        rows = (
            self.db.query(StockOHLCV.stock_code, StockOHLCV.trade_date, StockOHLCV.close_price)
            .filter(
                and_(
                    StockOHLCV.stock_code.in_(stock_codes),
                    StockOHLCV.trade_date >= cutoff,
                )
            )
            .order_by(StockOHLCV.stock_code, StockOHLCV.trade_date)
            .all()
        )

        by_code = defaultdict(list)
        for code, trade_date, close in rows:
            by_code[code].append(int(close))

        for code, prices in by_code.items():
            results[code] = prices[-7:]  # 최근 7거래일만

        return results

    async def _fetch_portfolio_trend(self) -> list[dict]:
        """TrackingSnapshot 30일 기반 포트폴리오 추이."""
        cutoff = today_kst() - timedelta(days=30)

        # ACTIVE 아이디어 ID 목록
        active_idea_ids = [
            row[0] for row in
            self.db.query(InvestmentIdea.id)
            .filter(InvestmentIdea.status == IdeaStatus.ACTIVE)
            .all()
        ]
        if not active_idea_ids:
            return []

        snapshots = (
            self.db.query(TrackingSnapshot)
            .filter(
                and_(
                    TrackingSnapshot.idea_id.in_(active_idea_ids),
                    TrackingSnapshot.snapshot_date >= cutoff,
                )
            )
            .order_by(TrackingSnapshot.snapshot_date)
            .all()
        )

        if not snapshots:
            return []

        # 날짜별 집계
        daily = defaultdict(lambda: {"invested": Decimal("0"), "eval": Decimal("0")})
        for snap in snapshots:
            d = snap.snapshot_date
            price_data = snap.price_data or {}

            # price_data에서 투자금/평가금 추출
            invested = Decimal(str(price_data.get("total_invested", 0)))
            eval_val = Decimal(str(price_data.get("total_eval", 0)))

            # 대안: unrealized_return_pct로 역산
            if eval_val == 0 and invested > 0 and snap.unrealized_return_pct:
                pct = Decimal(str(snap.unrealized_return_pct)) / 100
                eval_val = invested * (1 + pct)

            daily[d]["invested"] += invested
            daily[d]["eval"] += eval_val

        trend = []
        for d in sorted(daily.keys()):
            inv = daily[d]["invested"]
            ev = daily[d]["eval"]
            profit = ev - inv
            pct = float(profit / inv * 100) if inv > 0 else 0.0
            trend.append({
                "date": d,
                "total_invested": round(inv),
                "total_eval": round(ev),
                "unrealized_profit": round(profit),
                "return_pct": round(pct, 2),
            })

        return trend
