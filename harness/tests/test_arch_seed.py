"""Seeding Architect design bundles (S-GEN-067, S-ARCH-049): the request, assembly and the validity check."""
import copy
import json
import os
import tempfile
import unittest

import yaml

from helpers import STAFF, run_cli
from arch_eval import check_bundle
from prepare_agent import CONTRACTS
from seed_task import ARCH_SLOT_PLAN
from test_eval import product_repo, write
from test_ready_gate import RULE, requirement

TASK_SCHEMA = os.path.join(STAFF, "evals", "schemas", "architect-task.schema.json")
SEEDER_SCHEMA = os.path.join(STAFF, "plugins", "staff-meta", "schemas", "seeder-architect-output.schema.json")
FIXED = "The label photo is at most 5 MB."
PLANT = {"location": "requirements/catalog/REQ-002.md", "violates": "ADR-001/C-001", "corrected_text": FIXED}
SLOT_1 = ARCH_SLOT_PLAN["seeded"][0]


def md(front, body=""):
    return "---\n" + yaml.safe_dump(front, sort_keys=False, allow_unicode=True) + "---\n" + body


def story(**over):
    r = requirement(id="REQ-002", status="ready")
    r["acceptance_criteria"] = [dict(a, id=a["id"].replace("REQ-003", "REQ-002")) for a in r["acceptance_criteria"]]
    r["acceptance_criteria"][0]["key"]["target_id"] = "getLabel"
    r.update(over)
    return r


def quality(**over):
    r = requirement(id="REQ-003", type="quality", status="ready", title="Label reads are fast", rules=[])
    r["scope"]["in"][0]["text"] = "A label read answers within 300 ms at p95."
    r["acceptance_criteria"] = [dict(r["acceptance_criteria"][0], id="REQ-003/AC-001")]
    r.update(over)
    return r


def epic():
    e = requirement(id="REQ-001", type="epic", title="Catalog", acceptance_criteria=[], rules=[])
    e.pop("parent")
    return e


ADR = {"id": "ADR-001", "status": "accepted", "decision": {"outcome": "accepted", "chosen": "a", "decided_by": "o/r#1 comment 1"},
       "options": [{"key": "a", "constraints": [{"id": "ADR-001/C-001"}]}, {"key": "b", "constraints": [{"id": "ADR-001/C-002"}]}],
       "assumptions": [{"id": "A-001", "key": {"entity": "product", "target_id": None, "attribute": "shop count"},
                        "text": "No source states it.", "status": "open", "blocking": False}]}
IFACE = {"id": "IF-001", "versions": [{"version": "1.0.0", "status": "approved",
                                       "spec": "architecture/catalog/interfaces/IF-001/1.0.0.yaml"}]}
BASE = {
    ".staff/areas.yml": "areas:\n  catalog:\n    paths: [requirements/catalog/**]\n",
    "requirements/catalog/REQ-001.md": md(epic()),
    "requirements/catalog/sources/INT-001.md": "---\nid: INT-001\n---\n\n### T1 [interviewer]\n\nQ\n\n### T2 [human]\n\nA\n",
    "knowledge/rules/catalog/R-002.md": md(RULE),
    "architecture/catalog/adr/ADR-001.md": md(ADR),
    "architecture/catalog/interfaces/IF-001.md": md(IFACE),
    "architecture/catalog/interfaces/IF-001/1.0.0.yaml": "openapi: 3.1.0\npaths:\n  /things:\n    get: {operationId: listThings}\n",
}
PRODUCT = None


def product():
    global PRODUCT
    if PRODUCT is None:
        PRODUCT = product_repo(BASE)
    return PRODUCT


def overlay(reqs=None):
    return [{"path": f"requirements/catalog/{r['id']}.md", "content": md(r, "\n# body\n")}
            for r in (reqs if reqs is not None else [story(), quality()])]


def spec(kind="seeded"):
    s = {"clean": kind == "clean",
         "quality_drivers": [{"req": "REQ-003", "attribute": "latency", "target": {"value": 300, "unit": "ms", "direction": "max"}}],
         "conflicts": [], "defects": [], "unknown_figures": [],
         "interface_needs": [{"ac": "REQ-002/AC-001", "target_id": "getLabel", "if_id": "IF-001", "element": "operation",
                              "expected_class": "compatible"}]}
    if kind == "seeded":
        s.update(conflicts=[dict(PLANT, constraint_id="ADR-001/C-001", also_defect_targets=["REQ-002/AC-002"])],
                 defects=[dict(PLANT, target="REQ-002/AC-001", kinds=["untestable"])],
                 unknown_figures=[dict(PLANT, entity="label", attribute="photo size", terms=["photo size"], units=["MB"],
                                       needed_by="REQ-002")])
    return s


