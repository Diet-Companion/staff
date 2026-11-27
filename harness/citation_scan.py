"""The citation scan (S-DEV-016, the blocking part of S-BA-021 and S-ARCH-030 for tests). No model, and no product code runs.

CI runs it on every product PR, human or agent (S-DEV-027). It reads the lines the PR adds to test files
(`unit_tests` in the code map, and the layer `paths` of the QA test map) and fails when a `cites:` token
there names an S-DEV-016 ID (REQ-n/AC-m, REQ-n/AC-m/TC-k, R-n, IF-n@x.y.z[#element], ADR-n/C-k or
QAS-n) that is:
  - missing: doesn't exist at the base: no such requirement or AC, rule, interface or version, ADR or
    constraint, or QAS;
  - retired: a retired requirement, AC, rule, interface version or QAS, or a constraint of a rejected
    or superseded ADR.
A token in another form (an assumption A-n, a bare ADR-n, an interview or issue reference) is listed as a
note and doesn't fail the scan: whether such a token may stand as a test's source is the human's call
(S-DEV-016 names only the forms above).

Requirements, rules, architecture and both maps are read from the base commit, so a PR can't add or revive
the ID its own test cites. Only added lines count: a citation the PR doesn't touch is the nightly trace
check's (stale citations), not this one's.

Interpretations and deferrals:
  - A citation is the `cites:` token as dev_contract_check.tokens() reads it (in a name, tag or comment).
    Whether it sits within 3 lines of a test declaration is not checked here.
  - For REQ-n/AC-m/TC-k the AC is checked. Test-condition files (S-BA-050) aren't built yet, so TC-k isn't.
  - An `#element` of an interface citation isn't resolved against the spec.

CLI:
  citation_scan.py --repo DIR --base SHA --head SHA --out result.json [--summary summary.md]
Exit 0 when passed, 1 when a citation fails, 2 on a harness error (fail closed).
"""

import argparse
import os
import re
import sys
import tempfile

from code_map import classify, matches
from common import HarnessError, run_main, write_json
from dev_contract_check import SCHEMAS, live_acs, load_base_code_map, load_truth, tokens
from dev_diff_check import changed_files, git, merge_base
from render_comment import esc
from test_map import load_test_map

STAFF = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_MAP_SCHEMA = os.path.join(STAFF, "plugins", "staff-qa", "schemas", "test-map.schema.json")
MARKER = "<!-- staff-citation-scan:v1 -->"
FORM = re.compile(r"^(?:(?P<req>REQ-\d{3,})/(?P<ac>AC-\d{3,})(?:/TC-\d{3,})?|(?P<rule>R-\d{3,})"
                  r"|(?P<iface>IF-\d{3,})@(?P<version>\d+\.\d+\.\d+)(?:#[^\s#,]{1,200})?"
                  r"|(?P<adr>ADR-\d{3,})/(?P<constraint>C-\d{3,})|(?P<qas>QAS-\d{3,}))$")
RETIRED = {"retired"}
DEAD_ADR = {"rejected", "superseded"}


def load_base_test_globs(repo, rev, schema):
    """The layer `paths` of the QA test map at rev; none when the file doesn't exist there."""
    try:
        data = git(repo, "cat-file", "blob", f"{rev}:.staff/tests.yml")
    except HarnessError:
        return []
    with tempfile.NamedTemporaryFile("wb", suffix=".yml", delete=False) as fh:
        fh.write(data)
    try:
        test_map = load_test_map(fh.name, schema)
    finally:
        os.unlink(fh.name)
    return [g for layers in (test_map.get("areas") or {}).values() for layer in layers.values()
            for g in layer.get("paths") or []]


def is_test(path, code_map, test_globs):
    return (any("unit_tests" in classify(path, e) for e in code_map["areas"].values())
            or matches(path, test_globs))


