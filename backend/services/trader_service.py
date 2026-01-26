"""트레이더 관심종목 서비스."""
import json
import logging
import math
from datetime import datetime, date, timedelta
from typing import Optional
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_

from models import TraderMention, TraderStats, Stock
from integrations.kis import get_kis_client

logger = logging.getLogger(__name__)

MENTIONS_FILE_PATH = "/home/hyeon/project/88_bot/mentions.json"


class TraderService:
    """트레이더 관심종목 서비스."""

    # 영문 약자 → 한글 변환 매핑
    ABBREV_TO_KOREAN = {
        "DSC": "디에스씨",
        "SK": "에스케이",
        "LG": "엘지",
        "KT": "케이티",
        "GS": "지에스",
        "CJ": "씨제이",
        "HD": "에이치디",
        "KB": "케이비",
        "NH": "엔에이치",
        "DB": "디비",
        "LS": "엘에스",
        "DL": "디엘",
        "KG": "케이지",
        "SG": "에스지",
        "HL": "에이치엘",
        "HK": "에이치케이",
        "JB": "제이비",
        "BNK": "비엔케이",
        "DGB": "디지비",
        "IBK": "아이비케이",
        "OCI": "오씨아이",
        "SDN": "에스디엔",
        "BGF": "비지에프",
        "SNT": "에스엔티",
        "KCC": "케이씨씨",
        "AK": "에이케이",
        "KPX": "케이피엑스",
        "NPC": "엔피씨",
        "KSS": "케이에스에스",
    }

    # 한글 → 영문 약자 변환 (역방향)
    KOREAN_TO_ABBREV = {v: k for k, v in ABBREV_TO_KOREAN.items()}

    def __init__(self, db: Session):
        self.db = db

    def _normalize_name(self, name: str) -> list[str]:
        """종목명 정규화 - 여러 변형 생성."""
        variations = [name]

        # 1. 한글 → 영문 변환 시도
        for korean, abbrev in self.KOREAN_TO_ABBREV.items():
            if name.startswith(korean):
                variations.append(name.replace(korean, abbrev, 1))

        # 2. 영문 → 한글 변환 시도
        for abbrev, korean in self.ABBREV_TO_KOREAN.items():
            if name.upper().startswith(abbrev):
                variations.append(korean + name[len(abbrev):])

        return variations

    def _match_stock_code(self, stock_name: str) -> Optional[str]:
        """종목명으로 종목코드 매칭."""
        # 1. 정확한 매칭 시도
        stock = self.db.query(Stock).filter(Stock.name == stock_name).first()
        if stock:
            return stock.code

        # 2. 이름 변형으로 매칭 시도
        for variation in self._normalize_name(stock_name):
            if variation == stock_name:
                continue
            stock = self.db.query(Stock).filter(Stock.name == variation).first()
            if stock:
                return stock.code

        # 3. 부분 매칭 시도 (원본)
        stock = self.db.query(Stock).filter(
            Stock.name.contains(stock_name)
        ).first()
        if stock:
            return stock.code

        # 4. 부분 매칭 시도 (변형)
        for variation in self._normalize_name(stock_name):
            if variation == stock_name:
                continue
            stock = self.db.query(Stock).filter(
                Stock.name.contains(variation)
            ).first()
            if stock:
                return stock.code

        return None

    def sync_mentions(self, file_path: str = MENTIONS_FILE_PATH) -> dict:
        """mentions.json 파일과 DB 동기화.

        Returns:
            {
                "total_stocks": N,
                "total_mentions": M,
                "new_mentions": K,
                "updated_stocks": L
            }
        """
        result = {
            "total_stocks": 0,
            "total_mentions": 0,
            "new_mentions": 0,
            "updated_stocks": 0
        }

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            result["total_stocks"] = len(data)

            for stock_name, mentions in data.items():
                stock_code = self._match_stock_code(stock_name)

                for mention in mentions:
                    result["total_mentions"] += 1

                    try:
                        mention_date = datetime.strptime(
                            mention.get("date", ""),
                            "%Y-%m-%d"
                        ).date()
                    except:
                        continue

                    # 등락률 파싱
                    change_rate_str = mention.get("change_rate", "0")
                    try:
                        change_rate = float(change_rate_str.replace("+", "").replace("%", ""))
                    except:
                        change_rate = None

                    source_link = mention.get("link")
                    chat_id = str(mention.get("chat_id", ""))

                    # 중복 체크 (종목명 + 날짜 + 링크)
                    existing = self.db.query(TraderMention).filter(
                        TraderMention.stock_name == stock_name,
                        TraderMention.mention_date == mention_date,
                        TraderMention.source_link == source_link
                    ).first()

                    if not existing:
                        new_mention = TraderMention(
                            stock_name=stock_name,
                            stock_code=stock_code,
                            mention_date=mention_date,
                            change_rate=change_rate,
                            source_link=source_link,
                            chat_id=chat_id
                        )
                        self.db.add(new_mention)
                        result["new_mentions"] += 1

                # 종목코드 업데이트
                if stock_code:
                    updated = self.db.query(TraderMention).filter(
                        TraderMention.stock_name == stock_name,
                        TraderMention.stock_code.is_(None)
                    ).update({"stock_code": stock_code})
                    if updated > 0:
                        result["updated_stocks"] += 1

            self.db.commit()
            logger.info(f"Sync completed: {result}")

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            self.db.rollback()
            raise

        return result

    def get_hot_stocks(
        self,
        days_back: int = 7,
        limit: int = 20,
        include_price: bool = True
    ) -> list[dict]:
        """핫 종목 조회 (최근 언급 많은 종목).

        Args:
            days_back: 분석 기간
            limit: 상위 몇 개
            include_price: KIS API 데이터 포함 여부

        Returns:
            핫 종목 리스트
        """
        cutoff = date.today() - timedelta(days=days_back)
        prev_cutoff = cutoff - timedelta(days=days_back)

        # 최근 기간 통계
        recent_stats = self.db.query(
            TraderMention.stock_name,
            TraderMention.stock_code,
            func.count(TraderMention.id).label("mention_count"),
            func.min(TraderMention.mention_date).label("first_date"),
            func.max(TraderMention.mention_date).label("last_date"),
            func.avg(TraderMention.change_rate).label("avg_change")
        ).filter(
            TraderMention.mention_date >= cutoff
        ).group_by(
            TraderMention.stock_name,
            TraderMention.stock_code
        ).order_by(
            desc("mention_count")
        ).limit(limit * 2).all()

        # 이전 기간 언급 체크 (신규 판단용)
        prev_stocks = set(
            r[0] for r in self.db.query(TraderMention.stock_name)
            .filter(
                TraderMention.mention_date >= prev_cutoff,
                TraderMention.mention_date < cutoff
            ).distinct().all()
        )

        hot_stocks = []
        for stat in recent_stats:
            is_new = stat.stock_name not in prev_stocks

            hot_stocks.append({
                "stock_name": stat.stock_name,
                "stock_code": stat.stock_code,
                "mention_count": stat.mention_count,
                "first_mention_date": stat.first_date.isoformat() if stat.first_date else None,
                "last_mention_date": stat.last_date.isoformat() if stat.last_date else None,
                "is_new": is_new,
                "avg_mention_change": round(stat.avg_change, 2) if stat.avg_change else None,
                "current_price": None,
                "price_change": None,
                "price_change_rate": None,
                "volume": None,
                "performance_since_first": None,
                "weighted_score": None,
            })

        # KIS API로 주가 정보 추가
        if include_price:
            hot_stocks = self._enrich_with_kis_data(hot_stocks[:limit])
            # 가중치 점수로 재정렬
            hot_stocks.sort(key=lambda x: x.get("weighted_score") or 0, reverse=True)

        return hot_stocks[:limit]

    def get_rising_stocks(
        self,
        days_back: int = 7,
        limit: int = 20,
        include_price: bool = True
    ) -> list[dict]:
        """급상승 종목 조회 (언급 증가율 기준).

        Args:
            days_back: 분석 기간
            limit: 상위 몇 개
            include_price: KIS API 데이터 포함 여부
        """
        today = date.today()
        half = days_back // 2

        recent_start = today - timedelta(days=half)
        prev_start = today - timedelta(days=days_back)
        prev_end = recent_start - timedelta(days=1)

        # 최근 기간 통계
        recent_stats = dict(
            self.db.query(
                TraderMention.stock_name,
                func.count(TraderMention.id).label("cnt")
            ).filter(
                TraderMention.mention_date >= recent_start
            ).group_by(TraderMention.stock_name).all()
        )

        # 이전 기간 통계
        prev_stats = dict(
            self.db.query(
                TraderMention.stock_name,
                func.count(TraderMention.id).label("cnt")
            ).filter(
                TraderMention.mention_date >= prev_start,
                TraderMention.mention_date <= prev_end
            ).group_by(TraderMention.stock_name).all()
        )

        rising = []
        all_stocks = set(recent_stats.keys()) | set(prev_stats.keys())

        for stock_name in all_stocks:
            recent = recent_stats.get(stock_name, 0)
            prev = prev_stats.get(stock_name, 0)

            if recent == 0:
                continue

            if prev == 0:
                growth_rate = 100.0
                is_new = True
            else:
                growth_rate = ((recent - prev) / prev) * 100
                is_new = False

            # 종목코드 조회
            mention = self.db.query(TraderMention).filter(
                TraderMention.stock_name == stock_name
            ).first()
            stock_code = mention.stock_code if mention else None

            rising.append({
                "stock_name": stock_name,
                "stock_code": stock_code,
                "recent_mentions": recent,
                "prev_mentions": prev,
                "growth_rate": round(growth_rate, 1),
                "is_new": is_new,
                "current_price": None,
                "price_change_rate": None,
                "volume": None,
                "weighted_score": None,
            })

        # 1차 정렬
        rising.sort(key=lambda x: (x["is_new"], x["growth_rate"]), reverse=True)

        # KIS API 데이터 추가
        if include_price:
            rising = self._enrich_with_kis_data(rising[:limit], is_rising=True)
            rising.sort(key=lambda x: x.get("weighted_score") or 0, reverse=True)

        return rising[:limit]

    def get_performance_stats(self, days_back: int = 30) -> dict:
        """트레이더 성과 통계.

        Args:
            days_back: 분석 기간

        Returns:
            성과 통계
        """
        cutoff = date.today() - timedelta(days=days_back)

        # 언급된 종목들 가져오기
        mentions = self.db.query(
            TraderMention.stock_name,
            TraderMention.stock_code,
            TraderMention.mention_date,
            TraderMention.change_rate
        ).filter(
            TraderMention.mention_date >= cutoff,
            TraderMention.stock_code.isnot(None)
        ).all()

        if not mentions:
            return {
                "total_stocks": 0,
                "avg_performance": 0.0,
                "win_rate": 0.0,
                "best_stock": None,
                "best_performance": None,
                "worst_stock": None,
                "worst_performance": None,
            }

        # 종목별 성과 계산 (KIS API 호출)
        stock_codes = list(set(m.stock_code for m in mentions if m.stock_code))
        prices = self._fetch_kis_prices(stock_codes)

        # 종목별 첫 언급일 가격 vs 현재 가격
        stock_performance = {}
        for mention in mentions:
            if not mention.stock_code or mention.stock_code in stock_performance:
                continue

            current = prices.get(mention.stock_code, {}).get("current_price", 0)
            if current and mention.change_rate:
                # 대략적인 첫 언급 시점 가격 추정
                # (현재가 / (1 + change_rate/100)) 방식은 정확하지 않으므로
                # 단순히 언급일 등락률을 성과로 사용
                stock_performance[mention.stock_code] = {
                    "name": mention.stock_name,
                    "performance": mention.change_rate
                }

        performances = [v["performance"] for v in stock_performance.values() if v["performance"]]

        if not performances:
            return {
                "total_stocks": len(stock_codes),
                "avg_performance": 0.0,
                "win_rate": 0.0,
                "best_stock": None,
                "best_performance": None,
                "worst_stock": None,
                "worst_performance": None,
            }

        avg_perf = sum(performances) / len(performances)
        win_count = sum(1 for p in performances if p > 0)
        win_rate = (win_count / len(performances)) * 100

        best = max(stock_performance.items(), key=lambda x: x[1]["performance"] or 0)
        worst = min(stock_performance.items(), key=lambda x: x[1]["performance"] or 0)

        return {
            "total_stocks": len(stock_codes),
            "avg_performance": round(avg_perf, 2),
            "win_rate": round(win_rate, 1),
            "best_stock": best[1]["name"],
            "best_performance": best[1]["performance"],
            "worst_stock": worst[1]["name"],
            "worst_performance": worst[1]["performance"],
        }

    def get_new_mentions(self, since_hours: int = 24) -> list[dict]:
        """새로운 언급 조회 (알림용).

        Args:
            since_hours: 몇 시간 전부터

        Returns:
            새로운 언급 리스트
        """
        cutoff = datetime.utcnow() - timedelta(hours=since_hours)

        mentions = self.db.query(TraderMention).filter(
            TraderMention.created_at >= cutoff
        ).order_by(desc(TraderMention.created_at)).all()

        return [
            {
                "stock_name": m.stock_name,
                "stock_code": m.stock_code,
                "mention_date": m.mention_date.isoformat(),
                "change_rate": m.change_rate,
                "source_link": m.source_link,
            }
            for m in mentions
        ]

    def get_cross_check(self, idea_tickers: list[str]) -> list[dict]:
        """내 아이디어 종목과 트레이더 관심종목 크로스 체크.

        Args:
            idea_tickers: 내 아이디어 종목코드 리스트

        Returns:
            겹치는 종목 리스트
        """
        if not idea_tickers:
            return []

        cutoff = date.today() - timedelta(days=7)

        # 내 종목 중 트레이더들도 언급한 종목
        matches = self.db.query(
            TraderMention.stock_name,
            TraderMention.stock_code,
            func.count(TraderMention.id).label("mention_count"),
            func.max(TraderMention.mention_date).label("last_mention")
        ).filter(
            TraderMention.stock_code.in_(idea_tickers),
            TraderMention.mention_date >= cutoff
        ).group_by(
            TraderMention.stock_name,
            TraderMention.stock_code
        ).all()

        return [
            {
                "stock_name": m.stock_name,
                "stock_code": m.stock_code,
                "mention_count": m.mention_count,
                "last_mention": m.last_mention.isoformat() if m.last_mention else None,
            }
            for m in matches
        ]

    def _fetch_kis_prices(self, stock_codes: list[str]) -> dict:
        """KIS API로 주가 조회."""
        import asyncio
        from integrations.kis.client import KISClient

        async def fetch_all():
            # 매번 새 클라이언트 생성하여 이벤트 루프 문제 방지
            kis = KISClient()
            try:
                return await kis.get_multiple_prices(stock_codes)
            finally:
                await kis.close()

        try:
            return asyncio.run(fetch_all())
        except Exception as e:
            logger.warning(f"KIS API call failed: {e}")
            return {}

    def _enrich_with_kis_data(
        self,
        stocks: list[dict],
        is_rising: bool = False
    ) -> list[dict]:
        """KIS 데이터로 종목 정보 보강."""
        stock_codes = [s["stock_code"] for s in stocks if s.get("stock_code")]
        if not stock_codes:
            return stocks

        prices = self._fetch_kis_prices(stock_codes)

        for stock in stocks:
            code = stock.get("stock_code")
            if not code or code not in prices:
                continue

            price_info = prices[code]
            stock["current_price"] = int(price_info.get("current_price", 0))
            stock["price_change"] = int(price_info.get("change", 0))
            stock["price_change_rate"] = float(price_info.get("change_rate", 0))
            stock["volume"] = price_info.get("volume", 0)

            # 가중치 점수 계산
            stock["weighted_score"] = self._calculate_score(stock, is_rising)

        return stocks

    def _calculate_score(self, stock: dict, is_rising: bool = False) -> float:
        """가중치 점수 계산.

        언급 횟수/증가율 (40%) + 주가 상승률 (30%) + 거래량 (20%) + 신규 보너스 (10%)
        """
        score = 0.0

        # 1. 언급 점수 (40점)
        if is_rising:
            growth = stock.get("growth_rate", 0)
            mention_score = min(growth / 200 * 40, 40)
        else:
            count = stock.get("mention_count", 0)
            mention_score = min(count / 10 * 40, 40)
        score += mention_score

        # 2. 주가 상승률 (30점)
        price_change = stock.get("price_change_rate") or 0
        if price_change > 0:
            price_score = min(price_change / 10 * 30, 30)
        else:
            price_score = 0
        score += price_score

        # 3. 거래량 (20점)
        volume = stock.get("volume") or 0
        if volume > 0:
            volume_score = min(math.log10(volume + 1) / 7 * 20, 20)
        else:
            volume_score = 0
        score += volume_score

        # 4. 신규 보너스 (10점)
        if stock.get("is_new"):
            score += 10

        return round(score, 1)
