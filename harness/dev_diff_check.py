"""The Developer's code diff check (S-DEV-018, S-DEV-028). No model, and no product code runs.

CI runs it on every DEV agent PR (G3, S-GEN-020). It diffs the PR's merge base against its head
in a git checkout, with the code map read from the base branch (S-DEV-004), and reports:
  - blocked: what no sign-off clears (S-DEV-018);
  - flags: what needs an operator sign-off in the S-ARCH-053 form;
  - needs_label: labels the workflow applies, today `dev:dependency` (S-SEC-009).

Flag IDs are `DIFF-` plus 12 hex characters of sha256 over (check, element) (S-DEV-028). A
sign-off is a line `/signoff DIFF-… [DIFF-…]` in a PR comment by an operator: a `User` account
listed in governance/operators.yml, compared case-insensitively. A Bot's comment never counts.
The element is in the ID, so a push that changes it gives a new ID and voids the old sign-off.

The `not_unit_observable` declaration (S-DEV-010) comes from --pr-block: a JSON file holding the
product-PR block (S-DEV-009), either the block itself or an object with it under `pr` (the
validated developer output). Its `kind` is used when --kind isn't given.

Interpretations and deferrals:
  - Test IDs (S-DEV-045) are derived statically from `test_decl` lines as `<path>::<name>`, the
    name being the string literal the declaration opens (or a `name` group in the pattern).
    The `test_list` command is never run, because this check never runs product code. A file
    falls back to its net count of assertion lines (S-DEV-028) when a declaration has no plain
    name (parametrised: `.each`, `.for`, `%s`, `$x`, `${…}`), or when two tests share a name.
  - A changed assertion line in a cited test raises no flag here: S-QA-040's cited-value lint
    judges it (S-DEV-028). That lint isn't part of this script.
  - `generated` paths (S-DEV-043): an output change is blocked unless one of its generator's
    inputs changed in the same diff. TODO: re-run the generator with the base declaration and
    the head's inputs and compare byte for byte. Generators are never run here.
  - A `refactor` or `upkeep` PR that removes or changes an assertion line is blocked. The
    replay-verified exception (S-DEV-030) isn't built, so it is never downgraded to a flag.
  - Paths no code-map area claims are the scope lint's (S-DEV-005) and are skipped here.

CLI:
  dev_diff_check.py --repo DIR --base SHA --head SHA --code-map F --operators F --comments F
                    --out result.json [--summary summary.md] [--pr-block F]
                    [--kind feature|fix|drift|refactor|upkeep] [--area A] [--schema F]
The checkout needs history back to the merge base. Exit 0 when passed, 1 when anything is
blocked or a flag lacks a sign-off, 2 on a harness error (fail closed).
"""
import argparse
import functools
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter

from code_map import classify, load_code_map, matches
from common import HarnessError, load_json, run_main, write_json
from contract import load_operators
from render_comment import esc
from validate_output import CITE_RE, DEPENDENCY_KEYS

STAFF = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SCHEMA = os.path.join(STAFF, "plugins", "staff-engineering", "schemas", "code-map.schema.json")
MARKER = "<!-- staff-dev-diff-check:v1 -->"
PATTERN_CLASSES = ("test_decl", "assertion", "skip", "expected_failure", "authorization", "validation",
                   "permission_deny", "lint_suppression", "testability")
# Removed or changed lines of these classes are flagged, also when they move (S-DEV-028).
GUARD_CLASSES = ("authorization", "validation", "permission_deny", "testability")
# package.json sections whose entries are dependencies; overrides and resolutions pin them too.
DEP_SECTIONS = DEPENDENCY_KEYS + ("overrides", "resolutions")
KINDS = ("feature", "fix", "drift", "refactor", "upkeep")
DEPENDENCY_LABEL = "dev:dependency"
QUOTES = "'\"`"
# A declaration whose name is a template: the runner lists other names than the file holds (S-DEV-045).
PARAM_DECL = re.compile(r"\.(each|for)\b")
PARAM_NAME = re.compile(r"%[sdifjoOp#%]|\$\{|\$[A-Za-z_]")
SIGNOFF_RE = re.compile(r"^[ \t]*/signoff\b(.*)$", re.M)
FLAG_ID_RE = re.compile(r"\bDIFF-[0-9a-f]{12}\b")
PREAMBLE = "(before the first test)"


