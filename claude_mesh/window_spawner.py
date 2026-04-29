"""Open a foreground window running a command, per environment."""
import subprocess

SESSION_NAME = "claude-mesh"


def _spawn_tmux(title: str, command: str) -> None:
    subprocess.run(
        ["tmux", "new-window", "-t", SESSION_NAME, "-n", title, command],
        check=False,
    )


def _osascript(script: str) -> None:
    subprocess.run(["osascript", "-e", script], check=False)


def _spawn_iterm2(title: str, command: str) -> None:
    cmd = command.replace('"', '\\"')
    script = (
        'tell application "iTerm" '
        'to tell current window to create tab with default profile '
        f'and write text "{cmd}"'
    )
    _osascript(script)


def _spawn_terminal_app(title: str, command: str) -> None:
    cmd = command.replace('"', '\\"')
    script = f'tell application "Terminal" to do script "{cmd}"'
    _osascript(script)


def _spawn_screen(title: str, command: str) -> None:
    subprocess.run(
        ["screen", "-S", SESSION_NAME, "-X", "screen", "-t", title, "bash", "-lc", command],
        check=False,
    )


def _spawn_xterm(title: str, command: str) -> None:
    subprocess.Popen(["xterm", "-T", title, "-e", "bash", "-lc", command])


def spawn_window(env: str, title: str, command: str) -> None:
    if env == "tmux":
        _spawn_tmux(title, command)
    elif env == "iterm2":
        _spawn_iterm2(title, command)
    elif env == "terminal_app":
        _spawn_terminal_app(title, command)
    elif env == "screen":
        _spawn_screen(title, command)
    elif env == "xterm":
        _spawn_xterm(title, command)
    elif env == "headless":
        return
    else:
        raise ValueError(f"unknown env: {env}")
