"""텔레그램 채널 모니터링 서비스."""
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from core.timezone import now_kst
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

    @property
    def is_configured(self) -> bool:
        """Telethon API가 설정되어 있는지 확인."""
        from integrations.telegram.telethon_client import is_telethon_configured
        return is_telethon_configured()

    async def _get_client(self):
        """공유 Telethon 클라이언트 가져오기."""
        from integrations.telegram.telethon_client import get_telethon_client
        return await get_telethon_client()

    async def connect(self) -> bool:
        """텔레그램에 연결."""
        from integrations.telegram.telethon_client import connect_telethon
        return await connect_telethon()

    async def disconnect(self):
        """텔레그램 연결 해제."""
        from integrations.telegram.telethon_client import disconnect_telethon
        await disconnect_telethon()

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
                "updated_at": now_kst().replace(tzinfo=None),
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

    async def check_messages(self, limit: int = 100) -> list[dict]:
        """모든 채널의 새 메시지를 확인하고 키워드 매칭.

        Telethon과 SQLAlchemy async의 greenlet 충돌 방지를 위해
        1단계: DB에서 데이터 로드 (순수 DB)
        2단계: Telethon으로 메시지 수집 (순수 Telethon)
        3단계: 매칭 결과 DB 저장 (순수 DB)

        Returns:
            plain dict 리스트 (커밋 후 ORM expire 문제 방지)
        """
        from integrations.telegram.telethon_client import is_connected
        if not is_connected():
            connected = await self.connect()
            if not connected:
                return []

        # --- 1단계: DB에서 키워드/채널 로드 ---
        keywords = await self.get_active_keywords()
        if not keywords:
            logger.debug("모니터링할 키워드가 없습니다.")
            return []

        channels = await self.get_enabled_channels()
        if not channels:
            logger.debug("모니터링할 채널이 없습니다.")
            return []

        # ORM 객체를 plain dict로 변환 (greenlet 깨짐 방지)
        channel_data = [
            {
                "id": ch.id,
                "channel_id": ch.channel_id,
                "channel_name": ch.channel_name,
                "last_message_id": ch.last_message_id,
            }
            for ch in channels
        ]

        # --- 2단계: Telethon으로 메시지 수집 ---
        all_messages = {}  # channel_id -> [(msg_id, msg_text, msg_date), ...]
        client = await self._get_client()

        for ch in channel_data:
            try:
                entity = await client.get_entity(ch["channel_id"])
                messages = await client.get_messages(
                    entity,
                    limit=limit,
                    min_id=ch["last_message_id"],
                )
                if messages:
                    all_messages[ch["channel_id"]] = [
                        (msg.id, msg.text, msg.date)
                        for msg in messages
                        if msg.text
                    ]
            except Exception as e:
                logger.error(f"채널 메시지 조회 실패 ({ch['channel_name']}): {e}")

        # --- 3단계: 매칭 결과 DB 저장 ---
        # no_autoflush로 SELECT 시 premature flush 방지
        match_dicts = []
        seen_keys = set()  # 인메모리 중복 추적

        with self.db.no_autoflush:
            for ch in channel_data:
                msgs = all_messages.get(ch["channel_id"], [])
                if not msgs:
                    continue

                max_message_id = ch["last_message_id"]

                for msg_id, msg_text, msg_date in msgs:
                    max_message_id = max(max_message_id, msg_id)

                    for keyword, info in keywords.items():
                        if keyword in msg_text:
                            dedup_key = (ch["channel_id"], msg_id, keyword)

                            # 인메모리 중복 체크
                            if dedup_key in seen_keys:
                                continue

                            # DB 중복 체크
                            existing = await self.db.execute(
                                select(TelegramKeywordMatch.id).where(
                                    and_(
                                        TelegramKeywordMatch.channel_id == ch["channel_id"],
                                        TelegramKeywordMatch.message_id == msg_id,
                                        TelegramKeywordMatch.matched_keyword == keyword,
                                    )
                                )
                            )
                            if existing.scalar_one_or_none():
                                seen_keys.add(dedup_key)
                                continue

                            match_record = TelegramKeywordMatch(
                                channel_id=ch["channel_id"],
                                channel_name=ch["channel_name"],
                                message_id=msg_id,
                                message_text=msg_text[:1000],
                                message_date=msg_date,
                                matched_keyword=keyword,
                                stock_code=info.get("stock_code"),
                                idea_id=info.get("idea_id"),
                                notification_sent=False,
                            )
                            self.db.add(match_record)
                            # plain dict로 변환 (커밋 후 ORM expire 문제 방지)
                            match_dicts.append({
                                "id": match_record.id,
                                "channel_name": ch["channel_name"],
                                "message_text": msg_text[:1000],
                                "message_date": msg_date,
                                "matched_keyword": keyword,
                                "stock_code": info.get("stock_code"),
                            })
                            seen_keys.add(dedup_key)
                            logger.info(f"키워드 매칭: '{keyword}' in {ch['channel_name']}")

                # 마지막 메시지 ID 업데이트 (메시지가 있으면 매칭 여부와 무관하게)
                if max_message_id > ch["last_message_id"]:
                    stmt = (
                        select(TelegramChannel)
                        .where(TelegramChannel.id == ch["id"])
                    )
                    result = await self.db.execute(stmt)
                    db_channel = result.scalar_one_or_none()
                    if db_channel:
                        db_channel.last_message_id = max_message_id

        try:
            await self.db.commit()
        except Exception as e:
            logger.error(f"매칭 결과 저장 실패: {e}")
            await self.db.rollback()
            return []  # 커밋 실패 시 빈 리스트 반환 (알림 발송 방지)

        return match_dicts

    async def send_notifications(self, matches: list[dict]) -> int:
        """매칭된 키워드에 대해 알림 발송.

        동일 키워드에 대해 24시간 내 중복 알림을 방지합니다.
        matches는 check_messages에서 반환한 plain dict 리스트입니다.
        """
        telegram_client = get_telegram_client()
        if not telegram_client.is_configured:
            logger.warning("텔레그램 봇이 설정되지 않아 알림을 발송할 수 없습니다.")
            return 0

        # 최근 24시간 내 이미 발송된 키워드 조회 (중복 알림 방지)
        since = now_kst().replace(tzinfo=None) - timedelta(hours=24)
        recently_sent_stmt = (
            select(TelegramKeywordMatch.matched_keyword)
            .where(and_(
                TelegramKeywordMatch.notification_sent == True,
                TelegramKeywordMatch.created_at >= since,
            ))
            .distinct()
        )
        result = await self.db.execute(recently_sent_stmt)
        recently_notified = {r[0] for r in result}

        sent_count = 0

        for match_data in matches:
            keyword = match_data["matched_keyword"]

            # 24시간 내 이미 같은 키워드로 알림 발송됨 → 스킵
            if keyword in recently_notified:
                # DB에서 notification_sent=True로 마킹 (재시도 방지)
                match_stmt = select(TelegramKeywordMatch).where(
                    TelegramKeywordMatch.id == match_data["id"]
                )
                match_result = await self.db.execute(match_stmt)
                db_match = match_result.scalar_one_or_none()
                if db_match:
                    db_match.notification_sent = True
                continue

            try:
                text_preview = match_data["message_text"][:100]
                if len(match_data["message_text"]) > 100:
                    text_preview += "..."

                title = f"📢 종목 언급 감지: {keyword}"
                message = f"""채널: {match_data['channel_name']}
시간: {match_data['message_date'].strftime('%Y-%m-%d %H:%M')}

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
                    related_entity_id=str(match_data["id"]),
                )
                self.db.add(log)

                # DB에서 notification_sent=True로 마킹
                match_stmt = select(TelegramKeywordMatch).where(
                    TelegramKeywordMatch.id == match_data["id"]
                )
                match_result = await self.db.execute(match_stmt)
                db_match = match_result.scalar_one_or_none()
                if db_match:
                    db_match.notification_sent = True

                recently_notified.add(keyword)
                sent_count += 1

            except Exception as e:
                logger.error(f"알림 발송 실패 ({keyword}): {e}")

                log = NotificationLog(
                    alert_type=AlertType.TELEGRAM_KEYWORD,
                    channel=NotificationChannel.TELEGRAM,
                    title=f"종목 언급 감지: {keyword}",
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
        since = now_kst().replace(tzinfo=None) - timedelta(days=days)
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
        from integrations.telegram.telethon_client import is_connected
        if not is_connected():
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
