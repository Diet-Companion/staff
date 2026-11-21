---
name: review-tests
description: Checklist for reviewer/tests, the tests artifact type of the shared reviewer. Covers items TR-1 to TR-9, the oracle and citation rules it checks against, what the QA checks already flag, the healer rows and survivor categories. The harness preloads it when the target is a test-gen or ci-healer PR, or a human PR touching test paths labelled qa:review.
---

# Test checklist (reviewer/tests)

Source: `docs/strategy/roles/test-engineer.md`, S-QA-043 and S-QA-044, with the QA checks (S-QA-040 to S-QA-042) that S-QA-020 puts in this pack. QA owns this checklist (S-QA-002). Output: `schemas/review-output.schema.json` with `artifact_type: tests`. Item IDs are stable, and the checklist diff check protects them (S-QA-040).

Your main job is one that no script can do: check that each expected value matches its cited source (S-QA-002).

## Run (S-QA-013, S-QA-014, S-QA-044, S-GEN-057)

- **Starts when** a `test-gen-*` or `ci-healer` PR outside the stage-3 lane becomes ready for review or has its review re-requested, or when an operator applies `qa:review` to a human PR that touches test paths.
- **Write stage:** one comment and the label `qa:not-ready`. No paths. There are no private reports for this type: see the agent's limits.
- **Caps:** $1 and 10 min *(starting value)*.

## What you check against

- **Oracle rule** (S-QA-006). Every expected value comes from a source cited by ID: a ready AC, an active rule, a test condition, an approved or deprecated IF version (for its own version), or the `measure` of an accepted QAS. It never comes from what the code returns or the page shows. Candidates are never an oracle. A test with no source is labelled `characterization`. So are tool-generated tests, recorded traffic, and tests of an `as-built` version until `provenance_confirmed_by` is set. Characterization tests never count toward coverage.
- **Citation form v1** (S-QA-007, S-DEV-016). The `cites:` token, or `characterization`. The accepted IDs are:
  - `REQ-n/AC-m`;
  - `R-n`;
  - `REQ-n/AC-m/TC-k`;
  - `IF-n@x.y.z#<element>`;
  - `QAS-n`.

  Tests are keyed by test ID v1 (S-QA-008).
- **Citable status** (S-QA-010). An AC is citable when it is ready and not affected by a `changed` requirement. So are active rules, approved or deprecated versions, and accepted QAS. A declared rule change is a `changes[]` entry with `accepted_by` set. Free-text notes never count.
- **Cited values are frozen** (S-QA-009). A value changes only with its source: the ID retires with a replacement, or a newer IF version arrives. A cited test that fails on its product PR stays, with a strict expected-failure marker, and becomes a suspected product issue. It never gets a changed value.
- **Layers and paths** (S-QA-004, S-QA-005). Unit, API contract, API behaviour, UI journeys (core journeys only), and characterization. `.staff/tests.yml` sets the paths, the locator policy, mocks, request documents, fixtures and the mutation tool. QA never touches `source` paths (S-QA-014).
- **Healer rows** (S-QA-028). Row c (`qa:test-issue`): only locators, timing, or DOM or response structure changed; for unit tests, only a refactor. Asserted values and visible state still match the reference run. Row x (`qa:fix-landed`): a strict expected-failure passes, and its defect is fixed; the heal only removes the marker. A heal PR is valid only for rows c and x (S-QA-030).
- **Survivors** (S-QA-037). Each counted mutation survivor is `equivalent` (from `equivalence-filter`), or `out_of_scope` or `accepted_gap` (from the generator, with a reason). The decision summary lists every category.

## What scripts already flag (S-QA-040 to S-QA-042)

These checks block agent PRs and only report on human PRs. Every flagged diff needs an operator sign-off (G3). Read their outputs, and don't repeat them as findings:
- **assertion diff:** a removed, skipped or newly expected-failure test; a removed assertion line; a net decrease in assertion lines; a matcher moved to a weaker class;
- **cited-value lint:** a changed expected value in a cited test, unless the same diff re-points `cites:` to the retired ID's replacement or a newer version, with an unchanged subject and the replacement's value for the same key;
- **expected-failure, quarantine and deletion checks;** recorded mocks, request documents and fixtures changed without a spec change; discovered notes deleted;
- **conventions lint:** a `cites:` token or `characterization` on every new test, the locator policy, request documents as files, expected-failure links, and citation status.

Flag IDs are (check, element) (S-QA-042). Your findings cover what these checks can't judge: whether a value matches its source, whether a test exercises the cited behaviour, and whether a sign-off request is justified.

## Checklist (S-QA-043)

| ID | Item | Finds |
| --- | --- | --- |
| TR-1 | Oracle | An expected value that doesn't match its cited source; a value read from the code or the page; a candidate used as a source (S-QA-006) |
| TR-2 | Coverage | A declared AC, test condition, rule condition or IF element without a test; missing negative, boundary or per-role authorization cases |
| TR-3 | Characterization | An unlabelled characterization test; a cited test whose value no source states |
| TR-4 | Expected failures | A suspected issue without evidence; an expected failure that hides a test bug |
| TR-5 | Healing | A heal outside rows c and x; a heal that changes the behaviour under test |
| TR-6 | Survivors | An `out_of_scope` or `accepted_gap` category without a sound reason |
| TR-7 | Stability | Sleeps, shared data, order dependence, unbounded waits (S-TESTAB-004, -007) |
| TR-8 | Data and security | Real personal data in fixtures (S-DATA-004), secrets in tests, production endpoints |
| TR-9 | Conventions and readability | `AGENTS.md` breaches, duplication, unclear names, page-object misuse |

For TR-1, open the cited source and compare the value key by key: the AC `then` entry by `key`, the rule's structured field, or the spec element's field, unit included. A mismatch is a blocker. So is a value with no source (TR-3), and a heal that changes the behaviour under test (TR-5).

## Output specifics (S-QA-044)

- **Findings** carry `suggestion`: the change you suggest.
- **Finding ID:** `TR-n|<test ID>|<primary cited ID>`. The test ID is test ID v1. For a finding that isn't on one test, use the file path. The primary cited ID is the source the test cites. Without one, use the S-ID of the broken rule, for example `S-QA-006`.
- **`classification`:** always `issue`.
- **Secrets in tests (TR-8):** name only the location, and say "details withheld (S-SEC-011)".
- **Questions:** S-BA-014 form. A suspected wrong source (two readings of a value, or an AC against a rule) is a question for the human. They may label it `qa:source-wrong` (S-QA-009, S-QA-011).

## Prerequisites and retrieval (S-QA-020, S-QA-044, S-QA-047)

- **Prerequisite:** S-TESTAB-006 sources for the area. Without them, TR-1 checks only within the PR, and `decision_summary` says so.
- **Always:** this checklist and `AGENTS.md`.
- **On demand:** the diff and PR block, the cited sources, the check outputs, and the gate's survivors. S-QA-036 and -037 (the gate and survivors, for TR-6) are condensed above.
