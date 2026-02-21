"""전문가 관심종목 데이터 동기화 작업."""
import asyncio
import json
import logging

import httpx

from core.config import get_settings
from core.database import SessionLocal
from services.expert_service import ExpertService
from scheduler.job_tracker import track_job_execution

logger = logging.getLogger(__name__)


async def _fetch_mentions_from_gist() -> dict | None:
    """GitHub Gist에서 mentions.json 다운로드."""
    settings = get_settings()
    if not settings.mentions_gist_id or not settings.mentions_gist_token:
        return None

    url = f"https://api.github.com/gists/{settings.mentions_gist_id}"
    headers = {
        "Authorization": f"token {settings.mentions_gist_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()

        gist = resp.json()
        file_content = gist["files"]["mentions.json"]["content"]
        return json.loads(file_content)
    except Exception as e:
        logger.warning(f"Gist에서 mentions.json 가져오기 실패: {e}")
        return None


def _sync_with_data(data: dict) -> dict:
    """mentions dict로 DB 동기화 (스레드풀에서 실행)."""
    db = SessionLocal()
    try:
        service = ExpertService(db)
        return service.sync_mentions(data=data)
    finally:
        db.close()


def _sync_from_file() -> dict:
    """로컬 파일로 DB 동기화 (스레드풀에서 실행)."""
    db = SessionLocal()
    try:
        service = ExpertService(db)
        return service.sync_mentions()
    finally:
        db.close()


@track_job_execution("expert_sync")
async def sync_expert_mentions():
    """
    mentions.json과 DB 동기화.

    1순위: GitHub Gist에서 다운로드 (라파 → Gist → 서버)
    2순위: 로컬 파일 경로에서 읽기 (폴백)
    """
    logger.info("Starting expert mentions sync job...")

    try:
        settings = get_settings()
        gist_configured = bool(settings.mentions_gist_id and settings.mentions_gist_token)

        # 1순위: Gist에서 가져오기
        data = await _fetch_mentions_from_gist()
        if data:
            result = await asyncio.to_thread(_sync_with_data, data)
            logger.info(
                f"Expert mentions sync (Gist) completed: "
                f"{result['total_stocks']} stocks, "
                f"{result['new_mentions']} new mentions"
            )
        elif not gist_configured:
            # Gist 미설정 시에만 로컬 파일 fallback
            result = await asyncio.to_thread(_sync_from_file)
            logger.info(
                f"Expert mentions sync (file) completed: "
                f"{result['total_stocks']} stocks, "
                f"{result['new_mentions']} new mentions"
            )
        else:
            # Gist 설정됐지만 가져오기 실패
            logger.warning("Gist fetch failed, skipping expert mentions sync")
            return

        if result['new_mentions'] > 0:
            logger.info(f"New expert mentions detected: {result['new_mentions']}")

    except FileNotFoundError:
        logger.warning("mentions.json file not found and Gist not configured, skipping sync")
    except Exception as e:
        logger.error(f"Expert mentions sync failed: {e}")
