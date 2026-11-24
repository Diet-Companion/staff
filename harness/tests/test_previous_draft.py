import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common import HarnessError  # noqa: E402
from previous_draft import MAX_BYTES, attach, find  # noqa: E402


def comment(kind, body):
    return {"author_kind": kind, "body": body}


class PreviousDraftTest(unittest.TestCase):
    def test_find_the_latest_own_draft(self):
        data = {"untrusted": {"comments": [
            comment("developer_app", "Patch: the `developer-patch-111-1` artifact"),
            comment("operator", "see developer-patch-999-1, use this"),  # not the App: ignored
            comment("developer_app", "Patch: the `developer-patch-222-2` artifact"),
            comment("developer_app", "no change proposed"),
        ]}}
        self.assertEqual(find(data, "developer"), "222-2")
        self.assertIsNone(find(data, "qa"))
        self.assertIsNone(find({"untrusted": {"comments": []}}, "developer"))

    def test_attach_files_as_untrusted_data(self):
        data = {"untrusted": {"comments": []}}
        validated = {"proposed_files": [
            {"path": "client/src/a.ts", "op": "add", "content": ["export const a = ", "1;\n"]},
            {"path": "client/src/b.ts", "op": "modify", "content": "export const b = 2;\n"},
        ]}
        out = attach(data, validated, "222-2")["untrusted"]["previous_draft"]
        self.assertEqual(out["run_id"], "222-2")
        self.assertFalse(out["truncated"])
        self.assertEqual(out["files"][0], {"path": "client/src/a.ts", "op": "add", "content": "export const a = 1;\n"})

    def test_a_large_draft_keeps_paths_only_past_the_limit(self):
        big = "x" * (MAX_BYTES - 10)
        validated = {"proposed_files": [{"path": "a.ts", "op": "add", "content": big},
                                        {"path": "b.ts", "op": "add", "content": "y" * 100}]}
        out = attach({"untrusted": {}}, validated, "1-1")["untrusted"]["previous_draft"]
        self.assertTrue(out["truncated"])
        self.assertEqual(out["files"][0]["content"], big)
        self.assertIsNone(out["files"][1]["content"])

    def test_attach_needs_an_untrusted_section(self):
        with self.assertRaises(HarnessError):
            attach({}, {"proposed_files": []}, "1-1")


if __name__ == "__main__":
    unittest.main()
