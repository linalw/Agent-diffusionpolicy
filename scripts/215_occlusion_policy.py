"""P34 phase 1: the policy's first-view evidence vs the occlusion band (offline).

    python3 scripts/215_occlusion_policy.py
    python3 scripts/215_occlusion_policy.py --glob 'logs/w7/B_ab/*.log' --json out.json

Parses the direct-policy rollout logs (`110_rl_rollout.py`), whose per-episode
lines carry the selected fruit's reset along-position (`y=+0.5xx`), the arm, the
class and the outcome, plus the intercept trigger's fire numbers. Then asks:

  * where the episodes *start* relative to the +Y belt's occlusion band
    (`scripts/212_occlusion_map.py`: fully hidden y = 0.52..0.87, the visible
    fraction crossing 0.99 at y = 0.45);
  * whether the episodes that start hidden do worse than the ones that start
    visible (the only contrast the shipped reset gives);
  * how many model calls (4 mm of belt travel each, P31 anatomy) elapse before
    the fruit is visible, and where the trigger fires relative to the band.

This is a correlation on existing logs, not an A/B: the reset position is the
feed schedule's backlog, so it is not randomised (the caveat is printed).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re

import numpy as np

RESET = re.compile(
    r"episode (\d+): (\w+) grade=(\w) d=([0-9.]+)cm bin=(\d) arm=(\w+) y=([+-][0-9.]+)"
)
OUTCOME = re.compile(
    r"episode (\d+): (\w+) d=([0-9.]+)cm bin=(\d) arm=(\w+) success=(\w+) "
    r"grasped=(\w+) placed=(\w+) ticks=(\d+)"
)
FIRE = re.compile(r"intercept trigger \(dy=([0-9.]+)cm, dx=([-0-9.]+)cm, t_arrive=([0-9.]+)s")
#: The analytic band from `scripts/212_occlusion_map.py` (x=0.28, d=58 mm).
BAND = dict(vis99=0.450, near50=0.485, near01=0.515, far01=0.870, far99=0.950)
BELT_SPEED = 0.12
CALL_MM = 4.0  # mm of belt travel per model call (P31 anatomy)


def parse(path):
    rows = []
    cur = {}
    try:
        text = open(path, encoding="utf-8", errors="ignore").read().splitlines()
    except OSError:
        return rows
    for line in text:
        m = RESET.search(line)
        if m:
            cur = dict(ep=int(m.group(1)), species=m.group(2), grade=m.group(3),
                       d=float(m.group(4)) / 100.0, arm=m.group(6),
                       y0=float(m.group(7)), log=os.path.basename(path))
            continue
        m = OUTCOME.search(line)
        if m and cur and int(m.group(1)) == cur["ep"]:
            cur.update(success=m.group(6) == "True", grasped=m.group(7) == "True",
                       placed=m.group(8) == "True", ticks=int(m.group(9)))
            f = FIRE.search(line)
            if f:
                cur.update(fire_dy=float(f.group(1)) / 100.0,
                           fire_dx=float(f.group(2)) / 100.0)
            rows.append(cur)
            cur = {}
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", action="append", default=[])
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    globs = args.glob or ["logs/p31/ab/*.log"]
    rows = []
    for g in globs:
        for path in sorted(glob.glob(g)):
            rows.extend(parse(path))
    if not rows:
        print("no episodes parsed")
        return 1
    y0 = np.array([r["y0"] for r in rows])
    ok = np.array([r["success"] for r in rows])
    placed = np.array([r["placed"] for r in rows])
    print(f"# {len(rows)} episodes from {len(set(r['log'] for r in rows))} logs")
    print(f"# reset along y: min {y0.min():+.3f} p10 {np.percentile(y0,10):+.3f} "
          f"p50 {np.median(y0):+.3f} p90 {np.percentile(y0,90):+.3f} max {y0.max():+.3f}")
    print(f"# band (analytic): fully hidden {BAND['near01']:.2f}..{BAND['far01']:.2f}, "
          f"vis>=0.99 below {BAND['vis99']:.2f}")
    for arm in ("left", "right", "all"):
        sel = [r for r in rows if arm == "all" or r["arm"] == arm]
        if not sel:
            continue
        a = np.array([r["y0"] for r in sel])
        s = np.array([r["success"] for r in sel])
        print(f"# arm={arm}: n={len(sel)} reset y p50 {np.median(a):+.3f} "
              f"({np.percentile(a,10):+.3f}..{np.percentile(a,90):+.3f}), "
              f"success {s.mean()*100:.0f}%")

    # The contrast the shipped reset gives: starts visible vs starts hidden.
    print("\n## The reset position vs the outcome")
    print("| start | y0 rule | n | success | placed | grasped-not-placed |")
    print("| --- | --- | --- | --- | --- | --- |")
    groups = [
        ("visible", y0 < BAND["vis99"]),
        ("edge", (y0 >= BAND["vis99"]) & (y0 < BAND["near01"])),
        ("hidden", y0 >= BAND["near01"]),
    ]
    table = []
    for name, mask in groups:
        n = int(mask.sum())
        if n == 0:
            continue
        s = ok[mask].mean()
        p = placed[mask].mean()
        cnp = np.array([r["grasped"] and not r["placed"] for r in rows])[mask].mean()
        table.append(dict(group=name, n=n, success=float(s), placed=float(p), cnp=float(cnp)))
        print(f"| {name} | {'y0<0.45' if name=='visible' else ('0.45<=y0<0.515' if name=='edge' else 'y0>=0.515')} "
              f"| {n} | {s*100:.0f}% | {p*100:.0f}% | {cnp*100:.0f}% |")
    # A second cut at the fully-hidden edge (0.52) and at the far edge (0.87).
    print("\n## Sensitivity: cut at 0.52 (fully hidden) and 0.47")
    for cut in (0.47, 0.52, 0.55):
        lo = y0 < cut
        print(f"y0<{cut:.2f}: n={int(lo.sum())} success {ok[lo].mean()*100:.0f}% | "
              f"y0>={cut:.2f}: n={int((~lo).sum())} success {ok[~lo].mean()*100:.0f}%")

    # How long the fruit is hidden from the reset (travel and model calls).
    print("\n## The hidden run from the reset to the visibility onset")
    hidden_m = np.maximum(0.0, y0 - BAND["vis99"])
    print(f"travel hidden: p50 {np.median(hidden_m):.3f} m = {np.median(hidden_m)/BELT_SPEED:.2f} s "
          f"= {np.median(hidden_m)*1000/CALL_MM:.0f} model calls; "
          f"p90 {np.percentile(hidden_m,90):.3f} m / {np.percentile(hidden_m,90)*1000/CALL_MM:.0f} calls")
    print(f"episodes whose reset is inside the fully-hidden band (y0>=0.515): "
          f"{int((y0>=BAND['near01']).sum())}/{len(y0)} = {(y0>=BAND['near01']).mean()*100:.0f}%")

    # Arm-stratified (the arm and the reset position are confounded: the left
    # lane's fruit arrive slightly higher upstream).
    print("\n## Arm-stratified: the reset position vs success")
    for arm in ("left", "right"):
        sel = [r for r in rows if r["arm"] == arm]
        if not sel:
            continue
        a = np.array([r["y0"] for r in sel])
        s = np.array([r["success"] for r in sel])
        med = float(np.median(a))
        lo = a < med
        print(f"arm={arm}: y0<{med:.3f} n={int(lo.sum())} success {s[lo].mean()*100:.0f}% | "
              f"y0>={med:.3f} n={int((~lo).sum())} success {s[~lo].mean()*100:.0f}%")

    # The analytic visible fraction at each episode's reset (x=0.28, d=58 mm).
    print("\n## The analytic visibility at the reset position")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "occlusion_map", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "212_occlusion_map.py"))
    om = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(om)
    vis0 = np.array([om.visible_fraction(0.28, float(r["y0"]), 0.058)["vis"] for r in rows])
    print(f"visible fraction at the reset: p50 {np.median(vis0):.2f} "
          f"p10 {np.percentile(vis0,10):.2f} p90 {np.percentile(vis0,90):.2f}; "
          f"fully hidden (<0.01) {int((vis0 < 0.01).sum())}/{len(vis0)} = "
          f"{(vis0 < 0.01).mean()*100:.0f}%, fully visible (>0.99) "
          f"{int((vis0 > 0.99).sum())}/{len(vis0)}")

    fire = np.array([r["fire_dy"] for r in rows if "fire_dy" in r])
    if len(fire):
        print(f"\ntrigger fire dy: n={len(fire)} min {fire.min():+.3f} p50 {np.median(fire):+.3f} "
              f"max {fire.max():+.3f} m; in the band (0.45..0.95): "
              f"{int(((fire>=BAND['vis99']) & (fire<=BAND['far99'])).sum())}/{len(fire)}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(dict(n=len(rows), table=table,
                           reset_y=y0.tolist(),
                           outcomes=[r["success"] for r in rows]), fh, indent=1)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
