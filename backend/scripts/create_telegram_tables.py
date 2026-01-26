"""텔레그램 모니터링 테이블 생성 스크립트."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import async_engine


async def create_tables():
    """텔레그램 관련 테이블 생성."""

    # 각 SQL 문을 개별로 실행
    statements = [
        # telegram_channels 테이블
        """
        CREATE TABLE IF NOT EXISTS telegram_channels (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            channel_id BIGINT UNIQUE NOT NULL,
            channel_name VARCHAR(200) NOT NULL,
            channel_username VARCHAR(100),
            is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            last_message_id BIGINT NOT NULL DEFAULT 0
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_telegram_channels_enabled ON telegram_channels(is_enabled)",
        "CREATE INDEX IF NOT EXISTS ix_telegram_channels_channel_id ON telegram_channels(channel_id)",

        # telegram_keyword_matches 테이블
        """
        CREATE TABLE IF NOT EXISTS telegram_keyword_matches (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            channel_id BIGINT NOT NULL,
            channel_name VARCHAR(200) NOT NULL,
            message_id BIGINT NOT NULL,
            message_text VARCHAR(1000) NOT NULL,
            message_date TIMESTAMP NOT NULL,
            matched_keyword VARCHAR(100) NOT NULL,
            stock_code VARCHAR(10),
            idea_id UUID,
            notification_sent BOOLEAN NOT NULL DEFAULT FALSE
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_telegram_keyword_matches_created ON telegram_keyword_matches(created_at)",
        "CREATE INDEX IF NOT EXISTS ix_telegram_keyword_matches_keyword ON telegram_keyword_matches(matched_keyword)",
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_telegram_keyword_matches_channel_msg
            ON telegram_keyword_matches(channel_id, message_id)
        """,
    ]

    async with async_engine.begin() as conn:
        print("텔레그램 테이블 생성 중...")
        for i, sql in enumerate(statements):
            await conn.execute(text(sql.strip()))
            print(f"  [{i+1}/{len(statements)}] 완료")

    print("\n✓ 모든 테이블이 생성되었습니다.")


if __name__ == "__main__":
    asyncio.run(create_tables())
