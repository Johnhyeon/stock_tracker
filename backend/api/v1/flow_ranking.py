"""수급 랭킹 API 엔드포인트."""
import asyncio
import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from integrations.kis.client import get_kis_client

router = APIRouter(prefix="/flow-ranking", tags=["flow-ranking"])
logger = logging.getLogger(__name__)

# 제외할 종목 패턴 (스팩, 리츠, ETF 등)
EXCLUDE_PATTERNS = [
    "스팩", "SPAC",
    "리츠", "Reit", "REIT",
    "ETN",
]

def _get_exclude_condition() -> str:
    """제외 조건 SQL 생성."""
    conditions = [f"stock_name NOT LIKE '%{p}%'" for p in EXCLUDE_PATTERNS]
    return " AND ".join(conditions)


# 테마 맵 로드 (종목코드 -> 테마 리스트)
def _load_stock_theme_map() -> dict[str, list[str]]:
    """종목코드별 속한 테마 리스트 반환."""
    theme_map_path = Path(__file__).parent.parent.parent / "data" / "theme_map.json"
    stock_themes: dict[str, list[str]] = {}
    try:
        with open(theme_map_path, "r", encoding="utf-8") as f:
            theme_map = json.load(f)
        for theme_name, stocks in theme_map.items():
            for stock in stocks:
                code = stock.get("code")
                if code:
                    if code not in stock_themes:
                        stock_themes[code] = []
                    stock_themes[code].append(theme_name)
    except Exception:
        pass
    return stock_themes


@router.get("/top")
async def get_top_flow_stocks(
    days: int = Query(default=5, le=30),
    limit: int = Query(default=30, le=100),
    investor_type: str = Query(default="all", regex="^(all|foreign|institution|individual)$"),
    db: AsyncSession = Depends(get_async_db),
):
    """수급 상위 종목 조회.

    최근 N일간 외국인+기관 순매수 상위 종목을 반환합니다.

    Args:
        days: 집계 기간 (기본 5일)
        limit: 반환할 종목 수 (기본 30개)
        investor_type: all(합계), foreign(외국인만), institution(기관만), individual(개인만)
    """
    # 순매수금액 기준 컬럼 선택 (네이버 방식)
    if investor_type == "foreign":
        order_col = "foreign_amount_sum"
    elif investor_type == "institution":
        order_col = "institution_amount_sum"
    elif investor_type == "individual":
        order_col = "individual_amount_sum"
    else:
        order_col = "total_amount_sum"

    # CURRENT_DATE 대신 MAX(flow_date)를 기준으로 사용 (휴일/주말에도 최신 거래일 데이터 표시)
    exclude_cond = _get_exclude_condition()
    query = text(f"""
        SELECT
            stock_code,
            stock_name,
            SUM(foreign_net) as foreign_sum,
            SUM(institution_net) as institution_sum,
            SUM(individual_net) as individual_sum,
            SUM(foreign_net + institution_net) as total_sum,
            SUM(foreign_net_amount) as foreign_amount_sum,
            SUM(institution_net_amount) as institution_amount_sum,
            SUM(individual_net_amount) as individual_amount_sum,
            SUM(foreign_net_amount + institution_net_amount) as total_amount_sum,
            AVG(flow_score) as avg_score,
            COUNT(*) as data_days,
            MAX(flow_date) as latest_date
        FROM stock_investor_flows
        WHERE flow_date >= (SELECT MAX(flow_date) - INTERVAL '{days} days' FROM stock_investor_flows)
            AND {exclude_cond}
        GROUP BY stock_code, stock_name
        HAVING COUNT(*) >= {max(1, days // 2)}
            AND SUM(foreign_net_amount + institution_net_amount) > 0
        ORDER BY {order_col} DESC
        LIMIT :limit
    """)

    result = await db.execute(query, {"limit": limit})
    rows = result.fetchall()

    # 테마 맵 로드
    stock_themes = _load_stock_theme_map()

    stocks = []
    for row in rows:
        stocks.append({
            "stock_code": row.stock_code,
            "stock_name": row.stock_name,
            "foreign_sum": int(row.foreign_sum),
            "institution_sum": int(row.institution_sum),
            "individual_sum": int(row.individual_sum),
            "total_sum": int(row.total_sum),
            # 금액 필드 추가 (단위: 원)
            "foreign_amount_sum": int(row.foreign_amount_sum or 0),
            "institution_amount_sum": int(row.institution_amount_sum or 0),
            "individual_amount_sum": int(row.individual_amount_sum or 0),
            "total_amount_sum": int(row.total_amount_sum or 0),
            "avg_score": float(row.avg_score),
            "data_days": int(row.data_days),
            "latest_date": row.latest_date.isoformat() if row.latest_date else None,
            "themes": stock_themes.get(row.stock_code, []),
        })

    return {
        "stocks": stocks,
        "count": len(stocks),
        "days": days,
        "investor_type": investor_type,
        "generated_at": datetime.now().isoformat(),
    }


