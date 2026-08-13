import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.database.api_nodes import ApiNodeRepository


def node(name: str, key: str) -> dict[str, str]:
    return {
        "name": name,
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
        "api_key": key,
    }


class ApiNodeRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = ApiNodeRepository(Path(self.temp_dir.name) / "nodes.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_keys_are_masked_and_never_returned(self):
        secret = "sk-private-12345678"
        created = self.repository.create(node("主节点", secret))
        self.assertNotIn("api_key", created)
        self.assertTrue(created["has_key"])
        self.assertTrue(created["key_mask"].endswith("5678"))
        self.assertNotIn(secret, str(self.repository.list()))

    def test_enabling_a_node_atomically_disables_the_previous_one(self):
        first = self.repository.create(node("线路 A", "key-a"))
        second = self.repository.create(node("线路 B", "key-b"))
        self.repository.set_enabled(first["id"], True)
        self.repository.set_enabled(second["id"], True)
        enabled = [item for item in self.repository.list() if item["enabled"]]
        self.assertEqual([item["id"] for item in enabled], [second["id"]])

    def test_database_rejects_two_enabled_nodes(self):
        first = self.repository.create(node("线路 A", "key-a"))
        second = self.repository.create(node("线路 B", "key-b"))
        self.repository.set_enabled(first["id"], True)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.repository.connection() as conn:
                conn.execute("UPDATE api_nodes SET enabled=1 WHERE id=?", (second["id"],))

    def test_editing_with_blank_key_keeps_existing_secret(self):
        created = self.repository.create(node("旧名称", "key-stays-private"))
        self.repository.update(created["id"], {**node("新名称", ""), "model": "deepseek-v4-pro"})
        stored = self.repository.get(created["id"], include_secret=True)
        self.assertEqual(stored["api_key"], "key-stays-private")
        self.assertEqual(stored["name"], "新名称")


if __name__ == "__main__":
    unittest.main()
