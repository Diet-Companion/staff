"""Render validated test-gen output into issue comments. No model involved.

Deterministic: the same inputs and arguments give the same bytes. Stage-1 output is comments only
(S-QA-018):
- one comment on the ticket per draft: the decision summary first, then the cited sources, the
  test files, the work-sandbox result (S-QA-017), the suspected issues (S-QA-009) and what goes
  back (questions). The full patch is a CI artifact, not comment text;
- one comment per requirement-defect item, on the requirement's own ticket when --req-tickets
  names it (S-QA-011), else on this ticket.
Private reports are never rendered (S-SEC-011): the comment says only that some were withheld.

Model text outside code blocks is escaped as in render_comment.py (S-SEC-002).

CLI:
  render_qa.py render  --in validated.json --meta qa-meta.json --out-dir D
                       [--applied applied.json] [--sandbox sandbox.json] [--req-tickets F]
                       [--patch-artifact NAME] <footer args>
  render_qa.py failure --reason CODE --out-dir D <footer args>
Writes NN-*.md files to D in posting order, plus routing.json as render_developer.py does.
"""
import argparse
import os

from common import REASONS, HarnessError, load_json, run_main, write_json
from render_architect import fenced
from render_comment import FOOTER_FORMATS, MAX_COMMENT_CHARS, esc, footer, ids, quote, render_questions
from work_sandbox import check_result, sandbox_of

ANSWER_HINT = ("Answer in a comment as `Q-001: b` (or free text); then comment `/qa` to continue. "
               "Choosing an option is your decision (S-QA-001); the recommendation never applies by itself.")
STAGE_NOTE = ("Stage-1 draft: nothing is committed (S-QA-018). To take it, apply the patch artifact "
              "on a branch and open the PR yourself.")


def render_files(applied, proposed):
    if applied is None:
        out = ["#### Files", ""] + [f"- `{esc(f['path'])}` ({esc(f['op'])})" for f in proposed]
        return out + ["", "The work sandbox did not apply the draft, so there is no patch.", ""]
    out = ["#### Files", "", "| File | + | − |", "| --- | --- | --- |"]
    for f in applied["files"]:
        out.append(f"| `{esc(f['path'])}` | {int(f['added'])} | {int(f['removed'])} |")
    return out + ["", f"{int(applied['lines_changed'])} changed lines.", ""]


def render_sandbox(result, sandbox):
    out = ["#### Work sandbox (S-QA-017)", ""]
    if result is None:
        return out + ["No result: the sandbox job didn't finish. See the run's logs.", ""]
    if not check_result(result, sandbox):
        return out + ["The sandbox result failed the harness's shape check, so it isn't shown.", ""]
    if result["status"] == "untested":
        return out + ["Not tested: `.staff/tests.yml` has no `sandbox` commands for this layer.", ""]
    t, b = result["tests"], result["build"]
    verdict = "**pass**" if result["status"] == "pass" else "**fail**"
    out += [f"Result: {verdict}. Build: base {'passes' if b['base'] else 'fails'}, change "
            f"{'passes' if b['head'] else '**fails**'}. Layer tests: {t['head_total']} on the change "
            f"({t['added']} added), {t['base_total']} on the base."]
    messages = result.get("messages") or {}
    for key, label in (("added_failing", "Added tests that fail"),
                       ("expected_failing", "Added tests that fail as expected (suspected issues)"),
                       ("regressions", "Tests that pass on the base and fail on the change"),
                       ("flaky", "Failed, then passed on a re-run (flaky)"), ("base_failing", "Already failing on the base")):
        if t.get(key):
            out += ["", f"{label}:", ""] + [f"- `{esc(x)}`" + (f": {esc(messages[x])}" if x in messages else "")
                                            for x in t[key]]
    f = result.get("failure")
    if f:
        step = {"setup": "Setup", "build": "The build", "report": "The test run"}[f["step"]]
        what = "wrote no JUnit report" if f["step"] == "report" else "failed"
        out += ["", f"{step} {what} on the change: `{esc(f['command'])}`. Its last output lines:", "",
                fenced("\n".join(f["tail"]) or "(no output)")]
    return out + ["", "The tests ran on the sandbox runner, so treat this result as advisory.", ""]


