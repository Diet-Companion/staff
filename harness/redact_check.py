"""Fail-closed redaction check (S-SEC-004).

Scans every string in a JSON file for secret-like values and personal email
addresses. Any hit fails the run: the item is dropped, not stored or posted.
Reports only the JSON path and the pattern name, never the matched value.
"""
import argparse
import math
import re
from collections import Counter

from common import HarnessError, load_json, run_main

PATTERNS = {
    "anthropic_key": re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    "github_pat": re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    "pem_header": re.compile(r"-----BEGIN [A-Z0-9 ]{0,40}(PRIVATE KEY|CERTIFICATE)[A-Z ]{0,20}-----"),
    "aws_access_key": re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
ALLOWED_EMAIL = re.compile(r"@users\.noreply\.github\.com$", re.I)
# Long runs of key-like characters with lower case, upper case and at least two
# digits. Hex digests (git SHAs) stay under the entropy bar: 16 symbols give at
# most 4 bits per character. URLs are left to the named patterns, because their
# paths look random. Tuned so random 32-char tokens are caught about 95% of the
# time, and 40-char base64 about 99%.
CANDIDATE = re.compile(r"[A-Za-z0-9+/_=-]{32,}")
URL = re.compile(r"https?://\S+")
ENTROPY_BITS = 4.3


def entropy(s):
    counts = Counter(s)
    return -sum(n / len(s) * math.log2(n / len(s)) for n in counts.values())


def high_entropy(s):
    for token in CANDIDATE.findall(URL.sub(" ", s)):
        if (re.search("[a-z]", token) and re.search("[A-Z]", token)
                and len(re.findall("[0-9]", token)) >= 2 and entropy(token) >= ENTROPY_BITS):
            return True
    return False


def scan_text(text):
    """Names of the patterns found in one string."""
    hits = [name for name, rx in PATTERNS.items() if rx.search(text)]
    if any(not ALLOWED_EMAIL.search(m) for m in EMAIL.findall(text)):
        hits.append("email")
    if high_entropy(text):
        hits.append("high_entropy")
    return hits


def walk(node, path=""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from walk(value, f"{path}/{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from walk(value, f"{path}/{i}")
    elif isinstance(node, str):
        yield path or "/", node


def scan(data):
    """(path, pattern) for every hit."""
    return [(path, name) for path, text in walk(data) for name in scan_text(text)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="path", required=True, help="JSON file to scan")
    ap.add_argument("--reason", default="redaction_hit", choices=["redaction_hit", "input_redaction"])
    args = ap.parse_args()
    hits = scan(load_json(args.path, "redaction_hit" if args.reason == "redaction_hit" else "input_invalid"))
    for path, name in hits:
        print(f"redaction hit: {path} ({name})")
    if hits:
        raise HarnessError(args.reason, f"{len(hits)} hit(s); the item is dropped (S-SEC-004)")
    print("redaction check: clean")


if __name__ == "__main__":
    run_main(main)
