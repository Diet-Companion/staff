"""The Developer's PR contract check (S-DEV-010, S-DEV-027). No model, and no product code runs.

CI runs it on every DEV agent PR (`agent/developer/*`, `agent/dev-upkeep/*`). It reads the PR body
for the product-PR block (S-DEV-009) that the publish job wrote there, and the PR's diff in a git
checkout. Requirements, rules, architecture and the code map are read from the base commit, so a PR
can't loosen what it is checked against. A PR fails when:
  - summary: the body doesn't open with the decision summary (`#### Decide first`), or holds no PR
    block, or more than one, or the block fails the product-PR schema (prose fields <= 2,000
    characters, S-SEC-002);
  - ticket, area: the block's ticket isn't the one the branch names, or the diff touches more than one
    code-map area (S-GEN-060);
  - size: more than 1000 changed lines (human decision 2026-11-26; starting value 500), not counting `generated` paths, which hold
    the lockfile (S-DEV-030). Split a larger ticket into several PRs in AC order;
  - declared: a declared AC isn't a live AC of a ready requirement, its requirement's quality targets
    have no accepted QAS, or a declared interface version isn't approved or deprecated (S-DEV-007).
    A `feature` declares at least one AC; a `refactor` or `upkeep` declares none;
  - tested: a declared AC is neither cited by a test at the head nor listed in `untested_acs`
    (S-DEV-012: each declared AC observable at unit level gets at least one citing test). An
    `untested_acs` entry must be a declared AC;
  - fix: a `fix` without `fixes`, or with neither `not_unit_observable` nor a test this PR adds or
    changes that cites the fix target;
  - drift: always, until the conformance check exists.

Interpretations and deferrals:
  - A citation is a `cites:` token (S-DEV-016) anywhere in a `unit_tests` file at the head. Whether
    the token sits on a test declaration, and whether the cited ID is live, is the citation scan's.
  - The regression-test check (S-DEV-029) isn't built. Until it is, a `fix` passes on a citing test
    added or changed in the PR, without proof that the test fails on the base.
  - The conformance check (S-ARCH-027) isn't built, so a `drift` PR can't pass.

CLI:
  dev_contract_check.py --repo DIR --base SHA --head SHA --head-ref REF --repo-name OWNER/NAME
                        --body body.md --out result.json [--summary summary.md]
                        [--code-map-schema F] [--pr-schema F]
The code map is read from the base commit's .staff/code.yml. Exit 0 when passed, 1 when any check
fails, 2 on a harness error (fail closed).
"""
import argparse
import base64
import binascii
import json
import os
import re
import sys
import tempfile

import yaml
from jsonschema import Draft202012Validator

from code_map import classify, load_code_map
from common import HarnessError, run_main, write_json
from dev_diff_check import changed_files, git, merge_base
from render_comment import esc
from validate_output import CITE_RE

STAFF = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMAS = os.path.join(STAFF, "plugins", "staff-engineering", "schemas")
MARKER = "<!-- staff-dev-contract-check:v1 -->"
MAX_LINES = 1000  # S-DEV-010: raised from the 500 starting value by the human, 2026-11-26
BLOCK_RE = re.compile(r"<!-- staff-pr-block:v1 ([A-Za-z0-9+/=]*) -->")
SUMMARY_RE = re.compile(r"\A[^\n]*\n\s*#### Decide first\n\s*\n> \S")
BRANCH_RE = re.compile(r"^agent/(developer|dev-upkeep)/(.+)$")
TRUTH_DIRS = ("requirements", "knowledge/rules", "architecture")


# ---- inputs from the base commit ---------------------------------------------------------------

def front_matter(text):
    if not text.startswith("---"):
        return None
    try:
        fm = yaml.safe_load(text.split("---", 2)[1])
    except (yaml.YAMLError, IndexError):
        return None
    return fm if isinstance(fm, dict) else None


