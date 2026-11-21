"""DevOps and ci-upkeep agents: schemas, fixtures, prompt build and pack budget.

Covers plugins/staff-engineering (S-DEVOPS-002, -013, -016): both read-stage
schemas are valid draft 2020-12 and pass the CLI's draft-07 copy; the valid
fixtures pass and the invalid ones fail; prepare_agent builds each agent with
read-only tools only; and each pack stays under 15k tokens at chars/3.2
(S-GEN-009).
"""
import copy
import glob
import inspect
import json
import os
import tempfile
import unittest

from jsonschema import Draft7Validator, Draft202012Validator

from helpers import FIXTURES, STAFF, run_cli

from common import HarnessError
from prepare_agent import build_prompt, cli_schema, front_matter_list, split_front_matter
from validate_output import check_schema

PLUGINS = os.path.join(STAFF, "plugins")
ENG = os.path.join(PLUGINS, "staff-engineering")
DEVOPS_FIXTURES = os.path.join(FIXTURES, "devops")

AGENTS = {
    "devops": {
        "agent": os.path.join(ENG, "agents", "devops.md"),
        "schema": os.path.join(ENG, "schemas", "devops-output.schema.json"),
        "skills": ["staff-core:strategy-shared", "staff-engineering:devops-core",
                   "staff-engineering:devops-controls", "staff-engineering:devops-delivery"],
        "marker": "You are **DevOps**",
    },
    "ci-upkeep": {
        "agent": os.path.join(ENG, "agents", "ci-upkeep.md"),
        "schema": os.path.join(ENG, "schemas", "ci-upkeep-output.schema.json"),
        "skills": ["staff-core:strategy-shared", "staff-engineering:devops-core",
                   "staff-engineering:devops-controls", "staff-engineering:devops-upkeep"],
        "marker": "You are **`ci-upkeep`**",
    },
}

# S-GEN-009: 15k tokens per pack at chars/3.2.
PACK_CAP_CHARS = 15_000 * 3.2


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def fixtures(prefix):
    return sorted(glob.glob(os.path.join(DEVOPS_FIXTURES, f"{prefix}-*.json")))


def schema_for(path):
    name = os.path.basename(path)
    return AGENTS["ci-upkeep" if "-ci-upkeep-" in name else "devops"]["schema"]


def skill_path(skill):
    plugin, _, name = skill.partition(":")
    return os.path.join(PLUGINS, plugin, "skills", name, "SKILL.md")


def pack_chars(agent):
    """Agent file plus every preloaded skill file (strategy-shared included), newlines included."""
    front, _ = split_front_matter(agent)
    paths = [agent] + [skill_path(s) for s in front_matter_list(front, "skills")]
    sizes = {}
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            sizes[os.path.relpath(p, STAFF)] = len(fh.read())
    return sizes


class SchemaTest(unittest.TestCase):
    def test_schemas_are_valid_2020_12(self):
        for name, a in AGENTS.items():
            with self.subTest(name):
                schema = load_json(a["schema"])
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
                Draft202012Validator.check_schema(schema)
                self.assertFalse(schema["additionalProperties"])
                self.assertIn("decision_summary", schema["required"])
                self.assertEqual(schema["$defs"]["text"]["maxLength"], 2000)

    def test_cli_copy_is_valid_draft_07(self):
        for name, a in AGENTS.items():
            with self.subTest(name):
                cli = cli_schema(load_json(a["schema"]))
                self.assertNotIn("$schema", cli)
                Draft7Validator.check_schema(cli)

    def test_every_object_closed(self):
        """additionalProperties is false on every object with properties, except the open-keyed maps."""
        open_maps = {"iac", "deploy_units", "migrations"}

        def walk(node, path):
            if isinstance(node, dict):
                if "properties" in node and node.get("type") == "object" and path[-1] not in open_maps:
                    self.assertIs(node.get("additionalProperties"), False, "/".join(path))
                for k, v in node.items():
                    walk(v, path + [k])
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, path + [str(i)])

        for name, a in AGENTS.items():
            walk(load_json(a["schema"]), [name])

    def test_fixture_sets_cover_both_schemas(self):
        valid, invalid = fixtures("valid"), fixtures("invalid")
        for name in AGENTS:
            tag = f"-{name}-"
            self.assertTrue(any(tag in os.path.basename(p) for p in valid), name)
            self.assertTrue(any(tag in os.path.basename(p) for p in invalid), name)

    def test_valid_fixtures_pass(self):
        for path in fixtures("valid"):
            with self.subTest(os.path.basename(path)):
                check_schema(load_json(path), load_json(schema_for(path)))

    def test_invalid_fixtures_fail(self):
        for path in fixtures("invalid"):
            with self.subTest(os.path.basename(path)):
                with self.assertRaises(HarnessError) as ctx:
                    check_schema(load_json(path), load_json(schema_for(path)))
                self.assertEqual(ctx.exception.reason, "schema_invalid")


