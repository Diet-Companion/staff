---
name: devops-controls
description: On-demand DEVOPS reference for the DevOps and ci-upkeep agents. Covers the security and pinning rules a draft must meet, what the DEVOPS diff checks block and flag (pipeline and build, IaC and environment, monitor and load), flag IDs and the sign-off form, and the human-built platform controls an agent is measured against but never drafts. Use when drafting or fixing any pipeline, build, IaC, environment, monitor, load or pin change.
---

# DEVOPS controls (S-DEVOPS-042 to S-DEVOPS-046, S-DEVOPS-049; platform S-DEVOPS-017 to -034, -058)

Source: `docs/strategy/roles/devops.md`, "On-demand reference". These sections are on demand in the strategy (S-DEVOPS-016): the fetch step adds them per trigger. The checks are human-authored scripts (S-DEVOPS-045). They run as required checks, read no switch and fail closed. Your draft is measured against them; you never change them (G3, G4).

## Security and pinning rules for every draft

- **Pin by digest.** Every action, image, base image, runner image and IaC provider is referenced by digest (or full commit SHA), from the package mirror or an allowlisted registry, never by tag (S-SEC-009, S-DEVOPS-042).
- **New or upgraded dependency:** a new or upgraded action, image, base image, runner image or provider gets the `devops:dependency` label and needs an operator sign-off once per (name, digest) (S-SEC-009). Put it in `pr.pins[]` with `signoff_ref: null`, and in `pr.flags[]`.
- **Propagation** (S-DEVOPS-049): a later PR that applies a (name, digest) already signed off in a merged PR keeps `devops:dependency`, cites that sign-off's ref in `pins[].signoff_ref` and the decision summary, and needs no new sign-off. It only replaces existing references of the same name and never adds one.
- **Permissions:** every product workflow sets top-level `permissions: {}` and declares minimal permissions per job (S-DEVOPS-022). Never add `id-token: write` to a job on the isolated pool (S-DEVOPS-018).
- **Triggers:** never add `pull_request_target`, `workflow_run`, `issue_comment` or `repository_dispatch` to a product workflow. Never interpolate untrusted event text into a shell step.
- **Secrets:** CI secrets reachable from `agent/*` branches hold only test-account credentials (S-SEC-005, S-TESTAB-004). Production, deploy, export, monitor and staging-deploy steps run only in the human-gated environments `production`, `production-plan`, `production-export`, `production-monitor` and `staging-deploy` (S-DEVOPS-022). Never write a plaintext secret value; reference vault secrets by name.
- **Runners and egress:** a job that runs PR code, agent-written code or agent-changed configuration stays on the isolated pool. Add no egress host the job doesn't need (S-SEC-007, S-DEVOPS-023).
- **Residency:** every resource and runner sits in a region `.staff/product.yml` allows (S-DATA-003, S-DEVOPS-028).
- **Caches:** never let a PR run write a cache that `main` restores.

## Pipeline and build diff check (S-DEVOPS-042)

Parses base and head and compares each job's effective settings as a net set, so moving a step isn't flagged.

| Blocked | Flagged (needs a sign-off) |
| --- | --- |
| A job or step that produces a required check removed or neutralised: `continue-on-error`, a skipping condition or path filter, exit-code masking (`\|\| true`, `set +e`), changed test-selection arguments | Net widening of a job's `permissions:`, including `id-token: write` on trusted-pool jobs |
| A scan or provenance-attestation step removed from a build (S-DEVOPS-035) | A new secret reference, environment binding or minting request |
| A new privileged trigger in a product workflow | A new egress host |
| An action, image or base image referenced by tag instead of digest | A new or upgraded action, image, base image or runner image (`devops:dependency`), unless a propagation S-DEVOPS-049 verifies; a propagation keeps the label |
| Untrusted event text interpolated into a shell step | A removed timeout or concurrency group |
| A job that runs PR code moved off the isolated pool; `id-token: write` on an isolated-pool job | A cache that a PR run can write and `main` restores |
| Any diff to `staff-*` workflows | |

## IaC and environment diff check (S-DEVOPS-043)

