import json
import uuid
from typing import List

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, selectinload

from app.database import SessionLocal
from app.models import Edge, Node, Scenario, ScenarioStatus
from app.parser import crawl
from app.schemas import (
    GenerateRequest,
    GenerateResponse,
    NodeDetail,
    NodeUpdate,
    SaveScriptRequest,
    SaveScriptResponse,
    ScenarioDetail,
    ScenarioResponse,
)
from app.script_gen import generate_script

app = FastAPI(title="OpenStax Nursing Scenario API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/api/scenarios", response_model=List[ScenarioResponse])
def list_scenarios(db: Session = Depends(get_db)):
    return db.query(Scenario).all()


@app.get("/api/scenarios/{scenario_id}", response_model=ScenarioDetail)
def get_scenario(scenario_id: uuid.UUID, db: Session = Depends(get_db)):
    scenario = (
        db.query(Scenario)
        .options(selectinload(Scenario.nodes).selectinload(Node.outgoing_edges))
        .filter(Scenario.id == scenario_id)
        .first()
    )
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    result = ScenarioDetail.model_validate(scenario)
    if scenario.script_draft:
        try:
            result.script = json.loads(scenario.script_draft)
        except (json.JSONDecodeError, ValueError):
            pass
    return result


@app.post("/api/scenarios/generate", response_model=GenerateResponse)
def generate_scenario(request: GenerateRequest, db: Session = Depends(get_db)):
    # 1. Parse content → markdown via crawl()
    markdown = crawl(
        request.textbook,
        unit_num=request.unit_num,
        chapter_num=request.chapter_num,
        page_num=request.page_num,
    )

    # 2. Generate branching script
    try:
        script = generate_script(request.description, markdown, model=request.model)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Script generation failed: {exc}")

    chapter_ref = request.textbook
    if request.chapter_num is not None:
        chapter_ref += f" — Unit {request.unit_num}, Ch {request.chapter_num}"
    else:
        chapter_ref += f" — Unit {request.unit_num}"
    if len(chapter_ref) > 255:
        chapter_ref = chapter_ref[:252] + "..."

    # 3. Persist scenario
    scenario = Scenario(
        chapter_reference=chapter_ref,
        status=ScenarioStatus.SCRIPT_READY,
        script_draft=json.dumps(script),
    )
    db.add(scenario)
    db.flush()

    # 4. Persist nodes + edges derived from script
    _persist_script_nodes(db, scenario.id, script)
    db.commit()

    return GenerateResponse(scenario_id=scenario.id, script=script)


@app.put("/api/scenarios/{scenario_id}/script", response_model=SaveScriptResponse)
def save_script(
    scenario_id: uuid.UUID,
    body: SaveScriptRequest,
    db: Session = Depends(get_db),
):
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    scenario.script_draft = json.dumps(body.script)
    # Resync nodes/edges from the updated script
    db.query(Node).filter(Node.scenario_id == scenario_id).delete()
    db.flush()
    _persist_script_nodes(db, scenario_id, body.script)
    db.commit()
    return SaveScriptResponse(scenario_id=scenario_id)


@app.put(
    "/api/scenarios/{scenario_id}/nodes/{node_id}", response_model=NodeDetail
)
def update_node(
    scenario_id: uuid.UUID,
    node_id: uuid.UUID,
    update: NodeUpdate,
    db: Session = Depends(get_db),
):
    node = (
        db.query(Node)
        .options(selectinload(Node.outgoing_edges))
        .filter(Node.id == node_id, Node.scenario_id == scenario_id)
        .first()
    )
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    if update.node_prompt is not None:
        node.node_prompt = update.node_prompt
    db.commit()
    db.refresh(node)
    return node


def _persist_script_nodes(db: Session, scenario_id: uuid.UUID, script: dict) -> None:
    """Create Node and Edge rows from a script JSON object."""
    nodes_data = script.get("nodes", [])
    id_map: dict = {}

    for node_data in nodes_data:
        node = Node(
            scenario_id=scenario_id,
            node_prompt=node_data.get("script", ""),
            is_endpoint=node_data.get("is_endpoint", False),
        )
        db.add(node)
        db.flush()
        id_map[node_data["id"]] = node.id

    for node_data in nodes_data:
        origin_id = id_map.get(node_data["id"])
        if not origin_id:
            continue
        for choice in node_data.get("choices", []):
            dest_id = id_map.get(choice.get("destination_scene_id", ""))
            if not dest_id:
                continue
            edge = Edge(
                origin_node_id=origin_id,
                destination_node_id=dest_id,
                choice_text=choice.get("text", ""),
                is_misconception_branch=choice.get("is_misconception", False),
            )
            db.add(edge)
