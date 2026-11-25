---
name: devops-delivery
description: The DevOps agent's own pack section - product delivery rules. Covers pipeline stages and digest builds, deploy and rollback, IaC plan and apply, data migrations, the staging-equivalent environment and load runs, QAS monitor duty, observability and control seams, and the ephemeral environment template. Use when drafting pipelines, environment definitions, deploy steps, IaC, monitors or load runs.
---

# Product delivery (S-DEVOPS-035 to S-DEVOPS-041)

Source: `docs/strategy/roles/devops.md`, "Product delivery", the DevOps pack's own section (S-DEVOPS-016). Stack-agnostic: the tools are whatever `.staff/delivery.yml` declares.

## Pipeline stages (S-DEVOPS-035)

1. **PR:** build once per commit, to a digest (S-TESTAB-003), with a provenance attestation. Required checks run (S-DEVOPS-020): the product suites without quarantined tests, the role checks, image and dependency scans, and, for delivery changes, validation and the test-environment plan.
2. **`main`:** the merge build's digest is the one every later stage uses. Nothing is rebuilt.
3. **Staging-equivalent:** deploy the latest `main` digest in the human-gated `staging-deploy` environment. Migrations first (S-DEVOPS-038), then the smoke checks. One approval covers every merge since the last deploy.
4. **Production:** human-gated (S-DEVOPS-036).

Ephemeral environments are per run, not a stage (S-DEVOPS-026). Draft pipelines that keep this shape: no rebuild after `main`, no stage that skips its gate.

## Deploy and rollback (S-DEVOPS-036)

- A production deploy is a job in the `production` environment, which the human approves. It deploys only a digest that has the `main` attestation and passed the staging-equivalent smoke checks.
- The job summary, which the human sees before approving, shows the latest load results (S-DEVOPS-039).
- Rollback is the same job with the previous recorded good digest, behind one approval. Migrations are expand-and-contract, so a rollback never needs a down-migration.
- You draft these jobs. You never run them.

## IaC plan and apply (S-DEVOPS-037)

- **On PRs:** the `work` sandbox validates and plans only the ephemeral stacks, with the plan-only role (S-DEVOPS-026). The staging-equivalent stack is planned only in the check's `run` job, never in your session. The production stack is never planned on a PR; it gets static checks only (S-DEVOPS-043).
- **Secrets in state:** the staging-equivalent state holds no non-test secret. Secrets are generated and kept in the vault and referenced by name. Never write a secret value into a definition.
- **After merge:** a human-gated `production-plan` job writes the full plan inside the production account and publishes only the destroy and replace summary (addresses and actions, no values). A human-gated `production-apply` job applies exactly that plan, by digest. A plan that destroys or replaces a stateful resource also needs an operator sign-off citing those flag IDs (S-DEVOPS-046); the apply job fails closed without it.

## Data migrations (S-DEVOPS-038)

- The deploy runs the delivery map's `migrations` command at the deploy digest as its own step, before the app rollout, in each environment. In production that step is inside the approved job. Ephemeral environments apply every migration at provisioning.
- **Expand and contract:** a migration must leave the previous digest working. The staging-equivalent deploy runs the previous digest's smoke checks against the migrated schema.
- **Contract steps** (drop or narrow) ship only in a later release, once no deployed digest uses the old shape.
- DEV owns and flags every migration diff (S-DEV-004, S-DEV-018). You wire the step; you don't write migrations.

## Staging-equivalent environment and load runs (S-DEVOPS-039)

- Persistent; built from the same IaC modules as production, with synthetic data at volume. It never holds real data, and no agent runs against it (S-TESTAB-002).
- **Load, soak and capacity runs** are scheduled check jobs, weekly *(starting value)* and on dispatch before a production deploy. They run the merged `delivery/load/QAS-n` definitions with the declared tool.
- **Results** per QAS: the measured value against the `measure`, as an unlinked `check_outcome` (S-GEN-031) in the digest. Nothing blocks automatically; the human decides at the deploy approval.

## QAS monitor duty (S-DEVOPS-040)

Covers every accepted QAS with `verification: monitor`, owner DEVOPS (S-ARCH-009).

| `verification.where` | Needs |
| --- | --- |
| `pre-production` | A load definition `delivery/load/QAS-n.<ext>` |
| `production` | A monitor definition `delivery/monitors/QAS-n.<ext>`, deployed with the production gate |
| `both` (the default when missing) | Both |

- Each definition carries `cites: QAS-n`; its threshold equals the QAS `measure`, unit included (S-DEVOPS-011).
- A QAS is covered when it has a merged definition for each place its `where` names. A missing one is a nightly finding that starts you.
- A QAS whose `measure` nothing can observe is a design request (`need: testability`), never a looser threshold (S-DEVOPS-008).
- Production monitor values stay in the monitoring stack, which only the human reads. A human-gated `monitor-status` job emits only QAS ID, pass or fail, and date.

## Observability and control hooks (S-DEVOPS-041)

- Every environment definition wires `run_id` correlation and a readiness endpoint (S-TESTAB-007). Logs and traces go to a per-environment store.
- The S-TESTAB-008 seams (feature flags, clock, fakes) are enabled only in ephemeral and staging-equivalent environments. Production sets them off; the IaC check blocks enabling them there.

## The ephemeral template (S-DEVOPS-026, S-DEVOPS-027)

The template lives in `delivery/environments/ephemeral/`. You may draft it; the human-authored provisioner applies only the base branch's version.
- Its deploy units come from component `deployment` fields (S-ARCH-007). Each runtime dependency is provisioned or replaced by a fake at its seam, as the environment's settings say (S-ARCH-025).
- It starts from a pinned digest and a synthetic snapshot, waits for readiness, and gets only test-account credentials (S-TESTAB-003, S-TESTAB-004).
- It never carries a production endpoint or credential, and it keeps its isolation and TTL (S-DEVOPS-043 flags any loosening).
- A deploy unit with no component, or a component `deployment` with no deploy unit, is a design request (`need: deployment`).
