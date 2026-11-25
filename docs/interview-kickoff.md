# Running a kickoff interview

How the operator runs the live kickoff interview for a new area (S-BA-013, S-BA-055 to S-BA-057), in the lean slice.

Trigger: on the first intake for an area, the Analyst posts an **interview guide** on the intake issue (`outcome: interview_guide`, at most 10 topics, blocking first). You then hold the interview yourself with the tool-less `analyst-interview` agent, commit the transcript, and hand back to the Analyst. Agents never start an interview or apply `ba:interview` (S-BA-055).

**Lean-slice gap.** The strategy runs the interviewer in a sandbox, behind a launch wrapper that tags speakers, redacts each human turn before it reaches the model, and records the run (S-BA-055, S-BA-056, S-DEVOPS-025). That wrapper isn't built yet. Until it is:
- your review of the transcript is the only check that speakers are right;
- `harness/check_transcript.py` is the only automated redaction check;
- the session has no run record or cost record (G5).

Keep the session short, and don't type anything personal into it.

## 1. Install the staff plugins locally (once per release)

The marketplace is named `staff` (`.claude-plugin/marketplace.json`). Pin a release tag that contains `agents/analyst-interview.md`, never a branch (S-GEN-016):

```sh
claude plugin marketplace add Diet-Companion/staff@<release-tag>
claude plugin install staff-core@staff
claude plugin install staff-product@staff
```

These install at user scope, the default, so nothing is added to the product repo. `staff-product` also depends on `staff-core`. After a new release, run `claude plugin marketplace update staff` and `claude plugin update staff-product@staff`, then restart Claude.

## 2. Start the interview

1. Open the guide comment on the intake issue. Check that the staff Analyst posted it, not another account. Copy its link (`...#issuecomment-<id>`).
2. In a terminal at the product repo root, fetch the guide's text and start the agent with no tools and no MCP servers:

   ```sh
   GUIDE="$(gh api repos/<owner>/<repo>/issues/comments/<id> --jq .body)"
   claude --agent staff-product:analyst-interview --tools "" --strict-mcp-config \
     "Kickoff interview. Intake: <owner>/<repo>#<n>. Area: <area>. Guide: <comment link>.

   $GUIDE"
   ```

   The agent can't open links, so the guide's text has to be in the prompt. The link goes into the transcript's Sources. To use glossary names for keys (S-BA-007), you can also append `"$(cat knowledge/product-core.md)"`. Don't paste the raw intake issue: the guide was drawn from it already.
3. Answer one question at a time. Answer about how the product should behave, with made-up examples ("user A enters a value of 500"). Never give your own weight, diet, conditions or other health data, or anyone else's (S-DATA-004). If you don't know an answer, say so. It becomes an open item.
4. At the end, the agent reads back each decision as its own point. Confirm or correct each one. Then it prints the transcript as one Markdown block. When it asks for the number, give the next free `INT-NNN` for the product. Numbers run per product and are never reused (S-BA-005):

   ```sh
   ls requirements/*/sources/INT-*.md
   ```

## 3. Review, check and commit the transcript

1. Save the block as `requirements/<area>/sources/INT-NNN.md`. The format is `plugins/staff-product/templates/INT-n.md` in staff.
2. Review every turn:
   - each `[human]` turn is your own words, and each `[interviewer]` turn is the agent's;
   - no question offers you a value, and no decision rests only on interviewer text;
   - nothing personal, health-related or secret is left in. Rewrite it with a made-up example, or delete it;
   - each decision cites the right turn (`INT-NNN#T<k>`, or the readback pair `INT-NNN#T<k>/T<k+1>`);
   - every topic that isn't `covered` is listed under Open items.
3. Set `human_confirmed: true`.
4. Run the check from a staff checkout. It needs only the Python standard library:

   ```sh
   python <staff checkout>/harness/check_transcript.py requirements/<area>/sources/INT-NNN.md
   ```

   It must print `transcript check: clean`. On a failure it names the line and the rule, never the matched value. Fix the file and run it again.
5. Commit on your own branch, not `agent/*`, and merge through a PR. Only you write `requirements/*/sources/**` (S-BA-056, S-BA-035):

   ```sh
   git switch -c interview/<area>-INT-NNN
   git add requirements/<area>/sources/INT-NNN.md
   git commit -m "Add INT-NNN: <area> kickoff interview"
   git push -u origin HEAD
   gh pr create --fill
   ```

   Review the diff one more time before you merge. A missed redaction stays in Git history until you rewrite it (S-DATA-008).

## 4. Continue with the Analyst

After the merge, comment exactly `/analyst` on the intake issue. The Analyst reads the merged transcript and drafts requirements that cite your turns. It turns open items and unconfirmed points into open assumptions and the first question batch (S-BA-057). Only human turns count as sources. Nothing the interviewer said becomes a fact unless you confirmed it (S-BA-056).
