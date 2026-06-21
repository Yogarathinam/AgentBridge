import os
from pathlib import Path

APP_NAME = "AgentBridge"

APP_VERSION = "1.0.0"
ENABLE_CLOUD = True

API_BASE_URL = "https://agentbridge-cloud.vercel.app/api"
WEB_URL = "https://agentbridge-cloud.vercel.app"

HOST = "127.0.0.1"

PORT_CANDIDATES = [8765]

QUEUE_LIMIT = 5

APP_DATA_DIR = (
    Path(os.getenv("LOCALAPPDATA"))
    / APP_NAME
)

APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR = APP_DATA_DIR

PROFILE_DIR = DATA_DIR / "chromium_profile"
STATE_FILE = DATA_DIR / "runtime_state.json"
CHAT_HISTORY_FILE = DATA_DIR / "chat_history.json"

LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

GEMINI_URL = "https://gemini.google.com/app"
GOOGLE_LOGIN_URL = "https://accounts.google.com/signin"

HEADLESS = False

REQUEST_TIMEOUT_SEC = 180
SCRAPE_POLL_INTERVAL = 1.2
SCRAPE_STABLE_POLLS = 2