"""Validate an agent's read-stage output (S-SEC-002, S-SEC-003).

Reads the `claude -p --output-format json` envelope, checks the run's cost and
status, extracts the structured result, validates it against the full
analyst-output schema, and runs the checks JSON Schema can't express. Writes the
validated JSON only when everything passes, and always writes a result file for
the run record. Messages name JSON paths and check names, never model text.

`--agent analyst` (the default) checks Analyst output. `--agent reviewer` checks the
shared reviewer's output against what the harness chose: the artifact type, the
target and the reviewed commit must match the input (S-BA-017 item 5).
"""
import argparse
import glob
import json
import os
import re
from collections import Counter

import yaml
from jsonschema import Draft202012Validator

from code_map import FLAGGED, classify, forbidden
from common import HarnessError, load_json, run_main, write_json
from contract import load_areas

SUBTYPE_REASONS = {"error_max_turns": "max_turns", "error_max_budget_usd": "budget_exceeded"}


def metrics(env):
    return {
        "cost_usd": env.get("total_cost_usd"),
        "num_turns": env.get("num_turns"),
        "duration_ms": env.get("duration_ms"),
        "subtype": env.get("subtype") if re.fullmatch(r"[a-z_]{1,64}", str(env.get("subtype"))) else None,
        "is_error": env.get("is_error"),
    }


def check_run(env, max_usd):
    if not isinstance(env, dict) or env.get("type") != "result":
        raise HarnessError("envelope_invalid", "not a claude -p result envelope")
    cost = env.get("total_cost_usd")
    if not isinstance(cost, (int, float)) or isinstance(cost, bool):
        raise HarnessError("cost_unknown", "total_cost_usd missing")
    if cost > max_usd:
        raise HarnessError("cost_cap", f"cost {cost:.4f} USD > cap {max_usd} USD (S-BA-038)")
    subtype = metrics(env)["subtype"]
    if subtype in SUBTYPE_REASONS:
        raise HarnessError(SUBTYPE_REASONS[subtype], f"run ended with {subtype}")
    if env.get("is_error") or subtype != "success":
        raise HarnessError("model_error", f"run ended with is_error={env.get('is_error')}, subtype={subtype}")


def extract(env):
    """The structured output (--json-schema), else the result text as one JSON object."""
    if isinstance(env.get("structured_output"), dict):
        return env["structured_output"]
    text = env.get("result")
    if not isinstance(text, str) or not text.strip():
        raise HarnessError("no_output", "envelope has no structured_output or result")
    try:
        out = json.loads(text.strip())
    except ValueError:
        raise HarnessError("output_not_json", "result is not one JSON object") from None
    if not isinstance(out, dict):
        raise HarnessError("output_not_json", "result is not a JSON object")
    return out


def check_schema(out, schema):
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    errors = sorted(validator.iter_errors(out), key=lambda e: list(map(str, e.absolute_path)))
    if errors:
        where = "; ".join(f"/{'/'.join(map(str, e.absolute_path))} ({e.validator})" for e in errors[:20])
        raise HarnessError("schema_invalid", f"{len(errors)} error(s): {where}")


def dupes(values):
    return sorted(v for v, n in Counter(values).items() if n > 1)