@router.get("/bottom")
async def get_bottom_flow_stocks(
    days: int = Query(default=5, le=30),
    limit: int = Query(default=30, le=100),
    investor_type: str = Query(default="all", regex="^(all|foreign|institution|individual)$"),
    db: AsyncSession = Depends(get_async_db),
):
    """수급 하위 종목 조회 (순매도 상위).

    최근 N일간 외국인+기관 순매도 상위 종목을 반환합니다.
    """
    # 순매수금액 기준 컬럼 선택 (네이버 방식)
    if investor_type == "foreign":
        order_col = "foreign_amount_sum"
    elif investor_type == "institution":
        order_col = "institution_amount_sum"
    elif investor_type == "individual":
        order_col = "individual_amount_sum"
    else:
        order_col = "total_amount_sum"

    # CURRENT_DATE 대신 MAX(flow_date)를 기준으로 사용 (휴일/주말에도 최신 거래일 데이터 표시)
    exclude_cond = _get_exclude_condition()
    query = text(f"""
        SELECT
            stock_code,
            stock_name,
            SUM(foreign_net) as foreign_sum,
            SUM(institution_net) as institution_sum,
            SUM(individual_net) as individual_sum,
            SUM(foreign_net + institution_net) as total_sum,
            SUM(foreign_net_amount) as foreign_amount_sum,
            SUM(institution_net_amount) as institution_amount_sum,
            SUM(individual_net_amount) as individual_amount_sum,
            SUM(foreign_net_amount + institution_net_amount) as total_amount_sum,
            AVG(flow_score) as avg_score,
            COUNT(*) as data_days,
            MAX(flow_date) as latest_date
        FROM stock_investor_flows
        WHERE flow_date >= (SELECT MAX(flow_date) - INTERVAL '{days} days' FROM stock_investor_flows)
            AND {exclude_cond}
        GROUP BY stock_code, stock_name
        HAVING COUNT(*) >= {max(1, days // 2)}
            AND SUM(foreign_net_amount + institution_net_amount) < 0
        ORDER BY {order_col} ASC
        LIMIT :limit
    """)

    result = await db.execute(query, {"limit": limit})
    rows = result.fetchall()

    # 테마 맵 로드
    stock_themes = _load_stock_theme_map()

    stocks = []
    for row in rows:
        stocks.append({
            "stock_code": row.stock_code,
            "stock_name": row.stock_name,
            "foreign_sum": int(row.foreign_sum),
            "institution_sum": int(row.institution_sum),
            "individual_sum": int(row.individual_sum),
            "total_sum": int(row.total_sum),
            # 금액 필드 추가 (단위: 원)
            "foreign_amount_sum": int(row.foreign_amount_sum or 0),
            "institution_amount_sum": int(row.institution_amount_sum or 0),
            "individual_amount_sum": int(row.individual_amount_sum or 0),
            "total_amount_sum": int(row.total_amount_sum or 0),
            "avg_score": float(row.avg_score),
            "data_days": int(row.data_days),
            "latest_date": row.latest_date.isoformat() if row.latest_date else None,
            "themes": stock_themes.get(row.stock_code, []),
        })

    return {
        "stocks": stocks,
        "count": len(stocks),
        "days": days,
        "investor_type": investor_type,
        "generated_at": datetime.now().isoformat(),
    }


