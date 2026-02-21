import logging
from enum import Enum
from typing import Callable, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime
from core.timezone import now_kst

logger = logging.getLogger(__name__)


class EventType(Enum):
    IDEA_CREATED = "idea_created"
    IDEA_UPDATED = "idea_updated"
    IDEA_DELETED = "idea_deleted"
    POSITION_ENTERED = "position_entered"
    POSITION_EXITED = "position_exited"
    POSITION_ADDED_BUY = "position_added_buy"
    POSITION_PARTIAL_EXIT = "position_partial_exit"
    FUNDAMENTAL_WARNING = "fundamental_warning"
    FOMO_DETECTED = "fomo_detected"
    TIME_EXPIRED = "time_expired"
    TARGET_REACHED = "target_reached"
    # Data collection events
    PRICE_UPDATED = "price_updated"
    DISCLOSURE_COLLECTED = "disclosure_collected"
    YOUTUBE_COLLECTED = "youtube_collected"
    # Snapshot events
    SNAPSHOT_REQUESTED = "snapshot_requested"


@dataclass
class Event:
    type: EventType
    payload: Dict[str, Any]
    entity_type: str = None
    entity_id: str = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = now_kst()


class EventBus:
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}

    def subscribe(self, event_type: EventType, handler: Callable) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable) -> None:
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(handler)

    async def publish(self, event: Event) -> None:
        if event.type in self._subscribers:
            for handler in self._subscribers[event.type]:
                try:
                    if callable(handler):
                        result = handler(event)
                        if hasattr(result, '__await__'):
                            await result
                except Exception as e:
                    logger.error(f"Event handler error for {event.type.value}: {e}", exc_info=True)


event_bus = EventBus()
