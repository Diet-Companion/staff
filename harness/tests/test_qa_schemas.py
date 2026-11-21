"""staff-qa: read-stage schemas, fixtures, agent preparation and pack sizes."""
import glob
import json
import os
import re
import tempfile
import unittest

from jsonschema import Draft7Validator, Draft202012Validator

from helpers import FIXTURES, STAFF, run_cli

from prepare_agent import HARNESS_CONTRACT, build_prompt, cli_schema, split_front_matter

PLUGINS = os.path.join(STAFF, "plugins")
QA = os.path.join(PLUGINS, "staff-qa")
SCHEMAS = os.path.join(QA, "schemas")
QA_FIXTURES = os.path.join(FIXTURES, "qa")

# agent -> its read-stage schema (the three generators share one, S-QA-026).
AGENTS = {
    "test-gen-unit": "test-gen",
    "test-gen-api": "test-gen",
    "test-gen-ui": "test-gen",
    "ci-healer": "ci-healer",
    "exploratory": "exploratory",
    "mutant-drafter": "mutant-drafter",
    "equivalence-filter": "equivalence-filter",
}
PACK_SKILLS = {
    "test-gen-unit": "qa-test-generation", "test-gen-api": "qa-test-generation", "test-gen-ui": "qa-test-generation",
    "ci-healer": "qa-healing", "exploratory": "qa-exploratory",
    "mutant-drafter": "qa-mutation", "equivalence-filter": "qa-mutation",
}
# S-GEN-009: 15k tokens at chars/3.2.
PACK_CAP_CHARS = 15000 * 3.2
TEXT_CAP = 2000  # S-SEC-002

# Each invalid fixture fails for one reason; this is the keyword that catches it.
INVALID = {
    "test-gen.invalid.add-without-content.json": "required",
    "test-gen.invalid.bad-cited-id.json": "pattern",
    "test-gen.invalid.blocked-with-files.json": "maxItems",
    "test-gen.invalid.chunk-too-long.json": "maxLength",
    "test-gen.invalid.defect-kind-infeasible.json": "enum",
    "test-gen.invalid.extra-property.json": "additionalProperties",
    "test-gen.invalid.feedback-round-3.json": "maximum",
    "test-gen.invalid.generator-sets-equivalent.json": "enum",
    "test-gen.invalid.layer-mismatch.json": "const",
    "test-gen.invalid.missing-decision-summary.json": "required",
    "test-gen.invalid.null-product-pr-not-main.json": "const",
    "test-gen.invalid.path-out-of-scope.json": "not",
    "test-gen.invalid.path-traversal.json": "pattern",
    "test-gen.invalid.repair-wrong-trigger.json": "const",
    "test-gen.invalid.text-too-long.json": "maxLength",
    "test-gen.invalid.too-many-questions.json": "maxItems",
    "ci-healer.invalid.bad-test-id.json": "pattern",
    "ci-healer.invalid.files-on-row-d.json": "maxItems",
    "ci-healer.invalid.heal-on-human-pr.json": "maxItems",
    "ci-healer.invalid.main-failure-without-item.json": "required",
    "ci-healer.invalid.quarantine-on-row-c.json": "maxItems",
    "ci-healer.invalid.repro-21-steps.json": "maxItems",
    "ci-healer.invalid.route-on-row-c.json": "const",
    "ci-healer.invalid.row-a-without-quarantine.json": "minItems",
    "ci-healer.invalid.row-b-without-declaring-ref.json": "type",
    "ci-healer.invalid.row-label-mismatch.json": "const",
    "exploratory.invalid.bad-mode.json": "enum",
    "exploratory.invalid.bug-target-test-condition.json": "pattern",
    "exploratory.invalid.bug-without-trace-refs.json": "required",
    "exploratory.invalid.candidate-without-cites.json": "minItems",
    "exploratory.invalid.charter-with-bugs.json": "maxItems",
    "exploratory.invalid.discovered-outside-scope.json": "pattern",
    "exploratory.invalid.missing-charter.json": "required",
    "exploratory.invalid.timebox-45.json": "maximum",
    "mutant-drafter.invalid.bad-concern-kind.json": "enum",
    "mutant-drafter.invalid.bad-operation.json": "pattern",
    "mutant-drafter.invalid.patch-and-mutation.json": "not",
    "mutant-drafter.invalid.patch-missing.json": "required",
    "mutant-drafter.invalid.patch-too-long.json": "maxLength",
    "mutant-drafter.invalid.too-many-mutants.json": "maxItems",
    "equivalence-filter.invalid.bad-verdict.json": "enum",
    "equivalence-filter.invalid.call-without-reason.json": "required",
    "equivalence-filter.invalid.missing-decision-summary.json": "required",
    "equivalence-filter.invalid.too-many-calls.json": "maxItems",
    "equivalence-filter.invalid.wrong-agent.json": "const",
}


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def schema_path(name):
    return os.path.join(SCHEMAS, f"{name}-output.schema.json")


