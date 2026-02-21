"""일일 시장 리포트 서비스.

장 마감 후 시장 분위기를 정리하여 텔레그램 리포트를 생성합니다.
- 상한가/급등 종목과 관련 테마
- 52주 신고가 종목
- 오늘의 주도 테마 (등락률 기준)
- AI 시장 분위기 요약
"""
import logging
from collections import defaultdict
from datetime import datetime, date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from models import StockOHLCV
from services.theme_map_service import get_theme_map_service
from integrations.gemini.client import get_gemini_client
from core.timezone import now_kst, today_kst

logger = logging.getLogger(__name__)


class DailyReportService:
    """일일 시장 리포트 생성 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._tms = get_theme_map_service()

    async def generate_report(self) -> str | None:
        """일일 리포트 전체 생성."""
        date_str = now_kst().strftime("%Y-%m-%d (%a)")

        # 오늘/전일 OHLCV 로드
        today_data, prev_data = await self._load_market_data()
        if not today_data:
            logger.info("오늘 OHLCV 데이터 없음")
            return None

        # 등락률 계산
        changes = self._calc_changes(today_data, prev_data)
        if not changes:
            return None

        sections = []

        # 1. 시장 개요
        overview = self._build_overview(changes)
        if overview:
            sections.append(overview)

        # 2. 상한가/급등 종목
        surge = self._build_surge_section(changes)
        if surge:
            sections.append(surge)

        # 3. 52주 신고가
        new_high = await self._build_52w_high_section(today_data)
        if new_high:
            sections.append(new_high)

        # 4. 주도 테마
        theme_section = self._build_theme_ranking(changes)
        if theme_section:
            sections.append(theme_section)

        # 5. AI 시장 분위기 요약
        ai_summary = await self._build_ai_summary(changes, sections)
        if ai_summary:
            sections.append(ai_summary)

        if not sections:
            return None

        body = "\n\n".join(sections)
        return f"""📊 <b>{date_str} 장 마감 리포트</b>

{body}

