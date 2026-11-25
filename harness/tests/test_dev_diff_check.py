"""The Developer's code diff check (S-DEV-018, S-DEV-028), on temporary git repos and the real
diet-companion code map (fixtures/developer/code-map-diet-companion.yml)."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from helpers import FIXTURES, STAFF, run_cli

from code_map import load_code_map
from common import HarnessError
from contract import load_operators
from dev_diff_check import MARKER, flag_id, run_check, summary

MAP_SCHEMA = os.path.join(STAFF, "plugins", "staff-engineering", "schemas", "code-map.schema.json")
MAP_PATH = os.path.join(FIXTURES, "developer", "code-map-diet-companion.yml")
OPS_PATH = os.path.join(FIXTURES, "operators.yml")
CODE_MAP = load_code_map(MAP_PATH, MAP_SCHEMA)
OPERATORS = load_operators(OPS_PATH)
GIT = ["git", "-c", "user.email=t@e", "-c", "user.name=t", "-c", "commit.gpgsign=false"]

TEST_FILE = "backend/src/meals/meals.test.ts"
ROUTES = "backend/src/meals/routes.ts"
SESSION = "backend/src/auth/session.ts"
TESTS = """import { describe, expect, it } from 'vitest';
import { addMeal, totals } from './meals';

describe('meals', () => {
  // cites: REQ-001/AC-001
  it('adds a meal', () => {
    const m = addMeal({ kcal: 100 });
    expect(m.kcal).toBe(100);
  });

  it('sums totals', () => {
    expect(totals([{ kcal: 1 }, { kcal: 2 }])).toBe(3);
    expect(totals([])).toBe(0);
  });
});
"""
ROUTES_TS = """import { requireOwner } from '../auth/owner';
import { parseMeal } from './schema';

export async function postMeal(req, reply) {
  requireOwner(req);
  const meal = parseMeal(req.body);
  if (!meal) return reply.code(400).send();
  // eslint-disable-next-line no-console
  console.log(meal.id);
  return save(meal);
}

export async function deleteMeal(req, reply) {
  if (!req.user) return reply.code(403).send();
  return remove(req.params.id);
}
"""
BACKEND_PKG = {"name": "backend", "scripts": {"test": "vitest"}, "dependencies": {"zod": "^3.23.0"}}
BASE = {
    TEST_FILE: TESTS,
    ROUTES: ROUTES_TS,
    "backend/src/meals/meals.ts": "export const addMeal = (m) => m;\n",
    SESSION: "export const TTL = 3600;\n",
    "backend/package.json": json.dumps(BACKEND_PKG, indent=2) + "\n",
    "package.json": json.dumps({"name": "diet-companion", "workspaces": ["backend"]}, indent=2) + "\n",
    "package-lock.json": json.dumps({"lockfileVersion": 3, "packages": {}}, indent=2) + "\n",
    "eslint.config.js": "export default [];\n",
    "README.md": "# Diet Companion\n",
}


class DiffCheckCase(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.repo, True)
        subprocess.run(["git", "init", "-q", "-b", "main", self.repo], check=True)
        self.base = self.commit(BASE)

    def git(self, *args):
        return subprocess.run([*GIT, "-C", self.repo, *args], check=True, capture_output=True,
                              text=True).stdout.strip()

    def commit(self, files, moves=None):
        """Apply moves {old: new}, then files {path: text, or None to delete}; commit; return the SHA."""
        for old, new in (moves or {}).items():
            os.makedirs(os.path.dirname(os.path.join(self.repo, new)) or self.repo, exist_ok=True)
            os.rename(os.path.join(self.repo, old), os.path.join(self.repo, new))
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

    def check(self, files=None, moves=None, comments=(), pr=None, kind=None, head=None):
        head = head or self.commit(files or {}, moves)
        return run_check(self.repo, self.base, head, CODE_MAP, OPERATORS, list(comments), pr=pr, kind=kind)

    def flags(self, result, check=None):
        return [f for f in result["flags"] if check is None or f["check"] == check]

    def edit(self, path, old, new):
        text = BASE[path]
        self.assertIn(old, text)
        return {path: text.replace(old, new)}


class TestsTest(DiffCheckCase):
    def test_clean_feature_passes(self):
        result = self.check({
            "backend/src/meals/plan.ts": "export const plan = (days) => days.map((d) => d.kcal);\n",
            "backend/src/meals/plan.test.ts": ("import { expect, it } from 'vitest';\n// cites: REQ-002/AC-001\n"
                                               "it('plans days', () => {\n  expect(plan([])).toEqual([]);\n});\n"),
            ROUTES: ROUTES_TS + "\nexport const ping = () => 'ok';\n",
        })
        self.assertEqual(result, {"passed": True, "blocked": [], "flags": [], "needs_label": []})

    def test_moved_test_file_is_not_flagged(self):
        result = self.check(moves={TEST_FILE: "backend/src/nutrition/meals.test.ts",
                                   ROUTES: "backend/src/nutrition/routes.ts"})
        self.assertEqual(result["flags"], [])
        self.assertTrue(result["passed"])

    def test_removed_test_is_flagged(self):
        text = TESTS.replace("""
  it('sums totals', () => {
    expect(totals([{ kcal: 1 }, { kcal: 2 }])).toBe(3);
    expect(totals([])).toBe(0);
  });
