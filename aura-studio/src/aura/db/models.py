"""SQLAlchemy models — the product's durable state.

JSON columns hold validated pydantic dumps (brief/plan/package/events), so
the schema stays stable while the pydantic contracts evolve. LangGraph's
checkpointer manages its own tables alongside these in the same database.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, String,
    Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    """Owned by Auth.js on the web side; the engine only reads id/tier."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    image: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    # queued | running | waiting_input | waiting_review | done | failed | cancelled
    tier: Mapped[str] = mapped_column(String(16), default="preview")  # preview|standard|studio
    request_text: Mapped[str] = mapped_column(Text)
    brief: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    package: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_cap_usd: Mapped[float] = mapped_column(Numeric(10, 4), default=5.0)
    spent_usd: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0)
    paid: Mapped[bool] = mapped_column(default=False)   # deliverables unlocked
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now,
                                                 onupdate=_now)


class ProjectEventRow(Base):
    """Append-only event log; `id` doubles as the SSE event id for replay."""

    __tablename__ = "project_events"
    __table_args__ = (Index("ix_events_project_id_id", "project_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"),
                                    primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    type: Mapped[str] = mapped_column(String(40))
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TaskRow(Base):
    """UI projection of WorkPlan task state (the checkpointer owns the truth)."""

    __tablename__ = "tasks"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    role_key: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    depends_on: Mapped[list] = mapped_column(JSON, default=list)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InterruptRow(Base):
    """Mirror of pending graph interrupts so the web app never reads
    checkpoint blobs."""

    __tablename__ = "interrupts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    kind: Mapped[str] = mapped_column(String(24))     # clarify | studio_review
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ArtifactRow(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    candidate_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[str] = mapped_column(String(24))     # preview_png|print_pdf|video|source|input
    storage_key: Mapped[str] = mapped_column(Text)
    mime: Mapped[str] = mapped_column(String(100), default="application/octet-stream")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SubscriptionRow(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    tier: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(16))          # stripe | razorpay
    provider_customer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="active")
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                                nullable=True)


class PaymentEventRow(Base):
    """Webhook idempotency ledger: one row per provider event, unique."""

    __tablename__ = "payment_events"
    __table_args__ = (UniqueConstraint("provider", "provider_event_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(16))
    provider_event_id: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TasteCorpusRow(Base):
    """The moat: every delivered project's full trace + what the client chose."""

    __tablename__ = "taste_corpus"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    artifact_type_key: Mapped[str] = mapped_column(String(64))
    archetype: Mapped[str] = mapped_column(Text)
    aura: Mapped[dict] = mapped_column(JSON)
    directions: Mapped[list] = mapped_column(JSON, default=list)
    critiques: Mapped[list] = mapped_column(JSON, default=list)
    picked_candidate_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    editor_notes: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
