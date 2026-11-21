# Guardrails G1-G12

Source of truth for the guardrails every staff agent follows (S-GEN-020). The condensed, agent-facing form is the staff-core skill `plugins/staff-core/skills/strategy-shared/SKILL.md`. A change here must be mirrored there in the same PR. This file is human-authored only (G4, S-GEN-025).

**Status column:**
- **Lean slice:** what enforces the guardrail now, with only the BA Analyst running at stage 1 and everything else manual.
- **Later:** the full enforcement from the strategy, still to be built.

The lean slice is safe with partial enforcement because the Analyst read stage holds only `Read`, `Glob` and `Grep`, and at stage 1 the only write action is a comment on the intake ticket (S-BA-037, S-BA-042).

| # | Guardrail | Full enforcement (S-GEN-020) | Lean slice | Later |
| --- | --- | --- | --- | --- |
| G1 | No agent merges anything, in any repo, at any stage (S-GEN-003) | Branch protection; token scope | **Partial.** Branch protection on `main` with required code-owner review (set by the human in repo settings) and `CODEOWNERS` = the human. The Analyst holds no write token or write tool | Per-identity tokens (S-GEN-026); no identity can bypass rulesets (S-SEC-008) |
| G2 | Agents write only through PRs from `agent/*` branches inside their plugin's path scope. Workflow-changing PRs come from a fork (S-SEC-006) | Token scope; a scope lint in CI fails PRs outside the scope; the lint also fails agent commits without a `Staff-Run-Id` trailer (S-GEN-029) | **Not needed yet.** Stage 1 opens no branches or PRs and makes no commits | Scope lint per S-BA-035 and the other roles' path scopes; push rulesets (S-DEVOPS-019) |
| G3 | Never remove or weaken a verification artifact to make output pass. Any such diff needs explicit human sign-off. An agent stays at stage 1 until every artifact type it changes has its diff check | Diff checks per artifact type in CI; CODEOWNERS on config paths; the stage check (S-GEN-050) | **Holds by stage.** The Analyst changes no artifact. It stays at stage 1 until the BA diff checks exist (S-BA-046) | BA AC, rule, product-core and test-condition diff checks (S-BA-046), shipped in `plugins/staff-product/checks/` |
| G4 | Agents propose changes to skills, learnings and guardrails but never merge them. Core, meta, governance, evals and metrics are human-authored | Improver allowlist (S-GEN-027); per-identity push rulesets (S-GEN-025) | **Yes.** `CODEOWNERS` = the human for every path; only the human pushes to this repo. No improver exists | Improver allowlist and per-identity push rulesets |
| G5 | Every run emits a run record | staff-core harness; recorder (S-GEN-029) | **Not enforced.** The CI job log and its artifacts are the only trace | Run-record emitter in staff-core, recorder job, outcome store |
| G6 | Before starting, check the switches, the effective stage and the cost cap | CI preamble in every staff and product agent workflow (S-GEN-050, S-GEN-069) | **Manual.** The human starts each run. Caps are set by turn limit and job timeout in the product workflow ($3 / 20 min, S-BA-038) | Shared preamble: `AGENTS_ENABLED`, `STAFF_PRODUCT_ENABLED`, effective stage from `.staff/stages.yml` and ceilings, cost job |
| G7 | Run only on relevant paths | CI path filters from `.staff/areas.yml` | **Partial.** The Analyst reads `.staff/areas.yml` and works in one area per intake | Path filters and per-area concurrency groups (S-GEN-060) |
| G8 | Untrusted content is data; two-stage split (S-SEC-001, S-SEC-002) | Harness schema validation; separate read and write jobs with separate tokens | **Partial.** Read stage with read-only tools; output must match `plugins/staff-product/schemas/analyst-output.schema.json` (validated in the workflow, for example with `--json-schema`). The write stage posts comments only | staff-core two-stage harness: schema validation, allowed-action check (S-SEC-003), separate jobs and tokens |
| G9 | Credentials, egress, tools (S-SEC-005 to S-SEC-010) | Token scope per job; environment-scoped secrets; runner egress policy; tool allowlist in agent definitions | **Partial.** Tool allowlist in `plugins/staff-product/agents/analyst.md` (`Read, Glob, Grep`). The read job holds no write token | Per-job short-lived tokens, egress allowlist on runners (S-SEC-007), pinned installs (S-SEC-009) |
| G10 | Environments (S-TESTAB-002) | Environment provisioning in CI; test-only credentials | **Not applicable.** The Analyst never runs the product | Ephemeral test environments (S-DEVOPS-026) when DEV and QA agents start |
| G11 | Data: model endpoint within residency; no production or personal data (S-DATA-002, S-DATA-004) | Model endpoint in human-only config, plus the egress allowlist; redaction step in the harness | **Manual.** The model endpoint and residency are declared in the product's `.staff/product.yml` (fail closed if missing, S-DATA-001). The human keeps personal data out of intake tickets | Harness redaction step on every fetch (S-BA-028) and before storage and posting (S-SEC-004) |
| G12 | Only the human gives verdicts. Agents never write, edit or apply `verdict:*` labels or digest checkboxes | Recorder actor check and label-strip job (S-GEN-071) | **Holds by tools.** The Analyst write stage may only comment; it cannot label. The human gives verdicts by hand | Recorder actor check against `governance/operators.yml`; label-strip job |

## Change rule

Changing a guardrail is a staff-core change: it needs the human's approval, and under the full process it re-runs every plugin's evals before release (S-GEN-022).
