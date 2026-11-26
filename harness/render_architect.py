"""Render validated Architect output into issue comments. No model involved.

Deterministic: the same input and arguments give the same bytes. Stage-1 output is
comments only (S-ARCH-041):
- one main comment on the design-need ticket: the decision summary first, then the
  questions that belong to no ADR, conflicts, assumptions, applied answers and notes;
- one comment per drafted artifact, each with a readable summary and the proposed
  file (the patch artifact) in a code block, so each draft gets its own verdict. An
  ADR draft and its question share one comment. An interface comment carries its
  spec documents;
- one comment per requirement-defect item, posted on the requirement's own ticket
  when --req-tickets names it (S-ARCH-017), else on the design-need ticket.

Model text outside code blocks is escaped as in render_comment.py (S-SEC-002). Code
blocks use a fence longer than any backtick run in their content, so model text can't
close them; GitHub renders no links, images, HTML or mentions inside them.

CLI:
  render_architect.py tickets --product-dir P --out F    (read stage: REQ-n -> intake issue number)
  render_architect.py render  --in validated.json --out-dir D [--req-tickets F] <footer args>
  render_architect.py failure --reason CODE --out-dir D <footer args>
Writes NN-*.md files to D in posting order, and render also writes routing.json:
{file name: issue number or null for the design-need ticket}.
"""
import argparse
import glob
import json
import os
import re

import yaml

from common import REASONS, HarnessError, load_json, run_main, write_json
from render_comment import (FOOTER_FORMATS, MAX_COMMENT_CHARS, _STRIP, esc, footer, ids, quote,
                            render_questions)

DIRS = {"adr": "adr", "component": "components", "interface": "interfaces", "qas": "quality"}
SPEC_EXT = {"openapi": "yaml", "asyncapi": "yaml", "json-schema": "json", "graphql": "graphql", "protobuf": "proto"}
OUTCOME_TITLES = {"design": "design drafts", "drift": "drift questions", "blocked": "blocked", "no_op": "nothing to do"}
ANSWER_HINT = ("Answer in a comment as `Q-001: b` (or free text); then comment `/architect` to continue. "
               "Choosing an option is your decision (S-ARCH-001); the recommendation never applies by itself.")
STAGE_NOTE = "Stage-1 draft: nothing is committed. To accept it, commit the file yourself (S-ARCH-041)."


def fenced(text, lang=""):
    text = _STRIP.sub("", str(text)).replace("\r", "")
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{lang}\n{text}\n{fence}"


def artifact_path(a):
    return f"architecture/{a['area']}/{DIRS[a['type']]}/{a['id']}.md"


def patch(a):
    front = {k: v for k, v in a.items() if k != "type"}
    text = "---\n" + yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=120) + "---\n"
    return [f"<details><summary>Proposed file <code>{esc(artifact_path(a))}</code></summary>", "",
            fenced(text, "yaml"), "", "</details>", ""]


def head(a, title):
    # An interface has no status of its own; each version has one.
    status = esc(a["status"]) if "status" in a else "per version"
    return [f"### {esc(a['id'])}: {title}", "", f"Area: {esc(a['area'])} · Status: {status}", ""]


