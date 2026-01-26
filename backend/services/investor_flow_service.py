"""투자자 수급 분석 서비스."""
import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert

from models import StockInvestorFlow
from integrations.kis.client import get_kis_client

logger = logging.getLogger(__name__)


class InvestorFlowService:
    """투자자별 수급 데이터 수집 및 분석 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.kis_client = get_kis_client()

    async def _get_latest_flow_date(self) -> Optional[date]:
        """DB에 저장된 가장 최신 수급 데이터 날짜 조회."""
        from sqlalchemy import func
        stmt = select(func.max(StockInvestorFlow.flow_date))
        result = await self.db.execute(stmt)
        return result.scalar()

    async def collect_investor_flow(
        self,
        stock_codes: list[str],
        stock_names: Optional[dict[str, str]] = None,
        days: int = 30,
        force_full: bool = False,
    ) -> dict:
        """여러 종목의 투자자 수급 데이터 수집 및 저장.

        기존 데이터가 있으면 최근 3일만 수집 (속도 최적화),
        없으면 최대 30일치 수집.

        Args:
            stock_codes: 종목코드 리스트
            stock_names: 종목코드 -> 종목명 매핑 (선택)
            days: 수집할 일수 (최대 30일, 기존 데이터 없을 때만 적용)
            force_full: True면 기존 데이터와 관계없이 전체 기간 수집

        Returns:
            {"collected_count": N, "failed_count": M, "records_saved": R, "fetch_days": D}
        """
        collected_stocks = 0
        failed_stocks = 0
        records_saved = 0

        # 기존 데이터 유무 확인 (force_full이 아닐 때만)
        fetch_days = days
        if not force_full:
            latest_date = await self._get_latest_flow_date()
            if latest_date:
                # 기존 데이터가 있으면 최근 3일만 수집
                fetch_days = 3
                logger.info(f"기존 데이터 있음 (최신: {latest_date}), {fetch_days}일치만 수집")
            else:
                logger.info(f"기존 데이터 없음, {days}일치 전체 수집")

        # KIS API로 데이터 조회
        try:
            flow_data = await self.kis_client.get_multiple_investor_trading(
                stock_codes,
                days=fetch_days,
                max_concurrent=3,
                delay_between=0.2,
            )
        except Exception as e:
            logger.error(f"수급 데이터 조회 실패: {e}")
            return {"collected_count": 0, "failed_count": len(stock_codes), "records_saved": 0, "fetch_days": fetch_days}

        # DB에 저장 (종목별로 여러 일치 데이터)
        for code, daily_data_list in flow_data.items():
            if not daily_data_list:
                failed_stocks += 1
                continue

            stock_name = (stock_names or {}).get(code, "")
            stock_saved = 0

            for daily_data in daily_data_list:
                try:
                    flow_date_str = daily_data.get("date", "")
                    if not flow_date_str:
                        continue

                    flow_date = date.fromisoformat(flow_date_str)
                    foreign_net = daily_data.get("foreign_net", 0)
                    institution_net = daily_data.get("institution_net", 0)
                    individual_net = daily_data.get("individual_net", 0)
                    # 순매수금액
                    foreign_net_amount = daily_data.get("foreign_net_amount", 0)
                    institution_net_amount = daily_data.get("institution_net_amount", 0)
                    individual_net_amount = daily_data.get("individual_net_amount", 0)

                    # 수급 점수 계산
                    flow_score = self._calculate_flow_score(foreign_net, institution_net)

                    stmt = insert(StockInvestorFlow).values(
                        stock_code=code,
                        stock_name=stock_name,
                        flow_date=flow_date,
                        foreign_net=foreign_net,
                        institution_net=institution_net,
                        individual_net=individual_net,
                        foreign_net_amount=foreign_net_amount,
                        institution_net_amount=institution_net_amount,
                        individual_net_amount=individual_net_amount,
                        flow_score=flow_score,
                    ).on_conflict_do_update(
                        index_elements=['stock_code', 'flow_date'],
                        set_={
                            'stock_name': stock_name,
                            'foreign_net': foreign_net,
                            'institution_net': institution_net,
                            'individual_net': individual_net,
                            'foreign_net_amount': foreign_net_amount,
                            'institution_net_amount': institution_net_amount,
                            'individual_net_amount': individual_net_amount,
                            'flow_score': flow_score,
                        }
                    )

                    await self.db.execute(stmt)
                    stock_saved += 1

                except Exception as e:
                    logger.warning(f"수급 데이터 저장 실패 ({code}, {daily_data.get('date')}): {e}")

            if stock_saved > 0:
                collected_stocks += 1
                records_saved += stock_saved
            else:
                failed_stocks += 1

        await self.db.commit()

        logger.info(f"수급 데이터 수집 완료: {collected_stocks}개 종목, {records_saved}개 레코드 저장 ({fetch_days}일치)")
        return {
            "collected_count": collected_stocks,
            "failed_count": failed_stocks,
            "records_saved": records_saved,
            "fetch_days": fetch_days,
        }

    def _calculate_flow_score(
        self,
        foreign_net: int,
        institution_net: int,
    ) -> float:
        """개별 종목 수급 점수 계산 (0-100).

        외국인 + 기관 순매수가 모두 양수이면 높은 점수.
        기준: 1만주당 25점 (기존 10만주 → 완화)
        """
        score = 50.0  # 기본 점수

        # 외국인 순매수 (최대 ±25점)
        if foreign_net > 0:
            score += min(foreign_net / 10000, 25)  # 1만주당 25점 추가
        elif foreign_net < 0:
            score += max(foreign_net / 10000, -25)

        # 기관 순매수 (최대 ±25점)
        if institution_net > 0:
            score += min(institution_net / 10000, 25)
        elif institution_net < 0:
            score += max(institution_net / 10000, -25)

        return max(0, min(100, score))

    async def recalculate_all_flow_scores(self) -> dict:
        """DB에 저장된 모든 수급 데이터의 flow_score 재계산.

        점수 계산 기준이 변경되었을 때 사용.
        """
        stmt = select(StockInvestorFlow)
        result = await self.db.execute(stmt)
        flows = result.scalars().all()

        updated = 0
        for flow in flows:
            new_score = self._calculate_flow_score(flow.foreign_net, flow.institution_net)
            if flow.flow_score != new_score:
                flow.flow_score = new_score
                updated += 1

        await self.db.commit()
        return {"total": len(flows), "updated": updated}

    async def get_theme_investor_flow(
        self,
        stock_codes: list[str],
        days: int = 5,
    ) -> dict:
        """테마 내 종목들의 수급 현황 조회.

        Args:
            stock_codes: 종목코드 리스트
            days: 조회 기간 (일)

        Returns:
            {
                "foreign_net_sum": int,    # 외국인 순매수 합계
                "institution_net_sum": int, # 기관 순매수 합계
                "positive_foreign": int,    # 외국인 순매수 종목 수
                "positive_institution": int, # 기관 순매수 종목 수
                "total_stocks": int,        # 전체 종목 수
                "avg_flow_score": float,    # 평균 수급 점수
            }
        """
        if not stock_codes:
            return {
                "foreign_net_sum": 0,
                "institution_net_sum": 0,
                "positive_foreign": 0,
                "positive_institution": 0,
                "total_stocks": 0,
                "avg_flow_score": 0,
            }

        start_date = date.today() - timedelta(days=days)

        stmt = (
            select(StockInvestorFlow)
            .where(
                and_(
                    StockInvestorFlow.stock_code.in_(stock_codes),
                    StockInvestorFlow.flow_date >= start_date,
                )
            )
        )

        result = await self.db.execute(stmt)
        flows = result.scalars().all()

        if not flows:
            return {
                "foreign_net_sum": 0,
                "institution_net_sum": 0,
                "positive_foreign": 0,
                "positive_institution": 0,
                "total_stocks": len(stock_codes),
                "avg_flow_score": 0,
            }

        # 종목별로 최신 데이터만 사용
        latest_flows = {}
        for f in flows:
            if f.stock_code not in latest_flows or f.flow_date > latest_flows[f.stock_code].flow_date:
                latest_flows[f.stock_code] = f

        foreign_net_sum = sum(f.foreign_net for f in latest_flows.values())
        institution_net_sum = sum(f.institution_net for f in latest_flows.values())
        positive_foreign = sum(1 for f in latest_flows.values() if f.foreign_net > 0)
        positive_institution = sum(1 for f in latest_flows.values() if f.institution_net > 0)
        avg_flow_score = sum(f.flow_score for f in latest_flows.values()) / len(latest_flows) if latest_flows else 0

        return {
            "foreign_net_sum": foreign_net_sum,
            "institution_net_sum": institution_net_sum,
            "positive_foreign": positive_foreign,
            "positive_institution": positive_institution,
            "total_stocks": len(stock_codes),
            "avg_flow_score": round(avg_flow_score, 1),
        }

    async def calculate_theme_flow_score(
        self,
        stock_codes: list[str],
        days: int = 5,
    ) -> dict:
        """테마의 수급 점수 계산 (15점 만점).

        Args:
            stock_codes: 테마 내 종목코드 리스트
            days: 조회 기간 (일)

        Returns:
            {"score": float, ...flow_data}
        """
        flow_data = await self.get_theme_investor_flow(stock_codes, days)

        if flow_data["total_stocks"] == 0:
            flow_data["score"] = 0
            return flow_data

        # 점수 계산 (15점 만점)
        score = 0.0

        # 1. 평균 수급 점수 기반 (0-7점)
        # avg_flow_score는 0-100 범위, 50이 중립
        # 0~100 전체 범위를 0~7점으로 매핑 (음수 없음)
        avg_score = flow_data["avg_flow_score"]
        score += (avg_score / 100) * 7

        # 2. 외국인 순매수 종목 비율 (0-5점)
        foreign_ratio = flow_data["positive_foreign"] / flow_data["total_stocks"] if flow_data["total_stocks"] > 0 else 0
        score += foreign_ratio * 5

        # 3. 기관 순매수 종목 비율 (0-3점)
        inst_ratio = flow_data["positive_institution"] / flow_data["total_stocks"] if flow_data["total_stocks"] > 0 else 0
        score += inst_ratio * 3

        flow_data["score"] = round(max(0, min(15, score)), 1)
        return flow_data

    async def get_stock_flow_history(
        self,
        stock_code: str,
        days: int = 30,
    ) -> list[dict]:
        """종목의 수급 히스토리 조회.

        Args:
            stock_code: 종목코드
            days: 조회 기간 (일)

        Returns:
            일별 수급 데이터 리스트
        """
        start_date = date.today() - timedelta(days=days)

        stmt = (
            select(StockInvestorFlow)
            .where(
                and_(
                    StockInvestorFlow.stock_code == stock_code,
                    StockInvestorFlow.flow_date >= start_date,
                )
            )
            .order_by(StockInvestorFlow.flow_date.desc())
        )

        result = await self.db.execute(stmt)
        flows = result.scalars().all()

        return [
            {
                "flow_date": f.flow_date.isoformat(),
                "foreign_net": f.foreign_net,
                "institution_net": f.institution_net,
                "individual_net": f.individual_net,
                "flow_score": f.flow_score,
            }
            for f in flows
        ]

    async def get_theme_stock_flows(
        self,
        stock_codes: list[str],
        days: int = 5,
    ) -> list[dict]:
        """테마 내 종목들의 개별 수급 데이터 조회.

        Args:
            stock_codes: 종목코드 리스트
            days: 조회 기간 (일)

        Returns:
            개별 종목별 수급 데이터 리스트
        """
        if not stock_codes:
            return []

        start_date = date.today() - timedelta(days=days)

        stmt = (
            select(StockInvestorFlow)
            .where(
                and_(
                    StockInvestorFlow.stock_code.in_(stock_codes),
                    StockInvestorFlow.flow_date >= start_date,
                )
            )
            .order_by(StockInvestorFlow.flow_date.desc())
        )

        result = await self.db.execute(stmt)
        flows = result.scalars().all()

        if not flows:
            return []

        # 종목별로 최신 데이터만 사용
        latest_flows = {}
        for f in flows:
            if f.stock_code not in latest_flows or f.flow_date > latest_flows[f.stock_code].flow_date:
                latest_flows[f.stock_code] = f

        # 외국인 순매수 기준으로 정렬하여 반환
        stock_flows = []
        for f in sorted(latest_flows.values(), key=lambda x: x.foreign_net, reverse=True):
            stock_flows.append({
                "stock_code": f.stock_code,
                "stock_name": f.stock_name or "",
                "flow_date": f.flow_date.isoformat(),
                "foreign_net": f.foreign_net,
                "institution_net": f.institution_net,
                "individual_net": f.individual_net,
                "flow_score": f.flow_score,
            })

        return stock_flows
