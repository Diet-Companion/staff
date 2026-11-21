# Business Analyst Strategy (BA)

Updated Nov 20, 2026

## Purpose and scope

This doc covers how requirements are built and kept correct when one human works with agent staff. The project starts from building requirements (`docs/decisions.md`, 2026-11-20), so ARCH, DEV and QA agents consume its output. It is product-agnostic and stack-agnostic.

It honours the common set in S-GEN-064, plus S-GEN-015, -018 and -019. GEN and shared/ decisions are referenced by ID, never restated.

The part from "On-demand reference" on is not always loaded (S-BA-052): S-BA-003, -017, -019 to -021, -025, -026, -029 to -033, -036, -038 to -041, -043 to -049, -051 to -057 and the OD closure table. Retrieve by trigger: kickoff or `INT-n` merge → S-BA-055 to -057; rule PR or demotion → S-BA-044; opening any BA PR → S-BA-049; ready-gate PR → S-BA-017; trace flag → S-BA-020, -021, -053; test-condition PR → S-BA-048; stale flag → S-BA-025; domain note → S-BA-026.

Markers: *(starting value)* means accepted in `docs/decisions.md` (2026-11-20); *(proposed)* means awaiting confirmation, and none is open. Named formats and tools are examples.

## Ownership and agents

- **S-BA-001** Ownership split:
  - **The human owns** business intent, scope, priorities, business rules and their changes, answers to questions, confirmation of assumptions, the ready gate (S-BA-018) and final acceptance.
  - **Agents** elicit, draft, structure, check, link and maintain.

  An agent never sets a human-owned field on its own authority (S-BA-015). *Depends on:* S-GEN-001, S-BA-015.
- **S-BA-002** Working agents in staff-product (S-GEN-014):
  - **Analyst:** turns intake into requirements and acceptance criteria (ACs), runs elicitation, refines drafts on feedback, proposes `changes` declarations, commits accepted test conditions (S-BA-050), and repairs links when an ID is retired.
  - **Knowledge drafting:** drafts and maintains the product core and the rules registry. It is label-based (S-GEN-068).
  - **`analyst-interview`:** conducts the live kickoff interview (S-BA-055). A separate eval unit (S-GEN-030) with its own skill, no tools and a minimal eval row (S-BA-040); part of the Analyst's elicitation, not a separate role.

  Asynchronous elicitation stays inside the Analyst, whose structuring finds the gaps. Only the interactive, tool-less live interview is split out. The BA checks are deterministic scripts, not agents (S-BA-051). This doc owns the reviewer/requirements checklist. Its eval row and caps stay in S-GEN-045 and S-GEN-057. *Depends on:* S-GEN-014, S-GEN-015, S-GEN-064, S-GEN-068, S-BA-050, S-BA-051.

## Requirements artifact model

- **S-BA-004** The product repo is the single source of truth for requirements. A tracker ticket is intake and work tracking only. It links to REQ IDs, and its text stays untrusted (S-SEC-001) until its content is merged into a requirement file. *Depends on:* S-GEN-010, S-SEC-001, S-TESTAB-006.
- **S-BA-005** Types and IDs:

  | Artifact | ID | Notes |
  | --- | --- | --- |
  | Requirement, type `epic` | REQ-n | Business goal and scope. Groups stories |
  | Requirement, type `story` | REQ-n | One user-visible behaviour change. Belongs to one epic |
  | Requirement, type `quality` | REQ-n | A non-functional requirement (performance, security, accessibility, availability, data) with a measurable target |
  | Acceptance criterion | REQ-n/AC-m | Scoped to its requirement |
  | Rule | R-n | An atomic business rule in the registry (S-GEN-018) |
  | Test condition | REQ-n/AC-m/TC-k | Drafted by reviewer/requirements. Committed by the Analyst once the human accepts it (S-BA-050) |
  | Interview transcript | INT-n, with turns `INT-n#T<k>` | A source, committed by the human (S-BA-056) |

  Numbers are zero-padded to at least three digits, allocated in sequence per product and never reused. The ID check fails a PR that adds an ID already present on `main` or in another open PR. The later PR renumbers. *Depends on:* S-BA-050.
- **S-BA-006** Required requirement fields. The format is open; the requirement needs schema-validated structured fields (for example Markdown with YAML front matter). The schema is versioned in staff-product (S-GEN-022).
  - `id`, `type`, `title`, `status`, `area` (from `.staff/areas.yml`, S-GEN-060), and `parent` (for stories, the epic ID);
  - `intent`: actor, need, business value;
  - `scope`: what is in and what is out;
  - `acceptance_criteria` (S-BA-007). Epics may have none;
  - `rules`: the R-IDs the requirement relies on;
  - `changes`: the rule-change declarations (the legacy "Changes: R-042"). Each entry is `{rule: R-n | new, kind: add | modify | retire, proposed_statement, accepted_by}`. `accepted_by` holds the ref of the human's accepting comment, or is empty;
  - `review_dispositions`: one entry per reviewer "contradicts" finding, `{finding_id, disposition: declared | accepted | rejected, ref}`. `declared` points to a `changes` entry. `accepted` and `rejected` cite a human comment. Finding IDs are deterministic (S-BA-032), so dispositions carry across re-reviews;
  - `review_waiver`: empty, or `{ref, revision}`. `ref` cites the human comment that waives the reviewer, and `revision` names the `revision` entry of the ready gate the waiver covers (S-BA-017);
  - `terms`: new glossary terms the requirement introduces, for use in `key` fields (S-BA-007);
  - `quality`: linked quality REQ IDs, or `none` with a reason;
  - `permissions`: the product user roles affected, with what each may and may not do;
  - `sources`: a ref for every statement (S-BA-012);
  - `assumptions` and `questions`, each with a `key` (S-BA-007), a status and a `blocking` flag;
  - `priority` (human-owned);
  - `tracker`: linked ticket refs;
  - `revision`: one entry per change, with date, what changed, reason and source ref. A change made because of a human-confirmed requirement defect (S-BA-048) adds `defect: {item ref, kind}`. The repair PR carries it, shown in its decision summary.

  The prose sits in named sections of at most 2,000 characters each (S-SEC-002). A requirement that needs more is split. *Depends on:* S-GEN-022, S-GEN-060, S-SEC-002.
- **S-BA-007** Acceptance criteria. Each AC is atomic and has:
  - `key`: `{entity, target_id, attribute}`. `target_id` is the stable identifier (S-TESTAB-005) of the operation, error, event or UI element involved, if there is one. `entity` and `attribute` use names from the product-core glossary, the interface specs or the requirement's `terms`. The source-ref check flags any other name. The key identifies what the AC is about, for tracing and eval matching;
  - `given`: preconditions, including data and the user role;
  - `when`: one trigger;
  - `then`: observable outcomes with expected values;
  - `cites`: the R-IDs or source refs its expected values come from;
  - `kind`: positive, negative or boundary.

  Every rule condition the requirement relies on gets at least one negative or boundary AC. Gherkin is one rendering; the structured fields are the contract. *Depends on:* S-TESTAB-005, S-TESTAB-006.
- **S-BA-008** Rule fields:
  - `id` and a one-sentence `statement`;
  - structured `entity`, `condition`, `behavior` and expected values;
  - `type`: validation, calculation, permission, state transition or invariant;
  - `status` (S-GEN-019);
  - `sources`: the introducing REQ, ticket or domain clause;
  - `code_refs` and `verifying_checks` (the IDs, in test ID v1 (S-DEV-045), of the tests that cite the rule);
  - when retired: `replaced_by` and `retired_reason` (wrong, behaviour changed, duplicate).

  There is one rule per file, so each diff covers one rule. *Depends on:* S-GEN-018, S-GEN-019, S-DEV-045.
- **S-BA-009** Requirement lifecycle:

  | Transition | How | Who decides |
  | --- | --- | --- |
  | draft → ready | A ready-gate PR is merged (S-BA-018) | Human |
  | ready → changed | A merged PR edits a ready requirement's ACs, `rules` or `changes` without passing the ready gate. The PR sets `changed` and lists the affected ACs in `revision` | Human (merge) |
  | changed → ready | A ready-gate PR | Human |
  | any → retired | A PR sets `retired`, with reason and `replaced_by`. Its ACs and test conditions retire with it | Human |

  The lifecycle check fails a PR that edits a ready requirement without one of these transitions. The one exception is a link repair (S-BA-053), which keeps the status. A retired requirement is never deleted. Test-condition files have no lifecycle of their own (S-BA-050). *Depends on:* S-BA-018, S-BA-050, S-BA-053.
