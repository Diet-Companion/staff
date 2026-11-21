# Architect Strategy (ARCH)

Updated Nov 20, 2026

## Purpose and scope

This doc covers how architecture is decided, recorded and kept true to the code when one human works with agent staff. ARCH comes after BA (`docs/decisions.md`, 2026-11-20). It takes ready requirements, especially quality requirements, and produces what developer, DevOps and test engineer agents build against. It is product-agnostic and stack-agnostic.

It honours the common set in S-GEN-064, plus S-GEN-018. GEN, shared/ and BA decisions are referenced by ID, never restated.

The part under "On-demand reference" is not always loaded (S-ARCH-048).

Markers:
- *(starting value)*: accepted by the human in `docs/decisions.md` (2026-11-20).
- *(proposed)*: awaiting human confirmation. No *(proposed)* item is open. Every value in Assumptions item 1 was accepted (`docs/decisions.md`, 2026-11-20).

Named formats and tools are examples.

## Ownership and agents

- **S-ARCH-001** Ownership split:
  - **The human decides** ADR outcomes and the option chosen, technology choices with real trade-offs, components, boundaries, allowed dependencies and data ownership, compatibility policies, breaking changes, conformance exceptions, and accepted quality and testability gaps.
  - **Agents** draft options and trade-offs, write component descriptions, interface specs and quality scenarios, check conformance, and keep the architecture docs current.

  An agent never sets a human-owned field (S-ARCH-020). *Depends on:* S-GEN-001, S-ARCH-020.
- **S-ARCH-002** Agents and checks. The working agents are in staff-engineering (S-GEN-014):
  - **Architect:** drafts ADRs, component descriptions, interface specs and quality scenarios, and raises requirement-defect items and drift questions.
  - **`arch-upkeep`:** keeps component `code_paths` and the overview current after product PRs merge.

  The reviewer is `reviewer/architecture`, the `architecture` artifact type of the shared reviewer. This doc owns its checklist (S-ARCH-031).

  Conformance is not an agent. Structural conformance is a check script (S-ARCH-027). ADR constraints marked `check: review` are an item in the developer's code checklist, which already reads the code diff (CC-2 in S-DEV-031). `arch-upkeep` is separate from the Architect because its trigger (merged code), its eval (diff-seeded mapping) and its stage-3 lane all differ. *Depends on:* S-GEN-014, S-GEN-030, S-ARCH-027, S-ARCH-031, S-DEV-031.
- **S-ARCH-003** Identities:
  - The Architect and `arch-upkeep` run as the staff-engineering identity, and `reviewer/architecture` as the staff-review identity (S-GEN-026).
  - All three use the two-stage split (S-SEC-002) with the schemas in S-ARCH-037.
  - Each agent pushes only to `agent/<agent>/*` branches. The scope lint maps the prefix to the agent's scope (S-ARCH-035), and fails a staff-engineering branch with an unknown prefix closed. This is a consistency check. The security boundary is the plugin's token and path scope, which staff-engineering shares with the developer and DevOps agents (S-GEN-025, S-GEN-026).

  *Depends on:* S-GEN-025, S-GEN-026, S-SEC-002, S-ARCH-035, S-ARCH-037.

## Architecture artifact model

The required fields are in the on-demand reference (S-ARCH-006 to -010). They ship as schemas in staff-engineering `schemas/`, which ARCH agents always load (S-ARCH-036).

- **S-ARCH-004** The product repo is the single source of truth for architecture. Tickets, PR comments and unmerged drafts are untrusted (S-SEC-001). Agents treat these as truth: merged accepted ADRs, active components, accepted QAS, and approved or deprecated interface versions, each for its own version until it retires. Everything else is a candidate, never an oracle. *Depends on:* S-GEN-010, S-SEC-001, S-TESTAB-006.
- **S-ARCH-005** Types and IDs:

  | Artifact | ID | Notes |
  | --- | --- | --- |
  | Architecture decision record | ADR-n | One decision with 2–4 options |
  | ADR constraint | ADR-n/C-k | A rule imposed by an option, which applies once that option is chosen |
  | Component or boundary | CMP-n | Has an immutable stable `name` (S-TESTAB-005) |
  | Interface | IF-n; a version is IF-n@x.y.z | API, event or data contract. Its spec holds the operation, error and event names |
  | Quality-attribute scenario | QAS-n | The architectural answer to one quality REQ |
  | Architecture overview | none | Bounded prose in named sections |

  IDs are allocated, padded and checked for duplicates as in S-BA-005. *Depends on:* S-BA-005, S-TESTAB-005.
- **S-ARCH-011** Lifecycles. Nothing is deleted.

  | Artifact | States |
  | --- | --- |
  | ADR | proposed, which exists only in PRs and stage-1 comments → accepted or rejected, set by `decision.outcome` → superseded (a newer accepted ADR names it in `supersedes`) or deprecated (`deprecated_reason`) |
  | Component | proposed → active → deprecated (new dependencies on it are violations) → retired (its `code_paths` match no file) |
  | Interface version | draft (in a PR) → approved (merged: truth for implementation) → deprecated (public versions have a `sunset`) → retired. Whether each element is implemented is derived, not stored (S-ARCH-021) |
  | Quality scenario | draft → accepted → retired (with `replaced_by`) |

  The lifecycle check fails an ADR merged as `proposed`, and any status change made another way. *Depends on:* S-ARCH-006, S-ARCH-020, S-ARCH-021.
- **S-ARCH-012** A change in meaning gets a new ID:
  - An accepted ADR's `decision`, `drivers` and chosen option never change. A new ADR supersedes it.
  - A QAS whose `measure` or `req` changes is retired and replaced.
  - A component's `name` never changes. A rename retires the component and adds a new one.
  - A breaking interface change needs a new major version (S-ARCH-023).
  - Edits to prose, and adding an exception (S-ARCH-028), keep the ID.

  *Depends on:* S-ARCH-023, S-ARCH-028.
- **S-ARCH-013** Product-contract paths (closes the artifact-path part of OD-GEN-2 for ARCH):
  - `architecture/overview.md`;
  - `architecture/<area>/adr/ADR-n.md` and `architecture/<area>/components/CMP-n.md`;
  - `architecture/<area>/interfaces/IF-n.md`, with one spec file per version under `architecture/<area>/interfaces/IF-n/`;
  - `architecture/<area>/quality/QAS-n.md`;
  - `architecture/<area>/conformance/`, which holds the conformance rules (S-ARCH-026).

  Cross-area artifacts sit under `architecture/system/`. `.staff/areas.yml` maps that directory and the overview to an area like any other path (S-GEN-060). The ARCH schemas and check scripts ship in staff-engineering `schemas/` and `checks/`. Both are human-only (S-GEN-025) and outside the improver allowlist (S-GEN-027). *Depends on:* S-GEN-017, S-GEN-025, S-GEN-027, S-GEN-060, OD-GEN-2.
- **S-ARCH-014** S-BA-012's no-invented-facts rule applies to every ARCH agent draft. ARCH sources also include ARCH IDs, spec refs, code refs and CI results. Any load figure, cost or capacity that no source states is an open assumption. *Depends on:* S-BA-012.

## From requirements to design

- **S-ARCH-015** Design status (closes the architect trigger part of OD-BA-3). The ARCH trace check computes a status for each ready requirement (S-BA-019):
  - **Quality REQ:** `pending` until an accepted QAS cites it, then `done`. An accepted gap QAS also counts as an answer.
  - **`arch:design`:** an operator applies this label to a ticket that links the REQ, and the status is `pending`. It becomes `done` when a merged ARCH artifact cites the ticket in `design_for` and no open design PR carries the ticket in `design_for`. It becomes `not-needed` when an operator removes the label. The check accepts label events only from accounts in `governance/operators.yml`, and reads them through the tracker (S-DEVOPS-021).
  - **Otherwise:** `not-needed`.

  Interface needs are not inferred from AC `target_id`, because UI targets (S-BA-007) never belong in an interface. They reach ARCH through `arch:design`. The human applies it after RC-3 flags an interface that has no spec (S-BA-030), or after a developer agent asks for design (S-DEV-008).

  The Architect works only on ready ACs. The affected ACs of a `changed` requirement wait for the gate, and the nightly run flags any ARCH artifact that cites them. *Depends on:* S-BA-004, S-BA-007, S-BA-009, S-BA-019, S-BA-030, S-ARCH-030, S-DEV-008, S-DEVOPS-021.
