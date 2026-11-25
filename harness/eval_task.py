"""Developer eval tasks (S-DEV-036): load one, build the tree the agent sees, and its ticket.

The eval runner keeps tasks in staff-evals-private. A task is one JSON file (evals/schemas/
developer-task.schema.json): a pinned product commit, a ticket, and three file layers.

  overlay    written onto the product before the agent runs (requirements, architecture, a seeded bug)
  reference  the reference implementation or correction; the validity check and scoring only
  heldout    API tests put in tests/api/heldout/ at scoring time only

Subcommands:

  check        Validate a task file (schema and kind rules). Prints nothing from the task.
  materialize  Export the product commit (tracked files only, no history), write the chosen layers, and
               commit the result as a fresh one-commit repo, so nothing in git hints at the task
               (S-GEN-040).
  event        Write the synthetic `issues: labeled` event and an empty comment list for build_input.py.
  sandbox      Join the code map's build, unit and integration commands and the API layer's test command into the
               file eval_score.py runs (every command from the product's own .staff files, never the task).

Nothing here prints task content: run logs of the private repo may be read by people who must stay blind.
"""
import argparse
import json
import os
import shutil
import subprocess
import tarfile
import tempfile

import yaml
from jsonschema import Draft202012Validator

from code_map import FORBIDDEN, FORBIDDEN_FILES
from common import HarnessError, load_json, run_main, write_json

HELDOUT_DIR = "tests/api/heldout"
LAYERS = ("overlay", "reference", "heldout")
# Fixed identity and date for the one commit, so the tree's history is the same for every task.
GIT_ENV = {"GIT_AUTHOR_NAME": "eval", "GIT_AUTHOR_EMAIL": "eval@invalid", "GIT_COMMITTER_NAME": "eval",
           "GIT_COMMITTER_EMAIL": "eval@invalid", "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
           "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"}


def load_task(path, schema_path):
    """The validated task, or HarnessError(input_invalid) naming only the failing location."""
    task = load_json(path, "input_invalid")
    schema = load_json(schema_path, "input_invalid")
    errors = sorted(Draft202012Validator(schema).iter_errors(task), key=lambda e: list(e.absolute_path))
    if errors:
        where = "/" + "/".join(str(p) for p in errors[0].absolute_path)
        raise HarnessError("input_invalid", f"task {where} does not match the task schema")
    kind = task["kind"]
    want_label = "dev:fix" if kind == "fix" else "dev:implement"
    if task["ticket"]["label"] != want_label:
        raise HarnessError("input_invalid", f"a {kind} task needs the {want_label} label")
    has = {layer: bool(task[layer]) for layer in LAYERS}
    rules = {
        "feature": has["reference"] and has["heldout"] and not task.get("trap"),
        "fix": has["overlay"] and has["reference"] and has["heldout"] and not task.get("trap"),
        "trap": has["overlay"] and not has["reference"] and not has["heldout"] and bool(task.get("trap")),
    }
    if not rules[kind]:
        raise HarnessError("input_invalid", f"the layers do not fit a {kind} task")
    for trap in task.get("trap") or []:
        if bool(trap.get("kinds")) == bool(trap.get("needs")):
            raise HarnessError("input_invalid", "a trap has exactly one of kinds or needs")
    for layer in ("overlay", "reference"):
        for f in task[layer]:
            p = f["path"]
            if p.startswith((".git/", ".github/", ".staff/", HELDOUT_DIR + "/")) or p in FORBIDDEN_FILES:
                raise HarnessError("input_invalid", f"a {layer} path is outside what a task may change")
    for f in task["reference"]:
        if f["path"].startswith(FORBIDDEN):
            raise HarnessError("input_invalid", "a reference path is outside the Developer's scope")
    return task


def write_layer(root, files):
    for f in files:
        target = os.path.realpath(os.path.join(root, f["path"]))
        if not target.startswith(os.path.realpath(root) + os.sep):
            raise HarnessError("path_out_of_scope", "a task path resolves outside the tree")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="") as fh:
            fh.write(f["content"])


def write_heldout(root, task):
    d = os.path.join(root, HELDOUT_DIR)
    os.makedirs(d, exist_ok=True)
    for f in task["heldout"]:
        with open(os.path.join(d, f["name"]), "w", encoding="utf-8", newline="") as fh:
            fh.write(f["content"])


