"""투자자 수급 기능 마이그레이션 스크립트.

실행:
    cd /home/hyeon/project/my_stock/backend
    python scripts/migrate_investor_flow.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)


def run_migration():
    """마이그레이션 실행."""
    print("=== 투자자 수급 기능 마이그레이션 시작 ===")

    with engine.connect() as conn:
        # 1. stock_investor_flows 테이블 생성
        print("\n1. stock_investor_flows 테이블 생성...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS stock_investor_flows (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                stock_code VARCHAR(10) NOT NULL,
                stock_name VARCHAR(100),
                flow_date DATE NOT NULL,
                foreign_net BIGINT NOT NULL DEFAULT 0,
                institution_net BIGINT NOT NULL DEFAULT 0,
                individual_net BIGINT NOT NULL DEFAULT 0,
                flow_score FLOAT NOT NULL DEFAULT 0.0
            )
        """))
        print("   - 테이블 생성 완료")

        # 2. stock_investor_flows 인덱스 생성
        print("\n2. stock_investor_flows 인덱스 생성...")
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS ix_stock_flow_code_date
            ON stock_investor_flows (stock_code, flow_date)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_stock_flow_date
            ON stock_investor_flows (flow_date)
        """))
        print("   - 인덱스 생성 완료")

        # 3. theme_setups 테이블에 investor_flow_score 컬럼 추가
        print("\n3. theme_setups 테이블에 investor_flow_score 컬럼 추가...")
        try:
            conn.execute(text("""
                ALTER TABLE theme_setups
                ADD COLUMN IF NOT EXISTS investor_flow_score FLOAT NOT NULL DEFAULT 0.0
            """))
            print("   - 컬럼 추가 완료")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                print("   - 컬럼이 이미 존재합니다")
            else:
                raise e

        conn.commit()

    print("\n=== 마이그레이션 완료 ===")


if __name__ == "__main__":
    run_migration()
