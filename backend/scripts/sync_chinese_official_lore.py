"""Synchronize official Simplified Chinese Ionia lore without overwriting curated lore."""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.lore_repository import LoreRepository
from backend.database.official_lore_repository import OfficialLoreRepository


LOCALE = "zh_cn"
REGION_URL = "https://yz.lol.qq.com/v1/zh_cn/factions/ionia/index.json"
REGION_PAGE = "https://yz.lol.qq.com/zh_CN/region/ionia/"
CHAMPION_API = "https://yz.lol.qq.com/v1/zh_cn/champions/{slug}/index.json"
CHAMPION_PAGE = "https://yz.lol.qq.com/zh_CN/champion/{slug}/"
STORY_API = "https://yz.lol.qq.com/v1/zh_cn/story/{slug}/index.json"
STORY_PAGE = "https://yz.lol.qq.com/zh_CN/story/{slug}/"


def fetch_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "RuneterraLoreSync/1.0", "Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def plain_text(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip()


def associated_champions(region: dict[str, Any]) -> list[dict[str, Any]]:
    raw = region.get("associated-champions") or []
    if isinstance(raw, dict):
        raw = raw.get("champions") or raw.get("items") or list(raw.values())
    return [item for item in raw if isinstance(item, dict) and item.get("slug")]


def local_champion_id(item: dict[str, Any], lore: LoreRepository) -> str:
    slug = str(item.get("slug", "")).lower().replace("-", "")
    aliases = {"monkeyking": "wukong"}
    by_slug = {record["id"].replace("_", "").lower(): record["id"] for record in lore.list("champions")}
    by_name = {record["title"].strip(): record["id"] for record in lore.list("champions")}
    return aliases.get(slug) or by_slug.get(slug) or by_name.get(str(item.get("name", "")).strip()) or str(item["slug"])


def compact_champion_payload(payload: dict[str, Any]) -> dict[str, Any]:
    champion = payload.get("champion") or {}
    biography = champion.get("biography") or {}
    return {
        "official_name": champion.get("name") or payload.get("name"),
        "official_title": champion.get("title") or payload.get("title"),
        "slug": champion.get("slug") or payload.get("id"),
        "roles": champion.get("roles") or [],
        "image": champion.get("image") or {},
        "biography": {
            "short": biography.get("short") or "",
            "full": biography.get("full") or "",
            "quote": biography.get("quote") or "",
            "short_text": plain_text(biography.get("short") or ""),
            "full_text": plain_text(biography.get("full") or ""),
        },
        "modules": payload.get("modules") or [],
        "related_champions": payload.get("related-champions") or [],
        "raw": payload,
    }


def compact_story_payload(payload: dict[str, Any], related_characters: list[str]) -> dict[str, Any]:
    story = payload.get("story") or {}
    fragments: list[str] = []
    for section in story.get("story-sections") or []:
        for subsection in section.get("story-subsections") or []:
            content = plain_text(subsection.get("content") or "")
            if content:
                fragments.append(content)
    return {
        "title": story.get("title") or payload.get("id"),
        "subtitle": story.get("subtitle") or "",
        "preview": plain_text(story.get("custom-story-preview") or ""),
        "body_text": "\n\n".join(fragments),
        "related_characters": sorted(set(related_characters)),
        "release_date": payload.get("release-date"),
        "minutes_to_read": payload.get("minutes-to-read"),
        "raw": payload,
    }


