import logging
from typing import Optional

LOGGER = logging.getLogger(__name__)


class VoiceActivityDetector:
    def __init__(self, aggressiveness: int = 2) -> None:
        self._aggressiveness = aggressiveness
        try:
            import webrtcvad
        except ImportError as exc:
            raise RuntimeError("webrtcvad is required for VAD") from exc
        self._vad = webrtcvad.Vad(aggressiveness)

    def is_speech(self, frame: bytes, sample_rate: int) -> bool:
        return self._vad.is_speech(frame, sample_rate)