def export_commit(product, sha, out):
    """Tracked files of `sha` only: no .git, no untracked or ignored files."""
    head = subprocess.run(["git", "-C", product, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != sha:
        raise HarnessError("input_invalid", "the product checkout is not at the task's base commit")
    with tempfile.TemporaryDirectory() as tmp:
        tar_path = os.path.join(tmp, "tree.tar")
        subprocess.run(["git", "-C", product, "archive", "--format=tar", "-o", tar_path, sha], check=True)
        with tarfile.open(tar_path) as tar:
            tar.extractall(out, filter="data")


def fresh_repo(root):
    env = dict(os.environ, **GIT_ENV)
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "Initial commit"]):
        subprocess.run(["git", "-C", root, *args], check=True, env=env, capture_output=True)


def cmd_check(args):
    task = load_task(args.task, args.schema)
    print(f"task ok: {task['id']}")


def cmd_materialize(args):
    task = load_task(args.task, args.schema)
    layers = [x for x in args.layers.split(",") if x]
    if layers[:1] != ["overlay"] or any(x not in LAYERS for x in layers):
        raise HarnessError("input_invalid", "layers start with overlay and name only overlay, reference, heldout")
    if os.path.exists(args.out):
        shutil.rmtree(args.out)
    os.makedirs(args.out)
    export_commit(args.product, task["base_sha"], args.out)
    for layer in layers:
        if layer == "heldout":
            write_heldout(args.out, task)
        else:
            write_layer(args.out, task[layer])
    fresh_repo(args.out)
    print(f"materialized {task['id']} with {'+'.join(layers)}")


def cmd_event(args):
    task = load_task(args.task, args.schema)
    t = task["ticket"]
    issue = {"number": 1, "title": t["title"], "body": t["body"], "state": "open",
             "html_url": f"https://github.com/{args.repo}/issues/1",
             "user": {"login": args.operator, "type": "User"}, "labels": [{"name": t["label"]}]}
    write_json(args.out_event, {"action": "labeled", "issue": issue, "label": {"name": t["label"]},
                                "repository": {"full_name": args.repo}, "sender": {"login": args.operator, "type": "User"}})
    write_json(args.out_comments, [])
    print("event written")


def cmd_sandbox(args):
    def read(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return yaml.safe_load(fh) or {}
        except (OSError, yaml.YAMLError):
            raise HarnessError("input_invalid", f"cannot read {os.path.basename(path)}") from None
    code = ((read(args.code_yml).get("areas") or {}).get(args.area) or {}).get("sandbox")
    api = (((read(args.tests_yml).get("areas") or {}).get(args.area) or {}).get(args.layer) or {}).get("sandbox")
    if not code or not api:
        raise HarnessError("input_invalid", "the code map or the test map has no sandbox block for the area")
    out = {"version": 1, "setup": code["setup"], "build": code["build"],
           "unit": {"test": code["unit_test"], "report": code["unit_report"]},
           "api": {"test": api["test"], "report": api["report"]},
           "heldout_dir": HELDOUT_DIR}
    if code.get("integration_test"):
        out["integration"] = {"test": code["integration_test"], "report": code["integration_report"]}
    write_json(args.out, out)
    print("sandbox written")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    default_schema = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "evals", "schemas", "developer-task.schema.json")
    c = sub.add_parser("check")
    m = sub.add_parser("materialize")
    e = sub.add_parser("event")
    for p in (c, m, e):
        p.add_argument("--task", required=True)
        p.add_argument("--schema", default=default_schema)
    m.add_argument("--product", required=True, help="product checkout at the task's base_sha")
    m.add_argument("--layers", required=True, help="overlay[,reference][,heldout]")
    m.add_argument("--out", required=True)
    e.add_argument("--operator", required=True, help="an operator login: the synthetic ticket's author")
    e.add_argument("--repo", required=True)
    e.add_argument("--out-event", required=True)
    e.add_argument("--out-comments", required=True)
    s = sub.add_parser("sandbox")
    s.add_argument("--code-yml", required=True)
    s.add_argument("--tests-yml", required=True)
    s.add_argument("--area", default="system")
    s.add_argument("--layer", default="api")
    s.add_argument("--out", required=True)
    args = ap.parse_args()
    {"check": cmd_check, "materialize": cmd_materialize, "event": cmd_event, "sandbox": cmd_sandbox}[args.cmd](args)


if __name__ == "__main__":
    run_main(main)
