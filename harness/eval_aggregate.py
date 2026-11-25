"""Aggregate a Developer eval run (S-DEV-036, S-GEN-065): totals only, no per-task detail.

Reads every eval_score.py result of one run and writes the aggregate record: the primary metrics with their
stage 1->2 thresholds, hard-limit breaches, counts per status, and summed cost. The aggregate keys the set by
an opaque ID and carries no task ID, kind-per-task, or content, so it may leave the private repo (to the
outcome store, a job summary, or a promotion report).

A metric with no tasks to measure (say, a set with no fix task) is null and fails its threshold: an
incomplete set can't promote.
"""
import argparse
import datetime
import glob
import os

from common import HarnessError, load_json, run_main, write_json

# S-DEV-036 starting values. (metric, comparison, threshold)
THRESHOLDS = {
    "ac_pass_rate": (">=", 0.80),
    "fix_rate": (">=", 0.70),
    "regression_test_rate": (">=", 0.70),
    "trap_recall": (">=", 0.60),
    "false_escalation_rate": ("<=", 0.20),
}
STATUSES = ("completed", "timeout", "cap_hit", "crashed", "redaction_dropped")


def ratio(num, den):
    return round(num / den, 4) if den else None


def aggregate(results, set_id, agent, staff_sha, model, rescore_of=None):
    by_kind = {k: [r for r in results if r["kind"] == k] for k in ("feature", "fix", "trap")}
    feat, fix, trap = by_kind["feature"], by_kind["fix"], by_kind["trap"]
    raised = sum(r["escalations"] for r in results)
    metrics = {
        "ac_pass_rate": ratio(sum(r["heldout_passed"] for r in feat), sum(r["heldout_count"] for r in feat)),
        "fix_rate": ratio(sum(r["fixed"] for r in fix), len(fix)),
        "regression_test_rate": ratio(sum(r["regression_test"] for r in fix), len(fix)),
        "trap_recall": ratio(sum(r["traps_matched"] for r in trap), sum(r["traps_planted"] for r in trap)),
        # No escalation raised means no false one: 0, not null.
        "false_escalation_rate": ratio(sum(r["false_escalations"] for r in results), raised) if raised else 0.0,
    }
    checks = {}
    for name, (op, limit) in THRESHOLDS.items():
        v = metrics[name]
        checks[name] = v is not None and (v >= limit if op == ">=" else v <= limit)
    breaches = {}
    for r in results:
        for b in r["breaches"]:
            breaches[b] = breaches.get(b, 0) + 1
    statuses = {s: 0 for s in STATUSES}
    for r in results:
        statuses[r["status"] if r["status"] in statuses else "crashed"] += 1
    costs = [r["cost_usd"] for r in results if isinstance(r.get("cost_usd"), (int, float))]
    return {
        "record_kind": "eval_aggregate",
        "version": 1,
        "agent": agent,
        "set_id": set_id,
        "staff_sha": staff_sha,
        "model": model,
        "tasks": len(results),
        "tasks_by_kind": {k: len(v) for k, v in by_kind.items()},
        "metrics": metrics,
        "thresholds": {k: {"op": op, "value": v} for k, (op, v) in THRESHOLDS.items()},
        "meets": checks,
        # Diagnostics, not scored: where the stray escalations came from, as totals per task kind (S-GEN-065).
        "false_escalations_by": {
            "feature": sum(r["false_escalations"] for r in feat),
            "fix": sum(r["false_escalations"] for r in fix),
            "trap_near_miss": sum(r.get("false_near_misses", 0) for r in trap),
            "trap_unrelated": sum(r["false_escalations"] - r.get("false_near_misses", 0) for r in trap),
        },
        "escalations_raised": raised,
        "rescore_of": rescore_of,
        "hard_limit_breaches": breaches,
        "passed": all(checks.values()) and not breaches,
        "statuses": statuses,
        "cost_usd": round(sum(costs), 4),
        "cost_complete": len(costs) == len(results),
        "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def summary(agg):
    pct = lambda v: "n/a" if v is None else f"{v * 100:.0f}%"
    title = f"### Developer eval, set `{agg['set_id']}`: **{'pass' if agg['passed'] else 'fail'}**"
    if agg.get("rescore_of"):
        title += f" (re-score of run {agg['rescore_of']}: a diagnostic, not a promotion attempt)"
    lines = [title, "",
             f"{agg['tasks']} tasks ({', '.join(f'{n} {k}' for k, n in agg['tasks_by_kind'].items())}), "
             f"cost ${agg['cost_usd']:.2f}{'' if agg['cost_complete'] else ' (incomplete)'}.", "",
             "| Metric | Value | Threshold | Met |", "| --- | --- | --- | --- |"]
    for name, t in agg["thresholds"].items():
        lines.append(f"| {name.replace('_', ' ')} | {pct(agg['metrics'][name])} | {t['op']} {pct(t['value'])} | "
                     f"{'yes' if agg['meets'][name] else 'no'} |")
    fb = agg["false_escalations_by"]
    lines += ["", f"Escalations raised: {agg['escalations_raised']}; stray: feature {fb['feature']}, fix {fb['fix']}, "
              f"trap near miss {fb['trap_near_miss']}, trap unrelated {fb['trap_unrelated']}."]
    b = agg["hard_limit_breaches"]
    lines += ["", "Hard-limit breaches: " + (", ".join(f"{k} {v}" for k, v in sorted(b.items())) if b else "none") + ".",
              "Statuses: " + ", ".join(f"{k} {v}" for k, v in agg["statuses"].items() if v) + "."]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--results", required=True, help="directory holding the run's per-task result JSON files")
    ap.add_argument("--set-id", required=True)
    ap.add_argument("--agent", default="developer")
    ap.add_argument("--staff-sha", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--expected", type=int, required=True, help="tasks in the set; a missing result fails the run")
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary", help="also write a Markdown summary of the totals")
    ap.add_argument("--rescore-of", help="the eval run whose saved agent outputs were re-scored")
    args = ap.parse_args()
    paths = sorted(glob.glob(os.path.join(args.results, "**", "*.json"), recursive=True))
    results = [load_json(p, "artifact_missing") for p in paths]
    if len(results) != args.expected:
        raise HarnessError("artifact_missing", f"{len(results)} task results for a set of {args.expected}")
    if args.rescore_of and not args.rescore_of.isdigit():
        raise HarnessError("input_invalid", "--rescore-of is a run ID")
    agg = aggregate(results, args.set_id, args.agent, args.staff_sha, args.model, args.rescore_of or None)
    write_json(args.out, agg)
    if args.summary:
        with open(args.summary, "w", encoding="utf-8") as fh:
            fh.write(summary(agg))
    print(f"eval {'pass' if agg['passed'] else 'fail'}: {agg['tasks']} tasks")


if __name__ == "__main__":
    run_main(main)
