"""Repository: every DB access the engine/API needs, as plain async functions.
Keeps SQLAlchemy out of agents, graph, and worker logic."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aura.db.models import (
    ArtifactRow, InterruptRow, PaymentEventRow, Project, ProjectEventRow,
    TaskRow, TasteCorpusRow,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Repo:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        self._sm = sessionmaker

    # -- projects -----------------------------------------------------------

    async def create_project(self, *, project_id: str, request_text: str,
                             tier: str, budget_cap_usd: float,
                             user_id: str | None = None) -> Project:
        async with self._sm() as s, s.begin():
            row = Project(id=project_id, request_text=request_text, tier=tier,
                          budget_cap_usd=budget_cap_usd, user_id=user_id)
            s.add(row)
        return row

    async def get_project(self, project_id: str) -> Project | None:
        async with self._sm() as s:
            return await s.get(Project, project_id)

    async def update_project(self, project_id: str, **fields) -> None:
        async with self._sm() as s, s.begin():
            await s.execute(update(Project).where(Project.id == project_id)
                            .values(**fields, updated_at=_now()))

    async def list_projects(self, user_id: str | None = None, limit: int = 50) -> list[Project]:
        async with self._sm() as s:
            q = select(Project).order_by(Project.created_at.desc()).limit(limit)
            if user_id:
                q = q.where(Project.user_id == user_id)
            return list((await s.execute(q)).scalars())

    # -- events --------------------------------------------------------------

    async def append_event(self, *, project_id: str, type: str, payload: dict,
                           task_id: str | None = None,
                           role_key: str | None = None) -> int:
        async with self._sm() as s, s.begin():
            row = ProjectEventRow(project_id=project_id, type=type, payload=payload,
                                  task_id=task_id, role_key=role_key)
            s.add(row)
            await s.flush()
            return row.id

    async def events_after(self, project_id: str, after_id: int = 0,
                           limit: int = 1000) -> list[ProjectEventRow]:
        async with self._sm() as s:
            q = (select(ProjectEventRow)
                 .where(ProjectEventRow.project_id == project_id,
                        ProjectEventRow.id > after_id)
                 .order_by(ProjectEventRow.id).limit(limit))
            return list((await s.execute(q)).scalars())

    # -- tasks (UI projection) ------------------------------------------------

    async def upsert_task(self, *, project_id: str, task_id: str, **fields) -> None:
        async with self._sm() as s, s.begin():
            row = await s.get(TaskRow, (project_id, task_id))
            if row is None:
                row = TaskRow(project_id=project_id, task_id=task_id,
                              role_key=fields.pop("role_key", ""),
                              title=fields.pop("title", task_id))
                s.add(row)
            for k, v in fields.items():
                setattr(row, k, v)

    async def list_tasks(self, project_id: str) -> list[TaskRow]:
        async with self._sm() as s:
            q = select(TaskRow).where(TaskRow.project_id == project_id)
            return list((await s.execute(q)).scalars())

    # -- interrupts ------------------------------------------------------------

    async def create_interrupt(self, *, project_id: str, kind: str, payload: dict) -> str:
        async with self._sm() as s, s.begin():
            row = InterruptRow(project_id=project_id, kind=kind, payload=payload)
            s.add(row)
            await s.flush()
            return row.id

    async def pending_interrupt(self, project_id: str) -> InterruptRow | None:
        async with self._sm() as s:
            q = (select(InterruptRow)
                 .where(InterruptRow.project_id == project_id,
                        InterruptRow.resolved_at.is_(None))
                 .order_by(InterruptRow.created_at.desc()))
            return (await s.execute(q)).scalars().first()

    async def resolve_interrupt(self, interrupt_id: str, response: dict) -> None:
        async with self._sm() as s, s.begin():
            await s.execute(update(InterruptRow).where(InterruptRow.id == interrupt_id)
                            .values(response=response, resolved_at=_now()))

    # -- artifacts ---------------------------------------------------------------

    async def add_artifact(self, *, project_id: str, kind: str, storage_key: str,
                           mime: str, task_id: str | None = None,
                           candidate_id: str | None = None) -> str:
        async with self._sm() as s, s.begin():
            row = ArtifactRow(project_id=project_id, kind=kind, storage_key=storage_key,
                              mime=mime, task_id=task_id, candidate_id=candidate_id)
            s.add(row)
            await s.flush()
            return row.id

    async def get_artifact(self, artifact_id: str) -> ArtifactRow | None:
        async with self._sm() as s:
            return await s.get(ArtifactRow, artifact_id)

    async def list_artifacts(self, project_id: str) -> list[ArtifactRow]:
        async with self._sm() as s:
            q = select(ArtifactRow).where(ArtifactRow.project_id == project_id)
            return list((await s.execute(q)).scalars())

    # -- payments -------------------------------------------------------------------

    async def record_payment_event(self, *, provider: str, provider_event_id: str,
                                   payload: dict) -> bool:
        """Returns False when the webhook was already processed (idempotency)."""
        async with self._sm() as s:
            try:
                async with s.begin():
                    s.add(PaymentEventRow(provider=provider,
                                          provider_event_id=provider_event_id,
                                          payload=payload))
                return True
            except IntegrityError:
                return False

    # -- taste corpus ------------------------------------------------------------------

    async def record_taste(self, **fields) -> None:
        async with self._sm() as s, s.begin():
            s.add(TasteCorpusRow(**fields))

    async def set_picked_candidate(self, project_id: str, candidate_id: str) -> None:
        async with self._sm() as s, s.begin():
            await s.execute(update(TasteCorpusRow)
                            .where(TasteCorpusRow.project_id == project_id)
                            .values(picked_candidate_id=candidate_id))
