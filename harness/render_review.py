"""Render validated reviewer output into one PR comment and its labels. No model involved.

Deterministic: the same input and arguments give the same bytes. One comment per
run (S-BA-032): the heading and "not yet qualified" notice, the decision summary
first, then findings ordered by severity, questions, proposed `changes`
declarations and draft test conditions. Model text is quoted data, escaped as in
render_comment.py (S-SEC-002).

The comment ends with a machine-readable block, an HTML comment that GitHub
doesn't display: the reviewed commit, the verdict, and each finding's ID,
severity and classification. The ready-gate check reads only this block, and
only from comments by the reviewer App (S-BA-017 item 5).

CLI:
  render_review.py render  --in validated.json --out-dir D <footer args>
  render_review.py failure --reason CODE --out-dir D <footer args>
Each writes 00-review.md (or 00-failure.md) to D, and render also writes
labels.json: {"add": [...], "remove": [...]}.
"""
import argparse
import json
import os

from common import REASONS, HarnessError, load_json, run_main, write_json
from render_comment import FOOTER_FORMATS, MAX_COMMENT_CHARS, esc, footer, ids, quote, render_questions

BLOCK_TAG = "staff-review:v1"
VERDICT_TITLES = {"ready": "ready", "ready_with_questions": "ready with questions", "not_ready": "not ready"}
# Labels the write stage may set (review-requirements skill, S-BA-034).
LABELS = {"not_ready": "ba:not-ready", "questions": "ba:questions"}
ANSWER_HINT = ("Answer in a comment as `Q-001: b` (or free text). After you push changes, comment "
               "`/review` for a re-review: finding IDs stay the same for issues that still hold.")
UNQUALIFIED = ("> **Not yet qualified.** This checklist hasn't met its stage 1→2 threshold yet "
               "(S-BA-032). The verdict is advice; you decide (S-BA-018).")


