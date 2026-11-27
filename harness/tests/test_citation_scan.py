"""The citation scan (S-DEV-016), on temporary git repos with the real diet-companion code map as the base's
.staff/code.yml and a one-layer QA test map."""
import os
import shutil
import subprocess
import tempfile
import unittest

from helpers import FIXTURES, run_cli

from citation_scan import MARKER, TEST_MAP_SCHEMA, run_scan, summary
from dev_contract_check import SCHEMAS

MAP_SCHEMA = os.path.join(SCHEMAS, "code-map.schema.json")
GIT = ["git", "-c", "user.email=t@e", "-c", "user.name=t", "-c", "commit.gpgsign=false"]

with open(os.path.join(FIXTURES, "developer", "code-map-diet-companion.yml"), encoding="utf-8") as fh:
    CODE_MAP_YML = fh.read()

with open(os.path.join(FIXTURES, "qa", "tests.yml"), encoding="utf-8") as fh:
    TEST_MAP_YML = fh.read()

REQ_001 = """---
id: REQ-001
status: ready
acceptance_criteria:
  - id: REQ-001/AC-001
  - id: REQ-001/AC-002
    status: retired
---
"""
BASE = {
    ".staff/code.yml": CODE_MAP_YML,
    ".staff/tests.yml": TEST_MAP_YML,
    "requirements/meals/REQ-001.md": REQ_001,
    "requirements/meals/REQ-002.md": REQ_001.replace("REQ-001", "REQ-002").replace("status: ready", "status: retired"),
    "knowledge/rules/R-001.md": "---\nid: R-001\nstatus: active\n---\n",
    "knowledge/rules/R-002.md": "---\nid: R-002\nstatus: retired\n---\n",
    "architecture/system/interfaces/IF-001/IF-001.md":
        "---\nid: IF-001\nversions:\n  - {version: 1.0.0, status: approved}\n  - {version: 0.9.0, status: retired}\n---\n",
    "architecture/system/adr/ADR-001.md":
        "---\nid: ADR-001\nstatus: accepted\noptions:\n  - key: a\n    constraints: [{id: ADR-001/C-001}]\n---\n",
    "architecture/system/adr/ADR-002.md":
        "---\nid: ADR-002\nstatus: superseded\noptions:\n  - key: a\n    constraints: [{id: ADR-002/C-001}]\n---\n",
    "architecture/system/qas/QAS-001.md": "---\nid: QAS-001\nstatus: accepted\n---\n",
    "backend/src/meals.test.ts": "// cites: REQ-001/AC-002\nit('old', () => {});\n",  # stale, not added here
}


def test_file(*cites):
    return "".join(f"// cites: {c}\nit('t{i}', () => {{}});\n" for i, c in enumerate(cites))


class CitationScanTest(unittest.TestCase):
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
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        self.git("add", "-A")
        self.git("commit", "-qm", "change", "--allow-empty")
        return self.git("rev-parse", "HEAD")

    def scan(self, files):
        return run_scan(self.repo, self.base, self.commit(files), MAP_SCHEMA, TEST_MAP_SCHEMA)

    def test_live_citations_pass(self):
        live = ["REQ-001/AC-001", "REQ-001/AC-001/TC-001", "R-001", "IF-001@1.0.0#getDayLog", "ADR-001/C-001",
                "QAS-001"]
        result = self.scan({"backend/src/new.test.ts": test_file(*live),
                            "client/src/View.test.tsx": "it('cites: REQ-001/AC-001 shows the day', () => {});\n"})
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual((result["files"], result["citations"]), (2, 7))

    def test_missing_and_retired_ids_fail(self):
        cases = {"REQ-009/AC-001": "missing", "REQ-001/AC-009": "missing", "REQ-001/AC-002": "retired",
                 "REQ-002/AC-001": "retired", "R-009": "missing", "R-002": "retired", "IF-002@1.0.0": "missing",
                 "IF-001@2.0.0": "missing", "IF-001@0.9.0": "retired", "ADR-009/C-001": "missing",
                 "ADR-001/C-009": "missing", "ADR-002/C-001": "retired", "QAS-009": "missing"}
        for cid, check in cases.items():
            with self.subTest(cid=cid):
                result = self.scan({"backend/src/new.test.ts": test_file(cid)})
                self.assertFalse(result["passed"])
                self.assertEqual([(f["check"], f["id"]) for f in result["failures"]], [(check, cid)])
                self.git("reset", "-q", "--hard", self.base)

    def test_other_forms_are_notes_and_only_added_test_lines_count(self):
        result = self.scan({
            "backend/src/new.test.ts": test_file("A-043", "ADR-013", "INT-002#T7/T8"),
            "tests/api/days/close.api.test.ts": test_file("REQ-001/AC-002"),  # a QA layer path counts
            "backend/src/meals.ts": "// cites: REQ-009/AC-001\n",  # not a test file
        })
        self.assertEqual([f["id"] for f in result["failures"]], ["REQ-001/AC-002"])
        self.assertEqual([n["id"] for n in result["notes"]], ["A-043", "ADR-013", "INT-002#T7/T8"])
        text = summary(result)
        self.assertTrue(text.startswith(MARKER))
        self.assertIn("Not checked (not an S-DEV-016 form): `A-043`", text)
        # The stale citation already on the base isn't the PR's: an unrelated edit to that file passes.
        self.git("reset", "-q", "--hard", self.base)
        result = self.scan({"backend/src/meals.test.ts": BASE["backend/src/meals.test.ts"] + "it('more', () => {});\n"})
        self.assertTrue(result["passed"], result["failures"])

    def test_truth_comes_from_the_base(self):
        # A PR can't revive the AC its own test cites.
        result = self.scan({"requirements/meals/REQ-001.md": REQ_001.replace("    status: retired\n", ""),
                            "backend/src/new.test.ts": test_file("REQ-001/AC-002")})
        self.assertEqual([f["check"] for f in result["failures"]], ["retired"])

    def test_cli_exit_codes(self):
        head = self.commit({"backend/src/new.test.ts": test_file("R-009")})
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out, True)
        args = ["--repo", self.repo, "--base", self.base, "--head", head, "--out", os.path.join(out, "r.json"),
                "--summary", os.path.join(out, "s.md")]
        r = run_cli("citation_scan.py", *args)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("Citation scan: 1 failure(s): missing", r.stdout)
        r = run_cli("citation_scan.py", *args[:4], "--head", "not-a-sha", *args[6:])
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
