"""내러티브 브리핑 서비스.

Gemini AI를 사용하여 종목별 내러티브 브리핑을 생성하고 DB에 캐시.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from core.timezone import now_kst

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from models.narrative_briefing import NarrativeBriefing
from services.cross_reference_service import CrossReferenceService
from integrations.gemini.client import get_gemini_client

logger = logging.getLogger(__name__)


def _is_market_hours() -> bool:
    """현재 장중인지 확인."""
    now = now_kst()
    if now.weekday() >= 5:
        return False
    t = now.hour * 100 + now.minute
    return 900 <= t <= 1530


class NarrativeService:
    """내러티브 브리핑 생성 및 캐싱."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_briefing(
        self,
        stock_code: str,
        force_refresh: bool = False,
    ) -> Optional[dict]:
        """내러티브 브리핑 조회 (캐시 → 생성)."""

        # 1) 캐시 확인
        if not force_refresh:
            cached = await self._get_cached(stock_code)
            if cached:
                return cached

        # 2) 프로필 데이터 수집
        cross_ref = CrossReferenceService(self.db)
        profile = await cross_ref.get_stock_profile(stock_code)

        stock_name = ""
        if profile.get("stock_info"):
            stock_name = profile["stock_info"].get("name", "")

        # 3) Gemini 호출
        gemini = get_gemini_client()
        if not gemini.is_configured:
            logger.warning("Gemini API 미설정 - 내러티브 브리핑 생성 불가")
            return None

        result = await gemini.analyze_narrative_briefing(
            stock_code=stock_code,
            stock_name=stock_name,
            profile_data=profile,
        )

        if not result:
            logger.warning(f"내러티브 브리핑 생성 실패: {stock_code}")
            return None

        # 4) DB 저장
        now = now_kst().replace(tzinfo=None)
        ttl_hours = 4 if _is_market_hours() else 12
        expires_at = now + timedelta(hours=ttl_hours)

        data_hash = NarrativeBriefing.compute_hash({
            "ohlcv": profile.get("ohlcv", {}),
            "flow": profile.get("investor_flow", {}),
        })

        briefing = NarrativeBriefing(
            stock_code=stock_code,
            generated_at=now,
            expires_at=expires_at,
            one_liner=result.get("one_liner", ""),
            why_moving=result.get("why_moving", ""),
            theme_context=result.get("theme_context", ""),
            expert_perspective=result.get("expert_perspective", ""),
            catalysts=result.get("catalysts", []),
            risk_factors=result.get("risk_factors", []),
            narrative_strength=result.get("narrative_strength", "weak"),
            market_outlook=result.get("market_outlook", "neutral"),
            financial_highlight=result.get("financial_highlight", ""),
            input_data_hash=data_hash,
        )
        self.db.add(briefing)
        await self.db.commit()

        result["stock_name"] = stock_name
        result["generated_at"] = now.isoformat()
        return result

    async def _get_cached(self, stock_code: str) -> Optional[dict]:
        """유효한 캐시 반환."""
        now = now_kst().replace(tzinfo=None)
        stmt = (
            select(NarrativeBriefing)
            .where(and_(
                NarrativeBriefing.stock_code == stock_code,
                NarrativeBriefing.expires_at > now,
            ))
            .order_by(NarrativeBriefing.generated_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()

        if not row:
            return None

        return {
            "stock_name": "",
            "one_liner": row.one_liner or "",
            "why_moving": row.why_moving or "",
            "theme_context": row.theme_context or "",
            "expert_perspective": row.expert_perspective or "",
            "catalysts": row.catalysts or [],
            "risk_factors": row.risk_factors or [],
            "narrative_strength": row.narrative_strength or "weak",
            "market_outlook": row.market_outlook or "neutral",
            "financial_highlight": row.financial_highlight or "",
            "generated_at": row.generated_at.isoformat() if row.generated_at else "",
        }

    async def batch_generate(self, stock_codes: list[str]) -> int:
        """배치 브리핑 생성 (스케줄러용). 2초 간격 rate limiting."""
        generated = 0
        for code in stock_codes:
            try:
                result = await self.get_briefing(code, force_refresh=False)
                if result:
                    generated += 1
                    logger.info(f"내러티브 생성 완료: {code}")
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"내러티브 생성 실패 ({code}): {e}")
        return generated
