from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from app.core.config import get_settings


class OpenAIJsonClient:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = (
            AsyncOpenAI(api_key=self._settings.openai_api_key)
            if self._settings.openai_api_key
            else None
        )

    @property
    def enabled(self) -> bool:
        return bool(self._settings.openai_api_key)

    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("OpenAI client is disabled because OPENAI_API_KEY is not set.")
        response = await self._client.chat.completions.create(
            model=self._settings.openai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
