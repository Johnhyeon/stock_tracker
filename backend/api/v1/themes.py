"""테마 순환매 API."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from services.theme_service import ThemeService
from services.youtube_service import YouTubeService
from services.trader_service import TraderService
from schemas.theme import (
    ThemeRotationResponse,
    ThemeListItem,
    ThemeSearchResult,
    ThemeHistoryItem,
)

router = APIRouter()


@router.get("/rotation", response_model=ThemeRotationResponse)
def get_theme_rotation(
    days_back: int = Query(default=7, ge=1, le=30, description="분석 기간"),
    db: Session = Depends(get_db),
):
    """테마 순환매 분석.

    YouTube와 트레이더 관심종목 데이터를 기반으로 현재 핫한 테마를 분석합니다.

    분석 요소:
    - YouTube 언급 + 트레이더 언급 횟수
    - 테마 내 관심 종목 수
    - 평균 주가 상승률
    - 총 거래량

    Returns:
        - hot_themes: 핫 테마 목록 (점수 순)
        - categories: 카테고리별 분류 (tech, bio, energy 등)
        - summary: 요약 통계
    """
    # YouTube 데이터 수집 (rising tickers with price info)
    youtube_service = YouTubeService(db)
    youtube_raw = youtube_service.get_rising_tickers(
        days_back=days_back,
        limit=50,
        include_price=True
    )

    # 트레이더 데이터 수집
    trader_service = TraderService(db)
    trader_raw = trader_service.get_hot_stocks(
        days_back=days_back,
        limit=50,
        include_price=True
    )

    # 테마 분석에 필요한 필드만 추출 (둘 다 dict)
    youtube_list = [
        {
            "stock_code": s.get("stock_code"),
            "stock_name": s.get("stock_name"),
            "recent_mentions": s.get("recent_mentions", 0),
            "volume": s.get("volume"),
            "price_change_rate": s.get("price_change_rate"),
        }
        for s in youtube_raw
    ]

    trader_list = [
        {
            "stock_code": s.get("stock_code"),
            "stock_name": s.get("stock_name"),
            "mention_count": s.get("mention_count", 0),
            "volume": s.get("volume"),
            "price_change_rate": s.get("price_change_rate"),
        }
        for s in trader_raw
    ]

    # 테마 분석
    theme_service = ThemeService(db)
    result = theme_service.analyze_theme_rotation(
        youtube_data=youtube_list,
        trader_data=trader_list,
        days=days_back,
    )

    return result


@router.get("/list", response_model=list[ThemeListItem])
def get_theme_list():
    """전체 테마 목록.

    네이버 증권에서 수집한 265개 테마 목록을 반환합니다.
    """
    tms = get_theme_map_service()
    return [
        {"name": name, "stock_count": len(stocks)}
        for name, stocks in tms.get_all_themes().items()
    ]


@router.get("/search", response_model=list[ThemeSearchResult])
def search_themes(
    q: str = Query(..., min_length=1, description="검색어"),
):
    """테마 검색.

    테마명에 검색어가 포함된 테마를 찾습니다.
    """
    tms = get_theme_map_service()
    query = q.lower()
    results = []
    for name, stocks in tms.get_all_themes().items():
        if query in name.lower():
            results.append({
                "name": name,
                "stock_count": len(stocks),
                "stocks": stocks[:5],
            })
    return results[:20]


@router.get("/{theme_name}/stocks")
def get_theme_stocks(
    theme_name: str,
    db: Session = Depends(get_db),
):
    """특정 테마의 종목 목록.

    해당 테마에 속한 모든 종목을 반환합니다.
    """
    theme_service = ThemeService(db)
    stocks = theme_service.get_stocks_in_theme(theme_name)

    if not stocks:
        return {"theme_name": theme_name, "stocks": [], "stock_count": 0}

    return {
        "theme_name": theme_name,
        "stocks": stocks,
        "stock_count": len(stocks),
    }


@router.get("/{theme_name}/history", response_model=list[ThemeHistoryItem])
def get_theme_history(
    theme_name: str,
    days: int = Query(default=30, ge=7, le=90, description="조회 기간"),
    db: Session = Depends(get_db),
):
    """특정 테마의 히스토리.

    테마 내 종목들의 언급 추이를 조회합니다.
    """
    theme_service = ThemeService(db)
    return theme_service.get_theme_history(theme_name, days=days)


@router.get("/stock/{stock_code}/themes")
def get_stock_themes(
    stock_code: str,
):
    """특정 종목이 속한 테마 목록.

    해당 종목이 어떤 테마에 속해있는지 확인합니다.
    """
    tms = get_theme_map_service()
    themes = tms.get_themes_for_stock(stock_code)

    return {
        "stock_code": stock_code,
        "themes": themes,
        "theme_count": len(themes),
    }
