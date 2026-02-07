"""테마맵 싱글톤 서비스.

theme_map.json을 한 번만 로딩하여 메모리에 캐시하고,
여러 서비스/API에서 공유하여 사용.
"""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

THEME_MAP_PATH = Path(__file__).parent.parent / "data" / "theme_map.json"


class ThemeMapService:
    """테마맵 싱글톤 서비스.

    theme_map.json을 한 번만 로딩하고 정방향/역방향 매핑을 모두 제공.
    """

    def __init__(self):
        self._theme_map: dict[str, list[dict]] = {}
        self._stock_to_themes: dict[str, list[str]] = {}
        self._load()

    def _load(self):
        """theme_map.json 로드 및 역매핑 생성."""
        try:
            with open(THEME_MAP_PATH, "r", encoding="utf-8") as f:
                self._theme_map = json.load(f)

            # 역매핑: 종목코드 → 테마명 리스트
            for theme_name, stocks in self._theme_map.items():
                for stock in stocks:
                    code = stock.get("code")
                    if code:
                        if code not in self._stock_to_themes:
                            self._stock_to_themes[code] = []
                        self._stock_to_themes[code].append(theme_name)

            logger.info(
                f"ThemeMapService: {len(self._theme_map)} themes, "
                f"{len(self._stock_to_themes)} stocks loaded"
            )
        except Exception as e:
            logger.error(f"ThemeMapService: theme_map.json 로드 실패: {e}")

    def get_all_themes(self) -> dict[str, list[dict]]:
        """전체 테마맵 반환 (테마명 → 종목 리스트)."""
        return self._theme_map

    def get_stocks_in_theme(self, theme_name: str) -> list[dict]:
        """테마에 속한 종목 리스트 반환."""
        return self._theme_map.get(theme_name, [])

    def get_themes_for_stock(self, stock_code: str) -> list[str]:
        """종목이 속한 테마명 리스트 반환."""
        return self._stock_to_themes.get(stock_code, [])

    def get_stock_theme_map(self) -> dict[str, list[str]]:
        """역매핑 전체 반환 (종목코드 → 테마명 리스트)."""
        return self._stock_to_themes

    def get_all_stock_codes(self) -> set[str]:
        """테마맵에 등록된 모든 종목코드 반환."""
        codes = set()
        for stocks in self._theme_map.values():
            for stock in stocks:
                code = stock.get("code")
                if code:
                    codes.add(code)
        return codes

    def get_theme_names(self) -> list[str]:
        """전체 테마명 리스트 반환."""
        return list(self._theme_map.keys())

    def theme_count(self) -> int:
        """테마 수 반환."""
        return len(self._theme_map)

    def find_theme_stocks(self, theme_name: str, limit: int = 20) -> list[dict]:
        """테마명으로 종목 검색 (정확/부분/키워드 매칭).

        Gemini 등이 반환하는 다양한 테마명을 theme_map 키에 매핑.
        """
        # 1. 정확 매칭
        if theme_name in self._theme_map:
            return self._theme_map[theme_name][:limit]

        # 2. 부분 매칭
        for key, stocks in self._theme_map.items():
            if theme_name in key or key in theme_name:
                return stocks[:limit]

        # 3. 키워드 기반 매칭
        keywords = theme_name.replace("/", " ").replace("·", " ").split()
        for tk in keywords:
            if len(tk) >= 2 and tk in self._theme_map:
                return self._theme_map[tk][:limit]

        return []


# 싱글톤 인스턴스
_theme_map_service: Optional[ThemeMapService] = None


def get_theme_map_service() -> ThemeMapService:
    """ThemeMapService 싱글톤 반환."""
    global _theme_map_service
    if _theme_map_service is None:
        _theme_map_service = ThemeMapService()
    return _theme_map_service
