"""Append run records and review verdicts to the outcome store (S-GEN-029, S-GEN-031).

The lean-slice outcome store is a JSONL log kept outside Git (S-GEN-012): one
issue per month in the product repo, titled "Staff outcome store YYYY-MM" and
labelled `staff:log`, with one comment per entry. Only the recorder (the
workflow's GITHUB_TOKEN, `github-actions[bot]`) writes there; on export, any
comment by another account is ignored. Entries survive the 90-day artifact
expiry (S-DATA-007), can be deleted per run_id (S-DATA-008), and appends never
conflict. A local JSONL file is the other target, for tests and manual use.

Every entry is validated against schemas/run-log-entry.schema.json and
redaction-checked before it is stored, and fails closed otherwise (S-SEC-004).

CLI:
  append_run_log.py append (--record run-record.json | --entry entry.json) (--repo OWNER/NAME | --jsonl F)
  append_run_log.py export (--repo OWNER/NAME [--since YYYY-MM] | --comments-file F) --out log.jsonl
`gh` must be on PATH with GH_TOKEN set for --repo.
"""
import argparse
import datetime
import json
import os
import re
import subprocess

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match

from common import HarnessError, load_json, run_main
from redact_check import scan

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schemas", "run-log-entry.schema.json")
LOG_VERSION = 1
LOG_LABEL = "staff:log"
LOG_TITLE = "Staff outcome store {month}"
LOG_TITLE_RE = re.compile(r"^Staff outcome store [0-9]{4}-[0-9]{2}$")
WRITER = "github-actions[bot]"
MARKER = "<!-- staff-log:v1 -->"
BODY_RE = re.compile(re.escape(MARKER) + r"\n.*?\n```json\n(\{.*\})\n```\s*$", re.S)
ISSUE_BODY = (
    "Outcome store for staff run records and review verdicts (S-GEN-029, S-GEN-071). "
    "One comment per entry, written by the recorder job only. Comments by any other account "
    "are ignored. Do not comment here. See `docs/measurement.md` in the staff repo."
)

_validators = {}


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validator(kind):
    if not _validators:
        defs = load_json(SCHEMA_PATH, "log_invalid")["$defs"]
        for k in ("agent_run", "verdict_update"):
            _validators[k] = Draft202012Validator({"$ref": f"#/$defs/{k}", "$defs": defs})
    return _validators[kind]


def schema_error(entry):
    """None if the entry is valid, else a short message naming the JSON path (never the value)."""
    if not isinstance(entry, dict):
        return "entry is not a JSON object"
    kind = entry.get("record_kind")
    if kind not in ("agent_run", "verdict_update"):
        return "record_kind is not agent_run or verdict_update"
    err = best_match(_validator(kind).iter_errors(entry))
    if err is None:
        return None
    return f"/{'/'.join(str(p) for p in err.absolute_path)} fails '{err.validator}'"


def check(entry):
    """Fail closed unless the entry matches the schema and passes redaction (S-SEC-004)."""
    err = schema_error(entry)
    if err:
        raise HarnessError("log_invalid", err)
    hits = scan(entry)
    if hits:
        paths = ", ".join(f"{p} ({n})" for p, n in hits)
        raise HarnessError("redaction_hit", f"entry dropped, not stored (S-SEC-004): {paths}")
    return entry


def entry_from_record(record, logged_at=None):
    """A run record (run_record.py) as a log entry: the same fields plus log_version and logged_at."""
    if not isinstance(record, dict):
        raise HarnessError("log_invalid", "run record is not a JSON object")
    return {"log_version": LOG_VERSION, "logged_at": logged_at or now(), **record}


def render_body(entry):
    """The comment body for one entry. The JSON is compact and on one line."""
    head = f"`{entry['record_kind']}` `{entry.get('run_id') or 'unmatched'}`"
    return f"{MARKER}\n{head}\n```json\n{json.dumps(entry, ensure_ascii=True, sort_keys=True)}\n```\n"


def parse_body(body):
    """The entry in a log comment body, or None if the body is not a log entry."""
    m = BODY_RE.match((body or "").replace("\r\n", "\n"))
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


# --- gh transport -------------------------------------------------------------

