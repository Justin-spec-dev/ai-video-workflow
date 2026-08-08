"""In-memory EventBus broadcasting to /ws/events subscribers."""
from __future__ import annotations

import asyncio
import time
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def publish(self, event: str, payload: dict[str, Any]) -> None:
        msg = {"event": event, "ts": int(time.time()), "payload": payload}
        for q in list(self._subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                # drop slow subscribers' oldest messages instead of blocking
                try:
                    q.get_nowait()
                    q.put_nowait(msg)
                except Exception:
                    pass


bus = EventBus()
