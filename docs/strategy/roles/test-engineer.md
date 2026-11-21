# Test Engineer Strategy (QA)

Updated Nov 20, 2026

## Purpose and scope

This doc covers how the product is tested when one human works with agent staff: test layers, test generation, healing, exploratory testing, mutation and the quality gates. QA comes after BA, ARCH and DEV (`docs/decisions.md`, 2026-11-20). It consumes ready ACs, test conditions, rules, approved interface versions, accepted QAS and product PRs, and gives every role one test convention. It is product-agnostic and stack-agnostic: tests on each layer use the stack of the app code on that layer (S-GEN-002).

It honours the common set in S-GEN-064, plus S-GEN-015 (it consumes test conditions) and S-GEN-025 (it authors `knowledge/discovered/**`). GEN, shared/, BA, ARCH and DEV decisions are referenced by ID, never restated. Its main source is the legacy `docs/test-automation-strategy.md`; where a later decision differs, the later decision wins (Assumptions item 3).

The part from "On-demand reference" on is not always loaded. Each QA agent loads a pack: the always-loaded part plus its own section (S-QA-020).

Markers: *(starting value)* means accepted in `docs/decisions.md` (2026-11-20 or 2026-11-21). *(proposed)* means awaiting confirmation, and none is open. Named tools are examples.

## Ownership and agents

