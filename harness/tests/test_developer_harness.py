"""The Developer's harness path: code map, readiness, input, prompt, output checks, sandbox, comments."""
import base64
import copy
import json
import os
import re
import subprocess
import tempfile
import unittest

from helpers import FIXTURES, STAFF, run_cli

from build_input import build
from code_map import classify, glob_re, load_code_map
from common import HarnessError
from dev_bundle import bundle, load_truth, readiness
from prepare_agent import build_prompt
from render_developer import pr_title, render, render_pr_body
from run_record import role_fields
from validate_output import check_developer, check_schema
from work_sandbox import check_result, clean_line, junit_results

PLUGINS = os.path.join(STAFF, "plugins")
AGENT = os.path.join(PLUGINS, "staff-engineering", "agents", "developer.md")
SCHEMA = os.path.join(PLUGINS, "staff-engineering", "schemas", "developer-output.schema.json")
MAP_SCHEMA = os.path.join(PLUGINS, "staff-engineering", "schemas", "code-map.schema.json")
FIX = os.path.join(FIXTURES, "developer")
CAP_CHARS = int(15_000 * 3.2)  # S-GEN-009
BOT = "diet-companion-engineering[bot]"

ENTRY = {
    "source": ["src/**"], "unit_tests": ["tests/unit/**"], "generated": ["src/gen/**", "package-lock.json"],
    "protected": ["src/auth/**"], "dependency_files": ["package.json"], "verification_config": ["vitest.config.ts"],
    "guard_patterns": [], "test_list": [], "generators": [], "interface_source": "none", "upkeep_tools": [],
}


def load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def fm(data, body=""):
    return "---\n" + json.dumps(data) + "\n---\n" + body


def product():
    """A product checkout: REQ-012 ready (AC-003 retired), quality REQ-020 with an accepted QAS, IF-002."""
    d = tempfile.mkdtemp()
    write(d, "requirements/orders/REQ-012.md", fm({
        "id": "REQ-012", "type": "story", "status": "ready", "quality": ["REQ-020"],
        "acceptance_criteria": [{"id": "REQ-012/AC-001"}, {"id": "REQ-012/AC-002"},
                                {"id": "REQ-012/AC-003", "status": "retired"}]}))
    write(d, "requirements/orders/REQ-013.md", fm({"id": "REQ-013", "type": "story", "status": "draft",
                                                    "acceptance_criteria": [{"id": "REQ-013/AC-001"}]}))
    write(d, "requirements/orders/REQ-014.md", fm({
        "id": "REQ-014", "type": "story", "status": "ready", "quality": {"none": "No quality target applies."},
        "acceptance_criteria": [{"id": "REQ-014/AC-001"}]}))
    write(d, "requirements/orders/REQ-020.md", fm({"id": "REQ-020", "type": "quality", "status": "ready",
                                                    "acceptance_criteria": [{"id": "REQ-020/AC-001"}]}))
    write(d, "requirements/orders/REQ-021.md", fm({"id": "REQ-021", "type": "quality", "status": "ready",
                                                    "acceptance_criteria": [{"id": "REQ-021/AC-001"}]}))
    write(d, "architecture/system/quality/QAS-001.md", fm({"id": "QAS-001", "status": "accepted", "req": "REQ-020"}))
    write(d, "architecture/system/interfaces/IF-002.md", fm({"id": "IF-002", "versions": [
        {"version": "1.0.0", "status": "approved"}, {"version": "1.1.0", "status": "draft"}]}))
    write(d, "architecture/system/adr/ADR-003.md", fm({"id": "ADR-003", "status": "accepted"}))
    write(d, "knowledge/rules/orders/R-004.md", fm({"id": "R-004", "status": "active"}))
    return d


def dev_input(kind="implement", body="Area: `system`\n\nREQ-012/AC-001 and REQ-012/AC-002", operator=True,
              entry=ENTRY, root=None):
    data = {"run": {"run_id": "1-1", "trigger": "label", "intake_ref": "example/shop#21", "ticket_kind": kind},
            "untrusted": {"issue": {"body": body, "author_is_operator": operator}, "comments": []}}
    return bundle(data, root or product(), {"version": 1, "areas": {"system": entry} if entry else {}},
                  ["orders", "system"])


