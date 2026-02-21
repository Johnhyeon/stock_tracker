"""장중 갭다운 회복 분석 서비스.

백그라운드 스케줄러가 2분마다 전체 스캔 → 캐시에 저장.
API는 캐시에서 즉시 반환 (KIS 호출 없음).
"""
import logging
from datetime import datetime

from core.cache import api_cache
from core.timezone import now_kst, KST

logger = logging.getLogger(__name__)

# 백그라운드 스캔 결과 저장 키
_SCAN_CACHE_KEY = "recovery:full_scan"


def _is_market_open() -> bool:
    """장 시간(09:00~15:30, 평일) 여부."""
    now = now_kst()
    if now.weekday() >= 5:
        return False
    t = now.hour * 100 + now.minute
    return 900 <= t <= 1530


async def _check_index_decline(threshold: float = -0.5) -> bool:
    """KOSPI 또는 KOSDAQ 지수가 threshold% 이상 하락했는지 확인.

    Returns:
        True이면 하락 조건 충족 (스캔 실행), False이면 미충족 (스킵).
    """
    from integrations.kis.client import get_kis_client

    kis = get_kis_client()
    for index_code in ["0001", "1001"]:  # KOSPI, KOSDAQ
        try:
            data = await kis.get_market_index(index_code)
            change_rate = float(data.get("change_rate", 0))
            if change_rate <= threshold:
                logger.info(
                    f"지수 하락 감지: {data.get('index_name', index_code)} "
                    f"{change_rate:+.2f}% (임계값 {threshold}%)"
                )
                return True
        except Exception as e:
            logger.warning(f"지수 조회 실패 ({index_code}): {e}")
            # 지수 조회 실패 시 안전하게 스캔 실행
            return True

    return False


async def run_gap_recovery_scan():
    """백그라운드 전체 스캔 (스케줄러에서 호출).

    전 종목 현재가를 KIS API로 조회하여 갭다운+회복 데이터를 계산하고 캐시에 저장.
    KOSPI/KOSDAQ 지수가 -0.5% 이상 하락한 경우에만 실행.
    """
    from integrations.kis.client import get_kis_client
    from services.theme_map_service import get_theme_map_service

    # 지수 하락 조건 체크
    if not await _check_index_decline(-0.5):
        logger.debug("갭 회복 스캔 스킵: 지수 하락 조건 미충족 (KOSPI/KOSDAQ 모두 -0.5% 미만)")
        return

    kis = get_kis_client()
    theme_map = get_theme_map_service()

    # 1. 추적 종목 수집 (스팩 제외)
    stock_codes = []
    stock_themes: dict[str, list[str]] = {}
    seen = set()
    for theme_name, stocks in theme_map.get_all_themes().items():
        for s in stocks:
            code = s.get("code")
            name = s.get("name", "")
            if code and "스팩" not in name and code not in seen:
                seen.add(code)
                stock_codes.append(code)
                stock_themes[code] = []
            if code and code in stock_themes:
                stock_themes[code].append(theme_name)

    # 중복 테마 제거
    for code in stock_themes:
        stock_themes[code] = list(dict.fromkeys(stock_themes[code]))

    if not stock_codes:
        logger.info("갭 회복 스캔: 추적 종목 없음")
        return

    logger.info(f"갭 회복 스캔 시작: {len(stock_codes)}종목")
    start = now_kst()

    # 2. KIS 현재가 일괄 조회 (최대 동시성 + 빠른 속도)
    try:
        prices = await kis.get_multiple_prices(
            stock_codes,
            max_concurrent=8,
            delay_between=0.08,
            batch_size=30,
        )
    except Exception as e:
        logger.error(f"갭 회복 스캔 KIS 조회 실패: {e}")
        return

    # 3. 전 종목 갭다운+회복 계산 (필터 없이 전부 저장)
    all_stocks = []
    for code, price in prices.items():
        open_p = float(price.get("open_price", 0))
        prev_close = float(price.get("prev_close", 0))
        current = float(price.get("current_price", 0))
        high = float(price.get("high_price", 0))
        low = float(price.get("low_price", 0))
        volume = int(price.get("volume", 0))
        name = price.get("stock_name", code)

        if prev_close == 0 or open_p == 0 or current == 0:
            continue
        if current < 2000:
            continue

        gap_pct = (open_p - prev_close) / prev_close * 100

        # 갭다운 종목만
        if gap_pct >= 0:
            continue

        gap_size = prev_close - open_p
        gap_fill_pct = (current - open_p) / gap_size * 100 if gap_size > 0 else 0
        change_from_open_pct = (current - open_p) / open_p * 100
        day_range = high - low
        recovery_from_low_pct = (current - low) / day_range * 100 if day_range > 0 else 50.0
        is_above_prev = current >= prev_close

        score = 0.0
        score += min(40, max(0, gap_fill_pct * 0.4))
        score += min(25, max(0, change_from_open_pct * 5))
        score += min(20, recovery_from_low_pct * 0.2)
        if is_above_prev:
            score += 15
        score = round(min(100, max(0, score)), 1)

        all_stocks.append({
            "stock_code": code,
            "stock_name": name,
            "themes": stock_themes.get(code, [])[:3],
            "prev_close": prev_close,
            "open_price": open_p,
            "current_price": current,
            "high_price": high,
            "low_price": low,
            "volume": volume,
            "gap_pct": round(gap_pct, 2),
            "change_from_open_pct": round(change_from_open_pct, 2),
            "gap_fill_pct": round(gap_fill_pct, 1),
            "recovery_from_low_pct": round(recovery_from_low_pct, 1),
            "is_above_prev_close": is_above_prev,
            "recovery_score": score,
        })

    all_stocks.sort(key=lambda x: x["recovery_score"], reverse=True)

    elapsed = (now_kst() - start).total_seconds()
    logger.info(f"갭 회복 스캔 완료: {len(all_stocks)}종목 갭다운 / {len(prices)}종목 조회 ({elapsed:.1f}초)")

    # 캐시에 전체 결과 저장 (3분 TTL — 2분 주기 스캔이므로 항상 갱신됨)
    api_cache.set(_SCAN_CACHE_KEY, {
        "stocks": all_stocks,
        "total_gap_down": len(all_stocks),
        "total_scanned": len(prices),
        "generated_at": now_kst().isoformat(),
    }, ttl=180)


