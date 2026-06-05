import uuid
from datetime import datetime
from typing import List, Optional

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
