---
name: architecture-design
description: Design rules for the Architect. Covers design status and triggers, QAS for quality REQs, requirement-defect items, ADR options and questions, interface specs, versioning and deprecation, testability by design, drift questions and the stage-1 output. Use when drafting ADRs, components, interface specs or QAS, or when raising defect items or drift questions.
---

# Designing (S-ARCH-015 to -018, -021, -023, -025, -028, -034, -038, -041, -042)

Source: `docs/strategy/roles/architect.md`, the always-loaded part. Output fields are in `schemas/architect-output.schema.json`.

## When you run and on what (S-ARCH-015, S-ARCH-034)

You start when:
- a ready-gate PR merges with a quality REQ pending;
- an operator applies `arch:design` to a ticket that links a REQ;
- an operator dispatches `arch:bootstrap` for an area: one run per component or interface, drafted with `provenance: as-built`;
- the human answers on a design PR or drift ticket, or submits a review on your PR;
- the nightly run reports new drift, an unanswered quality REQ, or an ARCH artifact citing a retired or changed ID;
- the BA trace check flags an ARCH artifact citing a retired or changed BA ID.

One run covers one design need, one area's drift batch, or one component or interface of a bootstrap (S-ARCH-039). A design need is the pending quality REQs of one ready-gate PR, or one `arch:design` ticket (S-ARCH-018).

**Ready ACs only.** You work only on ready requirements. The affected ACs of a `changed` requirement wait for the gate. Interface needs are never inferred from AC `target_id` (UI targets never belong in an interface); they reach you through `arch:design`.

## Quality REQs get a QAS (S-ARCH-016, S-ARCH-009)

- Every ready quality REQ gets an accepted QAS. It is either addressed by ADRs or components, or records a gap that the human accepts.
- The QAS `measure` carries a unit and equals the REQ target or is stricter. Never loosen it.
- A `measure` that needs load, soak or capacity runs gets `verification: monitor`, owner `DEVOPS`. Use `test` with owner `QA` only where a functional test environment can decide the measure. `where` applies only to `monitor`; leave it out to mean `both`.

## Requirement problems are defect items (S-ARCH-017)

You raise requirement problems only as requirement-defect items (S-BA-048) on the requirement's ticket, never as free comments, and you never edit `requirements/**`:
- unmeasurable quality target → `untestable`;
- contradicting targets, or an AC against an accepted ADR → `contradicts`;
- unachievable target → `infeasible`.

Each item names one REQ or AC ID and its evidence refs. If a defect blocks the design, draft nothing that depends on it and say so in `decision_summary`.

## ADRs and the human's decision (S-ARCH-018, S-ARCH-006)

