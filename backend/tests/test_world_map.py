import unittest

from backend.api.routes import world


class WorldMapApiTest(unittest.TestCase):
    def test_world_exposes_database_map_places(self):
        payload = world()
        places = {item["id"]: item for item in payload["map_places"]}
        self.assertGreaterEqual(len(places), 10)
        self.assertEqual(places["pallas"]["map_position"]["mode"], "point")
        self.assertEqual(places["placidium"]["name"], "纳沃利普雷西典")
        self.assertEqual(places["navori"]["map_position"]["mode"], "estimated_area")


if __name__ == "__main__":
    unittest.main()
