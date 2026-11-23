"""The Architect's harness path: input, prompt, output checks, comments, run record."""
import copy
import json
import os
import re
import tempfile
import unittest

from helpers import FIXTURES, STAFF, run_cli

from build_input import build
from common import HarnessError
from prepare_agent import build_prompt, cli_schema
from render_architect import fenced, render, req_tickets
from run_record import role_fields
from validate_output import check_architect, check_schema

PLUGINS = os.path.join(STAFF, "plugins")
AGENT = os.path.join(PLUGINS, "staff-engineering", "agents", "architect.md")
SCHEMA = os.path.join(PLUGINS, "staff-engineering", "schemas", "architect-output.schema.json")
FIX = os.path.join(FIXTURES, "architect")
CAP_CHARS = int(15_000 * 3.2)  # S-GEN-009
REPO = "Diet-Companion/diet-companion"
BOT = "diet-companion-engineering[bot]"


def load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


def expect_for(doc, comments=None):
    """The input a run of this fixture would have had."""
    ops = comments if comments is not None else [
        {"ref": a["comment_ref"], "author_kind": "operator"} for a in doc["answers_applied"]]
    return {"run": {"trigger": doc["trigger"]["kind"], "intake_ref": doc["trigger"]["ref"]},
            "product": {"areas": ["orders", "billing", "catalog", "system"]},
            "untrusted": {"comments": ops}}


class Args:
    run_id, run_url, stage = "123-1", "", 1
    model, staff_sha = "claude-sonnet-5-5", "c" * 40


class InputTest(unittest.TestCase):
    def event(self, comment=None):
        ev = {"repository": {"full_name": REPO},
              "issue": {"number": 40, "title": "Design: stack", "body": "Initial stack", "user": {"login": "giokur"},
                        "html_url": f"https://github.com/{REPO}/issues/40"}}
        if comment:
            ev["comment"] = comment
        return ev

    def test_architect_trigger_and_comment_kinds(self):
        comments = [
            {"id": 1, "user": {"login": "giokur", "type": "User"}, "body": "Q-001: b"},
            {"id": 2, "user": {"login": "giokur", "type": "User"}, "body": "/architect"},
            {"id": 3, "user": {"login": BOT, "type": "Bot"}, "body": "drafts"},
            {"id": 4, "user": {"login": "diet-companion-analyst[bot]", "type": "Bot"}, "body": "analyst"},
        ]
        data = build(self.event(), comments, {"giokur"}, ["catalog", "system"], BOT, "1-1",
                     "knowledge/product-core.md", True, agent="architect")
        self.assertEqual(data["kind"], "architect_input")
        self.assertEqual(data["run"]["trigger"], "arch_design")
        self.assertEqual([c["author_kind"] for c in data["untrusted"]["comments"]], ["operator", "architect_app"])
        self.assertIn("architect_app", data["comment_kinds"])
        answer = build(self.event({"id": 5}), [], {"giokur"}, ["catalog"], BOT, "1-1",
                       "knowledge/product-core.md", True, agent="architect")
        self.assertEqual(answer["run"]["trigger"], "answer")

    def test_analyst_unchanged(self):
        data = build(self.event(), [], {"giokur"}, ["catalog"], "diet-companion-analyst[bot]", "1-1",
                     "knowledge/product-core.md", True)
        self.assertEqual((data["kind"], data["run"]["trigger"]), ("analyst_input", "label"))
        self.assertEqual(set(data["comment_kinds"]), {"operator", "analyst_app"})


class PromptTest(unittest.TestCase):
    def test_reference_preloaded_within_budget(self):
        prompt, tools = build_prompt(AGENT, PLUGINS, ["staff-engineering:architecture-reference"], contract="architect")
        self.assertEqual(tools, ["Glob", "Grep", "Read"])
        self.assertIn("# Preloaded skill `staff-engineering:architecture-reference`", prompt)
        self.assertIn("on-demand reference is available in this run", prompt)
        self.assertLess(len(prompt), CAP_CHARS)

    def test_cli_schema_has_no_top_level_combinators(self):
        with open(SCHEMA, encoding="utf-8") as fh:
            cli = cli_schema(json.load(fh))
        self.assertFalse({"allOf", "anyOf", "oneOf", "if", "then", "else"} & set(cli))


