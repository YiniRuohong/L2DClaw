import json
import logging
from typing import Any, Dict

from openai import AsyncOpenAI

LOGGER = logging.getLogger(__name__)


class OpenClawClient:
    def __init__(self, config) -> None:
        openclaw = self._get_section(config, "openclaw")
        self._client = AsyncOpenAI(
            base_url=openclaw.get("base_url"),
            api_key=openclaw.get("api_key"),
            timeout=openclaw.get("timeout_seconds", 10),
        )
        self._model = openclaw.get("model")
        self._system_prompt = openclaw.get("system_prompt")

    async def think(self, context: str, user_text: str) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": f"[桌面状态]\n{context}\n\n[用户说]\n{user_text}"},
        ]
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return json.loads(content) if content else {}

    def _get_section(self, config, name: str) -> Dict:
        if isinstance(config, dict):
            return config.get(name, {})
        return getattr(config, name, {}) or {}