class RecoveryAnalysisService:
    """장중 갭다운 → 회복 분석 (캐시 기반 즉시 응답)."""

    async def get_realtime_recovery(
        self,
        min_gap_pct: float = 0.5,
        limit: int = 30,
    ) -> dict:
        """갭다운 후 회복 빠른 종목 랭킹 (캐시에서 즉시 반환)."""
        cached = api_cache.get(_SCAN_CACHE_KEY)

        if cached:
            # 캐시에서 필터링만
            stocks = [s for s in cached["stocks"] if s["gap_pct"] <= -min_gap_pct]
            return {
                "stocks": stocks[:limit],
                "count": min(len(stocks), limit),
                "total_gap_down": len(stocks),
                "total_scanned": cached["total_scanned"],
                "market_status": "open" if _is_market_open() else "closed",
                "min_gap_pct": min_gap_pct,
                "generated_at": cached["generated_at"],
            }

        # 캐시 없음 → 스캔이 아직 안 됨. 빈 응답 + 즉시 백그라운드 스캔 트리거
        import asyncio
        asyncio.get_running_loop().create_task(self._quick_scan_and_cache())

        return {
            "stocks": [],
            "count": 0,
            "total_gap_down": 0,
            "total_scanned": 0,
            "market_status": "open" if _is_market_open() else "closed",
            "min_gap_pct": min_gap_pct,
            "generated_at": now_kst().isoformat(),
            "message": "첫 스캔 진행중... 10~20초 후 새로고침하세요.",
        }

    async def _quick_scan_and_cache(self):
        """캐시 미스 시 백그라운드에서 즉시 스캔."""
        try:
            await run_gap_recovery_scan()
        except Exception as e:
            logger.error(f"긴급 갭 회복 스캔 실패: {e}")
