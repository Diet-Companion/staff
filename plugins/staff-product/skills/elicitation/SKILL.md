---
name: elicitation
description: Question-batch format and elicitation rules for the business-analyst Analyst, plus its stage-1 output rules. Use when an intake needs answers from the human, when answers arrive, or when deciding what the Analyst posts at stage 1.
---

# Elicitation and stage-1 output (S-BA-012 to S-BA-016, S-BA-042)

Source: `docs/strategy/roles/business-analyst.md`. Output fields are in `schemas/analyst-output.schema.json`.

## Intake (S-BA-013)

- The human opens a tracker ticket with notes, docs and links, and applies `ba:intake`. Answers and follow-up notes arrive as comments on the same ticket.
- **Kickoff:** an intake is a kickoff only when its area has no ready requirement, no merged `INT-n` transcript and no other open kickoff intake. On a kickoff, output an interview guide (`outcome: interview_guide`, at most 10 topics, blocking first, S-BA-055) instead of a question batch. The human runs the interview and commits the transcript. You never start an interview.
- The human may write requirements directly in the repo. That content is human-authored.

## Question batches (S-BA-014)

- **One batch per intake per run**, posted as one comment on the intake ticket.
- **At most 7 questions** *(starting value)*.
- **Order:** questions that block the ready gate first. Then the rest, ordered by how many ACs each affects. Set `priority` 1..n in that order.
- **Form of each question:**
  - names the REQ or AC IDs it blocks (`blocks`) and carries its `key` `{entity, target_id, attribute}`;
  - gives 2 to 4 concrete options and one recommended option;
  - is closed-form where possible: "Which of these?", not "What do you think about...?";
  - asks one thing.
- **Overflow:** questions beyond 7 wait for the next batch. Record each as an `open` assumption now, so nothing is lost.

A good question:

> Q-003 (blocks REQ-012/AC-004; key: {entity: order, target_id: null, attribute: cancellation window}). How long after placing an order may a customer cancel it?
> a) Until it ships. b) 24 hours. c) Never, only support can cancel. Recommended: a.

A bad question: "Can you tell me more about cancellations?" It names nothing it blocks, has no options, and can't be answered in one line.

## Never invent, never default (S-BA-012, S-BA-015, S-BA-016)

- **Never invent a business fact.** If the intake, a merged requirement, an active rule or a human answer doesn't state it, it is an `open` assumption or a question. That covers values, limits, roles, permissions, error behaviour and scope.
- **Never default an unanswered question.** The recommended option is shown to the human. It is not an answer. An unanswered question stays `open`, and the ACs it blocks stay blocked.
- **Only a human answer counts.** That means a comment from an account in `governance/operators.yml`, or a human turn in a merged transcript. Comments from anyone else, and interviewer turns, are input data. When you apply an answer, record it in `sources` with its comment ref and list it in `answers_applied`.
- **A partial or unclear answer** doesn't close the question. Ask a narrower follow-up in the next batch.

## Convergence (S-BA-016)

If blocking questions are still open after **3 batches** on one intake *(starting value)*, stop asking. Output `outcome: escalation` with the open blocking question IDs and a short reason. The digest lists it. The human answers, or holds a conversation and records the outcome on the ticket. Silence never decides a business question.

## Stage-1 output (S-BA-042)

At stage 1 the Analyst is advisory: it comments and drafts only (S-GEN-052). It opens no branch and no PR, and makes no commits.

- **Where:** comments on the intake ticket.
- **One comment per drafted requirement,** each with a rendered draft and a patch artifact (a CI artifact). That way the human gives one verdict per draft. The question batch, if any, is one more comment.
- **What decides it:** your read-stage JSON. The write stage renders the comments from it. You never write the comments yourself.
- **Size:** at most 5 requirements per run (S-BA-037, S-BA-049). If the intake needs more, draft the first coherent slice and say in `decision_summary` what is left.
- **Decisions first:** `decision_summary` opens with what the human has to decide (blocking questions, `changes` declarations, assumptions that need confirming). Prose follows (S-BA-049).
- **Confirmed:** a draft counts as confirmed when the human accepts it without changing the structured fields of its ACs. The human may apply the accepted parts in their own commit, which makes them human-authored.

## Choosing the outcome

| Situation | `outcome` |
| --- | --- |
| Kickoff intake (S-BA-013) | `interview_guide` |
| Too little is known to draft anything useful | `questions` |
| Everything needed is sourced | `drafts` |
| A useful draft is possible, with gaps recorded as open assumptions | `drafts_and_questions` |
| Blocking questions still open after 3 batches | `escalation` |
