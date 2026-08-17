import sqlite3

from fastapi import APIRouter, HTTPException, Response

from backend.database.api_nodes import ApiNodeRepository
from backend.database.lore_repository import LORE_CATEGORIES, LoreRepository
from backend.database.official_lore_repository import OfficialLoreRepository
from backend.models.schemas import (
    ApiNodeCreate,
    ApiNodePayload,
    ApiNodeToggle,
    GenerateTextRequest,
    LoreRecordCreate,
    LoreRecordUpdate,
)
from backend.services.deepseek_service import DeepSeekError, DeepSeekService
from backend.services.project_status_service import get_project_status


router = APIRouter(prefix="/api/admin", tags=["AI 节点管理"])
repository = ApiNodeRepository()
lore_repository = LoreRepository()
official_lore_repository = OfficialLoreRepository()
ai_client = DeepSeekService(repository)


@router.get("/project-status")
def project_status():
    return get_project_status()


@router.get("/ai-nodes")
def list_nodes():
    return {"nodes": repository.list(), "status": ai_client.status()}


@router.post("/ai-nodes", status_code=201)
def create_node(payload: ApiNodeCreate):
    try:
        return {"node": repository.create(payload.model_dump())}
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "节点名称已存在，请换一个名称。") from exc


@router.put("/ai-nodes/{node_id}")
def update_node(node_id: str, payload: ApiNodePayload):
    try:
        node = repository.update(node_id, payload.model_dump())
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "节点名称已存在，请换一个名称。") from exc
    if not node:
        raise HTTPException(404, "API 节点不存在。")
    return {"node": node}


@router.post("/ai-nodes/{node_id}/toggle")
def toggle_node(node_id: str, payload: ApiNodeToggle):
    node = repository.set_enabled(node_id, payload.enabled)
    if not node:
        raise HTTPException(404, "API 节点不存在。")
    return {"node": node, "nodes": repository.list(), "status": ai_client.status()}


@router.post("/ai-nodes/{node_id}/test")
def test_node(node_id: str):
    node = repository.get(node_id, include_secret=True)
    if not node:
        raise HTTPException(404, "API 节点不存在。")
    try:
        result = ai_client.generate(
            config=node,
            system="你是连接测试助手。",
            prompt="只回复：连接成功",
            temperature=0,
            max_tokens=64,
        )
        return {"ok": True, "message": result["text"], "model": result["model"]}
    except DeepSeekError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.delete("/ai-nodes/{node_id}", status_code=204)
def delete_node(node_id: str):
    if not repository.delete(node_id):
        raise HTTPException(404, "API 节点不存在。")
    return Response(status_code=204)


@router.get("/ai-status")
def ai_status():
    return ai_client.status()


@router.post("/generate")
def generate_text(payload: GenerateTextRequest):
    try:
        return ai_client.generate(**payload.model_dump())
    except DeepSeekError as exc:
        raise HTTPException(503, str(exc)) from exc


def _validate_lore_category(category: str) -> None:
    if category not in LORE_CATEGORIES:
        raise HTTPException(404, "未知的知识库分类。")


@router.get("/lore")
def lore_database_summary():
    return {
        "storage": "sqlite",
        "database": "game.db",
        "categories": list(LORE_CATEGORIES),
        "counts": lore_repository.counts(),
        "official_zh_cn_counts": official_lore_repository.counts("zh_cn"),
    }


@router.get("/lore-official")
def list_official_lore(category: str = "", q: str = ""):
    return {
        "locale": "zh_cn",
        "counts": official_lore_repository.counts("zh_cn"),
        "records": official_lore_repository.list("zh_cn", category, q, include_payload=False),
    }


@router.get("/lore-official/{category}/{record_id}")
def get_official_lore(category: str, record_id: str):
    record = official_lore_repository.get("zh_cn", category, record_id)
    if not record:
        raise HTTPException(404, "尚未同步这条中文官网资料。")
    return {"record": record}


@router.get("/lore/{category}")
def list_lore_records(category: str, q: str = "", limit: int = 200, offset: int = 0):
    _validate_lore_category(category)
    return {
        "category": category,
        "records": lore_repository.list(category, q, min(max(limit, 1), 500), max(offset, 0)),
    }


@router.post("/lore/{category}", status_code=201)
def create_lore_record(category: str, payload: LoreRecordCreate):
    _validate_lore_category(category)
    try:
        record = lore_repository.create(category, payload.id, payload.title, payload.data)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "该分类中已经存在相同 ID。") from exc
    return {"record": record}


@router.put("/lore/{category}/{record_id}")
def update_lore_record(category: str, record_id: str, payload: LoreRecordUpdate):
    _validate_lore_category(category)
    record = lore_repository.update(category, record_id, payload.title, payload.data)
    if not record:
        raise HTTPException(404, "知识库记录不存在。")
    return {"record": record}


@router.delete("/lore/{category}/{record_id}", status_code=204)
def delete_lore_record(category: str, record_id: str):
    _validate_lore_category(category)
    if category in {"metadata", "region"}:
        raise HTTPException(409, "元数据和地区总览是知识库根记录，只能编辑，不能删除。")
    if not lore_repository.delete(category, record_id):
        raise HTTPException(404, "知识库记录不存在。")
    return Response(status_code=204)
