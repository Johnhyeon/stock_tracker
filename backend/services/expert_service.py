"""전문가 관심종목 서비스."""
import json
import logging
import math
from datetime import datetime, date, timedelta
from typing import Optional
from collections import defaultdict

from core.timezone import now_kst, today_kst

from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, asc

from models import ExpertMention, ExpertStats, Stock
from models.stock_ohlcv import StockOHLCV
from core.config import get_settings

logger = logging.getLogger(__name__)

MENTIONS_FILE_PATH = get_settings().mentions_file_path


class ExpertService:
    """전문가 관심종목 서비스."""

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

    def sync_mentions(self, file_path: str = MENTIONS_FILE_PATH, data: dict = None) -> dict:
        """mentions.json 파일 또는 직접 전달된 dict와 DB 동기화.

        Args:
            file_path: mentions.json 파일 경로 (data가 None일 때 사용)
            data: 직접 전달된 mentions 딕셔너리 (우선 사용)

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
            if data is None:
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
                    existing = self.db.query(ExpertMention).filter(
                        ExpertMention.stock_name == stock_name,
                        ExpertMention.mention_date == mention_date,
                        ExpertMention.source_link == source_link
                    ).first()

                    if not existing:
                        new_mention = ExpertMention(
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
                    updated = self.db.query(ExpertMention).filter(
                        ExpertMention.stock_name == stock_name,
                        ExpertMention.stock_code.is_(None)
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
        cutoff = today_kst() - timedelta(days=days_back)
        prev_cutoff = cutoff - timedelta(days=days_back)

        # 최근 기간 통계
        recent_stats = self.db.query(
            ExpertMention.stock_name,
            ExpertMention.stock_code,
            func.count(ExpertMention.id).label("mention_count"),
            func.min(ExpertMention.mention_date).label("first_date"),
            func.max(ExpertMention.mention_date).label("last_date"),
            func.avg(ExpertMention.change_rate).label("avg_change")
        ).filter(
            ExpertMention.mention_date >= cutoff
        ).group_by(
            ExpertMention.stock_name,
            ExpertMention.stock_code
        ).order_by(
            desc("mention_count")
        ).limit(limit * 2).all()

        # 이전 기간 언급 체크 (신규 판단용)
        prev_stocks = set(
            r[0] for r in self.db.query(ExpertMention.stock_name)
            .filter(
                ExpertMention.mention_date >= prev_cutoff,
                ExpertMention.mention_date < cutoff
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
        today = today_kst()
        half = days_back // 2

        recent_start = today - timedelta(days=half)
        prev_start = today - timedelta(days=days_back)
        prev_end = recent_start - timedelta(days=1)

        # 최근 기간 통계
        recent_stats = dict(
            self.db.query(
                ExpertMention.stock_name,
                func.count(ExpertMention.id).label("cnt")
            ).filter(
                ExpertMention.mention_date >= recent_start
            ).group_by(ExpertMention.stock_name).all()
        )

        # 이전 기간 통계
        prev_stats = dict(
            self.db.query(
                ExpertMention.stock_name,
                func.count(ExpertMention.id).label("cnt")
            ).filter(
                ExpertMention.mention_date >= prev_start,
                ExpertMention.mention_date <= prev_end
            ).group_by(ExpertMention.stock_name).all()
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
            mention = self.db.query(ExpertMention).filter(
                ExpertMention.stock_name == stock_name
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
        """전문가 성과 통계.

        Args:
            days_back: 분석 기간

        Returns:
            성과 통계
        """
        cutoff = today_kst() - timedelta(days=days_back)

        # 언급된 종목들 가져오기
        mentions = self.db.query(
            ExpertMention.stock_name,
            ExpertMention.stock_code,
            ExpertMention.mention_date,
            ExpertMention.change_rate
        ).filter(
            ExpertMention.mention_date >= cutoff,
            ExpertMention.stock_code.isnot(None)
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

    def get_performance_detail(self, days_back: int = 30) -> dict:
        """전문가 성과 상세 분석 (StockOHLCV 기반 실제 수익률).

        Args:
            days_back: 분석 기간

        Returns:
            종목별 상세 리스트 + 요약 통계
        """
        cutoff = today_kst() - timedelta(days=days_back)

        # 1. 기간 내 종목별 첫 언급일 + 언급 횟수
        stock_mentions = self.db.query(
            ExpertMention.stock_name,
            ExpertMention.stock_code,
            func.min(ExpertMention.mention_date).label("first_mention"),
            func.count(ExpertMention.id).label("mention_count"),
        ).filter(
            ExpertMention.mention_date >= cutoff,
            ExpertMention.stock_code.isnot(None),
        ).group_by(
            ExpertMention.stock_name,
            ExpertMention.stock_code,
        ).all()

        if not stock_mentions:
            return {
                "items": [],
                "summary": {
                    "total": 0,
                    "avg_return": 0.0,
                    "win_rate": 0.0,
                    "median_return": 0.0,
                },
            }

        items = []
        for sm in stock_mentions:
            stock_code = sm.stock_code
            first_mention = sm.first_mention

            # 2. 첫 언급일의 close_price (매수가) - 해당 날짜 또는 이전 가장 가까운 거래일
            mention_ohlcv = self.db.query(StockOHLCV).filter(
                StockOHLCV.stock_code == stock_code,
                StockOHLCV.trade_date <= first_mention,
            ).order_by(desc(StockOHLCV.trade_date)).first()

            if not mention_ohlcv:
                continue

            mention_price = int(mention_ohlcv.close_price)
            if mention_price <= 0:
                continue

            # 3. 최신 close_price (현재가)
            latest_ohlcv = self.db.query(StockOHLCV).filter(
                StockOHLCV.stock_code == stock_code,
            ).order_by(desc(StockOHLCV.trade_date)).first()

            if not latest_ohlcv:
                continue

            current_price = int(latest_ohlcv.close_price)
            return_rate = round((current_price - mention_price) / mention_price * 100, 2)

            # 4. 기간별 수익률 계산 (1d/3d/7d/14d)
            period_returns = {}
            for label, offset_days in [("1d", 1), ("3d", 3), ("7d", 7), ("14d", 14)]:
                target_date = first_mention + timedelta(days=offset_days)
                # target_date 이후 가장 가까운 거래일
                ohlcv = self.db.query(StockOHLCV).filter(
                    StockOHLCV.stock_code == stock_code,
                    StockOHLCV.trade_date >= target_date,
                ).order_by(asc(StockOHLCV.trade_date)).first()

                if ohlcv:
                    p = int(ohlcv.close_price)
                    period_returns[label] = round((p - mention_price) / mention_price * 100, 2)
                else:
                    period_returns[label] = None

            items.append({
                "stock_name": sm.stock_name,
                "stock_code": stock_code,
                "mention_date": first_mention.isoformat(),
                "mention_price": mention_price,
                "current_price": current_price,
                "return_rate": return_rate,
                "return_1d": period_returns["1d"],
                "return_3d": period_returns["3d"],
                "return_7d": period_returns["7d"],
                "return_14d": period_returns["14d"],
                "mention_count": sm.mention_count,
                "rank": 0,
            })

        # 5. 수익률 순 정렬 및 순위 부여
        items.sort(key=lambda x: x["return_rate"], reverse=True)
        for i, item in enumerate(items):
            item["rank"] = i + 1

        # 6. 요약 통계
        returns = [it["return_rate"] for it in items]
        total = len(returns)
        avg_return = round(sum(returns) / total, 2) if total else 0.0
        win_count = sum(1 for r in returns if r > 0)
        win_rate = round(win_count / total * 100, 1) if total else 0.0
        sorted_returns = sorted(returns)
        if total % 2 == 0 and total > 0:
            median_return = round((sorted_returns[total // 2 - 1] + sorted_returns[total // 2]) / 2, 2)
        elif total > 0:
            median_return = sorted_returns[total // 2]
        else:
            median_return = 0.0

        return {
            "items": items,
            "summary": {
                "total": total,
                "avg_return": avg_return,
                "win_rate": win_rate,
                "median_return": median_return,
            },
        }

    def get_new_mentions(self, since_hours: int = 24) -> list[dict]:
        """새로운 언급 조회 (알림용).

        Args:
            since_hours: 몇 시간 전부터

        Returns:
            새로운 언급 리스트
        """
        cutoff = now_kst().replace(tzinfo=None) - timedelta(hours=since_hours)

        mentions = self.db.query(ExpertMention).filter(
            ExpertMention.created_at >= cutoff
        ).order_by(desc(ExpertMention.created_at)).all()

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
        """내 아이디어 종목과 전문가 관심종목 크로스 체크.

        Args:
            idea_tickers: 내 아이디어 종목코드 리스트

        Returns:
            겹치는 종목 리스트
        """
        if not idea_tickers:
            return []

        cutoff = today_kst() - timedelta(days=7)

        # 내 종목 중 전문가들도 언급한 종목
        matches = self.db.query(
            ExpertMention.stock_name,
            ExpertMention.stock_code,
            func.count(ExpertMention.id).label("mention_count"),
            func.max(ExpertMention.mention_date).label("last_mention")
        ).filter(
            ExpertMention.stock_code.in_(idea_tickers),
            ExpertMention.mention_date >= cutoff
        ).group_by(
            ExpertMention.stock_name,
            ExpertMention.stock_code
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
        """DB(stock_ohlcv)에서 최신 종가/거래량 조회."""
        if not stock_codes:
            return {}

        result = {}
        for code in stock_codes:
            rows = (
                self.db.query(StockOHLCV)
                .filter(StockOHLCV.stock_code == code)
                .order_by(StockOHLCV.trade_date.desc())
                .limit(2)
                .all()
            )
            if not rows:
                continue
            latest = rows[0]
            prev_close = rows[1].close_price if len(rows) >= 2 else latest.close_price
            change = latest.close_price - prev_close
            change_rate = round(change / prev_close * 100, 2) if prev_close else 0.0
            result[code] = {
                "current_price": latest.close_price,
                "change": change,
                "change_rate": change_rate,
                "volume": latest.volume,
                "prev_close": prev_close,
            }
        return result

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
