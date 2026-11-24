"""The test engineer's harness path (test-gen-api): test map, bundle, input, prompt, output checks, sandbox, comments."""
import copy
import json
import os
import tempfile
import unittest

import yaml
from helpers import FIXTURES, STAFF

from build_input import build
from common import HarnessError
from prepare_agent import build_prompt, cli_schema
from qa_bundle import bundle
from render_qa import render
from run_record import dev_outcome, role_fields
from test_developer_harness import product
from test_map import layer_entry, load_test_map, writable
from validate_output import check_schema, check_test_gen, file_citations
from dev_bundle import load_truth
from work_sandbox import check_result, is_expected, sandbox_of

PLUGINS = os.path.join(STAFF, "plugins")
AGENT = os.path.join(PLUGINS, "staff-qa", "agents", "test-gen-api.md")
SCHEMA = os.path.join(PLUGINS, "staff-qa", "schemas", "test-gen-output.schema.json")
MAP_SCHEMA = os.path.join(PLUGINS, "staff-qa", "schemas", "test-map.schema.json")
FIX = os.path.join(FIXTURES, "qa")
CAP_CHARS = int(15_000 * 3.2)  # S-GEN-009
TEST_DECL = r"\b(it|test)(\.each\([^)]*\))?\(\s*['\"`]"
CODE_ENTRY = {"source": ["src/**"], "unit_tests": ["src/**/*.test.ts"], "protected": ["src/auth/**"],
              "guard_patterns": [{"stack": "typescript", "test_decl": [TEST_DECL], "assertion": [r"\bexpect\("]}]}


def load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


def test_map():
    return load_test_map(os.path.join(FIX, "tests.yml"), MAP_SCHEMA)


def qa_input(body="Area: `system`\nLayer: api\n\nREQ-012/AC-001 and REQ-012/AC-002 against IF-002@1.0.0", operator=True):
    data = {"kind": "test_gen_input", "run": {"run_id": "1-1", "trigger": "label", "intake_ref": "example/shop#30"},
            "untrusted": {"issue": {"author_is_operator": operator, "body": body}, "comments": []}}
    code_map = {"version": 1, "areas": {"system": CODE_ENTRY}}
    return bundle(data, product(), test_map(), code_map, ["system", "orders"])


def with_content(out, text, path="tests/api/orders.api.test.ts"):
    out = copy.deepcopy(out)
    out["proposed_files"] = [{"path": path, "op": "add", "content": [text]}]
    return out


class TestMapTest(unittest.TestCase):
    def test_product_file_validates(self):
        entry = layer_entry(test_map(), "system", "api")
        self.assertEqual(entry["sandbox"]["test"], "npm run test:api")
        self.assertTrue(writable("tests/api/x.api.test.ts", entry))
        self.assertTrue(writable("tests/api/support/api.ts", entry))
        self.assertFalse(writable("backend/src/app.ts", entry))

    def test_invalid_and_missing(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "tests.yml")
        with open(path, "w") as fh:
            yaml.safe_dump({"version": 1, "areas": {"system": {"e2e": {"paths": ["x/**"]}}}}, fh)
        with self.assertRaises(HarnessError) as ctx:
            load_test_map(path, MAP_SCHEMA)
        self.assertEqual(ctx.exception.reason, "test_map_invalid")
        self.assertEqual(load_test_map(os.path.join(d, "none.yml"), MAP_SCHEMA), {"version": 1, "areas": {}})


