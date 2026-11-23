---
name: developer-change-contract
description: Always-loaded change contract for the developer agents (Developer and dev-upkeep). Covers the .staff/code.yml code map, path scope, the product-PR block, the DEV checks a change must expect, the read-stage proposed-change form, stage-1 output, load and human-owned items. Use on every Developer or dev-upkeep run.
---

# Change contract for developer agents (S-DEV-004, -005, -009, -010, -018, -021, -022, -024 to -026)

Source: `docs/strategy/roles/developer.md`, the part before "On-demand reference". The machine-readable forms are `schemas/developer-output.schema.json` and `schemas/dev-upkeep-output.schema.json` in this plugin. Where this skill and a schema differ, the schema is what the harness checks; say so in `decision_summary`.

Stack-agnostic: names of tools, languages and frameworks come from the product's `AGENTS.md` and `.staff/code.yml`, never from this skill (S-GEN-002). Tests use the same stack as the app code on each layer.

## Code map: `.staff/code.yml` (S-DEV-004)

The human declares DEV's paths and per-stack patterns per area. Only the human edits it (S-GEN-025). Checks read it from the **base branch**, so a PR can't change the rules it is checked against. Per area:

| Key | Holds |
| --- | --- |
| `source`, `unit_tests`, `generated` | Path globs |
| `protected` | Security-sensitive globs: at least authentication, authorisation, cryptography, secret handling, permission config, data migrations |
| `dependency_files` | Manifests and lockfiles |
| `verification_config` | Lint, formatter, type-check, coverage, mutation and test-runner configs |
| `guard_patterns` | Per stack, line patterns: test declarations (`test_decl`), assertions, skip and expected-failure markers, authorisation checks, validations, permission denies, lint suppressions, testability markers |
| `test_list` | Per stack, the runner's list or collect command (test IDs, S-DEV-045) |
| `generators` | `{generator_id, version, command, inputs, outputs}` for committed generated code (S-DEV-043) |
| `interface_source` | Command that generates the implemented interface from code, or `none` (S-DEV-012) |
| `upkeep_tools` | Formatters, linter autofixes, codemods: `{tool_id, kind, version, command}` |

**No entry for the area: fail closed.** Propose no change; say in `decision_summary` that the area's code-map entry is missing. The one exception is `dev:bootstrap` (Developer only, S-DEV-006).

## Path scope (S-DEV-005)

The scope lint (G2) enforces it by branch prefix and fails a commit without a `Staff-Run-Id` trailer (S-GEN-029).

| Agent | Writes | Never writes |
| --- | --- | --- |
| Developer | The area's `source` and `unit_tests`. `protected`, `dependency_files`, `verification_config` only as flagged diffs (S-DEV-018). `generated` only as `generators` output | `generated` by hand; `architecture/**`; `requirements/**`; `knowledge/**`; `.staff/**`; `.github/**` and CI or pipeline paths; `AGENTS.md`; tests outside `unit_tests` (QA's) |
| `dev-upkeep` | Files changed by an `upkeep_tools` run; `dependency_files`; call sites a bump or migration needs | As the Developer, plus `protected`: a change there becomes a draft Developer ticket (`handoffs[]`) |

Branches are `agent/developer/*` and `agent/dev-upkeep/*` (S-DEV-003). One PR covers **one ticket and one area** (S-GEN-060).

## Product-PR block (S-DEV-009)

Every DEV agent PR opens with its decision summary, then this block (the `pr` object in your schema):
- `kind`: `feature`, `fix`, `drift`, `refactor` or `upkeep`; `ticket`.
- `implements_acs[] {ac, part: full | partial}`: required for `feature`. Declare `full` only when every part of the AC is built.
- `implements[]`: the IF-n@x.y.z versions the change implements.
- `fixes {ticket, target}`: for `fix` and `drift`. Target: an AC, R-ID, IF element or ADR-n/C-k.
- `constraints[] {id, disposition: conform | n/a, reason}`: every `check: review` constraint of the accepted ADRs that the touched components cite.
- `untested_acs[] {ac, reason: other-layer | not-unit-observable}`; `not_unit_observable {target, test_gap}` for a `fix` no unit test can observe; `characterization[]` test IDs.
- `dependencies[] {name, from, to, reason}`; `flags[] {flag_id, reason}`: every diff you expect the code diff check to flag, with your reason.

`refactor` and `upkeep` PRs declare no AC and change no assertion, except as S-DEV-018 allows.

## DEV checks a change must expect

They run as required checks from a source the PR can't change, and fail closed. Detail is on demand (S-DEV-027 to -030, -043, -045).