class CodeMapTest(unittest.TestCase):
    def test_globs(self):
        self.assertTrue(glob_re("src/**").match("src/a/b.ts"))
        self.assertTrue(glob_re("**/*.test.ts").match("a.test.ts"))
        self.assertTrue(glob_re("**/*.test.ts").match("x/y/a.test.ts"))
        self.assertFalse(glob_re("src/*.ts").match("src/a/b.ts"))
        self.assertFalse(glob_re("src/**").match("srcx/a.ts"))
        self.assertFalse(glob_re("a.ts").match("a.tsx"))
        self.assertFalse(glob_re("**/a.ts").match("ba.ts"))
        self.assertTrue(glob_re("**/a.ts").match("x/a.ts"))
        self.assertEqual(classify("src/auth/login.ts", ENTRY), {"source", "protected"})
        self.assertEqual(classify("README.md", ENTRY), set())

    def test_load(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "code.yml")
        self.assertEqual(load_code_map(path, MAP_SCHEMA)["areas"], {})  # missing: empty, fail closed later
        with open(path, "w") as fh:
            json.dump({"version": 1, "areas": {"system": dict(ENTRY, sandbox={
                "setup": ["npm ci"], "build": ["npm run build"], "unit_test": "npm test",
                "unit_report": "reports/unit.xml"})}}, fh)
        self.assertIn("system", load_code_map(path, MAP_SCHEMA)["areas"])
        with open(path, "w") as fh:
            json.dump({"version": 1, "areas": {"system": {"source": ["src/**"]}}}, fh)
        with self.assertRaises(HarnessError) as ctx:
            load_code_map(path, MAP_SCHEMA)
        self.assertEqual(ctx.exception.reason, "code_map_invalid")


class ReadinessTest(unittest.TestCase):
    def setUp(self):
        self.truth = load_truth(product())

    def check(self, kind, body):
        return readiness(self.truth, kind, body, True)

    def test_feature(self):
        status, d = self.check("implement", "REQ-012/AC-001, REQ-012/AC-002 against IF-002@1.0.0")
        self.assertEqual((status, d["acs"], d["blockers"]), ("ready", ["REQ-012/AC-001", "REQ-012/AC-002"], []))
        status, d = self.check("implement", "REQ-012")  # a whole requirement: its live ACs
        self.assertEqual((status, d["acs"]), ("ready", ["REQ-012/AC-001", "REQ-012/AC-002"]))
        status, d = self.check("implement", "REQ-014")  # `quality: {none: ...}` links no quality requirement
        self.assertEqual((status, d["blockers"]), ("ready", []))

    def test_waiting(self):
        for body, hint in (("REQ-012/AC-003", "retired"), ("REQ-013/AC-001", "not ready"), ("REQ-099/AC-001", "exist"),
                           ("REQ-021/AC-001", "no accepted QAS"), ("REQ-012/AC-001 IF-002@1.1.0", "approved"),
                           ("nothing here", "names no requirement")):
            with self.subTest(body):
                status, d = self.check("implement", body)
                self.assertEqual(status, "waiting")
                self.assertTrue(any(hint in b for b in d["blockers"]), d["blockers"])

    def test_refactor_fix_and_operator(self):
        self.assertEqual(self.check("implement", "Kind: refactor\nTidy the layout")[0], "ready")
        self.assertEqual(self.check("fix", "Target: R-004")[0], "ready")
        self.assertEqual(self.check("fix", "Target: ADR-003/C-001")[0], "ready")
        self.assertEqual(self.check("fix", "Target: REQ-012/AC-003")[0], "waiting")
        status, d = readiness(self.truth, "implement", "REQ-012/AC-001", False)
        self.assertEqual(status, "waiting")

    def test_bundle(self):
        dev = dev_input()["developer"]
        self.assertEqual((dev["area"], dev["work"], dev["readiness"]["status"]), ("system", "feature", "ready"))
        self.assertEqual(dev_input(entry=None)["developer"]["readiness"]["status"], "waiting")  # no code map
        self.assertEqual(dev_input(kind="bootstrap", body="Area: system", entry=None)["developer"]["readiness"]["status"],
                         "ready")
        self.assertEqual(dev_input(body="REQ-012/AC-001")["developer"]["readiness"]["status"], "waiting")  # no area
        # A non-operator's body is never parsed: an outsider can't make a ticket ready.
        self.assertEqual(dev_input(operator=False)["developer"]["area"], None)


