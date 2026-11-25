"""Developer eval runner: tasks, scoring and the aggregate (S-DEV-036, S-GEN-041, S-GEN-065)."""
import copy
import json
import os
import subprocess
import tempfile
import unittest

from helpers import run_cli
from common import HarnessError
from eval_aggregate import aggregate, summary
from eval_task import load_task

STAFF = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMA = os.path.join(STAFF, "evals", "schemas", "developer-task.schema.json")

# A fake test runner: one testcase per test file matching the glob; it passes when impl.txt contains the
# file's text. cases.txt adds fixed testcases (the existing suite).
RUNNER = """#!/bin/sh
mkdir -p reports; out=""
for f in $1; do
  [ -f "$f" ] || continue
  if grep -qF "$(cat "$f")" impl.txt 2>/dev/null; then out="$out<testcase classname=\\"$f\\" name=\\"t\\"/>"
  else out="$out<testcase classname=\\"$f\\" name=\\"t\\"><failure/></testcase>"; fi
done
printf '<testsuites><testsuite>%s%s</testsuite></testsuites>' "$(cat cases.txt 2>/dev/null)" "$out" > "$2"
"""
SANDBOX = {"version": 1, "setup": ["true"], "build": ["test ! -f broken-build"],
           "unit": {"test": "sh t.sh 'backend/src/*.test.ts' reports/unit.xml", "report": "reports/unit.xml"},
           "api": {"test": "sh t.sh 'tests/api/heldout/*.api.test.ts' reports/api.xml", "report": "reports/api.xml"},
           "heldout_dir": "tests/api/heldout"}
ENTRY = {"source": ["backend/**", "impl.txt"], "unit_tests": ["backend/src/**/*.test.ts"], "generated": []}
EXISTING = '<testcase classname="backend/src/a.test.ts" name="existing"/>'


