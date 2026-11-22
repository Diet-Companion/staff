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
import json
import re
from collections import Counter

from jsonschema import Draft202012Validator

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
    last = -1
    for i, f in enumerate(findings):
        checklist_id, _, rest = f["finding_id"].partition("|")
        primary = rest.rpartition("|")[2]
        if checklist_id != f["checklist_id"]:
            raise HarnessError("finding_id_invalid", f"/findings/{i}/finding_id does not start with its checklist_id")
        if primary not in f["cited_ids"]:
            raise HarnessError("finding_id_invalid", f"/findings/{i}/finding_id names a primary ID missing from cited_ids")
        rank = SEVERITY_RANK[f["severity"]]
        if rank < last:
            raise HarnessError("severity_order", f"/findings/{i} is more severe than the finding before it")
        last = rank

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
    ap.add_argument("--agent", choices=["analyst", "reviewer"], default="analyst")
    ap.add_argument("--areas", help="product .staff/areas.yml (analyst)")
    ap.add_argument("--input", help="the review input file, for the expected type, target and commit (reviewer)")
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
        else:
            if not args.areas:
                raise HarnessError("input_invalid", "--areas is required with --agent analyst")
            check_harness(out, load_areas(args.areas), args.stage)
    except HarnessError as err:
        result.update(reason=err.reason, detail=err.detail)
        write_json(args.result, result)
        raise
    if args.agent == "reviewer":
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
