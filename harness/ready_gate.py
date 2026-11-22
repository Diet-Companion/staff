"""The ready-gate check (S-BA-017) and the requirement lifecycle check (S-BA-009). No model.

Compares every requirements/<area>/REQ-n.md between the PR base and head checkouts.

Lifecycle, for every requirement the PR touches (S-BA-009):
  draft -> draft | ready (gate) | retired; changed -> changed | ready (gate) | retired;
  ready -> changed (with affected ACs in a new revision entry) | retired; retired never changes.
  A ready requirement edited while staying ready fails: link repair (S-BA-053) isn't
  recognised yet, so it fails too, and says so. A requirement is never deleted.

Ready gate, for each requirement the PR makes ready (status ready at head, not at base):
  1. the schema, ID, source-ref and owner-field checks pass;
  2. no blocking question or assumption is open;
  3. quality and permissions are filled in or `none` with a reason, and priority is set;
  4. every R-ID in `rules` whose rule has a `condition` is cited by a negative or boundary AC;
  5. a reviewer/requirements result exists for a commit whose ACs, `rules` and `changes`
     match the head, and every `contradicts` finding about the requirement has a
     `review_dispositions` entry; or `review_waiver` cites an operator comment and names
     this PR, which must add a revision entry with this PR as its `source_ref`.
Reviewer results come only from comments by the reviewer App, and only from their
`staff-review:v1` block (render_review.py). The human judges the semantic items.

A PR that makes nothing ready passes the gate once its lifecycle check passes.

GitHub data (comments, commits, operator comments behind refs) comes from `gh api`, or
from --comments-file, --commits-file and --comment-lookup-file in tests. The head
checkout needs full history, so the reviewed commit can be read with `git show`.
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

import yaml
from jsonschema import Draft202012Validator

from common import HarnessError, load_json, run_main, write_json
from contract import load_operators

BLOCK_RE = re.compile(r"<!-- staff-review:v1\n(\{.*?\})\n-->", re.S)
COMMENT_REF = re.compile(r"^([\w.-]+/[\w.-]+)#([0-9]+) comment ([0-9]+)$")
ISSUE_REF = re.compile(r"^[\w.-]+/[\w.-]+#[0-9]+$")
INT_REF = re.compile(r"^(INT-[0-9]{3,})(?:#T([0-9]+)(?:/T([0-9]+))?)?$")
REQ_REF = re.compile(r"^(REQ-[0-9]{3,})(?:/(AC-[0-9]{3,}))?$")
RULE_REF = re.compile(r"^R-[0-9]{3,}$")
LOCAL_REF = re.compile(r"^[AQ]-[0-9]{3,}$")
INVISIBLE = re.compile("[​-‍⁠﻿]")
NEXT = {
    "draft": {"draft", "ready", "retired"},
    "changed": {"changed", "ready", "retired"},
    "ready": {"changed", "retired"},
    "retired": set(),
}
ITEMS = {
    1: "schema, ID, source-ref and owner-field checks",
    2: "no open blocking question or assumption",
    3: "quality, permissions and priority",
    4: "rule conditions covered by negative or boundary ACs",
    5: "reviewer result for the head, with dispositions, or a waiver",
}


# ---------- loading ----------

def _plain(node):
    """YAML dates as ISO strings, so the JSON schema sees what the file says."""
    if isinstance(node, dict):
        return {k: _plain(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_plain(v) for v in node]
    if isinstance(node, (datetime.date, datetime.datetime)):
        return node.isoformat()
    return node


def front_matter(text, where):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise HarnessError("input_invalid", f"{where}: no front matter")
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        raise HarnessError("input_invalid", f"{where}: front matter is not YAML") from None
    if not isinstance(data, dict):
        raise HarnessError("input_invalid", f"{where}: front matter is not a mapping")
    return _plain(data)


def load_tree(root):
    """{'reqs': {path: front}, 'rules': {R-id: front}, 'turns': {INT-n: {k}}, 'files': set(paths)}."""
    tree = {"reqs": {}, "rules": {}, "turns": {}, "files": set()}
    for path in glob.glob(os.path.join(root, "requirements", "**", "*"), recursive=True) + \
            glob.glob(os.path.join(root, "knowledge", "**", "*"), recursive=True):
        if os.path.isfile(path):
            tree["files"].add(os.path.relpath(path, root))
    for rel in sorted(tree["files"]):
        full = os.path.join(root, rel)
        if re.fullmatch(r"requirements/[^/]+/REQ-[0-9]+\.md", rel):
            with open(full, encoding="utf-8") as fh:
                tree["reqs"][rel] = front_matter(fh.read(), rel)
        elif re.fullmatch(r"knowledge/rules/[^/]+/R-[0-9]+\.md", rel):
            with open(full, encoding="utf-8") as fh:
                rule = front_matter(fh.read(), rel)
            tree["rules"][rule.get("id", os.path.basename(rel)[:-3])] = rule
        elif re.fullmatch(r"requirements/[^/]+/sources/INT-[0-9]+\.md", rel):
            with open(full, encoding="utf-8") as fh:
                turns = {int(n) for n in re.findall(r"(?m)^### T([0-9]+)\b", fh.read())}
            tree["turns"][os.path.basename(rel)[:-3]] = turns
    return tree


def fingerprint(req):
    """What a review covers: the ACs, `rules` and `changes` (S-BA-017 item 5)."""
    part = {k: req.get(k) for k in ("acceptance_criteria", "rules", "changes")}
    return hashlib.sha256(json.dumps(part, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def git_show(repo_dir, sha, path):
    try:
        out = subprocess.run(["git", "-C", repo_dir, "show", f"{sha}:{path}"], check=True,
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout


def reviewer_blocks(comments, reviewer_login, target):
    """staff-review:v1 blocks from the reviewer App's comments on this PR, oldest first."""
    out = []
    for c in comments:
        user = c.get("user") or {}
        if user.get("type") != "Bot" or user.get("login") != reviewer_login:
            continue
        for raw in BLOCK_RE.findall(c.get("body") or ""):
            try:
                block = json.loads(raw)
            except ValueError:
                continue
            if (isinstance(block, dict) and block.get("schema") == "staff-review:v1"
                    and block.get("artifact_type") == "requirements" and block.get("target") == target
                    and re.fullmatch(r"[0-9a-f]{40}", str(block.get("reviewed_sha")))):
                block["comment_id"] = c.get("id")
                out.append(block)
    return out


