import tempfile
import unittest
from pathlib import Path

from backend.database.lore_repository import LORE_DIR, LoreRepository
from backend.services.lore_service import LoreService
from backend.scripts.enrich_lore_media import update_media
from backend.scripts.enrich_timeline_details import enrich_timeline


class LoreRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "lore.db"
        self.repository = LoreRepository(self.db_path, LORE_DIR)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_seed_imports_complete_knowledge_base(self):
        counts = self.repository.counts()
        self.assertEqual(counts["champions"], 23)
        self.assertEqual(counts["places"], 14)
        self.assertEqual(counts["factions"], 10)
        self.assertEqual(counts["timeline"], 20)
        self.assertEqual(counts["relationships"], 26)
        self.assertEqual(counts["sources"], 28)

    def test_database_edit_is_visible_to_lore_service_immediately(self):
        yasuo = self.repository.get("champions", "yasuo")
        edited = {**yasuo["data"], "profile": "后台即时更新测试"}
        self.repository.update("champions", "yasuo", yasuo["title"], edited)
        lore = LoreService(self.repository)
        self.assertEqual(lore.champion("yasuo")["profile"], "后台即时更新测试")

    def test_champion_listing_integrates_linked_story_summaries(self):
        self.repository.create(
            "stories",
            "wind-story",
            "风的故事",
            {"preview": "亚索沿风而行。", "content": "完整正文不应进入人物卡片列表。", "related_characters": ["yasuo"]},
        )
        yasuo = next(record for record in self.repository.list_champions_with_stories() if record["id"] == "yasuo")
        self.assertEqual(yasuo["story_count"], 1)
        self.assertEqual(yasuo["stories"][0]["title"], "风的故事")
        self.assertNotIn("content", yasuo["stories"][0])
        self.assertEqual(self.repository.list_champions_with_stories("风的故事")[0]["id"], "yasuo")

    def test_create_delete_and_restart_preserve_user_content(self):
        self.repository.create("places", "test_place", "测试地点", {"id": "test_place", "summary": "自定义资料"})
        reopened = LoreRepository(self.db_path, LORE_DIR)
        self.assertEqual(reopened.get("places", "test_place")["title"], "测试地点")
        self.assertTrue(reopened.delete("places", "test_place"))
        self.assertIsNone(reopened.get("places", "test_place"))

    def test_media_enrichment_adds_official_images_and_map_positions(self):
        update_media(self.repository)
        yasuo = self.repository.get("champions", "yasuo")["data"]
        placidium = self.repository.get("places", "placidium")["data"]
        self.assertEqual(yasuo["image_url"], "/admin/assets/official/champions/yasuo.jpg")
        self.assertEqual(yasuo["image_credit"], "Riot Games · Data Dragon 官方原画")
        self.assertIn("map_position", placidium)
        self.assertEqual(placidium["map_position"]["space"], "riot_texture_2048")
        self.assertEqual(placidium["map_position"]["mode"], "point")
        self.assertTrue(placidium["map_position"]["official"])
        self.assertEqual((placidium["map_position"]["x"], placidium["map_position"]["y"]), (1504, 784))
        navori = self.repository.get("places", "navori")["data"]
        self.assertEqual(navori["map_position"]["mode"], "estimated_area")
        self.assertFalse(navori["map_position"]["official"])
        self.assertEqual(navori["map_position"]["confidence"], "high")
        self.assertGreater(navori["map_position"]["radius"], 0)
        omikayalan = self.repository.get("places", "omikayalan")["data"]
        self.assertEqual(omikayalan["map_position"]["confidence"], "low")
        self.assertIn("非 Riot 官方坐标", omikayalan["map_position"]["precision"])
        self.assertIn("lasting_altar", placidium["related_factions"])
        stand = self.repository.get("timeline", "event_70")["data"]
        self.assertIn("placidium", stand["related_regions"])
        self.assertIn("noxian_occupation", stand["related_factions"])
        self.assertIn("irelia", stand["related_characters"])

    def test_timeline_enrichment_adds_long_form_sections_without_losing_links(self):
        before = self.repository.get("timeline", "event_100")["data"]
        self.repository.update("timeline", "event_100", "素马长老之死与亚索流亡", {**before, "editor_note": "保留我的批注"})
        enrich_timeline(self.repository)
        after = self.repository.get("timeline", "event_100")["data"]
        for field in ("background", "process", "outcome", "historical_impact", "participants", "uncertainty"):
            self.assertTrue(after[field])
        self.assertGreater(len(after["process"]), 100)
        self.assertEqual(after["source_ids"], before["source_ids"])
        self.assertEqual(after["editor_note"], "保留我的批注")


if __name__ == "__main__":
    unittest.main()
