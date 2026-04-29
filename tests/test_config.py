import json
import os
import tempfile
import unittest
from unittest import mock

from claude_mesh import config


class TestConfig(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._env = mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": self._tmp.name})
        self._env.start()
        self.addCleanup(self._env.stop)

    def test_get_or_init_creates_default_config(self):
        cfg = config.get_or_init()
        self.assertEqual(cfg["port"], 7432)
        self.assertEqual(cfg["discovery_port"], 7433)
        self.assertEqual(cfg["static_peers"], [])
        self.assertRegex(cfg["machine_id"], r"^[a-zA-Z0-9._-]+-[a-f0-9]{4}$")

    def test_get_or_init_persists_to_disk(self):
        cfg = config.get_or_init()
        with open(os.path.join(self._tmp.name, "config.json")) as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk, cfg)

    def test_get_or_init_idempotent(self):
        first = config.get_or_init()
        second = config.get_or_init()
        self.assertEqual(first["machine_id"], second["machine_id"])

    def test_save_then_load_roundtrip(self):
        config.save({"machine_id": "x-0000", "port": 7432, "discovery_port": 7433, "static_peers": []})
        loaded = config.load()
        self.assertEqual(loaded["machine_id"], "x-0000")

    def test_machine_id_uses_hostname(self):
        with mock.patch("socket.gethostname", return_value="alex-mac"):
            cfg = config.get_or_init()
        self.assertTrue(cfg["machine_id"].startswith("alex-mac-"))


if __name__ == "__main__":
    unittest.main()
