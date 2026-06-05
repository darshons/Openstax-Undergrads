import uuid
from typing import List

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, selectinload

from app.database import SessionLocal
from app.models import Node, Scenario
from app.schemas import ScenarioDetail, ScenarioResponse

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
    return scenario
