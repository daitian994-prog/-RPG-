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
        while next_event:
            leave_index = next((index for index, choice in enumerate(next_event["choices"]) if any(word in choice["text"] for word in ("离开", "撤离", "退出"))), len(next_event["choices"]) - 1)
            game, resolution = self.service.resolve(game["id"], next_event["id"], leave_index, next_event["round"])
            next_event = resolution.get("nextEvent")

        follow_up = next(item for item in game["journal"] if item["id"] == FOLLOW_UP_LEAD_ID)
        self.assertEqual(follow_up["relatedLocations"], ["war_ruins"])
        self.assertEqual(follow_up["status"], "active")
        self.assertTrue(follow_up["isNew"])
        original = next(item for item in game["journal"] if item["id"] == OPENING_LEAD_ID)
        self.assertEqual(original["status"], "superseded")
        self.assertIn("已追查", original["summary"])
        self.assertIn("战争遗迹", original["summary"])
        self.assertNotEqual(game["playerIntent"].get("kind"), "track_lead")
        self.assertTrue(any(clue["id"] == "clue-human-activity" for clue in game["player"]["clues"]))
        self.assertTrue(resolution["mapUpdates"])

        with self.assertRaises(ValueError):
            self.service.travel(game["id"], "windbreak", lead_id=OPENING_LEAD_ID, narrate=False)
        game, _ = self.service.travel(game["id"], "war_ruins", lead_id=FOLLOW_UP_LEAD_ID, narrate=False)
        context = game["scene"]["eventContext"]
        self.assertEqual(context["playerIntent"]["leadId"], FOLLOW_UP_LEAD_ID)
        self.assertNotIn(OPENING_LEAD_ID, {item["id"] for item in context["trackableLeads"]})
        self.assertIn(OPENING_LEAD_ID, {item["id"] for item in context["leadHistory"]})

    def test_new_lead_does_not_automatically_close_current_lead(self):
        current = {
            "id": "lead-current", "kind": "lead", "title": "林缘的铜铃", "summary": "铜铃上有新鲜泥水。",
            "trackable": True, "relatedLocations": ["windbreak"], "sourceType": "test", "status": "active",
            "threadId": "noxian_remnants", "isNew": False, "focused": False,
        }
        self.game["journal"].append(current)
        self.game["location"] = "windbreak"
        self.game["playerIntent"] = {"kind": "track_lead", "leadId": current["id"], "threadId": current["threadId"]}
        ai_result = {
            "factsAdded": ["铜铃最近被人移动过"],
            "suggestedLead": {"title": "铜铃上的布纤维", "summary": "布纤维可能来自附近旅人。", "relatedLocations": ["pallas"], "threadId": "noxian_remnants"},
            "leadDisposition": "KEEP_ACTIVE",
        }
        feedback = self.service._record_journal_feedback(
            self.game, "test-event", {"title": "林缘现场"}, {"facts": []}, ai_result,
            {"code": "success"}, [],
        )
        self.assertTrue(feedback["mapUpdates"])
        self.assertEqual(current["status"], "active")
        self.assertFalse(feedback["leadUpdates"])

    def test_old_confirmed_lead_migrates_to_history_without_remaining_intent(self):
        old = next(item for item in self.game["journal"] if item["id"] == OPENING_LEAD_ID)
        old["status"] = "confirmed"
        self.game["journal"].append({
            "id": FOLLOW_UP_LEAD_ID, "kind": "lead", "title": "旧军道近期有人活动", "summary": "新方向",
            "trackable": True, "relatedLocations": ["war_ruins"], "sourceLeadId": OPENING_LEAD_ID,
            "status": "known", "threadId": "noxian_remnants",
        })
        self.game["playerIntent"] = {"kind": "track_lead", "leadId": OPENING_LEAD_ID}
        self.assertTrue(self.service._normalize_state(self.game))
        self.assertEqual(old["status"], "superseded")
        self.assertIn("已追查", old["summary"])
        self.assertEqual(self.game["playerIntent"]["kind"], "free_exploration")
        follow_up = next(item for item in self.game["journal"] if item["id"] == FOLLOW_UP_LEAD_ID)
        self.assertEqual(follow_up["status"], "active")

    def test_location_personalities_are_visible_and_distinct(self):
        profiles = {item["id"]: item for item in self.service.locations}
        self.assertEqual(profiles["pallas"]["risk"], "低")
        self.assertEqual(profiles["war_ruins"]["risk"], "高")
        self.assertNotEqual(profiles["pallas"]["feedbackTypes"], profiles["war_ruins"]["feedbackTypes"])


if __name__ == "__main__":
    unittest.main()