def schema_of_fixture(fixture_name):
    head = fixture_name.split(".")[0]
    return "test-gen" if head.startswith("test-gen") else head


def errors(instance, schema):
    v = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    return list(v.iter_errors(instance))


def walk(node, path=""):
    if isinstance(node, dict):
        yield path, node
        for k, v in node.items():
            yield from walk(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}/{i}")


def pack_chars(agent):
    """Agent body + its preloaded skills + strategy-shared, as build_prompt assembles them (S-GEN-009)."""
    prompt, _ = build_prompt(os.path.join(QA, "agents", f"{agent}.md"), PLUGINS)
    contract = "\n\n" + HARNESS_CONTRACT
    assert prompt.endswith(contract + "\n")
    return len(prompt) - len(contract) - 1, len(prompt)


class QASchemaTest(unittest.TestCase):
    def test_schemas_are_valid_2020_12(self):
        for name in sorted(set(AGENTS.values())):
            with self.subTest(name):
                schema = load_json(schema_path(name))
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
                Draft202012Validator.check_schema(schema)
                self.assertEqual(schema["$id"], f"urn:staff:staff-qa:{name}-output:1.0.0")

    def test_cli_copy_is_valid_draft_07(self):
        # The CLI validates --json-schema as draft-07 (see prepare_agent.py).
        for name in sorted(set(AGENTS.values())):
            with self.subTest(name):
                Draft7Validator.check_schema(cli_schema(load_json(schema_path(name))))

    def test_read_stage_conventions(self):
        for name in sorted(set(AGENTS.values())):
            schema = load_json(schema_path(name))
            with self.subTest(name):
                self.assertIs(schema["additionalProperties"], False)
                self.assertIn("decision_summary", schema["required"])
                self.assertIn("schema_version", schema["required"])
                self.assertIn("agent", schema["required"])
            for path, node in walk(schema):
                if node.get("type") == "object" and "properties" in node:
                    with self.subTest(name, path=path, check="closed object"):
                        self.assertIs(node.get("additionalProperties"), False)
                if node.get("type") == "string" and "enum" not in node and "const" not in node:
                    with self.subTest(name, path=path, check="text cap"):
                        self.assertIn("maxLength", node, "every string is capped, or patterned and bounded")
                        self.assertLessEqual(node["maxLength"], TEXT_CAP)
                if node.get("type") == "array":
                    with self.subTest(name, path=path, check="per-run cap"):
                        self.assertIn("maxItems", node)

    def test_every_schema_has_valid_and_invalid_fixtures(self):
        names = [os.path.basename(p) for p in glob.glob(os.path.join(QA_FIXTURES, "*.json"))]
        for name in sorted(set(AGENTS.values())):
            with self.subTest(name):
                mine = [n for n in names if schema_of_fixture(n) == name]
                self.assertTrue(any(".valid" in n for n in mine))
                self.assertTrue(any(".invalid." in n for n in mine))
        self.assertEqual(sorted(n for n in names if ".invalid." in n), sorted(INVALID))

    def test_valid_fixtures_pass(self):
        for path in sorted(glob.glob(os.path.join(QA_FIXTURES, "*.valid*.json"))):
            name = os.path.basename(path)
            with self.subTest(name):
                errs = errors(load_json(path), load_json(schema_path(schema_of_fixture(name))))
                self.assertEqual([f"{list(e.absolute_path)} {e.validator}" for e in errs], [])

    def test_invalid_fixtures_fail_for_their_reason(self):
        for name, keyword in sorted(INVALID.items()):
            with self.subTest(name):
                errs = errors(load_json(os.path.join(QA_FIXTURES, name)), load_json(schema_path(schema_of_fixture(name))))
                self.assertTrue(errs, "fixture should be invalid")
                self.assertIn(keyword, {e.validator for e in errs})

    def test_generator_agent_pins_its_layer(self):
        schema = load_json(schema_path("test-gen"))
        base = load_json(os.path.join(QA_FIXTURES, "test-gen-unit.valid.json"))
        for agent, layer in (("test-gen-unit", "unit"), ("test-gen-api", "api"), ("test-gen-ui", "ui")):
            for other in ("unit", "api", "ui"):
                out = json.loads(json.dumps(base))
                out["agent"], out["pr"]["layer"] = agent, other
                with self.subTest(agent=agent, layer=other):
                    self.assertEqual(bool(errors(out, schema)), other != layer)


