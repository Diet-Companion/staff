"""Seeding runs for the Developer's eval sets (S-GEN-028, S-GEN-067): the request in, the task out.

  request   Write the seeding request: the kind and slot, the tickets of the set's stored tasks (so the
            agent writes something different), and on a retry the refused attempt with its check result.
  assemble  Check the seeding agent's envelope (cost, schema, kind) and turn its output into a task file:
            an opaque ID, the set, the pinned product commit and provenance. The validity check
            (seed_check.py) runs next, in a job with no secrets.

Nothing here prints task content.
"""
import argparse
import glob
import os
import secrets
import string
import tempfile

from common import HarnessError, load_json, run_main, write_json
from eval_task import load_task
from validate_output import check_run, check_schema, extract, metrics

ID_ALPHABET = string.ascii_lowercase + string.digits


def opaque_id():
    return "".join(secrets.choice(ID_ALPHABET) for _ in range(12))


def cmd_request(args):
    existing = []
    for path in sorted(glob.glob(os.path.join(args.set_dir, "*.json"))):
        t = load_json(path, "input_invalid")
        existing.append({"kind": t.get("kind"), "title": (t.get("ticket") or {}).get("title"),
                         "summary": t.get("summary")})
    req = {"kind": args.kind, "slot": args.slot, "set": args.set, "existing": existing}
    if args.previous_task and os.path.exists(args.previous_task):
        prev = load_json(args.previous_task, "input_invalid")
        check = load_json(args.previous_check, "input_invalid") if args.previous_check and os.path.exists(args.previous_check) else {}
        req["previous"] = {"task": {k: prev.get(k) for k in ("ticket", "overlay", "reference", "heldout", "trap", "seed", "summary")},
                           "failures": check.get("failures") or [{"code": "check_missing"}]}
    write_json(args.out, req)
    print(f"request: {args.kind} slot {args.slot}, {len(existing)} existing, retry={'previous' in req}")


def cmd_assemble(args):
    result = {"ok": False, "reason": None}
    try:
        env = load_json(args.envelope, "envelope_invalid")
        result.update(metrics(env) if isinstance(env, dict) else {})
        check_run(env, args.max_run_usd)
        out = extract(env)
        check_schema(out, load_json(args.schema, "agent_invalid"))
        if out["kind"] != args.kind:
            raise HarnessError("kind_mismatch", f"asked for a {args.kind} task")
        task = {"version": 1, "id": opaque_id(), "agent": "developer", "set": args.set, "kind": out["kind"],
                "base_sha": args.base_sha,
                "seeding": {"run_id": args.run_id, "staff_sha": args.staff_sha, "model": args.model,
                            "holdout_seed": args.set == "promotion" and out["kind"] != "feature"},
                "summary": out["summary"], "ticket": out["ticket"],
                "overlay": out["overlay"], "reference": out["reference"], "heldout": out["heldout"]}
        if out.get("trap"):
            task["trap"] = out["trap"]
        if out.get("seed"):
            task["seed"] = out["seed"]
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "task.json")
            write_json(p, task)
            load_task(p, args.task_schema)
        write_json(args.out, task)
        result.update(ok=True)
    except HarnessError as err:
        result["reason"] = err.reason
        write_json(args.result, result)
        raise
    write_json(args.result, result)
    print(f"assembled a {args.kind} task")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    staff = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = sub.add_parser("request")
    r.add_argument("--kind", required=True, choices=["feature", "fix", "trap"])
    r.add_argument("--slot", required=True)
    r.add_argument("--set", required=True, choices=["visible", "hidden", "promotion"])
    r.add_argument("--set-dir", required=True, help="the set's stored task files")
    r.add_argument("--previous-task")
    r.add_argument("--previous-check")
    r.add_argument("--out", required=True)
    a = sub.add_parser("assemble")
    a.add_argument("--envelope", required=True)
    a.add_argument("--schema", default=os.path.join(staff, "plugins", "staff-meta", "schemas", "seeder-developer-output.schema.json"))
    a.add_argument("--task-schema", default=os.path.join(staff, "evals", "schemas", "developer-task.schema.json"))
    a.add_argument("--max-run-usd", type=float, required=True)
    a.add_argument("--kind", required=True, choices=["feature", "fix", "trap"])
    a.add_argument("--set", required=True, choices=["visible", "hidden", "promotion"])
    a.add_argument("--base-sha", required=True)
    a.add_argument("--run-id", required=True)
    a.add_argument("--staff-sha", required=True)
    a.add_argument("--model", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--result", required=True)
    args = ap.parse_args()
    {"request": cmd_request, "assemble": cmd_assemble}[args.cmd](args)


if __name__ == "__main__":
    run_main(main)
