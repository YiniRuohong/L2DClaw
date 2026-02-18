import base64
import io
import logging
from dataclasses import dataclass
from typing import Dict, Optional

LOGGER = logging.getLogger(__name__)


@dataclass
class ContentRecognizerConfig:
    content_recognition_enabled: bool = False
    content_recognition_mode: str = "ocr"
    capture_region: str = "active_window"


class ContentRecognizer:
    def __init__(self, config: ContentRecognizerConfig) -> None:
        self._config = config

    def capture_and_analyze(self) -> Optional[Dict]:
        if not self._config.content_recognition_enabled:
            return None

        screenshot = self._take_screenshot()
        if self._config.content_recognition_mode == "ocr":
            text = self._ocr(screenshot)
            return {"type": "ocr", "content": text[:500]}

        if self._config.content_recognition_mode == "vlm":
            b64 = self._compress_and_encode(screenshot)
            return {"type": "screenshot_b64", "content": b64}

        LOGGER.warning("Unknown content recognition mode: %s", self._config.content_recognition_mode)
        return None

    def _take_screenshot(self):
        import mss
        from PIL import Image

        with mss.mss() as sct:
            monitor = sct.monitors[0]
            image = sct.grab(monitor)
            return Image.frombytes("RGB", image.size, image.rgb)

    def _compress_and_encode(self, image) -> str:
        max_width = 1280
        max_height = 720
        width, height = image.size
        scale = min(max_width / width, max_height / height, 1.0)
        new_size = (int(width * scale), int(height * scale))
        resized = image.resize(new_size)

        buffer = io.BytesIO()
        resized.save(buffer, format="JPEG", quality=80)
        return base64.b64encode(buffer.getvalue()).decode("ascii")

    def _ocr(self, image) -> str:
        try:
            import easyocr
        except ImportError as exc:
            raise RuntimeError("easyocr is required for OCR mode") from exc

        reader = easyocr.Reader(["ch_sim", "en"], gpu=False)
        results = reader.readtext(image, detail=0)
        return " ".join(results)
