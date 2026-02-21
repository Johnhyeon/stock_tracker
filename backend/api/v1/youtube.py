"""YouTube API 엔드포인트."""
import asyncio
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from sqlalchemy.orm import Session

from core.database import get_db
from core.timezone import now_kst
from services.youtube_service import YouTubeService
from schemas.youtube import (
    YouTubeMentionResponse,
    YouTubeMentionListResponse,
    TrendingTickerResponse,
    TickerMentionHistoryItem,
    YouTubeCollectRequest,
    YouTubeCollectResponse,
    HotCollectRequest,
    HotCollectResponse,
    RisingTickerResponse,
    MediaTimelineResponse,
    MentionBacktestResponse,
    OverheatResponse,
)

router = APIRouter()

# YouTube 수집 상태 (인메모리)
_youtube_collect_status = {
    "is_running": False,
    "started_at": None,
    "completed_at": None,
    "result": None,
    "error": None,
    "type": None,  # "ideas" or "hot"
}


@router.get("", response_model=YouTubeMentionListResponse)
def list_youtube_mentions(
    stock_code: Optional[str] = Query(default=None, description="종목코드 필터"),
    channel_id: Optional[str] = Query(default=None, description="채널 ID 필터"),
    days_back: int = Query(default=7, ge=1, le=90, description="며칠 전까지"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db),
):
    """YouTube 언급 목록 조회."""
    service = YouTubeService(db)
    mentions = service.get_mentions(
        stock_code=stock_code,
        channel_id=channel_id,
        days_back=days_back,
        skip=skip,
        limit=limit,
    )

    return YouTubeMentionListResponse(
        items=[YouTubeMentionResponse.model_validate(m) for m in mentions],
        total=len(mentions),
        skip=skip,
        limit=limit,
    )


@router.get("/trending", response_model=list[TrendingTickerResponse])
def get_trending_tickers(
    days_back: int = Query(default=7, ge=1, le=30, description="며칠간의 데이터"),
    limit: int = Query(default=20, le=50),
    db: Session = Depends(get_db),
):
    """트렌딩 종목 조회 (YouTube 언급 횟수 기준)."""
    service = YouTubeService(db)
    trending = service.get_trending_tickers(
        days_back=days_back,
        limit=limit,
    )
    return [TrendingTickerResponse(**t) for t in trending]


@router.get("/history/{stock_code}", response_model=list[TickerMentionHistoryItem])
def get_ticker_mention_history(
    stock_code: str,
    days_back: int = Query(default=30, ge=1, le=90, description="며칠간의 데이터"),
    db: Session = Depends(get_db),
):
    """종목별 일간 YouTube 언급 추이."""
    service = YouTubeService(db)
    history = service.get_ticker_mention_history(
        stock_code=stock_code,
        days_back=days_back,
    )
    return [TickerMentionHistoryItem(**h) for h in history]


@router.get("/rising", response_model=list[RisingTickerResponse])
def get_rising_tickers(
    days_back: int = Query(default=7, ge=2, le=30, description="분석 기간"),
    limit: int = Query(default=20, le=50),
    include_price: bool = Query(default=True, description="KIS API로 주가/거래량 정보 포함"),
    db: Session = Depends(get_db),
):
    """급상승 종목 조회 (언급 증가율 + 주가/거래량 가중치).

    최근 기간 vs 이전 기간 언급 횟수를 비교하고,
    KIS API로 주가/거래량 정보를 가져와 가중치 점수를 계산합니다.

    가중치 구성:
    - 언급 증가율 (40%): YouTube 언급 증가율
    - 주가 상승률 (30%): 당일 등락률
    - 거래량 (20%): 거래량 (로그 스케일)
    - 신규 등장 보너스 (10%): 새로 발견된 종목
    """
    service = YouTubeService(db)
    rising = service.get_rising_tickers(
        days_back=days_back,
        limit=limit,
        include_price=include_price,
    )
    return [RisingTickerResponse(**r) for r in rising]


@router.get("/stock-timeline/{stock_code}", response_model=MediaTimelineResponse)
def get_stock_timeline(
    stock_code: str,
    days_back: int = Query(default=90, ge=7, le=365, description="분석 기간 (일)"),
    db: Session = Depends(get_db),
):
    """종목별 미디어 타임라인 (가격 + 언급 결합)."""
    service = YouTubeService(db)
    result = service.get_stock_timeline(stock_code=stock_code, days_back=days_back)
    return MediaTimelineResponse(**result)


@router.get("/mention-backtest", response_model=MentionBacktestResponse)
def get_mention_backtest(
    days_back: int = Query(default=90, ge=7, le=365, description="분석 기간"),
    min_mentions: int = Query(default=3, ge=1, le=20, description="최소 언급 횟수"),
    holding_days: str = Query(default="3,7,14", description="보유 기간 (콤마 구분)"),
    db: Session = Depends(get_db),
):
    """유튜브 언급 후 수익률 백테스트."""
    service = YouTubeService(db)
    result = service.get_mention_backtest(
        days_back=days_back,
        min_mentions=min_mentions,
        holding_days_str=holding_days,
    )
    return MentionBacktestResponse(**result)


