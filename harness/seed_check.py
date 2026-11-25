"""Validity check of a seeded Developer task (S-GEN-067), in a job with no secrets: it runs the task's code.

A task is stored only when every check passes:
  - the ticket passes the Developer's readiness check (S-DEV-007) on base + overlay, with an Area line;
  - a trap's targets are live ACs on base + overlay;
  - feature and fix: base + overlay builds and every existing test passes; every held-out test fails on it;
    base + overlay + reference builds, every existing test still passes, and every held-out test passes.
On a pass the task is written back with `heldout_count`, the AC pass rate's denominator. On a refusal,
check.json lists fixed failure codes with test IDs, first message lines or a build tail: the seeding agent's
retry reads them. Nothing here prints task content.
"""
import argparse
import os

from common import HarnessError, load_json, run_main, write_json
from dev_bundle import AREA_RE, live_acs, load_truth, readiness
from eval_score import build_tree, is_heldout, run_cmds, run_tests
from eval_task import load_task, write_heldout
from work_sandbox import junit_messages, output_tail

MAX_IDS = 20


def side(root, sandbox, log):
    """(failure or None, existing-test results). A failure is a build tail; tests don't run then."""
    start = os.path.getsize(log) if os.path.exists(log) else 0
    if not (run_cmds(root, sandbox["setup"], log) and run_cmds(root, sandbox["build"], log)):
        return output_tail(log, start, root), {}
    return None, run_tests(root, sandbox, log)


def heldout_run(root, task, sandbox, log):
    write_heldout(root, task)
    results = {t: p for t, p in run_tests(root, sandbox, log, layers=("api",)).items() if is_heldout(t)}
    return results, os.path.join(root, sandbox["api"]["report"])


def failure(code, ids=None, report=None, tail=None):
    f = {"code": code}
    if ids is not None:
        f["ids"] = sorted(ids)[:MAX_IDS]
        if report:
            f["messages"] = junit_messages(report, set(f["ids"]))
    if tail is not None:
        f["tail"] = tail
    return f


def check(args):
    task = load_task(args.task, args.schema)
    sandbox = load_json(args.sandbox, "input_invalid")
    os.makedirs(args.work, exist_ok=True)
    log = os.path.join(args.work, "check.log")
    failures = []
    base = os.path.join(args.work, "base")
    build_tree(args.product, task, ["overlay"], base)

    body = task["ticket"]["body"]
    kind = "fix" if task["ticket"]["label"] == "dev:fix" else "implement"
    truth = load_truth(base)
    status, details = readiness(truth, kind, body, True)
    if not AREA_RE.search(body):
        failures.append({"code": "no_area_line"})
    if status != "ready":
        failures.append({"code": "not_ready", "blockers": details["blockers"][:10]})
    for trap in task.get("trap") or []:
        for target in [trap["target"], *(trap.get("also") or [])]:
            req = truth["reqs"].get(target.split("/")[0])
            if req is None or ("/" in target and target not in live_acs(req)):
                failures.append({"code": "trap_target_not_live", "target": target})
    if task["kind"] == "trap":
        return task, failures

    tail, base_res = side(base, sandbox, log)
    if tail is not None:
        failures.append(failure("base_build_failed", tail=tail))
        return task, failures
    red = [t for t, ok in base_res.items() if not ok]
    if red:
        failures.append(failure("base_tests_failing", red))
    held, report = heldout_run(base, task, sandbox, log)
    if not held:
        failures.append({"code": "heldout_not_run"})
    passing = [t for t, ok in held.items() if ok]
    if passing:
        failures.append(failure("heldout_passes_on_base", passing))

    ref = os.path.join(args.work, "reference")
    build_tree(args.product, task, ["overlay", "reference"], ref)
    tail, ref_res = side(ref, sandbox, log)
    if tail is not None:
        failures.append(failure("reference_build_failed", tail=tail))
        return task, failures
    broken = [t for t, ok in ref_res.items() if not ok]
    if broken:
        failures.append(failure("reference_tests_failing", broken, os.path.join(ref, sandbox["unit"]["report"])))
    held, report = heldout_run(ref, task, sandbox, log)
    failing = [t for t, ok in held.items() if not ok]
    if not held:
        failures.append({"code": "heldout_not_run_on_reference"})
    if failing:
        failures.append(failure("heldout_fails_on_reference", failing, report))
    task["heldout_count"] = sum(1 for ok in held.values() if ok)
    return task, failures


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    staff = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--task", required=True)
    ap.add_argument("--schema", default=os.path.join(staff, "evals", "schemas", "developer-task.schema.json"))
    ap.add_argument("--product", required=True, help="product checkout at the task's base_sha")
    ap.add_argument("--sandbox", required=True, help="eval_task.py sandbox output")
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True, help="check.json")
    ap.add_argument("--out-task", required=True, help="the task with heldout_count, written only on a pass")
    args = ap.parse_args()
    task, failures = check(args)
    write_json(args.out, {"version": 1, "ok": not failures, "failures": failures})
    if failures:
        print("refused: " + ", ".join(f["code"] for f in failures))
        raise HarnessError("sandbox_failed", "the task failed its validity check")
    write_json(args.out_task, task)
    print("valid")


if __name__ == "__main__":
    run_main(main)
