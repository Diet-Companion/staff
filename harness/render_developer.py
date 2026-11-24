"""Render validated Developer output into issue comments. No model involved.

Deterministic: the same inputs and arguments give the same bytes. Stage-1 output is
comments only (S-DEV-022):
- one comment on the ticket per drafted change: the decision summary first, then the
  PR block, the changed files, the work-sandbox result (S-DEV-042) and what goes back
  (questions, design requests). The full patch is a CI artifact, not comment text;
- on dev:bootstrap, the drafted code-map entry in a code block, for the human to commit;
- one comment per requirement-defect item, on the requirement's own ticket when
  --req-tickets names it (S-DEV-008), else on this ticket.
Private reports are never rendered (S-DEV-019): the comment says only that some were withheld.

Model text outside code blocks is escaped as in render_comment.py (S-SEC-002).

CLI:
  render_developer.py render  --in validated.json --meta dev-meta.json --out-dir D
                              [--applied applied.json] [--sandbox sandbox.json] [--req-tickets F]
                              [--patch-artifact NAME] <footer args>
  render_developer.py failure --reason CODE --out-dir D <footer args>
Writes NN-*.md files to D in posting order, plus routing.json as render_architect.py does.
"""
import argparse
import os

import yaml

from common import REASONS, HarnessError, load_json, run_main, write_json
from render_architect import fenced
from render_comment import FOOTER_FORMATS, MAX_COMMENT_CHARS, esc, footer, ids, quote, render_questions
from work_sandbox import check_result

TITLES = {"proposed": "draft change", "code_map": "code-map draft", "no_code": "no change proposed"}
ANSWER_HINT = ("Answer in a comment as `Q-001: b` (or free text); then comment `/developer` to continue. "
               "Choosing an option is your decision (S-DEV-001); the recommendation never applies by itself.")
STAGE_NOTE = ("Stage-1 draft: nothing is committed (S-DEV-022). To take it, apply the patch artifact "
              "on a branch and open the PR yourself.")


def outcome(data):
    return "proposed" if data["pr"] else "code_map" if data["code_map"] else "no_code"


def render_pr(pr):
    acs = ", ".join(f"{esc(a['ac'])} ({esc(a['part'])})" for a in pr["implements_acs"]) or "none"
    out = ["#### Proposed change", "",
           f"- **Kind:** {esc(pr['kind'])} · **ACs:** {acs}",
           f"- **Implements:** {ids(pr['implements']) or 'no interface version'}"]
    if pr["fixes"]:
        out.append(f"- **Fixes:** {esc(pr['fixes']['target'])} ({esc(pr['fixes']['ticket'])})")
    for c in pr["constraints"]:
        out.append(f"- **Constraint {esc(c['id'])}:** {esc(c['disposition'])}. {esc(c['reason'])}")
    if pr["untested_acs"]:
        out.append("- **Untested ACs:** " + "; ".join(esc(json_text(u)) for u in pr["untested_acs"]))
    for f in pr["flags"]:
        out.append(f"- **Flag** {esc(f['flag_id'])}: {esc(f['reason'])}")
    for d in pr["dependencies"]:
        change = f"{esc(d['from'] or 'none')} → {esc(d['to'] or 'removed')}"
        out.append(f"- **Dependency** {esc(d['name'])}: {change}. {esc(d['reason'])}")
    return out + [""]


def json_text(v):
    return v if isinstance(v, str) else yaml.safe_dump(v, default_flow_style=True, sort_keys=True).strip()


def render_files(applied, proposed):
    if applied is None:
        out = ["#### Files", ""] + [f"- `{esc(f['path'])}` ({esc(f['op'])})" for f in proposed]
        return out + ["", "The work sandbox did not apply the change, so there is no patch.", ""]
    out = ["#### Files", "", "| File | + | − |", "| --- | --- | --- |"]
    for f in applied["files"]:
        gen = " (generated)" if f["generated"] else ""
        out.append(f"| `{esc(f['path'])}`{gen} | {int(f['added'])} | {int(f['removed'])} |")
    cap = int(applied["max_lines"])
    lines = int(applied["lines_changed"])
    out += ["", f"{lines} changed lines, generated files excepted (cap {cap}, S-DEV-010)."
            + (" **Over the cap: split the ticket.**" if applied["over_cap"] else "")]
    for g in applied.get("generators") or []:
        out.append(f"Generator `{esc(g['generator_id'])}`: {'ran' if g['ok'] else '**failed**'}.")
    return out + [""]


