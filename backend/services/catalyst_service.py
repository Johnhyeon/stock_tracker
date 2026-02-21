"""Catalyst Tracker 서비스."""
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from core.timezone import now_kst, today_kst

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, update

from models.catalyst_event import CatalystEvent
from models.stock_news import StockNews
from models.stock_ohlcv import StockOHLCV
from models.stock_investor_flow import StockInvestorFlow
from models import Disclosure

logger = logging.getLogger(__name__)

# Gemini 429 등으로 분류 실패 시 키워드 기반 폴백
_KEYWORD_TYPE_MAP: list[tuple[str, list[str]]] = [
    ("earnings", ["실적", "매출", "영업이익", "순이익", "어닝", "흑자", "적자", "분기", "잠정실적", "컨센서스"]),
    ("contract", ["수주", "계약", "공급", "납품", "MOU", "협약", "입찰", "낙찰"]),
    ("policy", ["정책", "규제", "보조금", "지원금", "관세", "법안", "정부", "국회", "세제", "인허가"]),
    ("product", ["신제품", "신약", "FDA", "임상", "승인", "기술", "개발", "특허", "출시", "허가"]),
    ("management", ["인수", "합병", "M&A", "유상증자", "무상증자", "자사주", "대표이사", "경영권", "지분", "CB", "BW"]),
    ("theme", ["테마", "AI", "반도체", "2차전지", "로봇", "양자", "바이오", "방산", "원전", "우주"]),
]


def _classify_by_keywords(title: str, description: str = "") -> str:
    """뉴스 제목+설명에서 키워드 기반 카탈리스트 유형 판별."""
    text = f"{title} {description}"
    scores: dict[str, int] = {}
    for ctype, keywords in _KEYWORD_TYPE_MAP:
        for kw in keywords:
            if kw in text:
                scores[ctype] = scores.get(ctype, 0) + 1
    if not scores:
        return "other"
    return max(scores, key=scores.get)


