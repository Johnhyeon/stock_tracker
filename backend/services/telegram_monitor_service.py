"""텔레그램 채널 모니터링 서비스."""
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from core.config import get_settings
from models import (
    TelegramChannel,
    TelegramKeywordMatch,
    InvestmentIdea,
    IdeaStatus,
    AlertType,
    NotificationLog,
    NotificationChannel,
)
from integrations.telegram.client import get_telegram_client

logger = logging.getLogger(__name__)


class TelegramMonitorService:
    """텔레그램 채널 모니터링 서비스.

    Telethon을 사용하여 등록된 채널의 메시지를 모니터링하고,
    활성 아이디어의 종목명이 언급되면 알림을 발송합니다.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self._client = None
        self._is_connected = False

    @property
    def is_configured(self) -> bool:
        """Telethon API가 설정되어 있는지 확인."""
        return bool(
            self.settings.telegram_api_id
            and self.settings.telegram_api_hash
        )

    async def _get_client(self):
        """Telethon 클라이언트 가져오기 (lazy initialization)."""
        if not self.is_configured:
            raise ValueError("Telegram API ID/Hash가 설정되지 않았습니다.")

        if self._client is None:
            try:
                from telethon import TelegramClient
                self._client = TelegramClient(
                    self.settings.telegram_session_name,
                    self.settings.telegram_api_id,
                    self.settings.telegram_api_hash,
                )
            except ImportError:
                raise ImportError("telethon 라이브러리가 설치되지 않았습니다. pip install telethon")

        return self._client

    async def connect(self) -> bool:
        """텔레그램에 연결."""
        if not self.is_configured:
            logger.warning("Telegram API가 설정되지 않아 모니터링을 시작할 수 없습니다.")
            return False

        try:
            client = await self._get_client()
            await client.start()
            self._is_connected = True
            logger.info("텔레그램 모니터링 클라이언트 연결 성공")
            return True
        except Exception as e:
            logger.error(f"텔레그램 연결 실패: {e}")
            return False

    async def disconnect(self):
        """텔레그램 연결 해제."""
        if self._client:
            await self._client.disconnect()
            self._is_connected = False
            logger.info("텔레그램 모니터링 클라이언트 연결 해제")

    async def get_active_keywords(self) -> dict[str, dict]:
        """활성 아이디어의 종목명 키워드 목록 조회.

        Returns:
            {종목명: {stock_code, idea_id, idea_tickers}}
        """
        stmt = select(InvestmentIdea).where(
            InvestmentIdea.status == IdeaStatus.ACTIVE
        )
        result = await self.db.execute(stmt)
        ideas = result.scalars().all()

        keywords = {}
        for idea in ideas:
            for ticker in idea.tickers:
                # "삼성전자(005930)" 형식에서 종목명과 코드 추출
                match = re.match(r"^(.+)\((\d{6})\)$", ticker)
                if match:
                    stock_name = match.group(1)
                    stock_code = match.group(2)
                    keywords[stock_name] = {
                        "stock_code": stock_code,
                        "idea_id": str(idea.id),
                        "idea_tickers": idea.tickers,
                    }
                else:
                    # 코드 없이 종목명만 있는 경우
                    keywords[ticker] = {
                        "stock_code": None,
                        "idea_id": str(idea.id),
                        "idea_tickers": idea.tickers,
                    }

        logger.debug(f"활성 키워드 {len(keywords)}개 로드: {list(keywords.keys())}")
        return keywords

    async def get_enabled_channels(self) -> list[TelegramChannel]:
        """활성화된 채널 목록 조회."""
        stmt = select(TelegramChannel).where(TelegramChannel.is_enabled == True)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_channel(
        self,
        channel_id: int,
        channel_name: str,
        channel_username: Optional[str] = None,
    ) -> TelegramChannel:
        """모니터링 채널 추가."""
        stmt = insert(TelegramChannel).values(
            channel_id=channel_id,
            channel_name=channel_name,
            channel_username=channel_username,
            is_enabled=True,
        ).on_conflict_do_update(
            index_elements=["channel_id"],
            set_={
                "channel_name": channel_name,
                "channel_username": channel_username,
                "is_enabled": True,
                "updated_at": datetime.utcnow(),
            }
        ).returning(TelegramChannel)

        result = await self.db.execute(stmt)
        await self.db.commit()

        channel = result.scalar_one()
        logger.info(f"채널 추가됨: {channel_name} ({channel_id})")
        return channel

    async def remove_channel(self, channel_id: int) -> bool:
        """모니터링 채널 비활성화."""
        stmt = select(TelegramChannel).where(TelegramChannel.channel_id == channel_id)
        result = await self.db.execute(stmt)
        channel = result.scalar_one_or_none()

        if channel:
            channel.is_enabled = False
            await self.db.commit()
            logger.info(f"채널 비활성화됨: {channel.channel_name}")
            return True
        return False

    async def check_messages(self, limit: int = 100) -> list[TelegramKeywordMatch]:
        """모든 채널의 새 메시지를 확인하고 키워드 매칭."""
        if not self._is_connected:
            connected = await self.connect()
            if not connected:
                return []

        keywords = await self.get_active_keywords()
        if not keywords:
            logger.debug("모니터링할 키워드가 없습니다.")
            return []

        channels = await self.get_enabled_channels()
        if not channels:
            logger.debug("모니터링할 채널이 없습니다.")
            return []

        matches = []

        for channel in channels:
            try:
                channel_matches = await self._check_channel_messages(
                    channel, keywords, limit
                )
                matches.extend(channel_matches)
            except Exception as e:
                logger.error(f"채널 메시지 확인 실패 ({channel.channel_name}): {e}")

        return matches

    async def _check_channel_messages(
        self,
        channel: TelegramChannel,
        keywords: dict[str, dict],
        limit: int,
    ) -> list[TelegramKeywordMatch]:
        """특정 채널의 메시지 확인."""
        matches = []
        client = await self._get_client()

        try:
            # 채널의 최근 메시지 조회
            entity = await client.get_entity(channel.channel_id)
            messages = await client.get_messages(
                entity,
                limit=limit,
                min_id=channel.last_message_id,  # 마지막 확인 이후 메시지만
            )

            if not messages:
                return matches

            max_message_id = channel.last_message_id

            for msg in messages:
                if not msg.text:
                    continue

                max_message_id = max(max_message_id, msg.id)

                # 키워드 매칭
                for keyword, info in keywords.items():
                    if keyword in msg.text:
                        # 중복 체크
                        existing = await self.db.execute(
                            select(TelegramKeywordMatch).where(
                                and_(
                                    TelegramKeywordMatch.channel_id == channel.channel_id,
                                    TelegramKeywordMatch.message_id == msg.id,
                                    TelegramKeywordMatch.matched_keyword == keyword,
                                )
                            )
                        )
                        if existing.scalar_one_or_none():
                            continue

                        # 매칭 기록 저장
                        match_record = TelegramKeywordMatch(
                            channel_id=channel.channel_id,
                            channel_name=channel.channel_name,
                            message_id=msg.id,
                            message_text=msg.text[:1000],  # 최대 1000자
                            message_date=msg.date,
                            matched_keyword=keyword,
                            stock_code=info.get("stock_code"),
                            idea_id=info.get("idea_id"),
                            notification_sent=False,
                        )
                        self.db.add(match_record)
                        matches.append(match_record)

                        logger.info(
                            f"키워드 매칭: '{keyword}' in {channel.channel_name}"
                        )

            # 마지막 메시지 ID 업데이트
            if max_message_id > channel.last_message_id:
                channel.last_message_id = max_message_id

            await self.db.commit()

        except Exception as e:
            logger.error(f"채널 메시지 조회 실패 ({channel.channel_name}): {e}")
            await self.db.rollback()

        return matches

    async def send_notifications(self, matches: list[TelegramKeywordMatch]) -> int:
        """매칭된 키워드에 대해 알림 발송."""
        telegram_client = get_telegram_client()
        if not telegram_client.is_configured:
            logger.warning("텔레그램 봇이 설정되지 않아 알림을 발송할 수 없습니다.")
            return 0

        sent_count = 0

        for match in matches:
            if match.notification_sent:
                continue

            try:
                # 메시지 내용 요약 (100자)
                text_preview = match.message_text[:100]
                if len(match.message_text) > 100:
                    text_preview += "..."

                title = f"📢 종목 언급 감지: {match.matched_keyword}"
                message = f"""채널: {match.channel_name}
