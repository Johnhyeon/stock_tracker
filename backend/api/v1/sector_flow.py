"""섹터별 거래대금/수급 분석 API."""
import asyncio
import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from core.timezone import now_kst
from integrations.kis.client import get_kis_client
from services.theme_map_service import get_theme_map_service

router = APIRouter(prefix="/sector-flow", tags=["sector-flow"])
logger = logging.getLogger(__name__)

# 실시간 섹터 데이터 캐시 (60초 TTL - API 호출 시간 고려)
_realtime_cache: dict = {"data": None, "timestamp": None, "ttl": 60}

# 제외할 종목 패턴 (스팩, 리츠, ETF 등)
EXCLUDE_PATTERNS = ["스팩", "SPAC", "리츠", "Reit", "REIT", "ETN"]


def _get_exclude_condition() -> str:
    """제외 조건 SQL 생성."""
    conditions = [f"stock_name NOT LIKE '%{p}%'" for p in EXCLUDE_PATTERNS]
    return " AND ".join(conditions)


def _load_theme_map() -> dict[str, list[dict]]:
    """테마 맵 로드 (테마명 -> 종목 리스트)."""
    return get_theme_map_service().get_all_themes()


def _load_stock_theme_map() -> dict[str, list[str]]:
    """종목코드별 속한 테마 리스트 반환."""
    return get_theme_map_service().get_stock_theme_map()


# 주요 섹터 그룹 정의 (테마맵 기반 확장)
SECTOR_GROUPS = {
    "반도체": ["반도체", "HBM", "파운드리", "낸드", "NAND", "DRAM", "메모리", "CXL", "뉴로모픽", "시스템반도체", "MLCC", "PCB"],
    "2차전지": ["2차전지", "배터리", "리튬", "음극재", "양극재", "전해액", "분리막", "LFP", "전고체", "나트륨이온", "니켈"],
    "자동차": ["자동차", "전기차", "EV", "자동차부품", "스마트카", "전장"],
    "바이오": ["바이오", "제약", "신약", "의료", "헬스케어", "진단", "면역", "항암", "mRNA", "줄기세포", "유전자", "백신", "치료제", "임상"],
    "핀테크": ["핀테크", "간편결제", "가상화폐", "비트코인", "블록체인", "NFT", "STO", "토큰", "디지털자산"],
    "AI": ["AI", "인공지능", "챗봇", "챗GPT", "딥러닝", "머신러닝", "GPT", "LLM"],
    "로봇": ["로봇", "협동로봇", "서비스로봇", "산업용로봇", "드론"],
    "원전": ["원전", "원자력", "SMR", "소형모듈원전", "핵융합", "우라늄"],
    "전력설비": ["전력", "변압기", "전선", "초고압", "송전", "배전", "전기차충전"],
    "조선": ["조선", "LNG선", "해운", "컨테이너", "선박"],
    "증권": ["증권", "자산운용"],
    "방산": ["방산", "방위", "K-방산", "무기", "국방"],
    "건설": ["건설", "시멘트", "레미콘", "건축", "인테리어", "리모델링", "GTX"],
    "철강": ["철강", "스틸", "강관"],
    "신규상장": ["신규상장", "공모주", "IPO", "SPAC", "기업인수목적"],
    "은행": ["은행", "금융지주", "시중은행"],
    "지주사": ["지주회사", "지주사", "홀딩스"],
    "화장품": ["화장품", "K-뷰티", "뷰티", "화장"],
    "자율주행": ["자율주행", "ADAS", "라이다", "자율차"],
    "물류": ["물류", "택배", "창고", "운송"],
    "엔터": ["엔터테인먼트", "엔터", "K-POP", "미디어", "OTT", "콘텐츠", "영화", "드라마", "음악"],
    "게임": ["게임", "e스포츠", "모바일게임"],
    "디스플레이": ["디스플레이", "OLED", "LED", "LCD", "패널"],
    "재생에너지": ["재생에너지", "태양광", "풍력", "ESS", "수소", "연료전지", "그린"],
    "우주항공": ["우주", "항공", "위성", "UAM", "도심항공"],
    "비철금속": ["비철금속", "구리", "알루미늄", "희토류", "그래핀"],
    "보험": ["보험", "생명보험", "손해보험"],
    "통신": ["통신", "5G", "6G", "이동통신", "네트워크"],
    "인터넷": ["인터넷", "포털", "플랫폼", "SNS", "소셜"],
    "유통": ["유통", "백화점", "마트", "이커머스", "쇼핑", "면세점"],
    "음식료": ["음식", "식품", "음료", "주류", "김밥", "라면"],
    "화학": ["화학", "석유화학", "정유", "LNG", "LPG", "가스"],
    "섬유의복": ["섬유", "의류", "패션", "의복"],
    "기계": ["기계", "공작기계", "건설기계", "산업기계"],
    "IT/SW": ["IT", "SI", "클라우드", "소프트웨어", "SW", "보안", "사이버"],
    "스마트폰": ["갤럭시", "아이폰", "폴더블", "휴대폰", "스마트폰", "카메라모듈"],
    "메타버스": ["가상현실", "VR", "AR", "증강현실", "메타버스"],
    "농업": ["농업", "사료", "비료", "농기계", "종자"],
    "관광/레저": ["여행", "호텔", "리조트", "카지노", "테마파크", "항공사", "레저"],
    "부동산": ["리츠", "REITs", "부동산", "모듈러"],
    "제지/포장": ["제지", "골판지", "포장재", "종이"],
    "환경": ["폐기물", "환경", "재활용", "친환경"],
}


