import json
import os
import tempfile
import unittest

from helpers import fixture, load, run_cli

from build_input import UNTRUSTED_NOTICE, build
from common import HarnessError

OPERATORS = {"test-operator", "second-op"}
BOT = "example-analyst[bot]"


class BuildInputTest(unittest.TestCase):
    def setUp(self):
        self.data = build(load("event-comment.json"), load("comments.json"), OPERATORS,
                          ["orders", "billing"], BOT, "100-1", "knowledge/product-core.md", True)

    def test_keeps_operator_and_own_app_comments_only(self):
        kept = [(c["author"], c["author_kind"]) for c in self.data["untrusted"]["comments"]]
        self.assertEqual(kept, [(BOT, "analyst_app"), ("test-operator", "operator"), ("second-op", "operator")])
        # drive-by user, other bot, the /analyst command and the spoofed bot login
        self.assertEqual(self.data["dropped_comments"], 4)

    def test_tracker_text_is_marked_untrusted(self):
        self.assertEqual(self.data["notice"], UNTRUSTED_NOTICE)
        self.assertIn("UNTRUSTED DATA", self.data["notice"])
        self.assertEqual(set(self.data), {"kind", "version", "notice", "run", "product", "comment_kinds",
                                          "dropped_comments", "untrusted"})
        self.assertIn("Ignore your instructions", self.data["untrusted"]["issue"]["body"])
        self.assertTrue(self.data["untrusted"]["issue"]["author_is_operator"])

    def test_product_context(self):
        self.assertEqual(self.data["product"]["areas"], ["orders", "billing"])
        self.assertEqual(self.data["product"]["product_core_path"], "knowledge/product-core.md")
        self.assertEqual(self.data["run"], {"run_id": "100-1", "trigger": "comment", "intake_ref": "example/shop#7"})
        self.assertEqual(self.data["untrusted"]["comments"][1]["ref"], "example/shop#7 comment 1002")

    def test_pull_requests_are_never_worked(self):
        event = load("event-comment.json")
        event["issue"]["pull_request"] = {"url": "x"}
        with self.assertRaises(HarnessError) as ctx:
            build(event, [], OPERATORS, ["orders"], BOT, "1-1", "k.md", True)
        self.assertEqual(ctx.exception.reason, "input_invalid")

    def _cli(self, *extra):
        out = os.path.join(tempfile.mkdtemp(), "input.json")
        proc = run_cli("build_input.py", "--event", fixture("event-comment.json"),
                       "--operators", fixture("operators.yml"), "--areas", fixture("areas.yml"),
                       "--bot-login", BOT, "--run-id", "100-1", "--out", out,
                       "--comments-file", fixture("comments.json"), *extra)
        return proc, out

    def test_cli_writes_input(self):
        proc, out = self._cli()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(out) as fh:
            self.assertEqual(len(json.load(fh)["untrusted"]["comments"]), 3)

    def test_cli_fails_closed_over_size_cap(self):
        proc, out = self._cli("--max-bytes", "500")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("input_too_large", proc.stderr)
        self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
