"""API 헬스체크 엔드포인트."""
import asyncio
from fastapi import APIRouter

from core.config import get_settings
from integrations.kis import get_kis_client
from integrations.dart import get_dart_client
from integrations.youtube import get_youtube_client

router = APIRouter()


@router.get("/apis")
async def check_all_apis():
    """모든 외부 API 연결 상태 확인."""
    settings = get_settings()

    results = {
        "kis": {"configured": False, "connected": False, "error": None},
        "dart": {"configured": False, "connected": False, "error": None},
        "youtube": {"configured": False, "connected": False, "error": None},
    }

    # KIS API 체크
    if settings.kis_app_key and settings.kis_app_secret:
        results["kis"]["configured"] = True
        try:
            client = get_kis_client()
            # 토큰 발급 테스트
            await client.token_manager.get_access_token()
            results["kis"]["connected"] = True
        except Exception as e:
            results["kis"]["error"] = str(e)[:100]

    # DART API 체크
    if settings.dart_api_key:
        results["dart"]["configured"] = True
        try:
            client = get_dart_client()
            # 간단한 API 호출 테스트
            await client.search_disclosures(page_count=1)
            results["dart"]["connected"] = True
        except Exception as e:
            results["dart"]["error"] = str(e)[:100]

    # YouTube API 체크
    if settings.youtube_api_key:
        results["youtube"]["configured"] = True
        try:
            client = get_youtube_client()
            # 간단한 검색 테스트 (채널 없어도 API 키 유효성 확인)
            await client.get("/search", params={
                "key": client.api_key,
                "part": "snippet",
                "q": "test",
                "maxResults": 1,
                "type": "video",
            })
            results["youtube"]["connected"] = True
        except Exception as e:
            results["youtube"]["error"] = str(e)[:100]

    return results


@router.get("/kis")
async def check_kis():
    """KIS API 연결 상태 확인."""
    settings = get_settings()

    if not settings.kis_app_key or not settings.kis_app_secret:
        return {"configured": False, "connected": False, "error": "API 키 미설정", "token_info": None}

    try:
        client = get_kis_client()
        await client.token_manager.get_access_token()
        token_info = client.token_manager.get_token_info()
        return {"configured": True, "connected": True, "error": None, "token_info": token_info}
    except Exception as e:
        return {"configured": True, "connected": False, "error": str(e)[:100], "token_info": None}


@router.get("/dart")
async def check_dart():
    """DART API 연결 상태 확인."""
    settings = get_settings()

    if not settings.dart_api_key:
        return {"configured": False, "connected": False, "error": "API 키 미설정"}

    try:
        client = get_dart_client()
        await client.search_disclosures(page_count=1)
        return {"configured": True, "connected": True, "error": None}
    except Exception as e:
        return {"configured": True, "connected": False, "error": str(e)[:100]}


@router.get("/youtube")
async def check_youtube():
    """YouTube API 연결 상태 확인."""
    settings = get_settings()

    if not settings.youtube_api_key:
        return {"configured": False, "connected": False, "error": "API 키 미설정"}

    try:
        client = get_youtube_client()
        await client.get("/search", params={
            "key": client.api_key,
            "part": "snippet",
            "q": "test",
            "maxResults": 1,
            "type": "video",
        })
        return {"configured": True, "connected": True, "error": None}
    except Exception as e:
        return {"configured": True, "connected": False, "error": str(e)[:100]}
