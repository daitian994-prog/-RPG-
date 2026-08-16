import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.models.schemas import ChoiceRequest, DialogueRequest, EventNarrativeRequest, NewGameRequest, RecoveryRequest, TravelRequest, WorldFocusRequest, WorldThreadInterventionRequest
from backend.services.game_service import GameService

router = APIRouter(prefix="/api")
service = GameService()
logger = logging.getLogger(__name__)


@router.get("/world")
def world():
    map_places = [
        {
            "id": place["id"],
            "name": place["name"],
            "type": place.get("type", "地点"),
            "map_position": place.get("map_position"),
        }
        for place in service.ai.lore.collection("places")
        if place.get("map_position", {}).get("mode") in {"point", "estimated_area"}
    ]
    return {"world": service.world, "locations": service.locations, "map_places": map_places, "npcs": service.npcs}


@router.post("/games")
def new_game(payload: NewGameRequest):
    return {"game": service.new_game(payload.answers)}


@router.get("/games/{game_id}")
def get_game(game_id: str):
    try:
        return {"game": service.get(game_id)}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/travel")
def travel(payload: TravelRequest):
    try:
        game, event = service.travel(payload.game_id, payload.location_id)
        return {"game": game, "event": event}
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/travel/prepare")
def prepare_travel(payload: TravelRequest):
    """L1: resolve world facts immediately; prose is streamed separately."""
    try:
        game, event = service.travel(payload.game_id, payload.location_id, narrate=False)
        return {"game": game, "event": event}
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/events/narrative-stream")
def narrative_stream(payload: EventNarrativeRequest):
    def ndjson():
        try:
            buffer = ""
            paragraphs = []
            for delta in service.stream_event(payload.game_id, payload.event_id):
                buffer += delta
                while "\n\n" in buffer:
                    paragraph, buffer = buffer.split("\n\n", 1)
                    if paragraph.strip():
                        paragraphs.append(paragraph.strip())
                        yield json.dumps({"type": "paragraph", "index": len(paragraphs) - 1, "text": paragraph.strip()}, ensure_ascii=False) + "\n"
            if buffer.strip():
                paragraphs.append(buffer.strip())
                yield json.dumps({"type": "paragraph", "index": len(paragraphs) - 1, "text": buffer.strip()}, ensure_ascii=False) + "\n"
            yield json.dumps({"type": "complete", "text": "\n\n".join(paragraphs)}, ensure_ascii=False) + "\n"
        except (KeyError, ValueError) as exc:
            logger.exception("event narrative stream failed")
            yield json.dumps({"type": "error", "message": "周围暂时没有新的发现。"}, ensure_ascii=False) + "\n"

    return StreamingResponse(ndjson(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/choices")
def choose(payload: ChoiceRequest):
    try:
        game, resolution = service.resolve(payload.game_id, payload.event_id, payload.choice_index)
        return {"game": game, "message": resolution["narrative"], "resolution": resolution}
    except (KeyError, ValueError, IndexError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/recover")
def recover(payload: RecoveryRequest):
    try:
        game, recovery = service.recover(payload.game_id, payload.method)
        return {"game": game, "recovery": recovery, "message": game["log"][-1]}
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/world-threads/intervene")
def intervene_world_thread(payload: WorldThreadInterventionRequest):
    try:
        game, intervention = service.intervene_world_thread(payload.game_id, payload.thread_id, payload.strategy)
        return {"game": game, "intervention": intervention}
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/world-focus")
def focus_world_topic(payload: WorldFocusRequest):
    try:
        game, focus = service.focus_world_topic(payload.game_id, payload.topic_id, payload.focused)
        return {"game": game, "focus": focus}
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/dialogue")
def dialogue(payload: DialogueRequest):
    try:
        game, message = service.dialogue(payload.game_id, payload.npc_id)
        return {"game": game, "message": message}
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
