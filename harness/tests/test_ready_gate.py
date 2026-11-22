"""The ready-gate check (S-BA-017) and the lifecycle check (S-BA-009) on small synthetic repos."""
import copy
import json
import os
import tempfile
import unittest

import yaml

from helpers import STAFF, run_cli

from ready_gate import Gate, description, fingerprint, load_tree, reviewer_blocks, summary

SCHEMA = os.path.join(STAFF, "plugins", "staff-product", "schemas", "analyst-output.schema.json")
REPO = "Diet-Companion/diet-companion"
BOT = "diet-companion-reviewer[bot]"
SHA = "a" * 40
OK_COMMENT = f"{REPO}#6 comment 100"
COMMENTS = {  # comment id -> comment, as gh api returns it
    "100": {"user": {"login": "giokur", "type": "User"}, "issue_url": f"https://api.github.com/repos/{REPO}/issues/6"},
    "200": {"user": {"login": "stranger", "type": "User"}, "issue_url": f"https://api.github.com/repos/{REPO}/issues/6"},
    "300": {"user": {"login": "giokur", "type": "User"}, "issue_url": f"https://api.github.com/repos/{REPO}/issues/40"},
}


def requirement(**over):
    req = {
        "id": "REQ-003", "type": "story", "title": "Add a product from a label photo", "status": "draft",
        "area": "catalog", "parent": "REQ-001",
        "intent": {"actor": "Owner", "need": "Photograph a label.", "business_value": "Speed.", "cites": ["INT-001#T1/T2"]},
        "scope": {"in": [{"text": "Photo upload.", "cites": ["INT-001#T1/T2"]}], "out": []},
        "acceptance_criteria": [
            {"id": "REQ-003/AC-001", "key": {"entity": "label", "target_id": None, "attribute": "add"},
             "given": ["A label photo"], "when": "Owner uploads it", "then": ["The product is saved"],
             "cites": ["INT-001#T1/T2"], "kind": "positive"},
            {"id": "REQ-003/AC-002", "key": {"entity": "product", "target_id": None, "attribute": "missing_fat"},
             "given": ["A photo without fat"], "when": "Owner uploads it", "then": ["The app asks for fat"],
             "cites": ["INT-001#T1/T2", "R-002"], "kind": "negative"},
        ],
        "rules": ["R-002"], "changes": [],
        "quality": {"none": "Deferred."},
        "permissions": [{"role": "Owner", "may": ["Upload label photos"], "may_not": []}],
        "sources": ["INT-001#T1/T2"], "assumptions": [], "questions": [], "priority": "high",
        "tracker": [f"{REPO}#6"],
        "revision": [{"date": "2026-11-22", "change": "Initial draft", "reason": "INT-001",
                      "source_ref": "requirements/catalog/sources/INT-001.md"}],
    }
    req.update(over)
    return req


RULE = {"id": "R-002", "statement": "A product needs a name, shop, calories, protein and fat.",
        "type": "validation", "entity": "product", "condition": "a product is saved",
        "behavior": "rejected unless the required fields are set", "status": "active"}


def write_repo(root, reqs, rules=(RULE,)):
    def put(rel, text):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    for req in reqs:
        put(f"requirements/{req['area']}/{req['id']}.md",
            "---\n" + yaml.safe_dump(req, sort_keys=False, allow_unicode=True) + "---\n\n# body\n")
    for rule in rules:
        put(f"knowledge/rules/catalog/{rule['id']}.md", "---\n" + yaml.safe_dump(rule, sort_keys=False) + "---\n")
    put("requirements/catalog/sources/INT-001.md", "---\nid: INT-001\n---\n\n### T1 [interviewer]\n\nQ\n\n### T2 [human]\n\nA\n")
    epic = requirement(id="REQ-001", type="epic", title="Catalog", acceptance_criteria=[], rules=[], parent=None)
    epic.pop("parent")
    if not any(r["id"] == "REQ-001" for r in reqs):
        put("requirements/catalog/REQ-001.md", "---\n" + yaml.safe_dump(epic, sort_keys=False) + "---\n")
    return root


def review_comment(findings=(), sha=SHA, target=f"{REPO}#40", login=BOT, kind="Bot"):
    block = {"schema": "staff-review:v1", "artifact_type": "requirements", "target": target,
             "reviewed_sha": sha, "verdict": "not_ready", "findings": list(findings), "questions": []}
    body = "### Reviewer\n\n<!-- staff-review:v1\n" + json.dumps(block) + "\n-->\n"
    return {"id": 9, "user": {"login": login, "type": kind}, "body": body}


