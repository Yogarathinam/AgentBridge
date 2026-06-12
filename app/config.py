from pathlib import Path

APP_NAME = "AgentBridge"
HOST = "127.0.0.1"
PORT_CANDIDATES = [8765, 8766, 8767, 8768, 8769]
QUEUE_LIMIT = 5
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
PROFILE_DIR = DATA_DIR / "chromium_profile"
STATE_FILE = DATA_DIR / "runtime_state.json"
CHAT_HISTORY_FILE = DATA_DIR / "chat_history.json"
GEMINI_URL = "https://gemini.google.com/app"
GOOGLE_LOGIN_URL = "https://accounts.google.com/signin"
HEADLESS = False
REQUEST_TIMEOUT_SEC = 180
SCRAPE_POLL_INTERVAL = 1.2
SCRAPE_STABLE_POLLS = 2
