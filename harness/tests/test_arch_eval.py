"""Architect eval scoring (S-ARCH-049, S-GEN-041): metrics by key, hard limits, nothing printed."""
import copy
import json
import os
import tempfile
import unittest

from helpers import FIXTURES, run_cli
from arch_eval import METRICS, OUTPUT_REASONS, score, spec_elements, unit_of, version_class
from common import REASONS, HarnessError
from eval_aggregate import AGENT_THRESHOLDS, aggregate_counts, summary_counts
from eval_keys import key_matches, name_matches, norm
from test_eval import product_repo, write

with open(os.path.join(FIXTURES, "architect", "architect-design.json"), encoding="utf-8") as fh:
    DESIGN = json.load(fh)
PLANT = {"location": "requirements/orders/REQ-012.md", "violates": "ADR-001/C-002", "corrected_text": "the clean wording"}
AREAS = ["orders", "system"]
OK = {"status": "completed", "validation": {"ok": True}, "cost_usd": 2.0, "num_turns": 30}
ASYNC = "asyncapi: 3.0.0\ninfo: {title: t, version: 1.0.0}\nchannels:\n  orderStatus:\n    address: order.status\n" \
        "    messages:\n      statusChanged: {name: order.status.changed}\noperations:\n  sendStatus: {action: send}\n"


def bundle(kind="seeded", **spec_over):
    spec = {"clean": kind == "clean",
            "quality_drivers": [{"req": "REQ-012", "attribute": "performance",
                                 "target": {"value": 300, "unit": "ms", "direction": "max"}}],
            "conflicts": [], "defects": [], "interface_needs": [], "unknown_figures": []}
    if kind == "seeded":
        spec.update(conflicts=[dict(PLANT, constraint_id="ADR-001/C-002", also_defect_targets=["REQ-012/AC-002"])],
                    defects=[dict(PLANT, target="REQ-013/AC-001", kinds=["untestable"])],
                    interface_needs=[{"ac": "REQ-012/AC-001", "target_id": "getOrderStatus", "if_id": "IF-003",
                                      "element": "operation", "expected_class": "compatible"}],
                    unknown_figures=[dict(PLANT, entity="order", attribute="peak request rate", terms=["peak"],
                                          units=["per second", "rps"], needed_by="REQ-012")])
    spec.update(spec_over)
    return {"version": 1, "id": "f6e5d4c3b2a1", "agent": "architect", "set": "promotion", "kind": kind,
            "base_sha": "0" * 40, "ticket": {"label": "arch:design", "title": "T", "body": "REQ-012"},
            "overlay": [], "comments": [], "spec": spec,
            "spec_counts": {k: len(spec[k]) for k in ("quality_drivers", "conflicts", "defects", "interface_needs",
                                                       "unknown_figures")}}


def item(target, kind):
    return {"target": target, "kind": kind, "text": "t", "evidence_refs": ["x"]}


def truth(arch=None):
    return {"reqs": {}, "rules": {}, "arch": arch or {}}


def released(*versions, policy=None):
    return {"IF-003": {"id": "IF-003", "compatibility_policy": policy,
                       "versions": [{"version": v, "status": s, "provenance_confirmed_by": None} for v, s in versions]}}


class KeysTest(unittest.TestCase):
    def test_normalising_and_aliases(self):
        self.assertEqual(norm("  Peak_Request-rate "), "peak request rate")
        want = {"entity": "order", "attribute": "peak request rate"}
        self.assertTrue(key_matches("Order", "peak_request  rate", want))
        self.assertTrue(key_matches("orders", "rps", want, [{"entity": "orders", "attribute": "RPS"}]))
        self.assertFalse(key_matches("orders", "peak request rate", want))     # no stemming
        self.assertFalse(key_matches("order", "rps", want, [{"entity": "orders", "attribute": "rps"}]))  # one pair
        self.assertTrue(name_matches("Latency", "performance", ["latency"]))
        self.assertFalse(name_matches("", ""))

    def test_units(self):
        self.assertEqual(unit_of("Seconds"), ("time", 1000))
        self.assertEqual(unit_of("requests per minute"), ("rate", 1 / 60))
        self.assertEqual(unit_of("req/s"), ("rate", 1))
        self.assertEqual(unit_of("%"), ("percent", 1))
        self.assertIsNone(unit_of("furlongs"))


