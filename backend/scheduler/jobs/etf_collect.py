"""ETF OHLCV 수집 스케줄러 작업."""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from pykrx import stock
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.config import get_settings
from core.database import Base
from models.etf_ohlcv import EtfOHLCV

logger = logging.getLogger(__name__)


def load_etf_codes() -> list[dict]:
    """theme_etf_map.json에서 모든 ETF 코드 로드."""
    etf_map_path = Path(__file__).parent.parent.parent / "data" / "theme_etf_map.json"

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
    """pykrx로 ETF OHLCV 데이터 조회."""
    try:
        df = stock.get_etf_ohlcv_by_date(start_date, end_date, etf_code)

        if df.empty:
            return []

        result = []
        prev_close = None

        for date_idx, row in df.iterrows():
            date_str = date_idx.strftime("%Y-%m-%d")
            close = int(row["종가"])

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
        logger.warning(f"ETF OHLCV 조회 실패 ({etf_code}): {e}")
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


async def collect_etf_ohlcv_daily():
    """ETF OHLCV 일별 수집.

    매일 장 마감 후 실행되어 당일 데이터를 수집합니다.
    """
    logger.info("ETF OHLCV 일별 수집 시작")

    settings = get_settings()
    engine = create_engine(settings.database_url)

    # 테이블 존재 확인
    Base.metadata.create_all(bind=engine, tables=[EtfOHLCV.__table__])

    # ETF 목록 로드
    etf_list = load_etf_codes()
    logger.info(f"수집 대상 ETF: {len(etf_list)}개")

    # 최근 5일치 수집 (장 마감 후 당일 + 누락분 보정)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    success_count = 0
    fail_count = 0
    total_records = 0

    for etf in etf_list:
        code = etf["code"]
        name = etf["name"]

        try:
            ohlcv = get_etf_ohlcv_pykrx(code, start_str, end_str)

            if ohlcv:
                saved = save_to_db(engine, code, name, ohlcv)
                total_records += saved
                success_count += 1
            else:
                fail_count += 1

        except Exception as e:
            logger.warning(f"{name}({code}) 수집 실패: {e}")
            fail_count += 1

    logger.info(f"ETF OHLCV 수집 완료: 성공 {success_count}, 실패 {fail_count}, 레코드 {total_records}")
