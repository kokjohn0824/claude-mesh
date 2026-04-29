"""conversation_id ↔ local Claude session_id mapping, persisted."""
import json
import os
import threading
import time
from typing import Optional

from claude_mesh import paths

_LOCK = threading.Lock()


def _read() -> dict:
    if not os.path.exists(paths.conv_registry_file()):
        return {}
    try:
        with open(paths.conv_registry_file()) as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def _write(data: dict) -> None:
    paths.ensure_mesh_dir()
    tmp = paths.conv_registry_file() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, paths.conv_registry_file())


def set_conv(conv_id: str, peer_id: str, session_id: Optional[str], _now: Optional[int] = None) -> None:
    now = _now if _now is not None else int(time.time())
    with _LOCK:
        data = _read()
        data[conv_id] = {
            "local_session_id": session_id,
            "peer_id": peer_id,
            "created_at": now,
            "last_active": now,
            "status": "active",
        }
        _write(data)


def get(conv_id: str) -> Optional[dict]:
    return _read().get(conv_id)


def touch(conv_id: str, _now: Optional[int] = None) -> None:
    now = _now if _now is not None else int(time.time())
    with _LOCK:
        data = _read()
        if conv_id in data:
            data[conv_id]["last_active"] = now
            _write(data)


def attach_session(conv_id: str, session_id: str) -> None:
    with _LOCK:
        data = _read()
        if conv_id in data:
            data[conv_id]["local_session_id"] = session_id
            _write(data)


def close(conv_id: str) -> None:
    with _LOCK:
        data = _read()
        if conv_id in data:
            data[conv_id]["status"] = "closed"
            _write(data)
