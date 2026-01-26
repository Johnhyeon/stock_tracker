"""데이터 상태 및 일괄 수집 API.

각 데이터의 최신화 상태 확인과 수동 새로고침 기능 제공.
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, distinct

from core.database import async_session_maker
from models import (
    StockInvestorFlow,
    StockOHLCV,
    ThemeChartPattern,
    ThemeSetup,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class DataStatusItem(BaseModel):
    """개별 데이터 상태."""
    name: str
    last_updated: Optional[datetime] = None
    record_count: int = 0
    is_stale: bool = False  # 오래된 데이터인지
    status: str = "unknown"  # ok, stale, empty, error


class DataStatusResponse(BaseModel):
    """전체 데이터 상태 응답."""
    investor_flow: DataStatusItem
    ohlcv: DataStatusItem
    chart_patterns: DataStatusItem
    theme_setups: DataStatusItem
    overall_status: str  # ok, needs_refresh, critical
    checked_at: datetime


class RefreshRequest(BaseModel):
    """새로고침 요청."""
    targets: list[str] = []  # 빈 리스트면 전체 새로고침
    force_full: bool = False  # 전체 기간 다시 수집


class RefreshResponse(BaseModel):
    """새로고침 응답."""
    started: bool
    message: str
    targets: list[str]


# 진행 상태 저장 (간단한 인메모리)
_refresh_status = {
    "is_running": False,
    "started_at": None,
    "completed_at": None,
    "progress": {},
    "errors": [],
}


@router.get("/status", response_model=DataStatusResponse)
async def get_data_status():
    """모든 데이터의 최신화 상태 확인.

    각 데이터가 언제 마지막으로 업데이트됐는지,
    현재 얼마나 오래됐는지 확인할 수 있습니다.
    """
    now = datetime.now()
    today = date.today()

    async with async_session_maker() as db:
        # 1. 투자자 수급 데이터
        investor_flow = await _check_investor_flow_status(db, today)

        # 2. OHLCV 데이터
        ohlcv = await _check_ohlcv_status(db, today)

        # 3. 차트 패턴 데이터
        chart_patterns = await _check_chart_pattern_status(db, today)

        # 4. 테마 셋업 점수
        theme_setups = await _check_theme_setup_status(db, now)

    # 전체 상태 결정
    statuses = [investor_flow.status, ohlcv.status,
                chart_patterns.status, theme_setups.status]

    if all(s == "ok" for s in statuses):
        overall = "ok"
    elif any(s == "empty" for s in statuses):
        overall = "critical"
    elif any(s == "stale" for s in statuses):
        overall = "needs_refresh"
    else:
        overall = "ok"

    return DataStatusResponse(
        investor_flow=investor_flow,
        ohlcv=ohlcv,
        chart_patterns=chart_patterns,
        theme_setups=theme_setups,
        overall_status=overall,
        checked_at=now,
    )


async def _check_investor_flow_status(db, today: date) -> DataStatusItem:
    """투자자 수급 데이터 상태 확인."""
    try:
        # 최신 날짜와 총 레코드 수
        stmt = select(
            func.max(StockInvestorFlow.flow_date),
            func.count(StockInvestorFlow.id),
            func.count(distinct(StockInvestorFlow.stock_code)),
        )
        result = await db.execute(stmt)
        row = result.one()

        latest_date, total_count, stock_count = row

        if not latest_date:
            return DataStatusItem(
                name="투자자 수급",
                record_count=0,
                is_stale=True,
                status="empty",
            )

        # 영업일 기준 2일 이상 지나면 stale
        days_old = (today - latest_date).days
        is_stale = days_old > 2

        return DataStatusItem(
            name="투자자 수급",
            last_updated=datetime.combine(latest_date, datetime.min.time()),
            record_count=total_count,
            is_stale=is_stale,
            status="stale" if is_stale else "ok",
        )
    except Exception as e:
        logger.error(f"투자자 수급 상태 확인 실패: {e}")
        return DataStatusItem(name="투자자 수급", status="error")


async def _check_ohlcv_status(db, today: date) -> DataStatusItem:
    """OHLCV 데이터 상태 확인."""
    try:
        # StockOHLCV는 복합 기본키 사용 (id 없음)
        stmt = select(
            func.max(StockOHLCV.trade_date),
            func.count(),  # 전체 레코드 수
            func.count(distinct(StockOHLCV.stock_code)),
        )
        result = await db.execute(stmt)
        row = result.one()

        latest_date, total_count, stock_count = row

        if not latest_date:
            return DataStatusItem(
                name="OHLCV (일봉)",
                record_count=0,
                is_stale=True,
                status="empty",
            )

        days_old = (today - latest_date).days
        is_stale = days_old > 2

        return DataStatusItem(
            name="OHLCV (일봉)",
            last_updated=datetime.combine(latest_date, datetime.min.time()),
            record_count=total_count,
            is_stale=is_stale,
            status="stale" if is_stale else "ok",
        )
    except Exception as e:
        logger.error(f"OHLCV 상태 확인 실패: {e}")
        return DataStatusItem(name="OHLCV (일봉)", status="error")


async def _check_chart_pattern_status(db, today: date) -> DataStatusItem:
    """차트 패턴 분석 데이터 상태 확인."""
    try:
        stmt = select(
            func.max(ThemeChartPattern.analysis_date),
            func.count(ThemeChartPattern.id),
        )
        result = await db.execute(stmt)
        row = result.one()

        latest_date, total_count = row

        if not latest_date:
            return DataStatusItem(
                name="차트 패턴",
                record_count=0,
                is_stale=True,
                status="empty",
            )

        # 1일 이상 지나면 stale
        days_old = (today - latest_date).days
        is_stale = days_old > 1

        return DataStatusItem(
            name="차트 패턴",
            last_updated=datetime.combine(latest_date, datetime.min.time()),
            record_count=total_count,
            is_stale=is_stale,
            status="stale" if is_stale else "ok",
        )
    except Exception as e:
        logger.error(f"차트 패턴 상태 확인 실패: {e}")
        return DataStatusItem(name="차트 패턴", status="error")


async def _check_theme_setup_status(db, now: datetime) -> DataStatusItem:
    """테마 셋업 점수 상태 확인."""
    try:
        stmt = select(
            func.max(ThemeSetup.updated_at),
            func.count(ThemeSetup.id),
        )
        result = await db.execute(stmt)
        row = result.one()

        latest_time, total_count = row

        if not latest_time:
            return DataStatusItem(
                name="테마 셋업",
                record_count=0,
                is_stale=True,
                status="empty",
            )

        # 12시간 이상 지나면 stale
        hours_old = (now - latest_time).total_seconds() / 3600
        is_stale = hours_old > 12

        return DataStatusItem(
            name="테마 셋업",
            last_updated=latest_time,
            record_count=total_count,
            is_stale=is_stale,
            status="stale" if is_stale else "ok",
        )
    except Exception as e:
        logger.error(f"테마 셋업 상태 확인 실패: {e}")
        return DataStatusItem(name="테마 셋업", status="error")


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_data(
    request: RefreshRequest,
    background_tasks: BackgroundTasks,
):
    """데이터 새로고침 (백그라운드 실행).

    targets가 비어있으면 모든 데이터를 새로고침합니다.
    유효한 targets: investor_flow, ohlcv, chart_patterns, theme_setups
    """
    global _refresh_status

    if _refresh_status["is_running"]:
        raise HTTPException(
            status_code=409,
            detail="이미 새로고침이 진행 중입니다."
        )

    valid_targets = {"investor_flow", "ohlcv", "chart_patterns", "theme_setups"}

    if request.targets:
        invalid = set(request.targets) - valid_targets
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"잘못된 target: {invalid}. 유효한 값: {valid_targets}"
            )
        targets = request.targets
    else:
        targets = list(valid_targets)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _run_refresh,
        targets=targets,
        force_full=request.force_full,
    )

    _refresh_status = {
        "is_running": True,
        "started_at": datetime.now(),
        "completed_at": None,
        "progress": {t: "pending" for t in targets},
        "errors": [],
    }

    return RefreshResponse(
        started=True,
        message=f"{len(targets)}개 데이터 새로고침을 시작합니다.",
        targets=targets,
    )


@router.get("/refresh/status")
async def get_refresh_status():
    """새로고침 진행 상태 확인."""
    return _refresh_status


async def _run_refresh(targets: list[str], force_full: bool = False):
    """백그라운드에서 데이터 새로고침 실행."""
    global _refresh_status

    try:
        tasks = []

        # 병렬 실행 가능한 작업들을 그룹화
        if "investor_flow" in targets:
            tasks.append(("investor_flow", _refresh_investor_flow(force_full)))

        if "ohlcv" in targets:
            tasks.append(("ohlcv", _refresh_ohlcv()))

        if "chart_patterns" in targets:
            tasks.append(("chart_patterns", _refresh_chart_patterns()))

        if "theme_setups" in targets:
            tasks.append(("theme_setups", _refresh_theme_setups()))

        # 병렬 실행
        results = await asyncio.gather(
            *[task for _, task in tasks],
            return_exceptions=True
        )

        # 결과 처리
        for (name, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                _refresh_status["progress"][name] = "error"
                _refresh_status["errors"].append(f"{name}: {str(result)}")
                logger.error(f"{name} 새로고침 실패: {result}")
            else:
                _refresh_status["progress"][name] = "completed"
                logger.info(f"{name} 새로고침 완료: {result}")

    except Exception as e:
        logger.error(f"새로고침 실패: {e}")
        _refresh_status["errors"].append(str(e))

    finally:
        _refresh_status["is_running"] = False
        _refresh_status["completed_at"] = datetime.now()


async def _refresh_investor_flow(force_full: bool = False) -> dict:
    """투자자 수급 데이터 새로고침."""
    import json
    from pathlib import Path
    from services.investor_flow_service import InvestorFlowService

    _refresh_status["progress"]["investor_flow"] = "running"

    theme_map_path = Path(__file__).parent.parent.parent / "data" / "theme_map.json"

    with open(theme_map_path, "r", encoding="utf-8") as f:
        theme_map = json.load(f)

    all_stocks = {}
    for stocks in theme_map.values():
        for stock in stocks:
            code = stock.get("code")
            name = stock.get("name", "")
            if code:
                all_stocks[code] = name

    stock_codes = list(all_stocks.keys())

    async with async_session_maker() as db:
        service = InvestorFlowService(db)
        result = await service.collect_investor_flow(
            stock_codes,
            all_stocks,
            days=30 if force_full else 5,
            force_full=force_full,
        )

    return result


async def _refresh_ohlcv() -> dict:
    """OHLCV 데이터 새로고침."""
    from scheduler.jobs.ohlcv_collect import collect_ohlcv_daily

    _refresh_status["progress"]["ohlcv"] = "running"
    await collect_ohlcv_daily()
    return {"status": "completed"}


async def _refresh_chart_patterns() -> dict:
    """차트 패턴 분석 새로고침."""
    from scheduler.jobs.chart_pattern_analyze import analyze_chart_patterns

    _refresh_status["progress"]["chart_patterns"] = "running"
    result = await analyze_chart_patterns()
    return result


async def _refresh_theme_setups() -> dict:
    """테마 셋업 점수 새로고침."""
    from scheduler.jobs.theme_setup_calculate import calculate_theme_setups

    _refresh_status["progress"]["theme_setups"] = "running"
    result = await calculate_theme_setups()
    return result