# ---- git: the diff only, never a checkout or a hook -------------------------------------------

def git(repo, *args):
    """stdout bytes of a git command, or HarnessError(diff_failed). Pathspecs are literal."""
    cmd = ["git", "--literal-pathspecs", "-C", repo, "-c", "core.quotePath=false", *args]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        raise HarnessError("diff_failed", f"git {args[0]} did not run") from None
    if r.returncode != 0:
        raise HarnessError("diff_failed", f"git {args[0]} failed (exit {r.returncode})")
    return r.stdout


def merge_base(repo, base, head):
    """The commit the PR branched from: what the code host's PR diff compares against."""
    for rev in (base, head):
        git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")
    return git(repo, "merge-base", base, head).decode().strip()


def changed_files(repo, old, new):
    """[{status, old, new}] with rename detection (-M), so a move maps old paths to new (S-DEV-028)."""
    try:
        parts = git(repo, "diff", "--name-status", "-z", "-M", "--no-ext-diff", old, new).decode("utf-8")
    except UnicodeDecodeError:
        raise HarnessError("diff_failed", "a changed path is not UTF-8") from None
    parts = parts.split("\0")
    if parts and parts[-1] == "":
        parts.pop()
    changes, i = [], 0
    try:
        while i < len(parts):
            st = parts[i][:1]
            if st == "R":
                changes.append({"status": "R", "old": parts[i + 1], "new": parts[i + 2]})
                i += 3
            elif st and st in "AMDT":
                path = parts[i + 1]
                changes.append({"status": st, "old": None if st == "A" else path, "new": None if st == "D" else path})
                i += 2
            else:
                raise HarnessError("diff_failed", f"unexpected diff status {parts[i][:4]!r}")
    except IndexError:
        raise HarnessError("diff_failed", "truncated name-status output") from None
    return changes


def blob(repo, rev, path):
    """A file's bytes at rev; empty when the side doesn't exist (an add or a delete)."""
    return git(repo, "cat-file", "blob", f"{rev}:{path}") if path else b""


def text_lines(data):
    """Lines of a text blob, or None for a binary one (a NUL in the first 8000 bytes, as git decides)."""
    if b"\0" in data[:8000]:
        return None
    return data.decode("utf-8", "replace").splitlines()


def file_hunks(repo, old, new, ch):
    """[(removed lines, added lines)] per hunk of one text file's diff.

    git's own -U0 hunks with a pinned algorithm, so a hunk hash is the same on every run. For a
    rename, the hunks are those between the old and the new content: a pure move has none.
    --text keeps a PR's .gitattributes (`-diff`) from hiding a text file's lines as binary; the
    caller decides what is binary from the blobs."""
    paths = [p for p in dict.fromkeys((ch["old"], ch["new"])) if p]
    out = git(repo, "diff", "-U0", "-M", "--text", "--no-color", "--no-ext-diff", "--no-textconv",
              "--diff-algorithm=myers", old, new, "--", *paths)
    hunks, cur = [], None
    for raw in out.split(b"\n"):
        line = raw.decode("utf-8", "replace")
        if cur is None and not line.startswith("@@"):
            continue  # the header: diff --git, index, ---, +++, rename, mode lines
        if line.startswith("@@"):
            cur = ([], [])
            hunks.append(cur)
        elif line.startswith("-"):
            cur[0].append(line[1:])
        elif line.startswith("+"):
            cur[1].append(line[1:])
    return hunks


# ---- elements and flag IDs (S-DEV-028, S-ARCH-053) --------------------------------------------

def short_hash(text):
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()[:16]


def flag_id(check, element):
    """`DIFF-` + 12 hex of sha256 over (check, element): stable across rebases, new when the element changes."""
    return "DIFF-" + hashlib.sha256(f"{check}\n{element}".encode("utf-8", "surrogatepass")).hexdigest()[:12]