class InputTest(unittest.TestCase):
    def event(self, labels, comment=None):
        ev = {"repository": {"full_name": "o/r"},
              "issue": {"number": 9, "title": "t", "body": "b", "user": {"login": "giokur"},
                        "labels": [{"name": n} for n in labels]}}
        if comment:
            ev["comment"] = comment
        return ev

    def test_ticket_kind(self):
        data = build(self.event(["dev:implement", "agent"]), [], {"giokur"}, ["system"], BOT, "1-1", "k.md", True,
                     agent="developer")
        self.assertEqual((data["kind"], data["run"]["ticket_kind"], data["run"]["trigger"]),
                         ("developer_input", "implement", "label"))
        data = build(self.event(["dev:fix"], {"id": 1}), [], {"giokur"}, ["system"], BOT, "1-1", "k.md", True,
                     agent="developer")
        self.assertEqual((data["run"]["ticket_kind"], data["run"]["trigger"]), ("fix", "answer"))
        for labels in ([], ["dev:fix", "dev:implement"]):
            with self.assertRaises(HarnessError):
                build(self.event(labels), [], {"giokur"}, ["system"], BOT, "1-1", "k.md", True, agent="developer")


class PromptTest(unittest.TestCase):
    def test_contract_and_reference_within_budget(self):
        prompt, tools = build_prompt(AGENT, PLUGINS, ["staff-engineering:developer-reference"], contract="developer")
        self.assertEqual(tools, ["Glob", "Grep", "Read"])
        self.assertIn("The work sandbox", prompt)
        self.assertLess(len(prompt), CAP_CHARS)


def feature_input():
    exp = dev_input()
    exp["run"]["intake_ref"] = "example/shop#21"
    return exp


