"""
Run once to create all tables in the configured Postgres database:
    python init_db.py
"""
from app.database import Base, engine

# Import all models so their metadata is registered with Base before create_all.
from app.models import (  # noqa: F401
    Edge,
    Node,
    Scenario,
    SessionAnalytics,
    StudentSession,
)


def init_db() -> None:
    print(f"Creating tables against: {engine.url}")
    Base.metadata.create_all(bind=engine)
    print("Done — all tables created.")


if __name__ == "__main__":
    init_db()
