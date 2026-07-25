"""
Event bus for the dashboard — bridges the training loop to SSE clients.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Dict, List


class EventBus:
    """Simple pub/sub event bus for SSE streaming."""

    def __init__(self):
        self._subscribers: List[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def publish(self, event: str, data: Dict[str, Any]) -> None:
        """Publish an event to all subscribers."""
        payload = json.dumps({"event": event, "data": data})
        dead: List[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.unsubscribe(q)


# Global singleton
event_bus = EventBus()


def make_callback(bus: EventBus):
    """Create a callback function compatible with TrainingLoop."""
    def callback(event: str, data: Dict[str, Any]) -> None:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(bus.publish(event, data))
        except RuntimeError:
            pass  # no event loop running
    return callback
