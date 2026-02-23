"""OpenAI API-based ASR implementation."""

import io
import wave

import numpy as np
from loguru import logger
from openai import OpenAI

from .asr_interface import ASRInterface


class VoiceRecognition(ASRInterface):
    """ASR implementation that calls the OpenAI Whisper API."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str = "whisper-1",
        lang: str | None = None,
        prompt: str | None = None,
    ) -> None:
        """Initialize the OpenAI API ASR client.

        Args:
            api_key: OpenAI API key.
            base_url: Optional API base URL for OpenAI-compatible endpoints.
            model: Whisper model name.
            lang: Optional language hint (e.g., "en", "zh").
            prompt: Optional prompt to guide transcription.
        """
        logger.info("Initializing OpenAI API ASR...")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.lang = lang
        self.prompt = prompt

    def transcribe_np(self, audio: np.ndarray) -> str:
        """Transcribe speech audio in numpy array format.

        Args:
            audio: The numpy array of the audio data to transcribe.

        Returns:
            str: The transcription result.
        """
        logger.info("Transcribing audio (OpenAI API ASR)...")

        audio = np.clip(audio, -1, 1)
        audio_integer = (audio * 32767).astype(np.int16)

        audio_buffer = io.BytesIO()
        with wave.open(audio_buffer, "wb") as wf:
            wf.setnchannels(self.NUM_CHANNELS)
            wf.setsampwidth(self.SAMPLE_WIDTH)
            wf.setframerate(self.SAMPLE_RATE)
            wf.writeframes(audio_integer.tobytes())

        audio_buffer.seek(0)

        request_kwargs: dict[str, object] = {
            "file": ("audio.wav", audio_buffer.read()),
            "model": self.model,
            "response_format": "text",
            "temperature": 0.0,
        }
        if self.lang:
            request_kwargs["language"] = self.lang
        if self.prompt:
            request_kwargs["prompt"] = self.prompt

        transcription = self.client.audio.transcriptions.create(**request_kwargs)
        return transcription
