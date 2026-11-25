import copy
import json
import os
import re
import tempfile
import unittest

from helpers import STAFF, fixture, run_cli

import append_run_log as arl
from common import HarnessError

LOG = fixture("run-log.jsonl")
BOT = arl.WRITER


def fixture_entries():
    with open(LOG) as fh:
        return [json.loads(line) for line in fh]


def first(kind):
    return copy.deepcopy(next(e for e in fixture_entries() if e["record_kind"] == kind))


class FakeGh:
    """Just enough of `gh api` for the issue transport: list, create, comment, list comments."""

    def __init__(self, label_applies=True):
        self.issues, self.comments, self.label_applies, self.calls = [], {}, label_applies, []

    def __call__(self, args):
        self.calls.append(args)
        path = next(a for a in args if a.startswith("repos/"))
        if "-X" not in args:
            if path.endswith("comments?per_page=100"):
                n = int(re.search(r"issues/(\d+)/comments", path).group(1))
                return "".join(json.dumps(c) + "\n" for c in self.comments.get(n, []))
            return "".join(json.dumps(i) + "\n" for i in self.issues)
        fields = dict(a.split("=", 1) for a in args if "=" in a and not a.startswith("repos/"))
        if path.endswith("/issues"):
            number = 100 + len(self.issues)
            issue = {"number": number, "title": fields["title"], "user": {"login": BOT, "type": "Bot"},
                     "labels": [{"name": arl.LOG_LABEL}] if self.label_applies else []}
            self.issues.append(issue)
            return json.dumps(issue)
        n = int(re.search(r"issues/(\d+)/comments", path).group(1))
        with open(fields["body"][1:]) as fh:
            body = fh.read()
        cid = 5000 + sum(len(v) for v in self.comments.values())
        self.comments.setdefault(n, []).append({"id": cid, "user": {"login": BOT, "type": "Bot"}, "body": body,
                                                "created_at": "2026-11-20T10:00:00Z",
                                                "updated_at": "2026-11-20T10:00:00Z"})
        return f"https://github.com/example/shop/issues/{n}#issuecomment-{cid}\n"


class SchemaTest(unittest.TestCase):
    def test_fixture_entries_are_valid(self):
        for e in fixture_entries():
            with self.subTest(e["record_kind"], run=e["run_id"]):
                self.assertIsNone(arl.schema_error(e))

    def test_run_record_output_is_a_valid_entry(self):
        # Cross-check: every field run_record.py writes is in the log schema.
        d = tempfile.mkdtemp()
        result = os.path.join(d, "result.json")
        with open(result, "w") as fh:
            json.dump({"ok": True, "cost_usd": 0.4, "num_turns": 6, "duration_ms": 42000}, fh)
        for extra in (["--result", result, "--validated", fixture("output-drafts.json"), "--input", fixture("comments.json")],
                      ["--reason", "cost_cap"]):
            out = os.path.join(d, "rec.json")
            proc = run_cli("run_record.py", "write", "--out", out, "--run-id", "100-1", "--attempt", "1",
                           "--identity", "example-analyst", "--plugin", "staff-product", "--agent", "analyst",
                           "--model", "claude-sonnet-5-5", "--staff-sha", "a" * 40, "--product-sha", "b" * 40,
                           "--trigger-type", "comment", "--trigger-ref", "example/shop#7",
                           "--plugins-root", os.path.join(STAFF, "plugins"), *extra)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            with open(out) as fh:
                entry = arl.entry_from_record(json.load(fh))
            self.assertIsNone(arl.schema_error(entry), extra)

    def test_rejects_free_text_and_unknown_fields(self):
        cases = {
            "prose in role": ("agent_run", lambda e: e["role"].__setitem__("note", "The model said hello")),
            "unknown field": ("agent_run", lambda e: e.__setitem__("transcript", "x")),
            "bad status": ("agent_run", lambda e: e.__setitem__("status", "fine")),
            "reason with spaces": ("agent_run", lambda e: e["validation"].__setitem__("reason", "schema invalid")),
            "verdict outside set": ("verdict_update", lambda e: e.__setitem__("human_verdict", "duplicate")),
            "minutes over a day": ("verdict_update", lambda e: e.__setitem__("review_minutes", 481)),
            "zero minutes": ("verdict_update", lambda e: e.__setitem__("review_minutes", 0)),
            "note field": ("verdict_update", lambda e: e.__setitem__("note", "looks fine")),
            "bad item id": ("verdict_update", lambda e: e["items"].__setitem__("first draft", "accepted")),
        }
        for name, (kind, mutate) in cases.items():
            with self.subTest(name):
                e = first(kind)
                mutate(e)
                self.assertIsNotNone(arl.schema_error(e))
        self.assertEqual(arl.schema_error({"record_kind": "timing"}), "record_kind is not agent_run or verdict_update")

    def test_check_fails_closed_on_redaction(self):
        e = first("agent_run")
        e["role"]["req_ids"] = ["sk-ant-abcdefghij123456"]  # passes the token pattern, fails redaction
        self.assertIsNone(arl.schema_error(e))
        with self.assertRaises(HarnessError) as ctx:
            arl.check(e)
        self.assertEqual(ctx.exception.reason, "redaction_hit")
        self.assertNotIn("sk-ant", str(ctx.exception))


