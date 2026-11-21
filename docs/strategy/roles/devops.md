# DevOps Strategy (DEVOPS)

Updated Nov 21, 2026

## Purpose and scope

This doc covers two things. The first is the product's own delivery: pipelines, environments, IaC, deploys and monitors. The second is the staff platform that every other strategy depends on: event routing, tokens, sandboxes, required checks, environments and placement. DEVOPS is the last role strategy (`docs/decisions.md`, 2026-11-20). It is product-agnostic and stack-agnostic (S-GEN-002). The CI is GitHub Actions *(starting value)* (S-GEN-004), and other named tools are examples.

It honours the common set in S-GEN-064, plus S-SEC-006 and -007 in depth. GEN, shared/ and role decisions are referenced by ID, never restated.

The part from "On-demand reference" on is not always loaded. Each DEVOPS agent loads a pack (S-DEVOPS-016). The platform (S-DEVOPS-017 to -034, and -058) is built and run by the human and by human-authored jobs. Agents retrieve it per trigger. The table of closed open dependencies is at the end of the reference.

Markers: *(starting value)* means accepted in `docs/decisions.md`; the round-1 and round-2 values were accepted on 2026-11-21 (Assumptions items 1 and 15). *(proposed)* means awaiting confirmation, and none is open.

## Ownership and agents

- **S-DEVOPS-001** Ownership split:
  - **The human** merges every change (S-GEN-003). The human also owns:
    - secrets, the credential vault and its minting policies (S-DEVOPS-018), and rulesets;
    - environments that hold real data;
    - every production plan, apply, deploy, rollback and export run (S-DEVOPS-022);
    - `.staff/delivery.yml` (S-DEVOPS-004), and every change to the controls of S-SEC-006 and -007.

    All platform code is human-authored (S-GEN-025): staff `ops/**` and `.github/**`, and the product's `staff-*` workflows.
  - **Agents** draft product pipeline, IaC, environment, monitor and load-run changes, keep product CI healthy, bump pins, review pipeline artifacts, and raise questions and design requests.

  No DEVOPS agent holds a production, deploy or real-data credential, or touches production state (S-SEC-005, -008). *Depends on:* S-GEN-001, S-GEN-003, S-GEN-025, S-SEC-005, S-SEC-006, S-SEC-007, S-SEC-008, S-DEVOPS-004, S-DEVOPS-018, S-DEVOPS-022.
- **S-DEVOPS-002** Agents and checks in staff-engineering (S-GEN-014). Each agent is its own eval unit (S-GEN-030):
  - **DevOps:** drafts product pipelines, IaC, environment definitions and deploy steps, plus the monitors and load runs for the QAS that DEVOPS owns (S-DEVOPS-040). It raises design requests and questions.
  - **`ci-upkeep`:** bumps the pins of actions, container images, runner images and IaC providers through the package mirror, and fixes cache keys. It is separate from DevOps because its trigger (the pin report), its eval (scripted tasks) and its stage-3 lane all differ, as for `dev-upkeep` (S-DEV-002).
  - **`reviewer/pipeline`:** the `pipeline` artifact type of the shared reviewer. This doc owns its checklist (S-DEVOPS-047).

  **Checks and jobs, not agents:**
  - The platform (S-DEVOPS-017 to -034, and -058) and the DEVOPS checks (S-DEVOPS-042 to -046) are human-authored scripts and jobs, because they are the controls agents are measured against (G3, G4).
  - Flaky infrastructure is found by a script, the platform health job (S-DEVOPS-033). Only confirmed recurring failures reach DevOps. Test failures stay with QA's healer (S-QA-028).

  *Depends on:* S-GEN-014, S-GEN-020, S-GEN-030, S-DEV-002, S-QA-028, S-DEVOPS-033.
- **S-DEVOPS-003** Identities. DevOps and `ci-upkeep` run as staff-engineering, and `reviewer/pipeline` as staff-review (S-GEN-026). All three use the two-stage split (S-SEC-002) with the schemas in S-DEVOPS-013. Their branches are `agent/devops/*` and `agent/ci-upkeep/*`, under the prefix lint (S-ARCH-003). DevOps and `ci-upkeep` work in the `work` sandbox (S-DEVOPS-024).
  - **Fork rule (S-SEC-006):** a PR that changes any file under `pipelines` (S-DEVOPS-004) comes from the DEVOPS fork (S-DEVOPS-019). Only these two agents' write-stage tokens carry the workflow-file permission, and only on the fork.
  - Their other PRs come from upstream branches.

  *Depends on:* S-GEN-026, S-SEC-002, S-SEC-006, S-ARCH-003, S-DEVOPS-004, S-DEVOPS-013, S-DEVOPS-019, S-DEVOPS-024.

## Delivery map and path scope

- **S-DEVOPS-004** Delivery map (closes the artifact-path part of OD-GEN-2 for DEVOPS). The human declares it in `.staff/delivery.yml`, which is human-only like every `.staff/` file (S-GEN-025). Its schema ships in staff-engineering `schemas/`. Keys:
  - `pipelines`: product CI/CD workflow and composite-action globs. These never include the `staff-*` platform workflows (`.github/workflows/staff-*`, "Nobody" in S-GEN-025);
  - `build`: build definitions (for example Dockerfiles), each producing a digest (S-TESTAB-003);
  - `iac`: per stack, `{paths, tool, validate, plan, parser, environments}`;
  - `environments`: `ephemeral` (the template), `staging-equivalent` and `production`. Each has its IaC stack, its data source (`synthetic` for all but production) and its control-seam and correlation settings (S-DEVOPS-041);
  - `deploy_units`: each mapped to the CMP IDs whose `deployment.unit` it carries (S-ARCH-007);
  - `migrations`: the migration command per stack (S-DEVOPS-038);
  - `monitors` and `load`: the monitor format, the load tool and their commands;
  - `pin_tool`: the command that rewrites pins to digests (S-DEVOPS-049);
  - `fork`: the registered DEVOPS fork (S-DEVOPS-019);
  - `exports`: the production-derived sources the export job may read (S-DEVOPS-029).

  The interim `monitor_where` key is retired: S-ARCH-009 now carries `verification.where` (S-DEVOPS-040).

  `build` and `iac` globs must not overlap the paths of `.staff/code.yml` or `.staff/tests.yml` (S-DEV-004, S-QA-005). The delivery check fails closed on an overlapping map, and DEVOPS read stages refuse to run until the human fixes it.

  Product-contract paths: `delivery/environments/<env>/**`, `delivery/monitors/QAS-n.<ext>`, `delivery/load/QAS-n.<ext>`, plus the declared `iac`, `build` and `pipelines` globs. DEVOPS checks read the map from the base branch. Without an entry, a DEVOPS read stage fails closed and the digest lists the gap. The one exception is `devops:bootstrap` (S-DEVOPS-006). *Depends on:* S-GEN-017, S-GEN-025, S-GEN-063, S-TESTAB-003, S-ARCH-007, S-DEV-004, S-QA-005, S-DEVOPS-019, S-DEVOPS-029, S-DEVOPS-038, S-DEVOPS-040, S-DEVOPS-041, S-DEVOPS-049, OD-GEN-2.
- **S-DEVOPS-005** Path scope (closes the agent-scope part of OD-GEN-2 for DEVOPS). The scope lint (G2) enforces it by branch prefix and head repository. It fails a DEVOPS commit without a `Staff-Run-Id` trailer (S-GEN-029).

  | Agent | Writes | Never writes |
  | --- | --- | --- |
  | DevOps | `pipelines`, `build` and `iac` globs; `delivery/**` | `staff-*` workflows and other platform files; `.staff/**`; `.github/CODEOWNERS`; other roles' paths (S-DEV-004, S-QA-005), `qa/quarantine.yml` included; production state |
  | `ci-upkeep` | Pin and cache-key lines in `pipelines`, `build` and `iac` files | Everything else. A needed change beyond pins becomes a draft DevOps ticket |
  | `reviewer/pipeline` | No paths: comments, private reports and the label `devops:not-ready` | Any path |

  The lint fails a fork PR whose head repository isn't the registered fork, or whose head branch isn't `agent/devops/*` or `agent/ci-upkeep/*`. *Depends on:* S-GEN-020, S-GEN-025, S-GEN-029, S-ARCH-003, S-DEV-004, S-QA-005, S-DEVOPS-004, S-DEVOPS-019, OD-GEN-2.

## Triggers and human-owned items

- **S-DEVOPS-006** Triggers (closes OD-GEN-1 for DEVOPS). The event classes are those of S-BA-034, as the router realises them (S-DEVOPS-017). Everything else is dropped.

  | Agent | Starts when |
  | --- | --- |
  | DevOps | An operator applies `devops:change` to a ticket. The post-merge delivery check sees a merged ARCH change that accepts a component or changes its `deployment`, or that accepts a QAS with `verification: monitor`, owner DEVOPS (S-DEVOPS-040). The nightly delivery check finds a gap: a monitor-owned QAS without a definition for each place its `where` names (S-DEVOPS-040), a deploy unit without an environment entry, or an environment missing a seam that its components mark `provided` (S-ARCH-025). An operator ticks an infrastructure item's checkbox in the digest (S-DEVOPS-033). An operator answers where it waits, or reviews its PR. A required check fails on its own PR, for at most 3 fix-up runs per PR *(starting value, `docs/decisions.md`, 2026-11-21)*; after that the digest lists it. An operator dispatches `devops:bootstrap`: it drafts the `.staff/delivery.yml` entry as a comment for the human to commit |
  | `ci-upkeep` | A weekly run *(starting value)* when the pin report (S-DEVOPS-049) has new items. An operator dispatches `devops:upkeep` with a target, or reviews its PR |
  | `reviewer/pipeline` | A DevOps or `ci-upkeep` PR becomes ready for review, or its review is re-requested. An operator applies `devops:review` to a human PR that touches delivery paths |

  *Depends on:* S-GEN-005, S-BA-034, S-ARCH-007, S-ARCH-025, S-DEVOPS-017, S-DEVOPS-033, S-DEVOPS-040, S-DEVOPS-049, OD-GEN-1.
- **S-DEVOPS-007** Human-owned:
  - the labels `devops:change` and `devops:review`, accepted only from accounts in `governance/operators.yml` (S-GEN-071);
  - the dispatches `devops:upkeep` and `devops:bootstrap`. They are operator dispatches of `staff-*` workflows only, and each workflow checks its triggering actor against `operators.yml` first (S-DEVOPS-017). A label with either name starts nothing;
  - `.staff/delivery.yml`;
  - sign-offs on flagged diffs and on `devops:dependency` PRs, in the S-ARCH-053 form;
  - answers to DEVOPS questions, counted as in S-BA-015;
  - approvals in the human-gated environments (S-DEVOPS-022).

  No DEVOPS agent applies or removes these labels or any `verdict:*` label (G12), and none dispatches a workflow. *Depends on:* S-GEN-020, S-GEN-071, S-BA-015, S-ARCH-053, S-DEVOPS-017, S-DEVOPS-022.
- **S-DEVOPS-008** Problems go back, never into infrastructure:
  - A QAS whose `measure` no monitor or load run can observe, or a deploy unit with no component, becomes a design request in the S-DEV-008 form, with `need: deployment` or `testability`.
  - A requirement problem becomes a requirement-defect item (S-BA-048).
  - A request that would weaken a control of S-SEC-006 or -007 becomes a question in the S-BA-014 form, never a PR.
  - A suspected vulnerability becomes a private report (S-SEC-011).

  Silence never decides. *Depends on:* S-SEC-006, S-SEC-007, S-SEC-011, S-BA-014, S-BA-048, S-DEV-008.

## PR contract and safety

