from __future__ import annotations

from abc import abstractmethod
from typing import Dict

from adapter.base import AdapterBase


class HardwareAdapterBase(AdapterBase):
    """Base class for hardware adapters with connection lifecycle hooks."""

    adapter_type = "hardware_base"

    @abstractmethod
    async def connect(self) -> bool:
        """Establish a connection to the hardware device."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the hardware device."""

    @property
    @abstractmethod
    def device_info(self) -> Dict:
        """Return device metadata (name, vendor, type, firmware_version)."""
