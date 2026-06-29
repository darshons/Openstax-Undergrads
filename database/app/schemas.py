import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict

from .models import ScenarioStatus


class EdgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    origin_node_id: uuid.UUID
    destination_node_id: uuid.UUID
    choice_text: str
    is_misconception_branch: bool


class NodeDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scenario_id: uuid.UUID
    video_path: Optional[str]
    node_prompt: Optional[str]
    is_endpoint: bool
    outgoing_edges: List[EdgeResponse]


class ScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chapter_reference: str
    status: ScenarioStatus
    created_at: datetime
    updated_at: datetime


class ScenarioDetail(ScenarioResponse):
    nodes: List[NodeDetail]
    script: Optional[Any] = None


class GenerateRequest(BaseModel):
    textbook: str
    unit_num: int
    chapter_num: Optional[int] = None
    page_num: Optional[str] = None
    description: str
    model: str = "anthropic"


class GenerateResponse(BaseModel):
    scenario_id: uuid.UUID
    script: Any


class SaveScriptRequest(BaseModel):
    script: Any


class SaveScriptResponse(BaseModel):
    scenario_id: uuid.UUID


class NodeUpdate(BaseModel):
    node_prompt: Optional[str] = None
