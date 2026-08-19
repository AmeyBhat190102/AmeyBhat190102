"""Role and schema registries.

ROLE_REGISTRY holds every specialist the producer can cast; SCHEMA_REGISTRY
maps output_schema_key -> pydantic model. Adding a specialist to the studio
is one `register_role` call in roles/library.py — no graph or executor change.
"""

from __future__ import annotations

from pydantic import BaseModel

from aura.planning.schemas import AgentRole

ROLE_REGISTRY: dict[str, AgentRole] = {}
SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {}

_loaded = False


def register_schema(key: str, model: type[BaseModel]) -> None:
    SCHEMA_REGISTRY[key] = model


def register_role(role: AgentRole) -> None:
    if role.output_schema_key not in SCHEMA_REGISTRY:
        raise ValueError(f"role {role.role_key!r} references unregistered schema "
                         f"{role.output_schema_key!r}")
    ROLE_REGISTRY[role.role_key] = role


def ensure_loaded() -> None:
    """Import the role library exactly once (import-time side registration)."""
    global _loaded
    if not _loaded:
        from aura.roles import library  # noqa: F401
        _loaded = True


def get_role(role_key: str) -> AgentRole:
    ensure_loaded()
    return ROLE_REGISTRY[role_key]


def get_schema(key: str) -> type[BaseModel]:
    ensure_loaded()
    return SCHEMA_REGISTRY[key]


def role_catalog() -> str:
    """Casting sheet shown to the producer: everything it may hire."""
    ensure_loaded()
    lines = []
    for r in ROLE_REGISTRY.values():
        fields = ", ".join(SCHEMA_REGISTRY[r.output_schema_key].model_fields)
        lines.append(
            f"- role_key: {r.role_key} — {r.display_name}\n"
            f"    purpose: {r.purpose}\n"
            f"    produces: {r.output_schema_key} ({fields})\n"
            f"    tools: {', '.join(r.allowed_tools)} · cost: {r.cost_class}"
        )
    return "\n".join(lines)