def render_sandbox(result, sandbox_cmds):
    out = ["#### Work sandbox (S-DEV-042)", ""]
    if result is None:
        return out + ["No result: the sandbox job didn't finish. See the run's logs.", ""]
    if not check_result(result, sandbox_cmds):
        return out + ["The sandbox result failed the harness's shape check, so it isn't shown.", ""]
    if result["status"] == "untested":
        return out + ["Not tested: `.staff/code.yml` has no `sandbox` commands for this area.", ""]
    t, b = result["tests"], result["build"]
    verdict = "**pass**" if result["status"] == "pass" else "**fail**"
    out += [f"Result: {verdict}. Build: base {'passes' if b['base'] else 'fails'}, change "
            f"{'passes' if b['head'] else '**fails**'}. Unit tests: {t['head_total']} on the change "
            f"({t['added']} added), {t['base_total']} on the base."]
    if b["head"] and not result["report"]["head"]:
        out.append("No JUnit report was written on the change.")
    messages = result.get("messages") or {}
    for key, label in (("added_failing", "Added tests that fail"), ("regressions", "Tests that pass on the base and fail on the change"),
                       ("flaky", "Failed, then passed on a re-run (flaky)"), ("base_failing", "Already failing on the base")):
        if t[key]:
            out += ["", f"{label}:", ""] + [f"- `{esc(x)}`" + (f": {esc(messages[x])}" if x in messages else "")
                                            for x in t[key]]
    f = result.get("failure")
    if f:
        step = {"setup": "Setup", "build": "The build", "report": "The test run"}[f["step"]]
        what = "wrote no JUnit report" if f["step"] == "report" else "failed"
        out += ["", f"{step} {what} on the change: `{esc(f['command'])}`. Its last output lines:", "",
                fenced("\n".join(f["tail"]) or "(no output)")]
    return out + ["", "The tests ran the proposed code on the sandbox runner, so treat this result as advisory.", ""]


def render_main(data, meta, applied, sandbox, args):
    r = meta["readiness"]
    out = [f"### Developer (stage 1): {TITLES[outcome(data)]}", "",
           f"Ticket kind: {esc(meta['ticket_kind'])} ({esc(meta['work'])}) · Area: {esc(meta['area'] or 'none')}"
           f" · Readiness: {esc(r['status'])}", "",
           "#### Decide first", "", quote(data["decision_summary"]), ""]
    if r["blockers"]:
        out += ["#### Blockers (S-DEV-007)", ""] + [f"- {esc(b)}" for b in r["blockers"]] + [""]
    if data["pr"]:
        out += render_pr(data["pr"]) + render_files(applied, data["proposed_files"])
        out += render_sandbox(sandbox, (meta.get("code_map_entry") or {}).get("sandbox"))
        if args.patch_artifact and args.run_url:
            out += [f"Patch: the `{esc(args.patch_artifact)}` artifact of [this run]({args.run_url}).", ""]
    if data["code_map"]:
        cm = data["code_map"]
        out += [f"#### Draft `.staff/code.yml` entry for `{esc(cm['area'])}`", "",
                "Human-owned (S-DEV-004): review it and commit it under `areas:` yourself.", "",
                fenced(yaml.safe_dump({cm["area"]: cm["entry"]}, allow_unicode=True, sort_keys=False, width=120), "yaml"), ""]
        out += ["Evidence: " + "; ".join(f"{esc(e['pattern_class'])} ({esc(e['stack'])}): {int(e['match_count'])} matches"
                                         for e in cm["evidence"]), ""]
    if data["classification"]:
        c = data["classification"]
        out += ["#### Classification (S-DEV-017)", "", f"- **Kind:** {esc(c['kind'])} · **Target:** {esc(c['defect']['target'])}",
                f"- **Expected:** {esc(c['defect']['expected'])}", f"- **Actual:** {esc(c['defect']['actual'])}", ""]
    if data["questions"]:
        out += render_questions(data["questions"], ANSWER_HINT) + [""]
    if data["design_requests"]:
        out += ["#### Design requests (S-DEV-008)", ""]
        out += [f"- **{esc(d['target'])}** ({esc(d['need'])}): {esc(d['missing'])} Evidence: {ids(d['evidence_refs'])}"
                for d in data["design_requests"]]
        out += ["", "To act on one, open a design-need ticket with `arch:design`.", ""]
    if data["assumptions"]:
        out += ["#### Assumptions", ""] + [f"- **{esc(a['id'])}**: {esc(a['text'])}" for a in data["assumptions"]] + [""]
    if data["defect_items"]:
        out += ["#### Requirement-defect items", "",
                f"{len(data['defect_items'])} item(s) posted on the requirements' tickets (S-DEV-008).", ""]
    withheld = data.get("private_reports_withheld") or []
    if withheld:
        out += [f"{len(withheld)} private report(s) withheld from this public comment (S-DEV-019): "
                + ", ".join(f"{esc(w['id'])} ({esc(w['kind'])})" for w in withheld)
                + ". Re-run the ticket privately to read them.", ""]
    if data["pr"]:
        out += [STAGE_NOTE, ""]
    out += [f"Sources: {ids(data['source_refs'])}", "", footer(args)]
    return "\n".join(out) + "\n"


