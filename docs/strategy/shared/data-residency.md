# Shared: Data residency (DATA)

Updated Nov 20, 2026

Covers where model calls and stored data may go, and which data agents may handle. It applies to every agent, every staff identity and every CI job, in all disciplines. Role strategies reference these IDs and never restate them.

Markers: *(starting value)* = accepted by the human in `docs/decisions.md`. No *(proposed)* item is open. Named providers are examples.

## Declaration

- **S-DATA-001** The product declares its residency in `.staff/product.yml`: either a list of allowed regions for model calls and stored data, or `unrestricted`. If the declaration is missing, every agent workflow for that product fails closed before it starts. *Depends on:* S-GEN-017.

## Where data may go

- **S-DATA-002** Every model call goes to an endpoint in an allowed region. This covers working agents, the improver, the eval runner and LLM judge, the seeding agent, the strategy designer and the reviewer, and it applies to calls from CI too. An example is Claude on Bedrock or Vertex in EU regions. The endpoint is set once, in config only the human edits. Product workflows read it from `.staff/product.yml`. Staff workflows read it from `governance/ops-config/`, which must satisfy the residency of every product served. It is never kept in a CI variable that the ops jobs can write (S-GEN-069). The egress allowlist admits only that endpoint (S-SEC-007). *Depends on:* S-DATA-001, S-SEC-007, S-GEN-025, S-GEN-069.
- **S-DATA-003** Stored data stays in an allowed region: the outcome store, transcripts, `staff-evals-private`, eval-private object storage, CI artifacts and logs. So do the runners that hold code or test data, and the host of the interactive sandbox (S-GEN-004). Where hosted runners can't guarantee the region, self-hosted runners in that region are used. *Depends on:* S-DATA-001, S-GEN-004, S-DEVOPS-028.

## Which data agents handle

- **S-DATA-004** Agents handle code, product docs and synthetic or anonymised test data. Production data and personal data of real people never reach an agent or a model call. Production-derived text, such as support tickets, user bug reports and analytics exports, reaches agents only after redaction (S-SEC-004). *Depends on:* S-SEC-004, S-BA-028, S-QA-048.

## Providers and tools

- **S-DATA-005** The model provider's terms exclude training on inputs. Zero or minimal provider-side retention is used where it is available.
- **S-DATA-006** A third-party tool or connector (an MCP server, a SaaS scanner, a tracker integration) gets product data only if it meets the residency declaration. Otherwise it is disabled for that product. *Depends on:* S-DATA-001, S-SEC-010.

## Retention and deletion

- **S-DATA-007** Retention periods:
  - **Transcripts of live and visible-set runs:** 90 days *(starting value, `docs/decisions.md`, 2026-11-20)*.
  - **Hidden-run and promotion-run records and transcripts** (eval-private object storage, S-GEN-065): kept until the hidden task rotates to visible, or until that agent's promotion set is rebuilt. That covers leak checks. At that point the eval runner releases the items the human must review to the outcome store (S-GEN-041). The eval-private copies are deleted within 90 days of release *(starting value)*.
  - **Run records:** kept for the life of the project. They hold no transcripts or raw inputs. They do hold redacted structured fields and short free text (S-SEC-002), which counts as untrusted (S-SEC-001). While run records still live in CI artifacts, they are moved to the database before the artifacts expire.

  *Depends on:* S-GEN-012, S-GEN-038, S-GEN-041, S-GEN-065.
- **S-DATA-008** Every item in a store outside Git (outcome store, object storage, CI artifacts) is keyed by `run_id`, so one run's data can be deleted across those stores. Deleting a run also deletes the `check_outcome` records whose `drafting_run_id` matches it (S-GEN-031). Content that reached a Git repo through a merged PR can only be removed by a history rewrite, which is a manual action by the human. *Depends on:* S-GEN-029, S-GEN-031.

## Assumptions

1. **Residency is a product fact:** it is a placeholder until a product is chosen. The fail-closed default turns a missing value into a one-line fix, not a silent leak.
2. **Provider terms:** a commercial API tier without training on inputs is available in every allowed region.
3. **Transcript retention:** 90 days *(starting value, `docs/decisions.md`, 2026-11-20)*. That is long enough for the weekly improver and for debugging bad runs. Reusing the same 90 days after rotation or rebuild for eval-private records is the designer's application of that value.

## Open dependencies

- **OD-DATA-1 (DevOps):** region placement of runners, CI artifacts, the outcome database and object storage (S-DATA-003). **Closed** by S-DEVOPS-028.
- **OD-DATA-2 (business analyst, test engineer):** the redaction path for production-derived sources that their agents read (S-DATA-004). **Closed:** BA by S-BA-028, QA by S-QA-048.

## Open questions

- [ ] Does any likely product need a residency rule that is stricter than region, such as a single country or on-premises only? If it does, S-DATA-002 needs a self-hosted model option.