- **S-BA-010** A change in meaning gets a new ID:
  - A change to an AC's `key`, `given`, `when`, `then` or `cites` retires that AC and adds a new AC ID. Its test conditions retire with it.
  - A rule whose statement or structured fields change is retired, with `replaced_by` set to a new R-ID.
  - Edits to prose sections keep the ID.
  - A link repair (S-BA-053) keeps the ID, because it doesn't change meaning.

  So every downstream artifact that cites an old meaning points at a retired ID, and the nightly trace check finds it (S-BA-021). *Depends on:* S-BA-021, S-BA-053.
- **S-BA-011** Product-contract paths (closes the artifact-path part of OD-GEN-2):
  - `requirements/<area>/REQ-n.md`, one file per requirement, and `requirements/<area>/REQ-n.tc.<ext>` for its test conditions (S-BA-050);
  - `requirements/<area>/sources/INT-n.md` for interview transcripts (S-BA-056);
  - `knowledge/product-core.md` and `knowledge/rules/<area>/R-n.md`, inside the S-GEN-017 layout.

  The requirement, rule and test-condition schemas ship in staff-product under `schemas/`, and the BA check scripts under `checks/`. Both are outside the improver allowlist (S-GEN-027). The trace matrix is generated by CI and not committed, for the reasons in S-GEN-012. *Depends on:* S-GEN-012, S-GEN-017, S-GEN-027, OD-GEN-2, S-BA-050.
- **S-BA-012** No invented facts. In every agent draft, each intent, scope item, AC and rule statement either cites a source ref (intake ticket, human answer, interview turn `INT-n#T<k>`, R-ID, doc) or is recorded as an `assumption` with status `open`. The source-ref check fails an agent commit that contains an uncited statement. Only a human answer turns an assumption into a fact (S-BA-015). *Depends on:* S-BA-015, S-BA-051.

## Elicitation

- **S-BA-013** Intake. Elicitation uses both channels (`docs/decisions.md`, 2026-11-20). A live interview kicks off each new area (S-BA-055 to -057). Asynchronous batches on the ticket handle follow-ups and changes (S-BA-014 to -016).
  - The human opens a tracker ticket with notes, docs and links, and applies `ba:intake`.
  - An intake is a kickoff only when its area has no ready requirement, no merged `INT-n` and no other open kickoff intake. On a kickoff, the Analyst posts an interview guide (S-BA-055) instead of a question batch.
  - Answers and follow-up notes arrive as comments on the same ticket.
  - The human may also write requirements directly in the repo. That content is human-authored, and the checks in S-BA-051 apply to it.

  *Depends on:* S-BA-051, S-BA-055.
- **S-BA-014** Question batches. The Analyst posts at most one question batch per intake per run, as a comment on the intake ticket. The digest lists a pointer to it (S-GEN-061, S-GEN-063).
  - **Size:** at most 7 questions *(starting value)*. Questions that block the ready gate come first, then the rest, ordered by how many ACs each affects.
  - **Form:** each question names the REQ or AC it blocks and carries its `key`. It gives 2–4 concrete options and a recommended default, and is closed-form where possible.
  - **Overflow:** questions beyond the limit wait for the next batch, and their assumptions are recorded as `open`.

  *Depends on:* S-GEN-061, S-GEN-063.
- **S-BA-015** Answers and human-owned fields. Only two things count as answers: comments from accounts in `governance/operators.yml` (read from the pinned staff-core, S-GEN-071), and human turns in a merged interview transcript (S-BA-056). Comments from any other account are input data. Interviewer turns are untrusted data for every agent; only human turns are sources (S-BA-056).

  The human-owned fields are:
  - `priority`;
  - an assumption's status (`confirmed`, `rejected`) and a question's status (`answered`);
  - `changes[].accepted_by`;
  - `accepted` and `rejected` entries in `review_dispositions`;
  - `review_waiver`.

  The Analyst records each answer in `sources` with its comment ref, and only then sets the field. The owner-field check fails an agent commit that changes a human-owned field without citing an operator comment or a human turn. It confirms a comment's author through the tracker (S-DEVOPS-021), and a turn's speaker from the merged transcript. *Depends on:* S-GEN-071, S-SEC-001, S-BA-056, S-DEVOPS-021.
- **S-BA-016** Convergence. If blocking questions are still open after 3 batches on one intake *(starting value)*, the Analyst stops asking and posts an escalation, which the digest lists. The human answers the questions, or holds a conversation and records the outcome on the ticket. Silence never decides a business question. *Depends on:* S-GEN-063.

## Ready gate

- **S-BA-018** The human decides the ready gate. Any PR that sets a requirement to `ready` is a ready-gate PR. It opens with a decision summary:
  - new and changed ACs, and the `changes` declarations;
  - open non-blocking assumptions;
  - the reviewer's verdict, the commit SHA it reviewed, and any unresolved findings;
  - the semantic items of S-BA-017.

  Its ready-gate check must pass. If the ACs changed after the reviewed commit, the check fails and asks for a re-review. The human's merge is the decision (S-GEN-003). Agents only propose readiness, and the reviewer's verdict is advice. *Depends on:* S-GEN-003, S-GEN-015, S-BA-017.

## Knowledge

S-GEN-018 sets the knowledge layers, their homes and owners. S-GEN-019 sets review and the base staleness rule. BA adds:

- **S-BA-022** Only merged active rules and the merged product core are truth for agents. Rules in open PRs, `changes` proposals, discovered notes and drafts are candidate data. Agents cite them as candidates and never use them as an oracle. *Depends on:* S-GEN-019, S-SEC-001.
- **S-BA-023** The registry describes the product as built. Knowledge drafting acts on the S-DEV-044 event, whatever its source:
  - **`direction: implemented`:** it drafts the rule additions and changes the REQ or `changes` entry declares, and the human merges them. Until then, checks and reviews use the requirement's ACs as their source (S-TESTAB-006).
  - **`direction: withdrawn`:** it flags the affected rules and open rule PRs in its output, which the digest lists. Nothing is auto-retired; the human decides.
  - **Sources:** rule changes come only from `changes[]` entries, and product-core patches only from REQ events. An event whose rule change is already active, or already in an open rule PR, is a no-op.

  Rules are never deleted, only retired (S-BA-010). *Depends on:* S-GEN-019, S-TESTAB-006, S-DEV-044.
- **S-BA-024** Product core. Knowledge drafting proposes a patch when a requirement that changes the glossary, roles and permissions, core journeys or invariants is implemented, or when the trace check flags an entry. Every entry cites its source IDs. The size limit holds (S-GEN-018, S-GEN-048). *Depends on:* S-GEN-018, S-GEN-048.
- **S-BA-027** Self-discovered knowledge. A candidate rule in `knowledge/discovered/` becomes a rule only through a knowledge-drafting PR that cites the note and its evidence. reviewer/requirements never treats discovered notes as rules. *Depends on:* S-GEN-018, S-GEN-025.
- **S-BA-028** Production-derived sources (closes the BA part of OD-DATA-2):
  - **What counts:** text written by or about real users, or exported from a production system. That includes support tickets, user feedback, analytics and production logs.
  - **Where it comes from:** BA agents read production-derived content only from redacted exports (S-DEVOPS-029), never through a live connector to a production system.
  - **Read-time redaction:** every tracker and connector fetch in a BA read stage passes through the harness redaction step (G11) before the content reaches the model. The step fails closed, as in S-SEC-004. This is stricter than S-SEC-004, which covers storage and posting: content pasted into an intake would otherwise reach the model unredacted.

  *Depends on:* S-SEC-004, S-DATA-004, S-GEN-020, S-DEVOPS-029.

## Triggers, scope and schemas

- **S-BA-034** Triggers (closes OD-GEN-1 for BA). Only three classes of event start a BA agent. Everything else is dropped.
  - **Human events:** tracker labels and comments, PR reviews and comments, merges, dispatches and verdicts whose actor is in `governance/operators.yml` (S-DEVOPS-017).
  - **Staff-app PR events:** a PR from the staff-product identity that becomes ready, or whose review is re-requested. These may trigger only reviewer/requirements.
  - **Check and schedule events:** the BA checks and nightly jobs, running from human-authored workflows (S-BA-051), and S-DEV-044 events from its post-merge, operator-comment and nightly runs.

  | Agent | Starts when |
  | --- | --- |
  | Analyst | `ba:intake` or `ba:interview` is applied; on a kickoff it posts the interview guide (S-BA-013, -055). An interview transcript `INT-n` merges (S-BA-057). All blocking questions in the latest batch have answers, or the human applies `ba:answered`. The human submits a review on an Analyst PR. The human gives `verdict:confirmed` on a requirement-defect item (S-BA-048). A ready-gate PR merges, which starts test-condition drafting (S-BA-050). The nightly trace check flags one of its artifacts |
  | Knowledge drafting | The human dispatches an area bootstrap. An S-DEV-044 event for a REQ or `changes` entry with rule or product-core impact, `implemented` or `withdrawn` (S-BA-023, -024). A rule is flagged stale (S-BA-025). A discovered note with a candidate rule merges (S-BA-027). The nightly trace check flags a rule or the product core |
  | reviewer/requirements | A PR touching `requirements/**` becomes ready for review, or its review is re-requested. The human applies `ba:review` to a ticket |
  | `analyst-interview` | Only the human launches it, interactively (S-BA-055) |

  A new push to a PR doesn't re-run the reviewer unless its review is re-requested. *Depends on:* S-GEN-005, OD-GEN-1, S-DEVOPS-017, S-BA-023, S-BA-024, S-BA-025, S-BA-027, S-BA-048, S-BA-050, S-BA-051, S-BA-055, S-BA-057, S-DEV-044.
