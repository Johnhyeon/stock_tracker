"""이메일 SMTP 클라이언트."""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List

from core.config import get_settings

logger = logging.getLogger(__name__)


class EmailClient:
    """이메일 SMTP 클라이언트."""

    def __init__(self):
        self.settings = get_settings()

    @property
    def is_configured(self) -> bool:
        """이메일이 설정되어 있는지 확인."""
        return all([
            self.settings.smtp_host,
            self.settings.smtp_user,
            self.settings.smtp_password,
            self.settings.smtp_from_email,
        ])

    def _create_smtp_connection(self) -> smtplib.SMTP:
        """SMTP 연결 생성."""
        smtp = smtplib.SMTP(
            self.settings.smtp_host,
            self.settings.smtp_port,
            timeout=30,
        )

        if self.settings.smtp_use_tls:
            smtp.starttls()

        smtp.login(
            self.settings.smtp_user,
            self.settings.smtp_password,
        )

        return smtp

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> bool:
        """
        이메일 전송.

        Args:
            to_email: 수신자 이메일 주소
            subject: 이메일 제목
            body: 텍스트 본문
            html_body: HTML 본문 (선택)

        Returns:
            성공 여부
        """
        if not self.is_configured:
            raise ValueError("이메일 SMTP 설정이 완료되지 않았습니다.")

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.settings.smtp_from_email
            msg["To"] = to_email

            # 텍스트 버전
            text_part = MIMEText(body, "plain", "utf-8")
            msg.attach(text_part)

            # HTML 버전 (있으면)
            if html_body:
                html_part = MIMEText(html_body, "html", "utf-8")
                msg.attach(html_part)

            with self._create_smtp_connection() as smtp:
                smtp.sendmail(
                    self.settings.smtp_from_email,
                    [to_email],
                    msg.as_string(),
                )

            logger.info(f"이메일 전송 성공: to={to_email}, subject={subject}")
            return True

        except Exception as e:
            logger.error(f"이메일 전송 실패: {e}")
            raise

    def send_alert(
        self,
        to_email: str,
        title: str,
        message: str,
        alert_type: Optional[str] = None,
    ) -> bool:
        """
        알림 형식으로 이메일 전송.

        Args:
            to_email: 수신자 이메일 주소
            title: 알림 제목
            message: 알림 내용
            alert_type: 알림 유형

        Returns:
            성공 여부
        """
        # 알림 유형별 한글 이름
        type_names = {
            "youtube_surge": "YouTube 급증 감지",
            "disclosure_important": "중요 공시 발생",
            "fomo_warning": "FOMO 위험 경고",
            "target_reached": "목표가 도달",
            "fundamental_deterioration": "펀더멘털 악화",
            "time_expired": "예상 기간 초과",
            "custom": "사용자 정의 알림",
        }

        type_name = type_names.get(alert_type, "알림")
        subject = f"[Investment Tracker] {type_name}: {title}"

        # 텍스트 본문
        text_body = f"""
{title}

{message}

---
Investment Tracker 알림 시스템
""".strip()

        # HTML 본문
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #3b82f6; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f8fafc; padding: 20px; border: 1px solid #e2e8f0; }}
        .footer {{ padding: 15px; text-align: center; color: #64748b; font-size: 12px; }}
        .alert-type {{ font-size: 12px; opacity: 0.8; }}
        h1 {{ margin: 0; font-size: 18px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="alert-type">{type_name}</div>
            <h1>{title}</h1>
        </div>
        <div class="content">
            <p>{message.replace(chr(10), '<br>')}</p>
        </div>
        <div class="footer">
            🤖 Investment Tracker 알림 시스템
        </div>
    </div>
</body>
</html>
""".strip()

        return self.send_email(
            to_email=to_email,
            subject=subject,
            body=text_body,
            html_body=html_body,
        )

    def test_connection(self) -> bool:
        """
        SMTP 연결 테스트.

        Returns:
            연결 성공 여부
        """
        if not self.is_configured:
            raise ValueError("이메일 SMTP 설정이 완료되지 않았습니다.")

        try:
            with self._create_smtp_connection() as smtp:
                smtp.noop()
            logger.info("이메일 SMTP 연결 테스트 성공")
            return True
        except Exception as e:
            logger.error(f"이메일 SMTP 연결 테스트 실패: {e}")
            raise


# 싱글톤 인스턴스
_email_client: Optional[EmailClient] = None


def get_email_client() -> EmailClient:
    """이메일 클라이언트 싱글톤 반환."""
    global _email_client
    if _email_client is None:
        _email_client = EmailClient()
    return _email_client
