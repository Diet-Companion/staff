"""The Developer's PR contract check (S-DEV-010), on temporary git repos with the real
diet-companion code map (fixtures/developer/code-map-diet-companion.yml) as the base's .staff/code.yml."""
import base64
import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from helpers import FIXTURES, STAFF, run_cli

from dev_contract_check import MARKER, run_check, summary, tokens

SCHEMAS = os.path.join(STAFF, "plugins", "staff-engineering", "schemas")
MAP_SCHEMA = os.path.join(SCHEMAS, "code-map.schema.json")
PR_SCHEMA = os.path.join(SCHEMAS, "developer-output.schema.json")
GIT = ["git", "-c", "user.email=t@e", "-c", "user.name=t", "-c", "commit.gpgsign=false"]
REPO = "Diet-Companion/diet-companion"
BRANCH = "agent/developer/7"

with open(os.path.join(FIXTURES, "developer", "code-map-diet-companion.yml"), encoding="utf-8") as fh:
    CODE_MAP_YML = fh.read()

REQ_001 = """---
id: REQ-001
status: ready
type: functional
quality: {none: no quality target}
acceptance_criteria:
  - id: REQ-001/AC-001
  - id: REQ-001/AC-002
  - id: REQ-001/AC-003
    status: retired
---
# Log a meal
"""
REQ_002 = REQ_001.replace("REQ-001", "REQ-002").replace("status: ready", "status: draft")
REQ_003 = REQ_001.replace("REQ-001", "REQ-003").replace("quality: {none: no quality target}", "quality: [REQ-009]")
IF_001 = """---
id: IF-001
versions:
  - {version: 1.0.0, status: approved}
  - {version: 1.1.0, status: proposed}
---
"""
BASE = {
    ".staff/code.yml": CODE_MAP_YML,
    "requirements/meals/REQ-001.md": REQ_001,
    "requirements/meals/REQ-002.md": REQ_002,
    "requirements/meals/REQ-003.md": REQ_003,
    "architecture/system/interfaces/IF-001/IF-001.md": IF_001,
    "backend/src/meals.ts": "export const addMeal = (m) => m;\n",
    "package-lock.json": "{}\n",
}
TEST_PATH = "backend/src/meals.test.ts"
CITING_TEST = ("import { expect, it } from 'vitest';\n// cites: REQ-001/AC-001, R-001\n"
               "it('adds a meal', () => {\n  expect(1).toBe(1);\n});\n")
BLOCK = {
    "kind": "feature", "ticket": f"{REPO}#7",
    "implements_acs": [{"ac": "REQ-001/AC-001", "part": "full"}],
    "implements": ["IF-001@1.0.0"], "fixes": None, "constraints": [], "untested_acs": [],
    "not_unit_observable": None, "characterization": [], "dependencies": [], "flags": [],
}


def body(block=None, summary_text="Adds the meal route.", blocks=1):
    marker = ""
    if block is not None:
        enc = base64.b64encode(json.dumps(block).encode()).decode()
        marker = "\n".join([f"<!-- staff-pr-block:v1 {enc} -->"] * blocks)
    return (f"Developer change for #7 (stage 2, S-GEN-052). Ticket kind: implement (feature) · Area: system\n\n"
            f"#### Decide first\n\n> {summary_text}\n\nSources: REQ-001\n\n{marker}\n")


class ContractCase(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.repo, True)
        subprocess.run(["git", "init", "-q", "-b", "main", self.repo], check=True)
        self.base = self.commit(BASE)

    def git(self, *args):
        return subprocess.run([*GIT, "-C", self.repo, *args], check=True, capture_output=True,
                              text=True).stdout.strip()

    def commit(self, files):
        for rel, text in files.items():
            path = os.path.join(self.repo, rel)
            if text is None:
                os.remove(path)
                continue
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        self.git("add", "-A")
        self.git("commit", "-qm", "change", "--allow-empty")
        return self.git("rev-parse", "HEAD")

    def check(self, files=None, block=BLOCK, text=None, head_ref=BRANCH):
        head = self.commit({TEST_PATH: CITING_TEST} if files is None else files)
        return run_check(self.repo, self.base, head, head_ref, REPO, text if text is not None else body(block),
                         MAP_SCHEMA, PR_SCHEMA)

    def failures(self, result, check):
        return [f["text"] for f in result["failures"] if f["check"] == check]

    def block(self, **changes):
        b = copy.deepcopy(BLOCK)
        b.update(changes)
        return b


