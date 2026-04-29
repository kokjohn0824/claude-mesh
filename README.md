# Claude Mesh

P2P Claude Code skill for cross-machine task dispatch and dialogue on a LAN.
Each machine runs a small daemon (Python 3 stdlib only); peers discover each
other via UDP heartbeat, exchange `task` / `reply` / `escalate` messages over
HTTP on port 7432, and continue conversations via `claude --resume <session>`.

When the remote Claude needs human input it emits the sentinel
`<<NEEDS_HUMAN: <reason>>>` in its reply — the receiving machine then opens
a foreground tmux window running `claude --resume <session>` so the human at
that machine can take over.

## Requirements

- Python 3.9+
- `claude` CLI on `PATH`, authenticated
- tmux (recommended; the daemon falls back to iTerm2 / Terminal.app / screen
  / xterm / headless mode if tmux is missing)
- All peer machines on the same LAN broadcast domain (or each machine listed
  in the others' `static_peers`)

## Install

### For humans

```bash
git clone https://github.com/kokjohn0824/claude-mesh.git ~/.claude/skills/claude-mesh
bash ~/.claude/skills/claude-mesh/activate.sh
```

`activate.sh` is idempotent — safe to re-run. It:

1. creates `~/.claude/mesh/` with a default `config.json` (generates a stable `machine_id`)
2. checks for tmux and prints an install hint if missing
3. starts `python3 -m claude_mesh.listener` in a detached tmux session named `claude-mesh` (or via `nohup` if tmux is unavailable)

Attach to the listener output:

```bash
tmux attach -t claude-mesh
```

Stop the daemon:

```bash
tmux kill-session -t claude-mesh    # tmux path
# or, for the nohup fallback:
pkill -f 'python3 -m claude_mesh.listener'
```

### For coding agents (Claude Code, Codex, etc.)

Run these two commands. The first installs the skill into the user's
personal skills directory; the second initialises the per-machine config
and starts the listener daemon:

```bash
git clone https://github.com/kokjohn0824/claude-mesh.git ~/.claude/skills/claude-mesh
bash ~/.claude/skills/claude-mesh/activate.sh
```

After install, the skill is invocable in Claude Code by name (`claude-mesh`).
The CLI is available as `python3 -m claude_mesh.client` (the activate.sh
exports the necessary `PYTHONPATH` for the daemon and its subprocesses; for
ad-hoc CLI use prefix with
`PYTHONPATH=$HOME/.claude/skills/claude-mesh`).

## Usage

```bash
# After activate.sh has been run once on each machine.

# List online peers (any machine that has heartbeated within the last 90s).
PYTHONPATH=~/.claude/skills/claude-mesh python3 -m claude_mesh.client peers

# Send a new task to a peer.
PYTHONPATH=~/.claude/skills/claude-mesh \
  python3 -m claude_mesh.client send <peer-id> "<your prompt>"

# Continue an existing conversation.
PYTHONPATH=~/.claude/skills/claude-mesh \
  python3 -m claude_mesh.client continue <conversation-id> "<follow-up>"
```

Replies arrive asynchronously and are appended to `~/.claude/mesh/inbox.log`.

> **Tip:** add `export PYTHONPATH="$HOME/.claude/skills/claude-mesh:$PYTHONPATH"`
> to your shell rc to drop the inline `PYTHONPATH=...` prefix.

## Configuration

`~/.claude/mesh/config.json` (auto-generated on first activate):

```json
{
  "machine_id": "alex-mac-a3f2",
  "port": 7432,
  "discovery_port": 7433,
  "static_peers": []
}
```

- `static_peers` is reserved for cross-subnet routing (currently declared
  but not yet read by the broadcaster — tracked for v1.0.1).

## Trust model

Claude Mesh assumes a trusted LAN. Heartbeats are unauthenticated UDP
packets; any machine on the broadcast domain can claim any `machine_id`.
Do not deploy on untrusted networks until TLS / shared-secret
authentication is added.

## Development

```bash
python3 -m unittest discover tests -v
```

65 tests, all stdlib (no pip install).

Plan: [`docs/superpowers/plans/2026-04-29-claude-mesh.md`](docs/superpowers/plans/2026-04-29-claude-mesh.md)

## License

TBD
