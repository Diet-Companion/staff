import json
import os
import tempfile
import unittest

from helpers import STAFF, fixture, run_cli

BASE = ["--run-id", "100-1", "--attempt", "1", "--identity", "example-analyst", "--plugin", "staff-product",
        "--agent", "analyst", "--model", "claude-sonnet-5-5", "--staff-sha", "a" * 40, "--product-sha", "b" * 40,
        "--trigger-type", "comment", "--trigger-ref", "example/shop#7",
        "--plugins-root", os.path.join(STAFF, "plugins")]


class RunRecordTest(unittest.TestCase):
    def write(self, *extra):
        d = tempfile.mkdtemp()
        out = os.path.join(d, "run-record.json")
        proc = run_cli("run_record.py", "write", "--out", out, *BASE, *extra)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(out) as fh:
            return out, json.load(fh)

    def test_completed_run(self):
        d = tempfile.mkdtemp()
        result = os.path.join(d, "result.json")
        with open(result, "w") as fh:
            json.dump({"ok": True, "cost_usd": 0.4, "num_turns": 6, "duration_ms": 42000}, fh)
        _, rec = self.write("--input", fixture("comments.json"), "--result", result,
                            "--validated", fixture("output-drafts.json"))
        self.assertEqual((rec["status"], rec["outcome"], rec["validation"]), ("completed", "drafts_and_questions",
                                                                             {"ok": True, "reason": None}))
        self.assertEqual(len(rec["input_sha256"]), 64)
        self.assertEqual((rec["cost_usd"], rec["num_turns"], rec["duration_s"]), (0.4, 6, 42.0))
        self.assertEqual(rec["plugin_versions"], {"staff-core": "0.1.0", "staff-product": "0.1.0"})
        self.assertEqual(rec["role"]["req_ids"], ["REQ-001", "REQ-002", "REQ-003"])
        self.assertEqual(rec["role"]["rule_ids_changed"], ["new"])
        self.assertEqual((rec["staff_sha"], rec["product_sha"], rec["model"]), ("a" * 40, "b" * 40, "claude-sonnet-5-5"))

    def test_failed_runs_map_to_status(self):
        for reason, status in (("cost_cap", "cap_hit"), ("redaction_hit", "redaction_dropped"),
                               ("claude_timeout", "timeout"), ("schema_invalid", "crashed")):
            with self.subTest(reason):
                _, rec = self.write("--reason", reason, "--validated", fixture("output-drafts.json"))
                self.assertEqual((rec["status"], rec["outcome"], rec["validation"]["reason"]), (status, "failed", reason))
                self.assertEqual(rec["role"], {})

    def test_update_adds_comment_urls(self):
        out, _ = self.write("--reason", "cost_cap")
        url = "https://github.com/example/shop/issues/7#issuecomment-1"
        proc = run_cli("run_record.py", "update", "--record", out, "--comment-url", url)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(out) as fh:
            rec = json.load(fh)
        self.assertEqual((rec["comment_urls"], rec["output_refs"]), ([url], [url]))


if __name__ == "__main__":
    unittest.main()