def load_truth(repo, rev):
    """Requirements, rules and architecture front matter at rev, by ID (as dev_bundle reads main)."""
    names = git(repo, "ls-tree", "-r", "-z", "--name-only", rev, "--", *TRUTH_DIRS).decode().split("\0")
    truth = {"reqs": {}, "rules": {}, "arch": {}}
    for path in filter(None, names):
        base = os.path.basename(path)
        if not path.endswith(".md"):
            continue
        key = ("reqs" if path.startswith("requirements/") and base.startswith("REQ-") else
               "rules" if path.startswith("knowledge/rules/") and base.startswith("R-") else
               "arch" if path.startswith("architecture/") else None)
        if key is None:
            continue
        fm = front_matter(git(repo, "cat-file", "blob", f"{rev}:{path}").decode("utf-8", "replace"))
        if fm and isinstance(fm.get("id"), str):
            truth[key][fm["id"]] = fm
    return truth


def load_base_code_map(repo, rev, schema):
    data = git(repo, "cat-file", "blob", f"{rev}:.staff/code.yml")
    with tempfile.NamedTemporaryFile("wb", suffix=".yml", delete=False) as fh:
        fh.write(data)
    try:
        return load_code_map(fh.name, schema)
    finally:
        os.unlink(fh.name)


def pr_validator(path):
    with open(path, encoding="utf-8") as fh:
        schema = json.load(fh)
    return Draft202012Validator({"$schema": schema.get("$schema"), "$defs": schema["$defs"], "$ref": "#/$defs/pr"})


# ---- the checks --------------------------------------------------------------------------------

def live_acs(req):
    return [ac["id"] for ac in req.get("acceptance_criteria") or []
            if isinstance(ac, dict) and ac.get("status") != "retired"]


def accepted_qas_for(truth, req_id):
    return any(a.get("req") == req_id and a.get("status") == "accepted" and str(a.get("id", "")).startswith("QAS-")
               for a in truth["arch"].values())


def parse_block(body, validator, fail):
    """The PR block from the body, or None after recording why it can't be read."""
    if not SUMMARY_RE.match(body):
        fail("summary", "the body doesn't open with the decision summary (#### Decide first)")
    found = BLOCK_RE.findall(body)
    if len(found) != 1:
        fail("summary", "the body holds no PR block" if not found else "the body holds more than one PR block")
        return None
    try:
        block = json.loads(base64.b64decode(found[0], validate=True))
    except (binascii.Error, ValueError):
        fail("summary", "the PR block isn't base64 JSON")
        return None
    errors = sorted(validator.iter_errors(block), key=lambda e: list(map(str, e.absolute_path)))
    for e in errors[:10]:
        fail("summary", f"the PR block fails the schema at /{'/'.join(map(str, e.absolute_path))} ({e.validator})")
    return None if errors else block


def check_ticket(block, head_ref, repo_name, fail):
    m = BRANCH_RE.match(head_ref)
    if m and m.group(1) == "developer":
        want = f"{repo_name}#{m.group(2)}"
        if block["ticket"] != want:
            fail("ticket", f"the block's ticket is {block['ticket'] or 'none'}, the branch names {want}")


def changed_lines(repo, mb, head):
    """{path: added + removed}, binary files counting 0, with the same rename detection as the diff."""
    out = {}
    raw = git(repo, "diff", "--numstat", "-z", "-M", "--no-ext-diff", mb, head).decode("utf-8", "replace")
    parts, i = raw.split("\0"), 0
    while i < len(parts) and parts[i]:
        added, removed, path = parts[i].split("\t", 2)
        if path == "":  # a rename: the old and new paths follow
            path, i = parts[i + 2], i + 3
        else:
            i += 1
        out[path] = (int(added) if added.isdigit() else 0) + (int(removed) if removed.isdigit() else 0)
    return out