def bundle(kind="seeded", **over):
    t = {"version": 1, "id": "f6e5d4c3b2a1", "agent": "architect", "set": "promotion", "kind": kind,
         "base_sha": product()[1], "ticket": {"label": "arch:design", "title": "Design label reads",
                                              "body": "Area: `catalog`\n\nREQ-002 and REQ-003."},
         "overlay": overlay(), "comments": [], "spec": spec(kind)}
    t.update(over)
    return t


class CheckTest(unittest.TestCase):
    def codes(self, t, plan=SLOT_1):
        _, failures = check_bundle(copy.deepcopy(t), product()[0], tempfile.mkdtemp(), plan)
        return [f["code"] for f in failures]

    def test_valid_bundles(self):
        t, failures = check_bundle(bundle(), product()[0], tempfile.mkdtemp(), SLOT_1)
        self.assertEqual(failures, [])
        self.assertEqual(t["spec_counts"], {"quality_drivers": 1, "conflicts": 1, "defects": 1, "interface_needs": 1,
                                            "unknown_figures": 1})
        self.assertEqual(self.codes(bundle("clean"), ARCH_SLOT_PLAN["clean"][1] | {"interface_needs": 1}), [])

    def test_requirements(self):
        draft = self.codes(bundle(overlay=overlay([story(status="draft"), quality()])))
        self.assertEqual(draft[:2], ["req_not_ready", "ticket_req_not_ready"])         # and what sits on it
        no_negative = story()
        no_negative["acceptance_criteria"] = no_negative["acceptance_criteria"][:1]      # R-002's condition uncovered
        self.assertIn("req_gate_failed", self.codes(bundle(overlay=overlay([no_negative, quality()]))))
        answered = story(questions=[{"id": "Q-001", "key": {"entity": "label", "target_id": None, "attribute": "size"},
                                     "text": "Max size?", "status": "answered", "blocking": True,
                                     "answer_ref": "o/r#1 comment 5"}])
        self.assertIn("req_gate_failed", self.codes(bundle(overlay=overlay([answered, quality()]))))   # no gh here
        changed = overlay([story(), quality(), dict(epic(), title="Changed")])
        self.assertIn("req_changed", self.codes(bundle(overlay=changed)))
        t = bundle()
        t["ticket"]["body"] = "Area: `catalog`\n\nREQ-001 and REQ-002/AC-009."
        self.assertEqual(self.codes(t), ["ticket_req_not_ready"] * 2)

    def test_drivers(self):
        t = bundle()
        t["spec"]["quality_drivers"][0]["req"] = "REQ-002"                            # not a quality REQ
        self.assertIn("driver_not_pending", self.codes(t))
        qas = {"path": "architecture/catalog/quality/QAS-001.md",
               "content": md({"id": "QAS-001", "req": "REQ-003", "status": "accepted"})}
        self.assertEqual(self.codes(bundle(overlay=overlay() + [qas])), ["driver_not_pending"])
        t = bundle()
        t["spec"]["quality_drivers"][0]["target"]["value"] = 30                        # "300" is not "30"
        self.assertEqual(self.codes(t), ["driver_target_absent"])

    def test_conflicts_defects_and_needs(self):
        t = bundle()
        t["spec"]["conflicts"][0]["constraint_id"] = "ADR-001/C-002"                   # option b wasn't chosen
        self.assertEqual(self.codes(t), ["conflict_constraint_not_live"])
        t = bundle()
        t["spec"]["defects"][0]["target"] = "REQ-002/AC-009"
        self.assertEqual(self.codes(t), ["defect_target_not_live"])
        t["spec"]["defects"][0]["target"] = "REQ-003/AC-001"                           # a driver
        self.assertEqual(self.codes(t), ["defect_target_not_live"])
        t = bundle()
        t["spec"]["interface_needs"][0]["target_id"] = "getOther"                       # the AC keys getLabel
        self.assertEqual(self.codes(t), ["need_target_mismatch"])
        t["spec"]["interface_needs"][0]["if_id"] = "IF-009"
        self.assertEqual(self.codes(t), ["need_target_mismatch"])
        met = story()
        met["acceptance_criteria"][0]["key"]["target_id"] = "listThings"
        t = bundle(overlay=overlay([met, quality()]))
        t["spec"]["interface_needs"][0]["target_id"] = "listThings"
        self.assertEqual(self.codes(t), ["need_already_met"])

    def test_figures(self):
        t = bundle()
        t["ticket"]["body"] += "\nKeep the photo size under 5 MB."
        self.assertEqual(self.codes(t), ["figure_stated"])
        t = bundle()
        t["ticket"]["body"] += "\nThe photo size matters for REQ-002."                  # an ID is not a figure
        self.assertEqual(self.codes(t), [])
        t = bundle()
        t["spec"]["unknown_figures"][0]["aliases"] = [{"entity": "Product", "attribute": "shop_count"}]
        self.assertEqual(self.codes(t), ["figure_already_assumed"])

    def test_plan_and_plants(self):
        plan = dict(SLOT_1, conflicts=2)
        self.assertEqual(self.codes(bundle(), plan), ["plan_mismatch"])
        clean = bundle("clean")
        clean["spec"]["conflicts"] = spec()["conflicts"]                               # load_task refuses it too
        self.assertIn("clean_has_plants", self.codes(clean, None))

    def test_leaks_and_size(self):
        leaky = quality()
        leaky["scope"]["in"][0]["text"] += " " + FIXED
        self.assertEqual(set(self.codes(bundle(overlay=overlay([story(), leaky])))), {"spec_leak"})
        t = bundle()
        t["ticket"]["body"] += "\nLatency target TBD."
        self.assertEqual(self.codes(t), ["spec_leak"])
        big = {"path": "knowledge/notes.md", "content": "x" * 150_001}
        self.assertEqual(self.codes(bundle(overlay=overlay() + [big])), ["bundle_too_large"])

    def test_assumption_ids(self):
        adr = dict(ADR, id="ADR-002", assumptions=[dict(ADR["assumptions"][0], key={"entity": "x", "target_id": None,
                                                                                    "attribute": "y"})])
        clash = {"path": "architecture/catalog/adr/ADR-002.md", "content": md(adr)}
        self.assertEqual(self.codes(bundle(overlay=overlay() + [clash])), ["assumption_id_clash"])
        same = {"path": "architecture/catalog/adr/ADR-002.md", "content": md(dict(ADR, id="ADR-002"))}
        self.assertEqual(self.codes(bundle(overlay=overlay() + [same])), [])            # same ID, same key

    def test_cli(self):
        d = tempfile.mkdtemp()
        out, out_task = os.path.join(d, "check.json"), os.path.join(d, "task.json")
        args = ["check", "--product", product()[0], "--work", os.path.join(d, "w"), "--out", out, "--out-task", out_task]
        res = run_cli("arch_eval.py", *args, "--task", write(d, "in.json", bundle()),
                      "--request", write(d, "req.json", {"kind": "seeded", "slot": "1", "plan": SLOT_1}))
        self.assertEqual((res.returncode, res.stdout.strip()), (0, "valid"), res.stderr)
        with open(out_task) as fh:
            self.assertIn("spec_counts", json.load(fh))
        os.remove(out_task)
        res = run_cli("arch_eval.py", *args, "--task", write(d, "in.json", bundle()),
                      "--request", write(d, "req.json", {"plan": dict(SLOT_1, defects=0)}))
        self.assertEqual(res.stdout.strip(), "refused: plan_mismatch")
        self.assertIn("input_invalid", res.stderr)
        self.assertFalse(os.path.exists(out_task))
        self.assertNotIn("label", (res.stdout + res.stderr).lower())                    # nothing from the bundle


