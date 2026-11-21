# Product contract

The minimum layout a product repo needs before staff agents work on it (S-GEN-017). Product facts live only in the product repo; this staff repo holds none (S-GEN-002, S-GEN-011).

Every file under `.staff/` is human-only, apart from `.staff/plugins.lock`, which the release job may also change through a PR (S-GEN-025). Checks read these files from the base branch, so a PR can't change the rules it is checked against.

**Lean** marks what the lean slice (BA Analyst at stage 1) needs now. The rest is needed when the matching role or mechanism starts.

## Contract files (`.staff/`)

| File | Holds | Role | Lean |
| --- | --- | --- | --- |
| `.staff/product.yml` | Data residency: allowed regions for model calls and stored data, or `unrestricted` (S-DATA-001). The model endpoint (S-DATA-002). The testability manifest: which S-TESTAB items the product provides (S-TESTAB-001). If residency is missing, every agent workflow fails closed | GEN, all roles | **Yes** |
| `.staff/areas.yml` | Path-to-area map. Areas key requirement and rule paths, concurrency groups and stages (S-GEN-060) | GEN, all roles | **Yes** |
| `.staff/plugins.lock` | Exact pinned version of every installed plugin, and exactly one staff-core. Release tags only, never floating (S-GEN-016) | GEN | No. In the lean slice, pin the tag in the marketplace source instead (see `README.md`) |
| `.staff/stages.yml` | Human-set stage per agent per area; role priority order (S-GEN-050, S-GEN-072) | GEN | No. The Analyst is at stage 1 by default |
| `.staff/code.yml` | DEV code map per area: `source`, `unit_tests`, `generated`, `protected`, `dependency_files`, `verification_config`, `guard_patterns`, `test_list`, `generators`, `interface_source`, `upkeep_tools` (S-DEV-004) | DEV | No |
| `.staff/tests.yml` | QA test map per area and layer: `paths`, `stack`, `locators`, `mocks`, `request_docs`, `fixtures`, `mutation`, `fuzz` (S-QA-005) | QA | No |
| `.staff/delivery.yml` | DEVOPS delivery map: `pipelines`, `build`, `iac`, `environments`, `deploy_units`, `migrations`, `monitors`, `load`, `pin_tool`, `fork`, `exports` (S-DEVOPS-004) | DEVOPS | No |

Minimal lean-slice shapes. Values are placeholders the human replaces; the formal schemas will ship in `plugins/*/schemas/`.

```yaml
# .staff/product.yml
residency:
  regions: [<region>]          # or: unrestricted
model_endpoint: <endpoint>     # in an allowed region (S-DATA-002)
testability: []                # S-TESTAB items provided; none are needed by the Analyst (S-BA-045)
```

```yaml
# .staff/areas.yml
areas:
  <area-key>:                  # lowercase, digits and hyphens
    paths:
      - requirements/<area-key>/**
      - knowledge/rules/<area-key>/**
```

## Product paths

| Path | Holds | Owner role | Lean |
| --- | --- | --- | --- |
| `requirements/<area>/REQ-n.md` | One requirement per file (S-BA-011) | BA | **Yes** |
| `requirements/<area>/REQ-n.tc.<ext>` | Test conditions of a requirement (S-BA-050) | BA | **Yes** (path reserved; filled after ready gates) |
| `requirements/<area>/sources/INT-n.md` | Interview transcripts, committed by the human only (S-BA-056) | BA (human) | **Yes** |
| `knowledge/product-core.md` | Glossary, roles and permissions, 5-10 core journeys, invariants, fragile areas (S-GEN-018) | BA (human-owned) | **Yes** |
| `knowledge/rules/<area>/R-n.md` | Rules registry, one rule per file (S-BA-008, S-BA-011) | BA (human-owned) | **Yes** |
| `knowledge/discovered/` | App map, state models, newly found rules (S-GEN-018) | BA, QA | **Yes** (may be empty) |
| `architecture/overview.md` | System overview (S-ARCH-013) | ARCH | No |
| `architecture/<area>/adr/ADR-n.md` | Architecture decisions | ARCH | No |
| `architecture/<area>/components/CMP-n.md` | Components | ARCH | No |
| `architecture/<area>/interfaces/IF-n.md`, `IF-n/` | Interfaces and one spec file per version | ARCH | No |
| `architecture/<area>/quality/QAS-n.md` | Quality attribute scenarios | ARCH | No |
| `architecture/<area>/conformance/` | Conformance rules (S-ARCH-026) | ARCH | No |
| `architecture/system/` | Cross-area architecture artifacts | ARCH | No |
| `delivery/environments/<env>/**`, `delivery/monitors/QAS-n.<ext>`, `delivery/load/QAS-n.<ext>` | Environments, monitors, load runs (S-DEVOPS-004) | DEVOPS | No |
| `qa/quarantine.yml` | Quarantine registry, changed only through quarantine PRs (S-QA-029) | QA | No |
| `AGENTS.md` | Conventions per language and layer | All | No |
| `.github/CODEOWNERS` | The human owns every path (S-GEN-025) | Human | **Yes** |
| `.github/workflows/staff-*` | Staff platform workflows, human-authored only (S-GEN-025) | Human | **Yes** (the Analyst workflow) |

## CI variables (not files)

Plugin switches (S-GEN-069), demotion ceilings (S-GEN-050), throttle ceilings (S-GEN-072) and pre-review switches (S-GEN-062). Nothing that affects security or residency is kept in a CI variable. None are needed in the lean slice.
