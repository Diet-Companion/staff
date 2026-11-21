"""Shared test helpers: import path, fixture paths, and a CLI runner."""
import json
import os
import subprocess
import sys

TESTS = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.dirname(TESTS)
STAFF = os.path.dirname(HARNESS)
FIXTURES = os.path.join(TESTS, "fixtures")
SCHEMA = os.path.join(STAFF, "plugins", "staff-product", "schemas", "analyst-output.schema.json")
sys.path.insert(0, HARNESS)


def fixture(name):
    return os.path.join(FIXTURES, name)


def load(name):
    with open(fixture(name), encoding="utf-8") as fh:
        return json.load(fh)


def run_cli(script, *args, env=None):
    """Run a harness script; returns the CompletedProcess."""
    full_env = {k: v for k, v in os.environ.items() if k != "STAFF_REASON_FILE"}
    full_env.update(env or {})
    return subprocess.run([sys.executable, os.path.join(HARNESS, script), *args],
                          capture_output=True, text=True, env=full_env)
