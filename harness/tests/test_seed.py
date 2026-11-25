"""Seeding runs and the validity check of a seeded Developer task (S-GEN-067)."""
import copy
import json
import os
import tempfile
import unittest

import yaml

from helpers import run_cli
from test_eval import RUNNER, SANDBOX, product_repo, task, write

REQ = "---\n" + yaml.safe_dump({"id": "REQ-001", "type": "story", "status": "ready", "quality": {"none": "n/a"},
                                "acceptance_criteria": [{"id": "REQ-001/AC-001"}, {"id": "REQ-001/AC-002"}]}) + "---\nBody\n"
NEW_REQ = REQ.replace("REQ-001", "REQ-002")
BODY = "Area: `system`\n\nREQ-002/AC-001 and REQ-002/AC-002"
EXISTING = '<testcase classname="backend/src/a.test.ts" name="existing"/>'


def product():
    return product_repo({"impl.txt": "base\n", "t.sh": RUNNER, "cases.txt": EXISTING,
                         "requirements/x/REQ-001.md": REQ})


def seeded(kind, sha, **over):
    t = task(kind, sha)
    t.pop("heldout_count", None)
    t["ticket"]["body"] = BODY if kind != "fix" else "Area: `system`\n\nREQ-001/AC-001 breaks: I saw X, expected Y."
    if kind != "fix":
        t["overlay"] = [{"path": "requirements/x/REQ-002.md", "content": NEW_REQ}]
    if kind == "trap":
        t["trap"] = [{"target": "REQ-002/AC-002", "kinds": ["contradicts"]}]
    t.update(over)
    return t


class CheckTest(unittest.TestCase):
    def check(self, t):
        prod, sha = product()
        t = copy.deepcopy(t)
        t["base_sha"] = sha
        d = tempfile.mkdtemp()
        out, out_task = os.path.join(d, "check.json"), os.path.join(d, "task.json")
        res = run_cli("seed_check.py", "--task", write(d, "in.json", t), "--product", prod,
                      "--sandbox", write(d, "sb.json", SANDBOX), "--work", os.path.join(d, "w"),
                      "--out", out, "--out-task", out_task)
        self.assertNotIn("alpha", res.stdout + res.stderr)
        with open(out) as fh:
            check = json.load(fh)
        self.assertEqual(res.returncode == 0, check["ok"], res.stderr)
        stored = None
        if os.path.exists(out_task):
            with open(out_task) as fh:
                stored = json.load(fh)
        return check, stored

    def codes(self, check):
        return [f["code"] for f in check["failures"]]

    def test_valid_feature_and_fix(self):
        check, stored = self.check(seeded("feature", ""))
        self.assertEqual((check["ok"], stored["heldout_count"]), (True, 2))
        check, stored = self.check(seeded("fix", ""))
        self.assertEqual((check["ok"], stored["heldout_count"]), (True, 1))

    def test_heldout_must_fail_on_base_and_pass_on_reference(self):
        t = seeded("feature", "", heldout=[{"name": "one.api.test.ts", "content": "a"}])  # passes on both
        check, stored = self.check(t)
        self.assertEqual((self.codes(check), stored), (["heldout_passes_on_base"], None))
        self.assertEqual(check["failures"][0]["ids"], ["tests/api/heldout/one.api.test.ts::t"])
        t = seeded("feature", "", reference=[{"path": "impl.txt", "content": "alpha only\n"}])
        self.assertEqual(self.codes(self.check(t)[0]), ["heldout_fails_on_reference"])

    def test_red_base_and_broken_reference(self):
        red = '<testcase classname="backend/src/a.test.ts" name="existing"><failure/></testcase>'
        t = seeded("fix", "", overlay=[{"path": "impl.txt", "content": "broken\n"}, {"path": "cases.txt", "content": red}])
        self.assertIn("base_tests_failing", self.codes(self.check(t)[0]))
        t = seeded("feature", "", reference=[{"path": "impl.txt", "content": "alpha beta\n"},
                                            {"path": "broken-build", "content": "x"}])
        self.assertEqual(self.codes(self.check(t)[0]), ["reference_build_failed"])

    def test_readiness_and_traps(self):
        check, _ = self.check(seeded("trap", ""))
        self.assertTrue(check["ok"])
        t = seeded("trap", "", trap=[{"target": "REQ-002/AC-009", "kinds": ["missing"]}])
        self.assertEqual(self.codes(self.check(t)[0]), ["trap_target_not_live"])
        t = seeded("trap", "", trap=[{"target": "REQ-002/AC-002", "also": ["REQ-002/AC-001"], "kinds": ["contradicts"]}])
        self.assertTrue(self.check(t)[0]["ok"])
        t = seeded("trap", "", trap=[{"target": "REQ-002/AC-002", "also": ["REQ-002/AC-007"], "kinds": ["contradicts"]}])
        self.assertEqual(self.codes(self.check(t)[0]), ["trap_target_not_live"])
        t = seeded("trap", "", overlay=[{"path": "requirements/x/REQ-002.md", "content": NEW_REQ.replace("ready", "draft")}])
        self.assertIn("not_ready", self.codes(self.check(t)[0]))
        t = seeded("trap", "")
        t["ticket"]["body"] = "REQ-002/AC-001"
        self.assertIn("no_area_line", self.codes(self.check(t)[0]))


