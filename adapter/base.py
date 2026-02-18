from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict


@dataclass
class AdapterEvent:
    """Standardized event payload emitted by adapters."""

    adapter_type: str
    event_type: str
    data: Dict
    timestamp: str
    priority: int = 5


class AdapterBase(ABC):
    """Base class for all adapter implementations."""

    adapter_type: str = "base"
    enabled: bool = True

    def __init__(self, config, event_callback: Callable[[AdapterEvent], None]) -> None:
        self.config = config
        self.emit = event_callback
        self._running = False

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize resources; return True when ready."""

    @abstractmethod
    async def start(self) -> None:
        """Start the background collection loop."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop collection and release resources."""

    @abstractmethod
    async def get_current_state(self) -> Dict:
        """Return a snapshot of the current adapter state."""

    def is_available(self) -> bool:
        """Check if the adapter is supported on this platform."""
        return True

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