def publish_official_stories(
    snapshots: OfficialLoreRepository,
    lore: LoreRepository,
) -> dict[str, int]:
    """Publish Chinese official story snapshots into the editable main lore database."""
    champion_records = lore.list("champions")
    story_ids_by_champion: dict[str, list[str]] = {record["id"]: [] for record in champion_records}
    published = 0

    for snapshot in snapshots.list(LOCALE, "stories", include_payload=True):
        payload = snapshot["payload"]
        related_characters = payload.get("related_characters") or []
        story_data = {
            "id": snapshot["id"],
            "title": payload.get("title") or snapshot["title"],
            "author": payload.get("subtitle") or "",
            "preview": payload.get("preview") or "",
            "content": payload.get("body_text") or "",
            "related_characters": related_characters,
            "release_date": payload.get("release_date"),
            "minutes_to_read": payload.get("minutes_to_read"),
            "source_url": snapshot["source_url"],
            "official_locale": LOCALE,
            "official_snapshot_id": snapshot["id"],
            "source_ids": [f"zh_cn_story:{snapshot['id']}"],
        }
        existing = lore.get("stories", snapshot["id"])
        if existing:
            lore.update("stories", snapshot["id"], story_data["title"], {**existing["data"], **story_data})
        else:
            lore.create("stories", snapshot["id"], story_data["title"], story_data)
        published += 1
        for champion_id in related_characters:
            if champion_id in story_ids_by_champion:
                story_ids_by_champion[champion_id].append(snapshot["id"])

    linked = 0
    for champion in champion_records:
        story_ids = sorted(set(story_ids_by_champion[champion["id"]]))
        data = {
            **champion["data"],
            "story_ids": story_ids,
            "official_story_count": len(story_ids),
            "official_story_status": (
                "中文官网人物故事已同步"
                if story_ids
                else "中文官网当前仅提供人物传记，暂无独立人物故事"
            ),
        }
        lore.update("champions", champion["id"], champion["title"], data)
        linked += bool(story_ids)

    return {"stories": published, "champions_with_stories": linked}


def sync(
    snapshots: OfficialLoreRepository,
    lore: LoreRepository,
    fetcher: Callable[[str], dict[str, Any]] = fetch_json,
) -> dict[str, Any]:
    region = fetcher(REGION_URL)
    region_title = region.get("name") or (region.get("faction") or {}).get("name") or "艾欧尼亚"
    snapshots.upsert(LOCALE, "region", "ionia", str(region_title), REGION_PAGE, region)

    synced: list[str] = []
    story_refs: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    for item in associated_champions(region):
        slug = str(item["slug"])
        record_id = local_champion_id(item, lore)
        try:
            payload = fetcher(CHAMPION_API.format(slug=slug))
            compact = compact_champion_payload(payload)
            title = compact["official_name"] or item.get("name") or slug
            snapshots.upsert(
                LOCALE,
                "champions",
                record_id,
                str(title),
                CHAMPION_PAGE.format(slug=slug),
                compact,
            )
            if slug != record_id:
                snapshots.delete(LOCALE, "champions", slug)
            synced.append(record_id)
            for module in payload.get("modules") or []:
                story_slug = module.get("story-slug") if module.get("type") == "story-preview" else None
                if not story_slug:
                    continue
                ref = story_refs.setdefault(str(story_slug), {"title": module.get("title") or story_slug, "characters": []})
                ref["characters"].append(record_id)
        except Exception as exc:  # one unavailable profile must not discard the successful snapshots
            errors.append({"slug": slug, "error": str(exc)})

    synced_stories: list[str] = []
    for story_slug, ref in story_refs.items():
        try:
            payload = fetcher(STORY_API.format(slug=story_slug))
            compact = compact_story_payload(payload, ref["characters"])
            snapshots.upsert(
                LOCALE,
                "stories",
                story_slug,
                str(compact["title"] or ref["title"]),
                STORY_PAGE.format(slug=story_slug),
                compact,
            )
            synced_stories.append(story_slug)
        except Exception as exc:
            errors.append({"slug": story_slug, "error": str(exc)})
    published = publish_official_stories(snapshots, lore)
    return {"region": "ionia", "champions": synced, "stories": synced_stories, "published": published, "errors": errors}


if __name__ == "__main__":
    result = sync(OfficialLoreRepository(), LoreRepository())
    print(json.dumps({"synced_champions": len(result["champions"]), "synced_stories": len(result["stories"]), **result}, ensure_ascii=False, indent=2))
