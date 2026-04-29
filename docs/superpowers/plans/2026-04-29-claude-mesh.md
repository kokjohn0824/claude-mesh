# Claude Mesh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a P2P Claude Code skill that lets any machine on a LAN dispatch tasks to and converse with Claude Code instances on peer machines, with auto-discovery, session continuity, and human-in-the-loop escalation.

**Architecture:** Python 3 stdlib-only daemon (`listener.py`) per machine that runs an HTTP server on port 7432 (message I/O), a UDP broadcaster/receiver on port 7433 (peer discovery), spawns `claude -p` subprocesses for incoming tasks, and escalates to a foreground tmux/terminal window when Claude emits a `<<NEEDS_HUMAN: ...>>` sentinel. A CLI client (`client.py`) sends task/reply messages to peers. Conversation continuity is maintained via `claude --resume <session_id>` keyed on a per-conversation UUID. A skill bootstrap script installs the directory layout, generates a stable `machine_id`, detects the terminal environment (tmux → iTerm2 → Terminal.app → screen → xterm → headless), and starts the daemon.

**Tech Stack:** Python 3.9+ (stdlib only — `http.server`, `socketserver`, `socket`, `subprocess`, `threading`, `json`, `uuid`, `argparse`, `unittest`); tmux / iTerm2 AppleScript / `osascript` / GNU `screen` / xterm for window management; `claude` CLI for task execution.

---

## File Structure

Runtime code (stdlib only):

```
claude-mesh/
├── claude_mesh/
│   ├── __init__.py
│   ├── paths.py              # XDG paths under ~/.claude/mesh/
│   ├── config.py             # config.json load/save, machine_id generation
│   ├── protocol.py           # Message dataclass, serialize/parse, validation
│   ├── peer_registry.py     # peers.json: add/update/list/mark_offline
│   ├── conv_registry.py     # conv_registry.json: get/set session_id per conversation
│   ├── discovery.py          # UDP broadcaster + UDP listener thread
│   ├── http_server.py        # HTTP server thread receiving messages on :7432
│   ├── http_client.py        # send_message() POST helper
│   ├── terminal_env.py       # detect tmux/iTerm2/Terminal/screen/xterm/headless
│   ├── window_spawner.py    # open new window per env; signature is uniform
│   ├── task_executor.py      # run `claude -p` (or --resume), parse NEEDS_HUMAN
│   ├── listener.py           # main daemon: wires all of the above
│   └── client.py             # CLI: send task/reply/list-peers
├── skill/
│   ├── SKILL.md              # Claude Code skill manifest
│   └── activate.sh           # bootstrap: dirs + config + tmux + start daemon
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_protocol.py
│   ├── test_peer_registry.py
│   ├── test_conv_registry.py
│   ├── test_discovery.py
│   ├── test_http_server.py
│   ├── test_http_client.py
│   ├── test_terminal_env.py
│   ├── test_window_spawner.py
│   ├── test_task_executor.py
│   └── test_listener.py
├── README.md
└── .gitignore
```

Each module owns one responsibility. `listener.py` is the only module that wires multiple modules together — every other module is independently testable.

Runtime files placed by `activate.sh` at first run:

```
~/.claude/mesh/
├── config.json          # machine_id, port, discovery_port, static_peers
├── peers.json           # discovered peers (auto-updated)
├── conv_registry.json   # conversation_id → local_session_id
└── inbox.log            # append-only message log (headless fallback)
```

---

## Conventions for all tasks

- All commands are run from the repo root (`/Users/alexchang/dev/claude-mesh/`) unless stated otherwise.
- Test runner: `python -m unittest tests.<module> -v` (no pytest dep — keeps stdlib-only philosophy in CI too).
- Each task ends with a commit. Use Conventional Commits (`feat:`, `test:`, `refactor:`, `chore:`).
- Networking tests bind to `127.0.0.1` and ephemeral ports (port 0) to avoid collisions.
- Do **not** run the daemon on the dev machine while tests run — port 7432 may already be bound.

---

## Task 0: Project bootstrap

**Files:**
- Create: `/Users/alexchang/dev/claude-mesh/.gitignore`
- Create: `/Users/alexchang/dev/claude-mesh/README.md`
- Create: `/Users/alexchang/dev/claude-mesh/claude_mesh/__init__.py`
- Create: `/Users/alexchang/dev/claude-mesh/tests/__init__.py`

- [ ] **Step 1: Initialise git**

```bash
cd /Users/alexchang/dev/claude-mesh
git init
git config user.email "claude@anthropic.local" 2>/dev/null || true
```

- [ ] **Step 2: Write `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
.venv/
*.egg-info/
.DS_Store
```

- [ ] **Step 3: Write `README.md`**

```markdown
# Claude Mesh

P2P Claude Code skill for cross-machine task dispatch and dialogue on a LAN.
See `docs/superpowers/plans/2026-04-29-claude-mesh.md` for the implementation plan,
and `Projects/claude-mesh-design.md` (in Obsidian) for the full design.

## Quick start (after install)

    bash skill/activate.sh

Run tests:

    python -m unittest discover tests -v
```

- [ ] **Step 4: Create empty package files**

`claude_mesh/__init__.py`:
```python
"""Claude Mesh — P2P Claude Code coordination."""
__version__ = "1.0.0"
```

`tests/__init__.py`: empty file.

- [ ] **Step 5: Verify Python version available**

Run: `python3 --version`
Expected: `Python 3.9.x` or newer.

- [ ] **Step 6: Commit**

```bash
git add .gitignore README.md claude_mesh/__init__.py tests/__init__.py
git commit -m "chore: bootstrap claude-mesh project structure"
```

---

## Task 1: Paths module

**Files:**
- Create: `claude_mesh/paths.py`
- Test: `tests/test_paths.py`

Centralises every filesystem path so tests can monkeypatch a temp dir.

- [ ] **Step 1: Write the failing test**

`tests/test_paths.py`:
```python
import os
import tempfile
import unittest
from unittest import mock

from claude_mesh import paths


class TestPaths(unittest.TestCase):
    def test_mesh_dir_defaults_to_home(self):
        with mock.patch.dict(os.environ, {"HOME": "/tmp/fakehome"}, clear=False):
            self.assertEqual(paths.mesh_dir(), "/tmp/fakehome/.claude/mesh")

    def test_mesh_dir_honours_override_env(self):
        with mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": "/tmp/m"}):
            self.assertEqual(paths.mesh_dir(), "/tmp/m")

    def test_named_files_under_mesh_dir(self):
        with mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": "/tmp/m"}):
            self.assertEqual(paths.config_file(), "/tmp/m/config.json")
            self.assertEqual(paths.peers_file(), "/tmp/m/peers.json")
            self.assertEqual(paths.conv_registry_file(), "/tmp/m/conv_registry.json")
            self.assertEqual(paths.inbox_log(), "/tmp/m/inbox.log")

    def test_ensure_mesh_dir_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "sub", "mesh")
            with mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": target}):
                paths.ensure_mesh_dir()
                self.assertTrue(os.path.isdir(target))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `python -m unittest tests.test_paths -v`
Expected: `ModuleNotFoundError: No module named 'claude_mesh.paths'`.

- [ ] **Step 3: Implement `paths.py`**

```python
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
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m unittest tests.test_paths -v`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add claude_mesh/paths.py tests/test_paths.py
git commit -m "feat: paths module for mesh dir resolution"
```

---

## Task 2: Config module

**Files:**
- Create: `claude_mesh/config.py`
- Test: `tests/test_config.py`

Generates `machine_id` (`hostname-XXXX`), persists `config.json`, exposes `load()`/`save()`/`get_or_init()`.

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
import json
import os
import tempfile
import unittest
from unittest import mock

from claude_mesh import config


