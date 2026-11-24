"""Write and update the run record (S-GEN-029, BA fields per S-BA-039).

The record holds IDs, hashes, counts and fixed codes only, never free text from
the model or the tracker (S-SEC-004).

CLI:
  run_record.py write  --out run-record.json ...   (read stage, always runs)
  run_record.py update --record run-record.json --comment-url URL ...   (write stage)
"""
import argparse
import datetime
import glob
import hashlib
import json
import os

from common import HarnessError, load_json, run_main, write_json

# Run status per S-GEN-029.
STATUS_BY_REASON = {
    "claude_timeout": "timeout",
    "cost_cap": "cap_hit", "budget_exceeded": "cap_hit", "max_turns": "cap_hit",
    "redaction_hit": "redaction_dropped", "input_redaction": "redaction_dropped",
}


def sha256(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def plugin_versions(plugins_root):
    out = {}
    for path in sorted(glob.glob(os.path.join(plugins_root, "*", ".claude-plugin", "plugin.json"))):
        manifest = load_json(path, "record_failed")
        out[manifest["name"]] = manifest.get("version")
    return out


def dev_outcome(validated):
    """The Developer's output has no outcome field; derive it as validate_output.py does."""
    if not validated or validated.get("agent") != "developer":
        return None
    return "proposed" if validated["pr"] else "code_map" if validated["code_map"] else "no_code"


def role_fields(validated):
    """Role fields from the validated output; IDs, counts and fixed codes only.

    Analyst: the BA fields (S-BA-039). Reviewer: the readiness verdict and the
    finding IDs with their classifications (S-BA-032), as the gate check reads them.
    """
    if not validated:
        return {}
    if validated.get("agent") == "architect":
        arts = validated["artifacts"]
        by = lambda kind: [a["id"] for a in arts if a["type"] == kind]
        adrs = [a for a in arts if a["type"] == "adr"]
        return {  # S-ARCH-040
            "req_ids": sorted({r for a in arts for r in (a.get("drivers") or ([a["req"]] if a.get("req") else []))
                               if str(r).startswith("REQ-")}),
            "adr_ids": by("adr"), "cmp_ids": by("component"), "qas_ids": by("qas"),
            "if_versions": [f"{a['id']}@{v['version']}" for a in arts if a["type"] == "interface" for v in a["versions"]],
            "options_count": {a["id"]: len(a["options"]) for a in adrs},
            "recommended_option": {a["id"]: a["recommended"]["option"] for a in adrs},
            "compat_class": None,  # set by the compatibility check, not the agent (S-ARCH-022)
            "defect_items_raised": len(validated["defect_items"]),
            "drift_ids": [q["drift_id"] for q in validated["questions"] if q.get("drift_id")],
            "question_ids": [q["id"] for q in validated["questions"]],
        }
    if validated.get("agent") == "developer":
        pr = validated["pr"] or {}
        return {
            "kind": pr.get("kind"),
            "ac_ids": [a["ac"] for a in pr.get("implements_acs") or []],
            "if_versions": list(pr.get("implements") or []),
            "files": len(validated["proposed_files"]),
            "flags": len(pr.get("flags") or []),
            "dependencies": len(pr.get("dependencies") or []),
            "classification": (validated["classification"] or {}).get("kind"),
            "code_map_area": (validated["code_map"] or {}).get("area"),
            "design_requests": len(validated["design_requests"]),
            "defect_items_raised": len(validated["defect_items"]),
            "private_reports": len(validated.get("private_reports_withheld") or []),
            "question_ids": [q["id"] for q in validated["questions"]],
        }
    if validated.get("agent") == "reviewer":
        return {
            "artifact_type": validated["artifact_type"],
            "target_ref": validated["target"]["ref"],
            "reviewed_sha": validated["reviewed_sha"],
            "readiness_verdict": validated["verdict"],
            "findings": [{"id": f["finding_id"], "severity": f["severity"],
                          "classification": f["classification"]} for f in validated["findings"]],
            "question_ids": [q["id"] for q in validated["questions"]],
            "blocking_questions": sum(1 for q in validated["questions"] if q["blocking"]),
            "proposed_changes": len(validated.get("proposed_changes", [])),
            "test_conditions": len(validated.get("test_conditions", [])),
        }
    reqs = validated["requirements"]
    return {
        "req_ids": [r["id"] for r in reqs],
        "ac_ids": [ac["id"] for r in reqs for ac in r["acceptance_criteria"]],
        "rule_ids_changed": sorted({c["rule"] for r in reqs for c in r["changes"]}),
        "questions_asked": len(validated["questions"]),
        "assumptions_open": len(validated["assumptions"]),
        "question_ids": [q["id"] for q in validated["questions"]],
        "batch_number": validated["intake"]["batch_number"],
        "is_kickoff": validated["intake"]["is_kickoff"],
    }


def build(args):
    result = load_json(args.result, "record_failed") if args.result and os.path.exists(args.result) else {}
    validated = load_json(args.validated, "record_failed") if args.validated and os.path.exists(args.validated) else None
    reason = args.reason or result.get("reason")
    ok = bool(result.get("ok")) and validated is not None and not args.reason
    duration_ms = result.get("duration_ms")
    return {
        "record_kind": "agent_run",
        "run_id": args.run_id,
        "run_attempt": args.attempt,
        "identity": args.identity,
        "plugin": args.plugin,
        "agent": args.agent,
        "stage": args.stage,
        "area": validated["intake"]["area"] if validated and "intake" in validated else None,
        "status": "completed" if ok else STATUS_BY_REASON.get(reason, "crashed"),
        "outcome": (validated.get("outcome") or validated.get("verdict") or dev_outcome(validated)) if ok else "failed",
        "validation": {"ok": ok, "reason": None if ok else (reason or "read_job_failed")},
        "read_schema_version": validated["schema_version"] if validated else None,
        "plugin_versions": plugin_versions(args.plugins_root) if args.plugins_root else {},
        "model": args.model,
        "staff_sha": args.staff_sha,
        "product_sha": args.product_sha,
        "trigger": {"type": args.trigger_type, "ref": args.trigger_ref},
        "input_refs": [args.trigger_ref],
        "input_sha256": sha256(args.input),
        "output_refs": [],
        "comment_urls": [],
        "cost_usd": result.get("cost_usd"),
        "num_turns": result.get("num_turns"),
        "duration_s": round(duration_ms / 1000, 1) if isinstance(duration_ms, (int, float)) else None,
        "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "role": role_fields(validated if ok else None),
    }


def update(record_path, urls):
    record = load_json(record_path, "record_failed")
    record["comment_urls"] = record.get("comment_urls", []) + urls
    record["output_refs"] = record.get("output_refs", []) + urls
    write_json(record_path, record)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--out", required=True)
    w.add_argument("--run-id", required=True)
    w.add_argument("--attempt", type=int, required=True)
    w.add_argument("--identity", required=True, help="the App that posts, e.g. diet-companion-analyst")
    w.add_argument("--plugin", required=True)
    w.add_argument("--agent", required=True)
    w.add_argument("--stage", type=int, default=1)
    w.add_argument("--model", required=True)
    w.add_argument("--staff-sha", required=True)
    w.add_argument("--product-sha", required=True)
    w.add_argument("--trigger-type", required=True, choices=["label", "comment", "pull_request"])
    w.add_argument("--trigger-ref", required=True)
    w.add_argument("--input", help="the input file, hashed")
    w.add_argument("--result", help="validate_output.py result file")
    w.add_argument("--validated", help="validated output, if it passed every check")
    w.add_argument("--reason", help="failure reason from an earlier step; overrides the result")
    w.add_argument("--plugins-root", help="staff plugins/ directory, for plugin_versions")
    u = sub.add_parser("update")
    u.add_argument("--record", required=True)
    u.add_argument("--comment-url", action="append", default=[])
    args = ap.parse_args()
    if args.cmd == "write":
        record = build(args)
        write_json(args.out, record)
        print(json.dumps({k: record[k] for k in ("run_id", "status", "outcome", "cost_usd", "num_turns")}))
    else:
        if not os.path.exists(args.record):
            raise HarnessError("record_failed", "no run record to update")
        update(args.record, args.comment_url)
        print(f"run record: {len(args.comment_url)} comment URL(s) added")


if __name__ == "__main__":
    run_main(main)
