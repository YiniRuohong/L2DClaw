from __future__ import annotations

from typing import Dict


def parse_response(response: Dict) -> Dict[str, str]:
    text = (response or {}).get("text") or ""
    emotion = (response or {}).get("emotion") or "neutral"
    motion = (response or {}).get("motion") or "idle"
    return {"text": text, "emotion": emotion, "motion": motion}
