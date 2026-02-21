"""KST 타임존 유틸리티.

서버가 UTC로 동작하더라도 항상 한국 시간(KST) 기준으로 동작하도록 보장.
모든 모듈에서 datetime.now() 대신 now_kst()를, date.today() 대신 today_kst()를 사용할 것.
"""
from datetime import datetime, date, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
    KST = ZoneInfo("Asia/Seoul")
except (ImportError, KeyError):
    # Windows에서 tzdata 패키지 없을 때 fallback
    KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    """현재 한국 시간 반환."""
    return datetime.now(KST)


def today_kst() -> date:
    """오늘 한국 날짜 반환."""
    return datetime.now(KST).date()
