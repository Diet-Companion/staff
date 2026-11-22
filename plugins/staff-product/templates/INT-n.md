---
id: INT-NNN
area: <area key from .staff/areas.yml>
intake: <owner/repo#n>
date: <YYYY-MM-DD>
human_confirmed: false
---

<!--
Interview transcript, source INT-n (S-BA-056). Save it as
requirements/<area>/sources/INT-NNN.md in the product repo. The file name and
`id` must match, numbers zero-padded to 3 digits and never reused (S-BA-005).
Only the human commits it; agents never write under requirements/*/sources/**.
Set human_confirmed to true only after checking every turn: speakers are right,
human turns are your own words, and nothing personal, health-related or secret
is left in (S-BA-056, S-DATA-004). Then run harness/check_transcript.py on it.
-->

# INT-NNN: <area> kickoff interview

## Topics covered

<!-- One row per guide topic, in guide order (blocking first, at most 10, S-BA-055).
Coverage: covered, partial or not covered. -->

| Topic | Category | Blocking | Coverage |
| --- | --- | --- | --- |
| T-01 | <actors, goals, journeys, rules, permissions, quality_targets or out_of_scope> | yes | covered |

## Turns

<!-- Numbered T1, T2, ... with no gaps. Speaker is human or interviewer (S-BA-056).
Every interviewer turn has a topic/kind line. A readback restates one point and
also has key, value and from (earlier human turns) (S-BA-055). -->

### T1 [interviewer]
topic: T-01 · kind: question

<one question, with no candidate values or defaults>

### T2 [human]

<the human's answer, as typed>

### T3 [interviewer]
topic: T-01 · kind: readback · key: {entity: <entity>, target_id: <stable id or null>, attribute: <attribute>} · value: <value from T2> · from: T2

<the single point, restated, with a request to confirm>

### T4 [human]

<confirmation or correction>

## Decisions

<!-- Each cites a confirmed readback pair INT-NNN#T<k>/T<k+1> or a human turn
INT-NNN#T<k>. Only human turns are sources (S-BA-056, S-BA-057). -->

- <decision> (INT-NNN#T3/T4)

## Open items

<!-- Every topic not covered, with its topic ID, plus anything left unanswered
or raised outside the guide. Write "- None." if nothing is open. These become
open assumptions and the first question batch (S-BA-057). -->

- T-NN: <what is still open>

## Sources

<!-- The inputs the session used. The intake ref must appear here. -->

- Interview guide: <owner/repo#n>, guide comment <link>
- Product core: knowledge/product-core.md at <commit>