- **S-ARCH-016** Every ready quality REQ gets an accepted QAS. The QAS is either addressed by ADRs or components, or records a gap that the human accepted. A ready quality REQ with neither 14 days after it became ready *(starting value)* is a nightly finding. *Depends on:* S-ARCH-009, S-ARCH-030.
- **S-ARCH-017** The Architect raises requirement problems only as requirement-defect items (S-BA-048) on the requirement's ticket. It never uses free comments and never edits `requirements/**`. Kinds map as follows:
  - unmeasurable quality target → `untestable`;
  - contradicting targets, or an AC against an accepted ADR → `contradicts`;
  - unachievable target → `infeasible`.

  *Depends on:* S-BA-048.

## Human decisions

- **S-ARCH-018** Design PRs. At stage 2 the Architect opens one design PR per design need. A need is the pending quality REQs of one ready-gate PR, or one `arch:design` ticket.
  - **Size:** a design PR holds at most 3 ADRs *(starting value)*. A need with more is split into several design PRs, in driver order.
  - **Decision summary:** each design PR opens with one, listing:
    - one question per ADR in the S-BA-014 form. Its options table shows each option's satisfied drivers, constraints, cost, reversibility and risks, plus the recommended option;
    - new components, widened `allowed_dependencies`, and `data` changes;
    - testability and quality gaps proposed for acceptance;
    - breaking changes, deprecations and new exceptions needing sign-off;
    - the requirement-defect items raised;
    - the reviewer's verdict, the commit it reviewed, and its open findings.
  - **Answers:** the human answers with a comment, and the Architect records the answer (S-ARCH-020). If the human names an option that wasn't drafted, the Architect adds it and re-requests review (S-ARCH-019).

  The human's merge is the decision (S-GEN-003). *Depends on:* S-GEN-003, S-BA-014, S-ARCH-019, S-ARCH-020.
- **S-ARCH-020** Human-owned fields:
  - ADR `decision {outcome, chosen, decided_by}`, `superseded_reason`, `deprecated_reason`;
  - `exceptions[].accepted_by`;
  - QAS `gap_accepted_by`, and component `testability[].gap_accepted_by`;
  - interface `compatibility_policy`; a version `sunset` earlier than S-ARCH-023 allows; `external_retired_by`; `provenance_confirmed_by`;
  - `accepted` and `rejected` entries in `review_dispositions`, and `review_waiver`;
  - sign-offs on flagged diffs (S-ARCH-053).

  Answers count as in S-BA-015. The ARCH owner-field check fails an agent commit that sets one of these fields without citing an operator answer. *Depends on:* S-BA-015, S-ARCH-023, S-ARCH-053.

## Interfaces