def render_adr(a, questions):
    out = head(a, esc(a["title"]))
    out += [f"Drivers: {ids(a['drivers'])} · Design for: {ids(a['design_for'])}", "", "**Context**", "",
            quote(a["context"]["text"]), "", f"Cites: {ids(a['context']['cites'])}", "", "**Options**", "",
            "| Option | Summary | Reversibility | Constraints |", "| --- | --- | --- | --- |"]
    for o in a["options"]:
        rec = " (recommended)" if o["key"] == a["recommended"]["option"] else ""
        keep = " · keeps the current design" if o.get("keeps_current_design") else ""
        cons = ", ".join(esc(c["id"]) for c in o["constraints"]) or "none"
        out.append(f"| {esc(o['key'])}{rec}{keep} | {esc(o['summary'])} | {esc(o['reversibility'])} | {cons} |")
    out.append("")
    for o in a["options"]:
        out += [f"**Option {esc(o['key'])}**", "",
                f"- Pros: {esc(o['pros'])}", f"- Cons: {esc(o['cons'])}", f"- Cost: {esc(o['cost'])}",
                f"- Risks: {esc(o['risks'])}", f"- Consequences: {esc(o['consequences'])}",
                f"- Satisfies: {ids(o['satisfies'])} · Affects: {ids(o['affects'])} · Cites: {ids(o['cites'])}"]
        out += [f"- Constraint {esc(c['id'])} ({esc(c['kind'])}, check: {esc(c['check'])}): {esc(c['statement'])}"
                for c in o["constraints"]]
        out.append("")
    out += [f"Recommended: **{esc(a['recommended']['option'])}**: {esc(a['recommended']['reason'])}", ""]
    own = [q for q in questions if q.get("adr") == a["id"]]
    if own:
        out += render_questions(own, ANSWER_HINT) + [""]
    return out


def render_component(a):
    out = head(a, f"component `{esc(a['name'])}`")
    out += ["**Responsibilities**", "", quote(a["responsibilities"]), "",
            f"Provides: {ids(a['provides'])} · Consumes: {ids(a['consumes'])} · "
            f"Allowed dependencies: {ids([str(d) for d in a['allowed_dependencies']])}", "",
            f"Provenance: {esc(a['provenance'])} · Cites: {ids(a['cites'])}", "",
            "| Testability item | State | Reason |", "| --- | --- | --- |"]
    out += [f"| {esc(t['item'])} | {esc(t['state'])} | {esc(t.get('reason') or '')} |" for t in a["testability"]]
    return out + [""]


def render_interface(a, specs, inline=True, run_id=""):
    out = head(a, f"interface `{esc(a['name'])}` ({esc(a['kind'])})")
    out += [f"Owner: {esc(a['owner'])} · Compatibility policy: {esc(a['compatibility_policy'] or 'not set (yours to decide)')}",
            "", "| Version | Status | Spec |", "| --- | --- | --- |"]
    out += [f"| {esc(v['version'])} | {esc(v['status'])} | {esc(v['spec'])} |" for v in a["versions"]]
    out.append("")
    declared = {v["version"]: v["spec"] for v in a["versions"]}
    for s in specs:
        # The path the interface file points at, so the proposed files agree. Only a path inside this
        # interface's own folder is trusted; anything else falls back to <version>.<ext> there.
        base = f"architecture/{a['area']}/interfaces/{a['id']}/"
        path = declared.get(s["version"], "")
        if not (path.startswith(base) and re.fullmatch(r"[A-Za-z0-9._/-]+", path) and ".." not in path):
            path = f"{base}{s['version']}.{SPEC_EXT.get(s['format'].lower(), 'txt')}"
        if inline:
            out += [f"<details><summary>Proposed spec <code>{esc(path)}</code> ({esc(s['format'])})</summary>", "",
                    fenced(s["document"]), "", "</details>", ""]
        else:
            # Too long for one comment (GitHub's limit): the spec stays in the run's validated output, which
            # the acceptance commit is built from. run_id is format-checked (FOOTER_FORMATS), so it goes into
            # the code span unescaped.
            out += [f"Proposed spec <code>{esc(path)}</code> ({esc(s['format'])}): {len(s['document']):,} characters, "
                    f"too long to show here. It is in the `architect-run-{run_id}` artifact of this run "
                    "(`validated.json`, `spec_versions`).", ""]
    return out


