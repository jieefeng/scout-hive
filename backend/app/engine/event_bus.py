import asyncio
from typing import Callable, Any

from pydantic import BaseModel


class Event(BaseModel):
    type: str  # node_started | node_completed | node_failed | task_completed | review_feedback
    task_id: str
    node_id: str = ""
    data: dict = {}


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}
        self._history: list[Event] = []

    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    async def publish(self, event: Event):
        self._history.append(event)
        for callback in self._subscribers.get(event.type, []):
            if asyncio.iscoroutinefunction(callback):
                await callback(event)
            else:
                callback(event)

    def get_history(self, task_id: str | None = None) -> list[Event]:
        if task_id:
            return [e for e in self._history if e.task_id == task_id]
        return list(self._history)