def _get_sector_for_theme(theme_name: str) -> str | None:
    """테마가 속한 섹터 그룹 반환."""
    for sector, themes in SECTOR_GROUPS.items():
        for t in themes:
            if t in theme_name or theme_name in t:
                return sector
    return None


@router.get("/summary")
async def get_sector_flow_summary(
    db: AsyncSession = Depends(get_async_db),
):
    """섹터별 거래대금 현황 조회.

    당일 거래대금과 5/10/20일 평균 대비 비율을 반환합니다.
    """
    theme_map = _load_theme_map()
    if not theme_map:
        return {"error": "테마 맵을 로드할 수 없습니다.", "sectors": []}

    # 테마별 종목 코드 수집 (섹터 그룹 기준)
    sector_stocks: dict[str, set[str]] = {}
    for theme_name, stocks in theme_map.items():
        sector = _get_sector_for_theme(theme_name)
        if sector:
            if sector not in sector_stocks:
                sector_stocks[sector] = set()
            for stock in stocks:
                code = stock.get("code")
                if code:
                    sector_stocks[sector].add(code)

    # 가장 많은 데이터가 있는 최신 거래일 조회 (최근 5일 중)
    date_query = text("""
        SELECT trade_date, COUNT(DISTINCT stock_code) as cnt
        FROM stock_ohlcv
        WHERE trade_date >= (SELECT MAX(trade_date) - INTERVAL '7 days' FROM stock_ohlcv)
        GROUP BY trade_date
        ORDER BY cnt DESC, trade_date DESC
        LIMIT 1
    """)
    date_result = await db.execute(date_query)
    max_date_row = date_result.fetchone()
    if not max_date_row or not max_date_row.trade_date:
        return {"error": "OHLCV 데이터가 없습니다.", "sectors": []}

    latest_date = max_date_row.trade_date
    logger.info(f"섹터 수급 기준일: {latest_date} (종목 수: {max_date_row.cnt})")

    # 섹터별 거래대금 집계
    sectors_data = []

    for sector_name, stock_codes in sector_stocks.items():
        if not stock_codes:
            continue

        codes_str = ",".join([f"'{c}'" for c in stock_codes])

        # 당일 + 과거 20일 거래대금 조회
        query = text(f"""
            WITH daily_trading AS (
                SELECT
                    trade_date,
                    SUM(close_price * volume) as trading_value,
                    COUNT(*) as stock_cnt
                FROM stock_ohlcv
                WHERE stock_code IN ({codes_str})
                    AND trade_date >= :start_date
                GROUP BY trade_date
                HAVING COUNT(*) >= 5
                ORDER BY trade_date DESC
            ),
            latest AS (
                SELECT trade_date, trading_value FROM daily_trading ORDER BY trade_date DESC LIMIT 1
            ),
            avg_5d AS (
                SELECT AVG(trading_value) as avg_val
                FROM (SELECT trading_value FROM daily_trading ORDER BY trade_date DESC LIMIT 6 OFFSET 1) t
            ),
            avg_10d AS (
                SELECT AVG(trading_value) as avg_val
                FROM (SELECT trading_value FROM daily_trading ORDER BY trade_date DESC LIMIT 11 OFFSET 1) t
            ),
            avg_20d AS (
                SELECT AVG(trading_value) as avg_val
                FROM (SELECT trading_value FROM daily_trading ORDER BY trade_date DESC LIMIT 21 OFFSET 1) t
            )
            SELECT
                (SELECT trade_date FROM latest) as trade_date,
                (SELECT trading_value FROM latest) as today_value,
                (SELECT avg_val FROM avg_5d) as avg_5d,
                (SELECT avg_val FROM avg_10d) as avg_10d,
                (SELECT avg_val FROM avg_20d) as avg_20d
        """)

        start_date = latest_date - timedelta(days=40)
        result = await db.execute(query, {"start_date": start_date})
        row = result.fetchone()

        if not row or not row.today_value:
            continue

        today_value = float(row.today_value or 0)
        avg_5d = float(row.avg_5d or 0) if row.avg_5d else today_value
        avg_10d = float(row.avg_10d or 0) if row.avg_10d else today_value
        avg_20d = float(row.avg_20d or 0) if row.avg_20d else today_value

        # 비율 계산 (%)
        ratio_5d = (today_value / avg_5d * 100) if avg_5d > 0 else 100
        ratio_10d = (today_value / avg_10d * 100) if avg_10d > 0 else 100
        ratio_20d = (today_value / avg_20d * 100) if avg_20d > 0 else 100

        # 수급 데이터 조회
        flow_query = text(f"""
            SELECT
                SUM(foreign_net_amount) as foreign_net,
                SUM(institution_net_amount) as institution_net
            FROM stock_investor_flows
            WHERE stock_code IN ({codes_str})
                AND flow_date = (SELECT MAX(flow_date) FROM stock_investor_flows WHERE stock_code IN ({codes_str}))
        """)
        flow_result = await db.execute(flow_query)
        flow_row = flow_result.fetchone()

        foreign_net = int(flow_row.foreign_net or 0) if flow_row else 0
        institution_net = int(flow_row.institution_net or 0) if flow_row else 0

        sectors_data.append({
            "sector_name": sector_name,
            "stock_count": len(stock_codes),
            "today_trading_value": int(today_value),
            "avg_5d": int(avg_5d),
            "avg_10d": int(avg_10d),
            "avg_20d": int(avg_20d),
            "ratio_5d": round(ratio_5d, 0),
            "ratio_10d": round(ratio_10d, 0),
            "ratio_20d": round(ratio_20d, 0),
            "is_hot": ratio_5d >= 200,  # 5일 평균 대비 200% 이상
            "foreign_net": foreign_net,
            "institution_net": institution_net,
        })

    # 거래대금 순으로 정렬
    sectors_data.sort(key=lambda x: x["today_trading_value"], reverse=True)

    # 총 시장 거래대금
    total_value = sum(s["today_trading_value"] for s in sectors_data)

    # 비중 계산
    for sector in sectors_data:
        sector["weight"] = round(sector["today_trading_value"] / total_value * 100, 1) if total_value > 0 else 0

    return {
        "sectors": sectors_data,
        "total_trading_value": int(total_value),
        "trade_date": latest_date.isoformat(),
        "generated_at": now_kst().isoformat(),
    }


