---
name: developer-reference
description: On-demand reference for the developer agents (not preloaded). Covers the implemented-interface source, security findings, production-derived content, context and the work sandbox, the DEV check scripts in detail (code diff, regression-test, replay, generator, implementation status, test ID), per-run caps, testability prerequisites and the dev-upkeep lane class. Read only the sections the trigger table in developer-change-contract names.
---

# Developer on-demand reference (S-DEV-012 to -045, on-demand part)

Source: the "On-demand reference" part of `docs/strategy/roles/developer.md`. It is not always loaded (S-DEV-026). Read only the sections your trigger needs. Checklist, eval, metric and record sections are not here: working agents don't act on them.

## Interfaces, security, context and sandbox

### S-DEV-012 Implemented-interface source
Where the stack can generate the interface from code, `interface_source` names the command. CI runs it on every product PR and on `main` and publishes the result for the conformance check. Keep the generator's annotations complete for every element you add. Never commit its output. With `none`, QA's contract verification feeds conformance instead.

### S-DEV-019 Security findings
A suspected vulnerability or exposed secret found while coding goes into `private_reports[]` only (S-SEC-011), never into a comment, a PR, a code comment or `decision_summary`. A fix cites only the private report's ref. Code holds no secret; tests reach test accounts only through CI secrets (S-TESTAB-004). A third-party service that may fail S-DATA-006 becomes a design request.

### S-DEV-020 Production-derived content
The fetch step redacts every tracker and connector fetch (S-BA-028). You never read production systems, logs or data. Incident evidence reaches you only as redacted defect tickets.

### S-DEV-023 Context

| Agent | Always loaded | Retrieved on demand |
| --- | --- | --- |
| Developer | Product core; `AGENTS.md` for the touched stack; the area's `.staff/code.yml` entry; the product-PR schema; own learnings | The ticket; ready ACs and cited rules; IF versions, components and ADRs for the touched `code_paths`; code and tests; CI, conformance and mutation results; reviewer comments; this reference |
| `dev-upkeep` | `AGENTS.md`; the area's `.staff/code.yml` entry; own learnings | Lint, deprecation and dependency reports; package release notes (untrusted); code |

On-demand items come from the fetched bundle and the checkout. A run that needs a ticket outside its bundle asks instead.

### S-DEV-042 Work sandbox
- **Fetch:** a harness step without a model, holding read-only tokens, bundles a checkout of the base, the redacted ticket and comments, CI and check results, and this reference.
- **Work (read stage):** the model runs in the S-GEN-066 sandbox profile: model credential and test-only credentials, no repo, tracker or private-store token; egress only to the model endpoint, the package mirror and the area's test environment. A draft or push needs: the build passes, no base-passing unit test of the area fails on the head, the added tests pass. Base failures are listed in the decision summary. A base-passing test that fails is re-run once; if it then passes, it is listed as flaky for the QA healer. Otherwise nothing is pushed, the failures are reported and the digest lists the run.
- **Hand-off:** the harness derives `files[]` from the workspace diff and validates it with the structured output. The write stage commits it byte for byte and never passes it to a model.

In the read-only form you propose `proposed_files[]`; the harness applies it in this sandbox and runs the gate (see developer-change-contract).

## DEV check scripts

### S-DEV-027 Who the checks apply to
- **Every product PR:** the citation scan (S-DEV-016).
- **DEV agent PRs (blocking):** contract check (S-DEV-010), code diff check (S-DEV-028), generator check (S-DEV-043), regression-test check (S-DEV-029) on `fix` PRs, replay check (S-DEV-030) on `dev-upkeep` PRs.
- **Human PRs (report only):** code diff check, generator check on `outputs`, contract check when the PR carries the block.
- **After merge, on operator `implemented_acs[]` comments, nightly:** implementation check (S-DEV-044). **Nightly:** readiness re-run and outcome check.

Checks read no switch, fail closed, and build or run code in the S-DEV-042 sandbox profile.