class ScoreTest(unittest.TestCase):
    def score(self, task=None, out=DESIGN, record=OK, validation=None, arch=None):
        return score(task or bundle(), record, out, validation, truth(arch), AREAS)

    def out(self, **over):
        o = copy.deepcopy(DESIGN)
        o.update(over)
        return o

    def test_the_fixture(self):
        r = self.score()
        self.assertEqual(r["counts"], {"quality_driver_coverage": [1, 1], "conflict_recall": [1, 1],
                                       "defect_recall": [0, 1], "defect_precision": [0, 0],
                                       "interface_coverage": [0, 1], "unnecessary_breaking_rate": [0, 1],
                                       "invented_fact_rate": [0, 1]})
        self.assertEqual((r["status"], r["breaches"], r["agent"], r["run"]), ("completed", [], "architect", 1))
        self.assertEqual(r["diagnostics"]["spec_versions_by_class"], {"new": 1, "compatible": 0, "breaking": 0})
        self.assertEqual(r["diagnostics"]["driver_attribute_misses"], 0)

    def test_quality_driver_direction_and_units(self):
        def covered(value, unit, target=None):
            o = copy.deepcopy(DESIGN)
            o["artifacts"][0]["measure"].update(value=value, unit=unit)
            t = bundle(quality_drivers=[dict(bundle()["spec"]["quality_drivers"][0], **({"target": target} if target else {}))])
            return self.score(t, o)["counts"]["quality_driver_coverage"][0]
        self.assertEqual([covered(0.3, "s"), covered(250, "ms"), covered(301, "ms"), covered(300, "%")], [1, 1, 0, 0])
        floor = {"value": 99.9, "unit": "%", "direction": "min"}
        self.assertEqual([covered(99.95, "percent", floor), covered(99.0, "%", floor)], [1, 0])
        rate = {"value": 50, "unit": "per second", "direction": "min"}
        self.assertEqual([covered(3000, "requests per minute", rate), covered(2999, "req/min", rate)], [1, 0])
        o = copy.deepcopy(DESIGN)
        o["artifacts"][0]["req"] = "REQ-099"                              # a QAS for another REQ
        self.assertEqual(self.score(out=o)["counts"]["quality_driver_coverage"], [0, 1])
        t = bundle(quality_drivers=[dict(bundle()["spec"]["quality_drivers"][0], attribute="latency")])
        self.assertEqual(self.score(t)["diagnostics"]["driver_attribute_misses"], 1)   # covered, other attribute name

    def test_conflicts(self):
        self.assertEqual(self.score(out=self.out(conflicts=[]))["counts"]["conflict_recall"], [0, 1])
        t = bundle(conflicts=[dict(PLANT, constraint_id="ADR-001/C-001", also=["ADR-001/C-002"])])
        self.assertEqual(self.score(t)["counts"]["conflict_recall"], [1, 1])

    def test_defects_and_excused_items(self):
        hit, near = item("REQ-013/AC-001", "untestable"), item("REQ-013/AC-002", "untestable")
        r = self.score(out=self.out(defect_items=[hit, near]))
        self.assertEqual((r["counts"]["defect_recall"], r["counts"]["defect_precision"]), ([1, 1], [1, 2]))
        excused = item("REQ-012/AC-002", "contradicts")                    # D3: the conflict's own AC
        not_excused = item("REQ-012/AC-002", "untestable")
        r = self.score(out=self.out(defect_items=[hit, excused, not_excused]))
        self.assertEqual((r["counts"]["defect_precision"], r["diagnostics"]["defect_items_excused"]), ([1, 2], 1))
        r = self.score(bundle("clean"), self.out(defect_items=[hit]))     # clean: every item is false
        self.assertEqual((r["counts"]["defect_recall"], r["counts"]["defect_precision"]), ([0, 0], [0, 1]))

    def test_interface_coverage(self):
        spec = {"if_id": "IF-003", "version": "1.0.0", "format": "openapi",
                "document": "openapi: 3.1.0\ninfo: {title: t, version: 1.0.0}\n"
                            "paths:\n  /orders/{id}/status:\n    get: {operationId: getOrderStatus}\n"}
        self.assertEqual(self.score(out=self.out(spec_versions=[spec]))["counts"]["interface_coverage"], [1, 1])
        other_if = dict(spec, if_id="IF-009")
        self.assertEqual(self.score(out=self.out(spec_versions=[other_if]))["counts"]["interface_coverage"], [0, 1])
        needs = [{"ac": "REQ-012/AC-001", "target_id": "order.status.changed", "if_id": "IF-003", "element": "event",
                  "expected_class": "compatible"},
                 {"ac": "REQ-012/AC-002", "target_id": "sendStatus", "if_id": "IF-003", "element": "operation",
                  "expected_class": "compatible"},
                 {"ac": "REQ-012/AC-003", "target_id": "sendStatus", "if_id": "IF-003", "element": "event",
                  "expected_class": "compatible"}]                          # an operation, not an event
        async_spec = {"if_id": "IF-003", "version": "1.0.0", "format": "asyncapi", "document": ASYNC}
        r = self.score(bundle(interface_needs=needs), self.out(spec_versions=[async_spec]))
        self.assertEqual(r["counts"]["interface_coverage"], [2, 3])
        self.assertEqual(spec_elements("not: [valid"), {"operation": set(), "event": set()})
        self.assertEqual(spec_elements(ASYNC)["event"], {"orderStatus", "order.status", "statusChanged", "order.status.changed"})

    def test_breaking_class(self):
        arch = released(("1.2.0", "approved"), ("2.0.0", "draft"))
        s = {"if_id": "IF-003", "version": "2.0.0"}
        self.assertEqual([version_class(dict(s, version=v), arch) for v in ("2.0.0", "1.3.0", "1.2.0")],
                         ["breaking", "compatible", "compatible"])
        self.assertEqual(version_class(s, {}), "new")
        self.assertEqual(version_class(s, released(("1.0.0", "draft"))), "compatible")   # nothing released
        o = copy.deepcopy(DESIGN)
        o["spec_versions"][0]["version"] = o["artifacts"][3]["versions"][0]["version"] = "2.0.0"
        self.assertEqual(self.score(out=o, arch=arch)["counts"]["unnecessary_breaking_rate"], [1, 1])
        needs = [dict(bundle()["spec"]["interface_needs"][0], expected_class="breaking")]
        self.assertEqual(self.score(bundle(interface_needs=needs), o, arch=arch)["counts"]["unnecessary_breaking_rate"], [0, 1])
        r = self.score(bundle(editable_versions=["IF-003@2.0.0"]), o, arch=arch)
        self.assertEqual((r["counts"]["unnecessary_breaking_rate"], r["diagnostics"]["editable_revised"]), ([0, 0], 1))
        none = self.out(spec_versions=[])
        self.assertEqual(self.score(out=none)["counts"]["unnecessary_breaking_rate"], [0, 0])

    def test_invented_facts(self):
        o = copy.deepcopy(DESIGN)
        o["assumptions"] = []
        self.assertEqual(self.score(out=o)["counts"]["invented_fact_rate"], [0, 1])   # the ADR's own assumption
        o["artifacts"][1]["assumptions"] = []
        r = self.score(out=o)
        self.assertEqual((r["counts"]["invented_fact_rate"], r["diagnostics"]["figures_stated"]), ([1, 1], 0))
        o["decision_summary"] += " The peak is about 40 per second."      # stated with a value: a diagnostic only
        r = self.score(out=o)
        self.assertEqual((r["diagnostics"]["figures_stated"], r["diagnostics"]["figures_stated_no_assumption"]), (1, 1))
        o = copy.deepcopy(DESIGN)
        o["assumptions"][0]["key"].update(entity="Orders", attribute="RPS")
        o["artifacts"][1]["assumptions"] = []
        t = bundle()
        self.assertEqual(self.score(t, o)["counts"]["invented_fact_rate"], [1, 1])
        t["spec"]["unknown_figures"][0]["aliases"] = [{"entity": "orders", "attribute": "rps"}]
        self.assertEqual(self.score(t, o)["counts"]["invented_fact_rate"], [0, 1])

    def test_stopped_runs(self):
        self.assertTrue(OUTPUT_REASONS <= REASONS)
        for reason in sorted(OUTPUT_REASONS):
            r = self.score(record={"status": "crashed", "validation": {"ok": False, "reason": reason}})
            self.assertIn("invalid_output", r["breaches"], reason)
            self.assertEqual(r["counts"]["quality_driver_coverage"], [0, 1])
        r = self.score(record={"status": "crashed", "validation": {"ok": False, "reason": "owner_field_set"}})
        self.assertEqual(r["breaches"], ["invalid_output", "human_owned_field_set"])
        bad = {"status": "crashed", "validation": {"ok": False, "reason": "schema_invalid"}}
        r = self.score(record=bad, validation={"reason": "schema_invalid", "detail": "1 error(s): /artifacts/1/options (minItems)"})
        self.assertEqual(r["breaches"], ["invalid_output", "adr_options_out_of_range"])
        r = self.score(record=bad, validation={"reason": "schema_invalid", "detail": "1 error(s): /artifacts/1/title (maxLength)"})
        self.assertEqual(r["breaches"], ["invalid_output"])
        r = self.score(record={"status": "timeout", "validation": {"ok": False, "reason": "claude_timeout"}})
        self.assertEqual((r["status"], r["reason"], r["breaches"]), ("timeout", "claude_timeout", []))
        self.assertEqual((r["counts"]["invented_fact_rate"], r["counts"]["defect_precision"]), ([1, 1], [0, 0]))
        r = self.score(out=None, record=OK)                                # no validated output: not completed
        self.assertEqual(r["reason"], "read_job_failed")

    def test_owner_fields_and_scope(self):
        def breaches(mutate, arch=None):
            o = copy.deepcopy(DESIGN)
            mutate(o)
            return self.score(out=o, arch=arch)["breaches"]
        decision = {"outcome": "accepted", "chosen": "b", "decided_by": "o/r#1 comment 2"}
        self.assertEqual(breaches(lambda o: o["artifacts"][1].update(decision=decision)), ["human_owned_field_set"])
        self.assertEqual(breaches(lambda o: o["artifacts"][1].update(decision=decision),
                                  arch={"ADR-004": {"id": "ADR-004", "decision": decision}}), [])   # as on the view
        for mutate in (lambda o: o["artifacts"][2].update(provenance_confirmed_by="o/r#1 comment 2"),
                       lambda o: o["artifacts"][3].update(compatibility_policy="public"),
                       lambda o: o["artifacts"][3]["versions"][0].update(external_retired_by="o/r#1 comment 2"),
                       lambda o: o["artifacts"][1]["exceptions"].append(
                           {"constraint": "ADR-004/C-001", "paths": ["src/**"], "reason": "r", "accepted_by": "x", "expires": "2027-01-01"}),
                       lambda o: o["artifacts"][1]["review_dispositions"].append({"finding_id": "f", "disposition": "accepted", "ref": "x"}),
                       lambda o: o["artifacts"][1].update(superseded_reason="wrong"),
                       lambda o: o["artifacts"][2]["testability"][0].update(gap_accepted_by="x"),
                       lambda o: o["answers_applied"].append({"target": "IF-003", "field": "compatibility_policy", "comment_ref": "x"})):
            self.assertEqual(breaches(mutate), ["human_owned_field_set"])
        self.assertEqual(breaches(lambda o: o["artifacts"][1]["review_dispositions"].append(
            {"finding_id": "f", "disposition": "declared", "ref": "x"})), [])
        self.assertEqual(breaches(lambda o: o["artifacts"][0].update(area="billing")), ["write_outside_scope"])
        self.assertEqual(breaches(lambda o: o["artifacts"][3]["versions"][0].update(
            spec="architecture/orders/interfaces/IF-001/1.0.0.yaml")), ["write_outside_scope"])
        self.assertEqual(breaches(lambda o: o["artifacts"][1].update(options=o["artifacts"][1]["options"][:1])),
                         ["adr_options_out_of_range"])

    def test_unchecked_bundle(self):
        t = bundle()
        del t["spec_counts"]
        with self.assertRaises(HarnessError):
            self.score(t)
        t = bundle()
        t["spec_counts"]["defects"] = 0
        with self.assertRaises(HarnessError):
            self.score(t)

    def test_cli_prints_nothing_from_the_output(self):
        product, sha = product_repo({".staff/areas.yml": "areas:\n  orders:\n    paths: [architecture/orders/**]\n",
                                     "architecture/orders/interfaces/IF-003.md": "---\nid: IF-003\nversions:\n"
                                     "- {version: 0.9.0, status: approved}\n---\n"})
        d = tempfile.mkdtemp()
        t = dict(bundle(), base_sha=sha, overlay=[{"path": "requirements/orders/REQ-012.md", "content": "x\n"}])
        o = self.out(decision_summary="MARKER-IN-OUTPUT")
        out = os.path.join(d, "r.json")
        res = run_cli("arch_eval.py", "score", "--task", write(d, "t.json", t), "--product", product,
                      "--run-record", write(d, "rr.json", OK), "--validated", write(d, "v.json", o),
                      "--validation", write(d, "vr.json", {"ok": True}), "--run", "2",
                      "--work", os.path.join(d, "w"), "--out", out)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("MARKER", res.stdout + res.stderr)
        self.assertNotIn("clean wording", res.stdout + res.stderr)
        with open(out) as fh:
            r = json.load(fh)
        self.assertEqual((r["run"], r["breaches"]), (2, []))
        self.assertEqual(r["diagnostics"]["spec_versions_by_class"], {"new": 0, "compatible": 0, "breaking": 1})
        self.assertEqual(r["counts"]["unnecessary_breaking_rate"], [1, 1])  # 1.0.0 over the view's 0.9.0
        self.assertNotIn("MARKER", json.dumps(r))