@router.get("/ranking")
async def get_sector_flow_ranking(
    period: str = Query(default="5d", regex="^(5d|10d|20d)$"),
    sort_by: str = Query(default="ratio", regex="^(ratio|value|flow)$"),
    limit: int = Query(default=30, le=50),
    db: AsyncSession = Depends(get_async_db),
):
    """섹터별 거래대금 비율 랭킹.

    Args:
        period: 비교 기간 (5d, 10d, 20d)
        sort_by: 정렬 기준 (ratio: 비율, value: 거래대금, flow: 수급)
        limit: 반환할 섹터 수
    """
    # summary API 호출하여 데이터 가져오기
    summary = await get_sector_flow_summary(db)

    if "error" in summary:
        return summary

    sectors = summary["sectors"]

    # 정렬
    period_key = f"ratio_{period.replace('d', '')}d"
    if sort_by == "ratio":
        sectors.sort(key=lambda x: x.get(period_key, 0), reverse=True)
    elif sort_by == "value":
        sectors.sort(key=lambda x: x["today_trading_value"], reverse=True)
    elif sort_by == "flow":
        sectors.sort(key=lambda x: x["foreign_net"] + x["institution_net"], reverse=True)

    return {
        "sectors": sectors[:limit],
        "period": period,
        "sort_by": sort_by,
        "count": len(sectors[:limit]),
        "trade_date": summary.get("trade_date"),
        "generated_at": now_kst().isoformat(),
    }