def added_citations(repo, mb, head, changes, code_map, test_globs):
    """{path: sorted IDs cited on the lines this PR adds to that test file}."""
    out = {}
    for ch in changes:
        if not ch["new"] or not is_test(ch["new"], code_map, test_globs):
            continue
        diff = git(repo, "diff", "-U0", "-M", "--no-ext-diff", mb, head, "--", *filter(None, (ch["old"], ch["new"])))
        added = "\n".join(line[1:] for line in diff.decode("utf-8", "replace").splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
        cited = tokens(added)
        if cited:
            out[ch["new"]] = sorted(cited)
    return out


def resolve(cid, truth):
    """None when the citation is live at the base, else (check, why)."""
    m = FORM.match(cid)
    if not m:
        return "form", "is not an S-DEV-016 form, so it isn't checked"
    if m["req"]:
        req = truth["reqs"].get(m["req"])
        if req is None:
            return "missing", f"{m['req']} doesn't exist"
        if req.get("status") in RETIRED:
            return "retired", f"{m['req']} is retired"
        ac = f"{m['req']}/{m['ac']}"
        if ac in live_acs(req):
            return None
        known = {a.get("id") for a in req.get("acceptance_criteria") or [] if isinstance(a, dict)}
        return ("retired", f"{ac} is retired") if ac in known else ("missing", f"{ac} doesn't exist")
    if m["rule"]:
        rule = truth["rules"].get(m["rule"])
        if rule is None:
            return "missing", f"{m['rule']} doesn't exist"
        return ("retired", f"{m['rule']} is retired") if rule.get("status") in RETIRED else None
    if m["iface"]:
        versions = [v for v in (truth["arch"].get(m["iface"]) or {}).get("versions") or [] if isinstance(v, dict)]
        version = next((v for v in versions if v.get("version") == m["version"]), None)
        if version is None:
            return "missing", f"{m['iface']}@{m['version']} doesn't exist"
        return ("retired", f"{m['iface']}@{m['version']} is retired") if version.get("status") in RETIRED else None
    if m["adr"]:
        adr = truth["arch"].get(m["adr"])
        if adr is None:
            return "missing", f"{m['adr']} doesn't exist"
        ids = {c.get("id") for o in adr.get("options") or [] if isinstance(o, dict)
               for c in o.get("constraints") or [] if isinstance(c, dict)}
        if cid not in ids:
            return "missing", f"{cid} doesn't exist"
        return ("retired", f"{m['adr']} is {adr.get('status')}") if adr.get("status") in DEAD_ADR else None
    qas = truth["arch"].get(m["qas"])
    if qas is None:
        return "missing", f"{m['qas']} doesn't exist"
    return ("retired", f"{m['qas']} is retired") if qas.get("status") in RETIRED else None


def run_scan(repo, base, head, code_map_schema, test_map_schema):
    mb = merge_base(repo, base, head)
    code_map = load_base_code_map(repo, base, code_map_schema)
    test_globs = load_base_test_globs(repo, base, test_map_schema)
    cited = added_citations(repo, mb, head, changed_files(repo, mb, head), code_map, test_globs)
    truth = load_truth(repo, base)
    failures, notes = [], []
    for path, ids in sorted(cited.items()):
        for cid in ids:
            bad = resolve(cid, truth)
            if bad:
                (notes if bad[0] == "form" else failures).append(
                    {"check": bad[0], "path": path, "id": cid, "text": f"{cid} {bad[1]}"})
    return {"passed": not failures, "failures": failures, "notes": notes, "files": len(cited),
            "citations": sum(len(v) for v in cited.values())}


def description(result):
    if result["passed"]:
        return f"Citation scan: passed ({result['citations']} added citations in {result['files']} test files)"
    checks = sorted({f["check"] for f in result["failures"]})
    return f"Citation scan: {len(result['failures'])} failure(s): {', '.join(checks)}"


def summary(result):
    """Markdown for the check summary and the PR comment. PR-derived text is escaped (S-SEC-002)."""
    out = [MARKER, "### Citation scan (S-DEV-016)", "", f"**{esc(description(result))}**", ""]
    if result["failures"]:
        out += [f"- **{esc(f['check'])}** in `{esc(f['path'])}`: {esc(f['text'])}" for f in result["failures"]]
        out += ["", "Cite a live ID: a live AC of a requirement, an active rule, an existing interface version, "
                "a constraint of an accepted ADR, or a QAS.", ""]
    if result["notes"]:
        out += ["Not checked (not an S-DEV-016 form): " +
                ", ".join(f"`{esc(n['id'])}` in `{esc(n['path'])}`" for n in result["notes"]), ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True, help="product git checkout with history to the merge base")
    ap.add_argument("--base", required=True, help="PR base SHA")
    ap.add_argument("--head", required=True, help="PR head SHA")
    ap.add_argument("--code-map-schema", default=os.path.join(SCHEMAS, "code-map.schema.json"))
    ap.add_argument("--test-map-schema", default=TEST_MAP_SCHEMA)
    ap.add_argument("--out", required=True, help="result JSON")
    ap.add_argument("--summary", help="Markdown summary file")
    args = ap.parse_args()
    result = run_scan(os.path.abspath(args.repo), args.base, args.head, args.code_map_schema, args.test_map_schema)
    write_json(args.out, result)
    if args.summary:
        with open(args.summary, "w", encoding="utf-8") as fh:
            fh.write(summary(result))
    print(description(result))
    if not result["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    run_main(main)
