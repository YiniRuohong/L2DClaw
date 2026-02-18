from __future__ import annotations

import asyncio
import logging
from typing import Callable, Dict, List

from adapter.base import AdapterBase, AdapterEvent

LOGGER = logging.getLogger(__name__)


class AdapterManager:
    """Register, start, and stop all adapters."""

    def __init__(self) -> None:
        self._adapters: List[AdapterBase] = []
        self._event_handlers: List[Callable[[AdapterEvent], None]] = []

    def register(self, adapter: AdapterBase) -> None:
        self._adapters.append(adapter)

    def on_event(self, event: AdapterEvent) -> None:
        for handler in self._event_handlers:
            handler(event)

    def add_event_handler(self, handler: Callable[[AdapterEvent], None]) -> None:
        self._event_handlers.append(handler)

    async def initialize_all(self) -> None:
        for adapter in self._adapters:
            if not adapter.is_available() or not adapter.enabled:
                continue
            try:
                await adapter.initialize()
            except Exception as exc:
                LOGGER.warning("Adapter %s failed to initialize: %s", adapter.adapter_type, exc)

    async def start_all(self) -> None:
        await self.initialize_all()
        tasks = []
        for adapter in self._adapters:
            if not adapter.is_available() or not adapter.enabled:
                continue
            tasks.append(asyncio.create_task(adapter.start()))
        if tasks:
            await asyncio.gather(*tasks)

    async def stop_all(self) -> None:
        for adapter in self._adapters:
            if not adapter.is_available() or not adapter.enabled:
                continue
            await adapter.stop()

    async def get_context_snapshot(self) -> Dict:
        snapshot: Dict = {}
        for adapter in self._adapters:
            if not adapter.is_available() or not adapter.enabled:
                continue
            snapshot[adapter.adapter_type] = await adapter.get_current_state()
        return snapshot