- **S-ARCH-021** Specs as ground truth (ARCH's share of S-TESTAB-006):
  - **Expected values:** approved and deprecated versions are the source of expected values for their own version. Developers implement against them and QA tests against them (S-DEV-005, S-QA-023).
  - **Spec first:** a version is approved by a design PR before code changes.
  - **Implementation, per element:** a product PR that implements part or all of a version lists it in `implements[]` (S-DEV-009). The conformance check compares elements, which are operations, fields, errors and events (S-ARCH-027). It blocks on two things: an element the PR implements differently from the spec, and an element the PR adds or changes that no approved version contains. Spec elements not yet built are not differences.
  - **Implemented:** derived per element on `main`. Where `interface_source` is `none`, it comes from QA's contract results over S-QA-023's merged-`implements[]` target set. A version counts as implemented once none of its elements is missing.
  - **Pending and drift:** elements not yet built are listed as pending implementation, not as drift. A later difference in an implemented element is drift (S-ARCH-028).
  - **Editable drafts:** an approved version stays an editable draft until whichever comes first:
    - the first PR that declares this version in `implements` merges;
    - a consumer is on this version. Either the conformance check derives it, as S-ARCH-027 does for deprecated versions, or the version's optional `consumers` names it.

    Interface-level `consumers`, including `external`, never end a draft. Only consumers on this version do. Changes to a draft still go through a design PR, but they are not classed as breaking (S-ARCH-022).

  *Depends on:* S-TESTAB-006, S-ARCH-022, S-ARCH-027, S-ARCH-028, S-DEV-005, S-DEV-009, S-QA-023.
- **S-ARCH-023** Versioning and deprecation. The compatibility rules are in S-ARCH-022.
  - **Breaking changes:** a breaking change only arrives as a new major version, and the previous major becomes deprecated.
  - **Public interfaces:** the deprecated version gets a `sunset` at least 90 days after deprecation *(starting value)*. External consumers count as gone at sunset only when the human signs `external_retired_by`.
  - **Internal interfaces:** a deprecated version carries no `sunset`. A later Architect PR retires it once the conformance check shows no consumer left on it. That is the only gate.
  - **Blocked:** removing a public version before its sunset, and removing any version while a consumer is still on it.

  *Depends on:* S-ARCH-020, S-ARCH-022, S-ARCH-027.
- **S-ARCH-024** Stable names (delivers S-TESTAB-005 for components and interfaces). Component names never change, and neither do the operation, error and event names within a major version. A rename is a retire-and-replace (S-ARCH-012), and for interfaces it is a breaking change. *Depends on:* S-TESTAB-005, S-ARCH-012, S-ARCH-022.

## Testability by design

- **S-ARCH-025** Design rules (closes OD-TESTAB-2). The `testability` field of every new or changed component states each item below as `provided`, `n/a` with a reason, or `gap`:
  - stable names for its operations, errors and events (S-TESTAB-005);
  - `run_id` correlation, a readiness endpoint and structured errors (S-TESTAB-007);
  - a seam for each feature flag, the clock, and each external dependency, which can be replaced by a fake or a recorded mock at a process boundary (S-TESTAB-008);
  - a seeding and cleanup path for the data it owns (S-TESTAB-004).

  A `gap` needs `gap_accepted_by` (S-ARCH-020). The human then enters it in the testability manifest (S-TESTAB-001). Developers implement these items (S-DEV-013). *Depends on:* S-TESTAB-001, S-TESTAB-004, S-TESTAB-005, S-TESTAB-007, S-TESTAB-008, S-ARCH-020, S-DEV-013.

## Drift

- **S-ARCH-028** Who repairs drift:
  - **Mechanical doc-side drift** (code that moved inside a component) goes to `arch-upkeep`.
  - **Decision drift** (code that violates an accepted constraint or boundary) and **implementation drift** (code that differs from an implemented element, S-ARCH-021) go to the Architect. It posts drift questions in the S-BA-014 form on one drift ticket per area, at most 7 per night *(starting value)*, oldest first. Overflow waits for the next night. An open question is never re-posted. A question unanswered for 7 days *(starting value)* is escalated in the digest. Each question offers:
    - **fix the code:** a draft work ticket for the developer that cites the constraint or the version (S-DEV-006);
    - **change the design:** a superseding ADR, or a new interface version under S-ARCH-023, through a design PR;
    - **time-bound exception:** an `exceptions[]` entry that expires at most 90 days ahead *(starting value)*.
  - Silence never decides. An expired exception turns back into drift.
  - A finding that describes an exploitable weakness follows S-SEC-011 instead.

  *Depends on:* S-BA-014, S-SEC-011, S-ARCH-006, S-ARCH-021, S-ARCH-023, S-ARCH-027, S-DEV-006.

## Triggers, scope, context and schemas

- **S-ARCH-034** Triggers (closes OD-GEN-1 for ARCH). The event classes are those of S-BA-034: operator events, staff-app PR events (which may trigger only `reviewer/architecture`), and check and schedule events. Everything else is dropped.

  | Agent | Starts when |
  | --- | --- |
  | Architect | A ready-gate PR merges with a quality REQ pending (S-ARCH-015). An operator applies `arch:design`. An operator dispatches `arch:bootstrap` for an area: one run per component or interface, drafted with `provenance: as-built`. The human answers on a design PR or drift ticket, or submits a review on an Architect PR. The nightly run reports new drift, an unanswered quality REQ, or an ARCH artifact citing a retired or changed ID. Or the BA trace check (S-BA-021) flags an ARCH artifact citing a retired or changed BA ID |
  | `arch-upkeep` | One nightly run across all areas, when product PRs that touch mapped code merged that day or mapping findings exist. It runs in the concurrency group of the `system` area (S-ARCH-013, S-GEN-060), and works area by area, oldest change first. It stops before its cap. The remaining areas wait for the next night, and the digest lists them. Overlap with open Architect PRs follows S-GEN-060. Overview updates for the acceptances merged since the last one are batched weekly *(starting value)* into that run |
  | `reviewer/architecture` | A PR touching `architecture/**` becomes ready for review, or its review is re-requested |

  *Depends on:* S-GEN-005, S-GEN-060, S-BA-021, S-BA-034, S-ARCH-013, S-ARCH-015, S-ARCH-027, S-ARCH-030, S-DEVOPS-017, S-DEVOPS-031, OD-GEN-1.
- **S-ARCH-035** Path scope (closes the agent-scope part of OD-GEN-2 for ARCH). The scope lint (G2) enforces it by branch prefix (S-ARCH-003). It also fails an ARCH agent commit that has no `Staff-Run-Id` trailer (S-GEN-029).

  | Agent | Writes | Never writes |
  | --- | --- | --- |
  | Architect | `architecture/<area>/**` | `architecture/overview.md`, `requirements/**`, `knowledge/**`, code, CI, tests |
  | `arch-upkeep` | `architecture/overview.md`; only the `code_paths` field in `architecture/*/components/**`. The component diff check blocks any other field change (S-ARCH-044) | Everything else |
  | `reviewer/architecture` | No paths: comments and the label in S-ARCH-037 | Any path |

  *Depends on:* S-GEN-020, S-GEN-025, S-GEN-029, S-ARCH-003, S-ARCH-044, OD-GEN-2.
- **S-ARCH-036** Context, in addition to the always-loaded set in S-GEN-009:

  | Agent | Always loaded | Retrieved on demand |
  | --- | --- | --- |
  | Architect | Product core, overview, ARCH schemas, own learnings | Ready REQs and ACs; the area's ADRs, components, specs and QAS; code; the drift report; reviewer comments; domain plugins; this doc's on-demand reference |
  | `arch-upkeep` | Overview, component schema, own learnings | Merged PR diffs, component descriptions, the drift report |
  | `reviewer/architecture` | Checklist (S-ARCH-031 to -033), overview | The cited ADRs, components, specs and REQs; the compatibility check output |

  *Depends on:* S-GEN-009, S-GEN-048.
- **S-ARCH-037** Read-stage schemas and write actions (closes OD-GEN-6 and OD-SEC-1 for ARCH). Every free-text field and spec description string holds at most 2,000 characters (S-SEC-002).

  | Agent | Read-stage output | Allowed write actions |
  | --- | --- | --- |
  | Architect | `artifacts[]` (S-ARCH-006 to -009 schemas); `spec_versions[]` {if_id, version, document}, where each document is a full spec, validated against its format's schema; `conflicts[]` {constraint_id, option_key, resolution: supersede, avoid}; `defect_items[]` (S-BA-048); `questions[]` (S-BA-014 form, with `adr` or `drift_id`); `assumptions[]`; `answers_applied[]` {field, comment ref}; `source_refs[]` | Stage 1: comments as in S-ARCH-041, requirement-defect items, drift tickets and their questions, and draft developer tickets. Stage 2 adds: an `agent/architect/*` branch and PR in its paths, comments on its own PRs, and the labels `agent` and `arch:decision` |
  | `arch-upkeep` | `component_patches[]` {cmp_id, code_paths_added[], code_paths_removed[], evidence_refs[]}; `overview_sections[]` {section_id, text}; `unmapped[]` {path, candidate_cmp, reason} | Stage 1: comments as in S-ARCH-041. Stage 2 adds: an `agent/arch-upkeep/*` branch and PR in its paths, and the label `agent` |
  | `reviewer/architecture` | `target`; `reviewed_sha`; `verdict`; `findings[]` {finding_id, checklist_id, severity, location, text, rewording, cited_ids, classification}; `questions[]` | One comment per run on the PR; the label `arch:not-ready` |

  No ARCH agent writes `verdict:*` labels (G12), and none applies or removes `arch:design`. *Depends on:* S-SEC-002, S-SEC-003, S-GEN-020, S-BA-014, S-BA-048, S-ARCH-041.
- **S-ARCH-038** ARCH read stages apply the read-time redaction rule of S-BA-028 to every tracker and connector fetch. ARCH agents read no production-derived content (S-DATA-004). When a decision needs production figures, the human supplies them as a cited answer, so OD-DATA-2 needs no ARCH part. *Depends on:* S-DATA-004, S-BA-028.

## Stage-1 output, load and knowledge

- **S-ARCH-041** Stage-1 output (comment and draft only, S-GEN-052). The agent posts one comment per drafted artifact, each with a rendered draft and a patch artifact (S-DATA-003), so each draft gets its own verdict (S-GEN-071).
  - **Architect:** comments on the ticket of the design need. An ADR draft and its question share one comment.
  - **`arch-upkeep`:** comments on one draft ticket per night.

  **When a draft counts as confirmed:**
  - Most drafts count as confirmed when the human accepts them without changing their structured fields.
  - An ADR draft counts as confirmed when the human chooses one of its drafted options, recommended or not, without changing that option's structured fields.
  - Adding an option or editing one counts as a correction.

  *Depends on:* S-GEN-052, S-GEN-071, S-DATA-003.
- **S-ARCH-042** Load (S-GEN-061, S-GEN-073):
  - Design PRs and at most one `arch-upkeep` PR per night count toward the working-agent cap.
  - Drift questions, reviewer comments and nightly findings reach the human through the digest, as one item per ticket or check.
  - Every ARCH PR opens with its decisions. The options table is the review.

  *Depends on:* S-GEN-061, S-GEN-063, S-GEN-073, S-ARCH-018.
- **S-ARCH-046** ARCH agents treat the product core and the rules registry as truth (S-BA-022), and never write `knowledge/**`. Accepted ADRs and approved specs are live sources (S-GEN-018). A rule candidate that an ARCH agent finds goes into its output as an advisory note, which the digest lists. *Depends on:* S-GEN-018, S-BA-022.
- **S-ARCH-048** Context budget and packaging (S-GEN-009, `docs/decisions.md`, 2026-11-20).
  - **Packaging:** S-GEN-009's packaging rule sets what is always loaded, what is on demand, how it is measured and the cap. The latest figures are in Assumptions item 2.
  - **Reviewer pack:** S-ARCH-031 to -033, which `reviewer/architecture` keeps always loaded (S-ARCH-036).
  - **What is on demand:** what only check scripts, the reviewer or occasional lookups need: artifact fields, the checks, the checklist, interfaces, caps and records, and evals, stages and metrics.
  - **Growth:** if the always-loaded part goes over the limit, more sections move (S-GEN-048).

  Agents retrieve the moved decisions they act on, per trigger:

  | Agent and trigger | Retrieves |
  | --- | --- |
  | Architect: design need or `arch:bootstrap` | S-ARCH-006 to -010 (fields), -019 (gate), -022 (compatibility), -026 (conformance rules), -044 (diff checks) |
  | Architect: human answer on a design PR | S-ARCH-019 item 6 (re-review), -053 (sign-off form) |
  | Architect: drift batch | S-ARCH-026, -027 |
  | `arch-upkeep`: nightly run | S-ARCH-007, -010, -044 (component and overview checks), -050 (lane class) |
  | `reviewer/architecture`: any run | S-ARCH-019 item 6, -022, -023. S-ARCH-031 to -033 are its always-loaded checklist (S-ARCH-036) |

  *Depends on:* S-GEN-009, S-GEN-048, S-ARCH-036.

## On-demand reference

### Artifact fields

- **S-ARCH-006** ADR fields. The schema is versioned in staff-engineering `schemas/` (S-GEN-022).
  - `id`, `title`, `status`, `area` (S-GEN-060), `date`, `design_for` (ticket refs);
  - `drivers`: REQ IDs (quality REQs first), QAS IDs, or for a technical decision with no requirement, an operator comment ref;
  - `context`: cited prose;
  - `options[]`: 2–4 *(starting value)*, each `{key, summary, satisfies[], pros, cons, cost, reversibility: two-way | costly | one-way, risks, constraints[], affects, consequences, cites}`. Each constraint is `{id: ADR-n/C-k, statement, kind: dependency | interface | technology | data | deployment | other, check: <rule ref> | review}`. "Keep the current design" is an option wherever one exists;
  - `recommended`: an option key and a reason, set by the agent;
  - `decision` (S-ARCH-020). Only the chosen option's constraints apply;
  - `exceptions[]` {constraint, paths, reason, accepted_by, expires};
  - `supersedes`, `superseded_by`, `superseded_reason: wrong | context-changed | refined`, `deprecated_reason`;
  - `review_dispositions` and `review_waiver`, with the semantics of S-BA-006;
  - `sources`, `assumptions`, `questions` and `revision`, in the S-BA-006 form.

  Prose fields hold at most 2,000 characters each (S-SEC-002). *Depends on:* S-GEN-022, S-GEN-060, S-SEC-002, S-BA-006, S-ARCH-020.
- **S-ARCH-007** Component fields:
  - `id`, `name` (immutable), `status`, `area`, `design_for`, `responsibilities`;
  - `provides` and `consumes`: IF IDs;
  - `allowed_dependencies`: CMP and IF IDs;
  - `code_paths`: path globs;
  - `data`: the stores it owns. A store is shared only if an ADR allows it;
  - `deployment` {unit, state: stateless | stateful, runtime_dependencies[]};
  - `testability[]` {item, state, reason, gap_accepted_by} (S-ARCH-025);
  - `provenance: designed | as-built`, `provenance_confirmed_by`;
  - `cites` (ADR IDs) and `revision`.

  *Depends on:* S-ARCH-020, S-ARCH-025.
- **S-ARCH-008** Interface fields:
  - `id`, `name`, `kind: api | event | data`, `owner` (CMP ID), `design_for`;
  - `compatibility_policy: public | internal`;
  - `consumers`: CMP IDs, or `external`;
  - `cites`: REQ and ADR IDs;
  - `versions[]` {version, status, spec (path), consumers (optional: CMP IDs declared on this version, S-ARCH-021), sunset (public interfaces only), replacement, provenance: designed | as-built, provenance_confirmed_by, external_retired_by};
  - `revision`.

  The spec format follows the product stack (S-GEN-002), for example OpenAPI, SDL, `.proto`, AsyncAPI or JSON Schema. Every element carries a structured unit where it has one, and a structured security requirement, using the format's own fields or an extension (S-ARCH-022). An `as-built` version records observed behaviour. QA treats it as characterization until `provenance_confirmed_by` is set (S-QA-006, S-QA-023). The lifecycle, compatibility and diff checks work per version entry. *Depends on:* S-GEN-002, S-TESTAB-006, S-ARCH-020, S-ARCH-022, S-QA-006, S-QA-023.
- **S-ARCH-009** QAS fields:
  - `id`, `status`, `req` (the quality REQ ID);
  - `attribute`, `stimulus`, `environment`, `artifact` (CMP or IF ID), `response`;
  - `measure`: with a unit, equal to the REQ target or stricter;
  - `addressed_by`: ADR or CMP IDs, or `gap` with `gap_reason` and `gap_accepted_by`;
  - `verification` {method: test | monitor | analysis, owner: QA | DEVOPS, where: pre-production | production | both}:
    - A `measure` that needs load, soak or capacity runs gets `verification: monitor` with owner DEVOPS (`docs/decisions.md`, 2026-11-20).
    - `test` with owner QA is used only where the measure can be decided in a functional test environment (S-QA-023).
    - `where` applies to `monitor`. A missing value reads as `both` *(starting value, `docs/decisions.md`, 2026-11-21)*. S-DEVOPS-040 reads it;
  - `revision`.

  *Depends on:* S-BA-005, S-ARCH-020, S-QA-023, S-DEVOPS-040.
- **S-ARCH-010** The overview is prose: the system context, the main flows, and pointers to IDs. It is split into named sections of at most 2,000 characters each, is patched per section, and is limited to 3,000 tokens in total *(starting value)* (S-GEN-048). The ADR index, the component map and the dependency graph are generated by CI and published as CI artifacts, not committed (S-GEN-012). *Depends on:* S-GEN-012, S-GEN-048, S-SEC-002.

### Gate, compatibility, conformance and trace checks

- **S-ARCH-019** Gate check. It applies to any PR that sets an ADR outcome, or that makes a component, interface version or QAS active, approved or accepted. It scripts only the structural items:
  1. the schema, ID, lifecycle, source-ref, owner-field, compatibility and conformance checks pass, and every diff flagged under S-ARCH-044 has a sign-off (S-ARCH-053);
  2. every decided ADR has `decision.outcome`, `decided_by` citing an operator answer, and for `accepted`, a `chosen` key that names a drafted option;
  3. every driver is a ready REQ, an accepted QAS, or an operator comment ref;
  4. every ID in `affects`, `provides`, `consumes` and `allowed_dependencies` exists;
  5. every new or changed component has a complete `testability` field (S-ARCH-025);
  6. a `reviewer/architecture` result exists for a commit whose fields match the head, ignoring `decision`, `status`, answer entries in `sources`, and the `review_*` fields. Every AR-1 "conflicts" finding has a `review_dispositions` entry. Alternatively, `review_waiver` cites an operator comment for this revision. An option added after the human's answer always needs a new review.

  The human judges the semantic items from the decision summary: whether the options are real, the trade-offs fair, and the choice sound. *Depends on:* S-ARCH-018, S-ARCH-020, S-ARCH-022, S-ARCH-025, S-ARCH-044, S-ARCH-053.
- **S-ARCH-022** Compatibility rules. The compatibility check combines a diff tool for the spec's format (for example an OpenAPI diff, GraphQL Inspector or `buf breaking`) with these rules. A diff to an existing element is **breaking** if it does any of these:
  - removes or renames an operation, field, enum value, event, error code or stable name;
  - makes an optional input required, or narrows the inputs accepted;
  - changes a type, or adds an output value that existing consumers can't parse;
  - changes a description, unit or security requirement.

  The last rule covers what format tools can't see. It holds unless the human signs the diff off as compatible (S-ARCH-053). If the tool is unsure, the diff counts as breaking. Every other diff is compatible.

  **Exempt:** a version that is still an editable draft (S-ARCH-021). *Depends on:* S-ARCH-021, S-ARCH-053.
- **S-ARCH-026** Conformance rules have three machine-checkable sources:
  - component `allowed_dependencies` and `data` ownership;
  - the chosen option's constraints with `check: <rule ref>`. Their rules sit in `architecture/<area>/conformance/` and run with the stack's dependency tool, for example ArchUnit, dependency-cruiser or import-linter;
  - the comparison of implemented versions with the implemented interface (S-ARCH-021). That interface comes from a spec generated from code (S-DEV-012). Where `interface_source` is `none`, it comes from QA's contract results over S-QA-023's target set, which on `main` is every element of the versions that merged PRs declare in `implements[]`.

  Constraints with `check: review` go to the developer's code checklist (CC-2 in S-DEV-031). *Depends on:* S-ARCH-006, S-ARCH-007, S-ARCH-021, S-DEV-012, S-DEV-031, S-QA-023.
- **S-ARCH-027** The conformance check:
  - **On every product PR (blocking):**
    - violations the diff adds;
    - elements the PR implements differently from the approved version it declares in `implements`;
    - in areas with an implemented-interface source, elements that any PR adds or changes and that no approved version contains. This catches new endpoints or events outside every IF. Unspecified elements that already exist go to the nightly report instead.

    Spec elements that aren't built yet never block (S-ARCH-021). The check runs with the base branch's rules, so a PR can't loosen a rule and pass in one step.
  - **Nightly (non-blocking):** the drift report. It lists:
    - existing violations and implementation drift;
    - existing implemented elements that no approved version contains;
    - elements pending implementation per approved version, in their own section, with the versions now fully implemented;
    - unmapped code, and components whose `code_paths` match nothing;
    - expired exceptions;
    - the consumers still on each deprecated version.

  The report is a CI artifact. Its findings go through the recorder (S-GEN-026), as unlinked `check_outcome` records (S-GEN-031), to the digest (S-GEN-063). Where an area's `interface_source` is `none`, the nightly report uses QA's contract results over S-QA-023's merged-`implements[]` target set instead, and says so. There, an element counts as pending only when its test shows it absent (S-QA-023). *Depends on:* S-GEN-026, S-GEN-031, S-GEN-063, S-ARCH-021, S-ARCH-026, S-QA-023.
- **S-ARCH-029** The trace chain is REQ → QAS → ADR or IF → CMP → code paths → tests. Links are stored on the citing side, as in S-BA-020:
  - QAS cite REQs;
  - ADRs cite REQs and QAS;
  - interfaces cite REQs and ADRs;
  - components cite ADRs and IFs;
  - code reaches components through `code_paths`;
  - product PRs cite versions through `implements`;
  - tests cite IF operation names (S-QA-007).

  *Depends on:* S-BA-020, S-DEV-009, S-QA-007.
- **S-ARCH-030** ARCH trace check, a script in staff-engineering `checks/`.
  - **Split with the BA check:** the BA trace check (S-BA-021) covers citations from ARCH artifacts into BA IDs. This check applies the same blocking scope and exemptions to citations of ARCH IDs from any file.
  - **Nightly additions:**
    - unanswered quality REQs (S-ARCH-016);
    - citations of versions past their sunset;
    - ARCH artifacts citing affected ACs of `changed` requirements;
    - active IF operations that no test cites. This finding triggers QA's `test-gen-api` (S-QA-013).
  - **Output:** the design status of S-ARCH-015, in the ARCH trace matrix, a CI artifact that developer triggers read (S-DEV-007).

  *Depends on:* S-BA-021, S-ARCH-015, S-ARCH-016, S-DEV-007, S-QA-007, S-QA-013, S-DEVOPS-021, S-DEVOPS-031.
- **S-ARCH-044** Diff checks (closes OD-GEN-9 for ARCH). They run on agent PRs. A flagged diff needs a sign-off (G3, S-ARCH-053), and a blocked one can't merge.
  - **ADR:** on an accepted ADR, a change to `decision`, `drivers` or the chosen option; an exception added; a status change outside S-ARCH-011. Deleting the file is blocked.
  - **Interface version:**
    - blocked: a breaking change without a new major (editable drafts are exempt, S-ARCH-022), a public version removed before its sunset, or any version removed while a consumer remains;
    - flagged: a validation constraint, error code or description removed or loosened even when compatible, and a `compatibility_policy` change.
  - **Component:**
    - flagged: `allowed_dependencies` or `data` widened, or a `testability` item moved away from `provided`;
    - blocked: a `name` change, and any change outside `code_paths` in an `arch-upkeep` commit;
    - `code_paths` are compared as a net set of mapped files: re-pointing after a move isn't flagged, but a file whose component changes or becomes unmapped is.
  - **QAS:** a `measure` loosened or removed; `addressed_by` set to `gap`; a retirement without `replaced_by`.
  - **Conformance rules:** a rule removed or loosened.
  - **Overview:** a cited active ADR or QAS ID removed.
  - **Checklist (staff repo):** a skill PR that removes or rewords an AR item.

  The Architect and `arch-upkeep` stay at stage 1 until all the product-side checks exist (G3). *Depends on:* S-GEN-020, S-GEN-051, S-ARCH-011, S-ARCH-053.
- **S-ARCH-045** ARCH check scripts. They ship from staff-engineering `checks/`, and run as required checks from a source the PR can't change (OD-SEC-2). They don't depend on switches and fail closed, as in S-BA-051. Who they apply to:
  - **every PR, human or agent:** the schema, ID, lifecycle, trace, compatibility and conformance checks;
  - **agent commits:** the source-ref and owner-field checks;
  - **gate PRs:** the gate check (S-ARCH-019);
  - **agent PRs:** the diff checks (S-ARCH-044).

  The ADR, interface, conformance and overview diff checks also run on human PRs, as reports. *Depends on:* S-BA-051, S-ARCH-019, S-ARCH-044, OD-SEC-2.
- **S-ARCH-053** Sign-off form. A sign-off is an operator comment on the PR that cites the flag ID the check printed, which is derived from (check, file, element). The owner-field logic verifies it (S-ARCH-020). A new push that changes the flagged element voids the sign-off. *Depends on:* S-BA-015, S-ARCH-020.
- **S-ARCH-054** Spec-change event. When a PR that changes an interface version merges, the compatibility check's post-merge run fires. It is an event workflow with no `run` job, so no PR code runs in it, and it is separate from the `interface_source` generation (S-DEVOPS-017):
  - it publishes `{if_id, versions, compat_class, pr}` as a CI artifact;
  - the router starts the QA workflow from it, as a check event (S-ARCH-034 classes; S-DEVOPS-017, -031).

  QA consumes it under S-QA-013 and S-QA-023. *Depends on:* S-ARCH-022, S-QA-013, S-QA-023, S-DEVOPS-017, S-DEVOPS-031.

### Architecture checklist (reviewer/architecture)

- **S-ARCH-031** The checklist (closes the ARCH part of OD-GEN-8). Item IDs are stable and protected by the checklist diff check (S-ARCH-044).

  | ID | Item | Finds |
  | --- | --- | --- |
  | AR-1 | ADR consistency | Conflicts with accepted ADRs and their constraints; a supersession that isn't declared |
  | AR-2 | Quality coverage | A driver quality REQ with no QAS; a `measure` looser than the target; claims without a measure |
  | AR-3 | Options | Fewer than 2 real options; one-sided trade-offs; a recommendation that doesn't follow from the drivers; a human-owned field set |
  | AR-4 | Boundaries and coupling | Unclear responsibilities, cycles, shared stores, dependencies outside `allowed_dependencies` |
  | AR-5 | Interfaces | A wrong compatibility class, a missing major bump or deprecation plan, an unlisted consumer, a missing unit or security field (S-ARCH-022, -023) |
  | AR-6 | Security and data | A `permissions` entry of a driver REQ with no enforcement point. A design that needs production data in tests (S-DATA-004), prevents test-only credentials (S-SEC-005), or adds a third-party service that fails the residency rule (S-DATA-006) |
  | AR-7 | Operability and cost | No failure modes, no deployment impact for DevOps, an uncited cost |
  | AR-8 | Testability | The items in S-ARCH-032 |
  | AR-9 | Reversibility | A one-way option without a reason or evidence; no rollback or migration path |
  | AR-10 | Sources | Uncited claims, assumptions presented as facts, stale citations (S-ARCH-014) |

  *Depends on:* S-GEN-015, S-SEC-005, S-DATA-004, S-DATA-006, S-ARCH-014, S-ARCH-022, S-ARCH-023, S-ARCH-032, OD-GEN-8.
- **S-ARCH-032** AR-8 testability items (closes the ARCH part of OD-TESTAB-1, and delivers ARCH's share of S-TESTAB-009):
  - every new or changed interface has a machine-readable spec (S-TESTAB-006);
  - every component's `testability` field covers S-ARCH-025, and each `n/a` gives a reason;
  - every QAS names a verification method and an owner that can run it in a test environment or through monitoring. A load, soak or capacity `measure` that isn't `monitor` with owner DEVOPS is a finding, and so is a `monitor` QAS whose `where` is set to an invalid value (S-ARCH-009);
  - asynchronous flows say how completion is observed (S-TESTAB-007).

  *Depends on:* S-TESTAB-006, S-TESTAB-007, S-TESTAB-009, S-ARCH-009, S-ARCH-025.
- **S-ARCH-033** Output and evaluation:
  - **Output:** one advisory comment per run, never an edit. The digest lists a pointer to it. It holds:
    - a verdict: ready, ready with questions, or not ready;
    - at most 7 findings, as in S-BA-032, ordered by severity. Each has a finding ID derived from (AR ID, location, cited ADR or IF ID), an AR ID, the location, a rewording and the cited IDs;
    - questions in the S-BA-014 form;
    - a machine-readable block with the reviewed SHA and the finding IDs and their classifications.

    Until the checklist qualifies, the comment is headed "not yet qualified".
  - **Evaluation:** the default `reviewer/<other type>` row of S-GEN-045, unchanged, with seeds covering every AR item. The caps are as in S-GEN-057.
  - **Escaped defects:** ADRs superseded as `wrong` become seeding inputs, as in S-BA-033. The escaped ADR itself never becomes a hidden or promotion task (S-GEN-028).

  *Depends on:* S-GEN-028, S-GEN-045, S-GEN-057, S-GEN-062, S-BA-014, S-BA-032, S-BA-033.

### Interfaces with other roles

- **S-ARCH-047** What ARCH provides:

  | Artifact | Schema | Consumers |
  | --- | --- | --- |
  | ADR and the chosen option's constraints | S-ARCH-006 | DEV (implements; code checklist item), DEVOPS, QA, `reviewer/architecture` |
  | Interface versions and specs | S-ARCH-008 | DEV (implements; generated clients), QA (contract tests, mocks, characterization of `as-built`), DEVOPS |
  | Component | S-ARCH-007 | DEV (`code_paths`, allowed dependencies, testability), DEVOPS (`deployment`), QA (stable names) |
  | Quality scenario | S-ARCH-009 | QA (`verification: test`), DEVOPS (`verification: monitor`) |
  | Spec-change event | S-ARCH-054 | QA (S-QA-013, S-QA-023) |
  | Drift report; ARCH trace matrix with design status | CI artifacts (S-ARCH-027, -030) | Every role; developer triggers (S-DEV-007) |
  | Requirement-defect items | S-BA-048 | BA |
  | Drift work tickets | Draft tracker tickets citing ADR-n/C-k or IF-n@x.y.z | DEV (S-DEV-006) |

  *Depends on:* S-BA-048, S-ARCH-006, S-ARCH-007, S-ARCH-008, S-ARCH-009, S-ARCH-027, S-ARCH-030, S-ARCH-054, S-DEV-006, S-DEV-007, S-QA-013, S-QA-023, S-DEVOPS-026, S-DEVOPS-040.

### Caps, records and prerequisites

- **S-ARCH-039** Per-run caps (closes OD-GEN-4 for ARCH):
  - **Architect:** $4 per run, 30 min *(starting value)*. One run covers one design need, one area's drift batch, or one component or interface of an `arch:bootstrap`. A bootstrap therefore runs as several runs.
  - **`arch-upkeep`:** $2 per run, 15 min *(starting value)*.
  - **`reviewer/architecture`:** as in S-GEN-057.

  Eval worst cases under S-GEN-070:
  - Architect: 20 × 5 × $4 = $400, plus $20 for the judge, so the skill-PR budget is $252.
  - `arch-upkeep`: 20 × 5 × $2 = $200, so the budget is $120.
  - `reviewer/architecture`: 30 × 5 × $1 = $150, with no judge, so the budget is $90.

  *Depends on:* S-GEN-056, S-GEN-057, S-GEN-059, S-GEN-070.
- **S-ARCH-040** ARCH run records add these fields inside `role` (S-GEN-029): `req_ids`, `adr_ids`, `cmp_ids`, `if_versions`, `qas_ids`, `options_count`, `recommended_option`, `compat_class`, `defect_items_raised`, `drift_ids`. *Depends on:* S-GEN-029.
- **S-ARCH-043** Testability prerequisites (closes OD-TESTAB-6 for ARCH):
  - **Architect:** none beyond the manifest (S-TESTAB-001). It produces S-TESTAB-005 and -006 sources. In an area without specs, `arch:bootstrap` comes first.
  - **`arch-upkeep`:** a component map with stable names for the area (S-TESTAB-005).
  - **`reviewer/architecture`:** the area's ADRs and specs (S-TESTAB-006). Without them, AR-1 and AR-5 check only within the PR, and the output says so.

  *Depends on:* S-TESTAB-001, S-TESTAB-005, S-TESTAB-006.

### Eval rows

- **S-ARCH-049** Eval rows (closes OD-GEN-3 for ARCH). Scores are pooled (S-GEN-035). Hidden and promotion tasks are scored by script (S-GEN-041).

  | Agent | Golden tasks | Promotion set minimum | Mode | Oracle | Primary metrics | Stage 1→2 threshold | Hard limits | LLM judge |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | Architect | 20 design bundles *(starting value)*: ready REQs with 1–3 quality REQs, accepted ADRs, specs and components. 16 are seeded with 0–2 constraint conflicts, 0–1 requirement defect and 1 unknown figure each. 4 are clean | 10 bundles *(starting value)*: 8 seeded with holdout seeds, 2 held-out clean | Artifact-seeded | A script matches outputs to spec entries by key (mapping below) | Quality-driver coverage, conflict recall, defect recall, defect precision, interface coverage, unnecessary-breaking rate, invented-fact rate | Coverage ≥80%, conflict recall ≥70%, defect recall ≥60%, defect precision ≥50%, interface coverage ≥80%, unnecessary breaking ≤10%, invented facts ≤5% *(starting value)* | Schema-valid output; no write outside its scope; no human-owned field set; every ADR has 2–4 options | Yes, for trade-off quality. Reported, not gating |
  | `arch-upkeep` | 20 scripted change PRs *(starting value)*: 10 moves or renames, 6 adding modules, 4 with no architecture impact | 10 *(starting value)*: 5 moves, 3 new modules, 2 clean | Diff-seeded | A script compares each file's resulting component with the spec. The S-GEN-067 check fails on stale `code_paths` and passes on the corrected ones | Mapping accuracy, clean no-op rate | Mapping accuracy ≥95% on moves and ≥80% on new modules; clean no-op ≥90% *(starting value)* | Schema-valid output; no field outside `code_paths` changed; no `name` changed | No |
  | `reviewer/architecture` | As in S-GEN-045, the default row (S-ARCH-033) | | | | | | | |

  **Catalogue.** The 8 seeded Architect promotion bundles are bug tasks. They add 24 entries to the holdout catalogue (S-GEN-039). The `arch-upkeep` tasks are scripted non-bug tasks (S-GEN-038) and add none.

  **Architect spec mapping.** The bundle supplies the REQ IDs. Agent-assigned ADR and IF IDs never appear in keys. Keys:
  - quality drivers: (REQ ID, attribute, target);
  - conflicts: the constraint ID, matched to `conflicts[].constraint_id`;
  - requirement defects: (REQ or AC ID, defect kind);
  - interface needs: (AC `target_id`, expected compatibility class);
  - unknown figures: (entity, attribute).

  Formulas:
  - **Quality-driver coverage:** planted quality REQs answered by a QAS that cites the REQ with a `measure` equal to the target or stricter / planted quality REQs.
  - **Conflict recall:** planted conflicts matched in `conflicts[]` / planted conflicts.
  - **Defect recall:** planted defects matched by a defect item with the right target and kind / planted defects.
  - **Defect precision:** defect items that match a planted defect / defect items raised.
  - **Interface coverage:** expected interface elements defined in `spec_versions[]` / expected elements.
  - **Unnecessary-breaking rate:** spec versions classed as breaking (S-ARCH-022) where the spec marks a compatible design as possible / spec versions produced.
  - **Invented-fact rate:** planted unknown figures stated with a value and no assumption / planted unknown figures.
  - **Mapping accuracy:** files in scope whose resulting component matches the spec / files in scope.
  - **Clean no-op rate:** clean tasks with no patch / clean tasks.

  *Depends on:* S-GEN-035, S-GEN-036, S-GEN-037, S-GEN-038, S-GEN-039, S-GEN-040, S-GEN-041, S-GEN-042, S-GEN-044, S-GEN-045, S-GEN-067, S-ARCH-022, S-ARCH-033, S-ARCH-037.

### Stage rules

- **S-ARCH-050** Stage-2 and stage-3 rules (closes OD-GEN-5 for ARCH). The role demotion triggers add to those in S-GEN-052.

  | Agent | Stage-2 quality metric that must hold for stage 3 | Role demotion trigger → stage 1 | Stage 3 |
  | --- | --- | --- | --- |
  | Architect | None, because it has no stage 3 | ADR rework rate >30% *(starting value)*, or live defect-item precision <50% *(starting value)* (S-ARCH-051) | None. Every ADR, spec and boundary change is a human decision, so the Architect stops at stage 2 |
  | `arch-upkeep` | Mapping correction rate ≤5% *(starting value)* | Mapping correction rate >15% *(starting value)* | **Change class:** PRs that only re-point the `code_paths` of active components for files that existed before. Every such file (with rename detection) keeps its component, no file becomes unmapped, and no new file is assigned. PRs that assign new files or touch the overview are stage-2 PRs. **Guard:** the net-set component diff check (S-ARCH-044). **Critical miss:** a merged lane PR that changed a file's component, assigned a new file, or left a file unmapped |

  `reviewer/architecture` is advisory at every stage (S-GEN-045, S-GEN-062). *Depends on:* S-GEN-045, S-GEN-052, S-GEN-053, S-GEN-062, S-ARCH-044, S-ARCH-051.

### Role metrics and outcome records

- **S-ARCH-051** Role metrics (closes OD-GEN-7 for ARCH, with S-ARCH-052). Windowed metrics count only items whose window has closed. Windows are *(starting value)*.

  | Metric | Formula |
  | --- | --- |
  | ADR rework rate | Architect-drafted ADRs with `chosen` = `recommended` that were superseded as `wrong` within 60 days of acceptance / such ADRs accepted at least 60 days ago, last 10 |
  | Live defect-item precision | Architect requirement-defect items with `verdict:confirmed` / those with a verdict, last 20 |
  | Recommended-option rate | Accepted Architect ADRs with `chosen` = `recommended` / accepted Architect ADRs, last 10. Reported, no threshold |
  | Mapping correction rate | Merged `arch-upkeep` PRs with a human commit to `code_paths`, or whose mapped files a human re-mapped within 14 days / `arch-upkeep` PRs merged at least 14 days ago, last 20 |
  | Quality-answer coverage | Ready quality REQs past the grace period with an accepted QAS / ready quality REQs past the grace period, nightly snapshot |
  | Drift backlog | Open drift questions, and the age of the oldest, nightly snapshot. A load signal |
  | Breaking-change sign-offs | Breaking interface versions merged, per 30 days. A load signal |
  | Interface test coverage | Active IF operations cited by ≥1 test / active IF operations, nightly snapshot. Reported, from test citations (S-QA-007) |

  *Depends on:* S-GEN-032, S-GEN-071, S-ARCH-052, S-QA-007.
- **S-ARCH-052** Outcome records. A nightly ARCH check derives per-artifact outcomes from the product repo and the tracker. It emits them through the recorder as linked `check_outcome` records (S-GEN-031). Their `drafting_run_id` comes from `Staff-Run-Id`, read per merged PR (S-GEN-029). The `role` fields are:
  - `adr_accepted`, `adr_recommended_chosen` and `adr_superseded_wrong_60d`;
  - `defect_items_confirmed` and `defect_items_rejected`, from operator verdicts read through the tracker (S-DEVOPS-021);
  - `code_paths_human_edited_14d`.

  Drift and trace findings (S-ARCH-027, -030) have no drafting run, so they are unlinked `check_outcome` records (S-GEN-031). The ops stage job computes S-ARCH-051 from these records.

  `artifact_id` per record type, which keeps `finding_key` stable (S-GEN-031):

  | Record | `artifact_id` |
  | --- | --- |
  | ADR fields (linked) | The ADR ID |
  | Defect-item fields (linked) | The defect item ref |
  | Mapping fields (linked) | The `arch-upkeep` PR number |
  | Decision drift | ADR-n/C-k plus the path |
  | Implementation drift; unspecified elements | IF-n@x.y.z (or IF-n) plus the element name |
  | Unmapped code | The path |
  | Expired exception | The constraint ID |
  | Elements pending implementation | IF-n@x.y.z |
  | Component whose `code_paths` match nothing | The CMP ID |
  | Consumer still on a deprecated version | IF-n@x.y.z plus the consumer's CMP ID |
  | Boundary violation (`allowed_dependencies` or `data` ownership) | The CMP ID plus the path |
  | Trace finding (S-ARCH-030) | The citing artifact's ID plus the cited ID |
  | Unanswered quality REQ (S-ARCH-016) | The REQ ID |

  *Depends on:* S-GEN-026, S-GEN-029, S-GEN-031, S-GEN-071, S-ARCH-040, S-ARCH-051, S-DEVOPS-021, S-DEVOPS-031.

### Open dependencies closed by this doc

| Open dependency | Closed by |
| --- | --- |
| OD-GEN-1 | S-ARCH-034 |
| OD-GEN-2 | S-ARCH-013, S-ARCH-035 |
| OD-GEN-3 | S-ARCH-049 |
| OD-GEN-4 | S-ARCH-039 |
| OD-GEN-5 | S-ARCH-050 |
| OD-GEN-6, OD-SEC-1 | S-ARCH-037 |
| OD-GEN-7 | S-ARCH-051, S-ARCH-052 |
| OD-GEN-8 (ARCH part) | S-ARCH-031 to S-ARCH-033 |
| OD-GEN-9 | S-ARCH-044, S-ARCH-045, S-ARCH-053 |
| OD-TESTAB-1 (ARCH part) | S-ARCH-032 |
| OD-TESTAB-2 | S-ARCH-025 |
| OD-TESTAB-6 | S-ARCH-043 |
| OD-BA-3 (architect part) | S-ARCH-015 (ready ACs only), S-ARCH-017 (requirement-defect items), S-ARCH-006 and S-ARCH-029 (ADRs cite REQ IDs) |

No OD-DATA item is addressed to ARCH: OD-DATA-1 is DevOps, and OD-DATA-2 is BA and QA. S-ARCH-038 keeps ARCH agents off production-derived sources. Not addressed to ARCH: OD-GEN-10, OD-SEC-2, OD-TESTAB-3 to -5, OD-BA-1, -2, -4, -5 and -6.

## Assumptions

Item 1 lists the values the human accepted as starting values (`docs/decisions.md`, 2026-11-20). Item 2 applies a human decision. Items 3–13 are designer defaults. No *(proposed)* item is open.

1. **Accepted values** *(starting value, `docs/decisions.md`, 2026-11-20, roles/architect rounds 1–2)*:
   - ADRs: 2–4 options each, at most 3 per design PR (S-ARCH-006, -018);
   - overview: 3,000 tokens, in sections of at most 2,000 characters (S-ARCH-010);
   - quality-answer grace period: 14 days (S-ARCH-016);
   - public deprecation window: at least 90 days (S-ARCH-023);
   - drift: at most 7 questions per area per night, escalation after 7 days, exceptions expiring within 90 days (S-ARCH-028);
   - overview updates batched weekly (S-ARCH-034);
   - caps: Architect $4 / 30 min, `arch-upkeep` $2 / 15 min (S-ARCH-039);
   - Architect eval: 20 golden bundles (16 seeded, 4 clean), 10 promotion bundles (8 seeded, 2 clean), and the seven thresholds in S-ARCH-049;
   - `arch-upkeep` eval: 20 golden and 10 promotion tasks with the mixes and thresholds in S-ARCH-049;
   - ADR rework rate: 60-day window, last 10, demotion above 30%. Live defect-item precision: last 20, demotion below 50%;
   - mapping correction rate: 14-day window, last 20, ≤5% to hold for stage 3, >15% to demote. Recommended-option rate: last 10.
2. **Context budget (`docs/decisions.md`, 2026-11-20):** the 15k budget stays. The always-loaded part is everything before the on-demand header, measured at characters / 3.2. The cap is computed per S-GEN-009 (S-ARCH-048). Figures as of the last measurement. The release gate re-measures them (S-GEN-009):
   - **shared/, always-loaded part only:** 13,257 characters, about 4.14k tokens. The cap is about 34,745 characters.
   - **Working agents:** the always-loaded part is 24,057 characters. With shared/, about 11.66k tokens.
   - **`reviewer/architecture`:** the reviewer pack (the part above plus S-ARCH-031 to -033) is 27,276 characters. With shared/, about 12.67k tokens, within 15k.

   Human-owned fields, path scope and triggers stay always loaded. Field lists, checks, the checklist, the evals and the closing sections are on demand. ARCH agents also load the field definitions as schemas (S-ARCH-036).
3. **Conformance as scripts plus the developer's code checklist (S-ARCH-002):** this is revisited if drift reports show misses on `check: review` constraints.
4. **Default reviewer row and caps (S-ARCH-033):** no GEN-owned row changes.
5. **Spec location (S-ARCH-013):** specs live under `architecture/<area>/interfaces/`. Code-first stacks commit the spec there and compare it with the generated one (S-ARCH-026).
6. **Branch prefixes (S-ARCH-003):** product CI can't read the outcome store (S-GEN-026), so the lint checks only the prefix, not the run record's `agent`.
7. **Interface needs through `arch:design` (S-ARCH-015):** this needs no change to S-BA-007. If BA later adds a target kind to the AC key, the trace check could detect interface needs by script.
8. **ADRs merge only as accepted or rejected (S-ARCH-011):** rejected ADRs keep the options considered.
9. **Options carry their own constraints (S-ARCH-006):** so acceptance only selects an option, and the reviewed content doesn't change after the human answers.
10. **Implemented, per element (S-ARCH-021):** each element of an approved version counts as implemented once a merged product PR that declares the version has built it and passed the conformance check. A version counts as implemented once no element is missing. Elements not yet built are pending implementation, not drift, so interfaces can be built in small PRs.
11. **Cross-area work (S-ARCH-013):** uses the ordinary area directory `architecture/system/`, which `areas.yml` maps like any path. No new product-contract key is needed.
12. **Description changes are breaking by default (S-ARCH-022):** this catches unit and meaning changes that format tools can't see. The cost is a sign-off on typo fixes.
13. **Architect judge:** reported, not gating, until it is calibrated (S-GEN-042).

## Open dependencies

- **OD-ARCH-1 (developer): closed by the developer strategy**, as mapped in its closure table:
  - implement against approved specs and accepted ADRs, and never edit `architecture/**` (S-ARCH-021): S-DEV-005;
  - ask for design with a comment that the human can turn into `arch:design` (S-ARCH-015): S-DEV-008;
  - developer triggers wait while the ARCH trace matrix shows design `pending` (S-ARCH-030): S-DEV-007;
  - product PRs declare the versions they implement in `implements` (S-ARCH-021): S-DEV-009;
  - the code checklist carries an item for `check: review` constraints, citing their IDs (S-ARCH-026): S-DEV-009, and CC-2 in S-DEV-031;
  - a trigger for drift work tickets (S-ARCH-028): S-DEV-006, S-DEV-017;
  - an implemented-interface source where the stack allows one (S-ARCH-026): S-DEV-012;
  - the S-ARCH-025 items (with OD-TESTAB-3): S-DEV-013.
- **OD-ARCH-2 (test engineer): closed by the test engineer strategy**, as mapped in its closure table:
  - tests cite IF operation names in a form the ARCH trace check reads (S-ARCH-029): S-QA-007;
  - contract tests run only against implemented elements (S-ARCH-021). Elements pending implementation may feed mocks. Both come from approved specs and are updated on the spec-change event (S-ARCH-054): S-QA-023;
  - tests of a deprecated version are kept until its sunset (S-ARCH-023): S-QA-023, S-QA-040;
  - `as-built` versions get characterization handling (S-ARCH-008, OD-TESTAB-5): S-QA-006, S-QA-023;
  - QAS with `verification: test` get quality tests, where the measure can be decided in a functional environment: S-QA-023. Load, soak and capacity QAS are `monitor` with owner DEVOPS (S-ARCH-009, AR-8; `docs/decisions.md`, 2026-11-20);
  - contract verification results feed S-ARCH-026 where no generated spec exists: S-QA-023.
- **OD-ARCH-3 (DevOps): closed by the DevOps strategy**, as mapped in its closure table:
  - tracker webhook routing with the S-ARCH-034 event classes and the operator actor check: S-DEVOPS-017;
  - read-only tracker access for product CI, for the owner-field and sign-off checks, the `arch:design` label events and S-ARCH-052: S-DEVOPS-021;
  - the ARCH checks as required checks under OD-SEC-2: S-DEVOPS-020. The nightly jobs and the S-ARCH-054 dispatch: S-DEVOPS-017, S-DEVOPS-031;
  - environments built from component `deployment` fields that expose the S-ARCH-025 seams (with OD-TESTAB-4): S-DEVOPS-026, S-DEVOPS-041;
  - monitors for QAS with `verification: monitor`: S-DEVOPS-040;
  - the `read` variant for ARCH agents: S-DEVOPS-024.
- **OD-ARCH-4 (general strategy): closed by S-GEN-031.** S-GEN-031 now defines linked and unlinked `check_outcome` records. ARCH drift and trace findings are unlinked (S-ARCH-027, -052).

## Open questions

- [ ] Should the Architect's trade-off judge ever gate promotion, once it is calibrated? It would measure what matters most to the human, at the cost of a 30-item calibration set and the judge spend.
- [x] Should GEN make `agent/<agent>/*` branch prefixes the convention for every plugin that hosts several agents (S-ARCH-003)? Answered in practice: every role now uses per-agent prefixes (S-ARCH-003, S-BA-037, S-DEVOPS-003, S-QA-014).
- [ ] When would a separate conformance agent be worth its cost? This is revisited after the developer's code-checklist results.
