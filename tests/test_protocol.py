import json
import unittest

from claude_mesh import protocol


class TestProtocol(unittest.TestCase):
    def test_message_dataclass_fields(self):
        m = protocol.Message(
            from_id="alex-mac",
            from_ip="192.168.1.10",
            conversation_id="conv-1",
            session_id=None,
            type="task",
            payload="hello",
            needs_human=False,
            timestamp=1700000000,
        )
        self.assertEqual(m.type, "task")
        self.assertIsNone(m.session_id)

    def test_serialize_includes_mesh_version(self):
        m = protocol.Message(
            from_id="a", from_ip="1.1.1.1", conversation_id="c",
            session_id="s", type="reply", payload="ok",
            needs_human=False, timestamp=1,
        )
        body = json.loads(protocol.serialize(m))
        self.assertEqual(body["mesh_version"], "1.0")
        self.assertEqual(body["type"], "reply")
        self.assertEqual(body["session_id"], "s")

    def test_parse_round_trip(self):
        m = protocol.Message(
            from_id="a", from_ip="1.1.1.1", conversation_id="c",
            session_id=None, type="task", payload="p",
            needs_human=False, timestamp=2,
        )
        parsed = protocol.parse(protocol.serialize(m))
        self.assertEqual(parsed, m)

    def test_parse_rejects_unknown_type(self):
        bad = json.dumps({
            "mesh_version": "1.0", "from_id": "a", "from_ip": "1.1.1.1",
            "conversation_id": "c", "session_id": None, "type": "bogus",
            "payload": "p", "needs_human": False, "timestamp": 1,
        })
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse(bad)

    def test_parse_rejects_wrong_version(self):
        bad = json.dumps({
            "mesh_version": "9.9", "from_id": "a", "from_ip": "1.1.1.1",
            "conversation_id": "c", "session_id": None, "type": "task",
            "payload": "p", "needs_human": False, "timestamp": 1,
        })
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse(bad)

    def test_parse_rejects_missing_field(self):
        bad = json.dumps({"mesh_version": "1.0", "type": "task"})
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse(bad)

    def test_new_message_fills_timestamp(self):
        m = protocol.new_message(
            from_id="a", from_ip="1.1.1.1",
            conversation_id="c", session_id=None,
            msg_type="task", payload="p",
        )
        self.assertGreater(m.timestamp, 0)
        self.assertFalse(m.needs_human)


if __name__ == "__main__":
    unittest.main()