def check_harness(out, areas, stage):
    """Checks JSON Schema can't express. Raises on the first failing check."""
    reqs, questions = out["requirements"], out["questions"]

    # Area keys come from the product's .staff/areas.yml (S-GEN-060).
    for path, area in [("/intake/area", out["intake"]["area"])] + [
            (f"/requirements/{i}/area", r["area"]) for i, r in enumerate(reqs)]:
        if area not in areas:
            raise HarnessError("unknown_area", f"{path} is not in .staff/areas.yml")

    # Unique IDs (S-BA-005).
    id_sets = {
        "requirements": [r["id"] for r in reqs],
        "acceptance criteria": [ac["id"] for r in reqs for ac in r["acceptance_criteria"]],
        "questions": [q["id"] for q in questions],
        "assumptions": [a["id"] for a in out["assumptions"]],
        "interview topics": [t["topic_id"] for t in (out.get("interview_guide") or {}).get("topics", [])],
        "test conditions": [t["id"] for t in out.get("test_conditions", [])],
    }
    for i, r in enumerate(reqs):
        id_sets[f"requirements/{i} questions"] = [q["id"] for q in r["questions"]]
        id_sets[f"requirements/{i} assumptions"] = [a["id"] for a in r["assumptions"]]
    for i, q in enumerate(questions):
        id_sets[f"questions/{i} options"] = [o["id"] for o in q["options"]]
    for name, ids in id_sets.items():
        if dupes(ids):
            raise HarnessError("duplicate_id", f"duplicate IDs in {name}: {', '.join(dupes(ids))}")

    # An AC belongs to its requirement: REQ-n/AC-m sits under REQ-n.
    for i, r in enumerate(reqs):
        for j, ac in enumerate(r["acceptance_criteria"]):
            if ac["id"].split("/")[0] != r["id"]:
                raise HarnessError("ac_id_mismatch", f"/requirements/{i}/acceptance_criteria/{j}/id")

    # Every story's parent is the run's epic (S-BA-006, S-BA-049).
    epics = [r["id"] for r in reqs if r["type"] == "epic"]
    stories = [(i, r) for i, r in enumerate(reqs) if r["type"] == "story"]
    if len(epics) > 1:
        raise HarnessError("multiple_epics", f"{len(epics)} epics in one run")
    parents = {r.get("parent") for _, r in stories}
    if epics:
        for i, r in stories:
            if r.get("parent") != epics[0]:
                raise HarnessError("parent_mismatch", f"/requirements/{i}/parent is not the run's epic {epics[0]}")
    elif len(parents) > 1:
        raise HarnessError("parent_mismatch", "stories in one run name different parent epics")

    # Blocking questions first, then priority 1..n in batch order (S-BA-014).
    seen_non_blocking = False
    for i, q in enumerate(questions):
        if q["blocking"] and seen_non_blocking:
            raise HarnessError("blocking_order", f"/questions/{i} is blocking but follows a non-blocking question")
        seen_non_blocking = seen_non_blocking or not q["blocking"]
        if q["priority"] != i + 1:
            raise HarnessError("blocking_order", f"/questions/{i}/priority is not {i + 1}")
        if q["recommended"] not in {o["id"] for o in q["options"]}:
            raise HarnessError("recommended_not_option", f"/questions/{i}/recommended")

    # Stage 1 is advisory: drafts only, no ready gate (S-BA-009, S-BA-042, S-GEN-052).
    if stage == 1:
        if out.get("ready_gate"):
            raise HarnessError("stage_violation", "/ready_gate is true at stage 1")
        for i, r in enumerate(reqs):
            if r["status"] != "draft":
                raise HarnessError("stage_violation", f"/requirements/{i}/status is not draft at stage 1")


SEVERITY_RANK = {"blocker": 0, "major": 1, "minor": 2}


# Stage-1 statuses for new drafts (S-ARCH-011): never moved forward by an agent. The one exception is an
# ADR decided by a cited operator answer, whose status follows decision.outcome (checked below).
ARCH_DRAFT_STATUS = {"adr": "proposed", "component": "proposed", "qas": "draft"}
# Human-owned fields (S-ARCH-020) that may be non-null only when answers_applied cites an operator comment.
ARCH_OWNER_FIELDS = {
    "adr": ["decision"],
    "component": ["provenance_confirmed_by"],
    "interface": ["compatibility_policy"],
    "qas": ["gap_accepted_by"],
}


def _applied(out, target, field):
    return any(a["target"] == target and a["field"].split(".")[0].split("[")[0] == field
               for a in out["answers_applied"])


def architecture_truth(product_dir):
    """ID -> front matter of each architecture file on the product's default branch (S-ARCH-004)."""
    truth = {}
    for path in sorted(glob.glob(os.path.join(product_dir, "architecture", "**", "*.md"), recursive=True)):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if not text.startswith("---"):
            continue
        try:
            fm = yaml.safe_load(text.split("---", 2)[1])
        except yaml.YAMLError:
            continue
        if isinstance(fm, dict) and isinstance(fm.get("id"), str):
            truth[fm["id"]] = fm
    return truth


