#!/usr/bin/env bash
set -euo pipefail

MESH_DIR="${HOME}/.claude/mesh"

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
