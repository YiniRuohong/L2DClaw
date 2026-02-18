from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import numpy as np

from tts.base import TTSBase

LOGGER = logging.getLogger(__name__)


class LocalQwen3TTS(TTSBase):
    """Local Qwen3-TTS inference using transformers backend."""

    def __init__(self, config) -> None:
        self._model_path = Path.home() / ".l2dclaw" / "models" / "qwen3-tts"
        self._device = self._detect_device()
        self._model = None
        self._processor = None
        self._stop_event = asyncio.Event()
        tts_config = self._get_section(config, "tts")
        self._voice = tts_config.get("voice", "default")

    def _detect_device(self) -> str:
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("torch is required for local TTS") from exc

        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    async def initialize(self) -> bool:
        try:
            from transformers import AutoModel, AutoProcessor
        except ImportError as exc:
            raise RuntimeError("transformers is required for local TTS") from exc

        if not self._model_path.exists():
            LOGGER.warning("Local Qwen3-TTS model not found at %s", self._model_path)
            return False

        self._processor = AutoProcessor.from_pretrained(self._model_path.as_posix())
        self._model = AutoModel.from_pretrained(self._model_path.as_posix()).to(self._device)
        return True

    async def speak(self, text: str) -> None:
        if not self.is_ready():
            raise RuntimeError("Local TTS not initialized")
        self._stop_event.clear()
        audio, sample_rate = await asyncio.to_thread(self._synthesize, text)
        await self._play_audio(audio, sample_rate)

    def stop(self) -> None:
        self._stop_event.set()

    def is_ready(self) -> bool:
        return self._model is not None and self._processor is not None

    def _synthesize(self, text: str) -> tuple[np.ndarray, int]:
        if self._model is None or self._processor is None:
            raise RuntimeError("Local TTS not initialized")

        inputs = self._processor(text, return_tensors="pt")
        inputs = {key: value.to(self._device) for key, value in inputs.items()}
        output = self._model.generate(**inputs)
        audio = output.cpu().numpy().squeeze()
        return audio, 22050

    async def _play_audio(self, audio: np.ndarray, sample_rate: int) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("sounddevice is required for audio playback") from exc

        sd.play(audio, samplerate=sample_rate)
        while sd.get_stream().active:
            if self._stop_event.is_set():
                sd.stop()
                break
            await asyncio.sleep(0.05)

    def _get_section(self, config, name: str) -> dict:
        if isinstance(config, dict):
            return config.get(name, {})
        return getattr(config, name, {}) or {}
