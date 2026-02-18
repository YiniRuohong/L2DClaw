from __future__ import annotations

import asyncio
import logging
import socket
import sys
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

from adapter.adapter_manager import AdapterManager
from adapter.context_builder import build_context
from adapter.keyboard.keyboard_adapter import KeyboardAdapter
from adapter.screen.screen_adapter import ScreenAdapter
from adapter.voice.voice_adapter import VoiceAdapter
from brain.openclaw_client import OpenClawClient
from brain.response_parser import parse_response
from config import load_config, load_user_prefs
from live2d_driver.driver_server import Live2DDriverServer
from setup.wizard import SetupWizard
from tts.dashscope_tts import DashscopeTTS
from tts.local_qwen3_tts import LocalQwen3TTS

LOGGER = logging.getLogger(__name__)
INIT_FLAG = Path.home() / ".l2dclaw" / "initialized"


async def _init_tts(config: Dict[str, Any]):
    tts = LocalQwen3TTS(config)
    try:
        ready = await tts.initialize()
    except Exception as exc:
        LOGGER.warning("Local TTS init failed: %s", exc)
        ready = False

    if ready:
        return tts

    fallback = DashscopeTTS(config)
    if not fallback.is_ready():
        LOGGER.warning("DashScope TTS not configured; speech disabled")
        return None

    return fallback


def _should_enable(section: Dict[str, Any], prefs: Dict[str, Any], key: str) -> bool:
    if section and isinstance(section.get("enabled"), bool):
        if not section.get("enabled"):
            return False
    if prefs and isinstance(prefs.get("enabled"), bool):
        return bool(prefs.get("enabled"))
    return True


def _check_openclaw_gateway(config: Dict[str, Any]) -> bool:
    openclaw = config.get("openclaw", {}) if isinstance(config, dict) else {}
    gateway_url = openclaw.get("gateway_url", "http://127.0.0.1:18789/v1")
    parsed = urlparse(gateway_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 18789

    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        LOGGER.error(
            "OpenClaw Gateway not running. Start it with: openclaw gateway"
        )
        return False


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not INIT_FLAG.exists():
        wizard = SetupWizard()
        if not wizard.run():
            sys.exit(0)

    try:
        config = load_config("conf.yaml")
    except FileNotFoundError as exc:
        LOGGER.error("%s", exc)
        return

    if not _check_openclaw_gateway(config):
        return

    user_prefs = load_user_prefs()

    tts = await _init_tts(config)

    manager = AdapterManager()

    screen_adapter = ScreenAdapter(config, user_prefs, manager.on_event)
    keyboard_adapter = KeyboardAdapter(config, manager.on_event)
    voice_adapter = VoiceAdapter(config, manager.on_event)

    screen_adapter.enabled = _should_enable(config.get("screen_watcher", {}), user_prefs.get("screen", {}), "screen")
    keyboard_adapter.enabled = _should_enable(config.get("keyboard_watcher", {}), user_prefs.get("keyboard", {}), "keyboard")
    voice_adapter.enabled = _should_enable(config.get("asr", {}), user_prefs.get("voice", {}), "voice")

    manager.register(screen_adapter)
    manager.register(keyboard_adapter)
    manager.register(voice_adapter)

    openclaw = OpenClawClient(config)
    driver = Live2DDriverServer(config)

    async def handle_voice_event(text: str) -> None:
        snapshot = await manager.get_context_snapshot()
        context = build_context(snapshot)
        response = await openclaw.think(context, text)
        parsed = parse_response(response)
        if not parsed.get("text"):
            LOGGER.warning("OpenClaw response missing text")
            return

        tasks = [driver.send_action(parsed["text"], parsed["emotion"], parsed["motion"])]
        if tts is not None:
            tasks.append(tts.speak(parsed["text"]))
        await asyncio.gather(*tasks)

    def on_event(event) -> None:
        if event.adapter_type == "voice" and event.event_type == "speech":
            text = event.data.get("text", "")
            if text:
                asyncio.create_task(handle_voice_event(text))

    manager.add_event_handler(on_event)

    await asyncio.gather(
        driver.start(),
        manager.start_all(),
    )


if __name__ == "__main__":
    asyncio.run(main())