def check_architect(out, expect, stage=1, truth=None):
    """Architect checks JSON Schema can't express (S-ARCH-037). Raises on the first failing check.

    truth maps the IDs already on main to their front matter. An element there keeps its status, and a
    human-owned field equal to main's value is not newly set, so a redraft can carry accepted elements."""
    truth = truth or {}
    run, areas = expect["run"], expect["product"]["areas"]
    if out["trigger"]["kind"] != run["trigger"] or out["trigger"]["ref"] != run["intake_ref"]:
        raise HarnessError("trigger_mismatch", "/trigger is not the run's trigger kind and ref")
    if out["trigger"]["area"] not in areas:
        raise HarnessError("unknown_area", "/trigger/area is not in .staff/areas.yml")
    arts = out["artifacts"]
    for i, a in enumerate(arts):
        if a["area"] not in areas:
            raise HarnessError("unknown_area", f"/artifacts/{i}/area is not in .staff/areas.yml")

    # Unique IDs, and constraints numbered under their own ADR (S-ARCH-005).
    ids = {"artifacts": [a["id"] for a in arts], "questions": [q["id"] for q in out["questions"]],
           "assumptions": [a["id"] for a in out["assumptions"]]}
    adrs = {a["id"]: a for a in arts if a["type"] == "adr"}
    for aid, adr in adrs.items():
        ids[f"{aid} options"] = [o["key"] for o in adr["options"]]
        ids[f"{aid} constraints"] = [c["id"] for o in adr["options"] for c in o["constraints"]]
        for o in adr["options"]:
            for c in o["constraints"]:
                if not c["id"].startswith(aid + "/"):
                    raise HarnessError("constraint_id_mismatch", f"{aid} option {o['key']} has a constraint of another ADR")
        if adr["recommended"]["option"] not in ids[f"{aid} options"]:
            raise HarnessError("option_mismatch", f"{aid} recommends an option it doesn't have")
    for name, values in ids.items():
        if dupes(values):
            raise HarnessError("duplicate_id", f"duplicate IDs in {name}")

    # Stage 1: drafts only, and no human-owned field without a cited operator answer (S-ARCH-011, -020).
    operator_refs = {c["ref"] for c in expect["untrusted"]["comments"] if c["author_kind"] == "operator"}
    for i, a in enumerate(out["answers_applied"]):
        if a["comment_ref"] not in operator_refs:
            raise HarnessError("owner_field_set", f"/answers_applied/{i} does not cite an operator comment of this ticket")
    for i, a in enumerate(arts):
        cur = truth.get(a["id"], {})
        decision = a.get("decision") if a["type"] == "adr" else None
        if stage == 1 and cur and "status" in a:
            # Already on main: the agent never moves its status (S-ARCH-011).
            if a["status"] != cur.get("status"):
                raise HarnessError("stage_violation", f"/artifacts/{i}/status is not its status on main")
        elif stage == 1 and decision:
            # An answered ADR: its status follows decision.outcome, so the file the human commits passes the
            # lifecycle check, which fails an ADR merged as proposed (S-ARCH-011, -019 item 2).
            if a["status"] != decision["outcome"]:
                raise HarnessError("stage_violation", f"/artifacts/{i}/status is not its decision.outcome")
            if decision["decided_by"] not in operator_refs:
                raise HarnessError("owner_field_set", f"/artifacts/{i}/decision/decided_by is not an operator comment of this ticket")
            if decision["outcome"] == "accepted" and decision["chosen"] not in ids[f"{a['id']} options"]:
                raise HarnessError("option_mismatch", f"/artifacts/{i}/decision/chosen is not one of its options")
        elif stage == 1 and a["type"] in ARCH_DRAFT_STATUS and a["status"] != ARCH_DRAFT_STATUS[a["type"]]:
            raise HarnessError("stage_violation", f"/artifacts/{i}/status is not {ARCH_DRAFT_STATUS[a['type']]} at stage 1")
        if stage == 1 and a["type"] == "interface":
            # New versions are drafts; a version on main keeps its status there.
            kept = {v.get("version"): v.get("status") for v in cur.get("versions") or [] if isinstance(v, dict)}
            for v in a["versions"]:
                if v["status"] != kept.get(v["version"], "draft"):
                    raise HarnessError("stage_violation",
                                       f"/artifacts/{i} version {v['version']} is neither draft nor its status on main")
        for field in ARCH_OWNER_FIELDS.get(a["type"], []):
            if a.get(field) is not None and a.get(field) != cur.get(field) and not _applied(out, a["id"], field):
                raise HarnessError("owner_field_set", f"/artifacts/{i}/{field} is set without an operator answer")
        kept_gaps = {(t.get("item"), t.get("gap_accepted_by")) for t in cur.get("testability") or [] if isinstance(t, dict)}
        for item in a.get("testability", []):
            if item.get("gap_accepted_by") is not None and (item.get("item"), item["gap_accepted_by"]) not in kept_gaps \
                    and not _applied(out, a["id"], "testability"):
                raise HarnessError("owner_field_set", f"/artifacts/{i} accepts a testability gap without an operator answer")

    # Questions: blocking first, 1..n, a real recommended option; an ADR question offers that ADR's options.
    seen_non_blocking = False
    for i, q in enumerate(out["questions"]):
        if q["blocking"] and seen_non_blocking:
            raise HarnessError("blocking_order", f"/questions/{i} is blocking but follows a non-blocking question")
        seen_non_blocking = seen_non_blocking or not q["blocking"]
        if q["priority"] != i + 1:
            raise HarnessError("blocking_order", f"/questions/{i}/priority is not {i + 1}")
        if q["recommended"] not in {o["id"] for o in q["options"]}:
            raise HarnessError("recommended_not_option", f"/questions/{i}/recommended")
        if q.get("adr"):
            adr = adrs.get(q["adr"])
            if adr is None:
                raise HarnessError("unknown_reference", f"/questions/{i}/adr is not an ADR of this run")
            if [o["id"] for o in q["options"]] != [o["key"] for o in adr["options"]]:
                raise HarnessError("option_mismatch", f"/questions/{i} does not offer {q['adr']}'s options in order")

    for i, c in enumerate(out["conflicts"]):
        adr = adrs.get(c["adr"])
        if adr is None or c["option_key"] not in {o["key"] for o in adr["options"]}:
            raise HarnessError("unknown_reference", f"/conflicts/{i} names an ADR option not in this run")

    # Every spec belongs to a drafted interface version and parses (S-ARCH-021, -037).
    versions = {(a["id"], v["version"]) for a in arts if a["type"] == "interface" for v in a["versions"]}
    for i, s in enumerate(out["spec_versions"]):
        if (s["if_id"], s["version"]) not in versions:
            raise HarnessError("unknown_reference", f"/spec_versions/{i} is not a drafted interface version")
        try:
            doc = yaml.safe_load(s["document"])
        except Exception:
            raise HarnessError("spec_invalid", f"/spec_versions/{i}/document does not parse") from None
        if not isinstance(doc, dict):
            raise HarnessError("spec_invalid", f"/spec_versions/{i}/document is not a mapping")
        if s["format"].lower().startswith("openapi") and "openapi" not in doc:
            raise HarnessError("spec_invalid", f"/spec_versions/{i}/document has no openapi version")


