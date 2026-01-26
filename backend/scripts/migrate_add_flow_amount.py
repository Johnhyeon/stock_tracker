"""수급 테이블에 금액 컬럼 추가 마이그레이션.

실행: cd backend && python scripts/migrate_add_flow_amount.py
"""
import asyncio
import os
import sys

# 상위 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import async_engine


async def migrate():
    """stock_investor_flows 테이블에 금액 컬럼 추가."""

    async with async_engine.begin() as conn:
        # 컬럼 존재 여부 확인
        check_sql = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'stock_investor_flows'
            AND column_name = 'foreign_net_amount'
        """)
        result = await conn.execute(check_sql)
        exists = result.fetchone()

        if exists:
            print("금액 컬럼이 이미 존재합니다.")
            return

        # 컬럼 추가
        alter_sql = text("""
            ALTER TABLE stock_investor_flows
            ADD COLUMN foreign_net_amount BIGINT DEFAULT 0 NOT NULL,
            ADD COLUMN institution_net_amount BIGINT DEFAULT 0 NOT NULL,
            ADD COLUMN individual_net_amount BIGINT DEFAULT 0 NOT NULL
        """)

        await conn.execute(alter_sql)
        print("금액 컬럼 3개 추가 완료:")
        print("  - foreign_net_amount (외국인 순매수금액)")
        print("  - institution_net_amount (기관 순매수금액)")
        print("  - individual_net_amount (개인 순매수금액)")
        print()
        print("기존 데이터 재수집이 필요합니다.")
        print("스케줄러가 18:30에 자동 수집하거나, 수동으로 수집해주세요.")


if __name__ == "__main__":
    asyncio.run(migrate())
