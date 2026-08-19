"""Concept designer agents — one per direction, run in parallel.

The designer routes on artifact class, because *how you make it* is the
quality decision:

- typographic_print -> LayoutSpec: the design is written as HTML/CSS and
  rendered by Chromium. Type is exact, print-safe, editable forever. Image
  models never touch lettering.
- illustrated_flat -> ImagePromptSpec: generative art carries the design;
  any type is composited on top as an HTML overlay.
- motion -> VideoShotListSpec: a cinematography plan driving image-to-video
  from the client's product photo, shot by shot.

The same agent also handles revisions when the critic sends work back."""

from __future__ import annotations

from aura.providers.base import TextLLM
from aura.schemas import (
    ARTIFACT_TYPES, ArtifactClass, AuraProfile, ConceptDirection, DesignBrief,
    DesignSpec, ImagePromptSpec, LayoutSpec, VideoShotListSpec,
)

LAYOUT_SYSTEM = """You are a typographic designer who works in code. You produce a
complete, standalone HTML document that Chromium will render at physical size
({width_mm}mm x {height_mm}mm) — this IS the artifact, not a mockup.

Craft rules:
- Inline all CSS. No external requests except Google Fonts (allowed). Use real
  typefaces from the aura profile's suggestions or close free equivalents.
- Design at physical scale: body sized to the viewport, margins generous,
  nothing critical within {bleed_mm}mm of the trim edge.
- HARD FACTS from the brief must appear verbatim, character for character.
- Honor the aura profile: its palette hex values, its typography voice, its
  composition notes, and especially its anti_patterns.
- Restraint is craft. One idea per card. The direction's thesis decides every
  choice; if an element doesn't argue the thesis, delete it.
- If the concept needs generated art (a motif, texture, engraving), describe it
  in background_image_prompt and design the type to sit on it; otherwise null.
- pages=2 for two-sided artifacts when the concept calls for a reverse side;
  put both pages in the document as sequential full-viewport sections."""

IMAGE_SYSTEM = """You are an art director writing prompts for a state-of-the-art image
model, designing a {display_name} ({width_px}x{height_px}px).

- The prompt must be a full art direction: subject, composition, light, medium,
  era, lens/texture, mood — derived from the aura profile, arguing the
  direction's thesis.
- Put every aura anti_pattern and cliché into negative_prompt.
- NEVER ask the image model to render text. If the artifact needs type (title,
  author, names), design it as overlay_html — a standalone HTML layer with
  transparent background, composited over the art at exact size.
"""

CINEMA_SYSTEM = """You are a commercial director of photography planning a
{duration_s:.0f}-second product film ({width_px}x{height_px}) built from the client's
product photo via image-to-video generation.

- 2-4 shots. Each shot's prompt must fully specify: camera movement (be precise:
  focal length, speed, direction), lighting continuity with the source photo,
  what moves in frame, and what must NOT change (the product's geometry, label,
  colors — brand fidelity is non-negotiable).
- Derive the film's mood from the aura profile: its light, its pace, its
  materials. A heritage watch and an energy drink do not move the same way.
- source_asset_id must be the id of the product photo asset given in the brief.
- Keep total shot durations equal to {duration_s:.0f}s. Write a one-line music_brief."""

REVISE_SUFFIX = """

You are REVISING existing work. Address every note from the studio critic below
while preserving the direction's thesis. Notes:
{notes}

Previous spec:
{previous}"""


async def design_concept(llm: TextLLM, *, brief: DesignBrief, aura: AuraProfile,
                         direction: ConceptDirection,
                         revision_notes: list[str] | None = None,
                         previous_spec: DesignSpec | None = None) -> DesignSpec:
    artifact = ARTIFACT_TYPES[brief.artifact_type_key]
    context = (
        "BRIEF:\n" + brief.model_dump_json(indent=2, exclude={"assets"})
        + "\n\nASSETS:\n" + "\n".join(f"- {a.asset_id} [{a.kind}]: {a.description}"
                                      for a in brief.assets)
        + "\n\nAURA PROFILE:\n" + aura.model_dump_json(indent=2)
        + "\n\nYOUR DIRECTION:\n" + direction.model_dump_json(indent=2)
    )

    if artifact.artifact_class is ArtifactClass.TYPOGRAPHIC_PRINT:
        system = LAYOUT_SYSTEM.format(width_mm=artifact.width_mm, height_mm=artifact.height_mm,
                                      bleed_mm=artifact.bleed_mm)
        output: type[DesignSpec] = LayoutSpec
    elif artifact.artifact_class is ArtifactClass.ILLUSTRATED_FLAT:
        system = IMAGE_SYSTEM.format(display_name=artifact.display_name,
                                     width_px=artifact.width_px, height_px=artifact.height_px)
        output = ImagePromptSpec
    else:
        system = CINEMA_SYSTEM.format(duration_s=artifact.duration_s or 8.0,
                                      width_px=artifact.width_px, height_px=artifact.height_px)
        output = VideoShotListSpec

    if revision_notes and previous_spec is not None:
        system += REVISE_SUFFIX.format(notes="\n".join(f"- {n}" for n in revision_notes),
                                       previous=previous_spec.model_dump_json(indent=2))

    return await llm.structured(system=system, prompt=context, output_model=output)