def order_questions(out):
    """Blocking questions first, then priorities renumbered 1..n, keeping the model's order otherwise.

    Order and numbering are presentation, not content, so the harness fixes them instead of failing
    the run (live run 45371316724, as sort_findings for the reviewer). Returns True when anything changed."""
    before = [(q["id"], q["priority"]) for q in out["questions"]]
    out["questions"].sort(key=lambda q: (not q["blocking"], q["priority"]))
    for i, q in enumerate(out["questions"], start=1):
        q["priority"] = i
    return [(q["id"], q["priority"]) for q in out["questions"]] != before


def check_questions(questions):
    """Blocking first, priorities 1..n, a real recommended option (S-BA-014)."""
    seen_non_blocking = False
    for i, q in enumerate(questions):
        if q["blocking"] and seen_non_blocking:
            raise HarnessError("blocking_order", f"/questions/{i} is blocking but follows a non-blocking question")
        seen_non_blocking = seen_non_blocking or not q["blocking"]
        if q["priority"] != i + 1:
            raise HarnessError("blocking_order", f"/questions/{i}/priority is not {i + 1}")
        if q["recommended"] not in {o["id"] for o in q["options"]}:
            raise HarnessError("recommended_not_option", f"/questions/{i}/recommended")


DEPENDENCY_KEYS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")


