"""Daily and weekly summary of the outcome store, as plain text or Markdown.

Reads one or more outcome-store JSONL files (append_run_log.py export, or a
local review log) and prints, for the day and the 7 days ending on it:
- runs, pass/fail by reason code, cost (S-GEN-029, S-GEN-058);
- the human's review minutes per day against the 60-minute gate (S-GEN-032, S-GEN-073):
  the self-logged minutes, and the S-GEN-032 timestamp estimate beside them for calibration;
- the verdict mix per agent, and the stage 1->2 verdict condition (S-GEN-052, S-BA-042).

Aggregates are printed, never committed (S-GEN-012).

CLI:
  report.py --log log.jsonl [--log reviews.jsonl] [--date YYYY-MM-DD] [--tz Europe/Berlin]
            [--format text|markdown]
"""
import argparse
import datetime
import zoneinfo
from collections import Counter, defaultdict

from append_run_log import load_logs
from common import HarnessError, run_main

GATE_MINUTES = 60          # S-GEN-073 starting value
GATE_WORKING_DAYS = 10     # S-GEN-073 starting value
CAP_C, IDLE_F = 30, 10     # S-GEN-032 starting values, until calibrated
PROMOTION_VERDICTS = 20    # S-GEN-052 stage 1->2
PROMOTION_PRECISION = 0.70
VERDICT_COLUMNS = ("accepted", "edited", "rejected")


def ts(text):
    return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))


def money(x):
    return f"${x:.2f}"


def mins(x):
    return "n/a" if x is None else (f"{x:.0f}" if float(x).is_integer() else f"{x:.1f}")


def pct(num, den):
    return "n/a" if not den else f"{100 * num / den:.0f}%"


class Doc:
    """Markdown or aligned plain text, from the same calls."""

    def __init__(self, fmt):
        self.md, self.lines = fmt == "markdown", []

    def heading(self, text, level=2):
        if self.md:
            self.lines += [f"{'#' * level} {text}", ""]
        else:
            self.lines += [text, ("=" if level == 1 else "-") * len(text), ""]

    def para(self, text):
        self.lines += [text, ""]

    def bullets(self, items):
        self.lines += [f"- {i}" for i in items] + [""]

    def table(self, headers, rows):
        rows = [[str(c) for c in r] for r in rows]
        if not rows:
            self.para("(none)")
            return
        if self.md:
            self.lines.append("| " + " | ".join(headers) + " |")
            self.lines.append("| " + " | ".join("---" for _ in headers) + " |")
            self.lines += ["| " + " | ".join(r) + " |" for r in rows]
        else:
            widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
            fmt = "  ".join(f"{{:<{w}}}" for w in widths)
            self.lines += [fmt.format(*headers).rstrip(), fmt.format(*("-" * w for w in widths))]
            self.lines += [fmt.format(*r).rstrip() for r in rows]
        self.lines.append("")

    def text(self):
        return "\n".join(self.lines).rstrip() + "\n"


class Data:
    def __init__(self, entries, tz):
        self.tz = tz
        self.runs = {e["run_id"]: e for e in entries if e["record_kind"] == "agent_run"}
        self.reviews = sorted((e for e in entries if e["record_kind"] == "verdict_update"),
                              key=lambda e: e["verdict_at"])
        self.estimates = self._estimates()

    def day(self, text):
        return ts(text).astimezone(self.tz).date()

    def agent(self, review):
        run = self.runs.get(review["run_id"])
        return run["agent"] if run else "(unmatched)"

    def _estimates(self):
        """S-GEN-032 per review event: elapsed = verdict_at - max(previous review event, item ready);
        if elapsed > C, count F when the item was ready before the previous event, else C.
        Item ready = the run's created_at. Unmatched reviews have no estimate."""
        out, prev = {}, defaultdict(lambda: None)
        for r in self.reviews:
            at, before = ts(r["verdict_at"]), prev[r["verdict_by"]]
            run = self.runs.get(r["run_id"])
            est = None
            if run:
                ready = ts(run["created_at"])
                start = max(ready, before) if before else ready
                elapsed = max((at - start).total_seconds() / 60, 0)
                if elapsed <= CAP_C:
                    est = round(elapsed, 1)
                else:
                    est = IDLE_F if before and ready < before else CAP_C
            out[id(r)] = est
            prev[r["verdict_by"]] = at
        return out

    def runs_on(self, days):
        return [r for r in self.runs.values() if self.day(r["created_at"]) in days]

    def reviews_on(self, days):
        return [r for r in self.reviews if self.day(r["verdict_at"]) in days]

    def minutes(self, days):
        rs = self.reviews_on(days)
        ests = [self.estimates[id(r)] for r in rs]
        return sum(r["review_minutes"] for r in rs), sum(e for e in ests if e is not None), ests.count(None)