@router.get("/treemap")
async def get_sector_treemap_data(
    period: str = Query(default="5d", regex="^(5d|10d|20d)$"),
    db: AsyncSession = Depends(get_async_db),
):
    """트리맵 시각화용 섹터 데이터.

    크기: 거래대금 비중
    색상: 평균 대비 비율 (200% 이상 강조)
    """
    summary = await get_sector_flow_summary(db)

    if "error" in summary:
        return summary

    period_key = f"ratio_{period.replace('d', '')}d"

    treemap_data = []
    for sector in summary["sectors"]:
        ratio = sector.get(period_key, 100)

        # 색상 결정 (비율 기준)
        if ratio >= 300:
            color_level = "extreme"  # 극단적 급등
        elif ratio >= 200:
            color_level = "hot"      # 급등
        elif ratio >= 150:
            color_level = "warm"     # 상승
        elif ratio >= 100:
            color_level = "neutral"  # 평균
        elif ratio >= 70:
            color_level = "cool"     # 하락
        else:
            color_level = "cold"     # 급락

        treemap_data.append({
            "name": sector["sector_name"],
            "value": sector["today_trading_value"],
            "weight": sector["weight"],
            "ratio": ratio,
            "color_level": color_level,
            "is_hot": sector["is_hot"],
            "foreign_net": sector["foreign_net"],
            "institution_net": sector["institution_net"],
            "stock_count": sector["stock_count"],
        })

    return {
        "data": treemap_data,
        "period": period,
        "total_value": summary["total_trading_value"],
        "trade_date": summary.get("trade_date"),
        "generated_at": now_kst().isoformat(),
    }