def line_element(file, cls, line):
    """A guard line's element (S-DEV-028): (file, pattern class, line hash), whitespace-trimmed."""
    return f"{file}|{cls}|{short_hash(line.strip())}"


def hunk_elements(file, ch, hunks, head_bytes):
    """One element per hunk, (file, hunk hash), for a protected or verification-config change
    (S-DEV-028). The hash covers the hunk's lines, not its position, so it holds across rebases."""
    out = []
    if ch["old"] and ch["new"] and ch["old"] != ch["new"]:
        out.append(f"{file}@renamed-from:{ch['old']}")
    if hunks is None:
        out.append(f"{file}@binary:{hashlib.sha256(head_bytes).hexdigest()[:16]}")
    else:
        for removed, added in hunks:
            out.append(f"{file}@" + short_hash("\n".join(["-" + x for x in removed] + ["+" + x for x in added])))
    return out or [f"{file}@mode"]  # a mode or type change with no content diff


class Findings:
    """Flags keyed by flag ID and blocks keyed by (check, file): one entry per element."""

    def __init__(self):
        self.flags, self.blocked, self.labels = {}, {}, set()

    def flag(self, check, file, element, reason):
        fid = flag_id(check, element)
        self.flags.setdefault(fid, {"id": fid, "check": check, "file": file, "element": element,
                                    "reason": reason, "signed_off_by": None})

    def block(self, check, file, reason):
        self.blocked.setdefault((check, file), {"check": check, "file": file, "reason": reason})


# ---- code map: per-path classes and patterns (S-DEV-004) --------------------------------------

@functools.lru_cache(maxsize=None)
def rx(pattern):
    try:
        return re.compile(pattern)
    except re.error:
        raise HarnessError("code_map_invalid", "a guard pattern is not a valid regular expression") from None


def first_match(patterns, line):
    return next((m for p in patterns if (m := p.search(line))), None)


def area_entries(code_map, area):
    """The entries the check applies: --area's, or every area's. No entry fails closed (S-DEV-004)."""
    areas = code_map.get("areas") or {}
    if area:
        if area not in areas:
            raise HarnessError("code_map_invalid", f"the code map has no entry for area {area}")
        return [areas[area]]
    if not areas:
        raise HarnessError("code_map_invalid", "the code map has no area entries")
    return list(areas.values())


def path_view(paths, entries):
    """(classes per path, patterns) over the areas that claim any of the paths. Patterns are the
    union of those areas' stacks: the map doesn't say which stack a file is, so all apply."""
    classes = {p: set() for p in paths}
    pats = {k: [] for k in PATTERN_CLASSES}
    for entry in entries:
        claims = {p: classify(p, entry) for p in paths}
        if not any(claims.values()):
            continue
        for p, c in claims.items():
            classes[p] |= c
        for g in entry.get("guard_patterns") or []:
            for k in PATTERN_CLASSES:
                pats[k] += [rx(x) for x in g.get(k) or [] if rx(x) not in pats[k]]
    return classes, pats


# ---- tests: a net set keyed by (test ID v1, cited IDs) (S-DEV-028, S-DEV-045) -----------------

def test_name(line, m):
    """The plain name a declaration opens, or None (no literal on the line, or a parametrised name)."""
    if "name" in m.re.groupindex and m.group("name") is not None:
        name = m.group("name")
    else:
        i = m.end()
        if m.group(0) and m.group(0)[-1] in QUOTES:
            q = m.group(0)[-1]
        else:
            rest = line[i:].lstrip(" \t(")
            if not rest or rest[0] not in QUOTES:
                return None
            i, q = len(line) - len(rest) + 1, rest[0]
        out = []
        while i < len(line) and line[i] != q:
            if line[i] == "\\" and i + 1 < len(line):
                i += 1
            out.append(line[i])
            i += 1
        if i >= len(line):
            return None  # the name runs past the line
        name = "".join(out)
    if PARAM_DECL.search(m.group(0)) or PARAM_NAME.search(name) or not name.strip():
        return None
    return name