def check_scope(code_map, changes, lines, fail):
    """One area, and the size cap without generated paths. Returns the areas touched."""
    areas, counted = set(), 0
    for ch in changes:
        paths = [p for p in (ch["old"], ch["new"]) if p]
        areas |= {name for name, entry in code_map["areas"].items() if any(classify(p, entry) for p in paths)}
        path = ch["new"] or ch["old"]
        if not any("generated" in classify(path, e) for e in code_map["areas"].values()):
            counted += lines.get(path, 0)
    if len(areas) > 1:
        fail("area", f"the diff touches {len(areas)} code-map areas: {', '.join(sorted(areas))}")
    if counted > MAX_LINES:
        fail("size", f"{counted} changed lines, over the {MAX_LINES}-line cap; split the ticket into "
                     "several PRs in AC order")
    return areas, counted


def check_declared(block, truth, fail):
    kind, acs = block["kind"], [a["ac"] for a in block["implements_acs"]]
    if kind == "feature" and not acs:
        fail("declared", "a feature declares no AC")
    if kind in ("refactor", "upkeep") and acs:
        fail("declared", f"a {kind} declares no AC")
    if len(set(acs)) != len(acs):
        fail("declared", "an AC is declared twice")
    for ac in sorted(set(acs)):
        rid = ac.split("/")[0]
        req = truth["reqs"].get(rid)
        if req is None:
            fail("declared", f"{ac}: {rid} doesn't exist on the base")
            continue
        if req.get("status") != "ready":
            fail("declared", f"{ac}: {rid} is {req.get('status')}, not ready (S-BA-019)")
        if ac not in live_acs(req):
            fail("declared", f"{ac} is retired or doesn't exist")
        linked = req.get("quality") if isinstance(req.get("quality"), list) else []
        for qid in [rid] * (req.get("type") == "quality") + linked:
            if not accepted_qas_for(truth, qid):
                fail("declared", f"{ac}: {qid} has no accepted QAS, so the design is pending (S-ARCH-015)")
    for v in block["implements"]:
        iid, num = v.split("@")
        found = [x for x in (truth["arch"].get(iid) or {}).get("versions") or []
                 if isinstance(x, dict) and x.get("version") == num]
        if not found or found[0].get("status") not in ("approved", "deprecated"):
            fail("declared", f"{v} isn't an approved or deprecated interface version (S-ARCH-011)")


def tokens(text):
    out = set()
    for m in CITE_RE.finditer(text):
        out.update(c.strip().rstrip(".;") for c in m.group(1).split(",") if c.strip())
    return out


def head_citations(repo, head, code_map):
    """Every ID a `cites:` token names in a unit_tests file at the head."""
    names = git(repo, "ls-tree", "-r", "-z", "--name-only", head).decode("utf-8", "replace").split("\0")
    tests = [p for p in names if p and any("unit_tests" in classify(p, e) for e in code_map["areas"].values())]
    cited = set()
    for p in tests:
        cited |= tokens(git(repo, "cat-file", "blob", f"{head}:{p}").decode("utf-8", "replace"))
    return cited


def check_tested(block, cited, fail):
    declared = {a["ac"] for a in block["implements_acs"]}
    untested = {u["ac"] for u in block["untested_acs"]}
    for ac in sorted(untested - declared):
        fail("tested", f"{ac} is listed in untested_acs but not declared")
    missing = sorted(declared - untested - cited)
    for ac in missing:
        fail("tested", f"{ac} is declared, but no test at the head cites it and untested_acs doesn't list it")
    return sorted(declared & cited), missing


