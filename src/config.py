import logging
import os
from dataclasses import dataclass
from pathlib import Path
import sys

from dotenv import load_dotenv

# --- Configuration Dataclasses ---
@dataclass
class BotConfig:
    token: str

@dataclass
class Config:
    bot: BotConfig

def load_config(path: str | None = None) -> Config:
    """Loads configuration from environment variables."""
    load_dotenv(path)
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logging.critical("BOT_TOKEN is not set in the environment or .env file. Exiting.")
        sys.exit(1)
    return Config(bot=BotConfig(token=bot_token))

# --- Path Constants ---
BASE_DIR = Path(__file__).resolve().parent.parent
SESSIONS_DIR = BASE_DIR / "sessions"
DOWNLOADS_DIR = BASE_DIR / "downloads"
DB_FILE = BASE_DIR / "bot_database.db"

# Create necessary directories
SESSIONS_DIR.mkdir(exist_ok=True)
DOWNLOADS_DIR.mkdir(exist_ok=True)


# --- Default Settings ---
DEFAULT_CHECK_FREQUENCY = 10
DEFAULT_INITIAL_FETCH = 10
DEFAULT_AUTOCLEAN_LIMIT = 0  # 0 means disabled
DEFAULT_DOWNLOAD_MEDIA = True
DEFAULT_DETECT_DELETIONS = True
SUPERVISOR_SLEEP_INTERVAL = 30 # How often supervisor checks for new/removed chats

# --- FSM Constants ---
CODE_LENGTH = 5
MASK_CHAR = "•"
PLACEHOLDER_CHAR = "_"