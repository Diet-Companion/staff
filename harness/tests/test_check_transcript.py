import os
import re
import tempfile
import unittest

from helpers import STAFF, fixture, run_cli

from check_transcript import META_RE, SECTIONS, TURN_RE, check

PRODUCT = os.path.join(STAFF, "plugins", "staff-product")
VALID = fixture(os.path.join("transcripts", "INT-001.md"))
AT = "@"

with open(VALID, encoding="utf-8") as fh:
    VALID_TEXT = fh.read()


def write(text, rel="INT-001.md"):
    path = os.path.join(tempfile.mkdtemp(), rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def problems_for(old, new, rel="INT-001.md"):
    assert old in VALID_TEXT, old
    problems, hits = check(write(VALID_TEXT.replace(old, new, 1), rel))
    return " | ".join(problems + hits)


class CheckTranscriptTest(unittest.TestCase):
    def test_valid_fixture_is_clean(self):
        self.assertEqual(check(VALID), ([], []))

    def test_valid_under_product_path(self):
        path = write(VALID_TEXT, os.path.join("requirements", "billing", "sources", "INT-001.md"))
        self.assertEqual(check(path), ([], []))

    def test_front_matter(self):
        cases = {
            ("human_confirmed: true", "human_confirmed: false"): "human_confirmed is not true",
            ("id: INT-001", "id: INT-002"): "id does not match the file name",
            ("id: INT-001", "id: INT-1"): "id is not INT-NNN",
            ("intake: example/shop#9\n", ""): "intake missing",
            ("date: 2026-11-21", "date: 21.11.2026"): "date is not YYYY-MM-DD",
            ("intake: example/shop#9", "intake: issue 9"): "intake is not owner/repo#n",
            ("area: billing\n", "area: billing\nowner: someone\n"): "unknown front matter field owner",
        }
        for (old, new), expected in cases.items():
            with self.subTest(expected):
                self.assertIn(expected, problems_for(old, new))

    def test_area_must_match_path(self):
        rel = os.path.join("requirements", "orders", "sources", "INT-001.md")
        self.assertIn("area does not match the path", problems_for("area: billing", "area: billing", rel))

    def test_turn_markers(self):
        cases = {
            ("### T2 [human]", "### T2 [agent]"): "speaker is not human or interviewer",
            ("### T4 [human]", "### T5 [human]"): "out of sequence",
            ("### T2 [human]", "### T2 human"): "not a turn marker",
            ("topic: T-01 · kind: question\n", ""): "lacks a valid topic/kind line",
            ("topic: T-02 · kind: question", "topic: T-09 · kind: question"): "topic is not in Topics covered",
            (" · key: {entity: refund, target_id: null, attribute: approver} · value: store admin · from: T2", ""):
                "needs key, value and from",
            ("· from: T2", "· from: T1"): "cites T1, which is not an earlier human turn",
            ("### T2 [human]\n\n", "### T2 [human]\ntopic: T-01 · kind: question\n"): "human turn T2 carries",
        }
        for (old, new), expected in cases.items():
            with self.subTest(expected):
                self.assertIn(expected, problems_for(old, new))

    def test_decisions_cite_human_turns(self):
        cases = {
            ("(INT-001#T2)", "(INT-001#T1)"): "T1 is not a human turn",
            ("(INT-001#T3/T4)", "(INT-001#T2/T3)"): "is not a readback and the human turn after it",
            ("(INT-001#T2)", "(INT-002#T2)"): "cites INT-002, not this transcript",
            (" (INT-001#T2)", ""): "decision cites no turn",
        }
        for (old, new), expected in cases.items():
            with self.subTest(expected):
                self.assertIn(expected, problems_for(old, new))

    def test_open_items(self):
        old = "- T-02: payment methods out of scope; the human is checking with the provider (INT-001#T6)."
        self.assertIn("topic T-02 is not covered but not listed", problems_for(old, "- None."))
        self.assertIn("Open items: no entries", problems_for(old, ""))
        self.assertEqual(problems_for("| T-02 | out_of_scope | no | not covered |",
                                      "| T-02 | out_of_scope | no | covered |"), "")

    def test_sections_and_sources(self):
        self.assertIn("section missing: ## Open items", problems_for("## Open items", "## Open"))
        self.assertIn("the intake ref is not cited",
                      problems_for("- Interview guide: example/shop#9, guide comment", "- Interview guide"))

    def test_redaction_reuses_redact_check(self):
        report = problems_for("Yes.", "Yes, mail jane.doe" + AT + "example.org.")
        self.assertRegex(report, r"line \d+: redaction hit \(email\)")
        self.assertNotIn("jane.doe", report)

    def test_cli(self):
        proc = run_cli("check_transcript.py", VALID)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("transcript check: clean", proc.stdout)
        bad = write(VALID_TEXT.replace("human_confirmed: true", "human_confirmed: false"))
        proc = run_cli("check_transcript.py", bad)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("transcript_invalid", proc.stderr)
        leaky = write(VALID_TEXT.replace("Yes.", "Yes, mail jane.doe" + AT + "example.org."))
        proc = run_cli("check_transcript.py", leaky)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("redaction_hit", proc.stderr)
        self.assertNotIn("jane.doe", proc.stdout + proc.stderr)


class InterviewKitTest(unittest.TestCase):
    """The template, skill and agent agree with the format the check enforces."""

    def read(self, *parts):
        with open(os.path.join(PRODUCT, *parts), encoding="utf-8") as fh:
            return fh.read()

    def assert_format(self, text):
        self.assertEqual(tuple(re.findall(r"^## (.+)$", text, re.M)), SECTIONS)
        markers = re.findall(r"^### .+$", text, re.M)
        self.assertTrue(markers)
        for line in markers:
            self.assertRegex(line, TURN_RE)
        metas = re.findall(r"^topic: .+$", text, re.M)
        self.assertEqual({m.group("kind") for m in map(META_RE.match, metas)}, {"question", "readback"})

    def test_template_format(self):
        self.assert_format(self.read("templates", "INT-n.md"))

    def test_skill_format(self):
        skill = self.read("skills", "analyst-interview", "SKILL.md")
        self.assert_format(skill.split("```markdown", 1)[1].split("\n```\n", 1)[0])

    def test_agent_is_tool_less_and_carries_the_skill(self):
        agent = self.read("agents", "analyst-interview.md")
        skill = self.read("skills", "analyst-interview", "SKILL.md")
        front, body = agent.split("\n---\n", 1)
        self.assertIn("\ntools: []\n", front + "\n")
        self.assertIn(skill.split("\n---\n", 1)[1].strip(), body)


if __name__ == "__main__":
    unittest.main()
