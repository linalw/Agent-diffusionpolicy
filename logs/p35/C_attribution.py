#!/usr/bin/env python3
"""P35 phase 2: attribute the band census to the occluder (read-only).

    python3 logs/p35/C_attribution.py --dir logs/p35/C_ab --a A --b B

The `[park] call` rows are the band census (`FRUIT_PARK_DIAG=1`): one row per
model call whose target along is in **+0.30..+0.40** (the P0 census band), with
the target's pixels (`px`), its depth-corrected ratio (`rel`), the inactive arm's
pixels inside the target's projected-disc bbox (`arm_px`, `frac`) and the bbox's
top-3 instances (`top`). Sentinels, both in the rows and in the `[park] episode`
summary: `px=0` = the target mask is empty (fully hidden) and therefore `top=-`
(no bbox); `rel=-1` / `frac=-1` = the ratio is undefined (no target pixels / no
bbox), and a summary `min_rel=-1` means **no band call had a usable ratio**
(the target was never visible in the band). An **undefined `frac` never passes
the arm term**: the term requires at least one call with a defined `frac` and
`max(frac) < 0.10`, so a never-visible episode fails it (counting `-1` as small
would let the worst case - the whole fruit hidden - pass the arm test).

This script answers the question the manipulation check's *visibility* clause
raises: when the target's mask stays below 0.85 of the running maximum, **who
holds the pixels** - the parked arm, the +Y output belt/frame, or the main belt
- and does that differ between the arms. It attributes the *worst call that has
a bbox* (`px > 0`); a call with no target pixels has no bbox and is reported
separately as `never-visible`.
"""

from __future__ import annotations

import argparse
import glob
import os
import statistics as st
import re

CALL = re.compile(
    r"\[park\] call ep=(\d+) n=(\d+) along=(\S+) x=(\S+) px=(-?\d+) "
    r"disc=(\S+) vis=(\S+) rel=(\S+) arm_px=(-?\d+) tgt_px=(-?\d+) "
    r"frac=(\S+) ok=(-?\d+) top=(.*)$"
)
EP = re.compile(r"\[park\] episode (\d+) arm=(\w+) inactive=(\w+) park=(\S+)")


def owner(text: str) -> str:
    first = (text or "").split("|")[0].strip()
    if not first or first == "-":
        return "no-bbox"
    if "openarm_" in first:
        return "arm"
    if "OutputBeltP" in first:
        return "output-belt"
    if "Conveyor/Belt" in first:
        return "belt"
    if "/Fruits/" in first:
        return "target"
    return "other"


def scan(directory: str, label: str) -> dict:
    """{(run, episode): {...}} keyed by each row's **own** episode number.

    The per-call rows are printed *during* the episode, i.e. before the
    `[park] episode` summary row, so they cannot be attached by "the current
    episode"; both row types carry their episode explicitly.
    """
    eps: dict[tuple[int, int], dict] = {}
    for path in sorted(glob.glob(os.path.join(directory, f"{label}_*.log"))):
        stem = os.path.basename(path)[:-4]
        try:
            run = int(stem.rsplit("_", 1)[1])
        except (IndexError, ValueError):
            continue
        for line in open(path, encoding="utf-8", errors="replace"):
            m = CALL.search(line)
            if m:
                key = (run, int(m.group(1)))
                rec = eps.setdefault(key, {"arm": "", "inactive": "", "calls": []})
                try:
                    rec["calls"].append({
                        "along": float(m.group(3)), "x": float(m.group(4)),
                        "px": int(m.group(5)), "disc": float(m.group(6)),
                        "vis": float(m.group(7)), "rel": float(m.group(8)),
                        "arm_px": int(m.group(9)), "frac": float(m.group(11)),
                        "ok": int(m.group(12)), "top": m.group(13),
                    })
                except ValueError:
                    continue
                continue
            m = EP.search(line)
            if m:
                rec = eps.setdefault((run, int(m.group(1))),
                                     {"arm": "", "inactive": "", "calls": []})
                rec["arm"] = m.group(2)
                rec["inactive"] = m.group(3)
    return eps


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default="logs/p35/B_ab")
    ap.add_argument("--a", default="A")
    ap.add_argument("--b", default="B")
    args = ap.parse_args()

    for label in (args.a, args.b):
        eps = scan(args.dir, label)
        banded = {k: v for k, v in eps.items() if v["calls"] and v["inactive"]}
        print(f"== arm {label}: {len(banded)} episodes with a band census")
        for side in ("left", "right"):
            sel = {k: v for k, v in banded.items() if v["inactive"] == side}
            if not sel:
                continue
            arm_ok = sum(1 for v in sel.values()
                         if max(c["frac"] for c in v["calls"]) >= 0
                         and max(c["frac"] for c in v["calls"]) < 0.10)
            vis_ok = sum(1 for v in sel.values()
                         if min(c["rel"] for c in v["calls"]) >= 0.85)
            both = sum(1 for v in sel.values()
                       if max(c["frac"] for c in v["calls"]) >= 0
                       and max(c["frac"] for c in v["calls"]) < 0.10
                       and min(c["rel"] for c in v["calls"]) >= 0.85)
            print(f"  inactive={side:5s} n={len(sel)} | arm-term "
                  f"(max_frac<0.10, defined frac required) {arm_ok}/{len(sel)} | "
                  f"visibility-term (min_rel>=0.85) {vis_ok}/{len(sel)} | "
                  f"both {both}/{len(sel)}")
            tally: dict[str, int] = {}
            for v in sel.values():
                if min(c["rel"] for c in v["calls"]) >= 0.85:
                    continue  # visibility term passes
                vis = [c for c in v["calls"] if c["px"] > 0]
                if not vis:
                    tally["never-visible"] = tally.get("never-visible", 0) + 1
                    continue
                worst = min(vis, key=lambda c: c["rel"])
                key = owner(worst["top"])
                tally[key] = tally.get(key, 0) + 1
            if tally:
                print("      worst visible call's largest instance (the episodes "
                      "whose visibility term fails): "
                      + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())))
            fr = [c["frac"] for v in sel.values() for c in v["calls"]]
            rel = [c["rel"] for v in sel.values() for c in v["calls"]]
            print(f"      band calls: {len(fr)} | arm_frac median={st.median(fr):.3f} "
                  f"max={max(fr):.3f} | rel median={st.median(rel):.3f} "
                  f"min={min(rel):.3f} | px=0 calls "
                  f"{sum(1 for c in (c for v in sel.values() for c in v['calls']) if c['px'] == 0)}"
                  f"/{len(fr)}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
