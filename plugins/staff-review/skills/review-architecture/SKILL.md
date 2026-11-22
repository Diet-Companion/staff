---
name: review-architecture
description: Checklist for reviewer/architecture, the architecture artifact type of the shared reviewer. Covers items AR-1 to AR-10, the AR-8 testability items, the ADR, component, interface and QAS model it checks against, and the compatibility rules. The harness preloads it when the target is a PR touching architecture/**.
---

# Architecture checklist (reviewer/architecture)

Source: `docs/strategy/roles/architect.md`, S-ARCH-031 to S-ARCH-033. ARCH owns this checklist (S-ARCH-002). Output: `schemas/review-output.schema.json` with `artifact_type: architecture`. Item IDs are stable, and the checklist diff check protects them (S-ARCH-044).

## Run (S-ARCH-034 to S-ARCH-037, S-GEN-057)

- **Starts when** a PR touching `architecture/**` becomes ready for review or has its review re-requested.
- **Write stage:** one comment on the PR and the label `arch:not-ready`. No paths.
- **Caps:** $1 and 10 min *(starting value)*.

## What you check against (S-ARCH-004 to S-ARCH-013, S-ARCH-020)

- **Truth:** merged accepted ADRs, active components, accepted QAS, and approved or deprecated interface versions, each for its own version. Everything else is a candidate (S-ARCH-004).
- **IDs and paths:**
  - `ADR-n` and its constraints `ADR-n/C-k`: `architecture/<area>/adr/`;
  - `CMP-n` (an immutable `name`): `architecture/<area>/components/`;
  - `IF-n@x.y.z`, with one spec per version: `architecture/<area>/interfaces/IF-n/`;
  - `QAS-n`: `architecture/<area>/quality/`;
  - the overview: `architecture/overview.md`;
  - cross-area artifacts: `architecture/system/` (S-ARCH-005, S-ARCH-013).
- **ADR** (S-ARCH-006): `drivers`, with quality REQs first; cited `context`; and 2 to 4 `options`, "keep the current design" among them wherever one exists. Each option has satisfies, pros, cons, cost, `reversibility` (two-way, costly or one-way), risks, `constraints` {id, statement, kind, check: rule ref | review}, affects, consequences and cites. It also has `recommended` with a reason. Only the chosen option's constraints apply.
- **Component** (S-ARCH-007): responsibilities, `provides`, `consumes`, `allowed_dependencies`, `code_paths`, `data` (a store is shared only if an ADR allows it), `deployment`, `testability[]`.
- **Interface** (S-ARCH-008): kind, owner, `compatibility_policy`, `consumers`, and `versions[]`. Each element of a spec carries a structured unit where it has one, and a security requirement.
- **QAS** (S-ARCH-009): `measure` with a unit, equal to the REQ target or stricter; `addressed_by`; `verification` {method: test | monitor | analysis, owner: QA | DEVOPS, where}. A load, soak or capacity measure is `monitor` with owner DEVOPS.
- **Change in meaning gets a new ID** (S-ARCH-012). An accepted ADR's decision, drivers and chosen option never change: a new ADR supersedes it. A component is never renamed. A breaking interface change is a new major version.
- **Human-owned** (S-ARCH-020): ADR `decision`, `superseded_reason`, `deprecated_reason`; `exceptions[].accepted_by`; `gap_accepted_by`; `compatibility_policy`; `sunset` earlier than allowed; `external_retired_by`; `provenance_confirmed_by`; `review_dispositions` accepted and rejected; `review_waiver`; sign-offs. An agent PR that sets one is an AR-3 blocker.
- **No invented facts** (S-ARCH-014): a load figure, cost or capacity that no source states is an open assumption.

## Compatibility (S-ARCH-022, S-ARCH-023)

A diff to an existing element is **breaking** if it:
- removes or renames an operation, field, enum value, event, error code or stable name;
- makes an optional input required, or narrows the inputs accepted;
- changes a type, or adds an output value that existing consumers can't parse;
- changes a description, unit or security requirement, unless the human signs it off as compatible.

A version that is still an editable draft is exempt (S-ARCH-021). A breaking change only arrives as a new major version, with the previous one deprecated. A public version gets a `sunset` at least 90 days out *(starting value)*. A version is never removed while a consumer is still on it. Read the compatibility check output first, and judge what it can't see.

## Checklist (S-ARCH-031)

| ID | Item | Finds |
| --- | --- | --- |
| AR-1 | ADR consistency | Conflicts with accepted ADRs and their constraints; a supersession that isn't declared |
| AR-2 | Quality coverage | A driver quality REQ with no QAS; a `measure` looser than the target; claims without a measure |
| AR-3 | Options | Fewer than 2 real options; one-sided trade-offs; a recommendation that doesn't follow from the drivers; a human-owned field set |
| AR-4 | Boundaries and coupling | Unclear responsibilities, cycles, shared stores, dependencies outside `allowed_dependencies` |
| AR-5 | Interfaces | A wrong compatibility class, a missing major bump or deprecation plan, an unlisted consumer, a missing unit or security field (S-ARCH-022, -023) |
| AR-6 | Security and data | A `permissions` entry of a driver REQ with no enforcement point; a design that needs production data in tests (S-DATA-004), prevents test-only credentials (S-SEC-005), or adds a third-party service that fails residency (S-DATA-006) |
| AR-7 | Operability and cost | No failure modes; no deployment impact for DevOps; an uncited cost |
| AR-8 | Testability | The items below (S-ARCH-032) |
| AR-9 | Reversibility | A one-way option without a reason or evidence; no rollback or migration path |
| AR-10 | Sources | Uncited claims, assumptions presented as facts, stale citations (S-ARCH-014) |

**AR-8 testability items** (S-ARCH-032, ARCH's share of S-TESTAB-009):
- every new or changed interface has a machine-readable spec (S-TESTAB-006);
- every component's `testability` field covers S-ARCH-025 (stable names, `run_id` correlation and readiness, seams for flags, clock and external services, seeding and cleanup), and each `n/a` gives a reason;
- every QAS names a verification method and an owner that can run it in a test environment or through monitoring. A load, soak or capacity `measure` that isn't `monitor` with owner DEVOPS is a finding. So is a `monitor` QAS with an invalid `where` (S-ARCH-009);
- asynchronous flows say how completion is observed (S-TESTAB-007).

## Output specifics (S-ARCH-033)

- **Findings** carry `rewording`: the suggested rewording of the field or option.
- **Finding ID:** `AR-n|<location key>|<primary cited ID>`. The location key is the artifact ID plus field path, for example `ADR-004#options[b].constraints`. The primary cited ID is the ADR or IF ID the finding rests on, for example `ADR-002/C-1` or `IF-003@2.0.0`. Without one, use the S-ID of the broken rule.
- **`classification`:** `conflicts` for an AR-1 conflict with an accepted ADR or one of its constraints. The gate needs a `review_dispositions` entry for each (S-ARCH-019 item 6). Use `issue` for everything else. An undisclosed conflict is a blocker.
- **Re-review:** a design PR needs a new review when its fields change, ignoring `decision`, `status`, answer entries in `sources` and the `review_*` fields. An option added after the human's answer always needs one (S-ARCH-019 item 6).
- **Questions:** S-BA-014 form, with `blocks` naming the ADR or artifact.

## Prerequisites and retrieval (S-ARCH-036, S-ARCH-043, S-ARCH-048)

- **Prerequisite:** the area's ADRs and specs (S-TESTAB-006). Without them, AR-1 and AR-5 check only within the PR, and `decision_summary` says so.
- **Always:** this checklist and `architecture/overview.md`.
- **On demand:** the cited ADRs, components, specs and REQs, and the compatibility check output.
