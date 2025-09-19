import math

from aiogram.types import CallbackQuery

from src.config import SESSIONS_DIR, CODE_LENGTH, MASK_CHAR, PLACEHOLDER_CHAR

def get_user_sessions(user_id: int) -> list[str]:
    """Retrieves a sorted list of session phone numbers for a given user."""
    return sorted([f.stem.split('_', 1)[1] for f in SESSIONS_DIR.glob(f"{user_id}_*.session")])

def format_masked_code(code: str) -> str:
    """Formats the interactive code entry for the user."""
    masked = (MASK_CHAR * len(code)).ljust(CODE_LENGTH, PLACEHOLDER_CHAR)
    return f"<code>{' '.join(list(masked))}</code>"

async def get_details_for_callback(callback: CallbackQuery) -> tuple[str, int, int]:
    """Parses callback data for chat-related actions."""
    parts = callback.data.split(':')
    phone, chat_id, page = parts[-3], int(parts[-2]), int(parts[-1])
    return phone, chat_id, page

def format_bytes(size_bytes: int | None) -> str:
    """Converts bytes into a human-readable format."""
    if size_bytes is None or size_bytes == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"