class BundleTest(unittest.TestCase):
    def test_ready(self):
        qa = qa_input()["qa"]
        self.assertEqual((qa["area"], qa["layer"], qa["readiness"]["status"]), ("system", "api", "ready"))
        self.assertEqual(qa["readiness"]["acs"], ["REQ-012/AC-001", "REQ-012/AC-002"])
        self.assertIn("sandbox", qa["test_map_entry"])

    def test_waiting(self):
        for body, hint in (("Area: `orders`\nREQ-012/AC-001", "no api entry"), ("Area: `system`\nLayer: ui\nREQ-012/AC-001", "ui layer"),
                           ("REQ-012/AC-001", "no valid area"), ("Area: `system`\nREQ-013/AC-001", "not ready")):
            with self.subTest(body):
                r = qa_input(body)["qa"]["readiness"]
                self.assertEqual(r["status"], "waiting")
                self.assertTrue(any(hint in b for b in r["blockers"]), r["blockers"])
        self.assertEqual(qa_input(operator=False)["qa"]["readiness"]["status"], "waiting")


class InputAndPromptTest(unittest.TestCase):
    def test_build_input(self):
        event = {"issue": {"number": 30, "title": "t", "body": "b", "user": {"login": "giokur"}, "labels": []},
                 "repository": {"full_name": "example/shop"}}
        comments = [{"id": 1, "user": {"login": "diet-companion-qa[bot]", "type": "Bot"}, "body": "draft"},
                    {"id": 2, "user": {"login": "giokur", "type": "User"}, "body": "/qa"},
                    {"id": 3, "user": {"login": "giokur", "type": "User"}, "body": "Q-001: a"}]
        data = build(event, comments, {"giokur"}, ["system"], "diet-companion-qa[bot]", "1-1", "k.md", True,
                     agent="test-gen-api")
        self.assertEqual((data["kind"], data["run"]["trigger"]), ("test_gen_input", "label"))
        self.assertEqual([c["author_kind"] for c in data["untrusted"]["comments"]], ["qa_app", "operator"])

    def test_prompt_within_budget(self):
        prompt, tools = build_prompt(AGENT, PLUGINS, contract="test-gen")
        self.assertEqual(tools, ["Glob", "Grep", "Read"])
        self.assertIn("The oracle rule", prompt)
        self.assertIn("Fix-up rounds", prompt)
        self.assertLess(len(prompt), CAP_CHARS)

    def test_cli_schema(self):
        with open(SCHEMA, encoding="utf-8") as fh:
            schema = json.load(fh)
        self.assertNotIn("allOf", cli_schema(schema))


class CheckTestGenTest(unittest.TestCase):
    def setUp(self):
        self.expect = qa_input()
        self.truth = load_truth(product())
        with open(SCHEMA, encoding="utf-8") as fh:
            self.schema = json.load(fh)

    def assert_reason(self, out, reason, expect=None):
        check_schema(out, self.schema)
        with self.assertRaises(HarnessError) as ctx:
            check_test_gen(out, expect or self.expect, self.truth)
        self.assertEqual(ctx.exception.reason, reason)

    def test_fixture_passes(self):
        out = load("output-tests.json")
        check_schema(out, self.schema)
        check_test_gen(out, self.expect, self.truth)

    def test_no_tests_and_not_ready(self):
        out = load("output-tests.json")
        out.update(pr=None, proposed_files=[], suspected_issues=[])
        check_schema(out, self.schema)
        check_test_gen(out, qa_input("Area: `system`\nREQ-013/AC-001"), self.truth)
        self.assert_reason(load("output-tests.json"), "not_ready", qa_input("Area: `system`\nREQ-013/AC-001"))

    def test_path_scope(self):
        base = load("output-tests.json")
        text = "".join(base["proposed_files"][0]["content"])
        for path in ("src/orders.api.test.ts", "tests/unit/orders.test.ts", ".github/workflows/x.yml", "tests/api/x.ts"):
            with self.subTest(path):
                self.assert_reason(with_content(base, text, path), "path_out_of_scope")
        deleted = copy.deepcopy(base)
        deleted["proposed_files"][0].update(op="delete", content=[])
        self.assert_reason(deleted, "path_out_of_scope")
        check_test_gen(with_content(base, "export const x = 1;\n", "tests/api/support/x.ts"), self.expect, self.truth)

    def test_citations(self):
        base = load("output-tests.json")
        uncited = "it(\"no source\", () => {\n  expect(1).toBe(1);\n});\n"
        self.assert_reason(with_content(base, uncited), "citation_missing")
        labelled = "// characterization: pins today's status\nit(\"pins\", () => {\n  expect(1).toBe(1);\n});\n"
        check_test_gen(with_content(base, labelled), self.expect, self.truth)
        for cite in ("REQ-013/AC-001", "REQ-012/AC-003", "R-099", "IF-002@1.1.0#createOrder", "REQ-12/AC-1"):
            with self.subTest(cite):
                text = f"// cites: {cite}\nit(\"x\", () => {{\n  expect(1).toBe(1);\n}});\n"
                self.assert_reason(with_content(base, text), "cite_invalid")

    def test_expected_failures_pair_with_suspected_issues(self):
        out = load("output-tests.json")
        out["suspected_issues"] = []
        self.assert_reason(out, "unknown_reference")

    def test_file_citations(self):
        cited, uncited = file_citations("// cites: R-004, REQ-012/AC-001.\ntest('a', () => {});\n", [TEST_DECL])
        self.assertEqual((cited, uncited), (["R-004", "REQ-012/AC-001"], None))


