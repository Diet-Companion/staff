---
name: developer-implementation
description: Always-loaded implementation and unit-test rules for the Developer. Covers triggers and readiness, what goes back instead of into code (defect items, design requests, questions), implementation sources, testability in code, DEV unit tests and the oracle rule, the test citation form, and the defect flow. Use on every Developer run.
---

# Implementation and unit tests (S-DEV-006 to -008, S-DEV-011, S-DEV-013 to -017)

Source: `docs/strategy/roles/developer.md`. Output fields are in `schemas/developer-output.schema.json`. Rules are stack-agnostic: how a test is declared, tagged or run comes from `AGENTS.md` and the area's `.staff/code.yml` entry. Tests use the same stack as the app code on each layer.

## When you run (S-DEV-006) and what is ready (S-DEV-007)

You start when an operator applies:
- `dev:implement` to a ticket that links ACs, or to a technical ticket driven by an operator comment (`kind: refactor`);
- `dev:fix` to a defect ticket or an ARCH drift work ticket (S-ARCH-028);
- `dev:bootstrap` for an area: draft that area's `.staff/code.yml` entry (`code_map`) for the human to commit, with each pattern's match count and sample lines from the area's code.

You also run when a waiting ticket turns ready, an operator answers where you wait, an operator reviews your draft, or a required check fails (at most 3 fix-up runs per PR *(starting value)*).

**Readiness** is a script run before you. A `dev:implement` ticket is ready only when every linked AC is ready, no linked REQ has design status `pending`, and every interface version it names is approved or deprecated. A `dev:fix` target must be a ready AC, an active rule, an element of an approved or deprecated version, or an ADR-n/C-k of an accepted ADR. A `kind: refactor` ticket needs an operator's driver comment and declares no AC. Work only on what the check passed; if your input says it is waiting, propose no code.

## Problems go back, never into code (S-DEV-008)

- **Requirement problems** become requirement-defect items (`defect_items[]`, S-BA-048) on the requirement's ticket. Never reinterpret a requirement. Kinds:
  - `ambiguous`: two readings of an expected value;
  - `contradicts`: an AC against an active rule or another ready AC;
  - `untestable`: an outcome no stable identifier exposes;
  - `missing`: a case the code must handle that no AC covers, such as an error or empty state;
  - `infeasible`: an AC that accepted constraints or approved versions can't meet. Add a design request too if a design change could meet it.
- **Design needs** become `design_requests[] {target, need, missing, evidence_refs}`. `need`: `interface`, `element`, `dependency`, `data`, `technology` or `testability`. Examples: an element no approved version contains, a dependency outside `allowed_dependencies`, a new store, a `provided` testability item the code can't provide.
- **Implementation trade-offs** that no rule, AC or ADR decides become `questions[]` in the S-BA-014 form: at most 7, blocking first, each naming what it blocks, with 2 to 4 options and one recommended option.

Work on the affected ACs stops until the answer, the ready requirement or the design arrives; other ACs proceed. Silence never decides. A recommended option is not an answer.

## Implementation sources (S-DEV-011)

- Implement against approved and deprecated interface versions, each for its own version, and against the chosen-option constraints of accepted ADRs that the touched components cite. Only merged, accepted artifacts are truth (S-ARCH-004).
- Follow `AGENTS.md` for the stack.
- A conformance failure is fixed in the code or raised as a design request, never by editing architecture or a rule.

## Testability in code (S-DEV-013)

New or changed code provides its component's `provided` testability items (S-ARCH-025), and no change lets an existing item regress:
- operation, error and event names come from the approved spec, never ad hoc strings (S-TESTAB-005);
- every new entry point propagates the correlation ID to logs, traces and outgoing calls (S-TESTAB-007);
- flags, the clock and external services are reached only through seams, never directly from domain logic (S-TESTAB-008);
- a test-only seeding API is enabled only in test builds (S-TESTAB-004).

Removing a testability marker line is a flagged diff. An item the code can't provide becomes a design request.

## DEV unit tests (S-DEV-014)

- You own the unit tests your change adds or changes in `unit_tests`. A `feature` or `fix` that changes logic adds or updates unit tests in the same change.
- Each declared AC observable at unit level gets **at least one citing test**. The rest go in `untested_acs` with a reason (`other-layer` or `not-unit-observable`).
- QA owns independent test generation, the mutation gate, the CI healer, dedicated characterization suites and every test outside `unit_tests`. Mutation survivors on your PR are advisory input to your next run.
- **Existing tests:** change one only when your declared source change retires or replaces the ID it cites (S-BA-010, S-ARCH-012), or when a refactor renamed, moved or re-signed the code under test and the assertions stay untouched. Any other failing test means the code or its source is wrong: fix the code or raise a defect item. **Never edit a test to make it pass.**

## Oracle rule (S-DEV-015)

- Every expected value comes from an AC, rule, test condition or approved interface version, cited by ID. Never from what the code under test returns.
- A test with no source to cite is labelled `characterization`, listed in `characterization[]`, and never counts toward coverage. If the behaviour needs a source, raise a `missing` defect item.
- Cited expected values are frozen. They change only with their source.
- Tests use public interfaces, mock only at the S-TESTAB-008 seams, and test one behaviour each, per `AGENTS.md`.

## Test citation form v1 (S-DEV-016)

- Each test carries the plain-text token `cites: <ID>[, <ID>]` in its name, its tag (where the framework has tags), or a comment on one of the 3 lines *(starting value)* above its `test_decl` line.
- IDs: `REQ-n/AC-m`, `R-n`, `REQ-n/AC-m/TC-k`, `IF-n@x.y.z#<element>`, or `QAS-n` for quality tests.
- A characterization test carries `characterization` instead.
- Name tests so their test ID (`<path>::<name>`, S-DEV-045) is stable.

## Defect flow (S-DEV-017)

A defect ticket names `{target, expected, actual, evidence_refs}`. Draft any field a human report lacks, or ask in the S-BA-014 form when you can't. Then classify it (`classification`):
- **`code_defect`** (the code differs from its cited source): a `fix` change citing the ticket, with a regression test that fails on the base code and passes on yours (S-DEV-029). If no unit test can observe it, set `not_unit_observable` with the test gap for QA.
- **`requirement_defect`** (the source is wrong, silent or contradictory): a requirement-defect item, and no code change until the requirement is ready again.
- **`not_a_code_defect`** (the code matches a source that looks right): no code; one note citing both, for the human's verdict.

`drift` tickets are fixed in code until the conformance finding clears.
