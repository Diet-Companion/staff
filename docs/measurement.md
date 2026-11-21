# Measurement (lean slice)

What staff records about each agent run and each human review, where it is kept, how the human logs review time, and how to read the numbers. It covers the run record and outcome store (S-GEN-029, S-GEN-031), the review-minutes metric and the 60-minute gate (S-GEN-032, S-GEN-073), and the verdicts that promotion needs (S-GEN-050, S-GEN-052, S-BA-042).

## What is recorded

The store holds two kinds of entry, both defined by [`harness/schemas/run-log-entry.schema.json`](../harness/schemas/run-log-entry.schema.json). Every string in them is pattern-bound: IDs, hashes, counts, fixed reason codes and URLs. No model, tracker or human free text is stored (S-SEC-004).

| Kind | Written by | When | Holds |
| --- | --- | --- | --- |
| `agent_run` | [`run_record.py`](../harness/run_record.py), appended by [`append_run_log.py`](../harness/append_run_log.py) | Once per run, after the write stage, even when the run failed (G5) | The run record unchanged: run ID, agent, stage, area, status, outcome, `validation.reason`, model, staff and product SHAs, trigger, input hash, comment URLs, cost, turns, duration, BA role fields (S-BA-039). Plus `log_version` and `logged_at` |
| `verdict_update` | [`log_review.py`](../harness/log_review.py), appended by `append_run_log.py` | Once per `/review` comment from an operator | The reviewed run, the self-logged review minutes, the verdict (`accepted`, `edited`, `rejected` or none), optional per-item verdicts, who and when, and the comment URL |

A new run-record field must be added to the schema first. Otherwise the append fails closed, and a test (`test_run_record_output_is_a_valid_entry`) catches the mismatch.

**Verdicts.** These are the S-BA-042 meanings, and what S-GEN-052's output precision needs:
- `accepted`: taken without changing the structured fields of its ACs or rule. Only this counts as confirmed.
- `edited`: taken after the human changed it. It counts as a verdict, but not as confirmed.
- `rejected`: not taken.

So output precision is accepted / (accepted + edited + rejected). S-GEN-071's labels map as `verdict:confirmed` = accepted and `verdict:rejected` = rejected. `edited` has no S-GEN-071 label yet. A review with no verdict, such as answering a question batch, still logs its minutes.

## Where it lives

**The outcome store is one issue per month in the product repo**, titled `Staff outcome store YYYY-MM` and labelled `staff:log`, with one comment per entry. Each comment carries a marker and the entry as one line of JSON, so the store reads as JSONL. `append_run_log.py append` creates the month's issue when it is missing. `append_run_log.py export` reads every store issue back into a JSONL file.

Why here, and not a JSONL file on a `staff-log` branch:
- **S-GEN-012 keeps run records out of Git.** Concurrent appends conflict, and a missed redaction would stay in history for good. Issue comments are not Git. They never conflict, and each one can be deleted per `run_id` (S-DATA-008).
- **No `contents: write`.** A branch store needs a workflow token that can push to the product repo. The comment store needs only `issues: write` on the workflow's own `GITHUB_TOKEN`.
- **It survives artifact expiry.** The 90-day workflow artifacts stay as they are, as the per-run copy. S-DATA-007 keeps run records for the life of the project, and asks for them to be moved out of CI artifacts before those expire. This is that move, until a small database replaces it (S-GEN-010).
- **Same host, same region.** The data stays on the code host that already holds the artifacts and the tickets (S-DATA-003).
- **Recorder only (S-GEN-010).** Only comments by `github-actions[bot]` on issues opened by `github-actions[bot]` are read back. Anything anyone else posts there is ignored and counted. An edited entry is kept but flagged, because only the human can edit those comments.
- **Size.** At about 30 entries a day, a monthly issue holds about 900 comments. Rotating each month keeps every issue and every export small.

