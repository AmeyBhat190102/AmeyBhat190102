"""Output contracts for specialist roles beyond the core design specs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CopyBlock(BaseModel):
    slot: str                      # e.g. "invitation_main", "rsvp", "tagline"
    text: str                      # final wording, verbatim — this gets printed
    tone_note: str = ""


class CopyDeck(BaseModel):
    """Invitation wording, taglines, back-of-card lines — words as craft."""

    language: str = "en"
    blocks: list[CopyBlock]
    pronunciation_or_transliteration_notes: str = ""


class FontPairing(BaseModel):
    display_family: str            # Google Fonts name (licensing-safe at launch)
    body_family: str
    rationale: str


class TypographyPlan(BaseModel):
    """Calligraphy/type specialist: exact typographic system for the artifact."""

    pairing: FontPairing
    name_treatment: str            # case, tracking, size relationships for the hero line
    hierarchy: list[str]           # ordered levels with size/weight/case notes
    flourishes: str = ""           # swashes, ligatures, rules — and where restraint wins


class Motif(BaseModel):
    name: str
    meaning: str                   # why this symbol belongs to this subject
    image_prompt: str              # generation prompt (transparent/flat, print-friendly)
    placement_hint: str            # where it lives on the artifact


class MotifSet(BaseModel):
    """Illustrated symbols. The executor renders each prompt; rendered files
    are exposed to downstream layout tasks as __MOTIF_0__, __MOTIF_1__…
    tokens they can place as <img src="__MOTIF_0__"> in their HTML."""

    motifs: list[Motif] = Field(min_length=1, max_length=4)
    style_note: str                # shared style so the set feels like one hand


class SoundBrief(BaseModel):
    """Music/sound direction for motion artifacts."""

    mood: str
    tempo_bpm: int
    instrumentation: str
    sound_design_beats: list[str]  # e.g. "0.0s: room tone", "2.1s: soft whoosh on reveal"
    reference_tracks: list[str] = Field(default_factory=list)


class LogoConcept(BaseModel):
    """Mark concept: rendered by image gen now, Recraft SVG in production."""

    concept: str                   # the idea the mark argues
    image_prompt: str              # flat vector-style mark, solid background
    lockup_rules: str              # clearspace, min size, do/don't
    monochrome_behavior: str
