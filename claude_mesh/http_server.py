"""Threaded HTTP server receiving mesh messages on POST /messages."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional

from claude_mesh import protocol

OnMessage = Callable[[protocol.Message], Optional[dict]]


def _make_handler(on_message: OnMessage):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/messages":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            try:
                msg = protocol.parse(raw)
            except protocol.ProtocolError as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
                return
            try:
                result = on_message(msg) or {}
            except Exception as e:  # handler crash → 500
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        def log_message(self, *_):
            pass  # silence default stderr logging

    return Handler


def start(host: str, port: int, on_message: OnMessage) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), _make_handler(on_message))
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="mesh-http")
    thread.start()
    server._mesh_thread = thread  # type: ignore[attr-defined]
    return server


def stop(server: ThreadingHTTPServer) -> None:
    server.shutdown()
    server.server_close()