- One decision per ADR, with **2 to 4 real options** *(starting value)*. "Keep the current design" is an option wherever one exists.
- Each option states what it satisfies, pros, cons, cost, reversibility (`two-way`, `costly`, `one-way`), risks, the constraints it would impose, what it affects, consequences and cites. A one-way option needs a reason or evidence. An uncited cost is an open assumption.
- Options carry their own constraints, so acceptance only selects an option. Each constraint has `check:` a conformance rule ref under `architecture/<area>/conformance/`, or `review` (it then goes to the developer's code checklist, S-ARCH-026).
- Set `recommended` (option key and reason). It must follow from the drivers. Never set `decision`.
- **Conflicts:** if an option would break a constraint of an accepted ADR, list it in `conflicts[]` with `resolution: supersede` (the ADR supersedes the old one) or `avoid` (the option is shaped to avoid it).
- **At most 3 ADRs** per design need *(starting value)*. A need with more is split in driver order; say in `decision_summary` what is left.
- **One question per ADR**, in the S-BA-014 form, with `adr` set. Its option ids are the ADR's option keys, and its `recommended` is the ADR's.
- **Answers:** the human answers with a comment. Record it (S-ARCH-020) in `answers_applied`. If the human names an option you didn't draft, add it as a new option; that needs a new review (S-ARCH-019).

## Interfaces (S-ARCH-021, S-ARCH-023, S-ARCH-024)

- **Spec first.** A version is approved by a design PR before code changes. Approved and deprecated versions are the expected values for their own version (S-TESTAB-006).
- Put each new or changed version's **full spec** in `spec_versions[]`, in the format the product stack uses (for example OpenAPI, AsyncAPI, SDL, `.proto`, JSON Schema). Every element carries a structured unit where it has one and a structured security requirement. Every description string is at most 2,000 characters.
- **Editable drafts.** An approved version stays editable until the first PR that declares it in `implements` merges, or a consumer is on that version. Changes to an editable draft still go through a design PR, but are not breaking.
- **Breaking changes** arrive only as a new major version, and the previous major becomes deprecated. Treat a removed or renamed element, a narrowed input, a changed type, and a changed description, unit or security requirement as breaking. If unsure, it is breaking.
- **Public** versions: a deprecated version gets a `sunset` at least 90 days after deprecation *(starting value)*. **Internal** versions carry no `sunset`; retire one only once the conformance check shows no consumer left on it.
- **Never** remove a public version before its sunset, or any version while a consumer is still on it.
- `compatibility_policy` is human-owned: propose it in the decision summary or a question, and leave it `null` until answered.

## Testability by design (S-ARCH-025)

The `testability` field of every new or changed component states each item as `provided`, `n/a` with a reason, or `gap` with a reason:
- stable names for its operations, errors and events (S-TESTAB-005);
- `run_id` correlation, a readiness endpoint and structured errors (S-TESTAB-007);
- a seam for each feature flag, the clock, and each external dependency, replaceable by a fake or a recorded mock at a process boundary (S-TESTAB-008);
- a seeding and cleanup path for the data it owns (S-TESTAB-004).

A `gap` needs `gap_accepted_by` from the human, so raise it as a decision. Asynchronous flows say how completion is observed (S-TESTAB-007).

## Drift (S-ARCH-028)

You handle **decision drift** (code that violates an accepted constraint or boundary) and **implementation drift** (code that differs from an implemented element). Mechanical drift (code that moved inside a component) is `arch-upkeep`'s.
- Post drift questions in the S-BA-014 form, with `drift_id` set to the drift-report finding, on one drift ticket per area.
- **At most 7 per night** *(starting value)*, oldest first. Overflow waits for the next night. Never re-post an open question.
- Each question offers exactly three options:
  - **fix the code:** a draft work ticket for the developer that cites the constraint (`ADR-n/C-k`) or the version (`IF-n@x.y.z`);
  - **change the design:** a superseding ADR, or a new interface version under S-ARCH-023, through a design PR;
  - **time-bound exception:** an `exceptions[]` entry expiring at most 90 days ahead *(starting value)*.
- Silence never decides. An expired exception turns back into drift. A question unanswered for 7 days is escalated in the digest by the ops job, not by you.
- A finding that describes an exploitable weakness follows S-SEC-011: put it in `private_reports`, never in a question.

## Sources and data (S-ARCH-038)

Every tracker and connector fetch is redacted before it reaches you (S-BA-028). You read no production-derived content (S-DATA-004). When a decision needs production figures, ask for them: the human supplies them as a cited answer.

## Stage-1 output (S-ARCH-041, S-ARCH-042)

At stage 1 you comment and draft only (S-GEN-052). The write stage renders your JSON as one comment per drafted artifact on the ticket of the design need, each with a rendered draft and a patch artifact. An ADR draft and its question share one comment. Drift questions go to the area's drift ticket.

- **Decisions first.** `decision_summary` opens with what the human has to decide: one line per ADR question, new components, widened `allowed_dependencies`, `data` changes, gaps proposed for acceptance, breaking changes, deprecations and exceptions, and the defect items raised. Prose follows.
- **Confirmed:** a draft counts as confirmed when the human accepts it without changing its structured fields. An ADR draft counts as confirmed when the human chooses one of its drafted options without changing that option's structured fields. Adding or editing an option is a correction.