- **S-DEVOPS-009** PR block and contract check. Every DevOps and `ci-upkeep` PR opens with its decision summary (S-DEVOPS-015), then a block in the delivery-PR schema (staff-engineering `schemas/`):
  - `kind`: `pipeline`, `iac`, `environment`, `monitor`, `load` or `upkeep`, plus `ticket`;
  - `cites[]`: QAS-n, CMP-n, ADR-n/C-k or IF versions;
  - `environments[]` touched, and `plan_refs[]` to the test-environment plans (S-DEVOPS-037);
  - `pins[] {name, from, to, signoff_ref}`, and `flags[] {flag_id, reason}`.

  The contract check fails a PR that has no summary or a schema-invalid block, has a prose field over 2,000 characters (S-SEC-002), targets a base other than `main`, covers more than one ticket, or changes more than 500 lines *(starting value)*, not counting lockfiles and plan output. ACs that DevOps work delivers are declared with an operator `implemented_acs[]` comment (S-DEV-044). *Depends on:* S-GEN-022, S-SEC-002, S-DEV-044, S-DEVOPS-015, S-DEVOPS-037.
- **S-DEVOPS-010** Safety, DEVOPS's share of G3:
  - Never remove, skip or neutralise a required check, widen `permissions:`, egress or a secret's reach, or loosen an IaC safeguard to make output pass. The diff checks (S-DEVOPS-042 to -044) flag or block each case, and every flag needs a sign-off.
  - Never plan, apply or deploy against production, and never read production state (S-DEVOPS-012, -037).
  - DevOps and `ci-upkeep` stay at stage 1 until every artifact type they change has its check (S-GEN-051).

  *Depends on:* S-GEN-020, S-GEN-051, S-SEC-006, S-SEC-007, S-DEVOPS-012, S-DEVOPS-037, S-DEVOPS-042, S-DEVOPS-043, S-DEVOPS-044.
- **S-DEVOPS-011** Cited thresholds are frozen, a local rule in the spirit of S-QA-009. Every monitor or load definition carries `cites: QAS-n`, and its threshold equals the QAS `measure`, unit included. The threshold changes only when the QAS is replaced (S-ARCH-012). The monitor check enforces it (S-DEVOPS-044). *Depends on:* S-ARCH-009, S-ARCH-012, S-QA-009, S-DEVOPS-044.
- **S-DEVOPS-012** Data boundary:
  - DEVOPS fetch steps and read stages apply the read-time redaction of S-BA-028 to every tracker and connector fetch.
  - DEVOPS agents never read production systems, state, logs or telemetry. Production monitor values reach only the human (S-DEVOPS-040).

  So OD-DATA-2 needs no DEVOPS part. *Depends on:* S-DATA-004, S-BA-028, S-DEVOPS-040.

## Schemas, output and load

- **S-DEVOPS-013** Read-stage schemas and write actions (closes OD-GEN-6 and OD-SEC-1 for DEVOPS). Prose fields hold at most 2,000 characters (S-SEC-002). `files[]` is derived from the workspace diff and passed in full, in ordered chunks, with the parse, scope and secret checks of S-DEV-021.

  | Agent | Read-stage output | Allowed write actions |
  | --- | --- | --- |
  | DevOps | `pr` (S-DEVOPS-009); `decision_summary`; `files[]` (harness-derived); `design_requests[]` (S-DEV-008 form); `defect_items[]` (S-BA-048); `questions[]` (S-BA-014 form); `assumptions[]`; `private_reports[]`; `delivery_map` (`devops:bootstrap` only); `source_refs[]` | Stage 1: comments as in S-DEVOPS-014, design requests, defect items, questions and private reports. Stage 2 adds: a branch and PR (S-DEVOPS-003), pushes to it, comments on its own PRs, and the labels `agent` and `devops:dependency` |
  | `ci-upkeep` | `pr`; `decision_summary`; `files[]`; `tool_runs[] {tool_id, version, paths[]}`; `handoffs[]` (draft DevOps tickets); `source_refs[]` | Stage 1: comments as in S-DEVOPS-014 and draft tickets. Stage 2 adds: a branch and PR, pushes to it, comments on its own PRs, and the labels `agent` and `devops:dependency` |
  | `reviewer/pipeline` | `target`; `reviewed_sha`; `verdict`; `findings[] {finding_id, checklist_id, severity, location, text, suggestion, cited_ids, classification}`; `questions[]`; `private_reports[]` | One comment per run, the label `devops:not-ready`, and private reports |

  A stage-1 draft or a push needs the `work` sandbox to show, for each kind it touches, that the change validates, its test-environment plan succeeds, and a changed pipeline passes its emulated run (S-DEVOPS-024). *Depends on:* S-SEC-002, S-SEC-003, S-SEC-011, S-BA-014, S-BA-048, S-DEV-008, S-DEV-021, S-DEVOPS-003, S-DEVOPS-009, S-DEVOPS-014, S-DEVOPS-024.
- **S-DEVOPS-014** Stage-1 output (comment and draft only, S-GEN-052). There is one comment per drafted PR, with the rendered decision summary, the full patch and the test-environment plan as CI artifacts (S-DATA-003). So each draft gets its own verdict (S-GEN-071). DevOps comments on the ticket. `ci-upkeep` posts one comment per pin group per run on one draft upkeep ticket per week, so each group gets its own verdict. Every comment carries its `run_id` in its machine-readable block (S-DEV-039). `verdict:confirmed` means the draft would merge as is. *Depends on:* S-GEN-052, S-GEN-071, S-DATA-003, S-DEV-039.
- **S-DEVOPS-015** Load (S-GEN-061, S-GEN-073):
  - DEVOPS PRs count toward the working-agent cap. At most 2 DevOps PRs await review at a time *(starting value)*. `ci-upkeep` opens at most 1 scheduled PR per week *(starting value)*. Fix-up pushes are not new PRs. Fork-PR runs awaiting the human's approval (S-SEC-006), and jobs waiting on an approval in a human-gated environment (S-DEVOPS-022), are listed in the digest as load.
  - **Overlap:** a run whose paths overlap an open agent PR waits, as in S-DEV-024, and the digest lists the wait.
  - Questions, design requests, infrastructure items and reviewer comments reach the human through the digest, one item per ticket or check.
  - **Decision summary**, first in every DEVOPS PR: cited IDs; flagged diffs; net changes to permissions, egress, secrets and environment bindings; pins with their sign-off refs; the plan summary per stack (adds, changes, destroys); the environments touched; the reviewer's verdict, the commit it reviewed and its open findings.

  *Depends on:* S-GEN-060, S-GEN-061, S-GEN-063, S-GEN-073, S-SEC-006, S-DEV-024, S-DEVOPS-022.
- **S-DEVOPS-016** Packs and retrieval (S-GEN-009, `docs/decisions.md`, 2026-11-20). Each DEVOPS agent loads its pack: the always-loaded part plus its own on-demand sections, as in S-QA-020. The packaging check (S-GEN-021) measures each pack with the always-loaded shared/ part, at chars/3.2, against 15k. The figures are in Assumptions item 2.

  | Pack | Own sections |
  | --- | --- |
  | DevOps | Product delivery (S-DEVOPS-035 to -041) |
  | `ci-upkeep` | Upkeep (S-DEVOPS-049) |
  | `reviewer/pipeline` | DEVOPS checks (S-DEVOPS-042 to -046); pipeline checklist (S-DEVOPS-047, -048) |

  Context, in addition to the always-loaded set in S-GEN-009:

  | Agent | Always loaded | Retrieved on demand |
  | --- | --- | --- |
  | DevOps | Product core; the `.staff/delivery.yml` entry; the delivery-PR schema; own learnings | The ticket; cited QAS, components and ADRs; pipeline, build, IaC and environment files; plan and emulated-run output; the pin report; check outputs; the decisions below |
  | `ci-upkeep` | The `.staff/delivery.yml` entry; own learnings | The pin report and approved-pin index; release notes (untrusted); the pinned files |
  | `reviewer/pipeline` | Its checklist (in its pack); the `.staff/delivery.yml` entry | The diff and PR block; plan summaries; check outputs; cited QAS, components and ADRs; the decisions below |

  The fetch step adds the other moved decisions an agent acts on, per trigger:

  | Agent and trigger | Retrieves |
  | --- | --- |
  | DevOps: pipeline work | S-DEVOPS-018 (credentials), -020 (check jobs), -022 (environments), -023 (runner pools), -042 to -046 (checks), -049 (approved pins) |
  | DevOps: IaC or environment work, an ARCH change or a gap finding | S-DEVOPS-026, -027 (environments), -028 (placement), -043, -044, -046 |
  | DevOps: a confirmed infrastructure item | S-DEVOPS-023, -033 (signatures), -042 |
  | DevOps: an answer, review or check failure on its PR | S-DEVOPS-042 to -046; the S-ARCH-053 sign-off form |
  | DevOps: `devops:bootstrap` | S-DEVOPS-028, -034 (bootstrap order), -052 (prerequisites) |
  | `ci-upkeep`: any run | S-DEVOPS-042, -046, -054 (lane class) |
  | `reviewer/pipeline`: any run | S-DEVOPS-018, -020, -022, -023, -026, -028, -035 to -038, -041 |

  If a pack goes over, more sections move (S-GEN-048). *Depends on:* S-GEN-009, S-GEN-021, S-GEN-048, S-QA-020.

## On-demand reference

### Platform: shared pieces

Each piece is defined once here. The closure table maps every role's request to it.