def clean_id(value):
    return INVISIBLE.sub("", str(value)).strip()


# ---------- the checks ----------

class Gate:
    def __init__(self, *, repo, pr, base, head, head_dir, schema, operators, reviewer_login,
                 comments, commits, lookup_comment, git=git_show):
        self.repo, self.pr, self.base, self.head, self.head_dir = repo, pr, base, head, head_dir
        sub = dict(schema["$defs"]["requirement"])
        sub["$defs"] = schema["$defs"]
        self.validator = Draft202012Validator(sub, format_checker=Draft202012Validator.FORMAT_CHECKER)
        self.operators, self.reviewer_login = operators, reviewer_login
        self.comments, self.commits = comments, commits
        self.lookup_comment, self.git = lookup_comment, git
        self.pr_ref = f"{repo}#{pr}"
        self._comment_cache = {}

    # -- helpers
    def operator_comment(self, ref):
        """True when ref is '<this repo>#n comment id' and an operator wrote that comment on #n."""
        m = COMMENT_REF.match(str(ref))
        if not m or m.group(1) != self.repo:
            return False
        cid = m.group(3)
        if cid not in self._comment_cache:
            self._comment_cache[cid] = self.lookup_comment(cid)
        c = self._comment_cache[cid] or {}
        user = c.get("user") or {}
        issue = str(c.get("issue_url", "")).rsplit("/", 1)[-1]
        return (user.get("type") == "User" and str(user.get("login", "")).lower() in self.operators
                and issue == m.group(2))

    def non_operator_commits(self):
        out = []
        for c in self.commits:
            login = ((c.get("author") or {}).get("login") or "").lower()
            if login not in self.operators:
                out.append(c.get("sha", "")[:7])
        return out

    # -- lifecycle (S-BA-009)
    def lifecycle(self):
        problems, gated = [], []
        for path in sorted(set(self.base["reqs"]) | set(self.head["reqs"])):
            b, h = self.base["reqs"].get(path), self.head["reqs"].get(path)
            if h is None:
                problems.append(f"{path}: deleted; a requirement is never deleted, retire it (S-BA-009)")
                continue
            hs = h.get("status")
            if b is None:
                if hs not in ("draft", "ready"):
                    problems.append(f"{path}: a new requirement starts as draft, not {hs}")
                elif hs == "ready":
                    gated.append(path)
                continue
            if b == h:
                continue
            bs = b.get("status")
            if bs == hs == "ready":
                problems.append(f"{path}: edits a ready requirement without a transition; set `changed` "
                                "(S-BA-009). Link repairs (S-BA-053) are not recognised yet")
            elif hs not in NEXT.get(bs, set()) and hs != bs:
                problems.append(f"{path}: {bs} -> {hs} is not an allowed transition (S-BA-009)")
            elif bs == "retired":
                problems.append(f"{path}: a retired requirement never changes (S-BA-009)")
            else:
                if hs == "ready":
                    gated.append(path)
                if hs == "changed" and bs == "ready":
                    new = [r for r in h.get("revision") or [] if r not in (b.get("revision") or [])]
                    if not any(r.get("affected_acs") for r in new):
                        problems.append(f"{path}: ready -> changed needs a new revision entry listing "
                                        "affected_acs (S-BA-009)")
                if hs == "retired" and not h.get("retired"):
                    problems.append(f"{path}: retired needs `retired` with reason and replaced_by (S-BA-009)")
        return problems, gated

    # -- item 1
    def item1(self, path, req):
        out = []
        for e in sorted(self.validator.iter_errors(req), key=lambda e: list(map(str, e.absolute_path)))[:10]:
            out.append(f"schema: /{'/'.join(map(str, e.absolute_path))} ({e.validator})")
        if out:
            return out  # the field checks below assume the schema's shapes
        rid, area = req["id"], path.split("/")[1]
        if os.path.basename(path) != f"{rid}.md":
            out.append(f"ID: {rid} is not the file name")
        if req["area"] != area:
            out.append(f"ID: area {req['area']} is not the folder {area}")
        acs = [ac["id"] for ac in req["acceptance_criteria"]]
        if len(acs) != len(set(acs)):
            out.append("ID: duplicate AC IDs")
        out += [f"ID: {a} is not under {rid}" for a in acs if not a.startswith(rid + "/")]
        for name in ("questions", "assumptions"):
            ids = [x["id"] for x in req[name]]
            if len(ids) != len(set(ids)):
                out.append(f"ID: duplicate {name} IDs")
        out += self.source_refs(req)
        out += self.owner_fields(path, req)
        return out

    def local_ids(self, req):
        ids = {x["id"] for x in req["questions"]} | {x["id"] for x in req["assumptions"]}
        parent = next((r for r in self.head["reqs"].values() if r.get("id") == req.get("parent")), None)
        if parent:
            ids |= {x["id"] for x in parent.get("questions", [])} | {x["id"] for x in parent.get("assumptions", [])}
        return ids

    def refs_of(self, req):
        """(field, ref) for every source ref in the requirement."""
        yield from (("intent.cites", r) for r in req["intent"].get("cites", []))
        for side in ("in", "out"):
            for item in req["scope"].get(side, []):
                yield from ((f"scope.{side}", r) for r in item.get("cites", []))
        for ac in req["acceptance_criteria"]:
            yield from ((ac["id"], r) for r in ac["cites"])
        yield from (("sources", r) for r in req["sources"])
        for rev in req["revision"]:
            yield ("revision", rev["source_ref"])

    def resolve(self, ref, req):
        """None when ref resolves at head, else a reason."""
        ref = str(ref)
        if m := INT_REF.match(ref):
            turns = self.head["turns"].get(m.group(1))
            if turns is None:
                return "no such transcript"
            missing = [t for t in (m.group(2), m.group(3)) if t and int(t) not in turns]
            return f"no turn T{missing[0]}" if missing else None
        if m := REQ_REF.match(ref):
            target = next((r for r in self.head["reqs"].values() if r.get("id") == m.group(1)), None)
            if target is None:
                return "no such requirement"
            if m.group(2):
                ac = next((a for a in target.get("acceptance_criteria", []) if a.get("id") == ref), None)
                if ac is None:
                    return "no such AC"
            return None
        if RULE_REF.match(ref):
            return None if ref in self.head["rules"] else "no such rule"
        if LOCAL_REF.match(ref):
            return None if ref in self.local_ids(req) else "not a question or assumption of this requirement or its epic"
        if COMMENT_REF.match(ref) or ISSUE_REF.match(ref):
            return None  # tracker refs: format only; owner-field refs are verified below
        if ref in self.head["files"]:
            return None
        return "unrecognised ref"

    def source_refs(self, req):
        out = []
        for field, ref in self.refs_of(req):
            why = self.resolve(ref, req)
            if why:
                out.append(f"source ref: {field} cites {ref!r}: {why}")
        for r in req["rules"]:
            rule = self.base["rules"].get(r)
            if not rule or rule.get("status") != "active":
                out.append(f"source ref: rules lists {r}, which is not a merged active rule (S-BA-022)")
        return out[:15]

    def owner_values(self, req):
        return {
            "priority": req.get("priority"),
            "status": req.get("status"),
            "accepted_by": [c.get("accepted_by") for c in req.get("changes", [])],
            "questions": [(q.get("id"), q.get("status"), q.get("answer_ref")) for q in req.get("questions", [])],
            "assumptions": [(a.get("id"), a.get("status"), a.get("answer_ref")) for a in req.get("assumptions", [])],
            "dispositions": [(d.get("finding_id"), d.get("disposition"), d.get("ref"))
                             for d in req.get("review_dispositions") or []],
            "review_waiver": req.get("review_waiver"),
        }

    def owner_fields(self, path, req):
        """Human-owned fields (S-BA-015): set only in operator commits, and backed by operator comments."""
        out = []
        base = self.base["reqs"].get(path) or {}
        if self.owner_values(base) != self.owner_values(req) and self.non_operator_commits():
            out.append("owner fields: changed in a PR with commits not by an operator: "
                       + ", ".join(self.non_operator_commits()))
        for c in req["changes"]:
            if c["accepted_by"] and not self.operator_comment(c["accepted_by"]):
                out.append(f"owner fields: changes {c['rule']} accepted_by is not an operator comment ref")
        for kind, items, done in (("question", req["questions"], {"answered"}),
                                  ("assumption", req["assumptions"], {"confirmed", "rejected"})):
            for x in items:
                if x["status"] in done and x.get("answer_ref") and not self.operator_comment(x["answer_ref"]):
                    out.append(f"owner fields: {kind} {x['id']} answer_ref is not an operator comment ref")
        return out

    # -- items 2 to 4
    @staticmethod
    def item2(req):
        out = [f"question {q['id']} is open and blocking" for q in req["questions"]
               if q["blocking"] and q["status"] == "open"]
        out += [f"assumption {a['id']} is open and blocking" for a in req["assumptions"]
                if a["blocking"] and a["status"] == "open"]
        return out

    @staticmethod
    def item3(req):
        # The schema already requires quality and permissions, as IDs or `none` with a reason.
        return [] if str(req.get("priority") or "").strip() else ["priority is not set (human-owned, S-BA-015)"]

    def item4(self, req):
        out = []
        live = [ac for ac in req["acceptance_criteria"] if ac.get("status") != "retired"]
        for r in req["rules"]:
            rule = self.base["rules"].get(r) or {}
            if not str(rule.get("condition") or "").strip():
                continue
            if not any(ac["kind"] in ("negative", "boundary") and r in ac["cites"] for ac in live):
                out.append(f"{r} has a condition, but no live negative or boundary AC cites it (S-BA-007)")
        return out

    # -- item 5
    def item5(self, path, req):
        head_fp = fingerprint(req)
        match = None
        for block in reversed(self.blocks):
            text = self.git(self.head_dir, block["reviewed_sha"], path)
            if text is None:
                continue
            try:
                if fingerprint(front_matter(text, path)) == head_fp:
                    match = block
                    break
            except HarnessError:
                continue
        if match is None:
            waiver = self.waiver_problems(path, req)
            if waiver is None:
                return []  # a valid waiver for this gate
            why = ("no reviewer result" if not self.blocks else
                   "no reviewer result for a commit whose ACs, rules and changes match the head; "
                   "comment /review for a re-review")
            return [why] + (waiver if req.get("review_waiver") else [])
        out = []
        rid = req["id"]
        dispositions = {clean_id(d["finding_id"]): d for d in req.get("review_dispositions") or []}
        declared = {c["rule"] for c in req["changes"] if c["accepted_by"]}
        for f in match.get("findings", []):
            fid = clean_id(f.get("id"))
            loc = fid.split("|")[1] if fid.count("|") == 2 else ""
            if f.get("classification") != "contradicts" or not (
                    loc == rid or loc.startswith(rid + "/") or loc.startswith(rid + "#")):
                continue
            d = dispositions.get(fid)
            if d is None:
                out.append(f"finding {fid} (contradicts) has no review_dispositions entry")
            elif d["disposition"] == "declared" and d["ref"] not in declared:
                out.append(f"finding {fid}: declared, but {d['ref']} is not an accepted changes entry")
            elif d["disposition"] in ("accepted", "rejected") and not self.operator_comment(d["ref"]):
                out.append(f"finding {fid}: {d['disposition']} needs an operator comment ref")
        return out

    def waiver_problems(self, path, req):
        """None when a valid waiver for this gate is present, else the reasons it doesn't count."""
        w = req.get("review_waiver")
        if not w:
            return ["no review_waiver"]
        out = []
        if not self.operator_comment(w["ref"]):
            out.append("review_waiver ref is not an operator comment")
        if w["revision"] != self.pr_ref:
            out.append(f"review_waiver names {w['revision']}, not this gate {self.pr_ref}")
        base = self.base["reqs"].get(path) or {}
        new = [r for r in req["revision"] if r not in (base.get("revision") or [])]
        if not any(r["source_ref"] == self.pr_ref for r in new):
            out.append(f"this PR adds no revision entry with source_ref {self.pr_ref}")
        return out or None

    # -- all
    def run(self):
        self.blocks = reviewer_blocks(self.comments, self.reviewer_login, self.pr_ref)
        lifecycle, gated = self.lifecycle()
        reqs = []
        for path in gated:
            req = self.head["reqs"][path]
            items = {1: self.item1(path, req)}
            schema_ok = not any(m.startswith("schema:") for m in items[1])
            for n, fn in ((2, self.item2), (3, self.item3), (4, self.item4)):
                items[n] = fn(req) if schema_ok else ["not checked: schema invalid"]
            items[5] = self.item5(path, req) if schema_ok else ["not checked: schema invalid"]
            reqs.append({"path": path, "id": req.get("id"),
                         "items": {str(n): {"ok": not msgs, "item": ITEMS[n], "problems": msgs}
                                   for n, msgs in items.items()}})
        ok = not lifecycle and all(i["ok"] for r in reqs for i in r["items"].values())
        return {"kind": "ready_gate_result", "version": 1, "pr": self.pr_ref, "ok": ok,
                "lifecycle_problems": lifecycle, "gated": reqs,
                "reviewer_results": [{"reviewed_sha": b["reviewed_sha"], "verdict": b.get("verdict"),
                                      "comment_id": b.get("comment_id")} for b in self.blocks]}


