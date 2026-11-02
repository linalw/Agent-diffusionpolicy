"""P94 census: the commanded-jump table, the per-leg offset table, the classes.

    python3 logs/p94/census.py            # -> logs/p94/census.txt
    python3 logs/p94/census.py --json     # the same numbers, machine-readable

Read-only: opens the records named on the command line (or the phase's default
cell set), prints tables. No simulator.

The **reading** is `_gripper_offset` as the carry saw it (`[diag] carry-assist
... |offset|=`), and the **applied jump** is `|jaw_target - cmd_centre|` from the
*same* row - the distance the carry actually commanded the arm away from the
pads it is carrying. Before P94 the applied jump equals the reading on every leg;
the fix makes it 0 on every leg whose reading is above the bound (and leaves the
reading itself untouched, because the reading is the same physical quantity).

Attempt association is `logs/p92/census.py`'s own loop (attempt start =
`[task] target ... with <arm> arm`, attempt end = `[biarm] result <arm> ...`,
per-arm leg buffer), with the `[diag] carry-assist` capture added. The
classifier is imported from `logs/p92/census.py` unchanged, so this phase's
`cnp` / `never_held` rows are the same object P92/P93 measured.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

#: `logs/p92/census.py` loaded **by path**: importing it as `census` would
#: collide with this file's own module name (both are `census.py`), and the
#: collision silently resolves to whichever was imported first.
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "p92_census", os.path.join(ROOT, "logs", "p92", "census.py")
)
p92 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p92)  # the classifier of record, unchanged

#: the applied-jump row: `jaw_target` and `cmd_centre` are printed to 4 dp in m.
OFFSET = re.compile(
    r"\[diag\] carry-assist (?P<arm>left|right) (?P<leg>\w+) tick (?P<tick>\d+): "
    r"cmd_centre=\[(?P<centre>[^\]]+)\] offset=\[(?P<offset>[^\]]+)\] "
    r"\|offset\|=(?P<mag>\d+) mm .*?jaw_target=\[(?P<target>[^\]]+)\]"
)

#: the phase's cell set: tag -> (seed, path, arm_class)
DEFAULT_CELLS = [
    ("C5", 5, "logs/p92/C5.log", "control"),
    ("T5", 5, "logs/p94/T5.log", "fix"),
    ("C6", 6, "logs/p92/C6.log", "control"),
    ("T6", 6, "logs/p94/T6.log", "fix"),
    ("C101", 101, "logs/p93/C101.log", "control"),
    ("T101", 101, "logs/p94/T101.log", "fix"),
    ("C202", 202, "logs/p93/C202.log", "control"),
    ("T202", 202, "logs/p94/T202.log", "fix"),
    ("N5", 5, "logs/p94/N5.log", "tree-check"),
    ("P5", 5, "logs/p94/P5.log", "post-flip"),
]


def _vec(text: str) -> list[float]:
    return [float(v) for v in text.replace(" ", "").split(",")]


def parse(path: str) -> dict:
    """`logs/p92/census.py`'s parse loop + the `[diag] carry-assist` capture."""
    with open(path, "r", errors="replace") as fh:
        lines = fh.readlines()
    attempts: list[dict] = []
    legs: dict[str, dict] = {"left": {}, "right": {}}
    cur: dict[str, dict | None] = {"left": None, "right": None}
    stats = None
    noelig = {"left": 0, "right": 0}
    acquired = {"left": 0, "right": 0}
    diverts: list[dict] = []
    for ln in lines:
        if m := p92.TARGET.search(ln):
            arm = m.group("arm")
            cur[arm] = {
                "fruit": m.group("fruit"), "grade": m.group("grade"),
                "dia_cm": float(m.group("dia")), "arm": arm,
                "legs": {}, "offsets": {}, "raw": {}, "x": None, "queue": None,
            }
            legs[arm] = cur[arm]["legs"]
            continue
        if m := OFFSET.search(ln):
            arm = m.group("arm")
            if cur[arm] is not None and int(m.group("tick")) == 0:
                centre = _vec(m.group("centre"))
                target = _vec(m.group("target"))
                cur[arm]["offsets"][m.group("leg")] = {
                    "mag": int(m.group("mag")),
                    "offset": _vec(m.group("offset")),
                    "applied": sum((a - b) ** 2 for a, b in zip(target, centre)) ** 0.5,
                    "centre": centre,
                    "target": target,
                }
            continue
        if m := p92.WAITX.search(ln):
            for arm in ("left", "right"):
                if cur[arm] is not None and cur[arm]["x"] is None:
                    cur[arm]["x"] = float(m.group("x"))
            continue
        if m := p92.HANDOVER.search(ln):
            for arm in ("left", "right"):
                if cur[arm] is not None and cur[arm]["queue"] is None:
                    cur[arm]["queue"] = int(m.group("q"))
            continue
        if m := p92.CARRY.search(ln):
            arm = m.group("arm")
            if cur[arm] is not None:
                cur[arm]["legs"][m.group("leg")] = p92.parse_leg(m.group("body"))
                cur[arm]["raw"][m.group("leg")] = m.group("body")
            continue
        if m := p92.RESULT.search(ln):
            arm = m.group("arm")
            rec = cur[arm] or {
                "fruit": m.group("fruit"), "grade": "?", "dia_cm": None,
                "arm": arm, "legs": {}, "offsets": {}, "raw": {}, "x": None,
                "queue": None,
            }
            rec.update(
                index=int(m.group("index")),
                grasped=m.group("grasped") == "True",
                placed=m.group("placed") == "True",
                lift=float(m.group("lift")),
                force=float(m.group("force")),
                span=float(m.group("span")),
                notes=m.group("notes"),
            )
            cls, detail, ev = p92.classify(rec)
            rec.update(cls=cls, detail=detail, ev=ev, log=os.path.basename(path))
            attempts.append(rec)
            cur[arm] = None
            continue
        if m := p92.NOELIG.search(ln):
            noelig[m.group("arm")] += 1
            continue
        if m := p92.ACQ.search(ln):
            acquired[m.group("arm")] += 1
            continue
        if m := p92.DIVERT.search(ln):
            diverts.append({"fruit": m.group("fruit"), "index": int(m.group("index")),
                            "n": int(m.group("n"))})
            continue
        if m := p92.STATS.search(ln):
            stats = {"attempts": int(m.group("att")), "successes": int(m.group("ok")),
                     "diverted": int(m.group("div"))}
            continue
    return {
        "path": path, "attempts": attempts, "stats": stats, "noelig": noelig,
        "acq": acquired, "diverts": diverts,
    }


