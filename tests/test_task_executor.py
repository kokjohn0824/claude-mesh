import json
import subprocess
import unittest
from unittest import mock

from claude_mesh import task_executor


def _completed(stdout: str, returncode: int = 0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


class TestTaskExecutor(unittest.TestCase):
    def test_run_task_new_session_invokes_claude_with_p_flag(self):
        out = json.dumps({"session_id": "sess-1", "result": "hello back"})
        with mock.patch("subprocess.run", return_value=_completed(out)) as run:
            res = task_executor.run_task("hi", session_id=None)
            args = run.call_args.args[0]
            self.assertEqual(args[0], "claude")
            self.assertIn("-p", args)
            self.assertIn("--output-format", args)
            self.assertIn("json", args)
            self.assertNotIn("--resume", args)
        self.assertEqual(res.session_id, "sess-1")
        self.assertEqual(res.payload, "hello back")
        self.assertFalse(res.needs_human)

    def test_run_task_resumes_existing_session(self):
        out = json.dumps({"session_id": "sess-1", "result": "ok"})
        with mock.patch("subprocess.run", return_value=_completed(out)) as run:
            task_executor.run_task("again", session_id="sess-1")
            args = run.call_args.args[0]
            self.assertIn("--resume", args)
            idx = args.index("--resume")
            self.assertEqual(args[idx + 1], "sess-1")

    def test_run_task_detects_needs_human_marker(self):
        out = json.dumps({
            "session_id": "sess-1",
            "result": "I started but <<NEEDS_HUMAN: please confirm production deploy>> halt",
        })
        with mock.patch("subprocess.run", return_value=_completed(out)):
            res = task_executor.run_task("deploy", session_id=None)
        self.assertTrue(res.needs_human)
        self.assertIn("please confirm production deploy", res.escalation_reason)

    def test_run_task_raises_on_nonzero_exit(self):
        with mock.patch("subprocess.run", return_value=_completed("err", returncode=2)):
            with self.assertRaises(task_executor.TaskError):
                task_executor.run_task("hi", session_id=None)

    def test_run_task_raises_on_invalid_json(self):
        with mock.patch("subprocess.run", return_value=_completed("not json")):
            with self.assertRaises(task_executor.TaskError):
                task_executor.run_task("hi", session_id=None)


if __name__ == "__main__":
    unittest.main()
