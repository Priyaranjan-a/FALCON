"""In-process publish/subscribe for live updates (scan progress to the console).

Publishers are scan-runner threads; subscribers are Server-Sent Events
responses on the event loop. ``publish`` is thread-safe and never blocks: a
slow subscriber loses intermediate frames (each queue is bounded) instead of
stalling a scan.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any


class EventHub:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self, topic: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=512)
        with self._lock:
            self._subscribers.setdefault(topic, set()).add(queue)
        return queue

    def unsubscribe(self, topic: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            subscribers = self._subscribers.get(topic)
            if subscribers:
                subscribers.discard(queue)
                if not subscribers:
                    del self._subscribers[topic]

    def publish(self, topic: str, event: dict[str, Any]) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        with self._lock:
            if topic not in self._subscribers:
                return
        try:
            loop.call_soon_threadsafe(self._fanout, topic, event)
        except RuntimeError:  # loop shutting down
            pass

    def _fanout(self, topic: str, event: dict[str, Any]) -> None:
        with self._lock:
            queues = list(self._subscribers.get(topic, ()))
        for queue in queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass


hub = EventHub()
