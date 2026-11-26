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

QA mode (S-QA-017): when the meta file is a test-gen `qa` section, the commands come from the layer's
`sandbox` block in `.staff/tests.yml` instead, and `test --validated` names the draft's expected failures:
an added test listed there may fail without failing the draft; it is reported as expected.

Every command comes from `.staff/code.yml` or `.staff/tests.yml` on the base branch, never from the model.
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

MAX_LINES = 1000          # S-DEV-010: raised from the 500 starting value by the human, 2026-11-26
CMD_TIMEOUT = 15 * 60     # seconds per command
MAX_REPORT_BYTES = 5_000_000
TEST_ID_MAX = 300
TAIL_LINES, TAIL_WIDTH, MESSAGE_MAX, MESSAGES_MAX = 40, 200, 300, 10
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
# DATABASE_URL points at the job's throwaway PostgreSQL service container (the QA api layer), never at a
# real database: the sandbox job holds no secrets.
CLEAN_ENV_KEYS = ("PATH", "HOME", "LANG", "TMPDIR", "RUNNER_TEMP", "DATABASE_URL")


UNTESTED_REASONS = ("no sandbox commands in .staff/code.yml", "no sandbox commands in .staff/tests.yml")


def meta_of(path):
    """The harness-made section: dev-meta.json, qa-meta.json, or a bundled input file."""
    data = load_json(path, "input_invalid")
    return data.get("developer") or data.get("qa") or data


def code_map_entry(path):
    """The area's code-map entry, from the meta file."""
    return meta_of(path).get("code_map_entry") or {}


def sandbox_of(meta):
    """(normalised sandbox {setup, build, test, report} or None, the reason when None)."""
    if "test_map_entry" in meta:
        sb = (meta.get("test_map_entry") or {}).get("sandbox")
        return (dict(sb) if sb else None), UNTESTED_REASONS[1]
    sb = (meta.get("code_map_entry") or {}).get("sandbox")
    if not sb:
        return None, UNTESTED_REASONS[0]
    return {"setup": sb["setup"], "build": sb["build"], "test": sb["unit_test"], "report": sb["unit_report"]}, None


def expected_ids(validated_path):
    """The test IDs the draft expects to fail (test-gen pr.expected_failures), or an empty set."""
    if not validated_path:
        return set()
    pr = (load_json(validated_path, "artifact_missing") or {}).get("pr") or {}
    return {e["test_id"] for e in pr.get("expected_failures") or [] if isinstance(e, dict) and isinstance(e.get("test_id"), str)}


def is_expected(tid, expected):
    """A report test ID matches a declared one exactly, or by file and full title suffix."""
    if tid in expected:
        return True
    path, _, name = tid.partition("::")
    return any(e.partition("::")[0] == path and name.endswith(e.partition("::")[2]) for e in expected)


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


def clean_line(line, root):
    """One log line made safe to show: no ANSI or control characters, no runner path, bounded."""
    line = ANSI_RE.sub("", line).replace(os.path.realpath(root) + "/", "").replace(root.rstrip("/") + "/", "")
    return "".join(c for c in line if c == "\t" or ord(c) >= 32)[:TAIL_WIDTH]


def output_tail(log, start, root):
    """The last lines a command wrote to the log after byte offset start, cleaned."""
    with open(log, encoding="utf-8", errors="replace") as fh:
        fh.seek(start)
        raw = fh.read().splitlines()
    header = next((i for i, x in enumerate(raw) if x.startswith("$ ")), -1)  # the "$ <command>" line sh() wrote
    lines = [clean_line(x, root) for x in raw[header + 1:]]
    return [x for x in lines if x.strip()][-TAIL_LINES:]


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


def junit_messages(path, ids):
    """{test_id: first line of its failure message} for the given failing tests, cleaned."""
    try:
        if os.path.getsize(path) > MAX_REPORT_BYTES:
            return {}
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return {}
    out = {}
    for case in root.iter("testcase"):
        tid = f"{case.get('classname') or case.get('file') or ''}::{case.get('name') or ''}"[:TEST_ID_MAX]
        if tid not in ids or tid in out or len(out) >= MESSAGES_MAX:
            continue
        for child in case:
            if child.tag in ("failure", "error"):
                text = (child.get("message") or child.text or "").strip().splitlines()
                out[tid] = clean_line(text[0] if text else child.tag, "/nonexistent")[:MESSAGE_MAX] or child.tag
                break
    return out


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
    """(build_ok, results or None, failure or None) for one checkout. sandbox is normalised (sandbox_of)."""
    report = os.path.join(repo, sandbox["report"])
    if os.path.exists(report):
        os.remove(report)
    for step, cmds in (("setup", sandbox["setup"]), ("build", sandbox["build"])):
        for cmd in cmds:
            start = os.path.getsize(log) if os.path.exists(log) else 0
            if not sh(cmd, repo, log):
                return False, None, {"step": step, "command": cmd, "tail": output_tail(log, start, repo)}
    start = os.path.getsize(log) if os.path.exists(log) else 0
    sh(sandbox["test"], repo, log)
    results = junit_results(report)
    if results is None:
        return True, None, {"step": "report", "command": sandbox["test"], "tail": output_tail(log, start, repo)}
    return True, results, None


