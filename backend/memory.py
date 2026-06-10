import sqlite3
from datetime import datetime

DB_PATH = "squanch.db"


def now():
    return datetime.now().isoformat(timespec="seconds")


def db():
    return sqlite3.connect(DB_PATH)


def save_memory(category: str, content: str, source: str = "manual"):
    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO memories (category, content, source, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (category or "general", content, source or "manual", now()),
    )
    memory_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return memory_id


def get_memories(limit: int = 50):
    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, category, content, source, created_at
        FROM memories
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "category": row[1],
            "content": row[2],
            "source": row[3],
            "created_at": row[4],
        }
        for row in rows
    ]


def search_memories(query: str, limit: int = 20):
    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, category, content, source, created_at
        FROM memories
        WHERE content LIKE ? OR category LIKE ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (f"%{query}%", f"%{query}%", limit),
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "category": row[1],
            "content": row[2],
            "source": row[3],
            "created_at": row[4],
        }
        for row in rows
    ]
