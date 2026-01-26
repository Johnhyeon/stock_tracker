#!/usr/bin/env python3
"""CSV 파일에서 종목/ETF 데이터를 DB에 로드하는 스크립트"""

import sys
import csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import SessionLocal, engine, Base
from models.stock import Stock


def load_stocks_csv(filepath: str, db_session):
    """종목 CSV 로드"""
    count = 0
    with open(filepath, 'r', encoding='euc-kr') as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row['단축코드'].strip().strip('"')
            name = row['한글 종목약명'].strip().strip('"')
            market = row['시장구분'].strip().strip('"')
            stock_type = row.get('주식종류', '').strip().strip('"')

            if not code or not name:
                continue

            # KOSDAQ GLOBAL -> KOSDAQ으로 통일
            if 'KOSDAQ' in market:
                market = 'KOSDAQ'

            stock = Stock(
                code=code,
                name=name,
                market=market,
                stock_type=stock_type or '보통주'
            )
            db_session.merge(stock)
            count += 1

            if count % 500 == 0:
                print(f"  {count}개 처리 중...")

    return count


def load_etf_csv(filepath: str, db_session):
    """ETF CSV 로드"""
    count = 0
    with open(filepath, 'r', encoding='euc-kr') as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row['단축코드'].strip().strip('"')
            name = row['한글종목약명'].strip().strip('"')

            if not code or not name:
                continue

            stock = Stock(
                code=code,
                name=name,
                market='ETF',
                stock_type='ETF'
            )
            db_session.merge(stock)
            count += 1

            if count % 500 == 0:
                print(f"  {count}개 처리 중...")

    return count


def main():
    # 테이블 생성
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 종목 로드
        stocks_path = "/home/hyeon/project/88_bot/data/국내상장종목.csv"
        print(f"종목 데이터 로드 중: {stocks_path}")
        stock_count = load_stocks_csv(stocks_path, db)
        print(f"  종목 {stock_count}개 로드 완료")

        # ETF 로드
        etf_path = "/home/hyeon/project/88_bot/data/국내상장ETF.csv"
        print(f"ETF 데이터 로드 중: {etf_path}")
        etf_count = load_etf_csv(etf_path, db)
        print(f"  ETF {etf_count}개 로드 완료")

        db.commit()
        print(f"\n총 {stock_count + etf_count}개 데이터 저장 완료!")

    except Exception as e:
        db.rollback()
        print(f"오류 발생: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