class CommentStoreTest(unittest.TestCase):
    def test_body_round_trip(self):
        e = first("verdict_update")
        body = arl.render_body(e)
        self.assertTrue(body.startswith(arl.MARKER))
        self.assertEqual(arl.parse_body(body), e)
        self.assertEqual(arl.parse_body(body.replace("\n", "\r\n")), e)
        self.assertIsNone(arl.parse_body("just a comment"))
        self.assertIsNone(arl.parse_body(arl.MARKER + "\nx\n```json\n{not json}\n```\n"))

    def test_export_trusts_only_the_recorder(self):
        good, other = first("agent_run"), first("verdict_update")
        invalid = dict(good, status="fine")
        comments = [
            {"user": {"login": BOT}, "body": arl.render_body(good), "created_at": "t", "updated_at": "t"},
            {"user": {"login": "test-operator"}, "body": arl.render_body(other)},   # spoofed by a human
            {"user": {"login": "example-analyst[bot]"}, "body": arl.render_body(other)},  # another bot
            {"user": {"login": BOT}, "body": "Outcome store notice"},
            {"user": {"login": BOT}, "body": arl.render_body(invalid)},
            {"user": {"login": BOT}, "body": arl.render_body(other), "created_at": "t", "updated_at": "u"},
        ]
        entries, counts = arl.entries_from_comments(comments)
        self.assertEqual(entries, [good, other])
        self.assertEqual(counts, {"kept": 2, "other_author": 2, "not_entry": 1, "invalid": 1, "edited": 1})

    def test_dedupe_keeps_latest_run_entry_and_one_per_review(self):
        run, review = first("agent_run"), first("verdict_update")
        later = dict(run, logged_at="2026-12-01T00:00:00Z", comment_urls=[])
        out = arl.dedupe([run, review, later, copy.deepcopy(review)])
        self.assertEqual(len(out), 2)
        self.assertIn(later, out)

    def test_issue_transport_creates_monthly_issue_once(self):
        gh = FakeGh()
        d = tempfile.mkdtemp()
        e1, e2 = first("agent_run"), first("verdict_update")
        url1 = arl.append_issue("example/shop", e1, run=gh, workdir=d)
        url2 = arl.append_issue("example/shop", e2, run=gh, workdir=d)
        self.assertEqual([i["title"] for i in gh.issues], ["Staff outcome store 2026-11"])
        self.assertTrue(url1.endswith("issues/100#issuecomment-5000"))
        self.assertTrue(url2.endswith("issues/100#issuecomment-5001"))
        self.assertEqual(os.listdir(d), [])  # temp body files removed
        dec = dict(e1, logged_at="2026-12-01T00:00:00Z", run_id="300-1")
        arl.append_issue("example/shop", dec, run=gh, workdir=d)
        self.assertEqual(len(gh.issues), 2)
        entries, counts = arl.entries_from_comments(arl.fetch_comments("example/shop", run=gh))
        self.assertEqual([e["run_id"] for e in entries], [e1["run_id"], e2["run_id"], "300-1"])
        entries, _ = arl.entries_from_comments(arl.fetch_comments("example/shop", run=gh, since="2026-12"))
        self.assertEqual([e["run_id"] for e in entries], ["300-1"])

    def test_issues_from_other_authors_are_not_the_store(self):
        gh = FakeGh()
        gh.issues.append({"number": 7, "title": "Staff outcome store 2026-11", "user": {"login": "someone"}})
        arl.append_issue("example/shop", first("agent_run"), run=gh, workdir=tempfile.mkdtemp())
        self.assertEqual([i["number"] for i in gh.issues], [7, 101])
        self.assertNotIn(7, gh.comments)

    def test_missing_label_fails_closed(self):
        with self.assertRaises(HarnessError) as ctx:
            arl.append_issue("example/shop", first("agent_run"), run=FakeGh(label_applies=False),
                             workdir=tempfile.mkdtemp())
        self.assertEqual(ctx.exception.reason, "log_store_failed")


