import unittest
from unittest.mock import patch

from backend.database import db


class FakeRuntimeCache:
    def __init__(self) -> None:
        self.values = {}
        self.options = None

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, options=None):
        self.values[key] = value
        self.options = options


class VercelStorageTest(unittest.TestCase):
    def test_vercel_uses_runtime_cache_for_game_state(self):
        cache = FakeRuntimeCache()
        state = {"id": "demo-player", "season": "春"}
        with patch.object(db, "IS_VERCEL", True), patch.object(db, "_runtime_cache", cache):
            db.save_game("demo-player", state)
            self.assertEqual(db.load_game("demo-player"), state)
        self.assertEqual(cache.options["ttl"], db.GAME_CACHE_TTL_SECONDS)
        self.assertIn("runeterra-games", cache.options["tags"])


if __name__ == "__main__":
    unittest.main()
