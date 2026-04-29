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