def dependency_sets_change(f, base_dir):
    """True when a proposed dependency file changes what it depends on.

    A JSON manifest (package.json) is compared section by section with the base file, so a
    script or metadata edit isn't a dependency change (live run 45373601246). Anything that
    can't be compared counts as a change, failing towards asking for a dependencies entry."""
    if f["op"] != "modify" or not base_dir or not f["path"].endswith(".json"):
        return True
    try:
        with open(os.path.join(base_dir, f["path"]), encoding="utf-8") as fh:
            before = json.load(fh)
        after = json.loads("".join(f["content"]))
    except (OSError, ValueError):
        return True
    if not isinstance(before, dict) or not isinstance(after, dict):
        return True
    return any(before.get(k) != after.get(k) for k in DEPENDENCY_KEYS)


def check_developer(out, expect, base_dir=None):
    """Developer checks JSON Schema can't express (S-DEV-005, -007, -009, -021). Raises on the first failure.

    expect is the bundled input: `run` and the harness-made `developer` section. Changed
    lines are capped later, in the work sandbox, where the base exists to diff against."""
    run, dev = expect["run"], expect.get("developer") or {}
    kind, work, entry = dev.get("ticket_kind"), dev.get("work"), dev.get("code_map_entry")
    readiness = dev.get("readiness") or {}
    pr, files = out["pr"], out["proposed_files"]
    check_questions(out["questions"])
    if kind == "bootstrap":
        if out["code_map"] is None or files:
            raise HarnessError("kind_mismatch", "a dev:bootstrap run drafts code_map and proposes no files")
        if out["code_map"]["area"] != dev.get("area"):
            raise HarnessError("unknown_area", "/code_map/area is not the ticket's area")
    elif out["code_map"] is not None:
        raise HarnessError("kind_mismatch", "/code_map is set on a ticket that is not dev:bootstrap")
    if (kind == "fix") != (out["classification"] is not None):
        raise HarnessError("kind_mismatch", "/classification is set exactly on dev:fix tickets (S-DEV-017)")
    if pr is None:
        return
    if readiness.get("status") != "ready" or entry is None:
        raise HarnessError("not_ready", "code is proposed for a ticket that is not ready or has no code-map entry")
    if pr["kind"] != {"implement": work, "fix": "fix"}.get(kind):
        raise HarnessError("kind_mismatch", "/pr/kind does not match the ticket")
    if pr["ticket"] != run["intake_ref"]:
        raise HarnessError("ticket_mismatch", "/pr/ticket is not this ticket")
    live = set(readiness.get("acs") or [])
    for i, a in enumerate(pr["implements_acs"]):
        if a["ac"] not in live:
            raise HarnessError("ac_not_ready", f"/pr/implements_acs/{i} is not one of the ticket's ready ACs")
    if pr["kind"] == "feature" and not pr["implements_acs"]:
        raise HarnessError("ac_not_ready", "a feature change declares no AC (S-DEV-009)")
    if pr["kind"] == "refactor" and pr["implements_acs"]:
        raise HarnessError("kind_mismatch", "a refactor declares no AC (S-DEV-007)")

    # Path scope (S-DEV-005): the area's source and unit tests; flagged classes need flags (S-DEV-018).
    seen, flagged, deps = set(), set(), False
    for i, f in enumerate(files):
        if f["path"] in seen:
            raise HarnessError("duplicate_id", f"/proposed_files/{i}/path is proposed twice")
        seen.add(f["path"])
        for p in [f["path"]] + ([f["from"]] if f.get("from") else []):
            cls = classify(p, entry)
            if forbidden(p) or "generated" in cls or not cls & {"source", "unit_tests", *FLAGGED}:
                raise HarnessError("path_out_of_scope", f"/proposed_files/{i} is outside the area's code-map scope")
            flagged |= cls & set(FLAGGED)
            deps |= "dependency_files" in cls and (p != f["path"] or dependency_sets_change(f, base_dir))
    if flagged and not pr["flags"]:
        raise HarnessError("flag_missing", f"{', '.join(sorted(flagged))} paths change without a /pr/flags entry")
    if deps and not pr["dependencies"]:
        raise HarnessError("flag_missing", "a dependency file changes without a /pr/dependencies entry")


