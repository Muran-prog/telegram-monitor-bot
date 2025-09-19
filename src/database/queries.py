import sqlite3
from typing import List, Dict, Any, Tuple
from src.config import DB_FILE

# --- Session Credentials ---
def db_add_session_credentials(user_id: int, phone: str, api_id: int, api_hash: str):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?, ?, ?)", (user_id, phone, api_id, api_hash))
        conn.commit()

def db_get_session_credentials(user_id: int, phone: str) -> Tuple[int, str] | None:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT api_id, api_hash FROM sessions WHERE user_id=? AND phone=?", (user_id, phone))
        return cursor.fetchone()

def db_remove_session_credentials(user_id: int, phone: str):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM sessions WHERE user_id=? AND phone=?", (user_id, phone))
        conn.commit()

# --- Monitored Chats ---
def db_add_chat(user_id: int, phone: str, chat_id: int, title: str, chat_type: str):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT OR IGNORE INTO monitored_chats (user_id, session_phone, chat_id, title, type) VALUES (?, ?, ?, ?, ?)", (user_id, phone, chat_id, title, chat_type))
        conn.commit()

def db_get_chats(user_id: int, phone: str) -> List[Dict[str, Any]]:
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id, title, type FROM monitored_chats WHERE user_id=? AND session_phone=?", (user_id, phone))
        return [{'id': r['chat_id'], 'title': r['title'], 'type': r['type']} for r in cursor.fetchall()]

def db_remove_chat(user_id: int, phone: str, chat_id: int):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM monitored_chats WHERE user_id=? AND session_phone=? AND chat_id=?", (user_id, phone, chat_id))
        conn.commit()

def db_remove_all_chats_for_session(user_id: int, phone: str):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM monitored_chats WHERE user_id=? AND session_phone=?", (user_id, phone))
        conn.commit()

def db_is_chat_monitored(user_id: int, phone: str, chat_id: int) -> bool:
    with sqlite3.connect(DB_FILE) as conn:
        return conn.execute("SELECT 1 FROM monitored_chats WHERE user_id=? AND session_phone=? AND chat_id=?", (user_id, phone, chat_id)).fetchone() is not None

# --- Chat Settings ---
def db_get_chat_settings(user_id: int, session_phone: str, chat_id: int) -> Dict[str, Any] | None:
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        row = cursor.execute("SELECT * FROM monitored_chats WHERE user_id=? AND session_phone=? AND chat_id=?", (user_id, session_phone, chat_id)).fetchone()
        return dict(row) if row else None

def db_update_chat_setting(user_id: int, session_phone: str, chat_id: int, setting_key: str, setting_value: Any):
    with sqlite3.connect(DB_FILE) as conn:
        allowed_keys = ['check_frequency_seconds', 'initial_fetch_limit', 'db_autoclean_limit', 'download_media', 'detect_deletions']
        if setting_key not in allowed_keys:
            raise ValueError("Invalid setting key")
        conn.execute(f"UPDATE monitored_chats SET {setting_key}=? WHERE user_id=? AND session_phone=? AND chat_id=?", (setting_value, user_id, session_phone, chat_id))
        conn.commit()

# --- Messages ---
def db_add_message(telethon_message_id: int, chat_id: int, session_phone: str, text: str, sender_id: int, date, file_path: str | None, file_size: int | None):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT OR IGNORE INTO messages (telethon_message_id, chat_id, session_phone, text, sender_id, date, file_path, file_size) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (telethon_message_id, chat_id, session_phone, text, sender_id, date, file_path, file_size))
        conn.commit()

def db_get_last_message_id(session_phone: str, chat_id: int) -> int:
    with sqlite3.connect(DB_FILE) as conn:
        res = conn.execute("SELECT MAX(telethon_message_id) FROM messages WHERE session_phone=? AND chat_id=?", (session_phone, chat_id)).fetchone()
        return res[0] if res and res[0] is not None else 0

def db_get_recent_active_messages(session_phone: str, chat_id: int) -> List[Dict]:
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute("SELECT id, telethon_message_id, text, file_path, date FROM messages WHERE session_phone=? AND chat_id=? AND status='active' ORDER BY date DESC LIMIT 200", (session_phone, chat_id)).fetchall()]

def db_mark_message_as_deleted(db_id: int):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("UPDATE messages SET status='deleted' WHERE id=?", (db_id,))
        conn.commit()

def db_autoclean_messages(session_phone: str, chat_id: int, limit: int):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM messages WHERE id IN (SELECT id FROM messages WHERE session_phone=? AND chat_id=? ORDER BY date DESC LIMIT -1 OFFSET ?)", (session_phone, chat_id, limit))
        conn.commit()

# --- Statistics ---
def db_calculate_chat_statistics(session_phone: str, chat_id: int) -> Dict[str, Any]:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        base_query = "FROM messages WHERE session_phone=? AND chat_id=?"
        
        cursor.execute(f"SELECT COUNT(*) {base_query}", (session_phone, chat_id))
        total_messages = cursor.fetchone()[0]

        cursor.execute(f"SELECT COUNT(*) {base_query} AND status='deleted'", (session_phone, chat_id))
        deleted_messages = cursor.fetchone()[0]

        cursor.execute(f"SELECT COUNT(*), SUM(file_size) {base_query} AND file_path IS NOT NULL", (session_phone, chat_id))
        media_files, media_size_bytes = cursor.fetchone()

        cursor.execute(f"SELECT MIN(date), MAX(date) {base_query}", (session_phone, chat_id))
        first_message_ts, last_message_ts = cursor.fetchone()

        return {
            'total_messages': total_messages or 0,
            'deleted_messages': deleted_messages or 0,
            'media_files': media_files or 0,
            'media_size_bytes': media_size_bytes or 0,
            'first_message_ts': first_message_ts,
            'last_message_ts': last_message_ts
        }