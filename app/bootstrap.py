from __future__ import annotations

import asyncio
import shutil
import threading
from dataclasses import dataclass, field

import uvicorn

from app.config import HOST, PROFILE_DIR
from app.port_manager import find_available_port
from app.server import create_server
from app.services.connection_manager import ConnectionManager
from app.services.gemini_worker import GeminiWorker
from app.state import AppState
from app.ui.desktop_app import AgentBridgeWindow


class AsyncBridgeLoop:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self.runtime = None

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=2)


@dataclass
class Runtime:
    state: AppState
    gemini_loop: AsyncBridgeLoop
    gemini_worker: GeminiWorker
    connection_manager: ConnectionManager | None
    window: AgentBridgeWindow | None = None
    logs: list[str] = field(default_factory=list)
    server_thread: threading.Thread | None = None
    uvicorn_server: uvicorn.Server | None = None
    server_started: bool = False

    def log(self, text: str) -> None:
        print(f'[runtime] {text}')
        self.logs.append(text)
        if len(self.logs) > 300:
            self.logs = self.logs[-300:]

    async def ask_from_ui(self, prompt: str) -> dict:
        return await self.gemini_worker.ask(prompt)

    async def start_service(self) -> int:
        if self.server_started and self.state.get_status().get('server_running'):
            return int(self.state.get_status().get('current_port') or 0)

        await self.gemini_worker.start()

        self.log('Performing startup login probe...')
        is_logged_in = await self.gemini_worker.check_login()
        if is_logged_in:
            self.log('Startup probe passed: Authenticated.')
        else:
            self.log('Startup probe failed: Not authenticated.')

        port = self.state.get_status().get('current_port')
        if not port:
            port = find_available_port()

        info_msg = (
            f'WebSocket server running on {HOST}:{port}. '
            + ('Authenticated.' if is_logged_in else 'Login required.')
        )

        self.state.update_status(
            server_running=True,
            current_port=port,
            last_info=info_msg,
            last_error='',
        )

        app = create_server(self)
        config = uvicorn.Config(app=app, host=HOST, port=port, log_level='warning')
        server = uvicorn.Server(config)
        self.uvicorn_server = server

        def run_server():
            self.log(f'Server started on ws://{HOST}:{port}/ws')
            try:
                server.run()
            finally:
                self.state.update_status(
                    server_running=False,
                    last_info='WebSocket server stopped.',
                )
                self.server_started = False
                self.log('Server stopped')

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        self.server_thread = thread
        self.server_started = True
        return port

    async def stop_service(self) -> None:
        try:
            await self.gemini_worker.stop()
        except Exception:
            pass

        if self.uvicorn_server:
            self.uvicorn_server.should_exit = True

        self.state.update_status(
            server_running=False,
            browser_ready=False,
            logged_in=False,
            busy=False,
            last_info='Service stopped.',
        )
        self.server_started = False

    def clear_profile(self):
        try:
            self.gemini_loop.run(self.stop_service())
        except Exception:
            pass
        if PROFILE_DIR.exists():
            shutil.rmtree(PROFILE_DIR, ignore_errors=True)
            self.log('Profile cleared')
        self.state.update_status(
            server_running=False,
            browser_ready=False,
            logged_in=False,
            busy=False,
            current_port=None,
            last_info='Profile cleared. Restart service to create a fresh session.',
            last_error='',
        )

    def shutdown(self):
        try:
            self.gemini_loop.run(self.stop_service())
        except Exception:
            pass
        self.gemini_loop.stop()


def bootstrap_app() -> Runtime:
    state = AppState()
    state.update_status(
        last_info='Starting AgentBridge...',
        server_running=False,
        browser_ready=False,
        logged_in=False,
        current_port=None,
        connected_clients=0,
        busy=False,
    )

    gemini_loop = AsyncBridgeLoop()
    gemini_worker = GeminiWorker(state)
    runtime = Runtime(
        state=state,
        gemini_loop=gemini_loop,
        gemini_worker=gemini_worker,
        connection_manager=None,
    )
    gemini_loop.runtime = runtime

    def on_connections(count: int):
        state.update_status(connected_clients=count)
        runtime.log(f'Connected clients: {count}')

    connection_manager = ConnectionManager(on_connections)
    runtime.connection_manager = connection_manager

    runtime.log('Gemini worker will start only when service starts')

    window = AgentBridgeWindow(runtime)
    runtime.window = window
    return runtime