def result(run):
    return "pass" if run["validation"]["ok"] else (run["validation"]["reason"] or run["status"])


def cost(runs):
    known = [r["cost_usd"] for r in runs if r["cost_usd"] is not None]
    return sum(known), len(runs) - len(known)


def outputs(review):
    """Verdicted outputs of one review: one per item if items are given, else the run (S-BA-042)."""
    if review["items"]:
        return list(review["items"].values())
    return [review["human_verdict"]] if review["human_verdict"] else []


def run_section(doc, data, days, label):
    runs = data.runs_on(days)
    total, unknown = cost(runs)
    passed = sum(1 for r in runs if r["validation"]["ok"])
    doc.para(f"Runs: {len(runs)}, passed {passed}, failed {len(runs) - passed}. Cost: {money(total)}"
             + (f" ({unknown} run(s) with unknown cost)" if unknown else "") + ".")
    by = Counter((r["agent"], result(r)) for r in runs)
    doc.table(["Agent", "Result (reason code)", "Runs"],
              [[a, res, n] for (a, res), n in sorted(by.items(), key=lambda kv: (kv[0][0], kv[0][1] != "pass", kv[0][1]))])
    if label == "week":
        per_agent = defaultdict(list)
        for r in runs:
            per_agent[r["agent"]].append(r)
        rows = []
        for a, rs in sorted(per_agent.items()):
            c, _ = cost(rs)
            rows.append([a, len(rs), money(c), money(c / len(rs))])
        doc.table(["Agent", "Runs", "Cost", "Per run"], rows)


def verdict_table(doc, data, reviews, runs):
    mix = defaultdict(Counter)
    for r in reviews:
        mix[data.agent(r)][r["human_verdict"] or "time only"] += 1
    reviewed = {r["run_id"] for r in data.reviews if r["run_id"]}
    for run in runs:
        if run["status"] == "completed" and run["run_id"] not in reviewed:
            mix[run["agent"]]["awaiting review"] += 1
    cols = (*VERDICT_COLUMNS, "time only", "awaiting review")
    doc.table(["Agent", *cols], [[a, *(mix[a][c] for c in cols)] for a in sorted(mix)])


