"""Deterministic lint for interview transcripts, requirements/<area>/sources/INT-n.md.

Run by the human before committing a transcript (S-BA-056). Checks the format in
plugins/staff-product/templates/INT-n.md: the front matter, the ID against the
file name, the turn markers (S-BA-055, S-BA-056), decision citations, open items
for every topic not covered, the sources, and human_confirmed: true. It also runs
the redaction scan of redact_check.py over every line (S-SEC-004).

Reports line numbers and rule names, never matched values. Exit 0 when clean,
exit 2 with reason transcript_invalid or redaction_hit otherwise.
"""
import argparse
import datetime
import os
import re

from common import HarnessError, run_main
from contract import AREA_RE
from redact_check import scan_text

FIELDS = ("id", "area", "intake", "date", "human_confirmed")
SECTIONS = ("Topics covered", "Turns", "Decisions", "Open items", "Sources")
CATEGORIES = {"actors", "goals", "journeys", "rules", "permissions", "quality_targets", "out_of_scope"}
COVERAGE = {"covered", "partial", "not covered"}
MAX_TOPICS = 10  # S-BA-055, starting value

ID_RE = re.compile(r"^INT-[0-9]{3,}$")
INTAKE_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[0-9]+$")
TOPIC_RE = re.compile(r"^T-[0-9]{2,}$")
TURN_RE = re.compile(r"^### (\S+) \[(\S+)\]$")
META_RE = re.compile(
    r"^topic: (?P<topic>\S+) · kind: (?P<kind>question|readback)"
    r"(?: · key: \{entity: (?P<entity>[^,{}]+), target_id: (?P<target>[^,{}]+),"
    r" attribute: (?P<attr>[^,{}]+)\} · value: (?P<value>.+?) · from: (?P<from>T[0-9]+(?:, T[0-9]+)*))?$")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def _blank_comments(text):
    """Drop HTML comments but keep line numbers."""
    return COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def _front_matter(lines, problems):
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        problems.append("line 1: front matter missing (--- block)")
        return {}, 0
    end = lines.index("---", 1)
    fields = {}
    for n, line in enumerate(lines[1:end], start=2):
        m = re.fullmatch(r"([a-z_]+): *(.*?) *", line)
        if not m:
            problems.append(f"line {n}: front matter line is not 'key: value'")
        elif m.group(1) not in FIELDS:
            problems.append(f"line {n}: unknown front matter field {m.group(1)}")
        elif m.group(1) in fields:
            problems.append(f"line {n}: duplicate front matter field {m.group(1)}")
        else:
            fields[m.group(1)] = m.group(2)
    for name in FIELDS:
        if name not in fields:
            problems.append(f"front matter: {name} missing")
    return fields, end + 1


def _check_fields(fields, path, problems):
    stem = os.path.splitext(os.path.basename(path))[0]
    tid = fields.get("id")
    if tid is not None and not ID_RE.match(tid):
        problems.append("front matter: id is not INT-NNN (S-BA-005)")
    if tid is not None and tid != stem:
        problems.append(f"front matter: id does not match the file name {stem}.md")
    area = fields.get("area")
    if area is not None and not AREA_RE.match(area):
        problems.append("front matter: area is not an area key (S-GEN-060)")
    parts = os.path.normpath(os.path.abspath(path)).split(os.sep)
    if len(parts) >= 4 and parts[-4] == "requirements" and parts[-2] == "sources" and area != parts[-3]:
        problems.append(f"front matter: area does not match the path requirements/{parts[-3]}/sources/")
    if fields.get("intake") is not None and not INTAKE_RE.match(fields["intake"]):
        problems.append("front matter: intake is not owner/repo#n")
    if fields.get("date") is not None:
        try:
            datetime.date.fromisoformat(fields["date"])
        except ValueError:
            problems.append("front matter: date is not YYYY-MM-DD")
    if fields.get("human_confirmed") is not None and fields["human_confirmed"] != "true":
        problems.append("front matter: human_confirmed is not true; the human checks every turn first (S-BA-056)")


def _sections(lines, start, problems):
    """{title: [(line_no, text), ...]} for the ## sections after the front matter."""
    out, current = {}, None
    for n, line in enumerate(lines[start:], start=start + 1):
        if line.startswith("## "):
            current = line[3:].strip()
            if current in out:
                problems.append(f"line {n}: duplicate section {current}")
            out[current] = []
        elif current is not None:
            out[current].append((n, line))
    for name in SECTIONS:
        if name not in out:
            problems.append(f"section missing: ## {name}")
    for name in out:
        if name not in SECTIONS:
            problems.append(f"unexpected section: ## {name}")
    return out


def _bullets(body):
    return [(n, line[2:].strip()) for n, line in body if line.startswith("- ")]


def _topics(body, problems):
    topics = {}
    rows = [(n, [c.strip() for c in line.strip().strip("|").split("|")])
            for n, line in body if line.strip().startswith("|")]
    for n, cells in rows[2:]:  # header and divider rows
        if len(cells) != 4:
            problems.append(f"line {n}: topic row needs Topic, Category, Blocking, Coverage")
            continue
        topic, category, blocking, coverage = cells
        if not TOPIC_RE.match(topic):
            problems.append(f"line {n}: topic ID is not T-NN")
        elif topic in topics:
            problems.append(f"line {n}: duplicate topic {topic}")
        if category not in CATEGORIES:
            problems.append(f"line {n}: unknown topic category")
        if blocking not in ("yes", "no"):
            problems.append(f"line {n}: blocking is not yes or no")
        if coverage not in COVERAGE:
            problems.append(f"line {n}: coverage is not covered, partial or not covered")
        topics[topic] = coverage
    if not topics:
        problems.append("Topics covered: no topic rows")
    if len(topics) > MAX_TOPICS:
        problems.append(f"Topics covered: more than {MAX_TOPICS} topics (S-BA-055)")
    return topics


