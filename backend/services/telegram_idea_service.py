"""텔레그램 아이디어 수집 서비스.

투자아이디어 채팅방에서 아이디어를 자동 수집하여 저장.
- 투자아이디어 (내 아이디어): source_type='my'
- 투자아이디어2 (타인 아이디어): source_type='others'
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from core.timezone import now_kst
from core.config import get_settings
from models import TelegramIdea, IdeaSourceType, Stock

logger = logging.getLogger(__name__)


class TelegramIdeaService:
    """텔레그램 아이디어 수집 서비스."""

    # 채널 ID → source_type 매핑
    CHANNEL_MAP = {
        5008508687: ("my", "투자아이디어"),
        5132891681: ("others", "투자아이디어2"),
    }

    # 해시태그 패턴: #종목명 → 종목명만 추출 (공백 없이, 줄바꿈 전까지)
    HASHTAG_PATTERN = re.compile(r'#([가-힣A-Za-z0-9]+)')

    # 종목코드 패턴: `489460` → 코드 추출
    CODE_PATTERN = re.compile(r'`(\d{6})`')

    # 종목명(종목코드) 패턴: 삼성전자(005930) → 둘 다 추출
    NAME_CODE_PATTERN = re.compile(r'([가-힣A-Za-z0-9]+)\s*[\(\[](\d{6})[\)\]]')

    # 봇 메시지 필터링 패턴 (📊 이모지가 포함된 메시지는 봇 메시지)
    BOT_MESSAGE_PATTERN = re.compile(r'📊|🤖|⏰.*스케줄러')

    # 봇 포맷팅 메시지 패턴: 📨 **작성자** | YYYY-MM-DD HH:MM\n━━━━━━━━━━━━━━━━\n내용
    BOT_FORWARD_PATTERN = re.compile(
        r'^📨\s*\*\*(.+?)\*\*\s*\|\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*\n'
        r'[━─]+\s*\n',
        re.MULTILINE
    )

    # 봇 포맷팅 메시지 패턴: 📨 **작성자** | YYYY-MM-DD HH:MM\n━━━━━━━━━━━━━━━━\n내용
    BOT_FORWARD_PATTERN = re.compile(
        r'^📨\s*\*\*(.+?)\*\*\s*\|\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*\n'
        r'[━─]+\s*\n',
        re.MULTILINE
    )

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    @property
    def is_telethon_configured(self) -> bool:
        """Telethon API가 설정되어 있는지 확인."""
        from integrations.telegram.telethon_client import is_telethon_configured
        return is_telethon_configured()

    async def _get_telethon_client(self):
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

    def _is_bot_message(self, text: str) -> bool:
        """봇 메시지인지 확인."""
        return bool(self.BOT_MESSAGE_PATTERN.search(text))

    def _parse_bot_forward_format(self, text: str) -> tuple[str, Optional[str], Optional[datetime]]:
        """봇 포워드 포맷 메시지를 파싱.

        입력: 📨 **작성자** | 2026-02-06 15:26\n━━━━━━━━━━━━━━━━\n#종목명 내용...
        출력: (정리된 메시지, 작성자명, 원본 날짜)
        """
        match = self.BOT_FORWARD_PATTERN.match(text)
        if not match:
            return text, None, None

        author_name = match.group(1).strip()
        date_str = match.group(2).strip()

        # 날짜 파싱
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        except ValueError:
            parsed_date = None

        # 포맷팅 헤더 제거한 순수 메시지
        clean_text = self.BOT_FORWARD_PATTERN.sub('', text).strip()

        return clean_text, author_name, parsed_date

    def _parse_bot_forward_format(self, text: str) -> tuple[str, Optional[str], Optional[datetime]]:
        """봇 포워드 포맷 메시지를 파싱.

        입력: 📨 **작성자** | 2026-02-06 15:26\n━━━━━━━━━━━━━━━━\n#종목명 내용...
        출력: (정리된 메시지, 작성자명, 원본 날짜)
        """
        match = self.BOT_FORWARD_PATTERN.match(text)
        if not match:
            return text, None, None

        author_name = match.group(1).strip()
        date_str = match.group(2).strip()

        # 날짜 파싱
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        except ValueError:
            parsed_date = None

        # 포맷팅 헤더 제거한 순수 메시지
        clean_text = self.BOT_FORWARD_PATTERN.sub('', text).strip()

        return clean_text, author_name, parsed_date

    async def _find_stock_by_name(self, name: str) -> Optional[Stock]:
        """종목명으로 주식 조회."""
        # 정확한 매칭
        stmt = select(Stock).where(Stock.name == name)
        result = await self.db.execute(stmt)
        stock = result.scalar_one_or_none()
        if stock:
            return stock

        # 부분 매칭 (종목명이 포함된 경우)
        stmt = select(Stock).where(Stock.name.ilike(f"%{name}%")).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _find_stock_by_code(self, code: str) -> Optional[Stock]:
        """종목 코드로 주식 조회."""
        stmt = select(Stock).where(Stock.code == code)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def extract_stocks_from_text(self, text: str) -> list[dict]:
        """텍스트에서 종목 추출.

        Returns:
            [{"code": "005930", "name": "삼성전자", "hashtag": "#삼성전자"}, ...]
        """
        stocks = []
        seen_codes = set()
        seen_names = set()

        # 1. 종목명(종목코드) 패턴: 삼성전자(005930)
        for match in self.NAME_CODE_PATTERN.finditer(text):
            name, code = match.groups()
            if code not in seen_codes:
                seen_codes.add(code)
                seen_names.add(name)
                stocks.append({
                    "code": code,
                    "name": name,
                    "hashtag": None
                })

        # 2. 백틱 종목코드 패턴: `489460`
        for match in self.CODE_PATTERN.finditer(text):
            code = match.group(1)
            if code not in seen_codes:
                # DB에서 종목명 조회
                stock = await self._find_stock_by_code(code)
                if stock:
                    seen_codes.add(code)
                    seen_names.add(stock.name)
                    stocks.append({
                        "code": code,
                        "name": stock.name,
                        "hashtag": None
                    })

        # 3. 해시태그 패턴: #삼일씨엔에스
        for match in self.HASHTAG_PATTERN.finditer(text):
            name = match.group(1).strip()

            # 일반 해시태그 제외 (투자, 매수, 주식 등)
            skip_tags = {"투자", "매수", "매도", "주식", "테마", "급등", "급락", "뉴스", "공시", "실적"}
            if name in skip_tags:
                continue

            if name not in seen_names:
                # DB에서 종목코드 조회
                stock = await self._find_stock_by_name(name)
                if stock:
                    seen_codes.add(stock.code)
                    seen_names.add(stock.name)
                    stocks.append({
                        "code": stock.code,
                        "name": stock.name,
                        "hashtag": f"#{name}"
                    })
                # DB에 없는 종목은 필터링 (저장하지 않음)

        return stocks

    def _extract_hashtags(self, text: str) -> list[str]:
        """텍스트에서 모든 해시태그 추출."""
        return [f"#{match.group(1)}" for match in self.HASHTAG_PATTERN.finditer(text)]

    async def collect_ideas(self, limit: int = 100, collect_all: bool = False) -> dict:
        """양쪽 채널에서 아이디어 수집.

        Args:
            limit: 채널당 수집할 메시지 수 (collect_all=True면 배치 크기)
            collect_all: True면 모든 히스토리 수집 (min_id 기반 반복)

        Returns:
            {
                "results": [{"channel_name", "messages_collected", "ideas_created", "errors"}, ...],
                "total_messages": int,
                "total_ideas": int
            }
        """
        from integrations.telegram.telethon_client import is_connected
        if not is_connected():
            connected = await self.connect()
            if not connected:
                return {"results": [], "total_messages": 0, "total_ideas": 0, "error": "연결 실패"}

        from telethon.tl.types import PeerChannel

        client = await self._get_telethon_client()
        results = []
        total_messages = 0
        total_ideas = 0

        # 엔티티 캐시 사전 로드
        _dialogs_loaded = False

        # 두 채널 모두 수집
        channel_ids = [
            self.settings.telegram_idea_my_channel_id,
            self.settings.telegram_idea_others_channel_id,
        ]

        for channel_id in channel_ids:
            if channel_id not in self.CHANNEL_MAP:
                continue

            source_type, channel_name = self.CHANNEL_MAP[channel_id]
            channel_result = {
                "channel_name": channel_name,
                "messages_collected": 0,
                "ideas_created": 0,
                "errors": []
            }

            try:
                # 엔티티 resolve (PeerChannel 명시 → dialogs 로드 fallback)
                entity = None
                try:
                    entity = await client.get_input_entity(PeerChannel(channel_id))
                except ValueError:
                    pass

                if entity is None:
                    if not _dialogs_loaded:
                        logger.info("Loading dialogs to populate entity cache...")
                        await client.get_dialogs()
                        _dialogs_loaded = True
                    entity = await client.get_entity(channel_id)

                # collect_all 모드면 가장 오래된 저장된 message_id부터 역순으로 수집
                min_id = 0
                if collect_all:
                    # DB에서 해당 채널의 가장 작은 message_id 조회
                    stmt = select(func.min(TelegramIdea.message_id)).where(
                        TelegramIdea.channel_id == channel_id
                    )
                    result = await self.db.execute(stmt)
                    existing_min_id = result.scalar()
                    if existing_min_id:
                        # 기존 데이터보다 오래된 메시지 수집 (offset_id 사용)
                        messages = await client.get_messages(
                            entity,
                            limit=limit,
                            offset_id=existing_min_id,  # 이 ID보다 작은 메시지 조회
                        )
                    else:
                        messages = await client.get_messages(entity, limit=limit)
                else:
                    messages = await client.get_messages(entity, limit=limit)

                if not messages:
                    results.append(channel_result)
                    continue

                for msg in messages:
                    if not msg.text:
                        continue

                    # 봇 메시지 필터링
                    if self._is_bot_message(msg.text):
                        continue

                    channel_result["messages_collected"] += 1

                    # 원본 메시지 텍스트
                    message_text = msg.text

                    # 포워드 정보 추출
                    is_forwarded = msg.forward is not None
                    forward_from_name = None
                    original_date = msg.date.replace(tzinfo=None) if msg.date.tzinfo else msg.date

                    if is_forwarded and msg.forward:
                        # 포워드 메시지의 원본 날짜 사용
                        if msg.forward.date:
                            original_date = msg.forward.date.replace(tzinfo=None) if msg.forward.date.tzinfo else msg.forward.date

                        # 포워드 발신자 정보
                        if hasattr(msg.forward, 'from_name') and msg.forward.from_name:
                            forward_from_name = msg.forward.from_name
                        elif hasattr(msg.forward, 'sender_id') and msg.forward.sender_id:
                            try:
                                sender = await client.get_entity(msg.forward.sender_id)
                                if hasattr(sender, 'first_name'):
                                    forward_from_name = sender.first_name
                                    if hasattr(sender, 'last_name') and sender.last_name:
                                        forward_from_name += f" {sender.last_name}"
                            except Exception:
                                pass

                    # 봇 포워드 포맷 파싱 (📨 **작성자** | 날짜 형식)
                    clean_text, bot_author, bot_date = self._parse_bot_forward_format(message_text)
                    if bot_author:
                        # 봇 포맷 메시지: 파싱된 정보 사용
                        message_text = clean_text
                        forward_from_name = bot_author
                        is_forwarded = True
                        if bot_date:
                            original_date = bot_date

                    # 종목 추출 (정리된 메시지 기준)
                    stocks = await self.extract_stocks_from_text(message_text)
                    raw_hashtags = self._extract_hashtags(message_text)

                    if stocks:
                        # 종목별로 분리하여 저장
                        for stock in stocks:
                            try:
                                created = await self._save_idea(
                                    channel_id=channel_id,
                                    channel_name=channel_name,
                                    source_type=source_type,
                                    message_id=msg.id,
                                    message_text=message_text,  # 정리된 메시지
                                    original_date=original_date,
                                    is_forwarded=is_forwarded,
                                    forward_from_name=forward_from_name,
                                    stock_code=stock.get("code"),
                                    stock_name=stock.get("name"),
                                    raw_hashtags=raw_hashtags,
                                )
                                if created:
                                    channel_result["ideas_created"] += 1
                            except Exception as e:
                                await self.db.rollback()
                                channel_result["errors"].append(f"종목 저장 실패 ({stock.get('name')}): {str(e)}")
                    # 종목이 없는 메시지는 필터링 (저장하지 않음)

                total_messages += channel_result["messages_collected"]
                total_ideas += channel_result["ideas_created"]

            except Exception as e:
                await self.db.rollback()
                channel_result["errors"].append(f"채널 수집 실패: {str(e)}")
                logger.error(f"채널 {channel_name} 수집 실패: {e}")

            results.append(channel_result)

        await self.db.commit()

        return {
            "results": results,
            "total_messages": total_messages,
            "total_ideas": total_ideas,
        }

    async def _save_idea(
        self,
        channel_id: int,
        channel_name: str,
        source_type: str,
        message_id: int,
        message_text: str,
        original_date: datetime,
        is_forwarded: bool,
        forward_from_name: Optional[str],
        stock_code: Optional[str],
        stock_name: Optional[str],
        raw_hashtags: list[str],
    ) -> bool:
        """아이디어 저장 (중복 체크 후 INSERT).

        Returns:
            True if created, False if already exists
        """
        from sqlalchemy import and_

        # 중복 체크
        if stock_code:
            check_stmt = select(TelegramIdea.id).where(
                and_(
                    TelegramIdea.channel_id == channel_id,
                    TelegramIdea.message_id == message_id,
                    TelegramIdea.stock_code == stock_code,
                )
            )
        else:
            check_stmt = select(TelegramIdea.id).where(
                and_(
                    TelegramIdea.channel_id == channel_id,
                    TelegramIdea.message_id == message_id,
                    TelegramIdea.stock_code.is_(None),
                )
            )

        existing = await self.db.execute(check_stmt)
        if existing.scalar_one_or_none():
            return False

        # 새 레코드 삽입
        idea = TelegramIdea(
            channel_id=channel_id,
            channel_name=channel_name,
            source_type=source_type,
            message_id=message_id,
            message_text=message_text,
            original_date=original_date,
            is_forwarded=is_forwarded,
            forward_from_name=forward_from_name,
            stock_code=stock_code,
            stock_name=stock_name,
            raw_hashtags=raw_hashtags,
        )
        self.db.add(idea)
        return True

    async def get_ideas(
        self,
        source_type: Optional[str] = None,
        days: int = 7,
        stock_code: Optional[str] = None,
        author: Optional[str] = None,
        sentiment: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TelegramIdea], int]:
        """아이디어 목록 조회.

        Args:
            source_type: "my" 또는 "others"
            days: 조회 기간 (일)
            stock_code: 특정 종목만
            author: 발신자 필터 (타인 아이디어용)
            sentiment: 감정 필터 (POSITIVE, NEGATIVE, NEUTRAL)
            limit: 조회 수
            offset: 오프셋

        Returns:
            (아이디어 목록, 전체 개수)
        """
        since = now_kst().replace(tzinfo=None) - timedelta(days=days)
        conditions = [TelegramIdea.original_date >= since]

        if source_type:
            conditions.append(TelegramIdea.source_type == source_type)

        if stock_code:
            conditions.append(TelegramIdea.stock_code == stock_code)

        if author:
            conditions.append(TelegramIdea.forward_from_name == author)

        if sentiment:
            conditions.append(TelegramIdea.sentiment == sentiment)

        # 전체 개수
        count_stmt = (
            select(func.count())
            .select_from(TelegramIdea)
            .where(and_(*conditions))
        )
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # 목록 조회
        stmt = (
            select(TelegramIdea)
            .where(and_(*conditions))
            .order_by(desc(TelegramIdea.original_date))
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        ideas = list(result.scalars().all())

        return ideas, total

    async def get_stock_stats(self, days: int = 30) -> list[dict]:
        """종목별 언급 통계.

        Returns:
            [{"stock_code", "stock_name", "mention_count", "latest_date", "sources"}, ...]
        """
        since = now_kst().replace(tzinfo=None) - timedelta(days=days)

        stmt = (
            select(
                TelegramIdea.stock_code,
                TelegramIdea.stock_name,
                func.count().label("mention_count"),
                func.max(TelegramIdea.original_date).label("latest_date"),
                func.array_agg(func.distinct(TelegramIdea.source_type)).label("sources"),
            )
            .where(
                and_(
                    TelegramIdea.original_date >= since,
                    TelegramIdea.stock_code.isnot(None),
                )
            )
            .group_by(TelegramIdea.stock_code, TelegramIdea.stock_name)
            .order_by(desc("mention_count"))
            .limit(50)
        )
        result = await self.db.execute(stmt)

        stats = []
        for row in result:
            stats.append({
                "stock_code": row.stock_code,
                "stock_name": row.stock_name,
                "mention_count": row.mention_count,
                "latest_date": row.latest_date,
                "sources": list(row.sources) if row.sources else [],
            })

        return stats

    async def get_author_stats(self, days: int = 30) -> list[dict]:
        """발신자별 통계 (타인 아이디어용).

        Returns:
            [{"name", "idea_count", "top_stocks", "latest_idea_date"}, ...]
        """
        since = now_kst().replace(tzinfo=None) - timedelta(days=days)

        # 발신자별 아이디어 수
        stmt = (
            select(
                TelegramIdea.forward_from_name,
                func.count().label("idea_count"),
                func.max(TelegramIdea.original_date).label("latest_idea_date"),
            )
            .where(
                and_(
                    TelegramIdea.original_date >= since,
                    TelegramIdea.source_type == "others",
                    TelegramIdea.forward_from_name.isnot(None),
                )
            )
            .group_by(TelegramIdea.forward_from_name)
            .order_by(desc("idea_count"))
            .limit(30)
        )
        result = await self.db.execute(stmt)

        authors = []
        for row in result:
            if not row.forward_from_name:
                continue

            # 발신자별 TOP 종목 조회
            top_stocks = await self._get_author_top_stocks(
                row.forward_from_name, since, limit=5
            )

            authors.append({
                "name": row.forward_from_name,
                "idea_count": row.idea_count,
                "top_stocks": top_stocks,
                "latest_idea_date": row.latest_idea_date,
            })

        return authors

    async def _get_author_top_stocks(
        self, author: str, since: datetime, limit: int = 5
    ) -> list[dict]:
        """발신자의 TOP 종목 조회."""
        stmt = (
            select(
                TelegramIdea.stock_code,
                TelegramIdea.stock_name,
                func.count().label("count"),
            )
            .where(
                and_(
                    TelegramIdea.original_date >= since,
                    TelegramIdea.forward_from_name == author,
                    TelegramIdea.stock_code.isnot(None),
                )
            )
            .group_by(TelegramIdea.stock_code, TelegramIdea.stock_name)
            .order_by(desc("count"))
            .limit(limit)
        )
        result = await self.db.execute(stmt)

        return [
            {"stock_code": row.stock_code, "stock_name": row.stock_name, "count": row.count}
            for row in result
        ]
