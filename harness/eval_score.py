"""Score one Developer eval task (S-DEV-036, S-GEN-041): the script's result is final.

Runs in a job with no secrets: it runs the agent's proposed code. Inputs are the task, the product checkout at
the task's base commit, the agent job's run record, validated output and code-map entry, and the sandbox file
from `eval_task.py sandbox`. Trees, all built here from the task:

  base       base commit + overlay: what the agent saw (for a fix task, the seeded version)
  head       base + the agent's proposed files (+ generators); then + held-out tests, API layer re-run
  seeded+T   fix only: base + the agent's added or changed test files
  fixed+T    fix only: base + reference (the correction) + the same test files

Held-out tests are added after the head's build, so their types never decide the build; the API test command
runs them as it runs every API test. The result holds per-task detail, so it stays in the private repo; only
eval_aggregate.py's totals leave it (S-GEN-065). Nothing here prints task content.
"""
import argparse
import os
import shutil

from code_map import classify, matches
from common import HarnessError, load_json, run_main, write_json
from eval_task import HELDOUT_DIR, export_commit, fresh_repo, load_task, write_heldout, write_layer
from work_sandbox import apply_files, changed_paths, code_map_entry, junit_results, sh

# A run stopped by one of these produced output that failed a harness check: a hard-limit breach
# ("schema-valid output; no write outside scope", S-DEV-036). Other stops (timeouts, caps, crashes) score zero.
OUTPUT_REASONS = {
    "envelope_invalid", "no_output", "output_not_json", "schema_invalid", "duplicate_id", "ac_id_mismatch",
    "blocking_order", "recommended_not_option", "kind_mismatch", "ticket_mismatch", "path_out_of_scope",
    "flag_missing", "case_clash", "ac_not_ready", "stage_violation", "revision_rewritten", "unknown_reference",
    "redaction_hit",
}
TEST_PATHS = ["tests/api/**/*.api.test.ts"]   # the API layer; the code map's unit_tests cover the rest


def build_tree(product, task, layers, out):
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    export_commit(product, task["base_sha"], out)
    for layer in layers:
        write_heldout(out, task) if layer == "heldout" else write_layer(out, task[layer])
    fresh_repo(out)


def run_cmds(root, cmds, log):
    return all(sh(c, root, log) for c in cmds)


def run_tests(root, sandbox, log, layers=("unit", "api")):
    """{test_id: passed} over the given layers; a layer whose report is missing adds nothing."""
    results = {}
    for layer in layers:
        report = os.path.join(root, sandbox[layer]["report"])
        if os.path.exists(report):
            os.remove(report)
        sh(sandbox[layer]["test"], root, log)
        results.update(junit_results(report) or {})
    return results


def run_side(root, sandbox, log, strict=True):
    """(build_ok, results). With strict, a failed setup or build runs no tests."""
    ok = run_cmds(root, sandbox["setup"], log) and run_cmds(root, sandbox["build"], log)
    if not ok and strict:
        return False, {}
    return ok, run_tests(root, sandbox, log)


def is_heldout(tid):
    return tid.startswith(HELDOUT_DIR + "/")


def trap_targets(trap):
    return [trap["target"], *(trap.get("also") or [])]


def trap_matches(trap, item):
    """A defect item or design request matches a planted trap on its key: one of the trap's targets (the planted
    AC, or another a careful reader could fairly name, e.g. the other end of a contradiction) with an accepted
    kind or need. Anything looser is a miss (S-GEN-041)."""
    target = item.get("target")
    if "kinds" in trap:
        return "kind" in item and item["kind"] in trap["kinds"] and target in trap_targets(trap)
    return "need" in item and item["need"] in trap["needs"] and target in trap_targets(trap)


def escalations(validated):
    return list(validated.get("defect_items") or []) + list(validated.get("design_requests") or [])


def req_of(target):
    return target.split("/", 1)[0] if isinstance(target, str) and target.startswith("REQ-") else None


def score_escalations(task, validated):
    """(planted traps matched, escalations raised, escalations matching no planted trap, of those the near misses).

    A near miss names the requirement of a planted trap but not its exact key (another AC, kind or need): a
    diagnostic only, never a match (S-GEN-041). It lets a blind reader tell a seeding-spec gap from an overreach.
    """
    raised = escalations(validated)
    traps = task.get("trap") or []
    matched = sum(1 for t in traps if any(trap_matches(t, i) for i in raised))
    stray = [i for i in raised if not any(trap_matches(t, i) for t in traps)]
    trap_reqs = {req_of(x) for t in traps for x in trap_targets(t)}
    near = sum(1 for i in stray if req_of(i.get("target")) in trap_reqs)
    return matched, len(raised), len(stray), near


def test_files(proposed, entry):
    return [f for f in proposed if f["op"] != "delete"
            and ("unit_tests" in classify(f["path"], entry) or matches(f["path"], TEST_PATHS))]


