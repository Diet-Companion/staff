---
name: review-requirements
description: Checklist for reviewer/requirements, the requirements artifact type of the shared reviewer. Covers items RC-1 to RC-9, the RC-3 testability items, contradiction detection against the rules registry, proposed changes declarations and draft test conditions. The harness preloads it when the target is a PR touching requirements/** or a ticket labelled ba:review.
---

# Requirements checklist (reviewer/requirements)

Source: `docs/strategy/roles/business-analyst.md`, S-BA-029 to S-BA-032. BA owns this checklist (S-GEN-015). Output: `schemas/review-output.schema.json` with `artifact_type: requirements`. Item IDs are stable, and the checklist diff check protects them (S-BA-046).

## Run (S-BA-034, S-BA-035, S-BA-037, S-GEN-057)

- **Starts when** a PR touching `requirements/**` becomes ready for review or has its review re-requested, or when the human applies `ba:review` to a ticket. For a ticket, set `target.kind: ticket` and `reviewed_sha: null`. A new push doesn't start a re-run.
- **Write stage:** one comment on the PR or ticket, plus the labels `ba:not-ready` and `ba:questions`. No paths.
- **Caps:** $0.50 and 5 min *(starting value)*.

## What you check against (S-BA-004 to S-BA-012, S-BA-022)

- **Truth:** merged active rules in `knowledge/rules/<area>/R-n.md`, ready requirements, and `knowledge/product-core.md` (glossary, user roles, journeys, invariants). Drafts, open PRs and `knowledge/discovered/` notes are candidates. They are never rules (S-BA-027). In `requirements/<area>/sources/INT-n.md`, only human turns are sources (S-BA-056).
- **Requirement** `requirements/<area>/REQ-n.md` (S-BA-006). Its type is epic, story (with a `parent` epic) or quality. Required: `intent` {actor, need, business_value, cites}, `scope` in and out, `acceptance_criteria`, `rules`, `changes`, `quality` (IDs, or none with a reason), `permissions` (role, may, may_not, or none with a reason), `sources`, `assumptions`, `questions`, `revision`.
- **AC** `REQ-n/AC-m` (S-BA-007): a `key` {entity, target_id, attribute} using glossary names; `given` with the data and user role; exactly one `when`; `then` with expected values; `cites`; and a `kind` of positive, negative or boundary. Every rule condition the requirement relies on has a negative or boundary AC.
- **`changes[]`** {rule, kind: add | modify | retire, proposed_statement, accepted_by}. A change counts as declared only with `accepted_by` set.
- **Human-owned:** `priority`, question and assumption statuses, `accepted_by`, the `accepted` and `rejected` dispositions, `review_waiver` (S-BA-015), and the `ready` status, which only a human-merged ready-gate PR sets (S-BA-009, S-BA-018). An agent PR that sets one is an RC-2 blocker.
- **Cite or assume:** every intent, scope item and AC cites a source, or an open assumption (S-BA-012).

## Checklist (S-BA-029)

| ID | Item | Finds |
| --- | --- | --- |
| RC-1 | Ambiguity | Vague or unquantified terms ("fast", "usually"); terms missing from the glossary |
| RC-2 | Completeness | Missing fields or ACs; missing error and empty states; missing negative or boundary ACs (S-BA-007) |
| RC-3 | Testability | The items below (S-BA-030) |
| RC-4 | Consistency | Contradictions inside the requirement, with other ready requirements, and with the registry (S-BA-031) |
| RC-5 | Impact | Undeclared rule changes; affected requirements, areas and existing checks |
| RC-6 | Non-functional | Missing or unmeasurable quality targets |
| RC-7 | Permissions | Product user roles not covered; missing deny cases |
| RC-8 | Domain compliance | Conflicts with domain clauses (S-BA-026) |
| RC-9 | Sources and assumptions | Uncited statements; assumptions presented as facts; real personal data in examples (S-DATA-004) |

**RC-3 testability items** (S-BA-030, BA's share of S-TESTAB-009):
- every expected value traces to a cited source, and every interface the requirement adds or changes has a machine-readable spec or is flagged as needing one (S-TESTAB-006);
- outcomes are observable through stable identifiers, not layout or wording (S-TESTAB-005);
- data preconditions can be created by a seed script or factory, and every named user role maps to a test account (S-TESTAB-004);
- behaviour that depends on time, flags or third parties names the condition to control (S-TESTAB-008);
- asynchronous outcomes say how completion is observed: an event, a status or a correlated log (S-TESTAB-007).

## RC-4 and RC-5: contradiction detection (S-BA-031)

1. Split the requirement into atomic statements (entity, condition, behaviour), in the rule-field form (S-BA-008).
2. Retrieve only related rules: by entity, operation, glossary term, area and changed code paths, then by search.
3. Classify each pair as consistent, extends, duplicate, contradicts or ambiguous overlap. Consistent pairs are not findings.
4. Compare with `changes`. A declared change is an RC-5 impact item: check that the affected requirements, areas and checks are named. An undeclared contradiction or extension is an RC-4 finding, with a `proposed_changes` entry.
5. Check claims about current behaviour against the latest CI results of the rule's verifying checks. Never probe a test environment.
6. An existing check that would have to change without a declaration counts as an undeclared contradiction.

Set `classification` to the pair class (`contradicts`, `extends`, `duplicate`, `ambiguous_overlap`) on RC-4 and RC-5 findings, and to `issue` on every other finding. The ready gate needs a `review_dispositions` entry for every `contradicts` finding (S-BA-017 item 5). An undeclared `contradicts` is a blocker. Known limit: implicit contradictions across several rules are often missed, so look for them.

## RC-8: domain (S-BA-026)

Use the staff-domain plugins' clauses. Cite the clause in `evidence_refs`. If the plugin was last reviewed more than 12 months ago *(starting value)*, set `domain_source_stale: true` on every RC-8 finding that relies on it. Put a suggested domain addition in `decision_summary` as an advisory note. Never write to a domain plugin.

## Output specifics (S-BA-032)

- **Findings** carry `rewording`: the suggested rewording of the field or AC.
- **Finding ID:** `RC-n|<location key>|<primary cited ID>`. The location key is the AC ID (`REQ-n/AC-m`), or the requirement ID plus field path (`REQ-n#permissions`). The primary cited ID is the R-ID for RC-4 and RC-5. Otherwise it is the S-ID of the broken rule, for example `S-BA-007` for a missing negative AC, or `S-TESTAB-005` for an RC-3 item.
- **`proposed_changes`:** one per undeclared contradiction or extension: `requirement`, `rule` (R-ID, or `new`), `kind`, `proposed_statement`, `cites`, and the `finding_id` it answers. Never fill `accepted_by`.
- **`test_conditions`:** draft test conditions v1 (S-BA-048), one or more per reviewed AC that you found clear enough to test. They are candidate input for the Analyst's test-condition PR (S-BA-050), so use provisional `TC` IDs. Each `given`, `when` and `then` comes from the AC and its cited sources, never from invention. Leave out an AC that has an open blocking finding.
- **Questions:** S-BA-014 form, with `key` and `blocks` naming REQ or AC IDs.

## Prerequisites and retrieval (S-BA-036, S-BA-045)

- **Prerequisite:** an S-TESTAB-006 rules registry for the area. Without one, RC-4 checks only between requirements, and `decision_summary` says so.
- **Always:** this checklist, the product core, the domain summary.
- **On demand:** related rules (step 2), linked requirements, CI results of verifying checks, specs.
