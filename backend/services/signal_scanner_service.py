"""시그널 스캐너 서비스.

차트 매매 규칙 기반 시그널 엔진:
- ABCD 구간 판별
- 신고거래량 감지
- 이평선 배열 분석
- 갭 분류 (보통/돌파/진행/소멸)
- 깬돌지 (깨진자리 재돌파 지지)
- 눌림 품질 평가
"""
import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from models import StockOHLCV
from schemas.signal_scanner import (
    ABCDPhase, GapType, MAAlignment,
    ChecklistItem, ScannerSignal,
)
from services.theme_map_service import get_theme_map_service
from core.timezone import today_kst

logger = logging.getLogger(__name__)


def _grade(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    return "D"


class SignalScannerService:
    """차트 규칙 기반 시그널 엔진."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._tms = get_theme_map_service()

    # ── 데이터 조회 ──

    async def _get_all_stocks(self) -> list[dict]:
        stocks = []
        seen = set()
        for theme_stocks in self._tms.get_all_themes().values():
            for s in theme_stocks:
                code = s.get("code")
                name = s.get("name", "")
                if code and code not in seen and "스팩" not in name:
                    seen.add(code)
                    stocks.append({"code": code, "name": name})
        return stocks

    async def _bulk_get_ohlcv(self, stock_codes: list[str], days: int = 240) -> dict[str, dict]:
        start_date = today_kst() - timedelta(days=days + 30)
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
            grouped[row.stock_code].append(row)

        ohlcv_map = {}
        for code, candles in grouped.items():
            if len(candles) < 60:
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

    # ── MA 계산 ──

    def _calc_mas(self, closes: np.ndarray) -> dict:
        n = len(closes)
        return {
            "ma5": int(np.mean(closes[-5:])) if n >= 5 else None,
            "ma20": int(np.mean(closes[-20:])) if n >= 20 else None,
            "ma60": int(np.mean(closes[-60:])) if n >= 60 else None,
            "ma120": int(np.mean(closes[-120:])) if n >= 120 else None,
        }

    # ── 규칙 1: 신고거래량 감지 (20점) ──

    def _detect_record_volume(self, ohlcv: dict) -> dict:
        """A구간: 새로운 신고거래량이 터지며 기준봉."""
        volumes = ohlcv["volumes"]
        closes = ohlcv["closes"]
        opens = ohlcv["opens"]

        score = 0.0
        has_record = False
        detail = ""

        # 최근 10일 내 60일 최고 거래량 갱신 여부
        n60 = min(60, len(volumes))
        if n60 < 20:
            return {"score": 0, "max_score": 20, "has_record": False, "detail": "데이터 부족"}

        max_vol_60d = float(np.max(volumes[-n60:-10])) if n60 > 10 else float(np.max(volumes[-n60:]))
        recent_max_vol = float(np.max(volumes[-10:]))
        recent_max_idx = int(np.argmax(volumes[-10:])) + len(volumes) - 10

        if recent_max_vol > max_vol_60d:
            has_record = True
            ratio = recent_max_vol / max_vol_60d if max_vol_60d > 0 else 1
            # 기준봉: 양봉이면 추가 점수
            is_bullish = closes[recent_max_idx] > opens[recent_max_idx]

            if ratio >= 3.0 and is_bullish:
                score = 20
                detail = f"신고거래량 {ratio:.1f}배 (양봉 기준봉)"
            elif ratio >= 2.0:
                score = 15
                detail = f"신고거래량 {ratio:.1f}배"
            elif ratio >= 1.5:
                score = 10
                detail = f"거래량 증가 {ratio:.1f}배"
            else:
                score = 5
                detail = f"거래량 소폭 갱신 {ratio:.1f}배"
        else:
            # 최근 20일 평균 대비 비율
            avg_vol = float(np.mean(volumes[-20:]))
            if avg_vol > 0:
                ratio = float(np.max(volumes[-5:])) / avg_vol
                if ratio >= 2.0:
                    score = 8
                    detail = f"최근 거래량 활성 ({ratio:.1f}x)"

        return {"score": score, "max_score": 20, "has_record": has_record, "detail": detail}

    # ── 규칙 2: ABCD 구간 판별 (20점) ──

    def _detect_abcd_phase(self, ohlcv: dict) -> dict:
        """Post 06 ABCD 매매: A(신고거래량+기준봉) → B(1차돌파) → C(눌림+정배열전환) → D(재돌파)."""
        closes = ohlcv["closes"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        volumes = ohlcv["volumes"]

        if len(closes) < 60:
            return {"score": 0, "max_score": 20, "phase": ABCDPhase.UNKNOWN, "detail": "데이터 부족"}

        # 피크/트러프 찾기
        peaks, troughs = self._find_peaks_troughs(closes, window=10)

        mas = self._calc_mas(closes)
        current = float(closes[-1])
        ma20 = mas["ma20"]
        ma60 = mas["ma60"]

        phase = ABCDPhase.UNKNOWN
        score = 0.0
        detail = ""

        if not peaks or not troughs:
            return {"score": 0, "max_score": 20, "phase": ABCDPhase.UNKNOWN, "detail": "패턴 인식 불가"}

        last_peak_val = float(highs[peaks[-1]])
        last_trough_val = float(lows[troughs[-1]]) if troughs else current

        # 최근 60일 고점/저점
        high_60d = float(np.max(highs[-60:]))
        low_60d = float(np.min(lows[-60:]))
        price_range = high_60d - low_60d if high_60d > low_60d else 1

        # 현재 위치 비율
        position = (current - low_60d) / price_range

        # MA 배열 상태
        ma_bullish = ma20 and ma60 and ma20 > ma60
        price_above_ma20 = ma20 and current > ma20

        # D구간: 이전 고점 돌파 + 정배열 + 거래량 증가
        if (ma_bullish and price_above_ma20 and
                current >= last_peak_val * 0.98 and position > 0.8):
            vol_ratio = float(np.mean(volumes[-5:])) / float(np.mean(volumes[-20:])) if float(np.mean(volumes[-20:])) > 0 else 1
            if vol_ratio >= 1.2:
                phase = ABCDPhase.D
                score = 20
                detail = f"D구간: 재돌파 (고점 대비 {(current/last_peak_val-1)*100:+.1f}%, 거래량 {vol_ratio:.1f}x)"
            else:
                phase = ABCDPhase.D
                score = 15
                detail = f"D구간: 재돌파 시도 (거래량 미확인 {vol_ratio:.1f}x)"

        # C구간: 역배열→정배열 전환 중 + 눌림 + MA20 근접
        elif ma_bullish and 0.3 < position < 0.7:
            ma20_dist = abs(current - ma20) / ma20 * 100 if ma20 else 999
            if ma20_dist < 5:
                phase = ABCDPhase.C
                score = 18
                detail = f"C구간: 눌림 후 정배열 전환 (MA20 거리 {ma20_dist:.1f}%)"
            else:
                phase = ABCDPhase.C
                score = 12
                detail = f"C구간: 정배열 + 조정 중 (MA20 거리 {ma20_dist:.1f}%)"

        # B구간: 첫 번째 돌파 후 상승 중
        elif price_above_ma20 and position > 0.5:
            if not ma_bullish:
                phase = ABCDPhase.B
                score = 10
                detail = f"B구간: 1차 돌파 중 (MA20 위, 정배열 미완)"
            else:
                phase = ABCDPhase.B
                score = 8
                detail = f"B구간: 상승 진행 중"

        # A구간: 초기 거래량 폭발 + 저위치
        elif position < 0.4:
            recent_vol_max = float(np.max(volumes[-10:]))
            avg_vol = float(np.mean(volumes[-60:]))
            if avg_vol > 0 and recent_vol_max / avg_vol >= 2:
                phase = ABCDPhase.A
                score = 8
                detail = f"A구간: 초기 거래량 폭발 ({recent_vol_max/avg_vol:.1f}x)"
            else:
                phase = ABCDPhase.A
                score = 3
                detail = "A구간: 바닥권"

        return {"score": score, "max_score": 20, "phase": phase, "detail": detail}

    def _find_peaks_troughs(self, closes: np.ndarray, window: int = 10) -> tuple[list[int], list[int]]:
        """로컬 고점/저점 인덱스 찾기."""
        peaks, troughs = [], []
        n = len(closes)
        for i in range(window, n - window):
            seg = closes[max(0, i - window):i + window + 1]
            if float(closes[i]) == float(np.max(seg)):
                peaks.append(i)
            elif float(closes[i]) == float(np.min(seg)):
                troughs.append(i)
        return peaks, troughs

    # ── 규칙 3: 이평선 배열 (15점) ──

    def _detect_ma_alignment(self, ohlcv: dict) -> dict:
        """역배열→정배열 전환이 C구간."""
        closes = ohlcv["closes"]
        mas = self._calc_mas(closes)
        current = float(closes[-1])

        ma5 = mas["ma5"]
        ma20 = mas["ma20"]
        ma60 = mas["ma60"]
        ma120 = mas["ma120"]

        score = 0.0
        alignment = MAAlignment.MIXED

        if not all([ma5, ma20, ma60]):
            return {"score": 0, "max_score": 15, "alignment": MAAlignment.MIXED, "detail": "MA 데이터 부족"}

        # 정배열: 가격 > MA5 > MA20 > MA60 (> MA120)
        bullish_order = current > ma5 > ma20 > ma60
        bearish_order = current < ma5 < ma20 < ma60

        if bullish_order:
            alignment = MAAlignment.BULLISH
            score = 15
            detail = "완전 정배열 (가격>5>20>60)"
            if ma120 and ma60 > ma120:
                detail += " + MA120 위"
        elif bearish_order:
            alignment = MAAlignment.BEARISH
            score = 0
            detail = "역배열"
        else:
            alignment = MAAlignment.MIXED
            # 부분 정배열 체크
            if ma20 > ma60:
                score = 10
                detail = "반정배열 (MA20>MA60)"
                if current > ma20:
                    score = 12
                    detail += ", 가격>MA20"
            elif current > ma20:
                score = 5
                detail = "MA20 위 (역배열 중)"
            else:
                score = 2
                detail = "혼조세"

        return {"score": score, "max_score": 15, "alignment": alignment, "detail": detail}

    # ── 규칙 4: 갭 분류 (15점) ──

    def _detect_gaps(self, ohlcv: dict) -> dict:
        """Post 12: 보통갭/돌파갭/진행갭/소멸갭."""
        opens = ohlcv["opens"]
        closes = ohlcv["closes"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        volumes = ohlcv["volumes"]

        if len(closes) < 20:
            return {"score": 0, "max_score": 15, "gap_type": GapType.NONE, "detail": "데이터 부족"}

        # 최근 10일 내 갭 탐색
        gap_type = GapType.NONE
        score = 0.0
        detail = "갭 없음"

        for i in range(-10, 0):
            prev_close = float(closes[i - 1])
            curr_open = float(opens[i])
            if prev_close == 0:
                continue

            gap_pct = (curr_open - prev_close) / prev_close * 100

            if abs(gap_pct) < 1.5:
                continue

            is_up_gap = gap_pct > 0
            vol_ratio = float(volumes[i]) / float(np.mean(volumes[max(0, i - 20):i])) if float(np.mean(volumes[max(0, i - 20):i])) > 0 else 1

            # 갭 이후 메워졌는지 체크
            gap_filled = False
            for j in range(i + 1, 0):
                if is_up_gap and float(lows[j]) <= prev_close:
                    gap_filled = True
                    break
                elif not is_up_gap and float(highs[j]) >= prev_close:
                    gap_filled = True
                    break

            if not is_up_gap:
                continue  # 하락 갭은 매수 관점에서 부정적이므로 무시

            if gap_filled:
                gap_type = GapType.COMMON
                score = 3
                detail = f"보통갭 {gap_pct:+.1f}% (메워짐)"
            elif vol_ratio >= 2.0:
                # 고점 대비 위치로 돌파갭 vs 진행갭 vs 소멸갭 구분
                high_60d = float(np.max(highs[-60:]))
                current = float(closes[-1])
                position = (current - float(np.min(lows[-60:]))) / (high_60d - float(np.min(lows[-60:]))) if high_60d > float(np.min(lows[-60:])) else 0.5

                if position < 0.4:
                    gap_type = GapType.BREAKAWAY
                    score = 15
                    detail = f"돌파갭 {gap_pct:+.1f}% (거래량 {vol_ratio:.1f}x, 바닥 탈출)"
                elif position < 0.7:
                    gap_type = GapType.RUNAWAY
                    score = 12
                    detail = f"진행갭 {gap_pct:+.1f}% (추세 가속)"
                else:
                    gap_type = GapType.EXHAUSTION
                    score = 5
                    detail = f"소멸갭 의심 {gap_pct:+.1f}% (고점 부근 주의)"
            else:
                gap_type = GapType.COMMON
                score = 5
                detail = f"상승갭 {gap_pct:+.1f}% (미메워짐)"

        return {"score": score, "max_score": 15, "gap_type": gap_type, "detail": detail}

    # ── 규칙 5: 깬돌지 (15점) ──

    def _detect_kkandolji(self, ohlcv: dict) -> dict:
        """Post 28: 깨진자리 재돌파 지지."""
        closes = ohlcv["closes"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        volumes = ohlcv["volumes"]

        if len(closes) < 40:
            return {"score": 0, "max_score": 15, "has_kkandolji": False, "detail": "데이터 부족"}

        current = float(closes[-1])
        has_kkandolji = False
        score = 0.0
        detail = "깬돌지 패턴 없음"

        # 과거 지지선(20~60일 전) 중 한 번 이탈 후 재돌파한 가격대 찾기
        peaks, troughs = self._find_peaks_troughs(closes, window=5)

        for t_idx in troughs:
            if t_idx < 20 or t_idx > len(closes) - 10:
                continue

            support_level = float(lows[t_idx])
            if support_level <= 0:
                continue

            # 해당 지지선 아래로 깨진 적이 있는지
            broke_below = False
            break_idx = None
            for i in range(t_idx + 1, min(t_idx + 30, len(closes))):
                if float(closes[i]) < support_level * 0.97:
                    broke_below = True
                    break_idx = i
                    break

            if not broke_below or break_idx is None:
                continue

            # 깨진 후 다시 돌파했는지
            reclaimed = False
            for i in range(break_idx + 1, len(closes)):
                if float(closes[i]) > support_level * 1.01:
                    reclaimed = True
                    break

            if reclaimed and current >= support_level * 0.98:
                has_kkandolji = True
                dist = (current - support_level) / support_level * 100
                vol_ratio = float(np.mean(volumes[-5:])) / float(np.mean(volumes[-20:])) if float(np.mean(volumes[-20:])) > 0 else 1

                if dist < 3 and vol_ratio >= 1.3:
                    score = 15
                    detail = f"깬돌지 확인: 지지 {int(support_level):,}원 재돌파 (거리 {dist:.1f}%, 거래량 {vol_ratio:.1f}x)"
                elif dist < 5:
                    score = 10
                    detail = f"깬돌지: 지지 {int(support_level):,}원 부근 (거리 {dist:.1f}%)"
                else:
                    score = 5
                    detail = f"과거 깬돌지 패턴 존재 (현재 거리 {dist:.1f}%)"
                break

        return {"score": score, "max_score": 15, "has_kkandolji": has_kkandolji, "detail": detail}

    # ── 규칙 6: 눌림 품질 (15점) ──

    def _detect_pullback_quality(self, ohlcv: dict) -> dict:
        """정배열 + MA20 근접 + 거래량 감소 → 이상적 눌림."""
        closes = ohlcv["closes"]
        volumes = ohlcv["volumes"]
        highs = ohlcv["highs"]

        if len(closes) < 20:
            return {"score": 0, "max_score": 15, "quality": 0, "detail": "데이터 부족"}

        mas = self._calc_mas(closes)
        current = float(closes[-1])
        ma20 = mas["ma20"]
        ma60 = mas["ma60"]

        if not ma20 or not ma60:
            return {"score": 0, "max_score": 15, "quality": 0, "detail": "MA 부족"}

        score = 0.0
        parts = []

        # 1) 정배열 (ma20 > ma60)
        if ma20 > ma60:
            score += 4
            parts.append("정배열")

        # 2) MA20 근접 (5% 이내)
        ma20_dist = abs(current - ma20) / ma20 * 100
        if ma20_dist <= 2:
            score += 5
            parts.append(f"MA20 밀착 ({ma20_dist:.1f}%)")
        elif ma20_dist <= 5:
            score += 3
            parts.append(f"MA20 근접 ({ma20_dist:.1f}%)")

        # 3) 거래량 감소 (조정 중 거래량 줄어들어야)
        if len(volumes) >= 20:
            vol_recent = float(np.mean(volumes[-5:]))
            vol_avg = float(np.mean(volumes[-20:]))
            vol_ratio = vol_recent / vol_avg if vol_avg > 0 else 1
            if vol_ratio < 0.7:
                score += 4
                parts.append(f"거래량 수축 ({vol_ratio:.2f}x)")
            elif vol_ratio < 1.0:
                score += 2
                parts.append(f"거래량 감소 ({vol_ratio:.2f}x)")

        # 4) 고점 대비 적정 하락 (10~20%)
        high_60d = float(np.max(highs[-60:]))
        if high_60d > 0:
            pullback = (high_60d - current) / high_60d * 100
            if 7 <= pullback <= 20:
                score += 2
                parts.append(f"조정 {pullback:.0f}%")

        detail = ", ".join(parts) if parts else "눌림 조건 미충족"
        quality = min(100, score / 15 * 100)

        return {"score": min(score, 15), "max_score": 15, "quality": quality, "detail": detail}

    # ── 통합 분석 ──

    def _analyze_single(self, code: str, name: str, ohlcv: dict) -> Optional[ScannerSignal]:
        """단일 종목 시그널 분석."""
        closes = ohlcv["closes"]
        volumes = ohlcv["volumes"]
        current = int(closes[-1])

        # 잡주 필터
        if current < 2000:
            return None
        avg_vol = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else float(np.mean(volumes))
        if current * avg_vol < 500_000_000:
            return None

        # 6개 규칙 실행
        r1 = self._detect_record_volume(ohlcv)
        r2 = self._detect_abcd_phase(ohlcv)
        r3 = self._detect_ma_alignment(ohlcv)
        r4 = self._detect_gaps(ohlcv)
        r5 = self._detect_kkandolji(ohlcv)
        r6 = self._detect_pullback_quality(ohlcv)

        total = r1["score"] + r2["score"] + r3["score"] + r4["score"] + r5["score"] + r6["score"]
        total = min(100, total)

        breakdown = {
            "record_volume": r1["score"],
            "abcd_phase": r2["score"],
            "ma_alignment": r3["score"],
            "gap_analysis": r4["score"],
            "kkandolji": r5["score"],
            "pullback_quality": r6["score"],
        }

        mas = self._calc_mas(closes)
        ma20 = mas["ma20"]
        ma20_dist = round((current - ma20) / ma20 * 100, 2) if ma20 and ma20 > 0 else None

        vol_ratio = None
        if len(volumes) >= 20:
            v_recent = float(np.mean(volumes[-5:]))
            v_avg = float(np.mean(volumes[-20:]))
            vol_ratio = round(v_recent / v_avg, 2) if v_avg > 0 else 1.0

        # 볼린저밴드 위치 (0~1)
        bb_position = None
        if ma20 and len(closes) >= 20:
            std = float(np.std(closes[-20:]))
            if std > 0:
                upper = ma20 + 2 * std
                lower = ma20 - 2 * std
                bb_position = round((current - lower) / (upper - lower), 3) if upper != lower else 0.5

        themes = self._tms.get_themes_for_stock(code)[:3]

        return ScannerSignal(
            stock_code=code,
            stock_name=name,
            current_price=current,
            total_score=round(total, 1),
            grade=_grade(total),
            abcd_phase=r2["phase"],
            ma_alignment=r3["alignment"],
            gap_type=r4["gap_type"],
            score_breakdown=breakdown,
            themes=themes,
            ma5=mas["ma5"],
            ma20=mas["ma20"],
            ma60=mas["ma60"],
            ma120=mas["ma120"],
            volume_ratio=vol_ratio,
            has_record_volume=r1["has_record"],
            has_kkandolji=r5["has_kkandolji"],
            pullback_quality=r6.get("quality"),
            ma20_distance_pct=ma20_dist,
            bb_position=bb_position,
        )

    def _build_checklist(self, ohlcv: dict) -> list[ChecklistItem]:
        """8개 항목 체크리스트."""
        r1 = self._detect_record_volume(ohlcv)
        r2 = self._detect_abcd_phase(ohlcv)
        r3 = self._detect_ma_alignment(ohlcv)
        r4 = self._detect_gaps(ohlcv)
        r5 = self._detect_kkandolji(ohlcv)
        r6 = self._detect_pullback_quality(ohlcv)

        closes = ohlcv["closes"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        volumes = ohlcv["volumes"]
        current = float(closes[-1])

        items = [
            ChecklistItem(
                name="record_volume",
                label="신고거래량",
                passed=r1["has_record"],
                score=r1["score"],
                max_score=r1["max_score"],
                detail=r1["detail"],
            ),
            ChecklistItem(
                name="abcd_phase",
                label="ABCD 구간",
                passed=r2["score"] >= 10,
                score=r2["score"],
                max_score=r2["max_score"],
                detail=r2["detail"],
            ),
            ChecklistItem(
                name="ma_alignment",
                label="이평선 배열",
                passed=r3["alignment"] == MAAlignment.BULLISH,
                score=r3["score"],
                max_score=r3["max_score"],
                detail=r3["detail"],
            ),
            ChecklistItem(
                name="gap_analysis",
                label="갭 분석",
                passed=r4["gap_type"] in (GapType.BREAKAWAY, GapType.RUNAWAY),
                score=r4["score"],
                max_score=r4["max_score"],
                detail=r4["detail"],
            ),
            ChecklistItem(
                name="kkandolji",
                label="깬돌지",
                passed=r5["has_kkandolji"],
                score=r5["score"],
                max_score=r5["max_score"],
                detail=r5["detail"],
            ),
            ChecklistItem(
                name="pullback_quality",
                label="눌림 품질",
                passed=r6["score"] >= 10,
                score=r6["score"],
                max_score=r6["max_score"],
                detail=r6["detail"],
            ),
        ]

        # 7) 지지/저항
        support_score = 0.0
        support_detail = ""
        if len(closes) >= 60:
            support_line = float(np.percentile(lows[-60:], 10))
            resistance_line = float(np.percentile(highs[-60:], 90))
            s_dist = (current - support_line) / support_line * 100 if support_line > 0 else 999
            r_dist = (resistance_line - current) / current * 100 if current > 0 else 999

            if s_dist < 5:
                support_score = 5
                support_detail = f"지지선 근접 ({int(support_line):,}원, 거리 {s_dist:.1f}%)"
            elif r_dist < 3:
                support_score = 3
                support_detail = f"저항선 접근 ({int(resistance_line):,}원, 거리 {r_dist:.1f}%)"
            else:
                support_detail = f"지지 {int(support_line):,} / 저항 {int(resistance_line):,}"

        items.append(ChecklistItem(
            name="support_resistance",
            label="지지/저항",
            passed=support_score >= 3,
            score=support_score,
            max_score=5,
            detail=support_detail or "분석 불가",
        ))

        # 8) 다중시간대 (일봉 데이터를 주봉으로 변환하여 분석)
        mtf_score = 0.0
        mtf_detail = ""
        if len(closes) >= 100:
            # 주봉 추세: 최근 20주(100일) 종가 기울기
            weekly_closes = [float(np.mean(closes[i:i + 5])) for i in range(len(closes) - 100, len(closes), 5)]
            if len(weekly_closes) >= 5:
                x = np.arange(len(weekly_closes))
                slope = float(np.polyfit(x, weekly_closes, 1)[0])
                if slope > 0:
                    mtf_score = 5
                    mtf_detail = f"주봉 상승 추세 (기울기 {slope:.0f})"
                else:
                    mtf_detail = f"주봉 하락 추세 (기울기 {slope:.0f})"
        else:
            mtf_detail = "주봉 데이터 부족"

        items.append(ChecklistItem(
            name="multi_timeframe",
            label="다중시간대",
            passed=mtf_score >= 3,
            score=mtf_score,
            max_score=5,
            detail=mtf_detail,
        ))

        return items

    # ── 공개 API ──

    async def analyze_batch(
        self,
        min_score: float = 0.0,
        limit: int = 200,
    ) -> list[ScannerSignal]:
        """전체 종목 배치 분석."""
        all_stocks = await self._get_all_stocks()
        stock_codes = [s["code"] for s in all_stocks]
        code_to_name = {s["code"]: s["name"] for s in all_stocks}

        ohlcv_map = await self._bulk_get_ohlcv(stock_codes, days=240)

        results: list[ScannerSignal] = []
        for code in stock_codes:
            ohlcv = ohlcv_map.get(code)
            if ohlcv is None:
                continue
            try:
                sig = self._analyze_single(code, code_to_name.get(code, ""), ohlcv)
                if sig and sig.total_score >= min_score:
                    results.append(sig)
            except Exception as e:
                logger.warning(f"시그널 분석 실패 ({code}): {e}")

        results.sort(key=lambda s: s.total_score, reverse=True)
        return results[:limit]

    async def analyze_stock(self, stock_code: str) -> Optional[ScannerSignal]:
        """단일 종목 분석."""
        stock_name = ""
        for stocks in self._tms.get_all_themes().values():
            for s in stocks:
                if s.get("code") == stock_code:
                    stock_name = s.get("name", "")
                    break

        ohlcv_map = await self._bulk_get_ohlcv([stock_code], days=240)
        ohlcv = ohlcv_map.get(stock_code)
        if ohlcv is None:
            return None

        return self._analyze_single(stock_code, stock_name, ohlcv)

    async def get_checklist(self, stock_code: str) -> Optional[list[ChecklistItem]]:
        """종목 체크리스트."""
        ohlcv_map = await self._bulk_get_ohlcv([stock_code], days=240)
        ohlcv = ohlcv_map.get(stock_code)
        if ohlcv is None:
            return None
        return self._build_checklist(ohlcv)

    async def get_stock_detail(self, stock_code: str) -> Optional[dict]:
        """종목 상세 (signal + checklist + price_history)."""
        ohlcv_map = await self._bulk_get_ohlcv([stock_code], days=240)
        ohlcv = ohlcv_map.get(stock_code)
        if ohlcv is None:
            return None

        stock_name = ""
        for stocks in self._tms.get_all_themes().values():
            for s in stocks:
                if s.get("code") == stock_code:
                    stock_name = s.get("name", "")
                    break

        signal = self._analyze_single(stock_code, stock_name, ohlcv)
        if signal is None:
            return None

        checklist = self._build_checklist(ohlcv)

        # 가격 히스토리 (120일)
        n = min(120, len(ohlcv["dates"]))
        price_history = []
        for i in range(-n, 0):
            price_history.append({
                "date": ohlcv["dates"][i].isoformat(),
                "open": int(ohlcv["opens"][i]),
                "high": int(ohlcv["highs"][i]),
                "low": int(ohlcv["lows"][i]),
                "close": int(ohlcv["closes"][i]),
                "volume": int(ohlcv["volumes"][i]),
            })

        return {
            "signal": signal,
            "checklist": checklist,
            "price_history": price_history,
        }

    async def get_ohlcv_summary(self, stock_code: str) -> Optional[dict]:
        """AI 분석을 위한 OHLCV 요약 데이터."""
        ohlcv_map = await self._bulk_get_ohlcv([stock_code], days=240)
        ohlcv = ohlcv_map.get(stock_code)
        if ohlcv is None:
            return None

        closes = ohlcv["closes"]
        volumes = ohlcv["volumes"]
        mas = self._calc_mas(closes)

        # 최근 5일 캔들 요약
        recent_candles = []
        for i in range(-5, 0):
            recent_candles.append({
                "date": ohlcv["dates"][i].isoformat(),
                "open": int(ohlcv["opens"][i]),
                "high": int(ohlcv["highs"][i]),
                "low": int(ohlcv["lows"][i]),
                "close": int(ohlcv["closes"][i]),
                "volume": int(ohlcv["volumes"][i]),
            })

        vol_avg_20 = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else float(np.mean(volumes))
        vol_ratio = round(float(volumes[-1]) / vol_avg_20, 2) if vol_avg_20 > 0 else 1.0

        return {
            "current_price": int(closes[-1]),
            "ma5": mas["ma5"],
            "ma20": mas["ma20"],
            "ma60": mas["ma60"],
            "ma120": mas["ma120"],
            "volume_ratio": vol_ratio,
            "high_60d": int(np.max(ohlcv["highs"][-60:])),
            "low_60d": int(np.min(ohlcv["lows"][-60:])),
            "recent_candles": recent_candles,
        }
