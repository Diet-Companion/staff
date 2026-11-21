# Agentic Strategy — General (GEN)

Updated Nov 20, 2026

## Purpose and scope

This is the frame every role strategy plugs into. It covers how one human runs a project with agent staff, where everything lives, who may do what, and how agent results are measured, promoted and paid for. It is product-agnostic and stack-agnostic.

Topics that touch every discipline are stated only in shared/: security (S-SEC), testability (S-TESTAB) and data residency (S-DATA). This doc references them by ID. QA-only content (the healer table, mutation, test layers, the oracle rule) waits for the test engineer strategy. `docs/test-automation-strategy.md` (the legacy doc) stays as its source.

Markers:
- *(starting value)*: accepted by the human in `docs/decisions.md` (2026-11-20). These are revisited after the first measured results.
- *(proposed)*: awaiting human confirmation. No *(proposed)* item is open.

Named tools are examples.

## Operating model

- **S-GEN-001** One human operator runs the project with agent staff for five roles: business analyst, architect, developer, DevOps and test engineer (`docs/decisions.md`). The human owns business rules, priorities, scope, budget and every merge. Agents draft, generate, run, review and repair.
- **S-GEN-002** Staff is product-agnostic and stack-agnostic. Product facts live only in the product repo (S-GEN-011). Tests on each layer use the stack of the app code on that layer (`docs/decisions.md`). Other agent-written artifacts follow the product's existing stack and conventions.
- **S-GEN-003** No agent merges anything, in any repo, at any stage. Every merge needs the human's code-owner approval through branch protection (S-SEC-008). This generalises the no-auto-merge decision (`docs/decisions.md`, 2026-11-20). *Depends on:* S-SEC-008, S-GEN-025.
- **S-GEN-004** Platform and hosting:
  - Agents run on Claude, with one skill set per agent, headless in ephemeral CI jobs.
  - The CI is GitHub Actions *(starting value)*. Any CI with concurrency groups, branch protection and code owners works.
  - Runners are hosted or self-hosted. Self-hosted runners are used where test environments are private, and runner placement follows S-DATA-003.
  - Skills and learnings live in Git, so nothing needs always-on hosting. A separate service (Claude Agent SDK in a container) is added only for a measured long-running or cross-repo need.
  - **Interactive mode, the one exception to headless runs.** It is allowed only for `analyst-interview` (S-BA-055), and only the human launches it. Three parts make it up:
    - **Launch wrapper:** a human-dispatched CI job. It holds a short-lived per-job read token (S-SEC-008) that never reaches the sandbox. It runs the G6 preamble and stops on any failure. It publishes the redacted inputs as a bundle valid for one session. Through the recorder, it emits an opening `agent_run` record with status `open` and the agent's per-run cap as reserved `cost_usd`, so the cost job counts the session from the start.
    - **Sandbox:** the S-GEN-066 profile, in its interactive variant. It starts only from that bundle, holds only the model credential, reaches only the model endpoint (S-DATA-002), and has no write tools. Its host is placed per S-DATA-003.
    - **Post-session hand-off:** a human-dispatched CI job. It completes the opening record with the actual status and cost, and delivers the timing events through the recorder (S-GEN-026, S-GEN-071). The digest lists every session still `open` 2 h after its timebox ends *(starting value, `docs/decisions.md`, 2026-11-20)* (S-GEN-063).

    Any other agent that needs interactive mode needs an amendment to this decision.

  *Depends on:* S-DATA-002, S-DATA-003, S-SEC-008, S-GEN-026, S-GEN-029, S-GEN-058, S-GEN-063, S-GEN-066, S-GEN-071, S-BA-055, OD-BA-6.
- **S-GEN-005** Each agent starts on its own event: a ticket change, a PR event, a CI failure or a schedule. There is no single linear pipeline. Role strategies define the triggers. *Depends on:* OD-GEN-1.

## Strategy system

- **S-GEN-006** The doc set lives in the staff repo: `docs/strategy/agentic-strategy.md`, `docs/strategy/shared/<topic>.md` and `docs/strategy/roles/<role>.md` (`docs/decisions.md`). The decisions log `docs/decisions.md` sits beside it, and only the human writes to it.
- **S-GEN-007** Every decision has an ID (`S-<AREA>-NNN`) and declares its dependencies. Open dependencies are labelled `OD-<AREA>-<n>`. When a decision changes, the reviewer checks the decisions that depend on it in other strategies (`docs/decisions.md`). The ID, OD and marker rules are in the `strategy-authoring` skill.
- **S-GEN-008** There is one strategy designer, with a skill per discipline, in staff-meta. Strategy review is the `strategy` artifact type of the shared reviewer in staff-review: one checklist per doc type, plus the cross-strategy consistency check. There is no designer/reviewer pair per role (`docs/decisions.md`). *Depends on:* S-GEN-013.
- **S-GEN-009** Working agents load their own role strategy plus the shared/ decisions as always-loaded context (`docs/decisions.md`; the shared/ closing sections are on demand, per the 2026-11-20 amendment). They don't load this doc. The GEN rules that bind them at runtime reach them through the staff-core guardrails skill (S-GEN-020). A role strategy's always-loaded part plus the always-loaded shared/ part stays within 15k tokens *(starting value, `docs/decisions.md`, 2026-11-20)*. Detail beyond that moves to on-demand references.

  **Packaging rule** (clarification, `docs/decisions.md`, 2026-11-20; shared/ part as amended there, "closing sections of the shared/ docs"):
  - **Always loaded:** everything in the role doc before its "On-demand reference" header, plus the always-loaded shared/ part.
  - **Always-loaded shared/ part:** in every pack, each shared/ doc up to its first closing section. Content is not moved out of the shared/ docs; only the packaging changes.
  - **On demand:** the role doc's on-demand section, and the closing sections (Assumptions, Open dependencies, Open questions) of the role doc and of every shared/ doc.
  - **Measure:** characters / 3.2. The cap for the always-loaded role part is (15k − measured always-loaded shared/ tokens) × 3.2 characters.
  - **Reviewer pack:** a `reviewer/<type>` unit loads the role's always-loaded part plus its own checklist section from the role's on-demand reference. That pack, with the always-loaded shared/ part, is measured separately and must also fit within 15k.
  - **Agent pack:** a role may declare a pack per agent: the always-loaded part plus that agent's own sections of the on-demand reference, built the same way as a reviewer pack (for example S-QA-020). Each declared pack, with the always-loaded shared/ part, is measured separately and must also fit within 15k.
  - **Injected sandbox pack:** an agent that runs in the interactive sandbox (S-GEN-004) gets a narrow set instead of the always-loaded part. The role doc declares that set, and the launch wrapper injects it through the session bundle. An example is BA's `analyst-interview` pack (S-BA-052). The pack has two parts, checked at different times:
    - **Static part:** the declared role sections plus the always-loaded shared/ part. The packaging or release-gate check measures it.
    - **Injected inputs:** at launch, the launch wrapper checks that the bundle's inputs fit the budget the static part leaves, and fails closed if they don't.

    Together they must fit within 15k.
  - **Re-measurement:** the packaging or release-gate check (S-GEN-021) re-measures every pack of a role whenever that role doc or anything under shared/ changes. That covers the always-loaded, reviewer and role-declared agent packs, and the static part of injected sandbox packs. The check fails closed when any pack is over 15k. Every addition to the always-loaded shared/ part lowers every role's cap, so a shared/ PR must show the re-measured packs of every existing role. Edits confined to shared/ closing sections don't change any cap.

  *Depends on:* S-GEN-004, S-GEN-020, S-GEN-021, S-GEN-048.

## Repo topology

- **S-GEN-010** Three repos plus two stores outside Git (`docs/decisions.md`, 2026-11-20), each with fixed readers and writers:

  | Store | Holds | Read | Write |
  | --- | --- | --- | --- |
  | `staff` repo (Git) | Plugins (agents, skills, learnings), governance, strategy docs and the decisions log, visible evals, run-record schema and metric definitions, ops job code, experiment log | All staff identities; the human | The human. The improver, strategy designer and eval runner may push only to `agent/*` branches inside their allowlists, via PR. The release job may only create tags. The shared reviewer may only comment on strategy PRs |
  | Product repo (Git) | Product artifacts (requirements, code, architecture, DevOps), product knowledge, contract files (`.staff/`), pinned plugin versions | Working agents, shared reviewer, release job, ops jobs, eval runner, seeding agent; the human | The human. Working agents and the release job may push only to `agent/*` branches inside their path scope, via PR. The shared reviewer may only comment and label. Ops jobs may write only the digest issue and strip labels (S-GEN-071) |
  | `staff-evals-private` (private Git repo) | Hidden sets, promotion sets, the seeded-bug catalogue and patches, seeded artifacts and defect specs, frozen charters, held-out labels, judge calibration labels, set assignments | Eval runner, seeding agent | Seeding agent (seeds, seeded artifacts); eval runner (set assignments) |
  | Eval-private object storage (prefix) | Per-task records, outputs and transcripts of hidden and promotion runs (S-GEN-065) | Eval runner only | Eval runner |
  | Outcome store (not Git) | Run records and verdicts for live and visible-set runs: CI artifacts at first, a small database later. Their transcripts, in access-controlled object storage. Aggregate records for hidden and promotion runs (S-GEN-065). Items released at rotation or retirement (S-GEN-041). Labelling timing records, without item references or label values (S-GEN-071) | Recorder, improver, ops jobs, eval runner; the human | Recorder only |

  *Depends on:* S-GEN-026, S-GEN-028, S-GEN-065.