class CheckArchitectTest(unittest.TestCase):
    def assert_reason(self, doc, reason, expect=None):
        with self.assertRaises(HarnessError) as ctx:
            check_architect(doc, expect or expect_for(doc))
        self.assertEqual(ctx.exception.reason, reason)

    def adr(self, doc):
        return next(a for a in doc["artifacts"] if a["type"] == "adr")

    def test_fixtures_pass(self):
        with open(SCHEMA, encoding="utf-8") as fh:
            schema = json.load(fh)
        for name in ("architect-design.json", "architect-blocked.json", "architect-drift.json"):
            doc = load(name)
            with self.subTest(name):
                check_schema(doc, schema)
                check_architect(doc, expect_for(doc))

    def test_trigger_and_area(self):
        doc = load("architect-design.json")
        exp = expect_for(doc)
        exp["run"]["intake_ref"] = "ticket#99"
        self.assert_reason(doc, "trigger_mismatch", exp)
        doc["artifacts"][0]["area"] = "nowhere"
        self.assert_reason(doc, "unknown_area")

    def test_constraints_options_and_ids(self):
        doc = load("architect-design.json")
        self.adr(doc)["options"][1]["constraints"][0]["id"] = "ADR-009/C-001"
        self.assert_reason(doc, "constraint_id_mismatch")
        doc = load("architect-design.json")
        self.adr(doc)["recommended"]["option"] = "z"
        self.assert_reason(doc, "option_mismatch")
        doc = load("architect-design.json")
        q = next(q for q in doc["questions"] if q.get("adr"))
        q["options"] = list(reversed(q["options"]))
        self.assert_reason(doc, "option_mismatch")
        doc = load("architect-design.json")
        doc["artifacts"].append(copy.deepcopy(doc["artifacts"][0]))
        self.assert_reason(doc, "duplicate_id")

    def test_stage_one_drafts_only(self):
        doc = load("architect-design.json")
        self.adr(doc)["status"] = "accepted"
        self.assert_reason(doc, "stage_violation")
        doc = load("architect-design.json")
        iface = next(a for a in doc["artifacts"] if a["type"] == "interface")
        iface["versions"][0]["status"] = "approved"
        self.assert_reason(doc, "stage_violation")

    def test_owner_fields_need_an_operator_answer(self):
        doc = load("architect-design.json")
        self.adr(doc)["decision"] = {"chosen": "b"}
        self.assert_reason(doc, "owner_field_set")
        doc["answers_applied"] = [{"target": self.adr(doc)["id"], "field": "decision.chosen",
                                   "comment_ref": f"{REPO}#40 comment 7"}]
        self.assert_reason(doc, "owner_field_set", expect_for(doc, comments=[]))  # not this ticket's operator
        check_architect(doc, expect_for(doc))  # now cited

    def test_conflicts_specs_and_question_order(self):
        doc = load("architect-design.json")
        doc["conflicts"][0]["option_key"] = "z"
        self.assert_reason(doc, "unknown_reference")
        doc = load("architect-design.json")
        doc["spec_versions"][0]["document"] = "title: [unclosed"
        self.assert_reason(doc, "spec_invalid")
        doc = load("architect-design.json")
        doc["spec_versions"][0]["document"] = "info: {title: x}"
        self.assert_reason(doc, "spec_invalid")
        doc = load("architect-design.json")
        doc["spec_versions"][0]["version"] = "9.0.0"
        self.assert_reason(doc, "unknown_reference")
        doc = load("architect-design.json")
        doc["questions"][0]["priority"] = 5
        self.assert_reason(doc, "blocking_order")


class RenderTest(unittest.TestCase):
    def test_one_comment_per_draft_and_routing(self):
        doc = load("architect-design.json")
        doc["defect_items"] = [{"target": "REQ-012/AC-001", "kind": "untestable", "text": "No unit.",
                                "evidence_refs": ["REQ-012/AC-001"]}]
        files, routing = render(doc, Args, {"REQ-012": 16})
        names = [n for n, _ in files]
        self.assertEqual(names[0], "00-main.md")
        self.assertEqual(len(names), 2 + len(doc["artifacts"]))
        self.assertEqual(routing[names[-1]], 16)
        self.assertIsNone(routing["00-main.md"])
        self.assertEqual(files, render(copy.deepcopy(doc), Args, {"REQ-012": 16})[0])
        adr = dict(files)[next(n for n in names if "ADR-" in n)]
        self.assertIn("#### Questions", adr)  # the ADR's question shares its comment
        self.assertIn("Proposed file <code>architecture/orders/adr/ADR-004.md</code>", adr)
        main = dict(files)["00-main.md"]
        self.assertLess(main.index("Decide first"), main.index("#### Drafts"))

    def test_fence_cannot_be_closed_by_model_text(self):
        text = "a\n```\n@giokur <img src=x>\n````\nb"
        block = fenced(text)
        fence = block.splitlines()[0]
        self.assertEqual(len(fence), 5)
        self.assertEqual(block.count("\n" + fence), 1)
        doc = load("architect-design.json")
        doc["artifacts"][0]["stimulus"] = "x ``` y"
        doc["decision_summary"] = "@giokur see [x](http://e) <b>"
        main = dict(render(doc, Args, {})[0])["00-main.md"]
        self.assertNotIn("@giokur", main)
        self.assertNotIn("[x](", main)

    def test_req_tickets(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "requirements", "catalog"))
        with open(os.path.join(d, "requirements", "catalog", "REQ-003.md"), "w") as fh:
            fh.write(f"---\nid: REQ-003\ntracker:\n- other/repo#1\n- {REPO}#6\n---\n")
        with open(os.path.join(d, "requirements", "catalog", "REQ-004.md"), "w") as fh:
            fh.write("---\nid: REQ-004\ntracker: []\n---\n")
        self.assertEqual(req_tickets(d, REPO), {"REQ-003": 6})

    def test_cli(self):
        d = tempfile.mkdtemp()
        src = os.path.join(d, "validated.json")
        with open(src, "w") as fh:
            json.dump(load("architect-design.json"), fh)
        footer = ["--run-id", "123-1", "--model", "claude-sonnet-5-5", "--staff-sha", "c" * 40]
        out = os.path.join(d, "out")
        res = run_cli("render_architect.py", "render", "--in", src, "--out-dir", out, *footer)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("routing.json", os.listdir(out))
        res = run_cli("render_architect.py", "failure", "--reason", "cost_cap", "--out-dir", out, *footer)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(os.path.join(out, "00-failure.md")) as fh:
            self.assertTrue(re.match(r"Architect run 123-1 failed: `cost_cap`", fh.read()))


class RunRecordTest(unittest.TestCase):
    def test_architect_role_fields(self):
        fields = role_fields(load("architect-design.json"))
        self.assertEqual(fields["adr_ids"], ["ADR-004"])
        self.assertIn("REQ-012", fields["req_ids"])
        self.assertEqual(fields["recommended_option"], {"ADR-004": "b"})
        self.assertEqual(fields["options_count"], {"ADR-004": 2})
        self.assertIsNone(fields["compat_class"])


if __name__ == "__main__":
    unittest.main()
