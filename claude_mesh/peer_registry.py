"""Discovered peers registry, persisted to peers.json."""
import json
import os
import threading
import time
from typing import Dict, List, Optional

from claude_mesh import paths

_LOCK = threading.Lock()

OFFLINE_AFTER_SECONDS = 90


def _read() -> Dict[str, dict]:
    if not os.path.exists(paths.peers_file()):
        return {}
    try:
        with open(paths.peers_file()) as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def _write(data: Dict[str, dict]) -> None:
    paths.ensure_mesh_dir()
    tmp = paths.peers_file() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, paths.peers_file())


def record(peer_id: str, ip: str, port: int, ts: Optional[int] = None) -> None:
    if ts is None:
        ts = int(time.time())
    with _LOCK:
        data = _read()
        data[peer_id] = {"ip": ip, "port": port, "last_seen": ts}
        _write(data)


def list_all() -> List[dict]:
    out = []
    for pid, info in _read().items():
        out.append({"id": pid, **info})
    return out


def get(peer_id: str) -> Optional[dict]:
    info = _read().get(peer_id)
    if info is None:
        return None
    return {"id": peer_id, **info}


def online() -> List[dict]:
    now = int(time.time())
    return [p for p in list_all() if now - p["last_seen"] <= OFFLINE_AFTER_SECONDS]