시간: {match.message_date.strftime('%Y-%m-%d %H:%M')}

내용:
{text_preview}"""

                await telegram_client.send_alert(
                    title=title,
                    message=message,
                    alert_type="telegram_keyword",
                )

                # 알림 로그 저장
                log = NotificationLog(
                    alert_type=AlertType.TELEGRAM_KEYWORD,
                    channel=NotificationChannel.TELEGRAM,
                    recipient=telegram_client.default_chat_id,
                    title=title,
                    message=message,
                    is_success=True,
                    related_entity_type="telegram_keyword_match",
                    related_entity_id=str(match.id),
                )
                self.db.add(log)

                match.notification_sent = True
                sent_count += 1

            except Exception as e:
                logger.error(f"알림 발송 실패 ({match.matched_keyword}): {e}")

                # 실패 로그 저장
                log = NotificationLog(
                    alert_type=AlertType.TELEGRAM_KEYWORD,
                    channel=NotificationChannel.TELEGRAM,
                    title=f"종목 언급 감지: {match.matched_keyword}",
                    message=str(e),
                    is_success=False,
                    error_message=str(e),
                )
                self.db.add(log)

        await self.db.commit()
        return sent_count

    async def run_monitor_cycle(self) -> dict:
        """모니터링 사이클 실행 (스케줄러용)."""
        result = {
            "checked_channels": 0,
            "matches_found": 0,
            "notifications_sent": 0,
        }

        try:
            channels = await self.get_enabled_channels()
            result["checked_channels"] = len(channels)

            matches = await self.check_messages()
            result["matches_found"] = len(matches)

            if matches:
                sent = await self.send_notifications(matches)
                result["notifications_sent"] = sent

            logger.info(
                f"모니터링 사이클 완료: {result['checked_channels']}채널, "
                f"{result['matches_found']}매칭, {result['notifications_sent']}알림"
            )

        except Exception as e:
            logger.error(f"모니터링 사이클 실패: {e}")
            result["error"] = str(e)

        return result

    async def get_recent_matches(
        self,
        days: int = 7,
        limit: int = 50,
    ) -> list[TelegramKeywordMatch]:
        """최근 매칭 기록 조회."""
        since = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(TelegramKeywordMatch)
            .where(TelegramKeywordMatch.created_at >= since)
            .order_by(TelegramKeywordMatch.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def resolve_channel_by_username(self, username: str) -> Optional[dict]:
        """@username으로 채널 정보 조회."""
        if not self._is_connected:
            connected = await self.connect()
            if not connected:
                return None

        try:
            client = await self._get_client()
            entity = await client.get_entity(username)

            return {
                "channel_id": entity.id,
                "channel_name": getattr(entity, "title", None) or getattr(entity, "first_name", username),
                "channel_username": getattr(entity, "username", None),
            }
        except Exception as e:
            logger.error(f"채널 조회 실패 ({username}): {e}")
            return None
