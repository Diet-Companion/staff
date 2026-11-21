---
name: qa-test-generation
description: Test-generation pack for test-gen-unit, test-gen-api and test-gen-ui. Covers generation inputs, the per-layer test rules, interfaces and quality scenarios, test PRs and feedback rounds, survivor categories, citation repair, what the QA diff checks flag, and the read-stage output. Use on every test-generation run.
---

# Test generation (S-QA-021 to S-QA-026)

Source: the "Test generation" section of the on-demand reference in `docs/strategy/roles/test-engineer.md`, plus what the fetch step retrieves for every generator run (S-QA-020): survivors (S-QA-037) and the QA checks (S-QA-040). The output fields are in `schemas/test-gen-output.schema.json`.

## Inputs (S-QA-021)

- **Always in context:**
  - the product core;
  - the `AGENTS.md` conventions for the layer's stack, including its protocol rules;
  - the area's `.staff/tests.yml` and `.staff/code.yml` entries;
  - your own learnings.
- **Fetched into your input:**
  - the product PR's diff and block (S-DEV-009);
  - 2 or 3 of the changed modules' existing tests, as style references;
  - the cited ACs, test conditions and rules;
  - IF versions and QAS;
  - the ARCH drift report and the BA and ARCH trace matrices;
  - survivors and candidate tests.
- **Duplicates:** before writing a test, check the existing tests by test ID, cited IDs and target. Skip behaviour that is already covered.
- **Prerequisites (S-QA-047):** S-TESTAB-003 and -006 sources, plus the area's `tests.yml` and `code.yml` entries. API and UI also need S-TESTAB-002, -004 and -005. API needs approved versions for the area, and UI needs the core journeys in the product core. If a prerequisite is missing, set `blocked.reason: missing_prerequisite`.

## Layer rules (S-QA-022)

The details for each stack live in `AGENTS.md`. Follow it, and use the test map's `locators`, `mocks`, `request_docs` and `fixtures` globs.

**Unit**
- Test public interfaces only. Mock only at seams (S-TESTAB-008).
- Follow the module's folder layout and naming.
- A survivor is the prompt: write a test that kills it.

**API**
- Typed clients and stubs come from approved specs, through DEV's declared generators (S-DEV-043). Never hand-write them.
- Assert on the protocol's error channel, not on transport status alone. For example, where the protocol returns errors in the response body next to partial data, assert on both.
- Test authorization per product user role on the same operation (S-TESTAB-004).
- Keep request documents as files beside the tests. A request document asks only for the fields the test asserts on.
- Coverage spans operations, fields, enum values, validation and error codes.

**UI**
- Cover core journeys only, unless an operator asks for more.
- Work in the front end's declared end-to-end framework.
- Locators follow `locators`: accessible roles and names, or test IDs (S-TESTAB-005). Never CSS or XPath.
- Waits use readiness signals (S-TESTAB-007), never sleeps.

**Every layer**
- Each test creates its own data through factories and cleans up (S-TESTAB-004).
- Use only synthetic data (S-DATA-004), no secrets, and no production endpoints.
- Pass the `run_id` as the correlation ID where the test calls the app (S-TESTAB-007).

**Tools**
- Tool-generated tests are characterization, ported to the layer's stack.
- Spec fuzzing is an advisory check, not your job.

## Interfaces and quality scenarios (S-QA-023)

**Contract tests cover implemented elements only.**
- On a product PR, the targets are the elements of the versions in its `implements[]`.
- On `main`, they are the elements the drift report lists as implemented. Where `interface_source` is `none`, add every element of the versions that merged PRs declare in `implements[]`.

**Failing contract tests**
- A failing contract test counts as *pending implementation* only when the response shows the element is absent: an unknown operation, field or event, as the protocol reports it.
- Any other failure is a suspected product issue (S-QA-009).
- Pending elements feed spec-derived mocks for consumers' tests, labelled with their version.

**Spec-change events (S-ARCH-054)**
- A compatible change updates the affected tests.
- A breaking change gets tests for the new major version as its elements are implemented.

