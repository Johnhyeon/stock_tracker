"""전문가 관심종목 API."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body, UploadFile, File
from sqlalchemy.orm import Session

from core.database import get_db
from services.expert_service import ExpertService
from schemas.expert import (
    ExpertHotStock,
    ExpertRisingStock,
    ExpertPerformanceStats,
    ExpertPerformanceDetailResponse,
    SyncRequest,
    SyncResponse,
)

router = APIRouter()


@router.post("/sync", response_model=SyncResponse)
def sync_mentions(
    request: SyncRequest = Body(default=SyncRequest()),
    db: Session = Depends(get_db),
):
    """mentions.json 파일과 DB 동기화.

    1순위: GitHub Gist에서 다운로드
    2순위: 로컬 파일 경로에서 읽기
    """
    import json
    import httpx
    from core.config import get_settings

    service = ExpertService(db)
    settings = get_settings()

    try:
        # 명시적 file_path가 주어진 경우
        if request.file_path:
            result = service.sync_mentions(file_path=request.file_path)
            return SyncResponse(**result)

        # 1순위: Gist에서 가져오기
        if settings.mentions_gist_id and settings.mentions_gist_token:
            try:
                url = f"https://api.github.com/gists/{settings.mentions_gist_id}"
                headers = {
                    "Authorization": f"token {settings.mentions_gist_token}",
                    "Accept": "application/vnd.github.v3+json",
                }
                resp = httpx.get(url, headers=headers, timeout=30)
                resp.raise_for_status()
                gist = resp.json()
                data = json.loads(gist["files"]["mentions.json"]["content"])
                result = service.sync_mentions(data=data)
                return SyncResponse(**result)
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Gist에서 가져오기 실패: {str(e)}")

        # 2순위: 로컬 파일
        result = service.sync_mentions()
        return SyncResponse(**result)
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="mentions.json 파일을 찾을 수 없으며 Gist도 설정되지 않았습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"동기화 실패: {str(e)}")


@router.post("/upload-mentions", response_model=SyncResponse)
def upload_mentions(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """mentions.json 파일 업로드 후 DB 동기화.

    라즈베리파이 등 원격에서 파일을 직접 전송할 때 사용합니다.
    curl -X POST http://서버:8000/api/v1/experts/upload-mentions -F file=@mentions.json
    """
    import json

    try:
        content = file.file.read()
        data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"잘못된 JSON 파일: {e}")

    service = ExpertService(db)
    try:
        result = service.sync_mentions(data=data)
        return SyncResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"동기화 실패: {str(e)}")


@router.get("/hot", response_model=list[ExpertHotStock])
def get_hot_stocks(
    days_back: int = Query(default=7, ge=1, le=30, description="분석 기간"),
    limit: int = Query(default=20, le=50),
    include_price: bool = Query(default=True, description="KIS API 주가 정보 포함"),
    db: Session = Depends(get_db),
):
    """전문가 핫 종목 조회.

    최근 전문가들이 가장 많이 언급한 종목을 조회합니다.
    KIS API를 통해 현재 주가/거래량 정보를 추가하고 가중치 점수를 계산합니다.

    가중치 구성:
    - 언급 횟수 (40%)
    - 주가 상승률 (30%)
    - 거래량 (20%)
    - 신규 등장 보너스 (10%)
    """
    service = ExpertService(db)
    return service.get_hot_stocks(
        days_back=days_back,
        limit=limit,
        include_price=include_price
    )


@router.get("/rising", response_model=list[ExpertRisingStock])
def get_rising_stocks(
    days_back: int = Query(default=7, ge=2, le=30, description="분석 기간"),
    limit: int = Query(default=20, le=50),
    include_price: bool = Query(default=True, description="KIS API 주가 정보 포함"),
    db: Session = Depends(get_db),
):
    """전문가 급상승 종목 조회.

    최근 언급이 급증한 종목을 조회합니다.
    (최근 N/2일 vs 이전 N/2일 비교)
    """
    service = ExpertService(db)
    return service.get_rising_stocks(
        days_back=days_back,
        limit=limit,
        include_price=include_price
    )


@router.get("/performance", response_model=ExpertPerformanceStats)
def get_performance_stats(
    days_back: int = Query(default=30, ge=7, le=90, description="분석 기간"),
    db: Session = Depends(get_db),
):
    """전문가 성과 통계.

    전문가들이 언급한 종목들의 평균 성과, 승률 등을 계산합니다.
    """
    service = ExpertService(db)
    return service.get_performance_stats(days_back=days_back)


@router.get("/performance-detail", response_model=ExpertPerformanceDetailResponse)
def get_performance_detail(
    days_back: int = Query(default=30, ge=7, le=90, description="분석 기간"),
    db: Session = Depends(get_db),
):
    """전문가 성과 상세 분석.

    StockOHLCV 데이터를 기반으로 실제 수익률을 계산합니다.
    종목별 첫 언급일 종가를 매수가로, 최신 종가를 현재가로 사용합니다.
    """
    service = ExpertService(db)
    return service.get_performance_detail(days_back=days_back)


@router.get("/new-mentions")
def get_new_mentions(
    since_hours: int = Query(default=24, ge=1, le=168, description="몇 시간 전부터"),
    db: Session = Depends(get_db),
):
    """새로운 언급 조회.

    최근 N시간 동안 새로 추가된 언급을 조회합니다.
    알림 시스템에서 사용됩니다.
    """
    service = ExpertService(db)
    return service.get_new_mentions(since_hours=since_hours)


@router.get("/cross-check")
def get_cross_check(
    db: Session = Depends(get_db),
):
    """내 아이디어 종목과 전문가 관심종목 크로스 체크.

    내가 등록한 아이디어 종목 중 전문가들도 주목하는 종목을 찾습니다.
    """
    from models import InvestmentIdea, IdeaStatus

    # 내 아이디어의 종목코드 가져오기
    ideas = db.query(InvestmentIdea).filter(
        InvestmentIdea.status.in_([IdeaStatus.ACTIVE, IdeaStatus.WATCHING])
    ).all()

    idea_tickers = set()
    for idea in ideas:
        if idea.tickers:
            idea_tickers.update(idea.tickers)

    service = ExpertService(db)
    return service.get_cross_check(list(idea_tickers))
