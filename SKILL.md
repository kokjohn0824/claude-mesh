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

The CLI is `python3 -m claude_mesh.client`. The skill directory must be on
`PYTHONPATH` for the import to resolve, so prefix every CLI invocation with
`PYTHONPATH=$HOME/.claude/skills/claude-mesh`:

- List online peers:

      PYTHONPATH=$HOME/.claude/skills/claude-mesh python3 -m claude_mesh.client peers

- Send a new task to a peer:

      PYTHONPATH=$HOME/.claude/skills/claude-mesh python3 -m claude_mesh.client send <peer-id> "<prompt>"

  Prints a `conversation_id` you'll use to continue the dialogue.

- Continue an existing conversation:

      PYTHONPATH=$HOME/.claude/skills/claude-mesh python3 -m claude_mesh.client continue <conv-id> "<prompt>"

Replies arrive asynchronously and are appended to `~/.claude/mesh/inbox.log`.

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

## Trust model

Claude Mesh assumes a trusted LAN. Heartbeats are unauthenticated UDP packets;
any machine on the broadcast domain can claim any `machine_id`. Do not deploy
on untrusted networks until TLS / shared-secret authentication is added.
