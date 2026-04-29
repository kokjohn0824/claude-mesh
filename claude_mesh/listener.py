"""Listener daemon: wires HTTP, UDP, task executor, and window spawner."""
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
        default_peer_port: int = 7432,
    ):
        self.machine_id = machine_id
        self.local_ip = local_ip
        self.http_port = http_port
        self.terminal_env = terminal_env
        self.default_peer_port = default_peer_port
        self._executor = ThreadPoolExecutor(max_workers=TASK_WORKERS, thread_name_prefix="mesh-task")
        self._inflight = 0
        self._inflight_lock = threading.Lock()
        self._idle = threading.Event()
        self._idle.set()

    # --- inflight tracking so tests can wait for background work ---
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

    # --- message dispatch ---
    def handle_message(self, msg: protocol.Message) -> dict:
        _append_inbox(f"[{int(time.time())}] {msg.type} from {msg.from_id}: {msg.payload[:200]}")
        if msg.type == "task":
            self._inc_inflight()
            try:
                self._executor.submit(self._handle_task, msg)
            except RuntimeError:
                self._dec_inflight()
                raise
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
        if peer is not None:
            ip, port = peer["ip"], peer["port"]
        else:
            ip = original.from_ip
            port = self.default_peer_port
            _append_inbox(f"[mesh] peer {original.from_id} not in registry; replying to envelope ip {ip}:{port}")
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
            http_client.send_message(ip, port, reply, timeout=10.0)
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


# --- top-level daemon entry ---

def serve_forever() -> None:
    paths.ensure_mesh_dir()
    cfg = config.get_or_init()
    env = terminal_env.detect()
    local_ip = _detect_local_ip()

    listener_inst = Listener(
        machine_id=cfg["machine_id"],
        local_ip=local_ip,
        http_port=cfg["port"],
        terminal_env=env,
        default_peer_port=cfg["port"],
    )

    server = http_server.start("0.0.0.0", cfg["port"], listener_inst.handle_message)
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
