"""차트 패턴 감지 서비스."""
import logging
from datetime import datetime, date, timedelta
from typing import Optional
from dataclasses import dataclass

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete, func
from sqlalchemy.dialects.postgresql import insert

from models import ThemeChartPattern, ChartPatternType, YouTubeMention, ExpertMention, StockOHLCV
from services.price_service import get_price_service
from services.theme_map_service import get_theme_map_service
from core.timezone import now_kst, today_kst

logger = logging.getLogger(__name__)


@dataclass
class OHLCVData:
    """OHLCV 데이터."""
    dates: list[str]
    opens: np.ndarray
    highs: np.ndarray
    lows: np.ndarray
    closes: np.ndarray
    volumes: np.ndarray


@dataclass
class PatternResult:
    """패턴 감지 결과."""
    pattern_type: str
    confidence: int
    pattern_data: dict
    current_price: int
    price_from_support_pct: Optional[float] = None
    price_from_resistance_pct: Optional[float] = None


class ChartPatternService:
    """차트 패턴 감지 서비스.

    180일 일봉 데이터를 분석하여 셋업 패턴을 감지합니다.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.price_service = get_price_service()
        self._tms = get_theme_map_service()

    async def _get_ohlcv_data(
        self,
        stock_code: str,
        days: int = 90,
    ) -> Optional[OHLCVData]:
        """종목의 OHLCV 데이터 조회.

        1. DB(stock_ohlcv 테이블)에서 먼저 조회
        2. DB에 충분한 데이터가 없으면 KIS API fallback
        """
        end_date = today_kst()
        start_date = end_date - timedelta(days=days + 30)  # 여유분 포함

        # 1. DB에서 먼저 조회
        try:
            stmt = (
                select(StockOHLCV)
                .where(
                    and_(
                        StockOHLCV.stock_code == stock_code,
                        StockOHLCV.trade_date >= start_date,
                        StockOHLCV.trade_date <= end_date,
                    )
                )
                .order_by(StockOHLCV.trade_date)
            )
            result = await self.db.execute(stmt)
            db_records = result.scalars().all()

            if db_records and len(db_records) >= 30:
                # DB 데이터가 충분하면 사용
                data = db_records[-days:] if len(db_records) > days else db_records

                return OHLCVData(
                    dates=[d.trade_date.strftime("%Y%m%d") for d in data],
                    opens=np.array([float(d.open_price) for d in data]),
                    highs=np.array([float(d.high_price) for d in data]),
                    lows=np.array([float(d.low_price) for d in data]),
                    closes=np.array([float(d.close_price) for d in data]),
                    volumes=np.array([float(d.volume) for d in data]),
                )
        except Exception as e:
            logger.warning(f"DB OHLCV 조회 실패 ({stock_code}): {e}")

        # 2. DB에 데이터 부족 시 KIS API fallback
        try:
            data = await self.price_service.get_ohlcv(
                stock_code=stock_code,
                period="D",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                use_cache=True,  # 캐시 사용으로 API 호출 최소화
            )

            if not data or len(data) < 30:  # 최소 30일 데이터 필요 (60 → 30 완화)
                return None

            # 최근 90일만 사용
            data = data[-days:] if len(data) > days else data

            return OHLCVData(
                dates=[d["date"] for d in data],
                opens=np.array([float(d["open"]) for d in data]),
                highs=np.array([float(d["high"]) for d in data]),
                lows=np.array([float(d["low"]) for d in data]),
                closes=np.array([float(d["close"]) for d in data]),
                volumes=np.array([float(d["volume"]) for d in data]),
            )
        except Exception as e:
            logger.warning(f"KIS API OHLCV 조회 실패 ({stock_code}): {e}")
            return None

    def _find_peaks_troughs(
        self,
        prices: np.ndarray,
        window: int = 5,
    ) -> tuple[list[int], list[int]]:
        """가격 배열에서 고점과 저점 찾기.

        Args:
            prices: 가격 배열
            window: 비교 윈도우 크기

        Returns:
            (고점 인덱스 리스트, 저점 인덱스 리스트)
        """
        peaks = []
        troughs = []

        for i in range(window, len(prices) - window):
            # 고점: 양 옆 window 개보다 모두 높음
            if all(prices[i] > prices[i - j] for j in range(1, window + 1)) and \
               all(prices[i] > prices[i + j] for j in range(1, window + 1)):
                peaks.append(i)

            # 저점: 양 옆 window 개보다 모두 낮음
            if all(prices[i] < prices[i - j] for j in range(1, window + 1)) and \
               all(prices[i] < prices[i + j] for j in range(1, window + 1)):
                troughs.append(i)

        return peaks, troughs

    def _detect_range_bound(
        self,
        ohlcv: OHLCVData,
    ) -> Optional[PatternResult]:
        """횡보/박스권 패턴 감지.

        조건:
        - 60일 이상 변동폭 15% 이내
        - 지지/저항 3회+ 터치
        """
        if len(ohlcv.closes) < 60:
            return None

        # 최근 60일 분석
        recent_highs = ohlcv.highs[-60:]
        recent_lows = ohlcv.lows[-60:]
        recent_closes = ohlcv.closes[-60:]

        max_high = np.max(recent_highs)
        min_low = np.min(recent_lows)

        # 변동폭 계산
        range_pct = (max_high - min_low) / min_low * 100

        if range_pct > 15:
            return None

        # 지지/저항선 계산
        resistance = np.percentile(recent_highs, 90)
        support = np.percentile(recent_lows, 10)

        # 저항선 터치 횟수 (상위 5% 이내)
        resistance_touches = np.sum(recent_highs >= resistance * 0.98)
        # 지지선 터치 횟수 (하위 5% 이내)
        support_touches = np.sum(recent_lows <= support * 1.02)

        total_touches = resistance_touches + support_touches

        if total_touches < 3:
            return None

        # 신뢰도 계산
        confidence = min(100, 50 + total_touches * 5 + max(0, (15 - range_pct) * 3))

        current_price = int(ohlcv.closes[-1])

        return PatternResult(
            pattern_type=ChartPatternType.RANGE_BOUND.value,
            confidence=int(confidence),
            pattern_data={
                "support": int(support),
                "resistance": int(resistance),
                "range_pct": round(range_pct, 2),
                "touch_count": int(total_touches),
                "period_days": 60,
            },
            current_price=current_price,
            price_from_support_pct=round((current_price - support) / support * 100, 2),
            price_from_resistance_pct=round((current_price - resistance) / resistance * 100, 2),
        )

    def _detect_double_bottom(
        self,
        ohlcv: OHLCVData,
    ) -> Optional[PatternResult]:
        """쌍바닥 패턴 감지.

        조건:
        - 두 저점 가격차 5% 이내
        - 간격 20-60일
        - 중간고점 10%+ 상승
        """
        _, troughs = self._find_peaks_troughs(ohlcv.lows, window=5)

        if len(troughs) < 2:
            return None

        # 최근 저점들 분석
        recent_troughs = [t for t in troughs if t > len(ohlcv.lows) - 120]

        for i in range(len(recent_troughs) - 1):
            t1_idx = recent_troughs[i]
            t2_idx = recent_troughs[i + 1]

            # 간격 체크 (20-60일)
            gap = t2_idx - t1_idx
            if gap < 20 or gap > 60:
                continue

            t1_price = ohlcv.lows[t1_idx]
            t2_price = ohlcv.lows[t2_idx]

            # 가격차 5% 이내
            price_diff_pct = abs(t1_price - t2_price) / min(t1_price, t2_price) * 100
            if price_diff_pct > 5:
                continue

            # 중간고점 체크
            mid_high = np.max(ohlcv.highs[t1_idx:t2_idx + 1])
            bottom_avg = (t1_price + t2_price) / 2
            mid_rise_pct = (mid_high - bottom_avg) / bottom_avg * 100

            if mid_rise_pct < 10:
                continue

            # 현재가가 두 번째 저점보다 위에 있어야 함
            current_price = ohlcv.closes[-1]
            if current_price < t2_price:
                continue

            support = min(t1_price, t2_price)

            # 넥라인(중간고점) 대비 30% 이상 상승 시 패턴 만료 (이미 돌파 완료)
            if current_price > mid_high * 1.3:
                continue

            # 신뢰도 계산
            confidence = min(100, 60 + mid_rise_pct + (5 - price_diff_pct) * 4)

            return PatternResult(
                pattern_type=ChartPatternType.DOUBLE_BOTTOM.value,
                confidence=int(confidence),
                pattern_data={
                    "bottom1_price": int(t1_price),
                    "bottom1_date": ohlcv.dates[t1_idx],
                    "bottom2_price": int(t2_price),
                    "bottom2_date": ohlcv.dates[t2_idx],
                    "neckline": int(mid_high),
                    "gap_days": gap,
                    "price_diff_pct": round(price_diff_pct, 2),
                },
                current_price=int(current_price),
                price_from_support_pct=round((current_price - support) / support * 100, 2),
            )

        return None

    def _detect_triple_bottom(
        self,
        ohlcv: OHLCVData,
    ) -> Optional[PatternResult]:
        """삼중바닥 패턴 감지.

        조건:
        - 세 저점 가격 유사 (5% 이내)
        - 각 간격 15-40일
        """
        _, troughs = self._find_peaks_troughs(ohlcv.lows, window=4)

        if len(troughs) < 3:
            return None

        # 최근 저점들 분석
        recent_troughs = [t for t in troughs if t > len(ohlcv.lows) - 150]

        for i in range(len(recent_troughs) - 2):
            t1_idx = recent_troughs[i]
            t2_idx = recent_troughs[i + 1]
            t3_idx = recent_troughs[i + 2]

            # 간격 체크 (15-40일)
            gap1 = t2_idx - t1_idx
            gap2 = t3_idx - t2_idx

            if not (15 <= gap1 <= 40 and 15 <= gap2 <= 40):
                continue

            t1_price = ohlcv.lows[t1_idx]
            t2_price = ohlcv.lows[t2_idx]
            t3_price = ohlcv.lows[t3_idx]

            # 세 저점 가격 유사성 (5% 이내)
            prices = [t1_price, t2_price, t3_price]
            avg_price = np.mean(prices)
            max_diff = max(abs(p - avg_price) / avg_price * 100 for p in prices)

            if max_diff > 5:
                continue

            current_price = ohlcv.closes[-1]
            support = min(prices)

            # 지지선 대비 50% 이상 상승 시 패턴 만료 (이미 돌파 완료)
            if current_price > support * 1.5:
                continue

            # 신뢰도 계산
            confidence = min(100, 70 + (5 - max_diff) * 6)

            return PatternResult(
                pattern_type=ChartPatternType.TRIPLE_BOTTOM.value,
                confidence=int(confidence),
                pattern_data={
                    "bottom1_price": int(t1_price),
                    "bottom1_date": ohlcv.dates[t1_idx],
                    "bottom2_price": int(t2_price),
                    "bottom2_date": ohlcv.dates[t2_idx],
                    "bottom3_price": int(t3_price),
                    "bottom3_date": ohlcv.dates[t3_idx],
                    "gap1_days": gap1,
                    "gap2_days": gap2,
                },
                current_price=int(current_price),
                price_from_support_pct=round((current_price - support) / support * 100, 2),
            )

        return None

    def _detect_converging(
        self,
        ohlcv: OHLCVData,
    ) -> Optional[PatternResult]:
        """수렴 패턴 감지.

        조건:
        - 고점 하향 추세
        - 저점 상향 추세
        - 변동성 감소 추세
        """
        if len(ohlcv.closes) < 60:
            return None

        peaks, troughs = self._find_peaks_troughs(ohlcv.closes, window=5)

        # 최근 60일 내 고점/저점
        recent_peaks = [p for p in peaks if p > len(ohlcv.closes) - 60]
        recent_troughs = [t for t in troughs if t > len(ohlcv.closes) - 60]

        if len(recent_peaks) < 2 or len(recent_troughs) < 2:
            return None

        # 고점 하향 추세 확인
        peak_prices = [ohlcv.highs[p] for p in recent_peaks]
        if len(peak_prices) >= 2 and peak_prices[-1] >= peak_prices[0]:
            return None  # 고점이 하향하지 않음

        # 저점 상향 추세 확인
        trough_prices = [ohlcv.lows[t] for t in recent_troughs]
        if len(trough_prices) >= 2 and trough_prices[-1] <= trough_prices[0]:
            return None  # 저점이 상향하지 않음

        # 변동성 감소 확인
        first_half = ohlcv.closes[-60:-30]
        second_half = ohlcv.closes[-30:]

        first_volatility = np.std(first_half) / np.mean(first_half)
        second_volatility = np.std(second_half) / np.mean(second_half)

        if second_volatility >= first_volatility:
            return None  # 변동성이 감소하지 않음

        # 수렴 기울기 계산
        high_slope = (peak_prices[-1] - peak_prices[0]) / (recent_peaks[-1] - recent_peaks[0])
        low_slope = (trough_prices[-1] - trough_prices[0]) / (recent_troughs[-1] - recent_troughs[0])

        current_price = ohlcv.closes[-1]
        current_high = peak_prices[-1] + high_slope * (len(ohlcv.closes) - recent_peaks[-1])
        current_low = trough_prices[-1] + low_slope * (len(ohlcv.closes) - recent_troughs[-1])

        # 외삽된 지지/저항선이 비현실적이면 제외
        if current_low <= 0 or current_high <= 0:
            return None
        if current_low >= current_high:
            return None  # 이미 수렴 완료

        # 신뢰도 계산
        volatility_reduction = (first_volatility - second_volatility) / first_volatility * 100
        confidence = min(100, 55 + volatility_reduction * 2)

        return PatternResult(
            pattern_type=ChartPatternType.CONVERGING.value,
            confidence=int(confidence),
            pattern_data={
                "high_slope": round(float(high_slope), 4),
                "low_slope": round(float(low_slope), 4),
                "volatility_reduction_pct": round(volatility_reduction, 2),
                "current_range": int(current_high - current_low),
            },
            current_price=int(current_price),
            price_from_support_pct=round((current_price - current_low) / current_low * 100, 2) if current_low > 0 else None,
            price_from_resistance_pct=round((current_price - current_high) / current_high * 100, 2) if current_high > 0 else None,
        )

    def _detect_pre_breakout(
        self,
        ohlcv: OHLCVData,
    ) -> Optional[PatternResult]:
        """돌파 직전 패턴 감지.

        조건:
        - 저항선 5% 이내 위치
        - 거래량 130%+ 증가
        - 변동성 축소 후 확대 징후
        """
        if len(ohlcv.closes) < 60:
            return None

        # 저항선 계산 (최근 60일 고점의 상위 10%)
        resistance = np.percentile(ohlcv.highs[-60:], 90)
        current_price = ohlcv.closes[-1]

        # 저항선 대비 위치 (5% 이내)
        distance_pct = (resistance - current_price) / resistance * 100

        if distance_pct < 0 or distance_pct > 5:
            return None  # 이미 돌파했거나 너무 멀리 있음

        # 거래량 증가 확인
        recent_volume_avg = np.mean(ohlcv.volumes[-5:])
        prev_volume_avg = np.mean(ohlcv.volumes[-20:-5])

        if prev_volume_avg == 0:
            return None

        volume_ratio = recent_volume_avg / prev_volume_avg

        if volume_ratio < 1.3:
            return None  # 거래량 증가 부족

        # 변동성 패턴 확인 (축소 후 확대)
        mid_volatility = np.std(ohlcv.closes[-30:-10]) / np.mean(ohlcv.closes[-30:-10])
        recent_volatility = np.std(ohlcv.closes[-10:]) / np.mean(ohlcv.closes[-10:])

        # 신뢰도 계산
        confidence = 60

        # 저항선에 가까울수록 점수 추가
        confidence += (5 - distance_pct) * 4

        # 거래량 증가율에 따라 점수 추가
        confidence += min((volume_ratio - 1.3) * 20, 20)

        # 변동성 확대 시 점수 추가
        if recent_volatility > mid_volatility:
            confidence += 10

        return PatternResult(
            pattern_type=ChartPatternType.PRE_BREAKOUT.value,
            confidence=min(100, int(confidence)),
            pattern_data={
                "resistance": int(resistance),
                "distance_pct": round(distance_pct, 2),
                "volume_ratio": round(volume_ratio, 2),
                "recent_volatility": round(recent_volatility * 100, 2),
            },
            current_price=int(current_price),
            price_from_resistance_pct=round(-distance_pct, 2),
        )

    async def analyze_stock(
        self,
        stock_code: str,
        stock_name: str,
        theme_name: str,
    ) -> Optional[PatternResult]:
        """단일 종목의 차트 패턴 분석.

        여러 패턴을 검사하고 가장 높은 신뢰도의 패턴 반환.
        """
        ohlcv = await self._get_ohlcv_data(stock_code)
        if ohlcv is None:
            return None

        # 모든 패턴 검사
        patterns = []

        result = self._detect_pre_breakout(ohlcv)
        if result:
            patterns.append(result)

        result = self._detect_double_bottom(ohlcv)
        if result:
            patterns.append(result)

        result = self._detect_triple_bottom(ohlcv)
        if result:
            patterns.append(result)

        result = self._detect_converging(ohlcv)
        if result:
            patterns.append(result)

        result = self._detect_range_bound(ohlcv)
        if result:
            patterns.append(result)

        if not patterns:
            return None

        # 가장 높은 신뢰도의 패턴 반환
        return max(patterns, key=lambda p: p.confidence)

    async def analyze_theme(
        self,
        theme_name: str,
    ) -> list[dict]:
        """테마 내 모든 종목의 차트 패턴 분석."""
        stocks = self._tms.get_stocks_in_theme(theme_name)
        results = []

        for stock in stocks:
            code = stock.get("code")
            name = stock.get("name")

            if not code or not name:
                continue

            try:
                pattern = await self.analyze_stock(code, name, theme_name)
                if pattern:
                    results.append({
                        "stock_code": code,
                        "stock_name": name,
                        "pattern": pattern,
                    })
            except Exception as e:
                logger.warning(f"패턴 분석 실패 ({theme_name}/{code}): {e}")
                continue

        return results

    async def _get_mentioned_stock_codes(self, days: int = 7) -> set[str]:
        """최근 언급된 종목 코드 조회 (YouTube + Expert)."""
        start_date = today_kst() - timedelta(days=days)
        mentioned_codes = set()

        # YouTube 언급 종목
        youtube_stmt = (
            select(YouTubeMention.mentioned_tickers)
            .where(YouTubeMention.published_at >= start_date)
        )
        youtube_result = await self.db.execute(youtube_stmt)
        for row in youtube_result.scalars().all():
            if row:
                mentioned_codes.update(row)

        # Expert 언급 종목
        expert_stmt = (
            select(func.distinct(ExpertMention.stock_code))
            .where(ExpertMention.mention_date >= start_date)
        )
        expert_result = await self.db.execute(expert_stmt)
        for code in expert_result.scalars().all():
            if code:
                mentioned_codes.add(code)

        logger.info(f"최근 {days}일 언급된 종목: {len(mentioned_codes)}개")
        return mentioned_codes

    def _get_themes_for_stocks(self, stock_codes: set[str]) -> set[str]:
        """종목 코드들이 속한 테마 목록 반환."""
        themes = set()
        for theme_name, stocks in self._tms.get_all_themes().items():
            theme_codes = {s.get("code") for s in stocks if s.get("code")}
            if theme_codes & stock_codes:  # 교집합이 있으면
                themes.add(theme_name)
        return themes

    async def analyze_all_themes(self) -> dict:
        """언급된 종목이 있는 테마만 차트 패턴 분석.

        Returns:
            {
                "analyzed_themes": int,
                "stocks_with_pattern": int,
                "analysis_date": str,
                "mentioned_stocks": int,
            }
        """
        analysis_date = today_kst()
        total_patterns = 0

        # 1. 언급된 종목 코드 수집
        mentioned_codes = await self._get_mentioned_stock_codes(days=7)

        if not mentioned_codes:
            logger.warning("언급된 종목이 없어 패턴 분석 스킵 (기존 패턴 유지)")
            # 기존 패턴 개수 조회
            existing_count = await self.db.scalar(
                select(func.count()).select_from(ThemeChartPattern).where(
                    ThemeChartPattern.is_active == True
                )
            )
            return {
                "analyzed_themes": 0,
                "stocks_with_pattern": existing_count or 0,
                "analysis_date": analysis_date.isoformat(),
                "mentioned_stocks": 0,
                "message": "언급된 종목이 없어 기존 패턴 유지",
            }

        # 2. 언급된 종목이 속한 테마만 선별
        target_themes = self._get_themes_for_stocks(mentioned_codes)
        logger.info(f"분석 대상 테마: {len(target_themes)}개 (전체 {self._tms.theme_count()}개 중)")

        # 3. 분석 대상 종목의 기존 패턴만 삭제 (전체 삭제 X)
        # 오늘 날짜 + 분석 대상 종목만 삭제
        if mentioned_codes:
            delete_stmt = delete(ThemeChartPattern).where(
                and_(
                    ThemeChartPattern.analysis_date == analysis_date,
                    ThemeChartPattern.stock_code.in_(mentioned_codes)
                )
            )
            await self.db.execute(delete_stmt)
            await self.db.commit()

        # 4. 선별된 테마만 분석 (언급된 종목만)
        for theme_name in target_themes:
            try:
                stocks = self._tms.get_stocks_in_theme(theme_name)
                # 테마 내에서 언급된 종목만 분석
                mentioned_in_theme = [
                    s for s in stocks
                    if s.get("code") in mentioned_codes
                ]

                for stock in mentioned_in_theme:
                    code = stock.get("code")
                    name = stock.get("name")

                    if not code or not name:
                        continue

                    try:
                        pattern = await self.analyze_stock(code, name, theme_name)
                        if pattern:
                            # numpy float를 python float로 변환
                            price_from_support = float(pattern.price_from_support_pct) if pattern.price_from_support_pct is not None else None
                            price_from_resistance = float(pattern.price_from_resistance_pct) if pattern.price_from_resistance_pct is not None else None

                            stmt = insert(ThemeChartPattern).values(
                                theme_name=theme_name,
                                stock_code=code,
                                stock_name=name,
                                pattern_type=pattern.pattern_type,
                                confidence=pattern.confidence,
                                pattern_data=pattern.pattern_data,
                                analysis_date=analysis_date,
                                is_active=True,
                                current_price=pattern.current_price,
                                price_from_support_pct=price_from_support,
                                price_from_resistance_pct=price_from_resistance,
                            ).on_conflict_do_update(
                                index_elements=['theme_name', 'stock_code', 'analysis_date'],
                                set_={
                                    'pattern_type': pattern.pattern_type,
                                    'confidence': pattern.confidence,
                                    'pattern_data': pattern.pattern_data,
                                    'is_active': True,
                                    'current_price': pattern.current_price,
                                    'price_from_support_pct': price_from_support,
                                    'price_from_resistance_pct': price_from_resistance,
                                    'updated_at': now_kst().replace(tzinfo=None),
                                }
                            )
                            await self.db.execute(stmt)
                            await self.db.commit()  # 각 종목마다 커밋
                            total_patterns += 1
                    except Exception as e:
                        logger.warning(f"종목 패턴 분석 실패 ({code}): {e}")
                        await self.db.rollback()  # 실패 시 롤백
                        continue

            except Exception as e:
                logger.error(f"테마 패턴 분석 실패 ({theme_name}): {e}")

        logger.info(f"차트 패턴 분석 완료: {len(target_themes)}개 테마, {total_patterns}개 패턴 감지")

        return {
            "analyzed_themes": len(target_themes),
            "stocks_with_pattern": total_patterns,
            "analysis_date": analysis_date.isoformat(),
            "mentioned_stocks": len(mentioned_codes),
        }

    async def get_theme_patterns(
        self,
        theme_name: str,
        analysis_date: Optional[date] = None,
    ) -> list[dict]:
        """테마의 패턴 결과 조회."""
        target_date = analysis_date or today_kst()

        stmt = (
            select(ThemeChartPattern)
            .where(
                and_(
                    ThemeChartPattern.theme_name == theme_name,
                    ThemeChartPattern.analysis_date == target_date,
                    ThemeChartPattern.is_active == True,
                )
            )
            .order_by(ThemeChartPattern.confidence.desc())
        )

        result = await self.db.execute(stmt)
        patterns = result.scalars().all()

        return [
            {
                "stock_code": p.stock_code,
                "stock_name": p.stock_name,
                "pattern_type": p.pattern_type,
                "confidence": p.confidence,
                "pattern_data": p.pattern_data,
                "current_price": p.current_price,
                "price_from_support_pct": p.price_from_support_pct,
                "price_from_resistance_pct": p.price_from_resistance_pct,
            }
            for p in patterns
        ]

    async def get_stock_pattern(
        self,
        stock_code: str,
        analysis_date: Optional[date] = None,
    ) -> Optional[dict]:
        """특정 종목의 패턴 조회."""
        target_date = analysis_date or today_kst()

        stmt = (
            select(ThemeChartPattern)
            .where(
                and_(
                    ThemeChartPattern.stock_code == stock_code,
                    ThemeChartPattern.analysis_date == target_date,
                    ThemeChartPattern.is_active == True,
                )
            )
            .order_by(ThemeChartPattern.confidence.desc())
            .limit(1)
        )

        result = await self.db.execute(stmt)
        pattern = result.scalar_one_or_none()

        if not pattern:
            return None

        return {
            "theme_name": pattern.theme_name,
            "stock_code": pattern.stock_code,
            "stock_name": pattern.stock_name,
            "pattern_type": pattern.pattern_type,
            "confidence": pattern.confidence,
            "pattern_data": pattern.pattern_data,
            "current_price": pattern.current_price,
            "price_from_support_pct": pattern.price_from_support_pct,
            "price_from_resistance_pct": pattern.price_from_resistance_pct,
        }

    async def get_pattern_score(
        self,
        theme_name: str,
    ) -> dict:
        """테마의 차트 패턴 점수 계산 (35점 만점).

        Returns:
            {
                "score": 0-35,
                "pattern_ratio": float,
                "avg_confidence": float,
                "patterns": list,
            }
        """
        stocks = self._tms.get_stocks_in_theme(theme_name)
        total_stocks = len(stocks)

        if total_stocks == 0:
            return {"score": 0, "pattern_ratio": 0, "avg_confidence": 0, "patterns": []}

        patterns = await self.get_theme_patterns(theme_name)
        pattern_count = len(patterns)

        if pattern_count == 0:
            return {"score": 0, "pattern_ratio": 0, "avg_confidence": 0, "patterns": []}

        # 패턴 감지 비율
        pattern_ratio = pattern_count / total_stocks

        # 평균 신뢰도
        avg_confidence = sum(p["confidence"] for p in patterns) / pattern_count

        # 점수 계산 (35점 만점)
        # 패턴 비율 (0-20점): 40% 이상 감지 시 만점
        ratio_score = min(pattern_ratio / 0.4 * 20, 20)
        # 평균 신뢰도 (0-15점): 80% 이상 시 만점
        confidence_score = min(avg_confidence / 80 * 15, 15)

        total_score = ratio_score + confidence_score

        # 패턴 타입별 집계
        pattern_types = list(set(p["pattern_type"] for p in patterns))

        return {
            "score": round(total_score, 1),
            "pattern_ratio": round(pattern_ratio, 2),
            "avg_confidence": round(avg_confidence, 1),
            "patterns": pattern_types,
            "pattern_count": pattern_count,
            "total_stocks": total_stocks,
        }
