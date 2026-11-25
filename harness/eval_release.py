"""Later review of stray escalations (S-GEN-041): release them for the human, then the task retires.

For one scored task, returns the defect items and design requests that matched no planted trap: their
target, kind or need, text and evidence, nothing else from the task. The caller retires the task in the
same step, because an item may hint at what was planted. The release is redaction-checked before anyone
sees it (S-SEC-004).

  eval_release.py items  --task T --validated V --out items.json     one task's stray items
  eval_release.py render --items DIR --out release.md                 the human's review page
"""
import argparse
import glob
import os

from common import load_json, run_main, write_json
from eval_score import escalations, trap_matches

TEXT_MAX = 2000


def stray_items(task, validated):
    traps = task.get("trap") or []
    out = []
    for item in escalations(validated):
        if any(trap_matches(t, item) for t in traps):
            continue
        is_defect = "kind" in item
        out.append({
            "type": "defect_item" if is_defect else "design_request",
            "target": item.get("target"),
            "kind" if is_defect else "need": item.get("kind") if is_defect else item.get("need"),
            "text": str(item.get("text") if is_defect else item.get("missing") or "")[:TEXT_MAX],
            "evidence_refs": [str(r)[:200] for r in (item.get("evidence_refs") or [])][:10],
        })
    return out


def cmd_items(args):
    task = load_json(args.task, "input_invalid")
    validated = load_json(args.validated, "artifact_missing")
    items = stray_items(task, validated)
    write_json(args.out, {"task_kind": task["kind"], "items": items})
    print(f"stray items: {len(items)}")


def render(groups):
    lines = ["### Stray escalations for your review (S-GEN-041)", "",
             "Each item below matched no planted problem, so the script counted it as a false escalation. "
             "Its task is retired, so reading it doesn't leak anything still in the set. For each item, say "
             "whether it is a **real defect** (in our requirements or architecture: we file it) or **noise** "
             "(an overreach by the Developer).", ""]
    n = 0
    for g in groups:
        for it in g["items"]:
            n += 1
            what = it.get("kind") or it.get("need")
            lines += [f"**{n}. {it['type'].replace('_', ' ')}, `{what}`, on `{it['target']}`** (a {g['task_kind']} task)", "",
                      "> " + it["text"].replace("\n", "\n> "), ""]
            if it["evidence_refs"]:
                lines += ["Evidence: " + ", ".join(f"`{r}`" for r in it["evidence_refs"]), ""]
    if not n:
        lines.append("No stray items in this run.")
    return "\n".join(lines) + "\n"


def cmd_render(args):
    groups = [load_json(p, "artifact_missing") for p in sorted(glob.glob(os.path.join(args.items, "*.json")))]
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(render(groups))
    print(f"rendered {sum(len(g['items']) for g in groups)} items")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("items")
    i.add_argument("--task", required=True)
    i.add_argument("--validated", required=True)
    i.add_argument("--out", required=True)
    r = sub.add_parser("render")
    r.add_argument("--items", required=True, help="directory of items JSON files")
    r.add_argument("--out", required=True)
    args = ap.parse_args()
    {"items": cmd_items, "render": cmd_render}[args.cmd](args)


if __name__ == "__main__":
    run_main(main)
