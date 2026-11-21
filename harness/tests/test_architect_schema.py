"""Architect and arch-upkeep: read-stage schemas, fixtures, agent packs (S-ARCH-037, S-ARCH-048)."""
import copy
import json
import os
import re
import tempfile
import unittest

from jsonschema import Draft7Validator, Draft202012Validator

from helpers import FIXTURES, STAFF, run_cli

from common import HarnessError
from prepare_agent import build_prompt, cli_schema, front_matter_list, split_front_matter
from validate_output import check_schema

PLUGINS = os.path.join(STAFF, "plugins")
ENG = os.path.join(PLUGINS, "staff-engineering")
ARCH_FIXTURES = os.path.join(FIXTURES, "architect")
ROLE_DOC = os.path.join(STAFF, "docs", "strategy", "roles", "architect.md")

AGENTS = {
    "architect": {
        "agent": os.path.join(ENG, "agents", "architect.md"),
        "schema": os.path.join(ENG, "schemas", "architect-output.schema.json"),
        "skills": ["staff-core:strategy-shared", "staff-engineering:architecture-model",
                   "staff-engineering:architecture-design"],
        "valid": ["architect-design.json", "architect-drift.json", "architect-blocked.json"],
        "invalid": ["invalid-architect-extra-action.json", "invalid-architect-one-option.json",
                    "invalid-architect-drift-two-options.json"],
    },
    "arch-upkeep": {
        "agent": os.path.join(ENG, "agents", "arch-upkeep.md"),
        "schema": os.path.join(ENG, "schemas", "arch-upkeep-output.schema.json"),
        "skills": ["staff-core:strategy-shared", "staff-engineering:architecture-model"],
        "valid": ["arch-upkeep-nightly.json", "arch-upkeep-noop.json"],
        "invalid": ["invalid-arch-upkeep-name-change.json"],
    },
}

# S-GEN-009: 15k tokens at characters / 3.2.
PACK_CAP_CHARS = 15000 * 3.2


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def fixture(name):
    return load_json(os.path.join(ARCH_FIXTURES, name))


def skill_path(skill):
    plugin, _, name = skill.partition(":")
    return os.path.join(PLUGINS, plugin, "skills", name, "SKILL.md")


def pack_chars(agent):
    """Agent body plus every preloaded skill body (S-GEN-009 always-loaded pack)."""
    front, body = split_front_matter(AGENTS[agent]["agent"])
    total = len(body)
    for skill in front_matter_list(front, "skills"):
        total += len(split_front_matter(skill_path(skill))[1])
    return total


class SchemaTest(unittest.TestCase):
    def assertInvalid(self, out, schema):
        with self.assertRaises(HarnessError) as ctx:
            check_schema(out, schema)
        self.assertEqual(ctx.exception.reason, "schema_invalid")

    def test_schemas_are_valid_2020_12(self):
        for name, spec in AGENTS.items():
            with self.subTest(name):
                schema = load_json(spec["schema"])
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
                Draft202012Validator.check_schema(schema)
                self.assertFalse(schema["additionalProperties"])
                self.assertIn("decision_summary", schema["required"])
                self.assertEqual(schema["properties"]["agent"]["const"], name)

    def test_free_text_capped_at_2000(self):
        for name, spec in AGENTS.items():
            with self.subTest(name):
                self.assertEqual(load_json(spec["schema"])["$defs"]["text"]["maxLength"], 2000)

    def test_valid_fixtures_pass(self):
        for name, spec in AGENTS.items():
            schema = load_json(spec["schema"])
            for fx in spec["valid"]:
                with self.subTest(fx):
                    check_schema(fixture(fx), schema)

    def test_invalid_fixtures_fail(self):
        for name, spec in AGENTS.items():
            schema = load_json(spec["schema"])
            for fx in spec["invalid"]:
                with self.subTest(fx):
                    self.assertInvalid(fixture(fx), schema)

    def test_cli_copy_accepts_valid_fixtures_as_draft_07(self):
        """The CLI copy drops maxContains; it must still accept every valid output."""
        for name, spec in AGENTS.items():
            cli = cli_schema(load_json(spec["schema"]))
            Draft7Validator.check_schema(cli)
            for fx in spec["valid"]:
                with self.subTest(fx):
                    self.assertEqual(list(Draft7Validator(cli).iter_errors(fixture(fx))), [])


