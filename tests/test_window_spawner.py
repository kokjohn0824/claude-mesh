import unittest
from unittest import mock

from claude_mesh import window_spawner


class TestWindowSpawner(unittest.TestCase):
    def test_tmux_spawns_new_window_in_session(self):
        with mock.patch("subprocess.run") as run:
            run.return_value.returncode = 0
            window_spawner.spawn_window("tmux", title="task-1", command="claude --resume abc")
            args = run.call_args_list[0].args[0]
            self.assertEqual(args[0], "tmux")
            self.assertIn("new-window", args)
            self.assertIn("-t", args)
            self.assertIn("claude-mesh", args)
            self.assertIn("-n", args)
            self.assertIn("task-1", args)
            self.assertIn("claude --resume abc", args)

    def test_iterm2_uses_osascript(self):
        with mock.patch("subprocess.run") as run:
            run.return_value.returncode = 0
            window_spawner.spawn_window("iterm2", title="t", command="echo hi")
            args = run.call_args_list[0].args[0]
            self.assertEqual(args[0], "osascript")
            self.assertIn("-e", args)
            joined = " ".join(args)
            self.assertIn("iTerm", joined)
            self.assertIn("echo hi", joined)

    def test_terminal_app_uses_osascript(self):
        with mock.patch("subprocess.run") as run:
            run.return_value.returncode = 0
            window_spawner.spawn_window("terminal_app", title="t", command="echo hi")
            args = run.call_args_list[0].args[0]
            self.assertEqual(args[0], "osascript")
            joined = " ".join(args)
            self.assertIn("Terminal", joined)

    def test_screen_uses_screen_command(self):
        with mock.patch("subprocess.run") as run:
            run.return_value.returncode = 0
            window_spawner.spawn_window("screen", title="t", command="echo hi")
            args = run.call_args_list[0].args[0]
            self.assertEqual(args[0], "screen")
            self.assertIn("-S", args)
            self.assertIn("claude-mesh", args)

    def test_xterm_spawns_xterm(self):
        with mock.patch("subprocess.Popen") as popen:
            window_spawner.spawn_window("xterm", title="t", command="echo hi")
            args = popen.call_args.args[0]
            self.assertEqual(args[0], "xterm")
            self.assertIn("-T", args)
            self.assertIn("t", args)

    def test_headless_is_a_noop(self):
        with mock.patch("subprocess.run") as run, mock.patch("subprocess.Popen") as popen:
            window_spawner.spawn_window("headless", title="t", command="echo hi")
            run.assert_not_called()
            popen.assert_not_called()

    def test_unknown_env_raises(self):
        with self.assertRaises(ValueError):
            window_spawner.spawn_window("magic", title="t", command="echo hi")


if __name__ == "__main__":
    unittest.main()
