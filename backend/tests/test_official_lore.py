import tempfile
import unittest
from pathlib import Path

from backend.database.lore_repository import LORE_DIR, LoreRepository
from backend.database.official_lore_repository import OfficialLoreRepository
from backend.scripts.sync_chinese_official_lore import REGION_URL, sync


class OfficialLoreSyncTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "lore.db"
        self.lore = LoreRepository(self.db_path, LORE_DIR)
        self.snapshots = OfficialLoreRepository(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def fetcher(url):
        if url == REGION_URL:
            return {
                "name": "艾欧尼亚",
                "associated-champions": [{"name": "亚索", "slug": "yasuo"}],
                "modules": [{"title": "艾欧尼亚的生活"}],
            }
        return {
            "champion": {
                "name": "亚索",
                "title": "疾风剑豪",
                "slug": "yasuo",
                "biography": {"short": "<p>官方简介</p>", "full": "<p>官方完整传记</p>"},
            },
            "modules": [{"title": "故事"}],
        }

    def test_sync_is_idempotent_and_preserves_curated_lore(self):
        before = self.lore.get("champions", "yasuo")["data"]["profile"]
        sync(self.snapshots, self.lore, self.fetcher)
        sync(self.snapshots, self.lore, self.fetcher)
        self.assertEqual(self.snapshots.counts(), {"champions": 1, "region": 1})
        official = self.snapshots.get("zh_cn", "champions", "yasuo")
        self.assertEqual(official["payload"]["biography"]["full_text"], "官方完整传记")
        self.assertEqual(self.lore.get("champions", "yasuo")["data"]["profile"], before)

    def test_chinese_api_monkeyking_slug_maps_to_local_wukong_id(self):
        def fetcher(url):
            if url == REGION_URL:
                return {"name": "艾欧尼亚", "associated-champions": [{"name": "悟空", "slug": "monkeyking"}]}
            return {"champion": {"name": "悟空", "slug": "monkeyking", "biography": {}}}

        sync(self.snapshots, self.lore, fetcher)
        self.assertIsNotNone(self.snapshots.get("zh_cn", "champions", "wukong"))
        self.assertIsNone(self.snapshots.get("zh_cn", "champions", "monkeyking"))

    def test_related_story_body_is_saved_once_with_character_links(self):
        def fetcher(url):
            if url == REGION_URL:
                return {"name": "艾欧尼亚", "associated-champions": [{"name": "亚索", "slug": "yasuo"}]}
            if "/story/" in url:
                return {"story": {"title": "兄弟手足", "story-sections": [{"story-subsections": [{"content": "<p>中文故事正文</p>"}]}]}}
            return {"champion": {"name": "亚索", "slug": "yasuo", "biography": {}}, "modules": [{"type": "story-preview", "story-slug": "yasuo-color-story", "title": "兄弟手足"}]}

        sync(self.snapshots, self.lore, fetcher)
        story = self.snapshots.get("zh_cn", "stories", "yasuo-color-story")["payload"]
        self.assertEqual(story["body_text"], "中文故事正文")
        self.assertEqual(story["related_characters"], ["yasuo"])
        published = self.lore.get("stories", "yasuo-color-story")
        self.assertEqual(published["data"]["content"], "中文故事正文")
        self.assertEqual(published["data"]["related_characters"], ["yasuo"])
        self.assertIn("yasuo-color-story", self.lore.get("champions", "yasuo")["data"]["story_ids"])


if __name__ == "__main__":
    unittest.main()
