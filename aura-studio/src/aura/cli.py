"""CLI: run a full studio project from the terminal.

    aura "Business card for Adv. R. K. Sharma, senior advocate, ..." \
        --asset photo.jpg="portrait of the client"

With no API keys (or AURA_PROVIDERS=mock) it runs the whole pipeline on
mock reasoning — and still renders a real card via the layout engine."""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes

from aura.config import Settings, build_providers
from aura.graph.pipeline import run_studio
from aura.schemas import InputAsset
from aura.storage import ArtifactStore


def main() -> None:
    parser = argparse.ArgumentParser(prog="aura", description="AURA design studio")
    parser.add_argument("brief", help="the design request, in the client's words")
    parser.add_argument("--asset", action="append", default=[],
                        metavar="PATH=DESCRIPTION",
                        help="attach a photo/logo/reference (repeatable)")
    args = parser.parse_args()

    assets = []
    for raw in args.asset:
        path, _, desc = raw.partition("=")
        assets.append(InputAsset(
            path=path, description=desc,
            media_type=mimetypes.guess_type(path)[0] or "image/png",
        ))

    settings = Settings()
    providers = build_providers(settings)
    store = ArtifactStore(settings.artifact_dir)

    package = asyncio.run(run_studio(
        providers, settings, store, request_text=args.brief, assets=assets))

    print(f"\n=== {len(package.selected)} designs delivered "
          f"({package.rejected_count} rejected in review) ===\n")
    print(f"Aura: {package.aura.archetype}\n")
    for candidate, rationale in zip(package.selected, package.rationales):
        print(f"• {candidate.direction.name}  [{candidate.direction.risk_level}]")
        print(f"  {rationale.headline} — {rationale.body}")
        for p in candidate.preview_paths:
            print(f"  preview: {p}")
        if candidate.print_pdf_path:
            print(f"  print:   {candidate.print_pdf_path}")
        print()
    manifest = store.save(package.project_id, "package.json",
                          package.model_dump_json(indent=2).encode())
    print(f"manifest: {manifest}")


if __name__ == "__main__":
    main()
