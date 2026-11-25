"""The Developer's code map, `.staff/code.yml` (S-DEV-004), and path scope (S-DEV-005).

The map is human-owned and read from the base branch only, so a change can't
loosen the rules it is checked against. Globs use `**` for any number of path
segments, `*` and `?` within one segment.
"""
import json
import re

import yaml
from jsonschema import Draft202012Validator

from common import HarnessError

# Paths no Developer change may touch, whatever the code map says (S-DEV-005).
FORBIDDEN = ("architecture/", "requirements/", "knowledge/", ".staff/", ".github/", "governance/")
FORBIDDEN_FILES = {"AGENTS.md", "CLAUDE.md", "CODEOWNERS"}
# Path classes that need a flag in the PR block (S-DEV-018).
FLAGGED = ("protected", "dependency_files", "verification_config")


def load_code_map(path, schema_path):
    """The validated map, or HarnessError(code_map_invalid). A missing file is an empty map."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except FileNotFoundError:
        return {"version": 1, "areas": {}}
    except (OSError, yaml.YAMLError) as exc:
        raise HarnessError("code_map_invalid", f"cannot read {path} ({type(exc).__name__})") from None
    with open(schema_path, encoding="utf-8") as fh:
        schema = json.load(fh)
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        where = "/" + "/".join(str(p) for p in errors[0].absolute_path)
        raise HarnessError("code_map_invalid", f"{path}: {where} does not match the code-map schema")
    return data


def glob_re(pattern):
    """Compile a path glob: ** spans segments, * and ? stay inside one."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def matches(path, globs):
    return any(glob_re(g).match(path) for g in globs)


def forbidden(path):
    return path.startswith(FORBIDDEN) or path in FORBIDDEN_FILES


def classify(path, entry):
    """The set of code-map classes a path falls in, e.g. {'source', 'protected'}."""
    keys = ("source", "unit_tests", "generated") + FLAGGED
    return {k for k in keys if matches(path, entry.get(k) or [])}
