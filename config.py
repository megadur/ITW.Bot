import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# Ensure runtime directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Telegram Credentials
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "").strip()
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "").strip()
SESSION_FILE = str(DATA_DIR / "scambaiter.session")

# Gemini / LLM Settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest").strip()

# Timing & Behavior
MIN_DELAY_SECONDS = int(os.getenv("MIN_DELAY_SECONDS", "25"))
MAX_DELAY_SECONDS = int(os.getenv("MAX_DELAY_SECONDS", "75"))
TYPING_DURATION_SECONDS = int(os.getenv("TYPING_DURATION_SECONDS", "6"))
MAX_REPLIES_PER_CHAT = int(os.getenv("MAX_REPLIES_PER_CHAT", "50"))
NOTIFY_SAVED_MESSAGES = os.getenv("NOTIFY_SAVED_MESSAGES", "true").lower() in ("true", "1", "yes")

# Database & Log paths
DB_PATH = DATA_DIR / "conversations.db"