class CheckDeveloperTest(unittest.TestCase):
    def assert_reason(self, out, reason, expect=None):
        with self.assertRaises(HarnessError) as ctx:
            check_developer(out, expect or feature_input())
        self.assertEqual(ctx.exception.reason, reason)

    def test_fixture_passes(self):
        out = load("developer-feature.json")
        with open(SCHEMA, encoding="utf-8") as fh:
            check_schema(out, json.load(fh))
        check_developer(out, feature_input())

    def test_path_scope(self):
        for path, reason in (("docs/x.md", "path_out_of_scope"), ("src/gen/api.ts", "path_out_of_scope"),
                             (".github/workflows/x.yml", "path_out_of_scope"), ("AGENTS.md", "path_out_of_scope"),
                             ("src/auth/login.py", "flag_missing"), ("package.json", "flag_missing")):
            with self.subTest(path):
                out = load("developer-feature.json")
                out["proposed_files"][0]["path"] = path
                self.assert_reason(out, reason)
        out = load("developer-feature.json")
        out["proposed_files"][0]["path"] = "package.json"
        out["pr"]["flags"] = [{"flag_id": "dependency:package.json", "reason": "new dependency"}]
        self.assert_reason(out, "flag_missing")  # a dependency file also needs a dependencies entry
        out["pr"]["dependencies"] = [{"name": "fastify", "from": None, "to": "5.0.0", "reason": "ADR-007"}]
        check_developer(out, feature_input())
        out = load("developer-feature.json")
        out["proposed_files"].append(copy.deepcopy(out["proposed_files"][0]))
        self.assert_reason(out, "duplicate_id")
        # Forbidden paths stay out even when the code map's globs are broad (S-DEV-005).
        broad = dev_input(entry=dict(ENTRY, source=["**"]))
        for path in (".github/workflows/x.yml", "AGENTS.md", "requirements/orders/REQ-012.md"):
            with self.subTest(path):
                out = load("developer-feature.json")
                out["proposed_files"][0]["path"] = path
                self.assert_reason(out, "path_out_of_scope", broad)

    def test_dependency_entry_only_for_dependency_changes(self):
        base = tempfile.mkdtemp()
        write(base, "package.json", json.dumps({"name": "x", "scripts": {"a": "x"}, "dependencies": {"pg": "^8"}}))

        def proposal(manifest, op="modify"):
            out = load("developer-feature.json")
            out["proposed_files"][0] = {"path": "package.json", "op": op, "content": [json.dumps(manifest)]}
            out["pr"]["flags"] = [{"flag_id": "dependency:package.json", "reason": "manifest edit"}]
            return out

        scripts_only = {"name": "x", "scripts": {"a": "x", "hash": "y"}, "dependencies": {"pg": "^8"}}
        check_developer(proposal(scripts_only), feature_input(), base)  # a script edit needs no entry
        for manifest, op, base_dir in ((dict(scripts_only, dependencies={"pg": "^9"}), "modify", base),
                                       (dict(scripts_only, devDependencies={"x": "1"}), "modify", base),
                                       (scripts_only, "modify", None),       # no base to compare: ask
                                       (scripts_only, "add", base)):
            with self.subTest(manifest=manifest, op=op, base=bool(base_dir)):
                with self.assertRaises(HarnessError) as ctx:
                    check_developer(proposal(manifest, op), feature_input(), base_dir)
                self.assertEqual(ctx.exception.reason, "flag_missing")
        out = proposal(scripts_only)
        out["pr"]["flags"] = []
        with self.assertRaises(HarnessError):  # the flag is still required for any manifest edit
            check_developer(out, feature_input(), base)

    def test_ticket_and_acs(self):
        out = load("developer-feature.json")
        out["pr"]["ticket"] = "example/shop#22"
        self.assert_reason(out, "ticket_mismatch")
        out = load("developer-feature.json")
        out["pr"]["implements_acs"].append({"ac": "REQ-012/AC-003", "part": "full"})
        self.assert_reason(out, "ac_not_ready")
        out = load("developer-feature.json")
        out["pr"]["kind"] = "refactor"
        self.assert_reason(out, "kind_mismatch")
        self.assert_reason(load("developer-feature.json"), "not_ready", dev_input(body="Area: system\nREQ-013/AC-001"))
        self.assert_reason(load("developer-feature.json"), "kind_mismatch", dev_input(kind="fix", body="Area: system\nR-004"))

    def test_question_order_is_fixed_not_failed(self):
        from validate_output import order_questions
        out = load("developer-feature.json")
        q = {"key": {"entity": "x", "target_id": None, "attribute": "y"}, "blocks": ["REQ-012/AC-001"], "text": "t",
             "options": [{"id": "a", "text": "a"}, {"id": "b", "text": "b"}], "recommended": "a"}
        out["questions"] = [dict(q, id="Q-001", blocking=False, priority=2), dict(q, id="Q-002", blocking=True, priority=5)]
        self.assertTrue(order_questions(out))
        self.assertEqual([(x["id"], x["priority"]) for x in out["questions"]], [("Q-002", 1), ("Q-001", 2)])
        self.assertFalse(order_questions(out))  # already in order: unchanged

    def test_silent_no_op_on_a_ready_ticket_fails(self):
        # diet-companion#160: a "Placeholder to be replaced." summary, no PR and nothing raised.
        out = load("developer-feature.json")
        out.update(pr=None, proposed_files=[], design_requests=[], decision_summary="Placeholder to be replaced.")
        self.assert_reason(out, "no_output")
        q = {"id": "Q-001", "key": {"entity": "x", "target_id": None, "attribute": "y"}, "blocks": ["REQ-012/AC-001"],
             "text": "t", "options": [{"id": "a", "text": "a"}, {"id": "b", "text": "b"}], "recommended": "a",
             "blocking": True, "priority": 1}
        check_developer(dict(out, questions=[q]), feature_input())  # a question is an answer
        exp = feature_input()
        exp["developer"]["round"] = {"trigger": "review", "pr": 9, "check_round": 0}
        check_developer(out, exp)  # a PR round may decline in the summary
        exp = feature_input()
        exp["developer"]["readiness"] = {"status": "waiting", "acs": [], "blockers": ["x"]}
        check_developer(out, exp)  # a waiting ticket proposes nothing

    def test_bootstrap_and_fix_shapes(self):
        boot = load("developer-bootstrap.json")
        exp = dev_input(kind="bootstrap", body="Area: system", entry=None)
        self.assert_reason(boot, "unknown_area", exp)  # the fixture drafts `orders`
        boot["code_map"]["area"] = "system"
        check_developer(boot, exp)
        self.assert_reason(load("developer-feature.json"), "kind_mismatch", exp)
        rd = load("developer-requirement-defect.json")
        check_developer(rd, dev_input(kind="fix", body="Area: system\nTarget: REQ-012/AC-002"))
        self.assert_reason(rd, "kind_mismatch")  # classification on an implement ticket


def git_repo(files):
    d = tempfile.mkdtemp()
    for rel, text in files.items():
        write(d, rel, text)
    subprocess.run(["git", "init", "-q", d], check=True)
    subprocess.run(["git", "-C", d, "add", "-A"], check=True)
    subprocess.run(["git", "-C", d, "-c", "user.email=t@e", "-c", "user.name=t", "commit", "-qm", "base",
                    "--allow-empty"], check=True)
    return d


REPORT = ('mkdir -p reports && printf \'<testsuites><testsuite>%s</testsuite></testsuites>\' '
          '"$(cat cases.txt 2>/dev/null)" > reports/unit.xml')


