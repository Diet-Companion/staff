"""Developer fetch step (S-DEV-042): add the readiness result and code-map entry to the input.

Reads the input file from build_input.py --agent developer and the product checkout
at the default branch (truth). Writes the input back with a `developer` section:
- the area and ticket kind, parsed from the operator's ticket body only;
- the readiness result (S-DEV-007): `ready`, or `waiting` with blockers;
- the area's code-map entry (S-DEV-004), or null.

The readiness rules, until the BA and ARCH trace matrices exist:
- implement (feature): the ticket names ACs (`REQ-n/AC-k`) or whole requirements
  (`REQ-n`, meaning all its live ACs). Each requirement is `ready`, each AC exists and
  is not retired. Each such requirement, and each quality requirement it lists, has an
  accepted QAS (its design isn't pending, S-ARCH-015). Each interface version the ticket
  names (`IF-n@x.y.z`) is approved or deprecated.
- implement with `Kind: refactor`: an operator ticket is the driver; no AC is needed.
- fix: the ticket names a target: a live AC, an active rule, or a constraint of an
  accepted ADR (S-DEV-007).
- bootstrap: the area exists. No code map is needed (S-DEV-006).
Every kind but bootstrap also needs the area's code-map entry.
"""
import argparse
import glob
import os
import re

import yaml

from code_map import load_code_map
from common import HarnessError, load_json, run_main, write_json

KINDS = ("implement", "fix", "bootstrap")
AREA_RE = re.compile(r"(?im)^[\s>*_-]*area[\s*_]*:[\s*_]*`?([a-z0-9][a-z0-9-]{0,63})`?")
KIND_RE = re.compile(r"(?im)^[\s>*_-]*kind[\s*_]*:[\s*_]*`?(feature|refactor)`?")
AC_RE = re.compile(r"\bREQ-\d{3,}/AC-\d{3,}\b")
REQ_RE = re.compile(r"\bREQ-\d{3,}\b(?!/AC-)")
IF_RE = re.compile(r"\bIF-\d{3,}@\d+\.\d+\.\d+\b")
RULE_RE = re.compile(r"\bR-\d{3,}\b")
CONSTRAINT_RE = re.compile(r"\bADR-\d{3,}/C-\d{3,}\b")


def front_matter(path):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if not text.startswith("---"):
            return None
        fm = yaml.safe_load(text.split("---", 2)[1])
    except (OSError, yaml.YAMLError, IndexError):
        return None
    return fm if isinstance(fm, dict) else None


def load_truth(product_dir):
    """Requirements, rules and architecture front matter on the default branch, by ID."""
    def by_id(pattern):
        out = {}
        for path in sorted(glob.glob(os.path.join(product_dir, pattern), recursive=True)):
            fm = front_matter(path)
            if fm and isinstance(fm.get("id"), str):
                out[fm["id"]] = fm
        return out
    return {"reqs": by_id("requirements/**/REQ-*.md"), "rules": by_id("knowledge/rules/**/R-*.md"),
            "arch": by_id("architecture/**/*.md")}


def live_acs(req):
    return [ac["id"] for ac in req.get("acceptance_criteria") or []
            if isinstance(ac, dict) and ac.get("status") != "retired"]


def accepted_qas_for(truth, req_id):
    return any(a.get("req") == req_id and a.get("status") == "accepted" and str(a.get("id", "")).startswith("QAS-")
               for a in truth["arch"].values())


