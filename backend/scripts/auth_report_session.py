"""일일 리포트 전용 텔레그램 세션 인증 스크립트.

별도 텔레그램 계정으로 채널에 리포트를 발송하기 위한 세션을 생성합니다.
한 번만 실행하면 이후에는 자동으로 인증됩니다.

사용법:
    cd backend
    python scripts/auth_report_session.py
"""
import asyncio
import os
import sys
from pathlib import Path

# .env 파일에서 설정 직접 로드 (venv 불필요)
def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    config = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()
    return config


async def main():
    config = load_env()

    api_id = config.get("DAILY_REPORT_API_ID")
    api_hash = config.get("DAILY_REPORT_API_HASH")
    channel = config.get("DAILY_REPORT_CHANNEL")
    session_name = config.get("DAILY_REPORT_SESSION_NAME", "daily_report")

    if not api_id or not api_hash:
        print("오류: DAILY_REPORT_API_ID와 DAILY_REPORT_API_HASH가 .env에 없습니다.")
        return

    from telethon import TelegramClient

    print("=" * 50)
    print("일일 리포트 전용 텔레그램 인증")
    print("=" * 50)
    print(f"API ID: {api_id}")
    print(f"세션 이름: {session_name}")
    print(f"발송 채널: {channel}")
    print()

    session_path = Path(__file__).parent.parent / session_name

    client = TelegramClient(
        str(session_path),
        int(api_id),
        api_hash,
    )

    await client.start()

    me = await client.get_me()
    print()
    print("=" * 50)
    print(f"인증 성공!")
    print(f"계정: {me.first_name} (@{me.username})")
    print(f"세션 파일: {session_path}.session")
    print("=" * 50)

    # 채널 접근 테스트
    if channel:
        try:
            try:
                channel_id = int(channel)
            except ValueError:
                channel_id = channel

            entity = await client.get_entity(channel_id)
            title = getattr(entity, "title", str(entity))
            print(f"채널 확인: {title}")
            print()
            print("모든 준비 완료! 서버를 재시작하면 일일 리포트가 자동 발송됩니다.")
        except Exception as e:
            print(f"채널 접근 실패: {e}")
            print("채널에 이 계정이 관리자로 등록되어 있는지 확인하세요.")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
