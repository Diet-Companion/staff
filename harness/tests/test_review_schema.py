"""staff-review: review-output schema, reviewer prompt and per-type pack budget.

The reviewer agent file preloads only staff-core:strategy-shared. The harness adds
one checklist skill per run (S-GEN-030). prepare_agent.py has no `--skill` yet,
so `review_prompt` below builds the prompt the way that option would: the agent
body, its front-matter skills, the checklist skill, then the harness contract.
"""
import copy
import glob
import json
import os
import re
import unittest

from jsonschema import Draft7Validator, Draft202012Validator

from helpers import FIXTURES, STAFF

from prepare_agent import HARNESS_CONTRACT, build_prompt, cli_schema, split_front_matter

PLUGINS = os.path.join(STAFF, "plugins")
REVIEW = os.path.join(PLUGINS, "staff-review")
AGENT = os.path.join(REVIEW, "agents", "reviewer.md")
SCHEMA = os.path.join(REVIEW, "schemas", "review-output.schema.json")
REVIEW_FIXTURES = os.path.join(FIXTURES, "review")

# S-GEN-009: 15k tokens per pack, measured as characters / 3.2.
CAP_CHARS = int(15_000 * 3.2)

# Checklist item IDs per type, from the owning role docs.
CHECKLISTS = {
    "requirements": [f"RC-{i}" for i in range(1, 10)],   # S-BA-029
    "architecture": [f"AR-{i}" for i in range(1, 11)],   # S-ARCH-031
    "code": [f"CC-{i}" for i in range(1, 10)],           # S-DEV-031
    "tests": [f"TR-{i}" for i in range(1, 10)],          # S-QA-043
    "pipeline": [f"PL-{i}" for i in range(1, 11)],       # S-DEVOPS-047
}

# The owning role's own always-loaded skills, where that role's plugin exists.
# Not loaded by the reviewer today; measured as a worst case (S-GEN-009 counts
# the role's always-loaded part in a reviewer pack).
ROLE_SKILLS = {
    "requirements": ["staff-product:requirements", "staff-product:elicitation"],
}


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def skill_section(skill):
    plugin, _, name = skill.partition(":")
    _, body = split_front_matter(os.path.join(PLUGINS, plugin, "skills", name, "SKILL.md"))
    return f"# Preloaded skill `{skill}`\n\n{body}"


def review_prompt(artifact_type, extra_skills=()):
    """The reviewer prompt with one checklist skill, as `--skill` would build it."""
    prompt, tools = build_prompt(AGENT, PLUGINS)
    added = [skill_section(f"staff-review:review-{artifact_type}")]
    added += [skill_section(s) for s in extra_skills]
    head, sep, tail = prompt.rpartition(HARNESS_CONTRACT)
    assert sep, "harness contract not found"
    return head + "\n\n".join(added) + "\n\n" + sep + tail, tools


class ReviewSchemaTest(unittest.TestCase):
    schema = load_json(SCHEMA)
    validator = Draft202012Validator(schema)

    def errors(self, doc):
        return list(self.validator.iter_errors(doc))

    def test_schema_is_valid_2020_12(self):
        Draft202012Validator.check_schema(self.schema)
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertFalse(self.schema["additionalProperties"])
        self.assertIn("decision_summary", self.schema["required"])

    def test_cli_copy_is_valid_draft_07(self):
        cli = cli_schema(self.schema)
        self.assertNotIn("$schema", cli)
        Draft7Validator.check_schema(cli)
        for path in glob.glob(os.path.join(REVIEW_FIXTURES, "valid-*.json")):
            with self.subTest(os.path.basename(path)):
                self.assertEqual(list(Draft7Validator(cli).iter_errors(load_json(path))), [])

    def test_every_free_text_is_capped(self):
        self.assertEqual(self.schema["$defs"]["text"]["maxLength"], 2000)

        def walk(node, path):
            if isinstance(node, dict):
                if node.get("type") == "string" and "enum" not in node and "const" not in node:
                    self.assertIn("maxLength", node, f"uncapped string at {path}")
                if node.get("type") == "array":
                    self.assertIn("maxItems", node, f"unbounded array at {path}")
                for k, v in node.items():
                    walk(v, f"{path}/{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}/{i}")
        walk(self.schema, "#")

    def test_valid_fixtures_cover_every_type(self):
        paths = sorted(glob.glob(os.path.join(REVIEW_FIXTURES, "valid-*.json")))
        self.assertTrue(paths)
        seen = set()
        for path in paths:
            doc = load_json(path)
            with self.subTest(os.path.basename(path)):
                self.assertEqual(self.errors(doc), [])
                seen.add(doc["artifact_type"])
                for f in doc["findings"]:
                    item, _, cited = f["finding_id"].split("|")
                    self.assertEqual(item, f["checklist_id"])
                    self.assertIn(cited, f["cited_ids"])
                order = ["blocker", "major", "minor"]
                ranks = [order.index(f["severity"]) for f in doc["findings"]]
                self.assertEqual(ranks, sorted(ranks), "findings not ordered by severity")
        self.assertEqual(seen, set(CHECKLISTS))

    def test_invalid_fixtures_fail(self):
        paths = sorted(glob.glob(os.path.join(REVIEW_FIXTURES, "invalid-*.json")))
        self.assertGreaterEqual(len(paths), 10)
        for path in paths:
            with self.subTest(os.path.basename(path)):
                self.assertNotEqual(self.errors(load_json(path)), [])

    def test_bounds(self):
        base = load_json(os.path.join(REVIEW_FIXTURES, "valid-tests-ready.json"))
        cases = {
            "eight findings": lambda d: d.update(findings=[copy.deepcopy(d["findings"][0]) for _ in range(8)]),
            "eight questions": lambda d: d.update(verdict="ready_with_questions", questions=[{
                "id": f"Q-{i:03d}", "blocks": ["pr#70"], "blocking": False, "text": "Which?",
                "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
                "recommended": "a", "priority": min(i, 7)} for i in range(1, 9)]),
            "text over 2,000": lambda d: d["findings"][0].update(text="x" * 2001),
            "summary over 2,000": lambda d: d.update(decision_summary="x" * 2001),
            "eleven cited ids": lambda d: d["findings"][0].update(cited_ids=["S-QA-006"] * 11),
            "unknown severity": lambda d: d["findings"][0].update(severity="critical"),
        }
        for name, fn in cases.items():
            doc = copy.deepcopy(base)
            fn(doc)
            with self.subTest(name):
                self.assertNotEqual(self.errors(doc), [])
        ok = copy.deepcopy(base)
        ok["findings"][0]["text"] = "x" * 2000
        self.assertEqual(self.errors(ok), [])