class PassTest(ContractCase):
    def test_cited_feature_passes(self):
        result = self.check()
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["cited"], ["REQ-001/AC-001"])
        self.assertEqual(result["lines_changed"], 5)

    def test_untested_ac_with_a_reason_passes(self):
        result = self.check(block=self.block(
            implements_acs=[{"ac": "REQ-001/AC-001", "part": "full"}, {"ac": "REQ-001/AC-002", "part": "partial"}],
            untested_acs=[{"ac": "REQ-001/AC-002", "reason": "other-layer"}]))
        self.assertTrue(result["passed"], result["failures"])


class SummaryTest(ContractCase):
    def test_missing_block_fails(self):
        self.assertEqual(self.failures(self.check(block=None), "summary"), ["the body holds no PR block"])

    def test_two_blocks_fail(self):
        result = self.check(text=body(BLOCK, blocks=2))
        self.assertEqual(self.failures(result, "summary"), ["the body holds more than one PR block"])

    def test_body_without_decision_summary_fails(self):
        enc = base64.b64encode(json.dumps(BLOCK).encode()).decode()
        result = self.check(text=f"Some change.\n\n<!-- staff-pr-block:v1 {enc} -->\n")
        self.assertIn("the body doesn't open with the decision summary (#### Decide first)",
                      self.failures(result, "summary"))

    def test_prose_over_2000_characters_fails_the_schema(self):
        block = self.block(flags=[{"flag_id": "guard-line:x", "reason": "x" * 2001}])
        [text] = self.failures(self.check(block=block), "summary")
        self.assertIn("/flags/0/reason (maxLength)", text)


class TicketAndSizeTest(ContractCase):
    def test_ticket_other_than_the_branch_fails(self):
        result = self.check(block=self.block(ticket=f"{REPO}#8"))
        self.assertEqual(self.failures(result, "ticket"), [f"the block's ticket is {REPO}#8, the branch names {REPO}#7"])

    def test_over_1000_lines_fails(self):
        big = "".join(f"export const v{i} = {i};\n" for i in range(996))
        result = self.check({TEST_PATH: CITING_TEST, "backend/src/big.ts": big})
        self.assertEqual(result["lines_changed"], 1001)
        self.assertEqual(len(self.failures(result, "size")), 1)

    def test_1000_lines_pass(self):
        big = "".join(f"export const v{i} = {i};\n" for i in range(995))
        result = self.check({TEST_PATH: CITING_TEST, "backend/src/big.ts": big})
        self.assertTrue(result["passed"], result["failures"])

    def test_generated_lines_are_not_counted(self):
        lock = "".join(f'"p{i}": 1,\n' for i in range(1500))
        result = self.check({TEST_PATH: CITING_TEST, "package-lock.json": lock})
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["lines_changed"], 5)


class DeclaredTest(ContractCase):
    def test_retired_unknown_and_unready_acs_fail(self):
        acs = [{"ac": a, "part": "partial"} for a in ("REQ-001/AC-003", "REQ-002/AC-001", "REQ-404/AC-001")]
        result = self.check(block=self.block(implements_acs=acs,
                                             untested_acs=[{"ac": a["ac"], "reason": "other-layer"} for a in acs]))
        self.assertEqual(self.failures(result, "declared"), [
            "REQ-001/AC-003 is retired or doesn't exist",
            "REQ-002/AC-001: REQ-002 is draft, not ready (S-BA-019)",
            "REQ-404/AC-001: REQ-404 doesn't exist on the base",
        ])

    def test_quality_target_without_accepted_qas_fails(self):
        result = self.check({TEST_PATH: CITING_TEST.replace("REQ-001/AC-001", "REQ-003/AC-001")},
                            block=self.block(implements_acs=[{"ac": "REQ-003/AC-001", "part": "full"}]))
        self.assertEqual(self.failures(result, "declared"),
                         ["REQ-003/AC-001: REQ-009 has no accepted QAS, so the design is pending (S-ARCH-015)"])

    def test_unapproved_interface_version_fails(self):
        result = self.check(block=self.block(implements=["IF-001@1.1.0"]))
        self.assertEqual(self.failures(result, "declared"),
                         ["IF-001@1.1.0 isn't an approved or deprecated interface version (S-ARCH-011)"])

    def test_refactor_declaring_an_ac_fails(self):
        # The schema holds this rule; the check's own copy guards a schema that loses it.
        result = self.check(block=self.block(kind="refactor"))
        self.assertEqual(self.failures(result, "summary"),
                         ["the PR block fails the schema at /implements_acs (maxItems)"])


