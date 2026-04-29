"""Centralised filesystem paths for claude-mesh."""
import os


def mesh_dir() -> str:
    override = os.environ.get("CLAUDE_MESH_DIR")
    if override:
        return override
    return os.path.join(os.environ["HOME"], ".claude", "mesh")


def config_file() -> str:
    return os.path.join(mesh_dir(), "config.json")


def peers_file() -> str:
    return os.path.join(mesh_dir(), "peers.json")


def conv_registry_file() -> str:
    return os.path.join(mesh_dir(), "conv_registry.json")


def inbox_log() -> str:
    return os.path.join(mesh_dir(), "inbox.log")


def ensure_mesh_dir() -> None:
    os.makedirs(mesh_dir(), exist_ok=True)
