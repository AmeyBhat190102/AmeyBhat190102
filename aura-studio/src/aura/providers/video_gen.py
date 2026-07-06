"""Video generation via Replicate, which fronts the current best i2v models
(Google Veo, Kling, Minimax) behind one API — so 'best video tool of the
month' is a model-slug change, not an integration project.
"""

from __future__ import annotations

import asyncio
import base64
import mimetypes
from pathlib import Path

import httpx

DEFAULT_MODEL = "google/veo-3-fast"


class ReplicateVideoGen:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model

    async def generate(self, *, prompt: str, source_image: str | None,
                       duration_s: float, width: int, height: int) -> bytes:
        payload: dict = {"input": {"prompt": prompt, "duration": int(duration_s)}}
        if source_image:
            media_type = mimetypes.guess_type(source_image)[0] or "image/png"
            b64 = base64.b64encode(Path(source_image).read_bytes()).decode()
            payload["input"]["image"] = f"data:{media_type};base64,{b64}"

        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"https://api.replicate.com/v1/models/{self.model}/predictions",
                headers=headers, json=payload,
            )
            resp.raise_for_status()
            prediction = resp.json()

            while prediction["status"] not in ("succeeded", "failed", "canceled"):
                await asyncio.sleep(5)
                poll = await client.get(prediction["urls"]["get"], headers=headers)
                poll.raise_for_status()
                prediction = poll.json()

            if prediction["status"] != "succeeded":
                raise RuntimeError(f"video generation failed: {prediction.get('error')}")

            out = prediction["output"]
            url = out if isinstance(out, str) else out[0]
            video = await client.get(url, timeout=600)
            video.raise_for_status()
            return video.content