def cite_tokens(line):
    """Cited IDs on a line, read as validate_output.file_citations does, cut at a quote or space."""
    out = []
    for m in CITE_RE.finditer(line):
        for c in m.group(1).split(","):
            token = re.split(r"[\s'\"`)]", c.strip(), maxsplit=1)[0].rstrip(".;")
            if token:
                out.append(token)
    return out


def parse_tests(file, lines, pats):
    """{test ID: {cites, asserts}} for one version of a test file, or None when S-DEV-045 falls back.

    A test spans from its test_decl line to the next one. An assertion line belongs to the span
    that holds it; the lines above the first test form a preamble entry. A `cites:` token belongs
    to the first test declared on its line or within the 3 lines after it (S-DEV-016)."""
    decls = []
    for i, line in enumerate(lines):
        m = first_match(pats["test_decl"], line)
        if m:
            decls.append((i, test_name(line, m)))
    names = [n for _, n in decls]
    if None in names or len(set(names)) != len(names):
        return None
    starts = [i for i, _ in decls]
    cites = {i: set() for i in starts}
    for c, line in enumerate(lines):
        tokens = cite_tokens(line)
        owner = next((d for d in starts if c <= d <= c + 3), None)
        if tokens and owner is not None:
            cites[owner].update(tokens)
    bounds = [(f"{file}::{PREAMBLE}", 0, starts[0] if starts else len(lines), frozenset())]
    for n, (i, name) in enumerate(decls):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        bounds.append((f"{file}::{name}", i, end, frozenset(cites[i])))
    return {tid: {"cites": cited, "asserts": [x.strip() for x in lines[a:b] if first_match(pats["assertion"], x)]}
            for tid, a, b, cited in bounds}


def assertion_lines(lines, pats):
    return Counter(x.strip() for x in lines if first_match(pats["assertion"], x))


def check_tests(res, file, old_lines, new_lines, pats, kind):
    """The test rules of S-DEV-018/-028 for one test file. Base IDs use the head path: the rename rewrite."""
    if not pats["assertion"]:
        raise HarnessError("code_map_invalid", f"a test file changes but its area has no assertion pattern ({file})")

    # Newly skipped or expected-failure tests: marker lines whose count grew, so a move isn't one.
    marked = set()
    for cls, check, what in (("skip", "test_skipped", "skipped"),
                             ("expected_failure", "test_expected_failure", "marked expected-failure")):
        before = Counter(x.strip() for x in old_lines if first_match(pats[cls], x))
        after = Counter(x.strip() for x in new_lines if first_match(pats[cls], x))
        for line in sorted(after - before):
            name = test_name(line, first_match(pats[cls], line))
            element = f"{file}::{name}" if name else line_element(file, cls, line)
            marked.add(element)
            res.flag(check, file, element, f"a test is newly {what}")

    # A refactor or upkeep PR changes no assertion (S-DEV-009); the S-DEV-030 exception isn't built.
    if kind in ("refactor", "upkeep") and assertion_lines(old_lines, pats) - assertion_lines(new_lines, pats):
        res.block("refactor_assertion", file, f"a {kind} PR removes or changes an assertion line")

    base, head = parse_tests(file, old_lines, pats), parse_tests(file, new_lines, pats)
    if base is None or head is None:  # S-DEV-045 fallback: per-file net assertion count
        b, h = sum(assertion_lines(old_lines, pats).values()), sum(assertion_lines(new_lines, pats).values())
        if h < b:
            res.flag("assertion_net_decrease", file, f"{file}#{b}->{h}",
                     f"the file's net assertion lines drop from {b} to {h} (test IDs not derivable)")
        return
    for tid, t in base.items():
        h = head.get(tid)
        preamble = tid.endswith("::" + PREAMBLE)
        if not preamble and (h is None or h["cites"] != t["cites"]):
            if tid not in marked:
                res.flag("test_removed", file, tid, "the test's key (test ID, cited IDs) is gone from the head")
            continue
        h = h or {"asserts": []}
        if len(h["asserts"]) < len(t["asserts"]):
            res.flag("assertion_shrunk", file, tid,
                     f"the test's assertion lines drop from {len(t['asserts'])} to {len(h['asserts'])}")
        elif not t["cites"] and Counter(t["asserts"]) - Counter(h["asserts"]):
            res.flag("assertion_changed", file, tid, "an assertion line changes in an uncited test")
        # A changed assertion in a cited test is S-QA-040's (cited-value lint), not flagged here.