@router.get("/consecutive")
async def get_consecutive_buy_stocks(
    min_days: int = Query(default=3, le=20),
    investor_type: str = Query(default="all", regex="^(all|foreign|institution|individual)$"),
    limit: int = Query(default=30, le=100),
    db: AsyncSession = Depends(get_async_db),
):
    """연속 순매수 종목 조회.

    최근 N일 연속 순매수 중인 종목을 반환합니다.
    """
    # 최근 데이터부터 연속 순매수 일수 계산 (간소화된 버전)
    # CURRENT_DATE 대신 MAX(flow_date)를 기준으로 사용 (휴일/주말에도 최신 거래일 데이터 표시)
    exclude_cond = _get_exclude_condition()
    query = text(f"""
        SELECT DISTINCT stock_code, stock_name
        FROM stock_investor_flows
        WHERE flow_date >= (SELECT MAX(flow_date) - INTERVAL '30 days' FROM stock_investor_flows)
            AND {exclude_cond}
    """)

    result = await db.execute(query)
    all_stocks = result.fetchall()

    # 각 종목별 연속 순매수 일수 계산
    stock_themes = _load_stock_theme_map()
    stocks = []

    for stock in all_stocks:
        # 해당 종목의 최근 데이터 조회 (금액 필드 포함)
        flow_query = text(f"""
            SELECT flow_date, foreign_net, institution_net, individual_net,
                   foreign_net_amount, institution_net_amount, individual_net_amount
            FROM stock_investor_flows
            WHERE stock_code = :code
            ORDER BY flow_date DESC
            LIMIT 30
        """)
        flow_result = await db.execute(flow_query, {"code": stock.stock_code})
        flows = flow_result.fetchall()

        if not flows:
            continue

        # 연속 순매수 일수 계산
        consecutive = 0
        foreign_sum = 0
        institution_sum = 0
        individual_sum = 0
        foreign_amount_sum = 0
        institution_amount_sum = 0
        individual_amount_sum = 0

        for flow in flows:
            # 금액 기준으로 순매수 판단
            if investor_type == "foreign":
                is_buy = (flow.foreign_net_amount or 0) > 0
            elif investor_type == "institution":
                is_buy = (flow.institution_net_amount or 0) > 0
            elif investor_type == "individual":
                is_buy = (flow.individual_net_amount or 0) > 0
            else:
                is_buy = ((flow.foreign_net_amount or 0) + (flow.institution_net_amount or 0)) > 0

            if is_buy:
                consecutive += 1
                foreign_sum += flow.foreign_net
                institution_sum += flow.institution_net
                individual_sum += flow.individual_net
                foreign_amount_sum += flow.foreign_net_amount or 0
                institution_amount_sum += flow.institution_net_amount or 0
                individual_amount_sum += flow.individual_net_amount or 0
            else:
                break

        if consecutive >= min_days:
            stocks.append({
                "stock_code": stock.stock_code,
                "stock_name": stock.stock_name,
                "consecutive_days": consecutive,
                "foreign_sum": int(foreign_sum),
                "institution_sum": int(institution_sum),
                "individual_sum": int(individual_sum),
                "foreign_amount_sum": int(foreign_amount_sum),
                "institution_amount_sum": int(institution_amount_sum),
                "individual_amount_sum": int(individual_amount_sum),
                "total_amount_sum": int(foreign_amount_sum + institution_amount_sum),
                "themes": stock_themes.get(stock.stock_code, []),
            })

    # 연속 일수 및 금액 기준 정렬 (금액 기준으로 변경)
    stocks.sort(key=lambda x: (x["consecutive_days"], x["total_amount_sum"]), reverse=True)

    return {
        "stocks": stocks[:limit],
        "count": len(stocks[:limit]),
        "min_days": min_days,
        "investor_type": investor_type,
        "generated_at": datetime.now().isoformat(),
    }


