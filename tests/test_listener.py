import os
import tempfile
import threading
import time
import unittest
from unittest import mock

from claude_mesh import (conv_registry, listener, peer_registry, protocol,
                         task_executor)


def _make_msg(**overrides):
    base = dict(
        from_id="alex-mac", from_ip="192.168.1.10",
        conversation_id="conv-1", session_id=None,
        msg_type="task", payload="say hi",
    )
    base.update(overrides)
    return protocol.new_message(**base)


class TestListener(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        p = mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)

        # Register the sender as a known peer so reply-routing works.
        peer_registry.record("alex-mac", "192.168.1.10", port=7432, ts=int(time.time()))

    def _make_listener(self, **kwargs):
        defaults = dict(
            machine_id="bob-linux",
            local_ip="192.168.1.11",
            http_port=7432,
            terminal_env="tmux",
        )
        defaults.update(kwargs)
        return listener.Listener(**defaults)

    def test_task_runs_executor_and_posts_reply_back(self):
        l = self._make_listener()
        result = task_executor.TaskResult(
            session_id="sess-x", payload="done", needs_human=False, escalation_reason=None,
        )
        with mock.patch.object(listener.task_executor, "run_task", return_value=result) as run, \
             mock.patch.object(listener.http_client, "send_message") as send:
            l.handle_message(_make_msg())
            l.wait_idle(timeout=2.0)
        run.assert_called_once()
        # Reply was POSTed back to the sender's IP.
        send.assert_called_once()
        ip, port, msg = send.call_args.args[:3]
        self.assertEqual(ip, "192.168.1.10")
        self.assertEqual(port, 7432)
        self.assertEqual(msg.type, "reply")
        self.assertEqual(msg.payload, "done")
        self.assertEqual(msg.session_id, "sess-x")
        # conv_registry recorded the new session.
        rec = conv_registry.get("conv-1")
        self.assertEqual(rec["local_session_id"], "sess-x")

    def test_task_with_needs_human_spawns_window(self):
        l = self._make_listener()
        result = task_executor.TaskResult(
            session_id="sess-y", payload="<<NEEDS_HUMAN: confirm>>",
            needs_human=True, escalation_reason="confirm",
        )
        with mock.patch.object(listener.task_executor, "run_task", return_value=result), \
             mock.patch.object(listener.http_client, "send_message"), \
             mock.patch.object(listener.window_spawner, "spawn_window") as spawn:
            l.handle_message(_make_msg())
            l.wait_idle(timeout=2.0)
        spawn.assert_called_once()
        # Support either kwargs or positional invocation.
        if spawn.call_args.args:
            env, title, command = spawn.call_args.args
        else:
            env = spawn.call_args.kwargs["env"]
            title = spawn.call_args.kwargs["title"]
            command = spawn.call_args.kwargs["command"]
        self.assertEqual(env, "tmux")
        self.assertIn("conv-1", title)
        self.assertIn("--resume", command)
        self.assertIn("sess-y", command)

    def test_task_resumes_existing_session_when_known(self):
        conv_registry.set_conv("conv-1", peer_id="alex-mac", session_id="sess-prev")
        l = self._make_listener()
        result = task_executor.TaskResult(
            session_id="sess-prev", payload="ok", needs_human=False, escalation_reason=None,
        )
        with mock.patch.object(listener.task_executor, "run_task", return_value=result) as run, \
             mock.patch.object(listener.http_client, "send_message"):
            l.handle_message(_make_msg(session_id="sess-prev"))
            l.wait_idle(timeout=2.0)
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs.get("session_id"), "sess-prev")

    def test_reply_appends_to_inbox_log(self):
        l = self._make_listener()
        l.handle_message(_make_msg(msg_type="reply", payload="result text"))
        log_path = os.path.join(self._tmp.name, "inbox.log")
        self.assertTrue(os.path.exists(log_path))
        with open(log_path) as f:
            self.assertIn("result text", f.read())

    def test_unknown_peer_reply_target_is_logged_not_crashed(self):
        l = self._make_listener()
        msg = _make_msg(from_id="ghost", from_ip="10.0.0.99")
        result = task_executor.TaskResult(
            session_id="s", payload="ok", needs_human=False, escalation_reason=None,
        )
        with mock.patch.object(listener.task_executor, "run_task", return_value=result), \
             mock.patch.object(listener.http_client, "send_message", side_effect=listener.http_client.SendError("nope")):
            # Should not raise.
            l.handle_message(msg)
            l.wait_idle(timeout=2.0)


if __name__ == "__main__":
    unittest.main()
