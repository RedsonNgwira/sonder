"""
db/database.py — SQLite persistence for worlds using JSON serialization.
Worlds are stored as JSON blobs — simple, portable, easy to back up.
"""
import sqlite3
import json
from pathlib import Path
from db.models import World

DB_PATH = Path(__file__).parent.parent / "sonder.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS worlds (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)


def save_world(world: World):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO worlds (id, name, data, created_at) VALUES (?, ?, ?, ?)",
            (world.id, world.name, world.model_dump_json(), world.created_at)
        )


def load_world(world_id: str) -> World | None:
    with get_conn() as conn:
        row = conn.execute("SELECT data FROM worlds WHERE id = ?", (world_id,)).fetchone()
    return World.model_validate_json(row["data"]) if row else None


def list_worlds() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT id, name, created_at FROM worlds ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def delete_world(world_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM worlds WHERE id = ?", (world_id,))