def render_qas(a):
    m = a["measure"]
    out = head(a, f"quality scenario for {esc(a['req'])} ({esc(a['attribute'])})")
    out += [f"- **Stimulus:** {esc(a['stimulus'])}", f"- **Environment:** {esc(a['environment'])}",
            f"- **Response:** {esc(a['response'])}",
            f"- **Measure:** {esc(m.get('statement', ''))} (cites {ids(m.get('cites', []))})",
            f"- **Verification:** {esc(json.dumps(a['verification'], ensure_ascii=False, sort_keys=True))}",
            f"- **Addressed by:** {ids(a['addressed_by'] or [])}", ""]
    if a.get("gap_reason"):
        out += [f"Gap: {esc(a['gap_reason'])} (accepting a gap is yours, S-ARCH-016)", ""]
    return out


def render_artifact(a, data, args):
    if a["type"] == "adr":
        out = render_adr(a, data["questions"])
    elif a["type"] == "component":
        out = render_component(a)
    elif a["type"] == "interface":
        specs = [s for s in data["spec_versions"] if s["if_id"] == a["id"]]
        text = "\n".join(render_interface(a, specs) + patch(a) + [STAGE_NOTE, "", footer(args)]) + "\n"
        if len(text) <= MAX_COMMENT_CHARS:
            return text
        out = render_interface(a, specs, inline=False, run_id=args.run_id)
    else:
        out = render_qas(a)
    out += patch(a) + [STAGE_NOTE, "", footer(args)]
    return "\n".join(out) + "\n"


def render_main(data, args):
    t = data["trigger"]
    out = [f"### Architect (stage 1): {OUTCOME_TITLES[data['outcome']]}", "",
           f"Trigger: {esc(t['kind'])} · {esc(t['ref'])} · Area: {esc(t['area'])}", "",
           "#### Decide first", "", quote(data["decision_summary"]), ""]
    if data["artifacts"]:
        out += ["#### Drafts", ""] + [f"- **{esc(a['id'])}** ({esc(a['type'])}): `{esc(artifact_path(a))}`"
                                      for a in data["artifacts"]] + ["", "Each draft follows in its own comment.", ""]
    loose = [q for q in data["questions"] if not q.get("adr")]
    if loose:
        out += render_questions(loose, ANSWER_HINT) + [""]
    if data["conflicts"]:
        out += ["#### Conflicts with accepted constraints", ""]
        out += [f"- {esc(c['constraint_id'])} vs {esc(c['adr'])} option {esc(c['option_key'])}: "
                f"{esc(c['resolution'])}. {esc(c['reason'])}" for c in data["conflicts"]] + [""]
    if data["assumptions"]:
        out += ["#### Open assumptions", ""]
        out += [f"- **{esc(a['id'])}**{' (blocking)' if a.get('blocking') else ''}: {esc(a['text'])}"
                for a in data["assumptions"]] + [""]
    if data["defect_items"]:
        out += ["#### Requirement-defect items", "",
                f"{len(data['defect_items'])} item(s) posted on the requirements' tickets (S-ARCH-017).", ""]
    if data["answers_applied"]:
        out += ["#### Answers applied", ""]
        out += [f"- {esc(a['target'])} `{esc(a['field'])}` from {esc(a['comment_ref'])}" for a in data["answers_applied"]] + [""]
    if data.get("advisory_notes"):
        out += ["#### Advisory notes", ""] + [f"- {esc(n if isinstance(n, str) else json.dumps(n, sort_keys=True))}"
                                               for n in data["advisory_notes"]] + [""]
    out += [f"Sources: {ids(data['source_refs'])}", "", footer(args)]
    return "\n".join(out) + "\n"


def render_defect(d, data, args):
    out = [f"### Requirement-defect item: {esc(d['target'])} ({esc(d['kind'])})", "",
           f"From the Architect's run on {esc(data['trigger']['ref'])} (S-ARCH-017).", "",
           quote(d["text"]), "", f"Evidence: {ids(d['evidence_refs'])}", "",
           "The Architect never edits requirements. Fix it through the Analyst or your own commit.", "", footer(args)]
    return "\n".join(out) + "\n"


