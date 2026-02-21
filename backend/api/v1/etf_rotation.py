"""ETF 순환매 분석 API 엔드포인트."""
from datetime import datetime
from typing import Literal

from core.timezone import now_kst

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from services.etf_rotation_service import EtfRotationService

router = APIRouter(prefix="/etf-rotation", tags=["etf-rotation"])


@router.get("/heatmap")
async def get_etf_heatmap(
    period: Literal["1d", "5d", "20d", "60d"] = Query(default="5d"),
    db: AsyncSession = Depends(get_async_db),
):
    """테마별 ETF 히트맵 데이터 조회.

    Args:
        period: 기준 기간 (1d, 5d, 20d, 60d)

    Returns:
        테마별 ETF 성과 리스트 (등락률순)
    """
    service = EtfRotationService(db)
    data = await service.get_theme_heatmap_data(period)

    return {
        "period": period,
        "themes": data,
        "count": len(data),
        "generated_at": now_kst().isoformat(),
    }


@router.get("/realtime-heatmap")
async def get_realtime_etf_heatmap(
    db: AsyncSession = Depends(get_async_db),
):
    """실시간 ETF 히트맵 데이터 조회.

    KIS API를 통해 테마별 대표 ETF의 실시간 현재가를 조회하여
    당일 등락률 기준 히트맵을 제공합니다.

    장 운영 시간(09:00~15:30)에만 실시간 데이터가 반영되며,
    장 마감 후에는 마지막 거래 데이터가 반환됩니다.

    Returns:
        {
            "themes": [...],  # 테마별 ETF 실시간 데이터 (등락률순)
            "updated_at": "2026-01-26T10:30:00",
            "market_status": "open" | "closed",
            "total_count": 30,
            "error_count": 0
        }
    """
    service = EtfRotationService(db)
    data = await service.get_realtime_heatmap_data()

    return data


@router.get("/all-etfs")
async def get_all_etfs(
    db: AsyncSession = Depends(get_async_db),
):
    """전체 ETF 데이터 조회 (상세).

    Returns:
        모든 ETF의 성과 데이터
    """
    service = EtfRotationService(db)
    data = await service.get_etf_heatmap_data()

    return {
        "etfs": data,
        "count": len(data),
        "generated_at": now_kst().isoformat(),
    }


@router.get("/signals")
async def get_rotation_signals(
    db: AsyncSession = Depends(get_async_db),
):
    """순환매 시그널 조회.

    강세/약세 전환, 모멘텀 변화 등의 시그널을 반환합니다.

    Returns:
        순환매 시그널 리스트
    """
    service = EtfRotationService(db)
    signals = await service.get_rotation_signals()

    # 시그널 타입별 분류
    strong_up = [s for s in signals if s["signal_type"] == "STRONG_UP"]
    momentum_up = [s for s in signals if s["signal_type"] == "MOMENTUM_UP"]
    reversal_up = [s for s in signals if s["signal_type"] == "REVERSAL_UP"]
    strong_down = [s for s in signals if s["signal_type"] == "STRONG_DOWN"]

    return {
        "signals": signals,
        "summary": {
            "strong_up": len(strong_up),
            "momentum_up": len(momentum_up),
            "reversal_up": len(reversal_up),
            "strong_down": len(strong_down),
            "total": len(signals),
        },
        "top_signals": signals[:5],
        "generated_at": now_kst().isoformat(),
    }


@router.get("/chart/{etf_code}")
async def get_etf_chart(
    etf_code: str,
    days: int = Query(default=60, le=365),
    db: AsyncSession = Depends(get_async_db),
):
    """ETF 차트 데이터 조회.

    Args:
        etf_code: ETF 종목코드
        days: 조회 기간 (일)

    Returns:
        OHLCV 차트 데이터
    """
    service = EtfRotationService(db)
    data = await service.get_etf_chart_data(etf_code, days)

    return {
        "etf_code": etf_code,
        "days": days,
        "candles": data,
        "count": len(data),
    }


@router.get("/compare")
async def compare_etfs(
    codes: str = Query(..., description="ETF 코드 목록 (쉼표 구분)"),
    days: int = Query(default=60, le=365),
    db: AsyncSession = Depends(get_async_db),
):
    """여러 ETF 비교 차트 데이터.

    Args:
        codes: ETF 종목코드 목록 (쉼표 구분)
        days: 조회 기간 (일)

    Returns:
        ETF별 차트 데이터
    """
    service = EtfRotationService(db)
    code_list = [c.strip() for c in codes.split(",") if c.strip()]

    result = {}
    for code in code_list[:5]:  # 최대 5개
        data = await service.get_etf_chart_data(code, days)
        if data:
            result[code] = {
                "etf_name": data[0].get("etf_name") if data else None,
                "candles": data,
            }

    return {
        "etfs": result,
        "days": days,
        "generated_at": now_kst().isoformat(),
    }


@router.get("/theme/{theme_name}")
async def get_theme_detail(
    theme_name: str,
    db: AsyncSession = Depends(get_async_db),
):
    """테마 상세 정보 조회.

    ETF 성과, 차트, 연관 테마, 뉴스 등 상세 정보를 반환합니다.

    Args:
        theme_name: 테마명

    Returns:
        테마 상세 정보
    """
    service = EtfRotationService(db)
    data = await service.get_theme_detail(theme_name)

    if not data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"테마를 찾을 수 없습니다: {theme_name}")

    return {
        **data,
        "generated_at": now_kst().isoformat(),
    }


@router.get("/all-compare")
async def get_all_etf_compare(
    start_date: str = Query(default="2025-01-02", description="시작일 (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_async_db),
):
    """전체 ETF 수익률 비교 차트 데이터.

    모든 테마 대표 ETF의 수익률 추이를 반환합니다.
    시작일 기준 수익률(%)로 정규화됩니다.

    Args:
        start_date: 시작일 (기본: 2025-01-02)

    Returns:
        ETF별 수익률 추이 데이터
    """
    service = EtfRotationService(db)
    data = await service.get_all_etf_compare(start_date)

    return {
        "start_date": start_date,
        "etfs": data,
        "count": len(data),
        "generated_at": now_kst().isoformat(),
    }


@router.get("/holdings/{etf_code}")
async def get_etf_holdings(
    etf_code: str,
    limit: int = Query(default=15, le=50),
    db: AsyncSession = Depends(get_async_db),
):
    """ETF 구성 종목 조회.

    ETF의 구성 종목과 각 종목의 등락률, 수급, 아이디어 여부를 반환합니다.

    Args:
        etf_code: ETF 종목코드
        limit: 최대 종목 수

    Returns:
        구성 종목 리스트
    """
    service = EtfRotationService(db)
    holdings = await service.get_etf_holdings(etf_code, limit)

    return {
        "etf_code": etf_code,
        "holdings": holdings,
        "count": len(holdings),
        "generated_at": now_kst().isoformat(),
    }
