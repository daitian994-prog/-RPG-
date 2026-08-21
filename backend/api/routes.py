import json
import logging
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.models.schemas import ChoiceRequest, DialogueRequest, EventNarrativeRequest, NewGameRequest, RecoveryRequest, TravelRequest, WorldFocusRequest, WorldThreadInterventionRequest
from backend.services.game_service import GameService
from backend.services.public_view_service import PublicViewService

router = APIRouter(prefix="/api")
service = GameService()
public_views = PublicViewService()
logger = logging.getLogger(__name__)


def _debug_allowed(requested: bool) -> bool:
    production = os.getenv("RUNETERRA_ENV", "development").lower() in {"production", "prod"} or bool(os.getenv("VERCEL"))
    return requested and not production


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
def new_game(payload: NewGameRequest, debug: bool = False):
    enabled = _debug_allowed(debug)
    return {"game": public_views.game(service.new_game(payload.answers), debug=enabled)}


@router.get("/games/{game_id}")
def get_game(game_id: str, debug: bool = False):
    try:
        return {"game": public_views.game(service.get(game_id), debug=_debug_allowed(debug))}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/travel")
def travel(payload: TravelRequest, debug: bool = False):
    try:
        game, event = service.travel(payload.game_id, payload.location_id)
        enabled = _debug_allowed(debug)
        return {"game": public_views.game(game, debug=enabled), "event": public_views.event(event, debug=enabled)}
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/travel/prepare")
def prepare_travel(payload: TravelRequest, debug: bool = False):
    """L1: resolve world facts immediately; prose is streamed separately."""
    try:
        game, event = service.travel(payload.game_id, payload.location_id, narrate=False)
        enabled = _debug_allowed(debug)
        return {"game": public_views.game(game, debug=enabled), "event": public_views.event(event, debug=enabled)}
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
def choose(payload: ChoiceRequest, debug: bool = False):
    try:
        game, resolution = service.resolve(payload.game_id, payload.event_id, payload.choice_index, payload.choice_round)
        enabled = _debug_allowed(debug)
        next_event = resolution.get("nextEvent")
        return {
            "game": public_views.game(game, debug=enabled), "message": resolution["narrative"],
            "resolution": public_views.resolution(resolution, debug=enabled),
            "event": public_views.event(next_event, debug=enabled) if next_event else None,
        }
    except (KeyError, ValueError, IndexError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/recover")
def recover(payload: RecoveryRequest, debug: bool = False):
    try:
        game, recovery = service.recover(payload.game_id, payload.method)
        return {"game": public_views.game(game, debug=_debug_allowed(debug)), "recovery": recovery, "message": game["log"][-1]}
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/world-threads/intervene")
def intervene_world_thread(payload: WorldThreadInterventionRequest, debug: bool = False):
    try:
        game, intervention = service.intervene_world_thread(payload.game_id, payload.thread_id, payload.strategy)
        return {"game": public_views.game(game, debug=_debug_allowed(debug)), "intervention": intervention}
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/world-focus")
def focus_world_topic(payload: WorldFocusRequest, debug: bool = False):
    try:
        game, focus = service.focus_world_topic(payload.game_id, payload.topic_id, payload.focused)
        return {"game": public_views.game(game, debug=_debug_allowed(debug)), "focus": focus}
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/dialogue")
def dialogue(payload: DialogueRequest, debug: bool = False):
    try:
        game, message = service.dialogue(payload.game_id, payload.npc_id)
        return {"game": public_views.game(game, debug=_debug_allowed(debug)), "message": message}
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
