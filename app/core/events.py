from abc import ABC, abstractmethod
from typing import Any, Dict
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from app.core.uuid import generate_uuidv7

class DomainEvent(BaseModel):
    """Base Domain Event."""
    event_id: str = Field(default_factory=lambda: str(generate_uuidv7()))
    occurred_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_name: str

class UserRegisteredEvent(DomainEvent):
    """Event published when a new user registers (INV-AUTH-001/002)."""
    user_id: str
    email: str
    role: str
    
    def __init__(self, **data: Any):
        super().__init__(event_name="UserRegisteredEvent", **data)

class EventDispatcherInterface(ABC):
    """Interface for publishing domain events."""
    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        pass

class InMemoryEventDispatcher(EventDispatcherInterface):
    """InMemory stub for domain event dispatching."""
    def __init__(self):
        self.published_events = []

    async def publish(self, event: DomainEvent) -> None:
        self.published_events.append(event)

_event_dispatcher = InMemoryEventDispatcher()

def get_event_dispatcher() -> EventDispatcherInterface:
    return _event_dispatcher