class AssembleTest(unittest.TestCase):
    def assemble(self, out, kind="trap", cost=1.0):
        d = tempfile.mkdtemp()
        env = {"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": cost, "num_turns": 9,
               "structured_output": out}
        args = ["assemble", "--envelope", write(d, "env.json", env), "--max-run-usd", "6", "--kind", kind,
                "--set", "promotion", "--base-sha", "a" * 40, "--run-id", "1-1", "--staff-sha", "b" * 40,
                "--model", "m", "--out", os.path.join(d, "task.json"), "--result", os.path.join(d, "result.json")]
        res = run_cli("seed_task.py", *args)
        with open(os.path.join(d, "result.json")) as fh:
            result = json.load(fh)
        t = None
        if res.returncode == 0:
            with open(os.path.join(d, "task.json")) as fh:
                t = json.load(fh)
        return result, t

    def output(self):
        t = seeded("trap", "a" * 40)
        return {"schema_version": 1, "agent": "seeder-developer", "kind": "trap", "summary": "s",
                **{k: t[k] for k in ("ticket", "overlay", "reference", "heldout", "trap")}}

    def test_assemble(self):
        result, t = self.assemble(self.output())
        self.assertTrue(result["ok"])
        self.assertRegex(t["id"], r"^[a-z0-9]{12}$")
        self.assertEqual((t["base_sha"], t["seeding"]["holdout_seed"], t["set"]), ("a" * 40, True, "promotion"))

    def test_refusals(self):
        self.assertEqual(self.assemble(self.output(), kind="fix")[0]["reason"], "kind_mismatch")
        self.assertEqual(self.assemble(self.output(), cost=9)[0]["reason"], "cost_cap")
        bad = dict(self.output(), reference=[{"path": "impl.txt", "content": "x"}])   # a trap with code
        self.assertEqual(self.assemble(bad)[0]["reason"], "input_invalid")
        self.assertEqual(self.assemble(dict(self.output(), extra=1))[0]["reason"], "schema_invalid")

    def test_request(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "set"))
        write(os.path.join(d, "set"), "x.json", dict(seeded("fix", "a" * 40), summary="old"))
        prev = write(d, "prev.json", seeded("feature", "a" * 40))
        check = write(d, "check.json", {"ok": False, "failures": [{"code": "heldout_passes_on_base"}]})
        out = os.path.join(d, "req.json")
        res = run_cli("seed_task.py", "request", "--kind", "feature", "--slot", "2", "--set", "promotion",
                      "--set-dir", os.path.join(d, "set"), "--previous-task", prev, "--previous-check", check, "--out", out)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(out) as fh:
            req = json.load(fh)
        self.assertEqual(req["existing"][0]["summary"], "old")
        self.assertEqual(req["previous"]["failures"], [{"code": "heldout_passes_on_base"}])
        self.assertNotIn("base_sha", req["previous"]["task"])


if __name__ == "__main__":
    unittest.main()