def machine_block(data, args):
    """The hidden block the gate check parses. JSON that can't close the HTML comment."""
    block = {
        "schema": BLOCK_TAG,
        "artifact_type": data["artifact_type"],
        "target": data["target"]["ref"],
        "reviewed_sha": data["reviewed_sha"],
        "verdict": data["verdict"],
        "findings": [{"id": f["finding_id"], "checklist_id": f["checklist_id"],
                      "severity": f["severity"], "classification": f["classification"]}
                     for f in data["findings"]],
        "questions": [{"id": q["id"], "blocking": q["blocking"]} for q in data["questions"]],
        "run_id": args.run_id,
        "staff_sha": args.staff_sha,
    }
    text = json.dumps(block, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    # Inside a JSON string these escapes decode to the same text; outside one they never occur.
    text = text.replace("<", "\\u003c").replace(">", "\\u003e").replace("--", "-\\u002d")
    return f"<!-- {BLOCK_TAG}\n{text}\n-->"


def counts(findings):
    by = {s: sum(1 for f in findings if f["severity"] == s) for s in ("blocker", "major", "minor")}
    return ", ".join(f"{n} {s}" for s, n in by.items())


def render_findings(findings):
    out = ["#### Findings", ""]
    if not findings:
        return out + ["None.", ""]
    for n, f in enumerate(findings, start=1):
        out += [
            f"**{n}. {esc(f['severity'])} · {esc(f['checklist_id'])} · {esc(f['classification'])}** "
            f"· ID {esc(f['finding_id'])}",
            "",
            f"Location: {esc(f['location'])}",
            "",
            quote(f["text"]),
            "",
        ]
        if f.get("rewording"):
            out += ["Suggested rewording:", "", quote(f["rewording"]), ""]
        if f.get("domain_source_stale"):
            out += ["Domain source stale (S-BA-026).", ""]
        out += [f"Cites: {ids(f['cited_ids'])} · Evidence: {ids(f['evidence_refs'])}", ""]
    return out


def render_changes(changes):
    out = ["#### Proposed `changes` declarations", "",
           "Not applied. Add one to the requirement, with your `accepted_by`, only if you accept it (S-BA-015).", ""]
    for c in changes:
        out += [f"- {esc(c['requirement'])} → {esc(c['rule'])} ({esc(c['kind'])}), for finding {esc(c['finding_id'])}:",
                "", quote(c["proposed_statement"]), "", f"  Cites: {ids(c['cites'])}", ""]
    return out


def render_test_conditions(conditions):
    out = ["<details><summary>Draft test conditions ({}): candidate input for S-BA-050</summary>".format(len(conditions)), ""]
    for tc in conditions:
        out += [f"**{esc(tc['id'])}** ({esc(tc['kind'])})", ""]
        out += [f"- **Given** {esc(g)}" for g in tc["given"]]
        out += [f"- **When** {esc(tc['when'])}"]
        out += [f"- **Then** {esc(t)}" for t in tc["then"]]
        out += ["", f"Cites: {ids(tc['cites'])}", ""]
    return out + ["</details>", ""]


def render_review(data, args):
    q = data["questions"]
    blocking = sum(1 for x in q if x["blocking"])
    out = [
        f"### Reviewer ({esc(data['artifact_type'])}): {VERDICT_TITLES[data['verdict']]}",
        "",
        UNQUALIFIED,
        "",
        f"**Verdict:** {VERDICT_TITLES[data['verdict']]} · **Reviewed commit:** `{esc(data['reviewed_sha'])}`  ",
        f"Findings: {counts(data['findings'])} · Questions: {len(q)} ({blocking} blocking)",
        "",
        "#### Decide first",
        "",
        quote(data["decision_summary"]),
        "",
    ]
    out += render_findings(data["findings"])
    if q:
        out += render_questions(q, ANSWER_HINT) + [""]
    if data.get("proposed_changes"):
        out += render_changes(data["proposed_changes"])
    if data.get("test_conditions"):
        out += render_test_conditions(data["test_conditions"])
    out += [footer(args), "", machine_block(data, args)]
    return "\n".join(out) + "\n"


def labels(data):
    want = set()
    if data["verdict"] == "not_ready":
        want.add(LABELS["not_ready"])
    if data["questions"]:
        want.add(LABELS["questions"])
    return {"add": sorted(want), "remove": sorted(set(LABELS.values()) - want)}


def render_failure(reason, args):
    code = reason if reason in REASONS else "read_job_failed"
    logs = f"[the run's logs]({args.run_url})" if args.run_url else "the run's logs"
    return f"Reviewer run {args.run_id} failed: `{code}`. See {logs}. No verdict was given.\n\n{footer(args)}\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=["render", "failure"])
    ap.add_argument("--in", dest="path", help="validated output (render mode)")
    ap.add_argument("--reason", help="reason code (failure mode)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--run-url", default="")
    ap.add_argument("--stage", type=int, default=1)
    ap.add_argument("--model", required=True)
    ap.add_argument("--staff-sha", required=True)
    args = ap.parse_args()
    for name, rx in FOOTER_FORMATS.items():
        if getattr(args, name) and not rx.fullmatch(getattr(args, name)):
            raise HarnessError("render_failed", f"--{name.replace('_', '-')} has an unexpected format")
    os.makedirs(args.out_dir, exist_ok=True)
    if args.mode == "render":
        data = load_json(args.path, "artifact_missing")
        if data.get("agent") != "reviewer":
            raise HarnessError("render_failed", "not reviewer output")
        name, text = "00-review.md", render_review(data, args)
    else:
        name, text = "00-failure.md", render_failure(args.reason or "", args)
    if len(text) > MAX_COMMENT_CHARS:
        raise HarnessError("render_too_large", f"{name} has {len(text)} chars > {MAX_COMMENT_CHARS}")
    with open(os.path.join(args.out_dir, name), "w", encoding="utf-8") as fh:
        fh.write(text)
    if args.mode == "render":
        write_json(os.path.join(args.out_dir, "labels.json"), labels(data))
    print(name)


if __name__ == "__main__":
    run_main(main)
