import asyncio
import logging
from typing import Dict

from pynput import keyboard

from adapter.base import AdapterBase, AdapterEvent

LOGGER = logging.getLogger(__name__)


class KeyboardAdapter(AdapterBase):
    adapter_type = "keyboard"

    def __init__(self, config, event_callback) -> None:
        super().__init__(config, event_callback)
        self._interval = self._get_section(config, "keyboard_watcher").get("interval_seconds", 5)
        self._count = 0
        self._last_burst = 0
        self._listener = None
        self._running = False

    async def initialize(self) -> bool:
        return True

    async def start(self) -> None:
        self._running = True
        self._listener = keyboard.Listener(on_press=self._on_key_press)
        self._listener.start()

        while self._running:
            if self._count:
                event = AdapterEvent(
                    adapter_type=self.adapter_type,
                    event_type="typing_burst",
                    data={"count": self._count},
                    timestamp=self._now_iso(),
                )
                self.emit(event)
                self._last_burst = self._count
                self._count = 0
            await asyncio.sleep(self._interval)

    async def stop(self) -> None:
        self._running = False
        if self._listener is not None:
            self._listener.stop()

    async def get_current_state(self) -> Dict:
        return {"typing_burst": self._last_burst}

    def _on_key_press(self, _key) -> None:
        self._count += 1

    def _get_section(self, config, name: str) -> Dict:
        if isinstance(config, dict):
            return config.get(name, {})
        return getattr(config, name, {}) or {}