class TestConfig(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._env = mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": self._tmp.name})
        self._env.start()
        self.addCleanup(self._env.stop)

    def test_get_or_init_creates_default_config(self):
        cfg = config.get_or_init()
        self.assertEqual(cfg["port"], 7432)
        self.assertEqual(cfg["discovery_port"], 7433)
        self.assertEqual(cfg["static_peers"], [])
        self.assertRegex(cfg["machine_id"], r"^[a-zA-Z0-9._-]+-[a-f0-9]{4}$")

    def test_get_or_init_persists_to_disk(self):
        cfg = config.get_or_init()
        with open(os.path.join(self._tmp.name, "config.json")) as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk, cfg)

    def test_get_or_init_idempotent(self):
        first = config.get_or_init()
        second = config.get_or_init()
        self.assertEqual(first["machine_id"], second["machine_id"])

    def test_save_then_load_roundtrip(self):
        config.save({"machine_id": "x-0000", "port": 7432, "discovery_port": 7433, "static_peers": []})
        loaded = config.load()
        self.assertEqual(loaded["machine_id"], "x-0000")

    def test_machine_id_uses_hostname(self):
        with mock.patch("socket.gethostname", return_value="alex-mac"):
            cfg = config.get_or_init()
        self.assertTrue(cfg["machine_id"].startswith("alex-mac-"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `python -m unittest tests.test_config -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `config.py`**

```python
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
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m unittest tests.test_config -v`
Expected: 5 pass.

- [ ] **Step 5: Commit**

```bash
git add claude_mesh/config.py tests/test_config.py
git commit -m "feat: config with persistent machine_id and ports"
```

---

## Task 3: Protocol module

**Files:**
- Create: `claude_mesh/protocol.py`
- Test: `tests/test_protocol.py`

`Message` dataclass + `serialize` / `parse` / `validate` for the JSON wire format defined in the design doc.

- [ ] **Step 1: Write the failing test**

`tests/test_protocol.py`:
```python
import json
import unittest

from claude_mesh import protocol


class TestProtocol(unittest.TestCase):
    def test_message_dataclass_fields(self):
        m = protocol.Message(
            from_id="alex-mac",
            from_ip="192.168.1.10",
            conversation_id="conv-1",
            session_id=None,
            type="task",
            payload="hello",
            needs_human=False,
            timestamp=1700000000,
        )
        self.assertEqual(m.type, "task")
        self.assertIsNone(m.session_id)

    def test_serialize_includes_mesh_version(self):
        m = protocol.Message(
            from_id="a", from_ip="1.1.1.1", conversation_id="c",
            session_id="s", type="reply", payload="ok",
            needs_human=False, timestamp=1,
        )
        body = json.loads(protocol.serialize(m))
        self.assertEqual(body["mesh_version"], "1.0")
        self.assertEqual(body["type"], "reply")
        self.assertEqual(body["session_id"], "s")

    def test_parse_round_trip(self):
        m = protocol.Message(
            from_id="a", from_ip="1.1.1.1", conversation_id="c",
            session_id=None, type="task", payload="p",
            needs_human=False, timestamp=2,
        )
        parsed = protocol.parse(protocol.serialize(m))
        self.assertEqual(parsed, m)

    def test_parse_rejects_unknown_type(self):
        bad = json.dumps({
            "mesh_version": "1.0", "from_id": "a", "from_ip": "1.1.1.1",
            "conversation_id": "c", "session_id": None, "type": "bogus",
            "payload": "p", "needs_human": False, "timestamp": 1,
        })
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse(bad)

    def test_parse_rejects_wrong_version(self):
        bad = json.dumps({
            "mesh_version": "9.9", "from_id": "a", "from_ip": "1.1.1.1",
            "conversation_id": "c", "session_id": None, "type": "task",
            "payload": "p", "needs_human": False, "timestamp": 1,
        })
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse(bad)

    def test_parse_rejects_missing_field(self):
        bad = json.dumps({"mesh_version": "1.0", "type": "task"})
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse(bad)

    def test_new_message_fills_timestamp(self):
        m = protocol.new_message(
            from_id="a", from_ip="1.1.1.1",
            conversation_id="c", session_id=None,
            msg_type="task", payload="p",
        )
        self.assertGreater(m.timestamp, 0)
        self.assertFalse(m.needs_human)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `python -m unittest tests.test_protocol -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `protocol.py`**

```python
"""Wire-format Message dataclass and (de)serializer."""
import json
import time
from dataclasses import asdict, dataclass
from typing import Optional

MESH_VERSION = "1.0"
ALLOWED_TYPES = {"task", "reply", "heartbeat", "escalate"}


class ProtocolError(ValueError):
    """Raised for malformed or incompatible mesh messages."""


@dataclass(frozen=True)
class Message:
    from_id: str
    from_ip: str
    conversation_id: str
    session_id: Optional[str]
    type: str
    payload: str
    needs_human: bool
    timestamp: int


def new_message(
    from_id: str,
    from_ip: str,
    conversation_id: str,
    session_id: Optional[str],
    msg_type: str,
    payload: str,
    needs_human: bool = False,
) -> Message:
    if msg_type not in ALLOWED_TYPES:
        raise ProtocolError(f"unknown type: {msg_type}")
    return Message(
        from_id=from_id,
        from_ip=from_ip,
        conversation_id=conversation_id,
        session_id=session_id,
        type=msg_type,
        payload=payload,
        needs_human=needs_human,
        timestamp=int(time.time()),
    )


def serialize(m: Message) -> str:
    body = {"mesh_version": MESH_VERSION, **asdict(m)}
    return json.dumps(body)


_REQUIRED = ["from_id", "from_ip", "conversation_id", "session_id",
             "type", "payload", "needs_human", "timestamp"]


def parse(raw: str) -> Message:
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProtocolError(f"invalid JSON: {e}") from e
    if body.get("mesh_version") != MESH_VERSION:
        raise ProtocolError(f"version mismatch: {body.get('mesh_version')}")
    for key in _REQUIRED:
        if key not in body:
            raise ProtocolError(f"missing field: {key}")
    if body["type"] not in ALLOWED_TYPES:
        raise ProtocolError(f"unknown type: {body['type']}")
    return Message(
        from_id=body["from_id"],
        from_ip=body["from_ip"],
        conversation_id=body["conversation_id"],
        session_id=body["session_id"],
        type=body["type"],
        payload=body["payload"],
        needs_human=bool(body["needs_human"]),
        timestamp=int(body["timestamp"]),
    )
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m unittest tests.test_protocol -v`
Expected: 7 pass.

- [ ] **Step 5: Commit**

```bash
git add claude_mesh/protocol.py tests/test_protocol.py
git commit -m "feat: wire protocol Message dataclass and (de)serializer"
```

---

## Task 4: Peer registry

**Files:**
- Create: `claude_mesh/peer_registry.py`
- Test: `tests/test_peer_registry.py`

Stores discovered peers with `last_seen` timestamps. Heartbeats older than `OFFLINE_AFTER_SECONDS` (90s) flip a peer to offline.

- [ ] **Step 1: Write the failing test**

`tests/test_peer_registry.py`:
```python
import json
import os
import tempfile
import time
import unittest
from unittest import mock

from claude_mesh import peer_registry


class TestPeerRegistry(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        p = mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)

    def test_record_then_list_returns_peer(self):
        peer_registry.record("alex-mac", "192.168.1.10", port=7432, ts=1000)
        peers = peer_registry.list_all()
        self.assertEqual(len(peers), 1)
        self.assertEqual(peers[0]["id"], "alex-mac")
        self.assertEqual(peers[0]["ip"], "192.168.1.10")
        self.assertEqual(peers[0]["port"], 7432)
        self.assertEqual(peers[0]["last_seen"], 1000)

    def test_record_updates_last_seen(self):
        peer_registry.record("a", "1.1.1.1", port=7432, ts=1000)
        peer_registry.record("a", "1.1.1.1", port=7432, ts=2000)
        peers = peer_registry.list_all()
        self.assertEqual(len(peers), 1)
        self.assertEqual(peers[0]["last_seen"], 2000)

    def test_record_updates_ip_change(self):
        peer_registry.record("a", "1.1.1.1", port=7432, ts=1000)
        peer_registry.record("a", "2.2.2.2", port=7432, ts=2000)
        peers = peer_registry.list_all()
        self.assertEqual(peers[0]["ip"], "2.2.2.2")

    def test_online_filters_by_freshness(self):
        peer_registry.record("fresh", "1.1.1.1", port=7432, ts=int(time.time()))
        peer_registry.record("stale", "1.1.1.2", port=7432, ts=1)
        online = peer_registry.online()
        ids = [p["id"] for p in online]
        self.assertIn("fresh", ids)
        self.assertNotIn("stale", ids)

    def test_get_returns_none_for_unknown(self):
        self.assertIsNone(peer_registry.get("nobody"))

    def test_persists_across_calls(self):
        peer_registry.record("a", "1.1.1.1", port=7432, ts=1)
        with open(os.path.join(self._tmp.name, "peers.json")) as f:
            data = json.load(f)
        self.assertIn("a", data)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m unittest tests.test_peer_registry -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `peer_registry.py`**

```python
"""Discovered peers registry, persisted to peers.json."""
import json
import os
import time
from typing import Dict, List, Optional

from claude_mesh import paths

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
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m unittest tests.test_peer_registry -v`
Expected: 6 pass.

- [ ] **Step 5: Commit**

```bash
git add claude_mesh/peer_registry.py tests/test_peer_registry.py
git commit -m "feat: peer registry with online/offline tracking"
```

---

## Task 5: Conversation registry

**Files:**
- Create: `claude_mesh/conv_registry.py`
- Test: `tests/test_conv_registry.py`

Maps `conversation_id` → `{local_session_id, peer_id, created_at, last_active, status}`.

- [ ] **Step 1: Write the failing test**

`tests/test_conv_registry.py`:
```python
import os
import tempfile
import unittest
from unittest import mock

from claude_mesh import conv_registry


class TestConvRegistry(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        p = mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)

    def test_get_unknown_returns_none(self):
        self.assertIsNone(conv_registry.get("missing"))

    def test_set_then_get(self):
        conv_registry.set_conv("c1", peer_id="alex", session_id="s-1")
        rec = conv_registry.get("c1")
        self.assertEqual(rec["local_session_id"], "s-1")
        self.assertEqual(rec["peer_id"], "alex")
        self.assertEqual(rec["status"], "active")
        self.assertGreater(rec["created_at"], 0)
        self.assertGreaterEqual(rec["last_active"], rec["created_at"])

    def test_touch_updates_last_active(self):
        conv_registry.set_conv("c1", peer_id="alex", session_id=None, _now=1000)
        conv_registry.touch("c1", _now=2000)
        rec = conv_registry.get("c1")
        self.assertEqual(rec["last_active"], 2000)
        self.assertEqual(rec["created_at"], 1000)

    def test_attach_session_id_after_first_run(self):
        conv_registry.set_conv("c1", peer_id="alex", session_id=None)
        conv_registry.attach_session("c1", "s-2")
        self.assertEqual(conv_registry.get("c1")["local_session_id"], "s-2")

    def test_close_marks_status(self):
        conv_registry.set_conv("c1", peer_id="alex", session_id="s-1")
        conv_registry.close("c1")
        self.assertEqual(conv_registry.get("c1")["status"], "closed")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m unittest tests.test_conv_registry -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `conv_registry.py`**

```python
"""conversation_id ↔ local Claude session_id mapping, persisted."""
import json
import os
import time
from typing import Optional

from claude_mesh import paths


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
    data = _read()
    if conv_id in data:
        data[conv_id]["last_active"] = now
        _write(data)


def attach_session(conv_id: str, session_id: str) -> None:
    data = _read()
    if conv_id in data:
        data[conv_id]["local_session_id"] = session_id
        _write(data)


def close(conv_id: str) -> None:
    data = _read()
    if conv_id in data:
        data[conv_id]["status"] = "closed"
        _write(data)
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m unittest tests.test_conv_registry -v`
Expected: 5 pass.

- [ ] **Step 5: Commit**

```bash
git add claude_mesh/conv_registry.py tests/test_conv_registry.py
git commit -m "feat: conversation registry mapping conv_id to session_id"
```

---

## Task 6: HTTP client (send_message)

**Files:**
- Create: `claude_mesh/http_client.py`
- Test: `tests/test_http_client.py`

Tiny stdlib `urllib.request` wrapper that POSTs a serialized `Message` and returns the parsed reply (or raises on non-2xx). The test uses a real `http.server.BaseHTTPRequestHandler` on a random port — no mocks of `urllib`.

- [ ] **Step 1: Write the failing test**

`tests/test_http_client.py`:
```python
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from claude_mesh import http_client, protocol


class _Handler(BaseHTTPRequestHandler):
    received = []  # class-level capture

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length).decode()
        self.__class__.received.append((self.path, body))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def log_message(self, *_):
        pass


class TestHTTPClient(unittest.TestCase):
    def setUp(self):
        _Handler.received = []
        self.srv = HTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def test_send_posts_to_messages_endpoint(self):
        msg = protocol.new_message(
            from_id="a", from_ip="1.1.1.1",
            conversation_id="c", session_id=None,
            msg_type="task", payload="hi",
        )
        resp = http_client.send_message("127.0.0.1", self.port, msg, timeout=2.0)
        self.assertEqual(resp, {"ok": True})
        self.assertEqual(len(_Handler.received), 1)
        path, body = _Handler.received[0]
        self.assertEqual(path, "/messages")
        roundtrip = protocol.parse(body)
        self.assertEqual(roundtrip.payload, "hi")

    def test_raises_on_unreachable(self):
        # Bind to a closed port: shut server down first.
        self.srv.shutdown()
        self.srv.server_close()
        msg = protocol.new_message(
            from_id="a", from_ip="1.1.1.1",
            conversation_id="c", session_id=None,
            msg_type="task", payload="hi",
        )
        with self.assertRaises(http_client.SendError):
            http_client.send_message("127.0.0.1", self.port, msg, timeout=0.5)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m unittest tests.test_http_client -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `http_client.py`**

```python
"""Stdlib HTTP POST client for mesh messages."""
import json
import urllib.error
import urllib.request

from claude_mesh import protocol

ENDPOINT_PATH = "/messages"


class SendError(RuntimeError):
    """Raised when a peer is unreachable or returns a non-2xx response."""


def send_message(ip: str, port: int, msg: protocol.Message, timeout: float = 5.0) -> dict:
    url = f"http://{ip}:{port}{ENDPOINT_PATH}"
    data = protocol.serialize(msg).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            if not body:
                return {}
            return json.loads(body)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ConnectionError) as e:
        raise SendError(f"failed to POST to {url}: {e}") from e
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m unittest tests.test_http_client -v`
Expected: 2 pass.

- [ ] **Step 5: Commit**

```bash
git add claude_mesh/http_client.py tests/test_http_client.py
git commit -m "feat: HTTP client for posting mesh messages to peers"
```

---

## Task 7: HTTP server

**Files:**
- Create: `claude_mesh/http_server.py`
- Test: `tests/test_http_server.py`

Threaded HTTP server bound to `0.0.0.0:<port>`. Routes `POST /messages` → invokes a caller-supplied `on_message(Message) -> dict | None` handler. Returns 200 with handler's dict (or `{}`) on success, 400 on parse error.

- [ ] **Step 1: Write the failing test**

`tests/test_http_server.py`:
```python
import json
import threading
import time
import unittest
import urllib.request

from claude_mesh import http_server, protocol


class TestHTTPServer(unittest.TestCase):
    def test_post_invokes_handler_and_returns_200(self):
        received = []

        def on_message(m):
            received.append(m)
            return {"ack": True}

        server = http_server.start("127.0.0.1", 0, on_message)
        try:
            port = server.server_address[1]
            msg = protocol.new_message(
                from_id="a", from_ip="1.1.1.1",
                conversation_id="c", session_id=None,
                msg_type="task", payload="hi",
            )
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/messages",
                data=protocol.serialize(msg).encode(),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                self.assertEqual(resp.status, 200)
                body = json.loads(resp.read().decode())
            self.assertEqual(body, {"ack": True})
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0].payload, "hi")
        finally:
            http_server.stop(server)

    def test_post_with_bad_json_returns_400(self):
        server = http_server.start("127.0.0.1", 0, lambda m: {})
        try:
            port = server.server_address[1]
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/messages",
                data=b"not json",
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            try:
                urllib.request.urlopen(req, timeout=2)
                self.fail("expected HTTP 400")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 400)
        finally:
            http_server.stop(server)

    def test_unknown_path_returns_404(self):
        server = http_server.start("127.0.0.1", 0, lambda m: {})
        try:
            port = server.server_address[1]
            req = urllib.request.Request(f"http://127.0.0.1:{port}/nope", method="POST", data=b"{}")
            try:
                urllib.request.urlopen(req, timeout=2)
                self.fail("expected HTTP 404")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 404)
        finally:
            http_server.stop(server)


if __name__ == "__main__":
    unittest.main()
```

> Need `import urllib.error` — add to test imports.

Update test imports section:
```python
import urllib.error
import urllib.request
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m unittest tests.test_http_server -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `http_server.py`**

```python
"""Threaded HTTP server receiving mesh messages on POST /messages."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional

from claude_mesh import protocol

OnMessage = Callable[[protocol.Message], Optional[dict]]


def _make_handler(on_message: OnMessage):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/messages":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            try:
                msg = protocol.parse(raw)
            except protocol.ProtocolError as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
                return
            try:
                result = on_message(msg) or {}
            except Exception as e:  # handler crash → 500
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        def log_message(self, *_):
            pass  # silence default stderr logging

    return Handler


def start(host: str, port: int, on_message: OnMessage) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), _make_handler(on_message))
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="mesh-http")
    thread.start()
    server._mesh_thread = thread  # type: ignore[attr-defined]
    return server


def stop(server: ThreadingHTTPServer) -> None:
    server.shutdown()
    server.server_close()
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m unittest tests.test_http_server -v`
Expected: 3 pass.

- [ ] **Step 5: Commit**

```bash
git add claude_mesh/http_server.py tests/test_http_server.py
git commit -m "feat: threaded HTTP server for receiving mesh messages"
```

---

## Task 8: UDP discovery (broadcaster + receiver)

**Files:**
- Create: `claude_mesh/discovery.py`
- Test: `tests/test_discovery.py`

A `Broadcaster` periodically sends a heartbeat datagram. A `Receiver` listens, parses, and updates `peer_registry`. Tests bind broadcaster + receiver to `127.0.0.1` on the loopback (using `SO_BROADCAST` is not required for loopback unicast — design uses `255.255.255.255` in production, but tests target `127.0.0.1`).

> Implementation note: in production the broadcaster uses `255.255.255.255` and `SO_BROADCAST=1`. Both tests pass an explicit `target` to inject a different address. Keep the production default as a constant `BROADCAST_ADDR = "255.255.255.255"`.

- [ ] **Step 1: Write the failing test**

`tests/test_discovery.py`:
```python
import json
import os
import socket
import tempfile
import time
import unittest
from unittest import mock

from claude_mesh import discovery, peer_registry, protocol


class TestDiscovery(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        p = mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)

    def test_make_heartbeat_payload_contains_machine_info(self):
        body = discovery.make_heartbeat_bytes(
            machine_id="alex-mac", ip="192.168.1.10", http_port=7432
        )
        parsed = json.loads(body.decode())
        self.assertEqual(parsed["mesh_version"], protocol.MESH_VERSION)
        self.assertEqual(parsed["from_id"], "alex-mac")
        self.assertEqual(parsed["from_ip"], "192.168.1.10")
        self.assertEqual(parsed["http_port"], 7432)
        self.assertEqual(parsed["type"], "heartbeat")

    def test_receiver_records_incoming_heartbeat_into_peer_registry(self):
        # Bind receiver on loopback ephemeral port.
        rsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rsock.bind(("127.0.0.1", 0))
        rport = rsock.getsockname()[1]
        receiver = discovery.Receiver(sock=rsock)
        receiver.start()
        try:
            ssock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            payload = discovery.make_heartbeat_bytes("peer-1", "127.0.0.1", 7432)
            ssock.sendto(payload, ("127.0.0.1", rport))
            ssock.close()

            deadline = time.time() + 2.0
            while time.time() < deadline:
                if peer_registry.get("peer-1"):
                    break
                time.sleep(0.05)
            rec = peer_registry.get("peer-1")
            self.assertIsNotNone(rec)
            self.assertEqual(rec["ip"], "127.0.0.1")
            self.assertEqual(rec["port"], 7432)
        finally:
            receiver.stop()

    def test_broadcaster_sends_one_heartbeat_per_tick(self):
        rsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rsock.bind(("127.0.0.1", 0))
        rport = rsock.getsockname()[1]
        rsock.settimeout(2.0)

        b = discovery.Broadcaster(
            machine_id="me", get_ip=lambda: "127.0.0.1",
            http_port=7432, target=("127.0.0.1", rport), interval=0.1,
        )
        b.start()
        try:
            data, _ = rsock.recvfrom(4096)
            payload = json.loads(data.decode())
            self.assertEqual(payload["from_id"], "me")
        finally:
            b.stop()
            rsock.close()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m unittest tests.test_discovery -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `discovery.py`**

```python
"""UDP heartbeat broadcaster and receiver for peer discovery."""
import json
import socket
import threading
import time
from typing import Callable, Optional, Tuple

from claude_mesh import peer_registry, protocol

BROADCAST_ADDR = "255.255.255.255"
DEFAULT_INTERVAL = 30.0  # seconds


def make_heartbeat_bytes(machine_id: str, ip: str, http_port: int) -> bytes:
    body = {
        "mesh_version": protocol.MESH_VERSION,
        "from_id": machine_id,
        "from_ip": ip,
        "type": "heartbeat",
        "http_port": http_port,
        "timestamp": int(time.time()),
    }
    return json.dumps(body).encode("utf-8")


class Broadcaster:
    def __init__(
        self,
        machine_id: str,
        get_ip: Callable[[], str],
        http_port: int,
        target: Tuple[str, int],
        interval: float = DEFAULT_INTERVAL,
    ):
        self.machine_id = machine_id
        self.get_ip = get_ip
        self.http_port = http_port
        self.target = target
        self.interval = interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="mesh-broadcast")
        self._thread.start()

    def _run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            while not self._stop.is_set():
                payload = make_heartbeat_bytes(self.machine_id, self.get_ip(), self.http_port)
                try:
                    sock.sendto(payload, self.target)
                except OSError:
                    pass
                self._stop.wait(self.interval)
        finally:
            sock.close()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)


class Receiver:
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.sock.settimeout(0.2)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @classmethod
    def bound(cls, host: str, port: int) -> "Receiver":
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        return cls(sock=s)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="mesh-discover")
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                body = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if body.get("type") != "heartbeat":
                continue
            if body.get("mesh_version") != protocol.MESH_VERSION:
                continue
            peer_id = body.get("from_id")
            ip = body.get("from_ip") or addr[0]
            port = int(body.get("http_port", 7432))
            if peer_id:
                peer_registry.record(peer_id, ip, port=port)

    def stop(self) -> None:
        self._stop.set()
        try:
            self.sock.close()
        except OSError:
            pass
        if self._thread:
            self._thread.join(timeout=2.0)
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m unittest tests.test_discovery -v`
Expected: 3 pass.

- [ ] **Step 5: Commit**

```bash
git add claude_mesh/discovery.py tests/test_discovery.py
git commit -m "feat: UDP broadcaster and receiver for peer discovery"
```

---

## Task 9: Terminal environment detection

**Files:**
- Create: `claude_mesh/terminal_env.py`
- Test: `tests/test_terminal_env.py`

Returns one of: `"tmux" | "iterm2" | "terminal_app" | "screen" | "xterm" | "headless"`. Detection order matches the design doc.

- [ ] **Step 1: Write the failing test**

`tests/test_terminal_env.py`:
```python
import unittest
from unittest import mock

from claude_mesh import terminal_env


class TestTerminalEnv(unittest.TestCase):
    def test_prefers_tmux_when_available(self):
        with mock.patch("shutil.which", side_effect=lambda c: "/x/tmux" if c == "tmux" else None), \
             mock.patch("sys.platform", "darwin"):
            self.assertEqual(terminal_env.detect(), "tmux")

    def test_macos_iterm2_when_no_tmux_and_iterm_running(self):
        which_map = {"tmux": None, "screen": None}
        with mock.patch("shutil.which", side_effect=lambda c: which_map.get(c, None)), \
             mock.patch("sys.platform", "darwin"), \
             mock.patch.object(terminal_env, "_iterm2_running", return_value=True):
            self.assertEqual(terminal_env.detect(), "iterm2")

    def test_macos_terminal_app_when_no_tmux_no_iterm(self):
        with mock.patch("shutil.which", return_value=None), \
             mock.patch("sys.platform", "darwin"), \
             mock.patch.object(terminal_env, "_iterm2_running", return_value=False):
            self.assertEqual(terminal_env.detect(), "terminal_app")

    def test_linux_screen_when_no_tmux(self):
        which_map = {"tmux": None, "screen": "/x/screen"}
        with mock.patch("shutil.which", side_effect=lambda c: which_map.get(c, None)), \
             mock.patch("sys.platform", "linux"), \
             mock.patch.dict("os.environ", {"DISPLAY": ":0"}, clear=True):
            self.assertEqual(terminal_env.detect(), "screen")

    def test_linux_xterm_with_display_no_tmux_no_screen(self):
        with mock.patch("shutil.which", side_effect=lambda c: "/x/xterm" if c == "xterm" else None), \
             mock.patch("sys.platform", "linux"), \
             mock.patch.dict("os.environ", {"DISPLAY": ":0"}, clear=True):
            self.assertEqual(terminal_env.detect(), "xterm")

    def test_linux_headless_when_nothing_available(self):
        with mock.patch("shutil.which", return_value=None), \
             mock.patch("sys.platform", "linux"), \
             mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(terminal_env.detect(), "headless")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m unittest tests.test_terminal_env -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `terminal_env.py`**

```python
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
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m unittest tests.test_terminal_env -v`
Expected: 6 pass.

- [ ] **Step 5: Commit**

```bash
git add claude_mesh/terminal_env.py tests/test_terminal_env.py
git commit -m "feat: terminal environment detection with platform fallbacks"
```

---

## Task 10: Window spawner

**Files:**
- Create: `claude_mesh/window_spawner.py`
- Test: `tests/test_window_spawner.py`

`spawn_window(env, title, command)` — opens a foreground window in the given environment running `command`. Returns immediately. For `headless`, returns without spawning (caller falls back to `inbox.log`). All shell-outs go through `subprocess.run` so we can mock with `unittest.mock.patch`.

- [ ] **Step 1: Write the failing test**

`tests/test_window_spawner.py`:
```python
import unittest
from unittest import mock

from claude_mesh import window_spawner


class TestWindowSpawner(unittest.TestCase):
    def test_tmux_spawns_new_window_in_session(self):
        with mock.patch("subprocess.run") as run:
            run.return_value.returncode = 0
            window_spawner.spawn_window("tmux", title="task-1", command="claude --resume abc")
            args = run.call_args_list[0].args[0]
            self.assertEqual(args[0], "tmux")
            self.assertIn("new-window", args)
            self.assertIn("-t", args)
            self.assertIn("claude-mesh", args)
            self.assertIn("-n", args)
            self.assertIn("task-1", args)
            self.assertIn("claude --resume abc", args)

    def test_iterm2_uses_osascript(self):
        with mock.patch("subprocess.run") as run:
            run.return_value.returncode = 0
            window_spawner.spawn_window("iterm2", title="t", command="echo hi")
            args = run.call_args_list[0].args[0]
            self.assertEqual(args[0], "osascript")
            self.assertIn("-e", args)
            joined = " ".join(args)
            self.assertIn("iTerm", joined)
            self.assertIn("echo hi", joined)

    def test_terminal_app_uses_osascript(self):
        with mock.patch("subprocess.run") as run:
            run.return_value.returncode = 0
            window_spawner.spawn_window("terminal_app", title="t", command="echo hi")
            args = run.call_args_list[0].args[0]
            self.assertEqual(args[0], "osascript")
            joined = " ".join(args)
            self.assertIn("Terminal", joined)

    def test_screen_uses_screen_command(self):
        with mock.patch("subprocess.run") as run:
            run.return_value.returncode = 0
            window_spawner.spawn_window("screen", title="t", command="echo hi")
            args = run.call_args_list[0].args[0]
            self.assertEqual(args[0], "screen")
            self.assertIn("-S", args)
            self.assertIn("claude-mesh", args)

    def test_xterm_spawns_xterm(self):
        with mock.patch("subprocess.Popen") as popen:
            window_spawner.spawn_window("xterm", title="t", command="echo hi")
            args = popen.call_args.args[0]
            self.assertEqual(args[0], "xterm")
            self.assertIn("-T", args)
            self.assertIn("t", args)

    def test_headless_is_a_noop(self):
        with mock.patch("subprocess.run") as run, mock.patch("subprocess.Popen") as popen:
            window_spawner.spawn_window("headless", title="t", command="echo hi")
            run.assert_not_called()
            popen.assert_not_called()

    def test_unknown_env_raises(self):
        with self.assertRaises(ValueError):
            window_spawner.spawn_window("magic", title="t", command="echo hi")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m unittest tests.test_window_spawner -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `window_spawner.py`**

```python
"""Open a foreground window running a command, per environment."""
import shlex
import subprocess

SESSION_NAME = "claude-mesh"


def _ensure_tmux_session() -> None:
    subprocess.run(
        ["tmux", "has-session", "-t", SESSION_NAME],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
    )


def _spawn_tmux(title: str, command: str) -> None:
    _ensure_tmux_session()
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
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m unittest tests.test_window_spawner -v`
Expected: 7 pass.

- [ ] **Step 5: Commit**

```bash
git add claude_mesh/window_spawner.py tests/test_window_spawner.py
git commit -m "feat: window spawner for tmux/iterm2/terminal/screen/xterm/headless"
```

---

## Task 11: Task executor (`claude -p`)

**Files:**
- Create: `claude_mesh/task_executor.py`
- Test: `tests/test_task_executor.py`

`run_task(prompt, session_id=None)` invokes `claude -p <prompt>` (or `claude --resume <session_id> -p <prompt>`), captures stdout, parses out:
- `local_session_id` — Claude prints `Session ID: <uuid>` on stderr or via `--print-session-id` flag (we use the simpler approach: tail-grep a marker).
- `needs_human` — `True` iff stdout contains `<<NEEDS_HUMAN: ...>>`.
- `payload` — the cleaned response text.

> Implementation choice: To keep this stdlib-only and avoid coupling to undocumented `claude` flags, the executor uses `claude -p --output-format=json <prompt>` which returns `{"session_id": "...", "result": "..."}` (per public Claude Code CLI). Tests stub `subprocess.run` to return that JSON.

- [ ] **Step 1: Write the failing test**

`tests/test_task_executor.py`:
```python
import json
import subprocess
import unittest
from unittest import mock

from claude_mesh import task_executor


def _completed(stdout: str, returncode: int = 0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


class TestTaskExecutor(unittest.TestCase):
    def test_run_task_new_session_invokes_claude_with_p_flag(self):
        out = json.dumps({"session_id": "sess-1", "result": "hello back"})
        with mock.patch("subprocess.run", return_value=_completed(out)) as run:
            res = task_executor.run_task("hi", session_id=None)
            args = run.call_args.args[0]
            self.assertEqual(args[0], "claude")
            self.assertIn("-p", args)
            self.assertIn("--output-format", args)
            self.assertIn("json", args)
            self.assertNotIn("--resume", args)
        self.assertEqual(res.session_id, "sess-1")
        self.assertEqual(res.payload, "hello back")
        self.assertFalse(res.needs_human)

    def test_run_task_resumes_existing_session(self):
        out = json.dumps({"session_id": "sess-1", "result": "ok"})
        with mock.patch("subprocess.run", return_value=_completed(out)) as run:
            task_executor.run_task("again", session_id="sess-1")
            args = run.call_args.args[0]
            self.assertIn("--resume", args)
            idx = args.index("--resume")
            self.assertEqual(args[idx + 1], "sess-1")

    def test_run_task_detects_needs_human_marker(self):
        out = json.dumps({
            "session_id": "sess-1",
            "result": "I started but <<NEEDS_HUMAN: please confirm production deploy>> halt",
        })
        with mock.patch("subprocess.run", return_value=_completed(out)):
            res = task_executor.run_task("deploy", session_id=None)
        self.assertTrue(res.needs_human)
        self.assertIn("please confirm production deploy", res.escalation_reason)

    def test_run_task_raises_on_nonzero_exit(self):
        with mock.patch("subprocess.run", return_value=_completed("err", returncode=2)):
            with self.assertRaises(task_executor.TaskError):
                task_executor.run_task("hi", session_id=None)

    def test_run_task_raises_on_invalid_json(self):
        with mock.patch("subprocess.run", return_value=_completed("not json")):
            with self.assertRaises(task_executor.TaskError):
                task_executor.run_task("hi", session_id=None)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m unittest tests.test_task_executor -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `task_executor.py`**

```python
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
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m unittest tests.test_task_executor -v`
Expected: 5 pass.

- [ ] **Step 5: Commit**

```bash
git add claude_mesh/task_executor.py tests/test_task_executor.py
git commit -m "feat: task executor wrapping `claude -p` with NEEDS_HUMAN detection"
```

---

## Task 12: Listener daemon — wiring

**Files:**
- Create: `claude_mesh/listener.py`
- Test: `tests/test_listener.py`

`Listener` class wires HTTP server, UDP receiver, UDP broadcaster, peer registry, conv registry, task executor, and window spawner together. The single message handler dispatches by `message.type`:

- `task` → look up/create conv, run task in background thread, post `reply` back to sender; if `needs_human`, also call `window_spawner.spawn_window(env, title, "claude --resume <sid>")`.
- `reply` → log into `inbox.log`; future enhancement could feed it back to the local Claude that initiated the task.
- `escalate` → spawn window with `claude --resume <sid>` if a session exists; otherwise log.
- `heartbeat` → ignore (UDP path handles peers).

Tests focus on the dispatcher (`Listener.handle_message`) and post-task reply path. `task_executor.run_task` and `http_client.send_message` are mocked.

- [ ] **Step 1: Write the failing test**

`tests/test_listener.py`:
```python
import os
import tempfile
import threading
import time
import unittest
from unittest import mock

from claude_mesh import (conv_registry, listener, peer_registry, protocol,
                         task_executor)


def _make_msg(**overrides):
    base = dict(
        from_id="alex-mac", from_ip="192.168.1.10",
        conversation_id="conv-1", session_id=None,
        msg_type="task", payload="say hi",
    )
    base.update(overrides)
    return protocol.new_message(**base)


class TestListener(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        p = mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)

        # Register the sender as a known peer so reply-routing works.
        peer_registry.record("alex-mac", "192.168.1.10", port=7432, ts=int(time.time()))

    def _make_listener(self, **kwargs):
        defaults = dict(
            machine_id="bob-linux",
            local_ip="192.168.1.11",
            http_port=7432,
            terminal_env="tmux",
        )
        defaults.update(kwargs)
        return listener.Listener(**defaults)

    def test_task_runs_executor_and_posts_reply_back(self):
        l = self._make_listener()
        result = task_executor.TaskResult(
            session_id="sess-x", payload="done", needs_human=False, escalation_reason=None,
        )
        with mock.patch.object(listener.task_executor, "run_task", return_value=result) as run, \
             mock.patch.object(listener.http_client, "send_message") as send:
            l.handle_message(_make_msg())
            l.wait_idle(timeout=2.0)
        run.assert_called_once()
        # Reply was POSTed back to the sender's IP.
        send.assert_called_once()
        ip, port, msg = send.call_args.args[:3]
        self.assertEqual(ip, "192.168.1.10")
        self.assertEqual(port, 7432)
        self.assertEqual(msg.type, "reply")
        self.assertEqual(msg.payload, "done")
        self.assertEqual(msg.session_id, "sess-x")
        # conv_registry recorded the new session.
        rec = conv_registry.get("conv-1")
        self.assertEqual(rec["local_session_id"], "sess-x")

    def test_task_with_needs_human_spawns_window(self):
        l = self._make_listener()
        result = task_executor.TaskResult(
            session_id="sess-y", payload="<<NEEDS_HUMAN: confirm>>",
            needs_human=True, escalation_reason="confirm",
        )
        with mock.patch.object(listener.task_executor, "run_task", return_value=result), \
             mock.patch.object(listener.http_client, "send_message"), \
             mock.patch.object(listener.window_spawner, "spawn_window") as spawn:
            l.handle_message(_make_msg())
            l.wait_idle(timeout=2.0)
        spawn.assert_called_once()
        env, title, command = spawn.call_args.kwargs.get("env"), spawn.call_args.kwargs.get("title"), spawn.call_args.kwargs.get("command")
        # Support either kwargs or positional.
        if env is None:
            env, title, command = spawn.call_args.args
        self.assertEqual(env, "tmux")
        self.assertIn("conv-1", title)
        self.assertIn("--resume", command)
        self.assertIn("sess-y", command)

    def test_task_resumes_existing_session_when_known(self):
        conv_registry.set_conv("conv-1", peer_id="alex-mac", session_id="sess-prev")
        l = self._make_listener()
        result = task_executor.TaskResult(
            session_id="sess-prev", payload="ok", needs_human=False, escalation_reason=None,
        )
        with mock.patch.object(listener.task_executor, "run_task", return_value=result) as run, \
             mock.patch.object(listener.http_client, "send_message"):
            l.handle_message(_make_msg(session_id="sess-prev"))
            l.wait_idle(timeout=2.0)
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs.get("session_id"), "sess-prev")

    def test_reply_appends_to_inbox_log(self):
        l = self._make_listener()
        l.handle_message(_make_msg(msg_type="reply", payload="result text"))
        log_path = os.path.join(self._tmp.name, "inbox.log")
        self.assertTrue(os.path.exists(log_path))
        with open(log_path) as f:
            self.assertIn("result text", f.read())

    def test_unknown_peer_reply_target_is_logged_not_crashed(self):
        l = self._make_listener()
        msg = _make_msg(from_id="ghost", from_ip="10.0.0.99")
        result = task_executor.TaskResult(
            session_id="s", payload="ok", needs_human=False, escalation_reason=None,
        )
        with mock.patch.object(listener.task_executor, "run_task", return_value=result), \
             mock.patch.object(listener.http_client, "send_message", side_effect=listener.http_client.SendError("nope")):
            # Should not raise.
            l.handle_message(msg)
            l.wait_idle(timeout=2.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m unittest tests.test_listener -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `listener.py`**

```python
"""Listener daemon: wires HTTP, UDP, task executor, and window spawner."""
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from claude_mesh import (config, conv_registry, discovery, http_client,
                         http_server, paths, peer_registry, protocol,
                         task_executor, terminal_env, window_spawner)

DISCOVERY_PORT = 7433
TASK_WORKERS = 4


def _append_inbox(line: str) -> None:
    paths.ensure_mesh_dir()
    with open(paths.inbox_log(), "a") as f:
        f.write(line.rstrip() + "\n")


class Listener:
    def __init__(
        self,
        machine_id: str,
        local_ip: str,
        http_port: int,
        terminal_env: str,
    ):
        self.machine_id = machine_id
        self.local_ip = local_ip
        self.http_port = http_port
        self.terminal_env = terminal_env
        self._executor = ThreadPoolExecutor(max_workers=TASK_WORKERS, thread_name_prefix="mesh-task")
        self._inflight = 0
        self._inflight_lock = threading.Lock()
        self._idle = threading.Event()
        self._idle.set()

    # --- inflight tracking so tests can wait for background work ----------
    def _inc_inflight(self) -> None:
        with self._inflight_lock:
            self._inflight += 1
            self._idle.clear()

    def _dec_inflight(self) -> None:
        with self._inflight_lock:
            self._inflight -= 1
            if self._inflight == 0:
                self._idle.set()

    def wait_idle(self, timeout: float) -> bool:
        return self._idle.wait(timeout=timeout)

    # --- message dispatch -------------------------------------------------
    def handle_message(self, msg: protocol.Message) -> dict:
        _append_inbox(f"[{int(time.time())}] {msg.type} from {msg.from_id}: {msg.payload[:200]}")
        if msg.type == "task":
            self._inc_inflight()
            self._executor.submit(self._handle_task, msg)
            return {"accepted": True}
        if msg.type == "reply":
            return {"accepted": True}
        if msg.type == "escalate":
            self._spawn_for_conv(msg.conversation_id, msg.session_id, reason=msg.payload)
            return {"accepted": True}
        return {"accepted": False, "reason": "unknown type"}

    def _handle_task(self, msg: protocol.Message) -> None:
        try:
            existing = conv_registry.get(msg.conversation_id)
            session_id: Optional[str] = msg.session_id or (existing["local_session_id"] if existing else None)
            if existing is None:
                conv_registry.set_conv(msg.conversation_id, peer_id=msg.from_id, session_id=session_id)
            else:
                conv_registry.touch(msg.conversation_id)

            try:
                result = task_executor.run_task(msg.payload, session_id=session_id)
            except task_executor.TaskError as e:
                self._post_reply(msg, payload=f"[mesh: task failed] {e}", session_id=session_id, needs_human=False)
                return

            if result.session_id:
                conv_registry.attach_session(msg.conversation_id, result.session_id)

            if result.needs_human:
                self._spawn_for_conv(msg.conversation_id, result.session_id, reason=result.escalation_reason or "")

            self._post_reply(msg, payload=result.payload, session_id=result.session_id, needs_human=result.needs_human)
        finally:
            self._dec_inflight()

    def _post_reply(self, original: protocol.Message, payload: str, session_id: Optional[str], needs_human: bool) -> None:
        peer = peer_registry.get(original.from_id)
        if peer is None:
            _append_inbox(f"[mesh] cannot reply to unknown peer {original.from_id}")
            return
        reply = protocol.new_message(
            from_id=self.machine_id,
            from_ip=self.local_ip,
            conversation_id=original.conversation_id,
            session_id=session_id,
            msg_type="reply",
            payload=payload,
            needs_human=needs_human,
        )
        try:
            http_client.send_message(peer["ip"], peer["port"], reply, timeout=10.0)
        except http_client.SendError as e:
            _append_inbox(f"[mesh] send_reply failed: {e}")

    def _spawn_for_conv(self, conv_id: str, session_id: Optional[str], reason: str) -> None:
        if not session_id:
            _append_inbox(f"[mesh] escalate requested but no session for {conv_id}: {reason}")
            return
        title = f"mesh-{conv_id[:8]}"
        command = f"claude --resume {session_id}"
        try:
            window_spawner.spawn_window(self.terminal_env, title, command)
        except Exception as e:  # noqa: BLE001
            _append_inbox(f"[mesh] spawn_window failed: {e}")


# --- top-level daemon entry --------------------------------------------------

def serve_forever() -> None:
    paths.ensure_mesh_dir()
    cfg = config.get_or_init()
    env = terminal_env.detect()
    local_ip = _detect_local_ip()

    listener = Listener(
        machine_id=cfg["machine_id"],
        local_ip=local_ip,
        http_port=cfg["port"],
        terminal_env=env,
    )

    server = http_server.start("0.0.0.0", cfg["port"], listener.handle_message)
    receiver = discovery.Receiver.bound("0.0.0.0", cfg["discovery_port"])
    receiver.start()
    broadcaster = discovery.Broadcaster(
        machine_id=cfg["machine_id"],
        get_ip=lambda: local_ip,
        http_port=cfg["port"],
        target=(discovery.BROADCAST_ADDR, cfg["discovery_port"]),
    )
    broadcaster.start()

    print(f"[mesh] listening on :{cfg['port']} as {cfg['machine_id']} ({env})", flush=True)
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        broadcaster.stop()
        receiver.stop()
        http_server.stop(server)


def _detect_local_ip() -> str:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    serve_forever()
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m unittest tests.test_listener -v`
Expected: 5 pass.

- [ ] **Step 5: Run the full suite to ensure nothing regressed**

Run: `python -m unittest discover tests -v`
Expected: every previously-green test still passes.

- [ ] **Step 6: Commit**

```bash
git add claude_mesh/listener.py tests/test_listener.py
git commit -m "feat: listener daemon wiring HTTP, UDP, task executor, windows"
```

---

## Task 13: CLI client (`claude_mesh.client`)

**Files:**
- Create: `claude_mesh/client.py`
- Test: `tests/test_client.py`

A small CLI exposing three commands:
- `claude-mesh send <peer-id> <prompt>` — POST a `task` message; print conversation_id.
- `claude-mesh continue <conv-id> <prompt>` — POST a follow-up `task` message in an existing conversation.
- `claude-mesh peers` — print online peers from the registry.

Implemented as a `main(argv)` function so it's testable without subprocess.

- [ ] **Step 1: Write the failing test**

`tests/test_client.py`:
```python
import io
import os
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock

from claude_mesh import client, conv_registry, peer_registry


class TestClient(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        p = mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)
        peer_registry.record("alex-mac", "192.168.1.10", port=7432, ts=int(time.time()))

    def test_peers_lists_online(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = client.main(["peers"])
        self.assertEqual(rc, 0)
        self.assertIn("alex-mac", buf.getvalue())
        self.assertIn("192.168.1.10", buf.getvalue())

    def test_send_posts_task_to_known_peer_and_prints_conv_id(self):
        with mock.patch.object(client.http_client, "send_message") as send:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = client.main(["send", "alex-mac", "hello there"])
            self.assertEqual(rc, 0)
        send.assert_called_once()
        ip, port, msg = send.call_args.args[:3]
        self.assertEqual(ip, "192.168.1.10")
        self.assertEqual(port, 7432)
        self.assertEqual(msg.type, "task")
        self.assertEqual(msg.payload, "hello there")
        self.assertIn(msg.conversation_id, buf.getvalue())

    def test_send_unknown_peer_returns_error(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = client.main(["send", "nobody", "hi"])
        self.assertEqual(rc, 2)
        self.assertIn("unknown peer", buf.getvalue())

    def test_continue_reuses_existing_conv_and_session(self):
        conv_registry.set_conv("conv-x", peer_id="alex-mac", session_id="sess-9")
        with mock.patch.object(client.http_client, "send_message") as send:
            rc = client.main(["continue", "conv-x", "follow up"])
        self.assertEqual(rc, 0)
        msg = send.call_args.args[2]
        self.assertEqual(msg.conversation_id, "conv-x")
        self.assertEqual(msg.session_id, "sess-9")
        self.assertEqual(msg.payload, "follow up")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m unittest tests.test_client -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `client.py`**

```python
"""Command-line client for sending mesh messages."""
import argparse
import sys
import uuid
from typing import List, Optional

from claude_mesh import (config, conv_registry, http_client, peer_registry,
                         protocol)


def _local_machine_id() -> str:
    return config.get_or_init()["machine_id"]


def _local_ip() -> str:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def _cmd_peers(_args) -> int:
    for p in peer_registry.online():
        print(f"{p['id']}\t{p['ip']}:{p['port']}\tlast_seen={p['last_seen']}")
    return 0


def _cmd_send(args) -> int:
    peer = peer_registry.get(args.peer_id)
    if peer is None:
        print(f"unknown peer: {args.peer_id}")
        return 2
    conv_id = str(uuid.uuid4())
    msg = protocol.new_message(
        from_id=_local_machine_id(),
        from_ip=_local_ip(),
        conversation_id=conv_id,
        session_id=None,
        msg_type="task",
        payload=args.prompt,
    )
    try:
        http_client.send_message(peer["ip"], peer["port"], msg)
    except http_client.SendError as e:
        print(f"send failed: {e}")
        return 1
    conv_registry.set_conv(conv_id, peer_id=args.peer_id, session_id=None)
    print(f"sent. conversation_id={conv_id}")
    return 0


def _cmd_continue(args) -> int:
    conv = conv_registry.get(args.conv_id)
    if conv is None:
        print(f"unknown conversation: {args.conv_id}")
        return 2
    peer = peer_registry.get(conv["peer_id"])
    if peer is None:
        print(f"peer {conv['peer_id']} no longer known")
        return 2
    msg = protocol.new_message(
        from_id=_local_machine_id(),
        from_ip=_local_ip(),
        conversation_id=args.conv_id,
        session_id=conv.get("local_session_id"),
        msg_type="task",
        payload=args.prompt,
    )
    try:
        http_client.send_message(peer["ip"], peer["port"], msg)
    except http_client.SendError as e:
        print(f"send failed: {e}")
        return 1
    conv_registry.touch(args.conv_id)
    print(f"continued. conversation_id={args.conv_id}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="claude-mesh")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_send = sub.add_parser("send", help="send a new task to a peer")
    p_send.add_argument("peer_id")
    p_send.add_argument("prompt")
    p_send.set_defaults(func=_cmd_send)

    p_cont = sub.add_parser("continue", help="continue an existing conversation")
    p_cont.add_argument("conv_id")
    p_cont.add_argument("prompt")
    p_cont.set_defaults(func=_cmd_continue)

    p_peers = sub.add_parser("peers", help="list online peers")
    p_peers.set_defaults(func=_cmd_peers)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m unittest tests.test_client -v`
Expected: 4 pass.

- [ ] **Step 5: Commit**

```bash
git add claude_mesh/client.py tests/test_client.py
git commit -m "feat: CLI client with send/continue/peers commands"
```

---

## Task 14: Skill manifest and bootstrap script

**Files:**
- Create: `skill/SKILL.md`
- Create: `skill/activate.sh`

The skill activation:
1. Creates `~/.claude/mesh/`.
2. Copies the `claude_mesh/` package into `~/.claude/mesh/lib/` (or symlinks during dev).
3. Generates default config via `python3 -m claude_mesh.config_init` (one-liner).
4. Detects tmux; if missing, prompts to install.
5. Starts the listener daemon inside `tmux new-session -d -s claude-mesh` (or fallback if no tmux).

This task is shell-only — no unit tests, but a smoke-test step verifies it runs end-to-end.

- [ ] **Step 1: Write `skill/SKILL.md`**

```markdown
---
name: claude-mesh
description: Use this skill to send tasks to, or converse with, Claude Code instances on other machines on the local network. Invoke when the user asks to dispatch work to "another machine", "remote claude", "the linux box", "the mac mini", or names a peer machine. Also invoke when the user asks to list mesh peers, check who is online, or continue a previously-started cross-machine conversation.
---

# Claude Mesh

Claude Mesh is a P2P mesh of Claude Code instances on your LAN. Once installed
and running, you can hand off any prompt to a peer machine and receive its
reply asynchronously.

## Setup (one-time per machine)

Run the bootstrap script:

    bash ~/.claude/skills/claude-mesh/activate.sh

It creates `~/.claude/mesh/`, generates a stable `machine_id`, detects the
best window environment (tmux preferred), and starts the listener daemon.

## Common operations

- List online peers:

      python3 -m claude_mesh.client peers

- Send a new task to a peer:

      python3 -m claude_mesh.client send <peer-id> "<prompt>"

  Prints a `conversation_id` you'll use to continue the dialogue.

- Continue an existing conversation:

      python3 -m claude_mesh.client continue <conv-id> "<prompt>"

When the remote Claude needs human input, it emits the sentinel
`<<NEEDS_HUMAN: <reason>>>` in its reply. The remote machine's listener
then opens a foreground tmux window running `claude --resume <session>` so
the human at that machine can take over.

## Configuration

`~/.claude/mesh/config.json` holds the machine_id, ports (default 7432 HTTP /
7433 UDP discovery), and any static peers for cross-subnet routing:

```json
{
  "machine_id": "alex-mac-a3f2",
  "port": 7432,
  "discovery_port": 7433,
  "static_peers": [
    {"id": "dev-server", "ip": "10.0.1.50"}
  ]
}
```
```

- [ ] **Step 2: Write `skill/activate.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

MESH_DIR="${HOME}/.claude/mesh"
SKILL_LIB="${HOME}/.claude/skills/claude-mesh/lib"

mkdir -p "${MESH_DIR}"

# Initialise config (idempotent).
python3 -c "from claude_mesh import config; config.get_or_init()"

# Detect tmux; offer install hint.
if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found. Recommended for the best experience."
  case "$(uname)" in
    Darwin) echo "  Install: brew install tmux" ;;
    Linux)  echo "  Install: sudo apt install tmux  (or your distro equivalent)" ;;
  esac
fi

# If a daemon is already up on port 7432, do nothing.
if command -v lsof >/dev/null 2>&1 && lsof -i :7432 -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "[mesh] listener already running on :7432"
  exit 0
fi

# Start daemon.
if command -v tmux >/dev/null 2>&1; then
  if ! tmux has-session -t claude-mesh 2>/dev/null; then
    tmux new-session -d -s claude-mesh -n listener "python3 -m claude_mesh.listener"
    echo "[mesh] daemon started in tmux session 'claude-mesh'."
    echo "      Attach with: tmux attach -t claude-mesh"
  else
    tmux new-window -t claude-mesh -n listener "python3 -m claude_mesh.listener"
    echo "[mesh] daemon started in existing tmux session."
  fi
else
  nohup python3 -m claude_mesh.listener \
    > "${MESH_DIR}/listener.out" 2> "${MESH_DIR}/listener.err" &
  echo "[mesh] daemon started in background (no tmux). Logs: ${MESH_DIR}/listener.{out,err}"
fi
```

Then:
```bash
chmod +x skill/activate.sh
```

- [ ] **Step 3: Smoke test the bootstrap (no daemon left running)**

Run, in a temp `CLAUDE_MESH_DIR` so we don't collide with anything real:

```bash
export CLAUDE_MESH_DIR=$(mktemp -d)
PYTHONPATH=. python3 -c "from claude_mesh import config; print(config.get_or_init())"
unset CLAUDE_MESH_DIR
```

Expected: prints a config dict with a `machine_id` matching `*-[a-f0-9]{4}`.

- [ ] **Step 4: Commit**

```bash
git add skill/SKILL.md skill/activate.sh
chmod +x skill/activate.sh
git add skill/activate.sh
git commit -m "feat: skill manifest and activate.sh bootstrap"
```

---

## Task 15: End-to-end loopback smoke test

**Files:**
- Create: `tests/test_e2e_loopback.py`

Spins up two `Listener` instances bound to two different ephemeral ports on `127.0.0.1`, mocks `task_executor.run_task` on the receiver, sends a real `task` message via the real `http_client.send_message`, waits for the real `reply` to arrive over real HTTP. This is the only test that exercises the whole stack end-to-end.

- [ ] **Step 1: Write the failing test**

`tests/test_e2e_loopback.py`:
```python
import os
import socket
import tempfile
import threading
import time
import unittest
from unittest import mock

from claude_mesh import (http_client, http_server, listener, peer_registry,
                         protocol, task_executor)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class TestE2ELoopback(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        p = mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)

    def test_task_round_trip_over_real_http(self):
        port_a = _free_port()
        port_b = _free_port()

        # Sender (A) and receiver (B) machine_ids registered as peers of each other.
        peer_registry.record("machine-a", "127.0.0.1", port=port_a, ts=int(time.time()))
        peer_registry.record("machine-b", "127.0.0.1", port=port_b, ts=int(time.time()))

        # Capture replies arriving back at A.
        received_replies = []
        ev = threading.Event()

        def a_handler(msg: protocol.Message):
            received_replies.append(msg)
            ev.set()
            return {"ok": True}

        srv_a = http_server.start("127.0.0.1", port_a, a_handler)
        self.addCleanup(lambda: http_server.stop(srv_a))

        # Receiver B has a full Listener.
        l = listener.Listener(
            machine_id="machine-b", local_ip="127.0.0.1",
            http_port=port_b, terminal_env="headless",
        )
        srv_b = http_server.start("127.0.0.1", port_b, l.handle_message)
        self.addCleanup(lambda: http_server.stop(srv_b))

        # Mock the actual `claude` invocation on B.
        result = task_executor.TaskResult(
            session_id="session-zzz",
            payload="response from B",
            needs_human=False,
            escalation_reason=None,
        )
        with mock.patch.object(listener.task_executor, "run_task", return_value=result):
            # A → B task.
            msg = protocol.new_message(
                from_id="machine-a", from_ip="127.0.0.1",
                conversation_id="conv-roundtrip",
                session_id=None,
                msg_type="task",
                payload="please handle this",
            )
            ack = http_client.send_message("127.0.0.1", port_b, msg, timeout=5.0)
            self.assertEqual(ack, {"accepted": True})

            # Wait for B to invoke executor and POST the reply back to A.
            self.assertTrue(ev.wait(timeout=10.0), "no reply received within timeout")

        self.assertEqual(len(received_replies), 1)
        reply = received_replies[0]
        self.assertEqual(reply.type, "reply")
        self.assertEqual(reply.from_id, "machine-b")
        self.assertEqual(reply.conversation_id, "conv-roundtrip")
        self.assertEqual(reply.payload, "response from B")
        self.assertEqual(reply.session_id, "session-zzz")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — expect PASS**

Run: `python -m unittest tests.test_e2e_loopback -v`
Expected: 1 pass.

- [ ] **Step 3: Run the entire suite once more**

Run: `python -m unittest discover tests -v`
Expected: all tests pass; no regressions.

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e_loopback.py
git commit -m "test: end-to-end loopback round-trip over real HTTP"
```

---

## Task 16: Manual QA checklist (no code)

A short script the implementer runs by hand on a single machine to confirm the whole thing actually starts and serves before declaring victory.

- [ ] **Step 1: Activate the skill in a scratch dir**

```bash
export CLAUDE_MESH_DIR=$(mktemp -d)
PYTHONPATH=. python3 -m claude_mesh.listener &
LISTENER_PID=$!
sleep 1
```

Expected output: `[mesh] listening on :7432 as <machine_id> (<env>)`.

- [ ] **Step 2: Self-send a task via the CLI**

```bash
# Manually inject self into peers so we can talk to ourselves.
PYTHONPATH=. python3 -c "
from claude_mesh import peer_registry, config
cfg = config.get_or_init()
peer_registry.record(cfg['machine_id'], '127.0.0.1', port=cfg['port'])
"

PYTHONPATH=. python3 -m claude_mesh.client peers
PYTHONPATH=. python3 -m claude_mesh.client send "$(PYTHONPATH=. python3 -c 'from claude_mesh import config; print(config.get_or_init()["machine_id"])')" "echo hi"
```

Expected: `peers` lists yourself; `send` prints `sent. conversation_id=...`. The listener log (`$CLAUDE_MESH_DIR/inbox.log`) shows the task arriving.

> Note: the actual `claude -p` call will fail unless the `claude` CLI is on PATH and authenticated. That's expected. The point of this manual check is the transport, not the LLM call.

- [ ] **Step 3: Tear down**

```bash
kill "$LISTENER_PID" 2>/dev/null || true
rm -rf "$CLAUDE_MESH_DIR"
unset CLAUDE_MESH_DIR
```

- [ ] **Step 4: Final commit (release tag)**

```bash
git tag v1.0.0
git log --oneline | head -20
```

---

## Self-Review Notes

I checked the plan against each section of the design doc:

- **零中央節點 / P2P** → Tasks 6–8 (HTTP client/server, UDP discovery) — no broker.
- **對等角色** → Listener (Task 12) treats every incoming message identically regardless of sender role.
- **安裝即用** → Task 14 (`activate.sh`).
- **人機協作（背景優先 + 升級）** → Task 11 detects `<<NEEDS_HUMAN>>`; Task 12 calls `window_spawner` to escalate; Task 10 covers all six fallback environments.
- **訊息格式 JSON / 4 種 type** → Task 3 (`protocol.py`).
- **UDP heartbeat 30s / 90s offline** → Task 8 (`discovery.py`) + Task 4 (`peer_registry.online()`).
- **Static peer cross-subnet** → Config field `static_peers` is loaded by Task 2 and consumed by `client.py` (peer_id-based send works regardless of how the peer entry got there). Heartbeat-based ping for static peers is *not* implemented in this plan; it's an enhancement listed in the design's "後續擴充方向" — calling it out here so the implementer knows it's deliberately deferred.
- **Session continuity (`claude --resume`)** → Tasks 5 & 11.
- **tmux session "claude-mesh"** → Task 10.
- **machine_id = hostname + 隨機後綴** → Task 2 with the regex test.
- **檔案結構 (~/.claude/mesh/...)** → Tasks 1 & 14.
- **平台支援矩陣** → Tasks 9, 10, 14 cover all rows.
- **訊息 log (inbox.log)** → Task 12 (`_append_inbox`).

No placeholders — every step contains the actual code or command. Type/method names are consistent across tasks (`Message`, `Listener.handle_message`, `task_executor.run_task`, `task_executor.TaskResult`, `window_spawner.spawn_window(env, title, command)`, `peer_registry.record/get/online`, `conv_registry.get/set_conv/touch/attach_session/close`).

One deliberate scope cut: cross-subnet active probing of `static_peers` (the design says "系統定期 HTTP ping") is not wired in. Static peers will only become reachable once they themselves send any message (which adds them to the local `peer_registry`), or when the user invokes `client.py send` against the static IP directly. If this matters at v1, add a Task 8b that runs an HTTP `GET /health` against each static peer every 30s and calls `peer_registry.record`. Flagging rather than silently expanding scope.