class CatalystService:
    """카탈리스트(재료) 감지 및 추적 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def detect_new_catalysts(self, target_date: Optional[date] = None) -> int:
        """등락률 >= 3% + 뉴스/공시가 있는 종목에 CatalystEvent 생성.

        Args:
            target_date: 감지 대상 날짜. None이면 오늘.

        Returns:
            생성된 이벤트 수
        """
        check_date = target_date or today_kst()
        created_count = 0

        # 1. 해당 날짜 OHLCV 조회
        day_ohlcv_stmt = (
            select(StockOHLCV)
            .where(StockOHLCV.trade_date == check_date)
        )
        day_result = await self.db.execute(day_ohlcv_stmt)
        day_ohlcvs = day_result.scalars().all()

        if not day_ohlcvs:
            logger.info(f"카탈리스트 감지: {check_date} OHLCV 데이터 없음")
            return 0

        # 전일 데이터 조회를 위한 종목코드 수집
        stock_codes = [o.stock_code for o in day_ohlcvs]
        prev_date = check_date - timedelta(days=7)  # 최근 7일 내 직전 거래일
        prev_stmt = (
            select(StockOHLCV)
            .where(
                and_(
                    StockOHLCV.stock_code.in_(stock_codes),
                    StockOHLCV.trade_date < check_date,
                    StockOHLCV.trade_date >= prev_date,
                )
            )
            .order_by(StockOHLCV.stock_code, desc(StockOHLCV.trade_date))
        )
        prev_result = await self.db.execute(prev_stmt)
        prev_ohlcvs = prev_result.scalars().all()

        # 종목별 직전 종가 매핑
        prev_close_map: dict[str, int] = {}
        for p in prev_ohlcvs:
            if p.stock_code not in prev_close_map:
                prev_close_map[p.stock_code] = p.close_price

        # 3% 이상 변동 종목 필터
        movers = []
        for ohlcv in day_ohlcvs:
            prev_close = prev_close_map.get(ohlcv.stock_code)
            if not prev_close or prev_close == 0:
                continue
            change_pct = (ohlcv.close_price - prev_close) / prev_close * 100
            if abs(change_pct) >= 3.0:
                movers.append((ohlcv, round(change_pct, 2)))

        if not movers:
            logger.info(f"카탈리스트 감지: {check_date} 3% 이상 변동 종목 없음")
            return 0

        # 종목명 조회 (StockNews에서)
        name_stmt = (
            select(StockNews.stock_code, StockNews.stock_name)
            .where(StockNews.stock_code.in_([m[0].stock_code for m in movers]))
            .distinct(StockNews.stock_code)
        )
        name_result = await self.db.execute(name_stmt)
        name_map = {row[0]: row[1] for row in name_result.fetchall()}

        for ohlcv, change_pct in movers:
            code = ohlcv.stock_code

            # 이미 해당 날짜에 이벤트가 있으면 스킵
            existing_stmt = (
                select(func.count(CatalystEvent.id))
                .where(
                    and_(
                        CatalystEvent.stock_code == code,
                        CatalystEvent.event_date == check_date,
                    )
                )
            )
            existing_result = await self.db.execute(existing_stmt)
            if (existing_result.scalar() or 0) > 0:
                continue

            # 2. 해당일 전후 1일 StockNews 확인 (뉴스 발행 시간과 거래일 차이 허용)
            news_range_start = check_date - timedelta(days=1)
            news_range_end = check_date + timedelta(days=1)
            news_stmt = (
                select(StockNews)
                .where(
                    and_(
                        StockNews.stock_code == code,
                        func.date(StockNews.published_at) >= news_range_start,
                        func.date(StockNews.published_at) <= news_range_end,
                    )
                )
                .order_by(desc(StockNews.published_at))
                .limit(5)
            )
            news_result = await self.db.execute(news_stmt)
            news_list = news_result.scalars().all()

            # 3. 해당일 공시 확인 (rcept_dt는 YYYYMMDD 문자열)
            check_date_str = check_date.strftime("%Y%m%d")
            disc_stmt = (
                select(Disclosure)
                .where(
                    and_(
                        Disclosure.stock_code == code,
                        Disclosure.rcept_dt == check_date_str,
                    )
                )
                .limit(3)
            )
            disc_result = await self.db.execute(disc_stmt)
            discs = disc_result.scalars().all()

            # 뉴스도 공시도 없으면 스킵
            if not news_list and not discs:
                continue

            # 4. 제목 생성 + 유형 분류
            title = ""
            catalyst_type = "other"
            description_parts = []

            if news_list:
                best_news = next((n for n in news_list if n.is_quality), news_list[0])
                title = best_news.title[:200]
                # Gemini 분류가 있으면 사용, 없으면 키워드 폴백
                catalyst_type = best_news.catalyst_type or _classify_by_keywords(
                    best_news.title, best_news.description or ""
                )
                description_parts.append(f"뉴스 {len(news_list)}건")

            if discs:
                disc_title = discs[0].report_nm[:200] if discs[0].report_nm else "공시 발생"
                if not title:
                    title = disc_title
                description_parts.append(f"공시 {len(discs)}건")
                # 뉴스 없이 공시만 있을 때 공시 제목으로 분류
                if catalyst_type == "other":
                    catalyst_type = _classify_by_keywords(disc_title)

            # 5. CatalystEvent 생성
            days_since = (today_kst() - check_date).days
            event = CatalystEvent(
                stock_code=code,
                stock_name=name_map.get(code),
                event_date=check_date,
                catalyst_type=catalyst_type,
                title=title,
                description=", ".join(description_parts),
                price_at_event=ohlcv.close_price,
                volume_at_event=ohlcv.volume,
                price_change_pct=change_pct,
                status="active",
                days_alive=days_since,
            )
            self.db.add(event)
            created_count += 1

        await self.db.commit()
        logger.info(f"카탈리스트 감지 완료 ({check_date}): {created_count}건 생성 (3%+ 변동 {len(movers)}종목)")
        return created_count

    async def backfill(self, days: int = 7) -> dict:
        """과거 N일간 카탈리스트 백필. 뉴스 수집 → 날짜별 감지 → 추적 업데이트.

        Args:
            days: 백필 일수 (기본 7일)

        Returns:
            날짜별 생성 건수 딕셔너리
        """
        today = today_kst()
        results = {}
        total_created = 0

        # 과거 날짜 순서대로 감지 (오래된 날짜부터)
        for i in range(days, 0, -1):
            target = today - timedelta(days=i)
            try:
                created = await self.detect_new_catalysts(target_date=target)
                results[target.isoformat()] = created
                total_created += created
            except Exception as e:
                logger.error(f"백필 실패 ({target}): {e}")
                results[target.isoformat()] = f"error: {e}"

        # 기존 "other" 이벤트 키워드 재분류
        reclassified = await self.reclassify_other_events()

        # 모든 날짜 감지 후 추적 업데이트
        updated = 0
        try:
            updated = await self.update_tracking()
        except Exception as e:
            logger.error(f"백필 추적 업데이트 실패: {e}")

        logger.info(f"카탈리스트 백필 완료: {days}일간 {total_created}건 생성, {reclassified}건 재분류, {updated}건 추적 업데이트")
        return {
            "days": days,
            "total_created": total_created,
            "total_reclassified": reclassified,
            "total_updated": updated,
            "by_date": results,
        }

    async def reclassify_other_events(self) -> int:
        """catalyst_type이 'other'인 이벤트를 키워드 기반으로 재분류."""
        stmt = (
            select(CatalystEvent)
            .where(CatalystEvent.catalyst_type.in_(["other", None]))
        )
        result = await self.db.execute(stmt)
        events = result.scalars().all()

        reclassified = 0
        for event in events:
            new_type = _classify_by_keywords(event.title or "", event.description or "")
            if new_type != "other":
                event.catalyst_type = new_type
                reclassified += 1

        if reclassified > 0:
            await self.db.commit()
            logger.info(f"카탈리스트 재분류: {reclassified}/{len(events)}건")

        return reclassified

    async def update_tracking(self) -> int:
        """active 상태의 CatalystEvent 추적 업데이트.

        Returns:
            업데이트된 이벤트 수
        """
        today = today_kst()

        # active, weakening 이벤트 조회
        stmt = (
            select(CatalystEvent)
            .where(CatalystEvent.status.in_(["active", "weakening"]))
        )
        result = await self.db.execute(stmt)
        events = result.scalars().all()

        if not events:
            return 0

        updated_count = 0

        for event in events:
            try:
                days_since = (today - event.event_date).days
                event.days_alive = days_since

                # OHLCV에서 현재 종가 조회
                latest_ohlcv_stmt = (
                    select(StockOHLCV)
                    .where(StockOHLCV.stock_code == event.stock_code)
                    .order_by(desc(StockOHLCV.trade_date))
                    .limit(1)
                )
                latest_result = await self.db.execute(latest_ohlcv_stmt)
                latest_ohlcv = latest_result.scalar_one_or_none()

                if latest_ohlcv and event.price_at_event and event.price_at_event > 0:
                    current_return = (latest_ohlcv.close_price - event.price_at_event) / event.price_at_event * 100
                    event.current_return = round(current_return, 2)

                    # 최대 수익률 갱신
                    if event.max_return is None or current_return > event.max_return:
                        event.max_return = round(current_return, 2)
                        event.max_return_day = days_since

                # T+N 수익률 (특정 일 데이터가 있을 때만)
                await self._update_return_at_day(event, 1, "return_t1")
                await self._update_return_at_day(event, 5, "return_t5")
                await self._update_return_at_day(event, 10, "return_t10")
                await self._update_return_at_day(event, 20, "return_t20")

                # 수급 동반 여부 (이벤트 후 5일)
                await self._update_flow_data(event)

                # 후속 뉴스 카운트
                news_count_stmt = (
                    select(func.count(StockNews.id))
                    .where(
                        and_(
                            StockNews.stock_code == event.stock_code,
                            func.date(StockNews.published_at) > event.event_date,
                        )
                    )
                )
                news_count_result = await self.db.execute(news_count_stmt)
                event.followup_news_count = news_count_result.scalar() or 0

                # 최근 뉴스 날짜
                latest_news_stmt = (
                    select(func.max(func.date(StockNews.published_at)))
                    .where(
                        and_(
                            StockNews.stock_code == event.stock_code,
                            func.date(StockNews.published_at) > event.event_date,
                        )
                    )
                )
                latest_news_result = await self.db.execute(latest_news_stmt)
                event.latest_news_date = latest_news_result.scalar()

                # 상태 판정
                event.status = self._determine_status(event)
                event.updated_at = now_kst().replace(tzinfo=None)
                updated_count += 1

            except Exception as e:
                logger.error(f"카탈리스트 추적 실패 ({event.stock_code}): {e}")
                continue

        await self.db.commit()
        logger.info(f"카탈리스트 추적 업데이트: {updated_count}/{len(events)}건")
        return updated_count

    async def _update_return_at_day(self, event: CatalystEvent, target_day: int, attr: str):
        """T+N일 수익률 업데이트."""
        if getattr(event, attr) is not None:
            return  # 이미 계산됨

        target_date = event.event_date + timedelta(days=target_day)
        if target_date > today_kst():
            return  # 아직 안 됨

        ohlcv_stmt = (
            select(StockOHLCV)
            .where(
                and_(
                    StockOHLCV.stock_code == event.stock_code,
                    StockOHLCV.trade_date >= target_date,
                )
            )
            .order_by(StockOHLCV.trade_date)
            .limit(1)
        )
        result = await self.db.execute(ohlcv_stmt)
        ohlcv = result.scalar_one_or_none()

        if ohlcv and event.price_at_event and event.price_at_event > 0:
            ret = (ohlcv.close_price - event.price_at_event) / event.price_at_event * 100
            setattr(event, attr, round(ret, 2))

    async def _update_flow_data(self, event: CatalystEvent):
        """수급 동반 여부 업데이트."""
        flow_start = event.event_date
        flow_end = event.event_date + timedelta(days=5)

        flow_stmt = (
            select(
                func.sum(StockInvestorFlow.foreign_net).label("foreign_sum"),
                func.sum(StockInvestorFlow.institution_net).label("inst_sum"),
            )
            .where(
                and_(
                    StockInvestorFlow.stock_code == event.stock_code,
                    StockInvestorFlow.flow_date >= flow_start,
                    StockInvestorFlow.flow_date <= flow_end,
                )
            )
        )
        flow_result = await self.db.execute(flow_stmt)
        row = flow_result.fetchone()

        if row:
            foreign_sum = row.foreign_sum or 0
            inst_sum = row.inst_sum or 0
            # 외국인+기관 순매수가 양수면 동반 확인
            event.flow_confirmed = (foreign_sum + inst_sum) > 0
            event.flow_score_5d = round(float(foreign_sum + inst_sum), 2)

    def _determine_status(self, event: CatalystEvent) -> str:
        """이벤트 상태 판정."""
        # T+20 이상이면 만료
        if event.days_alive >= 20:
            return "expired"

        # 수익률 전부 반납
        if (
            event.current_return is not None
            and event.max_return is not None
            and event.max_return > 3.0
            and event.current_return <= 0
        ):
            return "expired"

        # 약화 조건: 수급 이탈 + 후속뉴스 없음 + 수익률 하락
        weakening_signals = 0
        if event.flow_confirmed is False:
            weakening_signals += 1
        if event.followup_news_count == 0 and event.days_alive >= 3:
            weakening_signals += 1
        if (
            event.current_return is not None
            and event.max_return is not None
            and event.max_return > 0
            and event.current_return < event.max_return * 0.5
        ):
            weakening_signals += 1

        if weakening_signals >= 2:
            return "weakening"

        return "active"

    async def get_active_catalysts(
        self,
        status: Optional[str] = None,
        catalyst_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """상태별 카탈리스트 조회."""
        conditions = []
        if status:
            conditions.append(CatalystEvent.status == status)
        else:
            conditions.append(CatalystEvent.status.in_(["active", "weakening"]))

        if catalyst_type:
            conditions.append(CatalystEvent.catalyst_type == catalyst_type)

        stmt = (
            select(CatalystEvent)
            .where(and_(*conditions))
            .order_by(desc(CatalystEvent.event_date), desc(CatalystEvent.current_return))
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        events = result.scalars().all()

        return [self._to_dict(e) for e in events]

    async def get_stock_catalysts(self, stock_code: str, limit: int = 20) -> list[dict]:
        """종목별 카탈리스트 이력."""
        stmt = (
            select(CatalystEvent)
            .where(CatalystEvent.stock_code == stock_code)
            .order_by(desc(CatalystEvent.event_date))
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        events = result.scalars().all()

        return [self._to_dict(e) for e in events]

    async def get_catalyst_stats(self) -> dict:
        """유형별 통계."""
        stmt = (
            select(
                CatalystEvent.catalyst_type,
                func.count(CatalystEvent.id).label("count"),
                func.avg(CatalystEvent.days_alive).label("avg_days"),
                func.avg(CatalystEvent.max_return).label("avg_max_return"),
                func.avg(CatalystEvent.current_return).label("avg_current_return"),
            )
            .where(CatalystEvent.catalyst_type.isnot(None))
            .group_by(CatalystEvent.catalyst_type)
        )

        result = await self.db.execute(stmt)
        rows = result.fetchall()

        type_stats = {}
        for row in rows:
            type_stats[row.catalyst_type or "other"] = {
                "count": row.count,
                "avg_days": round(float(row.avg_days or 0), 1),
                "avg_max_return": round(float(row.avg_max_return or 0), 2),
                "avg_current_return": round(float(row.avg_current_return or 0), 2),
            }

        # 전체 요약
        from sqlalchemy import case
        total_stmt = (
            select(
                func.count(CatalystEvent.id).label("total"),
                func.sum(case((CatalystEvent.status == "active", 1), else_=0)).label("active_count"),
                func.sum(case((CatalystEvent.status == "weakening", 1), else_=0)).label("weakening_count"),
                func.sum(case((CatalystEvent.status == "expired", 1), else_=0)).label("expired_count"),
            )
        )
        total_result = await self.db.execute(total_stmt)
        total_row = total_result.fetchone()

        return {
            "total": total_row.total if total_row else 0,
            "active_count": total_row.active_count if total_row else 0,
            "weakening_count": total_row.weakening_count if total_row else 0,
            "expired_count": total_row.expired_count if total_row else 0,
            "by_type": type_stats,
        }

    async def get_enriched_catalysts(
        self,
        status: Optional[str] = None,
        catalyst_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """관련도 점수 + 가격 맥락이 포함된 카탈리스트."""
        events = await self.get_active_catalysts(status=status, catalyst_type=catalyst_type, limit=limit)

        for event in events:
            # 관련도 점수 계산
            event["relevance_score"] = self._calc_relevance(event)

            # 가격 맥락: 이벤트 전후 가격
            try:
                ohlcv_stmt = (
                    select(StockOHLCV)
                    .where(
                        and_(
                            StockOHLCV.stock_code == event["stock_code"],
                            StockOHLCV.trade_date >= (date.fromisoformat(event["event_date"]) - timedelta(days=7)),
                            StockOHLCV.trade_date <= (date.fromisoformat(event["event_date"]) + timedelta(days=15)),
                        )
                    )
                    .order_by(StockOHLCV.trade_date.asc())
                )
                result = await self.db.execute(ohlcv_stmt)
                ohlcv_rows = result.scalars().all()

                event["price_context"] = [
                    {
                        "date": r.trade_date.isoformat(),
                        "close": r.close_price,
                        "volume": r.volume,
                    }
                    for r in ohlcv_rows
                ]
            except Exception:
                event["price_context"] = []

        # 관련도 기준 정렬
        events.sort(key=lambda e: e.get("relevance_score", 0), reverse=True)
        return events

    def _calc_relevance(self, event: dict) -> int:
        """관련도 점수 (0~100)."""
        score = 0

        # 가격변동 크기 (30점)
        change = abs(event.get("price_change_pct") or 0)
        score += min(30, int(change * 3))

        # 수급 동반 (20점)
        if event.get("flow_confirmed"):
            score += 20

        # 후속 뉴스 (20점)
        news_count = event.get("followup_news_count") or 0
        score += min(20, news_count * 4)

        # 최대 수익률 (15점)
        max_ret = event.get("max_return") or 0
        score += min(15, int(max_ret * 1.5))

        # 활성 상태 (15점)
        if event.get("status") == "active":
            score += 15
        elif event.get("status") == "weakening":
            score += 7

        return min(100, score)

    async def get_business_impact(self, event_id: str) -> dict:
        """Gemini AI로 이벤트의 비즈니스 임팩트 요약."""
        stmt = select(CatalystEvent).where(CatalystEvent.id == event_id)
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()

        if not event:
            return {"impact": "이벤트를 찾을 수 없습니다."}

        try:
            from integrations.gemini.client import get_gemini_client
            gemini = get_gemini_client()
            if not gemini.is_configured:
                return {"impact": "AI가 설정되지 않았습니다."}

            prompt = f"""다음 카탈리스트 이벤트가 기업의 펀더멘탈에 미치는 영향을 2~3문장으로 요약해주세요.

