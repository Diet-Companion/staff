# staff

Product-agnostic agent staff for one human operator, packaged as [Claude Code](https://code.claude.com/docs) plugins. A product repo installs the plugins from this repo, which is a Claude Code plugin marketplace. The agents run as Claude Code in headless mode in the product repo's GitHub Actions.

This repo holds no product facts. Requirements, rules, code and architecture live in the product repo, at the paths in [`governance/product-contract.md`](governance/product-contract.md) (S-GEN-002, S-GEN-011).

The strategy behind it is in [`docs/strategy/`](docs/strategy/). That folder is a copy; the source of truth is designed elsewhere.

## Current stage: lean slice

Only one agent runs: the business-analyst **Analyst**, at **stage 1 (advisory)**.

- It reads an intake ticket and the product repo with read-only tools (`Read`, `Glob`, `Grep`).
- It returns JSON only, validated against [`analyst-output.schema.json`](plugins/staff-product/schemas/analyst-output.schema.json): a question batch, up to 5 draft requirements with acceptance criteria, a kickoff interview guide, or an escalation.
- A separate write step posts that output as comments on the ticket. The Analyst never commits, opens PRs, labels or merges.
- Everything else is manual: the human starts runs, gives verdicts, writes rules and the product core, commits accepted drafts, and runs any interview.

[`governance/guardrails.md`](governance/guardrails.md) shows which guardrail enforcement exists in the lean slice and which comes later.

## Layout

```
staff/
  .claude-plugin/marketplace.json      # plugin marketplace: staff-core, staff-product
  plugins/
    staff-core/
      .claude-plugin/plugin.json
      skills/strategy-shared/SKILL.md  # shared rules and guardrails G1-G12, loaded by every agent
    staff-product/                     # business analyst
      .claude-plugin/plugin.json
      agents/analyst.md                # Analyst read stage (stage 1)
      skills/requirements/SKILL.md     # requirement, AC and rule model, IDs, paths
      skills/elicitation/SKILL.md      # question batches, stage-1 output
      schemas/analyst-output.schema.json
  governance/
    guardrails.md                      # G1-G12 and how each is enforced
    product-contract.md                # what a product repo must contain
    operators.yml                      # the human's accounts, for actor checks
  docs/strategy/                       # copy of the approved strategy and decisions log
  CODEOWNERS                           # the human owns every path
```

The full target layout (more plugins, `evals/`, `metrics/`, `ops/`, `experiments/`) is in S-GEN-013. It is added as the matching parts are built.

## Installing in a product repo

1. Add the contract files the lean slice needs: `.staff/product.yml`, `.staff/areas.yml`, `requirements/` and `knowledge/` (see [`governance/product-contract.md`](governance/product-contract.md)).

2. Register this marketplace and enable the plugins in the product repo's `.claude/settings.json`. Pin a release tag, never a branch (S-GEN-016):

   ```json
   {
     "extraKnownMarketplaces": {
       "staff": {
         "source": { "source": "github", "repo": "Diet-Companion/staff", "ref": "v0.1.0" }
       }
     },
     "enabledPlugins": {
       "staff-core@staff": true,
       "staff-product@staff": true
     }
   }
   ```

3. In CI, install before running. Pinning the marketplace to the tag pins both plugins:

   ```sh
   claude plugin marketplace add Diet-Companion/staff@v0.1.0 --scope project
   claude plugin install staff-core@staff --scope project
   claude plugin install staff-product@staff --scope project
   ```

   Interactively, the same steps are `/plugin marketplace add Diet-Companion/staff@v0.1.0` and `/plugin install staff-product@staff`.

4. Run the Analyst read stage headless, with the schema as the output contract, the job's turn limit and a 20-minute timeout ($3 / 20 min per run, S-BA-038):

   ```sh
   claude -p --agent staff-product:analyst \
     --json-schema "$(cat <path-to-installed-plugin>/schemas/analyst-output.schema.json)" \
     --output-format json \
     --max-turns <n> \
     "<redacted intake ticket text>"
   ```

   Feed the validated JSON, never the raw ticket, to a separate comment-only step (S-SEC-002).

## Changing this repo

The human is the code owner of every path (S-GEN-025) and the only one who merges (G1). Strategy changes are made at the source and copied into `docs/strategy/`. Skill, agent, schema and governance changes come through reviewed PRs.
