"""Image generation providers.

Current best-in-class routing (mid-2026):
  - Ideogram: strongest at legible text-in-image; used when a spec insists on
    baked-in lettering (we mostly avoid that — layout engine owns type).
  - OpenAI gpt-image-1 / Google Imagen: strong general art direction; default
    for background art, motifs, cover illustration.
Both speak simple HTTP; keys via env. Fallback chain handled by the registry.
"""

from __future__ import annotations

import base64

import httpx


class OpenAIImageGen:
    def __init__(self, api_key: str, model: str = "gpt-image-1"):
        self.api_key = api_key
        self.model = model

    async def generate(self, *, prompt: str, negative_prompt: str = "",
                       width: int = 1024, height: int = 1024,
                       reference_image: str | None = None) -> bytes:
        full_prompt = prompt if not negative_prompt else f"{prompt}\n\nAvoid: {negative_prompt}"
        size = _nearest_openai_size(width, height)
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "prompt": full_prompt, "size": size, "quality": "high"},
            )
            resp.raise_for_status()
            return base64.b64decode(resp.json()["data"][0]["b64_json"])


class IdeogramImageGen:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(self, *, prompt: str, negative_prompt: str = "",
                       width: int = 1024, height: int = 1024,
                       reference_image: str | None = None) -> bytes:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                "https://api.ideogram.ai/v1/ideogram-v3/generate",
                headers={"Api-Key": self.api_key},
                json={
                    "prompt": prompt,
                    "negative_prompt": negative_prompt or None,
                    "resolution": f"{width}x{height}",
                    "rendering_speed": "QUALITY",
                },
            )
            resp.raise_for_status()
            url = resp.json()["data"][0]["url"]
            img = await client.get(url)
            img.raise_for_status()
            return img.content


def _nearest_openai_size(width: int, height: int) -> str:
    ratio = width / max(height, 1)
    if ratio > 1.2:
        return "1536x1024"
    if ratio < 0.8:
        return "1024x1536"
    return "1024x1024"
