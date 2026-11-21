import os
import tempfile
import unittest

from helpers import fixture, run_cli

from common import HarnessError
from contract import check_product, load_areas, load_operators


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

    def test_is_operator_cli(self):
        ok = run_cli("contract.py", "is-operator", "--operators", fixture("operators.yml"), "--login", "Test-Operator")
        self.assertEqual(ok.returncode, 0)
        no = run_cli("contract.py", "is-operator", "--operators", fixture("operators.yml"), "--login", "someone-else")
        self.assertEqual(no.returncode, 2)
        self.assertIn("not_operator", no.stderr)


if __name__ == "__main__":
    unittest.main()