- **S-DEVOPS-017** Event router, with actor checks (S-BA-034's event classes, for every role). Each repo has one router: a human-authored `staff-router` workflow.
  - **Sources, base-context triggers only:** issue, comment, label and review events; `pull_request_target` for PR metadata only, never checking out PR code; pushes to `main`; schedules; `workflow_run`; and `workflow_dispatch`. It never uses `pull_request`. A tracker without native code-host events is polled every 5 min *(starting value, `docs/decisions.md`, 2026-11-21)*, with the read-only tracker credential (S-DEVOPS-021). The cursor and the dedup set are a CI artifact of the router, published as a full new version under one concurrency group; the latest wins. No inbound endpoint and no long-lived token sit in the tracker.
  - **Classes:** each event's class is decided only from its authenticated actor and event metadata, never from body text:
    - **Operator event:** the actor's account ID is in `governance/operators.yml`, read from the pinned staff-core (S-GEN-071).
    - **Operator dispatch:** a `workflow_dispatch` of a `staff-*` workflow (bootstraps, `devops:upkeep`, the interview launch and hand-off). The dispatched workflow itself checks its triggering actor against `operators.yml` before any other step, and stops and records the drop otherwise.
    - **Staff-app PR event:** the actor is a staff app identity (S-GEN-026), and the event is a PR becoming ready or a review re-request. It may start only the `reviewer/<type>` whose paths the PR touches.
    - **Check or schedule event:** a schedule, or a `workflow_run` that passes the provenance check below.
  - **Provenance check** for every `workflow_run`. The router verifies the triggering run's workflow path, which must be a protected source (an org-ruleset required-workflow path, or a `staff-*` file at the base ref, S-DEVOPS-020), plus its repository, event, `head_repository` and `head_branch`. It never matches by workflow `name:`.
    - **Event artifacts** (S-ARCH-054, S-DEV-044, S-QA-041) are accepted only from event workflows that have no `run` job, so no PR code ran in the run that published them.
    - **PR-context checks:** the target PR comes from the triggering run's PR number and head SHA, read through the code-host API, never from the artifact.
  - **Everything else** is dropped, recorded through the recorder as an `ops_event` (S-GEN-031), and listed in the digest.
  - **Start mechanism:** the router run calls each target as a reusable workflow, one conditional job per target, so it needs no dispatch token and no new identity. The target's own trust levels mint their credentials (S-DEVOPS-018).
  - **Routing table:** label prefixes (`ba:*`, `arch:*`, `dev:*`, `qa:*`, `devops:*`) and events map to role workflows, as the role trigger tables set (S-BA-034, S-ARCH-034, S-DEV-006, S-QA-013, S-DEVOPS-006). `verdict:*` events and digest edits go to the recorder, which applies its own actor check, and to the label-strip job (S-GEN-071). An operator verdict or digest checkbox that a role's trigger table names also starts that agent. The table is human-authored in staff `ops/` and shipped with staff-core, like `operators.yml`.
  - **Payload:** only `{event_class, kind, actor_id, target_ref, event_id}`. Targets re-read content through their fetch step. Duplicates are dropped by `event_id`. Every target still runs its G6 preamble and its area's concurrency group (S-GEN-060).

  *Depends on:* S-GEN-026, S-GEN-031, S-GEN-060, S-GEN-063, S-GEN-071, S-BA-034, S-ARCH-034, S-ARCH-054, S-DEV-006, S-DEV-044, S-QA-013, S-QA-041, S-DEVOPS-006, S-DEVOPS-018, S-DEVOPS-020, S-DEVOPS-021.
- **S-DEVOPS-018** Per-job credentials, minted by OIDC (S-SEC-008, for every identity in S-GEN-026):
  - **No stored credential:** no app private key, tracker credential, model credential or cloud credential is stored as a CI secret. They sit in a vault and KMS in an allowed region (S-DEVOPS-028). For base-code jobs, vault credentials bound to protected workflow-ref, event and environment claims count as equivalent to S-SEC-006's reviewed environments (`docs/decisions.md`, 2026-11-21). S-SEC-006 carries this equivalence. The roles that stay human-gated are in S-DEVOPS-022.
  - **Trust levels as separate reusable workflows:** `router` (S-DEVOPS-017: the read-only tracker credential for polling, nothing else), `facts` (S-DEVOPS-020: read-only code-host and tracker tokens), `fetch`, `read`, `work` (and check `run`), `write`, `report` and `ops`. Each level is its own file in the protected source, so its `job_workflow_ref` claim identifies it. The CI's OIDC token has no per-job claim, so no two levels share a file.
  - **Minting:** a job gets a credential only by presenting the CI's OIDC token. The policy matches `job_workflow_ref`, repository, event, ref and, where one applies, the environment. A workflow changed on an agent branch or in a fork presents a different ref, so it gets nothing.
  - **Policy table:** human-authored IaC in staff `ops/**`. It maps each trust level to an identity, its repositories, a subset of its S-GEN-026 scopes, and a lifetime no longer than the job's timeout. Code-host tokens are down-scoped installation tokens.
  - **Isolated jobs never hold `id-token: write`.** The runner controller, outside the job, mints the credentials of the job's variant (S-DEVOPS-024) and stages them into the sandbox, short-lived, as it stages the bundle.
    - **Its trust anchor:** for each job it is asked to run, the controller looks up the job's run through the code-host API, with its own read-only credential. It reads the workflow path, ref, event, repository and head from there, never from the job's request.
    - It mints only when that run passes the S-DEVOPS-017 provenance rules and the workflow path is a listed trust level. The variant's credentials come from the policy table for that level. The pipeline diff check blocks `id-token: write` on an isolated-pool job (S-DEVOPS-042).
  - **Write tokens** exist only at the `write` level (S-SEC-007). The workflow-file permission is granted only to the DevOps and `ci-upkeep` write jobs, and only on the fork (S-DEVOPS-019). No other job gets it, so the DEV, QA, ARCH and BA tokens never carry it (S-DEV-003, S-QA-003). The `report` level uses the CI job token, with per-job `checks` and `pull-requests` permissions only. The `ops` level carries only the writes S-GEN-026 lists for ops jobs (S-GEN-069).
  - **Audit:** every mint and every denial is logged, and the digest lists denials.

  *Depends on:* S-GEN-026, S-GEN-069, S-SEC-006, S-SEC-007, S-SEC-008, S-DATA-002, S-DEV-003, S-QA-003, S-DEVOPS-019, S-DEVOPS-022, S-DEVOPS-023, S-DEVOPS-024, S-DEVOPS-028, S-DEVOPS-042.
- **S-DEVOPS-019** The fork and push rulesets (OD-SEC-2, OD-QA-3):
  - **DEVOPS fork:** one fork of the product repo, in an account or org the human owns. Only staff-engineering is installed on it. Actions are disabled in the fork. Upstream runs its PRs as S-SEC-006 sets for forks. The scope lint checks the head repository (S-DEVOPS-005).
  - **Push rulesets:** each identity may create or update only refs under its own prefixes. The rulesets reserve each prefix to its identity, and block every other `agent/*` ref. No identity has a bypass (S-SEC-008).

    | Identity | Prefixes |
    | --- | --- |
    | staff-product | `agent/analyst/*`, `agent/knowledge-drafting/*` *(starting value)*, as S-BA-037 uses them |
    | staff-engineering | `agent/architect/*`, `agent/arch-upkeep/*`, `agent/developer/*`, `agent/dev-upkeep/*`, `agent/devops/*`, `agent/ci-upkeep/*` |
    | staff-qa | `agent/test-gen-*/**`, `agent/ci-healer/**`, `agent/exploratory/**` |
    | Release job | `agent/release/*` in the product repo; tags only in staff |
    | Improver, strategy designer, eval runner (staff) | `agent/improver/*`, `agent/strategy/*`, `agent/eval-runner/*` *(starting value)* |
    | Shared reviewer, recorder, ops jobs, seeding agent | None |

  *Depends on:* S-GEN-010, S-GEN-026, S-SEC-006, S-SEC-008, S-BA-037, S-ARCH-003, S-QA-003, S-DEVOPS-005.
- **S-DEVOPS-020** Required checks, from a source the PR can't change (OD-SEC-2, for every role's checks):
  - **Source:** org-ruleset required workflows from staff `.github/workflows/`, pinned to a release tag. Where org rulesets aren't available, and only for same-repo PRs, the fallback is `pull_request_target` workflows in the repo's `staff-*` files, which only the human edits, with a base checkout. Either way, the check scripts run at the version pinned in the base branch's `.staff/plugins.lock` (staff checks: at the staff `main` commit the PR targets), and read `.staff/*.yml` from the base.
  - **Jobs,** each at its own trust level (S-DEVOPS-018):
    - `facts`: base code only. It reads PR files and metadata as data and never executes them. It holds read-only code-host and tracker tokens (S-DEVOPS-021).
    - `run`: only for checks that build or run PR code. It runs in the `work` variant (S-DEVOPS-024), with `permissions: contents: read`, no tokens and test-only credentials. The base-code harness runs the PR code in a nested container, and only the harness writes the result artifact. The job never saves to a cache that default-branch jobs restore.
    - `report`: base code only. It validates the other jobs' artifacts against the check's schema, sets the status, and posts the check's comment (for example S-DEV-007's blockers or S-QA-036's survivors), with the CI job token (S-DEVOPS-018).
  - **Fork PRs (DEVOPS):** a fork PR gets no OIDC token and no write token.
    - Its `facts` and `report` jobs run as base-checkout `pull_request_target` jobs from the human-only `staff-*` files, reading PR files only as data.
    - Its `run` job is the org-ruleset required workflow from staff, at the release tag, behind S-SEC-006's approval. So the PR can't rewrite the harness that writes the result.
    - There is no fallback for fork PRs. DEVOPS opens fork PRs only at stage 2, and S-DEVOPS-034 step 5 requires org-ruleset required workflows before then. Without them, a fork PR's checks fail closed.
  - **How `report` gets the `run` artifact:** on same-repo PRs, `report` is a job in the same run that depends on `run`. On fork PRs, `report` starts on the `workflow_run` of the required workflow. It runs only if that run passes the S-DEVOPS-017 provenance check, and it downloads that run's artifact by run ID through the code-host API.
  - **Always report:** a check whose scope doesn't match the PR reports "not applicable" as success, so required checks never hang. A check that can't run fails closed (S-BA-051). Report-only checks on human PRs (S-DEV-027, S-QA-041) pass with annotations.
  - **Registration:** the required-check list per repo is ruleset IaC in staff `ops/**`:

    | Repo | Required checks | Ship from |
    | --- | --- | --- |
    | Product | G2 scope lint with the trailer check (S-GEN-020, -029); lock check (S-GEN-022) | staff-core |
    | Product | BA (S-BA-051), ARCH (S-ARCH-045), DEV (S-DEV-027), QA (S-QA-041) and DEVOPS (S-DEVOPS-045) checks, each when its role ships | Each role's plugin `checks/` |
    | Staff | CI path check with the trailer check (S-GEN-025, -029); pack measurement on `docs/strategy/**` (S-GEN-021) | staff-core |
    | Staff | The checklist diff checks (S-BA-046, S-ARCH-044, S-DEV-031, S-QA-040, S-DEVOPS-045) | Each role's plugin `checks/` |
    | Staff | The eval status on skill PRs, including "eval incomplete" (S-GEN-036, -070) | Eval runner |

  *Depends on:* S-GEN-016, S-GEN-020, S-GEN-021, S-GEN-022, S-GEN-025, S-GEN-029, S-GEN-036, S-GEN-070, S-SEC-006, S-BA-046, S-BA-051, S-ARCH-044, S-ARCH-045, S-DEV-007, S-DEV-027, S-DEV-031, S-QA-036, S-QA-040, S-QA-041, S-DEVOPS-018, S-DEVOPS-021, S-DEVOPS-024, S-DEVOPS-045.
- **S-DEVOPS-021** Read access to the tracker and code host (OD-BA-5, OD-ARCH-3, OD-DEV-3, OD-QA-3):
  - There is one read-only tracker credential per product, in the vault. It is minted only to `facts` jobs, the router and `fetch` steps, and staged by the controller into the `read` variant (S-DEVOPS-018, -024).
  - **Tracker writes:** each S-GEN-026 identity that writes to the tracker has its own tracker account in the vault, minted only at the `write` level.
  - Reads go through the staff-core reader. It returns account IDs for comment authors and label actors, comment refs, and machine-readable blocks. It redacts text on read (S-BA-028).
  - Author and actor checks compare account IDs with `governance/operators.yml`, never display names.
  - The code-host API supplies revert markers, rename detection and per-PR commit trailers to `facts` jobs (S-GEN-029, S-DEV-028, -044).

  *Depends on:* S-GEN-026, S-GEN-029, S-GEN-071, S-BA-028, S-DEV-028, S-DEV-044, S-DEVOPS-018, S-DEVOPS-024.
- **S-DEVOPS-022** Secret layout, environments and default tokens (OD-SEC-2):
  - **CI secrets reachable from `agent/*` branches** hold only the test-account credentials of S-TESTAB-004 (S-SEC-005).
  - **Human-gated environments,** restricted to `main` with the human as required reviewer (`docs/decisions.md`, 2026-11-21):
    - `production`: apply, deploy, rollback and migrations;
    - `production-plan` (S-DEVOPS-037);
    - `production-export` (S-DEVOPS-029);
    - `production-monitor` (S-DEVOPS-040);
    - `staging-deploy`: deploys and migrations of the staging-equivalent environment (S-DEVOPS-035).

    The cloud roles behind them also require the environment claim in their minting policy. So a changed workflow that drops its binding gets nothing (S-SEC-006).
  - **Every other non-test credential** is a vault credential for base-code jobs (S-DEVOPS-018, S-SEC-006).
  - **Default `GITHUB_TOKEN`:** read-only in every repo and org that agents reach. Every staff and product workflow sets top-level `permissions: {}` and declares minimal permissions per job. Fork PR runs follow S-SEC-006.

  *Depends on:* S-SEC-005, S-SEC-006, S-SEC-008, S-TESTAB-004, S-DEVOPS-018, S-DEVOPS-029, S-DEVOPS-035, S-DEVOPS-037, S-DEVOPS-040.
