"""Aggregate an eval run (S-DEV-036, S-ARCH-049, S-GEN-065): totals only, no per-task detail.

Reads every per-task result of one run and writes the aggregate record: the primary metrics with their
stage 1->2 thresholds, hard-limit breaches, counts per status, and summed cost. The aggregate keys the set by
an opaque ID and carries no task ID, kind-per-task, or content, so it may leave the private repo (to the
outcome store, a job summary, or a promotion report).

`--agent developer` (the default) reads eval_score.py results. Any other agent in AGENT_THRESHOLDS
(`architect`: arch_eval.py score results) reads results that carry a [num, den] count per metric: they are
pooled over task x run, sum(num) / sum(den) (S-GEN-035), with the per-run range reported beside them.
`--previous` names the last aggregate of the same set: `consecutive` is true only when that one passed for the
same agent, set, staff commit and model, and this one passes too. Promotion needs two (D4).

A metric with no tasks to measure (say, a set with no fix task) is null and fails its threshold: an
incomplete set can't promote. The exceptions are rates of something going wrong with nothing to go wrong in
(no escalation raised, no spec version produced): 0, not null.
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
# Count-based agents: S-ARCH-049 starting values. (metric, comparison, threshold)
AGENT_THRESHOLDS = {
    "architect": {
        "quality_driver_coverage": (">=", 0.80),
        "conflict_recall": (">=", 0.70),
        "defect_recall": (">=", 0.60),
        "defect_precision": (">=", 0.50),
        "interface_coverage": (">=", 0.80),
        "unnecessary_breaking_rate": ("<=", 0.10),
        "invented_fact_rate": ("<=", 0.05),
    },
}
AGENT_KINDS = {"architect": ("seeded", "clean")}
ZERO_WHEN_EMPTY = {"unnecessary_breaking_rate"}   # no spec version produced: none was breaking


def ratio(num, den):
    return round(num / den, 4) if den else None


def meets(value, op, limit):
    return value is not None and (value >= limit if op == ">=" else value <= limit)


def infra_failures(results):
    """Results whose run never reached the model because the account's usage limit was hit. They say nothing
    about the agent, so a run holding any is invalid: neither a pass nor a fail, and not an attempt."""
    return sum(1 for r in results if r.get("reason") == "usage_limit")


def tallies(results):
    """(breaches per code, counts per status, summed cost, whether every result had a cost)."""
    breaches = {}
    for r in results:
        for b in r["breaches"]:
            breaches[b] = breaches.get(b, 0) + 1
    statuses = {s: 0 for s in STATUSES}
    for r in results:
        statuses[r["status"] if r["status"] in statuses else "crashed"] += 1
    costs = [r["cost_usd"] for r in results if isinstance(r.get("cost_usd"), (int, float))]
    return breaches, statuses, round(sum(costs), 4), len(costs) == len(results)


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
        "regression_misses_by": {k: sum(1 for r in fix if r.get("regression_miss") == k)
                                 for k in ("no_test_added", "tests_not_run", "fails_on_corrected", "passes_on_seeded")},
        "rescore_of": rescore_of,
        "hard_limit_breaches": breaches,
        "infra_failures": infra_failures(results),
        "valid": not infra_failures(results),
        "passed": all(checks.values()) and not breaches and not infra_failures(results),
        "statuses": statuses,
        "cost_usd": round(sum(costs), 4),
        "cost_complete": len(costs) == len(results),
        "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def aggregate_counts(results, set_id, agent, staff_sha, model, previous=None, rescore_of=None):
    """The aggregate of a count-based agent's results, one per task and run."""
    if agent not in AGENT_THRESHOLDS:
        raise HarnessError("input_invalid", f"no thresholds for agent {agent}")
    if any(r.get("agent") != agent for r in results):
        raise HarnessError("input_invalid", f"a result is not an {agent} result")
    thresholds = AGENT_THRESHOLDS[agent]

    def pooled(rs, name):
        return [sum(r["counts"][name][0] for r in rs), sum(r["counts"][name][1] for r in rs)]

    def value(num, den, name):
        return ratio(num, den) if den else (0.0 if name in ZERO_WHEN_EMPTY else None)

    runs = sorted({r.get("run", 1) for r in results})
    counts = {name: pooled(results, name) for name in thresholds}
    metrics = {name: value(*counts[name], name) for name in thresholds}
    per_run = {name: [v for v in (value(*pooled([r for r in results if r.get("run", 1) == n], name), name)
                                  for n in runs) if v is not None] for name in thresholds}
    checks = {name: meets(metrics[name], op, limit) for name, (op, limit) in thresholds.items()}
    breaches, statuses, cost, complete = tallies(results)
    diagnostics = {}
    for r in results:
        for k, v in (r.get("diagnostics") or {}).items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    diagnostics.setdefault(k, {})[kk] = diagnostics.get(k, {}).get(kk, 0) + vv
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                diagnostics[k] = diagnostics.get(k, 0) + v
    infra = infra_failures(results)
    passed = all(checks.values()) and not breaches and not infra
    same = previous is not None and all(previous.get(k) == v for k, v in (
        ("agent", agent), ("set_id", set_id), ("staff_sha", staff_sha), ("model", model)))
    # A re-score is a diagnostic, not a promotion attempt, on either side.
    consecutive = (same and passed and previous.get("passed") is True and not rescore_of
                   and not previous.get("rescore_of"))
    tasks = {r["task_id"] for r in results}
    return {
        "record_kind": "eval_aggregate",
        "version": 1,
        "agent": agent,
        "set_id": set_id,
        "staff_sha": staff_sha,
        "model": model,
        "tasks": len(tasks),
        "runs": len(runs),
        "results": len(results),
        "tasks_by_kind": {k: len({r["task_id"] for r in results if r["kind"] == k}) for k in AGENT_KINDS[agent]},
        "counts": counts,
        "metrics": metrics,
        "per_run": {name: {"min": min(v) if v else None, "max": max(v) if v else None} for name, v in per_run.items()},
        "thresholds": {k: {"op": op, "value": v} for k, (op, v) in thresholds.items()},
        "meets": checks,
        # Diagnostics, not scored: totals over the set (S-GEN-065).
        "diagnostics": diagnostics,
        "rescore_of": rescore_of,
        "hard_limit_breaches": breaches,
        "infra_failures": infra,
        "valid": not infra,
        "passed": passed,
        "previous_passed": None if previous is None else bool(same and previous.get("passed") is True),
        "consecutive": consecutive,
        "statuses": statuses,
        "cost_usd": cost,
        "cost_complete": complete,
        "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def verdict(agg):
    return "invalid" if not agg.get("valid", True) else ("pass" if agg["passed"] else "fail")


def infra_line(agg):
    n = agg.get("infra_failures") or 0
    return [f"**Invalid run:** {n} result(s) hit the account's usage limit before the model ran. Re-run the set; "
            "this run is not an attempt.", ""] if n else []


def summary_counts(agg):
    pct = lambda v: "n/a" if v is None else f"{v * 100:.0f}%"
    title = f"### {agg['agent'].capitalize()} eval, set `{agg['set_id']}`: **{verdict(agg)}**"
    if agg.get("rescore_of"):
        title += f" (re-score of run {agg['rescore_of']}: a diagnostic, not a promotion attempt)"
    lines = [title, "", *infra_line(agg),
             f"{agg['tasks']} tasks ({', '.join(f'{n} {k}' for k, n in agg['tasks_by_kind'].items())}), "
             f"{agg['runs']} run(s) each, cost ${agg['cost_usd']:.2f}{'' if agg['cost_complete'] else ' (incomplete)'}.", "",
             "| Metric | Value | Count | Per-run range | Threshold | Met |", "| --- | --- | --- | --- | --- | --- |"]
    for name, t in agg["thresholds"].items():
        num, den = agg["counts"][name]
        rng = agg["per_run"][name]
        lines.append(f"| {name.replace('_', ' ')} | {pct(agg['metrics'][name])} | {num}/{den} | "
                     f"{pct(rng['min'])} to {pct(rng['max'])} | {t['op']} {pct(t['value'])} | "
                     f"{'yes' if agg['meets'][name] else 'no'} |")
    b = agg["hard_limit_breaches"]
    lines += ["", "Hard-limit breaches: " + (", ".join(f"{k} {v}" for k, v in sorted(b.items())) if b else "none") + ".",
              "Statuses: " + ", ".join(f"{k} {v}" for k, v in agg["statuses"].items() if v) + "."]
    if agg["previous_passed"] is not None:
        lines.append(f"Previous run of this set passed: {'yes' if agg['previous_passed'] else 'no'}; "
                     f"consecutive: {'yes' if agg['consecutive'] else 'no'}.")
    return "\n".join(lines) + "\n"


def summary(agg):
    pct = lambda v: "n/a" if v is None else f"{v * 100:.0f}%"
    title = f"### Developer eval, set `{agg['set_id']}`: **{verdict(agg)}**"
    if agg.get("rescore_of"):
        title += f" (re-score of run {agg['rescore_of']}: a diagnostic, not a promotion attempt)"
    lines = [title, "", *infra_line(agg),
             f"{agg['tasks']} tasks ({', '.join(f'{n} {k}' for k, n in agg['tasks_by_kind'].items())}), "
             f"cost ${agg['cost_usd']:.2f}{'' if agg['cost_complete'] else ' (incomplete)'}.", "",
             "| Metric | Value | Threshold | Met |", "| --- | --- | --- | --- |"]
    for name, t in agg["thresholds"].items():
        lines.append(f"| {name.replace('_', ' ')} | {pct(agg['metrics'][name])} | {t['op']} {pct(t['value'])} | "
                     f"{'yes' if agg['meets'][name] else 'no'} |")
    fb = agg["false_escalations_by"]
    lines += ["", f"Escalations raised: {agg['escalations_raised']}; stray: feature {fb['feature']}, fix {fb['fix']}, "
              f"trap near miss {fb['trap_near_miss']}, trap unrelated {fb['trap_unrelated']}."]
    rm = agg["regression_misses_by"]
    if any(rm.values()):
        lines.append("Regression-test misses: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in rm.items() if v) + ".")
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
    ap.add_argument("--previous", help="the last aggregate of this set, for two consecutive passes (not developer)")
    args = ap.parse_args()
    paths = sorted(glob.glob(os.path.join(args.results, "**", "*.json"), recursive=True))
    results = [load_json(p, "artifact_missing") for p in paths]
    if len(results) != args.expected:
        raise HarnessError("artifact_missing", f"{len(results)} task results for a set of {args.expected}")
    if args.rescore_of and not args.rescore_of.isdigit():
        raise HarnessError("input_invalid", "--rescore-of is a run ID")
    if args.agent == "developer":
        if args.previous:
            raise HarnessError("input_invalid", "--previous is for count-based agents")
        agg = aggregate(results, args.set_id, args.agent, args.staff_sha, args.model, args.rescore_of or None)
        text = summary(agg)
    else:
        previous = load_json(args.previous, "input_invalid") if args.previous else None
        agg = aggregate_counts(results, args.set_id, args.agent, args.staff_sha, args.model, previous,
                               args.rescore_of or None)
        text = summary_counts(agg)
    write_json(args.out, agg)
    if args.summary:
        with open(args.summary, "w", encoding="utf-8") as fh:
            fh.write(text)
    line = f"eval {verdict(agg)}: {agg['tasks']} tasks"
    if args.previous:
        line += f", consecutive: {'yes' if agg['consecutive'] else 'no'}"
    print(line)


if __name__ == "__main__":
    run_main(main)