@router.get("/{sector_name}/stocks")
async def get_sector_stocks(
    sector_name: str,
    limit: int = Query(default=20, le=50),
    db: AsyncSession = Depends(get_async_db),
):
    """특정 섹터의 종목별 상세 거래대금/수급 데이터."""
    theme_map = _load_theme_map()

    # 섹터에 속한 종목 코드 수집
    stock_codes = set()
    for theme_name, stocks in theme_map.items():
        sector = _get_sector_for_theme(theme_name)
        if sector == sector_name:
            for stock in stocks:
                code = stock.get("code")
                if code:
                    stock_codes.add(code)

    if not stock_codes:
        return {"error": f"'{sector_name}' 섹터를 찾을 수 없습니다.", "stocks": []}

    codes_str = ",".join([f"'{c}'" for c in stock_codes])

    # 가장 많은 데이터가 있는 최신 거래일 조회
    date_query = text("""
        SELECT trade_date, COUNT(DISTINCT stock_code) as cnt
        FROM stock_ohlcv
        WHERE trade_date >= (SELECT MAX(trade_date) - INTERVAL '7 days' FROM stock_ohlcv)
        GROUP BY trade_date
        ORDER BY cnt DESC, trade_date DESC
        LIMIT 1
    """)
    date_result = await db.execute(date_query)
    max_date_row = date_result.fetchone()
    latest_date = max_date_row.trade_date if max_date_row else None

    if not latest_date:
        return {"error": "OHLCV 데이터가 없습니다.", "stocks": []}

    # 종목별 거래대금 조회
    query = text(f"""
        WITH today_ohlcv AS (
            SELECT
                o.stock_code,
                s.name as stock_name,
                o.close_price,
                o.volume,
                (o.close_price * o.volume) as trading_value
            FROM stock_ohlcv o
            LEFT JOIN stocks s ON o.stock_code = s.code
            WHERE o.stock_code IN ({codes_str})
                AND o.trade_date = :latest_date
        ),
        flow_data AS (
            SELECT
                stock_code,
                foreign_net_amount,
                institution_net_amount,
                individual_net_amount
            FROM stock_investor_flows
            WHERE stock_code IN ({codes_str})
                AND flow_date = (SELECT MAX(flow_date) FROM stock_investor_flows)
        )
        SELECT
            t.stock_code,
            COALESCE(t.stock_name, t.stock_code) as stock_name,
            t.close_price,
            t.volume,
            t.trading_value,
            COALESCE(f.foreign_net_amount, 0) as foreign_net,
            COALESCE(f.institution_net_amount, 0) as institution_net,
            COALESCE(f.individual_net_amount, 0) as individual_net
        FROM today_ohlcv t
        LEFT JOIN flow_data f ON t.stock_code = f.stock_code
        ORDER BY t.trading_value DESC
        LIMIT :limit
    """)

    result = await db.execute(query, {"latest_date": latest_date, "limit": limit})
    rows = result.fetchall()

    stocks = []
    for row in rows:
        stocks.append({
            "stock_code": row.stock_code,
            "stock_name": row.stock_name,
            "close_price": int(row.close_price or 0),
            "volume": int(row.volume or 0),
            "trading_value": int(row.trading_value or 0),
            "foreign_net": int(row.foreign_net or 0),
            "institution_net": int(row.institution_net or 0),
            "individual_net": int(row.individual_net or 0),
        })

    return {
        "sector_name": sector_name,
        "stocks": stocks,
        "count": len(stocks),
        "trade_date": latest_date.isoformat(),
        "generated_at": now_kst().isoformat(),
    }


def _build_sector_stocks_map() -> dict[str, set[str]]:
    """섹터별 종목 코드 맵 구축."""
    theme_map = _load_theme_map()
    sector_stocks: dict[str, set[str]] = {}

    for theme_name, stocks in theme_map.items():
        sector = _get_sector_for_theme(theme_name)
        if sector:
            if sector not in sector_stocks:
                sector_stocks[sector] = set()
            for stock in stocks:
                code = stock.get("code")
                if code:
                    sector_stocks[sector].add(code)

    return sector_stocks


