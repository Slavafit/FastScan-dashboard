from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any


class DashboardState:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {
            "summary": {},
            "history": [],
            "parties": [],
            "boxes": [],
            "health": {
                "onza": "waiting",
                "firebase": "waiting",
                "last_success": None,
                "last_attempt": None,
                "message": "Waiting for the first update",
            },
        }
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return deepcopy(self._data)

    async def update(self, data: dict[str, Any]) -> None:
        async with self._lock:
            self._data = deepcopy(data)
            snapshot = deepcopy(self._data)
        for subscriber in tuple(self._subscribers):
            if subscriber.full():
                try:
                    subscriber.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            subscriber.put_nowait(snapshot)

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)