def cmd_test(args):
    sandbox, reason = sandbox_of(meta_of(args.input))
    os.makedirs(args.out_dir, exist_ok=True)
    if not sandbox:
        write_json(args.out, {"version": 1, "status": "untested", "reason": reason})
        print(f"untested: {reason}")
        return
    expected = expected_ids(getattr(args, "validated", None))
    base_build, base, _ = run_side(args.base, sandbox, os.path.join(args.out_dir, "base.log"))
    head_log = os.path.join(args.out_dir, "head.log")
    head_build, head, failure = run_side(args.head, sandbox, head_log)
    base, head_res = base or {}, head or {}
    regressions = sorted(t for t, ok in head_res.items() if not ok and base.get(t) is True)
    flaky = []
    if regressions and head_build:
        sh(sandbox["test"], args.head, head_log)
        rerun = junit_results(os.path.join(args.head, sandbox["report"])) or {}
        flaky = sorted(t for t in regressions if rerun.get(t) is True)
        regressions = sorted(set(regressions) - set(flaky))
    added = sorted(t for t in head_res if t not in base)
    failing = sorted(t for t in added if not head_res[t])
    expected_failing = [t for t in failing if is_expected(t, expected)]
    added_failing = [t for t in failing if t not in expected_failing]
    if not head_build:
        status = "fail"
    elif head is None:
        status = "fail"  # the build passed but no test report was written
    else:
        status = "fail" if regressions or added_failing else "pass"
    messages = junit_messages(os.path.join(args.head, sandbox["report"]),
                              set(regressions + added_failing + expected_failing))
    write_json(args.out, {
        "version": 1, "status": status,
        "build": {"base": base_build, "head": head_build},
        "report": {"head": head is not None},
        "failure": failure,
        "messages": messages,
        "tests": {"base_total": len(base), "head_total": len(head_res), "added": len(added),
                  "regressions": regressions[:50], "flaky": flaky[:50], "added_failing": added_failing[:50],
                  "base_failing": sorted(t for t, ok in base.items() if not ok)[:50],
                  "expected_failing": expected_failing[:50]},
    })
    print(f"sandbox: {status}; build base={base_build} head={head_build}; tests {len(head_res)} "
          f"({len(added)} added, {len(added_failing)} added failing, {len(regressions)} regressions, {len(flaky)} flaky)")


# The write stage reads the test result as data from a job that ran proposed code: only these shapes pass.
TEST_ID_RE = re.compile(r"^[^\x00-\x1f]{1,300}$")
LINE_RE = re.compile(r"^[^\x00-\x08\x0a-\x1f]{0,200}$")


def check_failure(f, commands):
    """A head failure: a step, one of the code map's own commands, and a bounded, clean tail."""
    if f is None:
        return True
    return (isinstance(f, dict) and set(f) == {"step", "command", "tail"}
            and f["step"] in ("setup", "build", "report") and f["command"] in commands
            and isinstance(f["tail"], list) and len(f["tail"]) <= TAIL_LINES
            and all(isinstance(x, str) and LINE_RE.match(x) for x in f["tail"]))


def check_messages(m, ids):
    return (isinstance(m, dict) and len(m) <= MESSAGES_MAX
            and all(k in ids and isinstance(v, str) and 0 < len(v) <= MESSAGE_MAX and TEST_ID_RE.match(v)
                    for k, v in m.items()))


def check_result(data, sandbox=None):
    """Strict shape check of a `test` result before anything renders it.

    sandbox is the code map's sandbox block, when known: a failure must name one of its commands."""
    def ids(v):
        return isinstance(v, list) and len(v) <= 50 and all(isinstance(t, str) and TEST_ID_RE.match(t) for t in v)
    if not isinstance(data, dict) or data.get("version") != 1:
        return False
    if data.get("status") == "untested":
        return set(data) == {"version", "status", "reason"} and data["reason"] in UNTESTED_REASONS
    t, b = data.get("tests"), data.get("build")
    return (data.get("status") in ("pass", "fail") and isinstance(b, dict) and isinstance(t, dict)
            and all(isinstance(b.get(k), bool) for k in ("base", "head"))
            and isinstance((data.get("report") or {}).get("head"), bool)
            and all(isinstance(t.get(k), int) and 0 <= t[k] < 10**6 for k in ("base_total", "head_total", "added"))
            and all(ids(t.get(k)) for k in ("regressions", "flaky", "added_failing", "base_failing"))
            and ids(t.get("expected_failing", []))
            and check_failure(data.get("failure"), commands(sandbox))
            and check_messages(data.get("messages", {}), set(t["regressions"]) | set(t["added_failing"])
                               | set(t.get("expected_failing", []))))


def commands(sandbox):
    """The commands a failure may name: a code-map sandbox block or a normalised one."""
    if not sandbox:
        return set()
    return set(sandbox["setup"]) | set(sandbox["build"]) | {sandbox.get("test") or sandbox.get("unit_test")}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply")
    a.add_argument("--validated", required=True)
    a.add_argument("--input", required=True, help="dev-meta.json or qa-meta.json (or the bundled input), "
                   "for the code-map entry")
    a.add_argument("--repo", required=True, help="checkout of the base to change")
    a.add_argument("--out-dir", required=True)
    t = sub.add_parser("test")
    t.add_argument("--input", required=True, help="dev-meta.json or qa-meta.json (or the bundled input)")
    t.add_argument("--validated", help="the validated output, for test-gen expected failures")
    t.add_argument("--base", required=True, help="checkout of the base")
    t.add_argument("--head", required=True, help="the base with the change applied")
    t.add_argument("--out-dir", required=True, help="logs")
    t.add_argument("--out", required=True)
    args = ap.parse_args()
    {"apply": cmd_apply, "test": cmd_test}[args.cmd](args)


if __name__ == "__main__":
    run_main(main)