def _turns(body, topics, problems):
    """{k: (speaker, meta-match or None)} for turns T1..Tn."""
    turns, current = {}, None
    texts = {}
    for n, line in body:
        if re.match(r"#{3,6} ", line):
            m = TURN_RE.match(line)
            if not m or not re.fullmatch(r"T[1-9][0-9]*", m.group(1)):
                problems.append(f"line {n}: not a turn marker '### T<k> [human|interviewer]'")
                current = None
                continue
            k, speaker = int(m.group(1)[1:]), m.group(2)
            if speaker not in ("human", "interviewer"):
                problems.append(f"line {n}: speaker is not human or interviewer (S-BA-056)")
            if k != len(turns) + 1:
                problems.append(f"line {n}: turn T{k} out of sequence, expected T{len(turns) + 1}")
            current = k
            turns[k] = [speaker, None, n]
            texts[k] = []
        elif current is not None and line.strip():
            texts[current].append((n, line))
        elif current is None and line.strip():
            problems.append(f"line {n}: text before the first turn marker")
    for k, (speaker, _, n) in turns.items():
        lines = texts[k]
        if speaker == "interviewer":
            meta = META_RE.match(lines[0][1]) if lines else None
            if not meta:
                problems.append(f"line {n}: interviewer turn T{k} lacks a valid topic/kind line (S-BA-055)")
            else:
                turns[k][1] = meta
                if meta.group("topic") not in topics:
                    problems.append(f"line {n}: turn T{k} topic is not in Topics covered")
                if meta.group("kind") == "readback" and not meta.group("from"):
                    problems.append(f"line {n}: readback T{k} needs key, value and from (S-BA-055)")
            lines = lines[1:]
        elif lines and lines[0][1].startswith("topic: "):
            problems.append(f"line {n}: human turn T{k} carries an interviewer topic/kind line")
        if not lines:
            problems.append(f"line {n}: turn T{k} has no text")
    for k, (speaker, meta, n) in turns.items():
        if meta is not None and meta.group("from"):
            for ref in meta.group("from").split(", "):
                j = int(ref[1:])
                if j >= k or j not in turns or turns[j][0] != "human":
                    problems.append(f"line {n}: readback T{k} cites {ref}, which is not an earlier human turn")
    if not any(t[0] == "human" for t in turns.values()):
        problems.append("Turns: no human turn")
    return turns


def _decisions(body, tid, turns, problems):
    bullets = _bullets(body)
    if not bullets:
        problems.append("Decisions: no entries; write '- None.' if there are none")
    for n, text in bullets:
        if text == "None.":
            continue
        refs = re.findall(r"(INT-[0-9]+)#T([0-9]+)(?:/T([0-9]+))?", text)
        if not refs:
            problems.append(f"line {n}: decision cites no turn (S-BA-056)")
        for int_id, k, k2 in refs:
            k = int(k)
            if int_id != tid:
                problems.append(f"line {n}: decision cites {int_id}, not this transcript")
            elif k2:
                k2 = int(k2)
                rb = turns.get(k)
                if (k2 != k + 1 or rb is None or rb[1] is None or rb[1].group("kind") != "readback"
                        or turns.get(k2, ["?"])[0] != "human"):
                    problems.append(f"line {n}: T{k}/T{k2} is not a readback and the human turn after it")
            elif turns.get(k, ["?"])[0] != "human":
                problems.append(f"line {n}: T{k} is not a human turn; only human turns are sources (S-BA-056)")


def _open_items(body, topics, problems):
    bullets = _bullets(body)
    if not bullets:
        problems.append("Open items: no entries; write '- None.' if nothing is open")
    listed = {m for _, text in bullets for m in re.findall(r"T-[0-9]{2,}", text)}
    for topic, coverage in topics.items():
        if coverage != "covered" and topic not in listed:
            problems.append(f"Open items: topic {topic} is {coverage} but not listed")


def check(path):
    """(problems, redaction_hits) for one transcript file."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        return [f"cannot read the file ({type(exc).__name__})"], []
    hits = [f"line {n}: redaction hit ({name})"
            for n, line in enumerate(raw.splitlines(), start=1) for name in scan_text(line)]
    problems = []
    lines = _blank_comments(raw).splitlines()
    fields, start = _front_matter(lines, problems)
    _check_fields(fields, path, problems)
    sections = _sections(lines, start, problems)
    topics = _topics(sections.get("Topics covered", []), problems)
    turns = _turns(sections.get("Turns", []), topics, problems)
    _decisions(sections.get("Decisions", []), fields.get("id"), turns, problems)
    _open_items(sections.get("Open items", []), topics, problems)
    source_bullets = _bullets(sections.get("Sources", []))
    if not source_bullets:
        problems.append("Sources: no entries")
    elif fields.get("intake") and not any(fields["intake"] in text for _, text in source_bullets):
        problems.append("Sources: the intake ref is not cited")
    return problems, hits


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+", metavar="INT-n.md")
    args = ap.parse_args()
    failed, redacted = 0, False
    for path in args.paths:
        problems, hits = check(path)
        for line in hits + problems:
            print(f"{path}: {line}")
        failed += bool(problems or hits)
        redacted = redacted or bool(hits)
    if failed:
        raise HarnessError("redaction_hit" if redacted else "transcript_invalid",
                           f"{failed} transcript(s) failed; fix and re-run before committing (S-BA-056)")
    print("transcript check: clean")


if __name__ == "__main__":
    run_main(main)