class SandboxAndRenderTest(unittest.TestCase):
    def test_sandbox_of(self):
        qa = qa_input()["qa"]
        sb, _ = sandbox_of(qa)
        self.assertEqual((sb["test"], sb["report"]), ("npm run test:api", "reports/api.xml"))
        dev = {"code_map_entry": {"sandbox": {"setup": ["s"], "build": ["b"], "unit_test": "t", "unit_report": "r.xml"}}}
        self.assertEqual(sandbox_of(dev)[0], {"setup": ["s"], "build": ["b"], "test": "t", "report": "r.xml"})
        self.assertEqual(sandbox_of({"test_map_entry": {}}), (None, "no sandbox commands in .staff/tests.yml"))

    def test_is_expected(self):
        exp = {"tests/api/o.api.test.ts::orders API > refuses"}
        self.assertTrue(is_expected("tests/api/o.api.test.ts::orders API > refuses", exp))
        self.assertTrue(is_expected("tests/api/o.api.test.ts::suite > orders API > refuses", exp))
        self.assertFalse(is_expected("tests/api/other.api.test.ts::orders API > refuses", exp))

    def result(self):
        return {"version": 1, "status": "pass", "build": {"base": True, "head": True}, "report": {"head": True},
                "failure": None, "messages": {"tests/api/o.api.test.ts::x": "expected 409"},
                "tests": {"base_total": 4, "head_total": 6, "added": 2, "regressions": [], "flaky": [],
                          "added_failing": [], "base_failing": [], "expected_failing": ["tests/api/o.api.test.ts::x"]}}

    def test_check_result_with_expected_failing(self):
        sb, _ = sandbox_of(qa_input()["qa"])
        self.assertTrue(check_result(self.result(), sb))
        bad = self.result()
        bad["tests"]["expected_failing"] = ["bad\nid"]
        self.assertFalse(check_result(bad, sb))

    def test_render(self):
        class Args:
            run_id, run_url, model, staff_sha, stage = "1-1", "https://github.com/x/y/actions/runs/1", "m", "a" * 40, 1
            patch_artifact = "test-gen-patch-1-1"
        out, meta = load("output-tests.json"), qa_input()["qa"]
        files, routing = render(out, meta, None, self.result(), Args, {})
        text = files[0][1]
        self.assertIn("Suspected issues (S-QA-009)", text)
        self.assertIn("SI-001", text)
        self.assertIn("fail as expected", text)
        self.assertEqual(routing, {"00-main.md": None})

    def test_run_record(self):
        out = load("output-tests.json")
        fields = role_fields(out)
        self.assertEqual((fields["layer"], fields["suspected_issues"], fields["expected_failures"]), ("api", 1, 1))
        self.assertEqual(dev_outcome(out), "proposed")


if __name__ == "__main__":
    unittest.main()
