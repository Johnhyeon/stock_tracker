"""YouTube 종목 언급 모델."""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from core.database import Base


class YouTubeMention(Base):
    """YouTube 영상에서 추출된 종목 언급 정보."""
    __tablename__ = "youtube_mentions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # YouTube 영상 정보
    video_id = Column(String(20), nullable=False)  # YouTube 비디오 ID
    video_title = Column(String(500), nullable=False)  # 영상 제목
    channel_id = Column(String(50), nullable=False)  # 채널 ID
    channel_name = Column(String(200), nullable=True)  # 채널명
    published_at = Column(DateTime, nullable=False)  # 영상 게시 시간

    # 영상 메타데이터
    view_count = Column(Integer, nullable=True)  # 조회수
    like_count = Column(Integer, nullable=True)  # 좋아요 수
    comment_count = Column(Integer, nullable=True)  # 댓글 수
    duration = Column(String(20), nullable=True)  # 영상 길이 (ISO 8601)

    # 종목 언급 정보
    mentioned_tickers = Column(ARRAY(String), default=list, nullable=False)  # 언급된 종목코드 목록
    ticker_context = Column(Text, nullable=True)  # 언급 맥락 (제목/설명에서 추출)

    thumbnail_url = Column(String(500), nullable=True)  # 썸네일 URL

    __table_args__ = (
        Index("ix_youtube_mentions_video_id", "video_id"),
        Index("ix_youtube_mentions_channel_id", "channel_id"),
        Index("ix_youtube_mentions_published_at", "published_at"),
    )

    def __repr__(self):
        return f"<YouTubeMention {self.video_id} - {self.video_title[:30]}>"
