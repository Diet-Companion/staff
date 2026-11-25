"""Render validated Analyst output into Markdown issue comments. No model involved.

Deterministic: the same input and arguments give the same bytes. One main
comment (decision summary first, then the question batch, interview guide or
escalation), plus one comment per drafted requirement, so the human gives one
verdict per draft (S-BA-037, S-BA-042, S-BA-049).

All model text is quoted data (S-SEC-002): Markdown and HTML are escaped, and
@mentions and #references are broken, so a comment can't ping people, embed
images or links, or cross-reference other issues.

CLI:
  render_comment.py render  --in validated.json --out-dir D <footer args>
  render_comment.py failure --reason CODE --out-dir D <footer args>
Each writes NN-*.md files to D, in posting order.
"""
import argparse
import os
import re

from common import REASONS, HarnessError, load_json, run_main

MAX_COMMENT_CHARS = 60_000  # GitHub's limit is 65,536
WJ = "\u2060"  # word joiner: breaks @mentions and #refs without visible change
_ESCAPE = re.compile(r"([\\`*_\[\]<>!|~&])")  # links, images, HTML, emphasis, code, tables
_LINE_START = re.compile(r"^(\d*)([-+=.)])")  # list, setext and ordered-list starts
_STRIP = re.compile(r"[\x00-\x08\x0b-\x1f\x7f\u202a-\u202e\u2066-\u2069]")
OUTCOME_TITLES = {
    "questions": "question batch",
    "drafts": "draft requirements",
    "drafts_and_questions": "draft requirements and questions",
    "interview_guide": "kickoff interview guide",
    "escalation": "escalation",
}
FOOTER_FORMATS = {
    "run_id": re.compile(r"[0-9]+-[0-9]+"),
    "model": re.compile(r"[A-Za-z0-9._:\[\]-]{1,100}"),
    "staff_sha": re.compile(r"[0-9a-f]{40}"),
    "run_url": re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/actions/runs/[0-9]+(/attempts/[0-9]+)?"),
}
ANSWER_HINT = "Answer in a comment as `Q-001: b` (or free text); then comment `/analyst` to continue."


def esc(text):
    """One line of model text, safe as inline Markdown."""
    text = _STRIP.sub("", str(text)).replace("\r", "")
    text = " ".join(text.split())
    text = _LINE_START.sub(r"\1\\\2", _ESCAPE.sub(r"\\\1", text))
    return text.replace("@", "@" + WJ).replace("#", "#" + WJ)


def quote(text):
    """A block of model text as a Markdown blockquote, keeping its line breaks."""
    lines = _STRIP.sub("", str(text)).replace("\r", "").split("\n")
    return "\n".join("> " + esc(line) if line.strip() else ">" for line in lines)


def ids(values):
    return ", ".join(esc(v) for v in values) if values else "none"


def key_text(key):
    target = esc(key["target_id"]) if key.get("target_id") else "no target"
    return f"{esc(key['entity'])} / {target} / {esc(key['attribute'])}"


STAGE_LABELS = {1: "advisory: comments only", 2: "proposing: opens PRs, each fully reviewed"}


def footer(args):
    label = STAGE_LABELS.get(args.stage, STAGE_LABELS[1])
    return "\n".join([
        "---",
        f"Staff-Run-Id: {args.run_id}  ",
        f"Stage: {args.stage} ({label}) · Model: {args.model} · Staff commit: {args.staff_sha}  ",
        f"Run: {args.run_url}" if args.run_url else "Run: n/a",
    ])


def render_questions(questions, hint=ANSWER_HINT):
    out = ["#### Questions", ""]
    for q in questions:
        mark = "**blocking**" if q["blocking"] else "non-blocking"
        key = f" · key: {key_text(q['key'])}" if q.get("key") else ""  # optional for the reviewer
        out += [
            f"**{esc(q['id'])}** ({mark} · blocks {ids(q['blocks'])}{key})",
            "",
            quote(q["text"]),
            "",
        ]
        for o in q["options"]:
            rec = " **(recommended)**" if o["id"] == q["recommended"] else ""
            out.append(f"- {esc(o['id'])}) {esc(o['text'])}{rec}")
        out += ["", f"Recommended: **{esc(q['recommended'])}**", ""]
    out.append(hint)
    return out


def render_main(data, args):
    intake = data["intake"]
    out = [
        f"### Analyst: {OUTCOME_TITLES[data['outcome']]}",
        "",
        f"Intake {esc(intake['ref'])} · area **{esc(intake['area'])}** · batch {intake['batch_number']}"
        f"{' · kickoff' if intake['is_kickoff'] else ''}",
        "",
        "#### Decisions for you",
        "",
        quote(data["decision_summary"]),
        "",
    ]
    if data.get("escalation"):
        e = data["escalation"]
        out += ["#### Escalation", "", f"Open blocking questions: {ids(e['open_blocking_questions'])}",
                "", quote(e["reason"]), ""]
    if data.get("interview_guide"):
        out += ["#### Interview guide", ""]
        for t in data["interview_guide"]["topics"]:
            mark = ", **blocking**" if t["blocking"] else ""
            out.append(f"- **{esc(t['topic_id'])}** ({esc(t['category'])}{mark}): {esc(t['text'])}")
        out += ["", "You run the interview and commit the transcript; the Analyst never starts one (S-BA-055).", ""]
    if data["questions"]:
        out += render_questions(data["questions"]) + [""]
    if data["requirements"]:
        out += ["#### Drafts", ""]
        for r in data["requirements"]:
            parent = f", parent {esc(r['parent'])}" if r.get("parent") else ""
            out.append(f"- **{esc(r['id'])}** ({esc(r['type'])}{parent}): {esc(r['title'])}")
        out += ["", "Each draft follows in its own comment.", ""]
    if data["assumptions"]:
        out += ["#### Open assumptions", ""]
        for a in data["assumptions"]:
            mark = " **blocking**" if a["blocking"] else ""
            out.append(f"- **{esc(a['id'])}**{mark} ({key_text(a['key'])}): {esc(a['text'])}")
        out.append("")
    if data.get("answers_applied"):
        out += ["#### Answers applied", ""]
        for a in data["answers_applied"]:
            out.append(f"- {esc(a['target'])} `{esc(a['field'])}` from {esc(a['comment_ref'])}")
        out.append("")
    out.append(footer(args))
    return "\n".join(out) + "\n"