- **S-DEVOPS-023** Runner pools and egress (S-SEC-007):
  - **Isolated pool:** self-hosted and ephemeral, with one job per VM or pod, destroyed afterwards. Egress is enforced by a network policy outside the job, per job class. Every job that runs a model session, PR code, agent-written code or agent-changed configuration runs here. The pool sits in an allowed region (S-DEVOPS-028).
  - **Trusted pool:** for `fetch`, `facts`, `report`, `write` and `ops` jobs, which run only base code and no model session. It is hosted or self-hosted, per S-DEVOPS-028.
  - **Allowlists,** human-authored IaC:
    - `fetch`, `write` and the `read` variant: the model endpoint (`read` only), the mirror, the code host, the tracker and approved connectors (S-SEC-007);
    - sandbox variants: per S-DEVOPS-024;
    - check `run` jobs: the mirror and the run's environment.

    Endpoints come from `.staff/product.yml` and `governance/ops-config/` (S-DATA-002). An egress-filtering step on a hosted runner never counts as enforcement for an isolated job (SEC Assumptions item 6).

  *Depends on:* S-SEC-007, S-DATA-002, S-DATA-003, S-DEVOPS-024, S-DEVOPS-028.
- **S-DEVOPS-024** Sandbox launcher: one reusable launcher for the S-GEN-066 profile and its variants (OD-DEV-3, OD-QA-2, OD-BA-6).

  | Variant | Used by | Credentials | Egress |
  | --- | --- | --- | --- |
  | `read` | Not a variant of the S-GEN-066 profile. It is the S-SEC-007 read stage, run by the same launcher: it holds identity read tokens and reaches the code host and tracker, which S-GEN-066 excludes. S-GEN-066 notes that this launcher runs it. It serves read stages that retrieve on demand and run no product: the Analyst, knowledge drafting, the Architect, `arch-upkeep`, every `reviewer/<type>` (S-BA-036, S-ARCH-036) | Model; read-only code-host and tracker tokens of its identity | Model endpoint, mirror, code host, tracker, approved connectors (S-SEC-007) |
  | `eval` | The eval runner (S-GEN-066) | Model; test-only for the pinned eval environment; for DEVOPS tasks, the plan-only role of the eval account (S-DEVOPS-026) | Model endpoint, mirror, eval environment; for DEVOPS tasks, the eval account's API |
  | `work` | Developer and `dev-upkeep` (S-DEV-042), QA agents (S-QA-017), DevOps and `ci-upkeep`; check `run` jobs | Model (agents only); test-only; for DEVOPS, the plan-only role of the ephemeral account (S-DEVOPS-026) | Model endpoint (agents only), mirror, the run's environment (S-DEVOPS-026); for DEVOPS, the ephemeral account's API |
  | `tokenless` | `mutant-drafter`, `equivalence-filter` (S-QA-038, -039), the LLM judge (S-GEN-042) | Model only | Model endpoint |
  | `interactive` | `analyst-interview` (S-DEVOPS-025) | Model only | Model endpoint. The human's channel arrives inbound through the runner controller, so the sandbox's own egress stays model-only (S-GEN-066) |

  The controller stages every credential in the table (S-DEVOPS-018). In `read`, the write stage is a separate `write` job that gets only the validated output (S-SEC-002).

  Steps:
  1. **Fetch:** a model-free job on the trusted pool, with read-only tokens. It redacts (S-BA-028) and publishes a digest-addressed bundle. The `read` variant may skip it and retrieve through its read tokens, with read-time redaction (S-BA-028).
  2. **Work:** on the isolated pool. The runner controller, not the sandbox, stages the bundle read-only after checking its digest, so the `work`, `eval`, `tokenless` and `interactive` sandboxes need no route to the code host. The job timeout is the agent's wall-clock cap, and the harness enforces turn and cost limits. A kill emits status `timeout` or `cap_hit` (S-GEN-029).
  3. **Hand-off:** the controller collects the output directory. The harness derives `files[]` from the workspace diff and validates every output against its schema (S-DEV-021).
  4. **Write:** a trusted-pool job holding the write token commits byte for byte.

  Every launch runs the G6 preamble first (S-GEN-020). *Depends on:* S-GEN-020, S-GEN-029, S-GEN-042, S-GEN-066, S-SEC-002, S-SEC-007, S-BA-028, S-BA-036, S-ARCH-036, S-DEV-021, S-DEV-042, S-QA-017, S-QA-038, S-QA-039, S-DEVOPS-018, S-DEVOPS-023, S-DEVOPS-025, S-DEVOPS-026.
- **S-DEVOPS-025** Interactive path for `analyst-interview` (closes OD-BA-6, inside S-GEN-004):
  - **Launch wrapper:** a `staff-*` `workflow_dispatch` job that checks its triggering actor against `operators.yml` first (S-DEVOPS-017). It holds a read-only staff-product token, minted per S-DEVOPS-018, which never reaches the sandbox. It runs the G6 preamble, fetches and redacts the guide, product core and intake, and checks the injected inputs against the budget the pack's static part leaves (S-BA-052), failing closed. It publishes the single-session bundle, which expires at the timebox plus 15 min *(starting value, `docs/decisions.md`, 2026-11-21)*, and emits the opening record through the recorder (S-GEN-004).
  - **Sandbox:** the `interactive` variant on the isolated pool, in an allowed region. Its only ingress is the human's channel: an authenticated relay (for example SSO-protected) that admits only an operator account, and reaches the sandbox through the runner controller (S-DEVOPS-024). The relay carries unredacted human turns, so it keeps no copy and is placed per S-DEVOPS-028. The host is killed at the S-BA-055 caps.
  - **Session harness:** staff-core code, which DEVOPS hosts. It does what S-BA-056 and -057 assign to it, and writes the transcript and completion data to its output directory.
  - **Post-session hand-off:** a `workflow_dispatch` job, operator-only. It redacts the transcript again (S-SEC-004), completes the opening record, and delivers the timing events through the recorder (S-GEN-071). The recorder stores the redacted transcript as the session's `transcript_ref` in access-controlled object storage (S-GEN-010), never as a CI artifact that agents can read. The human downloads it from there to commit it (S-BA-056).

  *Depends on:* S-GEN-004, S-GEN-071, S-SEC-004, S-BA-052, S-BA-055, S-BA-056, S-BA-057, S-DEVOPS-018, S-DEVOPS-024, OD-BA-6.
- **S-DEVOPS-026** Ephemeral environments (closes the environment part of OD-TESTAB-4, OD-QA-1 and OD-ARCH-3):
  - **Template:** `delivery/environments/ephemeral/`. Its deploy units come from component `deployment` fields (S-ARCH-007). Each runtime dependency is either provisioned, or replaced by a fake at its seam (S-ARCH-025), as the environment's settings say (S-DEVOPS-041).
  - **Accounts:** ephemeral environments live in their own cloud account or accounts, and eval environments in an eval account. Neither has a trust path to the staging-equivalent environment, production or the vault, and each sits under a permission boundary. Inside them:
    - the provisioner role is minted only to the human-authored provisioner, which applies only the base branch's template and never agent-changed IaC;
    - a plan-only role, read-only on the ephemeral stacks, is the only cloud role a `work` or `eval` sandbox gets (S-DEVOPS-024);
    - a run-scoped template-test role is staged only into the check `run` job of a PR that changes the template (S-DEVOPS-018). Its permission boundary allows actions only on resources whose tag and name prefix carry that `run_id`, and denies creating any resource without them. Two more conditions keep the scope from escaping:
      - every role or user it creates must carry the same permission boundary, or the create is denied;
      - it may assume or pass only roles that carry that boundary and its own `run_id`.
  - **Provisioner:** a human-authored job that the launcher and check `run` jobs call. It creates `env-<run_id>` from a pinned digest (S-TESTAB-003) and a snapshot (S-DEVOPS-027), isolated by network from every other environment. It waits for readiness (S-TESTAB-007), and passes the URL and test credentials only into the sandbox. For a PR that changes the template, the check's `run` job applies the head template with the run-scoped role, so it can neither read nor change any other `env-<run_id>`. It then tears that environment down, and the reaper removes anything left under the `run_id`. The IaC diff check flags any change to that scoping (S-DEVOPS-043).
  - **Limits:** teardown at the end of the job; a reaper deletes any environment older than 3 h; at most 10 concurrent environments per product, with later requests queued. Both are *(starting value, `docs/decisions.md`, 2026-11-21)*.
  - **Fallback:** where the product can't run per job, S-TESTAB-002's shared environment applies, namespaced by `run_id`, and the delivery check marks the area.
  - No ephemeral environment is configured with a production endpoint or credential.

  *Depends on:* S-TESTAB-002, S-TESTAB-003, S-TESTAB-007, S-TESTAB-008, S-ARCH-007, S-ARCH-025, S-DEVOPS-018, S-DEVOPS-024, S-DEVOPS-027, S-DEVOPS-041, S-DEVOPS-043, OD-TESTAB-4.
- **S-DEVOPS-027** Snapshots, seeding and accounts (OD-TESTAB-4, OD-QA-1):
  - **Snapshot:** a synthetic dataset that the product's seed scripts (S-TESTAB-004) produce for a build digest. It is stored by digest in the container registry, as an OCI artifact, keyed by (build digest, seed hash). A post-merge job rebuilds it when seeds or migrations change. Eval runs pin (digest, snapshot) (S-GEN-043).
  - **Per-run reset:** each environment restores a fresh snapshot. Tests then create their own data through factories.
  - **Accounts:** the S-TESTAB-004 test-account credentials are seeded into each environment, and reach only the sandbox.

  *Depends on:* S-GEN-043, S-TESTAB-003, S-TESTAB-004, S-DATA-004.
- **S-DEVOPS-028** Placement (closes OD-DATA-1). Everything below sits in an allowed region of `.staff/product.yml`. Staff-wide stores must satisfy every product served, as in S-DATA-002.

  | Item | Placement |
  | --- | --- |
  | Isolated pool; self-hosted trusted runners; the interactive host | An allowed region |
  | Hosted runners | Trusted-pool jobs only, and only when residency is `unrestricted` or the provider guarantees an allowed region |
  | CI artifacts and logs | The code host's storage, only if it is in an allowed region (otherwise see Open questions). Agent job logs carry no raw content |
  | Outcome database; object storage (transcripts, eval-private prefix); vault and KMS; registry; environment clusters and their log and trace stores (S-DEVOPS-041); mirror cache; the `staff-evals-private` host | An allowed region |
  | The interview relay (S-DEVOPS-025); the production monitoring stack (S-DEVOPS-040) | An allowed region |
  | The router's cursor and dedup state (S-DEVOPS-017) | As CI artifacts |

  A nightly placement check compares the regions declared in IaC and the runner labels with the declaration. A mismatch is a digest finding, and the IaC diff check blocks new out-of-region resources (S-DEVOPS-043). *Depends on:* S-DATA-001, S-DATA-002, S-DATA-003, S-GEN-010, S-DEVOPS-017, S-DEVOPS-025, S-DEVOPS-040, S-DEVOPS-041, S-DEVOPS-043.
- **S-DEVOPS-029** Production export job (closes that part of OD-BA-5):
  - A human-authored `staff-export` workflow runs in the `production-export` environment (S-DEVOPS-022), weekly *(starting value, `docs/decisions.md`, 2026-11-21)* and on dispatch.
  - It reads only the sources listed under `exports` in `.staff/delivery.yml` (S-DEVOPS-004), through a read-only role.
  - It redacts per S-SEC-004. It fails closed, and dropped items are counted in the digest.
  - It publishes digest-addressed bundles as CI artifacts, retained for 90 days *(starting value)*. BA and QA fetch steps read them (S-BA-028, S-QA-048). There is never a live connector.

  *Depends on:* S-SEC-004, S-DATA-004, S-BA-028, S-QA-048, S-DEVOPS-004, S-DEVOPS-022.
