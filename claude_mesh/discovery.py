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
