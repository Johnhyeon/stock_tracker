#!/usr/bin/env python
"""봇 포맷 메시지 정리 스크립트.

📨 **작성자** | 날짜\n━━━━━━━━━━━━━━━━\n#종목명 내용...
형식의 메시지를 파싱해서 forward_from_name, original_date, message_text를 정리합니다.
"""
import asyncio
import re
import sys
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from core.database import async_session_maker
from models import TelegramIdea

# 봇 포워드 포맷 패턴
BOT_FORWARD_PATTERN = re.compile(
    r'^📨\s*\*\*(.+?)\*\*\s*\|\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*\n'
    r'[━─]+\s*\n',
    re.MULTILINE
)


def parse_bot_format(text: str) -> tuple[str, str | None, datetime | None]:
    """봇 포맷 메시지 파싱."""
    match = BOT_FORWARD_PATTERN.match(text)
    if not match:
        return text, None, None

    author_name = match.group(1).strip()
    date_str = match.group(2).strip()

    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    except ValueError:
        parsed_date = None

    clean_text = BOT_FORWARD_PATTERN.sub('', text).strip()
    return clean_text, author_name, parsed_date


async def cleanup_messages(dry_run: bool = True):
    """봇 포맷 메시지 정리."""
    async with async_session_maker() as db:
        # 봇 포맷 메시지 조회 (📨 로 시작하는 메시지)
        stmt = select(TelegramIdea).where(
            TelegramIdea.message_text.like('📨%')
        )
        result = await db.execute(stmt)
        ideas = list(result.scalars().all())

        print(f"봇 포맷 메시지 {len(ideas)}개 발견")

        updated_count = 0
        for idea in ideas:
            clean_text, author, parsed_date = parse_bot_format(idea.message_text)

            if author:
                print(f"\n[ID: {idea.id}]")
                print(f"  기존 forward_from_name: {idea.forward_from_name}")
                print(f"  → 새 forward_from_name: {author}")
                print(f"  기존 original_date: {idea.original_date}")
                print(f"  → 새 original_date: {parsed_date}")
                print(f"  기존 message (first 100): {idea.message_text[:100]}")
                print(f"  → 새 message (first 100): {clean_text[:100]}")

                if not dry_run:
                    idea.message_text = clean_text
                    idea.forward_from_name = author
                    idea.is_forwarded = True
                    if parsed_date:
                        idea.original_date = parsed_date

                updated_count += 1

        if not dry_run:
            await db.commit()
            print(f"\n✅ {updated_count}개 메시지 업데이트 완료")
        else:
            print(f"\n[DRY RUN] {updated_count}개 메시지가 업데이트될 예정")
            print("실제 적용하려면 --apply 옵션을 사용하세요.")


async def main():
    dry_run = "--apply" not in sys.argv

    if dry_run:
        print("=== DRY RUN 모드 (변경 없음) ===\n")
    else:
        print("=== APPLY 모드 (DB 변경됨) ===\n")

    await cleanup_messages(dry_run=dry_run)


if __name__ == "__main__":
    asyncio.run(main())
