import json
from typing import Any

from backend.database.lore_repository import LoreRepository


class LoreService:
    """Read-only Ionian lore repository and lightweight retrieval layer."""

    location_routes = {
        "pallas": {
            "places": ["pallas", "navori"],
            "champions": ["varus", "yasuo"],
            "factions": ["noxian_occupation"],
            "timeline": [20, 60, 110, 130],
        },
        "windbreak": {
            "places": ["omikayalan"],
            "champions": ["ivern", "lillia", "xayah", "rakan", "wukong"],
            "factions": ["vastaya_rebels"],
            "timeline": [10, 30, 150],
        },
        "war_ruins": {
            "places": ["placidium", "wuju_village", "faelor", "pallas"],
            "champions": ["irelia", "master_yi", "yasuo", "varus", "riven"],
            "factions": ["noxian_occupation", "shadow_order"],
            "timeline": [60, 70, 90, 100, 110, 130, 190],
        },
        "mountain_temple": {
            "places": ["shojin_monastery", "kinkou_temple", "lasting_altar_place"],
            "champions": ["lee_sin", "shen", "kennen", "karma", "akali"],
            "factions": ["shojin", "kinkou", "lasting_altar"],
            "timeline": [40, 80, 120, 140],
        },
    }

    def __init__(self, repository: LoreRepository | None = None) -> None:
        self.repository = repository or LoreRepository()
        self._refresh()

    def _refresh(self) -> None:
        self.metadata = self.repository.list("metadata")[0]["data"]
        self.region = self.repository.list("region")[0]["data"]
        self.champions = [item["data"] for item in self.repository.list("champions")]
        self.places = [item["data"] for item in self.repository.list("places")]
        self.factions = [item["data"] for item in self.repository.list("factions")]
        self.timeline = [item["data"] for item in self.repository.list("timeline")]
        self.relationships = [item["data"] for item in self.repository.list("relationships")]
        self.sources = [item["data"] for item in self.repository.list("sources")]
        self.champion_index = {item["id"]: item for item in self.champions}
        self.place_index = {item["id"]: item for item in self.places}
        self.faction_index = {item["id"]: item for item in self.factions}
        self.source_index = {item["id"]: item for item in self.sources}

    def collection(self, category: str) -> list[dict[str, Any]]:
        self._refresh()
        return {
            "champions": self.champions,
            "places": self.places,
            "factions": self.factions,
            "timeline": self.timeline,
            "relationships": self.relationships,
            "sources": self.sources,
        }[category]

    def summary(self) -> dict[str, Any]:
        self._refresh()
        return {
            "metadata": self.metadata,
            "region": self.region,
            "counts": {
                "champions": len(self.champions),
                "places": len(self.places),
                "factions": len(self.factions),
                "timeline_events": len(self.timeline),
                "relationships": len(self.relationships),
                "sources": len(self.sources),
            },
        }

    def champion(self, champion_id: str) -> dict[str, Any] | None:
        self._refresh()
        champion = self.champion_index.get(champion_id)
        if not champion:
            return None
        relationships = [
            edge for edge in self.relationships
            if edge["source"] == champion_id or edge["target"] == champion_id
        ]
        sources = [self.source_index[source_id] for source_id in champion.get("source_ids", []) if source_id in self.source_index]
        return {**champion, "relationship_edges": relationships, "sources": sources}

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        self._refresh()
        needle = query.strip().casefold()
        if not needle:
            return []
        results: list[dict[str, Any]] = []
        collections = {
            "champion": self.champions,
            "place": self.places,
            "faction": self.factions,
            "timeline": self.timeline,
            "relationship": self.relationships,
        }
        for kind, items in collections.items():
            for item in items:
                haystack = json.dumps(item, ensure_ascii=False).casefold()
                if needle in haystack:
                    title = item.get("name") or item.get("title") or f"{item.get('source')} → {item.get('target')}"
                    summary = item.get("summary") or item.get("profile") or ""
                    results.append({"kind": kind, "id": item.get("id") or item.get("order"), "title": title, "summary": summary})
                    if len(results) >= limit:
                        return results
        return results

    def _detect_champions(self, text: str) -> list[str]:
        found = []
        lower = text.casefold()
        for champion in self.champions:
            names = [champion["name"], champion["id"], champion.get("full_name", "")]
            if any(name and name.casefold() in lower for name in names):
                found.append(champion["id"])
        return found

    def context_for_event(self, location_id: str, event_type: str, text: str, max_chars: int = 1600) -> dict[str, Any]:
        self._refresh()
        route = self.location_routes.get(location_id, {})
        detected = self._detect_champions(text)
        champion_ids = list(dict.fromkeys([*detected, *route.get("champions", [])]))[:3]
        place_ids = route.get("places", [])[:2]
        faction_ids = route.get("factions", [])[:2]
        timeline_orders = set(route.get("timeline", []))

        context = {
            "地区基线": self.region["overview"],
            "当前地点关联": [
                {"name": self.place_index[item]["name"], "summary": self.place_index[item]["summary"]}
                for item in place_ids if item in self.place_index
            ],
            "相关人物": [
                {"name": self.champion_index[item]["name"], "status": self.champion_index[item]["status"], "profile": self.champion_index[item]["profile"]}
                for item in champion_ids if item in self.champion_index
            ],
            "相关派系": [
                {"name": self.faction_index[item]["name"], "summary": self.faction_index[item]["summary"]}
                for item in faction_ids if item in self.faction_index
            ],
            "历史背景": [
                {"title": item["title"], "summary": item["summary"]}
                for item in self.timeline if item["order"] in timeline_orders
            ][:3],
            "使用原则": "仅用于校验背景和气氛；不得让未被事件事实点名的英雄突然登场，不得泄露主角不可能知道的秘密。",
        }
        while len(json.dumps(context, ensure_ascii=False)) > max_chars:
            if context["历史背景"]:
                context["历史背景"].pop()
            elif context["相关人物"]:
                context["相关人物"].pop()
            elif context["相关派系"]:
                context["相关派系"].pop()
            elif context["当前地点关联"]:
                context["当前地点关联"].pop()
            else:
                break
        return context