def product_repo(files):
    d = tempfile.mkdtemp()
    for path, content in files.items():
        os.makedirs(os.path.dirname(os.path.join(d, path)) or d, exist_ok=True)
        with open(os.path.join(d, path), "w") as fh:
            fh.write(content)
    for args in (["init", "-q"], ["add", "-A"], ["-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "-m", "real history"]):
        subprocess.run(["git", "-C", d, *args], check=True)
    sha = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    return d, sha


def task(kind, sha, **over):
    t = {"version": 1, "id": "a1b2c3d4e5f6", "agent": "developer", "set": "promotion", "kind": kind, "base_sha": sha,
         "ticket": {"label": "dev:fix" if kind == "fix" else "dev:implement", "title": "T", "body": "REQ-001"},
         "overlay": [], "reference": [], "heldout": []}
    if kind == "feature":
        t.update(overlay=[{"path": "requirements/x.md", "content": "new req\n"}],
                 reference=[{"path": "impl.txt", "content": "alpha beta\n"}],
                 heldout=[{"name": "one.api.test.ts", "content": "alpha"}, {"name": "two.api.test.ts", "content": "beta"}],
                 heldout_count=2)
    elif kind == "fix":
        t.update(overlay=[{"path": "impl.txt", "content": "broken\n"}],
                 reference=[{"path": "impl.txt", "content": "alpha\n"}],
                 heldout=[{"name": "symptom.api.test.ts", "content": "alpha"}], heldout_count=1)
    else:
        t.update(overlay=[{"path": "requirements/x.md", "content": "defective req\n"}],
                 trap=[{"target": "REQ-001/AC-002", "kinds": ["contradicts", "ambiguous"]}])
    t.update(over)
    return t


def write(d, name, data):
    p = os.path.join(d, name)
    with open(p, "w") as fh:
        json.dump(data, fh)
    return p


class TaskTest(unittest.TestCase):
    def check(self, t):
        d = tempfile.mkdtemp()
        return load_task(write(d, "task.json", t), SCHEMA)

    def test_kinds(self):
        sha = "0" * 40
        for kind in ("feature", "fix", "trap"):
            self.assertEqual(self.check(task(kind, sha))["kind"], kind)

    def test_refusals(self):
        sha = "0" * 40
        bad = [
            task("fix", sha, ticket={"label": "dev:implement", "title": "T", "body": "b"}),        # wrong label
            task("trap", sha, reference=[{"path": "impl.txt", "content": "x"}]),                    # trap with code
            task("trap", sha, trap=[{"target": "REQ-001/AC-002", "kinds": ["missing"], "needs": ["data"]}]),
            task("feature", sha, overlay=[{"path": ".github/workflows/x.yml", "content": "x"}]),   # outside a task
            task("feature", sha, reference=[{"path": "requirements/r.md", "content": "x"}]),       # outside DEV scope
            task("feature", sha, overlay=[{"path": "../x", "content": "x"}]),                       # schema: escape
            task("feature", sha, heldout=[{"name": "x.ts", "content": "x"}]),                       # schema: not an API test
            task("feature", sha, id="Feature-0001"),                                                 # schema: id pattern
        ]
        for t in bad:
            with self.assertRaises(HarnessError):
                self.check(t)

    def test_materialize_and_event(self):
        product, sha = product_repo({"impl.txt": "base\n", "untracked-later": "x"})
        with open(os.path.join(product, "ignored-local-file"), "w") as fh:
            fh.write("not tracked")
        d = tempfile.mkdtemp()
        p = write(d, "task.json", task("feature", sha))
        out = os.path.join(d, "tree")
        res = run_cli("eval_task.py", "materialize", "--task", p, "--product", product, "--layers", "overlay", "--out", out)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("alpha", res.stdout + res.stderr)
        self.assertTrue(os.path.exists(os.path.join(out, "requirements/x.md")))
        self.assertFalse(os.path.exists(os.path.join(out, "ignored-local-file")))
        with open(os.path.join(out, "impl.txt")) as fh:
            self.assertEqual(fh.read(), "base\n")        # no reference
        self.assertFalse(os.path.exists(os.path.join(out, "tests/api/heldout")))
        log = subprocess.run(["git", "-C", out, "log", "--format=%s %an %ad"], capture_output=True, text=True).stdout
        self.assertEqual(log.strip().splitlines(), ["Initial commit eval Sat Jan 1 00:00:00 2000 +0000"])
        res = run_cli("eval_task.py", "materialize", "--task", p, "--product", product, "--layers", "reference", "--out", out)
        self.assertNotEqual(res.returncode, 0)            # the overlay always comes first
        res = run_cli("eval_task.py", "event", "--task", p, "--operator", "op", "--repo", "o/r",
                      "--out-event", os.path.join(d, "e.json"), "--out-comments", os.path.join(d, "c.json"))
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(os.path.join(d, "e.json")) as fh:
            event = json.load(fh)
        self.assertEqual((event["issue"]["user"]["login"], event["issue"]["labels"]), ("op", [{"name": "dev:implement"}]))

    def test_wrong_base_commit(self):
        product, _ = product_repo({"impl.txt": "base\n"})
        d = tempfile.mkdtemp()
        p = write(d, "task.json", task("feature", "1" * 40))
        res = run_cli("eval_task.py", "materialize", "--task", p, "--product", product, "--layers", "overlay",
                      "--out", os.path.join(d, "tree"))
        self.assertIn("input_invalid", res.stderr)

    def test_sandbox(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "code.yml"), "w") as fh:
            fh.write("version: 1\nareas:\n  system:\n    sandbox:\n      setup: [a]\n      build: [b]\n"
                     "      unit_test: c\n      unit_report: r/u.xml\n")
        with open(os.path.join(d, "tests.yml"), "w") as fh:
            fh.write("version: 1\nareas:\n  system:\n    api:\n      sandbox:\n        test: d\n        report: r/a.xml\n")
        out = os.path.join(d, "s.json")
        res = run_cli("eval_task.py", "sandbox", "--code-yml", os.path.join(d, "code.yml"),
                      "--tests-yml", os.path.join(d, "tests.yml"), "--out", out)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(out) as fh:
            s = json.load(fh)
        self.assertEqual((s["build"], s["unit"]["test"], s["api"]["report"]), (["b"], "c", "r/a.xml"))


class ScoreTest(unittest.TestCase):
    def score(self, t, proposed=None, record=None, product_files=None):
        product, sha = product_repo(product_files or {"impl.txt": "base\n", "t.sh": RUNNER, "cases.txt": EXISTING})
        t = copy.deepcopy(t)
        t["base_sha"] = sha
        d = tempfile.mkdtemp()
        validated = {"proposed_files": proposed or [], "defect_items": [], "design_requests": []}
        if isinstance(proposed, dict):
            validated = proposed
        args = ["--task", write(d, "task.json", t), "--product", product,
                "--run-record", write(d, "rr.json", record or {"status": "completed", "validation": {"ok": True}, "cost_usd": 1.5}),
                "--validated", write(d, "v.json", validated),
                "--meta", write(d, "meta.json", {"area": "system", "code_map_entry": ENTRY}),   # dev-meta.json's real shape
                "--sandbox", write(d, "sb.json", SANDBOX), "--work", os.path.join(d, "work"), "--out", os.path.join(d, "r.json")]
        res = run_cli("eval_score.py", *args)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("alpha", res.stdout + res.stderr)     # no task content in the log
        with open(os.path.join(d, "r.json")) as fh:
            return json.load(fh)

    def test_feature(self):
        r = self.score(task("feature", ""), [{"path": "impl.txt", "op": "modify", "content": ["alpha\n"]}])
        self.assertEqual((r["heldout_passed"], r["heldout_count"], r["suite_green"], r["breaches"]), (1, 2, True, []))
        r = self.score(task("feature", ""), [{"path": "impl.txt", "op": "modify", "content": ["alpha beta\n"]}])
        self.assertEqual(r["heldout_passed"], 2)

    def test_feature_breaking_the_build_or_suite(self):
        r = self.score(task("feature", ""), [{"path": "impl.txt", "op": "modify", "content": ["alpha beta\n"]},
                                             {"path": "broken-build", "op": "add", "content": ["x\n"]}])
        self.assertEqual((r["suite_green"], r["heldout_passed"], r["breaches"]), (False, 0, ["suite_not_green"]))
        r = self.score(task("feature", ""), [{"path": "impl.txt", "op": "modify", "content": ["alpha beta\n"]},
                                             {"path": "cases.txt", "op": "modify",
                                              "content": ['<testcase classname="backend/src/a.test.ts" name="existing"><failure/></testcase>']}])
        self.assertEqual((r["suite_green"], r["breaches"]), (False, ["suite_not_green"]))

    def test_fix_with_a_regression_test(self):
        r = self.score(task("fix", ""), [{"path": "impl.txt", "op": "modify", "content": ["alpha\n"]},
                                         {"path": "backend/src/fix.test.ts", "op": "add", "content": ["alpha"]}])
        self.assertEqual((r["fixed"], r["regression_test"], r["bug_encoding"], r["breaches"]), (True, True, 0, []))

    def test_fix_without_a_test_and_with_a_bug_encoding_test(self):
        r = self.score(task("fix", ""), [{"path": "impl.txt", "op": "modify", "content": ["alpha\n"]}])
        self.assertEqual((r["fixed"], r["regression_test"]), (True, False))
        # The agent "fixes" by encoding the bug: its test passes on the seeded version, fails on the correction.
        r = self.score(task("fix", ""), [{"path": "backend/src/bug.test.ts", "op": "add", "content": ["broken"]}])
        self.assertEqual((r["fixed"], r["regression_test"], r["bug_encoding"]), (False, False, 1))
        self.assertIn("bug_encoding", r["breaches"])

    def test_trap(self):
        hit = {"target": "REQ-001/AC-002", "kind": "contradicts", "evidence_refs": ["x"], "text": "t"}
        other = {"target": "REQ-001/AC-003", "kind": "missing", "evidence_refs": ["x"], "text": "t"}
        r = self.score(task("trap", ""), {"proposed_files": [], "defect_items": [hit, other], "design_requests": []})
        self.assertEqual((r["traps_matched"], r["escalations"], r["false_escalations"], r["breaches"]), (1, 2, 1, []))
        self.assertEqual(r["false_near_misses"], 1)              # REQ-001/AC-003: the trap's REQ, another AC
        unrelated = {"target": "REQ-007/AC-001", "kind": "missing", "evidence_refs": ["x"], "text": "t"}
        r = self.score(task("trap", ""), {"proposed_files": [], "defect_items": [hit, unrelated], "design_requests": []})
        self.assertEqual((r["false_escalations"], r["false_near_misses"]), (1, 0))
        wrong_kind = dict(hit, kind="untestable")
        r = self.score(task("trap", ""), {"proposed_files": [{"path": "backend/src/a.ts", "op": "add", "content": ["x"]}],
                                          "defect_items": [wrong_kind], "design_requests": []})
        self.assertEqual((r["traps_matched"], r["breaches"]), (0, ["code_for_trapped_ac"]))

    def test_a_completed_run_needs_the_code_map(self):
        d = tempfile.mkdtemp()
        product, sha = product_repo({"impl.txt": "base\n"})
        res = run_cli("eval_score.py", "--task", write(d, "t.json", task("trap", sha)), "--product", product,
                      "--run-record", write(d, "rr.json", {"status": "completed", "validation": {"ok": True}}),
                      "--validated", write(d, "v.json", {"proposed_files": []}),
                      "--meta", write(d, "m.json", {"area": "system"}), "--sandbox", write(d, "sb.json", SANDBOX),
                      "--work", os.path.join(d, "w"), "--out", os.path.join(d, "r.json"))
        self.assertIn("artifact_missing", res.stderr)

    def test_failed_runs(self):
        r = self.score(task("feature", ""), record={"status": "crashed", "validation": {"ok": False, "reason": "schema_invalid"}})
        self.assertEqual((r["status"], r["breaches"], r["heldout_passed"]), ("crashed", ["invalid_output"], 0))
        r = self.score(task("feature", ""), record={"status": "timeout", "validation": {"ok": False, "reason": "claude_timeout"}})
        self.assertEqual((r["status"], r["breaches"]), ("timeout", []))


def result(kind, **kw):
    r = {"kind": kind, "status": "completed", "cost_usd": 1.0, "heldout_passed": 0, "heldout_count": 0, "fixed": False,
         "regression_test": False, "traps_planted": 0, "traps_matched": 0, "escalations": 0, "false_escalations": 0,
         "breaches": []}
    r.update(kw)
    return r


class AggregateTest(unittest.TestCase):
    def promotion(self):
        return ([result("feature", heldout_passed=4, heldout_count=5)] * 5
                + [result("fix", fixed=True, regression_test=True)] * 3
                + [result("trap", traps_planted=1, traps_matched=1, escalations=1)] * 2)

    def test_passing_set(self):
        agg = aggregate(self.promotion(), "set-1", "developer", "0" * 40, "m")
        self.assertEqual(agg["metrics"]["ac_pass_rate"], 0.8)
        self.assertTrue(agg["passed"])
        self.assertEqual((agg["cost_usd"], agg["statuses"]["completed"]), (10.0, 10))
        text = summary(agg)
        self.assertIn("**pass**", text)
        self.assertNotIn("task_id", json.dumps(agg))

    def test_stray_escalation_breakdown(self):
        rs = self.promotion()
        rs[0] = result("feature", heldout_passed=4, heldout_count=5, escalations=1, false_escalations=1)
        rs[8] = result("trap", traps_planted=1, traps_matched=1, escalations=2, false_escalations=1, false_near_misses=1)
        agg = aggregate(rs, "s", "developer", "0" * 40, "m", rescore_of="123")
        self.assertEqual(agg["false_escalations_by"], {"feature": 1, "fix": 0, "trap_near_miss": 1, "trap_unrelated": 0})
        self.assertEqual((agg["escalations_raised"], agg["metrics"]["false_escalation_rate"]), (4, 0.5))
        self.assertIn("re-score of run 123", summary(agg))

    def test_failing_sets(self):
        rs = self.promotion()
        rs[5] = result("fix", fixed=True)                        # 2 of 3 regression tests: 67% < 70%
        agg = aggregate(rs, "s", "developer", "0" * 40, "m")
        self.assertEqual((agg["meets"]["regression_test_rate"], agg["passed"]), (False, False))
        rs = self.promotion()
        rs[0] = result("feature", heldout_passed=5, heldout_count=5, breaches=["suite_not_green"])
        agg = aggregate(rs, "s", "developer", "0" * 40, "m")
        self.assertEqual((agg["hard_limit_breaches"], agg["passed"]), ({"suite_not_green": 1}, False))
        agg = aggregate([r for r in self.promotion() if r["kind"] != "fix"], "s", "developer", "0" * 40, "m")
        self.assertIsNone(agg["metrics"]["fix_rate"])            # no fix task: null, and it fails
        self.assertFalse(agg["passed"])

    def test_cli_counts_results(self):
        d = tempfile.mkdtemp()
        for i, r in enumerate(self.promotion()[:3]):
            write(d, f"r{i}.json", r)
        res = run_cli("eval_aggregate.py", "--results", d, "--set-id", "s", "--staff-sha", "0" * 40, "--model", "m",
                      "--expected", "10", "--out", os.path.join(d, "..", "agg.json"))
        self.assertIn("artifact_missing", res.stderr)


if __name__ == "__main__":
    unittest.main()
