import json
import unittest

from backend.services.lore_service import LoreService


class LoreKnowledgeBaseTest(unittest.TestCase):
    def setUp(self):
        self.lore = LoreService()

    def test_all_ionian_champions_are_present(self):
        actual = {item["id"] for item in self.lore.champions}
        self.assertEqual(len(actual), 23)
        self.assertEqual(actual, set(self.lore.metadata["champion_ids"]))

    def test_every_source_reference_resolves(self):
        source_ids = set(self.lore.source_index)
        documents = [
            self.lore.region,
            *self.lore.champions,
            *self.lore.places,
            *self.lore.factions,
            *self.lore.timeline,
            *self.lore.relationships,
        ]
        missing = {source_id for document in documents for source_id in document.get("source_ids", []) if source_id not in source_ids}
        self.assertEqual(missing, set())

    def test_event_retrieval_is_relevant_and_bounded(self):
        context = self.lore.context_for_event("war_ruins", "战斗", "亚索在遗迹遇到诺克萨斯斥候")
        self.assertTrue(any(item["name"] == "亚索" for item in context["相关人物"]))
        self.assertLessEqual(len(json.dumps(context, ensure_ascii=False)), 1600)

    def test_search_finds_people_places_and_history(self):
        self.assertTrue(self.lore.search("普雷西典"))
        self.assertTrue(self.lore.search("亚索"))
        self.assertTrue(self.lore.search("均衡教派"))

    def test_champion_detail_contains_relationships_and_sources(self):
        yasuo = self.lore.champion("yasuo")
        self.assertEqual(yasuo["name"], "亚索")
        self.assertTrue(yasuo["relationship_edges"])
        self.assertTrue(yasuo["sources"])


if __name__ == "__main__":
    unittest.main()