class TestedTest(ContractCase):
    def test_citation_tokens(self):
        self.assertEqual(tokens("// cites: REQ-010/AC-012, R-012"), {"REQ-010/AC-012", "R-012"})
        self.assertEqual(tokens('it("cites: REQ-010/AC-012 a halfway total rounds up", () => {'), {"REQ-010/AC-012"})
        self.assertEqual(tokens('it("cites: REQ-010/AC-013, REQ-015/AC-010 meal totals", () => {'),
                         {"REQ-010/AC-013", "REQ-015/AC-010"})
        self.assertEqual(tokens('it("cites: REQ-010/AC-028")'), {"REQ-010/AC-028"})
        # The list ends at the first piece with more than an ID: later commas are prose.
        self.assertEqual(tokens('it("cites: REQ-010/AC-019 2000 is green, REQ-010/AC-020 too")'), {"REQ-010/AC-019"})
        self.assertEqual(tokens("cites:\n"), set())

    def test_declared_ac_without_a_citing_test_fails(self):
        # The #154 first draft: ACs declared, only a refactor behind them.
        acs = [{"ac": "REQ-001/AC-001", "part": "full"}, {"ac": "REQ-001/AC-002", "part": "full"}]
        result = self.check({"backend/src/meals.ts": "export const addMeal = (m) => ({ ...m });\n"},
                            block=self.block(implements_acs=acs))
        self.assertEqual(self.failures(result, "tested"), [
            "REQ-001/AC-001 is declared, but no test at the head cites it and untested_acs doesn't list it",
            "REQ-001/AC-002 is declared, but no test at the head cites it and untested_acs doesn't list it",
        ])

    def test_citation_from_an_earlier_pr_counts(self):
        self.base = self.commit({TEST_PATH: CITING_TEST})
        result = self.check({"backend/src/meals.ts": "export const addMeal = (m) => ({ ...m });\n"})
        self.assertTrue(result["passed"], result["failures"])

    def test_citation_outside_a_test_file_does_not_count(self):
        result = self.check({"backend/src/meals.ts": "// cites: REQ-001/AC-001\nexport const addMeal = (m) => m;\n"})
        self.assertEqual(len(self.failures(result, "tested")), 1)

    def test_untested_entry_that_is_not_declared_fails(self):
        result = self.check(block=self.block(untested_acs=[{"ac": "REQ-001/AC-002", "reason": "other-layer"}]))
        self.assertEqual(self.failures(result, "tested"), ["REQ-001/AC-002 is listed in untested_acs but not declared"])


class KindTest(ContractCase):
    FIX = {"kind": "fix", "implements_acs": [], "fixes": {"ticket": f"{REPO}#7", "target": "R-001"}}

    def test_fix_with_a_citing_test_passes(self):
        self.assertTrue(self.check(block=self.block(**self.FIX))["passed"])

    def test_fix_without_a_citing_test_fails(self):
        self.base = self.commit({TEST_PATH: CITING_TEST})
        result = self.check({"backend/src/meals.ts": "export const addMeal = (m) => ({ ...m });\n"},
                            block=self.block(**self.FIX))
        self.assertEqual(len(self.failures(result, "fix")), 1)

    def test_drift_cannot_pass_yet(self):
        result = self.check(block=self.block(kind="drift", implements_acs=[],
                                             fixes={"ticket": f"{REPO}#7", "target": "ADR-001/C-001"}))
        self.assertEqual(len(self.failures(result, "drift")), 1)


class CliTest(ContractCase):
    def test_cli_exit_codes_and_summary(self):
        head = self.commit({"backend/src/meals.ts": "export const addMeal = (m) => ({ ...m });\n"})
        out = os.path.join(self.repo, "..", os.path.basename(self.repo) + "-out")
        os.makedirs(out)
        self.addCleanup(shutil.rmtree, out, True)
        with open(os.path.join(out, "body.md"), "w", encoding="utf-8") as fh:
            fh.write(body(BLOCK))
        args = ["--repo", self.repo, "--base", self.base, "--head", head, "--head-ref", BRANCH,
                "--repo-name", REPO, "--body", os.path.join(out, "body.md"),
                "--out", os.path.join(out, "r.json"), "--summary", os.path.join(out, "s.md")]
        r = run_cli("dev_contract_check.py", *args)
        self.assertEqual(r.returncode, 1, r.stderr)
        with open(os.path.join(out, "s.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertTrue(text.startswith(MARKER))
        self.assertIn("**tested**", text)
        r = run_cli("dev_contract_check.py", *args[:4], "not-a-sha", *args[6:])
        self.assertEqual(r.returncode, 2)

    def test_summary_escapes_pr_text(self):
        result = {"passed": False, "failures": [{"check": "ticket", "text": "x <b>y</b>"}], "lines_changed": 1,
                  "max_lines": 500, "declared": [], "cited": []}
        self.assertNotIn("<b>", summary(result))


if __name__ == "__main__":
    unittest.main()
