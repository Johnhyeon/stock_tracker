"""눌림목 분석 서비스."""
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from models import StockOHLCV, StockInvestorFlow
from schemas.pullback import PullbackStock
from services.theme_map_service import get_theme_map_service

logger = logging.getLogger(__name__)


class PullbackService:
    """눌림목 분석 서비스.

    상승 후 조정을 받아 주요 지지선 근처에 위치한 종목을 찾습니다.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._tms = get_theme_map_service()

    def _get_themes_for_stock(self, stock_code: str) -> list[str]:
        """종목의 테마 목록 반환."""
        return self._tms.get_themes_for_stock(stock_code)

    async def _get_all_stocks(self) -> list[dict]:
        """테마에 등록된 모든 종목 목록 반환."""
        stocks = []
        seen_codes = set()
        for theme_name, theme_stocks in self._tms.get_all_themes().items():
            for stock in theme_stocks:
                code = stock.get("code")
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    stocks.append({
                        "code": code,
                        "name": stock.get("name", ""),
                    })
        return stocks

    async def _bulk_get_ohlcv(self, stock_codes: list[str], days: int = 90) -> dict[str, dict]:
        """전체 종목의 OHLCV 데이터를 벌크로 조회."""
        start_date = date.today() - timedelta(days=days + 30)
        stmt = (
            select(StockOHLCV)
            .where(
                and_(
                    StockOHLCV.stock_code.in_(stock_codes),
                    StockOHLCV.trade_date >= start_date,
                    StockOHLCV.trade_date <= date.today(),
                )
            )
            .order_by(StockOHLCV.stock_code, StockOHLCV.trade_date.asc())
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        # 종목별 그룹핑
        grouped = defaultdict(list)
        for row in rows:
            grouped[row.stock_code].append(row)

        # numpy 배열로 변환
        ohlcv_map = {}
        for code, candles in grouped.items():
            if len(candles) < 20:
                continue
            dates = []
            opens = []
            highs = []
            lows = []
            closes = []
            volumes = []
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

    async def _bulk_get_flow(self, stock_codes: list[str], days: int = 5) -> dict[str, dict]:
        """전체 종목의 수급 데이터를 벌크로 조회."""
        start_date = date.today() - timedelta(days=days + 5)
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

        # 종목별 그룹핑 후 합산
        grouped = defaultdict(list)
        for row in rows:
            grouped[row.stock_code].append(row)

        flow_map = {}
        for code, flows in grouped.items():
            recent_flows = flows[:days]
            foreign_sum = sum(f.foreign_net for f in recent_flows)
            institution_sum = sum(f.institution_net for f in recent_flows)
            avg_score = sum(f.flow_score for f in recent_flows) / len(recent_flows) if recent_flows else 50.0
            flow_map[code] = {
                "foreign_net_5d": foreign_sum,
                "institution_net_5d": institution_sum,
                "flow_score": round(avg_score, 1),
            }
        return flow_map

    def _analyze_from_bulk(
        self,
        stock_code: str,
        stock_name: str,
        ohlcv: Optional[dict],
        flow_data: dict,
    ) -> Optional[PullbackStock]:
        """벌크 데이터로 단일 종목 분석 (DB 쿼리 없음)."""
        if ohlcv is None:
            return None

        metrics = self._calculate_pullback_metrics(ohlcv)
        score_data = self._calculate_pullback_score(metrics, flow_data)
        themes = self._get_themes_for_stock(stock_code)

        return PullbackStock(
            stock_code=stock_code,
            stock_name=stock_name,
            current_price=metrics["current_price"],
            pullback_pct=metrics["pullback_pct"],
            ma20_distance_pct=metrics.get("ma20_distance_pct"),
            ma50_distance_pct=metrics.get("ma50_distance_pct"),
            ma200_distance_pct=metrics.get("ma200_distance_pct"),
            support_line=metrics.get("support_line"),
            support_distance_pct=metrics.get("support_distance_pct"),
            ma20=metrics.get("ma20"),
            ma50=metrics.get("ma50"),
            ma200=metrics.get("ma200"),
            foreign_net_5d=flow_data["foreign_net_5d"],
            institution_net_5d=flow_data["institution_net_5d"],
            flow_score=flow_data["flow_score"],
            volume_ratio=metrics.get("volume_ratio"),
            volume_decreasing=metrics.get("volume_decreasing", False),
            total_score=score_data["total_score"],
            grade=score_data["grade"],
            ma_support_score=score_data["ma_support_score"],
            depth_score=score_data["depth_score"],
            flow_score_component=score_data["flow_score_component"],
            volume_score=score_data["volume_score"],
            high_price_60d=metrics.get("high_price_60d"),
            low_price_60d=metrics.get("low_price_60d"),
            percentile_60d=metrics.get("percentile_60d"),
            themes=themes[:3],
        )

    async def _bulk_get_ohlcv(self, stock_codes: list[str], days: int = 90) -> dict[str, dict]:
        """전체 종목의 OHLCV 데이터를 벌크로 조회."""
        start_date = date.today() - timedelta(days=days + 30)
        stmt = (
            select(StockOHLCV)
            .where(
                and_(
                    StockOHLCV.stock_code.in_(stock_codes),
                    StockOHLCV.trade_date >= start_date,
                    StockOHLCV.trade_date <= date.today(),
                )
            )
            .order_by(StockOHLCV.stock_code, StockOHLCV.trade_date.asc())
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        # 종목별 그룹핑
        grouped = defaultdict(list)
        for row in rows:
            grouped[row.stock_code].append(row)

        # numpy 배열로 변환
        ohlcv_map = {}
        for code, candles in grouped.items():
            if len(candles) < 20:
                continue
            dates = []
            opens = []
            highs = []
            lows = []
            closes = []
            volumes = []
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

    async def _bulk_get_flow(self, stock_codes: list[str], days: int = 5) -> dict[str, dict]:
        """전체 종목의 수급 데이터를 벌크로 조회."""
        start_date = date.today() - timedelta(days=days + 5)
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

        # 종목별 그룹핑 후 합산
        grouped = defaultdict(list)
        for row in rows:
            grouped[row.stock_code].append(row)

        flow_map = {}
        for code, flows in grouped.items():
            recent_flows = flows[:days]
            foreign_sum = sum(f.foreign_net for f in recent_flows)
            institution_sum = sum(f.institution_net for f in recent_flows)
            avg_score = sum(f.flow_score for f in recent_flows) / len(recent_flows) if recent_flows else 50.0
            flow_map[code] = {
                "foreign_net_5d": foreign_sum,
                "institution_net_5d": institution_sum,
                "flow_score": round(avg_score, 1),
            }
        return flow_map

    def _analyze_from_bulk(
        self,
        stock_code: str,
        stock_name: str,
        ohlcv: Optional[dict],
        flow_data: dict,
    ) -> Optional[PullbackStock]:
        """벌크 데이터로 단일 종목 분석 (DB 쿼리 없음)."""
        if ohlcv is None:
            return None

        metrics = self._calculate_pullback_metrics(ohlcv)
        score_data = self._calculate_pullback_score(metrics, flow_data)
        themes = self._get_themes_for_stock(stock_code)

        return PullbackStock(
            stock_code=stock_code,
            stock_name=stock_name,
            current_price=metrics["current_price"],
            pullback_pct=metrics["pullback_pct"],
            ma20_distance_pct=metrics.get("ma20_distance_pct"),
            ma50_distance_pct=metrics.get("ma50_distance_pct"),
            ma200_distance_pct=metrics.get("ma200_distance_pct"),
            support_line=metrics.get("support_line"),
            support_distance_pct=metrics.get("support_distance_pct"),
            ma20=metrics.get("ma20"),
            ma50=metrics.get("ma50"),
            ma200=metrics.get("ma200"),
            foreign_net_5d=flow_data["foreign_net_5d"],
            institution_net_5d=flow_data["institution_net_5d"],
            flow_score=flow_data["flow_score"],
            volume_ratio=metrics.get("volume_ratio"),
            volume_decreasing=metrics.get("volume_decreasing", False),
            total_score=score_data["total_score"],
            grade=score_data["grade"],
            ma_support_score=score_data["ma_support_score"],
            depth_score=score_data["depth_score"],
            flow_score_component=score_data["flow_score_component"],
            volume_score=score_data["volume_score"],
            high_price_60d=metrics.get("high_price_60d"),
            low_price_60d=metrics.get("low_price_60d"),
            percentile_60d=metrics.get("percentile_60d"),
            themes=themes[:3],
        )

    async def _get_ohlcv_data(
        self,
        stock_code: str,
        days: int = 90,
        include_realtime: bool = False,
    ) -> Optional[dict]:
        """종목의 OHLCV 데이터 조회.

        Args:
            stock_code: 종목코드
            days: 조회 일수
            include_realtime: 실시간 데이터 포함 여부 (개별 조회 시만 True)
        """
        from services.ohlcv_service import OHLCVService
        from datetime import datetime

        ohlcv_service = OHLCVService(self.db)

        # 대량 조회 시에는 실시간 데이터 비활성화 (성능 최적화)
        candles = await ohlcv_service.get_ohlcv(
            stock_code=stock_code,
            days=days,
            include_realtime=include_realtime,
        )

        if not candles or len(candles) < 20:
            return None

        # 캔들 데이터를 numpy 배열로 변환
        dates = []
        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []

        for c in candles:
            # timestamp를 date로 변환
            trade_date = datetime.fromtimestamp(c["time"]).date()
            dates.append(trade_date)
            opens.append(float(c["open"]))
            highs.append(float(c["high"]))
            lows.append(float(c["low"]))
            closes.append(float(c["close"]))
            volumes.append(float(c["volume"]))

        return {
            "dates": dates,
            "opens": np.array(opens),
            "highs": np.array(highs),
            "lows": np.array(lows),
            "closes": np.array(closes),
            "volumes": np.array(volumes),
        }

    async def _get_flow_data(
        self,
        stock_code: str,
        days: int = 5,
    ) -> dict:
        """종목의 수급 데이터 조회."""
        start_date = date.today() - timedelta(days=days + 5)

        stmt = (
            select(StockInvestorFlow)
            .where(
                and_(
                    StockInvestorFlow.stock_code == stock_code,
                    StockInvestorFlow.flow_date >= start_date,
                )
            )
            .order_by(StockInvestorFlow.flow_date.desc())
        )
        result = await self.db.execute(stmt)
        flows = result.scalars().all()

        if not flows:
            return {
                "foreign_net_5d": 0,
                "institution_net_5d": 0,
                "flow_score": 50.0,
            }

        # 최근 5일 데이터 합산
        recent_flows = flows[:days]
        foreign_sum = sum(f.foreign_net for f in recent_flows)
        institution_sum = sum(f.institution_net for f in recent_flows)
        avg_score = sum(f.flow_score for f in recent_flows) / len(recent_flows) if recent_flows else 50.0

        return {
            "foreign_net_5d": foreign_sum,
            "institution_net_5d": institution_sum,
            "flow_score": round(avg_score, 1),
        }

    def _calculate_moving_averages(
        self,
        closes: np.ndarray,
    ) -> dict:
        """이동평균선 계산."""
        result = {}

        if len(closes) >= 20:
            result["ma20"] = int(np.mean(closes[-20:]))
        if len(closes) >= 50:
            result["ma50"] = int(np.mean(closes[-50:]))
        if len(closes) >= 200:
            result["ma200"] = int(np.mean(closes[-200:]))

        return result

    def _calculate_pullback_metrics(
        self,
        ohlcv: dict,
    ) -> dict:
        """눌림목 지표 계산."""
        closes = ohlcv["closes"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        volumes = ohlcv["volumes"]
        current_price = int(closes[-1])

        # 60일 고점/저점
        recent_60 = min(60, len(closes))
        high_60d = int(np.max(highs[-recent_60:]))
        low_60d = int(np.min(lows[-recent_60:]))

        # 눌림 깊이 (고점 대비 하락률)
        pullback_pct = round((high_60d - current_price) / high_60d * 100, 2) if high_60d > 0 else 0

        # 60일 가격 백분위 (0=저점, 100=고점)
        if high_60d > low_60d:
            percentile_60d = round((current_price - low_60d) / (high_60d - low_60d) * 100, 2)
        else:
            percentile_60d = 50.0

        # 지지선 계산 (하위 10% 가격)
        support_line = int(np.percentile(lows[-60:], 10))
        support_distance_pct = round((current_price - support_line) / support_line * 100, 2) if support_line > 0 else 0

        # 이동평균선 계산
        mas = self._calculate_moving_averages(closes)

        # 이평선 대비 거리
        ma20_distance_pct = None
        ma50_distance_pct = None
        ma200_distance_pct = None

        if "ma20" in mas and mas["ma20"] > 0:
            ma20_distance_pct = round((current_price - mas["ma20"]) / mas["ma20"] * 100, 2)
        if "ma50" in mas and mas["ma50"] > 0:
            ma50_distance_pct = round((current_price - mas["ma50"]) / mas["ma50"] * 100, 2)
        if "ma200" in mas and mas["ma200"] > 0:
            ma200_distance_pct = round((current_price - mas["ma200"]) / mas["ma200"] * 100, 2)

        # 거래량 감소 확인 (조정 구간에서 거래량 감소)
        if len(volumes) >= 20:
            # 최근 5일 평균 vs 20일 평균
            vol_recent = np.mean(volumes[-5:])
            vol_avg = np.mean(volumes[-20:])
            volume_ratio = round(vol_recent / vol_avg, 2) if vol_avg > 0 else 1.0
            # 조정 중 거래량 감소 (건전한 조정)
            volume_decreasing = volume_ratio < 0.8
        else:
            volume_ratio = 1.0
            volume_decreasing = False

        return {
            "current_price": current_price,
            "pullback_pct": pullback_pct,
            "high_price_60d": high_60d,
            "low_price_60d": low_60d,
            "percentile_60d": percentile_60d,
            "support_line": support_line,
            "support_distance_pct": support_distance_pct,
            "ma20": mas.get("ma20"),
            "ma50": mas.get("ma50"),
            "ma200": mas.get("ma200"),
            "ma20_distance_pct": ma20_distance_pct,
            "ma50_distance_pct": ma50_distance_pct,
            "ma200_distance_pct": ma200_distance_pct,
            "volume_ratio": volume_ratio,
            "volume_decreasing": volume_decreasing,
        }

    def _calculate_pullback_score(
        self,
        metrics: dict,
        flow_data: dict,
    ) -> dict:
        """눌림목 점수 계산 (100점 만점)."""
        score = 0.0
        breakdown = {
            "ma_support_score": 0.0,
            "depth_score": 0.0,
            "flow_score_component": 0.0,
            "volume_score": 0.0,
        }

        # 1. 이평선 지지 점수 (30점)
        ma_support_score = 0.0
        # 가장 가까운 이평선 기준
        distances = []
        if metrics.get("ma20_distance_pct") is not None:
            distances.append(("ma20", abs(metrics["ma20_distance_pct"])))
        if metrics.get("ma50_distance_pct") is not None:
            distances.append(("ma50", abs(metrics["ma50_distance_pct"])))
        if metrics.get("ma200_distance_pct") is not None:
            distances.append(("ma200", abs(metrics["ma200_distance_pct"])))

        if distances:
            # 가장 가까운 이평선 기준
            min_distance = min(d[1] for d in distances)
            # 5% 이내면 고득점, 멀수록 감점
            if min_distance <= 2:
                ma_support_score = 30
            elif min_distance <= 5:
                ma_support_score = 30 - (min_distance - 2) * 5
            elif min_distance <= 10:
                ma_support_score = max(0, 15 - (min_distance - 5) * 2)

        breakdown["ma_support_score"] = round(ma_support_score, 1)
        score += ma_support_score

        # 2. 눌림 깊이 점수 (25점)
        pullback_pct = metrics.get("pullback_pct", 0)
        depth_score = 0.0
        # 10-20% 구간이 최적 (25점)
        # 5-10%, 20-30% 구간 중간 점수
        # 5% 미만, 30% 초과 낮은 점수
        if 10 <= pullback_pct <= 20:
            depth_score = 25
        elif 15 <= pullback_pct <= 25:
            depth_score = 22
        elif 5 <= pullback_pct < 10:
            depth_score = 15 + (pullback_pct - 5) * 1.4
        elif 20 < pullback_pct <= 30:
            depth_score = 25 - (pullback_pct - 20) * 1.5
        elif pullback_pct < 5:
            depth_score = pullback_pct * 3
        elif pullback_pct > 30:
            depth_score = max(0, 10 - (pullback_pct - 30) * 0.5)

        breakdown["depth_score"] = round(depth_score, 1)
        score += depth_score

        # 3. 수급 점수 (25점)
        flow_score = flow_data.get("flow_score", 50)
        # flow_score는 0-100 범위, 50이 중립
        # 50 이상이면 양호, 70 이상이면 우수
        flow_component = 0.0
        if flow_score >= 70:
            flow_component = 25
        elif flow_score >= 60:
            flow_component = 20 + (flow_score - 60) * 0.5
        elif flow_score >= 50:
            flow_component = 12.5 + (flow_score - 50) * 0.75
        else:
            flow_component = max(0, (flow_score / 50) * 12.5)

        # 외인/기관 순매수 보너스
        if flow_data.get("foreign_net_5d", 0) > 0:
            flow_component = min(25, flow_component + 2)
        if flow_data.get("institution_net_5d", 0) > 0:
            flow_component = min(25, flow_component + 2)

        breakdown["flow_score_component"] = round(flow_component, 1)
        score += flow_component

        # 4. 거래량 감소 점수 (20점)
        volume_score = 0.0
        volume_ratio = metrics.get("volume_ratio", 1.0)
        volume_decreasing = metrics.get("volume_decreasing", False)

        # 조정 시 거래량 감소가 건전한 신호
        if volume_decreasing:
            volume_score = 20
        elif volume_ratio < 1.0:
            volume_score = 10 + (1.0 - volume_ratio) * 20
        else:
            # 거래량 증가 (급등 조짐일 수도 있지만 눌림목에선 좋지 않음)
            volume_score = max(0, 10 - (volume_ratio - 1.0) * 5)

        breakdown["volume_score"] = round(volume_score, 1)
        score += volume_score

        # 등급 계산
        if score >= 80:
            grade = "A"
        elif score >= 60:
            grade = "B"
        elif score >= 40:
            grade = "C"
        else:
            grade = "D"

        return {
            "total_score": round(score, 1),
            "grade": grade,
            **breakdown,
        }

    async def analyze_stock(
        self,
        stock_code: str,
        stock_name: str,
        include_realtime: bool = False,
    ) -> Optional[PullbackStock]:
        """단일 종목 눌림목 분석.

        Args:
            stock_code: 종목코드
            stock_name: 종목명
            include_realtime: 실시간 데이터 포함 여부 (개별 조회 시 True)
        """
        # OHLCV 데이터 조회
        ohlcv = await self._get_ohlcv_data(stock_code, days=90, include_realtime=include_realtime)
        if ohlcv is None:
            return None

        # 수급 데이터 조회
        flow_data = await self._get_flow_data(stock_code, days=5)

        # 지표 계산
        metrics = self._calculate_pullback_metrics(ohlcv)

        # 점수 계산
        score_data = self._calculate_pullback_score(metrics, flow_data)

        # 테마 정보
        themes = self._get_themes_for_stock(stock_code)

        return PullbackStock(
            stock_code=stock_code,
            stock_name=stock_name,
            current_price=metrics["current_price"],
            pullback_pct=metrics["pullback_pct"],
            ma20_distance_pct=metrics.get("ma20_distance_pct"),
            ma50_distance_pct=metrics.get("ma50_distance_pct"),
            ma200_distance_pct=metrics.get("ma200_distance_pct"),
            support_line=metrics.get("support_line"),
            support_distance_pct=metrics.get("support_distance_pct"),
            ma20=metrics.get("ma20"),
            ma50=metrics.get("ma50"),
            ma200=metrics.get("ma200"),
            foreign_net_5d=flow_data["foreign_net_5d"],
            institution_net_5d=flow_data["institution_net_5d"],
            flow_score=flow_data["flow_score"],
            volume_ratio=metrics.get("volume_ratio"),
            volume_decreasing=metrics.get("volume_decreasing", False),
            total_score=score_data["total_score"],
            grade=score_data["grade"],
            ma_support_score=score_data["ma_support_score"],
            depth_score=score_data["depth_score"],
            flow_score_component=score_data["flow_score_component"],
            volume_score=score_data["volume_score"],
            high_price_60d=metrics.get("high_price_60d"),
            low_price_60d=metrics.get("low_price_60d"),
            percentile_60d=metrics.get("percentile_60d"),
            themes=themes[:3],  # 최대 3개 테마
        )

    async def _bulk_analyze(self) -> list[PullbackStock]:
        """전체 종목 벌크 분석 (2 쿼리로 처리)."""
        all_stocks = await self._get_all_stocks()
        stock_codes = [s["code"] for s in all_stocks]
        code_to_name = {s["code"]: s["name"] for s in all_stocks}

        # 벌크 조회 (2 쿼리)
        ohlcv_map = await self._bulk_get_ohlcv(stock_codes)
        flow_map = await self._bulk_get_flow(stock_codes)

        default_flow = {"foreign_net_5d": 0, "institution_net_5d": 0, "flow_score": 50.0}
        results = []

        for code in stock_codes:
            try:
                ohlcv = ohlcv_map.get(code)
                flow = flow_map.get(code, default_flow)
                pullback = self._analyze_from_bulk(code, code_to_name[code], ohlcv, flow)
                if pullback:
                    results.append(pullback)
            except Exception as e:
                logger.warning(f"분석 실패 ({code}): {e}")
                continue

        return results

    async def get_ma_support_stocks(
        self,
        ma_type: str = "ma20",
        max_distance_pct: float = 5.0,
        require_above_ma: bool = False,
        limit: int = 50,
    ) -> list[PullbackStock]:
        """이평선 지지 종목 조회 (벌크)."""
        all_analyzed = await self._bulk_analyze()
        results = []

        for pullback in all_analyzed:
            distance_field = f"{ma_type}_distance_pct"
            distance = getattr(pullback, distance_field, None)
            if distance is None:
                continue
            if abs(distance) > max_distance_pct:
                continue
            if require_above_ma and distance < 0:
                continue
            results.append(pullback)

        def get_distance(p: PullbackStock) -> float:
            d = getattr(p, f"{ma_type}_distance_pct", None)
            return abs(d) if d is not None else 999

        results.sort(key=get_distance)
        return results[:limit]

    async def get_support_line_stocks(
        self,
        max_distance_pct: float = 10.0,
        limit: int = 50,
    ) -> list[PullbackStock]:
        """지지선 근처 종목 조회 (벌크)."""
        all_analyzed = await self._bulk_analyze()
        results = []

        for pullback in all_analyzed:
            if pullback.support_distance_pct is None:
                continue
            if pullback.support_distance_pct > max_distance_pct:
                continue
            if pullback.support_distance_pct < 0:
                continue
            results.append(pullback)

        results.sort(key=lambda p: p.support_distance_pct if p.support_distance_pct is not None else 999)
        return results[:limit]

    async def get_pullback_depth_stocks(
        self,
        min_pullback_pct: float = 10.0,
        max_pullback_pct: float = 30.0,
        limit: int = 50,
    ) -> list[PullbackStock]:
        """눌림 깊이순 종목 조회 (벌크)."""
        all_analyzed = await self._bulk_analyze()
        results = []

        for pullback in all_analyzed:
            if pullback.pullback_pct < min_pullback_pct:
                continue
            if pullback.pullback_pct > max_pullback_pct:
                continue
            results.append(pullback)

        def depth_score(p: PullbackStock) -> float:
            optimal = 15.0
            return abs(p.pullback_pct - optimal)

        results.sort(key=depth_score)
        return results[:limit]

    async def get_ranking(
        self,
        min_score: float = 0.0,
        min_grade: str = "D",
        require_positive_flow: bool = False,
        limit: int = 50,
    ) -> list[PullbackStock]:
        """종합 랭킹 조회 (벌크)."""
        all_analyzed = await self._bulk_analyze()

        grade_order = {"A": 1, "B": 2, "C": 3, "D": 4}
        min_grade_value = grade_order.get(min_grade, 4)
        results = []

        for pullback in all_analyzed:
            if pullback.total_score < min_score:
                continue
            stock_grade_value = grade_order.get(pullback.grade, 4)
            if stock_grade_value > min_grade_value:
                continue
            if require_positive_flow:
                if pullback.foreign_net_5d <= 0 and pullback.institution_net_5d <= 0:
                    continue
            results.append(pullback)

        results.sort(key=lambda p: p.total_score, reverse=True)
        return results[:limit]

    async def get_by_stock_codes(
        self,
        stock_codes: list[str],
        min_score: float = 0.0,
        limit: int = 50,
    ) -> list[PullbackStock]:
        """특정 종목 코드들의 눌림목 분석 조회."""
        results = []

        # 종목명 매핑 준비
        code_to_name = {}
        for theme_stocks in self._tms.get_all_themes().values():
            for stock in theme_stocks:
                code = stock.get("code")
                if code in stock_codes:
                    code_to_name[code] = stock.get("name", "")

        for stock_code in stock_codes:
            try:
                stock_name = code_to_name.get(stock_code, "")
                pullback = await self.analyze_stock(stock_code, stock_name)
                if pullback is None:
                    continue

                # 최소 점수 필터
                if pullback.total_score < min_score:
                    continue

                results.append(pullback)

            except Exception as e:
                logger.warning(f"분석 실패 ({stock_code}): {e}")
                continue

        # 종합 점수순 정렬
        results.sort(key=lambda p: p.total_score, reverse=True)
        return results[:limit]

    async def get_stock_detail(
        self,
        stock_code: str,
    ) -> Optional[dict]:
        """종목 상세 정보 조회."""
        # 종목명 찾기
        stock_name = ""
        for stocks in self._tms.get_all_themes().values():
            for s in stocks:
                if s.get("code") == stock_code:
                    stock_name = s.get("name", "")
                    break

        # 개별 상세 조회는 실시간 데이터 포함
        pullback = await self.analyze_stock(stock_code, stock_name, include_realtime=True)
        if pullback is None:
            return None

        # 가격 히스토리 (실시간 데이터 포함)
        ohlcv = await self._get_ohlcv_data(stock_code, days=60, include_realtime=True)
        price_history = []
        if ohlcv:
            for i in range(len(ohlcv["dates"])):
                price_history.append({
                    "date": ohlcv["dates"][i].isoformat(),
                    "open": int(ohlcv["opens"][i]),
                    "high": int(ohlcv["highs"][i]),
                    "low": int(ohlcv["lows"][i]),
                    "close": int(ohlcv["closes"][i]),
                    "volume": int(ohlcv["volumes"][i]),
                })

        # 수급 히스토리
        start_date = date.today() - timedelta(days=30)
        stmt = (
            select(StockInvestorFlow)
            .where(
                and_(
                    StockInvestorFlow.stock_code == stock_code,
                    StockInvestorFlow.flow_date >= start_date,
                )
            )
            .order_by(StockInvestorFlow.flow_date.desc())
        )
        result = await self.db.execute(stmt)
        flows = result.scalars().all()

        flow_history = [
            {
                "date": f.flow_date.isoformat(),
                "foreign_net": f.foreign_net,
                "institution_net": f.institution_net,
                "individual_net": f.individual_net,
                "flow_score": f.flow_score,
            }
            for f in flows
        ]

        # 분석 요약 생성
        summary_parts = []
        if pullback.grade == "A":
            summary_parts.append("최적의 눌림목 패턴")
        elif pullback.grade == "B":
            summary_parts.append("양호한 눌림목 패턴")
        elif pullback.grade == "C":
            summary_parts.append("보통 수준의 눌림목")
        else:
            summary_parts.append("약한 눌림목 신호")

        if pullback.pullback_pct >= 10 and pullback.pullback_pct <= 20:
            summary_parts.append(f"적정 조정폭 {pullback.pullback_pct:.1f}%")
        elif pullback.pullback_pct < 10:
            summary_parts.append(f"얕은 조정 {pullback.pullback_pct:.1f}%")
        else:
            summary_parts.append(f"깊은 조정 {pullback.pullback_pct:.1f}%")

        if pullback.ma20_distance_pct is not None and abs(pullback.ma20_distance_pct) <= 5:
            summary_parts.append(f"20일선 근처 (거리 {pullback.ma20_distance_pct:+.1f}%)")

        if pullback.foreign_net_5d > 0 or pullback.institution_net_5d > 0:
            summary_parts.append("외인/기관 수급 양호")

        if pullback.volume_decreasing:
            summary_parts.append("건전한 거래량 감소")

        return {
            "stock": pullback.model_dump(),
            "price_history": price_history[-30:],  # 최근 30일
            "flow_history": flow_history[:20],  # 최근 20일
            "analysis_summary": ". ".join(summary_parts),
        }
