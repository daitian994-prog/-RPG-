import json
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "game.db"


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS games (
                id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS api_nodes (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL DEFAULT 'deepseek',
                base_url TEXT NOT NULL,
                model TEXT NOT NULL,
                api_key TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0, 1)),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        conn.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS one_enabled_api_node
            ON api_nodes(enabled) WHERE enabled = 1"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS lore_records (
                category TEXT NOT NULL,
                id TEXT NOT NULL,
                title TEXT NOT NULL,
                data_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(category, id)
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS lore_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS lore_official_snapshots (
                locale TEXT NOT NULL,
                category TEXT NOT NULL,
                id TEXT NOT NULL,
                title TEXT NOT NULL,
                source_url TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                source_updated_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(locale, category, id)
            )"""
        )


def save_game(game_id: str, state: dict[str, Any]) -> None:
    payload = json.dumps(state, ensure_ascii=False)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """INSERT INTO games(id, state_json) VALUES(?, ?)
            ON CONFLICT(id) DO UPDATE SET
              state_json=excluded.state_json,
              updated_at=CURRENT_TIMESTAMP""",
            (game_id, payload),
        )


def load_game(game_id: str) -> dict[str, Any] | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT state_json FROM games WHERE id = ?", (game_id,)).fetchone()
    return json.loads(row[0]) if row else None
