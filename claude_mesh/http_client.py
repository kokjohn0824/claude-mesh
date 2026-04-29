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