@router.get("/realtime")
async def get_realtime_sector_flow(
    db: AsyncSession = Depends(get_async_db),
    force_refresh: bool = Query(default=False, description="캐시 무시하고 강제 갱신"),
):
    """실시간 섹터별 거래대금/수급 현황.

    KIS API를 통해 당일 실시간 데이터를 조회합니다.
    장중에만 유효하며, 장 마감 후에는 DB 데이터를 반환합니다.
    30초 캐시를 사용하여 API 부하를 줄입니다.
    """
    global _realtime_cache
    now = now_kst()
    is_market_open = (
        now.weekday() < 5  # 월-금
        and 9 <= now.hour < 16  # 09:00 ~ 15:59
    )

    # 장 마감 시 DB 데이터 반환
    if not is_market_open:
        summary = await get_sector_flow_summary(db)
        summary["market_status"] = "closed"
        summary["is_realtime"] = False
        return summary

    # 캐시 확인 (30초 이내)
    if not force_refresh and _realtime_cache["data"] and _realtime_cache["timestamp"]:
        elapsed = (now - _realtime_cache["timestamp"]).total_seconds()
        if elapsed < _realtime_cache["ttl"]:
            cached = _realtime_cache["data"].copy()
            cached["cached"] = True
            cached["cache_age_seconds"] = int(elapsed)
            return cached

    # 섹터별 종목 맵 구축
    sector_stocks = _build_sector_stocks_map()

    # 과거 평균 데이터 조회 (DB)
    date_query = text("SELECT MAX(trade_date) as max_date FROM stock_ohlcv")
    date_result = await db.execute(date_query)
    max_date_row = date_result.fetchone()
    if not max_date_row or not max_date_row.max_date:
        return {"error": "OHLCV 데이터가 없습니다.", "sectors": [], "market_status": "error"}

    latest_db_date = max_date_row.max_date

    # KIS API로 실시간 데이터 조회 (섹터별 대표 종목만)
    kis_client = get_kis_client()

    # 모든 섹터의 상위 종목을 한 번에 수집하여 일괄 조회
    # 속도 최적화: 각 섹터에서 3개씩만 샘플링 (총 ~120개, 약 15초 소요)
    all_codes_to_fetch: set[str] = set()
    sector_sample_codes: dict[str, list[str]] = {}

    for sector_name, stock_codes in sector_stocks.items():
        codes = list(stock_codes)[:3]  # 각 섹터 상위 3개만
        sector_sample_codes[sector_name] = codes
        all_codes_to_fetch.update(codes)

    # 샘플 종목의 과거 평균 조회 (동일 종목으로 비교)
    sector_avgs: dict[str, dict] = {}
    for sector_name, sample_codes in sector_sample_codes.items():
        if not sample_codes:
            continue

        codes_str = ",".join([f"'{c}'" for c in sample_codes])
        avg_query = text(f"""
            WITH daily_trading AS (
                SELECT trade_date, SUM(close_price * volume) as trading_value
                FROM stock_ohlcv
                WHERE stock_code IN ({codes_str})
                    AND trade_date >= :start_date
                GROUP BY trade_date
                ORDER BY trade_date DESC
            )
            SELECT
                AVG(trading_value) as avg_5d
            FROM (SELECT trading_value FROM daily_trading LIMIT 5) t
        """)
        start_date = latest_db_date - timedelta(days=10)
        result = await db.execute(avg_query, {"start_date": start_date})
        row = result.fetchone()
        sector_avgs[sector_name] = {
            "avg_5d": float(row.avg_5d or 0) if row else 0,
            "stock_codes": sector_stocks[sector_name],  # 전체 종목 수 유지
        }

    # 모든 종목 가격 일괄 조회 (병렬성 높이고 딜레이 줄임)
    all_codes_list = list(all_codes_to_fetch)
    all_prices: dict = {}

    try:
        # 더 빠른 조회: batch_size 증가, 딜레이 감소
        prices = await kis_client.get_multiple_prices(
            all_codes_list,
            max_concurrent=8,  # 동시 요청 수 증가
            delay_between=0.05,  # 딜레이 감소
            batch_size=20,  # 배치 크기 증가
        )
        all_prices.update(prices)
    except Exception as e:
        logger.error(f"실시간 가격 일괄 조회 실패: {e}")
        # 실패 시 DB 데이터 반환
        summary = await get_sector_flow_summary(db)
        summary["market_status"] = "error"
        summary["is_realtime"] = False
        summary["error"] = str(e)
        return summary

    # 시간 비율 계산
    minutes_elapsed = (now.hour - 9) * 60 + now.minute
    total_minutes = 6.5 * 60  # 390분
    time_ratio = max(0.1, min(1.0, minutes_elapsed / total_minutes))

    # 섹터별 수급 데이터 조회 (한 번에 모든 종목 조회 후 섹터별 집계)
    all_sector_codes = set()
    for codes in sector_stocks.values():
        all_sector_codes.update(codes)

    all_codes_str = ",".join([f"'{c}'" for c in all_sector_codes])
    flow_query = text(f"""
        SELECT stock_code, foreign_net_amount, institution_net_amount
        FROM stock_investor_flows
        WHERE stock_code IN ({all_codes_str})
            AND flow_date = (SELECT MAX(flow_date) FROM stock_investor_flows)
    """)
    flow_result = await db.execute(flow_query)
    flow_rows = flow_result.fetchall()

    # 종목별 수급 데이터 매핑
    stock_flows = {row.stock_code: {"foreign": row.foreign_net_amount or 0, "institution": row.institution_net_amount or 0} for row in flow_rows}

    # 섹터별 집계
    sector_flows: dict[str, dict] = {}
    for sector_name, stock_codes in sector_stocks.items():
        foreign_sum = sum(stock_flows.get(c, {}).get("foreign", 0) for c in stock_codes)
        institution_sum = sum(stock_flows.get(c, {}).get("institution", 0) for c in stock_codes)
        sector_flows[sector_name] = {
            "foreign_net": int(foreign_sum),
            "institution_net": int(institution_sum),
        }

    # 섹터별 집계 (샘플 종목끼리 비교 - 스케일업 없음)
    sectors_data = []
    for sector_name, codes in sector_sample_codes.items():
        total_trading_value = 0
        valid_count = 0

        for code in codes:
            price_data = all_prices.get(code)
            if price_data:
                current_price = price_data.get("current_price", 0)
                volume = price_data.get("volume", 0)
                if current_price and volume:
                    total_trading_value += float(current_price) * float(volume)
                    valid_count += 1

        if valid_count == 0:
            continue

        total_stocks = len(sector_avgs[sector_name]["stock_codes"])
        trading_value = int(total_trading_value)  # 샘플 종목의 실제 거래대금

        # 비율 계산 (샘플 종목의 과거 평균과 비교)
        avg_5d = sector_avgs[sector_name]["avg_5d"]
        estimated_full_day = trading_value / time_ratio if time_ratio > 0 else trading_value
        ratio_5d = (estimated_full_day / avg_5d * 100) if avg_5d > 0 else 100

        # 수급 데이터 (DB에서 조회)
        flow_data = sector_flows.get(sector_name, {})

        sectors_data.append({
            "sector_name": sector_name,
            "stock_count": total_stocks,
            "today_trading_value": trading_value,
            "estimated_full_day": int(estimated_full_day),
            "avg_5d": int(avg_5d),
            "ratio_5d": round(ratio_5d, 0),
            "is_hot": ratio_5d >= 200,
            "foreign_net": flow_data.get("foreign_net", 0),
            "institution_net": flow_data.get("institution_net", 0),
            "time_ratio": round(time_ratio * 100, 0),
            "sampled_stocks": valid_count,  # 조회된 샘플 종목 수
        })

    # 거래대금 순 정렬
    sectors_data.sort(key=lambda x: x["today_trading_value"], reverse=True)

    # 비중 계산
    total_value = sum(s["today_trading_value"] for s in sectors_data)
    for sector in sectors_data:
        sector["weight"] = round(sector["today_trading_value"] / total_value * 100, 1) if total_value > 0 else 0

    result = {
        "sectors": sectors_data,
        "total_trading_value": int(total_value),
        "market_status": "open",
        "is_realtime": True,
        "cached": False,
        "time_ratio": round((minutes_elapsed / total_minutes) * 100, 0) if is_market_open else 100,
        "generated_at": now_kst().isoformat(),
    }

    # 캐시 저장
    _realtime_cache["data"] = result
    _realtime_cache["timestamp"] = now

    return result