class ArchitectMutationTest(unittest.TestCase):
    schema = load_json(AGENTS["architect"]["schema"])

    def design(self):
        return copy.deepcopy(fixture("architect-design.json"))

    def assertInvalid(self, out):
        with self.assertRaises(HarnessError) as ctx:
            check_schema(out, self.schema)
        self.assertEqual(ctx.exception.reason, "schema_invalid")

    def adr(self, out):
        return next(a for a in out["artifacts"] if a["type"] == "adr")

    def test_missing_decision_summary(self):
        out = self.design()
        del out["decision_summary"]
        self.assertInvalid(out)

    def test_free_text_over_2000(self):
        out = self.design()
        out["decision_summary"] = "x" * 2001
        self.assertInvalid(out)

    def test_at_most_3_adrs(self):
        out = self.design()
        adr = self.adr(out)
        for n in (5, 6):
            extra = copy.deepcopy(adr)
            extra["id"] = f"ADR-{n:03d}"
            out["artifacts"].append(extra)
        check_schema(out, self.schema)  # 3 ADRs
        extra = copy.deepcopy(adr)
        extra["id"] = "ADR-007"
        out["artifacts"].append(extra)
        self.assertInvalid(out)

    def test_at_most_7_questions(self):
        out = self.design()
        q = out["questions"][1]
        out["questions"] = [dict(q, id=f"Q-{i:03d}", priority=min(i, 7)) for i in range(1, 9)]
        self.assertInvalid(out)

    def test_at_most_4_options(self):
        out = self.design()
        opts = self.adr(out)["options"]
        for k in "cde":
            opts.append(dict(opts[1], key=k))
        self.assertInvalid(out)

    def test_decision_needs_chosen_when_accepted(self):
        out = self.design()
        self.adr(out)["decision"] = {"outcome": "accepted", "chosen": None, "decided_by": "ticket#88/comment-3"}
        self.assertInvalid(out)

    def test_constraint_check_is_rule_ref_or_review(self):
        out = self.design()
        self.adr(out)["options"][1]["constraints"][0]["check"] = "lint it somehow"
        self.assertInvalid(out)

    def test_testability_must_be_complete(self):
        out = self.design()
        cmp_ = next(a for a in out["artifacts"] if a["type"] == "component")
        cmp_["testability"] = [t for t in cmp_["testability"] if t["item"] != "seam_clock"]
        self.assertInvalid(out)

    def test_testability_gap_needs_reason(self):
        out = self.design()
        cmp_ = next(a for a in out["artifacts"] if a["type"] == "component")
        cmp_["testability"][0] = {"item": "stable_names", "state": "gap", "gap_accepted_by": None}
        self.assertInvalid(out)

    def test_shared_store_needs_adr(self):
        out = self.design()
        cmp_ = next(a for a in out["artifacts"] if a["type"] == "component")
        cmp_["data"] = [{"store": "order-replica", "shared_with": ["CMP-002"]}]
        self.assertInvalid(out)
        cmp_["data"][0]["allowed_by"] = "ADR-004"
        check_schema(out, self.schema)

    def test_internal_interface_has_no_sunset(self):
        out = self.design()
        iface = next(a for a in out["artifacts"] if a["type"] == "interface")
        iface["compatibility_policy"] = "internal"
        iface["versions"][0]["sunset"] = "2027-03-01"
        self.assertInvalid(out)

    def test_spec_path_follows_product_contract(self):
        out = self.design()
        iface = next(a for a in out["artifacts"] if a["type"] == "interface")
        iface["versions"][0]["spec"] = "docs/order-status.yaml"
        self.assertInvalid(out)

    def test_qas_test_verification_is_qa(self):
        out = self.design()
        qas = next(a for a in out["artifacts"] if a["type"] == "qas")
        qas["verification"] = {"method": "test", "owner": "DEVOPS"}
        self.assertInvalid(out)

    def test_qas_where_only_with_monitor(self):
        out = self.design()
        qas = next(a for a in out["artifacts"] if a["type"] == "qas")
        qas["verification"] = {"method": "test", "owner": "QA", "where": "production"}
        self.assertInvalid(out)

    def test_qas_gap_needs_reason(self):
        out = self.design()
        qas = next(a for a in out["artifacts"] if a["type"] == "qas")
        qas["addressed_by"] = "gap"
        self.assertInvalid(out)
        qas["gap_reason"] = "No option meets the target at the A-001 rate."
        check_schema(out, self.schema)

    def test_defect_kinds_limited_to_arch_mapping(self):
        out = copy.deepcopy(fixture("architect-blocked.json"))
        out["defect_items"][0]["kind"] = "ambiguous"
        self.assertInvalid(out)

    def test_question_not_both_adr_and_drift(self):
        out = self.design()
        out["questions"][0]["drift_id"] = "ADR-002/C-001:src/x.ts"
        self.assertInvalid(out)

    def test_fix_code_needs_work_ticket(self):
        out = copy.deepcopy(fixture("architect-drift.json"))
        del out["questions"][0]["options"][0]["work_ticket"]
        self.assertInvalid(out)

    def test_drift_outcome_drafts_no_artifacts(self):
        out = copy.deepcopy(fixture("architect-drift.json"))
        out["artifacts"] = [self.adr(self.design())]
        self.assertInvalid(out)

    def test_design_outcome_needs_artifacts(self):
        out = self.design()
        out["artifacts"] = []
        self.assertInvalid(out)

    def test_bootstrap_drafts_one_component_or_interface(self):
        out = self.design()
        out["trigger"]["kind"] = "arch_bootstrap"
        self.assertInvalid(out)
        out["artifacts"] = [a for a in out["artifacts"] if a["type"] == "component"]
        check_schema(out, self.schema)

    def test_unknown_artifact_type(self):
        out = self.design()
        out["artifacts"].append({"type": "overview", "text": "x"})
        self.assertInvalid(out)