class SandboxTest(unittest.TestCase):
    def apply(self, out, entry=ENTRY):
        repo = git_repo({"src/a.py": "a = 1\n"})
        d = tempfile.mkdtemp()
        v, i = os.path.join(d, "v.json"), os.path.join(d, "i.json")
        with open(v, "w") as fh:
            json.dump(out, fh)
        with open(i, "w") as fh:
            json.dump({"developer": {"code_map_entry": entry}}, fh)
        res = run_cli("work_sandbox.py", "apply", "--validated", v, "--input", i, "--repo", repo, "--out-dir", d)
        return res, repo, d

    def test_apply(self):
        out = {"proposed_files": [
            {"path": "src/a.py", "op": "modify", "content": ["a = 2\n", "b = 3\n"]},
            {"path": "tests/unit/test_a.py", "op": "add", "content": ["def test_a():\n    assert True\n"]}]}
        entry = dict(ENTRY, generators=[{"generator_id": "lock", "version": "1", "command": "echo lock > package-lock.json",
                                         "inputs": ["src/**"], "outputs": ["package-lock.json"]}])
        res, repo, d = self.apply(out, entry)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(os.path.join(d, "applied.json")) as fh:
            applied = json.load(fh)
        by = {f["path"]: f for f in applied["files"]}
        self.assertEqual(set(by), {"src/a.py", "tests/unit/test_a.py", "package-lock.json"})
        self.assertTrue(by["package-lock.json"]["generated"])
        self.assertEqual(applied["lines_changed"], 5)  # 2 + 1 removed + 2, the lockfile excepted
        self.assertEqual(applied["generators"], [{"generator_id": "lock", "ok": True}])
        with open(os.path.join(d, "change.patch")) as fh:
            self.assertIn("+b = 3", fh.read())

    def test_apply_refuses_escapes(self):
        repo = git_repo({"src/a.py": "a\n"})
        os.symlink("/tmp", os.path.join(repo, "src", "link"))
        from work_sandbox import safe_target
        with self.assertRaises(HarnessError):
            safe_target(repo, "src/link/x.py")
        with self.assertRaises(HarnessError):
            safe_target(repo, "../x.py")
        os.symlink("../.git", os.path.join(repo, "src", "inner"))  # resolves inside the repo, into .git
        with self.assertRaises(HarnessError):
            safe_target(repo, "src/inner/hooks/pre-commit")

    def run_test(self, base_cases, head_cases, build="true"):
        sandbox = {"setup": ["true"], "build": [build], "unit_test": REPORT, "unit_report": "reports/unit.xml"}
        base = git_repo({"cases.txt": base_cases})
        head = git_repo({"cases.txt": head_cases})
        d = tempfile.mkdtemp()
        i = os.path.join(d, "i.json")
        with open(i, "w") as fh:
            json.dump({"developer": {"code_map_entry": dict(ENTRY, sandbox=sandbox)}}, fh)
        out = os.path.join(d, "sandbox.json")
        res = run_cli("work_sandbox.py", "test", "--input", i, "--base", base, "--head", head, "--out-dir", d, "--out", out)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(out) as fh:
            data = json.load(fh)
        self.assertTrue(check_result(data, sandbox))
        return data

    def test_results(self):
        a, b = '<testcase classname="t.py" name="a"/>', '<testcase classname="t.py" name="b"/>'
        fail_a = '<testcase classname="t.py" name="a"><failure/></testcase>'
        data = self.run_test(a, a + b)
        self.assertEqual((data["status"], data["tests"]["added"], data["tests"]["head_total"]), ("pass", 1, 2))
        data = self.run_test(a, fail_a + b)
        self.assertEqual((data["status"], data["tests"]["regressions"]), ("fail", ["t.py::a"]))
        data = self.run_test(a, a + '<testcase classname="t.py" name="b"><failure message="expected 1 to be 2&#10;more"/></testcase>')
        self.assertEqual((data["status"], data["tests"]["added_failing"]), ("fail", ["t.py::b"]))
        self.assertEqual(data["messages"], {"t.py::b": "expected 1 to be 2"})
        data = self.run_test(fail_a, fail_a)
        self.assertEqual((data["status"], data["tests"]["base_failing"]), ("pass", ["t.py::a"]))
        data = self.run_test(a, a, build="echo 'src/x.ts(5,13): error TS2769' && false")
        self.assertEqual(data["status"], "fail")
        self.assertEqual((data["failure"]["step"], data["failure"]["tail"]), ("build", ["src/x.ts(5,13): error TS2769"]))
        self.assertFalse(check_result(data))  # without the code map, a failure's command is unknown

    def test_result_shape_check(self):
        good = {"version": 1, "status": "pass", "build": {"base": True, "head": True}, "report": {"head": True},
                "tests": {"base_total": 1, "head_total": 2, "added": 1, "regressions": [], "flaky": [],
                          "added_failing": [], "base_failing": []}}
        self.assertTrue(check_result(good))
        for mutate in (lambda d: d.update(status="great"), lambda d: d["tests"].update(added="1"),
                       lambda d: d["tests"].update(regressions=["x\n@giokur"]), lambda d: d["build"].update(head="yes"),
                       lambda d: d["tests"].update(flaky=["t"] * 51)):
            bad = copy.deepcopy(good)
            mutate(bad)
            self.assertFalse(check_result(bad))
        self.assertTrue(check_result({"version": 1, "status": "untested",
                                      "reason": "no sandbox commands in .staff/code.yml"}))

    def test_clean_line(self):
        self.assertEqual(clean_line("\x1b[31m/w/head/src/a.ts\x07 bad\x1b[0m", "/w/head"), "src/a.ts bad")
        self.assertEqual(len(clean_line("x" * 500, "/r")), 200)

    def test_failure_shape(self):
        sandbox = {"setup": ["npm ci"], "build": ["npm run build"], "unit_test": "npm test", "unit_report": "r.xml"}
        base = {"version": 1, "status": "fail", "build": {"base": True, "head": False}, "report": {"head": False},
                "tests": {"base_total": 0, "head_total": 0, "added": 0, "regressions": [], "flaky": [],
                          "added_failing": [], "base_failing": []},
                "failure": {"step": "build", "command": "npm run build", "tail": ["error TS1"]}, "messages": {}}
        self.assertTrue(check_result(base, sandbox))
        for mutate in (lambda d: d["failure"].update(command="curl evil"), lambda d: d["failure"].update(tail=["a\nb"]),
                       lambda d: d["failure"].update(tail=["x"] * 41), lambda d: d["failure"].update(step="deploy"),
                       lambda d: d.update(messages={"t::not-failing": "m"})):
            bad = copy.deepcopy(base)
            mutate(bad)
            self.assertFalse(check_result(bad, sandbox))

    def test_junit_unreadable(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "r.xml")
        self.assertIsNone(junit_results(path))
        with open(path, "w") as fh:
            fh.write("<testsuites><testcase name='a'>")
        self.assertIsNone(junit_results(path))


