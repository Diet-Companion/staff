"""Architect eval bundles (S-ARCH-049): the bundle format, the tree the agent sees, and its ticket."""
import copy
import json
import os
import subprocess
import tempfile
import unittest

from helpers import run_cli
from build_input import build
from common import HarnessError
from eval_task import load_task, synthetic_event
from test_eval import product_repo, task, write

STAFF = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMAS = os.path.join(STAFF, "evals", "schemas")
ARCH_SCHEMA = os.path.join(SCHEMAS, "architect-task.schema.json")
DEV_SCHEMA = os.path.join(SCHEMAS, "developer-task.schema.json")
PLANT = {"location": "requirements/x/REQ-002.md", "violates": "ADR-001/C-001", "corrected_text": "the clean wording"}


def arch_task(kind, sha, **over):
    spec = {"clean": kind == "clean",
            "quality_drivers": [{"req": "REQ-003", "attribute": "latency",
                                 "target": {"value": 300, "unit": "ms", "direction": "max"}}],
            "conflicts": [], "defects": [], "interface_needs": [], "unknown_figures": []}
    if kind == "seeded":
        spec["conflicts"] = [dict(PLANT, constraint_id="ADR-001/C-001", also_defect_targets=["REQ-002/AC-002"])]
        spec["defects"] = [dict(PLANT, target="REQ-002/AC-001", kinds=["untestable"])]
        spec["unknown_figures"] = [dict(PLANT, entity="order", attribute="peak request rate", terms=["peak"],
                                        units=["per second"], needed_by="REQ-003")]
    t = {"version": 1, "id": "f6e5d4c3b2a1", "agent": "architect", "set": "promotion", "kind": kind, "base_sha": sha,
         "ticket": {"label": "arch:design", "title": "Design: order status", "body": "Area: `system`\n\nREQ-002, REQ-003"},
         "overlay": [{"path": "requirements/x/REQ-002.md", "content": "new req\n"}], "comments": [], "spec": spec}
    t.update(over)
    return t


def strip_descriptions(node):
    if isinstance(node, dict):
        return {k: strip_descriptions(v) for k, v in node.items() if k != "description"}
    if isinstance(node, list):
        return [strip_descriptions(v) for v in node]
    return node