def gh(args, timeout=120):
    """Run `gh api` and return stdout. Fails closed with log_store_failed."""
    try:
        return subprocess.run(["gh", "api", *args], check=True, capture_output=True, text=True,
                              timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        raise HarnessError("log_store_failed", f"gh api {args[0] if args else ''} failed") from None


def _json_lines(text):
    try:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    except ValueError:
        raise HarnessError("log_store_failed", "gh api returned invalid JSON") from None


def log_issues(repo, run=gh):
    """The store's issues, oldest first: labelled staff:log, opened by the recorder, with the store title."""
    out = run(["--paginate", "--jq", ".[]", f"repos/{repo}/issues?labels={LOG_LABEL}&state=all&per_page=100"])
    issues = [i for i in _json_lines(out)
              if "pull_request" not in i and (i.get("user") or {}).get("login") == WRITER
              and LOG_TITLE_RE.match(i.get("title") or "")]
    return sorted(issues, key=lambda i: i["number"])


def month_issue(repo, month, run=gh):
    """The issue number for `month` (YYYY-MM), created if missing. Two racing creates leave two
    issues with the same title; both are read on export, so nothing is lost."""
    title = LOG_TITLE.format(month=month)
    for issue in log_issues(repo, run):
        if issue["title"] == title:
            return issue["number"]
    created = json.loads(run(["-X", "POST", f"repos/{repo}/issues", "-f", f"title={title}",
                              "-f", f"body={ISSUE_BODY}", "-f", f"labels[]={LOG_LABEL}"]))
    if LOG_LABEL not in [lbl.get("name") for lbl in created.get("labels", [])]:
        raise HarnessError("log_store_failed", f"new store issue lacks the {LOG_LABEL} label; create the label first")
    return created["number"]


def append_issue(repo, entry, run=gh, workdir=None):
    """Post one entry as a comment on this month's store issue. Returns the comment URL."""
    number = month_issue(repo, entry["logged_at"][:7], run)
    path = os.path.join(workdir or os.environ.get("RUNNER_TEMP") or ".", f"staff-log-{os.getpid()}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render_body(entry))
    try:
        url = run(["-X", "POST", f"repos/{repo}/issues/{number}/comments", "-F", f"body=@{path}",
                   "--jq", ".html_url"]).strip()
    finally:
        os.remove(path)
    return url


def append_jsonl(path, entry):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n")


def fetch_comments(repo, run=gh, since=None):
    """Comments of every store issue, or of those from month `since` (YYYY-MM) on."""
    comments = []
    for issue in log_issues(repo, run):
        if since and issue["title"][-7:] < since:
            continue
        out = run(["--paginate", "--jq", ".[]", f"repos/{repo}/issues/{issue['number']}/comments?per_page=100"])
        comments.extend(_json_lines(out))
    return comments


# --- reading ------------------------------------------------------------------

def entries_from_comments(comments, writer=WRITER):
    """(entries, counts). Keeps only valid entries posted by the recorder."""
    entries, counts = [], {"kept": 0, "other_author": 0, "not_entry": 0, "invalid": 0, "edited": 0}
    for c in comments:
        if (c.get("user") or {}).get("login") != writer:
            counts["other_author"] += 1
            continue
        entry = parse_body(c.get("body"))
        if entry is None:
            counts["not_entry"] += 1
            continue
        if schema_error(entry):
            counts["invalid"] += 1
            continue
        if c.get("updated_at") and c.get("created_at") and c["updated_at"] != c["created_at"]:
            counts["edited"] += 1  # kept, but reported: only the human can edit a recorder comment
        entries.append(entry)
        counts["kept"] += 1
    return entries, counts


def read_jsonl(path):
    """Entries from a JSONL file. A bad line fails closed with its line number."""
    entries = []
    try:
        with open(path, encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    raise HarnessError("log_invalid", f"{path}:{n} is not JSON") from None
                err = schema_error(entry)
                if err:
                    raise HarnessError("log_invalid", f"{path}:{n} {err}")
                entries.append(entry)
    except OSError:
        raise HarnessError("log_invalid", f"cannot read {path}") from None
    return entries


def dedupe(entries):
    """One entry per run (the latest logged) and per review source; a re-run job may post twice."""
    out = {}
    for e in sorted(entries, key=lambda e: e["logged_at"]):
        if e["record_kind"] == "agent_run":
            key = ("run", e["run_id"])
        else:
            key = ("review", (e["source"].get("ref") or f"{e['run_id']}|{e['verdict_by']}|{e['verdict_at']}"))
        out[key] = e
    return list(out.values())


def load_logs(paths):
    return dedupe([e for p in paths for e in read_jsonl(p)])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("append")
    src = a.add_mutually_exclusive_group(required=True)
    src.add_argument("--record", help="a run record from run_record.py")
    src.add_argument("--entry", help="a ready entry, e.g. from log_review.py")
    dst = a.add_mutually_exclusive_group(required=True)
    dst.add_argument("--repo", help="OWNER/NAME of the product repo holding the store issues")
    dst.add_argument("--jsonl", help="append to this local JSONL file instead")
    x = sub.add_parser("export")
    xs = x.add_mutually_exclusive_group(required=True)
    xs.add_argument("--repo")
    xs.add_argument("--comments-file", help="a JSON array of issue comments, instead of gh api")
    x.add_argument("--since", help="with --repo: read only store issues from this month on, YYYY-MM")
    x.add_argument("--writer", default=WRITER, help="the only login whose entries are trusted")
    x.add_argument("--out", required=True)
    args = ap.parse_args()

    if args.cmd == "append":
        if args.record:
            entry = entry_from_record(load_json(args.record, "log_invalid"))
        else:
            entry = load_json(args.entry, "log_invalid")
        check(entry)
        if args.repo:
            print(f"outcome store: {entry['record_kind']} {entry.get('run_id')} -> {append_issue(args.repo, entry)}")
        else:
            append_jsonl(args.jsonl, entry)
            print(f"outcome store: {entry['record_kind']} {entry.get('run_id')} -> {args.jsonl}")
    else:
        comments = load_json(args.comments_file, "log_invalid") if args.comments_file else fetch_comments(args.repo, since=args.since)
        entries, counts = entries_from_comments(comments, args.writer)
        entries = dedupe(entries)
        with open(args.out, "w", encoding="utf-8") as fh:
            for e in sorted(entries, key=lambda e: e["logged_at"]):
                fh.write(json.dumps(e, ensure_ascii=True, sort_keys=True) + "\n")
        print("export: " + ", ".join(f"{k} {v}" for k, v in counts.items()) + f"; {len(entries)} after dedupe")
        if counts["edited"]:
            print(f"::warning::{counts['edited']} store comment(s) were edited after posting")


if __name__ == "__main__":
    run_main(main)