- **S-DEVOPS-030** Per-test result history (closes OD-QA-4):
  - Every test job emits a machine-readable report.
  - An indexer runs on each test workflow's completion and nightly, in one concurrency group. Each run adds the new rows `{test_id (S-DEV-045), workflow run, attempt, outcome, duration, build_digest, commit, branch, quarantined}` and publishes a full new version of the history index as a CI artifact. Readers take the latest version. Rows are kept for 35 days *(starting value, `docs/decisions.md`, 2026-11-21)*, beyond the 30-day reference window (S-QA-027).
  - The quarantine history is derived from the merged history of `qa/quarantine.yml` through the code-host API.
  - QA fetch steps, checks and the healer's fact script read it with read-only tokens. Reports are untrusted tool output, parsed by schema.

  *Depends on:* S-DEV-045, S-QA-027, S-QA-028, S-QA-029.
- **S-DEVOPS-031** Scheduled and post-merge jobs (OD-ARCH-3, OD-DEV-3, OD-QA-1, OD-QA-3). Each is a check of S-DEVOPS-020, uses its owner's logic, and runs in the area's concurrency group:

  | Job | Trigger | Owner |
  | --- | --- | --- |
  | BA nightly trace and outcome checks | Schedule | S-BA-021, -054 |
  | ARCH drift and trace reports, outcome records | Schedule | S-ARCH-027, -030, -052 |
  | Compatibility post-merge run and spec-change event | Push to `main` touching interfaces | S-ARCH-054 |
  | Implementation check | Push to `main`; an operator `implemented_acs[]` comment, via the router; schedule | S-DEV-044 |
  | Readiness re-run; DEV outcome check | Schedule | S-DEV-007, -039 |
  | `interface_source` (a `run` job) | Every product PR, and `main` | S-DEV-012 |
  | Lint, deprecation and dependency reports per area (a `run` job, mirror egress only), defined here: lint findings under the area's `verification_config`, deprecation warnings from its build output, and newer versions and advisories of its `dependency_files` from the mirror, as CI artifacts | Schedule | This decision, for S-DEV-006 |
  | Quarantine expiry, flake sweep, contract run, spec fuzzing, gap findings, QA outcome check | Schedule; fuzzing on PRs touching implemented interfaces | S-QA-022, -023, -029, -041 |
  | Pin report; delivery check; placement check; platform health | Schedule; delivery check also post-merge | S-DEVOPS-049, -045, -028, -033 |

  **Quarantine:** the test-runner wrapper reads `qa/quarantine.yml` from the base. It runs entries non-blocking while they are at most 28 days old, and ignores older ones (S-QA-029). *Depends on:* S-BA-021, S-BA-054, S-ARCH-027, S-ARCH-030, S-ARCH-052, S-ARCH-054, S-DEV-004, S-DEV-006, S-DEV-007, S-DEV-012, S-DEV-039, S-DEV-044, S-QA-022, S-QA-023, S-QA-029, S-QA-041, S-DEVOPS-020, S-DEVOPS-028, S-DEVOPS-033, S-DEVOPS-045, S-DEVOPS-049.
- **S-DEVOPS-032** Mutation and QA tooling (closes the tooling parts of OD-QA-1 and OD-QA-2):
  - **Tools:** mutation tools per stack, from the mirror as `.staff/tests.yml` declares, baked into check images by digest.
  - **Response mutation:** an interception proxy injected into the run's environment at its seams.
  - **Caps:** the gate, guard and nightly runs have job timeouts equal to S-QA-036's caps.
  - **Gate workflow jobs:** `facts` → `mutant-drafter` (`tokenless`) → `run`, which validates and applies concern mutants by script and runs the tests (S-QA-039) → `equivalence-filter` (`tokenless`) → `report`.

  *Depends on:* S-QA-005, S-QA-036, S-QA-038, S-QA-039, S-DEVOPS-020, S-DEVOPS-024, S-DEVOPS-026.
- **S-DEVOPS-033** Platform health. A script classifies failed jobs by infrastructure signature: runner lost, provisioning or readiness timeout, mirror or registry unavailable, rate limit, mint denied. Logs are untrusted (S-SEC-001). A signature that recurs at least 3 times in 7 days *(starting value, `docs/decisions.md`, 2026-11-21)* becomes one infrastructure item per signature in the digest, with a checkbox. Ops jobs have no tracker write (S-GEN-026), so no ticket is opened. The operator's tick is a verdict (S-GEN-071), and it starts DevOps (S-DEVOPS-006). *Depends on:* S-SEC-001, S-GEN-026, S-GEN-063, S-GEN-071, S-DEVOPS-006.
- **S-DEVOPS-058** Compute visibility (S-GEN-058, which sums only run records). The digest reports, per role and per day, isolated-pool runner minutes, ephemeral-environment hours, and staging-equivalent and load-run hours, from the runner controller and the provisioner. This is a load and cost signal with no threshold. Cloud and runner spend is outside the agent monthly cap, which the human sets. *Depends on:* S-GEN-058, S-GEN-063, S-DEVOPS-023, S-DEVOPS-026, S-DEVOPS-039.
- **S-DEVOPS-034** Bootstrap order. The platform is human-built (S-GEN-025), so it is the first bottleneck. The rows put in build order what each role's own rules already need before its agents run or leave stage 1: their checks (G3, S-GEN-051) and their testability prerequisites (S-TESTAB-001). This decision adds no gate of its own.

  | Step | Pieces | Before |
  | --- | --- | --- |
  | 0. Foundations | Placement (-028); vault, trust-level workflows and minting (-018); runner pools, controller and egress (-023); rulesets, the fork-run approval and read-only defaults (-019, -022); the staff-core and staff-repo rows of the required-check list (-020); recorder, outcome store, switches, G6, digest, cost job and compute report (-058); eval runner; the launcher with the `eval`, `tokenless` and `read` variants (-024); router (-017); tracker reads (-021) | Any agent result counts (S-GEN-033) |
  | 1. BA | BA router rows; the interactive path (-025). Then the BA required checks (-020), and the export job (-029) only if BA reads production-derived sources | BA stage 1, then stage 2 |
  | 2. ARCH | ARCH checks and nightly jobs (-031) | ARCH stage 2 |
  | 3. DEV | Digest builds (-035); the `work` variant and ephemeral environments (-026, -027); then the DEV checks with base builds, implementation runs, `interface_source` and reports (-031) | DEV stage 1, then stage 2 |
  | 4. QA | Snapshots and result history (-027, -030); then the QA checks, mutation tooling and quarantine wrapper (-031, -032) | QA stage 1, then stage 2 |
  | 5. DEVOPS | The fork (-019); org-ruleset required workflows for the product repo, with no fallback for fork PRs (-020); the DEVOPS checks (-042 to -045); the pin report (-049) | DEVOPS stage 2 |

  Where the human rolls DevOps out early, at stage 1, it drafts the product-side pieces of steps 3 and 4 (environment definitions, and product workflows that call the staff ones) as comments (Open questions). *Depends on:* S-GEN-025, S-GEN-033, S-GEN-051, S-GEN-073, S-TESTAB-001, S-DEVOPS-017 to S-DEVOPS-033, S-DEVOPS-035, S-DEVOPS-042 to S-DEVOPS-045, S-DEVOPS-049, S-DEVOPS-058.

### Product delivery

- **S-DEVOPS-035** Pipeline stages:
  1. **PR:** build once per commit, to a digest (S-TESTAB-003), with a provenance attestation. Required checks run (S-DEVOPS-020): the product suites without quarantined tests, the role checks, image and dependency scans, and, for delivery changes, validation and the test-environment plan.
  2. **`main`:** the merge build's digest is the one every later stage uses. Nothing is rebuilt.
  3. **Staging-equivalent:** a deploy of the latest `main` digest in the `staging-deploy` environment, which the human approves (S-DEVOPS-022; `docs/decisions.md`, 2026-11-21). Migrations go first (S-DEVOPS-038), then the smoke checks. One approval covers every merge since the last deploy. The scheduled load runs use whatever is deployed (S-DEVOPS-039).
  4. **Production:** human-gated (S-DEVOPS-036).

  Ephemeral environments are per run, not a stage (S-DEVOPS-026). *Depends on:* S-TESTAB-003, S-DEVOPS-020, S-DEVOPS-022, S-DEVOPS-026, S-DEVOPS-036, S-DEVOPS-038, S-DEVOPS-039.
- **S-DEVOPS-036** Deploy and rollback. A production deploy is a job in the `production` environment (S-DEVOPS-022), which the human approves. It deploys only a digest that has the `main` attestation and passed the staging-equivalent smoke checks. The job's summary, which the human sees before approving, shows the latest load results (S-DEVOPS-039). Rollback is the same job with the previous recorded good digest, behind one approval. Migrations are expand-and-contract, so a rollback never needs a down-migration (S-DEVOPS-038). *Depends on:* S-DEVOPS-022, S-DEVOPS-035, S-DEVOPS-038, S-DEVOPS-039.
- **S-DEVOPS-037** IaC plan and apply (S-SEC-005):
  - **On PRs:**
    - The `work` sandbox validates and plans only the ephemeral stacks, with the plan-only role (S-DEVOPS-026).
    - A plan of the staging-equivalent stack runs only in the check's `run` job, with a read-only plan role scoped to that stack. It never reaches an agent session. That stack's state holds no non-test secret: secrets are generated and kept in the vault and referenced by name, and the IaC diff check blocks secret values (S-DEVOPS-043). So the role is a test-environment credential under S-SEC-005.
    - The production stack is never planned on a PR. It gets static checks only (S-DEVOPS-043).
  - **After merge:** a `production-plan` job writes the full plan to storage inside the production account, readable only by the plan and apply roles. It publishes only the destroy and replace summary (resource addresses and actions, no values) as a CI artifact, so no production state reaches agents (S-DEVOPS-012). A `production-apply` job applies exactly that plan, by digest. Both are human-gated (S-DEVOPS-022). A plan that destroys or replaces a stateful resource also needs an operator sign-off in the S-ARCH-053 form, citing those resources' flag IDs (S-DEVOPS-046). The apply job verifies the sign-off before it starts, and fails closed without it.

  *Depends on:* S-SEC-005, S-ARCH-053, S-DEVOPS-012, S-DEVOPS-022, S-DEVOPS-026, S-DEVOPS-043, S-DEVOPS-046.
- **S-DEVOPS-038** Data migrations (closes that part of OD-DEV-3). The deploy runs the `migrations` command at the deploy digest as its own step, before the app rollout, in each environment. In production that step is inside the approved job. Ephemeral environments apply every migration at provisioning.
  - **Expand and contract:** a migration must leave the previous digest working. The staging-equivalent deploy runs the previous digest's smoke checks against the migrated schema.
  - **Contract steps,** which drop or narrow, ship only in a later release, once no deployed digest uses the old shape.

  DEV flags every migration diff (S-DEV-004, -018). *Depends on:* S-DEV-004, S-DEV-018, S-DEVOPS-026, S-DEVOPS-036.
- **S-DEVOPS-039** The staging-equivalent environment is persistent. It is built from the same IaC modules as production, with synthetic data at volume. It never holds real data, and no agent runs against it (S-TESTAB-002).
  - **Load, soak and capacity runs:** scheduled check jobs, weekly *(starting value, `docs/decisions.md`, 2026-11-21)* and on dispatch before a production deploy. They run the merged `delivery/load/QAS-n` definitions with the declared tool.
  - **Results:** per QAS, the measured value against the `measure`, as an unlinked `check_outcome` with `artifact_id` QAS-n (S-GEN-031), listed in the digest. Nothing blocks automatically. The human decides at the deploy approval.

  *Depends on:* S-GEN-031, S-TESTAB-002, S-DEVOPS-036, S-DEVOPS-040.
