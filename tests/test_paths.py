import os
import tempfile
import unittest
from unittest import mock

from claude_mesh import paths


class TestPaths(unittest.TestCase):
    def test_mesh_dir_defaults_to_home(self):
        with mock.patch.dict(os.environ, {"HOME": "/tmp/fakehome"}, clear=False):
            self.assertEqual(paths.mesh_dir(), "/tmp/fakehome/.claude/mesh")

    def test_mesh_dir_honours_override_env(self):
        with mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": "/tmp/m"}):
            self.assertEqual(paths.mesh_dir(), "/tmp/m")

    def test_named_files_under_mesh_dir(self):
        with mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": "/tmp/m"}):
            self.assertEqual(paths.config_file(), "/tmp/m/config.json")
            self.assertEqual(paths.peers_file(), "/tmp/m/peers.json")
            self.assertEqual(paths.conv_registry_file(), "/tmp/m/conv_registry.json")
            self.assertEqual(paths.inbox_log(), "/tmp/m/inbox.log")

    def test_ensure_mesh_dir_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "sub", "mesh")
            with mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": target}):
                paths.ensure_mesh_dir()
                self.assertTrue(os.path.isdir(target))


if __name__ == "__main__":
    unittest.main()
