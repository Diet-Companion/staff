---
name: review-pipeline
description: Checklist for reviewer/pipeline, the pipeline artifact type of the shared reviewer. Covers items PL-1 to PL-10, the delivery-PR block and delivery map it checks against, the platform rules it retrieves, what the DEVOPS diff checks already flag, and private reports. The harness preloads it when the target is a DevOps or ci-upkeep PR, or a human PR touching delivery paths labelled devops:review.
---

# Pipeline checklist (reviewer/pipeline)

Source: `docs/strategy/roles/devops.md`, S-DEVOPS-047 and S-DEVOPS-048, with the DEVOPS checks (S-DEVOPS-042 to S-DEVOPS-046) that S-DEVOPS-016 puts in this pack. DEVOPS owns this checklist (S-DEVOPS-002). Output: `schemas/review-output.schema.json` with `artifact_type: pipeline`. Item IDs are stable, and the checklist diff check protects them (S-DEVOPS-045).

## Run (S-DEVOPS-005, S-DEVOPS-006, S-DEVOPS-013, S-GEN-057)

- **Starts when** a DevOps or `ci-upkeep` PR becomes ready for review or has its review re-requested, or when an operator applies `devops:review` to a human PR that touches delivery paths. A DevOps PR that changes `pipelines` files comes from the DEVOPS fork (S-DEVOPS-003).
- **Write stage:** one comment, the label `devops:not-ready`, and private reports. No paths.
- **Caps:** $1 and 10 min *(starting value)*.

## What you check against

- **PR block** (S-DEVOPS-009):
  - `kind`: pipeline, iac, environment, monitor, load or upkeep, plus `ticket`;
  - `cites[]`: QAS, CMP, ADR-n/C-k or IF versions;
  - `environments[]` and `plan_refs[]`;
  - `pins[] {name, from, to, signoff_ref}` and `flags[]`.

  The decision summary shows the net permission, egress, secret and environment changes, and the plan summary per stack (S-DEVOPS-015).
- **Delivery map** `.staff/delivery.yml` (S-DEVOPS-004), read from the base:
  - `pipelines`, `build` and `iac` globs;
  - `environments` (ephemeral, staging-equivalent, production);
  - `deploy_units`, `migrations`, `monitors`, `load` and `pin_tool`.

  `staff-*` workflows are platform files that no agent changes.
- **Safety** (S-DEVOPS-010 to S-DEVOPS-012):
  - never remove, skip or neutralise a required check, widen `permissions:`, egress or a secret's reach, or loosen an IaC safeguard to make output pass;
  - never plan, apply or deploy against production, or read production state;
  - every monitor or load definition carries `cites: QAS-n`, and its threshold equals the QAS `measure`, unit included.
- **Platform rules** (condensed from the decisions S-DEVOPS-016 has you retrieve):
  - **Credentials (S-DEVOPS-018):** no stored cloud, app or model credential. Credentials are minted by OIDC, per trust level, with the shortest lifetime. Isolated-pool jobs never hold `id-token: write`. Write tokens exist only at the `write` level.
  - **Required checks (S-DEVOPS-020):** they come from a source the PR can't change. `facts` and `report` jobs run base code only. A `run` job has `contents: read`, no tokens, and never saves a cache that `main` restores.
  - **Secrets and environments (S-DEVOPS-022):** CI secrets reachable from `agent/*` branches hold only test accounts. `production`, `production-plan`, `production-export`, `production-monitor` and `staging-deploy` are human-gated. Every workflow sets top-level `permissions: {}` and minimal permissions per job.
  - **Runner pools (S-DEVOPS-023):** jobs that run PR code, agent-written code or a model session run on the isolated pool, with egress enforced outside the job.
  - **Ephemeral environments (S-DEVOPS-026):** they use their own accounts, with no trust path to staging, production or the vault. A run-scoped tag and name prefix sit under a permission boundary. They never hold a production endpoint or credential.
  - **Placement (S-DEVOPS-028):** runners, stores, the vault and clusters sit in an allowed region.
  - **Stages (S-DEVOPS-035 to S-DEVOPS-038):** a build is made once per commit, to an attested digest, and that digest is promoted with no rebuild. Production deploy and rollback are human-gated jobs. Migrations are expand-and-contract, so a rollback never needs a down-migration. A PR plans only ephemeral stacks; the production stack gets static checks only.
  - **Seams (S-DEVOPS-041):** `run_id` correlation and readiness are wired in every environment. The S-TESTAB-008 seams are on only outside production.

## What scripts already flag (S-DEVOPS-042 to S-DEVOPS-046)

These checks block DevOps and `ci-upkeep` PRs and only report on human PRs. Every flag needs a sign-off (G3). Read their outputs, and don't repeat them as findings:
- **Pipeline (blocked):** a required check removed or neutralised (`continue-on-error`, skip conditions, `|| true`, changed test selection); a scan or attestation step removed; new privileged triggers; a tag instead of a digest; untrusted text in shell; PR code off the isolated pool; any `staff-*` diff.
- **Pipeline (flagged):** widened `permissions:`; new secrets, environment bindings or minting; new egress; new or upgraded pins; a removed timeout or concurrency group; a PR-writable cache restored on `main`.
- **IaC (blocked):** production endpoints in ephemeral or staging definitions, out-of-region resources, seams enabled in production, plaintext secrets.
- **IaC (flagged):** destroy or replace; reduced deletion protection or backups; widened IAM or network; encryption or logging off; loosened isolation, TTL or boundary; any production-stack change.
- **Monitor and load:** a threshold that isn't the QAS `measure`; a definition removed while its QAS is accepted; a QAS that isn't `monitor` with owner DEVOPS.

Flag IDs are (check, element) (S-DEVOPS-046). Your findings cover what parsing can't judge: whether a permission or mint is needed, whether a gate still gates, whether a rollback works, and whether a cost is cited.

## Checklist (S-DEVOPS-047)

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

## Output specifics (S-DEVOPS-048)

- **Findings** carry `suggestion`: the change you suggest.
- **Finding ID:** `PL-n|<file>#<element>|<primary cited ID>`. The element is the job, step ID, permission, resource address or pin name, for example `PL-2|.github/workflows/build.yml#jobs.test.permissions|S-DEVOPS-018`. The primary cited ID is the QAS, ADR constraint or S-ID the finding rests on.
- **`classification`:** always `issue`.
- **`private_reports`** (S-SEC-011): an exploitable weakness or exposed secret goes here, never into a finding, and refers to a secret by location only. To make it count toward `not_ready`, add a blocker finding that names only the location and says "details withheld (S-SEC-011)".
- **Questions:** S-BA-014 form.

## Prerequisites and retrieval (S-DEVOPS-016, S-DEVOPS-052)

- **Prerequisite:** S-TESTAB-006 IaC and the area's ADRs. Without them, PL-6 and PL-7 check only within the PR, and `decision_summary` says so.
- **Always:** this checklist and the `.staff/delivery.yml` entry.
- **On demand:** the diff and PR block, plan summaries, check outputs, and the cited QAS, components and ADRs.