- **S-DEVOPS-040** QAS monitor duty (`docs/decisions.md`, 2026-11-20). It covers every accepted QAS with `verification: monitor`, owner DEVOPS (S-ARCH-009), which AR-8 checks for (S-ARCH-032):
  - **Where:** each such QAS is verified where its `verification.where` says: `pre-production`, `production` or `both`. S-ARCH-009 sets that field, with `both` as its default *(starting value)*, and AR-8 checks it (S-ARCH-032).
  - **Definitions:** `pre-production` needs a load definition (S-DEVOPS-039). `production` needs a monitor definition, which deploys with the production gate. Each cites the QAS, and its threshold follows S-DEVOPS-011.
  - **Coverage:** a QAS is covered when it has a merged definition for each place its `where` names. A missing one is a nightly finding that starts DevOps (S-DEVOPS-006).
  - **Results:** load results as in S-DEVOPS-039. Production monitor values stay in the monitoring stack, which only the human reads. A `monitor-status` job, in the `production-monitor` environment (S-DEVOPS-022), reads only alert states through a read-only role on that stack. It runs weekly *(starting value)*, and as a step of every production deploy. It emits only the QAS ID, pass or fail, and the date, as an unlinked `check_outcome` (S-GEN-031) for the digest (S-DATA-004).

  *Depends on:* S-GEN-031, S-ARCH-009, S-ARCH-032, S-DATA-004, S-DEVOPS-004, S-DEVOPS-006, S-DEVOPS-011, S-DEVOPS-022, S-DEVOPS-036, S-DEVOPS-039.
- **S-DEVOPS-041** Observability and control hooks:
  - Every environment definition wires `run_id` correlation and readiness (S-TESTAB-007). Logs and traces sit in a per-environment store, which the sandbox reads by `run_id` inside its egress.
  - The S-TESTAB-008 seams (flags, clock, fakes) are enabled only in ephemeral and staging-equivalent environments.
  - Production sets them off. The IaC diff check blocks enabling them there (S-DEVOPS-043).

  *Depends on:* S-TESTAB-007, S-TESTAB-008, S-ARCH-025, S-DEVOPS-043.

### DEVOPS checks

- **S-DEVOPS-042** Pipeline and build diff check (closes OD-GEN-9 for `pipelines` and `build`). It parses base and head and compares each job's effective settings as a net set, so moving a step isn't flagged.
  - **Blocked:**
    - a job or step that produces a required check removed or neutralised: `continue-on-error`, a condition or path filter that can skip it, exit-code masking (for example `|| true` or `set +e`), or changed test-selection arguments;
    - a scan or provenance-attestation step removed from a build (S-DEVOPS-035);
    - a new privileged trigger in a product workflow: `pull_request_target`, `workflow_run`, `issue_comment` or `repository_dispatch`;
    - an action, image or base image referenced by tag instead of digest;
    - untrusted event text interpolated into a shell step;
    - a job that runs PR code moved off the isolated pool, and `id-token: write` on an isolated-pool job (S-DEVOPS-018);
    - any diff to `staff-*` workflows.
  - **Flagged:**
    - net widening of a job's `permissions:`, including `id-token: write` on trusted-pool jobs;
    - a new secret reference, environment binding or minting request;
    - a new egress host;
    - a new or upgraded action, image, base image or runner image (`devops:dependency`, S-SEC-009), unless it is a propagation that S-DEVOPS-049 verifies. A propagation is not flagged, but keeps the label;
    - a removed timeout or concurrency group;
    - a cache that a PR run can write and `main` restores.

  *Depends on:* S-GEN-020, S-SEC-006, S-SEC-007, S-SEC-009, S-DEVOPS-020, S-DEVOPS-023, S-DEVOPS-035, S-DEVOPS-049, OD-GEN-9.
- **S-DEVOPS-043** IaC and environment diff check, from a static parse plus the test-environment plan:
  - **Blocked:**
    - a production endpoint or credential in an ephemeral or staging-equivalent definition;
    - a resource outside the declared regions (S-DEVOPS-028);
    - control seams enabled in production (S-DEVOPS-041);
    - a plaintext secret value, in a definition or in what the plan would write to state.
  - **Flagged:**
    - any destroy or replace in a plan;
    - deletion protection or backup retention reduced;
    - an IAM or network policy widened (new actions, wildcard principals or resources, public ingress or storage);
    - encryption or logging disabled;
    - environment isolation or TTL loosened, including any change to the run-scoped tag, the name prefix or the permission boundaries of the ephemeral accounts, or to the boundary's conditions on creating, assuming or passing roles (S-DEVOPS-026);
    - any change to a production stack.

  *Depends on:* S-GEN-020, S-DATA-003, S-DEVOPS-026, S-DEVOPS-028, S-DEVOPS-037, S-DEVOPS-041.
- **S-DEVOPS-044** Monitor and load check:
  - **Blocked:**
    - a threshold or unit that differs from the cited QAS `measure` (S-DEVOPS-011);
    - a definition removed while its QAS is accepted;
    - a cited QAS that isn't accepted with `verification: monitor`, owner DEVOPS. The check reads the QAS file from the base branch, where only merged states exist (S-ARCH-011), and fails closed when it can't read it.
  - **Flagged:** an alert, schedule or window disabled or shortened.
  - **Allowed:** removal together with the QAS's retirement.

  *Depends on:* S-ARCH-009, S-ARCH-011, S-DEVOPS-011.
- **S-DEVOPS-045** DEVOPS check scripts. They ship from staff-engineering `checks/`, run as required checks (S-DEVOPS-020), read no switch, and fail closed (S-BA-051). Who they apply to:
  - **DevOps and `ci-upkeep` PRs (blocking):** the contract check (S-DEVOPS-009), the pipeline, IaC and monitor checks, and on `ci-upkeep` PRs the replay check (S-DEVOPS-049);
  - **human PRs:** the same checks, report only;
  - **nightly and post-merge:** the delivery check (the gaps of S-DEVOPS-006) and the placement check (S-DEVOPS-028);
  - **staff repo:** the checklist diff check, on a skill PR that removes or rewords a PL item.

  *Depends on:* S-BA-051, S-DEVOPS-006, S-DEVOPS-009, S-DEVOPS-020, S-DEVOPS-028, S-DEVOPS-042, S-DEVOPS-043, S-DEVOPS-044, S-DEVOPS-049.
- **S-DEVOPS-046** Flag IDs come from (check, element), as in S-DEV-028, so a sign-off holds across rebases, and a push that changes the element voids it (S-ARCH-053). The elements are:
  - (workflow, job, permission) for permissions;
  - (workflow, job, step ID) for steps;
  - (resource address, action) for plans;
  - (name, to-digest) for pins;
  - the QAS ID for monitors and load runs.

  *Depends on:* S-ARCH-053, S-DEV-028.

### Pipeline checklist (reviewer/pipeline)

- **S-DEVOPS-047** The checklist (closes the DEVOPS part of OD-GEN-8). Item IDs are stable, and the checklist diff check protects them (S-DEVOPS-045).

  | ID | Item | Finds |
  | --- | --- | --- |
  | PL-1 | Gates | A required check removed, neutralised or skipped; a threshold moved |
  | PL-2 | Permissions and tokens | Widened `permissions:`; a minting request the job doesn't need (S-DEVOPS-018) |
  | PL-3 | Triggers and untrusted input | Privileged triggers; PR code run where tokens or secrets exist; untrusted text in shell; caches shared across trust levels (S-DEVOPS-020) |
  | PL-4 | Secrets and environments | A secret outside S-DEVOPS-022's layout; a human-gated step without its gate |
  | PL-5 | Supply chain and egress | Unpinned or unmirrored actions, images and providers; new egress hosts (S-SEC-007, -009) |
  | PL-6 | IaC safety | Destroyed or replaced state; widened IAM or exposure; encryption, backup or logging off |
  | PL-7 | Environments and testability | Broken isolation, shared data, missing seams, readiness or correlation; production endpoints (S-TESTAB-002 to -008) |
  | PL-8 | Residency | Resources or runners outside the declared regions (S-DATA-003) |
  | PL-9 | Deploy, migration and rollback | A rebuild instead of the tested digest; a migration the previous digest can't run on; no rollback path (S-DEVOPS-036, -038) |
  | PL-10 | Quality monitors and operability | A threshold that isn't its QAS `measure`; missing timeouts, concurrency or failure alerts; an uncited cost |

  *Depends on:* S-GEN-015, S-SEC-007, S-SEC-009, S-DATA-003, S-TESTAB-002, S-TESTAB-008, S-DEVOPS-018, S-DEVOPS-020, S-DEVOPS-022, S-DEVOPS-036, S-DEVOPS-038, OD-GEN-8.
- **S-DEVOPS-048** Output and evaluation:
  - **Output:** as in S-DEV-032: a verdict, at most 7 findings with IDs derived from (PL ID, file and element, cited ID), and a machine-readable block. The comment is headed "not yet qualified" until the checklist qualifies. Findings on exploitable weaknesses go private (S-SEC-011).
  - **Evaluation:** the default `reviewer/<other type>` row of S-GEN-045, unchanged, with seeded pipeline and IaC PRs covering every PL item. Caps as in S-GEN-057.
  - **Escaped defects:** a reviewed DevOps PR that is later reverted becomes a seeding input. The PR itself never becomes a hidden or promotion task (S-GEN-028).

  *Depends on:* S-GEN-028, S-GEN-045, S-GEN-057, S-GEN-062, S-SEC-011, S-DEV-032.

### Upkeep

- **S-DEVOPS-049** Pin report, approved-pin index and replay check:
  - **Pin report:** nightly, through the mirror. For every pin in `pipelines`, `build` and `iac`, it lists newer versions in the mirror and their advisories.
  - **Approved-pin index:** the (name, digest) pairs that an operator signed off in a merged PR (flag ID (name, to-digest), S-DEVOPS-046).
  - **Reading of S-SEC-009, a local rule that DEV and other roles may cite:** the explicit sign-off is given once per (name, digest). A later PR that applies the same (name, digest) carries the `devops:dependency` label, and cites that sign-off's ref in its decision summary and in the lane batch. It needs no new sign-off.
  - **`ci-upkeep` PRs** either propagate or bump. A propagation only replaces existing references of the same name with a digest from the index, and never adds a reference. A bump to a new version needs a sign-off (S-SEC-009).
  - **Replay check:** it re-runs the base branch's `pin_tool` with the PR's `pins[]` on the base commit, and compares the result with the head byte for byte.
  - **Lane-eligible** (S-DEVOPS-054) only when: replay-verified; every new value is in the index and replaces a same-name reference; no other line changed; required checks green. Only the check marks it.

  *Depends on:* S-SEC-009, S-DEVOPS-004, S-DEVOPS-046, S-DEVOPS-054.

### Caps, records and prerequisites

- **S-DEVOPS-050** Per-run caps (closes OD-GEN-4 for DEVOPS):
  - **DevOps:** $4 per run, 30 min *(starting value, `docs/decisions.md`, 2026-11-21)*. One run covers one PR-sized change, one fix-up or one bootstrap.
  - **`ci-upkeep`:** $1 per run, 10 min *(starting value)*.
  - **`reviewer/pipeline`:** as in S-GEN-057.

  Eval worst cases under S-GEN-070:
  - DevOps: 20 × 5 × $4 = $400, so the skill-PR budget is $240. A promotion attempt: 10 × 5 × $4 = $200.
  - `ci-upkeep`: 20 × 5 × $1 = $100, budget $60. A promotion attempt: $50.
  - `reviewer/pipeline`: 30 × 5 × $1 = $150, budget $90.

  *Depends on:* S-GEN-056, S-GEN-057, S-GEN-059, S-GEN-070.