**PR contract check (S-DEV-010)** fails a DEV agent PR that:
- doesn't open with the decision summary and a schema-valid block, or has a prose field over 2,000 characters;
- covers more than one ticket or area, or changes **more than 500 lines** *(starting value)*, not counting `generated` paths, lockfiles and lane-eligible tool output. Split a larger ticket into several PRs in AC order;
- declares an ID that doesn't exist, or an AC or version that fails the readiness check (S-DEV-007);
- is a `fix` without a passing regression test (S-DEV-029), unless `not_unit_observable` names the target and the test gap for QA. That declaration is a flagged diff;
- is a `drift` PR whose conformance finding still fires on the head.

**Code diff check (S-DEV-018).** A flagged diff needs a human sign-off citing its flag ID (S-ARCH-053, G3). Flagged:
- a test removed, skipped or marked expected-failure; an assertion removed, or changed in an uncited test;
- a removed or changed line matching an authorisation, validation, permission-deny or testability pattern;
- an added lint suppression;
- any change under `protected` or `verification_config`;
- any change to `dependency_files` (also labelled `dev:dependency`, S-SEC-009);
- a `not_unit_observable` declaration.

Blocked outright: deleting a file under `protected` or `verification_config`; a hand edit under `generated`; a `refactor` or `upkeep` PR that changes an assertion, unless it is replay-verified codemod output (flagged instead).

Never weaken a verification artifact to make a change pass (G3). A flag is a request for the human's judgement, never a way around a rule.

## The read-stage proposed change (S-DEV-021, S-DEV-042)

You run read-only: Read, Glob, Grep. You cannot edit, build or run anything. You return a **proposed change** as JSON; you never edit through tools.

- **`proposed_files[] {path, op, from, content[]}`**: `op` is `add`, `modify`, `delete` or `rename`; `from` only for `rename`. `content` is the file's **full new content**, never a diff or a reference, as ordered chunks of at most 2,000 characters. Concatenated in order, the chunks are the file byte for byte. A `delete` has no content. Paths are repo-relative and normalised.
- **After you:** the harness applies the proposal to a fresh checkout of the base in the work sandbox, builds it and runs the tests there (S-DEV-042). It then derives `files[]` from that workspace diff, never from your output, and checks each file: path in scope, the stack's parser accepts it, the secret scan passes, no binary content, the size limit. The write stage commits that `files[]` byte for byte (stage 2) or attaches it as a patch artifact (stage 1).
- **The sandbox gate:** a draft or push needs the build to pass, no unit test of the area that passes on the base to fail on the head, and your added tests to pass. Tests already failing on the base, and flaky tests, are listed by the harness. You can't run them, so reason about them from the code and the CI results you were given, and say what you could not verify.

## Stage-1 output (S-DEV-022) and load (S-DEV-024)

- Stage 1 is advisory (S-GEN-052): comments and drafts only. No branch, PR or commit. Each drafted PR becomes one comment with the rendered decision summary and the full patch as a CI artifact, so each gets its own verdict. `verdict:confirmed` means it would merge as is, or with formatting-only edits.
- The Developer keeps at most 2 open PRs per area awaiting review; `dev-upkeep` opens at most 1 scheduled PR per area per week *(starting values)*.
- **Overlap:** a ticket whose paths overlap an open agent PR waits until that PR merges or closes. `dev-upkeep` skips overlapping files until its next run.
- **Decision summary, first in every DEV PR:** declared ACs and versions; defect items and design requests raised; `check: review` dispositions; flagged diffs with reasons; dependency changes; characterization tests and untested ACs; tests already failing on the base, and flaky tests; the reviewer's verdict, the commit it reviewed and its open findings. Prose follows.

## Human-owned (S-DEV-025, S-DEV-001)

Never set, apply or remove:
- the labels `dev:implement`, `dev:fix`, `dev:review`, `dev:upkeep`, `dev:bootstrap`, `arch:design`, or any `verdict:*` label (G12);
- sign-offs on flagged diffs and `dev:dependency` PRs;
- answers to DEV questions (only operator comments count, as in S-BA-015) and `implemented_acs[]` comments;
- `.staff/code.yml`.

Dependency additions and upgrades, business rules, ADR constraints, boundaries and interfaces are the human's decisions. You propose; the human decides.

## On-demand reference (S-DEV-026)

`staff-engineering:developer-reference` is not preloaded. Read only the sections your trigger needs:

| Agent and trigger | Read |
| --- | --- |
| Developer: `dev:implement`, a ticket turning ready, `kind: refactor` | S-DEV-012, -019, -027, -028, -043, -045 |
| Developer: `dev:fix` or a drift ticket | S-DEV-019, -028, -029, -045 |
| Developer: a review, answer or check failure | S-DEV-027, -028; the S-ARCH-053 sign-off form |
| Developer: `dev:bootstrap` | S-DEV-028, -035 |
| `dev-upkeep`: any run | S-DEV-028, -030, -037 |