# ---------- output ----------

def description(result):
    """The commit status description: at most 140 characters (GitHub's limit)."""
    if result["lifecycle_problems"]:
        text = f"Lifecycle: {len(result['lifecycle_problems'])} problem(s)"
    elif not result["gated"]:
        text = "No requirement made ready; lifecycle OK"
    elif result["ok"]:
        text = "Ready gate passes: " + ", ".join(r["id"] for r in result["gated"])
    else:
        failing = [f"{r['id']} item {n}" for r in result["gated"] for n, i in r["items"].items() if not i["ok"]]
        text = "Fails: " + ", ".join(failing)
    return text if len(text) <= 140 else text[:137] + "..."


def summary(result):
    out = [f"## Ready gate (S-BA-017): {'pass' if result['ok'] else 'fail'}", ""]
    if result["lifecycle_problems"]:
        out += ["### Lifecycle (S-BA-009)", ""] + [f"- {p}" for p in result["lifecycle_problems"]] + [""]
    if not result["gated"]:
        out += ["This PR makes no requirement ready.", ""]
    for r in result["gated"]:
        out += [f"### {r['id']} (`{r['path']}`)", ""]
        for n, i in r["items"].items():
            out.append(f"- {'✅' if i['ok'] else '❌'} {n}. {i['item']}")
            out += [f"  - {p}" for p in i["problems"]]
        out.append("")
    out.append(f"Reviewer results on this PR: {len(result['reviewer_results'])}. "
               "The semantic items (atomic and complete ACs, every rule change declared, acceptable "
               "remaining findings) are yours to judge (S-BA-018).")
    return "\n".join(out) + "\n"


