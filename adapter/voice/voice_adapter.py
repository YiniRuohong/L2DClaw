import asyncio
import logging
import tempfile
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Optional

import pyaudio

from adapter.base import AdapterBase, AdapterEvent
from adapter.voice.asr import WhisperASR
from adapter.voice.vad import VoiceActivityDetector

LOGGER = logging.getLogger(__name__)


class VoiceAdapter(AdapterBase):
    adapter_type = "voice"

    def __init__(self, config, event_callback: Callable[[AdapterEvent], None]) -> None:
        super().__init__(config, event_callback)
        asr_config = self._get_section(config, "asr")
        self._model_size = asr_config.get("model_size", "base")
        self._language = asr_config.get("language", "zh")
        self._vad_aggressiveness = asr_config.get("vad_aggressiveness", 2)
        self._callback: Optional[Callable[[str], None]] = None
        self._asr = WhisperASR(self._model_size, self._language)
        self._vad = VoiceActivityDetector(self._vad_aggressiveness)
        self._running = False
        self._last_speech: Optional[datetime] = None

        self._sample_rate = 16000
        self._frame_duration_ms = 30
        self._frames_per_buffer = int(self._sample_rate * self._frame_duration_ms / 1000)

    async def initialize(self) -> bool:
        self._asr.initialize()
        return True

    def set_callback(self, callback: Callable[[str], None]) -> None:
        self._callback = callback

    async def start(self) -> None:
        self._running = True
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self._sample_rate,
            input=True,
            frames_per_buffer=self._frames_per_buffer,
        )

        frames = []
        try:
            while self._running:
                data = stream.read(self._frames_per_buffer, exception_on_overflow=False)
                is_speech = self._vad.is_speech(data, self._sample_rate)
                if is_speech:
                    frames.append(data)
                elif frames:
                    text = await self._transcribe_frames(frames)
                    frames = []
                    if text:
                        self._emit_text(text)
                await asyncio.sleep(0)
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()

    async def stop(self) -> None:
        self._running = False

    async def get_current_state(self) -> Dict:
        if self._last_speech is None:
            return {"last_speech_ago_seconds": None}
        delta = datetime.now(timezone.utc) - self._last_speech
        return {"last_speech_ago_seconds": int(delta.total_seconds())}

    def _emit_text(self, text: str) -> None:
        event = AdapterEvent(
            adapter_type=self.adapter_type,
            event_type="speech",
            data={"text": text},
            timestamp=self._now_iso(),
            priority=9,
        )
        self._last_speech = datetime.now(timezone.utc)
        self.emit(event)
        if self._callback is not None:
            result = self._callback(text)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)

    async def _transcribe_frames(self, frames) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            path = Path(tmp.name)
        with wave.open(path.as_posix(), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self._sample_rate)
            wf.writeframes(b"".join(frames))

        try:
            return self._asr.transcribe(path.as_posix())
        finally:
            try:
                path.unlink()
            except OSError:
                LOGGER.warning("Failed to remove temp audio file: %s", path)

    def _get_section(self, config, name: str) -> Dict:
        if isinstance(config, dict):
            return config.get(name, {})
        return getattr(config, name, {}) or {}