# ---- guard lines, paths, dependencies, generated code (S-DEV-018) -----------------------------

def check_guards(res, file, hunks, pats):
    """Removed or changed guard lines, also when moved; added lint suppressions (S-DEV-028)."""
    for removed, added in hunks or []:
        for line in removed:
            for cls in GUARD_CLASSES:
                if first_match(pats[cls], line):
                    res.flag("guard_line", file, line_element(file, cls, line),
                             f"a {cls.replace('_', '-')} line is removed or changed")
        for line in added:
            if first_match(pats["lint_suppression"], line):
                res.flag("lint_suppression", file, line_element(file, "lint_suppression", line),
                         "a lint suppression is added")


def check_paths(res, ch, classes, hunks, head_bytes):
    """protected and verification_config: a delete is blocked, any other change flagged per hunk."""
    old_cls = classes.get(ch["old"], set()) if ch["old"] else set()
    new_cls = classes.get(ch["new"], set()) if ch["new"] else set()
    for cls in ("protected", "verification_config"):
        what = cls.replace("_", " ")
        if cls in old_cls and cls not in new_cls:  # deleted, or moved out of the class
            res.block(f"{cls}_deleted", ch["old"], f"a {what} file is deleted or moved out of {cls}")
        elif cls in new_cls:
            for element in hunk_elements(ch["new"], ch, hunks, head_bytes):
                res.flag(cls, ch["new"], element, f"a {what} file changes")


def manifest(data):
    """A JSON manifest's object, {} for a missing side, or None when it isn't a JSON object."""
    if not data:
        return {}
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def version_text(value):
    return value if isinstance(value, str) else json.dumps(value, sort_keys=True, separators=(",", ":"))


def check_dependencies(res, ch, old_bytes, new_bytes, hunks):
    """dependency_files: one flag per (name, to-version) in a package.json-style manifest, else per
    hunk; and the dev:dependency label for any change (S-DEV-018, S-SEC-009)."""
    file = ch["new"] or ch["old"]
    res.labels.add(DEPENDENCY_LABEL)
    before, after = manifest(old_bytes), manifest(new_bytes)
    if not file.endswith(".json") or before is None or after is None:
        for element in hunk_elements(file, ch, hunks, new_bytes):
            res.flag("dependency", file, element, "a dependency file changes")  # not a JSON manifest
        return
    for sec in DEP_SECTIONS:
        b, a = before.get(sec), after.get(sec)
        if b == a:
            continue
        b = b if isinstance(b, dict) else {} if b is None else {f"({sec})": b}
        a = a if isinstance(a, dict) else {} if a is None else {f"({sec})": a}
        for name in sorted(set(b) | set(a)):
            if b.get(name) != a.get(name):
                to = version_text(a[name]) if name in a else "(removed)"
                was = version_text(b[name]) if name in b else "(none)"
                res.flag("dependency", file, f"{name}@{to}", f"{name} {was} -> {to} ({sec})")


def check_generated(res, changes, classes, entries):
    """A `generated` change not explained by its generator is blocked (S-DEV-018, S-DEV-043).

    Conservative for now: explained means one of the declaring generator's inputs changed in the
    same diff. TODO(S-DEV-043): re-run the generator and compare its outputs byte for byte."""
    generators = [g for e in entries for g in e.get("generators") or []]
    touched = [p for ch in changes for p in (ch["old"], ch["new"]) if p]
    for ch in changes:
        for path in dict.fromkeys(p for p in (ch["old"], ch["new"]) if p):
            if "generated" not in classes.get(path, set()):
                continue
            owners = [g for g in generators if matches(path, g["outputs"])]
            if not owners:
                res.block("generated_hand_edit", path, "a generated file changes and no generators entry outputs it")
            elif not any(matches(p, g["inputs"]) for g in owners for p in touched):
                ids = ", ".join(g["generator_id"] for g in owners)
                res.block("generated_hand_edit", path, f"a generated file changes but no input of {ids} does")