class MutationTest(unittest.TestCase):
    devops = load_json(AGENTS["devops"]["schema"])
    upkeep = load_json(AGENTS["ci-upkeep"]["schema"])

    def assertInvalid(self, out, schema):
        with self.assertRaises(HarnessError) as ctx:
            check_schema(out, schema)
        self.assertEqual(ctx.exception.reason, "schema_invalid")

    def base(self, name):
        return copy.deepcopy(load_json(os.path.join(DEVOPS_FIXTURES, name)))

    def test_devops_rejects(self):
        cases = {
            "extra top-level field": lambda o: o.update(actions=["push"]),
            "missing decision_summary": lambda o: o.pop("decision_summary"),
            "free text over 2,000": lambda o: o.update(decision_summary="x" * 2001),
            "flag reason over 2,000": lambda o: o["pr"]["flags"][0].update(reason="x" * 2001),
            "more than 7 questions": lambda o: o.update(questions=[{
                "id": f"Q-00{i}", "key": {"entity": "e", "target_id": None, "attribute": "a"},
                "blocks": ["t"], "blocking": False, "text": "q",
                "options": [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}],
                "recommended": "a", "priority": 1} for i in range(1, 9)]),
            "draft without pr": lambda o: o.pop("pr"),
            "unknown pr kind": lambda o: o["pr"].update(kind="release"),
            "unknown environment": lambda o: o["pr"].update(environments=["shared-staging"]),
            "extra pr field": lambda o: o["pr"].update(base="develop"),
            "files with an over-long chunk": lambda o: o.update(files=[
                {"path": "ci.yml", "op": "modify", "from": None, "content": ["x" * 2001]}]),
            "rename without from": lambda o: o.update(files=[
                {"path": "ci.yml", "op": "rename", "from": None, "content": []}]),
            "delivery map outside bootstrap": lambda o: o.update(
                delivery_map=self.base("valid-devops-bootstrap.json")["delivery_map"]),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                out = self.base("valid-devops-draft.json")
                mutate(out)
                self.assertInvalid(out, self.devops)

    def test_devops_returned_and_bootstrap_rules(self):
        out = self.base("valid-devops-returned.json")
        out["design_requests"][0]["need"] = "interface"
        self.assertInvalid(out, self.devops)
        out = self.base("valid-devops-returned.json")
        out["private_reports"][0]["id"] = "SR-1"
        self.assertInvalid(out, self.devops)
        out = self.base("valid-devops-bootstrap.json")
        out["delivery_map"]["environments"]["ephemeral"]["data_source"] = "production"
        self.assertInvalid(out, self.devops)
        out = self.base("valid-devops-bootstrap.json")
        out["delivery_map"]["deploy_units"]["web"] = []
        self.assertInvalid(out, self.devops)

    def test_ci_upkeep_rejects(self):
        cases = {
            "pin by tag": lambda o: o["pr"]["pins"][0].update(to="latest"),
            "upkeep without groups": lambda o: o.update(pin_groups=[]),
            "empty group": lambda o: o["pin_groups"][0].update(pins=[], cache_key_paths=[]),
            "upkeep_and_handoffs without handoffs": lambda o: o.update(handoffs=[]),
            "more than 10 groups": lambda o: o.update(pin_groups=[
                {"group_id": f"G-{i:02d}", "summary": "s", "pins": ["p"], "cache_key_paths": []}
                for i in range(11)]),
            "dispatch without target": lambda o: o.update(trigger={"kind": "dispatch", "ref": "r"}),
            "free text over 2,000": lambda o: o["handoffs"][0].update(text="x" * 2001),
            "private reports not allowed": lambda o: o.update(private_reports=[]),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                out = self.base("valid-ci-upkeep-upkeep.json")
                mutate(out)
                self.assertInvalid(out, self.upkeep)


class PrepareAgentTest(unittest.TestCase):
    def test_build_prompt_signature(self):
        self.assertEqual(list(inspect.signature(build_prompt).parameters), ["agent_path", "plugins_root"])

    def test_agents_build_with_read_only_tools(self):
        for name, a in AGENTS.items():
            with self.subTest(name):
                front, _ = split_front_matter(a["agent"])
                self.assertEqual(front_matter_list(front, "skills"), a["skills"])
                prompt, tools = build_prompt(a["agent"], PLUGINS)
                self.assertEqual(tools, ["Glob", "Grep", "Read"])
                self.assertFalse(prompt.startswith("---"))
                self.assertIn(a["marker"], prompt)
                positions = [prompt.index(f"# Preloaded skill `{s}`") for s in a["skills"]]
                self.assertEqual(positions, sorted(positions))
                self.assertIn("# Harness contract", prompt)

    def test_write_tools_fail_closed(self):
        for name, a in AGENTS.items():
            for extra in ("Edit", "Write", "Bash"):
                with self.subTest(f"{name}+{extra}"):
                    with open(a["agent"], encoding="utf-8") as fh:
                        text = fh.read().replace("tools: Read, Glob, Grep", f"tools: Read, Glob, Grep, {extra}")
                    path = os.path.join(tempfile.mkdtemp(), os.path.basename(a["agent"]))
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(text)
                    with self.assertRaises(HarnessError) as ctx:
                        build_prompt(path, PLUGINS)
                    self.assertEqual(ctx.exception.reason, "agent_invalid")

    def test_cli_builds_each_agent(self):
        for name, a in AGENTS.items():
            with self.subTest(name):
                d = tempfile.mkdtemp()
                proc = run_cli("prepare_agent.py", "--agent", a["agent"], "--plugins-root", PLUGINS,
                               "--schema", a["schema"], "--out-prompt", os.path.join(d, "prompt.md"),
                               "--out-schema", os.path.join(d, "schema.json"))
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("tools: Glob,Grep,Read", proc.stdout)
                Draft7Validator.check_schema(load_json(os.path.join(d, "schema.json")))


class PackBudgetTest(unittest.TestCase):
    def test_each_pack_under_15k_tokens(self):
        for name, a in AGENTS.items():
            with self.subTest(name):
                files = sum(pack_chars(a["agent"]).values())
                prompt, _ = build_prompt(a["agent"], PLUGINS)
                self.assertLess(files, PACK_CAP_CHARS)
                self.assertLess(len(prompt), PACK_CAP_CHARS)


if __name__ == "__main__":
    unittest.main()
