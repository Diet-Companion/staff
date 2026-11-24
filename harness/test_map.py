"""The QA test map, `.staff/tests.yml` (S-QA-005), and the test-gen path scope (S-QA-014).

Human-owned and read from the base branch only. Globs follow code_map.glob_re.
"""
import json

import yaml
from jsonschema import Draft202012Validator

from code_map import matches
from common import HarnessError

LAYERS = ("unit", "api", "ui")
# The globs a test-gen agent may write, per layer entry (S-QA-014).
WRITABLE = ("paths", "fixtures", "mocks", "request_docs")


def load_test_map(path, schema_path):
    """The validated map, or HarnessError(test_map_invalid). A missing file is an empty map."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except FileNotFoundError:
        return {"version": 1, "areas": {}}
    except (OSError, yaml.YAMLError) as exc:
        raise HarnessError("test_map_invalid", f"cannot read {path} ({type(exc).__name__})") from None
    with open(schema_path, encoding="utf-8") as fh:
        schema = json.load(fh)
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        where = "/" + "/".join(str(p) for p in errors[0].absolute_path)
        raise HarnessError("test_map_invalid", f"{path}: {where} does not match the test-map schema")
    return data


def layer_entry(test_map, area, layer):
    return ((test_map.get("areas") or {}).get(area) or {}).get(layer)


def writable(path, entry):
    return any(matches(path, entry.get(k) or []) for k in WRITABLE)


def is_test_file(path, entry):
    return matches(path, entry.get("paths") or [])