def check_declaration(res, pr):
    """A not_unit_observable declaration is a flagged diff; its element is fixes.target (S-DEV-010)."""
    nuo = pr.get("not_unit_observable")
    if not nuo:
        return
    target = (pr.get("fixes") or {}).get("target") or (nuo.get("target") if isinstance(nuo, dict) else None)
    if not isinstance(target, str) or not target.strip():
        raise HarnessError("input_invalid", "not_unit_observable is declared without a target")
    res.flag("not_unit_observable", None, target, "the PR declares a defect no unit test can observe")


# ---- sign-offs (S-ARCH-053) -------------------------------------------------------------------

def signoffs(comments, operators):
    """{flag ID: login} from `/signoff` lines in comments by operator User accounts. Bots never count."""
    out = {}
    for c in comments:
        user = c.get("user") or {}
        login = str(user.get("login") or "")
        if user.get("type") != "User" or login.lower() not in operators:
            continue
        for m in SIGNOFF_RE.finditer(str(c.get("body") or "")):
            for fid in FLAG_ID_RE.findall(m.group(1)):
                out.setdefault(fid, login)
    return out


def load_comments(path):
    """The PR's issue comments as the GitHub API returns them; one level of page arrays is flattened."""
    data = load_json(path, "input_invalid")
    if not isinstance(data, list):
        raise HarnessError("input_invalid", "--comments is not a JSON array")
    flat = [c for item in data for c in (item if isinstance(item, list) else [item])]
    if not all(isinstance(c, dict) for c in flat):
        raise HarnessError("input_invalid", "a comment is not a JSON object")
    return flat


def load_pr_block(path):
    """The product-PR block from --pr-block: the block, or an object holding it under `pr`."""
    if not path:
        return {}
    data = load_json(path, "input_invalid")
    if isinstance(data, dict) and "pr" in data:
        data = data["pr"] or {}
    if not isinstance(data, dict):
        raise HarnessError("input_invalid", "--pr-block is not a JSON object")
    return data


# ---- the check --------------------------------------------------------------------------------

def run_check(repo, base, head, code_map, operators, comments, pr=None, kind=None, area=None):
    """The result {passed, blocked[], flags[], needs_label[]} for one PR (S-DEV-018, S-DEV-028)."""
    pr = pr or {}
    kind = kind or pr.get("kind")
    if kind is not None and kind not in KINDS:
        raise HarnessError("input_invalid", "the PR kind is not one of " + ", ".join(KINDS))
    entries = area_entries(code_map, area)
    mb = merge_base(repo, base, head)
    changes = changed_files(repo, mb, head)
    res = Findings()
    all_paths = [p for ch in changes for p in (ch["old"], ch["new"]) if p]
    classes, _ = path_view(all_paths, entries)
    for ch in changes:
        paths = [p for p in (ch["old"], ch["new"]) if p]
        if not any(classes[p] for p in paths):
            continue  # no area claims it: the scope lint's (S-DEV-005)
        _, pats = path_view(paths, entries)
        file = ch["new"] or ch["old"]
        old_bytes, new_bytes = blob(repo, mb, ch["old"]), blob(repo, head, ch["new"])
        old_lines, new_lines = text_lines(old_bytes), text_lines(new_bytes)
        binary = old_lines is None or new_lines is None
        hunks = None if binary else file_hunks(repo, mb, head, ch)
        check_paths(res, ch, classes, hunks, new_bytes)
        check_guards(res, file, hunks, pats)
        if any("dependency_files" in classes[p] for p in paths):
            check_dependencies(res, ch, old_bytes, new_bytes, hunks)
        if not binary and any("unit_tests" in classes[p] for p in paths):
            check_tests(res, file, old_lines, new_lines, pats, kind)
    check_generated(res, changes, classes, entries)
    check_declaration(res, pr)

    signed = signoffs(comments, operators)
    flags = sorted(res.flags.values(), key=lambda f: (f["file"] or "", f["check"], f["element"]))
    for f in flags:
        f["signed_off_by"] = signed.get(f["id"])
    blocked = sorted(res.blocked.values(), key=lambda b: (b["file"] or "", b["check"]))
    return {"passed": not blocked and all(f["signed_off_by"] for f in flags), "blocked": blocked,
            "flags": flags, "needs_label": sorted(res.labels)}


