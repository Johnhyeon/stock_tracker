"""텔레그램 봇 API 클라이언트."""
import logging
from typing import Optional

import httpx

from core.config import get_settings

logger = logging.getLogger(__name__)


class TelegramClient:
    """텔레그램 봇 API 클라이언트."""

    BASE_URL = "https://api.telegram.org"

    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        """텔레그램이 설정되어 있는지 확인."""
        return bool(self.settings.telegram_bot_token)

    @property
    def bot_token(self) -> str:
        return self.settings.telegram_bot_token or ""

    @property
    def default_chat_id(self) -> Optional[str]:
        return self.settings.telegram_chat_id

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_api_url(self, method: str) -> str:
        return f"{self.BASE_URL}/bot{self.bot_token}/{method}"

    async def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML",
        disable_notification: bool = False,
    ) -> dict:
        """
        텔레그램 메시지 전송.

        Args:
            text: 전송할 메시지 (HTML 지원)
            chat_id: 수신자 채팅 ID (없으면 기본값 사용)
            parse_mode: 파싱 모드 (HTML, Markdown, MarkdownV2)
            disable_notification: 알림음 비활성화

        Returns:
            API 응답 딕셔너리
        """
        if not self.is_configured:
            raise ValueError("텔레그램 봇 토큰이 설정되지 않았습니다.")

        target_chat_id = chat_id or self.default_chat_id
        if not target_chat_id:
            raise ValueError("채팅 ID가 지정되지 않았습니다.")

        client = await self._get_client()
        url = self._get_api_url("sendMessage")

        payload = {
            "chat_id": target_chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification,
        }

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

            if result.get("ok"):
                logger.info(f"텔레그램 메시지 전송 성공: chat_id={target_chat_id}")
                return result
            else:
                error_desc = result.get("description", "Unknown error")
                logger.error(f"텔레그램 API 오류: {error_desc}")
                raise Exception(f"텔레그램 API 오류: {error_desc}")

        except httpx.HTTPStatusError as e:
            logger.error(f"텔레그램 HTTP 오류: {e}")
            raise
        except Exception as e:
            logger.error(f"텔레그램 전송 실패: {e}")
            raise

    async def send_alert(
        self,
        title: str,
        message: str,
        chat_id: Optional[str] = None,
        alert_type: Optional[str] = None,
    ) -> dict:
        """
        알림 형식으로 메시지 전송.

        Args:
            title: 알림 제목
            message: 알림 내용
            chat_id: 수신자 채팅 ID
            alert_type: 알림 유형 (이모지 선택용)

        Returns:
            API 응답 딕셔너리
        """
        # 알림 유형별 이모지
        emoji_map = {
            "youtube_surge": "📈",
            "disclosure_important": "📋",
            "fomo_warning": "⚠️",
            "target_reached": "🎯",
            "fundamental_deterioration": "📉",
            "time_expired": "⏰",
            "telegram_keyword": "📢",
            "custom": "🔔",
        }

        emoji = emoji_map.get(alert_type, "🔔")

        # HTML 형식 메시지 구성
        formatted_message = f"""
{emoji} <b>{title}</b>

{message}

<i>🤖 Investment Tracker 알림</i>
""".strip()

        return await self.send_message(
            text=formatted_message,
            chat_id=chat_id,
            parse_mode="HTML",
        )

    async def test_connection(self) -> dict:
        """
        봇 연결 테스트 (getMe API 호출).

        Returns:
            봇 정보 딕셔너리
        """
        if not self.is_configured:
            raise ValueError("텔레그램 봇 토큰이 설정되지 않았습니다.")

        client = await self._get_client()
        url = self._get_api_url("getMe")

        try:
            response = await client.get(url)
            response.raise_for_status()
            result = response.json()

            if result.get("ok"):
                bot_info = result.get("result", {})
                logger.info(f"텔레그램 봇 연결 성공: @{bot_info.get('username')}")
                return bot_info
            else:
                error_desc = result.get("description", "Unknown error")
                raise Exception(f"텔레그램 API 오류: {error_desc}")

        except Exception as e:
            logger.error(f"텔레그램 연결 테스트 실패: {e}")
            raise


# 싱글톤 인스턴스
_telegram_client: Optional[TelegramClient] = None


def get_telegram_client() -> TelegramClient:
    """텔레그램 클라이언트 싱글톤 반환."""
    global _telegram_client
    if _telegram_client is None:
        _telegram_client = TelegramClient()
    return _telegram_client
