"""test-gen fetch step (S-QA-017): add readiness and the layer's test-map entry to the input.

Reads the input file from build_input.py --agent test-gen-api and the product checkout at the
default branch (truth). Writes the input back with a `qa` section:
- the area and layer, parsed from the operator's ticket body only (`Area: <key>`, `Layer: api`;
  the layer defaults to the agent's own);
- the readiness result: the Developer's rules (dev_bundle.readiness) for the REQ, AC and IF
  references in the body, so QA cites only ready ACs and approved versions (S-QA-010);
- the area's layer entry from `.staff/tests.yml` (S-QA-005), and the area's code-map entry for its
  guard patterns and generators. Without the test-map entry the run fails closed: readiness is
  `waiting` with that blocker (S-QA-005).
"""
import argparse
import os
import re

from code_map import load_code_map
from common import HarnessError, load_json, run_main, write_json
from dev_bundle import AREA_RE, load_truth, readiness
from test_map import LAYERS, layer_entry, load_test_map

LAYER_RE = re.compile(r"(?im)^[\s>*_-]*layer[\s*_]*:[\s*_]*`?(unit|api|ui)`?")
AGENT_LAYER = {"test-gen-api": "api"}


def bundle(data, product_dir, test_map, code_map, areas, agent="test-gen-api"):
    issue = data["untrusted"]["issue"]
    operator = bool(issue.get("author_is_operator"))
    body = (issue.get("body") or "") if operator else ""
    m = AREA_RE.search(body)
    area = m.group(1) if m else None
    lm = LAYER_RE.search(body)
    layer = lm.group(1) if lm else AGENT_LAYER[agent]
    status, details = readiness(load_truth(product_dir), "implement", body, operator)
    details.pop("work", None)
    entry = layer_entry(test_map, area, layer) if area else None
    if area is None or area not in areas:
        details["blockers"].insert(0, "the ticket names no valid area (a line `Area: <key>` from .staff/areas.yml)")
        status = "waiting"
    elif layer != AGENT_LAYER[agent]:
        details["blockers"].insert(0, f"the ticket asks for the {layer} layer; this agent writes {AGENT_LAYER[agent]} tests")
        status = "waiting"
    elif entry is None:
        details["blockers"].insert(0, f"area {area} has no {layer} entry in .staff/tests.yml (S-QA-005)")
        status = "waiting"
    data["qa"] = {
        "area": area,
        "layer": layer,
        "readiness": dict(status=status, **details),
        "test_map_entry": entry,
        "test_map_path": ".staff/tests.yml",
        "code_map_entry": (code_map["areas"].get(area) if area else None),
    }
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", required=True, help="the build_input.py output; rewritten in place")
    ap.add_argument("--product-dir", required=True)
    ap.add_argument("--test-map-schema", required=True)
    ap.add_argument("--code-map-schema", required=True)
    ap.add_argument("--areas", required=True, help="product .staff/areas.yml")
    ap.add_argument("--agent", choices=sorted(AGENT_LAYER), default="test-gen-api")
    ap.add_argument("--meta-out", help="also write the qa section alone, for the later jobs")
    args = ap.parse_args()
    from contract import load_areas
    data = load_json(args.input, "input_invalid")
    if data.get("kind") != "test_gen_input":
        raise HarnessError("input_invalid", "not a test-gen input file")
    test_map = load_test_map(os.path.join(args.product_dir, ".staff", "tests.yml"), args.test_map_schema)
    code_map = load_code_map(os.path.join(args.product_dir, ".staff", "code.yml"), args.code_map_schema)
    bundle(data, args.product_dir, test_map, code_map, load_areas(args.areas), args.agent)
    write_json(args.input, data)
    if args.meta_out:
        write_json(args.meta_out, data["qa"])
    qa = data["qa"]
    print(f"qa: area={qa['area']} layer={qa['layer']} readiness={qa['readiness']['status']} "
          f"blockers={len(qa['readiness']['blockers'])}")


if __name__ == "__main__":
    run_main(main)
