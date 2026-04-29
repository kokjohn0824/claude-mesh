"""Persistent config: machine_id, ports, static peers."""
import json
import os
import re
import secrets
import socket
from typing import Any, Dict

from claude_mesh import paths

DEFAULT_PORT = 7432
DEFAULT_DISCOVERY_PORT = 7433


def _sanitise_hostname(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "-", name).strip("-") or "host"
    return cleaned[:32]


def _generate_machine_id() -> str:
    host = _sanitise_hostname(socket.gethostname())
    suffix = secrets.token_hex(2)
    return f"{host}-{suffix}"


def _default_config() -> Dict[str, Any]:
    return {
        "machine_id": _generate_machine_id(),
        "port": DEFAULT_PORT,
        "discovery_port": DEFAULT_DISCOVERY_PORT,
        "static_peers": [],
    }


def load() -> Dict[str, Any]:
    with open(paths.config_file()) as f:
        return json.load(f)


def save(cfg: Dict[str, Any]) -> None:
    paths.ensure_mesh_dir()
    with open(paths.config_file(), "w") as f:
        json.dump(cfg, f, indent=2)


def get_or_init() -> Dict[str, Any]:
    if os.path.exists(paths.config_file()):
        return load()
    cfg = _default_config()
    save(cfg)
    return cfg
