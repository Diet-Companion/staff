# Shared: Testability (TESTAB)

Updated Nov 20, 2026

What the product must provide so that agents in every discipline can build, run, check and debug it. Each item is product-agnostic. Role strategies say who delivers each item (Open dependencies) and reference these IDs without restating them.

Markers: no *(proposed)* item is open in this doc.

## Manifest

- **S-TESTAB-001** The product declares which items below it provides in its testability manifest in `.staff/product.yml` (S-GEN-017). Each agent's prerequisites, meaning the items it needs, are listed in its role strategy. An agent whose prerequisites are missing stays at stage 1 in that area, and the gap appears in the triage digest. *Depends on:* S-GEN-017, S-GEN-050, S-GEN-063, OD-TESTAB-6.

## Environments and builds

- **S-TESTAB-002** Every agent run that executes the product uses an isolated test environment, never shared staging or production. By default each job gets its own ephemeral environment, started from a pinned build and data snapshot and torn down afterwards. If the product cannot run per job, jobs share one test environment, with all data namespaced by `run_id` and cleaned up when the job ends. *Depends on:* S-TESTAB-003, S-TESTAB-004.
- **S-TESTAB-003** Every commit that agents test produces a build (for example a container image) that is addressable by digest. Eval runs and environments start from a pinned digest.

## Data and accounts

- **S-TESTAB-004** The product provides seed scripts or data factories that create the data a check needs, through public interfaces or a test-only seeding API, along with cleanup. Seeded data is synthetic (S-DATA-004). Each product user role (for example admin, customer or guest) has test accounts, stored as CI secrets that are valid only in test environments. *Depends on:* S-DATA-004.

## Stable identifiers

- **S-TESTAB-005** Everything an agent addresses has a stable identifier that doesn't change with layout or wording:
  - interactive UI elements have accessible roles and names, or test IDs;
  - API operations, error codes and events have stable names;
  - services and components have stable names in the architecture docs.

## Specs as ground truth

- **S-TESTAB-006** Every interface and requirement has a machine-readable, versioned source in the product repo:
  - interface specs (OpenAPI, SDL or `.proto`);
  - rules with IDs in the rules registry (S-GEN-018);
  - acceptance criteria linked to tickets;
  - architecture decisions as ADRs;
  - infrastructure as code.

  Expected values in any agent check come from these sources, not from observed behavior. Where a needed source is missing, producing it comes before agent work that depends on it. *Depends on:* S-GEN-018.

## Observability and control

- **S-TESTAB-007** The test environment accepts the agent's `run_id` as a correlation ID and propagates it into logs and traces. Agents can read those logs and traces as untrusted content (S-SEC-001). It exposes a readiness endpoint and returns structured errors. *Depends on:* S-SEC-001.
- **S-TESTAB-008** In a test environment, agents can set feature flags, control the clock, and replace external services at process boundaries with fakes or recorded mocks.

## Upstream review

- **S-TESTAB-009** The requirements and architecture checklists in staff-review each include testability items that cite these IDs, so gaps are found before code exists. *Depends on:* S-GEN-015, S-BA-030, S-ARCH-032.

## Assumptions

1. **Manifest location:** `.staff/product.yml` in the product repo, as set by the product contract.
2. **Shared-environment fallback:** this is a placeholder decision rule. Which branch applies is settled when a product is chosen.
3. **Synthetic data:** it is enough for every discipline. Production-derived data is ruled out by S-DATA-004.

## Open dependencies

- **OD-TESTAB-1 (business analyst, architect):** testability items for the requirements checklist (BA) and the architecture checklist (ARCH), citing S-TESTAB IDs. **Closed:** BA by S-BA-030, ARCH by S-ARCH-032.
- **OD-TESTAB-2 (architect):** design rules that make S-TESTAB-005, -007 and -008 part of every new component. **Closed** by S-ARCH-025.
- **OD-TESTAB-3 (developer):** implementing S-TESTAB-004, -005, -007 and -008 in code, and how the developer agents keep them in place. **Closed** by S-DEV-013.
- **OD-TESTAB-4 (DevOps):** delivering S-TESTAB-002 and -003: ephemeral environments, digest-addressed builds, data snapshots and per-role test accounts. **Closed** by S-DEVOPS-026 (environments), -027 (snapshots, seeding, reset, accounts) and -035 (digest builds).
- **OD-TESTAB-5 (test engineer):** how QA agents consume each item, and the stricter local oracle rule (cited source IDs, characterization label) that depends on S-TESTAB-006. **Closed** by S-QA-006 (oracle rule) and S-QA-047 (each item).
- **OD-TESTAB-6 (all roles):** for every working agent, the S-TESTAB items it needs before leaving stage 1 (S-TESTAB-001). **Closed:** BA by S-BA-045, ARCH by S-ARCH-043, DEV by S-DEV-035, QA by S-QA-047, DEVOPS by S-DEVOPS-052.

## Open questions

- [ ] None at this level. Product-specific gaps are recorded in each product's manifest.
