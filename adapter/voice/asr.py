import logging
from typing import Optional

LOGGER = logging.getLogger(__name__)


class WhisperASR:
    def __init__(self, model_size: str = "base", language: str = "zh") -> None:
        self._model_size = model_size
        self._language = language
        self._model = None

    def initialize(self) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("faster-whisper is required for ASR") from exc

        self._model = WhisperModel(self._model_size)

    def transcribe(self, audio_path: str) -> str:
        if self._model is None:
            raise RuntimeError("ASR model not initialized")

        segments, _info = self._model.transcribe(audio_path, language=self._language)
        return " ".join(segment.text for segment in segments)