""", "")
        result = self.check({TEST_FILE: text})
        [f] = result["flags"]
        self.assertEqual((f["check"], f["element"], f["file"]), ("test_removed", f"{TEST_FILE}::sums totals", TEST_FILE))
        self.assertFalse(result["passed"])

    def test_removed_test_after_move_keeps_the_new_path(self):
        new = "backend/src/nutrition/meals.test.ts"
        text = TESTS.replace("  it('sums totals'", "  it('sums all totals'")
        result = self.check({new: text}, moves={TEST_FILE: new})
        self.assertEqual([(f["check"], f["element"]) for f in result["flags"]], [("test_removed", f"{new}::sums totals")])

    def test_skip_and_expected_failure_are_flagged(self):
        for marker, check in (("it.skip(", "test_skipped"), ("xit(", "test_skipped"),
                              ("it.fails(", "test_expected_failure")):
            with self.subTest(marker=marker):
                self.setUp()
                result = self.check(self.edit(TEST_FILE, "it('sums totals'", f"{marker}'sums totals'"))
                self.assertEqual([(f["check"], f["element"]) for f in result["flags"]],
                                 [(check, f"{TEST_FILE}::sums totals")])

    def test_uncited_assertion_change_is_flagged_and_cited_is_not(self):
        text = TESTS.replace("toBe(100)", "toBe(101)").replace("toBe(3)", "toBe(4)")
        result = self.check({TEST_FILE: text})
        self.assertEqual([(f["check"], f["element"]) for f in result["flags"]],
                         [("assertion_changed", f"{TEST_FILE}::sums totals")])

    def test_cited_assertion_removed_is_flagged(self):
        result = self.check(self.edit(TEST_FILE, "    expect(m.kcal).toBe(100);\n", ""))
        self.assertEqual([(f["check"], f["element"]) for f in result["flags"]],
                         [("assertion_shrunk", f"{TEST_FILE}::adds a meal")])

    def test_changed_citation_changes_the_key(self):
        result = self.check(self.edit(TEST_FILE, "cites: REQ-001/AC-001", "cites: REQ-001/AC-009"))
        self.assertEqual([(f["check"], f["element"]) for f in result["flags"]],
                         [("test_removed", f"{TEST_FILE}::adds a meal")])

    def test_added_assertions_and_tests_are_not_flagged(self):
        text = TESTS.replace("    expect(totals([])).toBe(0);\n",
                             "    expect(totals([])).toBe(0);\n    expect(totals([{ kcal: 5 }])).toBe(5);\n")
        result = self.check({TEST_FILE: text + "\nit('is new', () => {\n  expect(1).toBe(1);\n});\n"})
        self.assertEqual(result["flags"], [])

    def test_parametrised_file_falls_back_to_net_assertion_count(self):
        path = "backend/src/meals/double.test.ts"
        text = ("import { expect, it } from 'vitest';\n"
                "it.each([[1], [2]])('doubles %i', (n) => {\n  expect(n * 2).toBe(n + n);\n  expect(n).toBeGreaterThan(0);\n});\n")
        self.base = self.commit({path: text})
        self.assertEqual(self.check({path: text.replace("  expect(n * 2).toBe(n + n);\n", "  expect(n * 2).toBe(n + n + 0);\n")})["flags"], [])
        result = self.check({path: text.replace("  expect(n).toBeGreaterThan(0);\n", "")})
        self.assertEqual([(f["check"], f["element"]) for f in result["flags"]],
                         [("assertion_net_decrease", f"{path}#2->1")])

    def test_refactor_that_changes_an_assertion_is_blocked(self):
        files = self.edit(TEST_FILE, "toBe(3)", "toBe(4)")
        head = self.commit(files)
        result = self.check(head=head, kind="refactor")
        self.assertEqual([(b["check"], b["file"]) for b in result["blocked"]], [("refactor_assertion", TEST_FILE)])
        self.assertEqual(self.check(head=head, pr={"kind": "upkeep"})["blocked"][0]["check"], "refactor_assertion")
        self.assertEqual(self.check(head=head, kind="feature")["blocked"], [])


class GuardAndPathTest(DiffCheckCase):
    def test_guard_line_removed_changed_or_moved_is_flagged(self):
        cases = {
            "removed": (("  requireOwner(req);\n", ""), "authorization"),
            "moved": (("  requireOwner(req);\n  const meal = parseMeal(req.body);\n",
                       "  const meal = parseMeal(req.body);\n  requireOwner(req);\n"), None),
            "changed": (("reply.code(403)", "reply.code(404)"), "permission_deny"),
        }
        for name, ((old, new), cls) in cases.items():
            with self.subTest(name):
                self.setUp()
                result = self.check(self.edit(ROUTES, old, new))
                guards = self.flags(result, "guard_line")
                self.assertTrue(guards)
                self.assertTrue(all(f["file"] == ROUTES for f in guards))
                if cls:
                    self.assertEqual([f["element"].split("|")[1] for f in guards], [cls])

    def test_gitattributes_cannot_hide_a_guard_line(self):
        files = self.edit(ROUTES, "  requireOwner(req);\n", "")
        files[".gitattributes"] = "*.ts -diff\n"
        self.assertEqual([f["check"] for f in self.check(files)["flags"]], ["guard_line"])

    def test_binary_protected_change_is_flagged(self):
        key = "backend/src/auth/key.der"
        with open(os.path.join(self.repo, key), "wb") as fh:
            fh.write(b"\x00\x01old")
        self.base = self.commit({})
        with open(os.path.join(self.repo, key), "wb") as fh:
            fh.write(b"\x00\x01new")
        [f] = self.check()["flags"]
        self.assertEqual(f["check"], "protected")
        self.assertIn("@binary:", f["element"])

    def test_guard_line_in_a_pure_move_is_not_flagged(self):
        self.assertEqual(self.check(moves={ROUTES: "backend/src/nutrition/routes.ts"})["flags"], [])

    def test_lint_suppression_added_is_flagged_and_removed_is_not(self):
        result = self.check(self.edit(ROUTES, "  return save(meal);\n",
                                      "  // @ts-expect-error legacy shape\n  return save(meal);\n"))
        [f] = result["flags"]
        self.assertEqual((f["check"], f["file"]), ("lint_suppression", ROUTES))
        self.assertIn("|lint_suppression|", f["element"])
        self.setUp()
        self.assertEqual(self.check(self.edit(ROUTES, "  // eslint-disable-next-line no-console\n", ""))["flags"], [])

    def test_protected_change_is_flagged_and_delete_is_blocked(self):
        result = self.check({SESSION: "export const TTL = 7200;\n"})
        [f] = result["flags"]
        self.assertEqual((f["check"], f["file"]), ("protected", SESSION))
        self.assertTrue(f["element"].startswith(SESSION + "@"))
        self.assertEqual(result["blocked"], [])
        result = self.check({SESSION: None})
        self.assertEqual([(b["check"], b["file"]) for b in result["blocked"]], [("protected_deleted", SESSION)])
        self.assertFalse(result["passed"])

    def test_protected_move_out_of_the_class_is_blocked(self):
        result = self.check(moves={SESSION: "backend/src/meals/session.ts"})
        self.assertEqual([b["check"] for b in result["blocked"]], ["protected_deleted"])

    def test_verification_config_change_is_flagged_and_delete_is_blocked(self):
        result = self.check({"eslint.config.js": "export default [{ rules: {} }];\n"})
        self.assertEqual([(f["check"], f["file"]) for f in result["flags"]], [("verification_config", "eslint.config.js")])
        result = self.check({"eslint.config.js": None})
        self.assertEqual([b["check"] for b in result["blocked"]], ["verification_config_deleted"])

    def test_paths_outside_the_code_map_are_skipped(self):
        self.assertEqual(self.check({"README.md": "# Diet Companion\n\nrequireOwner(x)\n"}),
                         {"passed": True, "blocked": [], "flags": [], "needs_label": []})


class DependencyTest(DiffCheckCase):
    def pkg(self, **deps):
        return json.dumps(dict(BACKEND_PKG, dependencies=deps), indent=2) + "\n"

    def test_dependency_bump_is_flagged_with_label(self):
        result = self.check({"backend/package.json": self.pkg(zod="^3.24.1", pino="9.0.0"),
                             "package-lock.json": json.dumps({"lockfileVersion": 3, "packages": {"zod": 1}}) + "\n"})
        self.assertEqual(sorted((f["check"], f["element"]) for f in result["flags"]),
                         [("dependency", "pino@9.0.0"), ("dependency", "zod@^3.24.1")])
        self.assertEqual(result["needs_label"], ["dev:dependency"])
        self.assertEqual(result["blocked"], [])

    def test_lockfile_change_needs_a_manifest_change(self):
        lock = {"package-lock.json": json.dumps({"lockfileVersion": 3, "packages": {"x": 1}}) + "\n"}
        result = self.check(lock)
        self.assertEqual([(b["check"], b["file"]) for b in result["blocked"]],
                         [("generated_hand_edit", "package-lock.json")])
        self.setUp()
        scripts = json.dumps(dict(BACKEND_PKG, scripts={"test": "vitest run"}), indent=2) + "\n"
        result = self.check(dict(lock, **{"backend/package.json": scripts}))
        self.assertEqual(result["blocked"], [])
        self.assertEqual(result["flags"], [])  # a script edit changes no dependency
        self.assertEqual(result["needs_label"], ["dev:dependency"])


class DeclarationTest(DiffCheckCase):
    PR = {"kind": "fix", "fixes": {"ticket": "#12", "target": "REQ-001/AC-002"},
          "not_unit_observable": {"target": "REQ-001/AC-002", "test_gap": "needs a browser"}}

    def test_not_unit_observable_is_flagged_by_target(self):
        result = self.check({"backend/src/meals/meals.ts": "export const addMeal = (m) => ({ ...m });\n"}, pr=self.PR)
        [f] = result["flags"]
        self.assertEqual((f["check"], f["file"], f["element"]), ("not_unit_observable", None, "REQ-001/AC-002"))

    def test_no_declaration_no_flag(self):
        self.assertEqual(self.check({}, pr=dict(self.PR, not_unit_observable=None))["flags"], [])


class SignOffTest(DiffCheckCase):
    def comment(self, body, login="test-operator", type_="User"):
        return {"user": {"login": login, "type": type_}, "body": body}

    def protected_flag(self, ttl="7200", comments=()):
        result = self.check({SESSION: f"export const TTL = {ttl};\n"}, comments=comments)
        [f] = result["flags"]
        return result, f

    def test_flag_id_is_short_and_deterministic(self):
        _, f = self.protected_flag()
        self.assertRegex(f["id"], r"^DIFF-[0-9a-f]{12}$")
        self.assertEqual(f["id"], flag_id(f["check"], f["element"]))

    def test_operator_signoff_clears_and_others_do_not(self):
        _, f = self.protected_flag()
        cases = {
            "operator": ([self.comment(f"Judged it.\n/signoff {f['id']}")], "test-operator"),
            "operator, other case": ([self.comment(f"/signoff {f['id']}", login="SECOND-op")], "SECOND-op"),
            "bot with an operator's login": ([self.comment(f"/signoff {f['id']}", type_="Bot")], None),
            "non-operator": ([self.comment(f"/signoff {f['id']}", login="someone")], None),
            "operator quoting the ID": ([self.comment(f"> /signoff {f['id']}\nwhy?")], None),
            "operator, other ID": ([self.comment("/signoff DIFF-000000000000")], None),
        }
        for name, (comments, who) in cases.items():
            with self.subTest(name):
                self.setUp()
                result, g = self.protected_flag(comments=comments)
                self.assertEqual(g["id"], f["id"])
                self.assertEqual(g["signed_off_by"], who)
                self.assertEqual(result["passed"], who is not None)

    def test_signoff_is_void_when_the_element_changes(self):
        first, f = self.protected_flag("7200")
        signed = [self.comment(f"/signoff {f['id']}")]
        head = self.commit({SESSION: "export const TTL = 9999;\n"})  # a new push
        result = self.check(head=head, comments=signed)
        [g] = result["flags"]
        self.assertNotEqual(g["id"], f["id"])
        self.assertIsNone(g["signed_off_by"])
        self.assertFalse(result["passed"])

    def test_flag_id_holds_across_a_rebase(self):
        _, f = self.protected_flag()
        old_base = self.base
        self.git("checkout", "-q", "-b", "main2", old_base)
        self.base = self.commit({"README.md": "# Diet Companion, moved on\n"})
        result, g = self.protected_flag()
        self.assertEqual(g["id"], f["id"])
        # An unrebased PR is compared with its merge base, so main's own changes aren't its.
        self.assertEqual(self.check(head=self.git("rev-parse", "main"))["flags"], [f | {"signed_off_by": None}])


class CliTest(DiffCheckCase):
    def run_check_cli(self, head, comments, *extra):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        paths = {k: os.path.join(d, k) for k in ("comments.json", "out.json", "summary.md")}
        with open(paths["comments.json"], "w") as fh:
            json.dump(comments, fh)
        proc = run_cli("dev_diff_check.py", "--repo", self.repo, "--base", self.base, "--head", head,
                       "--code-map", MAP_PATH, "--operators", OPS_PATH, "--comments", paths["comments.json"],
                       "--out", paths["out.json"], "--summary", paths["summary.md"], *extra)
        out = summary_text = None
        if os.path.exists(paths["out.json"]):
            with open(paths["out.json"]) as fh:
                out = json.load(fh)
            with open(paths["summary.md"]) as fh:
                summary_text = fh.read()
        return proc, out, summary_text

    def test_cli_result_summary_and_exit_codes(self):
        head = self.commit({SESSION: "export const TTL = 7200;\n"})
        proc, out, text = self.run_check_cli(head, [])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(set(out), {"passed", "blocked", "flags", "needs_label"})
        [f] = out["flags"]
        self.assertEqual(set(f), {"id", "check", "file", "element", "reason", "signed_off_by"})
        self.assertTrue(text.startswith(MARKER))
        self.assertIn(f"`{f['id']}`", text)
        self.assertIn("/signoff DIFF-", text)
        signed = [{"user": {"login": "test-operator", "type": "User"}, "body": f"/signoff {f['id']}"}]
        proc, out, _ = self.run_check_cli(head, [signed])  # a page array, as gh api --slurp gives
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(out["passed"])

    def test_cli_reads_the_pr_block_and_fails_closed(self):
        head = self.commit(self.edit(TEST_FILE, "toBe(3)", "toBe(4)"))
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        block = os.path.join(d, "validated.json")
        with open(block, "w") as fh:
            json.dump({"pr": {"kind": "refactor", "fixes": None, "not_unit_observable": None}}, fh)
        proc, out, text = self.run_check_cli(head, [], "--pr-block", block)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(out["blocked"][0]["check"], "refactor_assertion")
        self.assertIn("#### Blocked", text)
        proc, out, _ = self.run_check_cli("0" * 40, [])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("diff_failed", proc.stderr)
        self.assertIsNone(out)

    def test_missing_area_fails_closed(self):
        with self.assertRaises(HarnessError) as ctx:
            run_check(self.repo, self.base, self.base, CODE_MAP, OPERATORS, [], area="orders")
        self.assertEqual(ctx.exception.reason, "code_map_invalid")

    def test_summary_escapes_pr_text(self):
        result = {"passed": False, "blocked": [], "needs_label": [], "flags": [
            {"id": "DIFF-0123456789ab", "check": "dependency", "file": "a|b.json", "element": "@evil/x@<script>",
             "reason": "x", "signed_off_by": None}]}
        text = summary(result)
        self.assertNotIn("<script>", text)
        self.assertIn("a\\|b.json", text)
        self.assertTrue(re.search(r"`DIFF-0123456789ab`", text))


if __name__ == "__main__":
    unittest.main()