def report(entries, day, tz, fmt):
    data = Data(entries, tz)
    doc = Doc(fmt)
    week = [day - datetime.timedelta(days=i) for i in range(6, -1, -1)]
    doc.heading(f"Staff report: {day.isoformat()} ({tz.key})", 1)

    doc.heading(f"Day {day.isoformat()}")
    run_section(doc, data, {day}, "day")
    logged, est, unest = data.minutes({day})
    state = "over" if logged > GATE_MINUTES else "within"
    doc.para(f"Review minutes: {mins(logged)} logged, {state} the {GATE_MINUTES}-minute gate. "
             f"S-GEN-032 estimate: {mins(est)}" + (f" ({unest} unmatched review(s) not estimated)" if unest else "") + ".")
    verdict_table(doc, data, data.reviews_on({day}), data.runs_on({day}))

    doc.heading(f"Week {week[0].isoformat()} to {day.isoformat()}")
    run_section(doc, data, set(week), "week")
    rows = []
    for d in week:
        runs = data.runs_on({d})
        c, _ = cost(runs)
        lg, es, _ = data.minutes({d})
        rows.append([f"{d.isoformat()} {d.strftime('%a')}", len(runs), sum(1 for r in runs if not r["validation"]["ok"]),
                     money(c), mins(lg), mins(es), "OVER" if lg > GATE_MINUTES else "ok"])
    doc.table(["Day", "Runs", "Failed", "Cost", "Review min", "S-GEN-032 est.", f"Gate {GATE_MINUTES}"], rows)
    verdict_table(doc, data, data.reviews_on(set(week)), data.runs_on(set(week)))

    doc.heading("Rollout gate (S-GEN-073)")
    working, d = [], day
    while len(working) < GATE_WORKING_DAYS:
        if d.weekday() < 5:
            working.append(d)
        d -= datetime.timedelta(days=1)
    lg, es, _ = data.minutes(set(working))
    avg = lg / GATE_WORKING_DAYS
    doc.para(f"Average logged review minutes over the last {GATE_WORKING_DAYS} working days "
             f"({working[-1].isoformat()} to {working[0].isoformat()}, days without reviews count as 0): "
             f"{mins(round(avg, 1))} ({'met' if avg <= GATE_MINUTES else 'not met'}, gate <= {GATE_MINUTES}). "
             f"S-GEN-032 estimate: {mins(round(es / GATE_WORKING_DAYS, 1))}. The estimate's C and F are "
             f"uncalibrated starting values ({CAP_C} and {IDLE_F} min) until a self-timed week is fitted.")

    doc.heading("Stage 1 to 2 verdict condition (S-GEN-052)")
    per_agent = defaultdict(list)
    for r in data.reviews:
        if r["run_id"] in data.runs and ts(r["verdict_at"]).astimezone(tz).date() <= day:
            per_agent[data.agent(r)].extend(outputs(r))
    rows = []
    for a, outs in sorted(per_agent.items()):
        last = outs[-PROMOTION_VERDICTS:]
        ok = len(outs) >= PROMOTION_VERDICTS and last.count("accepted") / len(last) >= PROMOTION_PRECISION
        rows.append([a, f"{len(outs)}/{PROMOTION_VERDICTS}", pct(last.count("accepted"), len(last)),
                     "met" if ok else "not met"])
    doc.table(["Agent", "Verdicts", "Output precision, last 20", "Verdict condition"], rows)
    doc.para("Output precision counts accepted outputs only: an edited draft is not confirmed (S-BA-042). "
             "The eval-score half of the stage 1 to 2 rule is not covered here.")

    unmatched = [r for r in data.reviews_on(set(week)) if r["run_id"] not in data.runs]
    if unmatched:
        doc.para(f"{len(unmatched)} review(s) this week matched no run in the log; their minutes still count.")
    return doc.text()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", action="append", required=True, help="outcome-store JSONL, repeatable")
    ap.add_argument("--date", help="report day, YYYY-MM-DD (default: today in --tz)")
    ap.add_argument("--tz", default="UTC", help="IANA time zone for day boundaries, e.g. Europe/Berlin")
    ap.add_argument("--format", choices=["text", "markdown"], default="text")
    args = ap.parse_args()
    try:
        tz = zoneinfo.ZoneInfo(args.tz)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        raise HarnessError("log_invalid", f"unknown time zone {args.tz}") from None
    try:
        day = datetime.date.fromisoformat(args.date) if args.date else datetime.datetime.now(tz).date()
    except ValueError:
        raise HarnessError("log_invalid", "--date must be YYYY-MM-DD") from None
    print(report(load_logs(args.log), day, tz, args.format), end="")


if __name__ == "__main__":
    run_main(main)
