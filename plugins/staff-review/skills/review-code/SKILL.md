---
name: review-code
description: Checklist for reviewer/code, the code artifact type of the shared reviewer. Covers items CC-1 to CC-9, the product-PR block and code map it checks against, what the DEV diff checks already flag, and private reports for security findings. The harness preloads it when the target is a Developer or dev-upkeep PR, or a human PR or ticket labelled dev:review.
---

# Code checklist (reviewer/code)

Source: `docs/strategy/roles/developer.md`, S-DEV-031 and S-DEV-032. DEV owns this checklist (S-DEV-002). Output: `schemas/review-output.schema.json` with `artifact_type: code`. Item IDs are stable. A skill PR that removes or rewords a CC item is flagged (S-DEV-031).

## Run (S-DEV-005, S-DEV-006, S-DEV-021, S-GEN-057)

- **Starts when** a Developer or `dev-upkeep` PR becomes ready for review or has its review re-requested, or when an operator applies `dev:review` to a human PR, or to a ticket that holds a Developer stage-1 draft. For a ticket, set `target.kind: ticket` and `reviewed_sha: null`, and review the draft's patch artifact.
- **Write stage:** one comment, the label `dev:not-ready`, and private reports. No paths.
- **Caps:** $1 and 10 min *(starting value)*.

## What you check against

- **PR block** (S-DEV-009):
  - `kind`: feature, fix, drift, refactor or upkeep;
  - `implements_acs[] {ac, part: full | partial}` and `implements[]` (IF versions);
  - `fixes {ticket, target}`;
  - `constraints[] {id, disposition: conform | n/a, reason}`, which lists every `check: review` constraint of the accepted ADRs that the touched components cite;
  - `untested_acs[]`, `not_unit_observable`, `characterization[]`, `dependencies[]` and `flags[]`.

  `refactor` and `upkeep` PRs declare no AC and change no assertion.
- **Code map** `.staff/code.yml` (S-DEV-004), read from the base: the `source`, `unit_tests`, `generated`, `protected`, `dependency_files` and `verification_config` globs, plus the guard patterns.
- **Sources** (S-DEV-011): ready ACs (S-BA-019), active rules, approved or deprecated IF versions (each for its own version), the chosen-option constraints of accepted ADRs (S-ARCH-004), and `AGENTS.md` for the stack.
- **Testability in code** (S-DEV-013):
  - operation, error and event names come from the approved spec (S-TESTAB-005);
  - new entry points propagate the correlation ID (S-TESTAB-007);
  - flags, the clock and external services are reached only through seams (S-TESTAB-008);
  - a test-only seeding API is enabled only in test builds (S-TESTAB-004).
- **Unit-test oracle** (S-DEV-015, S-DEV-016):
  - every expected value comes from an AC, rule, test condition or approved IF version, cited with `cites: <ID>`, never from what the code under test returns;
  - a test with no source is labelled `characterization`;
  - tests use public interfaces and mock only at seams.
- **Problems go back, never into code** (S-DEV-008): a requirement problem becomes a requirement-defect item, and a design need becomes a design request. Reinterpreting a requirement in code is a CC-1 finding.

## What scripts already flag (S-DEV-018, S-DEV-028, S-QA-040, S-ARCH-027)

The code diff check flags these for sign-off: removed, skipped or expected-failure tests, removed assertions, changed guard lines (authorisation, validation, permission-deny, suppression, testability), lint suppressions, `protected` and `verification_config` changes, and dependency changes. The cited-value lint judges changed assertions in cited tests. Conformance blocks structural violations and spec mismatches. Read their outputs, and don't repeat them as findings. Your job is what they can't see, such as semantic loosening that matches no pattern (S-DEV-028).

## Checklist (S-DEV-031)

| ID | Item | Finds |
| --- | --- | --- |
| CC-1 | Requirement fit | Behaviour no declared AC asks for; an AC declared `full` but partly built; a requirement reinterpreted instead of raised (S-DEV-008) |
| CC-2 | ADR constraints | A `check: review` constraint violated, missing from `constraints[]`, or marked `n/a` without a sound reason. Cites ADR-n/C-k (S-ARCH-026) |
| CC-3 | Interfaces | Units, error semantics or security requirements that differ from the declared version where the conformance check can't see them (S-ARCH-022) |
| CC-4 | Security | A new entry point without the authorisation the AC's `permissions` need; missing input validation; injection; secret handling; a `protected` change without a reason. Exploitable weaknesses go private (S-DEV-019) |
| CC-5 | Tests and oracle | A declared AC with no citing test and no reason; an expected value read from the code under test; an unlabelled characterization test; a fix without a test that sees the defect (S-DEV-015) |
| CC-6 | Testability in code | A `provided` item of S-DEV-013 missing or broken |
| CC-7 | Data | Real personal data in fixtures or logs (S-DATA-004); production data in tests |
| CC-8 | Conventions and maintainability | `AGENTS.md` breaches, duplication, dead code, swallowed errors |
| CC-9 | Dependencies | A dependency without a reason, outside an ADR technology constraint, or a service that may fail S-DATA-006 |

## Output specifics (S-DEV-032)

- **Findings** carry `suggestion`: the change you suggest.
- **Finding ID:** `CC-n|<file>#<symbol>|<primary cited ID>`, for example `CC-2|src/orders/service.ts#createOrder|ADR-002/C-1`. The primary cited ID is the AC, constraint, IF version or S-ID the finding rests on.
- **`classification`:** `conflicts` for a CC-2 violation of an accepted ADR constraint, and `issue` for everything else.
- **`private_reports`** (S-DEV-019, S-SEC-011): a suspected vulnerability or exposed secret goes here, never into a finding. It holds the checklist ID (usually CC-4), the location, what you suspect and the cited IDs, and refers to a secret by location, never by value. To make it count toward `not_ready`, add a blocker finding that names only the location and says "details withheld (S-SEC-011)".
- **Questions:** S-BA-014 form, for implementation trade-offs that no rule, AC or ADR decides (S-DEV-008).

## Prerequisites and retrieval (S-DEV-023, S-DEV-035)

- **Prerequisite:** the area's ADRs and specs (S-TESTAB-006). Without them, CC-2 and CC-3 check only within the PR, and `decision_summary` says so.
- **Always:** this checklist and `AGENTS.md`.
- **On demand:**
  - the diff and the PR block;
  - the declared ACs and rules;
  - the cited ADRs, IF versions and components;
  - the check outputs.

  S-DEV-019 and S-DEV-028, which S-DEV-026 has this reviewer retrieve, are condensed above.
