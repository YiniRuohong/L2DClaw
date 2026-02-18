import importlib
import logging
import os
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelSpec:
    hf_repo: str
    modelscope_repo: str
    local_path: str
    required_files: List[str]


class ModelDownloader:
    MODELS: Dict[str, ModelSpec] = {
        "qwen3-tts": ModelSpec(
            hf_repo="Qwen/Qwen3-TTS",
            modelscope_repo="Qwen/Qwen3-TTS",
            local_path="~/.l2dclaw/models/qwen3-tts",
            required_files=[
                "model.safetensors",
                "config.json",
                "tokenizer.json",
            ],
        )
    }

    def download(
        self,
        model_name: str,
        use_modelscope: bool = False,
        progress: Optional[Any] = None,
        task_id: Optional[int] = None,
    ) -> None:
        spec = self._get_spec(model_name)
        local_dir = Path(spec.local_path).expanduser()
        local_dir.mkdir(parents=True, exist_ok=True)

        if self.is_downloaded(model_name):
            LOGGER.info("Model already downloaded: %s", model_name)
            return

        if use_modelscope or not self._hf_reachable():
            self._download_modelscope(spec, progress, task_id)
            return

        self._download_huggingface(spec, progress, task_id)

    def verify(self, model_name: str) -> bool:
        spec = self._get_spec(model_name)
        local_dir = Path(spec.local_path).expanduser()
        for filename in spec.required_files:
            file_path = local_dir / filename
            if not file_path.exists() or file_path.stat().st_size == 0:
                return False
        return True

    def is_downloaded(self, model_name: str) -> bool:
        return self.verify(model_name)

    def _get_spec(self, model_name: str) -> ModelSpec:
        if model_name not in self.MODELS:
            raise ValueError(f"Unknown model: {model_name}")
        return self.MODELS[model_name]

    def _hf_reachable(self) -> bool:
        url = "https://huggingface.co"
        try:
            with urllib.request.urlopen(url, timeout=3):
                return True
        except Exception:
            LOGGER.info("Hugging Face not reachable within 3 seconds")
            return False

    def _download_huggingface(
        self,
        spec: ModelSpec,
        progress: Optional[Any],
        task_id: Optional[int],
    ) -> None:
        hf_hub_download, hf_hub_url, hf_error, get_metadata = self._load_hf_modules()
        total_size = self._hf_total_size(spec, hf_hub_url, get_metadata)
        self._init_progress(progress, task_id, total_size)

        for filename in spec.required_files:
            self._download_hf_file(
                spec.hf_repo,
                filename,
                spec.local_path,
                hf_hub_download,
                hf_error,
            )
            self._advance_progress(progress, task_id, spec, filename)

        if not self.verify_from_path(spec):
            raise RuntimeError("Download completed but verification failed")

    def _load_hf_modules(self) -> tuple[Any, Any, Any, Optional[Any]]:
        try:
            hf_module = importlib.import_module("huggingface_hub")
            utils_module = importlib.import_module("huggingface_hub.utils")
        except ImportError as exc:
            raise RuntimeError("huggingface_hub is required for model downloads") from exc

        hf_hub_download = getattr(hf_module, "hf_hub_download")
        hf_hub_url = getattr(hf_module, "hf_hub_url")
        hf_error = getattr(utils_module, "HfHubHTTPError", Exception)
        get_metadata = getattr(hf_module, "get_hf_file_metadata", None)
        return hf_hub_download, hf_hub_url, hf_error, get_metadata

    def _download_modelscope(
        self,
        spec: ModelSpec,
        progress: Optional[Any],
        task_id: Optional[int],
    ) -> None:
        total_units = len(spec.required_files)
        self._init_progress(progress, task_id, total_units)

        try:
            module = importlib.import_module("modelscope.hub.snapshot_download")
        except ImportError as exc:
            raise RuntimeError("modelscope is required for fallback downloads") from exc

        snapshot_download = getattr(module, "snapshot_download")
        snapshot_download(
            model_id=spec.modelscope_repo,
            local_dir=Path(spec.local_path).expanduser().as_posix(),
        )

        if not self.verify_from_path(spec):
            raise RuntimeError("ModelScope download failed verification")

        self._advance_progress(progress, task_id, spec, None, force_complete=True)

    def _download_hf_file(
        self,
        repo: str,
        filename: str,
        local_path: str,
        hf_hub_download: Any,
        hf_error: Any,
    ) -> None:
        retries = 3
        for attempt in range(retries):
            try:
                hf_hub_download(
                    repo_id=repo,
                    filename=filename,
                    local_dir=os.path.expanduser(local_path),
                    local_dir_use_symlinks=False,
                )
                return
            except hf_error:
                LOGGER.warning("HF download failed (%s), attempt %s", filename, attempt + 1)
                if attempt == retries - 1:
                    raise
                time.sleep(1 + attempt)

    def _hf_total_size(
        self,
        spec: ModelSpec,
        hf_hub_url: Any,
        get_hf_file_metadata: Optional[Any],
    ) -> Optional[int]:
        if get_hf_file_metadata is None:
            return None
        total = 0
        for filename in spec.required_files:
            try:
                url = hf_hub_url(spec.hf_repo, filename)
                metadata = get_hf_file_metadata(url)
                if metadata is None or metadata.size is None:
                    return None
                total += metadata.size
            except Exception:
                return None
        return total

    def _init_progress(
        self,
        progress: Optional[Any],
        task_id: Optional[int],
        total: Optional[int],
    ) -> None:
        if progress is None or task_id is None:
            return
        if total is None:
            progress.update(task_id, total=len(self.MODELS["qwen3-tts"].required_files))
        else:
            progress.update(task_id, total=total)

    def _advance_progress(
        self,
        progress: Optional[Any],
        task_id: Optional[int],
        spec: ModelSpec,
        filename: Optional[str],
        force_complete: bool = False,
    ) -> None:
        if progress is None or task_id is None:
            return

        if force_complete:
            progress.update(task_id, completed=progress.tasks[0].total)
            return

        if filename is None:
            progress.advance(task_id, 1)
            return

        file_path = Path(spec.local_path).expanduser() / filename
        if progress.tasks[0].total:
            progress.advance(task_id, file_path.stat().st_size)
        else:
            progress.advance(task_id, 1)

    def verify_from_path(self, spec: ModelSpec) -> bool:
        local_dir = Path(spec.local_path).expanduser()
        for filename in spec.required_files:
            file_path = local_dir / filename
            if not file_path.exists() or file_path.stat().st_size == 0:
                return False
        return True
