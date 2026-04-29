import json
import threading
import time
import unittest
import urllib.error
import urllib.request

from claude_mesh import http_server, protocol


class TestHTTPServer(unittest.TestCase):
    def test_post_invokes_handler_and_returns_200(self):
        received = []

        def on_message(m):
            received.append(m)
            return {"ack": True}

        server = http_server.start("127.0.0.1", 0, on_message)
        try:
            port = server.server_address[1]
            msg = protocol.new_message(
                from_id="a", from_ip="1.1.1.1",
                conversation_id="c", session_id=None,
                msg_type="task", payload="hi",
            )
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/messages",
                data=protocol.serialize(msg).encode(),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                self.assertEqual(resp.status, 200)
                body = json.loads(resp.read().decode())
            self.assertEqual(body, {"ack": True})
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0].payload, "hi")
        finally:
            http_server.stop(server)

    def test_post_with_bad_json_returns_400(self):
        server = http_server.start("127.0.0.1", 0, lambda m: {})
        try:
            port = server.server_address[1]
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/messages",
                data=b"not json",
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            try:
                urllib.request.urlopen(req, timeout=2)
                self.fail("expected HTTP 400")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 400)
        finally:
            http_server.stop(server)

    def test_unknown_path_returns_404(self):
        server = http_server.start("127.0.0.1", 0, lambda m: {})
        try:
            port = server.server_address[1]
            req = urllib.request.Request(f"http://127.0.0.1:{port}/nope", method="POST", data=b"{}")
            try:
                urllib.request.urlopen(req, timeout=2)
                self.fail("expected HTTP 404")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 404)
        finally:
            http_server.stop(server)


if __name__ == "__main__":
    unittest.main()
