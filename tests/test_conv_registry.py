import os
import tempfile
import unittest
from unittest import mock

from claude_mesh import conv_registry


class TestConvRegistry(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        p = mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)

    def test_get_unknown_returns_none(self):
        self.assertIsNone(conv_registry.get("missing"))

    def test_set_then_get(self):
        conv_registry.set_conv("c1", peer_id="alex", session_id="s-1")
        rec = conv_registry.get("c1")
        self.assertEqual(rec["local_session_id"], "s-1")
        self.assertEqual(rec["peer_id"], "alex")
        self.assertEqual(rec["status"], "active")
        self.assertGreater(rec["created_at"], 0)
        self.assertGreaterEqual(rec["last_active"], rec["created_at"])

    def test_touch_updates_last_active(self):
        conv_registry.set_conv("c1", peer_id="alex", session_id=None, _now=1000)
        conv_registry.touch("c1", _now=2000)
        rec = conv_registry.get("c1")
        self.assertEqual(rec["last_active"], 2000)
        self.assertEqual(rec["created_at"], 1000)

    def test_attach_session_id_after_first_run(self):
        conv_registry.set_conv("c1", peer_id="alex", session_id=None)
        conv_registry.attach_session("c1", "s-2")
        self.assertEqual(conv_registry.get("c1")["local_session_id"], "s-2")

    def test_close_marks_status(self):
        conv_registry.set_conv("c1", peer_id="alex", session_id="s-1")
        conv_registry.close("c1")
        self.assertEqual(conv_registry.get("c1")["status"], "closed")


if __name__ == "__main__":
    unittest.main()
