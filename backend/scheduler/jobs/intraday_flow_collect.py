"""장중 투자자 수급 데이터 수집 작업.

장중 30분마다 실행하여 당일 수급 데이터를 수집합니다.
최근 수급 상위/하위 종목 100개를 대상으로 당일 데이터만 수집합니다.
18:30 정규 수집이 최종 데이터로 대체합니다.
"""
import logging

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert

from core.database import async_session_maker
from core.timezone import now_kst, today_kst
from models import StockInvestorFlow
from integrations.kis.client import get_kis_client
from services.theme_map_service import get_theme_map_service
from scheduler.job_tracker import track_job_execution

logger = logging.getLogger(__name__)


@track_job_execution("intraday_flow_collect")
async def collect_intraday_investor_flow() -> dict:
    """장중 수급 데이터 수집.

    최근 수급 상위/하위 100종목의 당일 수급을 KIS API로 조회하여
    stock_investor_flows 테이블에 upsert합니다.
    """
    result = {
        "collected_count": 0,
        "failed_count": 0,
        "timestamp": now_kst().isoformat(),
    }

    kis_client = get_kis_client()

    # 최근 수급 데이터가 있는 종목 중 상위/하위 100개 추출
    async with async_session_maker() as db:
        try:
            # 최근 3일간 외국인+기관 순매수량 합계 기준 상위/하위
            recent_date = today_kst()

            stmt = (
                select(
                    StockInvestorFlow.stock_code,
                    StockInvestorFlow.stock_name,
                    func.sum(StockInvestorFlow.foreign_net_amount + StockInvestorFlow.institution_net_amount).label("total_amount"),
                )
                .where(StockInvestorFlow.flow_date >= recent_date.replace(day=max(1, recent_date.day - 5)))
                .group_by(StockInvestorFlow.stock_code, StockInvestorFlow.stock_name)
                .order_by(func.abs(func.sum(StockInvestorFlow.foreign_net_amount + StockInvestorFlow.institution_net_amount)).desc())
                .limit(100)
            )
            db_result = await db.execute(stmt)
            target_stocks = {row.stock_code: row.stock_name or "" for row in db_result.fetchall()}

            if not target_stocks:
                # DB에 데이터가 없으면 테마맵에서 주요 종목 추출
                tms = get_theme_map_service()
                all_stocks = {}
                for stocks in tms.get_all_themes().values():
                    for stock in stocks:
                        code = stock.get("code")
                        name = stock.get("name", "")
                        if code:
                            all_stocks[code] = name
                # 처음 100개만
                target_stocks = dict(list(all_stocks.items())[:100])

            stock_codes = list(target_stocks.keys())
            logger.info(f"장중 수급 수집 대상: {len(stock_codes)}종목")

            # KIS API로 당일 데이터 조회 (1일치만)
            flow_data = await kis_client.get_multiple_investor_trading(
                stock_codes,
                days=1,
                max_concurrent=3,
                delay_between=0.15,
            )

            # DB에 upsert
            today = today_kst()
            saved = 0

            for code, daily_list in flow_data.items():
                if not daily_list:
                    result["failed_count"] += 1
                    continue

                # 당일 데이터만 사용
                for daily in daily_list:
                    flow_date_str = daily.get("date", "")
                    if not flow_date_str:
                        continue

                    flow_date = date.fromisoformat(flow_date_str)
                    if flow_date != today:
                        continue

                    foreign_net = daily.get("foreign_net", 0)
                    institution_net = daily.get("institution_net", 0)
                    individual_net = daily.get("individual_net", 0)
                    foreign_net_amount = daily.get("foreign_net_amount", 0)
                    institution_net_amount = daily.get("institution_net_amount", 0)
                    individual_net_amount = daily.get("individual_net_amount", 0)

                    # 수급 점수 계산
                    score = 50.0
                    if foreign_net > 0:
                        score += min(foreign_net / 10000, 25)
                    elif foreign_net < 0:
                        score += max(foreign_net / 10000, -25)
                    if institution_net > 0:
                        score += min(institution_net / 10000, 25)
                    elif institution_net < 0:
                        score += max(institution_net / 10000, -25)
                    score = max(0, min(100, score))

                    stmt = insert(StockInvestorFlow).values(
                        stock_code=code,
                        stock_name=target_stocks.get(code, ""),
                        flow_date=flow_date,
                        foreign_net=foreign_net,
                        institution_net=institution_net,
                        individual_net=individual_net,
                        foreign_net_amount=foreign_net_amount,
                        institution_net_amount=institution_net_amount,
                        individual_net_amount=individual_net_amount,
                        flow_score=score,
                    ).on_conflict_do_update(
                        index_elements=['stock_code', 'flow_date'],
                        set_={
                            'foreign_net': foreign_net,
                            'institution_net': institution_net,
                            'individual_net': individual_net,
                            'foreign_net_amount': foreign_net_amount,
                            'institution_net_amount': institution_net_amount,
                            'individual_net_amount': individual_net_amount,
                            'flow_score': score,
                        }
                    )
                    await db.execute(stmt)
                    saved += 1
                    break  # 당일 데이터 하나만

                result["collected_count"] += 1

            await db.commit()
            result["records_saved"] = saved

            logger.info(
                f"장중 수급 수집 완료: {result['collected_count']}개 종목, "
                f"{saved}개 레코드 저장"
            )

        except Exception as e:
            logger.error(f"장중 수급 수집 실패: {e}")
            result["error"] = str(e)

    return result
