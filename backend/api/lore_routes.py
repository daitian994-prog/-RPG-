from fastapi import APIRouter, HTTPException, Query

from backend.services.lore_service import LoreService


router = APIRouter(prefix="/api/lore/ionia", tags=["艾欧尼亚世界观知识库"])
lore = LoreService()


@router.get("")
def lore_summary():
    return lore.summary()


@router.get("/champions")
def champions():
    return {"champions": lore.collection("champions")}


@router.get("/champions/{champion_id}")
def champion(champion_id: str):
    result = lore.champion(champion_id)
    if not result:
        raise HTTPException(404, "知识库中没有这个艾欧尼亚英雄。")
    return result


@router.get("/places")
def places():
    return {"places": lore.collection("places")}


@router.get("/factions")
def factions():
    return {"factions": lore.collection("factions")}


@router.get("/timeline")
def timeline():
    return {"timeline": lore.collection("timeline")}


@router.get("/relationships")
def relationships():
    return {"relationships": lore.collection("relationships")}


@router.get("/sources")
def sources():
    return {"sources": lore.collection("sources")}


@router.get("/search")
def search(q: str = Query(min_length=1, max_length=80), limit: int = Query(default=20, ge=1, le=50)):
    return {"query": q, "results": lore.search(q, limit)}