### S-DEV-028 Code diff check detail
- **Tests** are compared as a net set keyed by (test ID, cited IDs). Renames are mapped first, so a moved file whose tests keep their names, citations and assertion lines isn't flagged. Flagged: a key that disappears, assertion lines that shrink, an assertion line changed in an uncited test. Where test IDs fall back, any decrease in a file's net assertion-line count is flagged.
- **Cited values:** a changed assertion line in a cited test is judged by QA's assertion-diff check and cited-value lint (S-QA-040, blocking on DEV agent PRs), not flagged here.
- **Guard lines:** a removed or changed line matching an authorisation, validation, permission-deny, suppression or testability pattern is flagged, also when it moves.
- **Verification configs:** any diff is flagged.
- **Flag IDs** come from (check, element), so a sign-off holds across rebases and a push that changes the element voids it (S-ARCH-053). Element: guard line → (file, pattern class, line hash); test → test ID; `protected` or `verification_config` → (file, hunk hash); dependency → (name, to-version); `not_unit_observable` → `fixes.target`.
- Semantic loosening no pattern sees is the reviewer's CC-4 and the human's job; say it in the decision summary.

### S-ARCH-053 Sign-off form
A sign-off is an operator comment on the PR that cites the flag ID the check printed. A new push that changes the flagged element voids it. Never write one.

### S-DEV-029 Regression-test check
On a `fix`, the PR's added or changed tests that cite `fixes.target` run against the merge-base code with only those tests applied. They must build there, and at least one must fail with an **assertion failure** (not an error, setup or build failure). All must pass on the head. A fix that can't be tested against the base code's interfaces uses `not_unit_observable`.

### S-DEV-030 Replay check (the `dev-upkeep` lane guard)
Re-runs each `tool_runs[]` entry with the base branch's `upkeep_tools` at its pinned version, on the base commit, over the listed paths, and reports whether the result equals the head byte for byte (replay-verified). A PR is lane-eligible only when it is replay-verified with empty `residual_edits`, touches no `dependency_files`, `protected`, `verification_config`, `generated`, `unit_tests` or other test path, and the build and the area's whole suite pass unchanged. Only the check marks a PR lane-eligible, never the agent.

### S-DEV-043 Generated code
`generated` paths change only as the output of a `generators` entry. The generator check re-runs a generator (base declaration, head inputs) when a PR touches its `outputs`, or when a DEV agent PR changes its `inputs`. Head outputs that differ byte for byte from the re-run are a hand edit, which is blocked. A PR that changes only inputs is never a hand edit; the regeneration arrives in the implementing Developer PR. Where a stack doesn't commit generated code, `generated` is empty.

In the read-only form you can't run a generator. Change its inputs, say which generator must run in `decision_summary`, and never write its outputs by hand.

### S-DEV-044 Implementation status
An AC is `implemented` once a merged PR declares it `full`, `partial` while merged PRs only declare it `partial`. A changed AC has a new ID and starts unimplemented. A revert withdraws its PR's declarations. So declare `full` only when the AC is fully built.

### S-DEV-045 Test ID v1
A test's ID is `<path>::<name>` as the area's `test_list` command prints it; checks never use an agent-declared list. A test spans from its `test_decl` line to the next one or the end of the file. A `cites:` token belongs to the test whose declaration line holds it, or that is declared within the 3 lines after it. Parametrised or generated tests that match no `test_decl` line fall back to per-file assertion counts.

## Caps, prerequisites and stages

### S-DEV-033 Per-run caps *(starting values)*
- **Developer:** $6 and 45 minutes. One run covers one PR-sized slice, one fix-up, or one bootstrap area.
- **`dev-upkeep`:** $2 and 20 minutes.

If you are running out, emit what you have and say so in `decision_summary`.

### S-DEV-035 Testability prerequisites
- **Developer:** digest-addressed builds for the area (S-TESTAB-003); S-TESTAB-006 sources (ready ACs, and approved versions where the area has interfaces); the area's `.staff/code.yml` entry. Out-of-process tests also need S-TESTAB-002.
- **`dev-upkeep`:** S-TESTAB-003, and a green suite for the area on `main`.

A missing prerequisite keeps the agent at stage 1 in that area (S-TESTAB-001); say so in `decision_summary`.

### S-DEV-037 Stage 3 for `dev-upkeep` only
The Developer has no stage 3. The `dev-upkeep` lane holds only PRs the replay check marks lane-eligible: pure tool output, no residual edit, no dependency, protected, verification-config, generated or test path. Dependency bumps are never in the lane (S-SEC-009).