class BundleTest(unittest.TestCase):
    def check(self, t, schema=ARCH_SCHEMA):
        return load_task(write(tempfile.mkdtemp(), "task.json", t), schema)

    def test_kinds(self):
        for kind in ("seeded", "clean"):
            self.assertEqual(self.check(arch_task(kind, "0" * 40))["kind"], kind)
        t = arch_task("seeded", "0" * 40)
        t["spec"].update(conflicts=[], defects=[])                     # 0 conflicts, 0 defects, 1 figure
        self.check(t)

    def test_kind_rules(self):
        sha = "0" * 40
        seeded, clean = arch_task("seeded", sha), arch_task("clean", sha)
        bad = []
        for spec in (dict(seeded["spec"], unknown_figures=[]),              # seeded: exactly one figure
                     dict(seeded["spec"], clean=True)):                      # seeded, declared clean
            bad.append(dict(seeded, spec=spec))
        for spec in (dict(clean["spec"], conflicts=seeded["spec"]["conflicts"]),   # a clean bundle has no plants
                     dict(clean["spec"], defects=seeded["spec"]["defects"]),
                     dict(clean["spec"], unknown_figures=seeded["spec"]["unknown_figures"]),
                     dict(clean["spec"], clean=False)):
            bad.append(dict(clean, spec=spec))
        for t in bad:
            with self.assertRaises(HarnessError) as cm:
                self.check(t)
            self.assertIn("does not fit", cm.exception.detail)

    def test_schema_and_path_rules(self):
        sha = "0" * 40
        t = arch_task("seeded", sha)
        many = t["spec"]["quality_drivers"] * 4
        bad = [
            dict(t, ticket=dict(t["ticket"], label="dev:implement")),                       # wrong label
            dict(t, comments=[{"body": "Q-001: b"}]),                                       # no comments in v1
            dict(t, spec=dict(t["spec"], quality_drivers=[])),                              # 1 to 3 drivers
            dict(t, spec=dict(t["spec"], quality_drivers=many)),
            dict(t, spec=dict(t["spec"], conflicts=t["spec"]["conflicts"] * 3)),            # at most 2 conflicts
            dict(t, spec=dict(t["spec"], defects=[dict(t["spec"]["defects"][0], kinds=["ambiguous"])])),  # not an Architect kind
            dict(t, spec=dict(t["spec"], defects=[{"target": "REQ-002/AC-001", "kinds": ["untestable"]}])),  # no seed form
            dict(t, overlay=[{"path": "backend/src/a.ts", "content": "x"}]),                # outside the Architect's truth
            dict(t, overlay=[{"path": ".github/workflows/x.yml", "content": "x"}]),
            dict(t, overlay=[{"path": "architecture/../x", "content": "x"}]),               # schema: escape
            dict(t, reference=[]),                                                           # no Developer layers
            dict(t, agent="developer"),
        ]
        for b in bad:
            with self.assertRaises(HarnessError):
                self.check(b)
        self.check(dict(t, overlay=[{"path": p, "content": "x"} for p in
                                    ("requirements/x/REQ-009.md", "architecture/system/adr/ADR-009.md",
                                     "knowledge/rules/x/R-009.md")]))

    def test_shared_defs_match_the_developer_schema(self):
        with open(ARCH_SCHEMA) as fh:
            arch = json.load(fh)
        with open(DEV_SCHEMA) as fh:
            dev = json.load(fh)
        self.assertEqual(arch["$defs"]["files"], dev["$defs"]["files"])
        self.assertEqual(strip_descriptions(arch["$defs"]["seeding"]), strip_descriptions(dev["properties"]["seeding"]))
        for key in ("id", "set", "base_sha"):
            self.assertEqual(arch["properties"][key], dev["properties"][key])

    def test_materialize(self):
        product, sha = product_repo({"impl.txt": "base\n"})
        d = tempfile.mkdtemp()
        p = write(d, "task.json", arch_task("seeded", sha))
        out = os.path.join(d, "tree")
        res = run_cli("eval_task.py", "materialize", "--agent", "architect", "--task", p, "--product", product,
                      "--layers", "overlay", "--out", out)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("clean wording", res.stdout + res.stderr)
        with open(os.path.join(out, "requirements/x/REQ-002.md")) as fh:
            self.assertEqual(fh.read(), "new req\n")
        log = subprocess.run(["git", "-C", out, "log", "--format=%s"], capture_output=True, text=True).stdout
        self.assertEqual(log.strip().splitlines(), ["Initial commit"])
        res = run_cli("eval_task.py", "materialize", "--agent", "architect", "--task", p, "--product", product,
                      "--layers", "overlay,reference", "--out", out)
        self.assertIn("input_invalid", res.stderr)                          # a bundle has the overlay only

    def test_event_with_label_and_comments(self):
        d = tempfile.mkdtemp()
        p = write(d, "task.json", arch_task("clean", "0" * 40))
        ev, cs = os.path.join(d, "e.json"), os.path.join(d, "c.json")
        res = run_cli("eval_task.py", "event", "--agent", "architect", "--task", p, "--operator", "op", "--repo", "o/r",
                      "--out-event", ev, "--out-comments", cs)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(ev) as fh:
            event = json.load(fh)
        with open(cs) as fh:
            self.assertEqual(json.load(fh), [])
        self.assertEqual((event["label"], event["issue"]["labels"]), ({"name": "arch:design"}, [{"name": "arch:design"}]))
        # Comments (none in v1 bundles) come through build_input.py as operator answers.
        t = dict(arch_task("clean", "0" * 40), comments=[{"body": "Q-001: b"}, {"body": "/architect"}])
        event, comments = synthetic_event(t, "o/r", "op")
        data = build(event, comments, {"op"}, ["system"], "bot[bot]", "1-1", "knowledge/product-core.md", True,
                     agent="architect")
        self.assertEqual((data["run"]["trigger"], data["run"]["intake_ref"]), ("arch_design", "o/r#1"))
        self.assertEqual([(c["ref"], c["author_kind"], c["body"]) for c in data["untrusted"]["comments"]],
                         [("o/r#1 comment 1", "operator", "Q-001: b")])
        self.assertEqual(data["dropped_comments"], 1)                       # the run command

    def test_developer_defaults_unchanged(self):
        d = tempfile.mkdtemp()
        dev = write(d, "dev.json", task("feature", "0" * 40))
        arch = write(d, "arch.json", arch_task("seeded", "0" * 40))
        self.assertEqual(run_cli("eval_task.py", "check", "--task", dev).returncode, 0)
        res = run_cli("eval_task.py", "check", "--task", arch)          # no --agent: the Developer schema
        self.assertIn("input_invalid", res.stderr)
        self.assertEqual(run_cli("eval_task.py", "check", "--agent", "architect", "--task", arch).returncode, 0)
        self.assertEqual(run_cli("eval_task.py", "check", "--task", arch, "--schema", ARCH_SCHEMA).returncode, 0)
        event, comments = synthetic_event(copy.deepcopy(task("fix", "0" * 40)), "o/r", "op")
        self.assertEqual((event["label"], comments), ({"name": "dev:fix"}, []))


if __name__ == "__main__":
    unittest.main()