def render_main(data, meta, applied, sandbox, args):
    r = meta["readiness"]
    title = "draft tests" if data["pr"] else "no tests proposed"
    out = [f"### Test engineer, {esc(data['agent'])} (stage 1): {title}", "",
           f"Area: {esc(meta['area'] or 'none')} · Layer: {esc(meta['layer'])} · Readiness: {esc(r['status'])}", "",
           "#### Decide first", "", quote(data["decision_summary"]), ""]
    if r["blockers"]:
        out += ["#### Blockers", ""] + [f"- {esc(b)}" for b in r["blockers"]] + [""]
    if data["suspected_issues"]:
        out += ["#### Suspected issues (S-QA-009)", "",
                "Each is a test whose cited expectation the code doesn't meet. You decide whether it's a bug.", ""]
        out += [f"- **{esc(s['id'])}** `{esc(s['test_id'])}` (cites {ids(s['cites'])}): {esc(s['text'])}"
                for s in data["suspected_issues"]] + [""]
    pr = data["pr"]
    if pr:
        out += ["#### Draft tests", "", f"- **Kind:** {esc(pr['kind'])} · **Base:** {esc(pr['base'])}",
                f"- **Cites:** {ids(pr['cited_ids'])}"]
        if pr["characterization"]:
            out.append(f"- **Characterization:** {ids(pr['characterization'])}")
        for e in pr["expected_failures"]:
            out.append(f"- **Expected failure** `{esc(e['test_id'])}`: expected {esc(e['expected'])}; "
                       f"actual {esc(e['actual'])}. Evidence: {ids(e['evidence_refs'])}")
        out += [""] + render_files(applied, data["proposed_files"])
        out += render_sandbox(sandbox, sandbox_of(meta)[0])
        if args.patch_artifact and args.run_url:
            out += [f"Patch: the `{esc(args.patch_artifact)}` artifact of [this run]({args.run_url}).", ""]
    if data["questions"]:
        out += render_questions(data["questions"], ANSWER_HINT) + [""]
    if data["assumptions"]:
        out += ["#### Assumptions", ""] + [f"- **{esc(a['id'])}**: {esc(a['text'])}" for a in data["assumptions"]] + [""]
    if data["defect_items"]:
        out += ["#### Requirement-defect items", "",
                f"{len(data['defect_items'])} item(s) posted on the requirements' tickets (S-QA-011).", ""]
    withheld = data.get("private_reports_withheld") or []
    if withheld:
        out += [f"{len(withheld)} private report(s) withheld from this public comment (S-SEC-011): "
                + ", ".join(f"{esc(w['id'])} ({esc(w['kind'])})" for w in withheld) + ".", ""]
    if pr:
        out += [STAGE_NOTE, ""]
    out += [f"Sources: {ids(data['source_refs'])}", "", footer(args)]
    return "\n".join(out) + "\n"


def render_defect(d, args):
    out = [f"### Requirement-defect item: {esc(d['target'])} ({esc(d['kind'])})", "",
           "From a test engineer run (S-QA-011).", "", quote(d["text"]), "", f"Evidence: {ids(d['evidence_refs'])}", "",
           "The test engineer never edits requirements. Fix it through the Analyst or your own commit.", "", footer(args)]
    return "\n".join(out) + "\n"


def render(data, meta, applied, sandbox, args, req_tickets):
    files, routing = [("00-main.md", render_main(data, meta, applied, sandbox, args))], {"00-main.md": None}
    for n, d in enumerate(data["defect_items"], start=1):
        name = f"{n:02d}-defect-{d['target'].replace('/', '-')}.md"
        files.append((name, render_defect(d, args)))
        routing[name] = req_tickets.get(d["target"].split("/")[0])
    return files, routing


def render_failure(reason, args):
    code = reason if reason in REASONS else "read_job_failed"
    logs = f"[the run's logs]({args.run_url})" if args.run_url else "the run's logs"
    return [("00-failure.md", f"Test engineer run {args.run_id} failed: `{code}`. See {logs}.\n\n{footer(args)}\n")]


def load_optional(path):
    return load_json(path, "render_failed") if path and os.path.exists(path) else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=["render", "failure"])
    ap.add_argument("--in", dest="path")
    ap.add_argument("--meta", help="qa-meta.json: the bundle's harness-made qa section")
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
        if not str(data.get("agent", "")).startswith("test-gen"):
            raise HarnessError("render_failed", "not test-gen output")
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
