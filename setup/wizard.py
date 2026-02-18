import logging
import os
from pathlib import Path
from typing import Dict

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from setup.model_downloader import ModelDownloader

LOGGER = logging.getLogger(__name__)

PREFS_DIR = Path.home() / ".l2dclaw"
PREFS_FILE = PREFS_DIR / "user_prefs.yaml"
INIT_FLAG = PREFS_DIR / "initialized"
LICENSE_FILE = Path(__file__).with_name("license.txt")


class SetupWizard:
    def __init__(self) -> None:
        self.console = Console()
        self.downloader = ModelDownloader()

    def run(self) -> bool:
        self._render_header()
        if not self._accept_license():
            return False

        prefs = self._collect_preferences()
        if not self._confirm_tts_download():
            return False

        self._download_tts_model()
        self._write_prefs(prefs)
        self._write_init_flag()
        return True

    def _render_header(self) -> None:
        header = Text("欢迎使用 L2DClaw 桌宠", style="bold")
        self.console.print(Panel(header, expand=False))

    def _accept_license(self) -> bool:
        if not LICENSE_FILE.exists():
            self.console.print("Missing license.txt", style="bold red")
            return False

        with LICENSE_FILE.open("r", encoding="utf-8") as handle:
            text = handle.read()

        self.console.print(Panel(text, title="用户许可协议", expand=False))
        return self._require_yes("你是否同意以上许可协议？")

    def _require_yes(self, prompt: str) -> bool:
        while True:
            answer = input(f"{prompt} [y/N] > ").strip().lower()
            if answer in {"y", "yes"}:
                return True
            if answer in {"", "n", "no"}:
                return False
            self.console.print("请输入 y 或 n", style="yellow")

    def _require_confirm(self, prompt: str, default: bool) -> bool:
        suffix = "[Y/n]" if default else "[y/N]"
        while True:
            answer = input(f"{prompt} {suffix} > ").strip().lower()
            if not answer:
                return default
            if answer in {"y", "yes"}:
                return True
            if answer in {"n", "no"}:
                return False
            self.console.print("请输入 y 或 n", style="yellow")

    def _collect_preferences(self) -> Dict[str, Dict[str, object]]:
        self.console.print(Panel("功能配置", expand=False))

        screen_content = self._require_confirm(
            "[1] 屏幕画面内容识别（截图分析）默认关闭，开启？",
            default=False,
        )

        if screen_content:
            warn = (
                "截图将发送给 OpenClaw 云端进行分析，\n"
                "请确认你接受此隐私风险。"
            )
            self.console.print(Panel(warn, title="隐私提示", expand=False))
            if not self._require_confirm("确认开启截图功能？", default=False):
                screen_content = False

        keyboard_active = self._require_confirm(
            "[2] 键盘活跃度感知（只统计频率，不记录内容）默认开启，开启？",
            default=True,
        )

        voice_active = self._require_confirm(
            "[3] 麦克风语音识别 默认开启，开启？",
            default=True,
        )

        return {
            "screen": {
                "content_recognition_enabled": screen_content,
                "content_recognition_mode": "vlm" if screen_content else "ocr",
            },
            "keyboard": {"enabled": keyboard_active},
            "voice": {"enabled": voice_active},
        }

    def _confirm_tts_download(self) -> bool:
        message = (
            "L2DClaw 使用本地 Qwen3 TTS 模型进行语音合成。\n"
            "模型大小约 1.2GB，将下载到 ~/.l2dclaw/models/qwen3-tts/。"
        )
        self.console.print(Panel(message, title="TTS 语音合成模型", expand=False))
        return self._require_confirm("开始下载？", default=True)

    def _download_tts_model(self) -> None:
        progress = None
        task_id = None
        try:
            from rich.progress import Progress, BarColumn, DownloadColumn, TimeRemainingColumn

            progress = Progress(
                "正在下载 Qwen3 TTS 模型...",
                BarColumn(),
                DownloadColumn(),
                TimeRemainingColumn(),
            )
            progress.start()
            task_id = progress.add_task("download", total=0)
        except Exception:
            LOGGER.info("Rich progress not available; downloading without progress")

        try:
            self.downloader.download("qwen3-tts", progress=progress, task_id=task_id)
        finally:
            if progress is not None:
                progress.stop()

        self.console.print("✅ 下载完成！")

    def _write_prefs(self, prefs: Dict[str, Dict[str, object]]) -> None:
        PREFS_DIR.mkdir(parents=True, exist_ok=True)
        with PREFS_FILE.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(prefs, handle, allow_unicode=True)

    def _write_init_flag(self) -> None:
        INIT_FLAG.parent.mkdir(parents=True, exist_ok=True)
        INIT_FLAG.write_text("initialized", encoding="utf-8")
