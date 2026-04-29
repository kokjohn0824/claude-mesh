import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from claude_mesh import http_client, protocol


class _Handler(BaseHTTPRequestHandler):
    received = []  # class-level capture

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length).decode()
        self.__class__.received.append((self.path, body))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def log_message(self, *_):
        pass


class TestHTTPClient(unittest.TestCase):
    def setUp(self):
        _Handler.received = []
        self.srv = HTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def test_send_posts_to_messages_endpoint(self):
        msg = protocol.new_message(
            from_id="a", from_ip="1.1.1.1",
            conversation_id="c", session_id=None,
            msg_type="task", payload="hi",
        )
        resp = http_client.send_message("127.0.0.1", self.port, msg, timeout=2.0)
        self.assertEqual(resp, {"ok": True})
        self.assertEqual(len(_Handler.received), 1)
        path, body = _Handler.received[0]
        self.assertEqual(path, "/messages")
        roundtrip = protocol.parse(body)
        self.assertEqual(roundtrip.payload, "hi")

    def test_raises_on_unreachable(self):
        # Bind to a closed port: shut server down first.
        self.srv.shutdown()
        self.srv.server_close()
        msg = protocol.new_message(
            from_id="a", from_ip="1.1.1.1",
            conversation_id="c", session_id=None,
            msg_type="task", payload="hi",
        )
        with self.assertRaises(http_client.SendError):
            http_client.send_message("127.0.0.1", self.port, msg, timeout=0.5)


if __name__ == "__main__":
    unittest.main()
