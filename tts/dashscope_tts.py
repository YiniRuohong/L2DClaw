from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

from tts.base import TTSBase

LOGGER = logging.getLogger(__name__)


class DashscopeTTS(TTSBase):
    """DashScope cloud TTS fallback."""

    def __init__(self, config) -> None:
        tts_config = self._get_section(config, "tts")
        self._api_key = tts_config.get("dashscope_api_key")
        self._voice = tts_config.get("voice", "default")
        self._stop_event = asyncio.Event()

    async def speak(self, text: str) -> None:
        if not self.is_ready():
            raise RuntimeError("DashScope TTS not configured")
        self._stop_event.clear()
        audio_path, sample_rate = await asyncio.to_thread(self._synthesize, text)
        await self._play_audio(audio_path, sample_rate)

    def stop(self) -> None:
        self._stop_event.set()

    def is_ready(self) -> bool:
        return bool(self._api_key)

    def _synthesize(self, text: str) -> tuple[Path, int]:
        try:
            import dashscope
        except ImportError as exc:
            raise RuntimeError("dashscope is required for cloud TTS") from exc

        dashscope.api_key = self._api_key
        response = dashscope.audio.tts.v1(
            model="sambert-zh",
            text=text,
            voice=self._voice,
        )
        if response is None or "audio" not in response:
            raise RuntimeError("DashScope TTS response missing audio")

        audio_bytes = response["audio"]
        sample_rate = response.get("sample_rate", 16000)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            return Path(tmp.name), sample_rate

    async def _play_audio(self, audio_path: Path, sample_rate: int) -> None:
        try:
            import sounddevice as sd
            import soundfile as sf
        except ImportError as exc:
            raise RuntimeError("sounddevice and soundfile are required for playback") from exc

        data, sr = sf.read(audio_path)
        if sr != sample_rate:
            sample_rate = sr

        sd.play(data, samplerate=sample_rate)
        while sd.get_stream().active:
            if self._stop_event.is_set():
                sd.stop()
                break
            await asyncio.sleep(0.05)

        try:
            audio_path.unlink()
        except OSError:
            LOGGER.warning("Failed to delete temp TTS file: %s", audio_path)

    def _get_section(self, config, name: str) -> dict:
        if isinstance(config, dict):
            return config.get(name, {})
        return getattr(config, name, {}) or {}