- **S-QA-001** Ownership split:
  - **The human decides** what counts as a bug (verdicts on suspected issues, failure items and draft bug tickets), test priorities (the `qa:*` start labels and the charter's `to_discover` line), every merge (S-GEN-003), sign-off on every flagged diff that removes or weakens verification (G3), quarantine extensions, and `.staff/tests.yml`.
  - **Agents** generate, run, heal, explore, classify and report.

  No agent sets anything human-owned (S-QA-015). *Depends on:* S-GEN-001, S-GEN-003, S-GEN-020, S-QA-015.
- **S-QA-002** Agents and checks in staff-qa (S-GEN-014). Each agent is its own eval unit (S-GEN-030):
  - **`test-gen-unit`, `test-gen-api`, `test-gen-ui`:** write tests per layer for product PRs, interface changes, coverage gaps and confirmed bugs, and repair citations. One unit per layer, because each layer has its own eval row, oracle run, mutation approach and thresholds (S-QA-049). They share one generation skill base.
  - **`ci-healer`:** classifies every failing test (S-QA-028), heals only test issues and landed fixes, and runs the flaky-test policy.
  - **`exploratory`:** drafts charters, runs timeboxed sessions against a running build, and drafts bug tickets, candidate tests and discovered knowledge.
  - **`mutant-drafter`:** drafts concern-driven mutants for the mutation gate from the rules, ACs, domain items, review findings and past bugs that touch the code under test (`docs/decisions.md`, 2026-11-21). It is a unit of its own, so that generation never grades its own tests: it never sees the tests it gates, and the generator never writes mutants. It holds no token and writes nothing (S-QA-039).
  - **`equivalence-filter`:** calls surviving mutants, tool and concern alike, equivalent or not. It is label-based (S-GEN-068), holds no token and writes nothing (S-QA-038).
  - **`reviewer/tests`:** the `tests` artifact type of the shared reviewer; this doc owns its checklist (S-QA-043). QA produces the most PR volume, and a qualified pre-review (S-GEN-062) checks what no script can: whether an expected value matches its cited source.

  **Checks, not agents:** the mutation gate (S-QA-036), the intake check that starts generation on DEV PRs (S-QA-012), and the QA diff checks (S-QA-040). The gate runs tool mutants and applies the drafter's mutants by script. The two model calls it uses, drafting and equivalence, are split out so each can be measured and staged on its own. *Depends on:* S-GEN-014, S-GEN-030, S-GEN-062, S-GEN-068, S-QA-012, S-QA-028, S-QA-036, S-QA-038, S-QA-039, S-QA-040, S-QA-043, S-QA-049.
- **S-QA-003** Identities. The QA agents run as the staff-qa identity, `reviewer/tests` as staff-review (S-GEN-026). Every agent that reads untrusted content and holds a write tool uses the two-stage split (S-SEC-002). Branches are `agent/<agent>/*`, under the prefix lint of S-ARCH-003. Per-job tokens carry no workflow-file permission (S-SEC-006). *Depends on:* S-GEN-026, S-SEC-002, S-SEC-006, S-ARCH-003.

## Layers and paths

- **S-QA-004** Layers. Tests use the layer's app stack and that ecosystem's standard test framework, so they share build tooling, types and mutation tooling with the code (`docs/decisions.md`, 2026-11-20).

  | Layer | Written by | Target share |
  | --- | --- | --- |
  | Unit | DEV for its own PRs (S-DEV-014); `test-gen-unit` for survivors and gaps (S-QA-012) | No ratio: every PR that changes logic gets unit tests |
  | API contract (schema, error format, auth per role, validation) | `test-gen-api`, from approved versions | ~50% *(starting value)* |
  | API behaviour (rules, invariants) | `test-gen-api`, from rules, ACs and test conditions | ~30% *(starting value)* |
  | UI journeys | `test-gen-ui`, for the core journeys in the product core (S-GEN-018) | ≤20% *(starting value)*. Other UI specs need an operator request |
  | Characterization | Tools or agents, labelled (S-QA-006) | Tracked separately |
  | Exploratory and manual | `exploratory`; the human for usability, visual and release acceptance | No ratio |

  The ratio covers agent-written API and UI tests. Black-box tools that commit no test code, such as spec fuzzers, are exempt from the stack rule. Behaviour tests prefer an in-process test client where the backend has one, because it makes code mutation affordable (S-QA-036). *Depends on:* S-GEN-002, S-GEN-018, S-DEV-014, S-QA-006, S-QA-012, S-QA-036.
- **S-QA-005** Test map (closes the artifact-path part of OD-GEN-2 for QA). The human declares QA's paths and per-layer settings in `.staff/tests.yml`, human-only like every `.staff/` file (S-GEN-025). Its schema ships in staff-qa `schemas/`. Per area and layer:
  - `paths`: test globs. The unit layer uses `unit_tests` from `.staff/code.yml` (S-DEV-004);
  - `stack`: a key into the `code.yml` `guard_patterns` and `test_list`, or the layer's own patterns and `test_list` where its framework differs; plus `expected_value` (a capture pattern for assertion lines) and the `matcher_strength` order;
  - `locators` (allowed and banned patterns), `mocks`, `request_docs` and `fixtures` globs, `mutation` (tool and command per approach) and `fuzz` (command or `none`). `fixtures` globs must sit inside the layer's `paths`.

  QA also keeps `qa/quarantine.yml`, the quarantine registry (S-QA-029). QA checks read both files from the base branch. Without an entry for its area and layer, a QA read stage fails closed and the digest lists the gap. *Depends on:* S-GEN-017, S-GEN-025, S-GEN-063, S-DEV-004, S-QA-029, OD-GEN-2.

## One test convention for every role

- **S-QA-006** Oracle rule for every test, on every layer and by every author (a stricter local rule on S-TESTAB-006; closes its part of OD-TESTAB-5):
  - Every expected value comes from a source cited by ID (S-QA-007): a ready AC, an active rule, a test condition, an approved or deprecated interface version for its own version (S-ARCH-021), or the `measure` of an accepted QAS. Never from what the code returns or the page shows.
  - Candidates are never an oracle (S-BA-022, S-ARCH-004).
  - A test with no source to cite is labelled `characterization`. So are tool-generated tests, recorded traffic, and tests of an `as-built` version until `provenance_confirmed_by` is set (S-ARCH-008). Characterization tests are reported separately in every metric and never count toward coverage or bugs caught.
  - Behaviour that needs a source and has none gets a `missing` requirement-defect item (S-QA-011).
  - Test design follows S-DEV-015's last bullet on every layer.

  A DEV test that meets S-DEV-015 meets this rule. The only addition is the QAS `measure` (closes OD-DEV-1's oracle item). *Depends on:* S-TESTAB-006, S-BA-022, S-ARCH-004, S-ARCH-008, S-ARCH-021, S-DEV-015, S-QA-007, S-QA-011, OD-DEV-1.
- **S-QA-007** Citation form. Every test uses test citation form v1 (S-DEV-016): the `cites:` token, or `characterization`. One additive extension: `QAS-n` joins the accepted IDs, for quality tests (S-QA-023). IF elements are cited as `IF-n@x.y.z#<element>`, with the operation, error or event name as the element, which the ARCH trace check reads (S-ARCH-029, -030). *Depends on:* S-BA-021, S-ARCH-029, S-ARCH-030, S-DEV-016, S-QA-023.
- **S-QA-008** Test ID. Every test uses test ID v1 (S-DEV-045) unchanged, from the layer's `test_list` (S-QA-005). BA `verifying_checks`, the stale-rule check, the QA checks, quarantine entries and QA records all key tests by it. *Depends on:* S-BA-008, S-BA-025, S-DEV-045, S-QA-005.
- **S-QA-009** Cited values are frozen. An agent never changes a cited expected value to make a test pass. The value changes only with its source: the cited ID retires with a replacement (S-BA-010, S-ARCH-012), or a newer interface version arrives (S-ARCH-023). The cited-value lint enforces it (S-QA-040).

  **When a cited test fails on the product PR it was written for:**
  1. The test stays, with the stack's strict expected-failure marker, so a later fix shows as an unexpected pass.
  2. The agent posts one advisory "suspected product issue" comment on the product PR: cited ID, expected and actual values, evidence refs. It never blocks the product PR.
  3. The human's verdict on the comment starts the generator again (S-QA-013): `verdict:confirmed` (a bug: it drafts the defect ticket, S-QA-011, and links it from the test); `qa:source-wrong` (it raises a requirement-defect item, and the test is regenerated once the source changes); or `verdict:rejected` (it fixes or drops the test).
  4. No expected-failure test reaches `main` without a linked defect ticket (S-QA-040). Merging follows S-QA-012.

  *Depends on:* S-BA-010, S-ARCH-012, S-ARCH-023, S-QA-011, S-QA-012, S-QA-013, S-QA-040.
- **S-QA-010** Inputs (closes OD-BA-1's schema, `changes` and trigger items, and the trigger part of OD-BA-3 for QA):
  - QA agents cite only ready ACs (S-BA-019), active rules, approved or deprecated versions (S-ARCH-011) and accepted QAS. The affected ACs of a `changed` requirement are skipped until it passes the gate again. Readiness comes from the BA and ARCH trace matrices of the latest `main` run.
  - Test conditions v1 (S-BA-048) is confirmed unchanged as the schema staff-qa consumes (S-GEN-022). The Analyst keeps authorship (S-BA-050).
  - A declared rule change is a `changes[]` entry with `accepted_by` set (S-BA-006) for a rule the test cites. Free-text notes never count.

  *Depends on:* S-GEN-022, S-BA-006, S-BA-019, S-BA-048, S-BA-050, S-ARCH-011, OD-BA-1, OD-BA-3.
- **S-QA-011** Problems go back (closes the defect-item part of OD-BA-3 for QA, and OD-DEV-2's ticket fields):
  - **Requirement problems** become requirement-defect items (S-BA-048), never free comments: two readings of an expected value → `ambiguous`; an AC or test condition against an active rule → `contradicts`; an outcome no stable identifier or seam exposes → `untestable`; behaviour with no source → `missing`.
  - **Product bugs** become draft defect tickets `{target, expected, actual, evidence_refs, repro[], severity_guess, build_digest, run_id}`. `target` is an AC, R-ID, IF element or QAS. `repro[]` holds at most 20 steps *(starting value)*, each a bounded field (S-SEC-002). The human labels a ticket `dev:fix` (S-DEV-017).
  - **Suspected vulnerabilities** go to private reports (S-SEC-011).

  *Depends on:* S-SEC-002, S-SEC-011, S-BA-048, S-DEV-017, OD-BA-3, OD-DEV-2.

## Working split with DEV

- **S-QA-012** Split (closes OD-DEV-2 and the QA part of OD-GEN-10):
  - **Test PRs:** QA reaches a product PR only through a test PR based on that PR's branch, so its tests run on the PR's build. It never pushes to that branch and never touches `source` paths (S-QA-014). A test PR merges only into `main` or a human product PR's branch, never into an `agent/*` branch. Once a DEV PR merges, the generator retargets its test PR to `main`, and the base check blocks any earlier merge (S-QA-041; `docs/decisions.md`, 2026-11-20). If the product PR closes unmerged, the test PR closes too.
  - **On DEV agent PRs** other than `kind: upkeep`, which intends no behaviour change (S-DEV-009), the QA intake check (S-QA-041) starts generation only where DEV tests leave work: `test-gen-unit` on mutation-gate survivors of the PR; `test-gen-api` and `-ui` for ACs declared `full` that sit in `untested_acs` with `other-layer`, and for the elements in `implements[]` (S-DEV-009). DEV tests already cite their sources, so regenerating everything would double the review load (DEV Open questions).
  - **On human PRs,** generation runs when an operator applies `qa:tests`.
  - **Mutation gate on DEV PRs** other than `kind: upkeep`: it runs on the changed lines when the PR becomes ready and when its review is re-requested, and posts survivors in one structured comment. It is advisory (S-QA-036). `test-gen-unit` owns those survivors; for the Developer they are advisory input only (S-DEV-014).
  - **`main` belongs to the healer:** it heals only on `main`, and never heals a test inside an open product PR. On a human PR it only comments a classification; DEV PRs handle their own failures (S-DEV-006, -042; S-QA-030).
  - **Test gaps:** a merged `fix` PR's `not_unit_observable`, and a merged PR's `other-layer` entries, start `test-gen-api` or `-ui` against `main` (S-DEV-010, -017).
  - **Flaky hand-off:** tests that DEV runs list as flaky (S-DEV-042) join the healer's nightly flake sweep (S-QA-029).
  - **Unit tests** that a DEV PR adds are DEV's (S-DEV-014). QA unit tests share the `unit_tests` paths and the same checks.

  *Depends on:* S-DEV-006, S-DEV-009, S-DEV-010, S-DEV-014, S-DEV-017, S-DEV-042, S-QA-014, S-QA-029, S-QA-030, S-QA-036, S-QA-041, OD-DEV-2, OD-GEN-10.

## Triggers, scope and human-owned items

- **S-QA-013** Triggers (closes OD-GEN-1 for QA). The event classes are those of S-BA-034: operator events, staff-app PR events (which may trigger only `reviewer/tests`), and check and schedule events. Everything else is dropped.

  | Agent | Starts when |
  | --- | --- |
  | `test-gen-*` | The intake check dispatches it for a DEV agent PR (S-QA-012). An operator applies `qa:tests` to a product PR, or re-applies it after new pushes. The mutation gate leaves survivors on its own test PR (S-QA-037). A merged PR leaves a test gap (S-QA-012). A spec-change event arrives (S-ARCH-054). The nightly run finds newly implemented IF elements (S-ARCH-027), implemented IF operations no test cites (S-ARCH-030), active rules without verifying checks (S-BA-021), or tests citing retired IDs (S-QA-025). The healer routes a `qa:test-update` item. A quarantined test it owns reaches the 14-day escalation (S-QA-029). An operator gives a verdict on its suspected-issue comment (S-QA-009), confirms a bug that came with a candidate test (S-QA-035), merges or closes the product PR its test PR is based on (S-QA-012), reviews its PR or answers its question |
  | `ci-healer` | A test fails in CI on `main`, or in a scheduled run on `main`. A strict expected-failure test passes. A test fails on a human product PR (classification only). The nightly flake sweep (S-QA-029). An operator gives a verdict on a failure item (S-QA-031), reviews its PR or extends a quarantine |
  | `exploratory` | The nightly run finds a REQ newly `implemented` (S-DEV-044): it drafts a charter. An operator applies `qa:explore` to that ticket, or dispatches it for an area: it runs a session. An operator reviews its PR |
  | `mutant-drafter` | The mutation gate's workflow launches it, before the mutants run, with the concerns of the code under test (S-QA-039) |
  | `equivalence-filter` | The mutation gate's workflow launches it with the run's survivors (S-QA-038) |
  | `reviewer/tests` | A `test-gen-*` or `ci-healer` PR outside the stage-3 lane becomes ready for review, or its review is re-requested. An operator applies `qa:review` to a human PR that touches test paths |

  A new push to a product PR doesn't re-run generation. A new run closes the earlier open test PR for the same product PR and layer as "superseded by #N". *Depends on:* S-GEN-005, S-BA-021, S-BA-034, S-ARCH-027, S-ARCH-030, S-ARCH-054, S-DEV-044, S-QA-009, S-QA-012, S-QA-025, S-QA-029, S-QA-031, S-QA-035, S-QA-037, S-QA-038, S-QA-039, OD-GEN-1.
- **S-QA-014** Path scope (closes the agent-scope part of OD-GEN-2 for QA). The scope lint (G2) enforces it by branch prefix (S-ARCH-003), and fails a QA commit without a `Staff-Run-Id` trailer (S-GEN-029).

  | Agent | Writes |
  | --- | --- |
  | `test-gen-unit` | The area's `unit_tests` globs |
  | `test-gen-api`, `test-gen-ui` | The layer's `paths`, `mocks` and `request_docs` globs |
  | `ci-healer` | Test paths of every layer; `qa/quarantine.yml` |
  | `exploratory` | `knowledge/discovered/**` (S-GEN-025) |
  | `mutant-drafter`, `equivalence-filter` | No paths and no token |
  | `reviewer/tests` | No paths: comments and the label `qa:not-ready` |

  Each agent never writes outside its row. In particular, no QA agent writes `source`, `protected`, `verification_config`, `generated` or `dependency_files` (S-DEV-004), `.staff/**`, `.github/**`, CI paths, `AGENTS.md`, `requirements/**`, `architecture/**` or other `knowledge/**` paths. *Depends on:* S-GEN-020, S-GEN-025, S-GEN-029, S-ARCH-003, S-DEV-004, S-QA-005, OD-GEN-2.
- **S-QA-015** Human-owned:
  - the labels `qa:tests`, `qa:explore`, `qa:review` and `qa:source-wrong`, accepted only from accounts in `governance/operators.yml` (S-GEN-071);
  - the charter's `to_discover` line, when an operator writes one (S-QA-033);
  - verdicts on suspected issues, failure items, draft bug tickets and equivalence calls (G12);
  - sign-offs on flagged diffs in the S-ARCH-053 form, and the one extension of a quarantine entry, with a written reason;
  - answers to QA questions, counted as in S-BA-015;
  - `.staff/tests.yml`.

  No QA agent applies or removes these labels or any `verdict:*` label (G12). Every check that reads them accepts them only from operator accounts. *Depends on:* S-GEN-020, S-GEN-071, S-BA-015, S-ARCH-053, S-QA-033.

## Safety, output and load

- **S-QA-016** Safety, QA's share of G3:
  - Never remove or weaken an assertion, skip a test, or change a cited value to make a test pass (S-QA-009).
  - Never heal a failure that the classification table doesn't label a test issue or a landed fix (S-QA-028). A suspected product issue is never healed.
  - Every diff the QA checks flag needs an operator sign-off (S-QA-040). An agent stays at stage 1 until every artifact type it changes has its check (S-GEN-051).
  - QA checks block agent PRs, DEV's included, and only report on human PRs (S-QA-041).

  *Depends on:* S-GEN-020, S-GEN-051, S-QA-009, S-QA-028, S-QA-040, S-QA-041.
- **S-QA-017** Work sandbox, a stricter local rule on S-SEC-002 and S-SEC-007 for every QA agent that runs the product or tests. It follows S-DEV-042's three steps: a model-free fetch step with read-only tokens builds the bundle (redacted per S-QA-048); the model works in the S-GEN-066 profile's `work` variant (S-DEVOPS-024), with test-only credentials and egress to the model endpoint, the package mirror and the run's isolated environment (S-TESTAB-002); the harness derives `files[]` from the workspace diff, as in S-DEV-021, and the write stage commits it byte for byte. *Depends on:* S-GEN-066, S-SEC-002, S-SEC-005, S-SEC-007, S-TESTAB-002, S-DEV-021, S-DEV-042, S-QA-048, S-DEVOPS-024.
- **S-QA-018** Stage-1 output (comment and draft only, S-GEN-052). One comment per drafted test PR, heal or discovered note, with the rendered decision summary and the full patch as a CI artifact (S-DATA-003), so each draft gets its own verdict (S-GEN-071).
  - `test-gen-*` comments on the product PR, or on the area's nightly QA draft ticket for other triggers.
  - `ci-healer` comments on the failure item (S-QA-031).
  - `exploratory` posts charters, session notes and draft bug tickets at every stage. Discovered notes are stage-1 drafts on the session ticket.

  Every comment carries its `run_id` in its machine-readable block, as S-DEV-039 needs. `verdict:confirmed` on a draft means it would merge as is. *Depends on:* S-GEN-052, S-GEN-071, S-DATA-003, S-DEV-039, S-QA-031.
- **S-QA-019** Load (S-GEN-061, S-GEN-073):
  - QA PRs count toward the working-agent cap. At most 2 test PRs per area await review across the three generators *(starting value)*; further triggers queue. The healer opens at most one heal PR and one quarantine PR per area per day *(starting value)*, one commit per test. Citation repairs arrive as one PR per area per night. `exploratory` opens at most one discovered-knowledge PR per area per week *(starting value)*.
  - A test PR changes at most 500 lines *(starting value)*, not counting request documents and recorded mocks.
  - **Overlap,** read as S-GEN-060 intends: a test PR based on a product PR's branch builds on that PR, so it doesn't overlap it. A QA run whose paths overlap any other open agent PR waits, a stricter local rule as in S-DEV-024, and the digest lists the wait.
  - Suspected issues, failure items, mutation comments, charters and bug drafts reach the human through the digest, one item per PR, ticket or check.
  - **Decision summary,** first in every QA PR: cited IDs, characterization tests, expected failures and their links, survivors and their categories, flagged diffs, quarantine entries with evidence, and the reviewer's verdict with the commit it reviewed.

  *Depends on:* S-GEN-060, S-GEN-061, S-GEN-063, S-GEN-073, S-DEV-024.
- **S-QA-020** Packs and retrieval (S-GEN-009, `docs/decisions.md`, 2026-11-20). Each QA agent loads a pack: the always-loaded part plus its own sections of the on-demand reference, in the same way as a reviewer pack. The packaging check (S-GEN-021) measures every pack below with the always-loaded shared/ part, at chars/3.2, against 15k. The figures are in Assumptions item 2.

  | Pack | Own sections |
  | --- | --- |
  | `test-gen-*` | Test generation (S-QA-021 to -026) |
  | `ci-healer` | CI healer (S-QA-027 to -032) |
  | `exploratory` | Exploratory (S-QA-033 to -035) |
  | `mutant-drafter`, `equivalence-filter` | Mutation (S-QA-036 to -039) |
  | `reviewer/tests` | Test checklist (S-QA-043, -044); QA checks (S-QA-040 to -042) |

  The fetch step adds the other moved decisions an agent acts on, per trigger:

  | Agent and trigger | Retrieves |
  | --- | --- |
  | `test-gen-*`: any run | S-QA-036, -037 (gate, survivors), -040 to -042 (QA checks), -047 (environments) |
  | `test-gen-*`: citation repair | S-QA-051 (lane class) |
  | `ci-healer`: heal or quarantine | S-QA-036 (healer guard), -040 to -042, -051 (lane class) |
  | `exploratory`: session | S-QA-047 (environments), -048 (data and security) |
  | `reviewer/tests`: any run | S-QA-036, -037 (survivors, for TR-6) |

  If a pack goes over, more sections move (S-GEN-048). *Depends on:* S-GEN-009, S-GEN-021, S-GEN-048.

## On-demand reference

### Test generation

- **S-QA-021** Generation inputs, in addition to the S-GEN-009 set:
  - **Always in context:** the product core; `AGENTS.md` conventions for the layer's stack, including the protocol rules (S-QA-022); the area's `.staff/tests.yml` and `.staff/code.yml` entries; own learnings.
  - **Fetched:** the product PR diff and block (S-DEV-009); the changed modules' existing tests, 2–3 of them as style references; cited ACs, test conditions and rules; IF versions and QAS; the ARCH drift report and trace matrices; survivors; candidate tests.
  - **Iteration:** the agent builds and runs its tests in the sandbox (S-QA-017) and iterates within its cap. A draft or push needs the build to pass, the conventions lint to be clean, and every new test to pass on the product PR's build or fail with a cited source under S-QA-009.
  - **Duplicates:** before writing, it checks existing tests by test ID, cited IDs and target, and skips behaviour already covered.

  *Depends on:* S-GEN-009, S-DEV-009, S-QA-009, S-QA-017, S-QA-022.
- **S-QA-022** Layer rules, kept in `AGENTS.md` per stack:
  - **Unit:** public interfaces only, mocks only at seams (S-TESTAB-008), the module's folder layout and naming. A survivor is the prompt: "write a test that kills this".
  - **API:** typed clients and stubs come from approved specs through DEV's declared generators (S-DEV-043); QA never hand-writes them. Every test asserts on the protocol's error channel, not on transport status alone; with GraphQL, that means the `errors` array and partial `data`. Authorization is tested per product user role on the same operation (S-TESTAB-004). Request documents live as files beside the tests and ask only for what the test asserts on. Coverage spans operations, fields, enum values, validation and error codes.
  - **UI:** core journeys only, unless an operator asks. A planner, a generator and a browser tool work in the front end's E2E framework (for example Playwright's test agents). Locators follow `locators`: accessible roles and names or test IDs (S-TESTAB-005), never CSS or XPath. Waits use readiness signals (S-TESTAB-007), not sleeps.
  - **Tools:** tool-generated tests (for example EvoMaster) are characterization, ported to the layer's stack. Spec fuzzing (for example Schemathesis) runs as an advisory check on product PRs that touch an implemented interface, and its findings go to the digest.

  *Depends on:* S-TESTAB-004, S-TESTAB-005, S-TESTAB-007, S-TESTAB-008, S-DEV-043, S-QA-006.
- **S-QA-023** Interfaces and quality scenarios (closes OD-ARCH-2):
  - **Contract tests cover implemented elements** (S-ARCH-021). The target set depends on context. On a product PR, it is the elements of the versions in its `implements[]`. On `main`, it is the elements the ARCH drift report lists as implemented, plus, where `interface_source` is `none`, every element of the versions that merged PRs declare in `implements[]`. A failing contract test counts as pending implementation (S-ARCH-027) only when the response shows the element is absent: an unknown operation, field or event, as the protocol reports it. Any other failure is a suspected product issue under S-QA-009. Elements pending implementation feed spec-derived mocks for consumers' tests, labelled with their version. Both follow the spec-change event (S-ARCH-054): a compatible change updates the affected tests, and a breaking change gets tests for the new major as its elements are implemented.
  - **Deprecated versions** keep their tests until the version retires. Deleting one earlier is blocked (S-QA-040).
  - **`as-built` versions** get characterization tests (S-QA-006). Once `provenance_confirmed_by` is set, cited contract tests are generated from the confirmed version. A characterization test is removed only when a cited test covers the same element, as a flagged diff.
  - **QAS with `verification: test` and owner QA:** `test-gen-api` writes quality tests citing `QAS-n` when the `measure` can be decided in a functional test environment, such as a limit, an error behaviour or a security requirement. A single-call latency test runs in a non-blocking job, because timing in an ephemeral environment is noisy. A `measure` that needs load, soak or capacity runs gets `verification: monitor` with owner DEVOPS (S-ARCH-009; `docs/decisions.md`, 2026-11-20).
  - **Contract results feed S-ARCH-026** where `interface_source` is `none` (S-DEV-012). The nightly contract run publishes per-element results as a CI artifact.

  *Depends on:* S-ARCH-008, S-ARCH-009, S-ARCH-021, S-ARCH-023, S-ARCH-026, S-ARCH-027, S-ARCH-054, S-DEV-009, S-DEV-012, S-QA-006, S-QA-009, S-QA-040, OD-ARCH-2.
- **S-QA-024** Test PRs:
  - One test PR per product PR and layer, based on the product PR's branch and merged as S-QA-012 says. Nightly and gap triggers target `main`, one PR per area and layer.
  - **Feedback:** survivors of the mutation gate start at most 2 feedback rounds *(starting value)*, each a run under the per-run cap. The survivors left after that get categories (S-QA-037).
  - **Mocks:** re-recorded mocks come with a per-field diff summary in the decision summary. Old mocks stay in use until the PR merges.
  - **Ready for review** only after the build, the conventions lint, the mutation gate and the QA diff checks have run (S-QA-040).

  *Depends on:* S-QA-012, S-QA-037, S-QA-040.
- **S-QA-025** Citation repair (closes OD-BA-1's re-pointing item). On a nightly finding that a test cites a retired ID (S-BA-021, S-ARCH-030):
  - **Re-point only** when a cited rule retired with `retired_reason: duplicate` and a `replaced_by` (S-BA-008). The meaning is unchanged, so the PR changes only `cites:` tokens. This is S-BA-053's duplicate case; its declared-change case doesn't apply, because a declared change alters the meaning a test asserts.
  - **Otherwise** the meaning changed (S-BA-010): a retired AC, a rule retired for another reason, or a new IF version. The test is regenerated against the replacement under S-QA-009.
  - Tests of a retired IF version are removed in the same run. S-QA-040 exempts them.

  *Depends on:* S-BA-008, S-BA-010, S-BA-021, S-BA-053, S-ARCH-030, S-QA-009, S-QA-040, OD-BA-1.
- **S-QA-026** Read-stage schema and write actions for `test-gen-*` (closes OD-GEN-6 and OD-SEC-1 for them; prose fields follow S-SEC-002):
  - **Read stage:** `pr` {kind: tests | repair, layer, product_pr, base, cited_ids[], characterization[], expected_failures[] {test_id, cites, expected, actual, evidence_refs}, survivor_categories[] (S-QA-037)}; `decision_summary`; `files[]` (harness-derived, S-QA-017); `suspected_issues[]`; `defect_items[]` (S-BA-048); `bug_drafts[]` (S-QA-011); `questions[]` (S-BA-014 form); `private_reports[]`; `source_refs[]`.
  - **Writes:** stage 1: comments as in S-QA-018, suspected-issue comments, requirement-defect items, draft defect tickets and private reports. Stage 2 adds: an `agent/test-gen-<layer>/*` branch and PR, pushes to it, retargeting and closing its own PRs, comments on its own PRs, and the label `agent`.

  *Depends on:* S-SEC-002, S-SEC-003, S-SEC-011, S-BA-014, S-BA-048, S-QA-011, S-QA-017, S-QA-018, S-QA-037.

### CI healer

- **S-QA-027** Reference run *(starting value)*: for a PR, the last green run of the test on the PR's merge-base; for `main` or scheduled runs, the last green run on `main` within 30 days. No reference run → needs human. Evidence comes from the per-test result history (S-DEVOPS-030), keyed by test ID v1, and from the PRs merged between the reference run and the failing commit, with their blocks (S-DEV-009). *Depends on:* S-DEV-009, S-QA-008, S-DEVOPS-030.
- **S-QA-028** Classification. Rows are evaluated top to bottom; the first match wins. Retries: 2 *(starting value)*.

  **Facts first.** Before the model runs, a script computes the facts that decide rows x, a, b and e, and injects them:
  - retry outcomes, flaky records and quarantine history (S-DEVOPS-030, S-QA-029);
  - declaration matches against `changes[]`, retired or `changed` IDs and newer IF versions (S-QA-010);
  - whether a reference run exists (S-QA-027);
  - ticket and `fix`-PR state.

  The model judges only c against d. The harness rejects a `row` that contradicts the facts, and any conflict becomes row e.

  | # | Evidence | Label | Action |
  | --- | --- | --- | --- |
  | x | A strict expected-failure test passes on every retry, and its linked defect ticket is closed or a merged `fix` PR names it (S-DEV-009) | `qa:fix-landed` | Heal PR that only removes the marker and links the ticket. Otherwise → row e |
  | a | Passes within the retry limit; isn't a new flake on a PR that touches the test's area or cited IDs (new = no flaky record in the last 28 days); and had no entry in `qa/quarantine.yml` at any time in the last 28 days, per the quarantine history (S-DEVOPS-030) | `qa:flaky` | Quarantine (S-QA-029); no heal |
  | b | Fails on every retry; the asserted behaviour changed, and the change is declared: a `changes[]` entry for a cited rule (S-QA-010), a cited ID retired or `changed`, or a newer version of the cited IF | `qa:test-update` | Route to `test-gen-<layer>` with the declaring ref, or to the human for a characterization test. Never a product issue |
  | c | Fails on every retry; asserted values and visible state match the reference run; only locators, timing or DOM or response structure changed (for unit tests, only a refactor such as a rename, move or signature change) | `qa:test-issue` | Heal PR under S-QA-030 |
  | d | Fails on every retry; the asserted behaviour changed with no declared change | `qa:product-issue` | Failure item with evidence (diff against the reference run, trace); never heal |
  | e | Anything else: a new flake on a PR touching the test's area, conflicting evidence, no reference run, no cited ID to match a declaration | `qa:needs-human` | Never heal |

  A test that fails the same way on every retry is a real failure, not a flake. *Depends on:* S-BA-006, S-DEV-009, S-QA-010, S-QA-027, S-QA-029, S-QA-030, S-DEVOPS-030.
- **S-QA-029** Flaky-test policy *(starting value)*:
  - A row-a test enters `qa/quarantine.yml` as `{test_id, evidence_refs, owner, since, expires, extension}` through a quarantine PR. Each new entry is a flagged diff (S-QA-040). `owner` is the generating agent for agent-written tests, otherwise the human.
  - Quarantined tests keep running in a nightly non-blocking job, so their flake rate is still measured.
  - After 14 days the digest escalates the entry. If the owner is an agent, its `test-gen-<layer>` is dispatched for a fix PR or a flagged deletion. The human may extend the entry once with a written reason (S-QA-015).
  - At 28 days CI stops honouring the entry (the quarantine wrapper of S-DEVOPS-031): the test runs blocking again, and the digest escalates it daily. The quarantine check fails only PRs that add or extend an entry beyond the limits (S-QA-040).
  - A test that had an entry at any time in the last 28 days, per the quarantine history (S-DEVOPS-030), goes to row e, not back to row a (S-QA-028).
  - **Flake sweep:** each night the healer re-runs on `main` the tests that DEV runs listed as flaky (S-DEV-042) and the tests whose recent runs passed only on retry, and classifies them.

  *Depends on:* S-DEV-042, S-QA-015, S-QA-028, S-QA-040, S-DEVOPS-030, S-DEVOPS-031.
- **S-QA-030** Heal rules:
  - Heals happen only on `main` (S-QA-012), and only for rows c and x. On a human PR the healer posts one classification comment; on a DEV PR it does nothing.
  - A row-c heal changes no assertion line, expected value, test data, cited ID or marker, and deletes no test. The assertion-diff check enforces it (S-QA-040).
  - **Healer guard:** the healed test kills at least as many of the same mutants as before (S-QA-036).
  - A heal that can't meet these becomes row e.

  *Depends on:* S-QA-012, S-QA-036, S-QA-040.
- **S-QA-031** Failure items (closes OD-BA-4):
  - A failure on `main` gets one failure item per test ID: a tracker draft ticket in the S-QA-011 defect-ticket form, with the row label, the evidence and the `run_id`. A repeat failure adds a comment to the open item.
  - **Verdicts** start the healer again (S-QA-013). On a `qa:product-issue` item:
    - `verdict:confirmed` makes the item itself the defect ticket, ready for `dev:fix`;
    - `qa:source-wrong` raises a requirement-defect item, and the test becomes `qa:test-update` once the source changes;
    - `verdict:rejected` routes the test to `test-gen-<layer>` as a test fix, or to the human for a characterization test.

    On other labels the verdict only scores accuracy.
  - **OD-BA-4:** the label that means "the rule and the behaviour disagree" is `qa:source-wrong`. Only an operator applies it, on a `qa:product-issue` item or a suspected-issue comment whose test cites the rule (S-QA-009). The stale-rule check reads it in both places, failure items through the tracker and suspected-issue comments through the code host, each with the `governance/operators.yml` actor check (S-BA-025, S-QA-015). An unconfirmed `qa:product-issue` never marks a rule stale, because the behaviour may be the bug.
  - The operator's verdict on each label feeds healer label accuracy (S-QA-052).

  *Depends on:* S-GEN-071, S-BA-025, S-BA-048, S-QA-009, S-QA-011, S-QA-013, S-QA-052, OD-BA-4.
- **S-QA-032** Read-stage schema and write actions for `ci-healer` (closes OD-GEN-6 and OD-SEC-1 for it):
  - **Context:** always the classification table, `AGENTS.md` conventions and own learnings. Fetched: the injected facts (S-QA-028), the failure log and trace, the reference run, the test and its cited sources, and the blocks of the merged PRs.
  - **Read stage:** `failure` {test_id, facts_ref, row, label, cited_ids, declaring_ref, evidence_refs}; `defect_items[]` (S-BA-048); `files[]` (rows c and x only, harness-derived, S-QA-017); `quarantine_entries[]`; `decision_summary`; `source_refs[]`.
  - **Writes:** stage 1: failure items and comments on them, requirement-defect items, classification comments on human PRs, and the `qa:*` row labels on its own items. Stage 2 adds: an `agent/ci-healer/*` branch with heal and quarantine PRs, comments on its own PRs, and the label `agent`.

  *Depends on:* S-SEC-002, S-SEC-003, S-BA-048, S-QA-017, S-QA-018, S-QA-028.

### Exploratory

- **S-QA-033** Charters. A charter reads "Explore <area or feature> with <roles, data, devices, interfaces> to discover <risks>", plus a timebox of 30 min *(starting value)*, the build digest and the ticket. `exploratory` drafts it as a comment on the REQ's ticket, from the ACs, the PR diffs, the spec diff, flags, existing tests and coverage, and bug history. The human starts a session with `qa:explore`. An operator comment with a `to_discover` line replaces the drafted one. *Depends on:* S-DEV-044, S-QA-015.
- **S-QA-034** Sessions:
  - Each session runs in its own isolated environment from the `main` build digest (S-TESTAB-002, -003; S-DEVOPS-026), with per-role test accounts and seeded data (S-TESTAB-004), in the S-QA-017 sandbox, through a browser tool and direct API calls.
  - App content, logs and traces are untrusted data (S-SEC-001). The session passes its `run_id` as the correlation ID and reads logs and traces by it (S-TESTAB-007).
  - **Context:** always the product core, the charter and own learnings. Fetched: the ticket and its ACs, the diffs, flags, bug history and the area's data factories (S-TESTAB-004).

  *Depends on:* S-SEC-001, S-TESTAB-002, S-TESTAB-003, S-TESTAB-004, S-TESTAB-007, S-QA-017.
- **S-QA-035** Outputs, schema and write actions (closes OD-GEN-6 and OD-SEC-1 for `exploratory`):
  - **Read stage:** `charter`; `session_notes` {tried[], skipped[]}; `bug_drafts[]` (S-QA-011) with `trace_refs`; `defect_items[]`; `questions[]`; `candidate_tests[]` {target, cites, steps, expected}; `discovered[]` {kind: app_map | state_model | candidate_rule, path, sections[], evidence_refs}, as full documents, never patches; `private_reports[]`.
  - **Writes:** stage 1: the charter and one session comment on the ticket, draft defect tickets, requirement-defect items and private reports. Stage 2 adds: an `agent/exploratory/*` branch and PR in `knowledge/discovered/**`, and the label `agent`.
  - **Candidate tests** go to `test-gen-<layer>` once the human confirms their bug. The test cites its source, carries the strict expected-failure marker and links the ticket. Row x removes the marker when the fix lands (S-QA-028).
  - **Candidate rules** become rules only through knowledge drafting (S-BA-027).

  *Depends on:* S-GEN-025, S-SEC-002, S-SEC-003, S-SEC-011, S-BA-027, S-QA-011, S-QA-028.

### Mutation

- **S-QA-036** Mutation gate, a check script in staff-qa `checks/`. Mutation measures whether a test notices a change, not whether its expected value is right; that is S-QA-006's job.

  | Use | Tests run in process (unit, in-process API) | Tests run out of process (black-box) | Cap per run *(starting value)* |
  | --- | --- | --- | --- |
  | Quality gate | Incremental code mutation of the changed lines, plus concern-driven mutants as code patches (S-QA-039) | Response mutation of the operations the new tests call (values, structure, error payloads, partial data, status, latency), plus concern-driven mutants expressed as response mutations | ≤50 mutants in total, ≤20 min |
  | Generator feedback | Survivors of the gate, tool and concern | Same | ≤2 rounds per test PR |
  | Healer guard | The same tool mutants before and after the heal | Same | ≤20 mutants, ≤10 min |
  | Improver signal | Kill rates from evals, and a nightly code-mutation run on high-risk modules | Same, plus a nightly scoped code-mutation run against the black-box suite if its per-mutant cost fits | ≤2 h nightly |

  UI tests get response mutation through the E2E framework's network interception. Tools follow the stack (for example PIT, Stryker, mutmut), as `.staff/tests.yml` declares. **Threshold:** at least 60% of non-equivalent mutants killed *(starting value)*, with every counted survivor categorised (S-QA-037). Concern mutants count toward it under S-QA-039's stage rule. It blocks QA test PRs; the guard blocks heal PRs; on DEV PRs it is advisory (S-QA-012). Thresholds and caps live in staff-qa `checks/`, which only the human authors (S-GEN-025). *Depends on:* S-GEN-025, S-QA-005, S-QA-006, S-QA-012, S-QA-037, S-QA-039, S-DEVOPS-032.
- **S-QA-037** Survivors. Each counted survivor left after the feedback rounds (S-QA-039) gets one category: `equivalent` (from `equivalence-filter`), or `out_of_scope` or `accepted_gap` (from the generator, with a reason). An `equivalent` call leaves the denominator under S-QA-038's stage rule. The decision summary lists every category. The human's merge confirms `out_of_scope` and `accepted_gap`. A review comment from an operator that cites a mutant ID rejects its category and returns it as a survivor. Accepted gaps become `check_outcome` records (S-QA-053). *Depends on:* S-GEN-071, S-QA-038, S-QA-039, S-QA-053.
- **S-QA-038** `equivalence-filter`:
  - The gate workflow launches it in the `tokenless` variant (S-DEVOPS-024, -032), with the survivors and their diffs, tool and concern mutants alike. It returns `calls[] {mutant_id, verdict: equivalent | not_equivalent | unsure, reason}`, schema-validated, as an artifact the gate reads. It holds no identity token and no write tool, so S-SEC-002's split doesn't apply (closes OD-SEC-1 for it). `unsure` counts as not equivalent.
  - The gate's survivors comment carries the filter's `run_id` with each call, which links each call to its run (S-QA-053).
  - **Stages,** mapped onto S-GEN-052 as S-BA-044 maps knowledge drafting:
    - **stage 1:** an `equivalent` call leaves the denominator only once an operator signs it off in the S-ARCH-053 form, citing the mutant ID. One comment may sign off several;
    - **stage 2:** calls count automatically, and a random 10% of them *(starting value)* go to the digest for an explicit verdict.
  - **Explicit verdicts only** feed its metrics: sign-offs, rejections that cite the mutant ID (S-QA-037), and digest verdicts.
  - **Unavailable:** if the filter can't run or its output fails validation, every survivor counts as not equivalent.

  *Depends on:* S-GEN-052, S-GEN-066, S-SEC-002, S-BA-044, S-ARCH-053, S-QA-017, S-QA-037, S-DEVOPS-024, S-DEVOPS-032.
- **S-QA-039** `mutant-drafter` and concern-driven mutants (`docs/decisions.md`, 2026-11-21: restored from the legacy doc):
  - **Concerns:** the gate's script collects, for the code under test, the rules, ACs and test conditions the PR declares or its tests cite; the domain clauses for the area (S-GEN-018); `reviewer/code` and `reviewer/tests` findings on the product PR; and the merged `fix` PRs that touched the same modules (S-DEV-041). At most 5 concerns per gate run *(starting value)*, cited IDs first.
  - **Drafting:** the gate workflow launches `mutant-drafter` in the `tokenless` variant (S-DEVOPS-024, -032), before the mutants run. It gets the concerns, passed as quoted data (S-SEC-002), and the product code under test, never the tests under gate. It returns `mutants[] {mutant_id, concern {kind, ref}, cited_id, form: code_patch | response_mutation, patch or mutation, rationale}`, with 3–5 mutants per concern as in the legacy rule. It holds no token and no write tool, so S-SEC-002's split doesn't apply (closes OD-SEC-1 for it).
  - **Validation by script:**
    - a code patch is at most 2,000 characters (S-SEC-002). It must apply to the product PR's changed modules only, touch `source` lines only and build, and it passes S-DEV-021's file checks: secret scan, no binary content;
    - a response mutation must name an operation the new tests call and a field of its approved spec;
    - an invalid mutant is dropped and counted (S-QA-053).

    Valid mutants run in the gate's `run` job, in the `work` variant, like tool mutants, with test-only credentials and the gate's egress only (S-SEC-005, -007; S-DEVOPS-024, -032). Their survivors go to `equivalence-filter` (S-QA-038).
  - **Stage rule** (`docs/decisions.md`, 2026-11-21): at stage 1, concern mutants run in every gate run, and their survivors feed generator feedback and the decision summary, but they don't count toward the threshold. Below stage 2, at most 20 concern mutants run per gate run *(starting value)*, so at least 30 of the 50 slots stay for the counted tool mutants. From stage 2, concern mutants count like tool mutants inside the 50, and their survivors need categories (S-QA-037).
  - **Verdicts:** each gate run puts a random sample of 2 drafted concern mutants in the digest, at most 4 per area per day, and 1 per area per day from stage 2 *(starting value)*. Each is shown with its concern. An operator marks each one `verdict:confirmed` (realistic and on the concern) or `verdict:rejected` (S-GEN-071). These verdicts give the output precision that S-GEN-052's stage 1→2 rule needs (S-QA-052).
  - **Trace:** requirement → rule or AC → concern → mutant → killing test. The mutant carries `cited_id`, and the killing test cites the same ID (S-QA-007).
  - **Nightly:** mutation results are published as CI artifacts and as kill-rate snapshots per area and per mutant source, tool or concern (S-QA-053). The improver reads them per agent and skill version (S-GEN-046).

  *Depends on:* S-GEN-018, S-GEN-046, S-GEN-052, S-GEN-066, S-GEN-071, S-SEC-002, S-SEC-005, S-SEC-007, S-DEV-021, S-DEV-041, S-QA-007, S-QA-017, S-QA-036, S-QA-037, S-QA-038, S-QA-052, S-QA-053, S-DEVOPS-024, S-DEVOPS-032.

### QA checks

- **S-QA-040** Diff checks (closes OD-GEN-9 for QA, and replaces S-DEV-028's interim cited-value rule, closing OD-DEV-1's checks). Tests are compared as S-DEV-028 does: a net set keyed by (test ID v1, cited IDs), after rename mapping. Every flagged diff needs a sign-off (G3).
  - **Assertion-diff check:** flags a test removed, skipped or newly marked expected-failure; an assertion line removed; a net decrease in assertion lines (the S-DEV-045 fallback); and a matcher moved to a weaker class in the stack's `matcher_strength` order. Any other changed assertion line goes to the cited-value lint, and is flagged outright in an uncited test.
  - **Cited-value lint:** the stack's `expected_value` capture isolates the expected value in each changed assertion line of a cited test. A changed value is flagged unless all of these hold:
    - the same diff re-points the test's `cites:` from a retired ID to its replacement, or to a newer IF version;
    - the assertion's subject expression is unchanged;
    - the new value equals the replacement's value for the same key that the old value matched in the retired source: an AC `then` entry by `key`, a rule's structured field, or a spec element's field (S-BA-007, -008, S-ARCH-008).

    Where the check can't isolate the value or map the key, the whole changed line is flagged. For cited tests on DEV PRs, S-QA-040 is the only check on changed assertion lines. DEV still flags removals, net decreases and changes in uncited tests (S-DEV-018, -028).
  - **Expected-failure check:** a new expected-failure marker must be strict, sit on a cited test, and carry a linked defect ticket before it reaches `main`. A marker is removed only in a row-x heal with assertions untouched.
  - **Quarantine check:** fails a PR that adds an entry without row-a evidence, an owner and `expires` at most 14 days after `since`, or that extends an entry more than once, without an operator's reason, or past 28 days. An entry the PR doesn't touch never fails it (S-QA-029).
  - **Test deletion:** flagged, except tests whose cited IDs are all retired. Deleting a test of a deprecated version before it retires is blocked (S-QA-023).
  - **Mocks, request documents and fixtures:** flagged are a recorded value changed for an element whose spec didn't change, a field or operation removed from an existing test's request document, and a value changed or removed in a `fixtures` file.
  - **Discovered notes:** deleting a note, or removing its evidence refs, is flagged.
  - **Conventions lint (blocking, zero violations):** a `cites:` token or `characterization` on every new test, the locator policy, request documents as files, and the expected-failure links.
  - **Citation status (in the conventions lint):** every ID that a new or changed `cites:` adds has the status S-QA-010 requires. That means a ready AC not affected by `changed`, an active rule, an approved or deprecated version, or an accepted QAS, read from the BA and ARCH trace matrices of the latest `main` run and from `changes[]`. The lint fails closed when the matrices are missing.
  - **Lane checks:** as in S-QA-051. **Checklist diff check (staff repo):** a skill PR that removes or rewords a TR item.

  *Depends on:* S-GEN-020, S-BA-007, S-BA-008, S-BA-021, S-ARCH-008, S-ARCH-030, S-DEV-018, S-DEV-028, S-DEV-045, S-QA-005, S-QA-010, S-QA-023, S-QA-028, S-QA-029, S-QA-051, OD-DEV-1, OD-GEN-9.
- **S-QA-041** QA check scripts. They ship from staff-qa `checks/` and run as required checks from a source the PR can't change (OD-SEC-2). They read no switch and fail closed, as in S-BA-051.
  - **Agent PRs that touch test paths, DEV's included (blocking, OD-DEV-1):** the diff checks and the conventions lint. Also the mutation gate on QA test PRs and the healer guard on heal PRs.
  - **Every staff-qa PR (blocking):** the base check. `agent/ci-healer/*` and `agent/exploratory/*` PRs must target `main`. `agent/test-gen-*/*` PRs must target `main` or the head branch of the open product PR named in their block. They can merge only into `main` or a human product PR's branch, so the check fails while the base is any `agent/*` branch (S-QA-012).
  - **Human PRs (report only):** the diff checks and the conventions lint.
  - **DEV agent PRs other than `kind: upkeep`:** the advisory mutation gate, when the PR becomes ready and on review re-request; and the intake check, which reads the PR block when the PR becomes ready and dispatches `test-gen-*` as a check event (S-QA-012). The intake check is an event workflow with no `run` job, separate from the gate. The router takes its PR target from the triggering run, never from its artifact (S-DEVOPS-017).
  - **Nightly:** quarantine expiry, the flake-sweep list, the contract run (S-QA-023), the gap findings that start generation (S-QA-013) and the outcome check (S-QA-053).

  They run as the `facts`, `run` and `report` jobs of S-DEVOPS-020. Checks that build or run tests do so in a `run` job in the `work` variant (S-DEVOPS-024), and the scheduled ones are S-DEVOPS-031's. *Depends on:* S-BA-051, S-QA-012, S-QA-013, S-QA-017, S-QA-023, S-QA-040, S-QA-053, OD-DEV-1, OD-SEC-2, S-DEVOPS-017, S-DEVOPS-020, S-DEVOPS-024, S-DEVOPS-031.
- **S-QA-042** Flag IDs come from (check, element), as in S-DEV-028, so a sign-off holds across rebases and a push that changes the element voids it (S-ARCH-053). The element is the test ID for test, assertion and quarantine flags, (test ID, value hash) for cited values, or (test ID, line hash) where the value can't be isolated, and (file, element) for mocks, request documents and fixtures. One operator comment may sign off several flag IDs. *Depends on:* S-ARCH-053, S-DEV-028.

### Test checklist (reviewer/tests)

- **S-QA-043** The checklist (closes the QA part of OD-GEN-8). Item IDs are stable, and the checklist diff check protects them (S-QA-040).

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

  *Depends on:* S-GEN-015, S-TESTAB-004, S-TESTAB-007, S-DATA-004, S-QA-006, S-QA-040, OD-GEN-8.
- **S-QA-044** Output and evaluation:
  - **Context:** always the checklist and `AGENTS.md`. Fetched: the diff and PR block, the cited sources, the check outputs and the gate's survivors.
  - **Read stage:** `target`, `reviewed_sha`, `verdict`, `findings[] {finding_id, checklist_id, severity, location, text, suggestion, cited_ids, classification}`, `questions[]`. **Writes:** one comment per run and the label `qa:not-ready` (closes OD-SEC-1 for it).
  - **Output:** as in S-DEV-032: a verdict, at most 7 findings with IDs derived from (TR ID, test ID, cited ID), and a machine-readable block. It is headed "not yet qualified" until the checklist qualifies.
  - **Evaluation:** the default `reviewer/<other type>` row of S-GEN-045, unchanged, with seeded test PRs covering every TR item. Caps as in S-GEN-057.
  - **Escaped defects:** a confirmed bug that a reviewed test PR covered with a wrong expected value becomes a seeding input. The PR itself never becomes a hidden or promotion task (S-GEN-028).

  *Depends on:* S-GEN-028, S-GEN-045, S-GEN-057, S-GEN-062, S-SEC-002, S-DEV-032.

### Caps, records, environments and data

- **S-QA-045** Per-run caps (closes OD-GEN-4 for QA):
  - `test-gen-*`: $5 per run, 20 min *(starting value)*. A test PR may use one generation run plus 2 feedback runs, so its worst case is 3 runs and 3 gate runs.
  - `ci-healer`: $2 per run, 10 min *(starting value)*.
  - `exploratory`: $5 per run, 40 min: the 30-min timebox plus reporting *(starting value)*.
  - `equivalence-filter`: $0.50 per gate run, 5 min *(starting value)*.
  - `mutant-drafter`: $1 per gate run, 5 min *(starting value)*.
  - `reviewer/tests`: as in S-GEN-057.
  - Mutation runs are CI steps with the caps in S-QA-036, outside the agent caps.

  Eval worst cases under S-GEN-070:
  - each `test-gen-*` layer: 20 × 5 × $5 = $500, so the skill-PR budget is $300; a promotion attempt costs $250;
  - `ci-healer`: 22 × 5 × $2 = $220, budget $132; promotion 12 × 5 × $2 = $120;
  - `exploratory`: 10 × 5 × $5 = $250, plus 10 × 5 × $0.20 = $10 for the judge, budget $156; promotion 6 × 5 × $5 = $150;
  - `equivalence-filter`: 50 × 5 × $0.50 = $125, budget $75;
  - `mutant-drafter`: 20 × 5 × $1 = $100, budget $60; promotion 10 × 5 × $1 = $50;
  - `reviewer/tests`: 30 × 5 × $1 = $150, budget $90.

  *Depends on:* S-GEN-056, S-GEN-057, S-GEN-059, S-GEN-070, S-QA-036.
- **S-QA-046** QA run records add these fields inside `role` (S-GEN-029): `layer`, `product_pr`, `trigger_kind`, `cited_ids`, `tests_added`, `characterization_tests`, `expected_failures`, `mutants`, `killed`, `survivors`, `feedback_round`, `row`, `label`, `test_ids`, `charter_ref`, `bug_drafts`, `equivalence_calls`, `concern_refs`, `mutants_drafted`, `mutants_invalid`, `lane_eligible`. *Depends on:* S-GEN-029.
- **S-QA-047** How QA consumes S-TESTAB (closes the rest of OD-TESTAB-5), and prerequisites (closes OD-TESTAB-6 for QA):

  | Item | How QA consumes it |
  | --- | --- |
  | S-TESTAB-001 | The prerequisites below. A gap keeps the agent at stage 1 in that area |
  | S-TESTAB-002 | Every API or UI run, healer re-run, out-of-process gate run and session gets its own environment |
  | S-TESTAB-003 | Reference runs, re-runs and sessions record and reuse the build digest |
  | S-TESTAB-004 | Tests create their own data through factories and clean up. Per-role tests use the role's test accounts from CI secrets |
  | S-TESTAB-005 | The locator policy; API assertions on stable operation, error and event names |
  | S-TESTAB-006 | The oracle rule (S-QA-006) |
  | S-TESTAB-007 | Tests and sessions pass `run_id`. The healer and sessions read logs and traces as evidence. Waits use the readiness endpoint |
  | S-TESTAB-008 | Tests control flags and the clock, and fake external services at seams. Response mutation goes through those seams |

  Prerequisites:
  - `test-gen-unit`: S-TESTAB-003 and -006, and the area's `tests.yml` and `code.yml` entries.
  - `test-gen-api`: as unit, plus S-TESTAB-002, -004 and -005, and approved versions for the area.
  - `test-gen-ui`: as unit, plus S-TESTAB-002, -004 and -005, and core journeys in the product core.
  - `ci-healer`: S-TESTAB-003 and the test-result history (S-DEVOPS-030); S-TESTAB-002 for out-of-process tests.
  - `exploratory`: S-TESTAB-002, -003, -004 and -007.
  - `equivalence-filter`: none beyond the manifest.
  - `mutant-drafter`: S-TESTAB-003 and -006 (the sources its concerns come from), and the area's `tests.yml` `mutation` entry.
  - `reviewer/tests`: S-TESTAB-006 sources for the area. Without them, TR-1 checks only within the PR, and the output says so.

  *Depends on:* S-TESTAB-001, S-TESTAB-002, S-TESTAB-003, S-TESTAB-004, S-TESTAB-005, S-TESTAB-006, S-TESTAB-007, S-TESTAB-008, S-QA-006, S-DEVOPS-030.
- **S-QA-048** Data and security (closes the QA part of OD-DATA-2):
  - QA fetch steps and read stages apply the read-time redaction of S-BA-028 to every tracker and connector fetch.
  - Production-derived content, such as user bug reports and support tickets, reaches QA agents only from the redacted exports of OD-BA-5, as charter input and defect evidence. QA agents never read production systems, logs or data, and tests never call production endpoints.
  - Test data follows S-DATA-004, and storage and posting follow S-SEC-004.

  *Depends on:* S-SEC-004, S-DATA-004, S-BA-028, OD-BA-5.

### Eval rows

- **S-QA-049** Eval rows (closes OD-GEN-3 for QA). Scores are pooled (S-GEN-035). Hidden and promotion tasks are scored by script (S-GEN-041). Every task starts from a pinned build and snapshot in the S-GEN-066 sandbox (S-GEN-043). Golden sizes for test generation are decided; the other values are *(starting value)*; all are from `docs/decisions.md` (2026-11-20).

  | Agent | Golden tasks | Promotion set minimum | Mode | Oracle | Primary metrics | Stage 1→2 threshold | Hard limits | LLM judge |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | `test-gen-unit` | 20 tasks on changed modules, at least 6 of them survivor-driven: a PR with its own tests and their survivors *(starting value, `docs/decisions.md`, 2026-11-21)* | 10 diff-seeded tasks with holdout seeds | Diff-seeded | Build; detection per the formula below; code-mutation kill rate; conventions lint | Seeded-bug recall, mutation kill rate | Recall ≥70%, kill rate ≥60% | Bug-encoding 0; lint 100%; schema-valid; no write outside scope; every new test cites a source or is labelled | No |
  | `test-gen-api` | 20 API operations | 10 diff-seeded with holdout seeds | Diff-seeded | As unit; mutation per S-QA-036 | As unit | Recall ≥60%, kill rate ≥60% | As unit | No |
  | `test-gen-ui` | 20 UI flows | 10 diff-seeded with holdout seeds | Diff-seeded | As unit; response mutation | As unit | Recall ≥50%, kill rate ≥50% | As unit | No |
  | `ci-healer` | 20 broken tests (8 c, 4 b, 4 d, 2 a, 2 e), plus 2 row-x | 12: 4 c, 2 b, 2 d with holdout seeds, 1 a, 1 e, 2 x | Diff-seeded for row d; scripted breakages for the rest | The label matches the task's row; heals pass, keep the kill count and touch no assertion | Label accuracy, heal success | Accuracy ≥90%, heal success ≥80% | No row-d task healed; schema-valid | No |
  | `exploratory` | 10 charters on areas with active seeded bugs | 6 charters with ≥2 holdout seeds each | Image-seeded; charters frozen before seeding | Draft tickets matched to seed specs by `target` and symptom | Seeded-bug recall, false-positive rate | Recall ≥40%, false positives ≤30% | Schema-valid; no write outside scope | Yes, repro quality on visible tasks; reported, not gating |
  | `equivalence-filter` | 50 labelled mutants | 30 mutants labelled after the skill freeze (S-GEN-068) | Label-based; seeded mutants in hidden sets where possible (S-QA-050) | Matches the human label | Error rate | ≤10% | Schema-valid | No |
  | `mutant-drafter` | 20 tasks *(starting value)*: product code, its concerns, a weak test set that misses a seeded fault, and a strong reference suite (S-QA-050) | 10 tasks with holdout seeds *(starting value)* | Diff-seeded | A script applies and builds each mutant, then runs both sets on it | Valid-mutant rate, gap recall | Valid ≥80%, gap recall ≥60% *(starting value)* | Schema-valid; no patch outside the changed modules' `source` lines; tests never in its input | No |
  | `reviewer/tests` | The default row of S-GEN-045 (S-QA-044) | | | | | | | |

  Formulas:
  - **Seeded-bug recall:** seeded bugs detected / seeded bugs in the tasks. For generation, detected means at least one generated test fails on the seeded version with an assertion failure and passes on the corrected one, with or without an expected-failure marker. For `exploratory`, a draft ticket matched to the seed spec.
  - **Bug-encoding:** generated tests that pass on the seeded version and fail on the corrected one. Target 0.
  - **Mutation kill rate:** mutants killed / non-equivalent mutants, per approach. In evals the task spec says which mutants are equivalent.
  - **Label accuracy:** tasks labelled with the spec's row / tasks.
  - **Heal success:** row-c tasks healed so that the test passes, keeps its kill count and touches no assertion / row-c tasks.
  - **False-positive rate:** draft tickets that match no seed / draft tickets. On visible tasks the human gives verdicts on unmatched tickets (S-GEN-041).
  - **Error rate:** calls that differ from the label, with `unsure` counted as not equivalent / calls.
  - **Valid-mutant rate:** drafted mutants that apply, build and are killed by the strong set / drafted mutants. The strong set kills every seeded fault for every concern the task supplies, so a mutant it doesn't kill is equivalent or off its concern, and counts as invalid.
  - **Gap recall:** tasks where at least one valid mutant survives the weak set / tasks.

  **Catalogue.** The legacy agent set's 54 holdout seeds (30 for generation, 2 for the healer, 12 for exploratory, and the 10 of reviewer/requirements) give the ≥162 entries of S-GEN-039. The 10 seeded `reviewer/tests` promotion PRs add 30 more, and the 10 `mutant-drafter` promotion tasks add another 30. *Depends on:* S-GEN-035, S-GEN-036, S-GEN-037, S-GEN-038, S-GEN-039, S-GEN-040, S-GEN-041, S-GEN-042, S-GEN-043, S-GEN-044, S-GEN-045, S-GEN-066, S-GEN-067, S-GEN-068, S-QA-036, S-QA-039, S-QA-044, S-QA-050.
- **S-QA-050** Task construction:
  - **Healer tasks:** the seeding agent writes each task with its expected row as the spec: a scripted breakage for rows a, b, c, e and x, or a diff-seeded undeclared behaviour change for row d, with its S-GEN-067 symptom check.
  - **Equivalence labels:** the eval runner samples survivors from gate runs, and the human labels them as labelling batches (timing-only records, S-GEN-071). Golden batches are assigned at random (S-GEN-028). Hidden sets use seeded mutants wherever the seeding agent can give a machine-checkable spec: a killing test for a non-equivalent mutant, or a rewrite from a fixed catalogue of semantics-preserving rewrites for an equivalent one (S-GEN-068). Live verdicts on calls stay full verdict records and never feed eval sets.
  - **Drafter tasks:** the seeding agent seeds at least one fault per concern the task supplies, and links each fault to its concern. It writes the weak set, which misses at least one of those faults, and the strong set: a reference suite that kills every seeded fault for every concern in the task. Before the task is used, it verifies by script that the strong set fails on every seed and passes on the corrected code. It also checks that the strong set kills at least 90% of the task's tool mutants *(starting value)*, so the strong set isn't tuned to the seeds alone (S-GEN-067). The drafter's input has neither set nor the seed, which are read only at scoring time (S-GEN-040).
  - **Escaped bugs:** confirmed bugs that a QA test should have caught, read from merged `fix` PRs (S-DEV-041), become seeding inputs for generation and exploratory tasks. The escaped item never becomes a hidden or promotion task (S-GEN-028).

  *Depends on:* S-GEN-028, S-GEN-040, S-GEN-067, S-GEN-068, S-GEN-071, S-DEV-041.

### Stage rules

- **S-QA-051** Stage-2 and stage-3 rules (closes OD-GEN-5 for QA). The role demotion triggers add to those in S-GEN-052. Values are *(starting value)* unless marked.

  | Agent | Stage-2 quality metric that must hold for stage 3 | Role demotion trigger → stage 1 | Stage 3 |
  | --- | --- | --- | --- |
  | `test-gen-*` | Generated-test flakiness ≤5% | Suspected-issue precision <70% over the last 20 comments | **Change class:** citation-repair PRs that only re-point `cites:` tokens from rules retired as `duplicate` (S-QA-025). **Guard:** the citation-lane check: only `cites:` tokens change, and each old ID is a rule retired as `duplicate` whose `replaced_by` is the new ID. **Critical miss:** a merged lane PR that changed anything else, or re-pointed to a wrong ID |
  | `ci-healer` | Healer label accuracy ≥90% over the last 20 labels | A merged heal of a row-d failure counts as a guardrail breach (S-GEN-052) | **Change class:** heal PRs whose every commit touches only locators, waits or page-object selectors (no assertion lines, expected values, test data or deletions) and that pass the healer guard. Light review, never auto-merge (`docs/decisions.md`, 2026-11-20). **Guard:** the locator-lane check, the assertion-diff check and the healer guard. **Critical miss:** one healed row-d failure |
  | `exploratory` | None: no stage 3 | None beyond S-GEN-052. Live bug-report precision is reported (S-QA-052) | None. Its findings are verdicts for the human |
  | `equivalence-filter` | None: no stage 3 | Live error rate >10% over the last 30 calls with an explicit verdict *(starting value)* | None. Stage 2 means sampled review (S-QA-038) |
  | `mutant-drafter` | None: no stage 3 | Live valid-mutant rate <80% over the last 100 drafted mutants *(starting value)* | None. Stage 2 means its mutants count toward the threshold (S-QA-039). Its S-GEN-052 output precision comes from the digest verdicts of S-QA-039 |

  `reviewer/tests` is advisory at every stage (S-GEN-045, S-GEN-062). Only the lane checks, never an agent, mark a PR lane-eligible. *Depends on:* S-GEN-045, S-GEN-052, S-GEN-053, S-GEN-062, S-BA-008, S-QA-025, S-QA-036, S-QA-038, S-QA-039, S-QA-040, S-QA-052.

### Role metrics and outcome records

- **S-QA-052** Role metrics (closes OD-GEN-7 for QA, with S-QA-053). Windowed metrics count only items whose window has closed. Windows are *(starting value)* unless marked.

  | Metric | Formula |
  | --- | --- |
  | Generated-test flakiness | Generated tests quarantined within 28 days of merge / generated tests merged at least 28 days ago, over the last 20 such test PRs |
  | Healer label accuracy | Labels confirmed by operator verdict / labels with a verdict, last 20 |
  | Suspected-issue precision | Suspected-issue comments confirmed as bugs / those with a verdict, last 20 |
  | Heal revert rate | Heals (one per test) reverted or re-healed within 14 days / heals merged at least 14 days ago, last 20. Reported; the lane itself uses S-GEN-052's lane revert rate |
  | Bugs caught | Distinct bugs confirmed by operator verdict, credited to the earliest QA output that pointed at them: a cited failing test, a row-d item or a draft ticket. Characterization excluded. Reported |
  | Live bug-report precision | `exploratory` draft tickets with `verdict:confirmed` / those with a verdict, last 20 *(starting value, `docs/decisions.md`, 2026-11-21)*. Reported |
  | Live valid-mutant rate | `mutant-drafter` mutants that pass validation and that `equivalence-filter` doesn't call `equivalent` / mutants drafted, last 100 *(starting value)*. The filter's calls are the equivalence input, because they exist for every concern survivor at every stage, while explicit verdicts cover only samples |
  | Drafter output precision | Sampled concern mutants with `verdict:confirmed` / sampled concern mutants with a verdict (S-QA-039), last 20. The S-GEN-052 stage 1→2 precision |
  | Equivalence live error rate | Calls rejected by an explicit operator verdict / calls with an explicit verdict (S-QA-038), last 30 |
  | Mutation kill rate | Killed / non-equivalent mutants, per approach, nightly snapshot. Reported |
  | Characterization share | Characterization tests / tests added by QA, last 20 PRs *(starting value, `docs/decisions.md`, 2026-11-21)*. Reported |
  | Quarantine backlog | Entries, and the age of the oldest, nightly snapshot. A load signal |

  *Depends on:* S-GEN-032, S-GEN-052, S-GEN-071, S-QA-038, S-QA-053.
- **S-QA-053** Outcome records. A nightly QA check derives outcomes from the product repo and the tracker and emits them through the recorder (S-GEN-026) as `check_outcome` records (S-GEN-031).
  - **Linked, per artifact.** `drafting_run_id` comes from `Staff-Run-Id`, read per merged PR (S-GEN-029), or from a comment's machine-readable block, read only from comments by the staff-qa identity, as S-DEV-039 does. For an `equivalent` category it is the filter's `run_id` carried in the gate's survivors comment (S-QA-038); for the other categories, the generator run that set them. For a sampled concern mutant, it is the drafter's `run_id`, which the digest item carries.

    | Record | `artifact_id` | `role` fields |
    | --- | --- | --- |
    | Merged QA PR | PR number | `merged`, `human_commits`, `reverted_14d`, `tests_merged`, `tests_quarantined_28d`, `flags`, `lane` |
    | Suspected issue | Comment ref | `confirmed`, `source_wrong`, `rejected` |
    | Failure item | Item ref | `row`, `verdict` |
    | Draft bug ticket | Ticket ref | `verdict`, `dev_fix` |
    | Survivor category | Mutant ID | `category`, `test_pr`, `rejected`, `explicit_verdict {kind: sign_off / rejection / digest, result}` |
    | Concern mutants (per drafter run) | None; per-run counts | `drafted`, `invalid`, `called_equivalent`, `killed` |
    | Sampled concern mutant | Mutant ID | `concern`, `explicit_verdict {kind: digest, result}` |

  - **Unlinked nightly findings,** keyed per S-GEN-031: quarantine entries past 14 or 28 days (test ID); tests citing retired IDs (test ID plus cited ID); quality-test gaps (QAS ID); kill-rate snapshots (area). Implemented IF operations that no test cites stay ARCH's finding (S-ARCH-030), which starts generation (S-QA-013).

  The check reads verdicts and `qa:source-wrong` only from operator accounts (S-GEN-071, S-QA-015). The ops stage job computes S-QA-052 from these records and the verdict updates. *Depends on:* S-GEN-026, S-GEN-029, S-GEN-031, S-GEN-071, S-ARCH-030, S-DEV-039, S-QA-013, S-QA-015, S-QA-038, S-QA-039, S-QA-046, S-QA-052.

### Interfaces with other roles

- **S-QA-054** What QA provides and consumes:

  | Artifact | Provider → consumers |
  | --- | --- |
  | Oracle rule, citation form, test ID (S-QA-006 to -008) | QA → every role's tests and checks |
  | Test PRs, survivor comments, suspected issues | QA → DEV (OD-DEV-2), the human |
  | `qa:source-wrong` on failure items and suspected issues | QA items, operator-labelled → the BA stale-rule check (S-BA-025) |
  | Draft defect tickets; requirement-defect items | QA → DEV (S-DEV-017); BA (S-BA-048) |
  | Contract results; tests citing IF elements | QA → ARCH (S-ARCH-026, -030) |
  | Discovered notes and candidate rules | QA → knowledge drafting (S-BA-027) |
  | QA checks, replacing S-DEV-028's interim rule | QA → every agent PR that touches tests |
  | Ready ACs, rules, test conditions v1, BA trace matrix | BA (S-BA-048) → QA |
  | IF versions, QAS, spec-change event, drift report, ARCH trace matrix | ARCH (S-ARCH-047) → QA |
  | PR blocks, implementation matrix, `code.yml`, flaky lists, generators | DEV (S-DEV-040) → QA |
  | Environments, sandbox, router, required checks, test-result history | DEVOPS (S-DEVOPS-017, -020, -024, -026, -027, -030 to -032) → QA |

  *Depends on:* S-BA-048, S-ARCH-047, S-DEV-040, S-DEVOPS-017, S-DEVOPS-020, S-DEVOPS-024, S-DEVOPS-026, S-DEVOPS-027, S-DEVOPS-030, S-DEVOPS-031, S-DEVOPS-032.

### Open dependencies closed by this doc

| Open dependency | Closed by |
| --- | --- |
| OD-BA-1 | Test conditions v1 confirmed, authorship stays with the Analyst: S-QA-010. Citations: S-QA-007. `changes`: S-QA-010, -028. Retired IDs: S-QA-025. Ready ACs only: S-QA-010 |
| OD-BA-3 (test engineer part) | S-QA-010 (ready ACs only), S-QA-011 (requirement-defect items) |
| OD-BA-4 | S-QA-031 (`qa:source-wrong`) |
| OD-ARCH-2 | Citation of IF elements: S-QA-007. Implemented elements only, mocks for pending ones: S-QA-023. Deprecated versions: S-QA-023, -040. `as-built`: S-QA-006, -023. QAS decidable in a functional environment: S-QA-023. Load, soak and capacity QAS: `verification: monitor`, owner DEVOPS (S-ARCH-009, AR-8 in S-ARCH-032; `docs/decisions.md`, 2026-11-20). Contract results: S-QA-023 |
| OD-DEV-1 | Citation form: S-QA-007. Test ID: S-QA-008. Oracle rule: S-QA-006. Assertion-diff check and cited-value lint: S-QA-040, -041 |
| OD-DEV-2 | S-QA-012 (split, including the no-merge rule into DEV branches), S-QA-041 (base check), S-QA-029 (flaky hand-off), S-QA-011 (ticket fields) |
| OD-GEN-1 | S-QA-013 |
| OD-GEN-2 | S-QA-005 (paths), S-QA-014 (agent scope) |
| OD-GEN-3 | S-QA-049, S-QA-050 (including `mutant-drafter`) |
| OD-GEN-4 | S-QA-045 (including `mutant-drafter`) |
| OD-GEN-5 | S-QA-051 |
| OD-GEN-6, OD-SEC-1 | S-QA-026, -032, -035, -038, -039, -044 |
| OD-GEN-7 | S-QA-052, S-QA-053 |
| OD-GEN-8 (QA part) | S-QA-043, -044; the consumed test-conditions schema: S-QA-010 |
| OD-GEN-9 (QA part) | S-QA-040 to S-QA-042 |
| OD-GEN-10 (QA part) | S-QA-012 |
| OD-TESTAB-5 | S-QA-006 (oracle rule), S-QA-047 (each item) |
| OD-TESTAB-6 | S-QA-047 |
| OD-DATA-2 (QA part) | S-QA-048 |

Not addressed to QA: OD-DATA-1, OD-SEC-2, OD-TESTAB-1 to -4, OD-BA-2, -5 and -6, OD-ARCH-1 and -3, OD-DEV-3.

## Assumptions

Items 1, 4, 18, 19 and 20 list values and decisions the human accepted (`docs/decisions.md`, 2026-11-20 and 2026-11-21). Item 2 applies a human decision. Items 24, 26 and 27 list more accepted values. No *(proposed)* item is open. Items 3, 5–17, 21–23 and 25 are designer defaults.

1. **Round-1 values, accepted** *(starting value, `docs/decisions.md`, 2026-11-20, roles/test-engineer round 1, auto-accepted recommendation)*:
   - at most 20 `repro[]` steps per draft defect ticket (S-QA-011);
   - at most 2 test PRs per area awaiting review; at most one heal PR and one quarantine PR per area per day; at most one discovered-knowledge PR per area per week; at most 500 changed lines per test PR (S-QA-019);
   - `equivalence-filter` caps of $0.50 and 5 min per gate run (S-QA-045); a 10% stage-2 review sample (S-QA-038); its live error rate over the last 30 calls with an explicit verdict, with demotion above 10% (S-QA-051, -052);
   - the generated-test flakiness window: the last 20 test PRs merged at least 28 days ago (S-QA-052).
2. **Context budget (`docs/decisions.md`, 2026-11-20):** 15k tokens per pack at chars/3.2, with the cap per S-GEN-009 (S-QA-020). Figures as of the last measurement; the release gate re-measures:
   - **always-loaded shared/:** 13,257 characters, about 4.14k tokens; the cap is about 34,745 characters;
   - **always-loaded part:** 23,154 characters, newlines included; about 11.38k tokens with shared/;
   - **packs** (always-loaded part plus own sections, S-QA-020), each within 15k:
     - `reviewer/tests` (plus Test checklist, about 2.5k, and QA checks, about 5.2k): about 31,350 characters, about 13.94k tokens, about 3.4k under the cap (re-measured after the DevOps cross-strategy pass, with the always-loaded part at about 23,180). This is the tightest pack;
     - `test-gen-*` (plus Test generation, about 7.2k): 30,324 characters, about 13.62k tokens, about 4.4k under the cap;
     - `ci-healer` (plus CI healer, about 7.1k): 30,214 characters, about 13.58k tokens;
     - `mutant-drafter` and `equivalence-filter` (plus Mutation, about 6.8k): 29,987 characters, about 13.51k tokens;
     - `exploratory` (plus Exploratory, about 2.3k): 25,495 characters, about 12.11k tokens.

   Human-owned items, path scope, triggers, the test convention and the DEV split stay always loaded. Each agent's mechanics and schema are in its own section. Caps, evals, stages, metrics and records are on demand, because the harness, the checks and the ops jobs apply them. In round 2 the QA checks section grew to about 5.1k, which would have left the `test-gen-*` and `ci-healer` packs only about 0.2k and 0.4k under the cap. So it moved from those packs to per-trigger retrieval, as planned in round 1 (S-GEN-048). It stays in the `reviewer/tests` pack.
3. **Legacy deviations.** Later decisions win over the legacy doc:
   - static review is reviewer/requirements (S-GEN-015), and knowledge drafting is BA's (S-BA-002);
   - "a human confirms each match" is replaced by script scoring of hidden and promotion tasks (S-GEN-041); exploratory false positives on those sets are scored by script;
   - the QA lead's rotation is the eval runner's (S-GEN-037); stages live in `stages.yml` with ceilings (S-GEN-050), not CI variables; the outcome store is not in Git (S-GEN-012);
   - "Ready for QA" becomes a REQ newly `implemented` (S-DEV-044) plus the operator's `qa:explore`; "Changes: R-xxx" becomes `changes[]` (S-BA-006);
   - the pilot roles collapse into the one human (S-GEN-001);
   - generation on every product PR becomes the conditional start of S-QA-012, as DEV's open question recommended;
   - "a failed agent check never blocks a product PR" narrows for DEV agent PRs: the QA diff checks and conventions lint block them, as OD-DEV-1 asks (S-QA-041). Human product PRs still get reports only.

   Item 19 records the two deviations the human decided on 2026-11-21.
4. **Carried starting values** (`docs/decisions.md`, 2026-11-20): the layer mix; the 30-day reference run; 2 retries, 14-day escalation and 28-day limit; the 30-min charter timebox; the gate at ≥60% with ≤50 mutants / 20 min, the healer guard at ≤20 / 10 min, ≤2 feedback rounds, ≤2 h nightly; caps $5 / 20 min, $2 / 10 min and $5 / 40 min; the eval rows, including 20 golden tasks per generation layer (decided), the healer's 20 + 2 row-x tasks, the promotion minimums and the thresholds; flakiness ≤5%, label accuracy ≥90%, suspected-issue precision 70%; the 14-day and 28-day windows and last-20 windows; locator-only heals never auto-merge.
5. **Test-condition authorship (S-QA-010):** stays with the Analyst, for BA's reasons (BA Assumptions item 10). Test conditions v1 already carries what generation needs.
6. **Mutation gate as a check (S-QA-036, -039):** a script runs the gate, the tool mutants and the validated concern mutants. The two model calls, drafting and equivalence, are separate token-less units, so a wrong output can only add a mutant or change a count that the human reviews.
7. **Stacked test PRs and S-GEN-060 (S-QA-012, -019):** a test PR based on a product PR's branch builds on that PR instead of competing with it, so it isn't the overlap S-GEN-060 guards against. That is a reading of S-GEN-060, not a local rule (CROSS-STRATEGY). It is never merged into a DEV agent branch (`docs/decisions.md`, 2026-11-20), nor into any other `agent/*` branch, so DEV's scope lint, size limit, test ownership and `dev-upkeep` lane stay intact (S-DEV-005, -010, -014, -030). `kind: upkeep` PRs get neither generation nor the gate, because they intend no behaviour change. Overlap with any other open PR waits, as DEV does, because code can't be merged by comment.
8. **`.staff/tests.yml` (S-QA-005):** test layouts are product-specific, so QA's paths and patterns sit in one human-only contract file, as DEV's do. S-GEN-025 already makes it human-only. S-GEN-017 doesn't list it yet (CROSS-STRATEGY).
9. **OD-BA-4 answer (S-QA-031):** only an operator's `qa:source-wrong` marks a rule stale. An agent's row-d label means only that the behaviour changed, and the human decides whether the rule or the code is wrong.
10. **Failure items (S-QA-031):** tracker draft tickets, one per test ID, because a failure on `main` has no PR to comment on.
11. **Healer only on `main` (S-QA-030):** DEV fixes its own PRs (S-DEV-042), and a heal pushed into a human's branch would bypass that author. A human PR gets a classification comment instead.
12. **`QAS-n` citation (S-QA-007):** quality tests take their expected values from the QAS `measure`, which can be stricter than the quality REQ's target (S-ARCH-009). The extension is additive, and S-DEV-016 now lists `QAS-n` among its accepted IDs.
13. **Quality tests (S-QA-023):** the legacy doc kept non-functional testing out of generation. QA keeps that for load, soak and capacity, which DevOps monitors (`docs/decisions.md`, 2026-11-20). It writes the functional quality tests that OD-ARCH-2 asks for, with single-call latency in a non-blocking job.
14. **Equivalence labels (S-QA-050):** live verdicts on calls never feed eval sets, as for knowledge drafting (S-BA-041). Promotion sets come from batches labelled after the freeze (S-GEN-068).
15. **Citation-repair lane (S-QA-051):** gives generation a narrow, guarded stage 3, so the carried flakiness bar keeps a purpose.
16. **Survivor confirmation (S-QA-037, -038):** `out_of_scope` and `accepted_gap` are listed in the decision summary, so the merge is an explicit act on them. An `equivalent` call changes the gate's denominator, so at stage 1 each one needs its own sign-off. The S-ARCH-053 form makes that one comment for several calls and an explicit, actor-checked verdict for the metric.
17. **Comment-posting checks (S-QA-012, -041):** the gate posts its survivors comment as S-DEV-007's readiness check posts its blockers comment. Both are realised by S-DEVOPS-020's `report` job, with the CI job token (S-DEVOPS-018).
18. **Round-2 values, accepted** *(starting value, `docs/decisions.md`, 2026-11-21, auto-accepted recommendation)*:
    - at least 6 of the 20 `test-gen-unit` golden tasks are survivor-driven (S-QA-049). The decided size of 20 is unchanged;
    - live bug-report precision over the last 20 draft tickets, and characterization share over the last 20 QA PRs, both reported only (S-QA-052).
19. **Legacy deviations decided by the human** (`docs/decisions.md`, 2026-11-21):
    - **Readability judge: dropped** from the generation rows (S-QA-049). The legacy rows used it for readability only, never for correctness, and it gated nothing. Readability is now covered by TR-9 on live PRs, the edit rate (S-GEN-032), the 500-line limit (S-QA-019) and the human's merge. **Revisit trigger:** if the edit rate of merged test PRs exceeds 30% over the last 20 *(starting value)*, or TR-9 findings appear on more than a third of the last 20 reviewed test PRs *(starting value)*, a report-only readability judge is added, calibrated first under S-GEN-042.
    - **Concern-driven mutants: restored** in the gate from the start, alongside tool and response mutation. To fit GEN, drafting is its own eval unit, `mutant-drafter`, with its own eval row, caps and stages (S-GEN-030, -044, -056). It never sees the tests it gates, so generation doesn't grade itself, and `equivalence-filter` applies to its survivors (S-QA-038, -039). Its concern mutants count toward the blocking threshold only from stage 2 (`docs/decisions.md`, 2026-11-21, option A).
20. **Merging stacked test PRs (S-QA-012, -041; `docs/decisions.md`, 2026-11-20, auto-accepted recommendation):** a QA test PR is never merged into a DEV agent branch. It is retargeted to `main` after the product PR lands, and the base check blocks merging into `agent/developer/*` bases. Since round 3 the base check is stricter: it blocks every `agent/*` base, which covers `dev-upkeep` branches too and doesn't contradict the decision. Load, soak and capacity QAS: `verification: monitor`, owner DEVOPS (same entry date).
21. **Healer facts (S-QA-028):** rows x, a, b and e depend on records a script can read, so the script decides them and the model judges only c against d, the one row pair that needs reading the diff and trace. A contradiction defaults to row e, which never heals.
22. **Verdict follow-up (S-QA-009, -031):** a confirmed `qa:product-issue` item already has the defect-ticket fields, so it becomes the defect ticket itself, with no second draft for the human to read. A suspected-issue comment gets its defect ticket only after `verdict:confirmed`, so rejected suspicions create no ticket noise.
23. **Quarantine at 28 days (S-QA-029):** CI stops honouring the entry, rather than failing unrelated PRs, so a stale entry blocks only through the test itself. "Quarantined in the last 28 days" means the test had an entry at any time in that window, read from the quarantine history (S-DEVOPS-030).
24. **Round-3 values, accepted** *(starting value, `docs/decisions.md`, 2026-11-21, auto-accepted recommendation)*:
    - `mutant-drafter`: at most 5 concerns per gate run (S-QA-039); caps $1 and 5 min per gate run (S-QA-045); 20 golden and 10 promotion tasks, with valid-mutant rate ≥80% and gap recall ≥60% (S-QA-049); demotion when the live valid-mutant rate falls below 80% over the last 100 drafted mutants (S-QA-051, -052);
    - the readability-judge revisit trigger: test-PR edit rate above 30% over the last 20, or TR-9 findings on more than a third of the last 20 reviewed test PRs (item 19).
25. **`mutant-drafter` design (S-QA-039, -049):**
    - **Scoring:** it is scored on whether its mutants are valid and expose a known test gap, so its eval needs no generator. The seeding agent's weak and strong test sets give a scripted oracle for both.
    - **Validation:** script validation keeps a bad mutant from touching tests or unrelated code.
    - **Counting:** at stage 1 its mutants feed feedback without moving the blocking threshold (`docs/decisions.md`, 2026-11-21), because S-GEN-052 lets a stage-1 unit only draft.
    - **Reaching stage 2:** the digest sample of S-QA-039 gives it human verdicts, so S-GEN-052's "≥20 verdicts with output precision ≥70%" can be met. A verdict judges whether the mutant is realistic and on its concern, which no script can decide live.
    - **Cap sharing below stage 2:** the chosen option keeps concern mutants to at most 20 of the 50 slots. That keeps the 20-min bound and leaves at least 30 slots for the counted tool mutants. The alternative was to run concern mutants outside the 50 under the same 20-min limit; it was not chosen because it lets concern mutants crowd out counted tool mutants in time rather than in count.
26. **Round-4 values, accepted** *(starting value, `docs/decisions.md`, 2026-11-21, auto-accepted recommendation)*:
    - at most 20 concern mutants per gate run while `mutant-drafter` is below stage 2 (S-QA-039);
    - a digest sample of 2 drafted concern mutants per gate run for an explicit verdict, at most 4 per area per day, and 1 per area per day from stage 2. The 20 verdicts S-GEN-052 needs arrive after about 10 gate runs, or about 5 days in one area (S-QA-039, -052).
27. **Round-5 value, accepted** *(starting value, `docs/decisions.md`, 2026-11-21, auto-accepted recommendation)*: the strong set of each `mutant-drafter` task kills at least 90% of the task's tool mutants, verified by the seeding agent's script (S-QA-050). Without this, a strong set tuned to the seeds alone would mark realistic, on-concern mutants invalid.
    - **Separation:** keeping it apart from generation follows the round-2 review's point that a generator writing its own mutants would grade itself.

## Open dependencies

All four are closed by the DevOps strategy, as mapped in its closure table.

- **OD-QA-1 (DevOps): closed.** Environments: S-DEVOPS-026, -027. Mutation tooling and runs: S-DEVOPS-032. Quarantine, contract and fuzzing jobs: S-DEVOPS-031. What it asked for:
  - an isolated environment per run from a pinned digest (S-TESTAB-002, -003), with seeding, isolation, per-run reset and per-role test accounts (S-TESTAB-004), for generation, healer re-runs, out-of-process gate runs and sessions;
  - the mutation tools per stack, response mutation through interception or a proxy, and the gate, guard and nightly runs within their caps (S-QA-036);
  - the nightly quarantine job, the nightly contract run (S-QA-023) and the spec-fuzzing job (S-QA-022).
- **OD-QA-2 (DevOps): closed** by S-DEVOPS-024 (the `work` and `tokenless` variants) and S-DEVOPS-032 (gate jobs, patch validation and application). It asked for the QA work sandbox (S-QA-017): the fetch step, the S-GEN-066 job with test-environment egress and browser tooling, the hand-off; and the gate-launched `mutant-drafter` and `equivalence-filter` jobs without test credentials, plus the gate's patch validation and sandboxed application of concern mutants (S-QA-038, -039).
- **OD-QA-3 (DevOps): closed.** QA checks and the comment token: S-DEVOPS-020. `qa:*` routing: S-DEVOPS-017. Tracker reads: S-DEVOPS-021. S-ARCH-054 routing and artifacts: S-DEVOPS-017, -031. Tokens: S-DEVOPS-018. Push rulesets: S-DEVOPS-019. Quarantine past 28 days: S-DEVOPS-031. What it asked for:
  - the QA checks as required checks under OD-SEC-2, with the token for the gate's and intake check's comments and dispatches;
  - tracker webhook routing for the `qa:*` labels with the S-QA-013 event classes and the operator actor check; read-only tracker access for the checks, for failure items, verdicts and `qa:source-wrong`;
  - routing the S-ARCH-054 dispatch to QA, and access to the DEV implementation matrix, the ARCH drift report and the trace matrices as CI artifacts;
  - per-job tokens without the workflow-file permission (S-QA-003), and per-identity push rulesets that limit staff-qa to `agent/test-gen-*/**`, `agent/ci-healer/**` and `agent/exploratory/**`;
  - CI that stops honouring a quarantine entry past 28 days (S-QA-029).
- **OD-QA-4 (DevOps): closed** by S-DEVOPS-030. It asked for a per-test result history keyed by test ID v1, with retries, outcome and build digest per run, plus quarantine history, kept for at least the 30-day reference window and readable by QA fetch steps, checks and the healer's fact script (S-QA-027, -028).

## Open questions

None needs an answer now. The open ones each have a recommended option:
- [x] Do concern mutants count toward the blocking ≥60% threshold before `mutant-drafter` reaches stage 2? No: they run in every gate run from day one and feed generator feedback and the decision summary, and count only from stage 2 (`docs/decisions.md`, 2026-11-21, option A; S-QA-039).
- [x] Concern-driven mutants: restored in the gate (`docs/decisions.md`, 2026-11-21; S-QA-039).
- [ ] Do concern mutants and traffic mutation find different weaknesses? This carries over from the legacy doc, and the nightly per-source kill rates answer it (S-QA-039).
- [x] Who covers load, soak and capacity QAS (S-QA-023)? `verification: monitor`, owner DEVOPS (`docs/decisions.md`, 2026-11-20). ARCH carries the rule in S-ARCH-009 and AR-8 (S-ARCH-032).
- [x] How are stacked test PRs merged? Never into a DEV agent branch; they are retargeted to `main` after the product PR lands (`docs/decisions.md`, 2026-11-20; S-QA-012).
- [ ] Should DEV's PR block carry the flaky tests of S-DEV-042 as a structured `flaky[]` field? **Recommended: yes.** Until it does, the healer reads the decision summary's flaky list as an untrusted hint and verifies it by re-running (S-QA-029).
- [x] The shared/security question on repro steps: answered by S-QA-011's structured `repro[]` of bounded fields, and closed in shared/security with a pointer to S-QA-011.