def cited(items):
    return [f"- {esc(i['text'])} (cites {ids(i['cites'])})" for i in items] or ["- none"]


def none_or(value, render):
    return [f"none: {esc(value['none'])}"] if isinstance(value, dict) else render(value)


def render_requirement(r, args):
    i = r["intent"]
    out = [
        f"### Draft {esc(r['id'])} ({esc(r['type'])}): {esc(r['title'])}",
        "",
        f"Status: {esc(r['status'])} · area {esc(r['area'])} · parent {esc(r.get('parent') or 'none')}"
        f" · priority {esc(r['priority'] or 'not set')}",
        "",
        "#### Intent",
        "",
        f"- Actor: {esc(i['actor'])}",
        f"- Need: {esc(i['need'])}",
        f"- Business value: {esc(i['business_value'])}",
        f"- Cites: {ids(i['cites'])}",
        "",
        "#### Scope",
        "",
        "In:",
        *cited(r["scope"]["in"]),
        "",
        "Out:",
        *cited(r["scope"]["out"]),
        "",
    ]
    if r["acceptance_criteria"]:
        out += ["#### Acceptance criteria", ""]
        for ac in r["acceptance_criteria"]:
            out += [f"- **{esc(ac['id'])}** ({esc(ac['kind'])}; key: {key_text(ac['key'])})"]
            out += [f"  - Given: {esc(g)}" for g in ac["given"]]
            out += [f"  - When: {esc(ac['when'])}"]
            out += [f"  - Then: {esc(t)}" for t in ac["then"]]
            out += [f"  - Cites: {ids(ac['cites'])}"]
        out.append("")
    out += [f"Rules relied on: {ids(r['rules'])}", ""]
    if r["changes"]:
        out += ["#### Rule changes (need your acceptance)", ""]
        out += [f"- {esc(c['rule'])} ({esc(c['kind'])}): {esc(c['proposed_statement'])}" for c in r["changes"]]
        out.append("")
    out += ["Quality: " + " ".join(none_or(r["quality"], lambda v: [ids(v)])), ""]
    out += ["#### Permissions", ""]
    out += none_or(r["permissions"], lambda v: [
        f"- {esc(p['role'])}: may {ids(p['may'])}; may not {ids(p['may_not'])}" for p in v])
    out.append("")
    if r.get("terms"):
        out += ["#### New terms", ""]
        out += [f"- **{esc(t['term'])}**: {esc(t['definition'])} (cites {ids(t['cites'])})" for t in r["terms"]]
        out.append("")
    if r["assumptions"] or r["questions"]:
        out += ["#### Open points", ""]
        out += [f"- {esc(a['id'])} ({esc(a['status'])}{', blocking' if a['blocking'] else ''}): {esc(a['text'])}"
                for a in r["assumptions"]]
        out += [f"- {esc(q['id'])} ({esc(q['status'])}{', blocking' if q['blocking'] else ''}): {key_text(q['key'])}"
                for q in r["questions"]]
        out.append("")
    out += [f"Sources: {ids(r['sources'])}", ""]
    out += ["Stage-1 draft: nothing is committed. To accept it, apply it in your own commit (S-BA-042).", ""]
    out.append(footer(args))
    return "\n".join(out) + "\n"


def render(data, args):
    """[(filename, markdown)] in posting order."""
    files = [("00-main.md", render_main(data, args))]
    for n, r in enumerate(data["requirements"], start=1):
        files.append((f"{n:02d}-{r['id']}.md", render_requirement(r, args)))
    return files


def render_failure(reason, args):
    code = reason if reason in REASONS else "read_job_failed"
    logs = f"[the run's logs]({args.run_url})" if args.run_url else "the run's logs"
    text = f"Analyst run {args.run_id} failed: `{code}`. See {logs}.\n\n{footer(args)}\n"
    return [("00-failure.md", text)]


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
    # Footer values come from the harness, not the model; they must match these shapes.
    for name, rx in FOOTER_FORMATS.items():
        if getattr(args, name) and not rx.fullmatch(getattr(args, name)):
            raise HarnessError("render_failed", f"--{name.replace('_', '-')} has an unexpected format")
    if args.mode == "render":
        files = render(load_json(args.path, "artifact_missing"), args)
    else:
        files = render_failure(args.reason or "", args)
    os.makedirs(args.out_dir, exist_ok=True)
    for name, text in files:
        if len(text) > MAX_COMMENT_CHARS:
            raise HarnessError("render_too_large", f"{name} has {len(text)} chars > {MAX_COMMENT_CHARS}")
    for name, text in files:
        with open(os.path.join(args.out_dir, name), "w", encoding="utf-8") as fh:
            fh.write(text)
        print(name)


if __name__ == "__main__":
    run_main(main)