class QAAgentTest(unittest.TestCase):
    def test_manifest(self):
        manifest = load_json(os.path.join(QA, ".claude-plugin", "plugin.json"))
        self.assertEqual(manifest["name"], "staff-qa")
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertEqual(manifest["dependencies"], ["staff-core"])

    def test_one_file_per_agent_and_no_reviewer(self):
        files = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(QA, "agents", "*.md")))
        self.assertEqual(files, sorted(AGENTS))

    def test_front_matter(self):
        for agent, schema in AGENTS.items():
            with self.subTest(agent):
                front, body = split_front_matter(os.path.join(QA, "agents", f"{agent}.md"))
                self.assertRegex(front, rf"(?m)^name: {re.escape(agent)}$")
                self.assertRegex(front, r"(?m)^tools: Read, Glob, Grep$")
                self.assertIn(f"schemas/{schema}-output.schema.json", body)
                self.assertTrue(os.path.exists(schema_path(schema)))
                self.assertRegex(body, r"S-QA-\d{3}")

    def test_tokenless_agents_say_so(self):
        for agent in ("mutant-drafter", "equivalence-filter"):
            with self.subTest(agent):
                _, body = split_front_matter(os.path.join(QA, "agents", f"{agent}.md"))
                self.assertIn("You hold no token and write nothing.", body)

    def test_build_prompt_passes_tools_check(self):
        # build_prompt(agent_path, plugins_root) -> (prompt, sorted tools); raises on tools beyond Read, Glob, Grep.
        for agent in AGENTS:
            with self.subTest(agent):
                prompt, tools = build_prompt(os.path.join(QA, "agents", f"{agent}.md"), PLUGINS)
                self.assertEqual(tools, ["Glob", "Grep", "Read"])
                self.assertFalse(prompt.startswith("---"))
                order = ["# Preloaded skill `staff-core:strategy-shared`", "# Preloaded skill `staff-qa:qa-core`",
                         f"# Preloaded skill `staff-qa:{PACK_SKILLS[agent]}`", "# Harness contract"]
                positions = [prompt.index(m) for m in order]
                self.assertEqual(positions, sorted(positions))

    def test_prepare_agent_cli(self):
        d = tempfile.mkdtemp()
        for agent, schema in AGENTS.items():
            with self.subTest(agent):
                out_prompt, out_schema = os.path.join(d, f"{agent}.md"), os.path.join(d, f"{agent}.json")
                res = run_cli("prepare_agent.py", "--agent", os.path.join(QA, "agents", f"{agent}.md"),
                              "--plugins-root", PLUGINS, "--schema", schema_path(schema),
                              "--out-prompt", out_prompt, "--out-schema", out_schema)
                self.assertEqual(res.returncode, 0, res.stderr)
                self.assertIn("tools: Glob,Grep,Read", res.stdout)
                Draft7Validator.check_schema(load_json(out_schema))

    def test_pack_within_context_budget(self):
        # S-GEN-009, S-QA-020: agent body + preloaded skills + strategy-shared < 15k tokens at chars/3.2.
        for agent in AGENTS:
            with self.subTest(agent):
                pack, _ = pack_chars(agent)
                self.assertLess(pack, PACK_CAP_CHARS)

    def test_product_agnostic(self):
        email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}")
        for path in glob.glob(os.path.join(QA, "**", "*.*"), recursive=True):
            with self.subTest(os.path.relpath(path, QA)):
                with open(path, encoding="utf-8") as fh:
                    self.assertIsNone(email.search(fh.read()))


if __name__ == "__main__":
    unittest.main()
