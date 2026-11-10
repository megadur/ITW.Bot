import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import config

def init_db():
    """Initialisiert die SQLite-Datenbank für Chats und Konversationen."""
    with sqlite3.connect(config.DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                created_at TIMESTAMP,
                last_seen TIMESTAMP,
                reply_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                sender TEXT, -- 'scammer' or 'bot'
                content TEXT,
                timestamp TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES chats (user_id)
            )
        """)
        conn.commit()

def get_or_create_chat(user_id: int, first_name: str = "", last_name: str = "", username: str = "", phone: str = "") -> dict:
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chats WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        now = datetime.now().isoformat()
        if not row:
            cursor.execute(
                "INSERT INTO chats (user_id, username, first_name, last_name, phone, created_at, last_seen, reply_count, status) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'active')",
                (user_id, username or "", first_name or "", last_name or "", phone or "", now, now)
            )
            conn.commit()
            cursor.execute("SELECT * FROM chats WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
        else:
            cursor.execute("UPDATE chats SET last_seen = ? WHERE user_id = ?", (now, user_id))
            conn.commit()
        return dict(row)

def save_message(user_id: int, sender: str, content: str):
    now = datetime.now()
    with sqlite3.connect(config.DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (user_id, sender, content, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, sender, content, now.isoformat())
        )
        if sender == "bot":
            cursor.execute("UPDATE chats SET reply_count = reply_count + 1 WHERE user_id = ?", (user_id,))
        conn.commit()

    # Auch in eine gut lesbare Markdown-Datei schreiben
    append_to_markdown_log(user_id, sender, content, now)

def get_chat_history(user_id: int, limit: int = 12) -> List[Dict[str, str]]:
    """Gibt die letzten Nachrichten für den LLM-Kontext zurück."""
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT sender, content FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        )
        rows = cursor.fetchall()
        # Chronologisch ordnen (älteste zuerst)
        return [{"sender": r["sender"], "content": r["content"]} for r in reversed(rows)]

def append_to_markdown_log(user_id: int, sender: str, content: str, timestamp: datetime):
    """Schreibt den Dialog in eine lesefreundliche Markdown-Datei unter logs/."""
    log_file = config.LOGS_DIR / f"chat_{user_id}.md"
    time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")

    # Header anlegen, falls Datei neu ist
    if not log_file.exists():
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"# 🎣 Scambait Log - Telegram User ID: `{user_id}`\n\n")
            f.write(f"*Gestartet am: {time_str}*\n\n---\n\n")

    sender_badge = "👴 **Opa Günther (Bot)**" if sender == "bot" else "👤 **Scammer**"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"### {sender_badge} `[{time_str}]`\n{content}\n\n")