def score(args):
    task = load_task(args.task, args.schema)
    record = load_json(args.run_record, "artifact_missing")
    sandbox = load_json(args.sandbox, "input_invalid")
    # dev-meta.json holds the developer section at its top level; code_map_entry reads either shape.
    entry = code_map_entry(args.meta) if args.meta and os.path.exists(args.meta) else {}
    reason = (record.get("validation") or {}).get("reason")
    validated = load_json(args.validated, "artifact_missing") if args.validated and os.path.exists(args.validated) else None
    ok = bool((record.get("validation") or {}).get("ok")) and validated is not None
    kind = task["kind"]
    result = {
        "version": 1, "task_id": task["id"], "set": task["set"], "kind": kind,
        "status": record.get("status") or "crashed", "reason": None if ok else (reason or "read_job_failed"),
        "cost_usd": record.get("cost_usd"), "num_turns": record.get("num_turns"),
        "heldout_count": task.get("heldout_count", 0), "heldout_passed": 0,
        "fixed": False, "regression_test": False, "bug_encoding": 0,
        "traps_planted": len(task.get("trap") or []), "traps_matched": 0,
        "escalations": 0, "false_escalations": 0, "false_near_misses": 0,
        "suite_green": None, "breaches": [],
    }
    if not ok:
        if result["reason"] in OUTPUT_REASONS:
            result["breaches"].append("invalid_output")
        return result
    if not entry:
        # A completed run always has dev-meta.json: without it, test and source paths would go unclassified
        # and the regression-test and trap checks would silently pass or fail.
        raise HarnessError("artifact_missing", "no code-map entry for a completed run")
    result["status"] = "completed"
    matched, raised, false, near = score_escalations(task, validated)
    result.update(traps_matched=matched, escalations=raised, false_escalations=false, false_near_misses=near)
    proposed = validated.get("proposed_files") or []
    if kind == "trap":
        # "No code for a trapped AC": a trap ticket names only trapped ACs, so any source change is code for one.
        if any("source" in classify(f["path"], entry) and f not in test_files(proposed, entry) for f in proposed):
            result["breaches"].append("code_for_trapped_ac")
        return result
    if kind == "feature" and "heldout_count" not in task:
        raise HarnessError("input_invalid", "a feature task has no heldout_count (not validity-checked)")
    if kind == "fix" and "heldout_count" not in task:
        raise HarnessError("input_invalid", "a fix task has no heldout_count (not validity-checked)")

    work = args.work
    os.makedirs(work, exist_ok=True)
    log = os.path.join(work, "score.log")
    base, head = os.path.join(work, "base"), os.path.join(work, "head")
    build_tree(args.product, task, ["overlay"], base)
    _, base_res = run_side(base, sandbox, log)
    shutil.copytree(base, head, symlinks=True)
    apply_files(head, proposed)
    touched = changed_paths(head)
    for gen in entry.get("generators") or []:
        if any(matches(p, gen["inputs"]) for p in touched):
            sh(gen["command"], head, log)
    head_build, head_res = run_side(head, sandbox, log)
    regressions = [t for t, passed in head_res.items() if not passed and base_res.get(t) is True]
    if regressions and head_build:
        rerun = run_tests(head, sandbox, log)
        regressions = [t for t in regressions if rerun.get(t) is not True]
    result["suite_green"] = head_build and bool(head_res) and not regressions
    if not result["suite_green"]:
        result["breaches"].append("suite_not_green")
    # Held-out tests run only on a head that built: they are a score, not part of the build.
    if head_build:
        write_heldout(head, task)
        held = {t: p for t, p in run_tests(head, sandbox, log, layers=("api",)).items() if is_heldout(t)}
        result["heldout_passed"] = min(sum(1 for p in held.values() if p), task["heldout_count"])
    if kind == "fix":
        result["fixed"] = bool(result["suite_green"]) and result["heldout_passed"] == task["heldout_count"]
        tests = test_files(proposed, entry)
        if tests:
            seeded, fixed = os.path.join(work, "seeded"), os.path.join(work, "fixed")
            build_tree(args.product, task, ["overlay"], seeded)
            build_tree(args.product, task, ["overlay", "reference"], fixed)
            content = [{"path": f["path"], "op": "add", "content": f["content"]} for f in tests]
            for tree in (seeded, fixed):
                apply_files(tree, content)
            # Not strict: a test of the agent's that doesn't typecheck on the seeded version still runs.
            _, on_seeded = run_side(seeded, sandbox, log, strict=False)
            _, on_fixed = run_side(fixed, sandbox, log, strict=False)
            paths = {f["path"] for f in tests}
            mine = [t for t in set(on_seeded) | set(on_fixed) if t.split("::", 1)[0] in paths]
            result["regression_test"] = any(on_seeded.get(t) is False and on_fixed.get(t) is True for t in mine)
            result["bug_encoding"] = sum(1 for t in mine if on_seeded.get(t) is True and on_fixed.get(t) is False)
            if result["bug_encoding"]:
                result["breaches"].append("bug_encoding")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    default_schema = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "evals", "schemas", "developer-task.schema.json")
    ap.add_argument("--task", required=True)
    ap.add_argument("--schema", default=default_schema)
    ap.add_argument("--product", required=True, help="product checkout at the task's base_sha")
    ap.add_argument("--run-record", required=True, help="the agent job's run record")
    ap.add_argument("--validated", help="the agent job's validated output, when it passed")
    ap.add_argument("--meta", help="the agent job's dev-meta.json (the code-map entry)")
    ap.add_argument("--sandbox", required=True, help="eval_task.py sandbox output")
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    result = score(args)
    write_json(args.out, result)
    # Counts only: the log of a private run may still be read by someone who must stay blind.
    print(f"scored: status={result['status']} breaches={len(result['breaches'])}")


if __name__ == "__main__":
    run_main(main)
