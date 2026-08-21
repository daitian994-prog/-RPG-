from typing import Any

from pydantic import BaseModel, Field


class NewGameRequest(BaseModel):
    answers: list[str] = Field(min_length=6, max_length=6)


class TravelRequest(BaseModel):
    game_id: str
    location_id: str
    lead_id: str | None = None


class OpeningRequest(BaseModel):
    game_id: str


class EventNarrativeRequest(BaseModel):
    game_id: str
    event_id: str


class ChoiceRequest(BaseModel):
    game_id: str
    event_id: str
    choice_index: int = Field(ge=0, le=3)
    choice_round: int | None = Field(default=None, ge=1, le=4)


class DialogueRequest(BaseModel):
    game_id: str
    npc_id: str


class RecoveryRequest(BaseModel):
    game_id: str
    method: str = Field(default="rest", pattern="^(rest|supplies|treatment)$")


class WorldThreadInterventionRequest(BaseModel):
    game_id: str
    thread_id: str
    strategy: str = Field(pattern="^(investigate|intervene)$")


class WorldFocusRequest(BaseModel):
    game_id: str
    topic_id: str
    focused: bool = True


class GameEnvelope(BaseModel):
    game: dict[str, Any]
    event: dict[str, Any] | None = None
    message: str | None = None


class ApiNodePayload(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    provider: str = Field(default="deepseek", pattern="^(deepseek|openai_compatible)$")
    base_url: str = Field(min_length=8, max_length=300)
    model: str = Field(min_length=1, max_length=100)
    api_key: str = Field(default="", max_length=500)


class ApiNodeCreate(ApiNodePayload):
    api_key: str = Field(min_length=1, max_length=500)


class ApiNodeToggle(BaseModel):
    enabled: bool


class GenerateTextRequest(BaseModel):
    system: str = Field(default="你是《无名者：符文之地》的叙事生成器。", max_length=2000)
    prompt: str = Field(min_length=1, max_length=12000)
    temperature: float = Field(default=0.8, ge=0, le=2)
    max_tokens: int = Field(default=900, ge=64, le=4000)


class LoreRecordCreate(BaseModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_\-]+$")
    title: str = Field(min_length=1, max_length=160)
    data: dict[str, Any]


class LoreRecordUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    data: dict[str, Any]
