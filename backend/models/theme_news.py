"""테마 관련 뉴스 모델."""
import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import Column, String, Text, DateTime, Integer, Date, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB

from core.database import Base


class ThemeNews(Base):
    """테마 관련 뉴스 원본 데이터."""
    __tablename__ = "theme_news"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 테마 정보
    theme_name = Column(String(100), nullable=False)  # 테마명
    matched_keyword = Column(String(100), nullable=False)  # 매칭된 키워드

    # 뉴스 정보
    news_title = Column(String(500), nullable=False)  # 뉴스 제목
    news_source = Column(String(100), nullable=True)  # 뉴스 출처 (매경, 한경 등)
    news_url = Column(String(1000), nullable=False, unique=True)  # URL (중복 체크용)
    published_at = Column(DateTime, nullable=False)  # 뉴스 발행 시간

    # 메타데이터
    description = Column(Text, nullable=True)  # 뉴스 요약/설명
    collection_source = Column(String(50), nullable=False)  # 수집 소스 (naver_api, rss)
    is_quality = Column(Boolean, default=False, nullable=False)  # 양질의 뉴스 여부 (정책, 계약 등)

    __table_args__ = (
        Index("ix_theme_news_theme_name", "theme_name"),
        Index("ix_theme_news_published_at", "published_at"),
        Index("ix_theme_news_theme_published", "theme_name", "published_at"),
    )

    def __repr__(self):
        return f"<ThemeNews {self.theme_name} - {self.news_title[:30]}>"


class ThemeNewsStats(Base):
    """테마별 일별 뉴스 통계."""
    __tablename__ = "theme_news_stats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 테마 및 날짜
    theme_name = Column(String(100), nullable=False)
    stat_date = Column(Date, nullable=False)

    # 통계
    mention_count = Column(Integer, default=0, nullable=False)  # 총 언급 횟수
    unique_sources = Column(Integer, default=0, nullable=False)  # 고유 출처 수
    top_keywords = Column(JSONB, default=list)  # 상위 키워드 목록 [{"keyword": "xxx", "count": 10}, ...]

    # 추이 분석용
    wow_change_pct = Column(Integer, nullable=True)  # 전주 대비 변화율 (%)

    __table_args__ = (
        Index("ix_theme_news_stats_theme_date", "theme_name", "stat_date", unique=True),
        Index("ix_theme_news_stats_stat_date", "stat_date"),
    )

    def __repr__(self):
        return f"<ThemeNewsStats {self.theme_name} {self.stat_date} - {self.mention_count}건>"
