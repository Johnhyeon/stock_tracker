"""차트 시그널 스캐너 서비스.

4가지 시그널을 감지: 눌림목, 전고점 돌파, 저항 돌파 시도, 지지선 테스트.
스코어링은 순수 차트 데이터만 사용 (수급은 참조용).
"""
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from core.timezone import today_kst

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from models import StockOHLCV, StockInvestorFlow, FinancialStatement
from schemas.pullback import SignalType, SignalStock
from services.theme_map_service import get_theme_map_service

logger = logging.getLogger(__name__)


def _grade_from_score(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    return "D"


class PullbackService:
    """차트 시그널 스캐너 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._tms = get_theme_map_service()

    # ── 데이터 조회 (중복 없는 단일 정의) ──

    async def _get_all_stocks(self) -> list[dict]:
        stocks = []
        seen_codes = set()
        for theme_stocks in self._tms.get_all_themes().values():
            for stock in theme_stocks:
                code = stock.get("code")
                name = stock.get("name", "")
                if code and code not in seen_codes and "스팩" not in name:
                    seen_codes.add(code)
                    stocks.append({"code": code, "name": name})
        return stocks

    async def _bulk_get_ohlcv(self, stock_codes: list[str], days: int = 120) -> dict[str, dict]:
        start_date = today_kst() - timedelta(days=days + 30)
        code_set = set(stock_codes)

        # 종목 수가 많으면 IN 절 없이 날짜만으로 전체 조회 (PostgreSQL IN 2000+ 파라미터 회피)
        if len(stock_codes) > 500:
            stmt = (
                select(StockOHLCV)
                .where(
                    and_(
                        StockOHLCV.trade_date >= start_date,
                        StockOHLCV.trade_date <= today_kst(),
                    )
                )
                .order_by(StockOHLCV.stock_code, StockOHLCV.trade_date.asc())
            )
        else:
            stmt = (
                select(StockOHLCV)
                .where(
                    and_(
                        StockOHLCV.stock_code.in_(stock_codes),
                        StockOHLCV.trade_date >= start_date,
                        StockOHLCV.trade_date <= today_kst(),
                    )
                )
                .order_by(StockOHLCV.stock_code, StockOHLCV.trade_date.asc())
            )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        grouped = defaultdict(list)
        for row in rows:
            if row.stock_code in code_set:
                grouped[row.stock_code].append(row)

        ohlcv_map = {}
        for code, candles in grouped.items():
            if len(candles) < 20:
                continue
            dates, opens, highs, lows, closes, volumes = [], [], [], [], [], []
            for c in candles:
                dates.append(c.trade_date)
                opens.append(float(c.open_price))
                highs.append(float(c.high_price))
                lows.append(float(c.low_price))
                closes.append(float(c.close_price))
                volumes.append(float(c.volume))
            ohlcv_map[code] = {
                "dates": dates,
                "opens": np.array(opens),
                "highs": np.array(highs),
                "lows": np.array(lows),
                "closes": np.array(closes),
                "volumes": np.array(volumes),
            }
        return ohlcv_map

    async def _bulk_get_flow(self, stock_codes: list[str], days: int = 20) -> dict[str, dict]:
        start_date = today_kst() - timedelta(days=days + 10)
        code_set = set(stock_codes)

        # 종목 수가 많으면 IN 절 없이 날짜만으로 전체 조회
        if len(stock_codes) > 500:
            stmt = (
                select(StockInvestorFlow)
                .where(StockInvestorFlow.flow_date >= start_date)
                .order_by(StockInvestorFlow.stock_code, StockInvestorFlow.flow_date.desc())
            )
        else:
            stmt = (
                select(StockInvestorFlow)
                .where(
                    and_(
                        StockInvestorFlow.stock_code.in_(stock_codes),
                        StockInvestorFlow.flow_date >= start_date,
                    )
                )
                .order_by(StockInvestorFlow.stock_code, StockInvestorFlow.flow_date.desc())
            )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        grouped = defaultdict(list)
        for row in rows:
            if row.stock_code in code_set:
                grouped[row.stock_code].append(row)

        flow_map = {}
        for code, flows in grouped.items():
            recent_5 = flows[:5]
            foreign_sum = sum(f.foreign_net for f in recent_5)
            institution_sum = sum(f.institution_net for f in recent_5)
            flow_map[code] = {
                "foreign_net_5d": foreign_sum,
                "institution_net_5d": institution_sum,
                "flow_list": [
                    {
                        "date": f.flow_date.isoformat(),
                        "foreign_net": f.foreign_net,
                        "institution_net": f.institution_net,
                        "individual_net": f.individual_net,
                        "flow_score": f.flow_score,
                    }
                    for f in flows[:days]
                ],
            }
        return flow_map

    async def _bulk_get_financial_quality(self, stock_codes: list[str]) -> dict[str, dict]:
        """FinancialStatement에서 최신 연간 재무 데이터로 품질 지표 계산."""
        # 당기순이익, 매출액 관련 계정만 조회
        target_accounts = ["당기순이익", "당기순이익(손실)", "매출액", "수익(매출액)", "매출"]
        code_set = set(stock_codes)

        # 종목 수가 많으면 IN 절 없이 조건만으로 전체 조회
        if len(stock_codes) > 500:
            stmt = (
                select(FinancialStatement)
                .where(
                    and_(
                        FinancialStatement.reprt_code == "11011",  # 연간
                        FinancialStatement.fs_div == "CFS",  # 연결
                        FinancialStatement.account_nm.in_(target_accounts),
                    )
                )
                .order_by(FinancialStatement.stock_code, FinancialStatement.bsns_year.desc())
            )
        else:
            stmt = (
                select(FinancialStatement)
                .where(
                    and_(
                        FinancialStatement.stock_code.in_(stock_codes),
                        FinancialStatement.reprt_code == "11011",  # 연간
                        FinancialStatement.fs_div == "CFS",  # 연결
                        FinancialStatement.account_nm.in_(target_accounts),
                    )
                )
                .order_by(FinancialStatement.stock_code, FinancialStatement.bsns_year.desc())
            )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        # 종목별로 그룹핑
        grouped: dict[str, list] = defaultdict(list)
        for row in rows:
            if row.stock_code in code_set:
                grouped[row.stock_code].append(row)

        quality_map: dict[str, dict] = {}
        for code, entries in grouped.items():
            net_income = None
            revenue_cur = None
            revenue_prev = None

            for entry in entries:
                if "순이익" in entry.account_nm:
                    if net_income is None and entry.thstrm_amount is not None:
                        net_income = entry.thstrm_amount
                if "매출" in entry.account_nm or "수익" in entry.account_nm:
                    if revenue_cur is None and entry.thstrm_amount is not None:
                        revenue_cur = entry.thstrm_amount
                    if revenue_prev is None and entry.frmtrm_amount is not None:
                        revenue_prev = entry.frmtrm_amount

            is_profitable = net_income > 0 if net_income is not None else None
            is_growing = None
            revenue_growth = None
            if revenue_cur is not None and revenue_prev is not None and revenue_prev > 0:
                revenue_growth = round((revenue_cur - revenue_prev) / revenue_prev * 100, 1)
                is_growing = revenue_growth > 0

            # 품질 점수 (최대 30)
            q_score = 0.0
            if is_profitable:
                q_score += 10
            if is_growing:
                q_score += 10
            if revenue_growth is not None and revenue_growth > 10:
                q_score += 5
            if net_income is not None and net_income > 0 and revenue_cur and revenue_cur > 0:
                # 순이익률 5% 이상이면 보너스
                margin = net_income / revenue_cur * 100
                if margin > 5:
                    q_score += 5

            quality_map[code] = {
                "is_profitable": is_profitable,
                "is_growing": is_growing,
                "revenue_growth": revenue_growth,
                "quality_score": round(q_score, 1),
            }
        return quality_map

    # ── 공통 지표 계산 ──

    def _calc_common(self, ohlcv: dict) -> dict:
        closes = ohlcv["closes"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        volumes = ohlcv["volumes"]
        current = int(closes[-1])

        n60 = min(60, len(closes))
        high_60d = int(np.max(highs[-n60:]))
        low_60d = int(np.min(lows[-n60:]))

        if high_60d > low_60d:
            percentile_60d = round((current - low_60d) / (high_60d - low_60d) * 100, 2)
        else:
            percentile_60d = 50.0

        ma20 = int(np.mean(closes[-20:])) if len(closes) >= 20 else None
        ma50 = int(np.mean(closes[-50:])) if len(closes) >= 50 else None

        ma20_dist = round((current - ma20) / ma20 * 100, 2) if ma20 and ma20 > 0 else None
        ma50_dist = round((current - ma50) / ma50 * 100, 2) if ma50 and ma50 > 0 else None

        if len(volumes) >= 20:
            vol_recent = float(np.mean(volumes[-5:]))
            vol_avg = float(np.mean(volumes[-20:]))
            volume_ratio = round(vol_recent / vol_avg, 2) if vol_avg > 0 else 1.0
        else:
            volume_ratio = 1.0

        return {
            "current_price": current,
            "high_price_60d": high_60d,
            "low_price_60d": low_60d,
            "percentile_60d": percentile_60d,
            "ma20": ma20,
            "ma50": ma50,
            "ma20_distance_pct": ma20_dist,
            "ma50_distance_pct": ma50_dist,
            "volume_ratio": volume_ratio,
        }

    # ── 시그널 감지: 눌림목 ──

    def _detect_pullback(self, ohlcv: dict, common: dict) -> Optional[dict]:
        closes = ohlcv["closes"]
        opens = ohlcv["opens"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        volumes = ohlcv["volumes"]
        current = common["current_price"]
        high_60d = common["high_price_60d"]

        if high_60d <= 0:
            return None

        pullback_pct = round((high_60d - current) / high_60d * 100, 2)
        if pullback_pct < 7 or pullback_pct > 25:
            return None

        # ── 필수 조건 1: 선행 랠리 (돌파 후 조정 패턴) ──
        # 60일 저점 대비 고점이 15% 이상 상승한 이력이 있어야 함
        n60 = min(60, len(highs))
        low_60d = common["low_price_60d"]
        if low_60d <= 0 or (high_60d - low_60d) / low_60d < 0.15:
            return None

        # ── 필수 조건 2: 정배열 (MA20 > MA50) ──
        ma20 = common.get("ma20")
        ma50 = common.get("ma50")
        if not ma20 or not ma50 or ma20 <= ma50:
            return None

        # ── 필수 조건 3: MA 지지 근접 — MA20 또는 MA50에서 7% 이내 ──
        ma20_dist = abs(common["ma20_distance_pct"]) if common["ma20_distance_pct"] is not None else 999
        ma50_dist = abs(common["ma50_distance_pct"]) if common["ma50_distance_pct"] is not None else 999
        if min(ma20_dist, ma50_dist) > 7:
            return None

        # ── 급등률 계산: 고점 도달 전 최저점 → 고점까지 상승률 ──
        # 60일 고점 위치 찾기
        n60_idx = len(highs) - n60
        high_idx = n60_idx + int(np.argmax(highs[-n60:]))
        # 고점 이전 20일 내 저점 찾기
        search_start = max(0, high_idx - 20)
        if search_start < high_idx:
            pre_surge_low = float(np.min(lows[search_start:high_idx + 1]))
        else:
            pre_surge_low = float(lows[high_idx])
        surge_pct = round((high_60d - pre_surge_low) / pre_surge_low * 100, 2) if pre_surge_low > 0 else 0.0

        # ── 보너스: 장대양봉 기준봉 (30일 내, 몸통 평균 2.5배+ & 4%+) ──
        n30 = min(30, len(closes))
        bodies = [abs(float(closes[i]) - float(opens[i])) for i in range(-n60, 0)]
        avg_body = float(np.mean(bodies)) if bodies else 0
        has_large_bullish = False
        for i in range(-n30, 0):
            c, o = float(closes[i]), float(opens[i])
            body = c - o
            if body > 0 and body > avg_body * 2.5 and o > 0 and body / o > 0.04:
                has_large_bullish = True
                break

        # 지지선 계산
        support_line = int(np.percentile(lows[-n60:], 10))
        support_dist = round((current - support_line) / support_line * 100, 2) if support_line > 0 else 0

        # 거래량 감소 확인
        vol_decreasing = False
        if len(volumes) >= 20:
            vol_recent = float(np.mean(volumes[-5:]))
            vol_avg = float(np.mean(volumes[-20:]))
            vol_decreasing = (vol_recent / vol_avg < 0.8) if vol_avg > 0 else False

        # --- 스코어링 (100점, 순수 차트) ---
        breakdown = {}

        # 1) 이평선 근접 (30점)
        distances = []
        if common["ma20_distance_pct"] is not None:
            distances.append(abs(common["ma20_distance_pct"]))
        if common["ma50_distance_pct"] is not None:
            distances.append(abs(common["ma50_distance_pct"]))

        ma_score = 0.0
        if distances:
            min_d = min(distances)
            if min_d <= 2:
                ma_score = 30
            elif min_d <= 5:
                ma_score = 30 - (min_d - 2) * 5
            elif min_d <= 10:
                ma_score = max(0, 15 - (min_d - 5) * 2)
        breakdown["ma_proximity"] = round(ma_score, 1)

        # 2) 조정 깊이 (25점) — 10~18%가 최적
        depth_score = 0.0
        if 10 <= pullback_pct <= 18:
            depth_score = 25
        elif 7 <= pullback_pct < 10:
            depth_score = 12 + (pullback_pct - 7) * 4.3
        elif 18 < pullback_pct <= 25:
            depth_score = 25 - (pullback_pct - 18) * 3
        breakdown["depth"] = round(depth_score, 1)

        # 3) 거래량 수축 (25점)
        vol_score = 0.0
        vr = common["volume_ratio"]
        if vol_decreasing:
            vol_score = 25
        elif vr < 1.0:
            vol_score = 10 + (1.0 - vr) * 30
            vol_score = min(25, vol_score)
        else:
            vol_score = max(0, 10 - (vr - 1.0) * 5)
        breakdown["volume_shrink"] = round(vol_score, 1)

        # 4) 캔들 반전 (20점) — 최근 3일 양봉 비율 + 아래꼬리
        candle_score = 0.0
        if len(closes) >= 3:
            recent_opens = ohlcv["opens"][-3:]
            recent_closes = closes[-3:]
            recent_lows = lows[-3:]
            bullish_count = sum(1 for i in range(3) if recent_closes[i] > recent_opens[i])
            candle_score += bullish_count * 4  # 최대 12점

            # 아래꼬리 길이 (하락 반전 신호)
            for i in range(3):
                body = abs(float(recent_closes[i]) - float(recent_opens[i]))
                lower_wick = float(min(recent_opens[i], recent_closes[i])) - float(recent_lows[i])
                if body > 0 and lower_wick > body * 1.5:
                    candle_score += 3
            candle_score = min(20, candle_score)
        breakdown["candle_reversal"] = round(candle_score, 1)

        # 5) 장대양봉 보너스 (10점)
        bullish_bonus = 10.0 if has_large_bullish else 0.0
        breakdown["large_bullish_bonus"] = bullish_bonus

        total = ma_score + depth_score + vol_score + candle_score + bullish_bonus

        # 최소 점수 40점 미만이면 제외
        if total < 40:
            return None

        return {
            "signal_type": SignalType.PULLBACK,
            "total_score": round(min(total, 100), 1),
            "grade": _grade_from_score(min(total, 100)),
            "score_breakdown": breakdown,
            "pullback_pct": pullback_pct,
            "support_line": support_line,
            "support_distance_pct": support_dist,
            "volume_decreasing": vol_decreasing,
            "surge_pct": surge_pct,
        }

    # ── 시그널 감지: 전고점 돌파 ──

    def _detect_high_breakout(self, ohlcv: dict, common: dict) -> Optional[dict]:
        closes = ohlcv["closes"]
        highs = ohlcv["highs"]
        volumes = ohlcv["volumes"]
        dates = ohlcv["dates"]
        current = common["current_price"]

        if len(closes) < 30:
            return None

        # 20~120일 전 구간에서 로컬 고점 찾기
        search_end = len(highs) - 3  # 최근 3일 제외
        search_start = max(0, len(highs) - 120)
        if search_end - search_start < 15:
            return None

        # 로컬 고점: 양쪽 5일 내 최고인 포인트
        local_highs = []
        for i in range(search_start + 5, search_end - 5):
            window = highs[max(0, i - 5):i + 6]
            if float(highs[i]) == float(np.max(window)):
                local_highs.append((i, float(highs[i]), dates[i]))

        if not local_highs:
            return None

        # 가장 높은 로컬 고점 선택
        best = max(local_highs, key=lambda x: x[1])
        prev_high_price = int(best[1])
        prev_high_date = best[2].isoformat() if hasattr(best[2], 'isoformat') else str(best[2])

        # 최근 3일 내 1% 이상 상향 돌파 확인
        breakout_pct = round((current - prev_high_price) / prev_high_price * 100, 2)
        if breakout_pct < 1:
            return None

        # 돌파 거래량 (최근 3일 평균 / 20일 평균)
        if len(volumes) >= 20:
            breakout_vol = float(np.mean(volumes[-3:]))
            base_vol = float(np.mean(volumes[-20:]))
            breakout_volume_ratio = round(breakout_vol / base_vol, 2) if base_vol > 0 else 1.0
        else:
            breakout_volume_ratio = 1.0

        # --- 스코어링 (100점) ---
        breakdown = {}

        # 1) 돌파 크기 (25점) — 1~10%가 건전, 10% 이상은 과열 감점
        bp = breakout_pct
        if 1 <= bp <= 5:
            size_score = 20 + bp
        elif 5 < bp <= 10:
            size_score = 25
        elif 10 < bp <= 20:
            size_score = 25 - (bp - 10) * 1
        else:
            size_score = max(0, 15 - (bp - 20) * 0.5)
        breakdown["breakout_size"] = round(size_score, 1)

        # 2) 거래량 확인 (30점) — 돌파 시 거래량 증가가 중요
        bvr = breakout_volume_ratio
        if bvr >= 2.0:
            vol_score = 30
        elif bvr >= 1.5:
            vol_score = 20 + (bvr - 1.5) * 20
        elif bvr >= 1.0:
            vol_score = 10 + (bvr - 1.0) * 20
        else:
            vol_score = bvr * 10
        breakdown["volume_confirm"] = round(vol_score, 1)

        # 3) 고점 의미도 (25점) — 고점이 60일 고점에 가까울수록 의미 큼
        high_60d = common["high_price_60d"]
        if high_60d > 0:
            significance = prev_high_price / high_60d
            if significance >= 0.95:
                sig_score = 25
            elif significance >= 0.85:
                sig_score = 15 + (significance - 0.85) * 100
            else:
                sig_score = max(0, significance * 15)
        else:
            sig_score = 10
        breakdown["high_significance"] = round(sig_score, 1)

        # 4) 이평선 정배열 (20점)
        align_score = 0.0
        ma20 = common["ma20"]
        ma50 = common["ma50"]
        if ma20 and current > ma20:
            align_score += 10
        if ma50 and current > ma50:
            align_score += 5
        if ma20 and ma50 and ma20 > ma50:
            align_score += 5
        breakdown["ma_alignment"] = round(align_score, 1)

        total = size_score + vol_score + sig_score + align_score

        return {
            "signal_type": SignalType.HIGH_BREAKOUT,
            "total_score": round(total, 1),
            "grade": _grade_from_score(total),
            "score_breakdown": breakdown,
            "prev_high_price": prev_high_price,
            "prev_high_date": prev_high_date,
            "breakout_pct": breakout_pct,
            "breakout_volume_ratio": breakout_volume_ratio,
        }

    # ── 시그널 감지: 저항 돌파 시도 ──

    def _detect_resistance_test(self, ohlcv: dict, common: dict) -> Optional[dict]:
        closes = ohlcv["closes"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        volumes = ohlcv["volumes"]
        current = common["current_price"]

        n60 = min(60, len(highs))
        if n60 < 20:
            return None

        recent_highs = highs[-n60:]

        # 저항선 후보: 상위 5% 가격대를 클러스터링
        high_threshold = float(np.percentile(recent_highs, 95))
        resistance_zone_hits = []
        tolerance = high_threshold * 0.02  # 2% 허용

        for i, h in enumerate(recent_highs):
            if abs(float(h) - high_threshold) <= tolerance:
                resistance_zone_hits.append(i)

        # 저항선 2회 이상 터치 필요
        touch_count = len(resistance_zone_hits)
        if touch_count < 2:
            return None

        resistance_price = int(high_threshold)

        # 현재가가 저항선 3% 이내여야 함 (아직 미돌파)
        if resistance_price <= 0:
            return None
        dist_pct = round((resistance_price - current) / resistance_price * 100, 2)
        if dist_pct < -1 or dist_pct > 3:
            # 이미 1% 이상 돌파했거나 3% 이상 멀면 제외
            return None

        resistance_distance_pct = dist_pct

        # --- 스코어링 (100점) ---
        breakdown = {}

        # 1) 저항 강도 (30점) — 터치 횟수 + 시간 분산
        if touch_count >= 4:
            strength_score = 30
        elif touch_count >= 3:
            strength_score = 22
        else:
            strength_score = 15
        # 터치 시간 분산 보너스
        if len(resistance_zone_hits) >= 2:
            time_spread = resistance_zone_hits[-1] - resistance_zone_hits[0]
            if time_spread >= 20:
                strength_score = min(30, strength_score + 5)
        breakdown["resistance_strength"] = round(strength_score, 1)

        # 2) 현재 근접도 (30점) — 저항선에 가까울수록 고점수
        if dist_pct <= 0.5:
            prox_score = 30
        elif dist_pct <= 1.0:
            prox_score = 25
        elif dist_pct <= 2.0:
            prox_score = 20 - (dist_pct - 1.0) * 5
        else:
            prox_score = max(0, 15 - (dist_pct - 2.0) * 5)
        breakdown["proximity"] = round(prox_score, 1)

        # 3) 거래량 증가 (20점) — 저항선 접근 시 거래량 증가
        vol_score = 0.0
        vr = common["volume_ratio"]
        if vr >= 1.5:
            vol_score = 20
        elif vr >= 1.2:
            vol_score = 12 + (vr - 1.2) * 26.7
        elif vr >= 1.0:
            vol_score = 8 + (vr - 1.0) * 20
        else:
            vol_score = vr * 8
        breakdown["volume_increase"] = round(vol_score, 1)

        # 4) 가격 수렴 (20점) — 최근 10일 가격 범위가 좁아지는 추세
        conv_score = 0.0
        if len(closes) >= 20:
            range_first = float(np.max(highs[-20:-10]) - np.min(lows[-20:-10]))
            range_second = float(np.max(highs[-10:]) - np.min(lows[-10:]))
            if range_first > 0:
                convergence = range_second / range_first
                if convergence <= 0.5:
                    conv_score = 20
                elif convergence <= 0.7:
                    conv_score = 15
                elif convergence <= 1.0:
                    conv_score = 10
                else:
                    conv_score = 5
        breakdown["convergence"] = round(conv_score, 1)

        total = strength_score + prox_score + vol_score + conv_score

        return {
            "signal_type": SignalType.RESISTANCE_TEST,
            "total_score": round(total, 1),
            "grade": _grade_from_score(total),
            "score_breakdown": breakdown,
            "resistance_price": resistance_price,
            "resistance_touch_count": touch_count,
            "resistance_distance_pct": resistance_distance_pct,
        }

    # ── 시그널 감지: 지지선 테스트 ──

    def _detect_support_test(self, ohlcv: dict, common: dict) -> Optional[dict]:
        closes = ohlcv["closes"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        opens = ohlcv["opens"]
        volumes = ohlcv["volumes"]
        current = common["current_price"]

        n = len(closes)
        n120 = min(120, n)
        if n120 < 30:
            return None

        # ── 1. 로컬 저점 수집 (양쪽 3일 내 최저인 포인트) ──
        search_lows = lows[-n120:]
        search_dates = list(range(n - n120, n))
        local_lows = []
        for i in range(3, len(search_lows) - 3):
            window = search_lows[max(0, i - 3):i + 4]
            if float(search_lows[i]) <= float(np.min(window)):
                local_lows.append((search_dates[i], float(search_lows[i])))

        if len(local_lows) < 2:
            return None

        # ── 2. 클러스터링: 가격 3% 허용 범위 내 그룹핑 ──
        clusters: list[list[tuple[int, float]]] = []
        for point in local_lows:
            placed = False
            for cluster in clusters:
                avg_price = np.mean([p[1] for p in cluster])
                if abs(point[1] - avg_price) / avg_price <= 0.03:
                    cluster.append(point)
                    placed = True
                    break
            if not placed:
                clusters.append([point])

        # 2회 이상 터치된 클러스터만 유효
        valid_clusters = [c for c in clusters if len(c) >= 2]
        if not valid_clusters:
            return None

        # 현재가에 가장 가까운 유효 클러스터 선택 (오래된 바닥이 아닌 관련성 높은 지지선)
        best_cluster = min(
            valid_clusters,
            key=lambda c: abs(current - np.mean([p[1] for p in c]))
        )
        touch_count = len(best_cluster)

        support_price = int(np.mean([p[1] for p in best_cluster]))
        if support_price <= 0:
            return None

        # ── 3. MA 지지 보강 ──
        ma20 = common.get("ma20")
        ma50 = common.get("ma50")
        ma120 = int(np.mean(closes[-120:])) if n >= 120 else None

        ma_support_count = 0
        for ma in [ma20, ma50, ma120]:
            if ma and abs(ma - support_price) / support_price <= 0.03:
                ma_support_count += 1
        ma_support_aligned = ma_support_count > 0

        # ── 4. 진입 조건: 현재가가 지지선 근처 ──
        dist_pct = round((current - support_price) / support_price * 100, 2)
        # 지지선 위 0~8% 또는 아래 -2% 이내
        if dist_pct > 8 or dist_pct < -2:
            return None

        # ── 5. 횡보 감지: 최근 10일 범위 / 60일 범위 ──
        n60 = min(60, n)
        n10 = min(10, n)
        range_10d = float(np.max(closes[-n10:]) - np.min(closes[-n10:]))
        range_60d = float(np.max(closes[-n60:]) - np.min(closes[-n60:]))
        consolidation_ratio = range_10d / range_60d if range_60d > 0 else 1.0
        consolidation_days = n10 if consolidation_ratio < 0.4 else 0

        # ── 스코어링 (100점) ──
        breakdown = {}

        # 1) 지지 강도 (30점) — 터치 횟수 + 시간 분산
        if touch_count >= 4:
            strength_score = 30.0
        elif touch_count >= 3:
            strength_score = 22.0
        else:
            strength_score = 15.0
        # 시간 분산 보너스
        if len(best_cluster) >= 2:
            time_spread = best_cluster[-1][0] - best_cluster[0][0]
            if time_spread >= 30:
                strength_score = min(30, strength_score + 5)
        breakdown["support_strength"] = round(strength_score, 1)

        # 2) 현재 근접도 (25점) — 거리 비례 감점
        abs_dist = abs(dist_pct)
        if abs_dist <= 1.0:
            prox_score = 25.0
        elif abs_dist <= 2.0:
            prox_score = 20.0
        elif abs_dist <= 4.0:
            prox_score = 15.0
        elif abs_dist <= 6.0:
            prox_score = 10.0
        else:
            prox_score = 5.0
        breakdown["proximity"] = round(prox_score, 1)

        # 3) 거래량 수축 (20점) — 횡보 시 거래량 감소 = 건전한 조정
        vol_score = 0.0
        if len(volumes) >= 20:
            vol_recent = float(np.mean(volumes[-5:]))
            vol_avg = float(np.mean(volumes[-20:]))
            vr = vol_recent / vol_avg if vol_avg > 0 else 1.0
            if vr < 0.6:
                vol_score = 20.0
            elif vr < 0.8:
                vol_score = 15.0
            elif vr < 1.0:
                vol_score = 10.0
            else:
                vol_score = max(0, 5 - (vr - 1.0) * 5)
        breakdown["volume_shrink"] = round(vol_score, 1)

        # 4) 반등 캔들 (15점) — 최근 3일 양봉, 아래꼬리
        candle_score = 0.0
        if n >= 3:
            recent_opens = opens[-3:]
            recent_closes = closes[-3:]
            recent_lows = lows[-3:]
            bullish_count = sum(1 for i in range(3) if recent_closes[i] > recent_opens[i])
            candle_score += bullish_count * 3  # 최대 9점

            for i in range(3):
                body = abs(float(recent_closes[i]) - float(recent_opens[i]))
                lower_wick = float(min(recent_opens[i], recent_closes[i])) - float(recent_lows[i])
                if body > 0 and lower_wick > body * 1.5:
                    candle_score += 2
            candle_score = min(15, candle_score)
        breakdown["candle_reversal"] = round(candle_score, 1)

        # 5) MA 지지 정렬 (10점)
        ma_align_score = min(10, ma_support_count * 5) if ma_support_aligned else 0.0
        breakdown["ma_support"] = round(ma_align_score, 1)

        total = strength_score + prox_score + vol_score + candle_score + ma_align_score

        if total < 30:
            return None

        return {
            "signal_type": SignalType.SUPPORT_TEST,
            "total_score": round(min(total, 100), 1),
            "grade": _grade_from_score(min(total, 100)),
            "score_breakdown": breakdown,
            "support_line": support_price,
            "support_distance_pct": dist_pct,
            "support_price": support_price,
            "support_touch_count": touch_count,
            "consolidation_days": consolidation_days,
            "ma_support_aligned": ma_support_aligned,
        }

    # ── 시그널 감지: MSS 근접 ──

    @staticmethod
    def _aggregate_weekly(ohlcv: dict) -> dict:
        """일봉 → 주봉 집계."""
        dates = ohlcv["dates"]
        opens = ohlcv["opens"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        closes = ohlcv["closes"]
        volumes = ohlcv["volumes"]

        weekly = {"dates": [], "opens": [], "highs": [], "lows": [], "closes": [], "volumes": []}
        week_open = week_high = week_low = week_close = week_vol = None
        prev_week = None

        for i in range(len(dates)):
            d = dates[i]
            iso_week = d.isocalendar()[1] * 100 + d.isocalendar()[0]  # 주차+년도 고유키

            if prev_week is not None and iso_week != prev_week:
                weekly["dates"].append(dates[i - 1])
                weekly["opens"].append(week_open)
                weekly["highs"].append(week_high)
                weekly["lows"].append(week_low)
                weekly["closes"].append(week_close)
                weekly["volumes"].append(week_vol)
                week_open = week_high = week_low = week_close = week_vol = None

            if week_open is None:
                week_open = float(opens[i])
                week_high = float(highs[i])
                week_low = float(lows[i])
                week_vol = 0.0
            week_high = max(week_high, float(highs[i]))
            week_low = min(week_low, float(lows[i]))
            week_close = float(closes[i])
            week_vol += float(volumes[i])
            prev_week = iso_week

        if week_open is not None:
            weekly["dates"].append(dates[-1])
            weekly["opens"].append(week_open)
            weekly["highs"].append(week_high)
            weekly["lows"].append(week_low)
            weekly["closes"].append(week_close)
            weekly["volumes"].append(week_vol)

        return {
            "dates": weekly["dates"],
            "opens": np.array(weekly["opens"]) if weekly["opens"] else np.array([]),
            "highs": np.array(weekly["highs"]) if weekly["highs"] else np.array([]),
            "lows": np.array(weekly["lows"]) if weekly["lows"] else np.array([]),
            "closes": np.array(weekly["closes"]) if weekly["closes"] else np.array([]),
            "volumes": np.array(weekly["volumes"]) if weekly["volumes"] else np.array([]),
        }

    @staticmethod
    def _aggregate_monthly(ohlcv: dict) -> dict:
        """일봉 → 월봉 집계."""
        dates = ohlcv["dates"]
        opens = ohlcv["opens"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        closes = ohlcv["closes"]
        volumes = ohlcv["volumes"]

        monthly = {"dates": [], "opens": [], "highs": [], "lows": [], "closes": [], "volumes": []}
        m_open = m_high = m_low = m_close = m_vol = None
        prev_month = None

        for i in range(len(dates)):
            d = dates[i]
            ym = d.year * 100 + d.month

            if prev_month is not None and ym != prev_month:
                monthly["dates"].append(dates[i - 1])
                monthly["opens"].append(m_open)
                monthly["highs"].append(m_high)
                monthly["lows"].append(m_low)
                monthly["closes"].append(m_close)
                monthly["volumes"].append(m_vol)
                m_open = m_high = m_low = m_close = m_vol = None

            if m_open is None:
                m_open = float(opens[i])
                m_high = float(highs[i])
                m_low = float(lows[i])
                m_vol = 0.0
            m_high = max(m_high, float(highs[i]))
            m_low = min(m_low, float(lows[i]))
            m_close = float(closes[i])
            m_vol += float(volumes[i])
            prev_month = ym

        if m_open is not None:
            monthly["dates"].append(dates[-1])
            monthly["opens"].append(m_open)
            monthly["highs"].append(m_high)
            monthly["lows"].append(m_low)
            monthly["closes"].append(m_close)
            monthly["volumes"].append(m_vol)

        return {
            "dates": monthly["dates"],
            "opens": np.array(monthly["opens"]) if monthly["opens"] else np.array([]),
            "highs": np.array(monthly["highs"]) if monthly["highs"] else np.array([]),
            "lows": np.array(monthly["lows"]) if monthly["lows"] else np.array([]),
            "closes": np.array(monthly["closes"]) if monthly["closes"] else np.array([]),
            "volumes": np.array(monthly["volumes"]) if monthly["volumes"] else np.array([]),
        }

    @staticmethod
    def _find_swings(highs, lows, window: int) -> list[tuple]:
        """스윙 고점/저점 찾기. 반환: [(index, price, 'high'|'low'), ...]"""
        n = len(highs)
        if n < window * 2 + 1:
            return []

        swings = []
        for i in range(window, n - window):
            # 스윙 고점
            is_swing_high = True
            h_val = float(highs[i])
            for j in range(i - window, i + window + 1):
                if j != i and float(highs[j]) >= h_val:
                    is_swing_high = False
                    break
            if is_swing_high:
                swings.append((i, h_val, "high"))

            # 스윙 저점
            is_swing_low = True
            l_val = float(lows[i])
            for j in range(i - window, i + window + 1):
                if j != i and float(lows[j]) <= l_val:
                    is_swing_low = False
                    break
            if is_swing_low:
                swings.append((i, l_val, "low"))

        swings.sort(key=lambda x: x[0])
        return swings

    @staticmethod
    def _find_mss_for_timeframe(ohlcv_data: dict, window: int) -> Optional[dict]:
        """단일 타임프레임에서 주요 저항 레벨(목선) 근접 탐색.

        1. 스윙 고점 찾기
        2. 비슷한 가격대(2% 이내) 스윙 고점을 클러스터링
        3. 2회 이상 터치된 클러스터만 = "목선"
        4. 현재가 기준 아래 5% ~ 위 3% 범위 내 레벨
        5. 가장 가까운 주요 저항 레벨 반환 + 터치 횟수
        """
        highs = ohlcv_data["highs"]
        lows = ohlcv_data["lows"]
        closes = ohlcv_data["closes"]

        if len(closes) < window * 2 + 5:
            return None

        current = float(closes[-1])
        swings = PullbackService._find_swings(highs, lows, window)

        # 스윙 고점만 추출
        swing_highs = [s for s in swings if s[2] == "high"]
        if len(swing_highs) < 2:
            return None

        # 저항 레벨 클러스터링: 비슷한 가격대(2% 이내) 그룹화
        clusters: list[list[tuple]] = []
        for point in swing_highs:
            placed = False
            for cluster in clusters:
                avg_price = np.mean([p[1] for p in cluster])
                if abs(point[1] - avg_price) / avg_price <= 0.02:
                    cluster.append(point)
                    placed = True
                    break
            if not placed:
                clusters.append([point])

        # 2회 이상 터치된 클러스터만 = 주요 저항 레벨(목선)
        valid_clusters = [c for c in clusters if len(c) >= 2]
        if not valid_clusters:
            return None

        # 현재가 기준 아래 5% ~ 위 3% 범위 내 레벨 필터링
        nearby: list[dict] = []
        for cluster in valid_clusters:
            level = float(np.mean([p[1] for p in cluster]))
            if level <= 0:
                continue
            dist_pct = (current - level) / level * 100
            if -5 <= dist_pct <= 3:
                nearby.append({
                    "level": int(level),
                    "touch_count": len(cluster),
                    "distance_pct": round(dist_pct, 2),
                })

        if not nearby:
            return None

        # 가장 가까운 주요 저항 레벨 반환
        best = min(nearby, key=lambda x: abs(x["distance_pct"]))
        return {
            "level": best["level"],
            "type": "bullish",
            "distance_pct": best["distance_pct"],
            "touch_count": best["touch_count"],
        }

    def _detect_mss_proximity(self, ohlcv: dict, common: dict, timeframe: str = "daily") -> Optional[dict]:
        """MSS(주요 저항선 목선) 근접 시그널 감지.

        단일 타임프레임에서 주요 저항 레벨 근접 종목을 탐색.
        Bullish만 (상승 여력 매수 관점).
        """
        closes = ohlcv["closes"]
        opens = ohlcv["opens"]
        volumes = ohlcv["volumes"]
        current = common["current_price"]

        if len(closes) < 60:
            return None

        # 타임프레임에 따라 데이터 집계 + window 결정
        if timeframe == "weekly":
            tf_ohlcv = self._aggregate_weekly(ohlcv)
            window = 3
            min_candles = 10
        elif timeframe == "monthly":
            tf_ohlcv = self._aggregate_monthly(ohlcv)
            window = 2
            min_candles = 6
        else:
            tf_ohlcv = ohlcv
            window = 5
            min_candles = 20

        if len(tf_ohlcv["closes"]) < min_candles:
            return None

        mss = self._find_mss_for_timeframe(tf_ohlcv, window=window)
        if mss is None:
            return None

        # ── 스코어링 (100점, 단일 타임프레임) ──
        breakdown = {}

        # 1) 근접도 (35점)
        abs_dist = abs(mss["distance_pct"])
        if abs_dist <= 1.0:
            prox_score = 35.0
        elif abs_dist <= 2.0:
            prox_score = 28.0
        elif abs_dist <= 3.0:
            prox_score = 21.0
        elif abs_dist <= 5.0:
            prox_score = 14.0
        else:
            prox_score = 7.0
        breakdown["proximity"] = round(prox_score, 1)

        # 2) 터치 횟수 (25점)
        touch_count = mss.get("touch_count", 2)
        if touch_count >= 5:
            touch_score = 25.0
        elif touch_count == 4:
            touch_score = 20.0
        elif touch_count == 3:
            touch_score = 16.0
        else:
            touch_score = 12.0
        breakdown["touch_count"] = round(touch_score, 1)

        # 3) 거래량 확인 (20점) — 일봉 기준 거래량 증가
        vol_score = 0.0
        if len(volumes) >= 20:
            vol_recent = float(np.mean(volumes[-3:]))
            vol_avg = float(np.mean(volumes[-20:]))
            vr = vol_recent / vol_avg if vol_avg > 0 else 1.0
            if vr >= 1.5:
                vol_score = 20.0
            elif vr >= 1.2:
                vol_score = 14.0
            elif vr >= 1.0:
                vol_score = 7.0
        breakdown["volume_confirmation"] = round(vol_score, 1)

        # 4) 캔들 품질 (20점) — 최근 3캔들 양봉 비율 + 모멘텀
        candle_score = 0.0
        if len(closes) >= 4:
            recent_closes = closes[-3:]
            recent_opens = opens[-3:]
            bullish_count = sum(1 for i in range(3) if float(recent_closes[i]) > float(recent_opens[i]))
            candle_score += bullish_count * 4  # 최대 12점

            # 모멘텀: 3일간 상승률
            if float(closes[-4]) > 0:
                momentum = (float(closes[-1]) - float(closes[-4])) / float(closes[-4]) * 100
                if momentum > 0:
                    candle_score += min(8, momentum * 2)
            candle_score = min(20, candle_score)
        breakdown["candle_quality"] = round(candle_score, 1)

        total = prox_score + touch_score + vol_score + candle_score

        if total < 30:
            return None

        return {
            "signal_type": SignalType.MSS_PROXIMITY,
            "total_score": round(min(total, 100), 1),
            "grade": _grade_from_score(min(total, 100)),
            "score_breakdown": breakdown,
            "mss_level": mss["level"],
            "mss_type": "bullish",
            "mss_distance_pct": mss["distance_pct"],
            "mss_touch_count": touch_count,
            "mss_timeframe": timeframe,
        }

    # ── 시그널 감지: 관성 구간 (Momentum Consolidation Zone) ──

    def _detect_momentum_zone(self, ohlcv: dict, common: dict) -> Optional[dict]:
        """급등 후 좁은 범위 횡보 + 변동성·거래량 수축 구간 탐지 (VCP/Bull Flag 변형)."""
        closes = ohlcv["closes"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        volumes = ohlcv["volumes"]
        current = common["current_price"]

        n = len(closes)
        if n < 40:
            return None

        # ── 1단계: 급등 탐색 (최근 90일 내 3~20일간 15%+ 상승) ──
        n90 = min(90, n)
        best_surge = None
        for end_i in range(n - 3, n - n90, -1):
            for dur in range(3, min(21, end_i + 1)):
                start_i = end_i - dur
                if start_i < 0:
                    break
                low_val = float(np.min(lows[start_i:start_i + 3]))
                high_val = float(np.max(highs[end_i - 2:end_i + 1]))
                if low_val <= 0:
                    continue
                surge_pct = (high_val - low_val) / low_val * 100
                if surge_pct >= 15:
                    if best_surge is None or surge_pct > best_surge["pct"]:
                        best_surge = {
                            "pct": surge_pct,
                            "days": dur,
                            "end_idx": end_i,
                            "high_val": high_val,
                        }
            if best_surge and best_surge["pct"] >= 30:
                break  # 충분히 강한 급등 발견

        if best_surge is None:
            return None

        surge_end = best_surge["end_idx"]
        surge_high = best_surge["high_val"]

        # ── 2단계: 횡보 검증 (급등 후 3~60일간 좁은 범위 횡보) ──
        consol_start = surge_end + 1
        if consol_start >= n:
            return None

        consol_days = n - consol_start
        if consol_days < 3:
            return None
        consol_days = min(consol_days, 60)

        consol_highs = highs[consol_start:consol_start + consol_days]
        consol_lows = lows[consol_start:consol_start + consol_days]
        consol_closes = closes[consol_start:consol_start + consol_days]

        upper_bound = float(np.max(consol_highs))
        lower_bound = float(np.min(consol_lows))
        if lower_bound <= 0:
            return None

        consol_range_pct = (upper_bound - lower_bound) / lower_bound * 100

        # 횡보 범위가 고점 대비 15% 이내여야 함
        if consol_range_pct > 15:
            return None

        # 횡보 구간 종가가 대체로 급등 고점 대비 85% 이상 유지
        if float(np.mean(consol_closes)) < surge_high * 0.85:
            return None

        # MA20 위 유지 확인 (마지막 종가 기준)
        ma20 = common.get("ma20")
        if ma20 and current < ma20 * 0.97:
            return None

        # ── 3단계: 수축 계산 ──
        # ATR 수축비: 횡보 구간 ATR / 급등 구간 ATR
        surge_start = max(0, surge_end - best_surge["days"])
        surge_ranges = highs[surge_start:surge_end + 1] - lows[surge_start:surge_end + 1]
        surge_atr = float(np.mean(surge_ranges)) if len(surge_ranges) > 0 else 1.0

        consol_ranges = consol_highs - consol_lows
        consol_atr = float(np.mean(consol_ranges)) if len(consol_ranges) > 0 else 1.0

        atr_contraction = round(consol_atr / surge_atr, 2) if surge_atr > 0 else 1.0

        # 거래량 수축비: 횡보 평균 거래량 / 급등 평균 거래량
        surge_vols = volumes[surge_start:surge_end + 1]
        consol_vols = volumes[consol_start:consol_start + consol_days]
        surge_avg_vol = float(np.mean(surge_vols)) if len(surge_vols) > 0 else 1.0
        consol_avg_vol = float(np.mean(consol_vols)) if len(consol_vols) > 0 else 1.0
        vol_shrink_ratio = round(consol_avg_vol / surge_avg_vol, 2) if surge_avg_vol > 0 else 1.0

        # 현재가 → 횡보 상단 거리
        distance_to_upper = round((upper_bound - current) / current * 100, 2) if current > 0 else 99.0

        # ── 스코어링 (100점) ──
        breakdown = {}

        # 1) 레인지 수축도 (25점): 횡보 범위가 좁을수록 고점
        if consol_range_pct <= 3:
            range_score = 25.0
        elif consol_range_pct <= 5:
            range_score = 22.0
        elif consol_range_pct <= 8:
            range_score = 18.0
        elif consol_range_pct <= 12:
            range_score = 12.0
        else:
            range_score = 6.0
        breakdown["range_contraction"] = round(range_score, 1)

        # 2) 거래량 수축 (20점): 급등 대비 거래량 감소
        if vol_shrink_ratio <= 0.3:
            vol_score = 20.0
        elif vol_shrink_ratio <= 0.5:
            vol_score = 16.0
        elif vol_shrink_ratio <= 0.7:
            vol_score = 12.0
        elif vol_shrink_ratio <= 1.0:
            vol_score = 6.0
        else:
            vol_score = 0.0
        breakdown["volume_shrink"] = round(vol_score, 1)

        # 3) ATR 수축 (20점): 변동성 감소 정도
        if atr_contraction <= 0.3:
            atr_score = 20.0
        elif atr_contraction <= 0.5:
            atr_score = 16.0
        elif atr_contraction <= 0.7:
            atr_score = 12.0
        elif atr_contraction <= 1.0:
            atr_score = 6.0
        else:
            atr_score = 0.0
        breakdown["atr_contraction"] = round(atr_score, 1)

        # 4) 정배열 (15점): MA5 > MA20 > MA60 > MA120 정도
        align_score = 0.0
        if n >= 5:
            ma5 = float(np.mean(closes[-5:]))
            ma20_v = float(np.mean(closes[-20:])) if n >= 20 else None
            ma60_v = float(np.mean(closes[-60:])) if n >= 60 else None
            ma120_v = float(np.mean(closes[-120:])) if n >= 120 else None

            if ma20_v and ma5 > ma20_v:
                align_score += 5
            if ma20_v and ma60_v and ma20_v > ma60_v:
                align_score += 5
            if ma60_v and ma120_v and ma60_v > ma120_v:
                align_score += 5
        breakdown["ma_alignment"] = round(align_score, 1)

        # 5) 돌파 근접도 (20점): 현재가가 횡보 상단에 가까울수록
        if distance_to_upper <= 0:
            # 이미 상단 돌파
            prox_score = 20.0
        elif distance_to_upper <= 1:
            prox_score = 18.0
        elif distance_to_upper <= 2:
            prox_score = 14.0
        elif distance_to_upper <= 4:
            prox_score = 10.0
        elif distance_to_upper <= 6:
            prox_score = 5.0
        else:
            prox_score = 0.0
        breakdown["breakout_proximity"] = round(prox_score, 1)

        total = range_score + vol_score + atr_score + align_score + prox_score

        if total < 40:
            return None

        return {
            "signal_type": SignalType.MOMENTUM_ZONE,
            "total_score": round(min(total, 100), 1),
            "grade": _grade_from_score(min(total, 100)),
            "score_breakdown": breakdown,
            "mz_surge_pct": round(best_surge["pct"], 1),
            "mz_surge_days": best_surge["days"],
            "mz_consolidation_days": consol_days,
            "mz_consolidation_range_pct": round(consol_range_pct, 1),
            "mz_atr_contraction_ratio": atr_contraction,
            "mz_volume_shrink_ratio": vol_shrink_ratio,
            "mz_upper_bound": int(upper_bound),
            "mz_distance_to_upper_pct": distance_to_upper,
        }

    # ── 시그널 감지: 캔들 수축 ──

    def _detect_candle_squeeze(self, ohlcv: dict, common: dict) -> Optional[dict]:
        """캔들 수축(VCP) 감지.

        조정 중 캔들 레인지가 점진적으로 줄어드는 구간 탐지.
        매도 압력 소진 → 변동성 수축 → 돌파 준비 패턴.
        """
        closes = ohlcv["closes"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        opens = ohlcv["opens"]
        volumes = ohlcv["volumes"]
        current = common["current_price"]

        n = len(closes)
        if n < 60:
            return None

        # ── 1차 필터: 60일 내 고점 대비 -7% ~ -30% 조정 중 ──
        n60 = min(60, n)
        high_60d = float(np.max(highs[-n60:]))
        if high_60d <= 0:
            return None

        correction_depth_pct = round((high_60d - current) / high_60d * 100, 2)
        if correction_depth_pct < 7 or correction_depth_pct > 30:
            return None

        # 고점 위치 찾기
        high_idx_in_window = int(np.argmax(highs[-n60:]))
        high_idx = n - n60 + high_idx_in_window

        # 조정 기간 (고점 이후 ~ 현재)
        correction_days = n - 1 - high_idx
        if correction_days < 10:
            return None

        # ── 캔들 수축 측정: 조정 구간을 3등분 ──
        corr_start = high_idx + 1
        corr_end = n
        corr_len = corr_end - corr_start
        if corr_len < 9:
            return None

        seg_len = corr_len // 3
        seg1_start = corr_start
        seg1_end = corr_start + seg_len
        seg3_start = corr_end - seg_len
        seg3_end = corr_end

        # 레인지 수축: high - low
        ranges_1 = highs[seg1_start:seg1_end] - lows[seg1_start:seg1_end]
        ranges_3 = highs[seg3_start:seg3_end] - lows[seg3_start:seg3_end]
        avg_range_1 = float(np.mean(ranges_1)) if len(ranges_1) > 0 else 1.0
        avg_range_3 = float(np.mean(ranges_3)) if len(ranges_3) > 0 else 1.0

        if avg_range_1 <= 0:
            return None
        contraction_pct = round((avg_range_3 - avg_range_1) / avg_range_1 * 100, 2)

        # 몸통 수축: |close - open|
        bodies_1 = np.abs(closes[seg1_start:seg1_end] - opens[seg1_start:seg1_end])
        bodies_3 = np.abs(closes[seg3_start:seg3_end] - opens[seg3_start:seg3_end])
        avg_body_1 = float(np.mean(bodies_1)) if len(bodies_1) > 0 else 1.0
        avg_body_3 = float(np.mean(bodies_3)) if len(bodies_3) > 0 else 1.0

        body_contraction_pct = round((avg_body_3 - avg_body_1) / avg_body_1 * 100, 2) if avg_body_1 > 0 else 0.0

        # 거래량 수축비
        vol_1 = float(np.mean(volumes[seg1_start:seg1_end])) if len(volumes[seg1_start:seg1_end]) > 0 else 1.0
        vol_3 = float(np.mean(volumes[seg3_start:seg3_end])) if len(volumes[seg3_start:seg3_end]) > 0 else 1.0
        volume_shrink_ratio = round(vol_3 / vol_1, 2) if vol_1 > 0 else 1.0

        # ── 스코어링 (100점) ──
        breakdown = {}

        # 1) 레인지 수축도 (25점)
        if contraction_pct <= -50:
            range_score = 25.0
        elif contraction_pct <= -30:
            range_score = 20.0
        elif contraction_pct <= -20:
            range_score = 15.0
        elif contraction_pct <= -10:
            range_score = 10.0
        elif contraction_pct <= 0:
            range_score = 5.0
        else:
            range_score = 0.0
        breakdown["range_contraction"] = round(range_score, 1)

        # 2) 몸통 수축도 (15점)
        if body_contraction_pct <= -50:
            body_score = 15.0
        elif body_contraction_pct <= -30:
            body_score = 12.0
        elif body_contraction_pct <= -20:
            body_score = 9.0
        elif body_contraction_pct <= -10:
            body_score = 6.0
        elif body_contraction_pct <= 0:
            body_score = 3.0
        else:
            body_score = 0.0
        breakdown["body_contraction"] = round(body_score, 1)

        # 3) 거래량 감소 (20점)
        if volume_shrink_ratio <= 0.3:
            vol_score = 20.0
        elif volume_shrink_ratio <= 0.5:
            vol_score = 16.0
        elif volume_shrink_ratio <= 0.7:
            vol_score = 12.0
        elif volume_shrink_ratio <= 1.0:
            vol_score = 8.0
        else:
            vol_score = 0.0
        breakdown["volume_shrink"] = round(vol_score, 1)

        # 4) MA 지지 근접 (15점)
        ma20 = common.get("ma20")
        ma50 = common.get("ma50")
        ma60 = int(np.mean(closes[-60:])) if n >= 60 else None
        ma120 = int(np.mean(closes[-120:])) if n >= 120 else None

        ma_distances = []
        for ma in [ma20, ma60, ma120]:
            if ma and ma > 0:
                ma_distances.append(abs((current - ma) / ma * 100))

        if ma_distances:
            min_ma_dist = min(ma_distances)
            if min_ma_dist <= 1:
                ma_score = 15.0
            elif min_ma_dist <= 3:
                ma_score = 12.0
            elif min_ma_dist <= 5:
                ma_score = 8.0
            elif min_ma_dist <= 7:
                ma_score = 4.0
            else:
                ma_score = 0.0
        else:
            ma_score = 0.0
        breakdown["ma_proximity"] = round(ma_score, 1)

        # 5) 조정 깊이 적절성 (15점)
        if 10 <= correction_depth_pct <= 20:
            depth_score = 15.0
        elif 7 <= correction_depth_pct < 10:
            depth_score = 10.0
        elif 20 < correction_depth_pct <= 25:
            depth_score = 8.0
        elif 25 < correction_depth_pct <= 30:
            depth_score = 4.0
        else:
            depth_score = 0.0
        breakdown["correction_depth"] = round(depth_score, 1)

        # 6) 정배열 유지 (10점)
        align_score = 0.0
        if ma20 and ma60 and ma20 > ma60:
            align_score += 5.0
        if ma60 and current > ma60:
            align_score += 3.0
        if ma60 and ma120 and ma60 > ma120:
            align_score += 2.0
        breakdown["ma_alignment"] = round(align_score, 1)

        total = range_score + body_score + vol_score + ma_score + depth_score + align_score

        if total < 40:
            return None

        return {
            "signal_type": SignalType.CANDLE_SQUEEZE,
            "total_score": round(min(total, 100), 1),
            "grade": _grade_from_score(min(total, 100)),
            "score_breakdown": breakdown,
            "cs_contraction_pct": contraction_pct,
            "cs_body_contraction_pct": body_contraction_pct,
            "cs_volume_shrink_ratio": volume_shrink_ratio,
            "cs_correction_days": correction_days,
            "cs_correction_depth_pct": correction_depth_pct,
        }

    def _detect_candle_expansion(self, ohlcv: dict, common: dict) -> Optional[dict]:
        """캔들 확장 감지.

        조용했던 종목에서 레인지/몸통/거래량이 점진적으로 확대 → 새 추세 시작 초기.
        """
        closes = ohlcv["closes"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        opens = ohlcv["opens"]
        volumes = ohlcv["volumes"]
        current = common["current_price"]

        n = len(closes)
        if n < 40:
            return None

        # ── 최근 30일을 3등분 (각 10일) ──
        seg1_start = n - 30
        seg1_end = n - 20
        seg2_start = n - 20
        seg2_end = n - 10
        seg3_start = n - 10
        seg3_end = n

        if seg1_start < 0:
            return None

        # ── 1차 필터 ──
        # 60일 ATR 계산
        n60 = min(60, n)
        ranges_60 = highs[-n60:] - lows[-n60:]
        atr_60 = float(np.mean(ranges_60)) if len(ranges_60) > 0 else 1.0
        if atr_60 <= 0:
            return None

        # 1구간 레인지 평균이 60일 ATR 이하 (원래 조용했어야 함)
        ranges_1 = highs[seg1_start:seg1_end] - lows[seg1_start:seg1_end]
        avg_range_1 = float(np.mean(ranges_1)) if len(ranges_1) > 0 else 1.0
        if avg_range_1 > atr_60:
            return None

        # 3구간에 양봉이 1개 이상 (완전 하락장 제외)
        bullish_3 = np.sum(closes[seg3_start:seg3_end] > opens[seg3_start:seg3_end])
        if bullish_3 < 1:
            return None

        # ── 캔들 확장 측정 ──
        # 레인지 확장
        ranges_3 = highs[seg3_start:seg3_end] - lows[seg3_start:seg3_end]
        avg_range_3 = float(np.mean(ranges_3)) if len(ranges_3) > 0 else 1.0
        expansion_pct = round((avg_range_3 - avg_range_1) / avg_range_1 * 100, 2) if avg_range_1 > 0 else 0.0

        # 몸통 확장
        bodies_1 = np.abs(closes[seg1_start:seg1_end] - opens[seg1_start:seg1_end])
        bodies_3 = np.abs(closes[seg3_start:seg3_end] - opens[seg3_start:seg3_end])
        avg_body_1 = float(np.mean(bodies_1)) if len(bodies_1) > 0 else 1.0
        avg_body_3 = float(np.mean(bodies_3)) if len(bodies_3) > 0 else 1.0
        body_expansion_pct = round((avg_body_3 - avg_body_1) / avg_body_1 * 100, 2) if avg_body_1 > 0 else 0.0

        # 거래량 증가비 (3구간/1구간)
        vol_1 = float(np.mean(volumes[seg1_start:seg1_end])) if len(volumes[seg1_start:seg1_end]) > 0 else 1.0
        vol_3 = float(np.mean(volumes[seg3_start:seg3_end])) if len(volumes[seg3_start:seg3_end]) > 0 else 1.0
        volume_surge_ratio = round(vol_3 / vol_1, 2) if vol_1 > 0 else 1.0

        # 3구간 양봉비율
        seg3_len = seg3_end - seg3_start
        bullish_pct = round(float(bullish_3) / seg3_len * 100, 1) if seg3_len > 0 else 0.0

        # ── 스코어링 (100점) ──
        breakdown = {}

        # 1) 레인지 확장도 (25점)
        if expansion_pct >= 100:
            range_score = 25.0
        elif expansion_pct >= 50:
            range_score = 20.0
        elif expansion_pct >= 30:
            range_score = 15.0
        elif expansion_pct >= 10:
            range_score = 10.0
        else:
            range_score = 0.0
        breakdown["range_expansion"] = round(range_score, 1)

        # 2) 몸통 확장도 (15점)
        if body_expansion_pct >= 100:
            body_score = 15.0
        elif body_expansion_pct >= 50:
            body_score = 12.0
        elif body_expansion_pct >= 30:
            body_score = 9.0
        elif body_expansion_pct >= 10:
            body_score = 6.0
        else:
            body_score = 0.0
        breakdown["body_expansion"] = round(body_score, 1)

        # 3) 거래량 증가 (20점)
        if volume_surge_ratio >= 2.0:
            vol_score = 20.0
        elif volume_surge_ratio >= 1.5:
            vol_score = 16.0
        elif volume_surge_ratio >= 1.2:
            vol_score = 12.0
        elif volume_surge_ratio >= 1.0:
            vol_score = 8.0
        else:
            vol_score = 0.0
        breakdown["volume_surge"] = round(vol_score, 1)

        # 4) 상승 방향성 (20점)
        # 3구간 양봉비율 (12점)
        if bullish_pct >= 70:
            bullish_score = 12.0
        elif bullish_pct >= 60:
            bullish_score = 9.0
        elif bullish_pct >= 50:
            bullish_score = 6.0
        elif bullish_pct >= 40:
            bullish_score = 3.0
        else:
            bullish_score = 0.0

        # 3구간 종가추세 (8점) - 선형 회귀 기울기
        seg3_closes = closes[seg3_start:seg3_end]
        if len(seg3_closes) >= 3:
            x = np.arange(len(seg3_closes))
            slope = float(np.polyfit(x, seg3_closes, 1)[0])
            avg_price_seg3 = float(np.mean(seg3_closes))
            slope_pct = (slope / avg_price_seg3 * 100) if avg_price_seg3 > 0 else 0
            if slope_pct >= 1.0:
                trend_score = 8.0
            elif slope_pct >= 0.5:
                trend_score = 6.0
            elif slope_pct >= 0.1:
                trend_score = 3.0
            else:
                trend_score = 0.0
        else:
            trend_score = 0.0

        direction_score = bullish_score + trend_score
        breakdown["direction"] = round(direction_score, 1)

        # 5) MA 정배열 (10점)
        ma20 = common.get("ma20")
        ma60 = int(np.mean(closes[-60:])) if n >= 60 else None
        ma120 = int(np.mean(closes[-120:])) if n >= 120 else None

        align_score = 0.0
        if ma20 and ma60 and ma20 > ma60:
            align_score += 4.0
        if ma20 and current > ma20:
            align_score += 3.0
        if ma60 and ma120 and ma60 > ma120:
            align_score += 3.0
        breakdown["ma_alignment"] = round(align_score, 1)

        # 6) 직전 침체 깊이 (10점) - 1구간 레인지/60일ATR 비율 낮을수록 가점
        quiet_ratio = avg_range_1 / atr_60 if atr_60 > 0 else 1.0
        if quiet_ratio <= 0.3:
            quiet_score = 10.0
        elif quiet_ratio <= 0.5:
            quiet_score = 8.0
        elif quiet_ratio <= 0.7:
            quiet_score = 6.0
        elif quiet_ratio <= 0.9:
            quiet_score = 4.0
        else:
            quiet_score = 2.0
        breakdown["quiet_depth"] = round(quiet_score, 1)

        total = range_score + body_score + vol_score + direction_score + align_score + quiet_score

        if total < 40:
            return None

        return {
            "signal_type": SignalType.CANDLE_EXPANSION,
            "total_score": round(min(total, 100), 1),
            "grade": _grade_from_score(min(total, 100)),
            "score_breakdown": breakdown,
            "ce_expansion_pct": expansion_pct,
            "ce_body_expansion_pct": body_expansion_pct,
            "ce_volume_surge_ratio": volume_surge_ratio,
            "ce_bullish_pct": bullish_pct,
        }

    # ── 유틸리티: 로컬 고점/저점 인덱스 찾기 ──

    @staticmethod
    def _find_peaks_troughs(closes: np.ndarray, window: int = 10) -> tuple[list[int], list[int]]:
        peaks, troughs = [], []
        n = len(closes)
        for i in range(window, n - window):
            seg = closes[max(0, i - window):i + window + 1]
            if float(closes[i]) == float(np.max(seg)):
                peaks.append(i)
            elif float(closes[i]) == float(np.min(seg)):
                troughs.append(i)
        return peaks, troughs

    # ── 시그널 감지: 120일선 전환 ──

    def _detect_ma120_turn(self, ohlcv: dict, common: dict) -> Optional[dict]:
        """120일 이평선 전환 감지.

        핵심 컨셉: "120일선을 돌리는 것은 거래량이다"
        하락파동 절반 회복 = 120일선 전환, 쌍바닥 + 거래량 + 저항돌파 = 매수 타점.
        """
        closes = ohlcv["closes"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        volumes = ohlcv["volumes"]
        current = common["current_price"]

        n = len(closes)
        if n < 130:
            return None

        # ── MA120 계산 ──
        ma120 = float(np.mean(closes[-120:]))
        if ma120 <= 0:
            return None

        # MA120 기울기: 20일 전 MA120 대비 변화율
        ma120_20d_ago = float(np.mean(closes[-140:-20])) if n >= 140 else float(np.mean(closes[:120]))
        ma120_slope_pct = round((ma120 - ma120_20d_ago) / ma120_20d_ago * 100, 2) if ma120_20d_ago > 0 else 0.0

        # MA120 대비 현재가 거리
        ma120_distance_pct = round((current - ma120) / ma120 * 100, 2)

        # ── 1차 필터 ──
        # MA120 기울기 >= -0.5% (강한 하락 제외)
        if ma120_slope_pct < -0.5:
            return None

        # 현재가 MA120 대비 -5% ~ +10% 범위
        if ma120_distance_pct < -5 or ma120_distance_pct > 10:
            return None

        # 거래량비 (5일/20일) >= 1.3
        vol_ratio = common["volume_ratio"]
        if vol_ratio < 1.3:
            return None

        # ── 하락파동 회복률 계산 ──
        # 최근 120일 내 고점→저점 하락파동, 현재 회복 비율
        n120 = min(120, n)
        high_120d = float(np.max(highs[-n120:]))
        low_120d = float(np.min(lows[-n120:]))
        if high_120d <= low_120d:
            return None
        recovery_pct = round((current - low_120d) / (high_120d - low_120d) * 100, 2)

        # ── 쌍바닥 감지 (W패턴) ──
        troughs_idx = []
        # 60일 내 저점들 찾기
        _, troughs = self._find_peaks_troughs(closes[-n120:], window=7)
        has_double_bottom = False
        if len(troughs) >= 2:
            # 마지막 2개 저점 비교: 가격 차이 5% 이내
            t1_price = float(closes[-n120:][troughs[-2]])
            t2_price = float(closes[-n120:][troughs[-1]])
            if t1_price > 0:
                diff_pct = abs(t2_price - t1_price) / t1_price * 100
                if diff_pct <= 5:
                    has_double_bottom = True

        # ── 이전 저항 돌파 감지 ──
        peaks, _ = self._find_peaks_troughs(closes[-n120:], window=7)
        resistance_broken = False
        if len(peaks) >= 1:
            # 가장 최근 고점 가격 기준
            last_peak_price = float(closes[-n120:][peaks[-1]])
            if current > last_peak_price:
                resistance_broken = True

        # ── 신고 거래량 감지 ──
        has_new_high_volume = False
        volume_surge_ratio = 1.0
        if n >= 60:
            vol_5d_avg = float(np.mean(volumes[-5:]))
            vol_20d_avg = float(np.mean(volumes[-20:]))
            vol_60d_max = float(np.max(volumes[-60:-5])) if n >= 65 else float(np.max(volumes[:-5]))
            volume_surge_ratio = round(vol_5d_avg / vol_20d_avg, 2) if vol_20d_avg > 0 else 1.0

            # 최근 5일 최대 거래량이 60일 최대를 넘는지
            vol_5d_max = float(np.max(volumes[-5:]))
            if vol_60d_max > 0 and vol_5d_max > vol_60d_max:
                has_new_high_volume = True

        # ── 스코어링 (100점) ──
        breakdown = {}

        # 1) MA120 기울기 전환 (20점)
        if ma120_slope_pct > 0:
            slope_score = 20.0
        elif ma120_slope_pct >= -0.1:
            slope_score = 15.0
        elif ma120_slope_pct >= -0.3:
            slope_score = 12.0
        else:
            slope_score = 10.0
        breakdown["ma120_slope"] = round(slope_score, 1)

        # 2) MA120 근접도 (15점)
        abs_dist = abs(ma120_distance_pct)
        if abs_dist <= 1:
            prox_score = 15.0
        elif abs_dist <= 2:
            prox_score = 13.0
        elif abs_dist <= 3:
            prox_score = 11.0
        elif abs_dist <= 5:
            prox_score = 8.0
        else:
            prox_score = 4.0
        breakdown["ma120_proximity"] = round(prox_score, 1)

        # 3) 거래량 증가 (20점)
        if has_new_high_volume and volume_surge_ratio >= 2.0:
            vol_score = 20.0
        elif has_new_high_volume:
            vol_score = 16.0
        elif volume_surge_ratio >= 2.0:
            vol_score = 14.0
        elif volume_surge_ratio >= 1.5:
            vol_score = 10.0
        else:
            vol_score = 7.0
        breakdown["volume_surge"] = round(vol_score, 1)

        # 4) 하락파동 회복률 (15점)
        if recovery_pct >= 70:
            recovery_score = 15.0
        elif recovery_pct >= 60:
            recovery_score = 13.0
        elif recovery_pct >= 50:
            recovery_score = 10.0
        elif recovery_pct >= 40:
            recovery_score = 6.0
        else:
            recovery_score = 2.0
        breakdown["recovery"] = round(recovery_score, 1)

        # 5) 쌍바닥 패턴 (10점)
        double_bottom_score = 10.0 if has_double_bottom else 0.0
        breakdown["double_bottom"] = round(double_bottom_score, 1)

        # 6) 이전 저항 돌파 (10점)
        resistance_score = 10.0 if resistance_broken else 0.0
        breakdown["resistance_break"] = round(resistance_score, 1)

        # 7) MA 정배열 시작 (10점)
        align_score = 0.0
        ma20 = common.get("ma20")
        ma60 = float(np.mean(closes[-60:])) if n >= 60 else None
        if ma20 and ma60 and ma20 > ma60:
            align_score += 5.0
        if ma20 and current > ma20:
            align_score += 3.0
        if ma20 and ma20 > ma120:
            align_score += 2.0
        breakdown["ma_alignment"] = round(align_score, 1)

        total = slope_score + prox_score + vol_score + recovery_score + double_bottom_score + resistance_score + align_score

        if total < 40:
            return None

        return {
            "signal_type": SignalType.MA120_TURN,
            "total_score": round(min(total, 100), 1),
            "grade": _grade_from_score(min(total, 100)),
            "score_breakdown": breakdown,
            "ma120": int(ma120),
            "ma120_slope_pct": ma120_slope_pct,
            "ma120_distance_pct": ma120_distance_pct,
            "recovery_pct": round(recovery_pct, 1),
            "has_double_bottom": has_double_bottom,
            "resistance_broken": resistance_broken,
            "has_new_high_volume": has_new_high_volume,
            "volume_surge_ratio": volume_surge_ratio,
        }

    # ── 통합 분석 ──

    async def _bulk_analyze(self, signal_filter: Optional[str] = None, mss_timeframe: str = "daily") -> list[SignalStock]:
        all_stocks = await self._get_all_stocks()
        stock_codes = [s["code"] for s in all_stocks]
        code_to_name = {s["code"]: s["name"] for s in all_stocks}

        days = 365 if (signal_filter is None or signal_filter in ("mss_proximity", "ma120_turn")) else 120
        ohlcv_map = await self._bulk_get_ohlcv(stock_codes, days=days)
        flow_map = await self._bulk_get_flow(stock_codes, days=20)
        quality_map = await self._bulk_get_financial_quality(stock_codes)

        default_flow = {"foreign_net_5d": 0, "institution_net_5d": 0, "flow_list": []}
        results: list[SignalStock] = []

        for code in stock_codes:
            ohlcv = ohlcv_map.get(code)
            if ohlcv is None:
                continue

            common = self._calc_common(ohlcv)

            # ── 잡주 필터 ──
            current = common["current_price"]
            if current < 2000:
                continue
            # 20일 평균 거래대금 5억원 미만 제외
            vols = ohlcv["volumes"]
            avg_vol = float(np.mean(vols[-20:])) if len(vols) >= 20 else float(np.mean(vols))
            avg_trading_value = current * avg_vol
            if avg_trading_value < 500_000_000:
                continue

            flow = flow_map.get(code, default_flow)
            quality = quality_map.get(code, {})
            themes = self._tms.get_themes_for_stock(code)[:3]

            # 기관+외인 순매수 여부
            has_inst_buying = (flow.get("foreign_net_5d", 0) + flow.get("institution_net_5d", 0)) > 0

            detectors = []
            if signal_filter is None or signal_filter == "pullback":
                detectors.append(self._detect_pullback)
            if signal_filter is None or signal_filter == "high_breakout":
                detectors.append(self._detect_high_breakout)
            if signal_filter is None or signal_filter == "resistance_test":
                detectors.append(self._detect_resistance_test)
            if signal_filter is None or signal_filter == "support_test":
                detectors.append(self._detect_support_test)
            if signal_filter is None or signal_filter == "mss_proximity":
                detectors.append(lambda o, c: self._detect_mss_proximity(o, c, timeframe=mss_timeframe))
            if signal_filter is None or signal_filter == "momentum_zone":
                detectors.append(self._detect_momentum_zone)
            if signal_filter is None or signal_filter == "ma120_turn":
                detectors.append(self._detect_ma120_turn)
            if signal_filter is None or signal_filter == "candle_squeeze":
                detectors.append(self._detect_candle_squeeze)
            if signal_filter is None or signal_filter == "candle_expansion":
                detectors.append(self._detect_candle_expansion)

            for detect_fn in detectors:
                try:
                    sig = detect_fn(ohlcv, common)
                    if sig is None:
                        continue

                    # 품질 보너스 반영
                    q_score = quality.get("quality_score", 0)
                    adjusted_score = sig["total_score"] + q_score

                    results.append(SignalStock(
                        stock_code=code,
                        stock_name=code_to_name.get(code, ""),
                        signal_type=sig["signal_type"],
                        current_price=common["current_price"],
                        total_score=round(adjusted_score, 1),
                        grade=_grade_from_score(adjusted_score),
                        themes=themes,
                        ma20=common["ma20"],
                        ma50=common["ma50"],
                        ma20_distance_pct=common["ma20_distance_pct"],
                        ma50_distance_pct=common["ma50_distance_pct"],
                        volume_ratio=common["volume_ratio"],
                        high_price_60d=common["high_price_60d"],
                        low_price_60d=common["low_price_60d"],
                        percentile_60d=common["percentile_60d"],
                        score_breakdown={**sig.get("score_breakdown", {}), "quality": q_score},
                        # 눌림목
                        pullback_pct=sig.get("pullback_pct"),
                        support_line=sig.get("support_line"),
                        support_distance_pct=sig.get("support_distance_pct"),
                        volume_decreasing=sig.get("volume_decreasing", False),
                        surge_pct=sig.get("surge_pct"),
                        # 전고점 돌파
                        prev_high_price=sig.get("prev_high_price"),
                        prev_high_date=sig.get("prev_high_date"),
                        breakout_pct=sig.get("breakout_pct"),
                        breakout_volume_ratio=sig.get("breakout_volume_ratio"),
                        # 저항 돌파 시도
                        resistance_price=sig.get("resistance_price"),
                        resistance_touch_count=sig.get("resistance_touch_count"),
                        resistance_distance_pct=sig.get("resistance_distance_pct"),
                        # 지지선 테스트
                        support_price=sig.get("support_price"),
                        support_touch_count=sig.get("support_touch_count"),
                        consolidation_days=sig.get("consolidation_days"),
                        ma_support_aligned=sig.get("ma_support_aligned"),
                        # MSS 근접
                        mss_level=sig.get("mss_level"),
                        mss_type=sig.get("mss_type"),
                        mss_distance_pct=sig.get("mss_distance_pct"),
                        mss_touch_count=sig.get("mss_touch_count"),
                        mss_timeframe=sig.get("mss_timeframe"),
                        # 관성 구간
                        mz_surge_pct=sig.get("mz_surge_pct"),
                        mz_surge_days=sig.get("mz_surge_days"),
                        mz_consolidation_days=sig.get("mz_consolidation_days"),
                        mz_consolidation_range_pct=sig.get("mz_consolidation_range_pct"),
                        mz_atr_contraction_ratio=sig.get("mz_atr_contraction_ratio"),
                        mz_volume_shrink_ratio=sig.get("mz_volume_shrink_ratio"),
                        mz_upper_bound=sig.get("mz_upper_bound"),
                        mz_distance_to_upper_pct=sig.get("mz_distance_to_upper_pct"),
                        # 120일선 전환
                        ma120=sig.get("ma120"),
                        ma120_slope_pct=sig.get("ma120_slope_pct"),
                        ma120_distance_pct=sig.get("ma120_distance_pct"),
                        recovery_pct=sig.get("recovery_pct"),
                        has_double_bottom=sig.get("has_double_bottom", False),
                        resistance_broken=sig.get("resistance_broken", False),
                        has_new_high_volume=sig.get("has_new_high_volume", False),
                        volume_surge_ratio=sig.get("volume_surge_ratio"),
                        # 캔들 수축
                        cs_contraction_pct=sig.get("cs_contraction_pct"),
                        cs_body_contraction_pct=sig.get("cs_body_contraction_pct"),
                        cs_volume_shrink_ratio=sig.get("cs_volume_shrink_ratio"),
                        cs_correction_days=sig.get("cs_correction_days"),
                        cs_correction_depth_pct=sig.get("cs_correction_depth_pct"),
                        # 캔들 확장
                        ce_expansion_pct=sig.get("ce_expansion_pct"),
                        ce_body_expansion_pct=sig.get("ce_body_expansion_pct"),
                        ce_volume_surge_ratio=sig.get("ce_volume_surge_ratio"),
                        ce_bullish_pct=sig.get("ce_bullish_pct"),
                        # 거래대금
                        avg_trading_value=avg_trading_value,
                        # 수급 (참조)
                        foreign_net_5d=flow.get("foreign_net_5d", 0),
                        institution_net_5d=flow.get("institution_net_5d", 0),
                        # 품질
                        is_profitable=quality.get("is_profitable"),
                        is_growing=quality.get("is_growing"),
                        has_institutional_buying=has_inst_buying,
                        quality_score=q_score,
                        revenue_growth=quality.get("revenue_growth"),
                    ))
                except Exception as e:
                    logger.warning(f"시그널 감지 실패 ({code}, {detect_fn.__name__}): {e}")

        results.sort(key=lambda s: s.total_score, reverse=True)
        return results

    # ── 관성 구간 백테스트 ──

    async def run_momentum_zone_backtest(
        self,
        lookback_days: int = 365,
        holding_days: list[int] | None = None,
        min_score: int = 40,
        step_days: int = 1,
    ) -> dict:
        """관성 구간 시그널의 과거 수익률을 백테스트한다.

        OHLCV를 슬라이딩 윈도우로 슬라이스하여 각 시점에서 _detect_momentum_zone 을
        호출하고, 다음 거래일 시가 진입 → N일 후 종가 청산 수익률을 계산한다.
        """
        if holding_days is None:
            holding_days = [5, 10, 20]
        max_hold = max(holding_days)
        min_data_len = 120  # _detect_momentum_zone 최소 40이지만 common 포함 여유

        all_stocks = await self._get_all_stocks()
        stock_codes = [s["code"] for s in all_stocks]
        code_to_name = {s["code"]: s["name"] for s in all_stocks}

        total_days_needed = lookback_days + min_data_len + max_hold + 30
        ohlcv_map = await self._bulk_get_ohlcv(stock_codes, days=total_days_needed)

        signals: list[dict] = []

        for code in stock_codes:
            ohlcv = ohlcv_map.get(code)
            if ohlcv is None:
                continue

            closes = ohlcv["closes"]
            opens = ohlcv["opens"]
            volumes = ohlcv["volumes"]
            n = len(closes)

            if n < min_data_len + max_hold + 5:
                continue

            current_price = float(closes[-1])
            # 잡주 필터
            if current_price < 2000:
                continue
            avg_vol = float(np.mean(volumes[-20:])) if n >= 20 else float(np.mean(volumes))
            if current_price * avg_vol < 500_000_000:
                continue

            # 사전 필터: 20일 윈도우에 15%+ 상승 이력이 전혀 없으면 스킵
            has_any_surge = False
            for i in range(20, min(n, min_data_len + lookback_days)):
                window_low = float(np.min(ohlcv["lows"][max(0, i - 20):i]))
                window_high = float(np.max(ohlcv["highs"][max(0, i - 20):i]))
                if window_low > 0 and (window_high - window_low) / window_low >= 0.15:
                    has_any_surge = True
                    break
            if not has_any_surge:
                continue

            # 스캔 범위 결정
            scan_end = n - max_hold - 1  # 마지막 holding 기간 확보
            scan_start = max(min_data_len, n - lookback_days - min_data_len)

            last_signal_idx = -999  # 쿨다운 추적

            for end_idx in range(scan_start, scan_end, step_days):
                # 쿨다운: 같은 종목 5일 이내 중복 방지
                if end_idx - last_signal_idx < 5:
                    continue

                # ohlcv 슬라이스
                sliced = {
                    "dates": ohlcv["dates"][:end_idx + 1],
                    "opens": ohlcv["opens"][:end_idx + 1],
                    "highs": ohlcv["highs"][:end_idx + 1],
                    "lows": ohlcv["lows"][:end_idx + 1],
                    "closes": ohlcv["closes"][:end_idx + 1],
                    "volumes": ohlcv["volumes"][:end_idx + 1],
                }
                try:
                    common = self._calc_common(sliced)
                    sig = self._detect_momentum_zone(sliced, common)
                except Exception:
                    continue

                if sig is None or sig["total_score"] < min_score:
                    continue

                last_signal_idx = end_idx

                # 다음 거래일 시가로 진입
                entry_idx = end_idx + 1
                if entry_idx >= n:
                    continue
                entry_price = float(opens[entry_idx])
                if entry_price <= 0:
                    continue

                signal_date = ohlcv["dates"][end_idx]
                entry_date = ohlcv["dates"][entry_idx]

                # 보유기간별 수익률 계산
                returns: dict[str, float | None] = {}
                for hd in holding_days:
                    exit_idx = entry_idx + hd
                    if exit_idx < n:
                        exit_price = float(closes[exit_idx])
                        returns[f"{hd}d"] = round((exit_price - entry_price) / entry_price * 100, 2)
                    else:
                        returns[f"{hd}d"] = None

                signals.append({
                    "stock_code": code,
                    "stock_name": code_to_name.get(code, ""),
                    "signal_date": signal_date.isoformat() if hasattr(signal_date, "isoformat") else str(signal_date),
                    "entry_date": entry_date.isoformat() if hasattr(entry_date, "isoformat") else str(entry_date),
                    "entry_price": int(entry_price),
                    "score": sig["total_score"],
                    "surge_pct": sig.get("mz_surge_pct", 0),
                    "consol_days": sig.get("mz_consolidation_days", 0),
                    "consol_range_pct": sig.get("mz_consolidation_range_pct", 0),
                    **returns,
                })

        return self._analyze_mz_backtest(
            signals, holding_days, lookback_days, min_score, step_days,
        )

    @staticmethod
    def _analyze_mz_backtest(
        signals: list[dict],
        holding_days: list[int],
        lookback_days: int,
        min_score: int,
        step_days: int,
    ) -> dict:
        """백테스트 결과 통계 분석."""

        # ── holding_stats ──
        holding_stats: dict[str, dict | None] = {}
        for hd in holding_days:
            key = f"{hd}d"
            valid = [s[key] for s in signals if s.get(key) is not None]
            if valid:
                sorted_rets = sorted(valid)
                n = len(sorted_rets)
                holding_stats[key] = {
                    "sample_count": n,
                    "avg_return": round(sum(valid) / n, 2),
                    "median": round(sorted_rets[n // 2], 2),
                    "win_rate": round(sum(1 for r in valid if r > 0) / n * 100, 1),
                    "q1": round(sorted_rets[n // 4], 2),
                    "q3": round(sorted_rets[3 * n // 4], 2),
                    "max_return": round(max(valid), 2),
                    "max_loss": round(min(valid), 2),
                }
            else:
                holding_stats[key] = None

        # ── score_analysis (점수 구간별) ──
        buckets = [(40, 60), (60, 80), (80, 101)]
        score_analysis: list[dict] = []
        ref_key = f"{holding_days[1]}d" if len(holding_days) > 1 else f"{holding_days[0]}d"
        for lo, hi in buckets:
            subset = [s for s in signals if lo <= s["score"] < hi and s.get(ref_key) is not None]
            if subset:
                rets = [s[ref_key] for s in subset]
                score_analysis.append({
                    "label": f"{lo}~{hi if hi < 101 else '100'}",
                    "count": len(subset),
                    "avg_return": round(sum(rets) / len(rets), 2),
                    "win_rate": round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1),
                })

        # ── monthly_analysis ──
        monthly_map: dict[str, list[float]] = {}
        for s in signals:
            month = s["signal_date"][:7]
            ret = s.get(ref_key)
            if ret is not None:
                monthly_map.setdefault(month, []).append(ret)
        monthly_analysis = sorted([
            {
                "month": m,
                "signal_count": len(rets),
                "avg_return": round(sum(rets) / len(rets), 2),
                "win_rate": round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1),
            }
            for m, rets in monthly_map.items()
        ], key=lambda x: x["month"])

        # ── top / worst performers (ref_key 기준) ──
        ranked = [s for s in signals if s.get(ref_key) is not None]
        ranked.sort(key=lambda s: s[ref_key], reverse=True)
        top_performers = ranked[:10]
        worst_performers = ranked[-10:][::-1] if len(ranked) >= 10 else ranked[::-1][:10]

        return {
            "params": {
                "lookback_days": lookback_days,
                "holding_days": holding_days,
                "min_score": min_score,
                "step_days": step_days,
            },
            "total_signals": len(signals),
            "holding_stats": holding_stats,
            "score_analysis": score_analysis,
            "monthly_analysis": monthly_analysis,
            "top_performers": top_performers,
            "worst_performers": worst_performers,
        }

    # ── 공개 API ──

    async def get_top_picks(self, limit: int = 20) -> list[SignalStock]:
        """TOP 필터를 적용한 오늘의 매매 후보."""
        all_signals = await self._bulk_analyze(signal_filter=None)

        # TOP 필터 (강화): 60일위치<70%, 거래량비>1.5, 점수>=60, 거래대금>=10억, 수급순매수>0
        filtered = [
            s for s in all_signals
            if (s.percentile_60d is not None and s.percentile_60d < 70)
            and (s.volume_ratio is not None and s.volume_ratio > 1.5)
            and s.total_score >= 60
            and (s.avg_trading_value is not None and s.avg_trading_value >= 1_000_000_000)
            and (s.foreign_net_5d + s.institution_net_5d) > 0
        ]

        # 동일 종목 중복 제거 (최고 점수 시그널만 유지)
        best_by_code: dict[str, SignalStock] = {}
        for s in filtered:
            existing = best_by_code.get(s.stock_code)
            if existing is None or s.total_score > existing.total_score:
                best_by_code[s.stock_code] = s
        unique = list(best_by_code.values())

        # 점수 내림차순 정렬
        unique.sort(key=lambda s: s.total_score, reverse=True)
        return unique[:limit]

    async def get_signals(
        self,
        signal_type: Optional[str] = None,
        min_score: float = 0.0,
        limit: int = 200,
        only_profitable: bool = False,
        only_growing: bool = False,
        only_institutional: bool = False,
        mss_timeframe: str = "daily",
    ) -> list[SignalStock]:
        all_signals = await self._bulk_analyze(signal_filter=signal_type, mss_timeframe=mss_timeframe)
        filtered = [s for s in all_signals if s.total_score >= min_score]
        if only_profitable:
            filtered = [s for s in filtered if s.is_profitable is True]
        if only_growing:
            filtered = [s for s in filtered if s.is_growing is True]
        if only_institutional:
            filtered = [s for s in filtered if s.has_institutional_buying is True]
        return filtered[:limit]

    async def get_summary(self) -> dict:
        all_signals = await self._bulk_analyze()
        counts = {"pullback": 0, "high_breakout": 0, "resistance_test": 0, "support_test": 0, "mss_proximity": 0, "momentum_zone": 0, "ma120_turn": 0, "candle_squeeze": 0, "candle_expansion": 0}
        for s in all_signals:
            counts[s.signal_type.value] += 1

        # 트렌드 테마: 돌파/저항 시그널 종목의 테마 집계
        from collections import Counter
        theme_counter = Counter()
        trend_stocks: dict[str, list[str]] = {}  # theme → [종목명]
        for s in all_signals:
            if s.signal_type.value in ("high_breakout", "resistance_test"):
                for t in s.themes:
                    theme_counter[t] += 1
                    trend_stocks.setdefault(t, [])
                    if s.stock_name not in trend_stocks[t]:
                        trend_stocks[t].append(s.stock_name)

        trend_themes = [
            {
                "theme": theme,
                "count": cnt,
                "stocks": trend_stocks.get(theme, [])[:5],
            }
            for theme, cnt in theme_counter.most_common(10)
        ]

        counts["trend_themes"] = trend_themes

        # 수축 테마: 캔들 수축 시그널 종목의 테마별 집계 → "재주목 테마"
        sq_counter = Counter()
        sq_stocks: dict[str, list[dict]] = {}  # theme → [{name, code, score, ...}]
        for s in all_signals:
            if s.signal_type.value == "candle_squeeze":
                for t in s.themes:
                    sq_counter[t] += 1
                    sq_stocks.setdefault(t, [])
                    sq_stocks[t].append({
                        "name": s.stock_name,
                        "code": s.stock_code,
                        "score": s.total_score,
                        "contraction_pct": s.cs_contraction_pct,
                        "correction_days": s.cs_correction_days,
                        "correction_depth_pct": s.cs_correction_depth_pct,
                        "volume_shrink": s.cs_volume_shrink_ratio,
                    })

        squeeze_themes = []
        for theme, cnt in sq_counter.most_common(15):
            if cnt < 2:
                continue
            stocks_list = sq_stocks[theme]
            avg_score = sum(st["score"] for st in stocks_list) / len(stocks_list)
            contractions = [st["contraction_pct"] for st in stocks_list if st["contraction_pct"] is not None]
            avg_contraction = sum(contractions) / len(contractions) if contractions else 0
            depths = [st["correction_depth_pct"] for st in stocks_list if st["correction_depth_pct"] is not None]
            avg_depth = sum(depths) / len(depths) if depths else 0
            vol_shrinks = [st["volume_shrink"] for st in stocks_list if st["volume_shrink"] is not None]
            avg_vol_shrink = sum(vol_shrinks) / len(vol_shrinks) if vol_shrinks else 1.0

            # 준비도: 수축이 깊고 + 점수가 높고 + 거래량도 줄었으면 높음
            readiness = min(100, avg_score * 0.5 + abs(min(avg_contraction, 0)) * 0.5 + (1 - min(avg_vol_shrink, 1)) * 30)

            squeeze_themes.append({
                "theme": theme,
                "count": cnt,
                "avg_score": round(avg_score, 1),
                "avg_contraction_pct": round(avg_contraction, 1),
                "avg_correction_depth_pct": round(avg_depth, 1),
                "avg_volume_shrink": round(avg_vol_shrink, 2),
                "readiness": round(readiness, 1),
                "stocks": sorted(stocks_list, key=lambda x: x["score"], reverse=True)[:5],
            })
        squeeze_themes.sort(key=lambda x: (-x["count"], -x["readiness"]))

        counts["squeeze_themes"] = squeeze_themes

        # TOP 필터 기반 TOP picks 카운트
        seen_codes: set[str] = set()
        top_picks_count = 0
        for s in all_signals:
            if s.stock_code in seen_codes:
                continue
            if (s.percentile_60d is not None and s.percentile_60d < 70
                    and s.volume_ratio is not None and s.volume_ratio > 1.5
                    and s.total_score >= 60
                    and s.avg_trading_value is not None and s.avg_trading_value >= 1_000_000_000
                    and (s.foreign_net_5d + s.institution_net_5d) > 0):
                top_picks_count += 1
                seen_codes.add(s.stock_code)
        counts["top_picks"] = top_picks_count

        return counts

    async def get_by_stock_codes(
        self,
        stock_codes: list[str],
        min_score: float = 0.0,
        limit: int = 50,
    ) -> list[SignalStock]:
        # 지정 종목만 분석
        ohlcv_map = await self._bulk_get_ohlcv(stock_codes, days=365)
        flow_map = await self._bulk_get_flow(stock_codes, days=20)

        default_flow = {"foreign_net_5d": 0, "institution_net_5d": 0, "flow_list": []}
        code_to_name = {}
        for theme_stocks in self._tms.get_all_themes().values():
            for stock in theme_stocks:
                c = stock.get("code")
                if c in stock_codes:
                    code_to_name[c] = stock.get("name", "")

        results: list[SignalStock] = []
        for code in stock_codes:
            ohlcv = ohlcv_map.get(code)
            if ohlcv is None:
                continue
            common = self._calc_common(ohlcv)

            # 잡주 필터
            current = common["current_price"]
            if current < 2000:
                continue
            vols = ohlcv["volumes"]
            avg_vol = float(np.mean(vols[-20:])) if len(vols) >= 20 else float(np.mean(vols))
            avg_trading_value = current * avg_vol
            if avg_trading_value < 500_000_000:
                continue

            flow = flow_map.get(code, default_flow)
            themes = self._tms.get_themes_for_stock(code)[:3]

            for detect_fn in [self._detect_pullback, self._detect_high_breakout, self._detect_resistance_test, self._detect_support_test, lambda o, c: self._detect_mss_proximity(o, c, timeframe="daily"), self._detect_momentum_zone, self._detect_ma120_turn, self._detect_candle_squeeze, self._detect_candle_expansion]:
                try:
                    sig = detect_fn(ohlcv, common)
                    if sig and sig["total_score"] >= min_score:
                        results.append(SignalStock(
                            stock_code=code,
                            stock_name=code_to_name.get(code, code),
                            signal_type=sig["signal_type"],
                            current_price=common["current_price"],
                            total_score=sig["total_score"],
                            grade=sig["grade"],
                            themes=themes,
                            ma20=common["ma20"],
                            ma50=common["ma50"],
                            ma20_distance_pct=common["ma20_distance_pct"],
                            ma50_distance_pct=common["ma50_distance_pct"],
                            volume_ratio=common["volume_ratio"],
                            high_price_60d=common["high_price_60d"],
                            low_price_60d=common["low_price_60d"],
                            percentile_60d=common["percentile_60d"],
                            score_breakdown=sig.get("score_breakdown", {}),
                            pullback_pct=sig.get("pullback_pct"),
                            support_line=sig.get("support_line"),
                            support_distance_pct=sig.get("support_distance_pct"),
                            volume_decreasing=sig.get("volume_decreasing", False),
                            prev_high_price=sig.get("prev_high_price"),
                            prev_high_date=sig.get("prev_high_date"),
                            breakout_pct=sig.get("breakout_pct"),
                            breakout_volume_ratio=sig.get("breakout_volume_ratio"),
                            resistance_price=sig.get("resistance_price"),
                            resistance_touch_count=sig.get("resistance_touch_count"),
                            resistance_distance_pct=sig.get("resistance_distance_pct"),
                            support_price=sig.get("support_price"),
                            support_touch_count=sig.get("support_touch_count"),
                            consolidation_days=sig.get("consolidation_days"),
                            ma_support_aligned=sig.get("ma_support_aligned"),
                            mss_level=sig.get("mss_level"),
                            mss_type=sig.get("mss_type"),
                            mss_distance_pct=sig.get("mss_distance_pct"),
                            mss_touch_count=sig.get("mss_touch_count"),
                            mss_timeframe=sig.get("mss_timeframe"),
                            mz_surge_pct=sig.get("mz_surge_pct"),
                            mz_surge_days=sig.get("mz_surge_days"),
                            mz_consolidation_days=sig.get("mz_consolidation_days"),
                            mz_consolidation_range_pct=sig.get("mz_consolidation_range_pct"),
                            mz_atr_contraction_ratio=sig.get("mz_atr_contraction_ratio"),
                            mz_volume_shrink_ratio=sig.get("mz_volume_shrink_ratio"),
                            mz_upper_bound=sig.get("mz_upper_bound"),
                            mz_distance_to_upper_pct=sig.get("mz_distance_to_upper_pct"),
                            ma120=sig.get("ma120"),
                            ma120_slope_pct=sig.get("ma120_slope_pct"),
                            ma120_distance_pct=sig.get("ma120_distance_pct"),
                            recovery_pct=sig.get("recovery_pct"),
                            has_double_bottom=sig.get("has_double_bottom", False),
                            resistance_broken=sig.get("resistance_broken", False),
                            has_new_high_volume=sig.get("has_new_high_volume", False),
                            volume_surge_ratio=sig.get("volume_surge_ratio"),
                            cs_contraction_pct=sig.get("cs_contraction_pct"),
                            cs_body_contraction_pct=sig.get("cs_body_contraction_pct"),
                            cs_volume_shrink_ratio=sig.get("cs_volume_shrink_ratio"),
                            cs_correction_days=sig.get("cs_correction_days"),
                            cs_correction_depth_pct=sig.get("cs_correction_depth_pct"),
                            ce_expansion_pct=sig.get("ce_expansion_pct"),
                            ce_body_expansion_pct=sig.get("ce_body_expansion_pct"),
                            ce_volume_surge_ratio=sig.get("ce_volume_surge_ratio"),
                            ce_bullish_pct=sig.get("ce_bullish_pct"),
                            avg_trading_value=avg_trading_value,
                            foreign_net_5d=flow.get("foreign_net_5d", 0),
                            institution_net_5d=flow.get("institution_net_5d", 0),
                        ))
                except Exception as e:
                    logger.warning(f"시그널 감지 실패 ({code}): {e}")

        results.sort(key=lambda s: s.total_score, reverse=True)
        return results[:limit]

    async def get_stock_detail(self, stock_code: str) -> Optional[dict]:
        stock_name = ""
        for stocks in self._tms.get_all_themes().values():
            for s in stocks:
                if s.get("code") == stock_code:
                    stock_name = s.get("name", "")
                    break

        ohlcv_map = await self._bulk_get_ohlcv([stock_code], days=365)
        flow_map = await self._bulk_get_flow([stock_code], days=20)

        ohlcv = ohlcv_map.get(stock_code)
        if ohlcv is None:
            return None

        flow = flow_map.get(stock_code, {"foreign_net_5d": 0, "institution_net_5d": 0, "flow_list": []})
        common = self._calc_common(ohlcv)
        themes = self._tms.get_themes_for_stock(stock_code)[:3]

        # 모든 시그널 검출
        signals = []
        for detect_fn in [self._detect_pullback, self._detect_high_breakout, self._detect_resistance_test, self._detect_support_test, lambda o, c: self._detect_mss_proximity(o, c, timeframe="daily"), self._detect_momentum_zone, self._detect_ma120_turn, self._detect_candle_squeeze, self._detect_candle_expansion]:
            sig = detect_fn(ohlcv, common)
            if sig:
                signals.append(sig)

        best_signal = max(signals, key=lambda s: s["total_score"]) if signals else None

        stock_data = {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "current_price": common["current_price"],
            "themes": themes,
            **common,
        }
        if best_signal:
            stock_data.update({
                "signal_type": best_signal["signal_type"].value,
                "total_score": best_signal["total_score"],
                "grade": best_signal["grade"],
                "score_breakdown": best_signal.get("score_breakdown", {}),
            })

        # 가격 히스토리 (60일)
        n60 = min(60, len(ohlcv["dates"]))
        price_history = []
        for i in range(-n60, 0):
            price_history.append({
                "date": ohlcv["dates"][i].isoformat(),
                "open": int(ohlcv["opens"][i]),
                "high": int(ohlcv["highs"][i]),
                "low": int(ohlcv["lows"][i]),
                "close": int(ohlcv["closes"][i]),
                "volume": int(ohlcv["volumes"][i]),
            })

        # 수급 히스토리 (20일)
        flow_history = flow.get("flow_list", [])

        # 분석 요약
        summary_parts = []
        if best_signal:
            st = best_signal["signal_type"]
            if st == SignalType.PULLBACK:
                summary_parts.append(f"눌림목 {best_signal.get('pullback_pct', 0):.1f}% 조정")
            elif st == SignalType.HIGH_BREAKOUT:
                summary_parts.append(f"전고점 {best_signal.get('breakout_pct', 0):.1f}% 돌파")
            elif st == SignalType.RESISTANCE_TEST:
                summary_parts.append(f"저항선 접근 (거리 {best_signal.get('resistance_distance_pct', 0):.1f}%)")
            elif st == SignalType.SUPPORT_TEST:
                summary_parts.append(f"지지선 테스트 (거리 {best_signal.get('support_distance_pct', 0):.1f}%, {best_signal.get('support_touch_count', 0)}회 터치)")
            elif st == SignalType.MSS_PROXIMITY:
                summary_parts.append(f"저항선 근접 (거리 {best_signal.get('mss_distance_pct', 0):.1f}%, {best_signal.get('mss_touch_count', 0)}회 터치)")
            elif st == SignalType.MOMENTUM_ZONE:
                summary_parts.append(f"관성 구간 (급등 {best_signal.get('mz_surge_pct', 0):.0f}% → {best_signal.get('mz_consolidation_days', 0)}일 횡보, 상단거리 {best_signal.get('mz_distance_to_upper_pct', 0):.1f}%)")
            elif st == SignalType.CANDLE_SQUEEZE:
                summary_parts.append(f"캔들 수축 (수축률 {best_signal.get('cs_contraction_pct', 0):.0f}%, {best_signal.get('cs_correction_days', 0)}일 조정)")
            elif st == SignalType.CANDLE_EXPANSION:
                summary_parts.append(f"캔들 확장 (확장률 +{best_signal.get('ce_expansion_pct', 0):.0f}%, 양봉 {best_signal.get('ce_bullish_pct', 0):.0f}%)")
            summary_parts.append(f"등급 {best_signal['grade']} ({best_signal['total_score']:.0f}점)")

        if common["ma20_distance_pct"] is not None:
            summary_parts.append(f"MA20 거리 {common['ma20_distance_pct']:+.1f}%")

        if flow.get("foreign_net_5d", 0) > 0 or flow.get("institution_net_5d", 0) > 0:
            summary_parts.append("외인/기관 매수 우위")

        return {
            "stock": stock_data,
            "price_history": price_history,
            "flow_history": flow_history,
            "analysis_summary": ". ".join(summary_parts) if summary_parts else "분석 데이터 부족",
        }