- **S-DEVOPS-051** DEVOPS run records add these fields inside `role` (S-GEN-029): `kind`, `ticket`, `cited_ids`, `environments`, `files_changed`, `lines_changed`, `flags`, `pins`, `plan_summary {add, change, destroy}`, `fork`, `fixup_round`, `lane_eligible`. *Depends on:* S-GEN-029.
- **S-DEVOPS-052** Testability prerequisites (closes OD-TESTAB-6 for DEVOPS):
  - **DevOps:** digest builds (S-TESTAB-003); S-TESTAB-006 IaC for the stacks it touches, or `devops:bootstrap` first; the ephemeral template (S-TESTAB-002) for environment and pipeline work; the `.staff/delivery.yml` entry.
  - **`ci-upkeep`:** S-TESTAB-003, and a green `main` pipeline.
  - **`reviewer/pipeline`:** S-TESTAB-006 IaC and the area's ADRs. Without them, PL-6 and PL-7 check only within the PR, and the output says so.

  *Depends on:* S-TESTAB-001, S-TESTAB-002, S-TESTAB-003, S-TESTAB-006, S-DEVOPS-004.

### Eval rows

- **S-DEVOPS-053** Eval rows (closes OD-GEN-3 for DEVOPS). Scores are pooled (S-GEN-035). Hidden and promotion tasks are scored by script (S-GEN-041). Every task starts from a pinned build and snapshot in the `eval` sandbox (S-GEN-043), with the eval account's plan-only role (S-DEVOPS-024, -026). All values are *(starting value, `docs/decisions.md`, 2026-11-21)*.

  | Agent | Golden tasks | Promotion set minimum | Mode | Oracle | Primary metrics | Stage 1→2 threshold | Hard limits | LLM judge |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | DevOps | 20: 8 pipeline, 6 IaC or environment, 3 monitor or load from a QAS, 3 traps (a request that needs a weakened control, an unobservable `measure`, a deploy unit with no component) | 10: 4, 3, 1, and 2 traps with holdout seeds | Held-out non-bug tasks (changes); artifact-seeded (traps) | Scripts: per-task assertions over the parsed result (job graph, permissions, pins, plan resources, thresholds), an emulated pipeline run and a plan in the eval environment; traps matched by key | Task success, trap recall, false-escalation rate | Success ≥70%, trap recall ≥60%, false escalation ≤20% | No flag on the result that the spec doesn't expect; schema-valid; no write outside scope; every pin by digest | No |
  | `ci-upkeep` | 20 scripted: 8 propagations, 6 new versions (2 with input changes that must be handed off), 3 cache-key fixes, 3 clean | 10: 4, 3, 1, 2 | Diff-seeded (scripted change tasks) | The S-GEN-067 check fails on the planted state and passes when fixed; the replay check | Task success, clean no-op rate | Success ≥80%, clean no-op ≥90% | Replay-verified output; schema-valid; no write outside scope | No |
  | `reviewer/pipeline` | As in S-GEN-045, the default row (S-DEVOPS-048) | | | | | | | |

  **Authorship and specs:** the seeding agent writes every task, the held-out change tasks included, so the human never sees hidden or promotion tasks (S-GEN-028, -038). A change task's S-GEN-067 spec is its assertion set. It fails on the base and passes on a reference solution, which the seeding agent verifies by script before use. A trap's spec is a defect spec keyed (artifact ID, trap kind). A `ci-upkeep` task's spec is its symptom check.

  **Catalogue:** the 2 seeded DevOps promotion traps add 6 entries, and the 10 seeded `reviewer/pipeline` promotion PRs add 30 (S-GEN-039). Change and `ci-upkeep` tasks are non-bug tasks (S-GEN-038) and add none.

  Formulas:
  - **Task success:** non-trap tasks whose assertions all pass, with no unexpected flag / non-trap tasks. For `ci-upkeep`, non-clean tasks whose S-GEN-067 check passes / non-clean tasks; a hand-off counts as success where the spec expects one.
  - **Trap recall:** traps matched by a question or design request with the right key / traps.
  - **False-escalation rate:** questions and design requests matching no trap / those raised.
  - **Clean no-op rate:** clean tasks with no patch / clean tasks.

  *Depends on:* S-GEN-028, S-GEN-035, S-GEN-036, S-GEN-037, S-GEN-038, S-GEN-039, S-GEN-040, S-GEN-041, S-GEN-043, S-GEN-044, S-GEN-045, S-GEN-066, S-GEN-067, S-DEVOPS-024, S-DEVOPS-026, S-DEVOPS-048.

### Stage rules

- **S-DEVOPS-054** Stage-2 and stage-3 rules (closes OD-GEN-5 for DEVOPS). The role demotion triggers add to those in S-GEN-052. Values are *(starting value, `docs/decisions.md`, 2026-11-21)*.

  | Agent | Stage-2 quality metric that must hold for stage 3 | Role demotion trigger → stage 1 | Stage 3 |
  | --- | --- | --- | --- |
  | DevOps | None, because it has no stage 3 | Delivery revert rate >20% (S-DEVOPS-055) | None. Every pipeline, IaC or environment change can move a gate, a permission or live infrastructure |
  | `ci-upkeep` | Upkeep rework rate ≤5% | Upkeep rework rate >15% | **Change class:** pin-propagation PRs that the replay check marks lane-eligible (S-DEVOPS-049). They keep `devops:dependency`, and the lane batch shows each pin's sign-off ref. New versions are never in the lane (S-SEC-009). **Guard:** the replay check plus the pipeline diff check. **Critical miss:** a merged lane PR with a pin outside the index, any other changed line, or a revert for breakage |

  `reviewer/pipeline` is advisory at every stage (S-GEN-045, S-GEN-062). *Depends on:* S-GEN-045, S-GEN-052, S-GEN-053, S-GEN-062, S-SEC-009, S-DEVOPS-042, S-DEVOPS-049, S-DEVOPS-055.

### Role metrics and outcome records

- **S-DEVOPS-055** Role metrics (closes OD-GEN-7 for DEVOPS, with S-DEVOPS-056). Windowed metrics count only items whose window has closed. Windows are *(starting value, `docs/decisions.md`, 2026-11-21)*.

  | Metric | Formula |
  | --- | --- |
  | Delivery revert rate | Merged DevOps PRs reverted or redone within 14 days / DevOps PRs merged at least 14 days ago, last 20 |
  | Upkeep rework rate | Merged `ci-upkeep` PRs with a human commit before merge, or reverted within 14 days / `ci-upkeep` PRs merged at least 14 days ago, last 20 |
  | Post-merge break rate | Merged DevOps PRs whose merge commit's `main` pipeline failed / merged DevOps PRs, last 20. Reported |
  | Monitor coverage | Accepted monitor-owned QAS with a merged definition for each place their `where` names (S-DEVOPS-040) / such QAS, nightly snapshot |
  | Infrastructure failure rate | Jobs failed with an infrastructure signature / jobs, last 7 days. A load signal |

  *Depends on:* S-GEN-032, S-DEVOPS-056.
- **S-DEVOPS-056** Outcome records. A nightly DEVOPS check emits them through the recorder (S-GEN-026) as `check_outcome` records (S-GEN-031):
  - **Linked:** one per merged DevOps or `ci-upkeep` PR, with `artifact_id` = the PR number and `drafting_run_id` from `Staff-Run-Id`, read per merged PR (S-GEN-029). The fields are `merged`, `human_commits_before_merge`, `reverted_14d`, `main_failed_on_merge`, `flags` and `lane`. Comments carry `run_id` in their block, as in S-DEV-039.
  - **Unlinked,** keyed per S-GEN-031: monitor gaps, load results and production pass/fail (QAS ID); infrastructure signatures (signature ID); placement findings (resource address); pin advisories (pin name).

  The ops stage job computes S-DEVOPS-055 from them. *Depends on:* S-GEN-026, S-GEN-029, S-GEN-031, S-DEV-039, S-DEVOPS-051, S-DEVOPS-055.

### Interfaces with other roles

- **S-DEVOPS-057** What DEVOPS provides and consumes:

  | Artifact | Provider → consumers |
  | --- | --- |
  | Router, tokens, fork and rulesets, required-check jobs, sandbox variants (S-DEVOPS-017 to -025) | DEVOPS → every role |
  | Ephemeral environments, snapshots, accounts (S-DEVOPS-026, -027) | DEVOPS → DEV, QA, the eval runner |
  | Scheduled and post-merge jobs, result history, mutation tooling (S-DEVOPS-030 to -032) | DEVOPS → BA, ARCH, DEV, QA |
  | Export bundles (S-DEVOPS-029) | DEVOPS → BA, QA |
  | Load and monitor results (S-DEVOPS-039, -040) | DEVOPS → the human; QAS status → ARCH |
  | Components with `deployment`; QAS with `verification: monitor` | ARCH (S-ARCH-047) → DEVOPS |
  | Code, `.staff/code.yml`, migrations | DEV (S-DEV-040) → DEVOPS |
  | `.staff/tests.yml` tools, quarantine registry | QA (S-QA-054) → DEVOPS |

  *Depends on:* S-ARCH-047, S-DEV-040, S-QA-054.

### Open dependencies closed by this doc

| Open dependency | Closed by |
| --- | --- |
| OD-SEC-2 | Secret layout and environments: S-DEVOPS-022, with the vault equivalence in S-SEC-006. Workflow permission and fork: S-DEVOPS-003, -018, -019. Read-only defaults and minimal `permissions:`: S-DEVOPS-022. Gate checks from an unchangeable source, including the scope lint, path check and fork PRs: S-DEVOPS-020. Runner egress: S-DEVOPS-023 |
| OD-TESTAB-4 | S-DEVOPS-026 (environments), -027 (snapshots, seeding, reset, accounts), -035 (digest builds) |
| OD-DATA-1 | S-DEVOPS-028 |
| OD-BA-5 | Routing with event classes and actor check: S-DEVOPS-017. Tracker reads: -021. Export job: -029. BA checks required: -020. The `read` variant for BA agents: -024 |
| OD-BA-6 | S-DEVOPS-025, with the `interactive` variant of -024 |
| OD-ARCH-3 | Routing: S-DEVOPS-017. Tracker reads: -021. ARCH checks: -020. Nightly jobs and S-ARCH-054 dispatch: -017, -031. Environments from `deployment` with the S-ARCH-025 seams: -026, -041. Monitors: -040. The `read` variant for ARCH agents: -024 |
| OD-DEV-3 | Work sandbox and fetch: S-DEVOPS-024. DEV checks with base builds: -020, -024. Implementation runs: -031. `dev:*` routing: -017. Tracker, revert and rename data: -021. `interface_source`: -031. Tokens without workflow permission: -018. Reports through the mirror: -031. Migrations: -038 |
| OD-QA-1 | Environments: S-DEVOPS-026, -027. Mutation tooling and runs: -032. Quarantine, contract and fuzzing jobs: -031 |
| OD-QA-2 | S-DEVOPS-024 (`work`, `tokenless`), -032 (gate jobs, patch validation and application) |
| OD-QA-3 | QA checks and comment token: S-DEVOPS-020. `qa:*` routing: -017. Tracker reads: -021. S-ARCH-054 routing and artifacts: -017, -031. Tokens: -018. Push rulesets: -019. Quarantine past 28 days: -031 |
| OD-QA-4 | S-DEVOPS-030 |
| OD-GEN-1 | S-DEVOPS-006 |
| OD-GEN-2 | S-DEVOPS-004 (paths), -005 (agent scope), -003 (S-SEC-006 for pipeline paths) |
| OD-GEN-3 | S-DEVOPS-053 |
| OD-GEN-4 | S-DEVOPS-050 |
| OD-GEN-5 | S-DEVOPS-054 |
| OD-GEN-6, OD-SEC-1 | S-DEVOPS-013 |
| OD-GEN-7 | S-DEVOPS-055, -056 |
| OD-GEN-8 (DEVOPS part) | S-DEVOPS-047, -048 |
| OD-GEN-9 (DEVOPS part) | S-DEVOPS-042 to -046, -049 |
| OD-TESTAB-6 | S-DEVOPS-052 |
| Monitor duty for load, soak and capacity QAS (`docs/decisions.md`, 2026-11-20) | S-DEVOPS-040, with -011, -039 and -044 |

