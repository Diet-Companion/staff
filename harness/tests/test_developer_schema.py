"""Developer and dev-upkeep read-stage schemas, fixtures and agent packs (staff-engineering)."""
import copy
import glob
import inspect
import json
import os
import tempfile
import unittest

from jsonschema import Draft7Validator, Draft202012Validator

from helpers import STAFF, run_cli

from prepare_agent import HARNESS_CONTRACT, build_prompt, cli_schema

ENG = os.path.join(STAFF, "plugins", "staff-engineering")
PLUGINS = os.path.join(STAFF, "plugins")
FIX = os.path.join(STAFF, "harness", "tests", "fixtures", "developer")
SCHEMAS = {
    "developer": os.path.join(ENG, "schemas", "developer-output.schema.json"),
    "dev-upkeep": os.path.join(ENG, "schemas", "dev-upkeep-output.schema.json"),
}
AGENTS = {name: os.path.join(ENG, "agents", f"{name}.md") for name in SCHEMAS}
SHARED_DEFS = ("text", "short_text", "ref", "path", "chunk", "req_id", "ac_id", "any_req_id", "rule_id",
               "if_version", "if_element", "adr_constraint", "fix_target", "test_id", "proposed_file",
               "dependency", "flag", "pr")
# S-GEN-009: 15k tokens at characters / 3.2.
PACK_CAP_CHARS = 15000 * 3.2
# The CLI validates --json-schema as draft-07 in strict mode (prepare_agent.py).
NOT_DRAFT7 = {"prefixItems", "unevaluatedProperties", "unevaluatedItems", "dependentRequired",
              "dependentSchemas", "$dynamicRef", "$dynamicAnchor", "minContains", "maxContains"}


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def schema_for(fixture_name):
    return "dev-upkeep" if os.path.basename(fixture_name).startswith("upkeep-") else "developer"


def walk(node, path=(), skip=("if", "then", "else", "not")):
    """Yield (path, dict) for every schema node outside conditional subschemas."""
    if isinstance(node, dict):
        yield path, node
        for k, v in node.items():
            if k not in skip:
                yield from walk(v, path + (k,), skip)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, path + (str(i),), skip)


