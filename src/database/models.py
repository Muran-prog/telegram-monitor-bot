import sqlite3
from src.config import (
    DB_FILE, DEFAULT_CHECK_FREQUENCY, DEFAULT_INITIAL_FETCH,
    DEFAULT_AUTOCLEAN_LIMIT, DEFAULT_DOWNLOAD_MEDIA, DEFAULT_DETECT_DELETIONS
)

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                user_id INTEGER, phone TEXT, api_id INTEGER, api_hash TEXT, PRIMARY KEY(user_id, phone)
            )
        """)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS monitored_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_phone TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                type TEXT NOT NULL,
                check_frequency_seconds INTEGER DEFAULT {DEFAULT_CHECK_FREQUENCY},
                initial_fetch_limit INTEGER DEFAULT {DEFAULT_INITIAL_FETCH},
                db_autoclean_limit INTEGER DEFAULT {DEFAULT_AUTOCLEAN_LIMIT},
                download_media INTEGER DEFAULT {int(DEFAULT_DOWNLOAD_MEDIA)},
                detect_deletions INTEGER DEFAULT {int(DEFAULT_DETECT_DELETIONS)},
                UNIQUE(user_id, session_phone, chat_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, telethon_message_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
                session_phone TEXT NOT NULL, text TEXT, sender_id INTEGER, date TIMESTAMP, file_path TEXT,
                file_size INTEGER,
                status TEXT DEFAULT 'active' NOT NULL, UNIQUE(telethon_message_id, chat_id, session_phone)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_for_deletion_check ON messages (session_phone, chat_id, status, date)
        """)
        # Backward compatibility check for file_size column
        cursor.execute("PRAGMA table_info(messages)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'file_size' not in columns:
            cursor.execute("ALTER TABLE messages ADD COLUMN file_size INTEGER")

        conn.commit()