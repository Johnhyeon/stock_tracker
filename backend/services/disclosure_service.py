"""공시 서비스."""
import logging
from datetime import datetime
from typing import Optional, Union
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, or_, select

from models import Disclosure, DisclosureType, DisclosureImportance, InvestmentIdea, IdeaStatus
from models.stock import Stock
from integrations.dart import (
    get_dart_client,
    filter_important_disclosures,
    classify_disclosure_type,
    classify_importance,
)
from integrations.dart.filters import extract_summary

logger = logging.getLogger(__name__)

DART_BASE_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="


class DisclosureService:
    """공시 서비스.

    DART API에서 공시를 수집하고 DB에 저장합니다.
    """

    def __init__(self, db: Union[Session, AsyncSession]):
        self.db = db
        self.dart_client = get_dart_client()

    def get_idea_stock_codes(self) -> list[str]:
        """활성/관찰 중인 아이디어의 종목코드 목록 조회.

        아이디어의 tickers(종목명)를 Stock 테이블에서 종목코드로 변환합니다.
        """
        # 활성/관찰 중인 아이디어 조회
        ideas = self.db.query(InvestmentIdea).filter(
            InvestmentIdea.status.in_([IdeaStatus.ACTIVE, IdeaStatus.WATCHING])
        ).all()

        # 모든 ticker 수집
        all_tickers = set()
        for idea in ideas:
            if idea.tickers:
                all_tickers.update(idea.tickers)

        if not all_tickers:
            return []

        # Stock 테이블에서 종목코드 조회 (이름 또는 코드로 매칭)
        stocks = self.db.query(Stock).filter(
            or_(
                Stock.name.in_(all_tickers),
                Stock.code.in_(all_tickers),
            )
        ).all()

        return [stock.code for stock in stocks]

    async def collect_disclosures(
        self,
        bgn_de: Optional[str] = None,
        end_de: Optional[str] = None,
        stock_codes: Optional[list[str]] = None,
        min_importance: DisclosureImportance = DisclosureImportance.MEDIUM,
    ) -> dict:
        """공시 수집 및 저장.

        Args:
            bgn_de: 시작일 (YYYYMMDD)
            end_de: 종료일 (YYYYMMDD)
            stock_codes: 관심 종목코드 목록
            min_importance: 최소 중요도

        Returns:
            {"collected": N, "new": M, "skipped": K}
        """
        result = {"collected": 0, "new": 0, "skipped": 0}

        try:
            # DART API에서 공시 조회
            data = await self.dart_client.search_disclosures(
                bgn_de=bgn_de,
                end_de=end_de,
            )

            disclosures = data.get("list", [])
            result["collected"] = len(disclosures)

            # 중요 공시 필터링
            filtered = filter_important_disclosures(
                disclosures,
                min_importance=min_importance,
                stock_codes=stock_codes,
            )

            # DB에 저장
            earnings_stock_codes = set()
            for disc in filtered:
                rcept_no = disc.get("rcept_no")

                # 중복 체크 (비동기)
                stmt = select(Disclosure).where(Disclosure.rcept_no == rcept_no)
                existing = (await self.db.execute(stmt)).scalars().first()

                if existing:
                    result["skipped"] += 1
                    continue

                disc_type = disc.get("disclosure_type", DisclosureType.OTHER)

                # 새 공시 저장
                disclosure = Disclosure(
                    rcept_no=rcept_no,
                    rcept_dt=disc.get("rcept_dt", ""),
                    corp_code=disc.get("corp_code", ""),
                    corp_name=disc.get("corp_name", ""),
                    stock_code=disc.get("stock_code"),
                    report_nm=disc.get("report_nm", ""),
                    flr_nm=disc.get("flr_nm"),
                    disclosure_type=disc_type,
                    importance=disc.get("importance", DisclosureImportance.MEDIUM),
                    summary=extract_summary(disc.get("report_nm", "")),
                    url=f"{DART_BASE_URL}{rcept_no}",
                )

                self.db.add(disclosure)
                result["new"] += 1

                # 실적 관련 공시(분기/반기/사업보고서) 감지
                if disc_type == DisclosureType.REGULAR and disc.get("stock_code"):
                    earnings_stock_codes.add(disc.get("stock_code"))

            await self.db.commit()
            result["earnings_stock_codes"] = list(earnings_stock_codes)
            logger.info(
                f"Disclosure collection completed: {result['new']} new, "
                f"{result['skipped']} skipped"
            )

        except Exception as e:
            logger.error(f"Disclosure collection failed: {e}")
            await self.db.rollback()
            raise

        return result

    def get_all(
        self,
        stock_code: Optional[str] = None,
        stock_codes: Optional[list[str]] = None,
        importance: Optional[DisclosureImportance] = None,
        disclosure_type: Optional[DisclosureType] = None,
        unread_only: bool = False,
        my_ideas_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Disclosure]:
        """공시 목록 조회.

        Args:
            stock_code: 단일 종목코드 필터
            stock_codes: 복수 종목코드 필터
            importance: 중요도 필터
            disclosure_type: 유형 필터
            unread_only: 읽지 않은 것만
            my_ideas_only: 내 아이디어 종목만
            skip: 건너뛸 개수
            limit: 조회 개수

        Returns:
            Disclosure 목록
        """
        query = self.db.query(Disclosure)

        # 내 아이디어 종목만 필터링
        if my_ideas_only:
            idea_stock_codes = self.get_idea_stock_codes()
            if not idea_stock_codes:
                return []  # 아이디어 종목이 없으면 빈 목록 반환
            query = query.filter(Disclosure.stock_code.in_(idea_stock_codes))
        elif stock_codes:
            query = query.filter(Disclosure.stock_code.in_(stock_codes))
        elif stock_code:
            query = query.filter(Disclosure.stock_code == stock_code)

        if importance:
            query = query.filter(Disclosure.importance == importance)
        if disclosure_type:
            query = query.filter(Disclosure.disclosure_type == disclosure_type)
        if unread_only:
            query = query.filter(Disclosure.is_read == False)

        return (
            query
            .order_by(desc(Disclosure.rcept_dt), desc(Disclosure.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get(self, disclosure_id: UUID) -> Optional[Disclosure]:
        """공시 상세 조회."""
        return self.db.query(Disclosure).filter(Disclosure.id == disclosure_id).first()

    def mark_as_read(self, disclosure_id: UUID) -> Optional[Disclosure]:
        """공시 읽음 처리."""
        disclosure = self.get(disclosure_id)
        if disclosure:
            disclosure.is_read = True
            self.db.commit()
            self.db.refresh(disclosure)
        return disclosure

    def mark_all_as_read(self, stock_code: Optional[str] = None) -> int:
        """모든 공시 읽음 처리.

        Args:
            stock_code: 특정 종목만 (없으면 전체)

        Returns:
            처리된 개수
        """
        query = self.db.query(Disclosure).filter(Disclosure.is_read == False)
        if stock_code:
            query = query.filter(Disclosure.stock_code == stock_code)

        count = query.update({"is_read": True})
        self.db.commit()
        return count

    def get_stats(self, stock_code: Optional[str] = None) -> dict:
        """공시 통계.

        Returns:
            {
                "total": N,
                "unread": M,
                "by_importance": {"high": X, "medium": Y, "low": Z},
                "by_type": {...}
            }
        """
        query = self.db.query(Disclosure)
        if stock_code:
            query = query.filter(Disclosure.stock_code == stock_code)

        disclosures = query.all()
        total = len(disclosures)
        unread = sum(1 for d in disclosures if not d.is_read)

        by_importance = {}
        for imp in DisclosureImportance:
            by_importance[imp.value] = sum(1 for d in disclosures if d.importance == imp)

        by_type = {}
        for dtype in DisclosureType:
            by_type[dtype.value] = sum(1 for d in disclosures if d.disclosure_type == dtype)

        return {
            "total": total,
            "unread": unread,
            "by_importance": by_importance,
            "by_type": by_type,
        }