@router.get("/spike")
async def get_spike_flow_stocks(
    recent_days: int = Query(default=2, le=5, description="최근 N일 (급증 감지 기간)"),
    base_days: int = Query(default=20, le=30, description="비교 기준 기간"),
    min_ratio: float = Query(default=3.0, description="최소 급증 배율"),
    min_amount: int = Query(default=1000000000, description="최소 급증 금액 (원, 기본 10억)"),
    limit: int = Query(default=30, le=100),
    investor_type: str = Query(default="all", regex="^(all|foreign|institution)$"),
    db: AsyncSession = Depends(get_async_db),
):
    """수급 급증 종목 조회.

    평소 대비 갑자기 수급이 급증한 종목을 반환합니다.
    급증 비율 = 최근 N일 순매수금액 / 기준 기간 일평균 순매수금액

    Args:
        recent_days: 최근 기간 (기본 2일)
        base_days: 비교 기준 기간 (기본 20일)
        min_ratio: 최소 급증 배율 (기본 3배)
        min_amount: 최소 급증 금액 (기본 10억원)
        limit: 반환할 종목 수
        investor_type: all(외인+기관), foreign(외국인), institution(기관)
    """
    # 금액 컬럼 선택
    if investor_type == "foreign":
        amount_col = "foreign_net_amount"
    elif investor_type == "institution":
        amount_col = "institution_net_amount"
    else:
        amount_col = "(foreign_net_amount + institution_net_amount)"

    exclude_cond = _get_exclude_condition()

    # 최근 N일 + 기준 기간 데이터를 한 번에 조회
    # CURRENT_DATE 대신 MAX(flow_date)를 기준으로 사용 (휴일/주말에도 최신 거래일 데이터 표시)
    query = text(f"""
        WITH max_date AS (
            SELECT MAX(flow_date) as ref_date FROM stock_investor_flows
        ),
        recent_flow AS (
            SELECT
                stock_code,
                stock_name,
                SUM(CASE WHEN flow_date >= (SELECT ref_date FROM max_date) - INTERVAL '{recent_days} days'
                    THEN {amount_col} ELSE 0 END) as recent_amount,
                SUM(CASE WHEN flow_date < (SELECT ref_date FROM max_date) - INTERVAL '{recent_days} days'
                    THEN {amount_col} ELSE 0 END) as base_amount,
                COUNT(CASE WHEN flow_date >= (SELECT ref_date FROM max_date) - INTERVAL '{recent_days} days'
                    THEN 1 END) as recent_count,
                COUNT(CASE WHEN flow_date < (SELECT ref_date FROM max_date) - INTERVAL '{recent_days} days'
                    THEN 1 END) as base_count,
                SUM(foreign_net_amount) as foreign_amount_sum,
                SUM(institution_net_amount) as institution_amount_sum,
                MAX(flow_date) as latest_date
            FROM stock_investor_flows
            WHERE flow_date >= (SELECT ref_date FROM max_date) - INTERVAL '{base_days} days'
                AND {exclude_cond}
            GROUP BY stock_code, stock_name
            HAVING COUNT(CASE WHEN flow_date >= (SELECT ref_date FROM max_date) - INTERVAL '{recent_days} days' THEN 1 END) >= 1
                AND COUNT(CASE WHEN flow_date < (SELECT ref_date FROM max_date) - INTERVAL '{recent_days} days' THEN 1 END) >= 5
        )
        SELECT
            stock_code,
            stock_name,
            recent_amount,
            base_amount,
            recent_count,
            base_count,
            foreign_amount_sum,
            institution_amount_sum,
            latest_date,
            (SELECT ref_date FROM max_date) as ref_date,
            CASE WHEN base_count > 0 THEN base_amount / base_count ELSE 0 END as base_avg,
            CASE
                WHEN base_count > 0 AND (base_amount / base_count) > 0
                THEN recent_amount / (base_amount / base_count * recent_count)
                ELSE 0
            END as spike_ratio
        FROM recent_flow
        WHERE recent_amount > :min_amount
        ORDER BY spike_ratio DESC
        LIMIT :limit_with_margin
    """)

    result = await db.execute(query, {
        "min_amount": min_amount,
        "limit_with_margin": limit * 3,  # 필터링 후 줄어들 수 있으므로 여유있게
    })
    rows = result.fetchall()

    # 기준 날짜 추출
    ref_date = None
    if rows:
        ref_date = rows[0].ref_date

    # 테마 맵 로드
    stock_themes = _load_stock_theme_map()

    stocks = []
    for row in rows:
        # 급증 비율 필터링
        spike_ratio = float(row.spike_ratio) if row.spike_ratio else 0
        if spike_ratio < min_ratio:
            continue

        # 기준 기간 일평균
        base_avg = float(row.base_avg) if row.base_avg else 0

        stocks.append({
            "stock_code": row.stock_code,
            "stock_name": row.stock_name,
            "recent_amount": int(row.recent_amount or 0),
            "base_avg": int(base_avg),
            "spike_ratio": round(spike_ratio, 1),
            "recent_days": int(row.recent_count),
            "foreign_amount_sum": int(row.foreign_amount_sum or 0),
            "institution_amount_sum": int(row.institution_amount_sum or 0),
            "latest_date": row.latest_date.isoformat() if row.latest_date else None,
            "themes": stock_themes.get(row.stock_code, []),
        })

        if len(stocks) >= limit:
            break

    return {
        "stocks": stocks,
        "count": len(stocks),
        "recent_days": recent_days,
        "base_days": base_days,
        "min_ratio": min_ratio,
        "min_amount": min_amount,
        "investor_type": investor_type,
        "ref_date": ref_date.isoformat() if ref_date else None,
        "generated_at": datetime.now().isoformat(),
    }


