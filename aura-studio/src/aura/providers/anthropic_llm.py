"""Claude as the reasoning engine for every agent (text + vision).

Structured output is enforced with a forced tool call whose input schema is
the pydantic model — validation errors are fed back for one retry, which in
practice eliminates malformed-output failures.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import TypeVar

from anthropic import AsyncAnthropic
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "claude-sonnet-5"


class AnthropicLLM:
    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        self.model = model
        self.client = AsyncAnthropic(api_key=api_key) if api_key else AsyncAnthropic()

    async def structured(self, *, system: str, prompt: str, output_model: type[T],
                         images: list[str] | None = None) -> T:
        tool = {
            "name": "emit",
            "description": f"Emit the final {output_model.__name__}.",
            "input_schema": output_model.model_json_schema(),
        }
        content: list[dict] = []
        for path in images or []:
            media_type = mimetypes.guess_type(path)[0] or "image/png"
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.b64encode(Path(path).read_bytes()).decode(),
                },
            })
        content.append({"type": "text", "text": prompt})

        messages = [{"role": "user", "content": content}]
        last_error: Exception | None = None
        for _ in range(2):  # one retry with the validation error fed back
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=system,
                messages=messages,
                tools=[tool],
                tool_choice={"type": "tool", "name": "emit"},
            )
            block = next(b for b in resp.content if b.type == "tool_use")
            try:
                return output_model.model_validate(block.input)
            except ValidationError as e:
                last_error = e
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({
                    "role": "user",
                    "content": f"Your output failed validation:\n{e}\nCall emit again, corrected.",
                })
        raise RuntimeError(f"structured output failed twice: {last_error}")
