"""Developer PR rounds (S-DEV-006): gate a review or check round on the agent's own PR, and bundle its context.

The Developer also runs when an operator requests changes on its PR, or when a required CI job fails on
its own push to the PR (at most --max-check-rounds check rounds per PR). Inputs are raw GitHub REST JSON
as `gh api` returns it; a list may also be `--paginate --slurp` output (an array of pages).

  gate    decides whether the round runs. Writes {allowed, reason, issue, pr, head_sha, trigger, check_round,
          review_id, failed_jobs} and exits 0 either way: a denial is data, not a failure.
  bundle  adds the PR's operator reviews, inline comments, conversation and failed-job log tails to the input
          file as `untrusted.pr_context` (S-SEC-001), and on a review or check round the PR head's files as
          `untrusted.previous_draft`. Records the round's facts in the trusted `developer.round`.

Review and comment text is kept only from operators (governance/operators.yml); everything else is counted
in `dropped`. The input is redaction-checked again after this step.
"""
import argparse
import os
import re

from common import HarnessError, load_json, run_main, write_json
from contract import load_operators
from previous_draft import MAX_BYTES

CHECK_MARKER = "[staff:check-round]"  # the workflow puts it in a check round's commit message
BRANCH_RE = re.compile(r"^agent/developer/([1-9][0-9]{0,8})$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_JOBS = "unit,integration"
FAILED = ("failure", "timed_out")
MAX_BODY = 4_000  # chars per review, comment or inline comment body
MAX_LOG = 6_000  # bytes per failed-job log tail, keeping the end
TRIGGERS = ("review", "check", "ticket")


# --- inputs -----------------------------------------------------------------

def pages(value, what):
    """A flat list from a REST list or an array of pages (`gh api --paginate --slurp`)."""
    if not isinstance(value, list):
        raise HarnessError("input_invalid", f"{what} is not a JSON array")
    if value and all(isinstance(v, list) for v in value):
        value = [item for page in value for item in page]
    if not all(isinstance(v, dict) for v in value):
        raise HarnessError("input_invalid", f"{what} has an item that is not an object")
    return value


def job_list(value):
    """The jobs of a `runs/ID/jobs` response, or of an array of such pages."""
    objs = value if isinstance(value, list) else [value]
    jobs = []
    for obj in objs:
        if not isinstance(obj, dict) or not isinstance(obj.get("jobs"), list):
            raise HarnessError("input_invalid", "jobs is not a {jobs: [...]} object or an array of them")
        jobs += obj["jobs"]
    return pages(jobs, "jobs")


def dig(obj, *keys):
    for k in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj


def pr_number(pr):
    if not isinstance(pr, dict) or not isinstance(pr.get("number"), int):
        raise HarnessError("input_invalid", "the PR JSON has no number")
    return pr["number"]


def is_operator(item, operators):
    user = item.get("user") or {}
    return user.get("type") == "User" and str(user.get("login", "")).lower() in operators


# --- gate -------------------------------------------------------------------

def _latest_operator_review(reviews, operators):
    mine = [r for r in reviews if is_operator(r, operators) and r.get("state") != "PENDING"]
    return max(mine, key=lambda r: (str(r.get("submitted_at") or ""), r.get("id") or 0), default=None)


def _gate_review(out, reviews, operators, head):
    review = _latest_operator_review(reviews, operators)
    if review is None or review.get("state") != "CHANGES_REQUESTED":
        return "no operator review requesting changes"
    out["review_id"] = review.get("id")
    if review.get("commit_id") != head:
        return "review is not on the current head"
    return None


def _gate_check(out, run, jobs, commits, args, head):
    if not isinstance(run, dict):
        raise HarnessError("input_invalid", "the run JSON is not an object")
    if run.get("head_sha") != head:
        return "stale run"
    if dig(run, "head_repository", "full_name") != args.repo:
        return "fork"
    if run.get("conclusion") != "failure" or run.get("event") != "pull_request":
        return "not a failed pull_request run"
    required = {j.strip() for j in args.required_jobs.split(",") if j.strip()}
    out["failed_jobs"] = sorted({str(j.get("name")) for j in jobs
                                 if j.get("conclusion") in FAILED and j.get("name") in required})
    if not out["failed_jobs"]:
        return "no required job failed"
    last = commits[-1] if commits else {}
    if last.get("sha") != head:
        return "stale run"
    if dig(last, "author", "login") != args.bot_login:
        return "the head commit is not the Developer's"
    out["check_round"] = 1 + sum(CHECK_MARKER in str(dig(c, "commit", "message") or "") for c in commits)
    if out["check_round"] > args.max_check_rounds:
        return "check round limit reached"
    return None


def gate(args, pr, commits, operators, reviews=None, run=None, jobs=None):
    """The gate record. Denies on the first failing rule (S-DEV-006)."""
    out = {"allowed": False, "reason": "", "issue": None, "pr": pr_number(pr), "head_sha": None,
           "trigger": args.kind, "check_round": 0, "review_id": None, "failed_jobs": []}

    def deny():
        if pr.get("state") != "open":
            return "PR is not open"
        if dig(pr, "head", "repo", "full_name") != args.repo or dig(pr, "base", "repo", "full_name") != args.repo:
            return "fork"  # a fork's head is never worked (S-SEC-002)
        m = BRANCH_RE.match(str(dig(pr, "head", "ref") or ""))
        if not m:
            return "not a Developer branch"
        out["issue"] = int(m.group(1))
        head = dig(pr, "head", "sha")
        if not isinstance(head, str) or not SHA_RE.match(head):
            return "bad head sha"
        out["head_sha"] = head
        if args.kind == "review":
            return _gate_review(out, reviews or [], operators, head)
        return _gate_check(out, run, jobs or [], commits, args, head)

    reason = deny()
    out["allowed"] = reason is None
    out["reason"] = reason or "ok"
    return out


# --- bundle -----------------------------------------------------------------

def cap(text, limit=MAX_BODY):
    text = text if isinstance(text, str) else ""
    return text if len(text) <= limit else text[:limit] + "…"


def is_command(body):
    """A run command or sign-off, not review content."""
    body = (body or "").strip()
    return body == "/developer" or body.split("\n", 1)[0].startswith("/signoff")


def pr_context(pr, reviews, review_comments, comments, failed_checks, operators, trigger, check_round):
    number, head = pr_number(pr), dig(pr, "head", "sha")
    ref = f"{dig(pr, 'base', 'repo', 'full_name')}#{number}"
    dropped = 0
    has_inline = {c.get("pull_request_review_id") for c in review_comments}

    kept_reviews = []
    for r in reviews:
        if not is_operator(r, operators):
            dropped += 1
            continue
        if r.get("state") == "PENDING" or (not (r.get("body") or "").strip() and r.get("id") not in has_inline):
            continue
        kept_reviews.append({"ref": f"{ref} review {r.get('id')}", "state": r.get("state"), "body": cap(r.get("body")),
                             "submitted_at": r.get("submitted_at"), "on_head": r.get("commit_id") == head})

    kept_inline = []
    for c in review_comments:
        if not is_operator(c, operators):
            dropped += 1
            continue
        line = c.get("line") if c.get("line") is not None else c.get("original_line")
        kept_inline.append({"ref": f"{ref} review comment {c.get('id')}", "review_id": c.get("pull_request_review_id"),
                            "path": c.get("path"), "line": line, "side": c.get("side"), "body": cap(c.get("body")),
                            "created_at": c.get("created_at"), "outdated": c.get("position") is None})

    kept_comments = []
    for c in comments:
        if not is_operator(c, operators):
            dropped += 1  # includes the bot's own notes, which are on the ticket already
            continue
        if is_command(c.get("body")):
            continue
        kept_comments.append({"ref": f"{ref} comment {c.get('id')}", "body": cap(c.get("body")),
                              "created_at": c.get("created_at")})

    return {"number": number, "url": pr.get("html_url"), "head_sha": head, "trigger": trigger,
            "check_round": check_round, "reviews": kept_reviews, "review_comments": kept_inline,
            "comments": kept_comments, "failed_checks": failed_checks, "dropped": dropped}


def read_failed_logs(log_dir):
    """[{name, log_tail}] from <job>.log files, each capped to its last MAX_LOG bytes, sorted by name."""
    if not log_dir:
        return []
    try:
        names = sorted(n for n in os.listdir(log_dir) if n.endswith(".log"))
    except OSError:
        raise HarnessError("input_invalid", "cannot list the failed-logs directory") from None
    out = []
    for n in names:
        path = os.path.join(log_dir, n)
        if os.path.islink(path) or not os.path.isfile(path):
            continue
        with open(path, "rb") as fh:
            raw = fh.read()
        out.append({"name": n[:-len(".log")], "log_tail": raw[-MAX_LOG:].decode("utf-8", errors="ignore")})
    return out


def safe_path(head_dir, path):
    """The file under head_dir for a repo-relative path; refuses anything that could leave it."""
    root = os.path.realpath(head_dir)
    if not isinstance(path, str) or not path or "\0" in path or os.path.isabs(path) or path.startswith("\\") \
            or ".." in re.split(r"[\\/]", path):
        raise HarnessError("input_invalid", "a changed file path is absolute or has a .. segment")
    full = os.path.realpath(os.path.join(root, path))
    if not full.startswith(root + os.sep):
        raise HarnessError("input_invalid", "a changed file path resolves outside the head directory")
    return full


def read_text(full):
    """The file's text, or None when it is missing, not a regular file, or not UTF-8 (binary)."""
    try:
        with open(full, "rb") as fh:
            return fh.read().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def head_draft(pr, files, head_dir):
    """The PR head's changed files, in previous_draft's shape and op vocabulary (developer-output schema)."""
    entries = []  # (path, op, full path or None)
    for f in files:
        status, path = f.get("status"), f.get("filename")
        if status == "removed":
            safe_path(head_dir, path)
            entries.append((path, "delete", None))
            continue
        if status == "renamed":
            safe_path(head_dir, f.get("previous_filename"))
            entries.append((f["previous_filename"], "delete", None))
        op = "add" if status in ("added", "renamed", "copied") else "modify"
        entries.append((path, op, safe_path(head_dir, path)))
    out, size, truncated = [], 0, False
    for path, op, full in entries:
        text = read_text(full) if full else None
        if text is not None:
            size += len(text.encode("utf-8"))
            if size > MAX_BYTES:
                truncated, text = True, None
        out.append({"path": path, "op": op, "content": text})
    return {"run_id": None, "source": "pr_head", "pr": pr_number(pr), "head_sha": dig(pr, "head", "sha"),
            "truncated": truncated, "files": out}


def bundle(data, args, operators, pr, reviews, review_comments, comments, files):
    if not isinstance(data.get("untrusted"), dict):
        raise HarnessError("input_invalid", "the input has no untrusted section")
    if not isinstance(data.get("developer"), dict):
        raise HarnessError("input_invalid", "the input has no developer section (run dev_bundle.py first)")
    if not SHA_RE.match(str(dig(pr, "head", "sha") or "")):
        raise HarnessError("input_invalid", "the PR head sha is not 40 hex")
    number = pr_number(pr)
    data["untrusted"]["pr_context"] = pr_context(pr, reviews, review_comments, comments,
                                                 read_failed_logs(args.failed_logs), operators, args.trigger,
                                                 args.check_round)
    if args.trigger != "ticket":  # a ticket round keeps its artifact-based draft (previous_draft.py)
        data["untrusted"]["previous_draft"] = head_draft(pr, files, args.head_dir)
    # Harness-written facts, trusted like the rest of `developer` (dev_bundle.py).
    data["developer"]["round"] = {"trigger": args.trigger, "pr": number, "check_round": args.check_round}
    return data


# --- CLI --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate")
    g.add_argument("--kind", choices=("review", "check"), required=True)
    g.add_argument("--pr", required=True, help="GET repos/R/pulls/N")
    g.add_argument("--commits", required=True, help="GET repos/R/pulls/N/commits")
    g.add_argument("--operators", required=True, help="staff governance/operators.yml")
    g.add_argument("--bot-login", required=True, help="the Developer App's bot login")
    g.add_argument("--repo", required=True, help="OWNER/NAME of the product repo")
    g.add_argument("--reviews", help="GET repos/R/pulls/N/reviews (review rounds)")
    g.add_argument("--run", help="GET repos/R/actions/runs/ID (check rounds)")
    g.add_argument("--jobs", help="GET repos/R/actions/runs/ID/jobs (check rounds)")
    g.add_argument("--required-jobs", default=REQUIRED_JOBS)
    g.add_argument("--max-check-rounds", type=int, default=3)
    g.add_argument("--out", required=True)
    b = sub.add_parser("bundle")
    b.add_argument("--input", required=True, help="the build_input.py + dev_bundle.py output; rewritten in place")
    b.add_argument("--trigger", choices=TRIGGERS, required=True)
    b.add_argument("--pr", required=True)
    b.add_argument("--reviews", required=True)
    b.add_argument("--review-comments", required=True, help="GET repos/R/pulls/N/comments")
    b.add_argument("--comments", required=True, help="GET repos/R/issues/N/comments")
    b.add_argument("--files", required=True, help="GET repos/R/pulls/N/files")
    b.add_argument("--head-dir", required=True, help="the PR head's changed files, as data")
    b.add_argument("--failed-logs", help="a directory of <job name>.log tails")
    b.add_argument("--check-round", type=int, default=0)
    b.add_argument("--operators", required=True)
    b.add_argument("--bot-login", required=True)
    args = ap.parse_args()
    operators = load_operators(args.operators)
    pr = load_json(args.pr, "input_invalid")
    pr_number(pr)

    if args.cmd == "gate":
        if args.kind == "review" and not args.reviews:
            raise HarnessError("input_invalid", "a review gate needs --reviews")
        if args.kind == "check" and not (args.run and args.jobs):
            raise HarnessError("input_invalid", "a check gate needs --run and --jobs")
        commits = pages(load_json(args.commits, "input_invalid"), "commits")
        reviews = pages(load_json(args.reviews, "input_invalid"), "reviews") if args.reviews else None
        run = load_json(args.run, "input_invalid") if args.run else None
        jobs = job_list(load_json(args.jobs, "input_invalid")) if args.jobs else None
        out = gate(args, pr, commits, operators, reviews, run, jobs)
        write_json(args.out, out)
        print(f"gate: allowed={str(out['allowed']).lower()} reason={out['reason']}")
        return

    data = load_json(args.input, "input_invalid")
    if not isinstance(data, dict):
        raise HarnessError("input_invalid", "the input is not a JSON object")
    lists = [pages(load_json(p, "input_invalid"), what) for p, what in
             ((args.reviews, "reviews"), (args.review_comments, "review comments"), (args.comments, "comments"),
              (args.files, "files"))]
    bundle(data, args, operators, pr, *lists)
    write_json(args.input, data)
    ctx = data["untrusted"]["pr_context"]
    draft = data["untrusted"].get("previous_draft") if args.trigger != "ticket" else None
    print(f"pr_context: pr={ctx['number']} trigger={args.trigger} reviews={len(ctx['reviews'])} "
          f"review_comments={len(ctx['review_comments'])} comments={len(ctx['comments'])} "
          f"failed_checks={len(ctx['failed_checks'])} dropped={ctx['dropped']} "
          f"draft_files={len(draft['files']) if draft else 'unchanged'}")


if __name__ == "__main__":
    run_main(main)
