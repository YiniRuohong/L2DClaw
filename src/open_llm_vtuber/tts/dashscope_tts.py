"""DashScope Qwen TTS engine using DashScope SDK."""

import base64
from typing import Any

import requests
from loguru import logger

from .tts_interface import TTSInterface


class TTSEngine(TTSInterface):
    """Text-to-speech engine backed by DashScope Qwen TTS."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str = "qwen3-tts-flash",
        voice: str = "Cherry",
        language_type: str | None = None,
        stream: bool = False,
        file_extension: str = "wav",
    ) -> None:
        """Initialize the DashScope TTS engine.

        Args:
            api_key: DashScope API key.
            base_url: Base URL for DashScope API (e.g., https://dashscope.aliyuncs.com/api/v1).
            model: DashScope TTS model name.
            voice: Voice name to use for synthesis.
            language_type: Optional language hint (e.g., Chinese, English).
            stream: Whether to request streaming responses.
            file_extension: Output audio file extension (wav or mp3).
        """
        self.api_key = self._normalize_env_placeholder(api_key, "api_key") or ""
        self.base_url = self._normalize_env_placeholder(base_url, "base_url")
        if not self.base_url:
            self.base_url = "https://dashscope.aliyuncs.com/api/v1"
            logger.info(
                "DashScope TTS base_url not set; defaulting to %s.",
                self.base_url,
            )
        self.model = (
            self._normalize_env_placeholder(model, "model") or "qwen3-tts-flash"
        )
        self.voice = self._normalize_env_placeholder(voice, "voice") or "Cherry"
        self.language_type = self._normalize_env_placeholder(
            language_type, "language_type"
        )
        self.stream = stream
        self.file_extension = file_extension.lower()
        if self.file_extension not in {"wav", "mp3"}:
            logger.warning(
                "Unsupported file extension '%s' for DashScope TTS. Defaulting to wav.",
                self.file_extension,
            )
            self.file_extension = "wav"

    @staticmethod
    def _normalize_env_placeholder(value: str | None, label: str) -> str | None:
        """Normalize unresolved env placeholders in config values.

        Args:
            value: Raw config value.
            label: Field name for logging.

        Returns:
            Normalized value with unresolved placeholders replaced by None.
        """
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            if stripped.startswith("${") and stripped.endswith("}"):
                logger.warning(
                    "DashScope TTS config {} is an unresolved env placeholder; ignoring it.",
                    label,
                )
                return None
            return stripped
        return value

    def generate_audio(self, text: str, file_name_no_ext: str | None = None) -> str:
        """Generate speech audio using DashScope TTS.

        Args:
            text: Text to synthesize.
            file_name_no_ext: Optional cache file name without extension.

        Returns:
            Path to the generated audio file. Returns empty string on failure.
        """
        if not self.api_key:
            logger.error("DashScope API key is missing; cannot synthesize audio.")
            return ""
        if not text:
            logger.warning("DashScope TTS received empty text; skipping synthesis.")
            return ""

        cache_file = self.generate_cache_file_name(
            file_name_no_ext, file_extension=self.file_extension
        )

        try:
            import dashscope

            if self.base_url:
                dashscope.base_http_api_url = self.base_url

            request_kwargs = {
                "api_key": self.api_key,
                "model": self.model,
                "text": text,
                "voice": self.voice,
                "stream": self.stream,
            }
            if self.language_type:
                request_kwargs["language_type"] = self.language_type
            if self.stream:
                audio_bytes = self._stream_audio_bytes(dashscope, request_kwargs)
                if not audio_bytes:
                    return ""
                with open(cache_file, "wb") as handle:
                    handle.write(audio_bytes)
                logger.info("DashScope TTS audio saved to %s", cache_file)
                return cache_file

            response = self._call_tts(dashscope, request_kwargs)
            status_code = self._get_attr(response, "status_code")
            if isinstance(status_code, str) and status_code.isdigit():
                status_code = int(status_code)
            if status_code and status_code != 200:
                logger.error(
                    "DashScope TTS request failed. {}",
                    self._summarize_response(response),
                )
                self._log_response_details(response)
                return ""
            audio_bytes, audio_url = self._extract_audio_payload(response)
            if audio_bytes:
                with open(cache_file, "wb") as handle:
                    handle.write(audio_bytes)
                logger.info("DashScope TTS audio saved to %s", cache_file)
                return cache_file
            if audio_url:
                self._download_audio(audio_url, cache_file)
                logger.info("DashScope TTS audio saved to %s", cache_file)
                return cache_file

            logger.error(
                "DashScope TTS response missing audio URL or data. {}",
                self._summarize_response(response),
            )
            self._log_response_details(response)
            return ""
        except Exception as exc:
            logger.error("DashScope TTS failed: %s", exc)
            return ""

    def _call_tts(self, dashscope: Any, request_kwargs: dict[str, Any]) -> Any:
        """Call DashScope TTS API with a compatible interface.

        Args:
            dashscope: DashScope SDK module.
            request_kwargs: Request payload for DashScope SDK.

        Returns:
            Response object or generator from DashScope SDK.
        """
        audio_module = getattr(dashscope, "audio", None)
        qwen_tts = getattr(audio_module, "qwen_tts", None) if audio_module else None
        synthesizer = getattr(qwen_tts, "SpeechSynthesizer", None) if qwen_tts else None
        call_fn = getattr(synthesizer, "call", None) if synthesizer else None
        if callable(call_fn):
            return call_fn(**request_kwargs)
        return dashscope.MultiModalConversation.call(**request_kwargs)

    def _stream_audio_bytes(
        self, dashscope: Any, request_kwargs: dict[str, Any]
    ) -> bytes:
        """Stream audio bytes from DashScope when streaming is enabled.

        Args:
            dashscope: DashScope SDK module.
            request_kwargs: Request payload for DashScope SDK.

        Returns:
            Concatenated audio bytes, or empty bytes on failure.
        """
        audio_chunks: list[bytes] = []
        audio_url: str | None = None
        response = self._call_tts(dashscope, request_kwargs)
        for chunk in response:
            for candidate in self._iter_audio_candidates(chunk):
                audio_bytes, candidate_url = self._read_audio_candidate(candidate)
                if audio_bytes:
                    audio_chunks.append(audio_bytes)
                if candidate_url and not audio_url:
                    audio_url = candidate_url
        if audio_chunks:
            return b"".join(audio_chunks)
        if audio_url:
            return self._download_audio(audio_url, None)
        logger.error("DashScope TTS streaming returned no audio data or URL.")
        return b""

    def _extract_audio_payload(self, response: Any) -> tuple[bytes, str | None]:
        """Extract audio data or URL from DashScope response object.

        Args:
            response: Response object or dict from DashScope SDK.

        Returns:
            Tuple of (audio bytes, audio URL). Bytes may be empty if not provided.
        """
        for candidate in self._iter_audio_candidates(response):
            audio_bytes, audio_url = self._read_audio_candidate(candidate)
            if audio_bytes or audio_url:
                return audio_bytes, audio_url
        return b"", None

    def _iter_audio_candidates(self, response: Any) -> list[Any]:
        """Collect audio candidate payloads from response objects.

        Args:
            response: Response object or dict from DashScope SDK.

        Returns:
            List of candidate audio payloads to inspect.
        """
        candidates: list[Any] = []
        if response is None:
            return candidates
        for container in (response, self._get_attr(response, "output")):
            candidates.extend(self._collect_audio_candidates(container))
        return candidates

    def _collect_audio_candidates(self, container: Any) -> list[Any]:
        """Collect possible audio payloads from a container.

        Args:
            container: Object or dict that may hold audio payloads.

        Returns:
            Candidate audio payloads.
        """
        if container is None:
            return []
        if isinstance(container, (list, tuple)):
            return list(container)
        candidates: list[Any] = []
        if self._has_audio_fields(container):
            candidates.append(container)
        if isinstance(container, dict):
            for key in (
                "audio",
                "audios",
                "audio_list",
                "audioData",
                "audio_data",
                "audioUrl",
                "audio_url",
            ):
                if key in container and container[key] is not None:
                    value = container[key]
                    if key in {"audioData", "audio_data"}:
                        candidates.append({"data": value})
                    elif key in {"audioUrl", "audio_url"}:
                        candidates.append({"url": value})
                    else:
                        candidates.append(value)
            return candidates
        for attr in (
            "audio",
            "audios",
            "audio_list",
            "audioData",
            "audio_data",
            "audioUrl",
            "audio_url",
        ):
            value = getattr(container, attr, None)
            if value is None:
                continue
            if attr in {"audioData", "audio_data"}:
                candidates.append({"data": value})
            elif attr in {"audioUrl", "audio_url"}:
                candidates.append({"url": value})
            else:
                candidates.append(value)
        return candidates

    def _read_audio_candidate(self, candidate: Any) -> tuple[bytes, str | None]:
        """Read audio bytes or URL from a candidate payload.

        Args:
            candidate: Candidate audio payload.

        Returns:
            Tuple of (audio bytes, audio URL).
        """
        if candidate is None:
            return b"", None
        if isinstance(candidate, (list, tuple)):
            for item in candidate:
                audio_bytes, audio_url = self._read_audio_candidate(item)
                if audio_bytes or audio_url:
                    return audio_bytes, audio_url
            return b"", None
        if isinstance(candidate, str):
            if candidate.startswith("http://") or candidate.startswith("https://"):
                return b"", candidate
            decoded = self._decode_audio_data(candidate)
            if decoded:
                return decoded, None
            return b"", None
        data = self._get_attr(candidate, "data")
        if data is None:
            data = self._get_attr(candidate, "audio_data")
        url = self._get_attr(candidate, "url")
        if url is None:
            url = self._get_attr(candidate, "audio_url")
        if isinstance(data, bytes):
            return data, url
        if isinstance(data, str):
            decoded = self._decode_audio_data(data)
            return decoded, url
        return b"", url

    @staticmethod
    def _has_audio_fields(obj: Any) -> bool:
        """Check if an object looks like an audio payload container.

        Args:
            obj: Object or dict to inspect.

        Returns:
            True if audio-like fields are present.
        """
        if obj is None:
            return False
        if isinstance(obj, dict):
            return any(
                key in obj for key in ("data", "url", "audio", "audios", "audio_list")
            )
        return any(
            hasattr(obj, attr)
            for attr in ("data", "url", "audio", "audios", "audio_list")
        )

    @staticmethod
    def _decode_audio_data(data: str) -> bytes:
        """Decode base64 audio data safely.

        Args:
            data: Base64-encoded audio data.

        Returns:
            Decoded bytes or empty bytes on failure.
        """
        try:
            return base64.b64decode(data, validate=True)
        except Exception:
            return b""

    @staticmethod
    def _summarize_response(response: Any) -> str:
        """Summarize DashScope response for error logging.

        Args:
            response: Response object or dict from DashScope SDK.

        Returns:
            Short summary string for debugging.
        """
        if response is None:
            return "response=None"
        if isinstance(response, dict):
            keys = ", ".join(sorted(response.keys()))
            return f"response.keys=[{keys}]"
        response_type = type(response).__name__
        status = getattr(response, "status_code", None)
        code = getattr(response, "code", None)
        message = getattr(response, "message", None)
        return f"response.type={response_type}, status_code={status}, code={code}, message={message}"

    def _log_response_details(self, response: Any) -> None:
        """Log DashScope response details for debugging.

        Args:
            response: Response object or dict from DashScope SDK.
        """
        output = self._get_attr(response, "output")
        audio = self._get_attr(output, "audio") if output else None
        logger.error(
            "DashScope TTS response debug: {}",
            self._summarize_object("response", response),
        )
        logger.error(
            "DashScope TTS response debug: {}",
            self._summarize_object("output", output),
        )
        logger.error(
            "DashScope TTS response debug: {}",
            self._summarize_object("audio", audio),
        )

    @staticmethod
    def _summarize_object(name: str, obj: Any) -> str:
        """Summarize an object for debug logging.

        Args:
            name: Label for the object.
            obj: Object or dict to summarize.

        Returns:
            Summary string with key attributes.
        """
        if obj is None:
            return f"{name}=None"
        if isinstance(obj, dict):
            keys = ", ".join(sorted(obj.keys()))
            parts = [f"{name}.keys=[{keys}]"]
            for field in ("status_code", "code", "message", "request_id"):
                if field in obj:
                    parts.append(f"{field}={TTSEngine._safe_preview(obj[field])}")
            return ", ".join(parts)
        attrs = [
            "status_code",
            "code",
            "message",
            "request_id",
            "text",
            "data",
            "url",
            "audio",
            "output",
        ]
        parts = [f"{name}.type={type(obj).__name__}"]
        for attr in attrs:
            value = getattr(obj, attr, None)
            if value is not None:
                parts.append(f"{attr}={TTSEngine._safe_preview(value)}")
        return ", ".join(parts)

    @staticmethod
    def _safe_preview(value: Any) -> str:
        """Create a short, safe preview for logging.

        Args:
            value: Value to preview.

        Returns:
            Short preview string.
        """
        if value is None:
            return "None"
        if isinstance(value, bytes):
            return f"bytes(len={len(value)})"
        if isinstance(value, str):
            if len(value) <= 200:
                return value
            return f"{value[:200]}...<truncated>"
        if isinstance(value, dict):
            keys = ", ".join(sorted(value.keys()))
            return f"dict(keys=[{keys}])"
        if isinstance(value, list):
            return f"list(len={len(value)})"
        preview = repr(value)
        if len(preview) <= 200:
            return preview
        return f"{preview[:200]}...<truncated>"

    def _extract_audio_url(self, response: Any) -> str | None:
        """Extract audio URL from DashScope response object.

        Args:
            response: Response object or dict from DashScope SDK.

        Returns:
            Audio URL if present.
        """
        output = self._get_attr(response, "output")
        audio = self._get_attr(output, "audio") if output else None
        return self._get_attr(audio, "url") if audio else None

    @staticmethod
    def _get_attr(obj: Any, name: str) -> Any:
        """Fetch attribute or dict key from a response object.

        Args:
            obj: Object or dict to read from.
            name: Attribute/key name.

        Returns:
            Extracted value or None.
        """
        if obj is None:
            return None
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)

    @staticmethod
    def _download_audio(url: str, target_path: str | None) -> bytes:
        """Download audio content from the given URL.

        Args:
            url: Audio file URL.
            target_path: Optional path to save the audio file.

        Returns:
            Audio bytes.
        """
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        if target_path:
            with open(target_path, "wb") as handle:
                handle.write(response.content)
        return response.content