class GateCase(unittest.TestCase):
    def gate(self, base_reqs, head_reqs, comments=(), commits=None, reviewed=None, head_rules=(RULE,)):
        """reviewed: the requirement as it was at SHA (defaults to the head version)."""
        d = tempfile.mkdtemp()
        base = load_tree(write_repo(os.path.join(d, "base"), base_reqs))
        head = load_tree(write_repo(os.path.join(d, "head"), head_reqs, head_rules))
        at_sha = {f"requirements/{r['area']}/{r['id']}.md": r for r in (reviewed or head_reqs)}

        def git(_dir, sha, path):
            r = at_sha.get(path) if sha == SHA else None
            return None if r is None else "---\n" + yaml.safe_dump(r, sort_keys=False) + "---\n"
        with open(SCHEMA, encoding="utf-8") as fh:
            schema = json.load(fh)
        return Gate(repo=REPO, pr=40, base=base, head=head, head_dir="unused", schema=schema,
                    operators={"giokur"}, reviewer_login=BOT, comments=list(comments),
                    commits=commits if commits is not None else [{"sha": "b" * 40, "author": {"login": "giokur"}}],
                    lookup_comment=COMMENTS.get, git=git).run()

    def problems(self, result, item):
        return result["gated"][0]["items"][str(item)]["problems"]


class LifecycleTest(GateCase):
    def test_draft_edit_is_not_a_gate(self):
        res = self.gate([requirement()], [requirement(title="New title")])
        self.assertTrue(res["ok"])
        self.assertEqual(res["gated"], [])
        self.assertEqual(description(res), "No requirement made ready; lifecycle OK")

    def test_bad_transitions(self):
        ready = requirement(status="ready")
        cases = {
            "edit a ready requirement": ([ready], [requirement(status="ready", title="x")]),
            "ready back to draft": ([ready], [requirement(status="draft")]),
            "delete": ([requirement()], []),
            "change a retired one": ([requirement(status="retired", retired={"reason": "dup", "replaced_by": None})],
                                     [requirement(status="retired", title="x",
                                                  retired={"reason": "dup", "replaced_by": None})]),
            "ready to changed without affected ACs": ([ready], [requirement(status="changed")]),
            "new requirement as changed": ([], [requirement(status="changed")]),
        }
        for name, (base, head) in cases.items():
            with self.subTest(name):
                res = self.gate(base, head)
                self.assertFalse(res["ok"])
                self.assertTrue(res["lifecycle_problems"])

    def test_ready_to_changed_with_affected_acs(self):
        rev = requirement()["revision"] + [{"date": "2026-11-23", "change": "AC-002 reworded", "reason": "x",
                                            "source_ref": f"{REPO}#40", "affected_acs": ["REQ-003/AC-002"]}]
        res = self.gate([requirement(status="ready")], [requirement(status="changed", revision=rev)])
        self.assertEqual(res["lifecycle_problems"], [])