def render(data, args, req_tickets):
    files, routing = [("00-main.md", render_main(data, args))], {"00-main.md": None}
    for n, a in enumerate(data["artifacts"], start=1):
        name = f"{n:02d}-{a['id']}.md"
        files.append((name, render_artifact(a, data, args)))
        routing[name] = None
    for n, d in enumerate(data["defect_items"], start=len(files)):
        name = f"{n:02d}-defect-{d['target'].replace('/', '-')}.md"
        files.append((name, render_defect(d, data, args)))
        routing[name] = req_tickets.get(d["target"].split("/")[0])
    return files, routing


def render_failure(reason, args):
    code = reason if reason in REASONS else "read_job_failed"
    logs = f"[the run's logs]({args.run_url})" if args.run_url else "the run's logs"
    return [("00-failure.md", f"Architect run {args.run_id} failed: `{code}`. See {logs}.\n\n{footer(args)}\n")]


def req_tickets(product_dir, repo):
    """{REQ-n: issue number} from each requirement's first tracker ref in this repo."""
    out = {}
    for path in sorted(glob.glob(os.path.join(product_dir, "requirements", "*", "REQ-*.md"))):
        with open(path, encoding="utf-8") as fh:
            m = re.match(r"^---\n(.*?)\n---\n", fh.read(), re.S)
        front = yaml.safe_load(m.group(1)) if m else {}
        for ref in (front or {}).get("tracker") or []:
            hit = re.fullmatch(re.escape(repo) + r"#([0-9]+)", str(ref))
            if hit:
                out[front["id"]] = int(hit.group(1))
                break
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=["tickets", "render", "failure"])
    ap.add_argument("--product-dir", help="product checkout (tickets mode)")
    ap.add_argument("--repo", help="owner/name (tickets mode)")
    ap.add_argument("--out", help="output file (tickets mode)")
    ap.add_argument("--in", dest="path", help="validated output (render mode)")
    ap.add_argument("--req-tickets", help="JSON {REQ-n: issue number}, from the requirements' tracker fields")
    ap.add_argument("--reason", help="reason code (failure mode)")
    ap.add_argument("--out-dir")
    ap.add_argument("--run-id")
    ap.add_argument("--run-url", default="")
    ap.add_argument("--stage", type=int, default=1)
    ap.add_argument("--model")
    ap.add_argument("--staff-sha")
    args = ap.parse_args()
    if args.mode == "tickets":
        if not (args.product_dir and args.repo and args.out):
            raise HarnessError("render_failed", "tickets needs --product-dir, --repo and --out")
        write_json(args.out, req_tickets(args.product_dir, args.repo))
        return
    if not (args.out_dir and args.run_id and args.model and args.staff_sha):
        raise HarnessError("render_failed", "render and failure need --out-dir, --run-id, --model and --staff-sha")
    for name, rx in FOOTER_FORMATS.items():
        if getattr(args, name) and not rx.fullmatch(getattr(args, name)):
            raise HarnessError("render_failed", f"--{name.replace('_', '-')} has an unexpected format")
    if args.mode == "render":
        data = load_json(args.path, "artifact_missing")
        if data.get("agent") != "architect":
            raise HarnessError("render_failed", "not Architect output")
        tickets = load_json(args.req_tickets, "render_failed") if args.req_tickets else {}
        if not all(isinstance(v, int) for v in tickets.values()):
            raise HarnessError("render_failed", "--req-tickets values must be issue numbers")
        files, routing = render(data, args, tickets)
    else:
        files, routing = render_failure(args.reason or "", args), {"00-failure.md": None}
    for name, text in files:
        if len(text) > MAX_COMMENT_CHARS:
            raise HarnessError("render_too_large", f"{name} has {len(text)} chars > {MAX_COMMENT_CHARS}")
    os.makedirs(args.out_dir, exist_ok=True)
    for name, text in files:
        with open(os.path.join(args.out_dir, name), "w", encoding="utf-8") as fh:
            fh.write(text)
        print(name)
    write_json(os.path.join(args.out_dir, "routing.json"), routing)


if __name__ == "__main__":
    run_main(main)
