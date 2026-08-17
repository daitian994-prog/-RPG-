import unittest
from unittest.mock import patch

from backend.api.routes import _debug_allowed
from backend.services.game_service import GameService
from backend.services.public_view_service import PublicViewService


class PublicViewTest(unittest.TestCase):
    def setUp(self):
        self.games = GameService()
        self.views = PublicViewService()

    def test_player_contract_omits_internal_state(self):
        game = self.games.new_game(["peace"] * 6)
        view = self.views.game(game)
        for key in ("worldState", "directorState", "pendingEvent", "aiNarratorDebug", "stateChangeLog"):
            self.assertNotIn(key, view)
        self.assertNotIn("legacyCombatStats", view["player"])
        self.assertNotIn("attributes", view["player"])
        self.assertNotIn("core_attributes", view["player"])
        self.assertNotIn("fate_weights", view["player"])
        self.assertNotIn("modifiers", view["player"]["bodyCondition"])
        self.assertIn("knownWorldThreads", view)

    def test_event_contract_keeps_actions_but_omits_composer_debug(self):
        game = self.games.new_game(["peace"] * 6)
        event = self.games.dynamic_events.generate_pool(game, "pallas")[0]
        for index, choice in enumerate(event["choices"]):
            choice["assessment"] = self.games.ai.assess_choice(event, choice, game, index)
        view = self.views.event(event)
        for key in ("dynamic", "components", "directorProfile", "compositionKey", "actionDebug"):
            self.assertNotIn(key, view)
        self.assertTrue(all(choice["text"] and "assessment" in choice for choice in view["choices"]))

    def test_debug_contract_is_explicit_and_unfiltered(self):
        game = self.games.new_game(["peace"] * 6)
        self.assertIs(self.views.game(game, debug=True), game)

    def test_production_never_allows_debug_query(self):
        with patch.dict("os.environ", {"VERCEL": "1"}, clear=False):
            self.assertFalse(_debug_allowed(True))


if __name__ == "__main__":
    unittest.main()