**Deleting a run (S-DATA-008):** find its comment in the month's issue and delete it (`gh api -X DELETE repos/<owner>/<repo>/issues/comments/<id>`), along with any `verdict_update` comment that names the same `run_id`.

## Logging review time

**Recommended: one comment on the issue or PR you reviewed.** You are already there when you finish, GitHub timestamps it, and the operator check (G12) comes for free.

```
/review <time> [accepted|edited|rejected] [run=<run_id>] [<ITEM-ID>=<verdict> ...]
```

- `<time>`: `12m`, `12`, `1h` or `1h30m`. That is the time you spent on this review, from 1 to 480 minutes.
- **Verdict:** optional. `accept`, `edit` and `reject` also work.
- **`run=`:** the `Staff-Run-Id` from the Analyst comment's footer. Leave it out to mean the latest completed run on this issue before your comment.
- **Item verdicts:** one per draft (S-BA-042), for example `REQ-002=edited`. Given alone, they set the run verdict: all accepted gives accepted, all rejected gives rejected, and anything else gives edited.
- **Only the first line counts.** Notes on later lines are for people and are never stored.
- **Confirmation:** the recorder reacts 👍 when the entry is stored. It reacts 😕 when nothing was stored, for a typo, a non-operator, or an unparsable line; see the job log, then post a corrected comment.

Examples:

```
/review 12m accepted
/review 25m REQ-001=accepted REQ-002=edited REQ-003=accepted
/review 8m                      (answered a question batch, no verdict)
/review 1h rejected run=1234567890-1
```

`/review` comments never reach the Analyst: `build_input.py` drops them like `/analyst`.

**Fallback, local CLI:** use this when the workflow was down or you reviewed offline.

```sh
python harness/log_review.py manual <run-id> <minutes> [verdict] --by <your-login> \
  --operators governance/operators.yml --at 2026-11-21T10:30:00Z --log log.jsonl --out review.json
python harness/append_run_log.py append --entry review.json --jsonl reviews.jsonl
```

Pass `reviews.jsonl` to the report as a second `--log`. It stays a local file: entries you post to the store issue under your own account are ignored on export, by design.

**How the minutes are used.** The S-GEN-032 metric derives minutes from timestamps, capped at C = 30 and with F = 10 for idle gaps. Both values must be fitted once against a week in which the human times their own reviews, before the metric gates a rollout (S-GEN-073). The `/review` minutes are that self-timed data. The report prints both side by side, so the human can fit C and F and then decide which one gates.

## Running the report

```sh
gh auth status                                   # your token needs issue read access to the product repo
python harness/append_run_log.py export --repo Diet-Companion/diet-companion --out log.jsonl
python harness/report.py --log log.jsonl --format markdown --tz Europe/Berlin   # or --format text
python harness/report.py --log log.jsonl --date 2026-11-20                      # a past day
```

It prints sections for the day and for the 7 days ending on it:
- runs, pass or fail per reason code, and cost, per agent;
- review minutes per day, logged and S-GEN-032-estimated, against the 60-minute gate;
- the verdict mix per agent, with runs still awaiting a review;
- the S-GEN-073 gate, as the average over the last 10 working days, counting days without reviews as 0;
- the S-GEN-052 verdict condition: at least 20 verdicts and output precision of at least 70% over the last 20. The eval-score half of that rule isn't covered.

The Markdown output pastes into an issue as it is. The report is printed, never committed (S-GEN-012). `--tz` sets the day boundaries, and the default is UTC.

## Product-workflow changes (human-authored, not yet applied)

These go into `diet-companion`. Only the human edits product workflows (S-GEN-025). Pin `STAFF_SHA` to the staff commit that contains these scripts.

**Permissions needed:** `issues: write` on the workflow's `GITHUB_TOKEN`, in two jobs: `record` and `record-review`. That covers reading the store, opening the monthly issue, appending comments and reacting to `/review`. **No `contents: write` anywhere.** The Analyst App token is unchanged and never touches the store. The report workflow needs only `issues: read`.

**One-time setup:** create the label, so the monthly issues can carry it:

