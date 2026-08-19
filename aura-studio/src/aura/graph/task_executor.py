"""Executes one WorkPlan task: spawn the role's agent, feed it its bound
inputs, validate its output, render it if it's a design spec, meter every
tool call, and never let an exception escape — a dead specialist becomes a
failed TaskResult, not a dead project."""

from __future__ import annotations

import asyncio
import json

from aura.config import Providers, Settings
from aura.events import ProjectEvent, emit
from aura.planning.schemas import RunBudget, TaskNode, TaskResult
from aura.providers.metering import ToolBelt
from aura.render.executor import render_candidate
from aura.roles.outputs import LogoConcept, MotifSet
from aura.roles.registry import get_role, get_schema
from aura.schemas import (
    ARTIFACT_TYPES, AuraProfile, Candidate, ConceptDirection, DesignBrief,
    ImagePromptSpec, LayoutSpec, VideoShotListSpec,
)
from aura.storage import ArtifactStore

_MAX_INPUT_CHARS = 6000  # per bound upstream output, to keep prompts sane


async def execute_task(providers: Providers, settings: Settings, store: ArtifactStore, *,
                       project_id: str, task: TaskNode, brief: DesignBrief,
                       aura: AuraProfile, upstream: dict[str, TaskResult],
                       budget: RunBudget) -> tuple[TaskResult, Candidate | None]:
    role = get_role(task.role_key)
    emit(ProjectEvent(project_id=project_id, type="task_started", task_id=task.task_id,
                      role_key=role.role_key,
                      payload={"title": task.title, "display_name": role.display_name}))

    def on_spend(amount: float, tool: str) -> None:
        emit(ProjectEvent(project_id=project_id, type="budget_update", task_id=task.task_id,
                          payload={"tool": tool, "amount_usd": amount,
                                   "spent_usd": round(budget.spent_usd, 4)}))

    belt = ToolBelt(providers, role, budget, on_spend=on_spend)
    result = TaskResult(task_id=task.task_id, role_key=role.role_key, status="failed")
    candidate: Candidate | None = None

    for attempt in range(task.max_retries + 1):
        result.attempts = attempt + 1
        spent_before = budget.spent_usd
        try:
            async with asyncio.timeout(role.default_timeout_s):
                output, candidate = await _run_role(
                    belt, providers, settings, store, project_id=project_id, task=task,
                    brief=brief, aura=aura, upstream=upstream)
            result.status = "succeeded"
            result.output_schema_key = role.output_schema_key
            result.output = output
            result.error = None
            if candidate:
                result.artifact_paths = [*candidate.preview_paths,
                                         *([candidate.print_pdf_path]
                                           if candidate.print_pdf_path else [])]
            elif "_artifact_paths" in output:
                result.artifact_paths = output["_artifact_paths"]
            break
        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"
        finally:
            result.cost_usd = round(result.cost_usd + (budget.spent_usd - spent_before), 4)

    emit(ProjectEvent(project_id=project_id, type="task_finished", task_id=task.task_id,
                      role_key=role.role_key,
                      payload={"status": result.status, "cost_usd": result.cost_usd,
                               "error": result.error}))
    return result, candidate