종목: {event.stock_name or event.stock_code}
이벤트 유형: {event.catalyst_type}
제목: {event.title}
설명: {event.description or '없음'}
주가 변동: {event.price_change_pct or 0:.1f}%
수급 동반: {'예' if event.flow_confirmed else '아니오'}
후속 뉴스: {event.followup_news_count}건

핵심만 간결하게 한국어로 응답해주세요."""

            response = await gemini._generate(prompt)
            return {"impact": response or "분석 실패"}
        except Exception as e:
            logger.warning(f"AI 임팩트 분석 실패: {e}")
            return {"impact": f"분석 중 오류: {str(e)}"}

    async def get_similar_events(self, event_id: str, limit: int = 5) -> list[dict]:
        """동일 유형 + 동일 종목/섹터의 과거 유사 이벤트."""
        stmt = select(CatalystEvent).where(CatalystEvent.id == event_id)
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()

        if not event:
            return []

        # 동일 종목 + 동일 유형의 과거 이벤트
        similar_stmt = (
            select(CatalystEvent)
            .where(
                and_(
                    CatalystEvent.id != event.id,
                    CatalystEvent.stock_code == event.stock_code,
                    CatalystEvent.catalyst_type == event.catalyst_type,
                )
            )
            .order_by(desc(CatalystEvent.event_date))
            .limit(limit)
        )
        result = await self.db.execute(similar_stmt)
        similars = result.scalars().all()

        return [self._to_dict(e) for e in similars]

    def _to_dict(self, e: CatalystEvent) -> dict:
        return {
            "id": str(e.id),
            "stock_code": e.stock_code,
            "stock_name": e.stock_name,
            "event_date": e.event_date.isoformat(),
            "catalyst_type": e.catalyst_type,
            "title": e.title,
            "description": e.description,
            "price_at_event": e.price_at_event,
            "volume_at_event": e.volume_at_event,
            "price_change_pct": e.price_change_pct,
            "return_t1": e.return_t1,
            "return_t5": e.return_t5,
            "return_t10": e.return_t10,
            "return_t20": e.return_t20,
            "current_return": e.current_return,
            "max_return": e.max_return,
            "max_return_day": e.max_return_day,
            "flow_confirmed": e.flow_confirmed,
            "flow_score_5d": e.flow_score_5d,
            "followup_news_count": e.followup_news_count,
            "latest_news_date": e.latest_news_date.isoformat() if e.latest_news_date else None,
            "status": e.status,
            "days_alive": e.days_alive,
            "created_at": e.created_at.isoformat(),
            "updated_at": e.updated_at.isoformat() if e.updated_at else None,
        }
