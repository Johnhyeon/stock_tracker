from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class DataSourcePlugin(ABC):
    """데이터 소스 플러그인 인터페이스

    새로운 데이터 소스(네이버 금융, 한국투자 API 등)를 추가할 때
    이 인터페이스를 구현합니다.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """플러그인 이름"""
        pass

    @abstractmethod
    async def fetch_price(self, ticker: str) -> Optional[float]:
        """현재가 조회"""
        pass

    @abstractmethod
    async def fetch_price_history(
        self, ticker: str, days: int
    ) -> List[Dict[str, Any]]:
        """과거 가격 데이터 조회"""
        pass

    @abstractmethod
    async def fetch_news(self, ticker: str, days: int) -> List[Dict[str, Any]]:
        """뉴스 데이터 조회"""
        pass


class AnalysisPlugin(ABC):
    """분석 플러그인 인터페이스

    AI 분석, 기술적 분석 등 분석 기능을 추가할 때
    이 인터페이스를 구현합니다.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """플러그인 이름"""
        pass

    @abstractmethod
    async def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """분석 실행"""
        pass


class AlertPlugin(ABC):
    """알림 플러그인 인터페이스

    텔레그램, 이메일, 슬랙 등 알림 기능을 추가할 때
    이 인터페이스를 구현합니다.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """플러그인 이름"""
        pass

    @abstractmethod
    async def send(self, message: str, **kwargs) -> bool:
        """알림 전송"""
        pass


class PluginRegistry:
    """플러그인 등록 및 관리"""

    def __init__(self):
        self._data_sources: Dict[str, DataSourcePlugin] = {}
        self._analyzers: Dict[str, AnalysisPlugin] = {}
        self._alerters: Dict[str, AlertPlugin] = {}

    def register_data_source(self, plugin: DataSourcePlugin) -> None:
        self._data_sources[plugin.name] = plugin

    def register_analyzer(self, plugin: AnalysisPlugin) -> None:
        self._analyzers[plugin.name] = plugin

    def register_alerter(self, plugin: AlertPlugin) -> None:
        self._alerters[plugin.name] = plugin

    def get_data_source(self, name: str) -> Optional[DataSourcePlugin]:
        return self._data_sources.get(name)

    def get_analyzer(self, name: str) -> Optional[AnalysisPlugin]:
        return self._analyzers.get(name)

    def get_alerter(self, name: str) -> Optional[AlertPlugin]:
        return self._alerters.get(name)

    @property
    def data_sources(self) -> List[str]:
        return list(self._data_sources.keys())

    @property
    def analyzers(self) -> List[str]:
        return list(self._analyzers.keys())

    @property
    def alerters(self) -> List[str]:
        return list(self._alerters.keys())


# 글로벌 플러그인 레지스트리
plugin_registry = PluginRegistry()
