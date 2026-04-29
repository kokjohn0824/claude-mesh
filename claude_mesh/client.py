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
