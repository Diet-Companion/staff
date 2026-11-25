"""Turn the human's review log into verdict_update entries (S-GEN-032, S-GEN-071).

The human logs each review with one comment on the issue or PR they reviewed:

  /review <time> [<verdict>] [run=<run_id>] [<ITEM-ID>=<verdict> ...]

  <time>     12m, 12, 1h or 1h30m (1 to 480 minutes)
  <verdict>  accepted (taken without changing structured fields: confirmed, S-BA-042),
             edited (taken after changes) or rejected (not taken). Optional, e.g. for
             time spent answering a question batch.
  run=       the reviewed run, from the comment footer's Staff-Run-Id. Default: the latest
             completed run on this issue before the comment.
  ITEM=      a verdict per drafted item (S-BA-042), e.g. REQ-002=edited. With items only,
             the run verdict is derived: all accepted, all rejected, else edited.

Only the first line is read. Anything after it is a note for humans and is never
stored. Only operator accounts count (governance/operators.yml, G12). A line
that starts with /review but doesn't parse fails closed (review_invalid), so a
typo is visible instead of silently lost.

CLI:
  log_review.py comment --event EVENT --operators F [--log log.jsonl] --out entry.json
  log_review.py manual RUN_ID MINUTES [VERDICT] --by LOGIN [--item ID=VERDICT] [--at TS] [--log F] --out entry.json
Append the entry with append_run_log.py append --entry entry.json.
"""
import argparse
import datetime
import re

from append_run_log import LOG_VERSION, check, now, read_jsonl
from common import HarnessError, load_json, run_main, write_json
from contract import load_operators

COMMAND = "/review"
MAX_MINUTES = 480
VERDICTS = {"accepted": "accepted", "accept": "accepted", "edited": "edited", "edit": "edited",
            "rejected": "rejected", "reject": "rejected"}
TIME_RE = re.compile(r"^(?:(\d{1,2})h)?(?:(\d{1,3})(?:m|min)?)?$")
ITEM_RE = re.compile(r"^([A-Z]{1,6}-[0-9]{3,}(?:/[A-Z]{1,6}-[0-9]{3,}){0,2})[=:]([A-Za-z]+)$")
RUN_RE = re.compile(r"^run=([A-Za-z0-9][A-Za-z0-9._-]{0,63})$")


def is_command(body):
    first = (body or "").lstrip().split("\n", 1)[0].strip()
    return first == COMMAND or first.startswith(COMMAND + " ")


def parse_minutes(token):
    m = TIME_RE.match(token.lower())
    if not token or not m or (m.group(1) is None and m.group(2) is None):
        raise HarnessError("review_invalid", "the first word after /review must be a time, e.g. 12m or 1h30m")
    minutes = int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
    if not 1 <= minutes <= MAX_MINUTES:
        raise HarnessError("review_invalid", f"review time must be 1 to {MAX_MINUTES} minutes")
    return minutes


def verdict_word(word):
    if word.lower() not in VERDICTS:
        raise HarnessError("review_invalid", "verdicts are accepted, edited or rejected")
    return VERDICTS[word.lower()]


def derive(items):
    values = set(items.values())
    if values == {"accepted"}:
        return "accepted"
    if values == {"rejected"}:
        return "rejected"
    return "edited"


def parse_command(body):
    """{'minutes', 'verdict', 'run_id', 'items'} from a /review comment, or None if it is not one."""
    if not is_command(body):
        return None
    tokens = body.lstrip().split("\n", 1)[0].split()[1:]
    if not tokens:
        raise HarnessError("review_invalid", "usage: /review <time> [accepted|edited|rejected] [run=<id>]")
    out = {"minutes": parse_minutes(tokens[0]), "verdict": None, "run_id": None, "items": {}}
    for tok in tokens[1:]:
        if RUN_RE.match(tok):
            if out["run_id"]:
                raise HarnessError("review_invalid", "run= given twice")
            out["run_id"] = RUN_RE.match(tok).group(1)
        elif ITEM_RE.match(tok):
            item, word = ITEM_RE.match(tok).groups()
            if item in out["items"]:
                raise HarnessError("review_invalid", "an item verdict is given twice")
            out["items"][item] = verdict_word(word)
        elif tok.lower() in VERDICTS:
            if out["verdict"]:
                raise HarnessError("review_invalid", "more than one run verdict")
            out["verdict"] = VERDICTS[tok.lower()]
        else:
            raise HarnessError("review_invalid", "unknown word; see log_review.py for the syntax")
    if out["verdict"] is None and out["items"]:
        out["verdict"] = derive(out["items"])
    return out


