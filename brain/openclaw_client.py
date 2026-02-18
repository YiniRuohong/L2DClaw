import json
import logging
from typing import Any, Dict

import httpx

LOGGER = logging.getLogger(__name__)


class OpenClawClient:
    def __init__(self, config) -> None:
        openclaw = self._get_section(config, "openclaw")
        self._gateway_url = openclaw.get("gateway_url", "http://127.0.0.1:18789/v1")
        self._token = openclaw.get("token", "")
        self._agent_id = openclaw.get("agent_id", "main")
        self._system_prompt = openclaw.get("system_prompt")
        self._timeout = openclaw.get("timeout_seconds", 10)

    async def think(self, context: str, user_text: str) -> Dict[str, Any]:
        url = f"{self._gateway_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "x-openclaw-agent-id": self._agent_id,
        }
        body = {
            "model": "openclaw",
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": f"[Context]\n{context}\n\n[User]\n{user_text}"},
            ],
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            LOGGER.error("OpenClaw request failed: %s", exc)
            return {}

        data = response.json()
        content = (
            data.get("choices", [{}])[0].get("message", {}).get("content") if data else None
        )
        if not content:
            return {}
        if isinstance(content, dict):
            return content
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            LOGGER.error("OpenClaw response is not valid JSON: %s", content)
            return {}

    def _get_section(self, config, name: str) -> Dict:
        if isinstance(config, dict):
            return config.get(name, {})
        return getattr(config, name, {}) or {}
