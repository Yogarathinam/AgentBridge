from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.config import APP_NAME, CHAT_HISTORY_FILE, QUEUE_LIMIT, STATE_FILE
from app.models import AppStatus, ChatMessage


class AppState:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.status = AppStatus(app_name=APP_NAME, queue_limit=QUEUE_LIMIT)
        self.messages: list[ChatMessage] = []
        self._load()

    def _safe_json_load(self, path: Path) -> Any:
        try:
            if not path.exists():
                return None
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return None

    def _load(self) -> None:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = self._safe_json_load(STATE_FILE)
        if isinstance(data, dict):
            for key, value in data.items():
                if hasattr(self.status, key):
                    setattr(self.status, key, value)

        items = self._safe_json_load(CHAT_HISTORY_FILE)
        if isinstance(items, list):
            loaded: list[ChatMessage] = []
            for item in items:
                try:
                    if isinstance(item, dict) and 'role' in item and 'text' in item:
                        loaded.append(ChatMessage(**item))
                except Exception:
                    continue
            self.messages = loaded

        self._normalize_status()

    def _normalize_status(self) -> None:
        s = self.status
        if s.queue_limit <= 0:
            s.queue_limit = QUEUE_LIMIT
        if s.queue_size < 0:
            s.queue_size = 0
        if s.connected_clients < 0:
            s.connected_clients = 0
        if not isinstance(s.server_running, bool):
            s.server_running = bool(s.server_running)
        if not isinstance(s.browser_ready, bool):
            s.browser_ready = bool(s.browser_ready)
        if not isinstance(s.logged_in, bool):
            s.logged_in = bool(s.logged_in)
        if not isinstance(s.busy, bool):
            s.busy = bool(s.busy)
        if not isinstance(s.test_mode, bool):
            s.test_mode = bool(s.test_mode)
        if not isinstance(s.first_run, bool):
            s.first_run = bool(s.first_run)
            
        # --- NEW CODE: Normalize force_update ---
        if not hasattr(s, 'force_update') or not isinstance(getattr(s, 'force_update', False), bool):
            s.force_update = bool(getattr(s, 'force_update', False))
        # ----------------------------------------
        
        if s.current_port is not None:
            try:
                s.current_port = int(s.current_port)
            except Exception:
                s.current_port = None
        if s.last_error is None:
            s.last_error = ''
        if s.last_info is None:
            s.last_info = ''

    def _write_atomic(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(content, encoding='utf-8')
        tmp.replace(path)

    def save(self) -> None:
            with self._lock:
                self._normalize_status()
                
                # 1. Grab the dictionary
                data_to_save = self.status.to_dict()
                
                # 2. Strip out 'force_update' so it NEVER saves to state.json
                data_to_save.pop('force_update', None)
                
                # 3. Save the clean data to the hard drive
                self._write_atomic(STATE_FILE, json.dumps(data_to_save, indent=2, ensure_ascii=False))
                self._write_atomic(CHAT_HISTORY_FILE, json.dumps([m.__dict__ for m in self.messages], indent=2, ensure_ascii=False))
                
    def update_status(self, **kwargs: Any) -> None:
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.status, key):
                    setattr(self.status, key, value)
            self._normalize_status()
            self.save()

    def add_message(self, role: str, text: str) -> None:
        with self._lock:
            self.messages.append(ChatMessage(role=role, text=text))
            self.save()

    def clear_messages(self) -> None:
        with self._lock:
            self.messages = []
            self.save()

    def get_messages(self) -> list[dict[str, str]]:
        with self._lock:
            return [m.__dict__.copy() for m in self.messages]

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            self._normalize_status()
            return self.status.to_dict()