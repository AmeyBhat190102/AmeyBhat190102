"""Planning contracts: how the producer casts a crew for each project.

The producer agent reads the brief + aura and emits a WorkPlan — a validated
task DAG over registered AgentRoles. The generic executor then spawns one
agent per task, in dependency order, in parallel where the DAG allows.
Everything an agent can be is data here; adding a new specialist to the
studio is a registry entry, never a graph change.
"""

from __future__ import annotations

import uuid
from graphlib import CycleError, TopologicalSorter
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from aura.schemas import ConceptDirection

ToolName = Literal["llm", "image_gen", "video_gen", "renderer"]


class AgentRole(BaseModel):
    """A castable specialist. system_prompt is a template with {brief},
    {aura}, {instructions} and {inputs} slots filled at spawn time."""

    role_key: str
    display_name: str
    purpose: str                                # shown to the producer when casting
    system_prompt: str
    output_schema_key: str                      # into roles.registry.SCHEMA_REGISTRY
    allowed_tools: list[ToolName] = Field(default_factory=lambda: ["llm"])
    cost_class: Literal["cheap", "standard", "expensive"] = "standard"
    default_timeout_s: int = 300
    uses_judge_model: bool = False              # critic/aura-class roles get the stronger model


class TaskNode(BaseModel):
    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    role_key: str
    title: str                                  # human-readable, shown in the theater
    instructions: str                           # the producer's task-specific brief
    depends_on: list[str] = Field(default_factory=list)
    # param name -> upstream task_id, or the reserved inputs "brief" / "aura"
    input_bindings: dict[str, str] = Field(default_factory=dict)
    criticality: Literal["required", "optional"] = "required"
    budget_usd: float = 0.5
    max_retries: int = 1
    # For design tasks (roles whose output is a renderable DesignSpec): the
    # creative territory this task explores. The producer IS the creative
    # director in the dynamic path — it stakes out directions when casting.
    direction: ConceptDirection | None = None


class WorkPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    rationale: str                              # why this crew, in one paragraph
    tasks: list[TaskNode] = Field(min_length=1)
    total_budget_usd: float = 5.0

    @model_validator(mode="after")
    def _validate_dag(self) -> "WorkPlan":
        ids = [t.task_id for t in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("task_ids must be unique")
        known = set(ids) | {"brief", "aura"}
        graph: dict[str, list[str]] = {}
        for t in self.tasks:
            for dep in t.depends_on:
                if dep not in set(ids):
                    raise ValueError(f"task {t.task_id!r} depends on unknown task {dep!r}")
            for binding in t.input_bindings.values():
                if binding not in known:
                    raise ValueError(
                        f"task {t.task_id!r} binds input to unknown source {binding!r}")
                if binding not in ("brief", "aura") and binding not in t.depends_on:
                    raise ValueError(
                        f"task {t.task_id!r} binds input to {binding!r} but does not "
                        f"declare it in depends_on")
            graph[t.task_id] = t.depends_on
        try:
            TopologicalSorter(graph).prepare()
        except CycleError as e:
            raise ValueError(f"plan contains a dependency cycle: {e}") from e
        if sum(t.budget_usd for t in self.tasks) > self.total_budget_usd * 1.01:
            raise ValueError("sum of task budgets exceeds total_budget_usd")
        return self

    def validate_against_registry(self, role_keys: set[str], max_tasks: int) -> None:
        """Registry/settings checks, applied after parse (kept out of the
        pydantic validator so the schema shown to the LLM stays portable)."""
        if len(self.tasks) > max_tasks:
            raise ValueError(f"plan has {len(self.tasks)} tasks; max is {max_tasks}")
        for t in self.tasks:
            if t.role_key not in role_keys:
                raise ValueError(f"task {t.task_id!r} casts unknown role {t.role_key!r}")

    def _task(self, task_id: str) -> TaskNode:
        return next(t for t in self.tasks if t.task_id == task_id)

    def ready_tasks(self, results: dict[str, "TaskResult"]) -> list[TaskNode]:
        """Unrun tasks whose dependencies are all terminal, with every
        *required* dependency succeeded. A failed optional dependency doesn't
        block its dependents — they run without that input."""
        out = []
        for t in self.tasks:
            if t.task_id in results:
                continue
            deps = [results.get(d) for d in t.depends_on]
            if all(deps) and all(
                    r.status == "succeeded" or self._task(r.task_id).criticality == "optional"
                    for r in deps):
                out.append(t)
        return out

    def doomed_tasks(self, results: dict[str, "TaskResult"]) -> list[TaskNode]:
        """Unrun tasks with a permanently failed *required* dependency."""
        dead = {tid for tid, r in results.items()
                if r.status in ("failed", "skipped", "budget_denied")
                and self._task(tid).criticality == "required"}
        return [t for t in self.tasks
                if t.task_id not in results and any(d in dead for d in t.depends_on)]


class TaskResult(BaseModel):
    task_id: str
    role_key: str
    status: Literal["succeeded", "failed", "skipped", "budget_denied"]
    output_schema_key: str = ""
    output: dict = Field(default_factory=dict)      # validated dump of the role's schema
    artifact_paths: list[str] = Field(default_factory=list)
    cost_usd: float = 0.0
    error: str | None = None
    attempts: int = 0


class RunBudget(BaseModel):
    cap_usd: float
    spent_usd: float = 0.0

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.cap_usd - self.spent_usd)

    @property
    def exhausted(self) -> bool:
        return self.spent_usd >= self.cap_usd
