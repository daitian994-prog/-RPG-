from backend.database.lore_repository import LoreRepository


OFFICIAL_REGION_PAGE = "https://universe.leagueoflegends.com/en_US/region/ionia/"
OFFICIAL_MAP_PAGE = "https://map.leagueoflegends.com/"
DATA_DRAGON_DOCS = "https://developer.riotgames.com/docs/lol#data-dragon"

# Riot's public pins file uses a world coordinate system centered on the map.
# The official client samples its 2048 x 2048 texture with x + 1024, 1024 - y.
# Entries without an official pin intentionally have no point coordinates.
PLACE_MEDIA = {
    "ionian_archipelago": (539, 232, "ionia", "first-lands.jpg"),
    "navori": (None, None, None, "ionian-farm.jpg"),
    "placidium": (480, 240, "placidium", "placidium.jpg"),
    "bahrl": (None, None, None, "great-monasteries.jpg"),
    "wuju_village": (467, 171, "master-yi-village", "great-stand.jpg"),
    "omikayalan": (None, None, None, "vastaya.jpg"),
    "koyehn": (None, None, None, "coastal-region.jpg"),
    "faelor": (361, 200, "faelor", "great-stand.jpg"),
    "pallas": (650, 31, "temple-pallas", "great-monasteries.jpg"),
    "wehle": (430, 183, "wehle", "village-market.jpg"),
    "shojin_monastery": (None, None, None, "great-monasteries.jpg"),
    "kinkou_temple": (421, 286, "kinkou-monastery", "kinkou.jpg"),
    "lasting_altar_place": (None, None, None, "great-monasteries.jpg"),
    "zhyun_pits": (594, 133, "zhyunia", "village-market.jpg"),
}

# Editorial estimates for places that Riot names in official stories but does not
# expose as public map pins. Coordinates use the same 2048 texture as official
# pins; radius expresses uncertainty rather than a literal administrative border.
ESTIMATED_PLACE_POSITIONS = {
    "navori": {
        "x": 1535, "y": 824, "radius": 118, "confidence": "high", "confidence_label": "较高",
        "basis": "纳沃利是包含普雷西典的中央省份；范围由普雷西典、崴里与哲云尼亚三个官方锚点共同约束。",
    },
    "bahrl": {
        "x": 1491, "y": 866, "radius": 64, "confidence": "high", "confidence_label": "较高",
        "basis": "官方传记明确无极村位于巴鲁省；以 Riot 的无极村锚点为中心，按省份尺度向周边扩展。",
    },
    "omikayalan": {
        "x": 1720, "y": 722, "radius": 92, "confidence": "low", "confidence_label": "较低",
        "basis": "官方故事仅确认它是远离城市聚落的古老原始森林与世界之心；结合艾欧尼亚东北部连续林地形态作低可信度推定。",
    },
    "koyehn": {
        "x": 1370, "y": 690, "radius": 58, "confidence": "medium", "confidence_label": "中等",
        "basis": "惠的官方背景明确科耶恩是西北岛屿，并具有海滩、集市与寺院；据西北离岛群的海岸地形推定。",
    },
    "shojin_monastery": {
        "x": 1642, "y": 770, "radius": 48, "confidence": "low", "confidence_label": "较低",
        "basis": "李青传记确认朔极寺院及其龙之灵传统，但未给出可与公开锚点直接对齐的位置；暂按东部山地寺院带推定。",
    },
    "lasting_altar_place": {
        "x": 1548, "y": 744, "radius": 42, "confidence": "medium", "confidence_label": "中等",
        "basis": "长存之殿属于纳沃利政治与精神中心，并与普雷西典及卡尔玛活动紧密相关；据普雷西典官方锚点向北部山地推定。",
    },
}

PLACE_REGIONS = {
    "ionian_archipelago": [], "navori": ["ionian_archipelago"], "placidium": ["navori"],
    "bahrl": ["ionian_archipelago"], "wuju_village": ["bahrl"], "omikayalan": ["ionian_archipelago"],
    "koyehn": ["ionian_archipelago"], "faelor": ["ionian_archipelago"], "pallas": ["ionian_archipelago"],
    "wehle": ["navori"], "shojin_monastery": ["ionian_archipelago"],
    "kinkou_temple": ["ionian_archipelago"], "lasting_altar_place": ["navori"], "zhyun_pits": ["navori"],
}

PLACE_FACTIONS = {
    "ionian_archipelago": [], "navori": ["lasting_altar", "navori_brotherhood", "noxian_occupation"],
    "placidium": ["lasting_altar", "noxian_occupation"], "bahrl": [], "wuju_village": ["noxian_occupation"],
    "omikayalan": ["vastaya_rebels"], "koyehn": [], "faelor": ["noxian_occupation"],
    "pallas": ["noxian_occupation"], "wehle": [], "shojin_monastery": ["shojin"],
    "kinkou_temple": ["kinkou", "shadow_order"], "lasting_altar_place": ["lasting_altar"], "zhyun_pits": [],
}

TIMELINE_MEDIA = {
    10: "vastaya.jpg", 30: "first-lands.jpg", 40: "great-monasteries.jpg",
    60: "great-stand.jpg", 70: "placidium.jpg", 80: "great-monasteries.jpg",
    90: "great-stand.jpg", 110: "coastal-region.jpg", 120: "kinkou.jpg",
    130: "first-lands.jpg", 150: "vastaya.jpg", 190: "great-stand.jpg",
}

