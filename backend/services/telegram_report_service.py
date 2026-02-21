"""텔레그램 리포트 수집 및 감정 분석 서비스."""
import logging
import re
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import select, and_, func, desc

from core.timezone import now_kst
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from core.config import get_settings
from models import (
    TelegramChannel,
    TelegramReport,
    ReportSentimentAnalysis,
    SentimentType,
    InvestmentSignal,
    Stock,
)
from integrations.gemini import get_gemini_client
from services.theme_map_service import get_theme_map_service

logger = logging.getLogger(__name__)


def find_theme_stocks(theme_name: str, limit: int = 3) -> list[dict]:
    """테마명으로 대표 종목 찾기.

    ThemeMapService의 find_theme_stocks에 위임.
    """
    return get_theme_map_service().find_theme_stocks(theme_name, limit)


class TelegramReportService:
    """텔레그램 리포트 수집 및 감정 분석 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    @property
    def is_telethon_configured(self) -> bool:
        """Telethon API가 설정되어 있는지 확인."""
        from integrations.telegram.telethon_client import is_telethon_configured
        return is_telethon_configured()

    @property
    def is_gemini_configured(self) -> bool:
        """Gemini API가 설정되어 있는지 확인."""
        return bool(self.settings.gemini_api_key)

    async def _get_telethon_client(self):
        """공유 Telethon 클라이언트 가져오기."""
        from integrations.telegram.telethon_client import get_telethon_client
        return await get_telethon_client()

    async def connect(self) -> bool:
        """텔레그램에 연결."""
        if not self.is_telethon_configured:
            return False

        from integrations.telegram.telethon_client import connect_telethon
        return await connect_telethon()

    async def disconnect(self):
        """텔레그램 연결 해제."""
        from integrations.telegram.telethon_client import disconnect_telethon
        await disconnect_telethon()

    def _extract_links(self, text: str) -> list[str]:
        """텍스트에서 URL 추출."""
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, text)
        return list(set(urls))

    def _extract_stocks_by_pattern(self, text: str) -> list[dict]:
        """정규식으로 종목코드/종목명 추출."""
        stocks = []

        # 종목명(종목코드) 패턴
        pattern1 = re.findall(r'([가-힣A-Za-z0-9]+)\s*[\(\[](\d{6})[\)\]]', text)
        for name, code in pattern1:
            if name and len(name) <= 20:  # 너무 긴 것 제외
                stocks.append({
                    "code": code,
                    "name": name.strip(),
                    "context": ""
                })

        # 6자리 숫자만 있는 경우 (앞뒤 문맥으로 종목 추정)
        pattern2 = re.findall(r'(?<![0-9])(\d{6})(?![0-9])', text)
        existing_codes = {s["code"] for s in stocks}
        for code in pattern2:
            if code not in existing_codes and code.startswith(('0', '1', '2', '3')):
                stocks.append({
                    "code": code,
                    "name": "",  # 나중에 DB에서 조회
                    "context": ""
                })

        return stocks

    async def collect_messages(self, limit: int = 100) -> dict:
        """모든 활성 채널에서 메시지 수집."""
        from integrations.telegram.telethon_client import is_connected
        if not is_connected():
            connected = await self.connect()
            if not connected:
                return {"collected": 0, "channels": 0, "error": "연결 실패"}

        # 활성 채널 조회
        stmt = select(TelegramChannel).where(TelegramChannel.is_enabled == True)
        result = await self.db.execute(stmt)
        channels = list(result.scalars().all())

        if not channels:
            return {"collected": 0, "channels": 0, "error": None}

        total_collected = 0
        client = await self._get_telethon_client()

        from telethon.tl.functions.messages import GetHistoryRequest
        from telethon.tl.types import PeerChannel

        # 엔티티 캐시 사전 로드 (세션에 없는 채널 resolve용)
        _dialogs_loaded = False

        for channel in channels:
            try:
                # 1순위: username으로 resolve
                if channel.channel_username:
                    try:
                        entity = await client.get_input_entity(channel.channel_username)
                    except ValueError:
                        entity = None
                else:
                    entity = None

                # 2순위: PeerChannel으로 명시적 지정
                if entity is None:
                    try:
                        entity = await client.get_input_entity(PeerChannel(channel.channel_id))
                    except ValueError:
                        entity = None

                # 3순위: dialogs 로드 후 재시도
                if entity is None:
                    if not _dialogs_loaded:
                        logger.info("Loading dialogs to populate entity cache...")
                        await client.get_dialogs()
                        _dialogs_loaded = True
                    entity = await client.get_input_entity(channel.channel_id)

                max_message_id = channel.last_message_id

                # Raw API로 메시지 가져오기 (엔티티 resolve 우회)
                history = await client(GetHistoryRequest(
                    peer=entity,
                    offset_id=0,
                    offset_date=None,
                    add_offset=0,
                    limit=limit,
                    max_id=0,
                    min_id=channel.last_message_id,
                    hash=0,
                ))

                messages = history.messages
                if not messages:
                    continue

                for msg in messages:
                    try:
                        msg_text = getattr(msg, 'message', None)
                        if not msg_text:
                            continue

                        max_message_id = max(max_message_id, msg.id)

                        # 메시지 URL 생성 (공개 채널인 경우)
                        message_url = None
                        if channel.channel_username:
                            message_url = f"https://t.me/{channel.channel_username}/{msg.id}"

                        # 링크 및 종목 추출
                        extracted_links = self._extract_links(msg_text)
                        extracted_stocks = self._extract_stocks_by_pattern(msg_text)

                        # timezone 제거 (naive datetime으로 변환)
                        message_date = msg.date.replace(tzinfo=None) if msg.date.tzinfo else msg.date

                        # UPSERT (중복 방지)
                        stmt = insert(TelegramReport).values(
                            channel_id=channel.channel_id,
                            channel_name=channel.channel_name,
                            message_id=msg.id,
                            message_text=msg_text,
                            message_date=message_date,
                            message_url=message_url,
                            extracted_links=extracted_links,
                            extracted_stocks=extracted_stocks,
                            extracted_themes=[],
                            is_processed=False,
                        ).on_conflict_do_nothing(
                            index_elements=["channel_id", "message_id"]
                        )

                        result = await self.db.execute(stmt)
                        if result.rowcount > 0:
                            total_collected += 1

                    except Exception as msg_err:
                        logger.debug(f"메시지 처리 스킵 (id={msg.id}): {msg_err}")
                        continue

                # 마지막 메시지 ID 업데이트
                if max_message_id > channel.last_message_id:
                    channel.last_message_id = max_message_id

            except Exception as e:
                logger.error(f"채널 {channel.channel_name} 메시지 수집 실패: {e}")
                continue

        await self.db.commit()

        return {
            "collected": total_collected,
            "channels": len(channels),
            "error": None
        }

    async def extract_entities_for_reports(self, limit: int = 10) -> dict:
        """미처리 리포트에서 종목/테마 추출 (Gemini + 정규식 병행)."""
        gemini = get_gemini_client()

        # 아직 종목/테마 추출 안 된 리포트 조회
        # extracted_stocks가 비어있거나 is_processed=False인 것
        stmt = (
            select(TelegramReport)
            .where(
                and_(
                    TelegramReport.is_processed == False,
                    func.jsonb_array_length(TelegramReport.extracted_stocks) == 0
                )
            )
            .order_by(TelegramReport.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        reports = list(result.scalars().all())

        if not reports:
            return {"processed": 0, "stocks_found": 0}

        processed = 0
        stocks_found = 0

        for report in reports:
            # 1. 정규식으로 먼저 추출
            pattern_stocks = self._extract_stocks_by_pattern(report.message_text)

            # 2. Gemini로 추가 추출 (설정된 경우)
            gemini_result = None
            if gemini.is_configured:
                try:
                    gemini_result = await gemini.extract_entities(report.message_text)
                except Exception as e:
                    logger.warning(f"Gemini 엔티티 추출 실패: {e}")

            # 결과 병합
            all_stocks = {s["code"]: s for s in pattern_stocks if s["code"]}
            themes = []

            if gemini_result:
                for stock in gemini_result.get("stocks", []):
                    if stock.get("code") and stock["code"] not in all_stocks:
                        all_stocks[stock["code"]] = stock
                    elif stock.get("name") and not stock.get("code"):
                        # 종목명만 있는 경우 DB에서 코드 조회
                        stock_record = await self._find_stock_by_name(stock["name"])
                        if stock_record:
                            all_stocks[stock_record.code] = {
                                "code": stock_record.code,
                                "name": stock_record.name,
                                "context": stock.get("context", "")
                            }
                themes = gemini_result.get("themes", [])

            # 종목명이 없는 경우 DB에서 조회
            for code, stock in all_stocks.items():
                if not stock.get("name"):
                    stock_record = await self._find_stock_by_code(code)
                    if stock_record:
                        stock["name"] = stock_record.name

            # 업데이트
            report.extracted_stocks = list(all_stocks.values())
            report.extracted_themes = themes
            stocks_found += len(all_stocks)
            processed += 1

        await self.db.commit()

        return {"processed": processed, "stocks_found": stocks_found}

    async def _find_stock_by_code(self, code: str) -> Optional[Stock]:
        """종목 코드로 주식 조회."""
        stmt = select(Stock).where(Stock.code == code)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _find_stock_by_name(self, name: str) -> Optional[Stock]:
        """종목명으로 주식 조회."""
        stmt = select(Stock).where(Stock.name == name)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def analyze_sentiment_batch(self, limit: int = 10) -> dict:
        """미처리 리포트 감정 분석 (배치).

        종목이 있는 리포트: 직접 감정 분석
        종목이 없는 리포트: 테마 감정 분석 → 테마 대표 종목에 매핑
        """
        gemini = get_gemini_client()

        if not gemini.is_configured:
            return {"analyzed": 0, "sentiments_created": 0, "theme_mapped": 0, "error": "Gemini API 미설정"}

        # 모든 미처리 리포트 조회 (종목 유무 관계없이)
        stmt = (
            select(TelegramReport)
            .where(TelegramReport.is_processed == False)
            .order_by(TelegramReport.message_date.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        reports = list(result.scalars().all())

        if not reports:
            return {"analyzed": 0, "sentiments_created": 0, "theme_mapped": 0, "error": None}

        analyzed = 0
        sentiments_created = 0
        theme_mapped = 0

        for report in reports:
            try:
                # Gemini 감정 분석
                analysis = await gemini.analyze_report_sentiment(report.message_text)

                if not analysis:
                    report.is_processed = True
                    analyzed += 1
                    continue

                # 테마 업데이트
                if analysis.get("themes"):
                    report.extracted_themes = analysis["themes"]

                # 1. 개별 종목에 대해 감정 분석 결과 저장
                for stock in analysis.get("stocks", []):
                    if not stock.get("name"):
                        continue

                    # 종목 코드는 항상 DB에서 조회 (Gemini가 반환한 코드는 무시)
                    # 동일 종목명이 여러 개일 수 있으므로 DB 조회 결과를 신뢰
                    stock_name = stock["name"].strip()
                    stock_record = await self._find_stock_by_name(stock_name)
                    if stock_record:
                        stock_code = stock_record.code
                        stock_name = stock_record.name  # 정확한 종목명 사용
                    else:
                        # DB에 없는 종목은 저장하지 않음 (알 수 없는 종목 필터링)
                        logger.debug(f"종목을 찾을 수 없음: {stock_name}")
                        continue

                    count = await self._save_sentiment(
                        report, stock_code, stock["name"],
                        stock.get("sentiment", "NEUTRAL"),
                        stock.get("sentiment_score", 0.0),
                        stock.get("confidence", 0.5),
                        stock.get("summary"),
                        stock.get("key_points", []),
                        stock.get("investment_signal"),
                    )
                    sentiments_created += count

                # 2. 테마 감정 분석 → 대표 종목 매핑 (비활성화)
                # 종목명이 직접 언급되지 않은 경우 테마 기반으로 매핑하면
                # 데이터 오염이 발생하므로 이 기능을 비활성화합니다.
                # 테마 정보는 extracted_themes에만 저장하고,
                # 감정 분석은 직접 언급된 종목에 대해서만 수행합니다.
                #
                # 기존 코드 (비활성화됨):
                # for theme_sentiment in analysis.get("theme_sentiments", []):
                #     ... 테마 대표 종목에 매핑 ...

                report.is_processed = True
                analyzed += 1

            except Exception as e:
                logger.error(f"리포트 감정 분석 실패 (id={report.id}): {e}")
                continue

        await self.db.commit()

        return {
            "analyzed": analyzed,
            "sentiments_created": sentiments_created,
            "theme_mapped": theme_mapped,
            "error": None
        }

    async def _save_sentiment(
        self,
        report: TelegramReport,
        stock_code: str,
        stock_name: str,
        sentiment_str: str,
        sentiment_score: float,
        confidence: float,
        summary: Optional[str],
        key_points: list,
        investment_signal_str: Optional[str],
    ) -> int:
        """감정 분석 결과 저장 (UPSERT)."""
        # 감정 타입 변환
        try:
            sentiment = SentimentType(sentiment_str.upper())
        except ValueError:
            sentiment = SentimentType.NEUTRAL

        # 투자 시그널 변환
        investment_signal = None
        if investment_signal_str:
            try:
                investment_signal = InvestmentSignal(investment_signal_str.upper())
            except ValueError:
                pass

        # UPSERT (동일 리포트-종목 조합 중복 방지)
        stmt = insert(ReportSentimentAnalysis).values(
            telegram_report_id=report.id,
            stock_code=stock_code,
            stock_name=stock_name,
            sentiment=sentiment,
            sentiment_score=sentiment_score,
            confidence=confidence,
            summary=summary,
            key_points=key_points,
            investment_signal=investment_signal,
        ).on_conflict_do_update(
            index_elements=["telegram_report_id", "stock_code"],
            set_={
                "sentiment": sentiment,
                "sentiment_score": sentiment_score,
                "confidence": confidence,
                "summary": summary,
                "key_points": key_points,
                "investment_signal": investment_signal,
            }
        )
        result = await self.db.execute(stmt)
        return 1 if result.rowcount > 0 else 0

    async def get_reports(
        self,
        days: int = 7,
        channel_id: Optional[int] = None,
        processed_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TelegramReport]:
        """리포트 목록 조회."""
        since = now_kst().replace(tzinfo=None) - timedelta(days=days)

        conditions = [TelegramReport.message_date >= since]

        if channel_id:
            conditions.append(TelegramReport.channel_id == channel_id)

        if processed_only:
            conditions.append(TelegramReport.is_processed == True)

        stmt = (
            select(TelegramReport)
            .where(and_(*conditions))
            .order_by(desc(TelegramReport.message_date))
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_sentiment_summary(self, days: int = 7) -> dict:
        """종목별 감정 분석 요약.

        Returns:
            {
                "positive_stocks": [{"code", "name", "count", "avg_score", "latest_signal"}],
                "negative_stocks": [{"code", "name", "count", "avg_score", "latest_signal"}],
                "total_reports": int,
                "total_sentiments": int,
                "generated_at": str
            }
        """
        since = now_kst().replace(tzinfo=None) - timedelta(days=days)

        # 긍정 종목 집계
        positive_stmt = (
            select(
                ReportSentimentAnalysis.stock_code,
                ReportSentimentAnalysis.stock_name,
                func.count().label("count"),
                func.avg(ReportSentimentAnalysis.sentiment_score).label("avg_score"),
            )
            .join(TelegramReport)
            .where(
                and_(
                    TelegramReport.message_date >= since,
                    ReportSentimentAnalysis.sentiment == SentimentType.POSITIVE
                )
            )
            .group_by(
                ReportSentimentAnalysis.stock_code,
                ReportSentimentAnalysis.stock_name
            )
            .order_by(desc("count"), desc("avg_score"))
            .limit(20)
        )
        positive_result = await self.db.execute(positive_stmt)
        positive_stocks = []
        for row in positive_result:
            # 최신 시그널 조회
            latest_signal = await self._get_latest_signal(row.stock_code, since)
            positive_stocks.append({
                "code": row.stock_code,
                "name": row.stock_name,
                "count": row.count,
                "avg_score": round(float(row.avg_score), 3),
                "latest_signal": latest_signal
            })

        # 부정 종목 집계
        negative_stmt = (
            select(
                ReportSentimentAnalysis.stock_code,
                ReportSentimentAnalysis.stock_name,
                func.count().label("count"),
                func.avg(ReportSentimentAnalysis.sentiment_score).label("avg_score"),
            )
            .join(TelegramReport)
            .where(
                and_(
                    TelegramReport.message_date >= since,
                    ReportSentimentAnalysis.sentiment == SentimentType.NEGATIVE
                )
            )
            .group_by(
                ReportSentimentAnalysis.stock_code,
                ReportSentimentAnalysis.stock_name
            )
            .order_by(desc("count"), "avg_score")
            .limit(20)
        )
        negative_result = await self.db.execute(negative_stmt)
        negative_stocks = []
        for row in negative_result:
            latest_signal = await self._get_latest_signal(row.stock_code, since)
            negative_stocks.append({
                "code": row.stock_code,
                "name": row.stock_name,
                "count": row.count,
                "avg_score": round(float(row.avg_score), 3),
                "latest_signal": latest_signal
            })

        # 전체 통계
        total_reports_stmt = (
            select(func.count())
            .select_from(TelegramReport)
            .where(TelegramReport.message_date >= since)
        )
        total_reports = await self.db.execute(total_reports_stmt)
        total_reports_count = total_reports.scalar() or 0

        total_sentiments_stmt = (
            select(func.count())
            .select_from(ReportSentimentAnalysis)
            .join(TelegramReport)
            .where(TelegramReport.message_date >= since)
        )
        total_sentiments = await self.db.execute(total_sentiments_stmt)
        total_sentiments_count = total_sentiments.scalar() or 0

        return {
            "positive_stocks": positive_stocks,
            "negative_stocks": negative_stocks,
            "total_reports": total_reports_count,
            "total_sentiments": total_sentiments_count,
            "generated_at": now_kst().isoformat()
        }

    async def _get_latest_signal(self, stock_code: str, since: datetime) -> Optional[str]:
        """특정 종목의 최신 투자 시그널 조회."""
        stmt = (
            select(ReportSentimentAnalysis.investment_signal)
            .join(TelegramReport)
            .where(
                and_(
                    ReportSentimentAnalysis.stock_code == stock_code,
                    TelegramReport.message_date >= since,
                    ReportSentimentAnalysis.investment_signal.isnot(None)
                )
            )
            .order_by(desc(TelegramReport.message_date))
            .limit(1)
        )
        result = await self.db.execute(stmt)
        signal = result.scalar_one_or_none()
        return signal.value if signal else None

    async def get_stock_sentiments(
        self,
        stock_code: Optional[str] = None,
        days: int = 7,
        limit: int = 50,
    ) -> list[dict]:
        """종목별 감정 분석 상세 목록."""
        since = now_kst().replace(tzinfo=None) - timedelta(days=days)

        conditions = [TelegramReport.message_date >= since]
        if stock_code:
            conditions.append(ReportSentimentAnalysis.stock_code == stock_code)

        stmt = (
            select(ReportSentimentAnalysis, TelegramReport)
            .join(TelegramReport)
            .where(and_(*conditions))
            .order_by(desc(TelegramReport.message_date))
            .limit(limit)
        )
        result = await self.db.execute(stmt)

        sentiments = []
        for sentiment, report in result:
            sentiments.append({
                "id": str(sentiment.id),
                "stock_code": sentiment.stock_code,
                "stock_name": sentiment.stock_name,
                "sentiment": sentiment.sentiment.value,
                "sentiment_score": sentiment.sentiment_score,
                "confidence": sentiment.confidence,
                "summary": sentiment.summary,
                "key_points": sentiment.key_points,
                "investment_signal": sentiment.investment_signal.value if sentiment.investment_signal else None,
                "report_id": str(report.id),
                "channel_name": report.channel_name,
                "message_date": report.message_date.isoformat(),
                "message_url": report.message_url,
            })

        return sentiments

    async def get_stock_sentiments_by_codes(
        self,
        stock_codes: list[str],
        days: int = 7,
    ) -> list[dict]:
        """여러 종목의 감정 분석 상세 목록 (테마 상세용)."""
        if not stock_codes:
            return []

        since = now_kst().replace(tzinfo=None) - timedelta(days=days)

        stmt = (
            select(ReportSentimentAnalysis, TelegramReport)
            .join(TelegramReport)
            .where(
                and_(
                    TelegramReport.message_date >= since,
                    ReportSentimentAnalysis.stock_code.in_(stock_codes),
                )
            )
            .order_by(desc(TelegramReport.message_date))
        )
        result = await self.db.execute(stmt)

        sentiments = []
        for sentiment, report in result:
            sentiments.append({
                "id": str(sentiment.id),
                "stock_code": sentiment.stock_code,
                "stock_name": sentiment.stock_name,
                "sentiment": sentiment.sentiment.value,
                "sentiment_score": sentiment.sentiment_score,
                "confidence": sentiment.confidence,
                "summary": sentiment.summary,
                "key_points": sentiment.key_points,
                "investment_signal": sentiment.investment_signal.value if sentiment.investment_signal else None,
                "report_id": str(report.id),
                "channel_name": report.channel_name,
                "message_date": report.message_date.isoformat(),
                "message_url": report.message_url,
            })

        return sentiments

    async def get_sentiment_trend_by_codes(
        self,
        stock_codes: list[str],
        days: int = 14,
    ) -> list[dict]:
        """여러 종목의 감정 분석 일별 추이 (테마 상세용).

        Returns:
            [
                {
                    "date": "2026-01-30",
                    "positive_count": 5,
                    "negative_count": 2,
                    "neutral_count": 1,
                    "total_count": 8,
                    "avg_score": 0.35,
                    "buy_signals": 3,
                    "sell_signals": 1,
                },
                ...
            ]
        """
        if not stock_codes:
            return []

        from core.timezone import today_kst

        since = now_kst().replace(tzinfo=None) - timedelta(days=days)
        start_date = today_kst() - timedelta(days=days)

        # 일별 감정 분석 집계
        from sqlalchemy import Integer as SQLInteger, case

        stmt = (
            select(
                func.date(TelegramReport.message_date).label("analysis_date"),
                func.sum(
                    case(
                        (ReportSentimentAnalysis.sentiment == SentimentType.POSITIVE, 1),
                        else_=0
                    )
                ).label("positive_count"),
                func.sum(
                    case(
                        (ReportSentimentAnalysis.sentiment == SentimentType.NEGATIVE, 1),
                        else_=0
                    )
                ).label("negative_count"),
                func.sum(
                    case(
                        (ReportSentimentAnalysis.sentiment == SentimentType.NEUTRAL, 1),
                        else_=0
                    )
                ).label("neutral_count"),
                func.count().label("total_count"),
                func.avg(ReportSentimentAnalysis.sentiment_score).label("avg_score"),
                func.sum(
                    case(
                        (ReportSentimentAnalysis.investment_signal == InvestmentSignal.BUY, 1),
                        else_=0
                    )
                ).label("buy_signals"),
                func.sum(
                    case(
                        (ReportSentimentAnalysis.investment_signal == InvestmentSignal.SELL, 1),
                        else_=0
                    )
                ).label("sell_signals"),
            )
            .select_from(ReportSentimentAnalysis)
            .join(TelegramReport)
            .where(
                and_(
                    TelegramReport.message_date >= since,
                    ReportSentimentAnalysis.stock_code.in_(stock_codes),
                )
            )
            .group_by(func.date(TelegramReport.message_date))
            .order_by(func.date(TelegramReport.message_date))
        )
        result = await self.db.execute(stmt)

        # 날짜별 데이터 딕셔너리로 변환
        data_by_date = {}
        for row in result:
            data_by_date[row.analysis_date] = {
                "date": row.analysis_date.isoformat(),
                "positive_count": row.positive_count or 0,
                "negative_count": row.negative_count or 0,
                "neutral_count": row.neutral_count or 0,
                "total_count": row.total_count or 0,
                "avg_score": round(float(row.avg_score or 0), 3),
                "buy_signals": row.buy_signals or 0,
                "sell_signals": row.sell_signals or 0,
            }

        # 빈 날짜 채우기
        trend = []
        for i in range(days + 1):
            d = start_date + timedelta(days=i)
            if d in data_by_date:
                trend.append(data_by_date[d])
            else:
                trend.append({
                    "date": d.isoformat(),
                    "positive_count": 0,
                    "negative_count": 0,
                    "neutral_count": 0,
                    "total_count": 0,
                    "avg_score": 0.0,
                    "buy_signals": 0,
                    "sell_signals": 0,
                })

        return trend
