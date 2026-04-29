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
