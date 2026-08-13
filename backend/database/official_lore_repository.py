import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from backend.database.db import DB_PATH


class OfficialLoreRepository:
    """Read-only source snapshots kept separate from game-ready lore summaries."""

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

    @staticmethod
    def public(row: sqlite3.Row, include_payload: bool = True) -> dict[str, Any]:
        item = {
            "locale": row["locale"],
            "category": row["category"],
            "id": row["id"],
            "title": row["title"],
            "source_url": row["source_url"],
            "source_updated_at": row["source_updated_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        if include_payload:
            item["payload"] = json.loads(row["payload_json"])
        return item

    def upsert(
        self,
        locale: str,
        category: str,
        record_id: str,
        title: str,
        source_url: str,
        payload: dict[str, Any],
        source_updated_at: str | None = None,
    ) -> dict[str, Any]:
        with self.connection() as conn:
            conn.execute(
                """INSERT INTO lore_official_snapshots(
                    locale, category, id, title, source_url, payload_json, source_updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(locale, category, id) DO UPDATE SET
                    title=excluded.title,
                    source_url=excluded.source_url,
                    payload_json=excluded.payload_json,
                    source_updated_at=excluded.source_updated_at,
                    updated_at=CURRENT_TIMESTAMP""",
                (
                    locale,
                    category,
                    record_id,
                    title,
                    source_url,
                    json.dumps(payload, ensure_ascii=False),
                    source_updated_at,
                ),
            )
        return self.get(locale, category, record_id)  # type: ignore[return-value]

    def get(self, locale: str, category: str, record_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(
                """SELECT * FROM lore_official_snapshots
                WHERE locale=? AND category=? AND id=?""",
                (locale, category, record_id),
            ).fetchone()
        return self.public(row) if row else None

    def list(
        self, locale: str = "zh_cn", category: str = "", query: str = "", include_payload: bool = False
    ) -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%"
        with self.connection() as conn:
            rows = conn.execute(
                """SELECT * FROM lore_official_snapshots
                WHERE locale=? AND (?='' OR category=?)
                  AND (?='' OR title LIKE ? OR id LIKE ?)
                ORDER BY category, title""",
                (locale, category, category, query.strip(), pattern, pattern),
            ).fetchall()
        return [self.public(row, include_payload) for row in rows]

    def counts(self, locale: str = "zh_cn") -> dict[str, int]:
        with self.connection() as conn:
            rows = conn.execute(
                """SELECT category, COUNT(*) AS amount FROM lore_official_snapshots
                WHERE locale=? GROUP BY category""",
                (locale,),
            ).fetchall()
        return {row["category"]: row["amount"] for row in rows}

    def delete(self, locale: str, category: str, record_id: str) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM lore_official_snapshots WHERE locale=? AND category=? AND id=?",
                (locale, category, record_id),
            )
        return cursor.rowcount > 0
