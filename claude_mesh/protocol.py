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
