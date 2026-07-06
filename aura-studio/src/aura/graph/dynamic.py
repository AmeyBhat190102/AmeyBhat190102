"""The dynamic studio: a producer casts a crew per project; a generic
executor spawns those agents in dependency order.

    intake → clarify(⏸ if blocking questions) → extract_aura → produce_plan
       → schedule ⇄ Send("execute_task" × ready) → review ⇄ revise
       → studio_gate(⏸ Studio tier) → curate → END

⏸ = LangGraph interrupt(): the run checkpoints and parks until the client
answers / the editor approves, surviving restarts. Send payloads carry
pydantic models (checkpoint-serializable); a crash mid-wave resumes with
completed tasks intact.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt

from aura.agents.aura_extractor import extract_aura
from aura.agents.concept_designer import design_concept
from aura.agents.critic import critique
from aura.agents.curator import curate
from aura.agents.intake import run_intake
from aura.agents.producer import produce_plan
from aura.config import Providers, Settings
from aura.events import ProjectEvent, emit
from aura.graph.task_executor import execute_task
from aura.planning.schemas import RunBudget, TaskNode, TaskResult, WorkPlan
from aura.render.executor import render_candidate
from aura.schemas import (
    AuraProfile, Candidate, ClarifyRequest, ClarifyResponse, Critique,
    DeliverablePackage, DesignBrief, InputAsset, ReviewRequest, ReviewResponse,
)


def _merge_dicts(left: dict, right: dict) -> dict:
    return {**left, **right}


def _last_int(left: int, right: int) -> int:
    return right


class DynamicState(TypedDict, total=False):
    project_id: str
    tier: str                                   # preview | standard | studio
    budget_cap_usd: float
    request_text: str
    assets: list[InputAsset]
    brief: DesignBrief
    aura: AuraProfile
    plan: WorkPlan
    task_results: Annotated[dict[str, TaskResult], _merge_dicts]
    candidates: Annotated[dict[str, Candidate], _merge_dicts]   # direction_id -> latest
    critiques: Annotated[dict[str, Critique], _merge_dicts]     # candidate_id -> critique
    studio_decisions: list[dict]
    studio_rounds: Annotated[int, _last_int]
    package: DeliverablePackage


def _spent(state: DynamicState) -> float:
    return round(sum(r.cost_usd for r in state.get("task_results", {}).values()), 4)


def build_dynamic_graph(providers: Providers, settings: Settings, store,
                        checkpointer=None):
    async def intake_node(state: DynamicState) -> dict:
        if state.get("brief"):
            return {}
        brief = await run_intake(providers.llm, request_text=state["request_text"],
                                 assets=state.get("assets", []))
        brief.project_id = state["project_id"]
        emit(ProjectEvent(project_id=state["project_id"], type="brief_ready",
                          payload={"artifact_type": brief.artifact_type_key,
                                   "subject": brief.subject_name,
                                   "open_questions": len(brief.open_questions)}))
        return {"brief": brief}

    async def clarify_node(state: DynamicState) -> dict:
        brief = state["brief"]
        blocking = [q for q in brief.open_questions if q.blocking]
        if not blocking:
            return {}
        emit(ProjectEvent(project_id=state["project_id"], type="interrupt_raised",
                          payload={"kind": "clarify",
                                   "questions": [q.question for q in blocking]}))
        raw = interrupt(ClarifyRequest(project_id=state["project_id"],
                                       questions=blocking).model_dump(mode="json"))
        resp = ClarifyResponse.model_validate(raw)
        emit(ProjectEvent(project_id=state["project_id"], type="interrupt_resolved",
                          payload={"kind": "clarify",
                                   "accepted_defaults": resp.accept_defaults}))
        if resp.answers:
            brief.stated_preferences = brief.stated_preferences + [
                f"(client answer) {q}: {a}" for q, a in resp.answers.items()]
        for q in brief.open_questions:
            q.blocking = False          # never re-raise on resume/replay
        return {"brief": brief}

    async def aura_node(state: DynamicState) -> dict:
        aura = await extract_aura(providers.judge, state["brief"])
        emit(ProjectEvent(project_id=state["project_id"], type="aura_ready",
                          payload={"archetype": aura.archetype,
                                   "adjectives": aura.adjectives,
                                   "palette": aura.palette.primary_hex}))
        return {"aura": aura}

    async def plan_node(state: DynamicState) -> dict:
        plan = await produce_plan(providers.llm, brief=state["brief"],
                                  aura=state["aura"], settings=settings,
                                  budget_usd=state.get("budget_cap_usd",
                                                       settings.project_budget_usd))
        emit(ProjectEvent(project_id=state["project_id"], type="plan_created",
                          payload={"rationale": plan.rationale,
                                   "tasks": [{"task_id": t.task_id, "role_key": t.role_key,
                                              "title": t.title, "depends_on": t.depends_on,
                                              "criticality": t.criticality}
                                             for t in plan.tasks]}))
        return {"plan": plan}

    async def schedule_node(state: DynamicState) -> dict:
        """Bookkeeping between waves: mark doomed and over-budget tasks so the
        DAG always makes progress. Dispatch happens in the router below."""
        plan, results = state["plan"], state.get("task_results", {})
        updates: dict[str, TaskResult] = {}
        for t in plan.doomed_tasks(results):
            updates[t.task_id] = TaskResult(task_id=t.task_id, role_key=t.role_key,
                                            status="skipped",
                                            error="required upstream task failed")
        budget = RunBudget(cap_usd=state.get("budget_cap_usd", settings.project_budget_usd),
                           spent_usd=_spent(state))
        if budget.exhausted:
            merged = {**results, **updates}
            for t in plan.ready_tasks(merged):
                updates[t.task_id] = TaskResult(task_id=t.task_id, role_key=t.role_key,
                                                status="budget_denied",
                                                error="project budget exhausted")
        for r in updates.values():
            emit(ProjectEvent(project_id=state["project_id"], type="task_finished",
                              task_id=r.task_id, role_key=r.role_key,
                              payload={"status": r.status, "cost_usd": 0.0,
                                       "error": r.error}))
        return {"task_results": updates} if updates else {}

    def dispatch(state: DynamicState):
        plan, results = state["plan"], state.get("task_results", {})
        ready = plan.ready_tasks(results)
        if ready:
            return [Send("execute_task", {"task": t, "state_slice": {
                        "project_id": state["project_id"],
                        "brief": state["brief"], "aura": state["aura"],
                        "budget_cap_usd": state.get("budget_cap_usd",
                                                    settings.project_budget_usd),
                        "spent_usd": _spent(state),
                        "upstream": {d: results[d] for d in t.depends_on if d in results},
                    }}) for t in ready]
        if len(results) < len(plan.tasks):
            return "schedule"           # doomed/budget marking still to converge
        return "review"

    async def execute_task_node(payload: dict) -> dict:
        task: TaskNode = payload["task"]
        s = payload["state_slice"]
        budget = RunBudget(cap_usd=s["budget_cap_usd"], spent_usd=s["spent_usd"])
        result, candidate = await execute_task(
            providers, settings, store, project_id=s["project_id"], task=task,
            brief=s["brief"], aura=s["aura"], upstream=s["upstream"], budget=budget)
        out: dict = {"task_results": {task.task_id: result}}
        if candidate is not None:
            out["candidates"] = {candidate.direction.direction_id: candidate}
        return out

    async def review_node(state: DynamicState) -> dict:
        pending = [c for c in state.get("candidates", {}).values()
                   if c.candidate_id not in state.get("critiques", {})]
        results = await asyncio.gather(*[
            critique(providers.judge, brief=state["brief"], aura=state["aura"],
                     candidate=c, threshold=settings.ship_threshold)
            for c in pending
        ])
        for r in results:
            emit(ProjectEvent(project_id=state["project_id"], type="critique",
                              payload={"candidate_id": r.candidate_id,
                                       "overall": r.overall, "verdict": r.verdict,
                                       "notes": r.revision_notes}))
        return {"critiques": {r.candidate_id: r for r in results}} if results else {}

    def route_after_review(state: DynamicState):
        sends = []
        for candidate in state.get("candidates", {}).values():
            verdict = state["critiques"].get(candidate.candidate_id)
            if (verdict and verdict.verdict == "revise"
                    and candidate.revision < settings.max_revisions):
                sends.append(Send("revise", {"candidate": candidate,
                                             "notes": verdict.revision_notes,
                                             "project_id": state["project_id"],
                                             "brief": state["brief"],
                                             "aura": state["aura"]}))
        return sends or "studio_gate"

    async def revise_node(payload: dict) -> dict:
        old: Candidate = payload["candidate"]
        emit(ProjectEvent(project_id=payload["project_id"], type="revision_started",
                          payload={"candidate_id": old.candidate_id,
                                   "direction": old.direction.name,
                                   "notes": payload["notes"]}))
        spec = await design_concept(
            providers.llm, brief=payload["brief"], aura=payload["aura"],
            direction=old.direction, revision_notes=payload["notes"],
            previous_spec=old.spec)
        candidate = await render_candidate(
            providers, store, brief=payload["brief"], direction=old.direction,
            spec=spec, revision=old.revision + 1,
            on_artifact=lambda kind, path: emit(ProjectEvent(
                project_id=payload["project_id"], type="artifact_ready",
                payload={"kind": kind, "path": path,
                         "direction": old.direction.name, "revision": old.revision + 1})))
        return {"candidates": {old.direction.direction_id: candidate}}

    async def studio_gate_node(state: DynamicState) -> dict:
        if state.get("tier") != "studio" or state.get("studio_rounds", 0) >= 3:
            return {"studio_decisions": []}
        live = [c for c in state["candidates"].values()
                if state["critiques"].get(c.candidate_id,
                                          Critique(candidate_id="", scores=[], overall=5,
                                                   verdict="ship")).verdict != "kill"]
        request = ReviewRequest(
            project_id=state["project_id"],
            candidate_ids=[c.candidate_id for c in live],
            preview_paths={c.candidate_id: c.preview_paths for c in live})
        emit(ProjectEvent(project_id=state["project_id"], type="interrupt_raised",
                          payload={"kind": "studio_review",
                                   "candidate_ids": request.candidate_ids}))
        raw = interrupt(request.model_dump(mode="json"))
        resp = ReviewResponse.model_validate(raw)
        emit(ProjectEvent(project_id=state["project_id"], type="interrupt_resolved",
                          payload={"kind": "studio_review",
                                   "decisions": [d.model_dump() for d in resp.decisions]}))
        critique_updates: dict[str, Critique] = {}
        by_id = {c.candidate_id: c for c in state["candidates"].values()}
        for d in resp.decisions:
            if d.candidate_id not in by_id:
                continue
            base = state["critiques"].get(d.candidate_id)
            if d.action == "reject":
                critique_updates[d.candidate_id] = base.model_copy(
                    update={"verdict": "kill"}) if base else Critique(
                    candidate_id=d.candidate_id, scores=[], overall=0, verdict="kill")
            elif d.action == "revise":
                notes = [d.notes] if d.notes else ["Editor requested another pass."]
                critique_updates[d.candidate_id] = base.model_copy(
                    update={"verdict": "revise", "revision_notes": notes}) if base else \
                    Critique(candidate_id=d.candidate_id, scores=[], overall=6,
                             verdict="revise", revision_notes=notes)
        return {"critiques": critique_updates,
                "studio_decisions": [d.model_dump() for d in resp.decisions],
                "studio_rounds": state.get("studio_rounds", 0) + 1}

    def route_after_studio(state: DynamicState):
        sends = []
        by_id = {c.candidate_id: c for c in state["candidates"].values()}
        for d in state.get("studio_decisions", []):
            if d.get("action") == "revise" and d["candidate_id"] in by_id:
                old = by_id[d["candidate_id"]]
                sends.append(Send("revise", {"candidate": old,
                                             "notes": [d.get("notes") or
                                                       "Editor requested another pass."],
                                             "project_id": state["project_id"],
                                             "brief": state["brief"],
                                             "aura": state["aura"]}))
        return sends or "curate"

    async def curate_node(state: DynamicState) -> dict:
        package = await curate(
            providers.llm, brief=state["brief"], aura=state["aura"],
            candidates=list(state.get("candidates", {}).values()),
            critiques=state.get("critiques", {}), final_count=settings.final_count)
        emit(ProjectEvent(project_id=state["project_id"], type="package_ready",
                          payload={"selected": len(package.selected),
                                   "rejected": package.rejected_count,
                                   "spent_usd": _spent(state)}))
        return {"package": package}

    g = StateGraph(DynamicState)
    g.add_node("intake", intake_node)
    g.add_node("clarify", clarify_node)
    g.add_node("extract_aura", aura_node)
    g.add_node("produce_plan", plan_node)
    g.add_node("schedule", schedule_node)
    g.add_node("execute_task", execute_task_node)
    g.add_node("review", review_node)
    g.add_node("revise", revise_node)
    g.add_node("studio_gate", studio_gate_node)
    g.add_node("curate", curate_node)

    g.add_edge(START, "intake")
    g.add_edge("intake", "clarify")
    g.add_edge("clarify", "extract_aura")
    g.add_edge("extract_aura", "produce_plan")
    g.add_edge("produce_plan", "schedule")
    g.add_conditional_edges("schedule", dispatch, ["execute_task", "schedule", "review"])
    g.add_edge("execute_task", "schedule")
    g.add_conditional_edges("review", route_after_review, ["revise", "studio_gate"])
    g.add_conditional_edges("studio_gate", route_after_studio, ["revise", "curate"])
    g.add_edge("revise", "review")
    g.add_edge("curate", END)
    return g.compile(checkpointer=checkpointer)