async def _run_role(belt: ToolBelt, providers: Providers, settings: Settings,
                    store: ArtifactStore, *, project_id: str, task: TaskNode,
                    brief: DesignBrief, aura: AuraProfile,
                    upstream: dict[str, TaskResult]) -> tuple[dict, Candidate | None]:
    role = get_role(task.role_key)
    artifact = ARTIFACT_TYPES[brief.artifact_type_key]

    inputs_text, substitutions = _resolve_inputs(task, upstream)
    system = (role.system_prompt
              .replace("{artifact}", artifact.model_dump_json())
              .replace("{instructions}", task.instructions)
              .replace("{inputs}", inputs_text))
    prompt = ("CLIENT BRIEF:\n" + brief.model_dump_json(indent=2, exclude={"assets"})
              + "\n\nASSETS:\n" + "\n".join(
                  f"- {a.asset_id} [{a.kind}]: {a.description}" for a in brief.assets)
              + "\n\nAURA PROFILE:\n" + aura.model_dump_json(indent=2))
    if task.direction:
        prompt += "\n\nYOUR DIRECTION:\n" + task.direction.model_dump_json(indent=2)

    output_model = get_schema(role.output_schema_key)
    output = await belt.llm.structured(system=system, prompt=prompt,
                                       output_model=output_model)

    # Design specs render immediately — the theater gets its thumbnail.
    if isinstance(output, (LayoutSpec, ImagePromptSpec, VideoShotListSpec)):
        direction = task.direction or ConceptDirection(
            name=task.title, thesis=task.instructions,
            how_it_expresses_aura="Producer-cast task.", differentiator=task.task_id)
        candidate = await render_candidate(
            belt.metered_providers(), store, brief=brief, direction=direction,
            spec=output, asset_substitutions=substitutions,
            on_artifact=lambda kind, path: emit(ProjectEvent(
                project_id=project_id, type="artifact_ready", task_id=task.task_id,
                role_key=role.role_key,
                payload={"kind": kind, "path": path, "direction": direction.name})))
        return output.model_dump(), candidate

    # Asset-producing roles: render their prompts into files now.
    if isinstance(output, MotifSet):
        paths = []
        for i, motif in enumerate(output.motifs):
            png = await belt.image_gen.generate(prompt=motif.image_prompt,
                                                width=1024, height=1024)
            path = store.save(project_id, f"{task.task_id}-motif{i}.png", png)
            paths.append(path)
            emit(ProjectEvent(project_id=project_id, type="artifact_ready",
                              task_id=task.task_id, role_key=role.role_key,
                              payload={"kind": "motif", "path": path, "name": motif.name}))
        return {**output.model_dump(), "_artifact_paths": paths}, None

    if isinstance(output, LogoConcept):
        png = await belt.image_gen.generate(prompt=output.image_prompt,
                                            width=1024, height=1024)
        path = store.save(project_id, f"{task.task_id}-logo.png", png)
        emit(ProjectEvent(project_id=project_id, type="artifact_ready",
                          task_id=task.task_id, role_key=role.role_key,
                          payload={"kind": "logo", "path": path}))
        return {**output.model_dump(), "_artifact_paths": [path]}, None

    return output.model_dump(), None


def _resolve_inputs(task: TaskNode,
                    upstream: dict[str, TaskResult]) -> tuple[str, dict[str, str]]:
    """Format bound upstream outputs for the prompt, and collect placeholder
    substitutions (__MOTIF_n__, __LOGO__) for rendered upstream assets."""
    sections: list[str] = []
    substitutions: dict[str, str] = {}
    for name, source in task.input_bindings.items():
        if source in ("brief", "aura"):
            continue  # always in the prompt already
        dep = upstream.get(source)
        if dep is None or dep.status != "succeeded":
            sections.append(f"[{name}] — unavailable (upstream task {source} "
                            f"{dep.status if dep else 'missing'}); proceed without it.")
            continue
        body = json.dumps({k: v for k, v in dep.output.items()
                           if not k.startswith("_")}, indent=1)
        sections.append(f"[{name}] (from {dep.role_key}):\n{body[:_MAX_INPUT_CHARS]}")
        if dep.output_schema_key == "MotifSet":
            for i, path in enumerate(dep.artifact_paths):
                substitutions[f"__MOTIF_{i}__"] = path
            sections.append("Motif assets available as tokens: "
                            + ", ".join(f"__MOTIF_{i}__ ({m['name']})"
                                        for i, m in enumerate(dep.output.get("motifs", []))
                                        if i < len(dep.artifact_paths)))
        elif dep.output_schema_key == "LogoConcept" and dep.artifact_paths:
            substitutions["__LOGO__"] = dep.artifact_paths[0]
            sections.append("Logo asset available as token: __LOGO__")
    text = ("YOUR INPUTS FROM THE CREW:\n" + "\n\n".join(sections)) if sections else ""
    return text, substitutions
