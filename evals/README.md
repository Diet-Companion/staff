# Evals

Eval tasks and the runner for stage promotion (S-GEN-052). The first set is the Developer's **promotion
set** (S-DEV-036): 10 tasks, 5 feature, 3 fix, 2 trap, written by the seeding agent and held in
`staff-evals-private`. Nobody reads them before scoring: not the operator, not whoever tunes the Developer
(S-GEN-038). Only aggregates leave the private repo (S-GEN-065).

## Task format

`schemas/developer-task.schema.json`. One JSON file per task, named by its opaque ID:

| Field | Seen by the Developer | What it is |
| --- | --- | --- |
| `base_sha` | as a plain tree, no history | the pinned product commit (S-GEN-043) |
| `ticket` | yes | the `dev:implement` or `dev:fix` ticket, authored by an operator |
| `overlay` | yes | files on top of the base: new requirements and interface versions, or the seeded bug |
| `reference` | no | the reference implementation (feature) or correction (fix) |
| `heldout` | no | API tests put in `tests/api/heldout/` at scoring: acceptance tests or the symptom check |
| `trap` | no | the planted defect's key: (AC, defect kinds) or (AC, design needs) |
| `heldout_count` | no | held-out tests passing on the reference, set by the validity check |

## Seeding (`seed.yml` in staff-evals-private)

1. **seed** (model token only): `seed_task.py request`, then the seeding agent
   (`plugins/staff-meta/agents/seeder-developer.md`, read-only tools) on the product at the pinned commit,
   then `seed_task.py assemble`.
2. **check** (no secrets, throwaway PostgreSQL): `seed_check.py`. Readiness on base + overlay; for feature
   and fix tasks, the base is green and every held-out test fails on it, and base + overlay + reference is
   green with every held-out test passing (S-GEN-067).
3. **store** (contents write on the private repo): commits the task. A refused task is retried with the
   check's failure codes, at most 3 rounds per slot.

## Scoring (`eval.yml` in staff-evals-private)

1. **agent**, per task: builds the tree the Developer sees (`eval_task.py materialize --layers overlay`)
   and a synthetic ticket event, deletes the task file, then runs the Developer exactly as
   `staff-developer.yml`'s read stage does.
2. **score**, per task (no secrets): `eval_score.py`. The existing unit and API tests on base and head, the
   held-out tests on the head, and for fix tasks the agent's own tests on the seeded and the corrected
   version. The result is final (S-GEN-041).
3. **aggregate**: `eval_aggregate.py` writes the totals: the five S-DEV-036 metrics against their
   thresholds, hard-limit breaches, statuses and cost. Promotion needs two consecutive passing runs.

Not checked yet: the S-DEV-018 flags a task doesn't expect, and test citations (both hard limits in
S-DEV-036); the maintainability judge (reported, not gating).
