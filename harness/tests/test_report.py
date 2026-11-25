import datetime
import os
import tempfile
import unittest
import zoneinfo

from helpers import fixture, run_cli

import report as rp
from append_run_log import dedupe, load_logs

LOG = fixture("run-log.jsonl")
UTC = zoneinfo.ZoneInfo("UTC")
DAY = datetime.date(2026, 11, 20)


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.entries = load_logs([LOG])
        self.data = rp.Data(self.entries, UTC)

    def test_s_gen_032_estimates(self):
        est = {r["source"]["ref"][-4:]: self.data.estimates[id(r)] for r in self.data.reviews}
        self.assertEqual(est, {
            "9001": 20.0,  # 20 min after the run: counted as elapsed
            "9002": 30,    # 2 h after a run that was ready after the previous review: C
            "9003": 15.0,
            "9004": 10,    # 75 min, but the run was ready before the previous review: idle, F
            "9005": None,  # unmatched: no item-ready time
        })

    def test_minutes_per_day(self):
        self.assertEqual(self.data.minutes({DAY}), (67, 25.0, 1))
        self.assertEqual(self.data.minutes({datetime.date(2026, 11, 17)}), (25, 30, 0))

    def test_text_report(self):
        text = rp.report(self.entries, DAY, UTC, "text")
        for expected in (
            "Runs: 3, passed 2, failed 1. Cost: $1.10 (1 run(s) with unknown cost).",
            "Review minutes: 67 logged, over the 60-minute gate. S-GEN-032 estimate: 25 (1 unmatched",
            "Runs: 7, passed 5, failed 2. Cost: $6.16",
            "analyst  cost_cap              1",
            "2026-11-20 Fri  3     1       $1.10  67          25              OVER",
            "2026-11-16 Mon  1     0       $0.31  8           20              ok",
            "last 10 working days (2026-11-09 to 2026-11-20, days without reviews count as 0): 10 (met",
            "analyst  5/20      60%                        not met",
            "1 review(s) this week matched no run in the log",
        ):
            self.assertIn(expected, text)
        self.assertNotIn("|", text)

    def test_verdict_mix_per_agent(self):
        text = rp.report(self.entries, DAY, UTC, "markdown")
        week = text.split("## Week")[1].split("## Rollout")[0]
        # accepted, edited, rejected, time only, awaiting review (205-1)
        self.assertIn("| analyst | 1 | 1 | 1 | 1 | 1 |", week)
        self.assertIn("| (unmatched) | 0 | 0 | 0 | 1 | 0 |", week)

    def test_markdown_report(self):
        text = rp.report(self.entries, DAY, UTC, "markdown")
        self.assertTrue(text.startswith("# Staff report: 2026-11-20 (UTC)\n"))
        self.assertIn("## Day 2026-11-20", text)
        self.assertIn("| Agent | Result (reason code) | Runs |\n| --- | --- | --- |", text)
        self.assertIn("| analyst | schema_invalid | 1 |", text)
        self.assertIn("| analyst | 5/20 | 60% | not met |", text)

    def test_time_zone_moves_day_boundaries(self):
        # In Honolulu (UTC-10) the 08:00Z and 09:00Z runs fall on 2026-11-19; only 205-1 (13:00Z) stays.
        text = rp.report(self.entries, DAY, zoneinfo.ZoneInfo("Pacific/Honolulu"), "text")
        self.assertIn("Runs: 1, passed 1, failed 0. Cost: $0.00 (1 run(s) with unknown cost).", text)

    def test_promotion_condition_met(self):
        entries = list(self.entries)
        base = next(e for e in entries if e["record_kind"] == "verdict_update" and e["human_verdict"] == "accepted")
        for i in range(20):
            entries.append(dict(base, verdict_at=f"2026-11-20T11:{i:02d}:00Z",
                                source={"type": "comment", "ref": f"https://github.com/example/shop/issues/9#c{i}"}))
        text = rp.report(dedupe(entries), DAY, UTC, "markdown")
        self.assertIn("| analyst | 25/20 | 100% | met |", text)

    def test_empty_log_and_cli(self):
        d = tempfile.mkdtemp()
        empty = os.path.join(d, "empty.jsonl")
        open(empty, "w").close()
        proc = run_cli("report.py", "--log", empty, "--date", "2026-11-20")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Runs: 0, passed 0, failed 0. Cost: $0.00.", proc.stdout)
        proc = run_cli("report.py", "--log", LOG, "--log", empty, "--date", "2026-11-20", "--format", "markdown")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("| analyst | 5/20 | 60% | not met |", proc.stdout)
        proc = run_cli("report.py", "--log", LOG, "--tz", "Mars/Olympus")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