- **S-GEN-011** Product knowledge (product core, rules registry, self-discovered knowledge) lives in the product repo, at the paths the product contract sets (S-GEN-017). Staff holds none. *Depends on:* S-GEN-017.
- **S-GEN-012** Run records and transcripts never go into Git. Concurrent appends conflict, a missed redaction would stay in history for good, and transcripts are large. Staff `metrics/` holds only the run-record schema and the metric definitions. Aggregate reports are generated from the outcome store, not committed, so they add no PRs. Redaction follows S-SEC-004 and retention follows S-DATA-007.

  **Carve-out:** interview transcripts that the human commits at product `requirements/*/sources/**` (S-BA-056) are requirement sources, not run transcripts. They are redacted twice and checked by the human before commit. The residual risk that a missed redaction persists in Git history is accepted by the human decision on live elicitation (`docs/decisions.md`, 2026-11-20; BA Assumptions item 17). Removal follows S-DATA-008. *Depends on:* S-SEC-004, S-DATA-007, S-DATA-008, S-BA-056.

## Staff repo layout

- **S-GEN-013** Layout:

  ```
  staff/
    docs/
      decisions.md              # human decisions log
      strategy/                 # agentic-strategy.md, shared/, roles/
    governance/
      product-contract.md       # required product repo layout
      guardrails.md             # shared rules for all agents (source of staff-core's guardrails skill)
      release-process.md
      operators.yml             # the human's account IDs, for verdict and actor checks (S-GEN-071)
      ops-config/               # model endpoint for staff workflows (S-DATA-002), switch defaults
    plugins/
      staff-core/               # guardrails skill, two-stage harness, run-record emitter, contract reader
      staff-product/            # business analyst
      staff-engineering/        # architect, developer, DevOps
      staff-qa/                 # test engineer
      staff-review/             # shared reviewer, one checklist skill per artifact type
      staff-meta/               # strategy designer, improver, seeding agent, LLM judge
      staff-domain-<domain>/    # domain knowledge, optional, one per domain
    evals/visible/<agent>/      # visible golden tasks only
    metrics/                    # run-record schema, metric definitions
    ops/                        # cost, switch, stage, eval runner, release, triage and recorder jobs
    experiments/                # experiment log
  ```

  Each plugin holds `agents/`, `skills/`, `learnings/<agent>.md` and a manifest (S-GEN-022). It may also hold:
  - `schemas/`, the versioned schemas it provides (S-GEN-022);
  - `checks/`, deterministic check scripts that run as required checks from a source the PR can't change (OD-SEC-2).

  staff-product holds both (S-BA-011).
- **S-GEN-014** Plugins per role:
  - business analyst: staff-product;
  - architect, developer and DevOps: staff-engineering;
  - test engineer: staff-qa.

  The cross-role plugins (core, review, meta, domain) are defined in this doc. *Depends on:* S-GEN-064.
- **S-GEN-015** Requirements review is `reviewer/requirements`, the `requirements` artifact type of the shared reviewer in staff-review. The business analyst strategy owns its checklist (`docs/decisions.md`, 2026-11-20). staff-qa has no requirements reviewer of its own. The checklist includes:
  - contradiction detection against the rules registry;
  - draft test conditions for QA, in a schema staff-qa consumes (S-GEN-022);
  - testability items that cite S-TESTAB IDs (S-TESTAB-009).

  *Depends on:* S-GEN-018, S-GEN-022, OD-GEN-8.
- **S-GEN-016** The product repo pins every installed plugin, and exactly one staff-core, by exact version in `.staff/plugins.lock`. Plugins are installed only from release tags of the staff repo. Floating versions are never used. *Depends on:* S-GEN-021.

## Governance

**Product contract**

- **S-GEN-017** `governance/product-contract.md` sets the minimum product repo layout:

  ```
  <product>/
    .staff/
      plugins.lock     # pinned plugin versions (S-GEN-016)
      product.yml      # residency and model endpoint (S-DATA-001, S-DATA-002), testability manifest (S-TESTAB-001)
      areas.yml        # path-to-area map (S-GEN-060)
      stages.yml       # human-set stage per agent per area; role priority order (S-GEN-050, S-GEN-072)
      code.yml         # code paths, guard patterns, verification_config, test_list, generators (S-DEV-004)
      tests.yml        # QA test paths and per-layer settings (S-QA-005)
      delivery.yml     # pipeline, build, IaC and environment map (S-DEVOPS-004)
    qa/
      quarantine.yml   # quarantine registry, changed only through quarantine PRs (S-QA-029)
    knowledge/
      product-core.md
      rules/           # rules registry
      discovered/      # app map, state models, newly found rules
    AGENTS.md          # conventions per language and layer
    .github/CODEOWNERS
  ```

  The product repo holds these CI variables:
  - plugin switches (S-GEN-069);
  - demotion ceilings per agent per area (S-GEN-050);
  - throttle ceilings per agent (S-GEN-072);
  - pre-review switches per checklist (S-GEN-062).

  Nothing that affects security or residency is kept in a CI variable (S-GEN-069).

  Role strategies set the paths of role artifacts (requirements, ADRs, pipelines, infrastructure as code, tests). *Depends on:* OD-GEN-2.
- **S-GEN-018** Knowledge layers:

  | Layer | Contents | Where | Owner |
  | --- | --- | --- | --- |
  | Product core (always loaded, 1–3 pages) | Glossary, roles and permissions, 5–10 core journeys *(starting value)*, business invariants, fragile areas | `knowledge/product-core.md` | Human |
  | Rules registry | Atomic rules with IDs (R-042), each linked to its source ticket, code and verifying checks | `knowledge/rules/` | Human |
  | Domain knowledge | The regulation and standard clauses that apply, domain glossary, invariants, risk heuristics, last-reviewed date | `staff-domain-<domain>` plugin. Human-authored; agent drafts are advisory | Human (domain expert role) |
  | Live sources (on demand) | Code, specs, tests, tickets, bug history, docs, ADRs, support tickets (redacted, S-DATA-004) | Repo and approved connectors (S-SEC-007) | Existing owners |
  | Self-discovered | App map, state models, newly found rules | `knowledge/discovered/`, via reviewed PRs | Agent-drafted, human-approved |

  *Depends on:* S-GEN-017, S-DATA-004, S-SEC-007.
- **S-GEN-019** Every change to the product core, the rules registry or self-discovered knowledge arrives as a reviewed PR. Agents treat rules as truth, so a wrong rule is worse than a missing one. Every rule is either active or retired. A rule is flagged as stale for review when a code or spec change leaves it without verifying checks, or makes those checks contradict it. *Depends on:* S-GEN-018.

**Guardrails**

- **S-GEN-020** These guardrails apply to every staff agent. Their source is `governance/guardrails.md`, which is packaged into staff-core. Every plugin depends on staff-core (S-GEN-022).

  | # | Guardrail | Enforced by |
  | --- | --- | --- |
  | G1 | No agent merges (S-GEN-003) | Branch protection; token scope |
  | G2 | Agents write only through PRs from `agent/*` branches, inside their plugin's path scope. Workflow-changing PRs come from a fork instead (S-SEC-006) | Token scope; a scope lint in CI fails PRs outside the scope (OD-GEN-2) |
  | G3 | Never remove or weaken a verification artifact (a test assertion, lint rule, gate threshold, checklist item or CI check) to make output pass. Any such diff needs explicit human sign-off. An agent stays at stage 1 until every artifact type it changes has its diff check | Diff checks per artifact type in CI (OD-GEN-9); CODEOWNERS on config paths; the stage check (S-GEN-050) |
  | G4 | Agents propose changes to skills, learnings and guardrails but never merge them. Core, meta, governance, evals and metrics are human-authored | Improver allowlist (S-GEN-027); per-identity push rulesets (S-GEN-025) |
  | G5 | Every run emits a run record | staff-core harness; recorder (S-GEN-029) |
  | G6 | Before starting, check the switches, the effective stage and the cost cap | CI preamble in every staff and product agent workflow (S-GEN-050, S-GEN-069) |
  | G7 | Run only on relevant paths | CI path filters from `areas.yml` |
  | G8 | Untrusted content (S-SEC-001, S-SEC-002) | Harness schema validation; separate read and write jobs with separate tokens |
  | G9 | Credentials, egress, tools (S-SEC-005 to S-SEC-010) | Token scope per job; environment-scoped secrets; runner egress policy; tool allowlist in agent definitions |
  | G10 | Environments (S-TESTAB-002) | Environment provisioning in CI; test-only credentials |
  | G11 | Data (S-DATA-002, S-DATA-004) | Model endpoint in human-only config, plus the egress allowlist; redaction step in the harness |
  | G12 | Only the human gives verdicts. Agents never write, edit or apply verdict labels or digest checkboxes | Recorder actor check and label-strip job (S-GEN-071) |

  *Depends on:* S-GEN-022, S-GEN-025, S-GEN-027, S-GEN-050, S-GEN-069, S-GEN-071, OD-GEN-2, OD-GEN-9.

