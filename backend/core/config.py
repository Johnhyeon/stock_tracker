from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    database_url: str = "postgresql://tracker:tracker123@localhost:5432/investment_tracker"
    cors_origins: str = "http://localhost:5173"

    # KIS API 설정
    kis_app_key: Optional[str] = None
    kis_app_secret: Optional[str] = None
    kis_account_no: Optional[str] = None  # 계좌번호 (예: "50123456-01")
    kis_is_mock: bool = True  # True: 모의투자, False: 실전투자

    # DART API 설정
    dart_api_key: Optional[str] = None

    # YouTube Data API 설정
    youtube_api_key: Optional[str] = None
    youtube_channel_ids: str = ""  # 쉼표로 구분된 채널 ID 목록

    # 스케줄러 설정
    scheduler_enabled: bool = True
    price_update_interval_minutes: int = 5
    disclosure_check_interval_minutes: int = 30
    youtube_check_interval_hours: int = 6

    # 피처 플래그 (false이면 해당 기능 관련 UI/데이터 전체 비활성화)
    telegram_feature_enabled: bool = True
    expert_feature_enabled: bool = True

    # Telegram Bot 설정 (알림 발송용)
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None  # 기본 수신 채팅 ID

    # Telegram MTProto API 설정 (채널 모니터링용)
    telegram_api_id: Optional[int] = None  # my.telegram.org에서 발급
    telegram_api_hash: Optional[str] = None  # my.telegram.org에서 발급
    telegram_session_name: str = "stock_monitor"  # 세션 파일명
    telegram_monitor_interval_minutes: int = 5  # 모니터링 간격 (분)

    # Email 설정
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[str] = None
    smtp_use_tls: bool = True

    # 알림 설정
    alert_check_interval_minutes: int = 5

    # Google Gemini AI 설정
    gemini_api_key: Optional[str] = None

    # 네이버 검색 API 설정
    naver_client_id: Optional[str] = None
    naver_client_secret: Optional[str] = None

    # 외부 데이터 파일 경로
    mentions_file_path: str = "/home/hyeon/project/88_bot/mentions.json"

    # 텔레그램 아이디어 채널 ID
    telegram_idea_my_channel_id: int = 5008508687
    telegram_idea_others_channel_id: int = 5132891681

    # GitHub Gist 중계 (라파 → Gist → 서버)
    mentions_gist_id: Optional[str] = None       # Gist ID
    mentions_gist_token: Optional[str] = None    # GitHub Personal Access Token

    # 일일 리포트 발송 설정 (별도 텔레그램 계정)
    daily_report_channel: Optional[str] = None  # @username 또는 채널ID
    daily_report_api_id: Optional[int] = None
    daily_report_api_hash: Optional[str] = None
    daily_report_session_name: str = "daily_report"  # 리포트 전용 세션 파일

    # 테마 셋업 스케줄러 설정
    theme_news_check_interval_hours: int = 6
    theme_setup_check_interval_hours: int = 6

    class Config:
        env_file = ".env"
        extra = "allow"

    @property
    def kis_base_url(self) -> str:
        if self.kis_is_mock:
            return "https://openapivts.koreainvestment.com:29443"
        return "https://openapi.koreainvestment.com:9443"

    @property
    def youtube_channel_id_list(self) -> list[str]:
        if not self.youtube_channel_ids:
            return []
        return [cid.strip() for cid in self.youtube_channel_ids.split(",") if cid.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