class ReviewerPromptTest(unittest.TestCase):
    def test_agent_is_read_only_and_preloads_only_shared(self):
        prompt, tools = build_prompt(AGENT, PLUGINS)
        self.assertEqual(tools, ["Glob", "Grep", "Read"])
        self.assertIn("You are the **shared reviewer**", prompt)
        self.assertIn("# Preloaded skill `staff-core:strategy-shared`", prompt)
        self.assertNotIn("# Preloaded skill `staff-review:", prompt)
        self.assertIn("S-GEN-026", prompt)

    def test_checklist_skills_hold_every_item_id(self):
        for artifact_type, items in CHECKLISTS.items():
            path = os.path.join(REVIEW, "skills", f"review-{artifact_type}", "SKILL.md")
            front, body = split_front_matter(path)
            with self.subTest(artifact_type):
                self.assertRegex(front, rf"(?m)^name: review-{artifact_type}$")
                for item in items:
                    self.assertRegex(body, rf"(?m)^\| {re.escape(item)} \|", f"{item} missing")

    def test_schema_item_patterns_match_checklists(self):
        schema = load_json(SCHEMA)
        branches = {b["if"]["properties"]["artifact_type"]["const"]: b["then"]
                    for b in schema["allOf"] if "artifact_type" in b["if"].get("properties", {})}
        for artifact_type, items in CHECKLISTS.items():
            pattern = branches[artifact_type]["properties"]["findings"]["items"]["properties"]["checklist_id"]["pattern"]
            prefix = items[0].split("-")[0]
            with self.subTest(artifact_type):
                for item in items:
                    self.assertRegex(item, pattern)
                self.assertNotRegex(f"{prefix}-{len(items) + 1}", pattern)

    def test_manifest(self):
        manifest = load_json(os.path.join(REVIEW, ".claude-plugin", "plugin.json"))
        self.assertEqual(manifest["name"], "staff-review")
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertEqual(manifest["dependencies"], ["staff-core"])

    def test_pack_per_type_within_budget(self):
        for artifact_type in CHECKLISTS:
            prompt, _ = review_prompt(artifact_type)
            with self.subTest(artifact_type):
                self.assertIn(f"# Preloaded skill `staff-review:review-{artifact_type}`", prompt)
                self.assertLess(prompt.index("strategy-shared`"), prompt.index(f"review-{artifact_type}`"))
                self.assertLess(prompt.index(f"review-{artifact_type}`"), prompt.index("# Harness contract"))
                self.assertLess(len(prompt), CAP_CHARS, f"{artifact_type}: {len(prompt)} chars")

    def test_pack_with_role_skills_within_budget(self):
        for artifact_type, extra in ROLE_SKILLS.items():
            prompt, _ = review_prompt(artifact_type, extra)
            with self.subTest(artifact_type):
                self.assertLess(len(prompt), CAP_CHARS, f"{artifact_type}: {len(prompt)} chars")


if __name__ == "__main__":
    unittest.main()
