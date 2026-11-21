import json
import os
import tempfile
import unittest

from helpers import load, run_cli

from redact_check import scan, scan_text

# Secret-like values are assembled at run time, so no file in the repo holds one.
RANDOMISH = "q8Zr2LmX7vKp4TnB9wYc3HdF6jQs1GaE"
AT = "@"
HITS = {
    "anthropic_key": "key sk-" + "ant-" + "api03-" + RANDOMISH,
    "github_token": "token gh" + "p_" + RANDOMISH + "abcd",
    "github_pat": "github_" + "pat_" + "11ABCDEFG0" + RANDOMISH,
    "pem_header": "-----BEGIN " + "RSA PRIVATE KEY-----",
    "aws_access_key": "AKIA" + "IOSFODNN7EXAMPLE",
    "jwt": "eyJ" + "hbGciOiJIUzI1NiJ9" + ".eyJ" + "zdWIiOiIxMjM0NTY3ODkwIn0" + ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
    "email": "write to jane.doe" + AT + "example.org please",
    "high_entropy": "value " + RANDOMISH,
}
MISSES = [
    "Answer from 12345+test-operator" + AT + "users.noreply.github.com counts",
    "commit 3d3c42e5aac5ba805825da76410c181273ba90b1",
    "https://github.com/example/shop/actions/runs/19234567890/job/54123456789",
    "https://github.com/user-attachments/assets/1bd90f6b-ff71-4645-b906-cfd6a5049c87",
    "REQ-001/AC-002/TC-003 cites knowledge/rules/orders/R-012.md",
    "The customer may cancel an order until it ships.",
    "ghp_short",
]


class RedactTest(unittest.TestCase):
    def test_each_pattern_hits(self):
        for name, text in HITS.items():
            with self.subTest(name):
                self.assertIn(name, scan_text(text))

    def test_misses(self):
        for text in MISSES:
            with self.subTest(text[:30]):
                self.assertEqual(scan_text(text), [])

    def test_valid_fixtures_are_clean(self):
        for name in ("output-questions.json", "output-drafts.json", "output-guide.json"):
            self.assertEqual(scan(load(name)), [])

    def test_reports_path_and_pattern(self):
        out = load("output-drafts.json")
        out["requirements"][1]["acceptance_criteria"][0]["then"].append(HITS["github_token"])
        self.assertIn(("/requirements/1/acceptance_criteria/0/then/1", "github_token"), scan(out))
        self.assertEqual({path for path, _ in scan(out)}, {"/requirements/1/acceptance_criteria/0/then/1"})

    def test_cli_fails_closed_and_never_prints_the_value(self):
        out = load("output-questions.json")
        out["decision_summary"] = HITS["anthropic_key"] + " and " + HITS["email"]
        path = os.path.join(tempfile.mkdtemp(), "validated.json")
        with open(path, "w") as fh:
            json.dump(out, fh)
        proc = run_cli("redact_check.py", "--in", path)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("/decision_summary (anthropic_key)", proc.stdout)
        self.assertIn("/decision_summary (email)", proc.stdout)
        self.assertIn("redaction_hit", proc.stderr)
        for secret in (RANDOMISH, "jane.doe"):
            self.assertNotIn(secret, proc.stdout + proc.stderr)

    def test_cli_input_reason(self):
        path = os.path.join(tempfile.mkdtemp(), "input.json")
        with open(path, "w") as fh:
            json.dump({"untrusted": {"body": HITS["aws_access_key"]}}, fh)
        proc = run_cli("redact_check.py", "--in", path, "--reason", "input_redaction")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("input_redaction", proc.stderr)


if __name__ == "__main__":
    unittest.main()