**Version lifecycle**
- Deprecated versions keep their tests until the version retires.
- `as-built` versions get characterization tests. Once `provenance_confirmed_by` is set, generate cited tests from the confirmed version.
- A characterization test is removed only when a cited test covers the same element, and the removal is a flagged diff.

**Quality tests (`test-gen-api`)**
- Write quality tests citing `QAS-n` for QAS with `verification: test` and owner QA, when the `measure` can be decided in a functional test environment. Examples are a limit, an error behaviour or a security requirement.
- A single-call latency test goes in a non-blocking job.
- Load, soak and capacity measures are not yours: they belong to DEVOPS, with `verification: monitor`.

## Test PRs and feedback (S-QA-024, S-QA-037)

- Draft one test PR per product PR and layer, based on the product PR's branch. Nightly and gap triggers target `main`, with one PR per area and layer. A new run supersedes your earlier open test PR for the same product PR and layer.
- **Feedback rounds:** mutation-gate survivors start at most 2 feedback rounds *(starting value)*. Set `pr.feedback_round` to 0 for the first run and 1 or 2 after that. In each round, write tests that kill the survivors.
- **Survivor categories:** each counted survivor that is left after the last round gets one category in `pr.survivor_categories`:
  - `out_of_scope`, with a reason;
  - `accepted_gap`, with a reason.

  Never set `equivalent`. That comes only from `equivalence-filter`. The human's merge confirms your categories. An operator review comment that cites a mutant ID rejects its category, and the mutant returns as a survivor.
- **Mocks:** a re-recorded mock comes with a per-field diff summary in `decision_summary`. Old mocks stay in use until the PR merges.
- A test PR is ready for review only after the build, the conventions lint, the mutation gate and the QA diff checks have run. The write stage runs them.

## Citation repair (S-QA-025)

The trigger is a nightly finding that a test cites a retired ID.
- **Re-point only** (`pr.kind: repair`) when the cited rule retired with `retired_reason: duplicate` and has a `replaced_by`. Change only the `cites:` tokens: no assertion, no value, no name.
- **Otherwise the meaning changed.** That covers a retired AC, a rule retired for any other reason, and a new IF version. Regenerate the test against the replacement (`pr.kind: tests`), under S-QA-009.
- Remove the tests of a retired IF version in the same run.

## What the QA checks flag (S-QA-040)

Each of these needs an operator sign-off, so avoid them, and list any you can't avoid in `decision_summary`:
- **Tests:** a test removed, skipped or newly marked expected-failure; an assertion line removed; fewer assertion lines in total; a matcher moved to a weaker class in `matcher_strength`.
- **Cited values:** a changed expected value in a cited test. The exception is a citation re-point whose new value equals the replacement source's value for the same key.
- **Deletions:** deleting a test, unless all its cited IDs are retired. Deleting a test of a deprecated version before it retires is blocked.
- **Mocks, request documents and fixtures:** a recorded value changed for an element whose spec didn't change; a field or operation removed from a request document; a value changed or removed in a fixtures file.

**The conventions lint blocks at zero violations.** It requires:
- a `cites:` token or `characterization` on every new test;
- the locator policy;
- request documents kept as files;
- expected-failure markers that are strict, sit on a cited test, and link a defect ticket before `main`.

**Citation status:** every ID you add to a `cites:` token has the status that S-QA-010 requires.

## Read-stage output (S-QA-026)

- `pr`:
  - `kind`, `layer` and `product_pr`;
  - `base`, which is `main` when there is no product PR;
  - `feedback_round` and `cited_ids`;
  - `characterization`: test IDs;
  - `expected_failures`: each with test ID, cites, expected, actual and evidence;
  - `survivor_categories`.
- `files[]`: the proposed test, mock and request-document files, as full content in chunks of at most 2,000 characters. Each path stays inside your row of the path-scope table.
- `suspected_issues[]`: one per expected failure, the same facts, as the advisory comment (S-QA-009).
- `defect_items[]`, `bug_drafts[]` (only after `verdict:confirmed`), `questions[]` (at most 7, in the S-BA-014 form), `private_reports[]` and `source_refs[]`.

**Stage-1 writes**, done by the write stage: comments as in S-QA-018, suspected-issue comments, requirement-defect items, draft defect tickets and private reports. No branch, PR or push until stage 2.