def render_defect(d, ticket, args):
    out = [f"### Requirement-defect item: {esc(d['target'])} ({esc(d['kind'])})", "",
           f"From the Developer's run on {esc(ticket)} (S-DEV-008).", "",
           quote(d["text"]), "", f"Evidence: {ids(d['evidence_refs'])}", "",
           "The Developer never edits requirements. Fix it through the Analyst or your own commit.", "", footer(args)]
    return "\n".join(out) + "\n"


def render(data, meta, applied, sandbox, args, req_tickets):
    files, routing = [("00-main.md", render_main(data, meta, applied, sandbox, args))], {"00-main.md": None}
    ticket = data["pr"]["ticket"] if data["pr"] else "this ticket"
    for n, d in enumerate(data["defect_items"], start=1):
        name = f"{n:02d}-defect-{d['target'].replace('/', '-')}.md"
        files.append((name, render_defect(d, ticket, args)))
        routing[name] = req_tickets.get(d["target"].split("/")[0])
    return files, routing


def render_failure(reason, args):
    code = reason if reason in REASONS else "read_job_failed"
    logs = f"[the run's logs]({args.run_url})" if args.run_url else "the run's logs"
    return [("00-failure.md", f"Developer run {args.run_id} failed: `{code}`. See {logs}.\n\n{footer(args)}\n")]


def load_optional(path):
    return load_json(path, "render_failed") if path and os.path.exists(path) else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=["render", "failure"])
    ap.add_argument("--in", dest="path")
    ap.add_argument("--meta", help="dev-meta.json: the bundle's harness-made developer section")
    ap.add_argument("--applied", help="applied.json from work_sandbox.py apply")
    ap.add_argument("--sandbox", help="sandbox.json from work_sandbox.py test")
    ap.add_argument("--req-tickets")
    ap.add_argument("--patch-artifact", default="")
    ap.add_argument("--reason")
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
    if args.mode == "render":
        data = load_json(args.path, "artifact_missing")
        meta = load_json(args.meta, "artifact_missing")
        if data.get("agent") != "developer":
            raise HarnessError("render_failed", "not Developer output")
        tickets = load_json(args.req_tickets, "render_failed") if args.req_tickets else {}
        if not all(isinstance(v, int) for v in tickets.values()):
            raise HarnessError("render_failed", "--req-tickets values must be issue numbers")
        files, routing = render(data, meta, load_optional(args.applied), load_optional(args.sandbox), args, tickets)
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
