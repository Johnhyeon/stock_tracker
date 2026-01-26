#!/usr/bin/env python
"""ETF OHLCV 데이터 수집 스크립트.

pykrx를 사용하여 테마별 대표 ETF의 일봉 데이터를 수집합니다.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from pykrx import stock
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.config import get_settings
from models.etf_ohlcv import EtfOHLCV
from core.database import Base


def load_etf_codes() -> list[dict]:
    """theme_etf_map.json에서 모든 ETF 코드 로드."""
    etf_map_path = Path(__file__).parent.parent / "data" / "theme_etf_map.json"

    with open(etf_map_path, "r", encoding="utf-8") as f:
        theme_etf_map = json.load(f)

    etf_list = []
    seen_codes = set()

    for theme_name, theme_data in theme_etf_map.items():
        for etf in theme_data.get("etfs", []):
            code = etf.get("code")
            if code and code not in seen_codes:
                seen_codes.add(code)
                etf_list.append({
                    "code": code,
                    "name": etf.get("name", ""),
                    "theme": theme_name,
                    "is_primary": etf.get("is_primary", False),
                })

    return etf_list


def get_etf_ohlcv_pykrx(etf_code: str, start_date: str, end_date: str) -> list[dict]:
    """pykrx로 ETF OHLCV 데이터 조회.

    Args:
        etf_code: ETF 종목코드
        start_date: 시작일 (YYYYMMDD)
        end_date: 종료일 (YYYYMMDD)

    Returns:
        OHLCV 데이터 리스트
    """
    try:
        df = stock.get_etf_ohlcv_by_date(start_date, end_date, etf_code)

        if df.empty:
            return []

        result = []
        prev_close = None

        for date_idx, row in df.iterrows():
            date_str = date_idx.strftime("%Y-%m-%d")
            close = int(row["종가"])

            # 등락률 계산
            change_rate = None
            if prev_close and prev_close > 0:
                change_rate = round((close - prev_close) / prev_close * 100, 2)

            result.append({
                "trade_date": date_str,
                "open": int(row["시가"]),
                "high": int(row["고가"]),
                "low": int(row["저가"]),
                "close": close,
                "volume": int(row["거래량"]),
                "trading_value": int(row["거래대금"]) if "거래대금" in row else None,
                "change_rate": change_rate,
            })

            prev_close = close

        return result

    except Exception as e:
        print(f"ETF OHLCV 조회 실패 ({etf_code}): {e}")
        return []


def save_to_db(engine, etf_code: str, etf_name: str, ohlcv_data: list[dict]) -> int:
    """OHLCV 데이터를 DB에 저장 (upsert)."""
    if not ohlcv_data:
        return 0

    saved_count = 0

    with engine.connect() as conn:
        for data in ohlcv_data:
            stmt = pg_insert(EtfOHLCV).values(
                etf_code=etf_code,
                etf_name=etf_name,
                trade_date=data["trade_date"],
                open_price=data["open"],
                high_price=data["high"],
                low_price=data["low"],
                close_price=data["close"],
                volume=data["volume"],
                trading_value=data.get("trading_value"),
                change_rate=data.get("change_rate"),
            ).on_conflict_do_update(
                index_elements=["etf_code", "trade_date"],
                set_={
                    "etf_name": etf_name,
                    "open_price": data["open"],
                    "high_price": data["high"],
                    "low_price": data["low"],
                    "close_price": data["close"],
                    "volume": data["volume"],
                    "trading_value": data.get("trading_value"),
                    "change_rate": data.get("change_rate"),
                }
            )
            conn.execute(stmt)
            saved_count += 1

        conn.commit()

    return saved_count


def main(days: int = 365):
    """메인 함수.

    Args:
        days: 수집할 기간 (일 수, 기본 1년)
    """
    print(f"=== ETF OHLCV 수집 시작 ({days}일) ===\n")

    # DB 연결
    settings = get_settings()
    engine = create_engine(settings.database_url)

    # 테이블 생성 확인
    Base.metadata.create_all(bind=engine, tables=[EtfOHLCV.__table__])

    # ETF 목록 로드
    etf_list = load_etf_codes()
    print(f"수집 대상 ETF: {len(etf_list)}개\n")

    # 날짜 범위
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    success_count = 0
    fail_count = 0
    total_records = 0

    for i, etf in enumerate(etf_list, 1):
        code = etf["code"]
        name = etf["name"]
        theme = etf["theme"]

        print(f"[{i}/{len(etf_list)}] {name}({code}) - {theme}...", end=" ")

        try:
            # OHLCV 조회
            ohlcv = get_etf_ohlcv_pykrx(code, start_str, end_str)

            if ohlcv:
                # DB 저장
                saved = save_to_db(engine, code, name, ohlcv)
                total_records += saved
                print(f"{saved}일 저장")
                success_count += 1
            else:
                print("데이터 없음")
                fail_count += 1

        except Exception as e:
            print(f"실패: {e}")
            fail_count += 1

    print(f"\n=== 수집 완료 ===")
    print(f"성공: {success_count}개 ETF")
    print(f"실패: {fail_count}개 ETF")
    print(f"총 레코드: {total_records}개")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ETF OHLCV 수집")
    parser.add_argument("--days", type=int, default=365, help="수집 기간 (일)")

    args = parser.parse_args()
    main(days=args.days)
