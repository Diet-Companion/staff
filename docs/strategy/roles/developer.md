# Developer Strategy (DEV)

Updated Nov 20, 2026

## Purpose and scope

This doc covers how product code is written, reviewed and kept healthy when one human works with agent staff. DEV comes after BA and ARCH (`docs/decisions.md`, 2026-11-20). It consumes ready ACs and accepted ADRs and approved interface versions, and produces code that DEVOPS deploys and QA tests. It is product-agnostic and stack-agnostic (S-GEN-002).

It honours the common set in S-GEN-064, plus S-GEN-019. GEN, shared/, BA and ARCH decisions are referenced by ID, never restated.

The part under "On-demand reference" is not always loaded (S-DEV-026). Markers: *(starting value)* means accepted in `docs/decisions.md`; Assumptions items 1 and 14 were accepted (2026-11-20, roles/developer rounds 1 and 2). *(proposed)* means awaiting confirmation, and none is open. Named tools are examples.

## Ownership and agents

- **S-DEV-001** Ownership split:
  - **The human decides** what is built and when (S-DEV-006 labels), every merge (S-GEN-003), business rules (through BA), every change to an ADR constraint, boundary or interface (through ARCH), sign-offs on flagged diffs, dependency additions and upgrades (S-SEC-009), and implementation trade-offs that agents raise as questions.
  - **Agents** implement ready ACs, fix confirmed defects, write the unit tests DEV owns (S-DEV-014), make mechanical upkeep changes, review code and answer review feedback.

  No agent sets or applies anything human-owned (S-DEV-025). *Depends on:* S-GEN-001, S-GEN-003, S-SEC-009, S-DEV-025.
- **S-DEV-002** Agents and checks, in staff-engineering (S-GEN-014):
  - **Developer:** implements ready ACs, fixes confirmed defects and the code side of drift (S-ARCH-028), writes DEV unit tests, and raises requirement-defect items, design requests and questions.
  - **`dev-upkeep`:** changes with no intended behaviour change: formatter and linter autofixes, codemod-driven deprecation migrations, and dependency patch and minor bumps. It is separate from the Developer because its trigger (a schedule, not a ticket), its eval (behaviour preservation on scripted tasks) and its stage-3 lane all differ, as for `arch-upkeep` (S-ARCH-002).
  - **`reviewer/code`:** the `code` artifact type of the shared reviewer. This doc owns its checklist (S-DEV-031).

  Not DEV agents: conformance (S-ARCH-027) and the DEV checks (S-DEV-027) are scripts; unit-test generation, the mutation gate and the CI healer are QA's (OD-DEV-2). Drift repairs change behaviour or structure, so they go to the Developer, not `dev-upkeep`. *Depends on:* S-GEN-014, S-GEN-030, S-ARCH-002, S-ARCH-027, S-ARCH-028, OD-DEV-2.
- **S-DEV-003** Identities. The Developer and `dev-upkeep` run as the staff-engineering identity, `reviewer/code` as staff-review (S-GEN-026). All three use the two-stage split (S-SEC-002) with the schemas in S-DEV-021, and the Developer and `dev-upkeep` work in the sandbox of S-DEV-042. Branches are `agent/developer/*` and `agent/dev-upkeep/*`, under the prefix lint of S-ARCH-003. Their per-job tokens carry no workflow-file permission (S-SEC-006, S-DEVOPS-018). *Depends on:* S-GEN-026, S-SEC-002, S-SEC-006, S-SEC-008, S-ARCH-003, S-DEV-042, S-DEVOPS-018.

## Code map and path scope

- **S-DEV-004** Code map (closes the artifact-path part of OD-GEN-2 for DEV). The human declares DEV's paths and per-stack patterns in `.staff/code.yml`, listed in the product contract (S-GEN-017), which only the human edits (S-GEN-025). The schema ships in staff-engineering `schemas/`. Per area:
  - `source`, `unit_tests` and `generated`: path globs;
  - `protected`: security-sensitive globs, at least authentication, authorisation, cryptography, secret handling, permission config and data migrations;
  - `dependency_files`: manifests and lockfiles;
  - `verification_config`: lint, formatter, type-check, coverage, mutation and test-runner configs;
  - `guard_patterns`: per stack, line patterns marking test declarations (`test_decl`), assertions, skip and expected-failure markers, authorisation checks, validations, permission denies, lint suppressions and testability markers (S-DEV-013);
  - `test_list`: per stack, the test runner's list or collect command (S-DEV-045);
  - `generators`: `{generator_id, version, command, inputs, outputs}` for committed generated code (S-DEV-043);
  - `interface_source`: the command that generates the implemented interface from code, or `none` (S-DEV-012);
  - `upkeep_tools`: formatters, linter autofixes and codemods, each `{tool_id, kind, version, command}`.

  DEV checks read it from the base branch, so a PR can't change the rules it is checked against. Without an entry for its area, a DEV read stage fails closed and the digest lists the gap. The one exception is `dev:bootstrap` (S-DEV-006). *Depends on:* S-GEN-017, S-GEN-025, S-GEN-063, OD-GEN-2.
- **S-DEV-005** Path scope (closes the agent-scope part of OD-GEN-2 for DEV). The scope lint (G2) enforces it by branch prefix (S-ARCH-003), and fails a DEV commit without a `Staff-Run-Id` trailer (S-GEN-029).

  | Agent | Writes | Never writes |
  | --- | --- | --- |
  | Developer | The area's `source` and `unit_tests` globs. `protected`, `dependency_files` and `verification_config` only under the flags in S-DEV-018. `generated` only as `generators` output (S-DEV-043) | `generated` by hand; `architecture/**`; `requirements/**`; `knowledge/**`; `.staff/**`, `.github/**` and CI or pipeline paths (DEVOPS); `AGENTS.md`; tests outside `unit_tests` (QA) |
  | `dev-upkeep` | Files changed by an `upkeep_tools` run; `dependency_files`; the call sites a bump or migration needs | As the Developer, plus `protected`: a change there becomes a draft Developer ticket |
  | `reviewer/code` | No paths: comments, private reports and the label `dev:not-ready` | Any path |

  *Depends on:* S-GEN-020, S-GEN-025, S-GEN-029, S-ARCH-003, S-ARCH-035, S-DEV-004, S-DEV-018, S-DEV-043, OD-GEN-2.

## Inputs and readiness

- **S-DEV-006** Triggers (closes OD-GEN-1 for DEV). The event classes are those of S-BA-034: operator events, staff-app PR events (which may trigger only `reviewer/code`), and check and schedule events. Everything else is dropped.

  | Agent | Starts when |
  | --- | --- |
  | Developer | An operator applies `dev:implement` to a ticket that links ACs, or to a technical ticket driven by an operator comment (`kind: refactor`), or `dev:fix` to a defect ticket or an ARCH drift work ticket (S-ARCH-028). A waiting ticket turns ready (S-DEV-007). An operator answers on a ticket where it waits, or reviews a Developer PR. A required check fails on its own PR, for at most 3 fix-up runs per PR *(starting value)*; then the digest lists it. An operator dispatches `dev:bootstrap` for an area: it drafts that area's `.staff/code.yml` entry as a comment for the human to commit, showing per pattern its match count and sample lines from the area's code |
  | `dev-upkeep` | A weekly run per area *(starting value)*, when the area's lint, deprecation or dependency report (S-DEVOPS-031) has new items. An operator dispatches `dev:upkeep` with a target, or reviews its PR |
  | `reviewer/code` | A Developer or `dev-upkeep` PR becomes ready for review, or its review is re-requested. An operator applies `dev:review` to a human PR, or to a ticket holding a Developer stage-1 draft |

  *Depends on:* S-GEN-005, S-GEN-060, S-BA-034, S-ARCH-028, S-DEV-007, S-DEVOPS-017, S-DEVOPS-031, OD-GEN-1.
