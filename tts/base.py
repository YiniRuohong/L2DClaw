from __future__ import annotations

from abc import ABC, abstractmethod


class TTSBase(ABC):
    @abstractmethod
    async def speak(self, text: str) -> None:
        """Synthesize and play speech from text."""

    @abstractmethod
    def stop(self) -> None:
        """Stop any ongoing playback."""

    @abstractmethod
    def is_ready(self) -> bool:
        """Return True when the TTS backend is ready to serve."""