def resolve_run(entries, target_ref, verdict_at):
    """The latest completed agent_run on target_ref created at or before verdict_at, else None."""
    runs = [e for e in entries if e["record_kind"] == "agent_run" and e["trigger"]["ref"] == target_ref
            and e["status"] == "completed" and e["created_at"] <= verdict_at]
    return max(runs, key=lambda e: e["created_at"])["run_id"] if runs else None


def build_entry(parsed, *, verdict_by, verdict_at, target_ref, source, entries):
    run_id = parsed["run_id"]
    if run_id is None and target_ref:
        run_id = resolve_run(entries, target_ref, verdict_at)
    if target_ref is None and run_id:
        target_ref = next((e["trigger"]["ref"] for e in entries
                           if e["record_kind"] == "agent_run" and e["run_id"] == run_id), None)
    return check({
        "log_version": LOG_VERSION,
        "logged_at": now(),
        "record_kind": "verdict_update",
        "run_id": run_id,
        "target_ref": target_ref,
        "human_verdict": parsed["verdict"],
        "items": parsed["items"],
        "review_minutes": parsed["minutes"],
        "verdict_by": verdict_by,
        "verdict_at": verdict_at,
        "source": source,
    })


def from_event(event, operators, entries):
    """The entry for an issue_comment event, or None if the comment is not a /review command."""
    comment = event.get("comment") or {}
    parsed = parse_command(comment.get("body"))
    if parsed is None:
        return None
    user = comment.get("user") or {}
    login = str(user.get("login", ""))
    if user.get("type") != "User" or login.lower() not in operators:
        raise HarnessError("not_operator", "only operator accounts log reviews (G12, S-GEN-071)")
    repo = (event.get("repository") or {}).get("full_name")
    number = (event.get("issue") or {}).get("number")
    if not repo or not isinstance(number, int):
        raise HarnessError("review_invalid", "event has no issue or repository")
    return build_entry(parsed, verdict_by=login, verdict_at=comment["created_at"], target_ref=f"{repo}#{number}",
                       source={"type": "comment", "ref": comment.get("html_url")}, entries=entries)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("comment", help="from an issue_comment event (the review workflow)")
    c.add_argument("--event", required=True, help="GITHUB_EVENT_PATH")
    c.add_argument("--operators", required=True, help="staff governance/operators.yml")
    m = sub.add_parser("manual", help="typed by the human, e.g. when the workflow was down")
    m.add_argument("run_id")
    m.add_argument("minutes")
    m.add_argument("verdict", nargs="?")
    m.add_argument("--by", required=True, help="the operator's GitHub login")
    m.add_argument("--operators", help="if given, --by must be listed in it")
    m.add_argument("--item", action="append", default=[], help="ITEM-ID=verdict, repeatable")
    m.add_argument("--at", help="review end time, UTC YYYY-MM-DDTHH:MM:SSZ (default: now)")
    for p in (c, m):
        p.add_argument("--log", action="append", default=[], help="outcome-store JSONL, to resolve the run")
        p.add_argument("--out", required=True)
    args = ap.parse_args()
    entries = [e for path in args.log for e in read_jsonl(path)]

    if args.cmd == "comment":
        entry = from_event(load_json(args.event, "review_invalid"), load_operators(args.operators), entries)
        if entry is None:
            print("not a /review command; nothing recorded")
            return
    else:
        if args.operators and args.by.lower() not in load_operators(args.operators):
            raise HarnessError("not_operator", "--by is not in governance/operators.yml")
        words = [args.minutes] + ([args.verdict] if args.verdict else []) + [f"run={args.run_id}"] + args.item
        parsed = parse_command(f"{COMMAND} {' '.join(words)}")
        at = args.at or now()
        try:
            datetime.datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            raise HarnessError("review_invalid", "--at must be YYYY-MM-DDTHH:MM:SSZ") from None
        entry = build_entry(parsed, verdict_by=args.by, verdict_at=at, target_ref=None,
                            source={"type": "cli", "ref": None}, entries=entries)
    write_json(args.out, entry)
    print(f"review: run {entry['run_id'] or 'unmatched'}, {entry['review_minutes']} min, "
          f"verdict {entry['human_verdict'] or 'none'}")


if __name__ == "__main__":
    run_main(main)
