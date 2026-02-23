"""Emotion learning helpers for per-character mood tracking."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime

from loguru import logger

from .config_manager import EmotionLearningConfig
from .live2d_model import Live2dModel


EMOTION_LABELS: tuple[str, ...] = (
    "joy",
    "sadness",
    "anger",
    "fear",
    "surprise",
    "disgust",
)

EMOTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "joy": ("happy", "glad", "great", "awesome", "yay", ":)", ":d", "love"),
    "sadness": ("sad", "sorry", "unhappy", "miss", ":(", ":'("),
    "anger": ("angry", "mad", "furious", "hate", "annoyed", "wtf"),
    "fear": ("afraid", "scared", "fear", "worried", "nervous", "anxious"),
    "surprise": ("wow", "surprised", "omg", "unexpected"),
    "disgust": ("disgust", "gross", "nasty", "ew"),
}

SAFE_COMPONENT_PATTERN = re.compile(r"^[\w\-]+$")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _is_safe_filename(filename: str) -> bool:
    if not filename or len(filename) > 255:
        return False
    return bool(SAFE_COMPONENT_PATTERN.match(filename))


def _sanitize_path_component(component: str) -> str:
    sanitized = os.path.basename(component.strip())
    if not _is_safe_filename(sanitized):
        raise ValueError(f"Invalid characters in path component: {component}")
    return sanitized


def _ensure_storage_dir(storage_dir: str) -> str:
    if not storage_dir:
        storage_dir = "emotion_memory"
    base_dir = os.path.abspath(storage_dir)
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def _get_safe_memory_path(storage_dir: str, conf_uid: str) -> str:
    safe_conf_uid = _sanitize_path_component(conf_uid)
    base_dir = _ensure_storage_dir(storage_dir)
    full_path = os.path.abspath(os.path.join(base_dir, f"{safe_conf_uid}.json"))
    if os.path.commonpath([base_dir, full_path]) != base_dir:
        raise ValueError("Invalid path: Path traversal detected")
    return full_path


def _default_state(now: str) -> dict:
    return {
        "label": "neutral",
        "valence": 0.0,
        "arousal": 0.0,
        "intensity": 0.0,
        "source": "init",
        "last_updated": now,
    }


def _default_counts() -> dict[str, float]:
    return {label: 0.0 for label in EMOTION_LABELS}


def _coerce_float_map(raw: dict[str, float] | None) -> dict[str, float]:
    if not raw:
        return {}
    return {k: float(v) for k, v in raw.items() if k in EMOTION_LABELS}


def _detect_emotions(text: str) -> dict[str, float]:
    if not text:
        return {}
    normalized = text.lower()
    scores: dict[str, float] = {}
    for label, keywords in EMOTION_KEYWORDS.items():
        count = 0
        for keyword in keywords:
            if keyword in normalized:
                count += normalized.count(keyword)
        if count:
            scores[label] = float(count)
    return scores


def _detect_expression_tags(
    text: str, live2d_model: Live2dModel | None
) -> dict[str, float]:
    if not text or not live2d_model:
        return {}
    normalized = text.lower()
    scores: dict[str, float] = {}
    for key in live2d_model.emo_map.keys():
        tag = f"[{key}]"
        if tag in normalized:
            scores[key] = float(normalized.count(tag))
    return scores


def load_emotion_memory(
    conf_uid: str, config: EmotionLearningConfig
) -> dict[str, object]:
    """Load per-character emotion memory.

    Args:
        conf_uid: Configuration identifier for the character.
        config: Emotion learning configuration.

    Returns:
        A dictionary containing emotion learning state.
    """
    if not config or not config.enabled:
        return {}

    now = _now_iso()
    data = {
        "version": 1,
        "updated_at": now,
        "state": _default_state(now),
        "emotion_counts": _default_counts(),
        "expression_habits": _default_counts(),
        "recent_events": [],
    }

    try:
        path = _get_safe_memory_path(config.storage_dir, conf_uid)
        if not os.path.exists(path):
            return data
        with open(path, "r", encoding="utf-8") as file:
            loaded = json.load(file)
        if not isinstance(loaded, dict):
            return data
        data.update(loaded)
    except Exception as exc:
        logger.warning(f"Failed to load emotion memory: {exc}")
        return data

    data["emotion_counts"] = (
        _coerce_float_map(data.get("emotion_counts", {})) or _default_counts()
    )
    data["expression_habits"] = (
        _coerce_float_map(data.get("expression_habits", {})) or _default_counts()
    )
    data.setdefault("state", _default_state(now))
    data.setdefault("recent_events", [])
    return data


def save_emotion_memory(
    conf_uid: str, config: EmotionLearningConfig, data: dict[str, object]
) -> None:
    """Persist per-character emotion memory.

    Args:
        conf_uid: Configuration identifier for the character.
        config: Emotion learning configuration.
        data: Emotion learning state to store.

    Returns:
        None.
    """
    if not config or not config.enabled:
        return

    try:
        path = _get_safe_memory_path(config.storage_dir, conf_uid)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning(f"Failed to save emotion memory: {exc}")


def update_emotion_memory(
    conf_uid: str,
    config: EmotionLearningConfig,
    user_text: str,
    assistant_text: str,
    live2d_model: Live2dModel | None,
) -> dict[str, object]:
    """Update emotion memory based on the latest exchange.

    Args:
        conf_uid: Configuration identifier for the character.
        config: Emotion learning configuration.
        user_text: Latest user utterance.
        assistant_text: Latest assistant response.
        live2d_model: Live2D model instance for expression tags.

    Returns:
        Updated emotion learning state.
    """
    if not config or not config.enabled:
        return {}

    data = load_emotion_memory(conf_uid, config)
    now = _now_iso()
    data["updated_at"] = now

    decay = float(config.decay)
    emotion_counts = _coerce_float_map(data.get("emotion_counts"))
    habits = _coerce_float_map(data.get("expression_habits"))

    for label in EMOTION_LABELS:
        emotion_counts[label] = emotion_counts.get(label, 0.0) * decay
        habits[label] = habits.get(label, 0.0) * decay

    user_scores = _detect_emotions(user_text)
    assistant_scores = _detect_emotions(assistant_text)
    expression_scores = _detect_expression_tags(assistant_text, live2d_model)

    for label, score in user_scores.items():
        emotion_counts[label] = emotion_counts.get(label, 0.0) + score
    for label, score in assistant_scores.items():
        emotion_counts[label] = emotion_counts.get(label, 0.0) + score

    for label, score in expression_scores.items():
        if label in EMOTION_LABELS:
            habits[label] = habits.get(label, 0.0) + score

    combined_scores = {**user_scores}
    for label, score in assistant_scores.items():
        combined_scores[label] = combined_scores.get(label, 0.0) + score

    state = data.get("state") or _default_state(now)
    total = sum(combined_scores.values())
    if total > 0:
        dominant_label = max(combined_scores, key=combined_scores.get)
        valence = (
            combined_scores.get("joy", 0.0)
            + 0.3 * combined_scores.get("surprise", 0.0)
            - combined_scores.get("sadness", 0.0)
            - combined_scores.get("anger", 0.0)
            - combined_scores.get("fear", 0.0)
            - combined_scores.get("disgust", 0.0)
        ) / total
        arousal = (
            combined_scores.get("anger", 0.0)
            + combined_scores.get("fear", 0.0)
            + combined_scores.get("surprise", 0.0)
        ) / total
        intensity = min(1.0, total / 4.0)
        state = {
            "label": dominant_label,
            "valence": round(valence, 3),
            "arousal": round(arousal, 3),
            "intensity": round(intensity, 3),
            "source": "conversation",
            "last_updated": now,
        }
    else:
        state["valence"] = round(float(state.get("valence", 0.0)) * decay, 3)
        state["arousal"] = round(float(state.get("arousal", 0.0)) * decay, 3)
        state["intensity"] = round(float(state.get("intensity", 0.0)) * decay, 3)
        if state["intensity"] < config.min_confidence:
            state["label"] = "neutral"
            state["source"] = "decay"
            state["last_updated"] = now

    data["state"] = state
    data["emotion_counts"] = emotion_counts
    data["expression_habits"] = habits

    recent_events = data.get("recent_events", [])
    max_events = max(0, int(config.max_recent_events))

    def _append_event(source: str, text: str, scores: dict[str, float]) -> None:
        if not scores:
            return
        snippet = (text or "").strip().replace("\n", " ")
        if len(snippet) > 160:
            snippet = f"{snippet[:157]}..."
        recent_events.append(
            {
                "ts": now,
                "source": source,
                "emotions": sorted(scores.keys()),
                "text": snippet,
            }
        )

    _append_event("user", user_text, user_scores)
    _append_event("assistant", assistant_text, assistant_scores)

    if max_events == 0:
        recent_events = []
    elif len(recent_events) > max_events:
        recent_events = recent_events[-max_events:]

    data["recent_events"] = recent_events

    save_emotion_memory(conf_uid, config, data)
    return data


def build_emotion_prompt(data: dict[str, object], config: EmotionLearningConfig) -> str:
    """Build a prompt snippet from emotion learning state.

    Args:
        data: Emotion learning state.
        config: Emotion learning configuration.

    Returns:
        Prompt snippet to append to the persona prompt.
    """
    if not config or not config.enabled or not data:
        return ""
    lines: list[str] = []
    state = data.get("state") or {}
    habits = _coerce_float_map(data.get("expression_habits"))
    recent_events = data.get("recent_events") or []

    lines.append("\n\n[Emotion Learning]")

    if config.include_state and state:
        lines.append(
            "Current mood: "
            f"{state.get('label', 'neutral')} "
            f"(valence {state.get('valence', 0.0):.2f}, "
            f"arousal {state.get('arousal', 0.0):.2f}, "
            f"intensity {state.get('intensity', 0.0):.2f})."
        )

    if config.include_habits and habits:
        total = sum(habits.values()) or 1.0
        ranked = sorted(habits.items(), key=lambda item: item[1], reverse=True)
        items = []
        for label, score in ranked:
            weight = score / total
            if weight < config.min_confidence:
                continue
            items.append(f"{label} {weight:.2f}")
            if len(items) >= config.prompt_max_items:
                break
        if items:
            lines.append("Expression habits: " + ", ".join(items) + ".")

    if config.include_recent_events and recent_events:
        recent = recent_events[-min(len(recent_events), config.prompt_max_items) :]
        cues = []
        for event in recent:
            emotions = ",".join(event.get("emotions", []))
            if emotions:
                cues.append(f"{event.get('source', 'unknown')}={emotions}")
        if cues:
            lines.append("Recent cues: " + "; ".join(cues) + ".")

    lines.append(
        "Keep responses aligned with the persona and these learned tendencies."
    )

    return "\n".join(lines)