def changed_test_citations(repo, mb, head, changes, code_map):
    """IDs cited on lines this PR adds to unit_tests files."""
    out = set()
    for ch in changes:
        if not ch["new"] or not any("unit_tests" in classify(ch["new"], e) for e in code_map["areas"].values()):
            continue
        diff = git(repo, "diff", "-U0", "-M", "--no-ext-diff", mb, head, "--", *filter(None, (ch["old"], ch["new"])))
        added = "\n".join(line[1:] for line in diff.decode("utf-8", "replace").splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
        out |= tokens(added)
    return out


def check_kind(block, repo, mb, head, changes, code_map, fail):
    if block["kind"] == "fix":
        fixes = block["fixes"]
        if not fixes:
            fail("fix", "a fix declares no fixes {ticket, target}")
        elif not block["not_unit_observable"] and \
                fixes["target"] not in changed_test_citations(repo, mb, head, changes, code_map):
            fail("fix", f"no test this PR adds or changes cites the fix target {fixes['target']}, and no "
                        "not_unit_observable is declared")
    if block["kind"] == "drift":
        fail("drift", "the conformance check (S-ARCH-027) isn't built, so a drift PR can't pass yet")


def run_check(repo, base, head, head_ref, repo_name, body, code_map_schema, pr_schema):
    failures = []

    def fail(check, text):
        failures.append({"check": check, "text": text})

    mb = merge_base(repo, base, head)
    code_map = load_base_code_map(repo, base, code_map_schema)
    changes = changed_files(repo, mb, head)
    areas, counted = check_scope(code_map, changes, changed_lines(repo, mb, head), fail)
    block = parse_block(body, pr_validator(pr_schema), fail)
    cited, untested = [], []
    if block is not None:
        check_ticket(block, head_ref, repo_name, fail)
        check_declared(block, load_truth(repo, base), fail)
        cited, untested = check_tested(block, head_citations(repo, head, code_map), fail)
        check_kind(block, repo, mb, head, changes, code_map, fail)
    return {"passed": not failures, "failures": failures, "lines_changed": counted, "max_lines": MAX_LINES,
            "areas": sorted(areas), "kind": block["kind"] if block else None,
            "declared": [a["ac"] for a in block["implements_acs"]] if block else [],
            "cited": cited, "uncited": untested}


def description(result):
    if result["passed"]:
        return f"PR contract check: passed ({len(result['declared'])} ACs, {result['lines_changed']} lines)"
    checks = sorted({f["check"] for f in result["failures"]})
    return f"PR contract check: {len(result['failures'])} failure(s): {', '.join(checks)}"


def summary(result):
    """Markdown for the check summary and the PR comment. PR-derived text is escaped (S-SEC-002)."""
    out = [MARKER, "### PR contract check (S-DEV-010)", "", f"**{esc(description(result))}**", ""]
    if result["failures"]:
        out += [f"- **{esc(f['check'])}**: {esc(f['text'])}" for f in result["failures"]] + [""]
    out += [f"Changed lines: {result['lines_changed']} of {result['max_lines']} "
            "(generated paths not counted).", ""]
    if result["declared"]:
        out += ["Declared ACs cited by a test at the head: " +
                (", ".join(esc(a) for a in result["cited"]) or "none"), ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True, help="product git checkout with history to the merge base")
    ap.add_argument("--base", required=True, help="PR base SHA")
    ap.add_argument("--head", required=True, help="PR head SHA")
    ap.add_argument("--head-ref", required=True, help="the PR's head branch")
    ap.add_argument("--repo-name", required=True, help="owner/name, for the ticket reference")
    ap.add_argument("--body", required=True, help="the PR body as a file")
    ap.add_argument("--code-map-schema", default=os.path.join(SCHEMAS, "code-map.schema.json"))
    ap.add_argument("--pr-schema", default=os.path.join(SCHEMAS, "developer-output.schema.json"))
    ap.add_argument("--out", required=True, help="result JSON")
    ap.add_argument("--summary", help="Markdown summary file")
    args = ap.parse_args()
    try:
        with open(args.body, encoding="utf-8") as fh:
            body = fh.read().replace("\r\n", "\n")
    except (OSError, UnicodeDecodeError):
        raise HarnessError("input_invalid", "cannot read --body") from None
    result = run_check(os.path.abspath(args.repo), args.base, args.head, args.head_ref, args.repo_name, body,
                       args.code_map_schema, args.pr_schema)
    write_json(args.out, result)
    if args.summary:
        with open(args.summary, "w", encoding="utf-8") as fh:
            fh.write(summary(result))
    print(description(result))
    if not result["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    run_main(main)