```sh
gh label create staff:log --repo Diet-Companion/diet-companion --color 5319e7 \
  --description "Staff outcome store: written by the recorder only"
```

### 1. `staff-analyst.yml`: add a `record` job after `write`

```yaml
  # Recorder (S-GEN-026, S-GEN-031). Appends the run record to the outcome store, an issue per month
  # in this repo (docs/measurement.md in staff). Holds only the workflow token, with issues: write.
  # Never the Analyst App token. Runs even when read or write failed (G5).
  record:
    needs: [gate, read, write]
    if: always() && needs.gate.outputs.allowed == 'true'
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    permissions:
      issues: write
    steps:
      - name: Fetch the staff harness at the pinned commit
        run: |
          set -euo pipefail
          git init -q staff
          git -C staff fetch -q --depth 1 "https://github.com/${STAFF_REPO}.git" "$STAFF_SHA"
          git -C staff checkout -q FETCH_HEAD
          [ "$(git -C staff rev-parse HEAD)" = "$STAFF_SHA" ]
          echo "WORK=$RUNNER_TEMP/analyst" >> "$GITHUB_ENV"

      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0
        with:
          python-version: "3.12"
      - name: Install pinned harness dependencies (S-SEC-009)
        run: python -m pip install --no-deps --only-binary ':all:' -r staff/harness/requirements.txt

      - name: Download the run record
        continue-on-error: true
        uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8.0.2
        with:
          name: analyst-run-${{ github.run_id }}-${{ github.run_attempt }}
          path: ${{ runner.temp }}/analyst

      - name: Append the run record to the outcome store (S-GEN-029)
        env:
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
          TRIGGER_TYPE: ${{ github.event_name == 'issue_comment' && 'comment' || 'label' }}
          TRIGGER_REF: ${{ github.repository }}#${{ github.event.issue.number }}
          ATTEMPT: ${{ github.run_attempt }}
        run: |
          set -euo pipefail
          mkdir -p "$WORK"
          if [ ! -s "$WORK/run-record.json" ]; then
            # The record was lost with the artifact: log the run anyway, as crashed / artifact_missing.
            python staff/harness/run_record.py write --out "$WORK/run-record.json" \
              --run-id "$RUN_ID" --attempt "$ATTEMPT" \
              --identity diet-companion-analyst --plugin staff-product --agent analyst --stage 1 \
              --model "$MODEL" --staff-sha "$STAFF_SHA" --product-sha unknown \
              --trigger-type "$TRIGGER_TYPE" --trigger-ref "$TRIGGER_REF" \
              --plugins-root staff/plugins --reason artifact_missing
          fi
          python staff/harness/append_run_log.py append --record "$WORK/run-record.json" --repo "$REPO"
```

Nothing else in `staff-analyst.yml` changes. The artifacts keep their 90-day retention as the per-run copy.

### 2. New `staff-review-log.yml`: record `/review` comments

