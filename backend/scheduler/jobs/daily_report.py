"""일일 시장 리포트 텔레그램 발송 작업.

별도 텔레그램 계정(Telethon)으로 지정 채널에 직접 발송합니다.
기존 모니터링용 Telethon 세션과 독립적으로 동작합니다.
"""
import logging
from typing import Optional

from sqlalchemy import select, and_

from core.config import get_settings
from core.database import async_session_maker
from core.timezone import today_kst
from models.job_execution_log import JobExecutionLog
from services.daily_report_service import DailyReportService
from scheduler.job_tracker import track_job_execution

logger = logging.getLogger(__name__)

# 리포트 전용 Telethon 클라이언트 (싱글톤)
_report_client = None


async def _get_report_client():
    """리포트 전용 Telethon 클라이언트 반환."""
    global _report_client

    settings = get_settings()
    if not settings.daily_report_api_id or not settings.daily_report_api_hash:
        raise ValueError("DAILY_REPORT_API_ID/API_HASH가 설정되지 않았습니다.")

    if _report_client is None:
        from telethon import TelegramClient
        _report_client = TelegramClient(
            settings.daily_report_session_name,
            settings.daily_report_api_id,
            settings.daily_report_api_hash,
        )

    if not _report_client.is_connected():
        await _report_client.connect()

    if not await _report_client.is_user_authorized():
        raise ConnectionError(
            "리포트 전용 Telethon 세션이 없습니다. 최초 인증을 실행하세요:\n"
            "  cd backend && python scripts/auth_report_session.py"
        )

    return _report_client


async def _send_via_telethon(message: str, channel: str):
    """리포트 전용 Telethon 클라이언트로 채널에 메시지 발송."""
    client = await _get_report_client()

    # 채널 resolve (@username 또는 숫자 ID)
    try:
        channel_id = int(channel)
    except ValueError:
        channel_id = channel  # @username 문자열

    entity = await client.get_entity(channel_id)
    await client.send_message(entity, message, parse_mode="html")
    logger.info(f"리포트 발송 완료: {channel}")


async def _already_sent_today() -> bool:
    """오늘 이미 daily_report가 성공적으로 발송되었는지 확인."""
    today_start = today_kst()
    async with async_session_maker() as db:
        stmt = (
            select(JobExecutionLog.id)
            .where(and_(
                JobExecutionLog.job_name == "daily_report",
                JobExecutionLog.status == "success",
                JobExecutionLog.started_at >= today_start,
            ))
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None


@track_job_execution("daily_report")
async def send_daily_report():
    """일일 시장 리포트 생성 및 텔레그램 채널 발송.

    매일 장 마감 후(19:00) 실행되어
    급등 시그널, 눌림목 기회, 주목 테마, AI 시장 관점을
    별도 텔레그램 계정으로 지정 채널에 발송합니다.
    """
    logger.info("일일 리포트 작업 시작")

    # 오늘 이미 성공 발송했으면 중복 방지
    if await _already_sent_today():
        logger.info("오늘 이미 일일 리포트 발송됨, 건너뜀")
        return

    settings = get_settings()
    channel = settings.daily_report_channel

    if not channel:
        logger.warning("DAILY_REPORT_CHANNEL이 설정되지 않아 일일 리포트 건너뜀")
        return

    async with async_session_maker() as session:
        try:
            service = DailyReportService(session)
            message = await service.generate_report()

            if not message:
                logger.info("리포트에 포함할 데이터 없음, 발송 건너뜀")
                return

            # 텔레그램 메시지 길이 제한 (4096자)
            if len(message) > 4096:
                message = message[:4050] + "\n\n<i>... (일부 생략)</i>"

            await _send_via_telethon(message, channel)
            logger.info("일일 리포트 발송 완료")

        except Exception as e:
            logger.error(f"일일 리포트 발송 실패: {e}")
            raise
