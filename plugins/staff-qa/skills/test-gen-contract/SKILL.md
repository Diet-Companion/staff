---
name: test-gen-contract
description: The test-gen-* change contract - path scope from .staff/tests.yml, the test PR block, expected failures and suspected issues, and the output form (S-QA-005, S-QA-014, S-QA-017, S-QA-018, S-QA-026).
---

# Test-gen change contract

## The test map and path scope (S-QA-005, S-QA-014)

The bundle's `qa.test_map_entry` is the area's layer entry from `.staff/tests.yml` (human-owned, read from `main`). You may add or modify files only under its globs:
- `paths`: the test files;
- `fixtures`, `mocks`, `request_docs`: support files.

Anything else fails the run (`path_out_of_scope`): product code, the code map's paths, `.staff/**`, `.github/**`, `AGENTS.md`, `requirements/**`, `architecture/**`, `knowledge/**`. Never delete a test, and never weaken an existing assertion; modify an existing test only to add to it.

## The PR block (S-QA-026, stage 1)

- `kind`: `tests` for new coverage, `repair` for re-pointing a citation (S-QA-025).
- `layer`: the bundle's layer.
- `product_pr`: `null` (stage 1 drafts target `main`); `base`: `main`.
- `cited_ids`: every source your tests cite, deduplicated.
- `characterization`: the test IDs labelled characterization.
- `expected_failures`: tests you expect to fail on `main` because the code differs from the cited source, each with `test_id`, `cites`, `expected`, `actual` (what the code does, from reading it) and `evidence_refs` (paths with lines). Each has a matching `suspected_issues` entry with the same `test_id`.

Test IDs are `<path>::<test title>` as the layer's test list prints them: the file path from the repo root, then the full title (describe blocks and the test name joined by ` > `).

## The work sandbox (S-QA-017)

After validation the harness writes your files onto `main` in a job with no secrets, runs the layer's `sandbox` commands from `.staff/tests.yml` on `main` and on your change (against a throwaway PostgreSQL), and posts the result. A draft passes when the build passes, no test that passed on `main` fails, and every test you added passes, except those in `expected_failures`. A failing draft triggers an automatic fix-up round with the failure in your latest comment: fix exactly that failure.

## Output form (S-QA-018)

One comment per draft is rendered from your JSON: the decision summary, the cited IDs, the files, the sandbox result and the suspected issues. The full patch is a CI artifact. Requirement-defect items go to the requirement's own ticket.