class CliTest(unittest.TestCase):
    def test_append_jsonl_and_export(self):
        d = tempfile.mkdtemp()
        log = os.path.join(d, "runs.jsonl")
        rec = first("agent_run")
        for k in ("log_version", "logged_at"):
            rec.pop(k)
        rec_path = os.path.join(d, "run-record.json")
        with open(rec_path, "w") as fh:
            json.dump(rec, fh)
        proc = run_cli("append_run_log.py", "append", "--record", rec_path, "--jsonl", log)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        entry_path = os.path.join(d, "entry.json")
        with open(entry_path, "w") as fh:
            json.dump(first("verdict_update"), fh)
        self.assertEqual(run_cli("append_run_log.py", "append", "--entry", entry_path, "--jsonl", log).returncode, 0)
        entries = arl.read_jsonl(log)
        self.assertEqual([e["record_kind"] for e in entries], ["agent_run", "verdict_update"])
        self.assertEqual(entries[0]["log_version"], 1)

        comments = [{"user": {"login": BOT}, "body": arl.render_body(e)} for e in entries]
        cpath, out = os.path.join(d, "comments.json"), os.path.join(d, "export.jsonl")
        with open(cpath, "w") as fh:
            json.dump(comments, fh)
        proc = run_cli("append_run_log.py", "export", "--comments-file", cpath, "--out", out)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("kept 2", proc.stdout)
        self.assertEqual(sorted(e["record_kind"] for e in arl.read_jsonl(out)), ["agent_run", "verdict_update"])

    def test_invalid_entry_is_not_appended(self):
        d = tempfile.mkdtemp()
        log, entry_path = os.path.join(d, "runs.jsonl"), os.path.join(d, "entry.json")
        with open(entry_path, "w") as fh:
            json.dump(dict(first("verdict_update"), note="free text"), fh)
        proc = run_cli("append_run_log.py", "append", "--entry", entry_path, "--jsonl", log)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("log_invalid", proc.stderr)
        self.assertFalse(os.path.exists(log))

    def test_bad_jsonl_line_fails_closed(self):
        d = tempfile.mkdtemp()
        log = os.path.join(d, "runs.jsonl")
        with open(LOG) as src, open(log, "w") as fh:
            fh.write(src.readline())
            fh.write('{"record_kind": "agent_run"}\n')
        with self.assertRaises(HarnessError) as ctx:
            arl.read_jsonl(log)
        self.assertEqual(ctx.exception.reason, "log_invalid")
        self.assertIn(":2", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
