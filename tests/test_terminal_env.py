import unittest
from unittest import mock

from claude_mesh import terminal_env


class TestTerminalEnv(unittest.TestCase):
    def test_prefers_tmux_when_available(self):
        with mock.patch("shutil.which", side_effect=lambda c: "/x/tmux" if c == "tmux" else None), \
             mock.patch("sys.platform", "darwin"):
            self.assertEqual(terminal_env.detect(), "tmux")

    def test_macos_iterm2_when_no_tmux_and_iterm_running(self):
        which_map = {"tmux": None, "screen": None}
        with mock.patch("shutil.which", side_effect=lambda c: which_map.get(c, None)), \
             mock.patch("sys.platform", "darwin"), \
             mock.patch.object(terminal_env, "_iterm2_running", return_value=True):
            self.assertEqual(terminal_env.detect(), "iterm2")

    def test_macos_terminal_app_when_no_tmux_no_iterm(self):
        with mock.patch("shutil.which", return_value=None), \
             mock.patch("sys.platform", "darwin"), \
             mock.patch.object(terminal_env, "_iterm2_running", return_value=False):
            self.assertEqual(terminal_env.detect(), "terminal_app")

    def test_linux_screen_when_no_tmux(self):
        which_map = {"tmux": None, "screen": "/x/screen"}
        with mock.patch("shutil.which", side_effect=lambda c: which_map.get(c, None)), \
             mock.patch("sys.platform", "linux"), \
             mock.patch.dict("os.environ", {"DISPLAY": ":0"}, clear=True):
            self.assertEqual(terminal_env.detect(), "screen")

    def test_linux_xterm_with_display_no_tmux_no_screen(self):
        with mock.patch("shutil.which", side_effect=lambda c: "/x/xterm" if c == "xterm" else None), \
             mock.patch("sys.platform", "linux"), \
             mock.patch.dict("os.environ", {"DISPLAY": ":0"}, clear=True):
            self.assertEqual(terminal_env.detect(), "xterm")

    def test_linux_headless_when_nothing_available(self):
        with mock.patch("shutil.which", return_value=None), \
             mock.patch("sys.platform", "linux"), \
             mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(terminal_env.detect(), "headless")


if __name__ == "__main__":
    unittest.main()
