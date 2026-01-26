"""텔레그램 모니터링 API."""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from models import TelegramChannel, TelegramKeywordMatch
from services.telegram_monitor_service import TelegramMonitorService

router = APIRouter(prefix="/telegram-monitor", tags=["telegram-monitor"])


# Schemas
class ChannelCreate(BaseModel):
    """채널 추가 요청."""
    username: Optional[str] = None  # @username (이걸로 조회)
    link: Optional[str] = None  # t.me/xxx 링크
    channel_id: Optional[int] = None  # 직접 ID 지정
    channel_name: Optional[str] = None  # 직접 이름 지정


class ChannelResponse(BaseModel):
    """채널 응답."""
    id: str
    channel_id: int
    channel_name: str
    channel_username: Optional[str]
    is_enabled: bool
    last_message_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KeywordMatchResponse(BaseModel):
    """키워드 매칭 응답."""
    id: str
    channel_name: str
    message_text: str
    message_date: datetime
    matched_keyword: str
    stock_code: Optional[str]
    notification_sent: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MonitorStatusResponse(BaseModel):
    """모니터링 상태 응답."""
    is_configured: bool
    enabled_channels: int
    active_keywords: int
    recent_matches: int


class MonitorCycleResponse(BaseModel):
    """모니터링 사이클 결과."""
    checked_channels: int
    matches_found: int
    notifications_sent: int
    error: Optional[str] = None


# Endpoints
@router.get("/status", response_model=MonitorStatusResponse)
async def get_monitor_status(db: AsyncSession = Depends(get_async_db)):
    """모니터링 상태 조회."""
    service = TelegramMonitorService(db)

    # 활성 채널 수
    channels = await service.get_enabled_channels()

    # 활성 키워드 수
    keywords = await service.get_active_keywords()

    # 최근 7일 매칭 수
    recent = await service.get_recent_matches(days=7)

    return MonitorStatusResponse(
        is_configured=service.is_configured,
        enabled_channels=len(channels),
        active_keywords=len(keywords),
        recent_matches=len(recent),
    )


@router.get("/channels", response_model=list[ChannelResponse])
async def list_channels(db: AsyncSession = Depends(get_async_db)):
    """등록된 채널 목록 조회."""
    stmt = select(TelegramChannel).order_by(TelegramChannel.created_at.desc())
    result = await db.execute(stmt)
    channels = result.scalars().all()

    return [
        ChannelResponse(
            id=str(ch.id),
            channel_id=ch.channel_id,
            channel_name=ch.channel_name,
            channel_username=ch.channel_username,
            is_enabled=ch.is_enabled,
            last_message_id=ch.last_message_id,
            created_at=ch.created_at,
            updated_at=ch.updated_at,
        )
        for ch in channels
    ]


def parse_telegram_link(link: str) -> Optional[str]:
    """텔레그램 링크에서 username/invite 추출."""
    import re
    # https://t.me/username, t.me/username
    match = re.search(r't\.me/([+\w]+)', link)
    if match:
        return match.group(1)
    return None


@router.post("/channels", response_model=ChannelResponse)
async def add_channel(
    request: ChannelCreate,
    db: AsyncSession = Depends(get_async_db),
):
    """모니터링 채널 추가."""
    service = TelegramMonitorService(db)

    # 링크에서 username 추출
    target = None
    if request.link:
        target = parse_telegram_link(request.link)
        if not target:
            raise HTTPException(
                status_code=400,
                detail="유효하지 않은 텔레그램 링크입니다.",
            )
    elif request.username:
        target = request.username

    # username/링크로 조회하는 경우
    if target:
        if not service.is_configured:
            raise HTTPException(
                status_code=400,
                detail="Telegram API가 설정되지 않아 조회할 수 없습니다. channel_id를 직접 입력해주세요.",
            )

        channel_info = await service.resolve_channel_by_username(target)
        if not channel_info:
            raise HTTPException(
                status_code=404,
                detail=f"채널을 찾을 수 없습니다: {target}",
            )

        channel = await service.add_channel(
            channel_id=channel_info["channel_id"],
            channel_name=channel_info["channel_name"],
            channel_username=channel_info["channel_username"],
        )

    # channel_id 직접 지정하는 경우
    elif request.channel_id and request.channel_name:
        channel = await service.add_channel(
            channel_id=request.channel_id,
            channel_name=request.channel_name,
            channel_username=None,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="username 또는 (channel_id + channel_name)을 입력해주세요.",
        )

    return ChannelResponse(
        id=str(channel.id),
        channel_id=channel.channel_id,
        channel_name=channel.channel_name,
        channel_username=channel.channel_username,
        is_enabled=channel.is_enabled,
        last_message_id=channel.last_message_id,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )


@router.delete("/channels/{channel_id}")
async def remove_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    """모니터링 채널 삭제."""
    stmt = delete(TelegramChannel).where(TelegramChannel.channel_id == channel_id)
    result = await db.execute(stmt)
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="채널을 찾을 수 없습니다.")

    return {"message": "채널이 삭제되었습니다."}


@router.patch("/channels/{channel_id}/toggle")
async def toggle_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    """채널 활성화/비활성화 토글."""
    stmt = select(TelegramChannel).where(TelegramChannel.channel_id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="채널을 찾을 수 없습니다.")

    channel.is_enabled = not channel.is_enabled
    await db.commit()

    return {
        "channel_id": channel_id,
        "is_enabled": channel.is_enabled,
    }


@router.get("/keywords")
async def list_keywords(db: AsyncSession = Depends(get_async_db)):
    """현재 모니터링 중인 키워드 목록."""
    service = TelegramMonitorService(db)
    keywords = await service.get_active_keywords()

    return {
        "count": len(keywords),
        "keywords": list(keywords.keys()),
    }


@router.get("/matches", response_model=list[KeywordMatchResponse])
async def list_matches(
    days: int = 7,
    limit: int = 50,
    db: AsyncSession = Depends(get_async_db),
):
    """최근 키워드 매칭 기록 조회."""
    service = TelegramMonitorService(db)
    matches = await service.get_recent_matches(days=days, limit=limit)

    return [
        KeywordMatchResponse(
            id=str(m.id),
            channel_name=m.channel_name,
            message_text=m.message_text,
            message_date=m.message_date,
            matched_keyword=m.matched_keyword,
            stock_code=m.stock_code,
            notification_sent=m.notification_sent,
            created_at=m.created_at,
        )
        for m in matches
    ]


@router.post("/run", response_model=MonitorCycleResponse)
async def run_monitor_cycle(db: AsyncSession = Depends(get_async_db)):
    """모니터링 사이클 수동 실행."""
    service = TelegramMonitorService(db)

    if not service.is_configured:
        raise HTTPException(
            status_code=400,
            detail="Telegram API가 설정되지 않았습니다. .env에 TELEGRAM_API_ID, TELEGRAM_API_HASH를 설정해주세요.",
        )

    result = await service.run_monitor_cycle()
    return MonitorCycleResponse(**result)


@router.post("/test-connection")
async def test_connection(db: AsyncSession = Depends(get_async_db)):
    """텔레그램 연결 테스트."""
    service = TelegramMonitorService(db)

    if not service.is_configured:
        raise HTTPException(
            status_code=400,
            detail="Telegram API가 설정되지 않았습니다.",
        )

    try:
        connected = await service.connect()
        if connected:
            await service.disconnect()
            return {"status": "success", "message": "텔레그램 연결 성공"}
        else:
            return {"status": "failed", "message": "텔레그램 연결 실패"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