class Args:
    run_id, run_url, stage = "123-1", "https://github.com/o/r/actions/runs/123/attempts/1", 1
    model, staff_sha, patch_artifact = "claude-sonnet-5-5", "c" * 40, "developer-patch-123-1"


META = {"area": "system", "ticket_kind": "implement", "work": "feature",
        "readiness": {"status": "ready", "acs": ["REQ-012/AC-001"], "reqs": ["REQ-012"], "interfaces": [], "blockers": []}}
APPLIED = {"version": 1, "files": [{"path": "src/orders/cancel.py", "added": 7, "removed": 0, "generated": False}],
           "lines_changed": 7, "max_lines": 500, "over_cap": False, "generators": []}


class RenderTest(unittest.TestCase):
    def test_main_comment(self):
        out = load("developer-feature.json")
        out["decision_summary"] = "@giokur see [x](http://e) <img src=x>"
        out["private_reports_withheld"] = [{"id": "SR-001", "kind": "vulnerability"}]
        out["defect_items"] = [{"target": "REQ-012/AC-002", "kind": "ambiguous", "evidence_refs": ["REQ-012"], "text": "t"}]
        sandbox = {"version": 1, "status": "fail", "build": {"base": True, "head": True}, "report": {"head": True},
                   "tests": {"base_total": 3, "head_total": 4, "added": 1, "regressions": ["t.py::a"], "flaky": [],
                             "added_failing": [], "base_failing": []}}
        files, routing = render(out, META, APPLIED, sandbox, Args, {"REQ-012": 16})
        main = dict(files)["00-main.md"]
        self.assertLess(main.index("Decide first"), main.index("Proposed change"))
        for needle in ("**fail**", "`t.py::a`", "developer-patch-123-1", "SR-001 (vulnerability)", "Design requests"):
            self.assertIn(needle, main)
        self.assertNotIn("@giokur", main)
        self.assertNotIn("[x](", main)
        self.assertEqual(routing[files[-1][0]], 16)
        self.assertEqual(files, render(copy.deepcopy(out), META, APPLIED, sandbox, Args, {"REQ-012": 16})[0])
        tampered = copy.deepcopy(sandbox)
        tampered["tests"]["regressions"] = ["ok\n### Approved"]
        main = dict(render(out, META, APPLIED, tampered, Args, {})[0])["00-main.md"]
        self.assertIn("failed the harness's shape check", main)
        self.assertNotIn("### Approved", main)

    def test_turn_limit_warning(self):
        class Stage2(Args):
            stage, issue = 2, 41
        out = load("developer-feature.json")
        self.assertNotIn("Turn limit reached", render_pr_body(out, META, APPLIED, None, Stage2))
        out["turn_limit_reached"] = {"num_turns": 40, "max_turns": 40}
        body = render_pr_body(out, META, APPLIED, None, Stage2)
        self.assertIn("used 40 of 40 turns", body)
        self.assertLess(body.index("Decide first"), body.index("Turn limit reached"))
        self.assertLess(body.index("Turn limit reached"), body.index("Proposed change"))
        self.assertIn("used 40 of 40 turns", dict(render(out, META, APPLIED, None, Args, {})[0])["00-main.md"])
        out["turn_limit_reached"] = {"num_turns": "40\n### Approved", "max_turns": 40}
        self.assertNotIn("Turn limit reached", render_pr_body(out, META, APPLIED, None, Stage2))

    def test_failure_tail_is_fenced(self):
        sandbox = {"setup": ["npm ci"], "build": ["npm run typecheck"], "unit_test": "npm test", "unit_report": "r.xml"}
        result = {"version": 1, "status": "fail", "build": {"base": False, "head": False}, "report": {"head": False},
                  "tests": {"base_total": 0, "head_total": 0, "added": 0, "regressions": [], "flaky": [],
                            "added_failing": [], "base_failing": []},
                  "failure": {"step": "build", "command": "npm run typecheck",
                              "tail": ["vite.config.ts(5,13): error TS2769", "```", "@giokur [x](http://e)"]}, "messages": {}}
        meta = dict(META, code_map_entry=dict(ENTRY, sandbox=sandbox))
        main = dict(render(load("developer-feature.json"), meta, APPLIED, result, Args, {})[0])["00-main.md"]
        self.assertIn("The build failed on the change: `npm run typecheck`", main)
        self.assertIn("````\nvite.config.ts(5,13): error TS2769", main)  # a longer fence than the tail's ```
        self.assertNotIn("\n@giokur", main.split("````")[0])

    def test_bootstrap_and_waiting(self):
        boot = load("developer-bootstrap.json")
        meta = dict(META, ticket_kind="bootstrap", work="bootstrap")
        main = dict(render(boot, meta, None, None, Args, {})[0])["00-main.md"]
        self.assertIn("Draft `.staff/code.yml` entry for `orders`", main)
        waiting = dict(META, readiness=dict(META["readiness"], status="waiting", blockers=["REQ-013 is draft"]))
        rd = load("developer-requirement-defect.json")
        main = dict(render(rd, dict(waiting, ticket_kind="fix", work="fix"), None, None, Args, {})[0])["00-main.md"]
        self.assertIn("REQ-013 is draft", main)
        self.assertIn("Classification", main)

    def test_stage_2_comment_links_the_pr(self):
        out = load("developer-feature.json")
        passing = {"version": 1, "status": "pass", "build": {"base": True, "head": True}, "report": {"head": True},
                   "tests": {"base_total": 3, "head_total": 4, "added": 1, "regressions": [], "flaky": [],
                             "added_failing": [], "base_failing": []}}

        class Stage2(Args):
            stage, pr_number = 2, 57
        main = dict(render(out, META, APPLIED, passing, Stage2, {})[0])["00-main.md"]
        self.assertIn("### Developer (stage 2)", main)
        self.assertIn("the change is in #57", main)
        self.assertIn("Stage: 2 (proposing", main)
        self.assertNotIn("Stage-1 draft", main)
        Stage2.pr_number = None
        main = dict(render(out, META, APPLIED, passing, Stage2, {})[0])["00-main.md"]
        self.assertIn("publishing the PR failed", main)
        failing = dict(passing, status="fail")
        main = dict(render(out, META, APPLIED, failing, Stage2, {})[0])["00-main.md"]
        self.assertIn("no PR, because the change didn't pass", main)

    def test_pr_title_and_body(self):
        out = load("developer-feature.json")
        out["decision_summary"] = "@giokur see [x](http://e)"

        class Stage2(Args):
            stage, issue = 2, 41
        title = pr_title(out["pr"], 41)
        self.assertTrue(title.startswith("Developer #41: feature "), title)
        self.assertNotIn("\n", title)
        body = render_pr_body(out, META, APPLIED, None, Stage2)
        self.assertLess(body.index("Decide first"), body.index("Proposed change"))
        self.assertIn("Developer change for #41", body)
        self.assertNotIn("@giokur", body)
        long = copy.deepcopy(out["pr"])
        long["implements_acs"] = [{"ac": f"REQ-012/AC-{i:03d}", "part": "full"} for i in range(1, 20)]
        self.assertLessEqual(len(pr_title(long, 41)), 120)
        bare = dict(out["pr"], kind="refactor", implements_acs=[], fixes=None)
        self.assertEqual(pr_title(bare, 98), "Developer #98: refactor")
        marker = re.search(r"<!-- staff-pr-block:v1 ([A-Za-z0-9+/=]+) -->\n\Z", body)
        self.assertIsNotNone(marker)
        self.assertEqual(json.loads(base64.b64decode(marker.group(1))), out["pr"])

    def test_cli(self):
        d = tempfile.mkdtemp()
        paths = {}
        for name, data in (("v", load("developer-feature.json")), ("m", META), ("a", APPLIED)):
            paths[name] = os.path.join(d, name + ".json")
            with open(paths[name], "w") as fh:
                json.dump(data, fh)
        footer = ["--run-id", "123-1", "--model", "claude-sonnet-5-5", "--staff-sha", "c" * 40]
        res = run_cli("render_developer.py", "render", "--in", paths["v"], "--meta", paths["m"], "--applied", paths["a"],
                      "--out-dir", os.path.join(d, "out"), *footer)
        self.assertEqual(res.returncode, 0, res.stderr)
        res = run_cli("render_developer.py", "failure", "--reason", "path_out_of_scope", "--out-dir",
                      os.path.join(d, "out"), *footer)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(os.path.join(d, "out", "00-failure.md")) as fh:
            self.assertTrue(re.match(r"Developer run 123-1 failed: `path_out_of_scope`", fh.read()))
        res = run_cli("render_developer.py", "pr", "--in", paths["v"], "--meta", paths["m"], "--issue", "41",
                      "--stage", "2", "--out-dir", os.path.join(d, "pr"), *footer)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(os.path.join(d, "pr", "pr-title.txt")) as fh:
            self.assertTrue(fh.read().startswith("Developer #41: "))
        res = run_cli("render_developer.py", "pr", "--in", paths["v"], "--meta", paths["m"], "--out-dir", d, *footer)
        self.assertEqual(res.returncode, 2)  # --issue is required for a PR


