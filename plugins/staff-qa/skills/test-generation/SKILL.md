---
name: test-generation
description: The shared generation base of the test-gen-* agents - the oracle rule, citations, frozen cited values, inputs, what goes back, and the API layer's rules (S-QA-004, S-QA-006 to -011).
---

# Test generation (shared base)

## The oracle rule (S-QA-006)

Every expected value in a test comes from a cited source: a ready AC (or its test condition), an active rule, an approved interface version (an operation, schema field or error code), an accepted ADR constraint or an accepted QAS. Never from running the code, reading what the code returns, or from another test. A test whose expectation has no source is labelled `characterization` and says what it pins; use it sparingly.

## Citations (S-QA-007)

Each test declaration has a comment within the three lines above it:
- `// cites: REQ-005/AC-001, R-004, IF-001@1.3.0#editProduct`, listing every source its expectations come from; or
- `// characterization: <what it pins>`.

Cite only IDs that exist and are live: ready ACs, active rules, approved or deprecated interface versions (`IF-n@x.y.z` or `IF-n@x.y.z#<operationId or schema>`), accepted ADR constraints (`ADR-n/C-k`) and accepted QAS. The harness checks every cited ID and fails the run on one that isn't.

## Cited values are frozen (S-QA-009)

Never change a cited expected value to make a test pass. When you can see the code won't meet it, keep the expectation, mark the test as an expected failure and report a suspected issue. The human decides whether it's a bug.

## Inputs (S-QA-010)

Use only ready requirements and their live ACs. Skip the affected ACs of a `changed` requirement. A rule change counts only as a `changes[]` entry with `accepted_by` set, never a free-text note.

## Problems go back (S-QA-011)

A source that is ambiguous, contradicts another, or has an outcome no stable identifier exposes is a requirement-defect item (`ambiguous`, `contradicts`, `untestable`, `missing`, `infeasible`) on that requirement, or a question. Never resolve it by choosing a reading in a test.

## API layer rules (S-QA-004, S-TESTAB-004/-005/-008)

- Drive the real backend through the layer's support code (`startApi()` in `tests/api/support/api.ts`): real stores, real database, real login.
- Assert on what the interface names: status codes, error `code`s, response fields and their values. Never on message wording, ordering the spec doesn't promise, or generated IDs' format.
- Each test creates the data it needs, with unique names, and never depends on another test's data or order.
- Fake external services only at their seams (the label provider, the clock), through the support code's options.
- One file per feature or operation group, named as the layer's `paths` require.
- Prefer one behaviour per test; name the test after the behaviour, in the source's words.
