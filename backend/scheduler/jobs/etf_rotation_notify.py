"""ETF 순환매 시그널 텔레그램 알림 작업."""
import logging
from datetime import datetime

from core.database import async_session_maker
from services.etf_rotation_service import EtfRotationService
from integrations.telegram.client import get_telegram_client

logger = logging.getLogger(__name__)


def format_signal_message(signals: list[dict]) -> str:
    """시그널을 텔레그램 메시지 형식으로 포맷."""
    if not signals:
        return ""

    # 시그널 타입별 이모지
    emoji_map = {
        "STRONG_UP": "🚀",
        "MOMENTUM_UP": "📈",
        "REVERSAL_UP": "🔄",
        "STRONG_DOWN": "📉",
    }

    # 시그널 타입별 한글 라벨
    label_map = {
        "STRONG_UP": "강세 전환",
        "MOMENTUM_UP": "모멘텀 상승",
        "REVERSAL_UP": "반등 시도",
        "STRONG_DOWN": "약세 전환",
    }

    lines = []

    # 상승 시그널
    up_signals = [s for s in signals if s["signal_type"] in ("STRONG_UP", "MOMENTUM_UP", "REVERSAL_UP")]
    if up_signals:
        lines.append("📊 <b>상승 시그널</b>")
        for s in up_signals:
            emoji = emoji_map.get(s["signal_type"], "")
            label = label_map.get(s["signal_type"], s["signal_type"])
            change = f"+{s['change_5d']:.1f}%" if s["change_5d"] > 0 else f"{s['change_5d']:.1f}%"
            lines.append(f"  {emoji} <b>{s['theme']}</b> - {label}")
            lines.append(f"      5일 {change} | 거래량비 {s['trading_value_ratio']:.1f}x")
        lines.append("")

    # 하락 시그널
    down_signals = [s for s in signals if s["signal_type"] == "STRONG_DOWN"]
    if down_signals:
        lines.append("📉 <b>약세 시그널</b>")
        for s in down_signals:
            change = f"{s['change_5d']:.1f}%"
            lines.append(f"  📉 <b>{s['theme']}</b>")
            lines.append(f"      5일 {change} | 거래량비 {s['trading_value_ratio']:.1f}x")
        lines.append("")

    return "\n".join(lines)


async def notify_rotation_signals():
    """순환매 시그널 텔레그램 알림.

    매일 장 마감 후 ETF 수집 후 실행되어
    순환매 시그널을 텔레그램으로 발송합니다.
    """
    logger.info("순환매 시그널 알림 작업 시작")

    telegram = get_telegram_client()

    if not telegram.is_configured:
        logger.warning("텔레그램이 설정되지 않아 시그널 알림 건너뜀")
        return

    async with async_session_maker() as session:
        try:
            service = EtfRotationService(session)
            signals = await service.get_rotation_signals()

            if not signals:
                logger.info("발생한 순환매 시그널 없음")
                return

            # 메시지 구성
            now = datetime.now()
            date_str = now.strftime("%Y-%m-%d")

            message_body = format_signal_message(signals)

            if not message_body:
                logger.info("알림할 시그널 없음")
                return

            title = f"섹터 순환매 시그널 ({date_str})"

            full_message = f"""
🔔 <b>{title}</b>

{message_body}
<i>💡 ETF 등락률 + 거래량 분석 기반</i>
""".strip()

            # 텔레그램 발송
            await telegram.send_message(
                text=full_message,
                parse_mode="HTML",
            )

            logger.info(f"순환매 시그널 알림 발송 완료: {len(signals)}개 시그널")

        except Exception as e:
            logger.error(f"순환매 시그널 알림 실패: {e}")
            raise
