"""Seeding runs for the eval sets (S-GEN-028, S-GEN-067): the request in, the task out.

  request   Write the seeding request: the kind and slot, the tickets of the set's stored tasks (so the
            agent writes something different), and on a retry the refused attempt with its check result.
            For the Architect, also the slot's `plan`: the exact plant counts (ARCH_SLOT_PLAN).
  assemble  Check the seeding agent's envelope (cost, schema, kind) and turn its output into a task file:
            an opaque ID, the set, the pinned product commit and provenance. The validity check runs next,
            in a job with no secrets: seed_check.py for the Developer, arch_eval.py check for the Architect.

`--agent developer` (the default) or `--agent architect`. Nothing here prints task content.
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
AGENT_KINDS = {"developer": ("feature", "fix", "trap"), "architect": ("seeded", "clean")}
PREVIOUS_KEYS = {"developer": ("ticket", "overlay", "reference", "heldout", "trap", "seed", "summary"),
                 "architect": ("ticket", "overlay", "spec", "summary")}
# The Architect promotion set's plants per slot (S-ARCH-049, D8): 8 seeded bundles, 2 clean. A slot's number
# is never stored in its bundle; only the request carries it.
ARCH_SLOT_PLAN = {
    "seeded": [{"quality_drivers": q, "conflicts": c, "defects": d, "interface_needs": n, "breaking_needs": b,
                "unknown_figures": 1}
               for q, c, d, n, b in zip([1, 2, 1, 3, 2, 1, 2, 1], [1, 2, 0, 1, 2, 1, 0, 1], [1, 0, 1, 1, 0, 1, 1, 0],
                                        [1, 1, 0, 1, 1, 0, 1, 0], [0, 0, 0, 1, 0, 0, 0, 0])],
    "clean": [{"quality_drivers": q, "conflicts": 0, "defects": 0, "interface_needs": n, "breaking_needs": 0,
               "unknown_figures": 0} for q, n in zip([2, 1], [1, 0])],
}


def check_kind(agent, kind):
    if kind not in AGENT_KINDS[agent]:
        raise HarnessError("input_invalid", f"a {agent} task is one of {', '.join(AGENT_KINDS[agent])}")


def slot_plan(kind, slot):
    plans = ARCH_SLOT_PLAN[kind]
    if not str(slot).isdigit() or not 1 <= int(slot) <= len(plans):
        raise HarnessError("input_invalid", f"an Architect {kind} slot is 1 to {len(plans)}")
    return plans[int(slot) - 1]


def opaque_id():
    return "".join(secrets.choice(ID_ALPHABET) for _ in range(12))


def cmd_request(args):
    check_kind(args.agent, args.kind)
    existing = []
    for path in sorted(glob.glob(os.path.join(args.set_dir, "*.json"))):
        t = load_json(path, "input_invalid")
        existing.append({"kind": t.get("kind"), "title": (t.get("ticket") or {}).get("title"),
                         "summary": t.get("summary")})
    req = {"kind": args.kind, "slot": args.slot, "set": args.set, "existing": existing}
    if args.agent == "architect":
        req["plan"] = slot_plan(args.kind, args.slot)
    if args.previous_task and os.path.exists(args.previous_task):
        prev = load_json(args.previous_task, "input_invalid")
        check = load_json(args.previous_check, "input_invalid") if args.previous_check and os.path.exists(args.previous_check) else {}
        req["previous"] = {"task": {k: prev.get(k) for k in PREVIOUS_KEYS[args.agent]},
                           "failures": check.get("failures") or [{"code": "check_missing"}]}
    write_json(args.out, req)
    print(f"request: {args.kind} slot {args.slot}, {len(existing)} existing, retry={'previous' in req}")


def architect_task(out, args):
    return {"version": 1, "id": opaque_id(), "agent": "architect", "set": args.set, "kind": out["kind"],
            "base_sha": args.base_sha,
            "seeding": {"run_id": args.run_id, "staff_sha": args.staff_sha, "model": args.model,
                        "holdout_seed": args.set == "promotion" and out["kind"] == "seeded"},
            "summary": out["summary"], "ticket": out["ticket"], "overlay": out["overlay"], "comments": [],
            "spec": out["spec"]}


def cmd_assemble(args):
    check_kind(args.agent, args.kind)
    result = {"ok": False, "reason": None}
    try:
        env = load_json(args.envelope, "envelope_invalid")
        result.update(metrics(env) if isinstance(env, dict) else {})
        check_run(env, args.max_run_usd)
        out = extract(env)
        check_schema(out, load_json(args.schema, "agent_invalid"))
        if out["kind"] != args.kind:
            raise HarnessError("kind_mismatch", f"asked for a {args.kind} task")
        if args.agent == "architect":
            task = architect_task(out, args)
        else:
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
    r.add_argument("--kind", required=True, help="feature, fix or trap; seeded or clean (AGENT_KINDS)")
    r.add_argument("--slot", required=True)
    r.add_argument("--set", required=True, choices=["visible", "hidden", "promotion"])
    r.add_argument("--set-dir", required=True, help="the set's stored task files")
    r.add_argument("--previous-task")
    r.add_argument("--previous-check")
    r.add_argument("--out", required=True)
    a = sub.add_parser("assemble")
    a.add_argument("--envelope", required=True)
    a.add_argument("--schema", help="default: the agent's seeder-<agent>-output schema")
    a.add_argument("--task-schema", help="default: the agent's task schema")
    a.add_argument("--max-run-usd", type=float, required=True)
    a.add_argument("--kind", required=True, help="feature, fix or trap; seeded or clean (AGENT_KINDS)")
    a.add_argument("--set", required=True, choices=["visible", "hidden", "promotion"])
    a.add_argument("--base-sha", required=True)
    a.add_argument("--run-id", required=True)
    a.add_argument("--staff-sha", required=True)
    a.add_argument("--model", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--result", required=True)
    for p in (r, a):
        p.add_argument("--agent", choices=sorted(AGENT_KINDS), default="developer")
    args = ap.parse_args()
    if args.cmd == "assemble":
        args.schema = args.schema or os.path.join(staff, "plugins", "staff-meta", "schemas",
                                                  f"seeder-{args.agent}-output.schema.json")
        args.task_schema = args.task_schema or os.path.join(staff, "evals", "schemas", f"{args.agent}-task.schema.json")
    {"request": cmd_request, "assemble": cmd_assemble}[args.cmd](args)


if __name__ == "__main__":
    run_main(main)