class ReadyGateTest(GateCase):
    def test_passes_with_a_matching_review(self):
        res = self.gate([requirement()], [requirement(status="ready")], [review_comment()])
        self.assertTrue(res["ok"], summary(res))
        self.assertEqual(description(res), "Ready gate passes: REQ-003")

    def test_item1_schema_and_refs(self):
        bad = requirement(status="ready")
        bad["acceptance_criteria"][0]["cites"] = ["INT-001#T9/T10", "REQ-077", "R-099", "A-001", "who knows"]
        probs = self.problems(self.gate([requirement()], [bad], [review_comment()]), 1)
        for text in ("no turn T9", "no such requirement", "no such rule", "not a question or assumption",
                     "unrecognised ref"):
            self.assertTrue(any(text in p for p in probs), (text, probs))
        broken = requirement(status="ready")
        del broken["intent"]
        res = self.gate([requirement()], [broken], [review_comment()])
        self.assertTrue(self.problems(res, 1)[0].startswith("schema:"))
        self.assertEqual(self.problems(res, 2), ["not checked: schema invalid"])

    def test_item1_rules_must_be_merged_and_active(self):
        new_rule = dict(RULE, id="R-020")
        head = requirement(status="ready", rules=["R-002", "R-020"])
        probs = self.problems(self.gate([requirement()], [head], [review_comment()],
                                        head_rules=(RULE, new_rule)), 1)
        self.assertTrue(any("R-020, which is not a merged active rule" in p for p in probs), probs)

    def test_item1_owner_fields(self):
        change = {"rule": "R-002", "kind": "modify", "proposed_statement": "x", "accepted_by": f"{REPO}#6 comment 200"}
        head = requirement(status="ready", changes=[change])
        probs = self.problems(self.gate([requirement()], [head], [review_comment()]), 1)
        self.assertTrue(any("accepted_by is not an operator comment" in p for p in probs), probs)
        change["accepted_by"] = f"{REPO}#7 comment 100"  # the right author, but on another issue
        probs = self.problems(self.gate([requirement()], [head], [review_comment()]), 1)
        self.assertTrue(any("accepted_by is not an operator comment" in p for p in probs), probs)
        agent = [{"sha": "c" * 40, "author": {"login": "diet-companion-analyst[bot]"}}]
        probs = self.problems(self.gate([requirement()], [requirement(status="ready")], [review_comment()],
                                        commits=agent), 1)
        self.assertTrue(any("commits not by an operator" in p for p in probs), probs)

    def test_item2_blocking(self):
        q = {"id": "Q-001", "key": {"entity": "e", "target_id": None, "attribute": "a"}, "status": "open", "blocking": True}
        a = {"id": "A-001", "key": {"entity": "e", "target_id": None, "attribute": "a"}, "text": "t",
             "status": "open", "blocking": False}
        res = self.gate([requirement()], [requirement(status="ready", questions=[q], assumptions=[a])], [review_comment()])
        self.assertEqual(self.problems(res, 2), ["question Q-001 is open and blocking"])

    def test_item3_priority(self):
        res = self.gate([requirement()], [requirement(status="ready", priority=None)], [review_comment()])
        self.assertEqual(len(self.problems(res, 3)), 1)

    def test_item4_rule_condition_needs_negative_ac(self):
        head = requirement(status="ready")
        head["acceptance_criteria"][1]["cites"] = ["INT-001#T1/T2"]
        res = self.gate([requirement()], [head], [review_comment()])
        self.assertIn("R-002 has a condition", self.problems(res, 4)[0])
        head["acceptance_criteria"][1]["status"] = "retired"
        head["acceptance_criteria"][1]["cites"] = ["R-002"]
        res = self.gate([requirement()], [head], [review_comment()])
        self.assertIn("R-002 has a condition", self.problems(res, 4)[0])

    def test_item5_review_must_match_the_head(self):
        res = self.gate([requirement()], [requirement(status="ready")])
        self.assertEqual(self.problems(res, 5), ["no reviewer result"])
        older = requirement(status="ready")
        older["acceptance_criteria"][0]["then"] = ["Something else"]
        res = self.gate([requirement()], [requirement(status="ready")], [review_comment()], reviewed=[older])
        self.assertIn("comment /review", self.problems(res, 5)[0])
        # Only the reviewer App's blocks, for this PR, count.
        for comment in (review_comment(login="giokur", kind="User"), review_comment(target=f"{REPO}#41")):
            res = self.gate([requirement()], [requirement(status="ready")], [comment])
            self.assertEqual(self.problems(res, 5), ["no reviewer result"])

    def test_item5_status_and_prose_changes_keep_the_review(self):
        reviewed = requirement(status="draft", title="Old title")
        res = self.gate([requirement()], [requirement(status="ready", priority="high")], [review_comment()],
                        reviewed=[reviewed])
        self.assertTrue(res["ok"], summary(res))

    def test_item5_contradicts_needs_a_disposition(self):
        fid = "RC-4|REQ-003/AC-001|R-002"
        finding = {"id": fid, "checklist_id": "RC-4", "severity": "blocker", "classification": "contradicts"}
        other = {"id": "RC-4|REQ-004/AC-001|R-002", "checklist_id": "RC-4", "severity": "blocker",
                 "classification": "contradicts"}
        comments = [review_comment([finding, other])]
        res = self.gate([requirement()], [requirement(status="ready")], comments)
        self.assertEqual(self.problems(res, 5), [f"finding {fid} (contradicts) has no review_dispositions entry"])
        # Copied from the rendered comment, with its invisible word joiner.
        copied = fid.replace("REQ", "⁠REQ")
        for disp, ref, ok in (("rejected", OK_COMMENT, True), ("accepted", f"{REPO}#6 comment 200", False),
                              ("declared", "R-002", False)):
            head = requirement(status="ready", review_dispositions=[{"finding_id": copied, "disposition": disp, "ref": ref}])
            with self.subTest(disp):
                self.assertEqual(not self.problems(self.gate([requirement()], [head], comments), 5), ok)
        change = {"rule": "R-002", "kind": "modify", "proposed_statement": "x", "accepted_by": OK_COMMENT}
        head = requirement(status="ready", changes=[change],
                           review_dispositions=[{"finding_id": fid, "disposition": "declared", "ref": "R-002"}])
        res = self.gate([requirement()], [head], comments)
        self.assertEqual(self.problems(res, 5), [])

    def test_item5_waiver(self):
        rev = requirement()["revision"] + [{"date": "2026-11-23", "change": "Ready gate", "reason": "Operator",
                                            "source_ref": f"{REPO}#40"}]
        waiver = {"ref": f"{REPO}#40 comment 300", "revision": f"{REPO}#40"}
        res = self.gate([requirement()], [requirement(status="ready", review_waiver=waiver, revision=rev)])
        self.assertEqual(self.problems(res, 5), [])
        old = {"ref": f"{REPO}#40 comment 300", "revision": f"{REPO}#12"}
        res = self.gate([requirement()], [requirement(status="ready", review_waiver=old, revision=rev)])
        self.assertTrue(any("not this gate" in p for p in self.problems(res, 5)))
        res = self.gate([requirement()], [requirement(status="ready", review_waiver=waiver)])
        self.assertTrue(any("adds no revision entry" in p for p in self.problems(res, 5)))


