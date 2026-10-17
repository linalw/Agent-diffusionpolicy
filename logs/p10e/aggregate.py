#!/usr/bin/env python3
"""P10-E aggregate: per-run census + class shares over the listed logs."""
from __future__ import annotations

import sys
sys.path.insert(0, ".")
from census import parse, pair_attempts

LOGS = [
    ("p10c/10_armA_diag", "A", 5),
    ("p10c/20_armB_1", "B", 5),
    ("p10c/22_armB_diag", "B", 5),
    ("p10c/50_seed11_A", "A", 11),
    ("p10c/51_seed11_B", "B", 11),
    ("p10c/52_seed23_A", "A", 23),
    ("p10c/53_seed23_B", "B", 23),
    ("p10c2/61_seed5_B_gate", "Bgate", 5),
    ("p10c2/62_seed11_B_gate", "Bgate", 11),
    ("p10c2/63_seed23_B_gate", "Bgate", 23),
]

ROOT = "../"

print(f"{'run':28s} {'arm':6s} {'seed':4s} {'ok':>3s} {'carried':>7s} {'nograsp':>7s} "
      f"{'okSpan':>7s} {'carSpan':>7s} {'ngSpan':>7s} {'ngShare%':>8s}")
tot = {"ok": 0, "carried": 0, "nograsp": 0, "okSpan": 0.0, "carSpan": 0.0, "ngSpan": 0.0}
ng_by_side = {"left": 0, "right": 0}
ng_by_species = {}
carried_by_side = {"left": 0, "right": 0}
for rel, arm, seed in LOGS:
    path = ROOT + rel + ".log"
    lines, attempts, rows = parse(path)
    out = pair_attempts(attempts, rows)
    ok = carried = nograsp = 0
    okSpan = carSpan = ngSpan = 0.0
    for num in sorted(out):
        r = out[num]
        span = r.get("sim", 0.0)
        if r.get("grasped") and r.get("placed"):
            ok += 1
            okSpan += span
        elif r.get("grasped") and not r.get("placed"):
            carried += 1
            carSpan += span
            carried_by_side[r["side"]] += 1
        elif not r.get("grasped"):
            nograsp += 1
            ngSpan += span
            ng_by_side[r["side"]] += 1
            key = (r["species"], r["grade"], r["side"])
            ng_by_species[key] = ng_by_species.get(key, 0) + 1
    failSpan = carSpan + ngSpan
    share = 100.0 * ngSpan / failSpan if failSpan > 0 else 0.0
    print(f"{rel:28s} {arm:6s} {seed:4d} {ok:3d} {carried:7d} {nograsp:7d} "
          f"{okSpan:7.1f} {carSpan:7.1f} {ngSpan:7.1f} {share:8.1f}")
    tot["ok"] += ok
    tot["carried"] += carried
    tot["nograsp"] += nograsp
    tot["okSpan"] += okSpan
    tot["carSpan"] += carSpan
    tot["ngSpan"] += ngSpan

failSpan = tot["carSpan"] + tot["ngSpan"]
print()
print(f"TOTAL ok={tot['ok']} carried-not-placed={tot['carried']} no-grasp={tot['nograsp']}")
print(f"  span attempt-s: ok={tot['okSpan']:.1f} carried={tot['carSpan']:.1f} "
      f"no-grasp={tot['ngSpan']:.1f}")
print(f"  no-grasp share of failure mass: {100.0*tot['ngSpan']/failSpan:.1f}% "
      f"({tot['ngSpan']:.0f} of {failSpan:.0f} attempt-s)")
print(f"  no-grasp share of failure count: "
      f"{100.0*tot['nograsp']/(tot['nograsp']+tot['carried']):.1f}%")
print(f"  no-grasp by side: {ng_by_side}")
print(f"  carried by side: {carried_by_side}")
print("  no-grasp by species/grade/side:")
for k in sorted(ng_by_species):
    print(f"    {k[0]:10s} {k[1]} {k[2]:5s}: {ng_by_species[k]}")
