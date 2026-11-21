import copy
import json
import os
import tempfile
import unittest

from helpers import fixture, load, run_cli

import log_review as lr
from append_run_log import read_jsonl, schema_error
from build_input import build
from common import HarnessError

OPERATORS = {"test-operator", "second-op"}
LOG = fixture("run-log.jsonl")


class ParseTest(unittest.TestCase):
    def test_valid_commands(self):
        cases = {
            "/review 12m": (12, None, None, {}),
            "/review 12": (12, None, None, {}),
            "/review 1h": (60, None, None, {}),
            "/review 1h30m accepted": (90, "accepted", None, {}),
            "/review 1h5 Edit run=123-2": (65, "edited", "123-2", {}),
            "/review 7min rejected\nwhy: wrong area": (7, "rejected", None, {}),
            "  /review 3m REQ-001=accepted REQ-001/AC-002:Rejected": (
                3, "edited", None, {"REQ-001": "accepted", "REQ-001/AC-002": "rejected"}),
            "/review 4m REQ-001=accepted REQ-002=accepted": (4, "accepted", None, {"REQ-001": "accepted",
                                                                                  "REQ-002": "accepted"}),
            "/review 4m R-010=reject": (4, "rejected", None, {"R-010": "rejected"}),
        }
        for body, (minutes, verdict, run_id, items) in cases.items():
            with self.subTest(body):
                self.assertEqual(lr.parse_command(body),
                                 {"minutes": minutes, "verdict": verdict, "run_id": run_id, "items": items})

    def test_not_a_command(self):
        for body in ("", None, "Q-001: a", "/reviewer 12m", "please /review 12m", "/analyst"):
            with self.subTest(body):
                self.assertIsNone(lr.parse_command(body))

    def test_invalid_commands_fail_closed(self):
        for body in ("/review", "/review accepted", "/review 0m", "/review 481", "/review 9h",
                     "/review 12m great", "/review 12m accepted rejected", "/review 12m run=1 run=2",
                     "/review 12m REQ-001=fine", "/review 12m REQ-001=accepted REQ-001=edited", "/review 12m 3m"):
            with self.subTest(body):
                with self.assertRaises(HarnessError) as ctx:
                    lr.parse_command(body)
                self.assertEqual(ctx.exception.reason, "review_invalid")


class EventTest(unittest.TestCase):
    def setUp(self):
        self.entries = read_jsonl(LOG)
        self.event = load("event-review.json")

    def test_comment_becomes_verdict_update(self):
        e = lr.from_event(self.event, OPERATORS, self.entries)
        self.assertIsNone(schema_error(e))
        self.assertEqual(e["run_id"], "201-1")  # latest completed run on #7 before the comment
        self.assertEqual((e["review_minutes"], e["human_verdict"]), (65, "edited"))
        self.assertEqual(e["items"], {"REQ-001": "accepted", "REQ-002": "edited"})
        self.assertEqual((e["verdict_by"], e["verdict_at"], e["target_ref"]),
                         ("Test-Operator", "2026-11-17T12:30:00Z", "example/shop#7"))
        self.assertEqual(e["source"], {"type": "comment",
                                       "ref": "https://github.com/example/shop/issues/7#issuecomment-9101"})
        self.assertNotIn("example.com", json.dumps(e))  # the note line is never stored

    def test_resolution_skips_failed_and_later_runs(self):
        ev = copy.deepcopy(self.event)
        ev["issue"]["number"] = 9
        ev["comment"]["created_at"] = "2026-11-20T10:00:00Z"  # 204-1 crashed at 09:00, 203-1 completed at 08:00
        self.assertEqual(lr.from_event(ev, OPERATORS, self.entries)["run_id"], "203-1")
        ev["comment"]["created_at"] = "2026-11-20T07:00:00Z"  # before any run on #9
        self.assertIsNone(lr.from_event(ev, OPERATORS, self.entries)["run_id"])

    def test_explicit_run_wins(self):
        ev = copy.deepcopy(self.event)
        ev["comment"]["body"] = "/review 5m accepted run=200-1"
        self.assertEqual(lr.from_event(ev, OPERATORS, self.entries)["run_id"], "200-1")

    def test_only_operators_count(self):
        for login, kind in (("drive-by-user", "User"), ("test-operator", "Bot"), ("example-analyst[bot]", "Bot")):
            with self.subTest(login):
                ev = copy.deepcopy(self.event)
                ev["comment"]["user"] = {"login": login, "type": kind}
                with self.assertRaises(HarnessError) as ctx:
                    lr.from_event(ev, OPERATORS, self.entries)
                self.assertEqual(ctx.exception.reason, "not_operator")

    def test_other_comments_are_ignored(self):
        ev = copy.deepcopy(self.event)
        ev["comment"]["body"] = "Q-001: a"
        self.assertIsNone(lr.from_event(ev, OPERATORS, self.entries))

    def test_cli_comment_and_manual(self):
        d = tempfile.mkdtemp()
        out = os.path.join(d, "entry.json")
        proc = run_cli("log_review.py", "comment", "--event", fixture("event-review.json"),
                       "--operators", fixture("operators.yml"), "--log", LOG, "--out", out)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("run 201-1, 65 min, verdict edited", proc.stdout)

        proc = run_cli("log_review.py", "manual", "206-1", "20m", "rejected", "--by", "test-operator",
                       "--operators", fixture("operators.yml"), "--at", "2026-11-20T11:00:00Z",
                       "--log", LOG, "--out", out)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(out) as fh:
            e = json.load(fh)
        self.assertEqual((e["run_id"], e["target_ref"], e["review_minutes"], e["source"]),
                         ("206-1", "example/shop#12", 20, {"type": "cli", "ref": None}))

        proc = run_cli("log_review.py", "manual", "206-1", "20m", "--by", "nobody",
                       "--operators", fixture("operators.yml"), "--out", out)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not_operator", proc.stderr)
        proc = run_cli("log_review.py", "manual", "206-1", "20m", "--by", "test-operator", "--at", "yesterday",
                       "--out", out)
        self.assertIn("review_invalid", proc.stderr)


class AnalystInputTest(unittest.TestCase):
    def test_review_comments_never_reach_the_analyst(self):
        comments = load("comments.json") + [{
            "id": 1010, "html_url": "https://github.com/example/shop/issues/7#issuecomment-1010",
            "user": {"login": "test-operator", "type": "User"}, "created_at": "2026-11-20T11:00:00Z",
            "updated_at": "2026-11-20T11:00:00Z", "body": "/review 12m accepted\nnice"}]
        data = build(load("event-comment.json"), comments, OPERATORS, ["orders"], "example-analyst[bot]",
                     "100-1", "knowledge/product-core.md", True)
        self.assertNotIn("/review", json.dumps(data["untrusted"]["comments"]))
        self.assertEqual(data["dropped_comments"], 5)


if __name__ == "__main__":
    unittest.main()
