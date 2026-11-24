"""Give a redraft or fix-up run its own previous draft, so it starts from those files.

The agent's latest draft comment on the ticket names its patch artifact (`developer-patch-<run>-<attempt>` or
`qa-patch-<run>-<attempt>`). The workflow downloads that run's validated output, and `attach` adds the draft's
files to the input file as `untrusted.previous_draft`: model output from an earlier run is untrusted data
like the rest of the input (S-SEC-001), and the input is redaction-checked again after this step.

  find    prints `<run>-<attempt>` for the latest draft comment of the agent's own App, or nothing.
  attach  adds {run_id, truncated, files: [{path, op, content}]} from that run's validated.json.
"""
import argparse
import re

from common import HarnessError, load_json, run_main, write_json

PATCH_RE = {"developer": re.compile(r"\bdeveloper-patch-(\d{1,20}-\d{1,4})\b"),
            "qa": re.compile(r"\bqa-patch-(\d{1,20}-\d{1,4})\b")}
APP_KINDS = {"developer": "developer_app", "qa": "qa_app"}
MAX_BYTES = 300_000  # a previous draft larger than this is attached as paths only


def find(data, prefix):
    """The run id of the latest draft comment written by the agent's own App, or None."""
    kind = APP_KINDS[prefix]
    comments = ((data.get("untrusted") or {}).get("comments")) or []
    for c in reversed(comments):
        if c.get("author_kind") != kind:
            continue
        m = PATCH_RE[prefix].search(c.get("body") or "")
        if m:
            return m.group(1)
    return None


def attach(data, validated, run_id):
    files, size, truncated = [], 0, False
    for f in validated.get("proposed_files") or []:
        if not isinstance(f, dict) or not isinstance(f.get("path"), str):
            continue
        content = f.get("content")
        text = "".join(content) if isinstance(content, list) else (content if isinstance(content, str) else "")
        size += len(text.encode("utf-8"))
        if size > MAX_BYTES:
            truncated = True
            text = None
        files.append({"path": f["path"], "op": f.get("op"), "content": text})
    if not isinstance(data.get("untrusted"), dict):
        raise HarnessError("input_invalid", "the input has no untrusted section")
    data["untrusted"]["previous_draft"] = {"run_id": run_id, "truncated": truncated, "files": files}
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find")
    f.add_argument("--input", required=True)
    f.add_argument("--prefix", choices=sorted(PATCH_RE), required=True)
    a = sub.add_parser("attach")
    a.add_argument("--input", required=True)
    a.add_argument("--validated", required=True)
    a.add_argument("--run-id", required=True)
    args = ap.parse_args()
    data = load_json(args.input, "input_invalid")
    if args.cmd == "find":
        run = find(data, args.prefix)
        if run:
            print(run)
        return
    if not re.fullmatch(r"\d{1,20}-\d{1,4}", args.run_id):
        raise HarnessError("input_invalid", "bad run id")
    write_json(args.input, attach(data, load_json(args.validated, "artifact_missing"), args.run_id))
    n = len(data["untrusted"]["previous_draft"]["files"])
    print(f"attached the previous draft {args.run_id}: {n} files")


if __name__ == "__main__":
    run_main(main)