class SeedTest(unittest.TestCase):
    def output(self, kind="seeded"):
        t = bundle(kind)
        return {"schema_version": 1, "agent": "seeder-architect", "kind": kind, "summary": "s",
                **{k: t[k] for k in ("ticket", "overlay", "spec")}}

    def assemble(self, out, kind="seeded", agent="architect", set_="promotion"):
        d = tempfile.mkdtemp()
        env = {"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 1.0, "num_turns": 9,
               "structured_output": out}
        res = run_cli("seed_task.py", "assemble", "--agent", agent, "--envelope", write(d, "env.json", env),
                      "--max-run-usd", "6", "--kind", kind, "--set", set_, "--base-sha", "a" * 40, "--run-id", "1-1",
                      "--staff-sha", "b" * 40, "--model", "m", "--out", os.path.join(d, "task.json"),
                      "--result", os.path.join(d, "result.json"))
        if not os.path.exists(os.path.join(d, "result.json")):
            return {"reason": "input_invalid" if "input_invalid" in res.stderr else None}, None
        with open(os.path.join(d, "result.json")) as fh:
            result = json.load(fh)
        t = None
        if res.returncode == 0:
            with open(os.path.join(d, "task.json")) as fh:
                t = json.load(fh)
        return result, t

    def test_plan_slots(self):
        seeded, clean = ARCH_SLOT_PLAN["seeded"], ARCH_SLOT_PLAN["clean"]
        self.assertEqual((len(seeded), len(clean)), (8, 2))
        self.assertEqual([p["conflicts"] for p in seeded], [1, 2, 0, 1, 2, 1, 0, 1])
        self.assertEqual([p["defects"] for p in seeded], [1, 0, 1, 1, 0, 1, 1, 0])
        self.assertEqual([p["quality_drivers"] for p in seeded], [1, 2, 1, 3, 2, 1, 2, 1])
        self.assertEqual((sum(p["interface_needs"] > 0 for p in seeded), sum(p["breaking_needs"] for p in seeded)), (5, 1))
        self.assertEqual({p["unknown_figures"] for p in seeded}, {1})
        self.assertEqual([(p["quality_drivers"], p["interface_needs"], p["conflicts"] + p["defects"] + p["unknown_figures"])
                          for p in clean], [(2, 1, 0), (1, 0, 0)])

    def test_assemble(self):
        result, t = self.assemble(self.output())
        self.assertTrue(result["ok"], result)
        self.assertEqual((t["agent"], t["kind"], t["comments"], t["seeding"]["holdout_seed"]), ("architect", "seeded", [], True))
        self.assertNotIn("slot", json.dumps(t))
        _, t = self.assemble(self.output("clean"), kind="clean")
        self.assertFalse(t["seeding"]["holdout_seed"])                                # clean bundles aren't seeds
        _, t = self.assemble(self.output(), set_="visible")
        self.assertFalse(t["seeding"]["holdout_seed"])

    def test_assemble_refusals(self):
        self.assertEqual(self.assemble(self.output(), kind="clean")[0]["reason"], "kind_mismatch")
        self.assertEqual(self.assemble(dict(self.output(), extra=1))[0]["reason"], "schema_invalid")
        outside = dict(self.output(), overlay=[{"path": "backend/a.ts", "content": "x"}])
        self.assertEqual(self.assemble(outside)[0]["reason"], "input_invalid")         # load_task's path rule
        self.assertEqual(self.assemble(self.output(), kind="trap")[0]["reason"], "input_invalid")
        self.assertEqual(self.assemble(self.output(), kind="seeded", agent="developer")[0]["reason"], "input_invalid")

    def test_request(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "set"))
        write(os.path.join(d, "set"), "x.json", dict(bundle("clean"), summary="old"))
        prev = write(d, "prev.json", bundle())
        check = write(d, "check.json", {"ok": False, "failures": [{"code": "figure_stated", "path": "ticket", "line": 3}]})
        out = os.path.join(d, "req.json")
        base = ["seed_task.py", "request", "--set", "promotion", "--set-dir", os.path.join(d, "set"), "--out", out]
        res = run_cli(*base, "--agent", "architect", "--kind", "seeded", "--slot", "4",
                      "--previous-task", prev, "--previous-check", check)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(out) as fh:
            req = json.load(fh)
        self.assertEqual(req["plan"], ARCH_SLOT_PLAN["seeded"][3])
        self.assertEqual(set(req["previous"]["task"]), {"ticket", "overlay", "spec", "summary"})
        self.assertEqual(req["previous"]["failures"][0]["code"], "figure_stated")
        for kind, slot in (("seeded", "9"), ("clean", "3"), ("seeded", "x"), ("feature", "1")):
            res = run_cli(*base, "--agent", "architect", "--kind", kind, "--slot", slot)
            self.assertIn("input_invalid", res.stderr, (kind, slot))
        res = run_cli(*base, "--kind", "trap", "--slot", "1")                          # the Developer: no plan
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(out) as fh:
            self.assertNotIn("plan", json.load(fh))
        self.assertIn("input_invalid", run_cli(*base, "--kind", "seeded", "--slot", "1").stderr)

    def test_schemas_and_contract(self):
        with open(SEEDER_SCHEMA) as fh:
            seeder = json.load(fh)
        with open(TASK_SCHEMA) as fh:
            task = json.load(fh)
        for name, d in seeder["$defs"].items():
            self.assertEqual(d, task["$defs"][name], name)
        for key in ("kind", "ticket"):
            self.assertEqual(seeder["properties"][key], task["properties"][key])
        self.assertIn("`plan`", CONTRACTS["seeder-architect"])
        self.assertNotEqual(CONTRACTS["seeder"], CONTRACTS["seeder-architect"])


if __name__ == "__main__":
    unittest.main()