@router.get("/overheat", response_model=OverheatResponse)
def get_overheat_stocks(
    recent_days: int = Query(default=3, ge=1, le=14, description="최근 기간 (일)"),
    baseline_days: int = Query(default=30, ge=14, le=90, description="기준 기간 (일)"),
    db: Session = Depends(get_db),
):
    """유튜브 과열 경고."""
    service = YouTubeService(db)
    result = service.get_overheat_stocks(
        recent_days=recent_days,
        baseline_days=baseline_days,
    )
    return OverheatResponse(**result)


@router.get("/{mention_id}", response_model=YouTubeMentionResponse)
def get_youtube_mention(
    mention_id: UUID,
    db: Session = Depends(get_db),
):
    """YouTube 언급 상세 조회."""
    service = YouTubeService(db)
    mention = service.get_mention(mention_id)
    if not mention:
        raise HTTPException(status_code=404, detail="YouTube mention not found")
    return YouTubeMentionResponse.model_validate(mention)


async def _run_collect_videos(hours_back: int):
    """백그라운드에서 YouTube 영상 수집 실행 (비동기 DB)."""
    global _youtube_collect_status
    from core.database import async_session_maker

    async with async_session_maker() as db:
        try:
            service = YouTubeService(db)
            result = await service.collect_videos(hours_back=hours_back)
            _youtube_collect_status["result"] = result
        except Exception as e:
            _youtube_collect_status["error"] = str(e)
        finally:
            _youtube_collect_status["is_running"] = False
            _youtube_collect_status["completed_at"] = now_kst().isoformat()


async def _run_collect_hot_videos(hours_back: int, mode: str):
    """백그라운드에서 핫 영상 수집 실행 (비동기 DB)."""
    global _youtube_collect_status
    from core.database import async_session_maker

    async with async_session_maker() as db:
        try:
            service = YouTubeService(db)
            result = await service.collect_hot_videos(hours_back=hours_back, mode=mode)
            _youtube_collect_status["result"] = result
        except Exception as e:
            _youtube_collect_status["error"] = str(e)
        finally:
            _youtube_collect_status["is_running"] = False
            _youtube_collect_status["completed_at"] = now_kst().isoformat()


@router.get("/collect/status")
def get_collect_status():
    """YouTube 수집 진행 상태 조회."""
    return _youtube_collect_status


@router.post("/collect")
async def collect_youtube_videos(
    request: YouTubeCollectRequest,
    background_tasks: BackgroundTasks,
):
    """내 아이디어 종목 YouTube 영상 수집 (백그라운드).

    내 아이디어에 등록된 종목명으로 YouTube 검색 후 수집합니다.
    수집은 백그라운드에서 실행되며, /collect/status로 진행 상태를 확인할 수 있습니다.
    """
    global _youtube_collect_status

    if _youtube_collect_status["is_running"]:
        raise HTTPException(
            status_code=409,
            detail="YouTube 수집이 이미 진행 중입니다."
        )

    _youtube_collect_status = {
        "is_running": True,
        "started_at": now_kst().isoformat(),
        "completed_at": None,
        "result": None,
        "error": None,
        "type": "ideas",
    }

    # 백그라운드 태스크로 실행
    background_tasks.add_task(_run_collect_videos, request.hours_back)

    return {
        "started": True,
        "message": "YouTube 영상 수집이 백그라운드에서 시작되었습니다.",
        "status_url": "/api/v1/youtube/collect/status",
    }


@router.post("/collect-hot")
async def collect_hot_videos(
    request: HotCollectRequest,
    background_tasks: BackgroundTasks,
):
    """핫 종목 발굴용 YouTube 영상 수집 (백그라운드).

    주식 관련 키워드로 인기 영상을 검색하고 종목 언급을 분석합니다.
    수집은 백그라운드에서 실행되며, /collect/status로 진행 상태를 확인할 수 있습니다.

    mode:
    - quick: 빠른 수집 (카테고리당 5개 키워드 샘플링)
    - normal: 일반 수집 (카테고리당 10개 키워드)
    - full: 전체 수집 (모든 키워드 + 인기 채널)
    """
    global _youtube_collect_status

    if _youtube_collect_status["is_running"]:
        raise HTTPException(
            status_code=409,
            detail="YouTube 수집이 이미 진행 중입니다."
        )

    _youtube_collect_status = {
        "is_running": True,
        "started_at": now_kst().isoformat(),
        "completed_at": None,
        "result": None,
        "error": None,
        "type": "hot",
    }

    # 백그라운드 태스크로 실행
    background_tasks.add_task(_run_collect_hot_videos, request.hours_back, request.mode)

    return {
        "started": True,
        "message": f"핫 영상 수집({request.mode})이 백그라운드에서 시작되었습니다.",
        "status_url": "/api/v1/youtube/collect/status",
    }
