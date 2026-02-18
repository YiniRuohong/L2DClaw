import asyncio
import logging
from typing import Dict, Optional

from adapter.base import AdapterBase, AdapterEvent
from adapter.screen.content_recognizer import ContentRecognizer, ContentRecognizerConfig
from adapter.screen.window_watcher import get_active_window

LOGGER = logging.getLogger(__name__)


class ScreenAdapter(AdapterBase):
    adapter_type = "screen"

    def __init__(self, config, user_prefs: Dict, event_callback) -> None:
        super().__init__(config, event_callback)
        screen_config = self._get_section(config, "screen_watcher")
        self._interval = screen_config.get("interval_seconds", 5)
        self._content_interval = screen_config.get("content_recognition_interval", 15)
        prefs = user_prefs.get("screen", {}) if user_prefs else {}
        self._recognizer = ContentRecognizer(
            ContentRecognizerConfig(
                content_recognition_enabled=prefs.get("content_recognition_enabled", False),
                content_recognition_mode=prefs.get("content_recognition_mode", "ocr"),
                capture_region=prefs.get("capture_region", "active_window"),
            )
        )
        self._last_window: Optional[Dict] = None
        self._last_content: Optional[Dict] = None
        self._content_counter = 0

    async def initialize(self) -> bool:
        return True

    async def start(self) -> None:
        self._running = True
        while self._running:
            window_info = get_active_window()
            if window_info != self._last_window:
                event = AdapterEvent(
                    adapter_type=self.adapter_type,
                    event_type="window_changed",
                    data=window_info,
                    timestamp=self._now_iso(),
                )
                self.emit(event)
                self._last_window = window_info

            if self._should_capture_content():
                content = self._recognizer.capture_and_analyze()
                if content:
                    self._last_content = content
                    event = AdapterEvent(
                        adapter_type=self.adapter_type,
                        event_type="screen_content",
                        data=content,
                        timestamp=self._now_iso(),
                        priority=7,
                    )
                    self.emit(event)

            await asyncio.sleep(self._interval)

    async def stop(self) -> None:
        self._running = False

    async def get_current_state(self) -> Dict:
        state = {"active_window": self._last_window, "content": self._last_content}
        return state

    def _get_section(self, config, name: str) -> Dict:
        if isinstance(config, dict):
            return config.get(name, {})
        return getattr(config, name, {}) or {}

    def _should_capture_content(self) -> bool:
        if not self._recognizer._config.content_recognition_enabled:
            return False
        self._content_counter += 1
        if self._content_counter >= max(1, int(self._content_interval / self._interval)):
            self._content_counter = 0
            return True
        return False
