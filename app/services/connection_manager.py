from __future__ import annotations

import asyncio
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self, on_change):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._on_change = on_change

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
            count = len(self._connections)
        print(f'[ws] connected clients={count}')
        self._on_change(count)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)
            count = len(self._connections)
        print(f'[ws] disconnected clients={count}')
        self._on_change(count)

    async def broadcast(self, message: dict) -> None:
        async with self._lock:
            connections = list(self._connections)
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                pass

    def count(self) -> int:
        return len(self._connections)