def sort_findings(out):
    """Order findings blocker first (S-BA-032), keeping the model's order within a severity.

    Ordering is presentation, not content, so the harness fixes it instead of failing
    the run (live run 45031393545). Returns True when the order changed.
    """
    before = [f["finding_id"] for f in out["findings"]]
    out["findings"].sort(key=lambda f: SEVERITY_RANK[f["severity"]])
    return [f["finding_id"] for f in out["findings"]] != before


def relativize(node, prefixes):
    """Rewrite known checkout prefixes in every string, in place: `/…/head/x` -> `head:x`.

    The reviewer reads files by absolute path, and sometimes cites them that way. A long
    absolute path trips the redaction check's entropy rule (live run 45032670952), and
    it says nothing the repo-relative path doesn't. Returns the number of rewrites.
    """
    count = 0

    def fix(s):
        nonlocal count
        for prefix, repl in prefixes:
            if prefix in s:
                count += s.count(prefix)
                s = s.replace(prefix, repl)
        return s

    def walk(n):
        items = n.items() if isinstance(n, dict) else enumerate(n) if isinstance(n, list) else ()
        for k, v in list(items):
            if isinstance(v, str):
                n[k] = fix(v)
            else:
                walk(v)

    walk(node)
    return count


def parse_prefixes(values):
    out = []
    for v in values:
        prefix, sep, repl = v.partition("=")
        if not sep or not prefix.startswith("/") or not prefix.endswith("/"):
            raise HarnessError("input_invalid", "--strip-prefix must be /absolute/dir/=replacement")
        out.append((prefix, repl))
    # Longest first, so a nested checkout is rewritten before its parent.
    return sorted(out, key=lambda p: -len(p[0]))