<i>🤖 Investment Tracker</i>"""

    # ── 데이터 로드 ──

    async def _load_market_data(self) -> tuple[dict, dict]:
        """오늘 + 전일 OHLCV 데이터 로드.

        최신 OHLCV 날짜가 오늘이 아니면 (휴장/수집 실패) 빈 데이터 반환하여
        같은 내용의 리포트가 반복 발송되는 것을 방지합니다.
        """
        # 가장 최근 거래일 2일치
        latest_dates_stmt = (
            select(StockOHLCV.trade_date)
            .distinct()
            .order_by(StockOHLCV.trade_date.desc())
            .limit(2)
        )
        result = await self.db.execute(latest_dates_stmt)
        dates = [row[0] for row in result.fetchall()]

        if not dates:
            return {}, {}

        today_date = dates[0]

        # 최신 OHLCV 데이터가 오늘이 아니면 새 데이터 없음 → 리포트 생성 안 함
        today = today_kst()  # date 객체
        latest = today_date if isinstance(today_date, date) else today_date
        if latest != today:
            logger.info(f"최신 OHLCV 날짜({latest})가 오늘({today})이 아님, 리포트 생성 건너뜀")
            return {}, {}

        prev_date = dates[1] if len(dates) > 1 else None

        # 오늘 데이터
        today_stmt = select(StockOHLCV).where(StockOHLCV.trade_date == today_date)
        result = await self.db.execute(today_stmt)
        today_data = {r.stock_code: r for r in result.scalars().all()}

        # 전일 데이터
        prev_data = {}
        if prev_date:
            prev_stmt = select(StockOHLCV).where(StockOHLCV.trade_date == prev_date)
            result = await self.db.execute(prev_stmt)
            prev_data = {r.stock_code: r for r in result.scalars().all()}

        return today_data, prev_data

    def _calc_changes(self, today_data: dict, prev_data: dict) -> list[dict]:
        """종목별 등락률 계산."""
        results = []
        for code, today in today_data.items():
            prev = prev_data.get(code)
            if not prev or prev.close_price <= 0:
                continue

            change_pct = (today.close_price - prev.close_price) / prev.close_price * 100
            name = ""
            themes = self._tms.get_themes_for_stock(code)
            # 테마맵에서 이름 찾기
            for theme_stocks in self._tms.get_all_themes().values():
                for s in theme_stocks:
                    if s.get("code") == code:
                        name = s.get("name", "")
                        break
                if name:
                    break

            if not name:
                continue

            results.append({
                "code": code,
                "name": name,
                "close": today.close_price,
                "prev_close": prev.close_price,
                "high": today.high_price,
                "low": today.low_price,
                "volume": today.volume,
                "change_pct": round(change_pct, 2),
                "themes": themes,
            })

        return results

    # ── 섹션 빌더 ──

    def _build_overview(self, changes: list[dict]) -> str:
        """시장 개요 - 전체 종목 통계."""
        total = len(changes)
        if total == 0:
            return ""

        up = sum(1 for c in changes if c["change_pct"] > 0)
        down = sum(1 for c in changes if c["change_pct"] < 0)
        flat = total - up - down
        avg_change = sum(c["change_pct"] for c in changes) / total

        # 상한가 수
        limit_up = sum(1 for c in changes if c["change_pct"] >= 29.0)

        if avg_change > 0.5:
            mood = "강세"
        elif avg_change > 0:
            mood = "보합 강세"
        elif avg_change > -0.5:
            mood = "보합 약세"
        else:
            mood = "약세"

        lines = [f"📈 <b>시장 개요</b> ({mood})"]
        lines.append(f"  상승 {up} | 하락 {down} | 보합 {flat} (총 {total}종목)")
        lines.append(f"  평균 등락률 {avg_change:+.2f}%")
        if limit_up > 0:
            lines.append(f"  상한가 {limit_up}종목 🔥")

        return "\n".join(lines)

    def _build_surge_section(self, changes: list[dict]) -> str:
        """상한가 + 급등(+10% 이상) 종목과 관련 테마."""
        surges = [c for c in changes if c["change_pct"] >= 10.0]
        surges.sort(key=lambda c: c["change_pct"], reverse=True)

        if not surges:
            return ""

        # 상한가 / 급등 분리
        limit_ups = [c for c in surges if c["change_pct"] >= 29.0]
        hot_ups = [c for c in surges if c["change_pct"] < 29.0]

        lines = []

        if limit_ups:
            lines.append(f"🔴 <b>상한가</b> ({len(limit_ups)}종목)")
            for c in limit_ups:
                theme_str = f" #{c['themes'][0]}" if c['themes'] else ""
                lines.append(
                    f"  • <b>{c['name']}</b> {c['close']:,}원 "
                    f"(+{c['change_pct']:.1f}%){theme_str}"
                )

        if hot_ups:
            lines.append(f"🟠 <b>급등</b> (+10% 이상, {len(hot_ups)}종목)")
            for c in hot_ups[:10]:
                theme_str = f" #{c['themes'][0]}" if c['themes'] else ""
                lines.append(
                    f"  • <b>{c['name']}</b> {c['close']:,}원 "
                    f"(+{c['change_pct']:.1f}%){theme_str}"
                )
            if len(hot_ups) > 10:
                lines.append(f"  ... 외 {len(hot_ups) - 10}종목")

        # 급등 종목에서 많이 나온 테마
        theme_count = defaultdict(int)
        for c in surges:
            for t in c["themes"][:2]:
                theme_count[t] += 1

        hot_themes = sorted(theme_count.items(), key=lambda x: x[1], reverse=True)[:5]
        if hot_themes:
            theme_tags = ", ".join(f"#{t}({cnt})" for t, cnt in hot_themes)
            lines.append(f"  → 관련 테마: {theme_tags}")

        return "\n".join(lines)

    async def _build_52w_high_section(self, today_data: dict) -> str:
        """52주(240거래일) 신고가 종목."""
        # 240일 전 기준
        start_date = today_kst() - timedelta(days=365)

        codes = list(today_data.keys())
        if not codes:
            return ""

        # 각 종목의 과거 240거래일 최고가 조회
        stmt = (
            select(
                StockOHLCV.stock_code,
                func.max(StockOHLCV.high_price).label("max_high"),
            )
            .where(
                and_(
                    StockOHLCV.stock_code.in_(codes),
                    StockOHLCV.trade_date >= start_date,
                    StockOHLCV.trade_date < today_kst(),
                )
            )
            .group_by(StockOHLCV.stock_code)
        )
        result = await self.db.execute(stmt)
        historical_highs = {row[0]: row[1] for row in result.fetchall()}

        new_highs = []
        for code, today in today_data.items():
            prev_max = historical_highs.get(code)
            if prev_max and today.high_price > prev_max:
                name = ""
                themes = self._tms.get_themes_for_stock(code)
                for theme_stocks in self._tms.get_all_themes().values():
                    for s in theme_stocks:
                        if s.get("code") == code:
                            name = s.get("name", "")
                            break
                    if name:
                        break
                if name:
                    new_highs.append({
                        "name": name,
                        "code": code,
                        "price": today.close_price,
                        "themes": themes,
                    })

        if not new_highs:
            return ""

        lines = [f"⭐ <b>52주 신고가</b> ({len(new_highs)}종목)"]
        for c in new_highs[:10]:
            theme_str = f" #{c['themes'][0]}" if c['themes'] else ""
            lines.append(f"  • <b>{c['name']}</b> {c['price']:,}원{theme_str}")
        if len(new_highs) > 10:
            lines.append(f"  ... 외 {len(new_highs) - 10}종목")

        return "\n".join(lines)

    def _build_theme_ranking(self, changes: list[dict]) -> str:
        """테마별 평균 등락률로 주도 테마 랭킹."""
        theme_changes = defaultdict(list)
        for c in changes:
            for t in c["themes"]:
                theme_changes[t].append(c["change_pct"])

        # 종목 3개 이상인 테마만
        theme_stats = []
        for theme, pcts in theme_changes.items():
            if len(pcts) < 3:
                continue
            avg = sum(pcts) / len(pcts)
            up_count = sum(1 for p in pcts if p > 0)
            theme_stats.append({
                "theme": theme,
                "avg_change": round(avg, 2),
                "count": len(pcts),
                "up_count": up_count,
                "up_ratio": round(up_count / len(pcts) * 100),
            })

        theme_stats.sort(key=lambda x: x["avg_change"], reverse=True)

        if not theme_stats:
            return ""

        # 상위 7 + 하위 3
        top = theme_stats[:7]
        bottom = [t for t in theme_stats[-3:] if t["avg_change"] < 0]

        lines = ["🏷️ <b>오늘의 주도 테마</b>"]

        for i, t in enumerate(top, 1):
            bar = "🟢" if t["avg_change"] > 1 else ("🔵" if t["avg_change"] > 0 else "⚪")
            lines.append(
                f"  {i}. {bar} <b>{t['theme']}</b> "
                f"{t['avg_change']:+.2f}% "
                f"(상승 {t['up_ratio']}%, {t['count']}종목)"
            )

        if bottom:
            lines.append("")
            lines.append("  📉 부진 테마")
            for t in bottom:
                lines.append(
                    f"  • {t['theme']} {t['avg_change']:+.2f}% "
                    f"({t['count']}종목)"
                )

        return "\n".join(lines)

    async def _build_ai_summary(
        self,
        changes: list[dict],
        existing_sections: list[str],
    ) -> str | None:
        """Gemini AI 시장 분위기 요약."""
        gemini = get_gemini_client()
        if not gemini.is_configured:
            return None

        # 기존 섹션 텍스트를 AI에게 전달 (HTML 태그 제거)
        import re
        section_text = "\n\n".join(existing_sections)
        clean_text = re.sub(r"<[^>]+>", "", section_text)

        # 추가 통계
        total = len(changes)
        avg = sum(c["change_pct"] for c in changes) / total if total else 0
        top5 = sorted(changes, key=lambda c: c["change_pct"], reverse=True)[:5]
        top5_str = ", ".join(
            f"{c['name']}({c['change_pct']:+.1f}%)" for c in top5
        )

        prompt = f"""당신은 한국 주식 시장 마감 후 구독자에게 시장 분위기를 전달하는 텔레그램 채널 운영자입니다.

아래 오늘의 시장 데이터를 참고하여, 오늘 시장 분위기를 자연스럽게 정리해주세요.

## 오늘의 데이터
평균 등락률: {avg:+.2f}% (전체 {total}종목)
등락률 상위: {top5_str}

{clean_text}

## 작성 규칙
- 4~6문장으로 자연스럽게 작성
- 오늘 시장의 전체적인 분위기와 흐름 (강세/약세/혼조)
- 어떤 테마/섹터가 주도했는지 핵심만
- 특이 사항이 있으면 언급 (상한가 많으면 과열 주의 등)
- 내일 주목할 포인트가 있다면 한 줄
- 한국어, 반말 아닌 ~입니다/~습니다 체
- HTML 태그 사용하지 않음
- 이모지 사용하지 않음
- 투자 추천/매수 권유 절대 금지, 순수 시장 관찰 기록만"""

        try:
            result = await gemini._generate(prompt)
            if result and len(result.strip()) > 20:
                return f"💬 <b>오늘의 시장</b>\n{result.strip()}"
        except Exception as e:
            logger.error(f"AI 시장 요약 생성 실패: {e}")

        return None