From a static parse plus the test-environment plan.

| Blocked | Flagged |
| --- | --- |
| A production endpoint or credential in an ephemeral or staging-equivalent definition | Any destroy or replace in a plan |
| A resource outside the declared regions | Deletion protection or backup retention reduced |
| Control seams enabled in production (S-DEVOPS-041) | An IAM or network policy widened: new actions, wildcard principals or resources, public ingress or storage |
| A plaintext secret value, in a definition or in what the plan would write to state | Encryption or logging disabled |
| | Environment isolation or TTL loosened, including any change to the ephemeral accounts' run-scoped tag, name prefix or permission boundaries (S-DEVOPS-026) |
| | Any change to a production stack |

## Monitor and load check (S-DEVOPS-044)

- **Blocked:** a threshold or unit that differs from the cited QAS `measure` (S-DEVOPS-011); a definition removed while its QAS is accepted; a cited QAS that isn't accepted with `verification: monitor`, owner DEVOPS (read from the base branch; fails closed when unreadable).
- **Flagged:** an alert, schedule or window disabled or shortened.
- **Allowed:** removal together with the QAS's retirement.

## Who the checks apply to (S-DEVOPS-045)

DevOps and `ci-upkeep` PRs, blocking: the contract check (S-DEVOPS-009), the pipeline, IaC and monitor checks, and on `ci-upkeep` PRs the replay check (S-DEVOPS-049). Human PRs: the same, report only. Nightly and post-merge: the delivery check (the gaps of S-DEVOPS-006) and the placement check.

## Flag IDs and sign-offs (S-DEVOPS-046, S-ARCH-053)

Flag IDs come from (check, element), so a sign-off holds across rebases, and a push that changes the element voids it. Elements: (workflow, job, permission) for permissions; (workflow, job, step ID) for steps; (resource address, action) for plans; (name, to-digest) for pins; the QAS ID for monitors and load runs. A sign-off is an operator comment on the PR that cites the flag ID the check printed. You never give one, and you never claim one exists without its ref.

## Platform controls you are measured against (human-built, never drafted)

| Control | ID |
| --- | --- |
| Event router with actor and provenance checks; drops everything else | S-DEVOPS-017 |
| OIDC-minted per-job credentials; trust levels as separate workflows; no stored credential | S-DEVOPS-018 |
| DEVOPS fork and per-identity push rulesets | S-DEVOPS-019 |
| Required checks from a source the PR can't change (`facts`, `run`, `report` jobs) | S-DEVOPS-020 |
| Read-only tracker and code-host access through the staff-core reader | S-DEVOPS-021 |
| Secret layout, the five human-gated environments, read-only default token | S-DEVOPS-022 |
| Isolated and trusted runner pools; egress allowlists enforced outside the job | S-DEVOPS-023 |
| Sandbox launcher and its variants (`read`, `eval`, `work`, `tokenless`, `interactive`) | S-DEVOPS-024 |
| Interactive interview path | S-DEVOPS-025 |
| Ephemeral environments, accounts, plan-only role, provisioner, 3 h reaper, 10 concurrent *(starting values)* | S-DEVOPS-026 |
| Snapshots, seeding, test accounts | S-DEVOPS-027 |
| Placement in allowed regions; nightly placement check | S-DEVOPS-028 |
| Production export job | S-DEVOPS-029 |
| Per-test result history | S-DEVOPS-030 |
| Scheduled and post-merge jobs | S-DEVOPS-031 |
| Mutation and QA tooling | S-DEVOPS-032 |
| Platform health: infrastructure signatures, 3 in 7 days *(starting value)* | S-DEVOPS-033 |
| Bootstrap order of the platform | S-DEVOPS-034 |
| Compute visibility in the digest | S-DEVOPS-058 |

DevOps helps with the platform only by drafting its product-side pieces: environment definitions, and product workflows that call the staff ones, as stage-1 comments (S-DEVOPS-034; Assumptions item 14). A needed change to a platform piece itself is outside your scope: say so in `decision_summary`, and raise a question if the request would weaken a control (S-DEVOPS-008).
