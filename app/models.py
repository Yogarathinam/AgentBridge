from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class QueueItem:
    request_id: str
    prompt: str
    source: str
    created_at: str = field(default_factory=now_iso)


@dataclass
class ChatMessage:
    role: str
    text: str
    created_at: str = field(default_factory=now_iso)


@dataclass
class AppStatus:
    app_name: str
    server_running: bool = False
    current_port: int | None = None
    logged_in: bool = False
    browser_ready: bool = False
    busy: bool = False
    connected_clients: int = 0
    queue_size: int = 0
    queue_limit: int = 5
    current_chat_url: str | None = None
    last_error: str = ''
    last_info: str = 'Starting...'
    test_mode: bool = True
    first_run: bool = True
    service_started: bool = False
    user_email: str | None = None
    latest_version: str | None = None
    update_available: bool = False
    cloud_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()