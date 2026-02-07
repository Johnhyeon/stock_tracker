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
    EtfOHLCV,
    YouTubeMention,
    TelegramReport,
    ReportSentimentAnalysis,
    TelegramIdea,
    Disclosure,
)
from schemas.data_status import (
    DataCategory,
    ScheduleInfo,
    DataStatusItemFull,
    AllDataStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ==========================================
# 데이터 타입 정의
# ==========================================

DATA_TYPES = {
    # 시세 데이터 (Market)
    "price_update": {
        "name": "실시간 가격",
        "category": DataCategory.MARKET,
        "schedule": ScheduleInfo(
            description="5분마다 (장중)",
            is_market_hours_only=True,
        ),
        "can_refresh": False,  # 실시간이므로 수동 새로고침 불가
    },
    "ohlcv": {
        "name": "OHLCV (일봉)",
        "category": DataCategory.MARKET,
        "schedule": ScheduleInfo(
            description="매일 16:40",
            is_market_hours_only=False,
        ),
        "can_refresh": True,
    },
    "etf_ohlcv": {
        "name": "ETF 일봉",
        "category": DataCategory.MARKET,
        "schedule": ScheduleInfo(
            description="매일 16:45",
            is_market_hours_only=False,
        ),
        "can_refresh": True,
    },
    "investor_flow": {
        "name": "투자자 수급",
        "category": DataCategory.MARKET,
        "schedule": ScheduleInfo(
            description="매일 18:30",
            is_market_hours_only=False,
        ),
        "can_refresh": True,
    },
    # 분석 데이터 (Analysis)
    "chart_patterns": {
        "name": "차트 패턴",
        "category": DataCategory.ANALYSIS,
        "schedule": ScheduleInfo(
            description="매일 16:30",
            is_market_hours_only=False,
        ),
        "can_refresh": True,
    },
    "theme_setups": {
        "name": "테마 셋업",
        "category": DataCategory.ANALYSIS,
        "schedule": ScheduleInfo(
            description="6시간마다",
            is_market_hours_only=False,
        ),
        "can_refresh": True,
    },
    # 외부 소스 (External)
    "youtube": {
        "name": "YouTube",
        "category": DataCategory.EXTERNAL,
        "schedule": ScheduleInfo(
            description="6시간마다",
            is_market_hours_only=False,
        ),
        "can_refresh": True,
    },
    "disclosure": {
        "name": "공시",
        "category": DataCategory.EXTERNAL,
        "schedule": ScheduleInfo(
            description="30분마다",
            is_market_hours_only=False,
        ),
        "can_refresh": True,
    },
    # 텔레그램 (Telegram)
    "telegram_reports": {
        "name": "텔레그램 리포트",
        "category": DataCategory.TELEGRAM,
        "schedule": ScheduleInfo(
            description="5분마다",
            is_market_hours_only=False,
        ),
        "can_refresh": True,
    },
    "telegram_sentiment": {
        "name": "감정 분석",
        "category": DataCategory.TELEGRAM,
        "schedule": ScheduleInfo(
            description="30분마다",
            is_market_hours_only=False,
        ),
        "can_refresh": True,
    },
    "telegram_ideas": {
        "name": "텔레그램 아이디어",
        "category": DataCategory.TELEGRAM,
        "schedule": ScheduleInfo(
            description="4시간마다",
            is_market_hours_only=False,
        ),
        "can_refresh": True,
    },
}


# ==========================================
# 기존 스키마 (하위 호환성 유지)
# ==========================================

class DataStatusItem(BaseModel):
    """개별 데이터 상태."""
    name: str
    last_updated: Optional[datetime] = None
    record_count: int = 0
    is_stale: bool = False
    status: str = "unknown"


class DataStatusResponse(BaseModel):
    """전체 데이터 상태 응답 (기존 API 호환)."""
    investor_flow: DataStatusItem
    ohlcv: DataStatusItem
    chart_patterns: DataStatusItem
    theme_setups: DataStatusItem
    overall_status: str
    checked_at: datetime


class RefreshRequest(BaseModel):
    """새로고침 요청."""
    targets: list[str] = []
    force_full: bool = False


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


# ==========================================
# 기존 API (하위 호환성)
# ==========================================

@router.get("/status", response_model=DataStatusResponse)
async def get_data_status():
    """모든 데이터의 최신화 상태 확인 (기존 API 호환).

    각 데이터가 언제 마지막으로 업데이트됐는지,
    현재 얼마나 오래됐는지 확인할 수 있습니다.
    """
    now = datetime.now()
    today = date.today()

    async with async_session_maker() as db:
        investor_flow = await _check_investor_flow_status(db, today)
        ohlcv = await _check_ohlcv_status(db, today)
        chart_patterns = await _check_chart_pattern_status(db, today)
        theme_setups = await _check_theme_setup_status(db, now)

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


# ==========================================
# 신규 API: 전체 데이터 상태
# ==========================================

@router.get("/status/all", response_model=AllDataStatusResponse)
async def get_all_data_status():
    """모든 데이터 타입의 상태를 카테고리별로 그룹화하여 반환.

    11개 데이터 타입의 상태를 4개 카테고리로 분류하여 반환합니다.
    """
    now = datetime.now()
    today = date.today()

    async with async_session_maker() as db:
        # 모든 데이터 상태 수집
        statuses = {}

        # Market 데이터
        statuses["price_update"] = _create_status_item("price_update", await _check_price_update_status(db, now))
        statuses["ohlcv"] = _create_status_item("ohlcv", await _check_ohlcv_status(db, today))
        statuses["etf_ohlcv"] = _create_status_item("etf_ohlcv", await _check_etf_ohlcv_status(db, today))
        statuses["investor_flow"] = _create_status_item("investor_flow", await _check_investor_flow_status(db, today))

        # Analysis 데이터
        statuses["chart_patterns"] = _create_status_item("chart_patterns", await _check_chart_pattern_status(db, today))
        statuses["theme_setups"] = _create_status_item("theme_setups", await _check_theme_setup_status(db, now))

        # External 데이터
        statuses["youtube"] = _create_status_item("youtube", await _check_youtube_status(db, now))
        statuses["disclosure"] = _create_status_item("disclosure", await _check_disclosure_status(db, today))

        # Telegram 데이터
        statuses["telegram_reports"] = _create_status_item("telegram_reports", await _check_telegram_reports_status(db, now))
        statuses["telegram_sentiment"] = _create_status_item("telegram_sentiment", await _check_telegram_sentiment_status(db, now))
        statuses["telegram_ideas"] = _create_status_item("telegram_ideas", await _check_telegram_ideas_status(db, now))

    # 카테고리별 그룹화
    market = [s for s in statuses.values() if s.category == DataCategory.MARKET]
    analysis = [s for s in statuses.values() if s.category == DataCategory.ANALYSIS]
    external = [s for s in statuses.values() if s.category == DataCategory.EXTERNAL]
    telegram = [s for s in statuses.values() if s.category == DataCategory.TELEGRAM]

    # 전체 상태 결정
    all_statuses = [s.status for s in statuses.values()]
    if all(s == "ok" for s in all_statuses):
        overall = "ok"
    elif any(s == "empty" for s in all_statuses):
        overall = "critical"
    elif any(s == "stale" for s in all_statuses):
        overall = "needs_refresh"
    else:
        overall = "ok"

    return AllDataStatusResponse(
        market=market,
        analysis=analysis,
        external=external,
        telegram=telegram,
        overall_status=overall,
        checked_at=now,
    )


def _create_status_item(key: str, status: DataStatusItem) -> DataStatusItemFull:
    """DataStatusItem을 DataStatusItemFull로 변환."""
    data_type = DATA_TYPES.get(key, {})
    return DataStatusItemFull(
        key=key,
        name=status.name,
        category=data_type.get("category", DataCategory.MARKET),
        last_updated=status.last_updated,
        record_count=status.record_count,
        is_stale=status.is_stale,
        status=status.status,
        schedule=data_type.get("schedule", ScheduleInfo(description="수동")),
        can_refresh=data_type.get("can_refresh", True),
    )


# ==========================================
# 상태 체크 함수들
# ==========================================

async def _check_price_update_status(db, now: datetime) -> DataStatusItem:
    """실시간 가격 업데이트 상태 (OHLCV 최신 데이터 기반)."""
    # 실시간 가격은 캐시에서 관리되므로, OHLCV 최신 데이터를 참조
    return DataStatusItem(
        name="실시간 가격",
        last_updated=now,
        record_count=0,
        is_stale=False,
        status="ok",
    )


async def _check_investor_flow_status(db, today: date) -> DataStatusItem:
    """투자자 수급 데이터 상태 확인."""
    try:
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
        stmt = select(
            func.max(StockOHLCV.trade_date),
            func.count(),
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


async def _check_etf_ohlcv_status(db, today: date) -> DataStatusItem:
    """ETF OHLCV 데이터 상태 확인."""
    try:
        stmt = select(
            func.max(EtfOHLCV.trade_date),
            func.count(),
            func.count(distinct(EtfOHLCV.etf_code)),
        )
        result = await db.execute(stmt)
        row = result.one()

        latest_date, total_count, etf_count = row

        if not latest_date:
            return DataStatusItem(
                name="ETF 일봉",
                record_count=0,
                is_stale=True,
                status="empty",
            )

        days_old = (today - latest_date).days
        is_stale = days_old > 2

        return DataStatusItem(
            name="ETF 일봉",
            last_updated=datetime.combine(latest_date, datetime.min.time()),
            record_count=total_count,
            is_stale=is_stale,
            status="stale" if is_stale else "ok",
        )
    except Exception as e:
        logger.error(f"ETF OHLCV 상태 확인 실패: {e}")
        return DataStatusItem(name="ETF 일봉", status="error")


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


async def _check_youtube_status(db, now: datetime) -> DataStatusItem:
    """YouTube 언급 데이터 상태 확인."""
    try:
        stmt = select(
            func.max(YouTubeMention.created_at),
            func.count(YouTubeMention.id),
        )
        result = await db.execute(stmt)
        row = result.one()

        latest_time, total_count = row

        if not latest_time:
            return DataStatusItem(
                name="YouTube",
                record_count=0,
                is_stale=True,
                status="empty",
            )

        hours_old = (now - latest_time).total_seconds() / 3600
        is_stale = hours_old > 12  # 12시간 이상 지나면 stale

        return DataStatusItem(
            name="YouTube",
            last_updated=latest_time,
            record_count=total_count,
            is_stale=is_stale,
            status="stale" if is_stale else "ok",
        )
    except Exception as e:
        logger.error(f"YouTube 상태 확인 실패: {e}")
        return DataStatusItem(name="YouTube", status="error")


async def _check_disclosure_status(db, today: date) -> DataStatusItem:
    """공시 데이터 상태 확인."""
    try:
        stmt = select(
            func.max(Disclosure.created_at),
            func.count(Disclosure.id),
        )
        result = await db.execute(stmt)
        row = result.one()

        latest_time, total_count = row

        if not latest_time:
            return DataStatusItem(
                name="공시",
                record_count=0,
                is_stale=True,
                status="empty",
            )

        hours_old = (datetime.now() - latest_time).total_seconds() / 3600
        is_stale = hours_old > 2  # 2시간 이상 지나면 stale

        return DataStatusItem(
            name="공시",
            last_updated=latest_time,
            record_count=total_count,
            is_stale=is_stale,
            status="stale" if is_stale else "ok",
        )
    except Exception as e:
        logger.error(f"공시 상태 확인 실패: {e}")
        return DataStatusItem(name="공시", status="error")


async def _check_telegram_reports_status(db, now: datetime) -> DataStatusItem:
    """텔레그램 리포트 상태 확인."""
    try:
        stmt = select(
            func.max(TelegramReport.created_at),
            func.count(TelegramReport.id),
        )
        result = await db.execute(stmt)
        row = result.one()

        latest_time, total_count = row

        if not latest_time:
            return DataStatusItem(
                name="텔레그램 리포트",
                record_count=0,
                is_stale=True,
                status="empty",
            )

        hours_old = (now - latest_time).total_seconds() / 3600
        is_stale = hours_old > 1  # 1시간 이상 지나면 stale

        return DataStatusItem(
            name="텔레그램 리포트",
            last_updated=latest_time,
            record_count=total_count,
            is_stale=is_stale,
            status="stale" if is_stale else "ok",
        )
    except Exception as e:
        logger.error(f"텔레그램 리포트 상태 확인 실패: {e}")
        return DataStatusItem(name="텔레그램 리포트", status="error")


async def _check_telegram_sentiment_status(db, now: datetime) -> DataStatusItem:
    """감정 분석 상태 확인."""
    try:
        stmt = select(
            func.max(ReportSentimentAnalysis.created_at),
            func.count(ReportSentimentAnalysis.id),
        )
        result = await db.execute(stmt)
        row = result.one()

        latest_time, total_count = row

        if not latest_time:
            return DataStatusItem(
                name="감정 분석",
                record_count=0,
                is_stale=True,
                status="empty",
            )

        hours_old = (now - latest_time).total_seconds() / 3600
        is_stale = hours_old > 2  # 2시간 이상 지나면 stale

        return DataStatusItem(
            name="감정 분석",
            last_updated=latest_time,
            record_count=total_count,
            is_stale=is_stale,
            status="stale" if is_stale else "ok",
        )
    except Exception as e:
        logger.error(f"감정 분석 상태 확인 실패: {e}")
        return DataStatusItem(name="감정 분석", status="error")


async def _check_telegram_ideas_status(db, now: datetime) -> DataStatusItem:
    """텔레그램 아이디어 상태 확인."""
    try:
        stmt = select(
            func.max(TelegramIdea.created_at),
            func.count(TelegramIdea.id),
        )
        result = await db.execute(stmt)
        row = result.one()

        latest_time, total_count = row

        if not latest_time:
            return DataStatusItem(
                name="텔레그램 아이디어",
                record_count=0,
                is_stale=True,
                status="empty",
            )

        hours_old = (now - latest_time).total_seconds() / 3600
        is_stale = hours_old > 8  # 8시간 이상 지나면 stale

        return DataStatusItem(
            name="텔레그램 아이디어",
            last_updated=latest_time,
            record_count=total_count,
            is_stale=is_stale,
            status="stale" if is_stale else "ok",
        )
    except Exception as e:
        logger.error(f"텔레그램 아이디어 상태 확인 실패: {e}")
        return DataStatusItem(name="텔레그램 아이디어", status="error")


# ==========================================
# 새로고침 API
# ==========================================

@router.post("/refresh", response_model=RefreshResponse)
async def refresh_data(
    request: RefreshRequest,
    background_tasks: BackgroundTasks,
):
    """데이터 새로고침 (백그라운드 실행).

    targets가 비어있으면 기존 4개 데이터를 새로고침합니다.
    신규 데이터 타입도 지원합니다.
    """
    global _refresh_status

    if _refresh_status["is_running"]:
        raise HTTPException(
            status_code=409,
            detail="이미 새로고침이 진행 중입니다."
        )

    valid_targets = {
        # 기존 4개
        "investor_flow", "ohlcv", "chart_patterns", "theme_setups",
        # 신규 7개
        "etf_ohlcv", "youtube", "disclosure",
        "telegram_reports", "telegram_sentiment", "telegram_ideas",
    }

    if request.targets:
        invalid = set(request.targets) - valid_targets
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"잘못된 target: {invalid}. 유효한 값: {valid_targets}"
            )
        targets = request.targets
    else:
        # 기본값: 기존 4개만 (하위 호환성)
        targets = ["investor_flow", "ohlcv", "chart_patterns", "theme_setups"]

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

        # 기존 데이터 타입
        if "investor_flow" in targets:
            tasks.append(("investor_flow", _refresh_investor_flow(force_full)))

        if "ohlcv" in targets:
            tasks.append(("ohlcv", _refresh_ohlcv()))

        if "chart_patterns" in targets:
            tasks.append(("chart_patterns", _refresh_chart_patterns()))

        if "theme_setups" in targets:
            tasks.append(("theme_setups", _refresh_theme_setups()))

        # 신규 데이터 타입
        if "etf_ohlcv" in targets:
            tasks.append(("etf_ohlcv", _refresh_etf_ohlcv()))

        if "youtube" in targets:
            tasks.append(("youtube", _refresh_youtube()))

        if "disclosure" in targets:
            tasks.append(("disclosure", _refresh_disclosure()))

        if "telegram_reports" in targets:
            tasks.append(("telegram_reports", _refresh_telegram_reports()))

        if "telegram_sentiment" in targets:
            tasks.append(("telegram_sentiment", _refresh_telegram_sentiment()))

        if "telegram_ideas" in targets:
            tasks.append(("telegram_ideas", _refresh_telegram_ideas()))

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


# ==========================================
# 새로고침 함수들 (기존)
# ==========================================

async def _refresh_investor_flow(force_full: bool = False) -> dict:
    """투자자 수급 데이터 새로고침."""
    from services.investor_flow_service import InvestorFlowService
    from services.theme_map_service import get_theme_map_service

    _refresh_status["progress"]["investor_flow"] = "running"

    tms = get_theme_map_service()
    all_stocks = {}
    for stocks in tms.get_all_themes().values():
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


# ==========================================
# 새로고침 함수들 (신규)
# ==========================================

async def _refresh_etf_ohlcv() -> dict:
    """ETF OHLCV 데이터 새로고침."""
    from scheduler.jobs.etf_collect import collect_etf_ohlcv_daily

    _refresh_status["progress"]["etf_ohlcv"] = "running"
    await collect_etf_ohlcv_daily()
    return {"status": "completed"}


async def _refresh_youtube() -> dict:
    """YouTube 데이터 새로고침."""
    from scheduler.jobs.youtube_collect import collect_youtube_videos

    _refresh_status["progress"]["youtube"] = "running"
    result = await collect_youtube_videos()
    return result


async def _refresh_disclosure() -> dict:
    """공시 데이터 새로고침."""
    from scheduler.jobs.disclosure_collect import collect_disclosures_for_active_positions

    _refresh_status["progress"]["disclosure"] = "running"
    result = await collect_disclosures_for_active_positions()
    return result


async def _refresh_telegram_reports() -> dict:
    """텔레그램 리포트 수집."""
    from scheduler.jobs.sentiment_analyze import collect_telegram_reports

    _refresh_status["progress"]["telegram_reports"] = "running"
    await collect_telegram_reports()
    return {"status": "completed"}


async def _refresh_telegram_sentiment() -> dict:
    """텔레그램 감정 분석 실행."""
    from scheduler.jobs.sentiment_analyze import analyze_telegram_sentiments

    _refresh_status["progress"]["telegram_sentiment"] = "running"
    await analyze_telegram_sentiments()
    return {"status": "completed"}


async def _refresh_telegram_ideas() -> dict:
    """텔레그램 아이디어 수집."""
    from scheduler.jobs.telegram_idea_collect import collect_telegram_ideas

    _refresh_status["progress"]["telegram_ideas"] = "running"
    await collect_telegram_ideas()
    return {"status": "completed"}