def leg_rows(tag: str, seed: int, arm_class: str, path: str) -> list[dict]:
    """One row per carry leg that printed a reading, with its attempt's outcome."""
    rec = parse(path)
    rows = []
    for n, att in enumerate(rec["attempts"]):
        for leg, off in att["offsets"].items():
            rows.append({
                "cell": tag, "seed": seed, "arm_class": arm_class,
                "attempt": n, "fruit": att["fruit"], "arm": att["arm"],
                "leg": leg, "read": off["mag"], "applied": off["applied"],
                "class": att["cls"], "placed": att["placed"],
                "log": att["log"],
            })
    return rows


def _p(vals: list[float], q: float):
    if not vals:
        return None
    s = sorted(vals)
    return s[min(len(s) - 1, int(q * len(s)))]


def summary(rows: list[dict]) -> dict:
    reads = [r["read"] for r in rows]
    apps = [r["applied"] for r in rows]
    return {
        "n": len(rows),
        "read_min": min(reads) if reads else None,
        "read_p50": _p(reads, 0.5), "read_p90": _p(reads, 0.9),
        "read_max": max(reads) if reads else None,
        "applied_max": max(apps) if apps else None,
        "applied_p50": _p(apps, 0.5),
        "over_bound": sum(1 for r in rows if r["read"] > BOUND * 1000),
        "moved": sum(1 for r in rows if r["applied"] > 1.0 and r["read"] > BOUND * 1000),
        "guarded": sum(1 for r in rows if r["read"] > BOUND * 1000 and r["applied"] <= 1.0),
    }


