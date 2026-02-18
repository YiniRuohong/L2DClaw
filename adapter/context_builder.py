from __future__ import annotations

from datetime import datetime
from typing import Dict


def build_context(adapter_snapshot: Dict) -> str:
    lines = []

    screen = adapter_snapshot.get("screen") or {}
    window = screen.get("active_window") or {}
    if window:
        title = window.get("title") or ""
        process = window.get("process") or ""
        if title or process:
            desc = " / ".join(part for part in [process, title] if part)
            lines.append(f"[桌面] 用户正在使用 {desc}")

    content = screen.get("content")
    if content and isinstance(content, dict):
        ctype = content.get("type")
        payload = content.get("content", "")
        if ctype == "ocr" and payload:
            lines.append(f"[屏幕内容] OCR 识别到: {payload}")
        elif ctype == "screenshot_b64":
            lines.append("[屏幕内容] 截图已采集")

    keyboard = adapter_snapshot.get("keyboard") or {}
    burst = keyboard.get("typing_burst")
    if isinstance(burst, int) and burst > 0:
        lines.append(f"[输入状态] 最近键盘输入 {burst} 次")

    voice = adapter_snapshot.get("voice") or {}
    last_speech = voice.get("last_speech_ago_seconds")
    if isinstance(last_speech, (int, float)):
        lines.append(f"[语音] 距离上次语音 {int(last_speech)} 秒")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"[时间] {now}")

    return "\n".join(lines)