```yaml
# Staff review log (S-GEN-032, S-GEN-071). HUMAN-AUTHORED (S-GEN-025).
# The operator logs a review with a comment: /review <time> [accepted|edited|rejected] [run=<id>] [ITEM=verdict ...]
# The recorder checks the author against staff governance/operators.yml (G12), appends a verdict_update entry
# to the outcome store, and reacts: +1 stored, confused not stored. It never checks out product code, and
# comment text reaches scripts only through the event file, never through ${{ }} in a script.
name: staff-review-log

on:
  issue_comment:
    types: [created]

permissions: {}

env:
  STAFF_SHA: <the same pin as staff-analyst.yml>
  STAFF_REPO: Diet-Companion/staff

jobs:
  record-review:
    if: >-
      github.event.comment.user.type == 'User' &&
      (github.event.comment.body == '/review' || startsWith(github.event.comment.body, '/review '))
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    permissions:
      issues: write
    concurrency:
      group: staff-review-log
      cancel-in-progress: false
    steps:
      - name: Fetch the staff harness at the pinned commit
        run: |
          set -euo pipefail
          git init -q staff
          git -C staff fetch -q --depth 1 "https://github.com/${STAFF_REPO}.git" "$STAFF_SHA"
          git -C staff checkout -q FETCH_HEAD
          [ "$(git -C staff rev-parse HEAD)" = "$STAFF_SHA" ]
          echo "WORK=$RUNNER_TEMP/review" >> "$GITHUB_ENV"

      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0
        with:
          python-version: "3.12"
      - name: Install pinned harness dependencies (S-SEC-009)
        run: python -m pip install --no-deps --only-binary ':all:' -r staff/harness/requirements.txt

      - name: Record the review
        id: review
        env:
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
        run: |
          set -euo pipefail
          mkdir -p "$WORK"
          since=$(date -u -d "$(date -u +%Y-%m-01) -1 day" +%Y-%m)   # this month and last, to find the run
          python staff/harness/append_run_log.py export --repo "$REPO" --since "$since" --out "$WORK/log.jsonl"
          python staff/harness/log_review.py comment --event "$GITHUB_EVENT_PATH" \
            --operators staff/governance/operators.yml --log "$WORK/log.jsonl" --out "$WORK/review.json"
          python staff/harness/append_run_log.py append --entry "$WORK/review.json" --repo "$REPO"

      - name: React to the command
        if: always()
        env:
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
          COMMENT_ID: ${{ github.event.comment.id }}
          OUTCOME: ${{ steps.review.outcome }}
        run: |
          content=confused
          [ "$OUTCOME" = success ] && content=+1
          gh api -X POST "repos/$REPO/issues/comments/$COMMENT_ID/reactions" -f content="$content" > /dev/null
```

Comments that the workflow token posts don't trigger workflows, so the store's own comments never start this job.

### 3. Optional `staff-report.yml`: the report in the job summary

```yaml
# Staff report (S-GEN-032). HUMAN-AUTHORED. Read-only.
name: staff-report
on:
  workflow_dispatch:
    inputs:
      date:
        description: "Report day, YYYY-MM-DD (default: today)"
        required: false
permissions: {}
env:
  STAFF_SHA: <the same pin as staff-analyst.yml>
  STAFF_REPO: Diet-Companion/staff
jobs:
  report:
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    permissions:
      issues: read
    steps:
      - name: Fetch the staff harness at the pinned commit
        run: |
          set -euo pipefail
          git init -q staff
          git -C staff fetch -q --depth 1 "https://github.com/${STAFF_REPO}.git" "$STAFF_SHA"
          git -C staff checkout -q FETCH_HEAD
      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0
        with:
          python-version: "3.12"
      - run: python -m pip install --no-deps --only-binary ':all:' -r staff/harness/requirements.txt
      - name: Report
        env:
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
          DATE: ${{ inputs.date }}
          REPORT_TZ: ${{ vars.STAFF_REPORT_TZ || 'UTC' }}
        run: |
          set -euo pipefail
          python staff/harness/append_run_log.py export --repo "$REPO" --out log.jsonl
          python staff/harness/report.py --log log.jsonl ${DATE:+--date "$DATE"} --tz "$REPORT_TZ" \
            --format markdown >> "$GITHUB_STEP_SUMMARY"
```

## Not covered yet

- **Verdict labels and digest checkboxes** (S-GEN-071). Only `/review` comments are captured. The label-strip job doesn't exist yet.
- **Merge and close as verdicts** for stage-2 PRs. `/review` on a PR works today, but the merge itself isn't recorded.
- **Timing records** for labelling batches and interview turns (S-GEN-031).
- **`ops_event` and `check_outcome` records.** These come with the ops jobs and the BA checks (S-BA-054).
- **`skipped_by_switch` records.** A gate denial posts nothing and writes no record.
- **The cost job, the stage job and the daily digest** (S-GEN-058, S-GEN-050, S-GEN-063). They will read this same store.
