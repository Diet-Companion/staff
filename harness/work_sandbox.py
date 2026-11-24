"""Developer work sandbox, stage 1 (S-DEV-042): apply the proposed change, then test it.

Runs in a job with no secrets and no write token. Two subcommands, run as separate
workflow steps so the patch is saved before any proposed code runs:

  apply  Writes `proposed_files` from the validated output onto a checkout of the base,
         runs the code map's `generators` whose inputs changed (S-DEV-043), and saves
         the full patch and a per-file summary. Changed lines count against the cap,
         generated outputs excepted (S-DEV-010).
  test   Runs the code map's `sandbox` commands on the base checkout and on the changed
         one: setup, build, then the unit tests with a JUnit report. A change passes when
         its build passes, no test that passes on the base fails on it (a failure is
         re-run once; passing then makes it flaky), and every test it adds passes.

Every command comes from `.staff/code.yml` on the base branch, never from the model.
The `test` step runs proposed code on the same runner, so its result is advisory:
the write stage validates it strictly and posts only counts and test IDs.
"""
import argparse
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET

from code_map import classify, matches
from common import HarnessError, load_json, run_main, write_json

MAX_LINES = 500           # S-DEV-010 starting value
CMD_TIMEOUT = 15 * 60     # seconds per command
MAX_REPORT_BYTES = 5_000_000
TEST_ID_MAX = 300
CLEAN_ENV_KEYS = ("PATH", "HOME", "LANG", "TMPDIR", "RUNNER_TEMP")


def code_map_entry(path):
    """The area's code-map entry, from dev-meta.json or a bundled input file."""
    data = load_json(path, "input_invalid")
    return (data.get("developer") or data).get("code_map_entry") or {}


def safe_target(repo, path):
    """repo/path, refusing anything that resolves outside repo or through a symlink."""
    root = os.path.realpath(repo)
    parts = path.split("/")
    cur = root
    for part in parts:
        cur = os.path.join(cur, part)
        if os.path.islink(cur):
            raise HarnessError("path_out_of_scope", "a proposed path goes through a symlink")
    full = os.path.realpath(os.path.join(root, path))
    if not full.startswith(root + os.sep):
        raise HarnessError("path_out_of_scope", "a proposed path resolves outside the repo")
    return full


def apply_files(repo, files):
    for f in files:
        target = safe_target(repo, f["path"])
        if f["op"] == "rename":
            src = safe_target(repo, f["from"])
            if os.path.isfile(src):
                os.remove(src)
        if f["op"] == "delete":
            if os.path.isfile(target):
                os.remove(target)
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="") as fh:
            fh.write("".join(f["content"]))


def sh(cmd, cwd, log, timeout=CMD_TIMEOUT):
    """Run one code-map command with a clean environment; True when it exits 0."""
    env = {k: os.environ[k] for k in CLEAN_ENV_KEYS if k in os.environ}
    env["CI"] = "true"
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(f"\n$ {cmd}\n")
        fh.flush()
        try:
            return subprocess.run(cmd, shell=True, cwd=cwd, env=env, stdout=fh, stderr=subprocess.STDOUT,
                                  timeout=timeout).returncode == 0
        except subprocess.TimeoutExpired:
            fh.write(f"timed out after {timeout}s\n")
            return False


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout


def changed_paths(repo):
    git(repo, "add", "-A")
    return [line for line in git(repo, "diff", "--cached", "--name-only").splitlines() if line]


def cmd_apply(args):
    out = load_json(args.validated, "artifact_missing")
    entry = code_map_entry(args.input)
    os.makedirs(args.out_dir, exist_ok=True)
    log = os.path.join(args.out_dir, "apply.log")
    apply_files(args.repo, out["proposed_files"])
    touched = changed_paths(args.repo)
    ran = []
    for gen in entry.get("generators") or []:
        if any(matches(p, gen["inputs"]) for p in touched):
            ok = sh(gen["command"], args.repo, log)
            ran.append({"generator_id": gen["generator_id"], "ok": ok})
    changed_paths(args.repo)
    patch = git(args.repo, "diff", "--cached", "--binary")
    with open(os.path.join(args.out_dir, "change.patch"), "w", encoding="utf-8") as fh:
        fh.write(patch)
    files, lines = [], 0
    for row in git(args.repo, "diff", "--cached", "--numstat").splitlines():
        added, removed, path = row.split("\t", 2)
        a = int(added) if added.isdigit() else 0
        r = int(removed) if removed.isdigit() else 0
        generated = "generated" in classify(path, entry)
        files.append({"path": path, "added": a, "removed": r, "generated": generated})
        lines += 0 if generated else a + r
    write_json(os.path.join(args.out_dir, "applied.json"), {
        "version": 1, "files": files, "lines_changed": lines, "max_lines": MAX_LINES,
        "over_cap": lines > MAX_LINES, "generators": ran,
    })
    print(f"applied: {len(files)} files, {lines} changed lines (cap {MAX_LINES}), {len(ran)} generators run")


