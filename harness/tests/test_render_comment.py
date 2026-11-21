import argparse
import os
import tempfile
import unittest

from helpers import fixture, load, run_cli

from render_comment import WJ, esc, render, render_failure

ARGS = argparse.Namespace(run_id="100-1", stage=1, model="claude-sonnet-5-5",
                          staff_sha="0123456789abcdef0123456789abcdef01234567",
                          run_url="https://github.com/example/shop/actions/runs/100/attempts/1")
UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"


class RenderTest(unittest.TestCase):
    def assertGolden(self, files, prefix):
        for name, text in files:
            path = fixture(f"golden/{prefix}-{name}")
            if UPDATE:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(text)
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(text, fh.read(), path)

    def test_question_batch_golden(self):
        self.assertGolden(render(load("output-questions.json"), ARGS), "questions")

    def test_drafts_golden(self):
        files = render(load("output-drafts.json"), ARGS)
        self.assertEqual([n for n, _ in files], ["00-main.md", "01-REQ-001.md", "02-REQ-002.md", "03-REQ-003.md"])
        self.assertGolden(files, "drafts")

    def test_interview_guide_golden(self):
        self.assertGolden(render(load("output-guide.json"), ARGS), "guide")

    def test_deterministic(self):
        data = load("output-drafts.json")
        self.assertEqual(render(data, ARGS), render(data, ARGS))

    def test_question_batch_contents(self):
        main = render(load("output-questions.json"), ARGS)[0][1]
        self.assertIn("**Q\\-001**".replace("\\-", "-"), main)
        self.assertIn("(**blocking** · blocks REQ-001", main)
        self.assertIn("- a) Until it ships. **(recommended)**", main)
        self.assertIn("Recommended: **a**", main)
        self.assertTrue(main.index("Decisions for you") < main.index("#### Questions"))
        self.assertIn("Answer in a comment as `Q-001: b` (or free text); then comment `/analyst` to continue.", main)
        self.assertIn("Staff-Run-Id: 100-1", main)
        self.assertIn("Model: claude-sonnet-5-5", main)
        self.assertIn("Staff commit: 0123456789abcdef0123456789abcdef01234567", main)

    def test_model_text_is_neutralised(self):
        text = esc("Ping @someone, see ![x](https://e.invalid/p.png) <img src=x> #12 `code` | t |")
        self.assertIn("@" + WJ + "someone", text)
        self.assertIn("#" + WJ + "12", text)
        for raw in (r"!\[", r"\]\(", "<img", "`code`", r"\| t \|"):  # none left unescaped
            self.assertNotRegex(text, r"(?<!\\)" + raw)
        self.assertEqual(esc("- not a list"), "\\- not a list")
        self.assertEqual(esc("1. not a list"), "1\\. not a list")
        self.assertEqual(esc("two\nlines"), "two lines")

    def test_failure_notice_is_fixed_text(self):
        (name, text), = render_failure("schema_invalid", ARGS)
        self.assertEqual(name, "00-failure.md")
        self.assertTrue(text.startswith(
            "Analyst run 100-1 failed: `schema_invalid`. See [the run's logs]"
            "(https://github.com/example/shop/actions/runs/100/attempts/1).\n"))
        unknown = render_failure("anything the model said", ARGS)[0][1]
        self.assertIn("failed: `read_job_failed`.", unknown)
        self.assertNotIn("model said", unknown)

    def test_cli_rejects_odd_footer_values(self):
        out = tempfile.mkdtemp()
        proc = run_cli("render_comment.py", "render", "--in", fixture("output-questions.json"), "--out-dir", out,
                       "--run-id", "100-1", "--model", "x y", "--staff-sha", ARGS.staff_sha)
        self.assertEqual(proc.returncode, 2)
        proc = run_cli("render_comment.py", "failure", "--reason", "cost_cap", "--out-dir", out,
                       "--run-id", "100-1", "--model", "claude-sonnet-5-5", "--staff-sha", ARGS.staff_sha)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(os.listdir(out), ["00-failure.md"])


if __name__ == "__main__":
    unittest.main()
