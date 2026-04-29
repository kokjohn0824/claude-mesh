"""Run `claude -p` to execute a mesh task and parse its output."""
import json
import re
import subprocess
from dataclasses import dataclass
from typing import Optional

NEEDS_HUMAN_RE = re.compile(r"<<NEEDS_HUMAN:\s*(.*?)>>", re.DOTALL)


class TaskError(RuntimeError):
    """Raised when `claude` exits non-zero or emits unparseable output."""


@dataclass
class TaskResult:
    session_id: str
    payload: str
    needs_human: bool
    escalation_reason: Optional[str]


def _build_argv(prompt: str, session_id: Optional[str]) -> list:
    argv = ["claude", "-p", "--output-format", "json"]
    if session_id:
        argv.extend(["--resume", session_id])
    argv.append(prompt)
    return argv


def run_task(prompt: str, session_id: Optional[str], timeout: Optional[float] = None) -> TaskResult:
    argv = _build_argv(prompt, session_id)
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as e:
        raise TaskError(f"`claude` CLI not found: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise TaskError(f"task timed out after {timeout}s") from e
    if proc.returncode != 0:
        raise TaskError(f"claude exited {proc.returncode}: {proc.stderr.strip()}")
    try:
        body = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise TaskError(f"claude output was not JSON: {e}") from e
    sid = body.get("session_id") or ""
    payload = body.get("result", "")
    match = NEEDS_HUMAN_RE.search(payload)
    needs_human = match is not None
    reason = match.group(1).strip() if match else None
    return TaskResult(
        session_id=sid,
        payload=payload,
        needs_human=needs_human,
        escalation_reason=reason,
    )