# ---------- CLI ----------

def gh_json(path, paginate=False):
    cmd = ["gh", "api", *(["--paginate", "--jq", ".[]"] if paginate else []), path]
    try:
        out = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120).stdout
        return [json.loads(line) for line in out.splitlines() if line.strip()] if paginate else json.loads(out)
    except (OSError, subprocess.SubprocessError, ValueError):
        raise HarnessError("input_fetch_failed", f"gh api could not read {path.split('?')[0]}") from None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--pr", type=int, required=True)
    ap.add_argument("--base-dir", required=True, help="checkout of the PR base")
    ap.add_argument("--head-dir", required=True, help="checkout of the PR head, with history")
    ap.add_argument("--schema", required=True, help="staff-product analyst-output schema (requirement def)")
    ap.add_argument("--operators", required=True, help="staff governance/operators.yml")
    ap.add_argument("--reviewer-login", required=True, help="the reviewer App's bot login")
    ap.add_argument("--out", required=True, help="result JSON")
    ap.add_argument("--summary", help="Markdown summary, e.g. $GITHUB_STEP_SUMMARY")
    ap.add_argument("--description", help="file for the one-line commit status description")
    ap.add_argument("--comments-file")
    ap.add_argument("--commits-file")
    ap.add_argument("--comment-lookup-file", help="JSON {comment_id: comment} instead of gh api")
    args = ap.parse_args()

    base = f"repos/{args.repo}"
    comments = (load_json(args.comments_file, "input_invalid") if args.comments_file
                else gh_json(f"{base}/issues/{args.pr}/comments?per_page=100", paginate=True))
    commits = (load_json(args.commits_file, "input_invalid") if args.commits_file
               else gh_json(f"{base}/pulls/{args.pr}/commits?per_page=100", paginate=True))
    if args.comment_lookup_file:
        table = load_json(args.comment_lookup_file, "input_invalid")
        lookup = table.get
    else:
        def lookup(cid):
            try:
                return gh_json(f"{base}/issues/comments/{cid}")
            except HarnessError:
                return None
    gate = Gate(repo=args.repo, pr=args.pr, base=load_tree(args.base_dir), head=load_tree(args.head_dir),
                head_dir=args.head_dir, schema=load_json(args.schema, "agent_invalid"),
                operators=load_operators(args.operators), reviewer_login=args.reviewer_login,
                comments=comments, commits=commits, lookup_comment=lookup)
    result = gate.run()
    write_json(args.out, result)
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as fh:
            fh.write(summary(result))
    if args.description:
        with open(args.description, "w", encoding="utf-8") as fh:
            fh.write(description(result))
    print(description(result))
    if not result["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    run_main(main)