**Release process**

- **S-GEN-021** Each plugin has its own semantic version and a changelog. The release job cuts the tag on a staff `main` commit. It does so only after the `release-gate` CI check passes. The check fails in two cases:
  - an agent the commit changed has no eval report that passes the regression rule (S-GEN-036);
  - any pack is over 15k: always-loaded, reviewer, role-declared agent (for example S-QA-020) or the static part of an injected sandbox pack (S-GEN-009).

  Pack measurement is also a required check on every staff PR that touches `docs/strategy/**`, so a shared/ PR shows every role's packs before it merges. *Depends on:* S-GEN-009, S-GEN-036, S-GEN-026.
- **S-GEN-022** Each plugin manifest declares two things:
  - the staff-core versions the plugin was evaluated with;
  - the schema versions it provides to other plugins and consumes from them. For example, staff-qa consumes the test-conditions schema of reviewer/requirements.

  The lock check in the product repo fails if any installed plugin's staff-core range or consumed schema isn't satisfied. A staff-core release re-runs the evals of every plugin before that plugin declares the new version (cost: S-GEN-070). The one exception is a patch confined to `governance/operators.yml`, which changes no agent behaviour (S-GEN-071). *Depends on:* S-GEN-016, S-GEN-070.
- **S-GEN-023** Rollback is per plugin: re-pin the previous version, or turn the plugin switch off. If the older version needs an older staff-core or schema, the lock check fails and the human decides what else to roll back. The run record carries every plugin's version (S-GEN-029), so each result is traced to the exact set. *Depends on:* S-GEN-016, S-GEN-022, S-GEN-029.
- **S-GEN-024** Pin bumps arrive as PRs from the release job and change only `.staff/plugins.lock`. The human merges them. *Depends on:* S-GEN-026.

**CODEOWNERS**

