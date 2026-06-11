"""
Inserts one dummy scenario (with nodes and an edge) for local dev/testing.
    python seed_db.py
"""
from app.database import SessionLocal
from app.models import Edge, Node, Scenario, ScenarioStatus


def seed() -> None:
    db = SessionLocal()
    try:
        scenario = Scenario(
            chapter_reference="Clinical Nursing Chapter 3: Anaphylaxis",
            status=ScenarioStatus.READY,
        )
        db.add(scenario)
        db.flush()  # populate scenario.id before referencing it in nodes

        node1 = Node(
            scenario_id=scenario.id,
            video_path="/static/videos/scene1.mp4",
            node_prompt="Patient shows signs of anaphylaxis. What is your first step?",
            is_endpoint=False,
        )
        node2 = Node(
            scenario_id=scenario.id,
            video_path="/static/videos/misconception1.mp4",
            node_prompt="That was incorrect. Let's explore why.",
            is_endpoint=True,
        )
        db.add_all([node1, node2])
        db.flush()

        edge = Edge(
            origin_node_id=node1.id,
            destination_node_id=node2.id,
            choice_text="Give them a glass of water",
            is_misconception_branch=True,
        )
        db.add(edge)
        db.commit()

        print("Seed complete.")
        print(f"Created scenario ID: {scenario.id}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
