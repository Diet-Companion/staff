import os
import tempfile
import unittest

from helpers import fixture, run_cli

from common import HarnessError
from contract import check_product, effective_stage, load_areas, load_operators, load_stages


def tmp_file(text):
    fd, path = tempfile.mkstemp(suffix=".yml")
    with os.fdopen(fd, "w") as fh:
        fh.write(text)
    return path


class ContractTest(unittest.TestCase):
    def test_operators_are_lowercased_handles(self):
        self.assertEqual(load_operators(fixture("operators.yml")), {"test-operator", "second-op"})

    def test_operators_fail_closed_on_odd_shapes(self):
        for text in ("operators: []\n", "version: 1\n", "operators:\n  - email: x\n"):
            with self.assertRaises(HarnessError):
                load_operators(tmp_file(text))

    def test_areas_inline_and_block_paths(self):
        self.assertEqual(load_areas(fixture("areas.yml")), ["orders", "billing"])

    def test_areas_fail_closed(self):
        for text in ("areas:\n", "areas:\n  Bad_Key:\n    paths: []\n", "areas:\n  a:\n  a:\n"):
            with self.assertRaises(HarnessError):
                load_areas(tmp_file(text))

    def test_product_contract(self):
        check_product(fixture("product.yml"), "anthropic-api")
        with self.assertRaises(HarnessError):
            check_product(fixture("product.yml"), "other-endpoint")
        with self.assertRaises(HarnessError):  # residency missing (S-DATA-001)
            check_product(tmp_file("model_endpoint: anthropic-api\n"), "anthropic-api")
        with self.assertRaises(HarnessError):
            check_product(tmp_file("residency:\n  regions: []\nmodel_endpoint: anthropic-api\n"), "anthropic-api")
        check_product(tmp_file("residency:\n  regions:\n    - eu\nmodel_endpoint: anthropic-api\n"), "anthropic-api")

    STAGES = "# human-only\nstages:\n  developer:\n    system: 2   # promoted 2026-11-25\n  analyst:\n    product: 1\n"

    def test_stages_read_per_agent_and_area(self):
        self.assertEqual(load_stages(tmp_file(self.STAGES)), {"developer": {"system": 2}, "analyst": {"product": 1}})
        self.assertEqual(load_stages("/nonexistent/stages.yml"), {})
        self.assertEqual(load_stages(tmp_file("stages:\n")), {})

    def test_stages_fail_closed(self):
        for text in ("stages:\n  developer:\n    system: 5\n", "stages:\n  developer:\n    system: two\n",
                     "stages:\n  developer:\n    system: 2\n    system: 1\n", "stages:\n  Dev_X:\n    system: 2\n"):
            with self.assertRaises(HarnessError):
                load_stages(tmp_file(text))

    def test_effective_stage_is_the_lowest(self):
        path = tmp_file(self.STAGES)
        self.assertEqual(effective_stage(path, "developer", "system"), 2)
        self.assertEqual(effective_stage(path, "developer", "system", "1"), 1)  # a demotion ceiling
        self.assertEqual(effective_stage(path, "developer", "system", "3"), 2)  # a ceiling never raises
        self.assertEqual(effective_stage(path, "developer", "system", "junk"), 1)  # fails closed
        self.assertEqual(effective_stage(path, "developer", "other-area"), 1)
        self.assertEqual(effective_stage(path, "architect", "system"), 1)
        self.assertEqual(effective_stage("/nonexistent/stages.yml", "developer", "system"), 1)

    def test_stage_cli(self):
        out = run_cli("contract.py", "stage", "--stages-yml", tmp_file(self.STAGES), "--agent", "developer",
                      "--area", "system", "--ceiling", "")
        self.assertEqual((out.returncode, out.stdout.strip()), (0, "2"))

    def test_is_operator_cli(self):
        ok = run_cli("contract.py", "is-operator", "--operators", fixture("operators.yml"), "--login", "Test-Operator")
        self.assertEqual(ok.returncode, 0)
        no = run_cli("contract.py", "is-operator", "--operators", fixture("operators.yml"), "--login", "someone-else")
        self.assertEqual(no.returncode, 2)
        self.assertIn("not_operator", no.stderr)


if __name__ == "__main__":
    unittest.main()