def junit_results(path):
    """{test_id: passed} from a JUnit XML report, or None when it is missing or unreadable."""
    try:
        if os.path.getsize(path) > MAX_REPORT_BYTES:
            return None
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    results = {}
    for case in root.iter("testcase"):
        cls = case.get("classname") or case.get("file") or ""
        tid = f"{cls}::{case.get('name') or ''}"[:TEST_ID_MAX]
        failed = any(child.tag in ("failure", "error") for child in case)
        skipped = any(child.tag == "skipped" for child in case)
        if not skipped:
            results[tid] = not failed and results.get(tid, True)
    return results


def run_side(repo, sandbox, log):
    """(build_ok, results or None) for one checkout."""
    report = os.path.join(repo, sandbox["unit_report"])
    if os.path.exists(report):
        os.remove(report)
    for cmd in sandbox["setup"] + sandbox["build"]:
        if not sh(cmd, repo, log):
            return False, None
    sh(sandbox["unit_test"], repo, log)
    return True, junit_results(report)


def cmd_test(args):
    entry = code_map_entry(args.input)
    os.makedirs(args.out_dir, exist_ok=True)
    sandbox = entry.get("sandbox")
    if not sandbox:
        write_json(args.out, {"version": 1, "status": "untested", "reason": "no sandbox commands in .staff/code.yml"})
        print("untested: the code map has no sandbox commands")
        return
    base_build, base = run_side(args.base, sandbox, os.path.join(args.out_dir, "base.log"))
    head_log = os.path.join(args.out_dir, "head.log")
    head_build, head = run_side(args.head, sandbox, head_log)
    base, head_res = base or {}, head or {}
    regressions = sorted(t for t, ok in head_res.items() if not ok and base.get(t) is True)
    flaky = []
    if regressions and head_build:
        sh(sandbox["unit_test"], args.head, head_log)
        rerun = junit_results(os.path.join(args.head, sandbox["unit_report"])) or {}
        flaky = sorted(t for t in regressions if rerun.get(t) is True)
        regressions = sorted(set(regressions) - set(flaky))
    added = sorted(t for t in head_res if t not in base)
    added_failing = sorted(t for t in added if not head_res[t])
    if not head_build:
        status = "fail"
    elif head is None:
        status = "fail"  # the build passed but no test report was written
    else:
        status = "fail" if regressions or added_failing else "pass"
    write_json(args.out, {
        "version": 1, "status": status,
        "build": {"base": base_build, "head": head_build},
        "report": {"head": head is not None},
        "tests": {"base_total": len(base), "head_total": len(head_res), "added": len(added),
                  "regressions": regressions[:50], "flaky": flaky[:50], "added_failing": added_failing[:50],
                  "base_failing": sorted(t for t, ok in base.items() if not ok)[:50]},
    })
    print(f"sandbox: {status}; build base={base_build} head={head_build}; tests {len(head_res)} "
          f"({len(added)} added, {len(added_failing)} added failing, {len(regressions)} regressions, {len(flaky)} flaky)")


# The write stage reads the test result as data from a job that ran proposed code: only these shapes pass.
TEST_ID_RE = re.compile(r"^[^\x00-\x1f]{1,300}$")


def check_result(data):
    """Strict shape check of a `test` result before anything renders it."""
    def ids(v):
        return isinstance(v, list) and len(v) <= 50 and all(isinstance(t, str) and TEST_ID_RE.match(t) for t in v)
    if not isinstance(data, dict) or data.get("version") != 1:
        return False
    if data.get("status") == "untested":
        return set(data) == {"version", "status", "reason"} and data["reason"] == "no sandbox commands in .staff/code.yml"
    t, b = data.get("tests"), data.get("build")
    return (data.get("status") in ("pass", "fail") and isinstance(b, dict) and isinstance(t, dict)
            and all(isinstance(b.get(k), bool) for k in ("base", "head"))
            and isinstance((data.get("report") or {}).get("head"), bool)
            and all(isinstance(t.get(k), int) and 0 <= t[k] < 10**6 for k in ("base_total", "head_total", "added"))
            and all(ids(t.get(k)) for k in ("regressions", "flaky", "added_failing", "base_failing")))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply")
    a.add_argument("--validated", required=True)
    a.add_argument("--input", required=True, help="dev-meta.json (or the bundled input), for the code-map entry")
    a.add_argument("--repo", required=True, help="checkout of the base to change")
    a.add_argument("--out-dir", required=True)
    t = sub.add_parser("test")
    t.add_argument("--input", required=True, help="dev-meta.json (or the bundled input)")
    t.add_argument("--base", required=True, help="checkout of the base")
    t.add_argument("--head", required=True, help="the base with the change applied")
    t.add_argument("--out-dir", required=True, help="logs")
    t.add_argument("--out", required=True)
    args = ap.parse_args()
    {"apply": cmd_apply, "test": cmd_test}[args.cmd](args)


if __name__ == "__main__":
    run_main(main)