- **S-GEN-025** The human is the code owner of every path in both repos, and only the human edits CODEOWNERS files. The map below sets which identity, besides the human, may author changes to each path. Per-identity push rulesets and a CI path check enforce it.

  | Repo | Path | May also be authored by |
  | --- | --- | --- |
  | staff | `docs/decisions.md`, `governance/**`, `plugins/staff-core/**`, `plugins/staff-meta/**`, `plugins/staff-domain-*/**`, `plugins/*/agents/**`, `plugins/*/schemas/**`, `plugins/*/checks/**` (including staff-product's, S-BA-011), `metrics/**`, `ops/**`, `.github/**` | Nobody |
  | staff | `evals/visible/**` | Eval runner (rotation and visible assignments, S-GEN-037) |
  | staff | `docs/strategy/**` | Strategy designer |
  | staff | Paths on the improver allowlist (S-GEN-027) | Improver |
  | product | `.staff/plugins.lock` | Release job |
  | product | Other files under `.staff/`, and `.github/CODEOWNERS` | Nobody |
  | product | `.github/workflows/staff-*`, the product's platform workflows (S-DEVOPS-004) | Nobody |
  | product | `knowledge/**` | staff-product agents (knowledge drafting) |
  | product | `knowledge/discovered/**` | staff-product agents and staff-qa agents (exploratory) |
  | product | `requirements/*/sources/**` | Nobody: human-committed interview transcripts (S-BA-056) |
  | product | All other paths | The working agents whose path scope covers them (OD-GEN-2). CI and pipeline paths also fall under S-SEC-006 |

  *Depends on:* S-GEN-027, OD-GEN-2.

## Identities and tokens

- **S-GEN-026** Each identity gets its own token, with the scopes below and nothing more (S-SEC-008):

  | Identity | Reads | Writes | Never |
  | --- | --- | --- | --- |
  | Working agents (one app per plugin that has agents: product, engineering, qa) | Product repo, own plugin, tracker | In the product repo: `agent/*` branches, PRs, comments and labels inside the plugin's path scope. Tracker comments and drafts | Staff repo, private eval stores, outcome store |
  | Shared reviewer (staff-review app) | Product repo; in staff, `docs/strategy/**` and `docs/decisions.md`; tracker | Comments and labels on product PRs and tickets, and on strategy PRs in staff | Branches in any repo, private eval stores, outcome store |
  | Improver | Staff repo, outcome store | `agent/*` branches and PRs in staff, inside S-GEN-027 | Private eval stores, product repo writes |
  | Eval runner (it launches the judge's sandbox job but never shares its tokens with it, S-GEN-042) | Staff repo, `staff-evals-private`, eval-private object storage, pinned product builds and snapshots, labelling events with their values (S-GEN-071), `governance/operators.yml` from the pinned staff-core | Set assignments and label values in `staff-evals-private`. Eval-private object storage. Aggregate eval records and dropped-label-event records (actor, timestamp, batch ID; no values) through the recorder. `agent/*` branches and PRs in staff touching only `evals/visible/**`. Eval-report comments on skill PRs | Product repo writes; any other staff path |
  | Seeding agent | Staff repo, product repo, `staff-evals-private` | `staff-evals-private` only | Outcome store, eval-private object storage, repo branches, PRs |
  | Recorder | CI job outputs; webhook events for verdicts (S-GEN-071); `governance/operators.yml` from the pinned staff-core | Outcome store (append-only) | Repos, private eval stores |
  | Ops jobs (cost, switch, stage, throttle, triage, label strip) | Outcome store; label and issue events; `governance/operators.yml` from the pinned staff-core | The switches (S-GEN-069), demotion and throttle ceilings, pre-review switches. The daily digest issue in the product repo. Removing `verdict:*` labels that any other actor applied (S-GEN-071) | `.staff/stages.yml`; verdicts; any other repo write |
  | Release job | Staff repo, release-gate results | Tags in staff. `agent/*` branch and PR in the product repo, `.staff/plugins.lock` only | Everything else |
  | Strategy designer | Staff repo | `agent/*` branches and PRs in staff, `docs/strategy/**` only | Everything else |

  The strategy designer and the improver are separate identities. Agents under eval and the LLM judge hold none of these tokens (S-GEN-066, S-GEN-042).
- **S-GEN-027** Improver path allowlist:
  - `plugins/{staff-product,staff-engineering,staff-qa,staff-review}/skills/**`
  - `plugins/{staff-product,staff-engineering,staff-qa,staff-review}/learnings/**`
  - `experiments/**`

  Every other path is closed to it. That includes its own plugin (staff-meta), staff-core, agent definitions, domain plugins, governance, evals, metrics, ops and docs. So the improver can't change its own grading, tools or guardrails. *Depends on:* S-GEN-025.
- **S-GEN-028** Blinding rule, needed because the human is also the skill author:
  - The human has no standing read access to `staff-evals-private` or eval-private object storage.
  - The seeding agent writes seeded bugs, seeded artifacts and clean artifacts.
  - Every seeding batch and every human-labelled batch is assigned at random by the eval runner across visible, hidden and holdout. For seeded items the assignment is never reported.
  - Hidden and promotion tasks are scored only by script (S-GEN-041).
  - LLM-judge re-checks use visible and live items only.
  - Break-glass access is logged, and it rebuilds every set the human opened.

  **Residual risk:** random assignment hides which set an item is in, not what it contains. For human-labelled items, the visible-assignment PR also shows the human which items of a batch went visible, and so which went hidden. For label-based agents, S-GEN-068 applies. *Depends on:* S-GEN-037, S-GEN-038, S-GEN-041, S-GEN-042, S-GEN-068.

## Outcome store and run record

- **S-GEN-029** Every agent run emits one run record, a JSON object. Verdicts are appended later as update records with the same `run_id` (S-GEN-071):

  `record_kind (S-GEN-031), run_id, identity, plugin, agent, area, stage, status (open / completed / timeout / cap_hit / crashed / skipped_by_switch / redaction_dropped), skill_version, plugin_versions {plugin: version}, read_schema_version, model, judge {model, prompt_version}, trigger {type, ref}, input_refs, output_refs, label, rule_ids, app_version (build digest), seeded_bug_set (evals, opaque ID), eval_set (visible / hidden / promotion), human_verdict, verdict_by, verdict_at, tokens_in, tokens_out, cost_usd, duration_s, transcript_ref, experiment_id, variant (skill / baseline), role {…}`

  Role strategies add fields only inside `role`. The common fields are fixed here.

  `open` is used only for interactive sessions between the opening record and the hand-off (S-GEN-004).

  **`Staff-Run-Id` trailer.** Every agent commit carries a `Staff-Run-Id: <run_id>` trailer, which links each artifact to the run that drafted it. This generalises the BA convention (S-BA-054) to every role.
  - **Agent commits** are commits by the working-agent, shared-reviewer, improver and strategy-designer identities (S-GEN-026). The shared reviewer normally makes none.
  - **Enforcement:** in the product repo, the G2 scope lint fails an agent commit without the trailer. In staff, the S-GEN-025 CI path check does.
  - **Exempt:** release-job and eval-runner commits. They are not agent runs and have no `run_id`. Their PRs touch only `.staff/plugins.lock` or `evals/visible/**`.
  - **Reading:** a check job that links artifacts to runs (`check_outcome`, S-GEN-031) reads the run IDs from the merged PR's commits through the code host API, keyed by the PR, not from commit messages on `main`. So the human's merge method isn't constrained: a squash merge or a PR with several runs still resolves.

  *Depends on:* S-SEC-003, S-GEN-004, S-GEN-020, S-GEN-025, S-GEN-026, S-GEN-042, S-BA-054.
- **S-GEN-030** In run records, eval sets, stages and caps, an "agent" is one eval unit: one agent definition with one skill set. Each reviewer checklist is its own unit (`reviewer/<artifact-type>`).
- **S-GEN-031** The recorder stores records only after redaction (S-SEC-004). Each record names its `record_kind`:

  | Kind | What it is |
  | --- | --- |
  | `agent_run` | An agent run, including interactive sessions (S-GEN-004) |
  | `verdict_update` | A human verdict (S-GEN-071) |
  | `timing` | A labelling or interview-turn event, with timing only (S-GEN-071) |
  | `check_outcome` | Outcomes or findings that a human-authored check job derives from the repo and emits through the recorder (for example S-BA-054, S-ARCH-052) |
  | `eval_aggregate` | A blind-eval aggregate (S-GEN-065) |
  | `ops_event` | A stage change, switch flip, promotion attempt or dropped event |

  **`check_outcome` records** come in two forms. Both carry `run_id` set to the check job's own run ID, so deletion per S-DATA-008 still works, plus `check {name, version}`:
  - **Linked:** `drafting_run_id` comes from the artifact's `Staff-Run-Id`, read per merged PR (S-GEN-029). These records feed the drafting agent's metrics and stage triggers. Two granularities are allowed:
    - one record per artifact, with `artifact_id` (for example S-ARCH-052);
    - one record per drafting run, with no `artifact_id` and per-run counts in `role` (for example S-BA-054).
  - **Unlinked:** `drafting_run_id` is empty, for nightly findings that no agent run produced. Examples are drift findings (S-ARCH-027, -052) and nightly trace findings (S-BA-021). They carry `artifact_id` and are keyed by `finding_key` = (check name, artifact ID, finding kind), with the snapshot `date` alongside. A finding whose key was already present in the check's previous successful snapshot is a repeat, not a new finding. A failed or skipped night doesn't reset the repeat count.
    - **Digest:** unlinked findings are grouped into one item per check per area. Each item shows new findings, repeats and the age of the oldest repeat.
    - **Metrics:** they never count toward any agent's metrics or stage triggers. Only role metrics that a role strategy defines as snapshot metrics read them.

  Transcripts of live and visible-set runs sit next to their verdicts, for the improver and for debugging. *Depends on:* S-SEC-004, S-GEN-010, S-GEN-029, S-GEN-063, S-GEN-065, S-DATA-008.
- **S-GEN-032** Common metrics, defined in staff `metrics/`. The windows are *(starting value)* unless marked otherwise. Role strategies add role metrics (OD-GEN-7).

  | Metric | Formula |
  | --- | --- |
  | Acceptance rate | Agent PRs merged / agent PRs closed (merged + rejected), last 20 PRs |
  | Edit rate | Merged agent PRs with human commits / merged agent PRs, last 20 PRs |
  | Revert rate | Merged agent PRs reverted or redone within 14 days / agent PRs merged, last 20 |
  | Review precision | Findings confirmed / findings issued, last 30 findings |
  | Output precision (stage 1 verdicts) | Outputs confirmed by human verdict / outputs with a verdict, last 20 |
  | Cost per useful output | Cost of all runs in the window / accepted PRs, confirmed bugs or confirmed findings |
  | Human review minutes per day | Sum over the day's verdict, labelling and interview-turn events (S-GEN-071), counted per item. For an interview turn, the item becomes ready at the preceding interviewer turn. First, elapsed = verdict_at − max(the human's previous review event, item ready). If elapsed ≤ C, the item counts elapsed. If elapsed > C, it counts F when the item became ready before the previous event (the human was likely idle), and C otherwise. Before S-GEN-073 uses the metric as a gate, C and F are fitted once against one week in which the human times their own reviews. Until then, C = 30 min and F = 10 min. The rule and both values are *(starting value, `docs/decisions.md`, 2026-11-20, as clarified for general round 5)* |

  *Depends on:* S-GEN-071, OD-GEN-7.

## Eval method

The eval method is defined once, here. Each agent's eval row lives in the strategy that owns its plugin.

- **S-GEN-033** Measurement is built first. The run record, the baseline runner, the N-run script and the cost job exist before any agent result counts.
- **S-GEN-034** Every experiment also runs the same task with plain prompting or without the skill (the baseline). That way "the skill helped" is measured, not assumed.
- **S-GEN-035** N = 5 runs per variant *(starting value)*. Scores are pooled over task × run trials, not taken as a median of per-run scores. The per-run range is reported alongside.
- **S-GEN-036** Regression rule *(starting value, pooled form accepted in `docs/decisions.md`, 2026-11-20)*, computed on the visible and hidden sets combined:
  - **Regression:** on any primary metric, the new pooled score is more than 5 percentage points below the baseline, or the new per-run range lies entirely below the baseline range.
  - **Improvement:** the pooled score is more than 5 points better, and the hidden set alone does not regress.
  - **Otherwise:** "no detectable difference".

  A gain on the visible set alone is reported as possible overfitting. *Depends on:* S-GEN-035, S-GEN-037.
- **S-GEN-037** Each golden set is split 70% visible (`staff/evals/visible/`) and 30% hidden (`staff-evals-private`) *(starting value)*. The split is stratified by task kind, and every kind with at least 2 tasks has at least one hidden task. Every 6 weeks *(starting value)* the eval runner rotates the split: hidden tasks move to visible through a PR touching only `evals/visible/**`, which the human merges. New hidden tasks come from the seeding agent, or from random assignment of human-labelled batches (S-GEN-028). *Depends on:* S-GEN-025, S-GEN-028.
- **S-GEN-038** Promotion set: a separate held-out set per agent, on top of the golden set.
  - It covers every task kind the agent's stage 1→2 thresholds need, in golden-set proportions.
  - Bug tasks use only holdout-catalogue seeds. Non-bug tasks (clean artifacts, scripted breakages) are written for the promotion set and held out the same way.
  - Holdout seeds and held-out non-bug tasks never appear in visible or hidden tasks, so rotation can't leak them.
  - It never rotates and scores only stage promotions.
  - Per-task results go to eval-private object storage (S-GEN-065).
  - Every attempt is logged. The set is rebuilt after 3 failed attempts *(starting value, `docs/decisions.md`, 2026-11-20)*, on a suspected leak, or when product drift makes its tasks stale.
  - Minimum sizes are in each agent's eval row.

  *Depends on:* S-GEN-039, S-GEN-044, S-GEN-065.
- **S-GEN-039** Seeded-bug catalogue:
  - **Entries:** each seed has an ID, a category, the affected rule ID, the expected symptom, a machine-checkable spec (S-GEN-067) and the seeding skill version.
  - **Holdout:** a third of the catalogue *(starting value)* is never used while building or tuning skills. It only feeds promotion sets.
  - **Size:** the catalogue holds at least three times the holdout bug tasks of all promotion sets combined. For the agent set carried over from the legacy doc, that is ≥162 entries *(starting value, `docs/decisions.md`, 2026-11-20)*. Each new agent's promotion bug tasks add three times their count. For example, `mutant-drafter`'s 10 promotion tasks with holdout seeds add 30 entries (S-QA-049).
  - **Rebuilds:** a rebuild retires the used holdout seeds, and the seeding agent adds as many new ones as the promotion set has bug tasks.

  *Depends on:* S-GEN-028, S-GEN-067.
- **S-GEN-040** Seeding modes. Seeds are read only at scoring time.

  | Mode | Fits | Blinding |
  | --- | --- | --- |
  | Diff-seeded | Agents that read a diff and code | The bug sits unmarked in a realistic task PR. History, branch names, commits and comments carry no hint |
  | Image-seeded | Black-box agents that see only the running product | A build job publishes the seeded build under an opaque tag. Inputs (such as charters) are frozen before seeding |
  | Artifact-seeded | Reviewers of tickets, ADRs, pipeline configs, strategy docs | The seeding agent writes the defects into realistic artifacts. The human neither writes nor reads them before scoring |

  Each role strategy picks a mode per agent. *Depends on:* S-GEN-028, OD-GEN-3.
- **S-GEN-041** Scoring. A script matches agent outputs (failing checks, draft tickets, findings) to seed specs.
  - **Visible tasks:** the human confirms matches and gives verdicts on unmatched outputs.
  - **Hidden and promotion tasks:** the script's result is final. An ambiguous match counts as a miss. An output that matches no seed, including any finding on a clean artifact, counts as a false positive. This biases precision and false-positive rates against the agent; the bias is accepted, because those sets exist to be blind.
  - **Later review:** when a hidden task rotates to visible, or a promotion set is retired at a rebuild, the eval runner releases that task's unmatched and ambiguous items and seed specs, redacted (S-SEC-004), to the outcome store. The human reviews them there. The eval-private retention clock starts at release (S-DATA-007).

  *Depends on:* S-GEN-028, S-GEN-065, S-SEC-004, S-DATA-007.
- **S-GEN-042** LLM judge (staff-meta):
  - It is used only for quality rubrics, never for correctness that a run can decide.
  - Before use, it must agree with the human on ≥80% of 30 human-labelled items per rubric *(starting value)*.
  - Afterwards, the human re-checks 10% of its scores *(starting value)*, drawn from visible and live items only.
  - Its model and prompt version are pinned and recorded (S-GEN-029).
  - It reads agent outputs, which are untrusted (S-SEC-001), so S-SEC-002 applies to it. It runs in its own sandbox job, which holds only the model credential, the item being scored and the rubric. It returns a score validated against a schema, with no free text for hidden or promotion items. The eval runner's tokens never reach that job.

  *Depends on:* S-GEN-028, S-SEC-001, S-SEC-002.
- **S-GEN-043** Every eval run starts from a pinned build and a data snapshot (S-TESTAB-003, S-TESTAB-004). Golden tasks replay past tickets and PRs where possible. *Depends on:* S-TESTAB-003, S-TESTAB-004.
- **S-GEN-044** Every agent has an eval row: golden size, promotion-set minimum, seeding mode, oracle, primary metrics, stage 1→2 thresholds, hard limits and judge use. The row lives in the strategy that owns the agent's plugin: role strategies for role plugins, this doc for staff-review and staff-meta. An agent without a row stays at stage 1. *Depends on:* OD-GEN-3.
- **S-GEN-045** Eval rows for the cross-role agents:

  | Agent | Golden tasks | Promotion set minimum | Mode | Oracle | Primary metrics | Stage 1→2 threshold | Hard limits | LLM judge |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | reviewer/requirements | 30 tickets: 15 seeded with contradictions, 15 clean *(starting value)* | 20 tickets: 10 seeded with holdout contradictions, 10 held-out clean *(starting value)* | Artifact-seeded | Findings matched to defect specs (S-GEN-041) | Precision, recall | Precision ≥70%, recall ≥60% *(starting value)* | No edit to the artifact; schema-valid output in every run | Yes, for rewording and question quality |
  | reviewer/<other type> (default until the owning role sets its own row) | 30 artifacts: 15 seeded, 15 clean *(starting value, `docs/decisions.md`, 2026-11-20)* | 20: 10 seeded with holdout seeds, 10 held-out clean *(starting value)* | Artifact-seeded | As above | Precision, recall | Precision ≥70%, recall ≥60% *(starting value)* | As above | Per checklist |
  | LLM judge | 30 human-labelled items per rubric | The 30-item calibration set, labelled per S-GEN-068 | None | Matches the human score | Agreement | ≥80% *(starting value)* | Pinned model and prompt | n/a |
  | Improver | Judged by the visible and hidden sets of the agent it changes | n/a | As that agent | Regression rule | That agent's primary metrics | No promotion: every PR needs the regression rule and human approval | Touches only S-GEN-027 paths | No |

  The seeding agent and the strategy designer have no eval row and no stage. The seeding agent's quality is tracked by the seed-validity rate (S-GEN-067). Every strategy change is reviewed by reviewer/strategy and the human. A reviewer is advisory at every stage; meeting its threshold only qualifies it for pre-review (S-GEN-062). *Depends on:* S-GEN-041, S-GEN-062, S-GEN-067, S-GEN-068.
- **S-GEN-065** Eval records of hidden and promotion runs are split by sensitivity (`docs/decisions.md`, 2026-11-20):
  - Per-task records, outputs and transcripts go to the eval-private object-storage prefix, which only the eval runner can read. Retention follows S-DATA-007.
  - The outcome store gets only aggregate records per agent, per set and per skill version, keyed by opaque set IDs. Each one carries the scores, summed `cost_usd` and tokens, and counts per `status` (`docs/decisions.md`, 2026-11-20), with no per-task detail. The eval runner writes one at the end of every eval run, so the cost job (S-GEN-058) and the triage digest (S-GEN-063) count blind runs too.
  - Eval reports on skill PRs show per-task detail for visible tasks and aggregates for hidden ones. Promotion reports show aggregates only.

  *Depends on:* S-DATA-007.
- **S-GEN-066** Agents under eval run in a sandbox job:
  - It holds the model endpoint credential, plus test-only credentials for the pinned eval environment where the agent runs the product (S-TESTAB-004).
  - It holds no repo, tracker, private-store or outcome-store token.
  - Its egress is limited to the model endpoint, the eval environment and the package mirror. It has no route to the code host or tracker.
  - The eval runner injects the task inputs, and the harness captures what the agent would have written (PRs, comments, labels) instead of posting it.

  This sandbox profile can be reused outside eval runs, with a launcher taking the eval runner's place. The same launcher (S-DEVOPS-024) also runs the S-SEC-007 `read` stage. That stage is not an S-GEN-066 profile: it holds read-only code-host and tracker tokens. Its interactive variant (S-GEN-004) is narrower:
  - it holds no test-environment credentials, and its egress reaches only the model endpoint;
  - it starts only from the single-session bundle the launch wrapper publishes;
  - its only output is the transcript, which the post-session hand-off takes over.

  *Depends on:* S-TESTAB-004, S-SEC-007, S-GEN-004, S-DEVOPS-024.
- **S-GEN-067** Every seed and clean artifact carries a machine-checkable spec:
  - **Diff and image seeds:** a scripted symptom check that fails on the seeded version and passes on the corrected one.
  - **Artifact seeds:** a defect spec: location, the rule or ID it violates, and the corrected text.
  - **Clean artifacts:** a declaration that no defect was seeded.

  **Seed-validity rate:** seeds and clean artifacts confirmed valid by human verdict / those reviewed, last 40. Only seeds that land in the visible set are reviewed. Every batch is assigned at random (S-GEN-028), so the visible seeds are an unbiased sample. They are about half of all seeds: two-thirds are non-holdout, and 70% of those are visible. Items released after rotation or retirement (S-GEN-041) are added to the sample. The threshold is ≥95%. Both values are *(starting value, `docs/decisions.md`, 2026-11-20)*. Below the threshold, the seeding skill is fixed, and the hidden and promotion sets built with that seeding version are rebuilt. *Depends on:* S-GEN-028, S-GEN-037, S-GEN-041.
- **S-GEN-068** Label-based agents are knowledge drafting, the equivalence filter and the LLM judge. Their human-labelled hidden set guards only against the improver, not against the human. The human has seen every item, and the visible-assignment PR shows which items of a batch went hidden (S-GEN-028). The guard against the human is the promotion set:
  - Promotion sets for these agents are built only from batches labelled after the skill version under promotion was frozen, for example from live verdicts.
  - Hidden sets use seeded items wherever a seeding mode exists. Seeded items keep both guards.

  *Depends on:* S-GEN-028, S-GEN-038.

## Self-improving loop

- **S-GEN-046** The loop runs per agent:
  1. **Work:** the agent runs in CI.
  2. **Record:** run records and verdicts are stored.
  3. **Reflect:** a weekly improver finds patterns and proposes edits to skills or learnings, within the PR cap in S-GEN-070.
  4. **Gate:** the edit arrives as a PR. The eval runner scores it on the agent's visible and hidden sets. It merges only if it passes the regression rule and the human approves.

  *Depends on:* S-GEN-027, S-GEN-036, S-GEN-070.
- **S-GEN-047** The improver reads transcripts and outcome text, which are untrusted (S-SEC-001), so S-SEC-002 applies to it. *Depends on:* S-SEC-001, S-SEC-002.
- **S-GEN-048** Every always-loaded file keeps a fixed size limit. The improver moves aging detail into on-demand references instead of growing the file.
- **S-GEN-049** Every experiment is logged in `staff/experiments/` with one template: **hypothesis · setup · versions · baseline · number of runs · what the agent produced · false positives and misses · cost and time · reviewer time spent · conclusion · next step.**

## Rollout stages

- **S-GEN-050** How stages work:
  - The human sets each agent's stage per area in `.staff/stages.yml`, which only the human edits.
  - A daily ops stage job evaluates the demotion triggers from run records (`agent`, `area`, `stage`). When one fires, it writes a demotion ceiling per agent per area as a CI variable.
  - The effective stage is the lowest of three values: `stages.yml`, the demotion ceiling and the throttle ceiling (S-GEN-072). Every agent workflow computes it before starting. The ops jobs cannot raise a stage above `stages.yml`.
  - To promote, the human raises `stages.yml` and clears the demotion ceiling. Lifting a throttle never clears a demotion.
  - Every change to a stage or ceiling is written to the outcome store.

  *Depends on:* S-GEN-017, S-GEN-026, S-GEN-029.
- **S-GEN-051** Before stage 2, an agent must:
  - meet its stage 1→2 thresholds on its promotion set;
  - beat its baseline under the regression rule;
  - have its testability prerequisites in place (S-TESTAB-001);
  - have a diff check for every artifact type it changes (G3).

  *Depends on:* S-GEN-020, S-GEN-036, S-GEN-038, S-TESTAB-001.
- **S-GEN-052** Stage table. Values are *(starting value, `docs/decisions.md`, 2026-11-20)*, generalised from the legacy doc:

  | Stage | What the agent may do | Promote when | Demote when |
  | --- | --- | --- | --- |
  | 1 Advisory | Comment and draft only | Promotion-set scores meet the stage 1→2 thresholds in 2 consecutive eval runs; ≥20 human verdicts with output precision ≥70% | n/a |
  | 2 Proposing | Open PRs. Every PR gets a full review | Acceptance ≥70% over the last 20 PRs; the role's stage-2 quality metrics hold (OD-GEN-5); no guardrail breach merged | Acceptance <50% over the last 20 PRs, a guardrail breach merged, or a role-specific trigger (OD-GEN-5) → stage 1 |
  | 3 Light-review lane | PRs inside the role's narrow change class (S-GEN-053) get one-click human approval from a daily batch summary | Lane revert rate ≤5% over the last 20 lane PRs, sustained for 4 weeks | Lane revert rate >10% over the last 20, or one critical miss defined by the role → stage 2 |
  | 4 Wider scope | Same permissions in more areas | n/a | Any demotion trigger in an area → that area back to stage 2 |

  *Depends on:* S-GEN-032, S-GEN-050, OD-GEN-5.
- **S-GEN-053** Stage 3 is a light-review lane with human approval, never auto-merge (`docs/decisions.md`, 2026-11-20). Each role strategy defines its eligible change class, which must be narrow, mechanical and covered by a guard check. A role that defines none tops out at stage 2. *Depends on:* S-GEN-003, OD-GEN-5.
- **S-GEN-054** Rollback at any stage means re-pinning the previous plugin version (S-GEN-023) or turning the agent's workflow off (S-GEN-069). *Depends on:* S-GEN-023, S-GEN-069.
- **S-GEN-055** Autonomy grows per agent and per area, one area at a time.
- **S-GEN-073** Rollout across roles goes one role and one area at a time. The next role starts only once the human's review minutes per day (S-GEN-032) average ≤60 over 10 working days *(starting value, `docs/decisions.md`, 2026-11-20)*, once that metric is calibrated. One-off labelling work is scheduled in batches and counted in the same metric: calibration sets, labelled rules, seed-validity verdicts and stage-1 verdicts. The human chooses which role goes first (Open questions). *Depends on:* S-GEN-032, S-GEN-055.

## Cost

- **S-GEN-056** Every agent has a per-run cost cap and a wall-clock cap. They are enforced with turn limits and job timeouts and checked against the run record. Role strategies set the caps for role agents (OD-GEN-4). An agent without caps doesn't run. *Depends on:* S-GEN-029, OD-GEN-4.
- **S-GEN-057** Caps for the cross-role agents. Improver and reviewer/requirements are *(starting value)*. The rest are *(starting value, `docs/decisions.md`, 2026-11-20, general round 1)*.

  | Agent | Per run | Wall-clock |
  | --- | --- | --- |
  | Improver | $15 | 60 min |
  | reviewer/requirements | $0.50 | 5 min |
  | reviewer/<other type> (default) | $1 | 10 min |
  | LLM judge (per scored item) | $0.20 | 2 min |
  | Seeding agent | $5 | 30 min |
  | Strategy designer | $15 | 60 min |
- **S-GEN-058** The human sets one monthly cap across all agents (placeholder). A scheduled cost job sums the run records.
  - **At 80%** *(starting value)*: it alerts the human. It also turns off `EVALS_ENABLED` and `IMPROVER_ENABLED` *(starting value, `docs/decisions.md`, 2026-11-20)*.
  - **At 100%** *(starting value)*: it turns off `AGENTS_ENABLED`.

  The sum includes the aggregate records of blind eval runs (S-GEN-065). When a new budget month starts, the cost job turns back on only the switches it turned off for budget. Switches the human turned off stay off. *Depends on:* S-GEN-029, S-GEN-065, S-GEN-069.
- **S-GEN-059** Every eval trial runs under its agent's per-run cap, and eval spend counts toward the monthly cap. *Depends on:* S-GEN-056, S-GEN-058.
- **S-GEN-069** Switches. Every staff and product workflow checks them in its G6 preamble:
  - `AGENTS_ENABLED`: every agent and meta workflow in all three repos.
  - `EVALS_ENABLED`: the eval runner and the judge.
  - `IMPROVER_ENABLED`: the improver.
  - `<PLUGIN>_ENABLED`: one per plugin.

  They are org-level CI variables, or the same variables set in each repo when the repos are not in one org. CI-variable write scope is granted per repo or org, not per variable, so the ops token alone cannot limit what it writes. The real controls are:
  - the ops job code is human-authored (`ops/**`, S-GEN-025) and writes only switches, ceilings and pre-review switches;
  - every flip is written to the outcome store and listed in the digest;
  - nothing that affects security or residency lives in a CI variable. The model endpoint is in human-only config (S-DATA-002).

  *Depends on:* S-GEN-025, S-GEN-026, S-DATA-002.
- **S-GEN-070** Eval cost control:
  - **Worst case per skill PR:** (visible + hidden tasks) × N × the agent's per-run cap, plus judged items × N × the judge cap. For example, test generation (unit): 20 × 5 × $5 = $500. reviewer/requirements: 30 × 5 × $0.50 = $75, plus 30 × 5 × $0.20 = $30 for the judge.
  - **Worst case per promotion attempt:** promotion tasks × N × the per-run cap. For example, 10 × 5 × $5 = $250 per test-generation layer.
  - **Worst case per staff-core release:** the sum of the per-skill-PR worst case over every agent.
  - **Baseline cache:** baseline runs are cached per (model, baseline definition, task-set version). They re-run only when one of those changes, so a skill PR pays for one variant.
  - **Skill PR budget, per agent:** 60% of that agent's worst case per skill PR *(starting value, `docs/decisions.md`, 2026-11-20)*. For example, $300 for test generation (unit) and $63 for reviewer/requirements. The eval runner stops at the budget and marks the PR "eval incomplete", which blocks merge. The human may raise the budget for one PR with a label. Once 20 skill PRs of an agent have measured costs, the fraction is revisited against the mean.
  - **Improver PR cap:** at most 1 skill PR per agent per week *(starting value, `docs/decisions.md`, 2026-11-20)*.
  - **staff-core releases:** batched, at most 1 per month, except security fixes *(starting value, `docs/decisions.md`, 2026-11-20)*.

  *Depends on:* S-GEN-035, S-GEN-056, S-GEN-057.

## Day-to-day operations

- **S-GEN-060** Concurrency:
  - Each agent workflow runs in a CI concurrency group keyed by area (`.staff/areas.yml`). Runs are queued, not cancelled.
  - Before opening a PR, an agent checks every open `agent`-labelled PR from any plugin. If one touches the same paths, it adds its change there as a comment instead of opening a second PR. A PR stacked on another PR's branch, such as a test PR based on its product PR, builds on that PR and doesn't count as overlapping it (S-QA-019).

  *Depends on:* S-GEN-017.
- **S-GEN-061** Review load. The human holds every review and triage role. Daily caps (`docs/decisions.md`, 2026-11-20):
  - **Working-agent PRs:** 5 per day *(starting value)*, including knowledge PRs.
  - **Meta PRs:** a separate cap of 2 per day, covering skill, strategy and pin-bump PRs. Eval-set PRs (S-GEN-037) count here too.
  - **Stage-3 batches:** a batch summary counts as one working-agent PR and holds at most 10 PRs *(starting value, `docs/decisions.md`, 2026-11-20)*.
  - **Queue order:** PRs over the cap queue in arrival order, and the human can reorder them by label.
  - **Advisory output:** comments, findings and draft tickets go into the daily digest, not one notification each.

  *Depends on:* S-GEN-052.
- **S-GEN-062** Pre-review. Before an agent PR reaches the human, the shared reviewer runs the matching checklist on it and posts the findings as an advisory comment.
  - Only checklists that have met their stage 1→2 threshold pre-review.
  - The ops job turns a checklist's pre-review switch off when its review precision falls below 70% over the last 30 findings *(starting value, `docs/decisions.md`, 2026-11-20)*.
  - Skill PRs get the eval report instead.

  *Depends on:* S-GEN-032, S-GEN-045, S-GEN-069.
- **S-GEN-063** Triage. The ops jobs post one daily digest issue in the product repo, listing:
  - runs with status timeout, cap_hit or crashed, including the status counts in blind-eval aggregates (S-GEN-065);
  - dropped verdict, label and timing events, and stripped verdict labels (S-GEN-071);
  - interactive sessions still `open` 2 h after their timebox (S-GEN-004);
  - cost alerts and switch flips;
  - demotions;
  - redaction_dropped records (S-SEC-004);
  - testability gaps (S-TESTAB-001);
  - private security pointers (S-SEC-011);
  - escalations defined by role strategies;
  - queued PRs;
  - advisory items awaiting a verdict.

  *Depends on:* S-GEN-026, S-GEN-029.
- **S-GEN-071** Verdict capture. The human gives verdicts in three ways:
  - by merging or closing a PR;
  - by applying a verdict label (`verdict:confirmed`, `verdict:rejected`, `verdict:duplicate`, `verdict:unclear`) on a PR, ticket or comment;
  - by ticking a checkbox in the daily digest issue.

  A webhook starts a recorder job, which turns each event into a verdict update record (`human_verdict`, `verdict_by`, `verdict_at`). Labelling work emits one timestamped event per item, so labelling enters the review-minutes metric (S-GEN-032). Its records are split so that held-out labels can't leak (S-GEN-068):
  - **Labelled items** (calibration items, labelled rules, any batch that feeds random assignment): the outcome store gets only a timing record, with actor, timestamp, opaque batch ID and event kind. It has no item reference and no label value. The label values go only to the eval runner, which writes them into `staff-evals-private` before assignment (S-GEN-028). The eval runner applies the same `governance/operators.yml` actor check to every label event it ingests. It drops events from any other actor and records each drop through the recorder, without the label value, so the drop appears in the digest (S-GEN-063).
  - **Seed-validity verdicts** on visible seeds, and on items released after rotation or retirement (S-GEN-041, S-GEN-067): these stay full verdict records.
  - **Interview-turn events** (`timing`, S-GEN-031): the session harness records one per human turn, with actor, timestamp, session `run_id` and event kind, and no turn content. The post-session hand-off delivers them to the recorder (S-GEN-004, S-BA-057). The recorder accepts them only from a hand-off run that an account in `governance/operators.yml` dispatched, and only for a session whose opening record is still `open`. It drops any other delivery and lists the drop in the digest.

  Agents never write verdicts (G12). Two checks enforce that:
  - **Recorder actor check:** the recorder accepts a verdict or label event only if its actor is one of the human's accounts in `governance/operators.yml`. That covers the merge, the label event and the edit of the digest issue. Every other event is dropped, and each drop is listed in the digest.
  - **Where the account list comes from:** the release job packages `operators.yml` into staff-core, so the recorder and the ops jobs read it from the pinned staff-core and need no staff repo token. A staff-core diff confined to `governance/operators.yml` is an eval-free patch release, and every plugin's staff-core range accepts it without re-running evals (S-GEN-022).
  - **Label strip:** an ops job removes every `verdict:*` label applied by any other actor, and logs the removal.

  *Depends on:* S-GEN-025, S-GEN-026, S-GEN-029.
- **S-GEN-072** Back-pressure:
  - **Working-agent PRs:** when more than 10 are queued, the ops job sets the throttle ceiling to 1 for every agent of the lowest-priority role (S-GEN-050). That role's agents then put drafts in the digest and open no PRs. Other roles in the same plugin are not affected. The ceiling is lifted when the queue drops below 5. The lowest-priority role is the most recently rolled-out one, until the human sets an order in `.staff/stages.yml` (`docs/decisions.md`, 2026-11-20).
  - **Meta PRs:** when more than 4 are queued, the improver pauses.

  The values (10, 5, 4) are *(starting value, `docs/decisions.md`, 2026-11-20)*. *Depends on:* S-GEN-017, S-GEN-050, S-GEN-061, S-GEN-069.

## Role index

- **S-GEN-064** Every role strategy honours the common set:
  - S-GEN-001 to -005, -009 and -016 to -017;
  - S-GEN-020 to -044;
  - S-GEN-050 to -073;
  - every S-SEC, S-TESTAB and S-DATA decision. These are always loaded; the closing sections of the shared/ docs are on demand (S-GEN-009).

  Agent lists are indicative; each role strategy fixes its own.

  | Role | Area | Plugin | Working agents | Also honours | Delivers for shared/ |
  | --- | --- | --- | --- | --- | --- |
  | Business analyst | BA | staff-product | Analyst (drafts and refines requirements and acceptance criteria); knowledge drafting (product core, rules registry); `analyst-interview` (live kickoff interview, the only interactive agent, S-GEN-004) | S-GEN-015 (owns the requirements checklist), -018, -019 | S-TESTAB-006 (acceptance criteria, rules); requirements checklist testability items (S-TESTAB-009) |
  | Architect | ARCH | staff-engineering | Architect (ADRs, components, interface specs, quality scenarios); `arch-upkeep` (component `code_paths` and the overview). Owns the checklist of `reviewer/architecture` in staff-review. Conformance is a check script, not an agent (S-ARCH-002) | S-GEN-018 | S-TESTAB-005, -006 (ADRs, specs), -007 and -008 by design; architecture checklist (S-TESTAB-009) |
  | Developer | DEV | staff-engineering | Developer (implements ready ACs, fixes confirmed defects, writes DEV unit tests); `dev-upkeep` (autofixes, codemod migrations, dependency patch and minor bumps). Owns the checklist of `reviewer/code` in staff-review (S-DEV-002) | S-GEN-019 | S-TESTAB-004, -005, -007 and -008 in code |
  | DevOps | DEVOPS | staff-engineering | DevOps (pipelines, IaC, environments, deploy steps, monitors and load runs for DEVOPS-owned QAS); `ci-upkeep` (pin bumps through the mirror, cache keys). Owns the checklist of `reviewer/pipeline` in staff-review (S-DEVOPS-002) | S-SEC-006 in depth | S-TESTAB-002 and -003; S-DATA-003 placement |
  | Test engineer | QA | staff-qa | `test-gen-unit`, `test-gen-api`, `test-gen-ui`; `ci-healer`; `exploratory`; `mutant-drafter`; `equivalence-filter`. The mutation gate is a check, not an agent. Owns the checklist of `reviewer/tests` in staff-review (S-QA-002) | S-GEN-015 (consumes test conditions); authors `knowledge/discovered/**` (S-GEN-025) | Consumes every S-TESTAB item |

  The cross-role plugins (staff-core, staff-review, staff-meta, staff-domain) are defined in this doc.

## Assumptions

Items 1–10 are reasonable defaults the designer made. Item 11 is retired; it is now a decision. Item 12 lists the human decisions of general rounds 1 and 2 that this doc applies. Item 13 lists the starting values carried over from the legacy doc. Item 14 lists the items reworked in round 3, which the human has since confirmed as starting values. Item 15 records the review-minutes rule confirmed after round 4. Item 16 records the open-session alert confirmed after round 8. Item 17 is a designer default. No *(proposed)* item is open.

1. **Outcome store form:** CI artifacts at first, then a small database. Transcripts of live and visible runs go to object storage. Aggregate reports are generated, not committed.
2. **Agent homes:**
   - developer agents in staff-engineering;
   - knowledge drafting in staff-product;
   - the seeding agent and the LLM judge in staff-meta;
   - `mutant-drafter`, the equivalence filter and the mutation gate (a check) in staff-qa;
   - domain knowledge in human-authored `staff-domain-<domain>` plugins.
3. **Strategy docs:** they live in `docs/strategy/` in the staff repo, matching the decided paths. Strategy review is `reviewer/strategy`.
4. **Product contract paths:** as in S-GEN-017. Role strategies add their artifact paths.
5. **Identities:** each plugin with agents gets one app identity. On top of the six identities in the context doc there are separate identities for the shared reviewer, the release job and the ops jobs. This keeps token scope aligned with path scope and limits a compromise to one discipline.
6. **Blinding mechanics (S-GEN-028, S-GEN-041, S-GEN-067, S-GEN-068):** these replace the legacy "a human confirms each match", which would expose hidden and promotion seeds to a human who is also the skill author.
7. **staff-core and schema compatibility:** plugins declare the staff-core versions and the schemas they were evaluated with. The product installs exactly one staff-core.
8. **Meta PR cap scope:** eval-set PRs (rotation and visible assignments) count toward the meta cap of 2 per day, next to the skill, strategy and pin-bump PRs the decision names.
9. **Placeholders:** the human sets the monthly cap. Residency and testability are set per product (S-DATA-001, S-TESTAB-001).
10. **Switch location:** org-level CI variables, or one copy per repo if the repos are not in one org.
11. *(Retired: the back-pressure default is now a decision, applied in S-GEN-072.)*
12. **Decisions applied** (`docs/decisions.md`, 2026-11-20):
    - **Round 1:**
      - three repos, with `staff-evals-private` as a private Git repo (S-GEN-010);
      - hidden and promotion records in eval-private object storage, with aggregates only in the outcome store (S-GEN-065);
      - reviewer/requirements in staff-review, with the checklist owned by BA (S-GEN-015);
      - caps of 5 working-agent PRs and 2 meta PRs per day (S-GEN-061);
      - the round 1 proposed values accepted as starting values: the 15k-token budget, the default reviewer row, and the default reviewer, judge, seeding agent and strategy designer caps.
    - **Round 2:**
      - the round 2 values accepted as starting values: seed validity, the rollout gate, the 80% evals and improver switch-off, the improver PR cap, staff-core release cadence, stage-3 batch size, the pre-review switch-off, and the back-pressure thresholds;
      - blind-eval aggregates carry cost, tokens and status counts (S-GEN-065);
      - the most recently rolled-out role is throttled first, through the per-role throttle ceiling (S-GEN-072).
13. **Carried starting values** (`docs/decisions.md`, 2026-11-20):
    - GitHub Actions;
    - 5–10 core journeys;
    - N = 5, pooled scoring, the 5-point margin;
    - a 30% hidden split rotated every 6 weeks;
    - one-third holdout and a catalogue of ≥162 entries;
    - promotion-set rebuild after 3 failed attempts;
    - the judge at ≥80% agreement on 30 items with a 10% re-check;
    - stage thresholds and metric windows;
    - the improver and reviewer/requirements caps;
    - the reviewer/requirements eval row;
    - the 80% alert and 100% kill switch.
14. **Confirmed after round 3** *(starting value, `docs/decisions.md`, 2026-11-20)*:
    - **Human review minutes (S-GEN-032):** per item, the time from the later of the human's previous verdict and the item becoming ready, to the verdict, capped at 30 min. Calibrated once against one week of self-timed reviews before it gates rollout. Item 15 refines this.
    - **Skill PR eval budget (S-GEN-070):** 60% of each agent's worst case per skill PR. This replaces the flat $200, which never bound for reviewers and bound at 40% for test generation. It is revisited after 20 measured skill PRs per agent.
15. **Confirmed after rounds 4 and 5** *(starting value, `docs/decisions.md`, 2026-11-20; supersedes the earlier F entry, as clarified for general round 5)*:
    - **Review-minutes rule:** as stated in S-GEN-032. Elapsed time counts up to C = 30 min. Only an item over C that became ready before the human's previous review event counts F = 10 min. C and F are fitted in the timed week. A long review of an item that arrived while the human was active counts C, not F, so the long-review undercount doesn't come back.
16. **Confirmed after round 8** *(starting value, `docs/decisions.md`, 2026-11-20)*:
    - **Open-session alert (S-GEN-004, S-GEN-063):** the digest lists an interactive session that is still `open` 2 h after its timebox ends. Until the hand-off completes it, the session's reserved cost (its per-run cap) counts toward the monthly cap.
17. **No merge-method rule:** run IDs are read from the merged PR's commits through the code host API (S-GEN-029), so squash merges keep working. A rule requiring merge commits or rebase merges would add nothing.

## Open dependencies

Every open dependency of this doc is now **fully closed**. Each entry lists the closing S-IDs per role.

- **OD-GEN-1 (all roles):** the triggers for each working agent (S-GEN-005). **Closed:** BA by S-BA-034, ARCH by S-ARCH-034, DEV by S-DEV-006, QA by S-QA-013, DEVOPS by S-DEVOPS-006.
- **OD-GEN-2 (all roles):** the path scope per plugin and per agent in the product repo, and the product-contract paths for role artifacts (S-GEN-017, S-GEN-020 G2, S-GEN-025). **Closed** (paths and agent scope):
  - BA by S-BA-011 and S-BA-035;
  - ARCH by S-ARCH-013 and S-ARCH-035;
  - DEV by S-DEV-004 and S-DEV-005;
  - QA by S-QA-005 and S-QA-014;
  - DEVOPS by S-DEVOPS-004 and -005, plus -003 (S-SEC-006 for pipeline paths).
- **OD-GEN-3 (all roles):** an eval row and seeding mode per agent (S-GEN-040, S-GEN-044). Carried values keep their starting values and citations, and label-based agents follow S-GEN-068. **Closed:**
  - **BA:** S-BA-040 and S-BA-041, which cover the Analyst, knowledge drafting and `analyst-interview`. Batch gating is in S-BA-044.
  - **ARCH:** S-ARCH-049, which covers the Architect and `arch-upkeep`.
  - **DEV:** S-DEV-036, which covers the Developer and `dev-upkeep`.
  - **QA:** S-QA-049 and S-QA-050, which carry the legacy rows and add `mutant-drafter`.
  - **DEVOPS:** S-DEVOPS-053.
- **OD-GEN-4 (all roles):** per-run caps per agent (S-GEN-056). **Closed:** BA by S-BA-038, ARCH by S-ARCH-039, DEV by S-DEV-033, QA by S-QA-045 (the legacy caps plus `mutant-drafter`), DEVOPS by S-DEVOPS-050.
- **OD-GEN-5 (roles whose agents open PRs):** stage-2 quality metrics, role demotion triggers, and the stage-3 change class with its critical-miss definition (S-GEN-052, S-GEN-053). **Closed:** BA by S-BA-043 and S-BA-044, ARCH by S-ARCH-050, DEV by S-DEV-037, QA by S-QA-051 (the legacy heal lane and triggers), DEVOPS by S-DEVOPS-054.
- **OD-GEN-6 (all roles):** read-stage schemas (see OD-SEC-1 in shared/security). **Closed:** BA by S-BA-037, ARCH by S-ARCH-037, DEV by S-DEV-021, QA by S-QA-026, -032, -035, -038, -039 and -044, DEVOPS by S-DEVOPS-013.
- **OD-GEN-7 (all roles):** role metrics with formulas (S-GEN-032). **Closed:** BA by S-BA-047 and S-BA-054, ARCH by S-ARCH-051 and S-ARCH-052, DEV by S-DEV-038 and S-DEV-039, QA by S-QA-052 and S-QA-053, DEVOPS by S-DEVOPS-055 and -056.
- **OD-GEN-8 (BA, ARCH, DEV, DEVOPS, QA):** checklist content for each role's artifact types in staff-review (S-GEN-015). **Closed:**
  - **BA:** the requirements checklist, S-BA-029 to S-BA-033.
  - **ARCH:** the architecture checklist, S-ARCH-031 to S-ARCH-033.
  - **DEV:** the code checklist, S-DEV-031 and S-DEV-032.
  - **QA:** the tests checklist, S-QA-043 and -044. The consumed test-conditions schema (test conditions v1, S-BA-048) is confirmed by S-QA-010.
  - **DEVOPS:** the pipeline checklist, S-DEVOPS-047 and -048.
- **OD-GEN-9 (all roles; QA first):** the diff checks that enforce G3 for each artifact type. **Closed:**
  - BA by S-BA-046 and S-BA-051;
  - ARCH by S-ARCH-044, S-ARCH-045 and S-ARCH-053;
  - DEV by S-DEV-018, S-DEV-027 to S-DEV-030, S-DEV-043 and S-DEV-045;
  - QA by S-QA-040 to S-QA-042, including the assertion-diff check and the cited-value lint;
  - DEVOPS by S-DEVOPS-042 to -046 and -049.
- **OD-GEN-10 (DEV, QA):** how unit-test writing is split between developer agents and QA test generation (agents write unit tests, per `docs/decisions.md`). **Closed:** DEV by S-DEV-014 and S-DEV-015, QA by S-QA-012.

## Open questions

- [ ] What is the monthly budget cap across all agents? S-GEN-070 gives the worst-case eval formulas to size it.
- [ ] Which role rolls out first, and in which area (S-GEN-073)?
- [ ] At what point, if any, does a separate agent service beat CI jobs?
