---
name: architecture-reference
description: On-demand reference for ARCH agents, not preloaded. Covers the artifact fields (ADR, component, interface, QAS, overview), the gate, compatibility, conformance, trace and diff checks, the sign-off form and the arch-upkeep lane class. Retrieve the sections your trigger needs, per the table at the top.
---

# Architecture on-demand reference (S-ARCH-006 to -010, -019, -022, -026, -027, -029, -030, -044, -050, -053)

Source: `docs/strategy/roles/architect.md`, section "On-demand reference" (S-ARCH-048). The read-stage schemas carry the same fields and are what the harness checks.

## What to retrieve, per trigger (S-ARCH-048)

| Agent and trigger | Sections |
| --- | --- |
| Architect: design need or `arch:bootstrap` | Fields; Gate; Compatibility; Conformance; Diff checks |
| Architect: human answer on a design PR | Gate item 6; Sign-off |
| Architect: drift batch | Conformance |
| `arch-upkeep`: nightly run | Fields: component and overview; Diff checks; Lane class |

## Fields

**ADR (S-ARCH-006).** `id`, `title`, `status`, `area`, `date`, `design_for` (ticket refs); `drivers` (REQ IDs with quality REQs first, QAS IDs, or for a technical decision with no requirement an operator comment ref); `context` (cited prose); `options[]` 2 to 4, each `{key, summary, satisfies[], pros, cons, cost, reversibility, risks, constraints[], affects, consequences, cites}`; each constraint `{id: ADR-n/C-k, statement, kind: dependency | interface | technology | data | deployment | other, check: <rule ref> | review}`; `recommended` (key and reason); `decision` (human-owned; only the chosen option's constraints apply); `exceptions[] {constraint, paths, reason, accepted_by, expires}`; `supersedes`, `superseded_by`, `superseded_reason: wrong | context-changed | refined`, `deprecated_reason`; `review_dispositions`, `review_waiver` (S-BA-006 semantics); `sources`, `assumptions`, `questions`, `revision` (S-BA-006 form). Prose fields at most 2,000 characters.

**Component (S-ARCH-007).** `id`, `name` (immutable), `status`, `area`, `design_for`, `responsibilities`; `provides`, `consumes` (IF IDs); `allowed_dependencies` (CMP and IF IDs); `code_paths` (path globs); `data` (the stores it owns; a store is shared only if an ADR allows it); `deployment {unit, state: stateless | stateful, runtime_dependencies[]}`; `testability[] {item, state, reason, gap_accepted_by}`; `provenance: designed | as-built`, `provenance_confirmed_by`; `cites` (ADR IDs); `revision`.

**Interface (S-ARCH-008).** `id`, `name`, `kind: api | event | data`, `owner` (CMP ID), `design_for`; `compatibility_policy: public | internal`; `consumers` (CMP IDs or `external`); `cites` (REQ and ADR IDs); `versions[] {version, status, spec (path), consumers (optional, CMP IDs on this version), sunset (public only), replacement, provenance, provenance_confirmed_by, external_retired_by}`; `revision`. An `as-built` version records observed behaviour; QA treats it as characterization until `provenance_confirmed_by` is set. Checks work per version entry.

**QAS (S-ARCH-009).** `id`, `status`, `req`; `attribute`, `stimulus`, `environment`, `artifact` (CMP or IF ID), `response`; `measure` (with a unit, equal to the REQ target or stricter); `addressed_by` (ADR or CMP IDs, or `gap` with `gap_reason` and `gap_accepted_by`); `verification {method: test | monitor | analysis, owner: QA | DEVOPS, where: pre-production | production | both}`; `revision`.

**Overview (S-ARCH-010).** Prose: system context, main flows, pointers to IDs. Named sections of at most 2,000 characters each, patched per section, at most 3,000 tokens in total *(starting value)*.

## Gate (S-ARCH-019)

Applies to any PR that sets an ADR outcome, or makes a component, interface version or QAS active, approved or accepted. Structural items:
1. schema, ID, lifecycle, source-ref, owner-field, compatibility and conformance checks pass; every flagged diff has a sign-off;
2. every decided ADR has `decision.outcome`, `decided_by` citing an operator answer, and for `accepted` a `chosen` key that names a drafted option;
3. every driver is a ready REQ, an accepted QAS, or an operator comment ref;
4. every ID in `affects`, `provides`, `consumes` and `allowed_dependencies` exists;
5. every new or changed component has a complete `testability` field;
6. a `reviewer/architecture` result exists for a commit whose fields match the head, ignoring `decision`, `status`, answer entries in `sources` and the `review_*` fields. Every AR-1 "conflicts" finding has a `review_dispositions` entry, or `review_waiver` cites an operator comment for this revision. An option added after the human's answer always needs a new review.

## Compatibility (S-ARCH-022)

A diff to an existing element is **breaking** if it removes or renames an operation, field, enum value, event, error code or stable name; makes an optional input required or narrows accepted inputs; changes a type or adds an output value existing consumers can't parse; or changes a description, unit or security requirement (unless the human signs it off as compatible). If the diff tool is unsure, it is breaking. Everything else is compatible. Editable drafts (S-ARCH-021) are exempt.

## Conformance (S-ARCH-026, S-ARCH-027)

Machine-checkable sources: component `allowed_dependencies` and `data` ownership; chosen-option constraints with `check: <rule ref>` (rules in `architecture/<area>/conformance/`, run with the stack's dependency tool); implemented versions compared with the implemented interface (generated from code, S-DEV-012, or QA's contract results where `interface_source` is `none`). `check: review` constraints go to CC-2 of the developer's code checklist.

- **Every product PR (blocking):** violations the diff adds; elements implemented differently from the declared version; elements any PR adds or changes that no approved version contains. Unbuilt spec elements never block. Rules come from the base branch.
- **Nightly drift report (non-blocking):** existing violations and implementation drift; implemented elements no approved version contains; elements pending implementation per version; unmapped code and components whose `code_paths` match nothing; expired exceptions; consumers still on each deprecated version.

## Trace (S-ARCH-029, S-ARCH-030)

REQ → QAS → ADR or IF → CMP → code paths → tests, stored on the citing side: QAS cite REQs; ADRs cite REQs and QAS; interfaces cite REQs and ADRs; components cite ADRs and IFs; code reaches components through `code_paths`; product PRs cite versions through `implements`; tests cite IF operation names. Nightly the trace check adds unanswered quality REQs, citations of versions past sunset, ARCH artifacts citing affected ACs of `changed` requirements, and active IF operations no test cites.

## Diff checks (S-ARCH-044)

Run on agent PRs. Flagged needs a sign-off; blocked can't merge.
- **ADR:** flagged: on an accepted ADR, a change to `decision`, `drivers` or the chosen option; an exception added; a status change outside S-ARCH-011. Blocked: deleting the file.
- **Interface version:** blocked: a breaking change without a new major (editable drafts exempt), a public version removed before sunset, any version removed while a consumer remains. Flagged: a validation constraint, error code or description removed or loosened even when compatible; a `compatibility_policy` change.
- **Component:** flagged: `allowed_dependencies` or `data` widened, or a `testability` item moved away from `provided`. Blocked: a `name` change, and any change outside `code_paths` in an `arch-upkeep` commit. `code_paths` compare as a net set of mapped files: re-pointing after a move isn't flagged; a file whose component changes or becomes unmapped is.
- **QAS:** a `measure` loosened or removed; `addressed_by` set to `gap`; a retirement without `replaced_by`.
- **Conformance rules:** a rule removed or loosened.
- **Overview:** a cited active ADR or QAS ID removed.

## Sign-off (S-ARCH-053)

An operator comment on the PR that cites the flag ID the check printed, derived from (check, file, element). A new push that changes the flagged element voids it.

## Lane class, `arch-upkeep` (S-ARCH-050)

Stage-3 lane PRs only re-point the `code_paths` of active components for files that existed before: every such file (with rename detection) keeps its component, no file becomes unmapped, and no new file is assigned. PRs that assign new files or touch the overview are stage-2 PRs. Critical miss: a merged lane PR that changed a file's component, assigned a new file, or left a file unmapped.
