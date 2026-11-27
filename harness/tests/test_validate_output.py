import copy
import json
import os
import tempfile
import unittest

from helpers import SCHEMA, fixture, load, run_cli

from common import HarnessError
from validate_output import check_harness, check_run, check_schema, extract, turn_limit

AREAS = ["orders", "billing"]


def envelope(output=None, **over):
    env = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 6,
           "duration_ms": 42000, "total_cost_usd": 0.42, "result": ""}
    if output is not None:
        env["structured_output"] = output
    env.update(over)
    return env


class ValidateTest(unittest.TestCase):
    with open(SCHEMA, encoding="utf-8") as fh:
        schema = json.load(fh)

    def assertReason(self, reason, fn, *args):
        with self.assertRaises(HarnessError) as ctx:
            fn(*args)
        self.assertEqual(ctx.exception.reason, reason)
        return ctx.exception

    def full_check(self, out):
        check_schema(out, self.schema)
        check_harness(out, AREAS, 1)

    # --- valid cases ---------------------------------------------------------
    def test_valid_fixtures_pass(self):
        for name in ("output-questions.json", "output-drafts.json", "output-guide.json"):
            with self.subTest(name):
                self.full_check(load(name))

    def test_result_text_fallback(self):
        out = load("output-questions.json")
        self.assertEqual(extract(envelope(result=json.dumps(out))), out)

    # --- envelope and cost ---------------------------------------------------
    def test_turn_limit(self):
        env = envelope(num_turns=40)
        old = os.environ.get("MAX_TURNS")
        try:
            os.environ["MAX_TURNS"] = "40"
            self.assertEqual(turn_limit(env), {"num_turns": 40, "max_turns": 40})
            self.assertIsNone(turn_limit(envelope(num_turns=39)))
            self.assertIsNone(turn_limit(envelope(num_turns=True)))
            os.environ["MAX_TURNS"] = "forty"
            self.assertIsNone(turn_limit(env))
            del os.environ["MAX_TURNS"]
            self.assertIsNone(turn_limit(env))
        finally:
            if old is not None:
                os.environ["MAX_TURNS"] = old

    def test_cost_cap(self):
        self.assertReason("cost_cap", check_run, envelope(total_cost_usd=3.01), 3.0)
        check_run(envelope(total_cost_usd=3.0), 3.0)

    def test_cost_unknown_fails_closed(self):
        env = envelope()
        del env["total_cost_usd"]
        self.assertReason("cost_unknown", check_run, env, 3.0)

    def test_run_errors(self):
        self.assertReason("max_turns", check_run, envelope(subtype="error_max_turns", is_error=True), 3.0)
        self.assertReason("budget_exceeded", check_run, envelope(subtype="error_max_budget_usd", is_error=True), 3.0)
        self.assertReason("model_error", check_run, envelope(is_error=True), 3.0)
        self.assertReason("envelope_invalid", check_run, {"type": "assistant"}, 3.0)

    def test_prose_or_missing_output(self):
        self.assertReason("output_not_json", extract, envelope(result="I will post the questions now."))
        self.assertReason("output_not_json", extract, envelope(result="[1, 2]"))
        self.assertReason("no_output", extract, envelope(result=""))

    # --- schema --------------------------------------------------------------
    def schema_case(self, mutate, base="output-questions.json"):
        out = copy.deepcopy(load(base))
        mutate(out)
        return self.assertReason("schema_invalid", check_schema, out, self.schema)

    def test_schema_rejects(self):
        cases = {
            "missing decision_summary": lambda o: o.pop("decision_summary"),
            "free text over 2,000 chars": lambda o: o.update(decision_summary="x" * 2001),
            "more than 7 questions": lambda o: o.update(questions=[o["questions"][0]] * 8),
            "option e": lambda o: o["questions"][0]["options"].append({"id": "e", "text": "five"}),
            "one option": lambda o: o["questions"][0].update(options=[{"id": "a", "text": "only"}]),
            "unknown field (write action)": lambda o: o.update(post_comment="hello"),
            "questions outcome without questions": lambda o: o.update(questions=[]),
            "escalation with questions": lambda o: o.update(outcome="escalation", escalation={
                "reason": "r", "open_blocking_questions": ["Q-001"]}),
            "bad area key": lambda o: o["intake"].update(area="Orders!"),
        }
        for name, mutate in cases.items():
            with self.subTest(name):
                self.schema_case(mutate)

    def test_schema_rejects_drafts(self):
        cases = {
            "story without parent": lambda o: o["requirements"][1].pop("parent"),
            "more than 5 requirements": lambda o: o.update(requirements=o["requirements"] * 2),
            "bad date": lambda o: o["requirements"][0]["revision"][0].update(date="21/11/2026"),
            "AC with no cites": lambda o: o["requirements"][1]["acceptance_criteria"][0].update(cites=[]),
        }
        for name, mutate in cases.items():
            with self.subTest(name):
                self.schema_case(mutate, "output-drafts.json")

    # --- harness checks ------------------------------------------------------
    def harness_case(self, reason, mutate, base="output-drafts.json"):
        out = copy.deepcopy(load(base))
        mutate(out)
        check_schema(out, self.schema)  # each case is schema-valid on purpose
        return self.assertReason(reason, check_harness, out, AREAS, 1)

    def test_requirement_revision_history_is_append_only(self):
        out = copy.deepcopy(load("output-drafts.json"))
        req = out["requirements"][0]
        on_main = [{"date": "2026-11-22", "change": "A-002 confirmed", "reason": "Operator answer",
                    "source_ref": "Diet-Companion/diet-companion#6 comment 1"}]
        truth = {req["id"]: {"id": req["id"], "revision": on_main}}
        req["revision"] = copy.deepcopy(on_main) + list(req.get("revision") or [])
        check_schema(out, self.schema)
        check_harness(out, AREAS, 1, truth)
        req["revision"][0]["change"] = "A-002 assumed"
        self.assertReason("revision_rewritten", check_harness, out, AREAS, 1, truth)
        req["revision"] = list(req["revision"][1:])
        self.assertReason("revision_rewritten", check_harness, out, AREAS, 1, truth)
        check_harness(out, AREAS, 1)  # a requirement that isn't on main has no history to keep

    def test_story_parent_must_be_the_runs_epic(self):
        self.harness_case("parent_mismatch", lambda o: o["requirements"][2].update(parent="REQ-099"))

    def test_one_epic_per_run(self):
        def two_epics(o):
            o["requirements"][2].update(type="epic", parent=None)
        self.harness_case("multiple_epics", two_epics)

    def test_stories_without_epic_share_a_parent(self):
        def no_epic(o):
            o["requirements"].pop(0)
            o["requirements"][1]["parent"] = "REQ-050"
        self.harness_case("parent_mismatch", no_epic)

    def test_blocking_questions_first(self):
        def order(o):
            o["questions"][0]["blocking"] = False
            o["questions"][1]["blocking"] = True
        self.harness_case("blocking_order", order, "output-questions.json")

    def test_priority_follows_batch_order(self):
        self.harness_case("blocking_order", lambda o: o["questions"][1].update(priority=3), "output-questions.json")

    def test_unique_ids(self):
        self.harness_case("duplicate_id", lambda o: o["requirements"][2].update(id="REQ-002"))
        self.harness_case("duplicate_id", lambda o: o["questions"].append(dict(o["questions"][0], priority=2)))
        self.harness_case("duplicate_id", lambda o: o["questions"][0]["options"].append({"id": "a", "text": "again"}))

    def test_ac_belongs_to_its_requirement(self):
        self.harness_case("ac_id_mismatch",
                          lambda o: o["requirements"][2]["acceptance_criteria"][0].update(id="REQ-002/AC-009"))

    def test_area_in_areas_yml(self):
        self.harness_case("unknown_area", lambda o: o["intake"].update(area="shipping"))
        self.harness_case("unknown_area", lambda o: o["requirements"][1].update(area="shipping"))

    def test_recommended_is_an_option(self):
        self.harness_case("recommended_not_option", lambda o: o["questions"][0].update(recommended="d"))

    def test_stage_one_drafts_only(self):
        self.harness_case("stage_violation", lambda o: o["requirements"][1].update(status="ready"))
        self.harness_case("stage_violation", lambda o: o.update(ready_gate=True, requirements=o["requirements"][:3]))

    # --- CLI -----------------------------------------------------------------
    def run_validate(self, env):
        d = tempfile.mkdtemp()
        paths = {k: os.path.join(d, f"{k}.json") for k in ("envelope", "out", "result")}
        with open(paths["envelope"], "w") as fh:
            json.dump(env, fh)
        proc = run_cli("validate_output.py", "--envelope", paths["envelope"], "--schema", SCHEMA,
                       "--areas", fixture("areas.yml"), "--max-run-usd", "3", "--out", paths["out"],
                       "--result", paths["result"])
        with open(paths["result"]) as fh:
            return proc, json.load(fh), os.path.exists(paths["out"])

    def test_cli_pass(self):
        proc, result, wrote = self.run_validate(envelope(load("output-drafts.json")))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(wrote)
        self.assertEqual((result["ok"], result["outcome"], result["cost_usd"], result["num_turns"]),
                         (True, "drafts_and_questions", 0.42, 6))

    def test_cli_failure_names_paths_not_model_text(self):
        out = load("output-questions.json")
        out["decision_summary"] = "SECRET-LOOKING MODEL TEXT " * 100
        proc, result, wrote = self.run_validate(envelope(out))
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(wrote)
        self.assertEqual(result["reason"], "schema_invalid")
        self.assertIn("/decision_summary (maxLength)", proc.stderr)
        self.assertNotIn("SECRET-LOOKING", proc.stderr + proc.stdout + json.dumps(result))

    def test_cli_cost_cap_still_records_metrics(self):
        proc, result, wrote = self.run_validate(envelope(load("output-questions.json"), total_cost_usd=7.5))
        self.assertEqual((proc.returncode, result["reason"], result["cost_usd"], wrote), (2, "cost_cap", 7.5, False))


if __name__ == "__main__":
    unittest.main()
