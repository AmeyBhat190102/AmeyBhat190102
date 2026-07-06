"""Turns a DesignSpec into files on disk — the only module that touches
image/video/layout engines directly."""

from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
from pathlib import Path

from aura.config import Providers
from aura.render.html_renderer import png_dimensions_for
from aura.schemas import (
    ARTIFACT_TYPES, Candidate, ConceptDirection, DesignBrief, DesignSpec,
    ImagePromptSpec, LayoutSpec, VideoShotListSpec,
)
from aura.storage import ArtifactStore


async def render_candidate(providers: Providers, store: ArtifactStore, *,
                           brief: DesignBrief, direction: ConceptDirection,
                           spec: DesignSpec, revision: int = 0) -> Candidate:
    artifact = ARTIFACT_TYPES[brief.artifact_type_key]
    candidate = Candidate(direction=direction, spec=spec, revision=revision)
    tag = f"{direction.direction_id}-r{revision}"

    if isinstance(spec, LayoutSpec):
        html = spec.html
        if spec.background_image_prompt:
            art = await providers.image_gen.generate(
                prompt=spec.background_image_prompt, width=1024, height=1024)
            html = _inject_background(html, art, spec.background_placement)
        w_px, h_px = png_dimensions_for(artifact.width_mm or 89, artifact.height_mm or 51)
        png = await providers.renderer.render_png(html=html, width_px=w_px, height_px=h_px)
        pdf = await providers.renderer.render_pdf(
            html=html, width_mm=artifact.width_mm or 89, height_mm=artifact.height_mm or 51)
        candidate.preview_paths = [store.save(brief.project_id, f"{tag}.png", png)]
        candidate.print_pdf_path = store.save(brief.project_id, f"{tag}.pdf", pdf)

    elif isinstance(spec, ImagePromptSpec):
        art = await providers.image_gen.generate(
            prompt=spec.prompt, negative_prompt=spec.negative_prompt,
            width=artifact.width_px or 1024, height=artifact.height_px or 1024)
        if spec.overlay_html:
            # Composite in the browser: art becomes the background layer of the
            # type overlay, rendered together at exact pixel size.
            html = _inject_background(spec.overlay_html, art, "cover")
            art = await providers.renderer.render_png(
                html=html, width_px=artifact.width_px or 1024,
                height_px=artifact.height_px or 1024)
        candidate.preview_paths = [store.save(brief.project_id, f"{tag}.png", art)]

    elif isinstance(spec, VideoShotListSpec):
        source = next((a.path for a in brief.assets if a.asset_id == spec.source_asset_id),
                      brief.assets[0].path if brief.assets else None)
        clips = []
        for shot in sorted(spec.shots, key=lambda s: s.order):
            mp4 = await providers.video_gen.generate(
                prompt=shot.prompt, source_image=source, duration_s=shot.duration_s,
                width=artifact.width_px or 1920, height=artifact.height_px or 1080)
            clips.append(store.save(brief.project_id, f"{tag}-shot{shot.order}.mp4", mp4))
        final = _stitch(clips)
        candidate.preview_paths = (
            [store.save(brief.project_id, f"{tag}.mp4", final)] if final else clips)

    return candidate


def _inject_background(html: str, png: bytes, placement: str) -> str:
    data_uri = "data:image/png;base64," + base64.b64encode(png).decode()
    style = (f"<style>body{{background-image:url('{data_uri}');"
             f"background-size:{placement};background-position:center;}}</style>")
    if "</head>" in html:
        return html.replace("</head>", style + "</head>", 1)
    return style + html


def _stitch(clip_paths: list[str]) -> bytes | None:
    """Concat shots with ffmpeg when available; otherwise deliver per-shot clips."""
    if len(clip_paths) < 2:
        return None
    if not shutil.which("ffmpeg"):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        manifest = Path(tmp) / "clips.txt"
        manifest.write_text("".join(f"file '{p}'\n" for p in map(Path.absolute, map(Path, clip_paths))))
        out = Path(tmp) / "final.mp4"
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(manifest),
             "-c", "copy", str(out)], capture_output=True)
        if result.returncode != 0:
            return None
        return out.read_bytes()
