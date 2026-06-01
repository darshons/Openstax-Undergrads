import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ScenarioStatus(str, PyEnum):
    GENERATING_SCRIPT = "generating_script"
    SCRIPT_READY = "script_ready"
    GENERATING_VIDEO = "generating_video"
    READY = "ready"
    FAILED = "failed"


class SessionStatus(str, PyEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DROPPED = "dropped"


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chapter_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    script_draft: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ScenarioStatus] = mapped_column(
        Enum(ScenarioStatus, name="scenario_status"),
        nullable=False,
        default=ScenarioStatus.GENERATING_SCRIPT,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    nodes: Mapped[List["Node"]] = relationship(
        "Node", back_populates="scenario", cascade="all, delete-orphan"
    )
    student_sessions: Mapped[List["StudentSession"]] = relationship(
        "StudentSession", back_populates="scenario", cascade="all, delete-orphan"
    )


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    video_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    node_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_endpoint: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="nodes")

    # Node owns its outgoing edges; incoming edges are owned by their origin node.
    outgoing_edges: Mapped[List["Edge"]] = relationship(
        "Edge",
        foreign_keys="[Edge.origin_node_id]",
        back_populates="origin_node",
        cascade="all, delete-orphan",
    )
    incoming_edges: Mapped[List["Edge"]] = relationship(
        "Edge",
        foreign_keys="[Edge.destination_node_id]",
        back_populates="destination_node",
        passive_deletes=True,
    )
    analytics: Mapped[List["SessionAnalytics"]] = relationship(
        "SessionAnalytics",
        back_populates="node",
        passive_deletes=True,
    )


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    origin_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Deleting the destination node also removes this edge (dead link prevention).
    destination_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    choice_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_misconception_branch: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    origin_node: Mapped["Node"] = relationship(
        "Node", foreign_keys=[origin_node_id], back_populates="outgoing_edges"
    )
    destination_node: Mapped["Node"] = relationship(
        "Node", foreign_keys=[destination_node_id], back_populates="incoming_edges"
    )
    analytics: Mapped[List["SessionAnalytics"]] = relationship(
        "SessionAnalytics",
        back_populates="chosen_edge",
        passive_deletes=True,
    )


class StudentSession(Base):
    __tablename__ = "student_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_identifier: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"),
        nullable=False,
        default=SessionStatus.IN_PROGRESS,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    scenario: Mapped["Scenario"] = relationship(
        "Scenario", back_populates="student_sessions"
    )
    analytics: Mapped[List["SessionAnalytics"]] = relationship(
        "SessionAnalytics", back_populates="session", cascade="all, delete-orphan"
    )


class SessionAnalytics(Base):
    __tablename__ = "session_analytics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Primary ownership chain: deleting a session cascades through the ORM.
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # DB-level cascades handle deletion when a node or edge is removed directly.
    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    chosen_edge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("edges.id", ondelete="CASCADE"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped["StudentSession"] = relationship(
        "StudentSession", back_populates="analytics"
    )
    node: Mapped["Node"] = relationship("Node", back_populates="analytics")
    chosen_edge: Mapped["Edge"] = relationship("Edge", back_populates="analytics")
