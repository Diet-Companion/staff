import os
import tempfile
import unittest

from helpers import SCHEMA, STAFF, load

from common import HarnessError
from prepare_agent import build_prompt, cli_schema

AGENT = os.path.join(STAFF, "plugins", "staff-product", "agents", "analyst.md")
PLUGINS = os.path.join(STAFF, "plugins")


class PrepareAgentTest(unittest.TestCase):
    def test_prompt_has_agent_body_skills_and_contract(self):
        prompt, tools = build_prompt(AGENT, PLUGINS)
        self.assertEqual(tools, ["Glob", "Grep", "Read"])
        self.assertFalse(prompt.startswith("---"))
        for marker in ("You are the **Analyst**", "# Preloaded skill `staff-core:strategy-shared`",
                       "# Preloaded skill `staff-product:requirements`",
                       "# Preloaded skill `staff-product:elicitation`", "# Harness contract"):
            self.assertIn(marker, prompt)
        self.assertLess(prompt.index("strategy-shared`"), prompt.index("requirements`"))

    def test_write_tools_fail_closed(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "bad.md")
        with open(path, "w") as fh:
            fh.write("---\nname: bad\ntools: Read, Bash\n---\nbody\n")
        with self.assertRaises(HarnessError):
            build_prompt(path, PLUGINS)

    def test_cli_schema_drops_unsupported_keywords_only(self):
        full = load(os.path.relpath(SCHEMA, os.path.join(STAFF, "harness", "tests", "fixtures")))
        cli = cli_schema(full)
        text = repr(cli)
        for kw in ("$schema", "minContains", "maxContains"):
            self.assertNotIn(f"'{kw}'", text)
        self.assertEqual(cli["required"], full["required"])
        self.assertEqual(cli["$defs"]["text"], full["$defs"]["text"])


if __name__ == "__main__":
    unittest.main()