@router.get("/realtime-spike")
async def get_realtime_spike_stocks(
    base_days: int = Query(default=5, le=20, description="비교 기준 기간 (기본 5일)"),
    min_ratio: float = Query(default=1.5, description="최소 급증 배율 (기본 1.5배)"),
    min_amount: int = Query(default=100000000, description="최소 급증 금액 (원, 기본 1억)"),
    limit: int = Query(default=30, le=100),
    investor_type: str = Query(default="all", regex="^(all|foreign|institution)$"),
    db: AsyncSession = Depends(get_async_db),
):
    """실시간 수급 급증 종목 조회.

    KIS API를 통해 당일 수급 데이터를 실시간으로 조회하고,
    과거 평균 대비 급증 종목을 반환합니다.

    실시간 기준 완화:
    - 과거 5일 평균 대비 1.5배 이상
    - 최소 1억원 이상 순매수
    - 장중에는 시간 경과를 고려한 비율 조정

    Args:
        base_days: 비교 기준 기간 (기본 5일)
        min_ratio: 최소 급증 배율 (기본 1.5배)
        min_amount: 최소 급증 금액 (기본 1억원)
        limit: 반환할 종목 수
        investor_type: all(외인+기관), foreign(외국인), institution(기관)
    """
    now = datetime.now()
    is_market_open = (
        now.weekday() < 5  # 월-금
        and 9 <= now.hour < 16  # 09:00 ~ 15:59
    )

    # 장중 시간 경과 비율 (09:00=0, 15:30=1)
    if is_market_open:
        minutes_elapsed = (now.hour - 9) * 60 + now.minute
        total_minutes = 6.5 * 60  # 09:00 ~ 15:30 = 390분
        time_ratio = max(0.1, min(1.0, minutes_elapsed / total_minutes))
    else:
        time_ratio = 1.0

    # 1. 과거 기준 기간 평균 수급 조회 (DB에서)
    if investor_type == "foreign":
        amount_col = "foreign_net_amount"
    elif investor_type == "institution":
        amount_col = "institution_net_amount"
    else:
        amount_col = "(foreign_net_amount + institution_net_amount)"

    exclude_cond = _get_exclude_condition()

    # 수급 상위 종목 조회 (조건 완화: 최근 수급 활발한 종목)
    base_query = text(f"""
        SELECT
            stock_code,
            stock_name,
            AVG({amount_col}) as daily_avg,
            COUNT(*) as data_days
        FROM stock_investor_flows
        WHERE flow_date >= (SELECT MAX(flow_date) - INTERVAL '{base_days} days' FROM stock_investor_flows)
            AND {exclude_cond}
        GROUP BY stock_code, stock_name
        HAVING COUNT(*) >= 2
            AND ABS(AVG({amount_col})) > 50000000
        ORDER BY ABS(SUM({amount_col})) DESC
        LIMIT 30
    """)

    result = await db.execute(base_query)
    rows = result.fetchall()
    logger.info(f"실시간 급증 조회 - 기준 종목 수: {len(rows)}")

    base_data = {}
    for row in rows:
        row_dict = row._mapping
        base_data[row_dict["stock_code"]] = {
            "stock_name": row_dict["stock_name"],
            "daily_avg": float(row_dict["daily_avg"] or 0),
            "data_days": int(row_dict["data_days"]),
        }

    if not base_data:
        return {
            "stocks": [],
            "count": 0,
            "total_checked": 0,
            "base_days": base_days,
            "min_ratio": min_ratio,
            "min_amount": min_amount,
            "investor_type": investor_type,
            "market_status": "open" if is_market_open else "closed",
            "time_ratio": round(time_ratio, 2),
            "generated_at": datetime.now().isoformat(),
        }

    # 2. KIS API로 당일 실시간 수급 조회
    kis_client = get_kis_client()
    stock_codes = list(base_data.keys())

    # 배치 처리 (10개씩 병렬)
    realtime_data = {}
    batch_size = 10

    today_str = datetime.now().strftime("%Y-%m-%d")

    async def fetch_single(code: str):
        try:
            # days=5로 조회 후 당일 데이터만 필터링
            data = await kis_client.get_investor_trading(code, days=5)
            if data:
                # 당일 데이터 찾기
                for item in data:
                    if item.get("date") == today_str:
                        return code, item
                # 당일 데이터가 없으면 가장 최근 데이터 사용
                if data:
                    logger.debug(f"당일 데이터 없음 ({code}), 최근 데이터: {data[0].get('date')}")
                    return code, data[0]
        except Exception as e:
            logger.warning(f"실시간 수급 조회 실패 ({code}): {e}")
        return code, None

    for i in range(0, len(stock_codes), batch_size):
        batch_codes = stock_codes[i:i + batch_size]
        tasks = [fetch_single(code) for code in batch_codes]
        results = await asyncio.gather(*tasks)

        for code, data in results:
            if data:
                realtime_data[code] = data

        if i + batch_size < len(stock_codes):
            await asyncio.sleep(0.2)

    # 3. 급증 비율 계산 (시간 경과 고려)
    stock_themes = _load_stock_theme_map()
    spike_stocks = []

    for code, realtime in realtime_data.items():
        base = base_data.get(code)
        if not base:
            continue

        # 투자자 유형별 당일 순매수금액
        if investor_type == "foreign":
            today_amount = realtime.get("foreign_net_amount", 0)
        elif investor_type == "institution":
            today_amount = realtime.get("institution_net_amount", 0)
        else:
            today_amount = (
                realtime.get("foreign_net_amount", 0) +
                realtime.get("institution_net_amount", 0)
            )

        daily_avg = abs(base["daily_avg"])
        if daily_avg < 10000000:  # 최소 1천만원 이상 평균
            continue

        # 시간 경과를 고려한 급증 비율
        # 장 시작 직후에는 적은 금액도 급증으로 판단
        adjusted_avg = daily_avg * time_ratio
        if adjusted_avg > 0:
            spike_ratio = today_amount / adjusted_avg
        else:
            spike_ratio = 0

        # 필터링 (양수 순매수 + 기준 충족)
        if today_amount < min_amount or spike_ratio < min_ratio:
            continue

        spike_stocks.append({
            "stock_code": code,
            "stock_name": base["stock_name"],
            "today_amount": int(today_amount),
            "daily_avg": int(daily_avg),
            "adjusted_avg": int(adjusted_avg),
            "spike_ratio": round(spike_ratio, 1),
            "foreign_amount": realtime.get("foreign_net_amount", 0),
            "institution_amount": realtime.get("institution_net_amount", 0),
            "trade_date": realtime.get("date"),
            "themes": stock_themes.get(code, []),
        })

    # 급증 비율 순으로 정렬
    spike_stocks.sort(key=lambda x: x["spike_ratio"], reverse=True)

    return {
        "stocks": spike_stocks[:limit],
        "count": len(spike_stocks[:limit]),
        "total_checked": len(realtime_data),
        "base_days": base_days,
        "min_ratio": min_ratio,
        "min_amount": min_amount,
        "investor_type": investor_type,
        "market_status": "open" if is_market_open else "closed",
        "time_ratio": round(time_ratio, 2),
        "generated_at": datetime.now().isoformat(),
    }
