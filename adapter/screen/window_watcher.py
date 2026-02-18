import logging
import subprocess
import sys
from typing import Dict

import psutil

LOGGER = logging.getLogger(__name__)


def get_active_window_win() -> Dict:
    try:
        import win32gui
        import win32process
    except ImportError as exc:
        raise RuntimeError("pywin32 is required on Windows") from exc

    hwnd = win32gui.GetForegroundWindow()
    title = win32gui.GetWindowText(hwnd)
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    process = psutil.Process(pid).name() if pid else ""
    return {"title": title, "process": process}


def get_active_window_mac() -> Dict:
    script = (
        'tell application "System Events"\n'
        '    set frontApp to name of first application process whose frontmost is true\n'
        '    set frontWindow to ""\n'
        '    try\n'
        '        set frontWindow to name of front window of (first application process whose frontmost is true)\n'
        '    end try\n'
        '    return frontApp & "|" & frontWindow\n'
        'end tell\n'
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout.strip()
    if not output:
        return {"title": "", "process": ""}
    parts = output.split("|", 1)
    process = parts[0] if parts else ""
    title = parts[1] if len(parts) > 1 else ""
    return {"title": title, "process": process}


def get_active_window() -> Dict:
    if sys.platform == "win32":
        return get_active_window_win()
    if sys.platform == "darwin":
        return get_active_window_mac()
    raise NotImplementedError(f"Platform {sys.platform} not supported")
