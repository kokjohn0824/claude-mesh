import os
import socket
import tempfile
import threading
import time
import unittest
from unittest import mock

from claude_mesh import (http_client, http_server, listener, peer_registry,
                         protocol, task_executor)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class TestE2ELoopback(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        p = mock.patch.dict(os.environ, {"CLAUDE_MESH_DIR": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)

    def test_task_round_trip_over_real_http(self):
        port_a = _free_port()
        port_b = _free_port()

        # Both machines registered as peers of each other.
        peer_registry.record("machine-a", "127.0.0.1", port=port_a, ts=int(time.time()))
        peer_registry.record("machine-b", "127.0.0.1", port=port_b, ts=int(time.time()))

        # Capture replies arriving back at A.
        received_replies = []
        ev = threading.Event()

        def a_handler(msg: protocol.Message):
            received_replies.append(msg)
            ev.set()
            return {"ok": True}

        srv_a = http_server.start("127.0.0.1", port_a, a_handler)
        self.addCleanup(lambda: http_server.stop(srv_a))

        # Receiver B has a full Listener.
        l = listener.Listener(
            machine_id="machine-b", local_ip="127.0.0.1",
            http_port=port_b, terminal_env="headless",
        )
        srv_b = http_server.start("127.0.0.1", port_b, l.handle_message)
        self.addCleanup(lambda: http_server.stop(srv_b))

        # Mock the actual `claude` invocation on B.
        result = task_executor.TaskResult(
            session_id="session-zzz",
            payload="response from B",
            needs_human=False,
            escalation_reason=None,
        )
        with mock.patch.object(listener.task_executor, "run_task", return_value=result):
            # A → B task.
            msg = protocol.new_message(
                from_id="machine-a", from_ip="127.0.0.1",
                conversation_id="conv-roundtrip",
                session_id=None,
                msg_type="task",
                payload="please handle this",
            )
            ack = http_client.send_message("127.0.0.1", port_b, msg, timeout=5.0)
            self.assertEqual(ack, {"accepted": True})

            # Wait for B to invoke executor and POST the reply back to A.
            self.assertTrue(ev.wait(timeout=10.0), "no reply received within timeout")

        self.assertEqual(len(received_replies), 1)
        reply = received_replies[0]
        self.assertEqual(reply.type, "reply")
        self.assertEqual(reply.from_id, "machine-b")
        self.assertEqual(reply.conversation_id, "conv-roundtrip")
        self.assertEqual(reply.payload, "response from B")
        self.assertEqual(reply.session_id, "session-zzz")


if __name__ == "__main__":
    unittest.main()