class UpkeepMutationTest(unittest.TestCase):
    schema = load_json(AGENTS["arch-upkeep"]["schema"])

    def nightly(self):
        return copy.deepcopy(fixture("arch-upkeep-nightly.json"))

    def assertInvalid(self, out):
        with self.assertRaises(HarnessError) as ctx:
            check_schema(out, self.schema)
        self.assertEqual(ctx.exception.reason, "schema_invalid")

    def test_overview_only_on_batch_run(self):
        out = self.nightly()
        out["run"]["overview_batch"] = False
        self.assertInvalid(out)

    def test_empty_patch_rejected(self):
        out = self.nightly()
        out["component_patches"][0]["code_paths_added"] = []
        out["component_patches"][0]["code_paths_removed"] = []
        self.assertInvalid(out)

    def test_patch_needs_evidence(self):
        out = self.nightly()
        out["component_patches"][0]["evidence_refs"] = []
        self.assertInvalid(out)

    def test_overview_section_capped(self):
        out = self.nightly()
        out["overview_sections"][0]["text"] = "x" * 2001
        self.assertInvalid(out)


class AgentPackTest(unittest.TestCase):
    def test_agents_build_read_only(self):
        for name, spec in AGENTS.items():
            with self.subTest(name):
                prompt, tools = build_prompt(spec["agent"], PLUGINS)
                self.assertEqual(tools, ["Glob", "Grep", "Read"])
                self.assertFalse(prompt.startswith("---"))
                for skill in spec["skills"]:
                    self.assertIn(f"# Preloaded skill `{skill}`", prompt)
                self.assertLess(prompt.index("strategy-shared`"), prompt.index("architecture-model`"))
                # The on-demand reference is never preloaded (S-ARCH-048).
                self.assertNotIn("# Preloaded skill `staff-engineering:architecture-reference`", prompt)

    def test_front_matter_skills_match(self):
        for name, spec in AGENTS.items():
            with self.subTest(name):
                front, _ = split_front_matter(spec["agent"])
                self.assertEqual(front_matter_list(front, "skills"), spec["skills"])
                self.assertEqual(front_matter_list(front, "tools"), ["Read", "Glob", "Grep"])

    def test_prepare_agent_cli(self):
        with tempfile.TemporaryDirectory() as d:
            self._prepare_all(d)

    def _prepare_all(self, d):
        for name, spec in AGENTS.items():
            with self.subTest(name):
                prompt, schema = os.path.join(d, f"{name}.md"), os.path.join(d, f"{name}.json")
                res = run_cli("prepare_agent.py", "--agent", spec["agent"], "--plugins-root", PLUGINS,
                              "--schema", spec["schema"], "--out-prompt", prompt, "--out-schema", schema)
                self.assertEqual(res.returncode, 0, res.stderr)
                self.assertIn("tools: Glob,Grep,Read", res.stdout)
                with open(schema, encoding="utf-8") as fh:
                    self.assertNotIn("maxContains", fh.read())

    def test_pack_within_context_budget(self):
        for name in AGENTS:
            with self.subTest(name):
                self.assertLess(pack_chars(name), PACK_CAP_CHARS)

    def test_cited_arch_ids_exist_in_role_doc(self):
        with open(ROLE_DOC, encoding="utf-8") as fh:
            defined = set(re.findall(r"\*\*(S-ARCH-\d{3})\*\*", fh.read()))
        files = [spec["agent"] for spec in AGENTS.values()] + [
            skill_path(f"staff-engineering:{n}")
            for n in ("architecture-model", "architecture-design", "architecture-reference")]
        files += [spec["schema"] for spec in AGENTS.values()]
        for path in files:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            # Expand ranges and short forms like "S-ARCH-011 to -014" and "-018, -042".
            cited = set(re.findall(r"S-ARCH-(\d{3})", text))
            cited |= set(re.findall(r"(?:,|to|and) -(\d{3})\b", text))
            with self.subTest(os.path.basename(os.path.dirname(path)) + "/" + os.path.basename(path)):
                self.assertEqual(sorted(f"S-ARCH-{n}" for n in cited if f"S-ARCH-{n}" not in defined), [])


if __name__ == "__main__":
    unittest.main()