class RunRecordTest(unittest.TestCase):
    def test_developer_role_fields(self):
        fields = role_fields(load("developer-feature.json"))
        self.assertEqual((fields["kind"], fields["ac_ids"], fields["files"]),
                         ("feature", ["REQ-012/AC-001", "REQ-012/AC-002"], 2))


if __name__ == "__main__":
    unittest.main()


class CaseClashTest(unittest.TestCase):
    def test_names_differing_only_in_case_are_refused(self):
        from validate_output import check_case_clash
        ok = [{"path": "client/src/dishFormLogic.ts", "op": "add"}, {"path": "client/src/DishFormView.tsx", "op": "add"},
              {"path": "client/src/dishForm.test.ts", "op": "add"}]
        check_case_clash(ok)
        clash = [{"path": "client/src/dishForm.ts", "op": "add"}, {"path": "client/src/DishForm.tsx", "op": "add"}]
        with self.assertRaises(HarnessError) as ctx:
            check_case_clash(clash)
        self.assertEqual(ctx.exception.reason, "case_clash")
        self.assertIn("client/src/DishForm.tsx differs from client/src/dishForm.ts", str(ctx.exception))
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "client", "src"))
        open(os.path.join(d, "client", "src", "flow.ts"), "w").close()
        check_case_clash([{"path": "client/src/flow.ts", "op": "modify"}], d)  # the same file is no clash
        with self.assertRaises(HarnessError) as ctx:
            check_case_clash([{"path": "client/src/Flow.tsx", "op": "add"}], d)  # clashes with flow.ts on main
        self.assertIn("differs from client/src/flow.ts", str(ctx.exception))

