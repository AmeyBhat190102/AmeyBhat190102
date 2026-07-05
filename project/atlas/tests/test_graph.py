"""Offline smoke tests: no network, no real API key needed.

- graph wiring compiles and contains the expected topology
- reducers behave as designed
- data-layer tools return correct shapes
- supervisor loop-guard falls back to `respond` for already-visited workers
"""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")

import pytest
from langchain_core.messages import HumanMessage

from atlas import data
from atlas.agents.supervisor import RouteDecision, make_supervisor_node
from atlas.graph import build_graph
from atlas.state import merge_dicts
from atlas.tools.support_tools import check_refund_eligibility, lookup_order


# --------------------------------------------------------------------------- #
# Graph wiring
# --------------------------------------------------------------------------- #

def test_graph_compiles_with_expected_nodes():
    graph, research_graph = build_graph()
    nodes = set(graph.get_graph().nodes)
    assert {"load_memory", "supervisor", "support", "analyst", "researcher", "respond"} <= nodes

    research_nodes = set(research_graph.get_graph().nodes)
    assert {"plan", "research_subtopic", "synthesize"} <= research_nodes


def test_graph_renders_mermaid():
    graph, _ = build_graph()
    mermaid = graph.get_graph().draw_mermaid()
    assert "supervisor" in mermaid and "researcher" in mermaid


# --------------------------------------------------------------------------- #
# State & reducers
# --------------------------------------------------------------------------- #

def test_merge_dicts_reducer_merges_not_overwrites():
    left = {"customer_id": "cus_001", "preferences": ["a"]}
    right = {"order": {"id": "ord_1001"}}
    merged = merge_dicts(left, right)
    assert merged == {"customer_id": "cus_001", "preferences": ["a"], "order": {"id": "ord_1001"}}
    assert merge_dicts(None, {"x": 1}) == {"x": 1}


# --------------------------------------------------------------------------- #
# Tools / data layer
# --------------------------------------------------------------------------- #

def test_lookup_order_found_and_missing():
    found = lookup_order.invoke({"order_id": "ord_1001"})
    assert "Nimbus X1" in found
    missing = lookup_order.invoke({"order_id": "ord_9999"})
    assert "No order found" in missing


def test_refund_eligibility_requires_delivery():
    in_transit = check_refund_eligibility.invoke({"order_id": "ord_1002"})
    assert "not delivered" in in_transit.lower()


def test_kb_search_ranks_relevant_docs():
    hits = data.search_kb("nimbus battery drain firmware")
    assert hits and hits[0]["id"] == "kb_01"


# --------------------------------------------------------------------------- #
# Supervisor routing guard (no LLM call — stubbed router)
# --------------------------------------------------------------------------- #

class _StubRouter:
    def __init__(self, decision: RouteDecision):
        self._decision = decision

    def invoke(self, _messages):
        return self._decision


class _StubModel:
    def __init__(self, decision: RouteDecision):
        self._decision = decision

    def with_structured_output(self, _schema):
        return _StubRouter(self._decision)


def test_supervisor_never_revisits_a_worker():
    decision = RouteDecision(next_agent="support", reason="stub")
    supervisor = make_supervisor_node(_StubModel(decision))

    state = {
        "messages": [HumanMessage(content="refund please")],
        "visited": ["support"],  # support already ran this turn
    }
    command = supervisor(state)
    assert command.goto == "respond"


def test_supervisor_routes_fresh_worker():
    decision = RouteDecision(next_agent="analyst", reason="stub")
    supervisor = make_supervisor_node(_StubModel(decision))

    command = supervisor({"messages": [HumanMessage(content="spend?")], "visited": []})
    assert command.goto == "analyst"
    assert command.update["routing_reason"] == "stub"


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