BOUND = 0.20  # the measured cell's bound; the census is read against it


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--cells", default="", help="comma-separated tags (default: all)")
    args = ap.parse_args()
    keep = {t for t in args.cells.split(",") if t} if args.cells else None

    out: dict = {"cells": {}, "legs": []}
    for tag, seed, path, arm_class in DEFAULT_CELLS:
        if keep is not None and tag not in keep:
            continue
        if not os.path.exists(os.path.join(ROOT, path)):
            out["cells"][tag] = {"missing": path}
            continue
        rows = leg_rows(tag, seed, arm_class, os.path.join(ROOT, path))
        rec = parse(os.path.join(ROOT, path))
        counts: dict[str, int] = {}
        for att in rec["attempts"]:
            counts[att["cls"]] = counts.get(att["cls"], 0) + 1
        out["cells"][tag] = {
            "seed": seed, "arm_class": arm_class, "path": path,
            "attempts": len(rec["attempts"]),
            "placed": sum(1 for a in rec["attempts"] if a["placed"]),
            "classes": counts,
            "starved": rec["noelig"], "diverted": len(rec["diverts"]),
            "offsets": summary(rows),
            "stats": rec["stats"],
        }
        out["legs"].extend(rows)

    if args.json:
        print(json.dumps(out, indent=1))
        return 0

    print("=" * 108)
    print("P94 CENSUS - the commanded-jump table (reading vs applied jump), per cell")
    print("=" * 108)
    print("  read   = |_gripper_offset| as the carry saw it (`[diag] carry-assist`)")
    print(f"  bound  = {BOUND * 1000:.0f} mm  (the phase's registered FRUIT_CARRY_OFFSET_MAX)")
    print("  applied= |jaw_target - cmd_centre|: what the carry actually commanded")
    print("=" * 108)
    head = (f"{'cell':<5} {'seed':>4} {'kind':<10} {'att':>4} {'ok':>3} {'legs':>4} "
            f"{'read p50':>8} {'read max':>8} {'>bound':>6} {'applied max':>11} {'guarded':>7} "
            f"{'cnp':>4} {'never':>5}")
    print(head)
    print("-" * 108)
    for tag, cell in out["cells"].items():
        if "missing" in cell:
            print(f"{tag:<5} {'-':>4} {'MISSING':<10} {cell['missing']}")
            continue
        o = cell["offsets"]
        print(f"{tag:<5} {cell['seed']:>4} {cell['arm_class']:<10} {cell['attempts']:>4} "
              f"{cell['placed']:>3} {o['n']:>4} "
              f"{o['read_p50'] if o['read_p50'] is not None else -1:>8.0f} "
              f"{o['read_max'] if o['read_max'] is not None else -1:>8.0f} "
              f"{o['over_bound']:>6} {o['applied_max'] if o['applied_max'] is not None else -1:>11.3f} "
              f"{o['guarded']:>7} "
              f"{cell['classes'].get('cnp', 0):>4} {cell['classes'].get('never_held', 0):>5}")

    print()
    print("=" * 108)
    print("THE PER-LEG TABLE  (the reading, and what the carry commanded from it)")
    print("=" * 108)
    print(f"{'cell':<5} {'att':>3} {'arm':<5} {'leg':<10} {'read mm':>8} {'applied mm':>10} "
          f"{'guard':>5} {'class':<10} {'fruit':<10}")
    print("-" * 108)
    for r in out["legs"]:
        guard = "YES" if (r["read"] > BOUND * 1000 and r["applied"] <= 1.0) else "-"
        flag = "  <== DEFECT" if r["read"] > BOUND * 1000 else ""
        print(f"{r['cell']:<5} {r['attempt']:>3} {r['arm']:<5} {r['leg']:<10} "
              f"{r['read']:>8} {r['applied'] * 1000:>10.1f} {guard:>5} {r['class']:<10} "
              f"{r['fruit']:<10}{flag}")

    print()
    print("=" * 108)
    print("BEFORE vs AFTER, pooled over the four seeds (controls = the pre-fix records)")
    print("=" * 108)
    before = [r for r in out["legs"] if r["arm_class"] == "control"]
    after = [r for r in out["legs"] if r["arm_class"] == "fix"]
    for label, rows in (("control (pre-fix)", before), ("fix", after)):
        s = summary(rows)
        if not s["n"]:
            print(f"  {label:<20} (no rows)")
            continue
        print(f"  {label:<20} legs={s['n']:>4}  read {s['read_min']}-{s['read_max']} mm "
              f"(p50 {s['read_p50']})  applied max {s['applied_max'] * 1000:.1f} mm  "
              f">bound {s['over_bound']}  guarded {s['guarded']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
