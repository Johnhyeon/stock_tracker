"""알림 서비스 - 규칙 엔진 및 발송 처리."""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.alert import AlertRule, NotificationLog, AlertType, NotificationChannel
from models.youtube_mention import YouTubeMention
from models.ticker_stats import TickerMentionStats
from models.disclosure import Disclosure, DisclosureImportance
from models.idea import InvestmentIdea, IdeaStatus
from models.position import Position
from models.trader_mention import TraderMention
from integrations.telegram.client import get_telegram_client
from integrations.email.client import get_email_client
from core.config import get_settings

logger = logging.getLogger(__name__)


class AlertService:
    """알림 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.telegram = get_telegram_client()
        self.email = get_email_client()

    # ============ CRUD Operations ============

    async def get_rules(
        self,
        enabled_only: bool = False,
        alert_type: Optional[AlertType] = None,
    ) -> List[AlertRule]:
        """알림 규칙 목록 조회."""
        query = select(AlertRule)

        if enabled_only:
            query = query.where(AlertRule.is_enabled == True)
        if alert_type:
            query = query.where(AlertRule.alert_type == alert_type)

        query = query.order_by(AlertRule.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_rule(self, rule_id: UUID) -> Optional[AlertRule]:
        """알림 규칙 조회."""
        result = await self.db.execute(
            select(AlertRule).where(AlertRule.id == rule_id)
        )
        return result.scalar_one_or_none()

    async def create_rule(self, data: dict) -> AlertRule:
        """알림 규칙 생성."""
        rule = AlertRule(**data)
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        logger.info(f"알림 규칙 생성: {rule.name} ({rule.alert_type.value})")
        return rule

    async def update_rule(self, rule_id: UUID, data: dict) -> Optional[AlertRule]:
        """알림 규칙 수정."""
        rule = await self.get_rule(rule_id)
        if not rule:
            return None

        for key, value in data.items():
            if value is not None:
                setattr(rule, key, value)

        await self.db.commit()
        await self.db.refresh(rule)
        logger.info(f"알림 규칙 수정: {rule.name}")
        return rule

    async def delete_rule(self, rule_id: UUID) -> bool:
        """알림 규칙 삭제."""
        rule = await self.get_rule(rule_id)
        if not rule:
            return False

        await self.db.delete(rule)
        await self.db.commit()
        logger.info(f"알림 규칙 삭제: {rule.name}")
        return True

    # ============ Notification Logs ============

    async def get_logs(
        self,
        limit: int = 50,
        alert_type: Optional[AlertType] = None,
        success_only: bool = False,
    ) -> List[NotificationLog]:
        """알림 로그 조회."""
        query = select(NotificationLog)

        if alert_type:
            query = query.where(NotificationLog.alert_type == alert_type)
        if success_only:
            query = query.where(NotificationLog.is_success == True)

        query = query.order_by(NotificationLog.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _create_log(
        self,
        alert_type: AlertType,
        channel: NotificationChannel,
        title: str,
        message: str,
        is_success: bool,
        error_message: Optional[str] = None,
        alert_rule_id: Optional[UUID] = None,
        recipient: Optional[str] = None,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[str] = None,
    ) -> NotificationLog:
        """알림 로그 생성."""
        log = NotificationLog(
            alert_rule_id=alert_rule_id,
            alert_type=alert_type,
            channel=channel,
            recipient=recipient,
            title=title,
            message=message,
            is_success=is_success,
            error_message=error_message,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
        self.db.add(log)
        await self.db.commit()
        return log

    # ============ Notification Sending ============

    async def send_notification(
        self,
        channel: NotificationChannel,
        title: str,
        message: str,
        recipient: Optional[str] = None,
        alert_type: AlertType = AlertType.CUSTOM,
        alert_rule_id: Optional[UUID] = None,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[str] = None,
    ) -> bool:
        """
        알림 발송.

        Args:
            channel: 발송 채널
            title: 알림 제목
            message: 알림 내용
            recipient: 수신자 (이메일 주소 또는 텔레그램 chat_id)
            alert_type: 알림 유형
            alert_rule_id: 연관 규칙 ID
            related_entity_type: 관련 엔티티 타입
            related_entity_id: 관련 엔티티 ID

        Returns:
            발송 성공 여부
        """
        success = False
        error_message = None

        try:
            if channel == NotificationChannel.TELEGRAM:
                await self.telegram.send_alert(
                    title=title,
                    message=message,
                    chat_id=recipient,
                    alert_type=alert_type.value if alert_type else None,
                )
                success = True

            elif channel == NotificationChannel.EMAIL:
                if not recipient:
                    raise ValueError("이메일 수신자가 지정되지 않았습니다.")
                self.email.send_alert(
                    to_email=recipient,
                    title=title,
                    message=message,
                    alert_type=alert_type.value if alert_type else None,
                )
                success = True

            elif channel == NotificationChannel.BOTH:
                # 텔레그램 발송
                try:
                    await self.telegram.send_alert(
                        title=title,
                        message=message,
                        alert_type=alert_type.value if alert_type else None,
                    )
                except Exception as e:
                    logger.warning(f"텔레그램 발송 실패 (BOTH 모드): {e}")

                # 이메일 발송
                if recipient:
                    try:
                        self.email.send_alert(
                            to_email=recipient,
                            title=title,
                            message=message,
                            alert_type=alert_type.value if alert_type else None,
                        )
                    except Exception as e:
                        logger.warning(f"이메일 발송 실패 (BOTH 모드): {e}")

                success = True  # BOTH는 일부 실패해도 성공으로 처리

        except Exception as e:
            error_message = str(e)
            logger.error(f"알림 발송 실패: {e}")

        # 로그 기록
        await self._create_log(
            alert_type=alert_type,
            channel=channel,
            title=title,
            message=message,
            is_success=success,
            error_message=error_message,
            alert_rule_id=alert_rule_id,
            recipient=recipient,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )

        return success

    # ============ Alert Rule Engine ============

    async def check_and_trigger_alerts(self) -> int:
        """
        모든 활성 알림 규칙을 확인하고 조건 충족 시 발송.

        Returns:
            발송된 알림 수
        """
        rules = await self.get_rules(enabled_only=True)
        triggered_count = 0

        for rule in rules:
            try:
                # 쿨다운 체크
                if rule.last_triggered_at:
                    cooldown_until = rule.last_triggered_at + timedelta(
                        minutes=rule.cooldown_minutes
                    )
                    if datetime.utcnow() < cooldown_until:
                        continue

                # 규칙 유형별 처리
                alerts = await self._evaluate_rule(rule)

                for alert_data in alerts:
                    success = await self.send_notification(
                        channel=rule.channel,
                        title=alert_data["title"],
                        message=alert_data["message"],
                        alert_type=rule.alert_type,
                        alert_rule_id=rule.id,
                        related_entity_type=alert_data.get("entity_type"),
                        related_entity_id=alert_data.get("entity_id"),
                    )

                    if success:
                        triggered_count += 1
                        # 마지막 발송 시간 업데이트
                        rule.last_triggered_at = datetime.utcnow()
                        await self.db.commit()

            except Exception as e:
                logger.error(f"알림 규칙 처리 오류 ({rule.name}): {e}")

        logger.info(f"알림 체크 완료: {triggered_count}건 발송")
        return triggered_count

    async def _evaluate_rule(self, rule: AlertRule) -> List[dict]:
        """
        알림 규칙을 평가하고 발송할 알림 목록 반환.

        Returns:
            발송할 알림 데이터 목록 [{title, message, entity_type, entity_id}, ...]
        """
        if rule.alert_type == AlertType.YOUTUBE_SURGE:
            return await self._check_youtube_surge(rule.conditions)

        elif rule.alert_type == AlertType.DISCLOSURE_IMPORTANT:
            return await self._check_important_disclosures(rule.conditions)

        elif rule.alert_type == AlertType.FOMO_WARNING:
            return await self._check_fomo_warning(rule.conditions)

        elif rule.alert_type == AlertType.TARGET_REACHED:
            return await self._check_target_reached(rule.conditions)

        elif rule.alert_type == AlertType.TIME_EXPIRED:
            return await self._check_time_expired(rule.conditions)

        elif rule.alert_type == AlertType.TRADER_NEW_MENTION:
            return await self._check_trader_new_mentions(rule.conditions)

        elif rule.alert_type == AlertType.TRADER_CROSS_CHECK:
            return await self._check_trader_cross_check(rule.conditions)

        return []

    async def _check_youtube_surge(self, conditions: dict) -> List[dict]:
        """YouTube 급증 체크."""
        alerts = []

        threshold = conditions.get("threshold", 5)  # 언급 급증 기준
        hours = conditions.get("time_window_hours", 24)

        since = datetime.utcnow() - timedelta(hours=hours)

        # 최근 기간 내 언급이 급증한 종목 조회
        result = await self.db.execute(
            select(TickerMentionStats)
            .where(TickerMentionStats.updated_at >= since)
            .where(TickerMentionStats.mention_count_7d >= threshold)
        )
        stats_list = result.scalars().all()

        for stats in stats_list:
            # 이전 대비 급증 여부 확인 (간단히 7일 vs 30일 비교)
            if stats.mention_count_30d > 0:
                growth_rate = stats.mention_count_7d / (stats.mention_count_30d / 4)
                if growth_rate >= 2:  # 2배 이상 급증
                    alerts.append({
                        "title": f"YouTube 언급 급증: {stats.stock_code}",
                        "message": f"최근 7일 언급 {stats.mention_count_7d}회 (급증률 {growth_rate:.1f}배)",
                        "entity_type": "ticker_stats",
                        "entity_id": stats.stock_code,
                    })

        return alerts

    async def _check_important_disclosures(self, conditions: dict) -> List[dict]:
        """중요 공시 체크."""
        alerts = []

        hours = conditions.get("time_window_hours", 24)
        stock_codes = conditions.get("stock_codes", [])

        since = datetime.utcnow() - timedelta(hours=hours)

        query = select(Disclosure).where(
            Disclosure.published_at >= since,
            Disclosure.importance == DisclosureImportance.HIGH,
        )

        if stock_codes:
            query = query.where(Disclosure.stock_code.in_(stock_codes))

        result = await self.db.execute(query)
        disclosures = result.scalars().all()

        for disc in disclosures:
            alerts.append({
                "title": f"중요 공시: {disc.stock_code}",
                "message": f"{disc.title}\n\n📅 {disc.published_at.strftime('%Y-%m-%d %H:%M')}",
                "entity_type": "disclosure",
                "entity_id": str(disc.id),
            })

        return alerts

    async def _check_fomo_warning(self, conditions: dict) -> List[dict]:
        """FOMO 위험 경고 체크."""
        alerts = []

        # 보유 중인 아이디어 중 FOMO 점수가 높은 것
        result = await self.db.execute(
            select(InvestmentIdea).where(
                InvestmentIdea.status.in_([IdeaStatus.ACTIVE, IdeaStatus.WATCHING])
            )
        )
        ideas = result.scalars().all()

        fomo_threshold = conditions.get("fomo_score_threshold", 70)

        for idea in ideas:
            # FOMO 점수 계산 (간단 버전)
            fomo_score = self._calculate_fomo_score(idea)
            if fomo_score >= fomo_threshold:
                alerts.append({
                    "title": f"FOMO 위험 경고: {idea.stock_code}",
                    "message": f"FOMO 점수: {fomo_score}/100\n근거: {idea.thesis[:100]}..." if idea.thesis else "",
                    "entity_type": "idea",
                    "entity_id": str(idea.id),
                })

        return alerts

    def _calculate_fomo_score(self, idea: InvestmentIdea) -> int:
        """간단한 FOMO 점수 계산."""
        score = 0

        # 목표 상승률이 너무 높으면 FOMO 위험
        if idea.target_price and idea.entry_price:
            expected_return = (idea.target_price - idea.entry_price) / idea.entry_price * 100
            if expected_return > 50:
                score += 30
            elif expected_return > 30:
                score += 15

        # 근거가 짧으면 충동적 판단 위험
        if idea.thesis and len(idea.thesis) < 50:
            score += 20

        # 확신도가 높으면서 근거가 부실하면 위험
        if idea.conviction_level and idea.conviction_level >= 8:
            if not idea.thesis or len(idea.thesis) < 100:
                score += 25

        return min(score, 100)

    async def _check_target_reached(self, conditions: dict) -> List[dict]:
        """목표가 도달 체크."""
        # 실제 구현 시 가격 서비스와 연동 필요
        return []

    async def _check_time_expired(self, conditions: dict) -> List[dict]:
        """예상 기간 초과 체크."""
        alerts = []

        result = await self.db.execute(
            select(InvestmentIdea).where(
                InvestmentIdea.status == IdeaStatus.ACTIVE,
                InvestmentIdea.expected_date.isnot(None),
                InvestmentIdea.expected_date < datetime.utcnow().date(),
            )
        )
        ideas = result.scalars().all()

        for idea in ideas:
            days_over = (datetime.utcnow().date() - idea.expected_date).days
            alerts.append({
                "title": f"예상 기간 초과: {idea.stock_code}",
                "message": f"예상일로부터 {days_over}일 경과\n원래 예상일: {idea.expected_date}",
                "entity_type": "idea",
                "entity_id": str(idea.id),
            })

        return alerts

    async def _check_trader_new_mentions(self, conditions: dict) -> List[dict]:
        """트레이더 신규 언급 체크."""
        alerts = []

        hours = conditions.get("time_window_hours", 24)
        min_mentions = conditions.get("min_mentions", 2)  # 최소 언급 횟수

        since = datetime.utcnow() - timedelta(hours=hours)

        # 최근 기간 내 신규 언급된 종목
        result = await self.db.execute(
            select(
                TraderMention.stock_name,
                TraderMention.stock_code,
                func.count(TraderMention.id).label("mention_count"),
            )
            .where(TraderMention.created_at >= since)
            .group_by(TraderMention.stock_name, TraderMention.stock_code)
            .having(func.count(TraderMention.id) >= min_mentions)
        )
        mentions = result.all()

        for mention in mentions:
            alerts.append({
                "title": f"트레이더 주목: {mention.stock_name}",
                "message": f"최근 {hours}시간 동안 {mention.mention_count}회 언급됨\n종목코드: {mention.stock_code or '미확인'}",
                "entity_type": "trader_mention",
                "entity_id": mention.stock_name,
            })

        return alerts

    async def _check_trader_cross_check(self, conditions: dict) -> List[dict]:
        """내 아이디어 종목과 트레이더 언급 교차 체크."""
        alerts = []

        hours = conditions.get("time_window_hours", 24)

        since = datetime.utcnow() - timedelta(hours=hours)

        # 내 활성 아이디어의 종목 코드
        ideas_result = await self.db.execute(
            select(InvestmentIdea).where(
                InvestmentIdea.status.in_([IdeaStatus.ACTIVE, IdeaStatus.WATCHING])
            )
        )
        ideas = ideas_result.scalars().all()

        idea_tickers = set()
        idea_map = {}  # stock_code -> idea
        for idea in ideas:
            if idea.tickers:
                for ticker in idea.tickers:
                    idea_tickers.add(ticker)
                    idea_map[ticker] = idea

        if not idea_tickers:
            return alerts

        # 트레이더가 언급한 종목 중 내 종목
        result = await self.db.execute(
            select(
                TraderMention.stock_name,
                TraderMention.stock_code,
                func.count(TraderMention.id).label("mention_count"),
            )
            .where(
                TraderMention.created_at >= since,
                TraderMention.stock_code.in_(list(idea_tickers)),
            )
            .group_by(TraderMention.stock_name, TraderMention.stock_code)
        )
        mentions = result.all()

        for mention in mentions:
            idea = idea_map.get(mention.stock_code)
            idea_title = idea.title if idea else "알 수 없음"
            alerts.append({
                "title": f"트레이더도 주목: {mention.stock_name}",
                "message": f"내 아이디어 '{idea_title}'의 종목\n최근 {hours}시간 동안 트레이더 {mention.mention_count}회 언급",
                "entity_type": "trader_cross_check",
                "entity_id": mention.stock_code,
            })

        return alerts

    # ============ Settings ============

    async def get_settings_status(self) -> dict:
        """알림 설정 현황 조회."""
        telegram_bot_username = None
        if self.telegram.is_configured:
            try:
                bot_info = await self.telegram.test_connection()
                telegram_bot_username = bot_info.get("username")
            except:
                pass

        # 규칙 통계
        all_rules = await self.get_rules()
        enabled_rules = [r for r in all_rules if r.is_enabled]

        return {
            "telegram_configured": self.telegram.is_configured,
            "telegram_bot_username": telegram_bot_username,
            "email_configured": self.email.is_configured,
            "smtp_host": self.settings.smtp_host if self.email.is_configured else None,
            "total_rules": len(all_rules),
            "enabled_rules": len(enabled_rules),
        }