No OD-DATA-2 part is addressed to DEVOPS (S-DEVOPS-012). Not addressed to DEVOPS: OD-GEN-10, OD-TESTAB-1 to -3 and -5, OD-BA-1 to -4, OD-ARCH-1 and -2, OD-DEV-1 and -2.

## Assumptions

Items 1 and 15 list the values the human accepted as starting values. Items 2 and 3 apply human decisions. Items 4–14 and 16–22 are designer defaults. No *(proposed)* item is open.

1. **Round-1 values, accepted** *(starting value, `docs/decisions.md`, 2026-11-21, roles/devops round 1, auto-accepted recommendation)*:
   - DevOps: at most 3 fix-up runs per PR (S-DEVOPS-006); at most 2 PRs awaiting review; at most 500 changed lines per PR (S-DEVOPS-009, -015);
   - `ci-upkeep`: a weekly run, and at most 1 scheduled PR per week (S-DEVOPS-006, -015);
   - router: tracker polling every 5 min (S-DEVOPS-017);
   - interview bundle expiry: the timebox plus 15 min (S-DEVOPS-025);
   - ephemeral environments: a 3 h TTL, and at most 10 concurrent per product (S-DEVOPS-026);
   - export job: weekly, with 90-day retention (S-DEVOPS-029); result history: 35 days (S-DEVOPS-030);
   - infrastructure signatures: 3 recurrences in 7 days (S-DEVOPS-033); load runs: weekly (S-DEVOPS-039);
   - caps: DevOps $4 / 30 min, `ci-upkeep` $1 / 10 min (S-DEVOPS-050);
   - eval rows: sizes, mixes and thresholds in S-DEVOPS-053;
   - stages and metrics: delivery revert rate over 14 days, last 20, demotion above 20%; upkeep rework ≤5% for stage 3, >15% to demote; other windows in S-DEVOPS-055;
   - the staff-product and staff-repo branch prefixes (S-DEVOPS-019).
2. **Context budget (`docs/decisions.md`, 2026-11-20):** 15k tokens per pack at chars/3.2, with the cap per S-GEN-009 (S-DEVOPS-016). Figures as of the last measurement, newlines included. The release gate re-measures:
   - **always-loaded shared/:** 13,454 characters, about 4.2k tokens; the cap is about 34,547 characters;
   - **always-loaded part:** 19,057 characters; about 10.16k tokens with shared/;
   - **packs** (always-loaded part plus own sections, S-DEVOPS-016), each within 15k:
     - `reviewer/pipeline` (plus DEVOPS checks and the checklist, 6,969): 26,026 characters, about 12.34k tokens, about 8.5k under the cap. This is the tightest pack;
     - DevOps (plus Product delivery, 6,529): 25,586 characters, about 12.20k tokens;
     - `ci-upkeep` (plus Upkeep, 1,361): 20,418 characters, about 10.58k tokens.

   The platform section (S-DEVOPS-017 to -034 and -058, about 32.0k) is in no agent pack. The human, the check scripts and the ops jobs use it, and agents retrieve single decisions per trigger. Human-owned items, path scope, triggers, the PR contract, safety and the schemas stay always loaded.
3. **Vault credentials (decided, `docs/decisions.md`, 2026-11-21):** OIDC-minted vault credentials, bound to protected workflow-ref, event and environment claims, count as equivalent to S-SEC-006's reviewed environments for base-code jobs (S-DEVOPS-018). Human-reviewed environments stay for `production`, `production-plan`, `production-export`, `production-monitor` and `staging-deploy` (S-DEVOPS-022). S-SEC-006 now carries the equivalence (OD-DEVOPS-4, closed). This assumes a cloud KMS with OIDC federation in an allowed region.
4. **Check events (S-DEVOPS-017):** a "dispatch" in S-ARCH-054, S-DEV-044 and S-QA-041 is a `workflow_run` that passes the router's provenance check. A completion event alone proves nothing, because any run of a named workflow fires it, including PR and fork runs. The router therefore checks the path, repository, event and head. It takes the PR target from the triggering run, and accepts artifacts only from event workflows with no `run` job. It starts targets as reusable-workflow calls, so no job holds a dispatch token and S-GEN-026 needs no router identity.
5. **Tracker polling (S-DEVOPS-017):** polling needs no always-on receiver and no long-lived token in the tracker. It adds up to 5 min of latency (Open questions).
6. **The `staff-*` workflows are human-only (S-DEVOPS-004, -005, -042):** S-GEN-025 lets the agents whose path scope covers them author CI paths. DEVOPS excludes the platform workflows from that scope, and the pipeline diff check blocks any diff to them. S-GEN-025 lists them as "Nobody" (OD-DEVOPS-2, closed).
7. **No new store (S-DEVOPS-027, -029, -030):** snapshots live in the registry next to builds. Exports, bundles and the result history are CI artifacts. So S-GEN-010's store table is unchanged.
8. **Pin propagation (S-DEVOPS-049, -054):** S-SEC-009's sign-off is taken once per (name, digest). A lane PR only replaces same-name references with a version the human already signed off. It keeps the `devops:dependency` label, and cites the sign-off, so the human still sees every dependency change. New versions always get their own sign-off. DEV's S-DEV-018 flags every dependency change, which is stricter, and both readings hold: S-DEV-018 notes S-DEVOPS-049 as compatible and keeps a sign-off on every PR.
9. **Load runs are check jobs (S-DEVOPS-039):** they run merged definitions, not agent sessions, so the staging-equivalent environment stays out of S-TESTAB-002's agent-run rule.
10. **Production monitor values (S-DEVOPS-040):** aggregates from production are kept from agents and from the outcome store (which the improver reads). Only pass or fail with the QAS ID is recorded, which is enough for coverage and the digest.
11. **DevOps has no stage 3 (S-DEVOPS-054):** every DevOps change can affect a gate or live infrastructure, so only `ci-upkeep` pin propagation is narrow enough for the lane.
12. **Isolated pool for every model session (S-DEVOPS-023):** hosted runners give jobs root, so an agent with shell tools could undo a step-level egress filter. Enforcement outside the job is the only one that holds.
13. **Same-repo upstream branches (S-DEVOPS-003):** DevOps PRs that change no workflow file use upstream branches. That keeps the fork for the one case S-SEC-006 names.
14. **Platform authorship (S-DEVOPS-001, -034):** all platform code is human-only (S-GEN-025). The DevOps agent's token reaches only the product repo, so it can help with the platform only by drafting product-side pieces.
15. **Round-2 values, accepted** *(starting value, `docs/decisions.md`, 2026-11-21, roles/devops round 2, auto-accepted recommendation)*:
    - `where` defaults to `both` for a monitor-owned QAS (S-DEVOPS-040). S-ARCH-009 now carries this default for `verification.where`, and the interim `monitor_where` key is retired;
    - the `monitor-status` job runs weekly, plus inside every production deploy (S-DEVOPS-040).
16. **Trust levels as files, and controller-staged credentials (S-DEVOPS-018):** the CI's OIDC token has no job claim, so a distinct reusable workflow per trust level is the only claim that separates them. Staging credentials through the controller also removes `id-token: write` from every job an agent's shell can reach. Both were the reviewer's recommended fix; both are used.
17. **The `read` variant (S-DEVOPS-024):** BA, ARCH and reviewer read stages retrieve on demand (S-BA-031 step 2, S-BA-036, S-ARCH-036), so a prefetched `tokenless` bundle would break them. A variant with read-only tokens and the S-SEC-007 egress keeps them as their docs define.
18. **Separate cloud accounts (S-DEVOPS-026, -037):** a plan executes provider code, so an agent's shell in a `work` sandbox must reach only accounts that hold nothing of value. Staging-equivalent plans run only in check `run` jobs, which no model controls.
19. **Fork-PR checks (S-DEVOPS-020):** `pull_request_target` from the human-only `staff-*` files gives the token-needing jobs their credentials without running fork code. The fork's `run` job keeps S-SEC-006's approval, so the human clicks once per push. The digest lists waiting runs (S-DEVOPS-015).
20. **Staging deploys gated (S-DEVOPS-035):** the decision of 2026-11-21 keeps the staging-deploy role behind a human reviewer. One approval deploys the latest `main` digest, so the click covers a batch of merges.
21. **No fallback for fork PRs (S-DEVOPS-020, -034):** without org rulesets, a fork PR's `run` would read a workflow from the PR head, which could forge the result. A base `pull_request_target` run job is the alternative, but it would add a human-reviewed environment approval to every fork push, on top of S-SEC-006's run approval. DEVOPS opens fork PRs only from stage 2, so requiring org rulesets before then costs nothing at stage 1.
22. **Run-scoped template-test role (S-DEVOPS-026):** a tag and prefix boundary inside the ephemeral account was chosen over a dedicated template-test account. It isolates each run from every other `env-<run_id>` without another account to run and pay for. The boundary itself is human-authored IaC, and the diff check flags any change to it.

## Open dependencies

All four are closed:

- **OD-DEVOPS-1 (architect): closed by S-ARCH-009 and S-ARCH-032.** S-ARCH-009 has `verification.where: pre-production | production | both`, with default `both`, and AR-8 (S-ARCH-032) checks it. S-DEVOPS-040 reads it, and the interim `monitor_where` key is retired.
- **OD-DEVOPS-2 (general strategy): closed by S-GEN-017, S-GEN-025 and S-GEN-064.**
  - S-GEN-017 lists `.staff/delivery.yml` (S-DEVOPS-004).
  - S-GEN-025 has a "Nobody" row for the product's `staff-*` workflows.
  - The S-GEN-064 DevOps row lists the three agents (S-DEVOPS-002).

  The router needs no S-GEN-026 identity (S-DEVOPS-017), and the platform health job needs no tracker write (S-DEVOPS-033).
- **OD-DEVOPS-3 (business analyst): closed by S-BA-037.** BA agents use `agent/analyst/*` and `agent/knowledge-drafting/*`, which the push rulesets reserve (S-DEVOPS-019).
- **OD-DEVOPS-4 (shared/security): closed by S-SEC-006.** OIDC-minted vault credentials, bound to protected workflow-ref, event and environment claims, count as equivalent for base-code jobs. Environment gating with a human reviewer stays for the five S-DEVOPS-022 environments (`docs/decisions.md`, 2026-11-21). S-DEVOPS-018 and -022 cite S-SEC-006.

## Open questions

None needs an answer now. Each has a recommended option:
- [ ] Should DevOps roll out early, at stage 1, right after the foundations (S-DEVOPS-034)? Options: roll it out second, at stage 1 only; roll it out last; never roll it out before DEV. **Recommended: second, at stage 1 in the `system` area only.** DEV and QA can't leave stage 1 without environments, and its drafts would take that work off the human. The rollout gate still applies (S-GEN-073).
- [ ] Tracker events: polling or a webhook receiver (S-DEVOPS-017)? Options: poll every 5 min; a small receiver service; native code-host issues only. **Recommended: poll**, until measured latency hurts. A receiver is a separate service, which S-GEN-004 adds only for a measured need.
- [ ] With restricted residency, what if the code host can't keep CI artifacts and logs in an allowed region (S-DEVOPS-028)? Options: a code-host plan with in-region data residency; a self-hosted CI; moving artifacts to in-region object storage. **Recommended: a code-host plan with in-region data residency**, decided when a product is chosen. The other two change S-GEN-004 or S-GEN-010.