def readiness(truth, kind, body, operator):
    """(status, details). Details hold the parsed IDs and the blockers, all harness text."""
    blockers, acs, reqs, versions = [], [], [], sorted(set(IF_RE.findall(body)))
    work = (KIND_RE.search(body).group(1) if KIND_RE.search(body) else "feature") if kind == "implement" else kind
    if not operator:
        blockers.append("the ticket was not opened by an operator (S-BA-015)")
    if kind == "implement" and work == "feature":
        named = sorted(set(AC_RE.findall(body)))
        whole = sorted(set(REQ_RE.findall(body)))
        reqs = sorted({a.split("/")[0] for a in named} | set(whole))
        if not reqs:
            blockers.append("the ticket names no requirement or AC (REQ-n or REQ-n/AC-k)")
        for rid in reqs:
            req = truth["reqs"].get(rid)
            if req is None:
                blockers.append(f"{rid} does not exist on main")
                continue
            if req.get("status") != "ready":
                blockers.append(f"{rid} is {req.get('status')}, not ready (S-BA-019)")
            live = live_acs(req)
            mine = [a for a in named if a.startswith(rid + "/")] or (live if rid in whole else [])
            for ac in mine:
                if ac not in live:
                    blockers.append(f"{ac} is retired or does not exist")
                elif ac not in acs:
                    acs.append(ac)
            for qid in [rid] * (req.get("type") == "quality") + list(req.get("quality") or []):
                if not accepted_qas_for(truth, qid):
                    blockers.append(f"{qid} has no accepted QAS, so the design of {rid} is pending (S-ARCH-015)")
    elif kind == "fix":
        targets = AC_RE.findall(body) + RULE_RE.findall(body) + CONSTRAINT_RE.findall(body)
        ok = False
        for t in targets:
            if "/AC-" in t:
                req = truth["reqs"].get(t.split("/")[0]) or {}
                ok |= req.get("status") == "ready" and t in live_acs(req)
            elif t.startswith("R-"):
                ok |= (truth["rules"].get(t) or {}).get("status") == "active"
            else:
                ok |= (truth["arch"].get(t.split("/")[0]) or {}).get("status") == "accepted"
        if not ok:
            blockers.append("the ticket names no live target: a ready AC, an active rule or an accepted ADR constraint")
    for v in versions:
        iid, num = v.split("@")
        found = [x for x in (truth["arch"].get(iid) or {}).get("versions") or [] if isinstance(x, dict)
                 and x.get("version") == num]
        if not found or found[0].get("status") not in ("approved", "deprecated"):
            blockers.append(f"{v} is not an approved or deprecated interface version (S-ARCH-011)")
    status = "waiting" if blockers else "ready"
    return status, {"work": work, "acs": acs, "reqs": reqs, "interfaces": versions, "blockers": blockers}


def bundle(data, product_dir, code_map, areas):
    run = data["run"]
    kind = run.get("ticket_kind")
    if kind not in KINDS:
        raise HarnessError("input_invalid", "run.ticket_kind is not implement, fix or bootstrap")
    issue = data["untrusted"]["issue"]
    operator = bool(issue.get("author_is_operator"))
    body = (issue.get("body") or "") if operator else ""
    m = AREA_RE.search(body)
    area = m.group(1) if m else None
    status, details = readiness(load_truth(product_dir), kind, body, operator)
    entry = (code_map["areas"].get(area) if area else None)
    if area is None or area not in areas:
        details["blockers"].insert(0, "the ticket names no valid area (a line `Area: <key>` from .staff/areas.yml)")
        status = "waiting"
    elif entry is None and kind != "bootstrap":
        details["blockers"].insert(0, f"area {area} has no entry in .staff/code.yml (S-DEV-004)")
        status = "waiting"
    data["developer"] = {
        "area": area,
        "ticket_kind": kind,
        "work": details.pop("work"),
        "readiness": dict(status=status, **details),
        "code_map_entry": entry,
        "code_map_path": ".staff/code.yml",
    }
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", required=True, help="the build_input.py output; rewritten in place")
    ap.add_argument("--product-dir", required=True)
    ap.add_argument("--code-map-schema", required=True)
    ap.add_argument("--areas", required=True, help="product .staff/areas.yml")
    ap.add_argument("--meta-out", help="also write the developer section alone, for the write stage")
    args = ap.parse_args()
    from contract import load_areas
    data = load_json(args.input, "input_invalid")
    code_map = load_code_map(os.path.join(args.product_dir, ".staff", "code.yml"), args.code_map_schema)
    bundle(data, args.product_dir, code_map, load_areas(args.areas))
    write_json(args.input, data)
    if args.meta_out:
        dev = data["developer"]
        write_json(args.meta_out, {k: dev[k] for k in ("area", "ticket_kind", "work", "readiness", "code_map_entry")})
    r = data["developer"]["readiness"]
    print(f"developer: area={data['developer']['area']} kind={data['developer']['ticket_kind']} "
          f"work={data['developer']['work']} readiness={r['status']} blockers={len(r['blockers'])}")


if __name__ == "__main__":
    run_main(main)
