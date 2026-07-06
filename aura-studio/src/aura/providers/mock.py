"""Offline providers for tests and keyless demos.

MockLLM serves hand-crafted fixtures for the pipeline's key models (so the
demo output reads like real studio work) and falls back to synthesizing any
other pydantic model from its JSON schema. MockImageGen/MockVideoGen emit
tiny valid PNG/MP4 stubs. The layout engine is real either way — mock mode
still renders an actual business card.
"""

from __future__ import annotations

import struct
import zlib
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_ADVOCATE_CARD_HTML = """<!doctype html><html><head><style>
  @page { margin: 0; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { width: 100%; height: 100vh; font-family: Georgia, 'Times New Roman', serif;
         background: #14100c; color: #e8ddc8; display: flex; }
  .card { margin: auto; text-align: center; padding: 6% 8%; width: 100%; }
  .rule { width: 38%; height: 1px; background: linear-gradient(90deg, transparent, #b08d4f, transparent);
          margin: 4.5% auto; }
  .name { font-size: 2.1em; letter-spacing: 0.14em; font-variant: small-caps; color: #f2ead6; }
  .title { font-size: 0.85em; letter-spacing: 0.34em; text-transform: uppercase; color: #b08d4f; margin-top: 2%; }
  .contact { font-size: 0.78em; letter-spacing: 0.08em; line-height: 1.9; color: #cbbfa4; }
</style></head><body><div class="card">
  <div class="title">Advocate · High Court</div>
  <div class="rule"></div>
  <div class="name">__NAME__</div>
  <div class="rule"></div>
  <div class="contact">__CONTACT__</div>
</div></body></html>"""


class MockLLM:
    """Returns fixtures keyed by output-model name; synthesizes anything else.
    Tests can override any fixture per-instance (e.g. to force a blocking
    clarifying question or a studio-tier flow)."""

    def __init__(self, overrides: dict[str, Any] | None = None) -> None:
        self.calls: list[str] = []
        self.overrides = overrides or {}

    async def structured(self, *, system: str, prompt: str, output_model: type[T],
                         images: list[str] | None = None) -> T:
        self.calls.append(output_model.__name__)
        fixture = self.overrides.get(output_model.__name__,
                                     _FIXTURES.get(output_model.__name__))
        if fixture is not None:
            data = fixture(prompt) if callable(fixture) else fixture
            return output_model.model_validate(data)
        return output_model.model_validate(_synthesize(output_model.model_json_schema()))


def _synthesize(schema: dict, defs: dict | None = None) -> Any:
    defs = defs or schema.get("$defs", {})
    if "$ref" in schema:
        return _synthesize(defs[schema["$ref"].split("/")[-1]], defs)
    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema:
            options = [s for s in schema[key] if s.get("type") != "null"] or schema[key]
            return _synthesize(options[0], defs)
    if "enum" in schema:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    t = schema.get("type")
    if t == "object":
        required = set(schema.get("required", []))
        return {k: _synthesize(v, defs) for k, v in schema.get("properties", {}).items()
                if k in required}
    if t == "array":
        return [_synthesize(schema.get("items", {"type": "string"}), defs)]
    if t == "string":
        return "mock"
    if t in ("number", "integer"):
        return max(schema.get("minimum", 1), 1)
    if t == "boolean":
        return True
    return "mock"


