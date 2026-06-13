# AgentBridge

AgentBridge is a local desktop bridge that connects a PyQt control panel, a FastAPI WebSocket server, and a Playwright-driven Gemini browser session. It keeps a persistent Google login profile, accepts prompts from websocket clients, and returns Gemini responses back to connected clients.

## Features

- Persistent Gemini session using a Chrome profile directory.
- Headless login check using Google account status.
- Optional headed login for first-time or failed manual sign-in.
- Local websocket API for external clients.
- Desktop UI for server control, authentication, session reset, and test prompts.
- Chat history and app state persistence.
- Debug logging for browser lifecycle and request flow.

## Architecture

AgentBridge is built from four main layers:

- **Desktop UI**: a PyQt window that starts/stops the service, opens login, clears the session, and sends test prompts.
- **Runtime**: the bootstrap layer that connects the UI, app state, browser worker, and websocket server.
- **WebSocket server**: a FastAPI-based service that accepts client messages and forwards them to the worker.
- **Gemini Worker**: a Playwright automation layer that opens Gemini, checks login state, sends prompts, and scrapes responses.

## How it works

### 1. Startup
When the app starts, it creates shared state, the background asyncio loop, the Gemini worker, and the websocket manager. The browser is not launched immediately.

### 2. Start server
When the user clicks **Start Server**, AgentBridge:
1. starts the Gemini worker,
2. launches a persistent Chrome context,
3. checks whether the user is already logged in,
4. starts the websocket server on an available port.

### 3. Login flow
AgentBridge uses a headless-first login check:
- It opens `https://myaccount.google.com/` in headless mode.
- If the URL stays on Google Accounts, the user is considered logged in.
- If it redirects elsewhere, the user is considered not logged in.

If login is required, the app can open a headed Chrome window for manual sign-in. After that, the persistent profile is reused on later runs.

### 4. Prompt flow
When a client sends an `ask` request:
1. The worker ensures Gemini is available.
2. It navigates to the active chat or Gemini home page.
3. It types the prompt into the Gemini input box.
4. It submits the prompt.
5. It scrapes the latest assistant response from the page.
6. It returns the response to the websocket client.

### 5. Response selection
The worker uses a response fingerprint to reduce stale-answer reuse. It compares the latest extracted response against the previous response and only accepts a genuinely new answer.

## Project layout

Typical modules in this project:

- `bootstrap.py` — application runtime and startup/shutdown wiring.
- `app/services/gemini_worker.py` — Gemini browser automation.
- `app/services/connection_manager.py` — WebSocket client tracking and broadcast.
- `app/server.py` — FastAPI websocket server factory.
- `app/state.py` — persistent app state and chat history.
- `app/ui/desktop_app.py` — PyQt desktop interface.
- `app/services/protocol_service.py` — request/response message helpers.
- `app/services/request_router.py` — routes incoming websocket messages.
- `app/services/chat_session_store.py` — stores session-related data.
- `app/services/status_service.py` — status helpers.

## Requirements

- Python 3.11 or newer.
- Google Chrome installed.
- A working Gemini/Google account session.
- Windows or another environment supported by PyQt6 and Playwright.

## Installation

```bash
git clone <your-repo-url>
cd AgentBridge

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
playwright install chrome
```

If your project uses a different browser setup, install the Playwright browser binaries required by your environment.

## Configuration

Common configuration values are typically stored in `app/config.py`:

- `HOST`
- `PROFILE_DIR`
- `GEMINI_URL`
- `GOOGLE_LOGIN_URL`
- `REQUEST_TIMEOUT_SEC`
- `SCRAPE_POLL_INTERVAL`
- `SCRAPE_STABLE_POLLS`

Make sure `PROFILE_DIR` points to a persistent folder so login cookies survive restarts.

## Usage

### Run the desktop app

```bash
python bootstrap.py
```

### Start the service
1. Open the desktop app.
2. Click **Start Server**.
3. Wait for the server and browser status to become ready.

### Authenticate
1. Click **Authenticate**.
2. If already logged in, the app will confirm it.
3. If not logged in, a visible Chrome window opens for manual sign-in.
4. After login, close the browser window and the app rechecks the session.

### Send a test prompt
1. Open the advanced panel.
2. Type a prompt into the test chat box.
3. Click **Send**.
4. The response appears in the chat output and websocket clients receive the same result.

### Connect a websocket client
External clients can connect to the local websocket endpoint shown in the UI logs, then send request messages such as `ask` and `ping`.

## Message flow

### Client to server
Common message types:

- `ping`
- `ask`
- other request types defined by your router/protocol layer

### Server to client
Common response types:

- `ask_result`
- `error`
- status or broadcast updates

## State management

AgentBridge persists:

- server status,
- browser readiness,
- login state,
- active port,
- current Gemini chat URL,
- connected client count,
- chat history.

This makes the app recoverable across restarts and helps debugging.

## Logging

The app prints useful lifecycle logs such as:

- worker start and stop,
- login probe results,
- browser mode changes,
- websocket connect/disconnect events,
- prompt submission and response length,
- saved Gemini chat URL.

These logs are important for diagnosing stale response scraping, login state issues, and duplicate request handling.

## Testing

Useful test cases:

1. Fresh profile, no login.
2. Headless login probe on startup.
3. Manual headed login flow.
4. Restart with the same profile and confirm login persists.
5. Send one prompt and verify the returned response is correct.
6. Send two prompts in sequence and confirm the second response is not the first repeated.
7. Long chat session and confirm response extraction still works.

A separate test harness can be used to validate response fingerprinting and stale-answer rejection before running the live browser.

## Troubleshooting

### Login is not detected
- Confirm `PROFILE_DIR` is the same between runs.
- Confirm Chrome is installed and accessible.
- Try clearing the profile directory and logging in again.

### Old response repeats
- Confirm the worker is using the latest response fingerprint logic.
- Check whether the Gemini DOM changed and the selectors need updating.
- Verify that the response extractor is not reading the previous assistant block.

### WebSocket clients disconnect
- Confirm the server is running.
- Check the websocket URL printed in logs.
- Make sure the client sends valid JSON messages.

### Browser closes unexpectedly
- Check whether visible and headless modes are being switched intentionally.
- Review `_mark_closed()` and `_close_context_only()` lifecycle logs.
- Confirm the same Playwright profile directory is reused.

## Development notes

The most important design rule in this project is to keep:
- login logic separate from Gemini readiness,
- websocket transport separate from browser control,
- and response scraping separate from request routing.

That separation keeps debugging manageable and reduces repeated-response bugs.

## Future improvements

Possible upgrades:
- stronger response-node tracking instead of DOM text scraping,
- request IDs stored through the full ask/response path,
- better UI status for headless vs headed mode,
- per-session debug snapshots,
- a proper automated test suite for worker behavior.

## License

Add your project license here.

## Credits

Built around:
- PyQt6 for the desktop UI,
- FastAPI for the websocket server,
- Playwright for browser automation.