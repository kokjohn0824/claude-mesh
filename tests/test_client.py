import io
import os
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock

from claude_mesh import client, conv_registry, peer_registry


class TestClient(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        p = mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)
        peer_registry.record("alex-mac", "192.168.1.10", port=7432, ts=int(time.time()))

    def test_peers_lists_online(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = client.main(["peers"])
        self.assertEqual(rc, 0)
        self.assertIn("alex-mac", buf.getvalue())
        self.assertIn("192.168.1.10", buf.getvalue())

    def test_send_posts_task_to_known_peer_and_prints_conv_id(self):
        with mock.patch.object(client.http_client, "send_message") as send:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = client.main(["send", "alex-mac", "hello there"])
            self.assertEqual(rc, 0)
        send.assert_called_once()
        ip, port, msg = send.call_args.args[:3]
        self.assertEqual(ip, "192.168.1.10")
        self.assertEqual(port, 7432)
        self.assertEqual(msg.type, "task")
        self.assertEqual(msg.payload, "hello there")
        self.assertIn(msg.conversation_id, buf.getvalue())

    def test_send_unknown_peer_returns_error(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = client.main(["send", "nobody", "hi"])
        self.assertEqual(rc, 2)
        self.assertIn("unknown peer", buf.getvalue())

    def test_continue_reuses_existing_conv_and_session(self):
        conv_registry.set_conv("conv-x", peer_id="alex-mac", session_id="sess-9")
        with mock.patch.object(client.http_client, "send_message") as send:
            rc = client.main(["continue", "conv-x", "follow up"])
        self.assertEqual(rc, 0)
        msg = send.call_args.args[2]
        self.assertEqual(msg.conversation_id, "conv-x")
        self.assertEqual(msg.session_id, "sess-9")
        self.assertEqual(msg.payload, "follow up")


if __name__ == "__main__":
    unittest.main()