- **S-DEV-007** Readiness check (closes the trigger parts of OD-BA-2 and OD-BA-3 for DEV, and OD-ARCH-1's wait on design). A script, run before every Developer read stage and in the contract check (S-DEV-010), on the BA and ARCH trace matrices of the latest `main` run. A `dev:implement` ticket is `ready` only when:
  - every linked AC is ready (S-BA-019);
  - the design status of every linked REQ is not `pending` (S-ARCH-015, S-ARCH-030);
  - every interface version the ticket names or the PR declares is approved or deprecated (S-ARCH-011).

  Otherwise it is `waiting`, and the check names the blockers in one comment. A nightly run re-evaluates waiting tickets and starts the Developer when one turns ready. A `dev:fix` target must be a ready AC, an active rule, an element of an approved or deprecated version, or an ADR-n/C-k of an accepted ADR. A `kind: refactor` ticket needs a driver comment from an operator, and its PR declares no AC. An open Developer PR whose declared ACs stop being ready fails its next contract-check run and goes to the digest. *Depends on:* S-BA-019, S-BA-021, S-ARCH-011, S-ARCH-015, S-ARCH-030, OD-BA-2, OD-BA-3, OD-ARCH-1.
- **S-DEV-008** Problems go back, never into code (closes the defect-item part of OD-BA-3 for DEV, and OD-ARCH-1's design request):
  - **Requirement problems** become requirement-defect items (S-BA-048) on the requirement's ticket. They are never free comments, and never solved by reinterpreting the requirement. Kinds: two readings of an expected value → `ambiguous`; an AC against an active rule or another ready AC → `contradicts`; an outcome no stable identifier exposes → `untestable`; a case the code must handle that no AC covers, such as an error or empty state → `missing`; an AC that accepted constraints or approved versions can't meet → `infeasible`, plus a design request if a design change could meet it.
  - **Design needs** become a design request comment on the ticket, `{target: AC | IF element | ADR-n/C-k, need: interface | element | dependency | data | technology | testability, missing, evidence_refs}`, which the human may turn into `arch:design` (S-ARCH-015). Needs include an element no approved version contains (S-ARCH-027 would block it), a dependency outside `allowed_dependencies`, a new store, and a `provided` testability item the code can't provide (S-ARCH-025).
  - **Implementation trade-offs** that no rule, AC or ADR decides become questions in the S-BA-014 form.

  Work on the affected ACs stops until the answer, the ready requirement or the design arrives; other ACs proceed. Silence never decides. *Depends on:* S-BA-014, S-BA-048, S-ARCH-007, S-ARCH-015, S-ARCH-017, S-ARCH-025, S-ARCH-027, OD-BA-3, OD-ARCH-1.

## Product PR contract

- **S-DEV-009** PR declaration (closes OD-BA-2's declaration, and OD-ARCH-1's `implements` and `check: review` parts). Every DEV agent PR opens with its decision summary (S-DEV-024), then a block in the product-PR schema (staff-engineering `schemas/`):
  - `kind`: `feature`, `fix`, `drift`, `refactor` or `upkeep`; and `ticket`;
  - `implements_acs[] {ac, part: full | partial}` (REQ-n/AC-m). Required for `feature`. A `full` declaration feeds the implementation status of S-DEV-044, not the PR merge itself;
  - `implements[]`: IF-n@x.y.z (S-ARCH-021);
  - `fixes {ticket, target}`: for `fix` and `drift`. The target is an AC, R-ID, IF element or ADR-n/C-k;
  - `constraints[] {id, disposition: conform | n/a, reason}`: every `check: review` constraint (S-ARCH-026) of the accepted ADRs that the touched components cite;
  - `untested_acs[] {ac, reason: other-layer | not-unit-observable}`; `not_unit_observable {target, test_gap}` for a `fix`; `characterization[]` (test IDs, S-DEV-045);
  - `dependencies[] {name, from, to, reason}` and `flags[] {flag_id, reason}`.

  `refactor` and `upkeep` PRs declare no AC and change no assertion, except as S-DEV-018 allows. Human PRs may carry the block, which then counts the same way. *Depends on:* S-GEN-022, S-ARCH-021, S-ARCH-026, S-BA-023, S-DEV-018, S-DEV-024, S-DEV-044, S-DEV-045, OD-BA-2, OD-ARCH-1.
- **S-DEV-010** PR contract check, a script (S-DEV-027). It fails a DEV agent PR (`agent/developer/*`, `agent/dev-upkeep/*`) that:
  - doesn't open with the decision summary and a schema-valid block, or has a prose field over 2,000 characters (S-SEC-002);
  - covers more than one ticket or one area (S-GEN-060), or changes more than 500 lines *(starting value)*, not counting `generated` paths, lockfiles and lane-eligible tool output (S-DEV-030). A larger ticket is split into several PRs in AC order;
  - declares an ID that doesn't exist, or an AC or version that fails the readiness check (S-DEV-007);
  - is a `fix` without a passing regression-test check (S-DEV-029), unless `not_unit_observable` names the target and the test gap for QA (S-DEV-017). That declaration is a flagged diff (S-DEV-018);
  - is a `drift` PR whose conformance finding (S-ARCH-027) still fires on the head.

  The scope lint covers the never-write paths and the trailer (S-DEV-005). `kind: upkeep` PRs get no QA intake check or mutation gate (S-QA-012). *Depends on:* S-GEN-060, S-SEC-002, S-ARCH-027, S-DEV-005, S-DEV-007, S-DEV-017, S-DEV-018, S-DEV-027, S-DEV-029, S-DEV-030, S-QA-012.

## Code quality and conformance

- **S-DEV-011** Implementation sources. The Developer implements against approved and deprecated interface versions, each for its own version (S-ARCH-021), and against the chosen-option constraints of accepted ADRs that the touched components cite (S-ARCH-004). Code follows `AGENTS.md` for its stack (S-GEN-002). A conformance failure (S-ARCH-027) is fixed in the code or raised as a design request (S-DEV-008), never by editing architecture or a rule. *Depends on:* S-GEN-002, S-ARCH-004, S-ARCH-021, S-ARCH-027, S-DEV-008.
- **S-DEV-013** Testability in code (closes OD-TESTAB-3, and the S-ARCH-025 part of OD-ARCH-1). New or changed code in a component provides that component's `provided` items of S-ARCH-025, and no PR lets an existing item regress. DEV adds these rules:
  - operation, error and event names come from the approved spec, never ad hoc strings (S-TESTAB-005);
  - every new entry point propagates the correlation ID to logs, traces and outgoing calls (S-TESTAB-007);
  - flags, the clock and external services are reached only through seams, never directly from domain logic (S-TESTAB-008);
  - a test-only seeding API is enabled only in test builds (S-TESTAB-004).

  Removing a testability marker line is a flagged diff (S-DEV-018), and CC-6 reviews the rest. An item the code can't provide becomes a design request (S-DEV-008). *Depends on:* S-TESTAB-004, S-TESTAB-005, S-TESTAB-007, S-TESTAB-008, S-ARCH-025, S-DEV-008, S-DEV-018, OD-TESTAB-3, OD-ARCH-1.

## Unit tests and the oracle

- **S-DEV-014** Unit-test split (closes the DEV part of OD-GEN-10; agents write unit tests per `docs/decisions.md`):
  - **DEV owns** the unit tests a DEV PR adds or changes in `unit_tests`. A `feature` or `fix` PR that changes logic adds or updates unit tests for it in the same PR. Each declared AC observable at unit level gets at least one citing test. The rest go in `untested_acs` with a reason.
  - **QA owns** independent test generation on any product PR, the mutation gate, the CI healer, dedicated characterization suites (for example of `as-built` versions) and every test outside `unit_tests` (OD-DEV-2). DEV PRs may still add labelled characterization tests (S-DEV-015).
  - **Existing tests:** a DEV PR changes one only when the PR's declared source change retires or replaces the cited ID (S-BA-010, S-ARCH-012), or when a refactor renamed, moved or re-signed the code under test and the assertions stay untouched. Any other failing test means the code or its source is wrong. The Developer fixes the code or raises a defect item (S-DEV-008), and never edits the test to pass.
  - **Mutation:** DEV unit tests go through QA's mutation gate on the changed lines (OD-DEV-2). `test-gen-unit` owns the survivors posted on the PR. For the Developer they are only advisory input to its next run on it (S-QA-012).

  *Depends on:* S-BA-010, S-ARCH-012, S-DEV-008, S-QA-012, OD-GEN-10, OD-DEV-2.
- **S-DEV-015** Oracle rule for DEV unit tests, a stricter local rule on S-TESTAB-006:
  - Every expected value comes from an AC, rule, test condition or approved interface version, cited by ID (S-DEV-016), never from what the code under test returns.
  - A test with no source to cite is labelled `characterization`, listed in the block, and never counts toward coverage or caught defects. If the behaviour needs a source, the Developer raises a `missing` defect item.
  - Cited expected values are frozen. They change only with their source (S-DEV-014).
  - Tests use public interfaces, mock only at the S-TESTAB-008 seams, and test one behaviour each, per `AGENTS.md`.

  *Depends on:* S-TESTAB-006, S-TESTAB-008, S-DEV-014, S-DEV-016, OD-DEV-1.
- **S-DEV-016** Test citation form v1 (DEV's share of S-BA-020 and S-ARCH-029). Each test carries the plain-text token `cites: <ID>[, <ID>]` in its name, its tag (the framework's tag mechanism where one exists), or a comment on one of the 3 lines *(starting value)* above its `test_decl` line. Tests are named by test ID v1 (S-DEV-045). IDs are REQ-n/AC-m, R-n, REQ-n/AC-m/TC-k, IF-n@x.y.z#<element> or QAS-n (for quality tests, S-QA-007). A characterization test carries `characterization` instead. A plain-text scan reads the token for the BA and ARCH trace checks (S-BA-021, S-ARCH-030). QA adopts the form (S-QA-007, closing OD-DEV-1). *Depends on:* S-BA-020, S-BA-021, S-ARCH-029, S-ARCH-030, S-DEV-045, S-QA-007, OD-DEV-1.

## Defect flow

- **S-DEV-017** Defect flow (closes the rest of OD-BA-3 for DEV). A defect ticket is one the human labels `dev:fix`, from any source: a QA finding, an exploratory bug, a human report or an incident. It names `{target, expected, actual, evidence_refs}` (OD-DEV-2). Where a human report lacks one, the Developer drafts it, or asks in the S-BA-014 form when it can't. Its read stage then classifies the ticket:
  - **Code defect** (the code differs from its cited source): a `fix` PR citing the ticket, with a regression test (S-DEV-010). If no unit test can observe it, the PR names the test gap, which QA picks up (OD-DEV-2).
  - **Requirement defect** (the source is wrong, silent or contradictory): a requirement-defect item (S-BA-048), and no code change until the requirement is ready again (S-DEV-007).
  - **Not a code defect** (the code matches a source that looks right): one comment citing both, for the human's verdict.

  `drift` tickets are fixed in code until the conformance finding clears (S-DEV-010). Escaped defects feed back as in S-DEV-041. *Depends on:* S-BA-014, S-BA-048, S-DEV-007, S-DEV-010, S-DEV-041, OD-BA-3, OD-DEV-2.

## Safety and change control

- **S-DEV-018** Code diff check (closes OD-GEN-9 for DEV; detail in S-DEV-028). It runs on every DEV agent PR. A flagged diff needs a sign-off in the S-ARCH-053 form (G3). Flagged:
  - a test removed, skipped or marked expected-failure; an assertion removed, or changed in an uncited test. A changed assertion line in a cited test is judged by S-QA-040's cited-value lint instead (S-DEV-028);
  - a removed or changed line matching an authorisation, validation, permission-deny or testability pattern (S-DEV-004);
  - a lint suppression added;
  - any change under `protected` or `verification_config`. Any diff to a verification config counts as a loosening until a finer rule exists;
  - any change to `dependency_files`, which also gets the label `dev:dependency` (S-SEC-009). DEV asks for a sign-off on every such PR. S-DEVOPS-049's once-per-(name, digest) reading of S-SEC-009 is compatible but not adopted here;
  - a `not_unit_observable` declaration (S-DEV-010).

  Blocked: deleting a file under `protected` or `verification_config`; a hand edit under `generated` (S-DEV-043); and a `refactor` or `upkeep` PR that changes an assertion, unless the change is replay-verified codemod output (S-DEV-030), which is flagged instead. The Developer and `dev-upkeep` stay at stage 1 until the check exists (G3). *Depends on:* S-GEN-020, S-GEN-051, S-SEC-009, S-ARCH-053, S-DEV-004, S-DEV-010, S-DEV-028, S-DEV-030, S-DEV-043, S-DEVOPS-049.

Security findings (S-DEV-019), production-derived content (S-DEV-020) and the work sandbox (S-DEV-042) are in the on-demand reference.

## Schemas, context and output

- **S-DEV-021** Read-stage schemas and write actions (closes OD-GEN-6 and OD-SEC-1 for DEV). Every prose field holds at most 2,000 characters (S-SEC-002). The harness derives `files[] {path, op: add / modify / delete / rename, from, content[]}` from the workspace diff (S-DEV-042), never from model output. Each file's full content travels as ordered chunks of at most 2,000 characters, never by reference. Before the write stage gets it, the harness checks each file: path in scope (S-DEV-005), the stack's parser accepts it, the secret scan passes, no binary content, and the size limit (S-DEV-010).

  | Agent | Read-stage output | Allowed write actions |
  | --- | --- | --- |
  | Developer | `pr` (S-DEV-009); `decision_summary`; `files[]` (harness-derived); `classification` (S-DEV-017); `defect_items[]` (S-BA-048); `design_requests[]` (S-DEV-008); `questions[]` (S-BA-014 form); `assumptions[]`; `private_reports[]`; `code_map` (`dev:bootstrap` only); `source_refs[]` | Stage 1: comments as in S-DEV-022, requirement-defect items, design requests, questions, private reports. Stage 2 adds: an `agent/developer/*` branch and PR, pushes to it, comments on its own PRs, and the labels `agent` and `dev:dependency` |
  | `dev-upkeep` | `pr`; `decision_summary`; `files[]` (harness-derived); `tool_runs[] {tool_id, version, paths[]}`; `residual_edits[] {path, reason}`; `dependencies[]`; `handoffs[]` (draft Developer tickets); `source_refs[]` | Stage 1: comments as in S-DEV-022, draft tickets. Stage 2 adds: an `agent/dev-upkeep/*` branch and PR, pushes to it, comments on its own PRs, and the labels `agent` and `dev:dependency` |
  | `reviewer/code` | `target`; `reviewed_sha`; `verdict`; `findings[] {finding_id, checklist_id, severity, location, text, suggestion, cited_ids, classification}`; `questions[]`; `private_reports[]` | One comment per run; the label `dev:not-ready`; private reports |

  No DEV agent writes `verdict:*` labels (G12), or applies or removes `dev:implement`, `dev:fix`, `dev:review`, `dev:upkeep`, `dev:bootstrap` or `arch:design`. The Developer and `dev-upkeep` work in the sandbox of S-DEV-042. A stage-1 draft or a push needs the build to pass, no base-passing test to fail, and its added tests to pass there. *Depends on:* S-SEC-002, S-SEC-003, S-SEC-011, S-GEN-020, S-BA-014, S-BA-048, S-DEV-005, S-DEV-008, S-DEV-009, S-DEV-010, S-DEV-022, S-DEV-042.
- **S-DEV-022** Stage-1 output (comment and draft only, S-GEN-052). One comment per drafted PR, with the rendered decision summary and the full patch as a CI artifact (S-DATA-003), so each draft gets its own verdict (S-GEN-071). The Developer comments on the ticket. `dev-upkeep` comments on one draft upkeep ticket per area per week. `verdict:confirmed` means the draft would merge as is, or with formatting-only edits. *Depends on:* S-GEN-052, S-GEN-071, S-DATA-003.
- **S-DEV-024** Load (S-GEN-061, S-GEN-073):
  - DEV PRs count toward the working-agent cap. The Developer keeps at most 2 PRs per area open and awaiting review *(starting value)*; further ready tickets wait. `dev-upkeep` opens at most 1 scheduled PR per area per week *(starting value)*. PRs from an operator's `dev:upkeep` dispatch don't count toward that limit. Fix-up pushes are not new PRs.
  - **Overlap,** a stricter local rule on S-GEN-060, which can't merge code by comment: a Developer ticket whose paths overlap an open agent PR waits until that PR merges or closes, and the digest lists the wait. `dev-upkeep` skips overlapping files until its next run.
  - Defect items, design requests, questions, waiting tickets and reviewer comments reach the human through the digest, one item per ticket or check.
  - **Decision summary**, first in every DEV PR: declared ACs and versions; defect items and design requests raised; `check: review` dispositions; flagged diffs with reasons; dependency changes; characterization tests and untested ACs; tests already failing on the base, and flaky tests (S-DEV-042); the reviewer's verdict, the commit it reviewed and its open findings. Prose follows.

  *Depends on:* S-GEN-060, S-GEN-061, S-GEN-063, S-GEN-073.
- **S-DEV-025** Human-owned:
  - the labels `dev:implement`, `dev:fix`, `dev:review`, `dev:upkeep` and `dev:bootstrap`, accepted only from accounts in `governance/operators.yml`;
  - sign-offs on flagged diffs and on `dev:dependency` PRs (S-ARCH-053 form);
  - answers to DEV questions, counted as in S-BA-015, and `implemented_acs[]` comments (S-DEV-044);
  - `.staff/code.yml` (S-DEV-004).

  *Depends on:* S-GEN-071, S-BA-015, S-ARCH-053, S-DEV-004.
- **S-DEV-026** Context budget and packaging (S-GEN-009, `docs/decisions.md`, 2026-11-20):
  - **Packaging:** S-GEN-009's rule sets what is always loaded, what is on demand, the measure and the cap. The latest figures are in Assumptions item 2.
  - **Reviewer pack:** the always-loaded part plus S-DEV-031 and -032.
  - **On demand:** context (S-DEV-023, which the harness applies), the sandbox and security handling, check details, the checklist, caps, records, evals, stages, metrics and interfaces. If a pack goes over, more sections move (S-GEN-048).

  Agents retrieve the moved decisions they act on, per trigger:

  | Agent and trigger | Retrieves |
  | --- | --- |
  | Developer: `dev:implement`, a ticket turning ready, `kind: refactor` | S-DEV-012 (interface source), -019 (security findings), -027, -028, -043 (generators), -045 (test ID) |
  | Developer: `dev:fix` or a drift ticket | S-DEV-019, -028, -029, -045 |
  | Developer: a review, answer or check failure on its PR | S-DEV-027, -028; the S-ARCH-053 sign-off form |
  | Developer: `dev:bootstrap` | S-DEV-028 (what the patterns drive), -035 (prerequisites) |
  | `dev-upkeep`: any run | S-DEV-028, -030 (replay check), -037 (lane class) |
  | `reviewer/code`: any run | S-DEV-019, -028. S-DEV-031 and -032 are in its pack |

  *Depends on:* S-GEN-009, S-GEN-048, S-DEV-023.

## On-demand reference

### Interfaces, security, context and sandbox

- **S-DEV-012** Implemented-interface source (closes that part of OD-ARCH-1). Where the stack can generate the interface from code (for example an OpenAPI export or a GraphQL schema dump), `interface_source` names the command. CI runs it on every product PR and on `main`, and publishes the result as a CI artifact for the conformance check (S-ARCH-026, S-ARCH-027). The Developer keeps the generator's annotations complete for every element it adds, and never commits the output. With `none`, QA's contract verification results feed S-ARCH-026 (OD-ARCH-2). *Depends on:* S-ARCH-026, S-ARCH-027, S-DEV-004, S-DEVOPS-031, OD-ARCH-2.
- **S-DEV-019** Security findings. A suspected vulnerability or exposed secret found while coding or reviewing goes into `private_reports[]` (S-SEC-011). Its fix PR cites only the private report's ref. Code holds no secret; tests reach test accounts only through CI secrets (S-TESTAB-004). A third-party service that may fail S-DATA-006 becomes a design request (S-DEV-008). *Depends on:* S-SEC-011, S-TESTAB-004, S-DATA-006, S-DEV-008.
- **S-DEV-020** Production-derived content. The DEV fetch step and the `reviewer/code` read stage apply the read-time redaction of S-BA-028 to every tracker and connector fetch. DEV agents never read production systems, logs or data. Incident evidence reaches them only as redacted defect tickets. So OD-DATA-2 needs no DEV part. *Depends on:* S-DATA-004, S-BA-028.
- **S-DEV-023** Context, in addition to the always-loaded set in S-GEN-009:

  | Agent | Always loaded | Retrieved on demand |
  | --- | --- | --- |
  | Developer | Product core; `AGENTS.md` for the touched stack; the area's `.staff/code.yml` entry; the product-PR schema; own learnings | The ticket; ready ACs and cited rules; IF versions, components and ADRs for the touched `code_paths`; code and tests; CI, conformance and mutation results; reviewer comments; this doc's on-demand reference |
  | `dev-upkeep` | `AGENTS.md`; the area's `.staff/code.yml` entry; own learnings | Lint, deprecation and dependency reports; package release notes (untrusted); code |
  | `reviewer/code` | Checklist (S-DEV-031, -032); `AGENTS.md` | The diff and PR block; declared ACs and rules; cited ADRs, IF versions and components; check outputs |

  For the Developer and `dev-upkeep`, on-demand items come from the fetched bundle and the checkout (S-DEV-042). The fetch step assembles the bundle from this table. *Depends on:* S-GEN-009, S-GEN-048, S-DEV-031, S-DEV-032, S-DEV-042.
- **S-DEV-042** Work sandbox, a stricter local rule on S-SEC-002 and S-SEC-007 for agents whose edits run. A Developer or `dev-upkeep` run has three steps:
  - **Fetch:** a harness step without a model, holding read-only tokens, bundles the inputs: a checkout of the base, the ticket and its comments redacted per S-DEV-020, CI and check results, and this doc's on-demand reference.
  - **Work (the read stage):** the model runs in the S-GEN-066 sandbox profile, which the DEV workflow launches from that bundle. It holds the model credential and test-only credentials (S-SEC-005), but no repo, tracker or private-store token. Its egress reaches only the model endpoint, the package mirror and the area's test environment (S-TESTAB-002). Its tools edit the workspace, build it and run tests. A stage-1 draft or a push needs three things there: the build passes, no unit test of the area that passes on the base fails on the head, and the PR's added tests pass. Tests already failing on the base are listed in the decision summary (S-DEV-024), so a red `main` doesn't block its own fix. A base-passing test that fails on the head is re-run once, and counts as failing only if it fails again. If it passes on the re-run, it is listed as flaky in the decision summary, for the QA CI healer (OD-DEV-2). Otherwise the run pushes nothing, reports the failures on the ticket or PR, and the digest lists it.
  - **Hand-off:** the harness derives `files[]` from the workspace diff and validates it with the structured output (S-DEV-021). The write stage commits it byte for byte and never passes it to a model.

  *Depends on:* S-GEN-066, S-SEC-002, S-SEC-005, S-SEC-007, S-TESTAB-002, S-DEV-020, S-DEV-021, S-DEV-024, S-DEVOPS-024, OD-DEV-2.

### DEV check scripts

- **S-DEV-027** DEV checks. They ship from staff-engineering `checks/` and run as required checks from a source the PR can't change (OD-SEC-2). They read no switch and fail closed, as in S-BA-051. Who they apply to:
  - **every product PR, human or agent:** the citation scan of S-DEV-016;
  - **DEV agent PRs (branches `agent/developer/*` and `agent/dev-upkeep/*`, blocking):** the PR contract check (S-DEV-010), the code diff check (S-DEV-028), the generator check (S-DEV-043), the regression-test check (S-DEV-029) on `fix` PRs, and the replay check (S-DEV-030) on `dev-upkeep` PRs;
  - **human PRs (report only):** the code diff check, the generator check when the PR touches `outputs`, and the contract check when the PR carries the block (S-DEV-009);
  - **other roles' agent PRs:** only the citation scan, plus the generator check (blocking) when the PR touches `outputs`. Their own G3 checks belong to their roles;
  - **after each merge, on each operator `implemented_acs[]` comment, and nightly:** the implementation check (S-DEV-044);
  - **nightly:** the readiness re-run (S-DEV-007) and the outcome check (S-DEV-039).

  Checks that build or run code do so in the S-DEV-042 sandbox profile. *Depends on:* S-BA-051, S-DEV-007, S-DEV-010, S-DEV-016, S-DEV-028, S-DEV-029, S-DEV-030, S-DEV-039, S-DEV-042, S-DEV-043, S-DEV-044, OD-SEC-2.
- **S-DEV-028** Code diff check detail:
  - **Tests** are compared as a net set keyed by (test ID v1, cited IDs) (S-DEV-045). First, the check maps old paths to new ones with the code host's rename detection, and rewrites base test IDs and flag elements to the new paths. So a moved or renamed file whose tests keep their names, citations and assertion lines isn't flagged. A test whose key disappears, whose assertion lines shrink, or that has an assertion line changed while uncited, is flagged. Where S-DEV-045 falls back, any decrease in a file's net count of assertion lines is flagged.
  - **Cited values:** for a changed assertion line in a test that carries `cites:`, DEV defers to S-QA-040's assertion-diff check and cited-value lint, which run blocking on DEV agent PRs (S-QA-041), and raises no flag of its own. Assertion removals, net decreases, and changes in uncited tests stay flagged here (closing OD-DEV-1's checks).
  - **Guard lines:** a removed or changed line matching an authorisation, validation, permission-deny, suppression or testability pattern is flagged, also when it moves.
  - **Verification configs:** any diff under `verification_config` is flagged, until a finer per-tool rule exists.
  - **Flag IDs** come from (check, element), so a sign-off holds across rebases, and a push that changes the element voids it (S-ARCH-053). The element is: for a guard line, (file, pattern class, line hash); for a test, its test ID; for a `protected` or `verification_config` change, (file, hunk hash); for a dependency, (name, to-version); for `not_unit_observable`, the `fixes.target`.
  - **Spec-side loosening** is ARCH's (S-ARCH-044). Semantic loosening that no pattern sees is CC-4's job (S-DEV-031), and the human judges it from the decision summary.

  *Depends on:* S-ARCH-044, S-ARCH-053, S-DEV-004, S-DEV-018, S-DEV-031, S-DEV-045, S-QA-040, S-QA-041, OD-DEV-1.
- **S-DEV-029** Regression-test check. On a `fix` PR, it runs the PR's added or changed tests that cite the `fixes.target` against the merge-base code with only those tests applied. They must build there, and at least one must fail with an assertion failure, as the runner's report classifies it, not an error, a setup failure or a build failure. All must pass on the head. A fix that can't be tested against the base code's interfaces uses `not_unit_observable` (S-DEV-010). Like S-GEN-067's symptom check, this proves the test sees the defect. *Depends on:* S-GEN-067, S-DEV-010, S-DEV-016.
- **S-DEV-030** Replay check, the guard of the `dev-upkeep` lane (S-DEV-037). It re-runs each `tool_runs[]` entry with the base branch's `upkeep_tools` at its pinned version, on the base commit, over the listed paths. It reports whether the result equals the head byte for byte (replay-verified), which S-DEV-018 also uses. A PR is lane-eligible only when:
  - it is replay-verified, and `residual_edits` is empty;
  - it touches no `dependency_files`, `protected`, `verification_config`, `generated`, `unit_tests` or other test path;
  - the build and the area's whole suite pass unchanged.

  The result is posted as a check status. Only the check, never the agent, marks a PR lane-eligible. *Depends on:* S-DEV-004, S-DEV-018, S-DEV-037.
- **S-DEV-043** Generated code. `generated` paths change only as the output of a `generators` entry (S-DEV-004). The generator check re-runs a generator, with the base branch's declaration and the head's inputs, when the PR touches its `outputs`, or when a DEV agent PR changes its `inputs`. A mismatch exists only then: the head's outputs differ byte for byte from the re-run. A mismatch is a hand edit, which is blocked (S-DEV-018). A PR that changes only inputs, such as an Architect PR changing an approved spec, is never a hand edit. The regeneration arrives in the implementing Developer PR. Clients and stubs generated from approved specs (S-ARCH-047) arrive this way, with the spec files as inputs. Where a stack doesn't commit generated code, `generated` is empty and CI builds it. *Depends on:* S-ARCH-021, S-ARCH-035, S-ARCH-047, S-DEV-004, S-DEV-018, S-DEV-027, S-DEV-042.
- **S-DEV-044** Implementation status: the "requirement implemented" signal (completes OD-BA-2's knowledge-drafting trigger). The implementation check derives it from the blocks of merged PRs (S-DEV-009):
  - **AC:** `implemented` once a merged PR declares it `full`, and `partial` while merged PRs only declare it `partial`. A changed AC gets a new ID (S-BA-010), so it starts unimplemented;
  - **Who may declare:** a DEV agent PR's block, a human PR's block, or an operator comment on the AC's ticket whose machine-readable block lists `implemented_acs[]`. The comment form covers ACs that no code PR delivers, such as DevOps or content work. It is read through the tracker with the `governance/operators.yml` actor check (S-DEVOPS-021);
  - **Revert:** when the code host marks a declaring PR as reverted, its declarations are withdrawn. The AC's status is then recomputed from the remaining declarations;
  - **REQ:** implemented once all its ready ACs are;
  - **`changes` entry:** implemented once every ready AC of the requirement that cites its rule is. For `rule: new`, that means once the REQ is implemented.

  **Event.** Whenever any declaration source moves a REQ or a `changes` entry into or out of `implemented`, the check publishes `{req, acs, changes[], direction: implemented | withdrawn, source: merge | comment | revert, ref}` as a CI artifact. It also dispatches the knowledge-drafting workflow as a check event (S-BA-034 classes), so S-BA-023 fires on implemented behaviour, never on a partial PR. Sources are a merge (including a revert), and an operator `implemented_acs[]` comment.
  - **Runs:** the event comes from the post-merge run, from a run triggered by that comment, and from the nightly run. The nightly run publishes the per-AC status as the DEV implementation matrix, and dispatches any transition since the previous matrix that no earlier run dispatched.
  - **Deduplication:** each event is keyed by (REQ or `changes` entry, direction, declaration-set hash), so one transition is dispatched once.

  A withdrawal is also listed in the digest. The runs are scheduled and post-merge jobs (S-DEVOPS-031). Each one publishes the event from an event workflow with no `run` job, so no PR code ran in it, which is the only form the router accepts (S-DEVOPS-017). *Depends on:* S-GEN-063, S-GEN-071, S-BA-010, S-BA-023, S-BA-034, S-DEV-009, S-DEVOPS-017, S-DEVOPS-021, S-DEVOPS-031.
- **S-DEV-045** Test ID v1. A test's ID is `<path>::<name>`, as the area's `test_list` command prints it. Checks run that command on the base and the head, and never use an agent-declared test list. A test spans from its `test_decl` line, matched by name, to the next `test_decl` line or the end of the file. An assertion line belongs to the test whose span holds it. A `cites:` token belongs to the test whose declaration line holds it, or that is declared within the 3 lines after it (S-DEV-016). When a listed test matches no `test_decl` line, as with parametrised or generated tests, the checks fall back to per-file net assertion counts (S-DEV-028). Test ID v1 is offered to BA's `verifying_checks` and to QA (OD-DEV-1). *Depends on:* S-DEV-004, S-DEV-016, S-DEV-028, OD-DEV-1.

### Code checklist (reviewer/code)

- **S-DEV-031** The checklist (closes the DEV part of OD-GEN-8, and carries OD-ARCH-1's `check: review` item). Item IDs are stable. A staff skill PR that removes or rewords a CC item is flagged by the checklist diff check, as in S-ARCH-044.

  | ID | Item | Finds |
  | --- | --- | --- |
  | CC-1 | Requirement fit | Behaviour no declared AC asks for; an AC declared `full` but partly built; a requirement reinterpreted instead of raised (S-DEV-008) |
  | CC-2 | ADR constraints | A `check: review` constraint violated, missing from `constraints[]`, or marked `n/a` without a sound reason. Cites ADR-n/C-k (S-ARCH-026) |
  | CC-3 | Interfaces | Units, error semantics or security requirements that differ from the declared version where the conformance check can't see them (S-ARCH-022) |
  | CC-4 | Security | A new entry point without the authorisation the AC's `permissions` need; missing input validation; injection; secret handling; a `protected` change without a reason. Findings on exploitable weaknesses go private (S-DEV-019) |
  | CC-5 | Tests and oracle | A declared AC with no citing test and no reason; an expected value read from the code under test; an unlabelled characterization test; a fix without a test that sees the defect (S-DEV-015) |
  | CC-6 | Testability in code | A `provided` item of S-DEV-013 missing or broken |
  | CC-7 | Data | Real personal data in fixtures or logs (S-DATA-004); production data in tests |
  | CC-8 | Conventions and maintainability | `AGENTS.md` breaches, duplication, dead code, swallowed errors |
  | CC-9 | Dependencies | A dependency without a reason, outside an ADR technology constraint, or a service that may fail S-DATA-006 |

  *Depends on:* S-GEN-015, S-DATA-004, S-DATA-006, S-ARCH-022, S-ARCH-026, S-DEV-008, S-DEV-013, S-DEV-015, S-DEV-019, OD-GEN-8, OD-ARCH-1.
- **S-DEV-032** Output and evaluation:
  - **Output:** one advisory comment per run, never an edit, with a digest pointer. It holds a verdict (ready, ready with questions, not ready); at most 7 findings as in S-BA-032, by severity, each with a finding ID derived from (CC ID, file and symbol, cited ID), a location, a suggestion and the cited IDs; questions in the S-BA-014 form; and a machine-readable block with the reviewed SHA and the finding IDs and classifications. Until the checklist qualifies, the comment is headed "not yet qualified".
  - **Evaluation:** the default `reviewer/<other type>` row of S-GEN-045, unchanged. Its artifacts are product PRs (diff plus block), seeded to cover every CC item. Caps as in S-GEN-057.
  - **Escaped defects:** a merged `fix` PR attributed to a feature PR that `reviewer/code` reviewed (S-DEV-041) becomes a seeding input. The escaped PR itself never becomes a hidden or promotion task (S-GEN-028).

  *Depends on:* S-GEN-028, S-GEN-045, S-GEN-057, S-GEN-062, S-BA-014, S-BA-032.

### Caps, records and prerequisites

- **S-DEV-033** Per-run caps (closes OD-GEN-4 for DEV):
  - **Developer:** $6 per run, 45 min *(starting value)*. One run covers one PR-sized slice, one fix-up, or one bootstrap area.
  - **`dev-upkeep`:** $2 per run, 20 min *(starting value)*.
  - **`reviewer/code`:** as in S-GEN-057.

  Eval worst cases under S-GEN-070:
  - Developer: 20 × 5 × $6 = $600, plus $20 for the judge, so the skill-PR budget is $372. A promotion attempt: 10 × 5 × $6 = $300.
  - `dev-upkeep`: 20 × 5 × $2 = $200, so the budget is $120. A promotion attempt: $100.
  - `reviewer/code`: 30 × 5 × $1 = $150, with no judge, so the budget is $90.

  *Depends on:* S-GEN-056, S-GEN-057, S-GEN-059, S-GEN-070.
- **S-DEV-034** DEV run records add these fields inside `role` (S-GEN-029): `kind`, `ticket`, `ac_ids`, `if_versions`, `constraint_ids`, `files_changed`, `lines_changed`, `tests_added`, `characterization_tests`, `flags`, `defect_items_raised`, `design_requests`, `fixup_round`, `tool_ids`, `lane_eligible`. *Depends on:* S-GEN-029.
- **S-DEV-035** Testability prerequisites (closes OD-TESTAB-6 for DEV):
  - **Developer:** digest-addressed builds for the area (S-TESTAB-003); S-TESTAB-006 sources (ready ACs, and approved versions where the area has interfaces); the area's `.staff/code.yml` entry. Tests that run out of process also need S-TESTAB-002.
  - **`dev-upkeep`:** S-TESTAB-003, and a green suite for the area on `main`, without which behaviour preservation can't be checked.
  - **`reviewer/code`:** the area's ADRs and specs (S-TESTAB-006). Without them, CC-2 and CC-3 check only within the PR, and the output says so.

  *Depends on:* S-TESTAB-001, S-TESTAB-002, S-TESTAB-003, S-TESTAB-006, S-DEV-004.

### Eval rows

- **S-DEV-036** Eval rows (closes OD-GEN-3 for DEV). Scores are pooled (S-GEN-035). Hidden and promotion tasks are scored by script (S-GEN-041). Every task starts from a pinned build and snapshot in the S-GEN-066 sandbox (S-GEN-043).

  | Agent | Golden tasks | Promotion set minimum | Mode | Oracle | Primary metrics | Stage 1→2 threshold | Hard limits | LLM judge |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | Developer | 20 tasks *(starting value)*: 10 feature, 6 fix, 4 trap (2 requirement defects, 2 design needs). Each feature task has ready ACs, approved versions, accepted ADRs with a `check: review` constraint, and an existing cited test that a careless change breaks | 10 *(starting value)*: 5 feature, 3 fix with holdout seeds, 2 traps with holdout seeds | Diff-seeded (fix), artifact-seeded (traps), held-out non-bug tasks (feature) | Scripts: held-out acceptance tests, symptom checks, trap matching (below) | AC pass rate, fix rate, regression-test rate, trap recall, false-escalation rate | AC pass ≥80%, fix ≥70%, regression test ≥70%, trap recall ≥60%, false escalation ≤20% *(starting value)* | Schema-valid output; no write outside scope; existing suite green on every head; no S-DEV-018 flag that the task spec doesn't expect; every new test cites a source or is labelled; bug-encoding 0; no code for a trapped AC | Yes, for maintainability. Reported, not gating |
  | `dev-upkeep` | 20 scripted tasks *(starting value)*: 8 tool runs, 5 codemod migrations with 1–3 call sites the codemod misses, 4 dependency bumps with an API change, 3 clean | 10 *(starting value)*: 4, 2, 2, 2 | Diff-seeded (scripted change tasks) | The S-GEN-067 check fails on the planted state (lint errors, deprecated calls, old version) and passes when fixed; held-out behaviour tests | Task success, clean no-op rate | Success ≥80%, clean no-op ≥90% *(starting value)* | Held-out behaviour tests green on every head; schema-valid; no write outside scope | No |
  | `reviewer/code` | As in S-GEN-045, the default row (S-DEV-032) | | | | | | | |

  **Specs and catalogue.** The seeding agent writes every task and its spec (S-GEN-067). A feature task's spec is a set of held-out acceptance tests, derived from its ACs, that fail on the base and pass on a reference implementation. A fix task's spec is the symptom check of its seeded bug, with a defect ticket that describes the symptom. A trap's spec is a defect spec keyed (AC ID, defect kind) or (AC ID, need). The 5 seeded Developer promotion tasks add 15 entries to the holdout catalogue, and the 10 seeded `reviewer/code` promotion PRs add 30 (S-GEN-039). Feature and `dev-upkeep` tasks are non-bug tasks (S-GEN-038) and add none.

  Formulas:
  - **AC pass rate:** held-out acceptance tests passing on the agent's head / held-out acceptance tests, over feature tasks.
  - **Fix rate:** fix tasks whose symptom check passes on the head with the existing suite green / fix tasks.
  - **Regression-test rate:** fix tasks whose added test fails on the seeded version and passes on the corrected one / fix tasks.
  - **Bug-encoding:** added tests that pass on the seeded version and fail on the corrected one.
  - **Trap recall:** planted traps matched by a defect item or design request with the right key / planted traps.
  - **False-escalation rate:** defect items and design requests matching no planted trap / those raised.
  - **Task success:** non-clean `dev-upkeep` tasks whose S-GEN-067 check passes with the behaviour tests green / non-clean tasks.
  - **Clean no-op rate:** clean tasks with no patch / clean tasks.

  *Depends on:* S-GEN-035, S-GEN-036, S-GEN-037, S-GEN-038, S-GEN-039, S-GEN-040, S-GEN-041, S-GEN-042, S-GEN-043, S-GEN-044, S-GEN-045, S-GEN-066, S-GEN-067, S-DEV-018, S-DEV-032.

### Stage rules

- **S-DEV-037** Stage-2 and stage-3 rules (closes OD-GEN-5 for DEV). The role demotion triggers add to those in S-GEN-052.

  | Agent | Stage-2 quality metric that must hold for stage 3 | Role demotion trigger → stage 1 | Stage 3 |
  | --- | --- | --- | --- |
  | Developer | None, because it has no stage 3 | Escaped code defect rate >25% *(starting value)*, or live defect-item precision <50% *(starting value)* (S-DEV-038) | None. Every Developer change implements or alters behaviour the human must review, so it stops at stage 2 |
  | `dev-upkeep` | Upkeep rework rate ≤5% *(starting value)* | Upkeep rework rate >15% *(starting value)* | **Change class:** PRs the replay check marks lane-eligible (S-DEV-030): pure tool output, no residual edit, no dependency, protected, verification-config, generated or test path. Dependency bumps are never in the lane (S-SEC-009). **Guard:** the replay check plus the code diff check (S-DEV-018). **Critical miss:** a merged lane PR that the replay check didn't reproduce, that touched an excluded path, or that was reverted for a behaviour change |

  `reviewer/code` is advisory at every stage (S-GEN-045, S-GEN-062). *Depends on:* S-GEN-045, S-GEN-052, S-GEN-053, S-GEN-062, S-SEC-009, S-DEV-018, S-DEV-030, S-DEV-038.

### Role metrics and outcome records

- **S-DEV-038** Role metrics (closes OD-GEN-7 for DEV, with S-DEV-039). Windowed metrics count only items whose window has closed. Windows are *(starting value)*.

  | Metric | Formula |
  | --- | --- |
  | Escaped code defect rate | Merged Developer `feature` PRs with ≥1 escaped defect / Developer `feature` PRs merged at least 30 days ago, last 20. An escaped defect is a ticket that an operator labelled `dev:fix` within 30 days of the feature PR's merge, and whose merged `fix` PR (any author) targets an AC or an element of an IF version that the feature PR declared |
  | Live defect-item precision | Developer requirement-defect items with operator `verdict:confirmed` / those with a verdict, last 20 |
  | Design-request conversion | Design requests followed by `arch:design` on the ticket within 14 days / design requests at least 14 days old, last 20. Reported |
  | Fix-up runs per PR | Fix-up runs / merged Developer PRs, last 20. A load signal |
  | Upkeep rework rate | Merged `dev-upkeep` PRs with a human commit before merge, or reverted or redone within 14 days / `dev-upkeep` PRs merged at least 14 days ago, last 20 |
  | Declared-AC test coverage | ACs declared `full` in merged PRs with ≥1 citing test on `main` / such ACs, nightly snapshot. Reported |
  | Characterization share | Characterization tests / DEV unit tests added, last 20 PRs. Reported |
  | Not-unit-observable rate | Merged `fix` PRs that use `not_unit_observable` / merged `fix` PRs, last 20 *(starting value)*. Reported |

  *Depends on:* S-GEN-032, S-GEN-071, S-DEV-039.
- **S-DEV-039** Outcome records. A nightly DEV check derives outcomes from the product repo and the tracker and emits them through the recorder (S-GEN-026) as `check_outcome` records (S-GEN-031).
  - **Linked, per artifact:** one record per merged DEV PR, with `artifact_id` = the PR number and `drafting_run_id` = the run of the PR's first agent commit, read per merged PR (S-GEN-029). The run IDs of fix-up commits go in `role.fixup_run_ids`. Fields: `merged`, `human_commits_before_merge`, `reverted_14d`, `escaped_defect_30d`, `flags`. Requirement-defect items (`artifact_id` = item ref, with `confirmed` or `rejected` from operator verdicts read through the tracker) and design requests (`artifact_id` = comment ref, with `converted_14d`) are linked to the run that raised them. Comments carry no commit trailer, so the write stage puts its `run_id` in the machine-readable block of every comment it posts. The check reads that block only from comments authored by the staff-engineering identity, as S-BA-017 does for staff-review.
  - **Unlinked nightly findings,** keyed per S-GEN-031: waiting tickets (ticket ref); open PRs whose ACs stopped being ready (PR number plus AC ID); declared ACs without a citing test (AC ID); PRs that hit the fix-up limit (PR number).

  The ops stage job computes S-DEV-038 from these records. *Depends on:* S-GEN-026, S-GEN-029, S-GEN-031, S-GEN-071, S-BA-017, S-DEV-034, S-DEV-038, S-DEVOPS-021.

### Interfaces with other roles

- **S-DEV-040** What DEV provides and consumes:

  | Artifact | Provider → consumers |
  | --- | --- |
  | Product-PR block (S-DEV-009) | DEV → the BA and ARCH trace and conformance checks, QA test generation |
  | Implementation status and its event (S-DEV-044) | DEV → knowledge drafting (S-BA-023) |
  | Test citation form v1 (S-DEV-016), test ID v1 (S-DEV-045) | DEV → BA and ARCH trace checks, BA `verifying_checks` (S-BA-008); QA (OD-DEV-1) |
  | Generated clients and stubs (S-DEV-043) | DEV, from ARCH specs (S-ARCH-047) |
  | Implemented-interface source (S-DEV-012) | DEV → ARCH conformance check |
  | Fix PRs, test-gap notes, escaped-defect seeds (S-DEV-017) | DEV → QA (OD-DEV-2), the seeding agent |
  | Requirement-defect items; design requests (S-DEV-008) | DEV → BA; the human and ARCH |
  | Code and `.staff/code.yml` patterns | DEV → DEVOPS (build and deploy), QA |
  | Ready ACs, rules, test conditions, BA trace matrix | BA (S-BA-048) → DEV |
  | IF versions, ADRs, components, drift tickets, ARCH trace matrix | ARCH (S-ARCH-047) → DEV |
  | Independent tests, mutation survivors, healer labels, defect tickets | QA (OD-DEV-1, OD-DEV-2) → DEV |
  | Builds, required checks, tokens, reports, event routing | DEVOPS (S-DEVOPS-017, -018, -020, -021, -024, -031, -038) → DEV |

  *Depends on:* S-BA-008, S-BA-023, S-BA-048, S-ARCH-047, S-DEV-043, S-DEV-044, S-DEV-045, S-DEVOPS-017, S-DEVOPS-018, S-DEVOPS-020, S-DEVOPS-021, S-DEVOPS-024, S-DEVOPS-031, S-DEVOPS-038, OD-DEV-1, OD-DEV-2.
- **S-DEV-041** Escaped defects feed back:
  - **Metrics:** a merged `fix` PR is attributed to the feature PR that declared its target (S-DEV-038).
  - **Seeds:** the seeding agent reads merged `fix` PRs (target, regression test) from the product repo as seeding inputs for Developer fix tasks and `reviewer/code` PRs (S-GEN-026). The fixed item itself never becomes a hidden or promotion task (S-GEN-028).
  - **Requirement defects** follow BA (S-BA-033, S-BA-047). Test gaps go to QA (OD-DEV-2).

  *Depends on:* S-GEN-026, S-GEN-028, S-BA-033, S-BA-047, S-DEV-032, S-DEV-038, OD-DEV-2.

### Open dependencies closed by this doc

| Open dependency | Closed by |
| --- | --- |
| OD-GEN-1 | S-DEV-006 |
| OD-GEN-2 | S-DEV-004 (paths), S-DEV-005 (agent scope) |
| OD-GEN-3 | S-DEV-036 |
| OD-GEN-4 | S-DEV-033 |
| OD-GEN-5 | S-DEV-037 |
| OD-GEN-6, OD-SEC-1 | S-DEV-021 |
| OD-GEN-7 | S-DEV-038, S-DEV-039 |
| OD-GEN-8 (DEV part) | S-DEV-031, S-DEV-032 |
| OD-GEN-9 (DEV part) | S-DEV-018, S-DEV-027 to S-DEV-030, S-DEV-043, S-DEV-045 |
| OD-GEN-10 (DEV part) | S-DEV-014, S-DEV-015. QA side: S-QA-012 |
| OD-TESTAB-3 | S-DEV-013 |
| OD-TESTAB-6 | S-DEV-035 |
| OD-BA-2 | S-DEV-007 (ready ACs only), S-DEV-009 (declaration), S-DEV-044 (the implemented signal that triggers knowledge drafting) |
| OD-BA-3 (developer part) | S-DEV-007 (ready ACs only), S-DEV-008 (requirement-defect items), S-DEV-017 (defect flow) |
| OD-ARCH-1 | Never edit `architecture/**`: S-DEV-005. Design request: S-DEV-008. Wait on `pending`: S-DEV-007. `implements`: S-DEV-009. `check: review` item: S-DEV-009 and CC-2 in S-DEV-031. Drift work tickets: S-DEV-006, S-DEV-017. Implemented-interface source: S-DEV-012. S-ARCH-025 items: S-DEV-013 |

No OD-DATA item is addressed to DEV: OD-DATA-1 is DevOps, and OD-DATA-2 is BA and QA. S-DEV-020 keeps DEV agents off production-derived sources. Not addressed to DEV: OD-SEC-2, OD-TESTAB-1, -2, -4 and -5, OD-BA-1, -4, -5 and -6, OD-ARCH-2 and -3.

## Assumptions

Items 1 and 14 list the values the human accepted as starting values. Item 2 applies a human decision. Items 3–13 and 15–21 are designer defaults. No *(proposed)* item is open.

1. **Accepted values** *(starting value, `docs/decisions.md`, 2026-11-20, roles/developer round 1, auto-accepted recommendation)*:
   - at most 3 fix-up runs per PR (S-DEV-006); a weekly `dev-upkeep` run per area (S-DEV-006);
   - at most 500 changed lines per PR, excluding generated paths and lockfiles (S-DEV-010);
   - at most 2 open Developer PRs per area awaiting review; at most 1 `dev-upkeep` PR per area per week (S-DEV-024);
   - caps: Developer $6 / 45 min, `dev-upkeep` $2 / 20 min (S-DEV-033);
   - Developer eval: 20 golden (10 feature, 6 fix, 4 trap), 10 promotion (5, 3, 2), and the five thresholds in S-DEV-036;
   - `dev-upkeep` eval: 20 golden (8, 5, 4, 3 clean), 10 promotion (4, 2, 2, 2), success ≥80%, clean no-op ≥90%;
   - escaped code defect rate: 30-day window, last 20, demotion above 25%. Live defect-item precision: last 20, demotion below 50%;
   - upkeep rework rate: 14-day window, last 20, ≤5% to hold for stage 3, >15% to demote;
   - design-request conversion: 14 days, last 20. Fix-up runs and characterization share: last 20.
2. **Context budget (`docs/decisions.md`, 2026-11-20):** the 15k budget stays, measured at characters / 3.2, with the cap computed per S-GEN-009 (S-DEV-026). The figures below are as of the last measurement, taken after shared/'s closing sections moved on demand, newlines included. The release gate re-measures every pack, and the current cap is the one S-GEN-009 computes:
   - **Always-loaded shared/:** 13,257 characters, about 4.14k tokens. The cap was about 34,745 characters.
   - **Working agents:** the always-loaded part is 25,427 characters. With shared/, about 12.09k tokens.
   - **`reviewer/code`:** the part above plus the checklist section (S-DEV-031, -032) is 28,281 characters. With shared/, about 12.98k tokens, within 15k and about 6.5k characters under the cap.

   Round 2 moved context (S-DEV-023), the interface source (S-DEV-012) and the security handling (S-DEV-019, -020) on demand, and put the new sandbox (S-DEV-042) and checks (S-DEV-043 to -045) there too. Human-owned items, path scope, triggers, readiness, the PR contract and the schemas stay always loaded.
3. **`.staff/code.yml` (S-DEV-004):** code layouts are product-specific, so the paths and patterns DEV checks need live in one human-only product-contract file. S-GEN-017 now lists the file in the product-contract layout, and S-GEN-025 makes it human-only, like every other `.staff/` file.
4. **Explicit start labels (S-DEV-006):** the Developer starts only when the human labels a ticket, not on every ready-gate merge. Priority is human-owned (S-BA-006), and the label bounds PR volume.
5. **`dev-upkeep` as its own agent (S-DEV-002):** the lane's PRs are pure tool output, so the agent's value is in scoping, batching, residual migration edits and dependency bumps. Its lane gives the human one-click review for the most frequent mechanical change.
6. **Code under S-SEC-002 (S-DEV-021, -042):** the harness derives code from the workspace diff, so no model output becomes a file. It passes in full, in chunks of at most 2,000 characters, so the free-text limit holds per field without passing content by reference. The parse, scope and secret checks add validation the limit alone can't give.
7. **Pattern-based guard lines (S-DEV-018, -028):** a per-stack pattern list can't see every semantic loosening. CC-4 and the human cover the rest. The patterns are human-authored and read from the base branch.
8. **Escaped-defect attribution (S-DEV-038):** a defect counts only when the human labels it `dev:fix` and a merged `fix` PR names its target. So the agent's own classification can't hide a defect. Human fixes without a PR block are missed.
9. **Outcome record granularity (S-DEV-039):** one record per merged PR keyed to the opening run. Fix-up run IDs are listed in `role`, so deleting a fix-up run (S-DATA-008) leaves only its ID behind.
10. **Default reviewer row and caps (S-DEV-032):** no GEN-owned row changes. A PR counts as an artifact for the artifact-seeded mode.
11. **Test citation token and test ID (S-DEV-016, -045):** a plain-text token works in every language and test framework without a per-stack parser. Test identity comes from the runner's own list output, plus one human-declared `test_decl` pattern per stack. Where those don't line up, per-file assertion counts are the safe fallback.
12. **Data migrations** are `protected` by default, so every one is flagged for sign-off. DevOps applies them at deploy time (S-DEVOPS-038).
13. **Conformance as scripts plus CC-2 (S-ARCH-002):** unchanged here. CC-2 results feed the ARCH open question on a separate conformance agent.
14. **Round-2 values, accepted** *(starting value, `docs/decisions.md`, 2026-11-20, roles/developer round 2, auto-accepted recommendation)*:
   - a `cites:` token counts for a test when it sits within the 3 lines above its declaration (S-DEV-016, -045);
   - the not-unit-observable rate uses the last 20 merged `fix` PRs, reported with no threshold (S-DEV-038).
15. **Work sandbox (S-DEV-042):** the S-GEN-066 profile already allows a launcher other than the eval runner. Prefetching the bundle means the model never holds a token. The bundle is enough because requirements, architecture and knowledge all sit in the product repo checkout. A run that needs a ticket outside its bundle asks in a comment instead.
16. **Generated code (S-DEV-043):** committed generated code is allowed only as reproducible generator output, the same idea as the replay check. Generator versions live in the human-only `.staff/code.yml`, so a generator bump is a human change.
17. **Implementation status (S-DEV-044):** it rests on `full` declarations, which CC-1 and the human's merge check. An AC that a human PR implements without a block, or that no code PR delivers, stays unimplemented until a block or an operator `implemented_acs[]` comment declares it. So knowledge drafting fires late rather than early. Reverts withdraw declarations, so a reverted behaviour doesn't stay "built".
18. **Verification configs (S-DEV-018, -028):** any diff is flagged rather than never-written, because adding a new test directory or a lint rule for new code is legitimate. A finer "loosened only" rule per tool is left for later.
19. **Overlap waits (S-DEV-024):** GEN's comment-on-the-other-PR rule suits documents, not code, so DEV waits instead. This is a stricter local rule, and S-GEN-060 is unchanged.
20. **Check scope (S-DEV-027):** the blocking DEV checks apply only to DEV agent branches, so BA, ARCH and QA agent PRs never need a product-PR block. The generator check still guards `outputs` from every author, because a hand edit there is a hand edit whoever makes it. Changing a spec input alone never fails, because spec first is ARCH's flow (S-ARCH-021).
21. **Red `main` (S-DEV-042):** "no base-passing test fails" replaces "all tests pass", so a run can fix a failing `main`, and failures it didn't cause are shown, not hidden.

## Open dependencies

- **OD-DEV-1 (test engineer): closed** by S-QA-007 (citation form), S-QA-008 (test ID), S-QA-006 (oracle rule), and S-QA-040 and -041 (assertion-diff check and cited-value lint). What it asked for:
  - confirm or extend test citation form v1 (S-DEV-016) and test ID v1 (S-DEV-045) as the one form for every test, together with OD-BA-1 and OD-ARCH-2;
  - apply the S-DEV-015 oracle rule to QA unit tests, or a stricter rule that DEV tests also satisfy;
  - deliver the assertion-diff check and the cited-value lint so they cover `unit_tests` paths, replacing the minimal rule in S-DEV-028.
- **OD-DEV-2 (test engineer): closed** by S-QA-012 (the split, including no merges into DEV branches), S-QA-041 (base check), S-QA-029 (flaky hand-off) and S-QA-011 (ticket fields). What it asked for, the working split with DEV:
  - QA test generation reaches a DEV PR only as a test PR against its branch. It never pushes to that branch, and never touches `source` paths;
  - the mutation gate runs on the changed lines of DEV PRs and posts survivors as a structured PR comment;
  - the CI healer owns failing tests on `main`, and never heals a test inside an open DEV PR;
  - QA picks up the test-gap notes of fix PRs (S-DEV-017);
  - the CI healer picks up the tests that DEV decision summaries list as flaky (S-DEV-042), under its flaky-test policy;
  - QA defect tickets carry `{target, expected, actual, evidence_refs}`.
- **OD-DEV-3 (DevOps): closed.** Work sandbox and fetch: S-DEVOPS-024. DEV checks with base builds: S-DEVOPS-020 and -024. Implementation runs: S-DEVOPS-031. `dev:*` routing: S-DEVOPS-017. Tracker, revert and rename data: S-DEVOPS-021. `interface_source`: S-DEVOPS-031. Tokens without workflow permission: S-DEVOPS-018. Reports through the mirror: S-DEVOPS-031. Migrations: S-DEVOPS-038. What it asked for:
  - the S-DEV-042 work sandbox: the fetch step with read-only tokens, the S-GEN-066 sandbox job launched from its bundle, and the hand-off to the write stage;
  - the DEV checks as required checks under OD-SEC-2, including the base-commit builds of the regression-test, replay and generator checks, which run in the same sandbox profile;
  - the post-merge, comment-triggered and nightly runs of the implementation check, each of which can dispatch the knowledge-drafting workflow (S-DEV-044);
  - tracker webhook routing for the `dev:*` labels, with the S-DEV-006 event classes and the operator actor check; read-only tracker access for the readiness, contract, implementation and outcome checks, including operator `implemented_acs[]` comments (S-DEV-044); the code host's revert and rename data for S-DEV-028 and -044;
  - the `interface_source` job, which publishes its output as a CI artifact (S-DEV-012);
  - per-job tokens without the workflow-file permission for the Developer and `dev-upkeep` (S-DEV-003);
  - lint, deprecation and dependency reports per area as CI artifacts, through the package mirror (S-SEC-009);
  - how `protected` data migrations are applied at deploy time.

## Open questions

None needs an answer now. Each has a recommended option:
- [ ] Could patch-level bumps of already-approved dependencies ever join the `dev-upkeep` lane? Options: never; after 20 bump PRs merged with no revert; only for dev-only dependencies. **Recommended: never for now.** S-SEC-009 requires explicit sign-off, and the replay guard can't vouch for third-party code. Revisit with the first rework data.
- [x] Is independent QA unit-test generation on Developer PRs worth its cost once DEV unit tests pass the mutation gate? Settled by S-QA-012: on DEV agent PRs, `test-gen-unit` runs only on mutation-gate survivors.
- [x] Should GEN list `.staff/code.yml` in the S-GEN-017 layout, so QA and DEVOPS can reuse its patterns? Yes: S-GEN-017 now lists it.