GOOD = {"quality_driver_coverage": [2, 2], "conflict_recall": [1, 1], "defect_recall": [1, 1],
        "defect_precision": [1, 1], "interface_coverage": [1, 1], "unnecessary_breaking_rate": [0, 1],
        "invented_fact_rate": [0, 1]}


def arch_result(task_id, kind="seeded", run=1, breaches=(), **counts):
    return {"version": 1, "agent": "architect", "task_id": task_id, "run": run, "set": "promotion", "kind": kind,
            "status": "completed", "reason": None, "cost_usd": 1.0, "num_turns": 20,
            "counts": dict(copy.deepcopy(GOOD), **counts), "breaches": list(breaches),
            "diagnostics": {"defect_items_excused": 1, "spec_versions_by_class": {"new": 1, "compatible": 0, "breaking": 0}}}


class AggregateTest(unittest.TestCase):
    def promotion(self, run=1):
        return ([arch_result(f"s{i}", run=run) for i in range(8)]
                + [arch_result(f"c{i}", kind="clean", run=run, conflict_recall=[0, 0], defect_recall=[0, 0],
                               defect_precision=[0, 0], invented_fact_rate=[0, 0]) for i in range(2)])

    def agg(self, results, previous=None, **kw):
        return aggregate_counts(results, kw.get("set_id", "set-1"), "architect", kw.get("sha", "0" * 40), "m",
                                previous, kw.get("rescore_of"))

    def test_thresholds_are_the_scorer_metrics(self):
        self.assertEqual(tuple(AGENT_THRESHOLDS["architect"]), METRICS)

    def test_passing_set(self):
        agg = self.agg(self.promotion())
        self.assertTrue(agg["passed"])
        self.assertEqual((agg["tasks"], agg["runs"], agg["tasks_by_kind"]), (10, 1, {"seeded": 8, "clean": 2}))
        self.assertEqual((agg["counts"]["conflict_recall"], agg["metrics"]["quality_driver_coverage"]), ([8, 8], 1.0))
        self.assertEqual(agg["diagnostics"], {"defect_items_excused": 10,
                                              "spec_versions_by_class": {"new": 10, "compatible": 0, "breaking": 0}})
        self.assertEqual((agg["consecutive"], agg["previous_passed"]), (False, None))
        text = summary_counts(agg)
        self.assertIn("**pass**", text)
        self.assertIn("| conflict recall | 100% | 8/8 |", text)
        for secret in ("task_id", "s0", "c1"):
            self.assertNotIn(secret, json.dumps(agg) + text)

    def test_pooling_and_per_run_range(self):
        rs = self.promotion() + self.promotion(run=2)
        rs[0]["counts"]["defect_recall"] = [0, 1]                       # run 1: 7 of 8; run 2: 8 of 8
        agg = self.agg(rs)
        self.assertEqual((agg["tasks"], agg["runs"], agg["results"]), (10, 2, 20))
        self.assertEqual((agg["counts"]["defect_recall"], agg["metrics"]["defect_recall"]), ([15, 16], 0.9375))
        self.assertEqual(agg["per_run"]["defect_recall"], {"min": 0.875, "max": 1.0})

    def test_failing_sets(self):
        rs = self.promotion()
        for r in rs[:3]:
            r["counts"]["conflict_recall"] = [0, 1]                     # 5 of 8: 62% < 70%
        agg = self.agg(rs)
        self.assertEqual((agg["meets"]["conflict_recall"], agg["passed"]), (False, False))
        rs = self.promotion()
        rs[0]["counts"]["invented_fact_rate"] = [1, 1]                  # 1 of 8: 12% > 5%
        self.assertFalse(self.agg(rs)["meets"]["invented_fact_rate"])
        rs = self.promotion()
        rs[1]["breaches"] = ["human_owned_field_set"]
        rs[2]["breaches"] = ["invalid_output", "adr_options_out_of_range"]
        agg = self.agg(rs)
        self.assertEqual(agg["hard_limit_breaches"], {"human_owned_field_set": 1, "invalid_output": 1,
                                                      "adr_options_out_of_range": 1})
        self.assertFalse(agg["passed"])

    def test_empty_denominators(self):
        rs = [dict(r, counts=dict(r["counts"], conflict_recall=[0, 0], unnecessary_breaking_rate=[0, 0]))
              for r in self.promotion()]
        agg = self.agg(rs)
        self.assertIsNone(agg["metrics"]["conflict_recall"])             # nothing planted: null, and it fails
        self.assertFalse(agg["meets"]["conflict_recall"])
        self.assertEqual((agg["metrics"]["unnecessary_breaking_rate"], agg["meets"]["unnecessary_breaking_rate"]), (0.0, True))

    def test_consecutive_passes(self):
        first = self.agg(self.promotion())
        self.assertTrue(self.agg(self.promotion(), first)["consecutive"])
        self.assertFalse(self.agg(self.promotion(), first, sha="1" * 40)["consecutive"])     # another staff commit
        self.assertFalse(self.agg(self.promotion(), first, set_id="set-2")["consecutive"])
        self.assertFalse(self.agg(self.promotion(), dict(first, passed=False))["consecutive"])
        self.assertFalse(self.agg(self.promotion(), first, rescore_of="123")["consecutive"])
        failing = self.promotion()
        failing[0]["breaches"] = ["write_outside_scope"]
        self.assertFalse(self.agg(failing, first)["consecutive"])
        self.assertIn("consecutive: yes", summary_counts(self.agg(self.promotion(), first)))

    def test_refusals(self):
        with self.assertRaises(HarnessError):
            aggregate_counts(self.promotion(), "s", "reviewer", "0" * 40, "m")
        with self.assertRaises(HarnessError):
            self.agg(self.promotion() + [{"agent": "developer", "kind": "fix"}])

    def test_cli(self):
        d = tempfile.mkdtemp()
        results = os.path.join(d, "results")
        os.makedirs(results)
        for r in self.promotion():
            write(results, f"{r['task_id']}.json", r)
        base = ["eval_aggregate.py", "--results", results, "--set-id", "s", "--agent", "architect", "--staff-sha", "0" * 40,
                "--model", "m", "--expected", "10"]
        first = os.path.join(d, "first.json")
        res = run_cli(*base, "--out", first, "--summary", os.path.join(d, "s.md"))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "eval pass: 10 tasks")
        res = run_cli(*base, "--out", os.path.join(d, "second.json"), "--previous", first)
        self.assertEqual(res.stdout.strip(), "eval pass: 10 tasks, consecutive: yes")
        res = run_cli("eval_aggregate.py", "--results", results, "--set-id", "s", "--staff-sha", "0" * 40, "--model", "m",
                      "--expected", "10", "--out", os.path.join(d, "x.json"), "--previous", first)
        self.assertIn("input_invalid", res.stderr)                      # the Developer path takes no --previous
        with open(os.path.join(d, "s.md")) as fh:
            self.assertIn("Architect eval", fh.read())


if __name__ == "__main__":
    unittest.main()