def keys_anywhere(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from keys_anywhere(v)
    elif isinstance(node, list):
        for v in node:
            yield from keys_anywhere(v)


class DeveloperSchemaTest(unittest.TestCase):
    schemas = {name: load(path) for name, path in SCHEMAS.items()}
    validators = {name: Draft202012Validator(s, format_checker=Draft202012Validator.FORMAT_CHECKER)
                  for name, s in schemas.items()}

    def errors(self, agent, out):
        return sorted(self.validators[agent].iter_errors(out), key=lambda e: list(map(str, e.absolute_path)))

    def assertInvalid(self, agent, out, at=None):
        errs = self.errors(agent, out)
        self.assertTrue(errs, "expected a schema error")
        if at is not None:
            def flat(es):  # errors under anyOf (nullable fields) sit in e.context
                for e in es:
                    yield e
                    yield from flat(e.context)
            paths = ["/" + "/".join(map(str, e.absolute_path)) for e in flat(errs)]
            self.assertTrue(any(p.startswith(at) for p in paths), f"no error at {at}: {paths}")

    # --- schema shape --------------------------------------------------------
    def test_metaschema_2020_12(self):
        for name, s in self.schemas.items():
            with self.subTest(name):
                self.assertEqual(s["$schema"], "https://json-schema.org/draft/2020-12/schema")
                Draft202012Validator.check_schema(s)
                self.assertEqual(s["properties"]["agent"], {"const": name})
                self.assertIn("decision_summary", s["required"])

    def test_closed_objects_and_capped_text(self):
        for name, s in self.schemas.items():
            for path, node in walk(s):
                if node.get("type") == "object" and "properties" in node:
                    with self.subTest(name, at="/".join(path)):
                        self.assertIs(node.get("additionalProperties"), False)
                if node.get("type") == "string" or node.get("type") == ["string", "null"]:
                    with self.subTest(name, at="/".join(path)):
                        self.assertLessEqual(node.get("maxLength", 10 ** 9), 2000)

    def test_no_files_field_from_the_model(self):
        # files[] is harness-derived from the workspace diff (S-DEV-021, S-DEV-042).
        for name, s in self.schemas.items():
            self.assertNotIn("files", s["properties"])
            self.assertIn("proposed_files", s["required"])

    def test_shared_defs_identical(self):
        dev, upk = self.schemas["developer"]["$defs"], self.schemas["dev-upkeep"]["$defs"]
        for d in SHARED_DEFS:
            with self.subTest(d):
                self.assertEqual(dev[d], upk[d])

    def test_cli_copy_is_draft7_compatible(self):
        for name, s in self.schemas.items():
            with self.subTest(name):
                cli = cli_schema(s)
                self.assertNotIn("$schema", cli)
                self.assertEqual(cli["required"], s["required"])
                self.assertFalse(NOT_DRAFT7 & set(keys_anywhere(cli)))
                Draft7Validator.check_schema(cli)

    # --- fixtures ------------------------------------------------------------
    def valid_fixtures(self):
        names = sorted(glob.glob(os.path.join(FIX, "*.json")))
        self.assertGreaterEqual(len(names), 6)
        return names

    def test_valid_fixtures_pass(self):
        for path in self.valid_fixtures():
            with self.subTest(os.path.basename(path)):
                self.assertEqual(self.errors(schema_for(path), load(path)), [])

    def test_cli_copy_agrees_on_fixtures(self):
        for path in self.valid_fixtures() + sorted(glob.glob(os.path.join(FIX, "invalid", "*.json"))):
            agent = schema_for(path)
            with self.subTest(os.path.basename(path)):
                full = bool(self.errors(agent, load(path)))
                cli = bool(list(Draft7Validator(cli_schema(self.schemas[agent])).iter_errors(load(path))))
                self.assertEqual(full, cli)

    INVALID = {
        "developer-files-without-pr.json": "/proposed_files",
        "developer-diff-instead-of-content.json": "/proposed_files/0",
        "developer-chunk-over-2000.json": "/proposed_files/0/content/0",
        "developer-path-escapes-repo.json": "/proposed_files/0/path",
        "developer-write-action.json": "",
        "developer-fix-without-classification.json": "/classification",
        "developer-requirement-defect-with-code.json": "/pr",
        "upkeep-feature-kind.json": "/pr/kind",
        "upkeep-tool-runs-without-pr.json": "/tool_runs",
    }

    def test_invalid_fixtures_fail_where_expected(self):
        found = {os.path.basename(p) for p in glob.glob(os.path.join(FIX, "invalid", "*.json"))}
        self.assertEqual(found, set(self.INVALID))
        for name, at in self.INVALID.items():
            path = os.path.join(FIX, "invalid", name)
            with self.subTest(name):
                self.assertInvalid(schema_for(name), load(path), at)

    # --- Developer rules -----------------------------------------------------
    def case(self, base, mutate, at=None, agent="developer"):
        out = copy.deepcopy(load(os.path.join(FIX, base)))
        mutate(out)
        self.assertInvalid(agent, out, at)

    def test_developer_rejects(self):
        f = "developer-feature.json"
        file0 = lambda o: o["proposed_files"][0]
        cases = {
            "missing decision_summary": (f, lambda o: o.pop("decision_summary"), ""),
            "decision_summary over 2,000": (f, lambda o: o.update(decision_summary="x" * 2001), "/decision_summary"),
            "more than 25 files": (f, lambda o: o.update(proposed_files=[file0(o)] * 26), "/proposed_files"),
            "more than 50 chunks": (f, lambda o: file0(o).update(content=["x"] * 51), "/proposed_files/0/content"),
            "NUL in content": (f, lambda o: file0(o).update(content=["a\x00b"]), "/proposed_files/0/content/0"),
            "absolute path": (f, lambda o: file0(o).update(path="/etc/passwd"), "/proposed_files/0/path"),
            "dot segment": (f, lambda o: file0(o).update(path="src/./x.py"), "/proposed_files/0/path"),
            "git dir": (f, lambda o: file0(o).update(path=".git/config"), "/proposed_files/0/path"),
            "rename without from": (f, lambda o: file0(o).update(op="rename"), "/proposed_files/0"),
            "from on modify": (f, lambda o: file0(o).update(op="modify", **{"from": "src/a.py"}), "/proposed_files/0"),
            "delete with content": (f, lambda o: file0(o).update(op="delete"), "/proposed_files/0/content"),
            "pr without files": (f, lambda o: o.update(proposed_files=[]), "/proposed_files"),
            "feature without ACs": (f, lambda o: o["pr"].update(implements_acs=[]), "/pr/implements_acs"),
            "feature with fixes": (f, lambda o: o["pr"].update(fixes={"ticket": "t#1", "target": "R-004"}), "/pr/fixes"),
            "not_unit_observable on feature": (f, lambda o: o["pr"].update(
                not_unit_observable={"target": "R-004", "test_gap": "gap"}), "/pr/not_unit_observable"),
            "refactor with ACs": (f, lambda o: o["pr"].update(kind="refactor"), "/pr/implements_acs"),
            "upkeep kind from Developer": (f, lambda o: o["pr"].update(kind="upkeep", implements_acs=[]), "/pr/kind"),
            "pr without ticket": (f, lambda o: o["pr"].update(ticket=None), "/pr/ticket"),
            "bad AC id": (f, lambda o: o["pr"]["implements_acs"][0].update(ac="REQ-12/AC-1"), "/pr/implements_acs/0/ac"),
            "bad IF version": (f, lambda o: o["pr"].update(implements=["IF-002@1.1"]), "/pr/implements/0"),
            "bad constraint id": (f, lambda o: o["pr"]["constraints"][0].update(id="ADR-3/C-2"), "/pr/constraints/0/id"),
            "bad disposition": (f, lambda o: o["pr"]["constraints"][0].update(disposition="waived"), "/pr/constraints/0"),
            "design request on a REQ": (f, lambda o: o["design_requests"][0].update(target="REQ-012"), "/design_requests/0/target"),
            "bad design need": (f, lambda o: o["design_requests"][0].update(need="ui"), "/design_requests/0/need"),
            "more than 7 design requests": (f, lambda o: o.update(design_requests=o["design_requests"] * 8), "/design_requests"),
            "characterization not a test id": (f, lambda o: o["pr"].update(characterization=["test_x"]), "/pr/characterization/0"),
            "missing classification key": (f, lambda o: o.pop("classification"), ""),
            "both pr and code_map": ("developer-bootstrap.json", lambda o: o.update(
                pr=load(os.path.join(FIX, f))["pr"], proposed_files=load(os.path.join(FIX, f))["proposed_files"]), "/pr"),
            "fix classified not_a_code_defect": ("developer-fix.json", lambda o: o["classification"].update(
                kind="not_a_code_defect"), "/classification/kind"),
            "fix without fixes": ("developer-fix.json", lambda o: o["pr"].update(fixes=None), "/pr/fixes"),
            "requirement defect without item": ("developer-requirement-defect.json", lambda o: o.update(
                defect_items=[]), "/defect_items"),
            "defect item on IF element": ("developer-requirement-defect.json", lambda o: o["defect_items"][0].update(
                target="IF-002@1.1.0#cancel"), "/defect_items/0/target"),
            "more than 7 questions": ("developer-requirement-defect.json", lambda o: o.update(
                questions=o["questions"] * 8), "/questions"),
            "one option": ("developer-requirement-defect.json", lambda o: o["questions"][0].update(
                options=[{"id": "a", "text": "only"}]), "/questions/0/options"),
            "private report kind": ("developer-requirement-defect.json", lambda o: o["private_reports"][0].update(
                kind="note"), "/private_reports/0/kind"),
            "bootstrap unknown key": ("developer-bootstrap.json", lambda o: o["code_map"]["entry"].update(
                ci_paths=[".github/**"]), "/code_map/entry"),
            "bootstrap more than 3 samples": ("developer-bootstrap.json", lambda o: o["code_map"]["evidence"][0].update(
                samples=o["code_map"]["evidence"][0]["samples"] * 4), "/code_map/evidence/0/samples"),
        }
        for name, (base, mutate, at) in cases.items():
            with self.subTest(name):
                self.case(base, mutate, at)

    def test_upkeep_rejects(self):
        u = "upkeep-change.json"
        cases = {
            "missing decision_summary": (lambda o: o.pop("decision_summary"), ""),
            "AC declared": (lambda o: o["pr"].update(implements_acs=[{"ac": "REQ-012/AC-001", "part": "full"}]),
                            "/pr/implements_acs"),
            "fixes set": (lambda o: o["pr"].update(fixes={"ticket": "t#1", "target": "R-004"}), "/pr/fixes"),
            "tool run without paths": (lambda o: o["tool_runs"][0].update(paths=[]), "/tool_runs/0/paths"),
            "more than 10 tool runs": (lambda o: o.update(tool_runs=o["tool_runs"] * 11), "/tool_runs"),
            "more than 7 handoffs": (lambda o: o.update(handoffs=o["handoffs"] * 8), "/handoffs"),
            "residual edit path escapes": (lambda o: o["residual_edits"][0].update(path="../x"), "/residual_edits/0/path"),
            "pr with nothing to do": (lambda o: o.update(tool_runs=[], proposed_files=[]), ""),
            "developer-only field": (lambda o: o.update(defect_items=[]), ""),
            "dependencies without pr": (lambda o: o.update(pr=None, tool_runs=[], proposed_files=[],
                                                           residual_edits=[]), "/dependencies"),
        }
        for name, (mutate, at) in cases.items():
            with self.subTest(name):
                self.case(u, mutate, at, agent="dev-upkeep")


class DeveloperAgentPackTest(unittest.TestCase):
    """The agents build with prepare_agent.build_prompt(agent_path, plugins_root) and fit S-GEN-009."""

    def test_build_prompt_signature(self):
        self.assertEqual(list(inspect.signature(build_prompt).parameters), ["agent_path", "plugins_root"])

    def test_agents_build_read_only(self):
        skills = {
            "developer": ["staff-core:strategy-shared", "staff-engineering:developer-change-contract",
                          "staff-engineering:developer-implementation"],
            "dev-upkeep": ["staff-core:strategy-shared", "staff-engineering:developer-change-contract"],
        }
        for name, path in AGENTS.items():
            with self.subTest(name):
                prompt, tools = build_prompt(path, PLUGINS)
                self.assertEqual(tools, ["Glob", "Grep", "Read"])
                self.assertFalse(prompt.startswith("---"))
                for skill in skills[name]:
                    self.assertIn(f"# Preloaded skill `{skill}`", prompt)
                self.assertLess(prompt.index("strategy-shared`"), prompt.index("developer-change-contract`"))
                # The on-demand reference is never preloaded (S-DEV-026).
                self.assertNotIn("Preloaded skill `staff-engineering:developer-reference`", prompt)
                self.assertNotIn("# Developer on-demand reference", prompt)

    def test_packs_within_budget(self):
        for name, path in AGENTS.items():
            with self.subTest(name):
                prompt, _ = build_prompt(path, PLUGINS)
                pack = len(prompt) - len(HARNESS_CONTRACT)
                self.assertLess(pack, PACK_CAP_CHARS)
                self.assertLess(len(prompt), PACK_CAP_CHARS)

    def test_prepare_agent_cli(self):
        for name, path in AGENTS.items():
            with self.subTest(name):
                d = tempfile.mkdtemp()
                out_prompt, out_schema = os.path.join(d, "prompt.md"), os.path.join(d, "schema.json")
                proc = run_cli("prepare_agent.py", "--agent", path, "--plugins-root", PLUGINS,
                               "--schema", SCHEMAS[name], "--out-prompt", out_prompt, "--out-schema", out_schema)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("tools: Glob,Grep,Read", proc.stdout)
                self.assertNotIn("$schema", load(out_schema))


if __name__ == "__main__":
    unittest.main()
