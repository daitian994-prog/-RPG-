import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from backend.database.db import DB_PATH


def _mask_key(value: str) -> str:
    if not value:
        return ""
    suffix = value[-4:] if len(value) >= 4 else "****"
    return f"••••••••{suffix}"


class ApiNodeRepository:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connection() as conn:
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
                "CREATE UNIQUE INDEX IF NOT EXISTS one_enabled_api_node ON api_nodes(enabled) WHERE enabled = 1"
            )

    @staticmethod
    def public(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        key = item.pop("api_key", "")
        item["enabled"] = bool(item["enabled"])
        item["has_key"] = bool(key)
        item["key_mask"] = _mask_key(key)
        return item

    def list(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM api_nodes ORDER BY enabled DESC, updated_at DESC, name"
            ).fetchall()
        return [self.public(row) for row in rows]

    def get(self, node_id: str, *, include_secret: bool = False) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM api_nodes WHERE id = ?", (node_id,)).fetchone()
        if not row:
            return None
        return dict(row) if include_secret else self.public(row)

    def active(self, *, include_secret: bool = False) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM api_nodes WHERE enabled = 1 LIMIT 1").fetchone()
        if not row:
            return None
        return dict(row) if include_secret else self.public(row)

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        node_id = uuid.uuid4().hex
        with self.connection() as conn:
            conn.execute(
                """INSERT INTO api_nodes(id, name, provider, base_url, model, api_key)
                VALUES(?, ?, ?, ?, ?, ?)""",
                (
                    node_id,
                    data["name"].strip(),
                    data.get("provider", "deepseek"),
                    data["base_url"].strip().rstrip("/"),
                    data["model"].strip(),
                    data["api_key"].strip(),
                ),
            )
        return self.get(node_id)  # type: ignore[return-value]

    def update(self, node_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        current = self.get(node_id, include_secret=True)
        if not current:
            return None
        api_key = data.get("api_key", "").strip() or current["api_key"]
        with self.connection() as conn:
            conn.execute(
                """UPDATE api_nodes SET name=?, provider=?, base_url=?, model=?, api_key=?,
                updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (
                    data["name"].strip(),
                    data.get("provider", current["provider"]),
                    data["base_url"].strip().rstrip("/"),
                    data["model"].strip(),
                    api_key,
                    node_id,
                ),
            )
        return self.get(node_id)

    def set_enabled(self, node_id: str, enabled: bool) -> dict[str, Any] | None:
        if not self.get(node_id):
            return None
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if enabled:
                conn.execute("UPDATE api_nodes SET enabled = 0 WHERE enabled = 1")
            conn.execute(
                "UPDATE api_nodes SET enabled=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (int(enabled), node_id),
            )
        return self.get(node_id)

    def delete(self, node_id: str) -> bool:
        with self.connection() as conn:
            cursor = conn.execute("DELETE FROM api_nodes WHERE id = ?", (node_id,))
        return cursor.rowcount > 0
