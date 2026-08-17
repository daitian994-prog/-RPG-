from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from backend.database.db import DB_PATH


LORE_DIR = Path(__file__).resolve().parents[2] / "game-data" / "lore"
LORE_CATEGORIES = ("metadata", "region", "champions", "stories", "places", "factions", "timeline", "relationships", "sources")


class LoreRepository:
    def __init__(self, db_path: Path = DB_PATH, lore_dir: Path = LORE_DIR) -> None:
        self.db_path = db_path
        self.lore_dir = lore_dir
        self.initialize()
        self.seed_if_empty()

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

    @staticmethod
    def _stable_id(category: str, item: dict[str, Any]) -> str:
        if item.get("id"):
            return str(item["id"])
        if category == "timeline":
            return f"event_{item['order']}"
        raw = f"{category}:{item.get('source')}:{item.get('target')}:{item.get('type')}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _title(category: str, item: dict[str, Any]) -> str:
        return str(
            item.get("name")
            or item.get("title")
            or (f"{item.get('source')} → {item.get('target')}" if category == "relationships" else item.get("id"))
            or "未命名资料"
        )

    def seed_if_empty(self) -> None:
        with self.connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM lore_records").fetchone()[0]
        if count:
            return

        records: list[tuple[str, str, str, str]] = []
        for category in LORE_CATEGORIES:
            path = self.lore_dir / f"{category}.json"
            source = json.loads(path.read_text(encoding="utf-8"))
            items = source if isinstance(source, list) else [source]
            for item in items:
                record_id = self._stable_id(category, item)
                records.append((category, record_id, self._title(category, item), json.dumps(item, ensure_ascii=False)))
        with self.connection() as conn:
            conn.executemany(
                "INSERT INTO lore_records(category, id, title, data_json) VALUES(?, ?, ?, ?)",
                records,
            )
            conn.execute(
                "INSERT OR REPLACE INTO lore_meta(key, value) VALUES('seed_version', ?)",
                ("1.0.0",),
            )

    @staticmethod
    def public(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "category": row["category"],
            "id": row["id"],
            "title": row["title"],
            "data": json.loads(row["data_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def counts(self) -> dict[str, int]:
        with self.connection() as conn:
            rows = conn.execute("SELECT category, COUNT(*) AS amount FROM lore_records GROUP BY category").fetchall()
        return {category: next((row["amount"] for row in rows if row["category"] == category), 0) for category in LORE_CATEGORIES}

    def list(self, category: str, query: str = "", limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
        if category not in LORE_CATEGORIES:
            raise ValueError("未知的知识库分类。")
        pattern = f"%{query.strip()}%"
        with self.connection() as conn:
            rows = conn.execute(
                """SELECT * FROM lore_records WHERE category=? AND (?='' OR title LIKE ? OR data_json LIKE ?)
                ORDER BY CASE WHEN json_extract(data_json, '$.order') IS NULL THEN 1 ELSE 0 END,
                CAST(json_extract(data_json, '$.order') AS INTEGER), title LIMIT ? OFFSET ?""",
                (category, query.strip(), pattern, pattern, limit, offset),
            ).fetchall()
        return [self.public(row) for row in rows]

    def list_champions_with_stories(self, query: str = "", limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
        """Return hero records with their stories nested, while keeping story bodies normalized."""
        champions = self.list("champions", "", 1000, 0)
        stories = self.list("stories", "", 1000, 0)
        query_text = query.strip().casefold()
        enriched: list[dict[str, Any]] = []
        for champion in champions:
            configured_ids = set(champion["data"].get("story_ids") or [])
            related = [
                story for story in stories
                if story["id"] in configured_ids or champion["id"] in (story["data"].get("related_characters") or [])
            ]
            related.sort(key=lambda story: (story["data"].get("release_date") or "", story["title"]), reverse=True)
            summaries = [
                {
                    "id": story["id"],
                    "title": story["title"],
                    "author": story["data"].get("author", ""),
                    "preview": story["data"].get("preview", ""),
                    "minutes_to_read": story["data"].get("minutes_to_read"),
                    "source_url": story["data"].get("source_url", ""),
                    "updated_at": story["updated_at"],
                }
                for story in related
            ]
            record = {**champion, "stories": summaries, "story_count": len(summaries)}
            searchable = json.dumps(record, ensure_ascii=False).casefold()
            if not query_text or query_text in searchable:
                enriched.append(record)
        return enriched[offset:offset + limit]

    def get(self, category: str, record_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM lore_records WHERE category=? AND id=?", (category, record_id)).fetchone()
        return self.public(row) if row else None

    def create(self, category: str, record_id: str, title: str, data: dict[str, Any]) -> dict[str, Any]:
        if category not in LORE_CATEGORIES:
            raise ValueError("未知的知识库分类。")
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO lore_records(category, id, title, data_json) VALUES(?, ?, ?, ?)",
                (category, record_id.strip(), title.strip(), json.dumps(data, ensure_ascii=False)),
            )
        return self.get(category, record_id)  # type: ignore[return-value]

    def update(self, category: str, record_id: str, title: str, data: dict[str, Any]) -> dict[str, Any] | None:
        with self.connection() as conn:
            cursor = conn.execute(
                """UPDATE lore_records SET title=?, data_json=?, updated_at=CURRENT_TIMESTAMP
                WHERE category=? AND id=?""",
                (title.strip(), json.dumps(data, ensure_ascii=False), category, record_id),
            )
        return self.get(category, record_id) if cursor.rowcount else None

    def delete(self, category: str, record_id: str) -> bool:
        with self.connection() as conn:
            cursor = conn.execute("DELETE FROM lore_records WHERE category=? AND id=?", (category, record_id))
        return cursor.rowcount > 0