class HelpersTest(unittest.TestCase):
    def test_fingerprint_ignores_status_and_prose(self):
        a, b = requirement(), requirement(status="ready", title="x", priority="low")
        self.assertEqual(fingerprint(a), fingerprint(b))
        b["rules"] = []
        self.assertNotEqual(fingerprint(a), fingerprint(b))

    def test_reviewer_blocks_skip_bad_json_and_short_sha(self):
        good = review_comment()
        bad = dict(review_comment(), body="<!-- staff-review:v1\n{not json}\n-->")
        short = review_comment(sha="abc")
        self.assertEqual(len(reviewer_blocks([good, bad, short], BOT, f"{REPO}#40")), 1)

    def test_description_length(self):
        res = {"ok": False, "lifecycle_problems": [], "reviewer_results": [],
               "gated": [{"id": f"REQ-{i:03d}", "items": {"5": {"ok": False}}} for i in range(40)]}
        self.assertLessEqual(len(description(res)), 140)

    def test_cli(self):
        d = tempfile.mkdtemp()
        write_repo(os.path.join(d, "base"), [requirement()])
        write_repo(os.path.join(d, "head"), [requirement(status="ready", priority=None)])
        files = {"comments": [], "commits": [{"sha": "b" * 40, "author": {"login": "giokur"}}], "lookup": COMMENTS}
        for name, data in files.items():
            with open(os.path.join(d, f"{name}.json"), "w") as fh:
                json.dump(data, fh)
        ops = os.path.join(d, "operators.yml")
        with open(ops, "w") as fh:
            fh.write("version: 1\noperators:\n  - github: giokur\n")
        res = run_cli("ready_gate.py", "--repo", REPO, "--pr", "40", "--base-dir", os.path.join(d, "base"),
                      "--head-dir", os.path.join(d, "head"), "--schema", SCHEMA, "--operators", ops,
                      "--reviewer-login", BOT, "--out", os.path.join(d, "result.json"),
                      "--summary", os.path.join(d, "summary.md"), "--description", os.path.join(d, "desc.txt"),
                      "--comments-file", os.path.join(d, "comments.json"),
                      "--commits-file", os.path.join(d, "commits.json"),
                      "--comment-lookup-file", os.path.join(d, "lookup.json"))
        self.assertEqual(res.returncode, 1, res.stderr)
        with open(os.path.join(d, "desc.txt")) as fh:
            self.assertEqual(fh.read(), "Fails: REQ-003 item 3, REQ-003 item 5")
        with open(os.path.join(d, "summary.md")) as fh:
            self.assertIn("❌ 3. quality, permissions and priority", fh.read())


if __name__ == "__main__":
    unittest.main()
