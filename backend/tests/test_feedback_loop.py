import os
import unittest

from backend.services.game_service import FOLLOW_UP_LEAD_ID, OPENING_LEAD_ID, GameService


class DemoFeedbackLoopTest(unittest.TestCase):
    def setUp(self):
        os.environ["RUNETERRA_DISABLE_REMOTE_AI"] = "1"
        self.service = GameService()
        self.game = self.service.new_game(["peace"] * 6)

    def test_opening_creates_a_reason_before_first_map(self):
        self.assertFalse(self.game["openingComplete"])
        self.assertLessEqual(len(self.game["opening"]["signals"]), 3)
        lead = next(item for item in self.game["journal"] if item["id"] == OPENING_LEAD_ID)
        self.assertTrue(lead["trackable"])
        self.assertEqual(lead["relatedLocations"], ["windbreak"])
        completed = self.service.complete_opening(self.game["id"])
        self.assertTrue(completed["openingComplete"])

    def test_lead_scene_creates_the_next_map_direction(self):
        self.service.complete_opening(self.game["id"])
        game, event = self.service.travel(self.game["id"], "windbreak", lead_id=OPENING_LEAD_ID, narrate=False)
        context = game["scene"]["eventContext"]
        self.assertEqual(context["playerIntent"]["leadId"], OPENING_LEAD_ID)
        self.assertIn("脚印", context["hardFacts"][-1])
        self.assertGreaterEqual(len({choice["text"] for choice in event["choices"]}), 2)

        game, resolution = self.service.resolve(game["id"], event["id"], 0, event["round"])
        next_event = resolution.get("nextEvent")
        if next_event:
            leave_index = next((index for index, choice in enumerate(next_event["choices"]) if any(word in choice["text"] for word in ("离开", "撤离", "退出"))), len(next_event["choices"]) - 1)
            game, resolution = self.service.resolve(game["id"], next_event["id"], leave_index, next_event["round"])

        follow_up = next(item for item in game["journal"] if item["id"] == FOLLOW_UP_LEAD_ID)
        self.assertEqual(follow_up["relatedLocations"], ["war_ruins"])
        self.assertTrue(follow_up["isNew"])
        self.assertTrue(any(clue["id"] == "clue-human-activity" for clue in game["player"]["clues"]))
        self.assertTrue(resolution["mapUpdates"])

    def test_location_personalities_are_visible_and_distinct(self):
        profiles = {item["id"]: item for item in self.service.locations}
        self.assertEqual(profiles["pallas"]["risk"], "低")
        self.assertEqual(profiles["war_ruins"]["risk"], "高")
        self.assertNotEqual(profiles["pallas"]["feedbackTypes"], profiles["war_ruins"]["feedbackTypes"])


if __name__ == "__main__":
    unittest.main()
