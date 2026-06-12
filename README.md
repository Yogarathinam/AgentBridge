# AgentBridge

Local desktop bridge for a logged-in Gemini web session.

## Features
- PyQt6 desktop control panel
- Visible Playwright Chromium worker
- Persistent login/profile storage
- FastAPI WebSocket bridge with fallback ports 8765-8769
- Bounded request queue
- Connection detection
- Built-in test chat panel
- Chat URL persistence for continuing the same chat or starting a new one

## Run
```bash
pip install -r requirements.txt
playwright install chromium
python run.py
```