def check_review(out, expect_type, expect_target, expect_sha):
    """Reviewer checks JSON Schema can't express. Raises on the first failing check."""
    if out["artifact_type"] != expect_type:
        raise HarnessError("type_mismatch", "/artifact_type is not the type the harness chose")
    if out["target"] != {"kind": "pull_request", "ref": expect_target}:
        raise HarnessError("target_mismatch", "/target is not the pull request under review")
    if out["reviewed_sha"] != expect_sha:
        raise HarnessError("sha_mismatch", "/reviewed_sha is not the head commit under review")

    findings, questions = out["findings"], out["questions"]
    for name, values in [("findings", [f["finding_id"] for f in findings]),
                         ("questions", [q["id"] for q in questions]),
                         ("test conditions", [t["id"] for t in out.get("test_conditions", [])])]:
        if dupes(values):
            raise HarnessError("duplicate_id", f"duplicate IDs in {name}: {len(dupes(values))}")

    # A finding ID is derived: <checklist ID>|<location key>|<primary cited ID> (S-BA-032).
    for i, f in enumerate(findings):
        checklist_id, _, rest = f["finding_id"].partition("|")
        primary = rest.rpartition("|")[2]
        if checklist_id != f["checklist_id"]:
            raise HarnessError("finding_id_invalid", f"/findings/{i}/finding_id does not start with its checklist_id")
        if primary not in f["cited_ids"]:
            raise HarnessError("finding_id_invalid", f"/findings/{i}/finding_id names a primary ID missing from cited_ids")

    ids = {f["finding_id"] for f in findings}
    for i, c in enumerate(out.get("proposed_changes", [])):
        if c["finding_id"] not in ids:
            raise HarnessError("unknown_finding", f"/proposed_changes/{i}/finding_id is not a finding of this run")

    # Blocking questions first, then priority 1..n (S-BA-014).
    seen_non_blocking = False
    for i, q in enumerate(questions):
        if q["blocking"] and seen_non_blocking:
            raise HarnessError("blocking_order", f"/questions/{i} is blocking but follows a non-blocking question")
        seen_non_blocking = seen_non_blocking or not q["blocking"]
        if q["priority"] != i + 1:
            raise HarnessError("blocking_order", f"/questions/{i}/priority is not {i + 1}")
        if q["recommended"] not in {o["id"] for o in q["options"]}:
            raise HarnessError("recommended_not_option", f"/questions/{i}/recommended")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--envelope", required=True, help="stdout of claude -p --output-format json")
    ap.add_argument("--schema", required=True, help="the full read-stage schema")
    ap.add_argument("--agent", choices=["analyst", "reviewer", "architect", "developer"], default="analyst")
    ap.add_argument("--areas", help="product .staff/areas.yml (analyst)")
    ap.add_argument("--input", help="the review input file, for the expected type, target and commit (reviewer)")
    ap.add_argument("--product-dir", help="product checkout at the base: the architecture on main (architect), "
                    "the dependency files a change edits (developer)")
    ap.add_argument("--strip-prefix", action="append", default=[], metavar="/DIR/=REPL",
                    help="rewrite an absolute checkout prefix in the output, e.g. /w/head/=head: (reviewer)")
    ap.add_argument("--max-run-usd", type=float, required=True)
    ap.add_argument("--stage", type=int, default=1)
    ap.add_argument("--out", required=True, help="validated output, written only on success")
    ap.add_argument("--result", required=True, help="validation result for the run record")
    args = ap.parse_args()

    result = {"ok": False, "reason": None, "detail": None}
    try:
        env = load_json(args.envelope, "envelope_invalid")
        if isinstance(env, dict):
            result.update(metrics(env))
        check_run(env, args.max_run_usd)
        out = extract(env)
        check_schema(out, load_json(args.schema, "agent_invalid"))
        if args.agent == "reviewer":
            if not args.input:
                raise HarnessError("input_invalid", "--input is required with --agent reviewer")
            expect = load_json(args.input, "input_invalid")
            check_review(out, expect["artifact_type"], expect["target"]["ref"], expect["reviewed_sha"])
            result["findings_reordered"] = sort_findings(out)
            result["paths_relativized"] = relativize(out, parse_prefixes(args.strip_prefix))
        elif args.agent == "architect":
            if not args.input:
                raise HarnessError("input_invalid", "--input is required with --agent architect")
            truth = architecture_truth(args.product_dir) if args.product_dir else {}
            check_architect(out, load_json(args.input, "input_invalid"), args.stage, truth)
        elif args.agent == "developer":
            if not args.input:
                raise HarnessError("input_invalid", "--input is required with --agent developer")
            result["questions_reordered"] = order_questions(out)
            check_developer(out, load_json(args.input, "input_invalid"), args.product_dir)
        else:
            if not args.areas:
                raise HarnessError("input_invalid", "--areas is required with --agent analyst")
            check_harness(out, load_areas(args.areas), args.stage)
    except HarnessError as err:
        result.update(reason=err.reason, detail=err.detail)
        write_json(args.result, result)
        raise
    if args.agent == "architect":
        result.update(ok=True, outcome=out["outcome"])
        summary = (f"outcome={out['outcome']}, {len(out['artifacts'])} artifacts, "
                   f"{len(out['questions'])} questions, {len(out['defect_items'])} defect items")
    elif args.agent == "developer":
        # The repo is public: private reports never reach an artifact or a comment (S-DEV-019).
        out["private_reports_withheld"] = [{"id": r["id"], "kind": r["kind"]} for r in out["private_reports"]]
        out["private_reports"] = []
        outcome = "proposed" if out["pr"] else "code_map" if out["code_map"] else "no_code"
        result.update(ok=True, outcome=outcome)
        summary = (f"outcome={outcome}, {len(out['proposed_files'])} files, {len(out['questions'])} questions, "
                   f"{len(out['design_requests'])} design requests, {len(out['defect_items'])} defect items")
    elif args.agent == "reviewer":
        result.update(ok=True, outcome=out["verdict"])
        summary = (f"verdict={out['verdict']}, {len(out['findings'])} findings, "
                   f"{len(out['questions'])} questions")
    else:
        result.update(ok=True, outcome=out["outcome"])
        summary = (f"outcome={out['outcome']}, {len(out['requirements'])} requirements, "
                   f"{len(out['questions'])} questions")
    write_json(args.result, result)
    write_json(args.out, out)
    print(f"output valid: {summary}, cost {result['cost_usd']} USD")


if __name__ == "__main__":
    run_main(main)
