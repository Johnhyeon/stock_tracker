"""텔레그램 세션 인증 스크립트.

이 스크립트를 실행하여 Telethon 세션 파일을 생성합니다.
한 번만 실행하면 이후에는 자동으로 인증됩니다.

사용법:
    cd backend
    source venv/bin/activate
    python scripts/telegram_auth.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from telethon import TelegramClient
from core.config import get_settings


async def main():
    settings = get_settings()

    if not settings.telegram_api_id or not settings.telegram_api_hash:
        print("오류: TELEGRAM_API_ID와 TELEGRAM_API_HASH가 설정되지 않았습니다.")
        print(".env 파일에 다음을 추가해주세요:")
        print("  TELEGRAM_API_ID=your_api_id")
        print("  TELEGRAM_API_HASH=your_api_hash")
        return

    print("=" * 50)
    print("텔레그램 인증 스크립트")
    print("=" * 50)
    print(f"API ID: {settings.telegram_api_id}")
    print(f"세션 이름: {settings.telegram_session_name}")
    print()

    # 세션 파일 경로 (backend 폴더에 생성됨)
    session_path = Path(__file__).parent.parent / settings.telegram_session_name

    client = TelegramClient(
        str(session_path),
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )

    await client.start()

    me = await client.get_me()
    print()
    print("=" * 50)
    print(f"인증 성공!")
    print(f"계정: {me.first_name} (@{me.username})")
    print(f"세션 파일: {session_path}.session")
    print("=" * 50)
    print()
    print("이제 백엔드를 재시작하면 텔레그램 모니터링이 작동합니다.")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
