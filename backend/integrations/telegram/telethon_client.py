"""공유 Telethon 유저 클라이언트 싱글톤.

텔레그램 MTProto API를 사용하는 여러 서비스가
단일 클라이언트를 공유하도록 합니다.
"""
import logging
from typing import Optional

from core.config import get_settings

logger = logging.getLogger(__name__)

_telethon_client = None
_is_connected = False


def is_telethon_configured() -> bool:
    """Telethon API가 설정되어 있는지 확인."""
    settings = get_settings()
    return bool(settings.telegram_api_id and settings.telegram_api_hash)


async def get_telethon_client():
    """공유 Telethon 클라이언트 반환 (lazy initialization).

    여러 서비스에서 호출해도 동일 인스턴스를 반환합니다.
    """
    global _telethon_client

    if not is_telethon_configured():
        raise ValueError("Telegram API ID/Hash가 설정되지 않았습니다.")

    if _telethon_client is None:
        try:
            from telethon import TelegramClient
            settings = get_settings()
            _telethon_client = TelegramClient(
                settings.telegram_session_name,
                settings.telegram_api_id,
                settings.telegram_api_hash,
            )
        except ImportError:
            raise ImportError("telethon 라이브러리가 설치되지 않았습니다. pip install telethon")

    return _telethon_client


async def connect_telethon() -> bool:
    """Telethon 클라이언트 연결.

    기존 세션 파일로만 연결을 시도합니다.
    세션이 만료되었으면 터미널에서 수동으로 재인증해야 합니다:
        python -c "from telethon.sync import TelegramClient; \
        c = TelegramClient('stock_monitor', API_ID, API_HASH); \
        c.start(); c.disconnect()"
    """
    global _is_connected

    if not is_telethon_configured():
        logger.warning("Telegram API가 설정되지 않아 연결할 수 없습니다.")
        return False

    try:
        client = await get_telethon_client()
        # start() 대신 connect()를 사용하여 인터랙티브 로그인 방지
        await client.connect()

        if not await client.is_user_authorized():
            logger.error(
                "Telethon 세션이 만료되었습니다. "
                "터미널에서 수동으로 재인증하세요: "
                "cd backend && python -c \"from telethon.sync import TelegramClient; "
                "c = TelegramClient('stock_monitor', API_ID, API_HASH); "
                "c.start(); c.disconnect()\""
            )
            await client.disconnect()
            return False

        _is_connected = True
        logger.info("공유 Telethon 클라이언트 연결 성공")
        return True
    except Exception as e:
        logger.error(f"Telethon 연결 실패: {e}")
        return False


async def disconnect_telethon():
    """Telethon 클라이언트 연결 해제."""
    global _telethon_client, _is_connected

    if _telethon_client and _is_connected:
        try:
            await _telethon_client.disconnect()
            _is_connected = False
            logger.info("공유 Telethon 클라이언트 연결 해제")
        except Exception as e:
            logger.error(f"Telethon 연결 해제 실패: {e}")


def is_connected() -> bool:
    """연결 상태 확인."""
    return _is_connected