def description(result):
    """One line for the commit status."""
    open_flags = sum(1 for f in result["flags"] if not f["signed_off_by"])
    if result["blocked"]:
        return f"code diff check: blocked ({len(result['blocked'])}), no sign-off clears it"
    if open_flags:
        return f"code diff check: {open_flags} of {len(result['flags'])} flags need an operator sign-off"
    if not result["flags"]:
        return "code diff check: passed, nothing flagged"
    return f"code diff check: passed ({len(result['flags'])} flags, all signed off)"


def summary(result):
    """Markdown for the check summary and the PR comment. PR-derived text is escaped (S-SEC-002)."""
    out = [MARKER, "### Code diff check (S-DEV-018)", "", f"**{esc(description(result))}**", ""]
    if result["blocked"]:
        out += ["#### Blocked", "", "No sign-off clears these; change the PR.", ""]
        out += [f"- {esc(b['file'] or '(PR)')}: {esc(b['reason'])} ({esc(b['check'])})" for b in result["blocked"]]
        out.append("")
    if result["flags"]:
        out += ["#### Flagged diffs (G3)", "", "| Flag ID | Check | File | Element | Reason | Signed off |",
                "| --- | --- | --- | --- | --- | --- |"]
        for f in result["flags"]:
            who = esc(f["signed_off_by"]) if f["signed_off_by"] else "no"
            out.append(f"| `{f['id']}` | {esc(f['check'])} | {esc(f['file'] or '(PR)')} | "
                       f"{esc(f['element'][:160])} | {esc(f['reason'])} | {who} |")
        out += ["", "To sign off a flag after judging it, an operator comments `/signoff DIFF-xxxxxxxxxxxx` "
                "(several IDs per line are fine). A push that changes a flagged element gives it a new ID, "
                "and the old sign-off no longer counts (S-ARCH-053).", ""]
    if result["needs_label"]:
        out += ["Labels: " + ", ".join(f"`{esc(x)}`" for x in result["needs_label"]), ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True, help="product git checkout with history to the merge base")
    ap.add_argument("--base", required=True, help="PR base SHA")
    ap.add_argument("--head", required=True, help="PR head SHA")
    ap.add_argument("--code-map", required=True, help=".staff/code.yml from the base branch (S-DEV-004)")
    ap.add_argument("--schema", default=DEFAULT_SCHEMA, help="code-map schema")
    ap.add_argument("--operators", required=True, help="staff governance/operators.yml")
    ap.add_argument("--comments", required=True, help="the PR's issue comments, GitHub API JSON")
    ap.add_argument("--pr-block", help="JSON product-PR block (S-DEV-009), or an object with it under `pr`")
    ap.add_argument("--kind", choices=KINDS, help="PR kind; defaults to the PR block's")
    ap.add_argument("--area", help="check only this code-map area (default: every area)")
    ap.add_argument("--out", required=True, help="result JSON")
    ap.add_argument("--summary", help="Markdown summary file (check summary and PR comment)")
    args = ap.parse_args()
    result = run_check(os.path.abspath(args.repo), args.base, args.head,
                       load_code_map(args.code_map, args.schema), load_operators(args.operators),
                       load_comments(args.comments), pr=load_pr_block(args.pr_block), kind=args.kind,
                       area=args.area)
    write_json(args.out, result)
    if args.summary:
        with open(args.summary, "w", encoding="utf-8") as fh:
            fh.write(summary(result))
    print(description(result))
    if not result["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    run_main(main)
