import os
import sqlite3
from datetime import datetime

# Resolve DB path relative to the project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "cache.db")


def get_db_connection():
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Creates tables if they don't exist, ensuring directory exists."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db_connection() as conn:
        # Create videos table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                channel_id TEXT NOT NULL,
                channel_name TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                published_at TEXT NOT NULL,
                tier TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            )
        """)

        conn.commit()


def is_video_cached(video_id: str) -> bool:
    """Checks if a video is already in the database cache."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM videos WHERE video_id = ?", (video_id,)
        ).fetchone()
        return row is not None


def save_video(video: dict):
    """Inserts a video row, ignoring conflicts."""
    fetched_at = datetime.utcnow().isoformat()
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO videos (
                video_id, channel_id, channel_name, title, description, published_at, tier, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                video["video_id"],
                video["channel_id"],
                video["channel_name"],
                video["title"],
                video.get("description"),
                video["published_at"],
                video["tier"],
                fetched_at,
            ),
        )
        conn.commit()


def get_corpus_since(days: int) -> list[dict]:
    """Returns all videos published within the last N days."""
    query = """
        SELECT
            video_id,
            channel_name,
            title,
            description,
            published_at,
            tier
        FROM videos
        WHERE datetime(published_at) >= datetime('now', ?)
        ORDER BY published_at DESC
    """
    with get_db_connection() as conn:
        cursor = conn.execute(query, (f"-{days} days",))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
