"""Detect the best available windowing environment."""
import os
import shutil
import subprocess
import sys


def _iterm2_running() -> bool:
    if sys.platform != "darwin":
        return False
    try:
        result = subprocess.run(
            ["pgrep", "-x", "iTerm2"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=1.0,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def detect() -> str:
    if shutil.which("tmux"):
        return "tmux"
    if sys.platform == "darwin":
        return "iterm2" if _iterm2_running() else "terminal_app"
    if shutil.which("screen"):
        return "screen"
    if os.environ.get("DISPLAY") and shutil.which("xterm"):
        return "xterm"
    return "headless"