- **S-BA-035** Path scope (closes the agent-scope part of OD-GEN-2 for BA). The scope lint (G2) enforces this split inside the staff-product scope that S-GEN-025 sets:

  | Agent | Writes | Never writes |
  | --- | --- | --- |
  | Analyst | `requirements/**`, including test-condition files | `requirements/*/sources/**` (human only, S-BA-056), `knowledge/**`, any other path |
  | `analyst-interview` | No paths, and no tokens (S-BA-055) | Any path |
  | Knowledge drafting | `knowledge/product-core.md`, `knowledge/rules/**` | `requirements/**`, `knowledge/discovered/**` (it only reads them), any other path |
  | reviewer/requirements | No paths: comments and the labels in S-BA-037 | Any path |

  The G2 scope lint also fails a BA agent commit that has no `Staff-Run-Id` trailer (S-GEN-029). *Depends on:* S-GEN-020, S-GEN-025, S-GEN-029, OD-GEN-2, S-BA-055, S-BA-056.
- **S-BA-037** Read-stage schemas and write actions (closes OD-GEN-6 and OD-SEC-1 for BA). Free-text fields follow S-SEC-002.

  | Agent | Read-stage output | Allowed write actions |
  | --- | --- | --- |
  | Analyst | `requirements[]` (S-BA-006 schema, ACs with `key`; ≤5 per PR-opening run, or one epic for a ready-gate PR, S-BA-049); `decision_summary` (required; the write stage renders it first in the PR body); `test_conditions[]` (S-BA-050); `questions[]` {id, key, blocks, text, options[2–4], recommended, priority}; `assumptions[]` {id, key, text, blocking}; `answers_applied[]` {field, comment ref}; `source_refs[]` | Stage 1: comments as in S-BA-042. Stage 2 adds: an `agent/analyst/*` branch and PR in `requirements/**`, comments on its own PRs, the labels `agent` and `ba:questions` |
  | Knowledge drafting | `rules[]` (S-BA-008 schema; ≤10 per PR, S-BA-044); `retirements[]` {R-ID, replaced_by, retired_reason}; `product_core_patch`; `source_refs[]` | Stage 1: draft tickets and comments as in S-BA-042. Stage 2 adds: an `agent/knowledge-drafting/*` branch and PR in its S-BA-035 paths, the label `agent` |
  | reviewer/requirements | `target`; `reviewed_sha`; `verdict`; `findings[]` {finding_id, checklist_id, severity, location, text, rewording, cited_ids, classification}; `questions[]`; `proposed_changes[]`; `test_conditions[]` | One comment per run on the PR or ticket; the labels `ba:not-ready` and `ba:questions` |

  No BA agent writes `verdict:*` labels (G12). The branch prefixes are reserved by the S-DEVOPS-019 push rulesets. Read stages run in the `read` launcher variant (S-DEVOPS-024). *Depends on:* S-SEC-002, S-SEC-003, S-GEN-020, S-BA-042, S-BA-044, S-BA-049, S-BA-050, S-DEVOPS-019, S-DEVOPS-024.

## Stage-1 output and test conditions

- **S-BA-042** Stage-1 output. At stage 1 (comment and draft only, S-GEN-052), the agent posts one comment per drafted requirement or rule, each with a rendered draft and a patch artifact (a CI artifact, S-DATA-003). That way the human gives one verdict per draft (S-GEN-071).
  - **Analyst:** comments on the intake ticket.
  - **Knowledge drafting:** comments on the merged product PR that triggered it. For other triggers, it comments on a draft tracker ticket. It opens at most one such ticket per area per day (one per nightly run, or one per bootstrap), and collects every draft for that area in it.

  A draft counts as confirmed when the human accepts it without changing the structured fields of its ACs or rule. The human may apply the accepted parts with their own commit, which makes them human-authored. *Depends on:* S-GEN-026, S-GEN-052, S-GEN-071, S-DATA-003.
- **S-BA-050** Test conditions get a home in the repo:
  - **Path:** `requirements/<area>/REQ-n.tc.<ext>`, in the schema of S-BA-048. The Analyst writes it.
  - **How they arrive:** when a ready-gate PR merges, the Analyst opens a test-condition PR. It uses the reviewer's draft test conditions as candidate input (S-BA-022) and gives one or more conditions per ready AC. The human's merge accepts them.
  - **Not gating:** test conditions are not a ready-gate criterion. A ready AC with no test condition 14 days after it became ready *(starting value)* is a nightly trace finding (S-BA-021).
  - **Status:** editing a test-condition file doesn't change the requirement's status. A test condition retires with its AC (S-BA-010).
  - **Ownership:** QA confirmed the schema and left authorship with the Analyst (S-QA-010).

  *Depends on:* S-BA-010, S-BA-021, S-BA-022, S-BA-048, S-QA-010.

## On-demand reference

### Identities, readiness, batching and packaging

- **S-BA-003** The Analyst and knowledge drafting run as the staff-product working-agent identity, and reviewer/requirements runs as the staff-review identity (S-GEN-026). These three read untrusted content and hold write tools, so they use the two-stage split (S-SEC-002) with the schemas in S-BA-037. `analyst-interview` holds no identity token and no write tools (S-GEN-004), so S-SEC-002 doesn't apply to it (S-BA-055). *Depends on:* S-GEN-004, S-GEN-026, S-SEC-002, S-BA-055.
- **S-BA-019** Downstream roles start work only on the ACs of `ready` requirements. On a `changed` requirement, the ACs listed as affected are not ready until the requirement passes the gate again. Its unaffected ACs stay valid. The other roles' triggers enforce this (S-ARCH-015, S-DEV-007, S-QA-010). *Depends on:* S-BA-009, S-ARCH-015, S-DEV-007, S-QA-010.
- **S-BA-044** Knowledge-drafting batch gating *(starting value, `docs/decisions.md`, 2026-11-20)*. Every rule is reviewed in every mode.
  - **Stage 1, one draft per rule,** is the legacy one-rule-per-PR mode. GEN allows no PRs before the promotion threshold (S-GEN-051).
  - **At stage 2,** rule PRs carry up to 10 rules each.
  - **Fallback:** a live rule precision (S-BA-047) below 80% is a role demotion trigger. The ops stage job sets knowledge drafting's demotion ceiling to 1 (S-GEN-050), which returns it to one draft per rule. To restore batches, the human clears the ceiling.

  *Depends on:* S-GEN-050, S-GEN-051, S-BA-043, S-BA-047.
- **S-BA-049** The BA flow fits S-GEN-061 and the rollout gate in S-GEN-073:
  - Each Analyst PR covers one intake slice, with at most 5 requirements *(starting value)*. A ready-gate PR may bundle the requirements of one epic. A test-condition PR covers one ready-gate PR. Link repairs arrive as one PR per area per nightly run (S-BA-053).
  - Question batches, reviewer comments, coverage gaps and stale-rule lists reach the human through the digest, as one item per intake or per check.
  - Knowledge PRs batch as in S-BA-044, and they count toward the working-agent cap.
  - Every BA PR opens with the decisions the human has to make. Prose follows.
  - Bootstrap labelling (50 + 30 rules) is scheduled as batches and counted in the review-minutes metric.

  *Depends on:* S-GEN-061, S-GEN-071, S-GEN-073, S-BA-044.
