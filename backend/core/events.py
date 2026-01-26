from enum import Enum
from typing import Callable, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime


class EventType(Enum):
    IDEA_CREATED = "idea_created"
    IDEA_UPDATED = "idea_updated"
    IDEA_DELETED = "idea_deleted"
    POSITION_ENTERED = "position_entered"
    POSITION_EXITED = "position_exited"
    FUNDAMENTAL_WARNING = "fundamental_warning"
    FOMO_DETECTED = "fomo_detected"
    TIME_EXPIRED = "time_expired"
    TARGET_REACHED = "target_reached"
    # Data collection events
    PRICE_UPDATED = "price_updated"
    DISCLOSURE_COLLECTED = "disclosure_collected"
    YOUTUBE_COLLECTED = "youtube_collected"


@dataclass
class Event:
    type: EventType
    payload: Dict[str, Any]
    entity_type: str = None
    entity_id: str = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


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
                    print(f"Error in event handler: {e}")


event_bus = EventBus()