def _mock_png() -> bytes:
    """Minimal valid 1x1 PNG."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(
            ">I", zlib.crc32(tag + data))
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xb0\x8d\x4f")
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", idat) + chunk(b"IEND", b""))


class MockImageGen:
    async def generate(self, *, prompt: str, negative_prompt: str = "",
                       width: int = 1024, height: int = 1024,
                       reference_image: str | None = None) -> bytes:
        return _mock_png()


class MockVideoGen:
    async def generate(self, *, prompt: str, source_image: str | None,
                       duration_s: float, width: int, height: int) -> bytes:
        return b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"  # stub mp4 header


# ---------------------------------------------------------------------------
# Fixtures — realistic outputs for the advocate-business-card demo
# ---------------------------------------------------------------------------

_DIRECTION_NAMES = [
    ("Counsel in Ink", "Quiet authority: letterpress restraint, ivory and iron-gall black.", "safe"),
    ("The Gold Standard", "Earned gravitas: deep charcoal field, hairline gold rules, small caps.", "balanced"),
    ("Brief & Verdict", "Editorial modernism: strict grid, oversized initials, single crimson accent.", "balanced"),
    ("Chambers", "Old-world texture: engraved motif of a pillared portico, cream stock.", "balanced"),
    ("Statute Modern", "Bold subversion: swiss type on legal-pad yellow, for the fearless litigator.", "bold"),
]


def _brief_fixture(prompt: str) -> dict:
    return {
        "artifact_type_key": "business_card",
        "subject_name": "Adv. R. K. Sharma",
        "subject_description": "Senior advocate, 20 years in constitutional law; measured, precise, quietly formidable.",
        "audience": "Judges, senior counsel, high-value clients.",
        "hard_facts": {"name": "Adv. R. K. Sharma", "title": "Advocate, High Court",
                       "phone": "+91 98765 43210", "email": "rks@chambers.law"},
        "stated_preferences": ["understated", "premium"],
        "constraints": ["standard card size", "print-ready"],
        "assets": [],
        "open_questions": [],
    }


_FIXTURES: dict[str, Any] = {
    "DesignBrief": _brief_fixture,
    "AuraProfile": {
        "archetype": "The Sage-Advocate: quiet authority earned in court, not announced.",
        "essence_statement": "Two decades of constitutional practice compressed into stillness. "
                             "The card should feel like his handshake: brief, firm, remembered.",
        "adjectives": ["measured", "precise", "formidable", "traditional", "unhurried"],
        "cultural_context": "Indian High Court bar; British-inherited legal formality, honored not mimicked.",
        "status_signals": ["restraint over ornament", "material quality over decoration", "small caps, wide tracking"],
        "typography": {
            "voice": "authoritative transitional serif with humanist warmth",
            "primary_family_suggestions": ["Baskerville", "Freight Text"],
            "secondary_family_suggestions": ["Trade Gothic", "Founders Grotesk"],
            "case_and_tracking": "small caps with +120 tracking for the name line",
        },
        "palette": {
            "mood": "iron-gall ink and aged brass: permanence, verdicts that stand",
            "primary_hex": ["#14100c", "#e8ddc8"],
            "accent_hex": ["#b08d4f"],
            "forbidden": ["neon", "gradients that read digital"],
        },
        "materials_and_finishes": ["600gsm cotton stock", "letterpress", "gold foil edge"],
        "motifs": ["hairline double rule", "pillared portico mark"],
        "composition_notes": "Symmetric, generous margins; the whitespace *is* the status signal.",
        "anti_patterns": ["clip-art scales of justice", "crowded contact block", "drop shadows"],
        "photography_light": "single warm key, deep falloff",
    },
    "DirectionsBatch": {
        "directions": [
            {"name": n, "thesis": t,
             "how_it_expresses_aura": "Translates restraint-as-status into form.",
             "differentiator": f"Distinct territory #{i + 1}: {n.lower()} register.",
             "risk_level": r}
            for i, (n, t, r) in enumerate(_DIRECTION_NAMES)
        ]
    },
    "LayoutSpec": {
        "spec_kind": "layout",
        "html": _ADVOCATE_CARD_HTML
        .replace("__NAME__", "Adv. R. K. Sharma")
        .replace("__CONTACT__", "High Court Chambers · +91 98765 43210 · rks@chambers.law"),
        "background_image_prompt": None,
        "pages": 1,
    },
    "Critique": lambda prompt: {
        "candidate_id": _extract(prompt, "candidate_id") or "unknown",
        "scores": [
            {"criterion": "aura_fidelity", "score": 8.6, "note": "Restraint reads as intended."},
            {"criterion": "craft", "score": 8.2, "note": "Tracking and rules are disciplined."},
            {"criterion": "legibility", "score": 9.0, "note": "Contact block clean at print size."},
            {"criterion": "print_safety", "score": 9.0, "note": "Inside safe margins."},
            {"criterion": "distinctiveness", "score": 7.8, "note": "Confident but familiar territory."},
        ],
        "overall": 8.5,
        "verdict": "ship",
        "revision_notes": [],
    },
    "RationaleCard": lambda prompt: {
        "candidate_id": _extract(prompt, "candidate_id") or "unknown",
        "headline": "Authority that doesn't raise its voice",
        "body": "The card mirrors how you practice: spare, exact, final. Gold appears once — "
                "like a citation that ends the argument.",
    },
}


def _extract(prompt: str, key: str) -> str | None:
    for line in prompt.splitlines():
        if key in line and ":" in line:
            return line.split(":", 1)[1].strip().strip('",')
    return None


# --- dynamic-planning fixtures ---------------------------------------------

def _direction(i: int, name: str, thesis: str, risk: str) -> dict:
    return {"name": name, "thesis": thesis,
            "how_it_expresses_aura": "Translates restraint-as-status into form.",
            "differentiator": f"Territory #{i}: {name.lower()} register.",
            "risk_level": risk}


_FIXTURES["WorkPlan"] = {
    "rationale": "Typography carries this artifact; cast a type specialist and a "
                 "motif illustrator first, then four distinct design territories.",
    "tasks": [
        {"task_id": "type1", "role_key": "calligraphy_specialist",
         "title": "Type system", "instructions": "Design the exact typographic system.",
         "budget_usd": 0.1},
        {"task_id": "motif1", "role_key": "motif_illustrator",
         "title": "Signature motifs", "instructions": "Two motifs owned by this subject.",
         "budget_usd": 0.3, "criticality": "optional"},
        *[
            {"task_id": f"design{i}", "role_key": "layout_designer",
             "title": f"Design: {name}",
             "instructions": f"Design the artifact in this territory: {thesis}",
             "depends_on": ["type1", "motif1"],
             "input_bindings": {"type_plan": "type1", "motifs": "motif1"},
             "budget_usd": 0.5,
             "direction": _direction(i, name, thesis, risk)}
            for i, (name, thesis, risk) in enumerate([
                ("Counsel in Ink", "Quiet authority: letterpress restraint.", "safe"),
                ("The Gold Standard", "Earned gravitas: charcoal and hairline gold.", "balanced"),
                ("Brief & Verdict", "Editorial modernism on a strict grid.", "balanced"),
                ("Statute Modern", "Bold subversion: swiss type, fearless.", "bold"),
            ], start=1)
        ],
    ],
    "total_budget_usd": 5.0,
}

_FIXTURES["TypographyPlan"] = {
    "pairing": {"display_family": "Cormorant Garamond", "body_family": "Inter",
                "rationale": "Transitional gravitas over neutral clarity."},
    "name_treatment": "small caps, +120 tracking, 2.1em",
    "hierarchy": ["name 2.1em small caps", "title 0.85em uppercase +340 tracking",
                  "contact 0.78em sentence case"],
    "flourishes": "hairline gradient rules only; no swashes.",
}

_FIXTURES["MotifSet"] = {
    "motifs": [
        {"name": "Pillared portico", "meaning": "The court itself: permanence, shelter of law.",
         "image_prompt": "minimal engraving of a classical courthouse portico, flat, "
                         "single ink color, solid ivory background, no text",
         "placement_hint": "reverse side, centered"},
        {"name": "Double rule", "meaning": "The line under a verdict.",
         "image_prompt": "two thin horizontal gold lines, flat, solid dark background, no text",
         "placement_hint": "under the name"},
    ],
    "style_note": "single-hand engraving style, restrained",
}

_FIXTURES["CopyDeck"] = {
    "language": "en",
    "blocks": [{"slot": "tagline", "text": "Counsel. Considered.", "tone_note": "spare"}],
    "pronunciation_or_transliteration_notes": "",
}
