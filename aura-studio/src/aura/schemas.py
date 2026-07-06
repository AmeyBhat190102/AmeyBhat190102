"""Core data contracts shared by every agent in the pipeline.

The pipeline is a series of typed transformations:

    raw multimodal input
        -> DesignBrief          (intake agent)
        -> AuraProfile          (aura extraction agent)
        -> [ConceptDirection]   (creative director, dynamic fan-out)
        -> [DesignSpec]         (concept designer agents, parallel)
        -> [Candidate]          (render layer)
        -> [Critique]           (critic agent, revision loop)
        -> DeliverablePackage   (curator)

Keeping these as strict pydantic models is what makes the system reliable:
every LLM call is forced into structured output and validated at the seam.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Artifact taxonomy
# ---------------------------------------------------------------------------

class ArtifactClass(str, Enum):
    """How an artifact gets *made* — the render route.

    New artifact types (menus, album art, packaging...) map onto one of these
    routes; adding a type is registry data, not new code.
    """

    TYPOGRAPHIC_PRINT = "typographic_print"   # business cards, wedding invites, letterheads
    ILLUSTRATED_FLAT = "illustrated_flat"     # book covers, posters, album art
    MOTION = "motion"                         # product shoot videos, animated idents


class ArtifactType(BaseModel):
    """A concrete deliverable kind, with its physical/production constraints."""

    key: str                                  # e.g. "business_card"
    display_name: str
    artifact_class: ArtifactClass
    # Physical specs for print artifacts (mm); pixel specs for digital ones.
    width_mm: float | None = None
    height_mm: float | None = None
    bleed_mm: float = 3.0
    width_px: int | None = None
    height_px: int | None = None
    duration_s: float | None = None           # motion artifacts
    notes: str = ""


ARTIFACT_TYPES: dict[str, ArtifactType] = {
    t.key: t
    for t in [
        ArtifactType(
            key="business_card", display_name="Business card",
            artifact_class=ArtifactClass.TYPOGRAPHIC_PRINT,
            width_mm=89, height_mm=51,
            notes="Two-sided. Text must be pixel-perfect; render via layout engine, never diffusion.",
        ),
        ArtifactType(
            key="wedding_invite", display_name="Wedding invitation",
            artifact_class=ArtifactClass.TYPOGRAPHIC_PRINT,
            width_mm=127, height_mm=178,
            notes="Ornamental motifs generated, typography rendered deterministically.",
        ),
        ArtifactType(
            key="letterhead", display_name="Letterhead",
            artifact_class=ArtifactClass.TYPOGRAPHIC_PRINT,
            width_mm=210, height_mm=297,
        ),
        ArtifactType(
            key="book_cover", display_name="Book cover",
            artifact_class=ArtifactClass.ILLUSTRATED_FLAT,
            width_px=1600, height_px=2560,
            notes="Front cover art via image gen; title/author type composited by layout engine.",
        ),
        ArtifactType(
            key="poster", display_name="Poster",
            artifact_class=ArtifactClass.ILLUSTRATED_FLAT,
            width_px=2000, height_px=3000,
        ),
        ArtifactType(
            key="product_video", display_name="Product shoot video",
            artifact_class=ArtifactClass.MOTION,
            width_px=1920, height_px=1080, duration_s=8.0,
            notes="Image-to-video from product photo, shot list authored by cinematographer agent.",
        ),
    ]
}


# ---------------------------------------------------------------------------
# Intake
# ---------------------------------------------------------------------------

class InputAsset(BaseModel):
    """A user-supplied file: portrait, product photo, logo, prior materials."""

    asset_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    kind: Literal["photo", "logo", "document", "reference_design", "other"] = "photo"
    path: str                                  # artifact-store path
    media_type: str = "image/png"
    description: str = ""                      # what the user says this is


class ClarifyingQuestion(BaseModel):
    question: str
    why_it_matters: str
    default_assumption: str                    # what we proceed with if unanswered
    blocking: bool = False                     # True => pause the run and ask the client


class DesignBrief(BaseModel):
    """Structured understanding of what the client actually needs."""

    project_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    artifact_type_key: str                     # key into ARTIFACT_TYPES
    subject_name: str                          # the person / product / event
    subject_description: str                   # who/what they are, in depth
    audience: str                              # who will hold/see this artifact
    hard_facts: dict[str, str] = Field(default_factory=dict)  # name, title, phone, date, venue...
    stated_preferences: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)      # budget, print house, deadline
    assets: list[InputAsset] = Field(default_factory=list)
    open_questions: list[ClarifyingQuestion] = Field(default_factory=list)
    language: str = "en"


# ---------------------------------------------------------------------------
# Aura — the differentiator
# ---------------------------------------------------------------------------

class TypographyDirection(BaseModel):
    voice: str                                 # e.g. "authoritative serif with humanist warmth"
    primary_family_suggestions: list[str]      # real, licensable typefaces
    secondary_family_suggestions: list[str]
    case_and_tracking: str                     # e.g. "small caps, +80 tracking for the name line"


class PaletteDirection(BaseModel):
    mood: str                                  # color psychology rationale
    primary_hex: list[str]                     # 2-3 anchors
    accent_hex: list[str]
    forbidden: list[str] = Field(default_factory=list)  # e.g. "no neon, undermines gravitas"


class AuraProfile(BaseModel):
    """The 'aura' translated into visual DNA. Every downstream agent designs
    *from this*, not from the raw brief — this is where taste transfer happens."""

    archetype: str                             # e.g. "The Sage-Advocate: quiet authority earned in court"
    essence_statement: str                     # 2-3 sentences capturing the person/product's presence
    adjectives: list[str]                      # 5-8, ranked
    cultural_context: str                      # region, tradition, industry codes to honor or subvert
    status_signals: list[str]                  # what communicates their standing (restraint? ornament? scale?)
    typography: TypographyDirection
    palette: PaletteDirection
    materials_and_finishes: list[str]          # letterpress, soft-touch, gold foil edge...
    motifs: list[str]                          # visual symbols that belong to this subject
    composition_notes: str                     # whitespace philosophy, symmetry vs tension
    anti_patterns: list[str]                   # what would betray the aura
    photography_light: str = ""                # for motion/photo work: lighting character


# ---------------------------------------------------------------------------
# Creative direction & design specs
# ---------------------------------------------------------------------------

class ConceptDirection(BaseModel):
    """One distinct creative territory. The director guarantees siblings differ."""

    direction_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str                                  # e.g. "Counsel in Ink"
    thesis: str                                # the one idea this design argues
    how_it_expresses_aura: str
    differentiator: str                        # what makes it unlike the other directions
    risk_level: Literal["safe", "balanced", "bold"] = "balanced"


class LayoutSpec(BaseModel):
    """Deterministic layout: full HTML+CSS document rendered by the layout
    engine. Used whenever typography must be exact (all print artifacts)."""

    spec_kind: Literal["layout"] = "layout"
    html: str                                  # complete standalone document
    background_image_prompt: str | None = None # optional generated art layered under type
    background_placement: str = "cover"
    pages: int = 1                             # 2 for two-sided cards


class ImagePromptSpec(BaseModel):
    """Pure generative image, for illustrative artifacts."""

    spec_kind: Literal["image_prompt"] = "image_prompt"
    prompt: str
    negative_prompt: str = ""
    style_tags: list[str] = Field(default_factory=list)
    overlay_html: str | None = None            # optional type layer composited on top


class Shot(BaseModel):
    order: int
    duration_s: float
    camera: str                                # e.g. "slow 20mm push-in, product center-framed"
    lighting: str
    action: str                                # what happens in frame
    prompt: str                                # final image-to-video prompt for this shot


class VideoShotListSpec(BaseModel):
    """Cinematographer output: per-shot image-to-video plan from product photo."""

    spec_kind: Literal["video_shots"] = "video_shots"
    source_asset_id: str                       # the product photo driving i2v
    art_direction: str
    shots: list[Shot]
    music_brief: str = ""


DesignSpec = LayoutSpec | ImagePromptSpec | VideoShotListSpec


# ---------------------------------------------------------------------------
# Candidates, critique, deliverables
# ---------------------------------------------------------------------------

class Candidate(BaseModel):
    """A rendered design awaiting judgment."""

    candidate_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    direction: ConceptDirection
    spec: DesignSpec = Field(discriminator="spec_kind")
    preview_paths: list[str] = Field(default_factory=list)   # PNG previews / video file
    print_pdf_path: str | None = None
    revision: int = 0


class CritiqueScore(BaseModel):
    criterion: str
    score: float = Field(ge=0, le=10)
    note: str


class Critique(BaseModel):
    candidate_id: str
    scores: list[CritiqueScore]
    overall: float = Field(ge=0, le=10)
    verdict: Literal["ship", "revise", "kill"]
    revision_notes: list[str] = Field(default_factory=list)


class RationaleCard(BaseModel):
    """Client-facing explanation: why this design carries their aura."""

    candidate_id: str
    headline: str
    body: str


class DeliverablePackage(BaseModel):
    project_id: str
    brief: DesignBrief
    aura: AuraProfile
    selected: list[Candidate]
    rationales: list[RationaleCard]
    rejected_count: int


# ---------------------------------------------------------------------------
# Human-in-the-loop interrupt payloads
# ---------------------------------------------------------------------------

class ClarifyRequest(BaseModel):
    """Raised mid-run when intake found blocking unknowns; the run pauses
    until the client answers (or explicitly accepts the defaults)."""

    kind: Literal["clarify"] = "clarify"
    project_id: str
    questions: list[ClarifyingQuestion]


class ClarifyResponse(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)  # question -> answer
    accept_defaults: bool = False


class ReviewRequest(BaseModel):
    """Studio-tier gate: a human editor sees the gallery before the client."""

    kind: Literal["studio_review"] = "studio_review"
    project_id: str
    candidate_ids: list[str]
    preview_paths: dict[str, list[str]] = Field(default_factory=dict)


class ReviewDecision(BaseModel):
    candidate_id: str
    action: Literal["approve", "revise", "reject"]
    notes: str = ""


class ReviewResponse(BaseModel):
    decisions: list[ReviewDecision]