TIMELINE_LINKS = {
    10: (["omikayalan"], ["vastaya_rebels"], ["xayah", "rakan", "wukong"]),
    20: (["pallas"], [], ["varus"]), 30: (["omikayalan"], [], ["ivern"]),
    40: (["lasting_altar_place"], ["lasting_altar"], ["karma", "darha"]),
    50: (["kinkou_temple"], ["kinkou"], ["jhin", "shen", "zed", "kusho"]),
    60: (["ionian_archipelago", "navori", "faelor", "pallas"], ["noxian_occupation"], []),
    70: (["placidium", "navori"], ["noxian_occupation", "lasting_altar"], ["irelia", "karma", "swain"]),
    80: (["shojin_monastery"], ["shojin", "noxian_occupation"], ["lee_sin"]),
    90: (["wuju_village", "bahrl"], ["noxian_occupation"], ["master_yi", "singed"]),
    100: (["navori"], ["noxian_occupation"], ["yasuo", "yone", "riven", "souma"]),
    110: (["pallas"], ["noxian_occupation"], ["varus", "kai", "valmar"]),
    120: (["kinkou_temple"], ["kinkou", "shadow_order"], ["zed", "shen", "kennen"]),
    130: (["ionian_archipelago", "navori"], ["noxian_occupation", "navori_brotherhood", "kinkou", "shadow_order"], []),
    140: (["kinkou_temple"], ["kinkou"], ["akali", "shen"]),
    150: (["omikayalan"], ["vastaya_rebels", "shadow_order"], ["xayah", "rakan", "zed"]),
    160: (["wehle"], [], ["yasuo", "yone", "riven"]),
    170: (["faelor"], ["noxian_occupation"], ["syndra"]),
    180: (["koyehn"], [], ["hwei", "jhin"]),
    190: (["faelor"], ["noxian_occupation"], ["riven"]),
    200: (["lasting_altar_place"], ["kinkou"], ["yunara"]),
}

FACTION_MEDIA = {
    "kinkou": "kinkou.jpg", "shadow_order": "kinkou.jpg", "shojin": "great-monasteries.jpg",
    "lasting_altar": "great-monasteries.jpg", "vastaya_rebels": "vastaya.jpg",
    "navori_brotherhood": "great-stand.jpg", "noxian_occupation": "great-stand.jpg",
}


def update_media(repository: LoreRepository) -> None:
    for record in repository.list("champions"):
        data = {**record["data"],
                "image_url": f"/admin/assets/official/champions/{record['id']}.jpg",
                "image_source_url": DATA_DRAGON_DOCS,
                "image_credit": "Riot Games · Data Dragon 官方原画"}
        repository.update("champions", record["id"], record["title"], data)

    for record in repository.list("places"):
        world_x, world_y, pin_slug, filename = PLACE_MEDIA[record["id"]]
        if pin_slug:
            map_position = {
                "mode": "point",
                "x": world_x + 1024,
                "y": 1024 - world_y,
                "space": "riot_texture_2048",
                "official": True,
                "official_pin_slug": pin_slug,
                "official_world_position": {"x": world_x, "y": world_y},
                "precision": "Riot 官方互动地图锚点",
            }
        elif record["id"] in ESTIMATED_PLACE_POSITIONS:
            estimate = ESTIMATED_PLACE_POSITIONS[record["id"]]
            map_position = {
                "mode": "estimated_area",
                "x": estimate["x"],
                "y": estimate["y"],
                "radius": estimate["radius"],
                "space": "riot_texture_2048",
                "official": False,
                "confidence": estimate["confidence"],
                "confidence_label": estimate["confidence_label"],
                "basis": estimate["basis"],
                "precision": f"剧情与地理关系推定 · 可信度{estimate['confidence_label']} · 非 Riot 官方坐标",
            }
        else:
            map_position = {
                "mode": "unlocated",
                "space": "riot_texture_2048",
                "official": False,
                "precision": "官方故事确认该地点存在，但 Riot 互动地图未公开精确锚点",
            }
        data = {**record["data"],
                "image_url": f"/admin/assets/official/ionia/{filename}",
                "image_source_url": OFFICIAL_REGION_PAGE,
                "image_credit": "Riot Games · Universe 艾欧尼亚地区素材",
                "related_regions": PLACE_REGIONS[record["id"]],
                "related_factions": PLACE_FACTIONS[record["id"]],
                "map_position": map_position,
                "map_source_url": OFFICIAL_MAP_PAGE}
        repository.update("places", record["id"], record["title"], data)

    for record in repository.list("timeline"):
        order = record["data"].get("order")
        filename = TIMELINE_MEDIA.get(order, "first-lands.jpg")
        regions, factions, characters = TIMELINE_LINKS.get(order, ([], [], []))
        data = {**record["data"], "image_url": f"/admin/assets/official/ionia/{filename}",
                "image_source_url": OFFICIAL_REGION_PAGE,
                "image_credit": "Riot Games · Universe 艾欧尼亚地区素材",
                "related_regions": regions, "related_factions": factions, "related_characters": characters}
        repository.update("timeline", record["id"], record["title"], data)

    for record in repository.list("factions"):
        filename = FACTION_MEDIA.get(record["id"], "first-lands.jpg")
        data = {**record["data"], "image_url": f"/admin/assets/official/ionia/{filename}",
                "image_source_url": OFFICIAL_REGION_PAGE,
                "image_credit": "Riot Games · Universe 艾欧尼亚地区素材"}
        repository.update("factions", record["id"], record["title"], data)

    region = repository.list("region")[0]
    region_data = {**region["data"], "image_url": "/admin/assets/official/ionia/first-lands.jpg",
                   "map_image_url": "/admin/assets/official/ionia/runeterra-terrain.jpg",
                   "image_source_url": OFFICIAL_REGION_PAGE, "map_source_url": OFFICIAL_MAP_PAGE}
    repository.update("region", region["id"], region["title"], region_data)


if __name__ == "__main__":
    update_media(LoreRepository())
    print("Lore media metadata updated.")