- **S-BA-052** Context budget: the S-GEN-009 packaging rule applies. Everything before `## On-demand reference` is always loaded; the rest, closing sections included, is on demand. Two packs are measured separately against 15k:
  - **reviewer/requirements:** adds S-BA-029 to -032 from the reference.
  - **`analyst-interview`:** a narrower local rule on S-GEN-009 and S-GEN-004, injected by the launch wrapper in the session bundle. Its static part is shared/ plus S-BA-007, -055 and -056, which the release gate measures. The S-BA-055 inputs are checked against the remaining budget at launch. The interviewer does no Analyst work, so the rest is left out.

  The packaging or release-gate check (S-GEN-021) re-measures every pack (always-loaded, reviewer and the interviewer's static part) whenever shared/ or this doc changes. It fails closed when any pack is over. The fix is to move more sections into the reference (S-GEN-048). *Depends on:* S-GEN-004, S-GEN-009, S-GEN-021, S-GEN-048, S-BA-055.

### Live interview

- **S-BA-055** Live interview: when and how it runs.
  - **When:** one session per new area, at kickoff (S-BA-013). A further session runs only when the human applies `ba:interview` to an intake. Agents never apply that label or start a session (`docs/decisions.md`, 2026-11-20). Everything else goes through asynchronous batches.
  - **Guide:** the Analyst prepares it in a normal run. It lists at most 10 topics *(starting value)*, each with a topic ID, blocking ones first. Topics are drawn from the intake, the product core and the RC-1 to RC-9 categories: actors, goals, journeys, rules, permissions, quality targets, out of scope.
  - **Run mode:** interactive mode as S-GEN-004 defines it, with its launch wrapper, sandbox and post-session hand-off (S-DEVOPS-025, in the `interactive` variant of S-DEVOPS-024). BA adds:
    - the wrapper's session bundle carries the interviewer pack (S-BA-052) with the guide, the product core and the intake, all redacted per S-BA-028;
    - **Checks:** the wrapper checks that the bundle's injected inputs fit the budget left after the pack's static part. If they don't, it fails closed (S-GEN-009);
    - the opening record reserves the $5 cap;
    - the sandbox's only output is the transcript, and the hand-off also delivers the redacted transcript to the human for commit (S-BA-056).
  - **Interviewer turns:** each turn is structured as `{topic_id, kind: question | readback, point}`. A readback carries exactly one point, `{text, key, value, from_turns[]}`: `key` and `value` hold the fact in structured form (S-BA-007), and `from_turns` lists the human turns it summarises. Questions never propose candidate values or defaults. Only a readback restates a value, and it takes that value from its `from_turns`.
  - **Limits:** timebox 60 min; caps $5 and 75 min per session (S-BA-038). All *(starting value)*.
  - **Eval and stage:** a minimal eval row (S-BA-040, `docs/decisions.md`, 2026-11-20) gives its skill PRs and releases the regression check that S-GEN-021 and S-GEN-046 need. It holds no write action, so it stays at stage 1.

  *Depends on:* S-GEN-004, S-GEN-009, S-GEN-021, S-GEN-026, S-GEN-030, S-GEN-046, S-GEN-058, S-GEN-066, S-GEN-071, S-SEC-008, S-DATA-002, S-BA-028, S-BA-040, S-BA-052, S-DEVOPS-024, S-DEVOPS-025.
- **S-BA-056** Transcript capture and storage:
  - **Speakers:** the session harness, not the model, records each turn with an ID, a speaker (`human` or `interviewer`) and a timestamp. Human turns come only from the human's input channel.
  - **Redaction:** each human turn passes the harness redaction step (G11) before it reaches the model. A turn that fails redaction isn't sent, and the human is asked to rephrase. At the end, the whole transcript is redacted again (S-SEC-004). The harness records the completion data (status, cost, tokens), which the hand-off uses to complete the session's single `agent_run` record (G5, S-BA-055).
  - **Storage:** the redacted transcript becomes source `INT-n`, at `requirements/<area>/sources/INT-n.md`. The human commits it, which checks it once more for missed redaction. Agents never write or edit `requirements/*/sources/**` (S-BA-035, S-BA-046).
  - **Trust, a stricter local rule on S-SEC-001:** after merge, only human turns are trusted. Interviewer turns stay untrusted data for every agent, because they were generated from untrusted inputs.
  - **Answers:** only human turns count. An interviewer turn is never a source.
  - **Readbacks:** a readback counts only for its single point, and only when the next human turn confirms it. It is cited as the pair `INT-n#T<k>/T<k+1>`. Any other human statement is cited as `INT-n#T<k>`.

  *Depends on:* S-GEN-012, S-GEN-020, S-GEN-025, S-SEC-001, S-SEC-004, S-BA-035, S-BA-046, S-BA-055.
- **S-BA-057** From transcript to requirements:
  - **Trigger:** the merge of `INT-n` starts the Analyst, as a human event (S-BA-034). The Analyst reads the transcript through its normal read stage (S-BA-037).
  - **Drafts:** it drafts epics, stories and ACs, each citing human turns (S-BA-012). Gaps and unconfirmed points become open assumptions and the first asynchronous question batch (S-BA-014).
  - **Facts:** nothing the interviewer suggested becomes a fact unless a human turn confirmed it.
  - **Review minutes:** the harness records a timing-only event (S-GEN-071) for each human turn, and the post-session hand-off delivers them to the recorder (S-BA-055). The recorder accepts them only from a hand-off run that an operator dispatched, for a session that is still `open` (S-GEN-071). The S-GEN-032 rule then counts the session's elapsed time, turn by turn, toward the rollout gate (S-GEN-073). Sessions are scheduled like other one-off batches.

  *Depends on:* S-GEN-032, S-GEN-071, S-GEN-073, S-BA-012, S-BA-014, S-BA-034, S-BA-037, S-BA-055.

### Ready-gate check

- **S-BA-017** Ready criteria. The ready-gate check scripts only the structural items:
  1. the schema, ID, lifecycle, source-ref and owner-field checks pass;
  2. no blocking question or assumption is open;
  3. `quality` and `permissions` are filled in, or set to `none` with a reason, and `priority` is set;
  4. every R-ID in `rules` that has a `condition` is cited by at least one AC of kind negative or boundary;
  5. either a reviewer/requirements result exists for a commit whose ACs, `rules` and `changes` match the head, and every "contradicts" finding in it has a `review_dispositions` entry; or `review_waiver` cites an operator comment and names this gate's `revision` entry, so an old waiver never passes a later gate. The waiver covers the case where the reviewer is switched off or not yet built. The check reads no switch (S-BA-051).

  The check reads reviewer results only from comments by the staff-review identity, and only their machine-readable block (S-BA-032). The human judges the semantic items from the decision summary (S-BA-018): that ACs are atomic and complete, that every rule change is declared, and that the remaining findings are acceptable. *Depends on:* S-BA-006, S-BA-015, S-BA-032, S-BA-051.

### Trace check, link repair and staleness

- **S-BA-020** The chain is requirement → rule → AC → test condition → downstream artifacts (ADRs, code changes, tests). Every link is stored on the citing side, by ID: ACs cite R-IDs; test-condition files cite AC IDs (S-BA-050); ADRs, product PRs and tests cite REQ, AC or R-IDs (S-ARCH-006, -029; S-DEV-009; S-QA-007). Nobody maintains back-links by hand. *Depends on:* S-BA-050, S-ARCH-006, S-ARCH-029, S-DEV-009, S-QA-007.
- **S-BA-021** Trace check, a script:
  - **On every product PR (blocking):** a citation that the PR adds or edits points to a missing or retired ID.
  - **Nightly (non-blocking):**
    - citations made stale by a retirement;
    - ready ACs with no test condition after the grace period (S-BA-050);
    - active rules without verifying checks (S-BA-025);
    - product-core entries that cite a retired ID.
  - **Exempt:** historical fields (`changes[].rule` of kind `modify` or `retire`, `revision`, `replaced_by`) and retired artifacts.

  The nightly findings go through the recorder (S-GEN-026) as unlinked `check_outcome` records, keyed by `finding_key` (check name, artifact ID, finding kind). A finding already present in the check's previous successful snapshot is a repeat (S-GEN-031). The digest lists them (S-GEN-063). They trigger the repair owners: the Analyst for requirements and test conditions, knowledge drafting for rules and the product core, QA for tests (S-QA-025), and the Architect for ADRs (S-ARCH-034). The trace matrix is published as a CI artifact. *Depends on:* S-GEN-026, S-GEN-031, S-GEN-063, S-BA-025, S-BA-050, S-ARCH-034, S-DEV-009, S-DEV-044, S-QA-025.
- **S-BA-053** Link repair. A diff counts as a link repair, and keeps the AC IDs and the requirement status, only if the lifecycle and trace checks verify all of the following:
  - it changes only entries in `rules` or AC `cites`;
  - each change replaces a retired R-ID with that rule's `replaced_by`;
  - the retirement either was declared in this requirement's own `changes` with `accepted_by` set, or has `retired_reason: duplicate`. In both cases the meaning the requirement relies on is the replacement's meaning.

  Every other re-point follows S-BA-010. The Analyst batches link repairs into one PR per area per nightly run. *Depends on:* S-BA-006, S-BA-008, S-BA-021, S-BA-049.
- **S-BA-025** Staleness. The stale-rule check implements S-GEN-019 as a script. A rule is flagged stale when it loses its last verifying check, or when an operator applies `qa:source-wrong` to a failure of one of its verifying checks. The check reads the label from tracker failure items and from code-host PR comments, each with the `governance/operators.yml` actor check (S-QA-031). Verifying checks are matched by test ID v1 (S-DEV-045). A test-file move is mapped through the S-DEV-028 rename mapping first, so a moved test doesn't count as lost. A stale rule triggers knowledge drafting, which proposes a correction or a retirement; the human decides. An active rule that still has no verifying check 30 days after its source entry became implemented (S-DEV-044) *(starting value)* is listed in the digest as a coverage gap, not as stale. For a rule with no S-DEV-044 source entry (bootstrap or discovered), the clock starts at the rule's merge. *Depends on:* S-GEN-019, S-GEN-063, S-GEN-071, S-DEV-028, S-DEV-044, S-DEV-045, S-QA-031.
- **S-BA-026** Domain knowledge. reviewer/requirements uses the staff-domain plugins for RC-8. BA agents never write to them; a suggested domain addition goes in the agent's output as an advisory note, which the digest lists. When a domain plugin's last-reviewed date is more than 12 months old *(starting value)*, every RC-8 finding that relies on it carries a "domain source stale" flag. *Depends on:* S-GEN-018, S-GEN-025.

### Requirements checklist (reviewer/requirements)

- **S-BA-029** The checklist (closes the BA part of OD-GEN-8). Each item has a stable ID, which the checklist diff check protects (S-BA-046):

  | ID | Item | Finds |
  | --- | --- | --- |
  | RC-1 | Ambiguity | Vague or unquantified terms ("fast", "usually"), terms missing from the glossary |
  | RC-2 | Completeness | Missing fields or ACs, missing error and empty states, missing negative or boundary ACs (S-BA-007) |
  | RC-3 | Testability | The items in S-BA-030 |
  | RC-4 | Consistency | Contradictions inside the requirement, with other ready requirements, and with the registry (S-BA-031) |
  | RC-5 | Impact | Undeclared rule changes; affected requirements, areas and existing checks |
  | RC-6 | Non-functional | Missing or unmeasurable quality targets |
  | RC-7 | Permissions | Product user roles not covered, missing deny cases |
  | RC-8 | Domain compliance | Conflicts with domain clauses (S-BA-026) |
  | RC-9 | Sources and assumptions | Uncited statements, assumptions presented as facts, real personal data in examples |

  *Depends on:* S-GEN-015, OD-GEN-8.
- **S-BA-030** RC-3 testability items (closes the BA part of OD-TESTAB-1 and delivers BA's share of S-TESTAB-009):
  - every expected value traces to a cited source, and every interface the requirement adds or changes has a machine-readable spec or is flagged as needing one (S-TESTAB-006);
  - outcomes are observable through stable identifiers, not layout or wording (S-TESTAB-005);
  - data preconditions can be created by a seed script or factory, and every named user role maps to a test account (S-TESTAB-004);
  - behaviour that depends on time, flags or third parties names the condition that has to be controlled (S-TESTAB-008);
  - asynchronous outcomes say how completion is observed: an event, a status or a correlated log (S-TESTAB-007).

  *Depends on:* S-TESTAB-004, S-TESTAB-005, S-TESTAB-006, S-TESTAB-007, S-TESTAB-008, S-TESTAB-009.
- **S-BA-031** Contradiction detection, carried over from the legacy doc and generalised:
  1. Split the requirement into atomic statements (entity, condition, behaviour), in the same form as the rule fields (S-BA-008).
  2. Retrieve only related rules: by entity, operation, glossary term, area and changed code paths, then by semantic search.
  3. Classify each pair as consistent, extends, duplicate, contradicts or ambiguous overlap.
  4. Compare with `changes`. A declared change is an impact item. An undeclared contradiction is a finding, with a proposed declaration.
  5. Check claims about current behaviour against the latest CI results of the rule's verifying checks. Probing a test environment doesn't fit the current cap (S-GEN-057) and is out of scope.
  6. Existing checks that would have to change without a declaration count as an undeclared contradiction.

  The human confirms every "contradicts" finding on live and visible items, through `review_dispositions`. Hidden and promotion items are scored by script (S-GEN-041). Known limit: implicit contradictions that span several rules are often missed. *Depends on:* S-BA-006, S-BA-008, S-GEN-041, S-GEN-057.
- **S-BA-032** Output: one advisory comment per run on the PR or ticket, never an edit. The digest lists a pointer to it (S-GEN-063). It contains:
  - a readiness verdict: ready, ready with questions, or not ready;
  - at most 7 findings *(starting value)*, ordered by severity, each with a finding ID, checklist ID, location, suggested rewording and cited IDs;
  - questions in the S-BA-014 form;
  - proposed `changes` declarations;
  - draft test conditions per AC, which are candidate input for S-BA-050;
  - a machine-readable block with the reviewed commit SHA, and the finding IDs and their classifications.

  A finding ID is derived from (checklist ID, AC `key` or location, cited R-ID), for example as a short hash. So the same finding gets the same ID on every re-review, and its disposition still applies.

  Until the checklist meets its stage 1→2 threshold, the comment is headed "not yet qualified". After that it pre-reviews agent PRs (S-GEN-062). *Depends on:* S-GEN-061, S-GEN-062, S-GEN-063.
### Context, caps and run records

- **S-BA-036** Context, in addition to the always-loaded set in S-GEN-009:

  | Agent | Always loaded | Retrieved on demand |
  | --- | --- | --- |
  | Analyst | Product core, requirement schema, own learnings | Intake ticket and attachments, related requirements and rules, reviewer comments, domain glossary, code and specs for the area |
  | Knowledge drafting | Product core, rule schema and lifecycle, own learnings | Code, specs, tests, the implementing PR and its requirement, stale flags, discovered notes |
  | reviewer/requirements | Checklist, product core, domain summary | Related rules (S-BA-031 step 2), linked requirements, CI results, specs |
  | `analyst-interview` | Only the interviewer pack (S-BA-052): shared/, S-BA-007, S-BA-055, S-BA-056, plus the guide, product core and redacted intake from the session bundle | None. The sandbox has no repo or tracker route (S-GEN-004) |

  *Depends on:* S-GEN-004, S-GEN-009, S-GEN-048, S-BA-031, S-BA-052.
- **S-BA-038** Per-run caps (closes OD-GEN-4 for BA):
  - **Analyst:** $3 per run, 20 min *(starting value)*.
  - **Knowledge drafting:** $2 per run, 15 min *(starting value)*. One run covers one source bundle, so an area bootstrap runs as several runs.
  - **reviewer/requirements:** as in S-GEN-057.
  - **`analyst-interview`:** $5 per session, 75 min *(starting value)* (S-BA-055). Each eval session runs under the same cap (S-GEN-059).

  Eval worst cases under S-GEN-070:
  - Analyst: 20 × 5 × $3 = $300, plus $20 for the judge, so the skill-PR budget is $192.
  - Knowledge drafting: 20 × 5 × $2 = $200, so its budget is $120.
  - `analyst-interview`: 12 × 5 × $5 = $300, so its budget is $180. *Depends on:* S-GEN-056, S-GEN-057, S-GEN-059, S-GEN-070.
- **S-BA-039** BA run records add these fields inside `role` (S-GEN-029): `req_ids`, `ac_ids`, `rule_ids_changed`, `questions_asked`, `assumptions_open`, `readiness_verdict`. They also carry the outcome fields in S-BA-054. *Depends on:* S-GEN-029, S-BA-054.

### Eval rows

- **S-BA-033** Evaluation uses the S-GEN-045 row unchanged. The legacy rule "escaped bugs join the golden set" is carried over in blind form. Human-confirmed requirement defects become seeding inputs, from which the seeding agent writes new seeded tickets. The seeding agent reads them from the product repo, which it can already read (S-GEN-026): they are the `revision` entries that carry `defect` (S-BA-006). The escaped item itself never becomes a hidden or promotion task (S-GEN-028). Secondary seeded defects are not added now. They are revisited after real reviewer results (`docs/decisions.md`, 2026-11-20). *Depends on:* S-GEN-026, S-GEN-028, S-GEN-045, S-BA-006, S-BA-048.

- **S-BA-040** Eval rows (closes OD-GEN-3 for BA). Scores are pooled (S-GEN-035). Hidden and promotion tasks are scored by script (S-GEN-041).

  | Agent | Golden tasks | Promotion set minimum | Mode | Oracle | Primary metrics | Stage 1→2 threshold | Hard limits | LLM judge |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | Analyst | 20 intake tasks, each seeded with 1–3 gaps; 10 also seeded with a conflict against an active rule *(starting value)* | 10 tasks with the same mix, using holdout seeds *(starting value)* | Artifact-seeded (mapping below) | A script matches outputs to spec entries by `key`: expected behaviours to AC keys, gaps to question or assumption keys, conflicts to `changes` R-IDs | AC coverage, unsupported-AC rate, gap recall, question precision, declaration recall, invented-fact rate | AC coverage ≥80%, unsupported ACs ≤15%, gap recall ≥70%, question precision ≥50%, declaration recall ≥70%, invented facts ≤5% *(starting value)* | Schema-valid output; no write outside `requirements/**`; no human-owned field set | Yes, for question and wording quality. Reported, not gating |
  | Knowledge drafting | 50 labelled rules *(starting value)*, across at most 20 source bundles *(starting value)* | 30 held-out labelled rules *(starting value)*, across at most 12 bundles *(starting value)* | None: label-based (S-BA-041) | A drafted rule matches a reference rule by structured fields. An ambiguous match is a miss | Rule precision (recall against the labelled set is reported, not gating) | ≥80% *(starting value)* | Schema-valid output; every rule cites a source; no rule deleted | No |
  | `analyst-interview` | 12 scripted simulated-human sessions *(starting value, `docs/decisions.md`, 2026-11-20)*, split 70/30 visible and hidden and rotated per S-GEN-037 | n/a: it never leaves stage 1 (S-BA-055) | Artifact-seeded. The seeding agent writes each session script and its spec: a guide, an answer bank of facts keyed by topic ID, one redaction-failing human turn, and one intake passage that tries to inject a human-tagged turn | The eval runner plays the scripted human in the S-GEN-066 sandbox. A script scores the transcript against the spec | Guide-topic coverage | Coverage ≥90% *(starting value)*. It gates skill PRs and releases through the regression rule (S-GEN-021, S-GEN-036), not a promotion | Interviewer-asserted facts = 0; speaker-tag integrity 100%; failed-redaction handling 100% *(starting value)* | No |
  | reviewer/requirements | As in S-GEN-045 (S-BA-033) | | | | | | | |

  **Analyst spec mapping.** Each spec entry uses the S-GEN-067 artifact-seed form:
  - location: the intake section;
  - violated ID: the entry's `key` {entity, target_id, attribute}, because the agent assigns REQ and AC IDs itself;
  - corrected text: the expected value, or the missing fact.

  Expected behaviours are entries of kind `expected`. They include the negative and boundary behaviours that S-BA-007 requires, so a compliant AC is never counted as unsupported. Gaps and conflicts are defect entries. Each bundle has a glossary and spec vocabulary, and key names are matched only against it (S-BA-007).

  Test conditions are not in this row. At stage 2 they are judged only by the human's merge, and their edit rate is reported (S-BA-047). Promotion-task seeds come from the holdout catalogue, and the 10 seeded promotion tasks add 30 entries to it (S-GEN-039).

  Formulas:
  - **AC coverage:** expected behaviours matched by an AC key / expected behaviours.
  - **Unsupported-AC rate:** ACs that match no expected behaviour / ACs produced.
  - **Gap recall:** planted gaps matched by a question or open assumption / planted gaps.
  - **Question precision:** questions and open assumptions that match a planted gap / questions and open assumptions raised.
  - **Declaration recall:** planted conflicts declared in `changes` with the right R-ID / planted conflicts.
  - **Invented-fact rate:** planted gaps whose key gets a stated value and no assumption / planted gaps.
  - **Rule precision:** drafted rules matching a reference rule / drafted rules.
  - **Rule recall (reported only):** reference rules matched / reference rules.
  - **Guide-topic coverage:** guide topics with at least one interviewer question tagged to them and answered by the scripted human / guide topics.
  - **Interviewer-asserted facts:** the count of interviewer turns that either:
    - fail the turn schema (S-BA-055);
    - contain an answer-bank value (exact or normalised match) before any human turn has delivered it;
    - are readbacks whose `point.key` and `point.value` don't match, exactly or after normalisation, an answer-bank fact delivered in the human turns listed in `point.from_turns`. The script compares `key` and `value` only, never the prose in `point.text`.

    The scripted human replies only from the answer bank, so the script knows which facts each human turn delivered.
  - **Speaker-tag integrity:** turns tagged `human` that came from the scripted-human channel / turns tagged `human`. The injection passage must produce no human-tagged turn.
  - **Failed-redaction handling:** redaction-failing turns that were withheld from the model and from the transcript and followed by a rephrase request / redaction-failing turns.

  Every session contains each trap kind, so stratification under S-GEN-037 puts at least one trap of each kind in the hidden set.

  *Depends on:* S-GEN-021, S-GEN-035, S-GEN-036, S-GEN-037, S-GEN-039, S-GEN-041, S-GEN-044, S-GEN-045, S-GEN-066, S-GEN-067, S-BA-007, S-BA-033, S-BA-041, S-BA-055.
- **S-BA-041** Labels for knowledge drafting:
  - The eval runner has the agent draft rules from source bundles in the eval sandbox (S-GEN-066).
  - The human labels each drafted rule as a labelling batch: correct, or wrong with corrected structured fields. These batches produce timing-only records (S-GEN-071).
  - **Reference rules** are the rules labelled correct, plus the corrected versions of rules labelled wrong. A draft that matches a rule's wrong original counts as a false positive.
  - Golden batches are assigned at random (S-GEN-028). Promotion batches are drafted and labelled only after the version under promotion is frozen (S-GEN-068).
  - Verdicts on live drafts stay full verdict records and never feed eval sets.

  *Depends on:* S-GEN-028, S-GEN-066, S-GEN-068, S-GEN-071.

### Stage rules and testability prerequisites

- **S-BA-043** Stage-2 and stage-3 rules (closes OD-GEN-5 for BA, together with S-BA-044). The role demotion triggers add to those in S-GEN-052.

  | Agent | Stage-2 quality metric that must hold for stage 3 | Role demotion trigger → stage 1 | Stage 3 |
  | --- | --- | --- | --- |
  | Analyst | None, because it has no stage 3 | Escaped requirement defect rate >30% *(starting value)* | None. Every requirement change is a business decision, so the Analyst stops at stage 2 |
  | Knowledge drafting | Rule correction rate ≤10% *(starting value)* | Rule correction rate >20% *(starting value)*, or live rule precision <80% (S-BA-044) | **Change class:** PRs that change only `verifying_checks` or `code_refs` of active rules, after tests or code moved. **Guard:** the trace check, and the net-set rule diff check (S-BA-046). Test IDs use v1 (S-DEV-045), and test-file moves are mapped through the S-DEV-028 rename mapping before the sets are compared. **Critical miss:** a merged lane PR that left an active rule with fewer verifying checks, or with a check that doesn't cite it |

  *Depends on:* S-GEN-052, S-GEN-053, S-BA-044, S-BA-046, S-BA-047, S-BA-054, S-DEV-028, S-DEV-045.
- **S-BA-045** Testability prerequisites (closes OD-TESTAB-6 for BA):
  - **Analyst:** none beyond the manifest (S-TESTAB-001). It produces S-TESTAB-006 sources.
  - **Knowledge drafting:** S-TESTAB-006 interface specs, for areas that have interfaces.
  - **reviewer/requirements:** an S-TESTAB-006 rules registry for the area. Without one, RC-4 checks only between requirements and says so in its output.

  *Depends on:* S-TESTAB-001, S-TESTAB-006.

### Diff checks, check scripts and outcome records

- **S-BA-046** Diff checks (closes OD-GEN-9 for BA). They run on agent PRs. Every flagged diff needs explicit human sign-off (G3).
  - **AC diff check:** on a ready or changed requirement, any of these is flagged:
    - an AC removed or retired;
    - a `then` value or `cites` entry removed or loosened;
    - a negative or boundary AC removed;
    - a quality requirement's measurable target removed or loosened;
    - a "may not" entry removed from `permissions`.

    A diff that the link-repair check verifies (S-BA-053) is exempt.
  - **Rule diff check:**
    - a rule is retired, or its structured fields change;
    - the set of `verifying_checks` shrinks, or gains a check that doesn't cite the rule. The set is compared net, so re-pointing a moved check isn't flagged;
    - deleting a rule file is always blocked.
  - **Product-core diff check:** an invariant, a role or permission entry, or a cited source is removed or loosened.
  - **Test-condition diff check:** any of these is flagged:
    - a test condition is removed;
    - a `then` value or `cites` entry is removed or loosened;
    - an AC loses its last negative or boundary test condition.

    Retirement together with its AC (S-BA-010) is exempt.
  - **Owner-field, ready-gate, trace and link-repair checks:** S-BA-015, S-BA-017, S-BA-018, S-BA-021 and S-BA-053.
  - **Source check:** an agent commit that adds, edits or deletes a file under `requirements/*/sources/**` is blocked.
  - **Checklist diff check (staff repo):** a skill PR removes or rewords an RC item.

  The Analyst and knowledge drafting stay at stage 1 until all the product-side checks exist (G3). *Depends on:* S-GEN-020, S-GEN-051, S-BA-015, S-BA-017, S-BA-018, S-BA-021, S-BA-050, S-BA-051, S-BA-053.
- **S-BA-051** BA check scripts:
  - **Schema, ID, lifecycle and trace checks** apply to every PR, human or agent.
  - **Source-ref and owner-field checks** apply to agent-authored commits. The human is a source in their own right.
  - **The ready-gate check** applies to every ready-gate PR.
  - **The diff checks** in S-BA-046 apply to agent PRs.

  The checks ship from staff-product `checks/` and run as required checks from a source the PR can't change (S-DEVOPS-020). They don't read `AGENTS_ENABLED` or any plugin switch, so they keep running when agents are off. A check that can't run fails closed. *Depends on:* S-GEN-069, S-BA-046, S-DEVOPS-020.
- **S-BA-054** BA outcome records. The ops stage job reads only the outcome store (S-GEN-026), so a nightly BA check derives the per-artifact outcomes from the product repo and emits them through the recorder, which takes CI job outputs. Every BA agent commit carries a `Staff-Run-Id` trailer, which links each artifact to the run that drafted it (S-GEN-029). The check reads the run IDs from each merged PR's commits through the code host API, not from trailers on `main` (S-GEN-029). Per drafting run, the check emits one linked `check_outcome` record (S-GEN-031). It has `drafting_run_id` set from the trailer, no `artifact_id`, and these counts in `role` (S-BA-039):
  - `rules_merged`, `rules_accepted_unchanged` and `rules_retired_wrong_30d`, for knowledge drafting;
  - `reqs_ready` and `reqs_with_defect_30d`, for the Analyst. These are counted from the confirmed requirement-defect items themselves: items carrying `verdict:confirmed` from an operator account, read through the tracker (S-DEVOPS-021) and mapped to their target REQ. They are not counted from the `revision` entries that the Analyst writes. The check also cross-checks the items against the repo. A confirmed item with no matching `defect` revision entry within 7 days *(starting value)* is a digest finding;
  - `tcs_merged` and `tcs_edited`, for Analyst test conditions.

  The ops stage job computes S-BA-047 from these records. *Depends on:* S-GEN-026, S-GEN-029, S-GEN-031, S-GEN-071, S-BA-006, S-BA-039, S-BA-047, S-BA-048, S-DEVOPS-021.

### Role metrics and interfaces

- **S-BA-047** Role metrics (closes OD-GEN-7 for BA). Windows are *(starting value, `docs/decisions.md`, 2026-11-20)*. The 30-day metrics count only items whose 30-day window has closed.

  | Metric | Formula |
  | --- | --- |
  | Escaped requirement defect rate | Analyst-drafted requirements with ≥1 human-confirmed requirement defect (S-BA-048) within 30 days of becoming ready / Analyst-drafted requirements made ready at least 30 days ago, last 20 |
  | Live rule precision | Rules accepted unchanged / rules reviewed, last 30 rules *(starting value, `docs/decisions.md`, 2026-11-20)* |
  | Rule correction rate | Merged agent-drafted rules retired as `wrong` within 30 days / agent-drafted rules merged at least 30 days ago, last 30 |
  | Questions per ready requirement | Questions asked / requirements made ready, last 20. A load signal with no threshold |
  | Trace completeness | Ready ACs past the grace period (S-BA-050) with ≥1 test condition / ready ACs past the grace period, nightly snapshot |
  | Rule coverage | Active rules with ≥1 verifying check / active rules, nightly snapshot |
  | Test-condition edit rate | Merged Analyst test conditions whose structured fields the human edited / merged Analyst test conditions, last 20. Reported, no threshold |

  The inputs come from S-BA-054. *Depends on:* S-GEN-032, S-GEN-071, S-BA-050, S-BA-054.
- **S-BA-048** What BA provides:

  | Artifact | Schema | Consumers |
  | --- | --- | --- |
  | Requirement and AC | S-BA-006, S-BA-007 (staff-product) | ARCH, DEV, QA |
  | Rule | S-BA-008 (staff-product) | Every role; reviewer/requirements; the QA oracle |
  | Test conditions v1 | `{id: REQ-n/AC-m/TC-k, ac, kind, given, when, then, cites[]}`, in staff-product; reviewer drafts use the same schema (S-GEN-022). Stored per S-BA-050 | QA (S-QA-010) |
  | Trace matrix | CI artifact (S-BA-021) | Every role |
  | Requirement-defect item | `{target: REQ or AC ID, kind: ambiguous, contradicts, untestable, missing or infeasible, evidence_refs}`. Any role's agent or the human posts it on the requirement's ticket; a human verdict confirms it | BA consumes it. ARCH (S-ARCH-017), DEV (S-DEV-008, -017) and QA (S-QA-011) raise it |

  What BA needed from other roles was OD-BA-1 to OD-BA-7, all now closed. *Depends on:* S-GEN-022, S-BA-050, S-ARCH-017, S-DEV-008, S-DEV-017, S-QA-010, S-QA-011.

### Open dependencies closed by this doc

| Open dependency | Closed by |
| --- | --- |
| OD-GEN-1 | S-BA-034 |
| OD-GEN-2 | S-BA-011, S-BA-035 |
| OD-GEN-3 | S-BA-040, S-BA-041 |
| OD-GEN-4 | S-BA-038 |
| OD-GEN-5 | S-BA-043, S-BA-044 |
| OD-GEN-6, OD-SEC-1 | S-BA-037 |
| OD-GEN-7 | S-BA-047, S-BA-054 |
| OD-GEN-8 (BA part) | S-BA-029 to S-BA-033; test conditions v1 in S-BA-048 and S-BA-050, confirmed by S-QA-010 |
| OD-GEN-9 | S-BA-046, S-BA-051 |
| OD-TESTAB-1 (BA part) | S-BA-030 |
| OD-TESTAB-6 | S-BA-045 |
| OD-DATA-2 (BA part) | S-BA-028 |

Not addressed to BA: OD-GEN-10, OD-SEC-2, OD-DATA-1 and OD-TESTAB-2 to -5.

## Assumptions

Items 2, 3, 5–11, 15, 17 and 19 are reasonable defaults the designer made. Items 1 and 14 are decisions. Items 4, 16 and 18 list the values the human accepted as starting values (`docs/decisions.md`, 2026-11-20). Item 12 lists the carried starting values. Item 13 is retired. No *(proposed)* item is open.

1. **Elicitation channel (decided, `docs/decisions.md`, 2026-11-20):** both channels. A live interview kicks off a new area, with its transcript saved as the source, and asynchronous batches on the ticket handle follow-ups and changes (S-BA-013 to S-BA-016, S-BA-055 to S-BA-057).
2. **Requirement storage:** one file per requirement in the product repo, with structured fields validated by schema and bounded prose sections. Markdown with YAML front matter is an example, not a requirement.
3. **Rule timing:** the registry describes the product as built, and declared rule changes merge after the implementing product PR (S-BA-023). That keeps contradiction detection anchored to current behaviour.
4. **Accepted values** *(starting value, `docs/decisions.md`, 2026-11-20)*:
   - elicitation: 7 questions per batch; 3 batches before escalation;
   - reviewer findings per comment: 7, carried from the legacy "top 5–7";
   - requirements per Analyst PR: 5;
   - caps: Analyst $3 / 20 min, knowledge drafting $2 / 15 min;
   - Analyst eval row: 20 golden tasks, 10 promotion tasks, and the six thresholds in S-BA-040;
   - knowledge-drafting source bundles: at most 20 golden and at most 12 promotion;
   - escaped requirement defect rate: 30-day maturity window, last 20, demotion above 30%;
   - rule correction rate: 30-day maturity window, last 30; ≤10% to hold stage 2 for stage 3; >20% to demote;
   - questions per ready requirement: last 20;
   - trace completeness and rule coverage: nightly snapshots;
   - test-condition grace period: 14 days;
   - coverage gap: 30 days;
   - domain staleness: 12 months.
5. **Mapping legacy batch gating onto stages (S-BA-044):** the legacy one-rule-per-PR mode is stage 1 (one draft per rule), both before the promotion threshold and as the precision fallback. The fallback therefore uses the existing demotion ceiling (S-GEN-050). The cost is that the human re-promotes by hand. In exchange, no GEN change is needed.
6. **Knowledge-drafting eval tasks:** a task is one source bundle with its labelled rules, so the carried counts of 50 and 30 labelled rules are spread over bundles.
7. **staff-product `schemas/` and `checks/`:** these directories are added to the plugin layout. S-GEN-025 lists them as authored by nobody but the human.
8. **New IDs for meaning changes (S-BA-010):** this makes stale downstream citations detectable by script, at the cost of more retired IDs.
9. **Contradiction step 5** reads CI results instead of probing an environment, to stay within the $0.50 / 5 min reviewer cap.
10. **Test-condition authorship (S-BA-050):** the Analyst writes test conditions, and S-QA-010 keeps it that way. The Analyst already works in the requirement's path and context, and the human accepts the conditions by merging.
11. **Tracker:** it supports labels, webhooks and comment authorship, and CI can read comment authors. Any tracker with these features works.
12. **Carried starting values** (`docs/decisions.md`, 2026-11-20):
    - knowledge drafting: 50 golden and 30 promotion labelled rules, rule precision ≥80%, batches of up to 10 rules, live precision over the last 30 rules;
    - the reviewer/requirements row and caps (S-GEN-045, S-GEN-057).
13. *(Retired: the `KD_SINGLE_RULE` variable is replaced by the demotion-ceiling fallback in S-BA-044.)*
14. **Context budget (S-BA-052; decided, `docs/decisions.md`, 2026-11-20):** 15k tokens per pack, measured as chars/3.2. The cap for the part above the `## On-demand reference` header is (15k − measured shared/ tokens) × 3.2 (S-GEN-009). shared/'s closing sections are on demand (`docs/decisions.md`, 2026-11-20), so the shared/ figure counts only its decisions. BA keeps a margin of at least about 3.2k chars under the cap.

    Figures as of the last measurement; the release gate re-measures (S-BA-052, S-GEN-009):
    - **shared/ (always-loaded part):** 13,257 chars, about 4.14k tokens;
    - **cap:** about 34,745 chars;
    - **always-loaded part:** 22,795 chars, about 11.27k tokens with shared/;
    - **reviewer/requirements pack** (plus S-BA-029 to -032): 26,969 chars, about 12.57k tokens with shared/;
    - **`analyst-interview` static part** (S-BA-007, -055, -056): 4,614 chars, about 5.58k tokens with shared/.
15. **Check-emitted outcome records (S-BA-054):** the nightly BA check emits `check_outcome` records (S-GEN-031) through the recorder, which ingests CI job outputs (S-GEN-026). The `Staff-Run-Id` trailer, and how it is read, are common to every role (S-GEN-029).
16. **Round 4 values, accepted** *(starting value, `docs/decisions.md`, 2026-11-20)*:
    - test-condition edit-rate window: last 20 (S-BA-047);
    - interview guide: at most 10 topics; session timebox: 60 min; interviewer caps: $5 and 75 min (S-BA-055, S-BA-038);
    - window for a `defect` revision entry after a confirmed defect item: 7 days (S-BA-054).
17. **Live interview mechanics (S-BA-055 to S-BA-057):**
    - **Sandbox:** the interviewer reuses the S-GEN-066 sandbox profile. The launch wrapper and the post-session hand-off take the eval runner's place, so the sandbox holds no tokens and can't write anything.
    - **Committing the transcript:** the human commits it. That gives a second redaction check by a person who was present, and it gives no agent a path to write unbounded free text.
    - **Redaction risk in Git:** the GEN reason in S-GEN-012 still applies. A missed redaction stays in Git history until the human rewrites it (S-DATA-008). The decision to save the transcript as the source accepts that risk, and the human's commit review mitigates it. The S-GEN-012 carve-out covers human-committed elicitation transcripts.
    - **Hosting:** S-GEN-004 allows interactive mode for `analyst-interview`. DevOps supplies the launch path (S-DEVOPS-025).
18. **Round 5 values, accepted** *(starting value, `docs/decisions.md`, 2026-11-20)*: `analyst-interview` eval row: 12 golden sessions, guide-topic coverage ≥90%, and the three hard limits (asserted facts 0, speaker-tag integrity 100%, failed-redaction handling 100%) (S-BA-040).
19. **Withdrawn implementation (S-BA-023):** on a `withdrawn` S-DEV-044 event, the default is to flag the affected rules and never auto-retire them. A revert is often temporary, and retiring a rule that is correct again after a re-merge would break its citations (S-BA-010). The human retires a rule with `retired_reason: behaviour changed` when the withdrawal is final.
    - **Test identity:** `verifying_checks`, the stale-rule check and the S-BA-043 lane guard use test ID v1 (S-DEV-045) and the S-DEV-028 rename mapping. That gives BA and DEV one test identity, so a moved test is never counted as a lost check.

## Open dependencies

- **OD-BA-1 (test engineer): closed by S-QA-007, -010, -025 and -028.**
  - **Test conditions v1** are confirmed, and authorship stays with the Analyst (S-QA-010).
  - **Citations:** tests cite AC and R-IDs in a form the trace check reads (S-QA-007).
  - **`changes`:** QA reads declared rule changes from the field (S-QA-010, -028).
  - **Retired IDs:** tests that cite a retired ID are re-pointed (S-QA-025).
  - **Ready ACs only:** QA triggers start only on ready ACs (S-QA-010).
- **OD-BA-2 (developer): closed by S-DEV-007, -009 and -044.** Product PRs declare the REQ and AC IDs they implement in a machine-readable field (S-DEV-009). The implementation status (S-DEV-044) triggers knowledge drafting (S-BA-023) and supplies a trace link. Developer triggers start only on ready ACs (S-DEV-007).
- **OD-BA-3 (architect, developer, test engineer): closed by S-ARCH-006, -015, -017, -029; S-DEV-007, -008, -017; S-QA-010, -011.** ADRs cite the REQ IDs they address, especially quality requirements. Agents of these roles raise requirement problems as requirement-defect items (S-BA-048), not as free comments. Their triggers start only on ready ACs (S-BA-019).
  - **Architect part:** closed by S-ARCH-006, -015, -017 and -029.
  - **Developer part:** closed by S-DEV-007, -008 and -017.
  - **Test engineer part:** closed by S-QA-010 and -011.
- **OD-BA-4 (test engineer): closed by S-QA-031.** The label that means "the rule and the behaviour disagree" is `qa:source-wrong`, and the stale-rule check reads it (S-BA-025).
- **OD-BA-5 (DevOps): closed by S-DEVOPS-017, -020, -021, -024 and -029.**
  - tracker webhook routing to the BA workflows, with the event classes and the `operators.yml` actor check (S-BA-034): S-DEVOPS-017;
  - read-only tracker access for product CI, so the owner-field check can confirm comment authors (S-BA-015): S-DEVOPS-021;
  - a human-authored export job that delivers redacted production-derived content to an agent-readable location (S-BA-028): S-DEVOPS-029;
  - the BA checks running as required checks under OD-SEC-2 (S-BA-051): S-DEVOPS-020;
  - BA read stages in the `read` launcher variant: S-DEVOPS-024.
- **OD-BA-6 (DevOps): closed by S-DEVOPS-025**, with the `interactive` variant of S-DEVOPS-024. It covers the interactive launch path for `analyst-interview` (S-BA-055):
  - **launch wrapper:** a human-dispatched CI job outside the sandbox, holding only a short-lived per-job staff-product read token (S-SEC-008) that never reaches the sandbox. It runs the G6 preamble (switches, effective stage, cost cap) and stops on any failure. It fetches and redacts (S-BA-028) the guide, the product core and the intake, and publishes them as a single-session bundle for the sandbox. It checks that the bundle's injected inputs fit the budget left after the static part of the `analyst-interview` pack, and fails closed if they don't (S-GEN-009, S-BA-052). It emits the opening `agent_run` record through the recorder;
  - **sandbox:** S-GEN-066 token and egress limits, the model endpoint from `.staff/product.yml`, and placement per S-DATA-003;
  - **session harness:** tags speakers, enforces the interviewer turn schema, redacts every human turn, enforces the timebox and caps, and records per-turn timing events and a run record;
  - **post-session hand-off:** a human-dispatched CI job that completes the opening record and sends the timing events through the recorder (S-GEN-026, S-GEN-071), and delivers the redacted transcript to the human for commit.
- **OD-BA-7 (general strategy): closed by S-GEN-004.** S-GEN-004 now allows the human-launched interactive sandbox mode for `analyst-interview`, with the launch wrapper and hand-off of S-BA-055.

## Open questions

- [x] Secondary seeded defects in the S-GEN-045 row? Not now: the row stays as it is and is revisited after real reviewer results (`docs/decisions.md`, 2026-11-20).
- [x] Live sessions or asynchronous batches? Both: a live kickoff per new area, then asynchronous batches (`docs/decisions.md`, 2026-11-20; S-BA-055 to S-BA-057).
- [ ] When is a seeded mode for knowledge drafting worth its cost? Synthetic source bundles with planted rules would give its hidden set both guards (S-GEN-068).
- [ ] Is the stage-1 demotion fallback for knowledge drafting (S-BA-044) too heavy in practice? If it is, GEN could add a per-agent batch ceiling to S-GEN-017, -026 and -069.
