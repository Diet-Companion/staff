"""Read the human-only contract files: governance/operators.yml (staff) and
.staff/areas.yml, .staff/product.yml and .staff/stages.yml (product). Stdlib only,
so the gate job needs no installs.

These readers accept only the simple shapes the contract defines
(governance/product-contract.md) and fail closed on anything else.

CLI:
  contract.py is-operator --operators F --login L      exit 0 if L is an operator
  contract.py check-product --product-yml F --endpoint E
  contract.py stage --stages-yml F --agent A --area R [--ceiling N]
                                                       print the effective stage (S-GEN-050)
"""
import argparse
import os
import re

from common import HarnessError, run_main

LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
AREA_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
AGENT_RE = re.compile(r"^[a-z0-9][a-z0-9/-]{0,63}$")
STAGES = (1, 2, 3, 4)


def _lines(path):
    """Yield (indent, text) for non-blank lines, with comments stripped."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read().splitlines()
    except OSError:
        raise HarnessError("contract_invalid", f"cannot read {path}") from None
    for line in raw:
        text = re.sub(r"(^|\s)#.*$", "", line).rstrip()
        if text.strip():
            yield len(text) - len(text.lstrip(" ")), text.strip()


def _block(path, key):
    """The lines under a top-level `key:`, as (indent, text)."""
    out, inside = [], False
    for indent, text in _lines(path):
        if indent == 0:
            inside = text == f"{key}:"
            continue
        if inside:
            out.append((indent, text))
    return out


def load_operators(path):
    """Operator GitHub logins from governance/operators.yml (S-GEN-071)."""
    logins = set()
    for _, text in _block(path, "operators"):
        m = re.fullmatch(r"-\s+github:\s*(\S+)", text)
        if not m or not LOGIN_RE.match(m.group(1)):
            raise HarnessError("contract_invalid", f"unexpected line in {path} operators")
        logins.add(m.group(1).lower())
    if not logins:
        raise HarnessError("contract_invalid", f"no operators in {path}")
    return logins


def load_areas(path):
    """Area keys from .staff/areas.yml (S-GEN-060), in file order."""
    block = _block(path, "areas")
    if not block:
        raise HarnessError("contract_invalid", f"no areas in {path}")
    key_indent = block[0][0]
    areas = []
    for indent, text in block:
        if indent != key_indent:
            continue
        m = re.fullmatch(r"([^:\s]+):", text)
        if not m or not AREA_RE.match(m.group(1)):
            raise HarnessError("contract_invalid", f"unexpected area key in {path}")
        areas.append(m.group(1))
    if len(set(areas)) != len(areas):
        raise HarnessError("contract_invalid", f"duplicate area key in {path}")
    return areas


def check_product(path, endpoint):
    """Fail closed unless residency is declared (S-DATA-001) and the model
    endpoint is the one this workflow calls (S-DATA-002)."""
    top = {}
    for indent, text in _lines(path):
        if indent == 0 and ":" in text:
            k, _, v = text.partition(":")
            top[k.strip()] = v.strip()
    if "residency" not in top:
        raise HarnessError("contract_invalid", "residency missing in product.yml (S-DATA-001)")
    residency = [t for _, t in _block(path, "residency")]
    declared = False
    for i, text in enumerate(residency):
        if text.startswith("regions:"):
            value = text.partition(":")[2].strip()
            following = residency[i + 1] if i + 1 < len(residency) else ""
            declared = value not in ("", "[]") or following.startswith("- ")
    if not declared:
        raise HarnessError("contract_invalid", "residency.regions missing in product.yml")
    if top.get("model_endpoint") != endpoint:
        raise HarnessError("contract_invalid", f"model_endpoint is not {endpoint} (S-DATA-002)")


def load_stages(path):
    """{agent: {area: stage}} from .staff/stages.yml (S-GEN-050). A missing file is empty."""
    if not os.path.exists(path):
        return {}
    block = _block(path, "stages")
    if not block:
        return {}
    stages, agent = {}, None
    for indent, text in block:
        if indent == block[0][0]:
            m = re.fullmatch(r"([^:\s]+):", text)
            if not m or not AGENT_RE.match(m.group(1)) or m.group(1) in stages:
                raise HarnessError("contract_invalid", f"unexpected agent key in {path} stages")
            agent = m.group(1)
            stages[agent] = {}
            continue
        m = re.fullmatch(r"([^:\s]+):\s*([0-9]+)", text)
        if agent is None or not m or not AREA_RE.match(m.group(1)) or int(m.group(2)) not in STAGES \
                or m.group(1) in stages[agent]:
            raise HarnessError("contract_invalid", f"unexpected stage line in {path}")
        stages[agent][m.group(1)] = int(m.group(2))
    return stages


def effective_stage(path, agent, area, ceiling=""):
    """The lowest of stages.yml and the demotion ceiling (S-GEN-050). Anything unset is stage 1.

    The ceiling is a CI variable the ops stage job writes; empty means none. A value that
    isn't a stage fails closed to 1, so a corrupted ceiling can never raise a stage.
    """
    stage = load_stages(path).get(agent, {}).get(area, 1)
    if ceiling.strip():
        cap = int(ceiling) if ceiling.strip().isdigit() else 1
        stage = min(stage, cap if cap in STAGES else 1)
    return stage


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    op = sub.add_parser("is-operator")
    op.add_argument("--operators", required=True)
    op.add_argument("--login", required=True)
    pr = sub.add_parser("check-product")
    pr.add_argument("--product-yml", required=True)
    pr.add_argument("--endpoint", required=True)
    st = sub.add_parser("stage")
    st.add_argument("--stages-yml", required=True)
    st.add_argument("--agent", required=True)
    st.add_argument("--area", required=True)
    st.add_argument("--ceiling", default="")
    args = ap.parse_args()
    if args.cmd == "is-operator":
        if args.login.lower() not in load_operators(args.operators):
            raise HarnessError("not_operator", "sender is not in governance/operators.yml")
        print("operator: yes")
    elif args.cmd == "stage":
        print(effective_stage(args.stages_yml, args.agent, args.area, args.ceiling))
    else:
        check_product(args.product_yml, args.endpoint)
        print("product contract: ok")


if __name__ == "__main__":
    run_main(main)
