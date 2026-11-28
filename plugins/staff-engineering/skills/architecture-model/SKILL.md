---
name: architecture-model
description: Architecture artifact model for ARCH agents (Architect, arch-upkeep). Covers what counts as truth, the artifact types and IDs (ADR-n, ADR-n/C-k, CMP-n, IF-n@x.y.z, QAS-n), the product-repo paths, the lifecycles, the new-ID rule, the human-owned fields and each agent's path scope. Use on every ARCH run, before drafting or patching any architecture artifact.
---

# Architecture model (S-ARCH-004, -005, -011 to -014, -020, -024, -035, -036, -046)

Source: `docs/strategy/roles/architect.md`, the always-loaded part. The field rules ship as the read-stage schemas in this plugin's `schemas/` (S-ARCH-036). Where this skill and a schema differ, the schema is what the harness checks; report the difference in your `decision_summary`.

## What is truth (S-ARCH-004, S-ARCH-046)

The product repo is the single source of truth. These count as truth, each for its own version until it retires:
- merged **accepted** ADRs (and the chosen option's constraints);
- **active** components;
- **approved** or **deprecated** interface versions;
- **accepted** QAS;
- the product core (`knowledge/product-core.md`) and merged active rules (S-BA-022).

Everything else is a candidate, never an oracle: tickets, PR comments, open PRs (agent PRs too), unmerged drafts, proposed ADRs, draft versions. Cite candidates as candidates. ARCH agents never write `knowledge/**`. A rule candidate you notice goes into `advisory_notes`; the digest lists it.

## Types and IDs (S-ARCH-005)

| Artifact | ID | Notes |
| --- | --- | --- |
| Architecture decision record | `ADR-n` | One decision, 2 to 4 options |
| ADR constraint | `ADR-n/C-k` | A rule an option imposes. It applies only once that option is chosen |
| Component or boundary | `CMP-n` | Has an immutable stable `name` (S-TESTAB-005) |
| Interface; a version | `IF-n`; `IF-n@x.y.z` | API, event or data contract. Its spec holds the operation, error and event names |
| Quality-attribute scenario | `QAS-n` | The architectural answer to one quality REQ |
| Architecture overview | none | Bounded prose in named sections |

IDs are allocated, padded and checked as in S-BA-005: at least three digits, in sequence per product, never reused. To pick the next number, Glob the existing files on `main` (for example `architecture/**/adr/ADR-*.md`) and add one. At stage 1 your IDs are provisional.

## Paths in the product repo (S-ARCH-013)

| Artifact | Path |
| --- | --- |
| Overview | `architecture/overview.md` |
| ADR | `architecture/<area>/adr/ADR-n.md` |
| Component | `architecture/<area>/components/CMP-n.md` |
| Interface | `architecture/<area>/interfaces/IF-n.md`, one spec file per version under `architecture/<area>/interfaces/IF-n/` |
| QAS | `architecture/<area>/quality/QAS-n.md` |
| Conformance rules (S-ARCH-026) | `architecture/<area>/conformance/` |

`<area>` is a key from `.staff/areas.yml`. Cross-area artifacts sit under `architecture/system/`, which `areas.yml` maps like any other path. The ADR index, component map and dependency graph are CI artifacts, never committed (S-ARCH-010).

## Lifecycles (S-ARCH-011)

Nothing is deleted.

| Artifact | States |
| --- | --- |
| ADR | `proposed` (exists only in PRs and stage-1 comments) → `accepted` or `rejected`, set by `decision.outcome` → `superseded` (a newer accepted ADR names it in `supersedes`) or `deprecated` (`deprecated_reason`) |
| Component | `proposed` → `active` → `deprecated` (new dependencies on it are violations) → `retired` (its `code_paths` match no file) |
| Interface version | `draft` (in a PR) → `approved` (merged: truth for implementation) → `deprecated` (public versions get a `sunset`) → `retired`. Whether an element is implemented is derived, never stored (S-ARCH-021) |
| QAS | `draft` → `accepted` → `retired` (with `replaced_by`) |

The lifecycle check fails an ADR merged as `proposed`, and any status change made another way. You never move an artifact's status forward yourself: a new artifact you draft is `proposed` (ADR, component), `draft` (interface version, QAS); an existing one keeps its merged status, the merged status of each of its versions, and its `revision` entries unchanged and in order (append only).

## A change in meaning gets a new ID (S-ARCH-012, S-ARCH-024)

- An accepted ADR's `decision`, `drivers` and chosen option never change. A new ADR supersedes it.
- A QAS whose `measure` or `req` changes is retired and replaced.
- A component's `name` never changes. A rename retires the component and adds a new one.
- Operation, error and event names never change within a major version. A rename is breaking and needs a new major (S-ARCH-023).
- Prose edits, and adding an exception (S-ARCH-028), keep the ID.

## Human-owned fields (S-ARCH-020)

You never set these on your own authority:
- ADR `decision {outcome, chosen, decided_by}`, `superseded_reason`, `deprecated_reason`;
- `exceptions[].accepted_by`;
- QAS `gap_accepted_by`, and component `testability[].gap_accepted_by`;
- interface `compatibility_policy`; a version `sunset` earlier than S-ARCH-023 allows; `external_retired_by`; `provenance_confirmed_by`;
- `accepted` and `rejected` entries in `review_dispositions`, and `review_waiver`;
- sign-offs on flagged diffs (S-ARCH-053).

Leave them `null` (or absent) in drafts. Answers count as in S-BA-015: only comments from accounts in `governance/operators.yml`. You set a human-owned field only after recording the answer, and you list it in `answers_applied` with the comment ref. The owner-field check fails an agent commit that sets one without citing an operator answer.

## No invented facts (S-ARCH-014)

S-BA-012 applies to every ARCH draft. Every statement cites a source ref (REQ or AC ID, R-ID, ARCH ID, spec ref, code ref, CI result, operator comment) or an open assumption you record. Any load figure, cost or capacity that no source states is an open assumption, never a value you pick.

## Path scope (S-ARCH-035)

| Agent | Writes | Never writes |
| --- | --- | --- |
| Architect | `architecture/<area>/**` | `architecture/overview.md`, `requirements/**`, `knowledge/**`, code, CI, tests |
| `arch-upkeep` | `architecture/overview.md`; only the `code_paths` field in `architecture/*/components/**` | Everything else |

Each agent pushes only to `agent/<agent>/*` branches, and every ARCH agent commit carries a `Staff-Run-Id` trailer (S-ARCH-003, S-GEN-029). Both apply from stage 2. At stage 1 you write nothing: you draft in your read-stage JSON.

## Context (S-ARCH-036)

| Agent | Always loaded | Retrieved on demand |
| --- | --- | --- |
| Architect | Product core, overview, ARCH schemas, own learnings | Ready REQs and ACs; the area's ADRs, components, specs and QAS; code; the drift report; reviewer comments; domain plugins; the on-demand reference |
| `arch-upkeep` | Overview, component schema, own learnings | Merged PR diffs, component descriptions, the drift report |

Read only what the run needs. The on-demand reference is the skill `staff-engineering:architecture-reference` (S-ARCH-048).
