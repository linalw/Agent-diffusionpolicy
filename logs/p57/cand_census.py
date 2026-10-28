"""P57 phase 1: the candidate census the `CandidateBoard` would run on.

Offline, read-only over logs that already exist. Parses the `[bed-sel]` blocks
(`FRUIT_BED_DIAG=1`, `tasks.py::bed_diag_report`) of the P56 corpus.

**The geometry that decides every number here.** The belt runs along **-Y** at
`0.12 m/s` (`cleated belt built: ... surface velocity -0.12 m/s`), releases are
placed at `along = spawn_y - min(late*v, 1.60)` (`fruits.py:2315`) and `spawn_y`
is `+0.68` while the catch floor is `+0.399`. So a fruit on the belt is always
**inside** the window (`<= 0.68 < pick_y+0.85`) and either

* at/above the floor -> **usable now** (`t_enter = 0`), or
* below the floor -> **leaving** the band (along decreases), so its time to
  enter is **infinite**, not `(floor - along)/v`.

The only finite arrival is therefore a **release**: the feeder's clock. A due
row lands at `0.68 - late*0.12`, is skipped when that is below the pump's own
floor (`pick_y + 0.10`, `fruits.py:2247`), and a backlog is burnt by **one pump
call** (skips do not count against `burst_max = 6`, `fruits.py:2293-2320`). So
the predicted wait is `max(0, -lag)` seconds plus one control tick.

    python3 logs/p57/cand_census.py [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

BELT = 0.12             # m/s, the shipped scenario speed
TICK = 1.0 / 120.0      # control tick
SPAWN_Y = 0.68          # assets.SceneConfig.spawn_y
PUMP_FLOOR = 0.10       # fruits.py:2247  floor = pick_y + 0.10
X_CLEAN = (0.18, 0.39)  # scripts/174_station_reach.py measured lateral band

# R10-A measured clean bands: per column x, the along offsets (dy from the
# station) whose grip residual is <= 6 mm (logs/r10/reach_intercept_*.json).
R10 = {
    "left": {0.20: (-0.10, 0.15), 0.28: (-0.05, 0.10), 0.36: (0.00, 0.10)},
    "right": {0.20: (-0.10, 0.10), 0.28: (-0.10, 0.05), 0.36: (-0.10, 0.00)},
}

HEAD = re.compile(
    r"\[bed-sel\] attempt (\d+) t=(?P<t>[0-9.]+) live=(?P<live>\d+) "
    r"on_belt=(?P<on_belt>\d+) admitted=(?P<adm>\d+) window=(?P<win>\d+) "
    r"pick=(?P<pick>\S+) pump_next=(?P<pump>[0-9.]+) lag=(?P<lag>[+-][0-9.]+)"
)
ROW = re.compile(
    r"\[bed-sel\]\s+(?P<cat>\S+)\s+along=(?P<along>[+-][0-9.]+)\s+"
    r"x=(?P<x>[0-9.]+)\s+z=(?P<z>[0-9.]+)\s+r=(?P<r>[0-9.]+)\s+"
    r"grade=(?P<grade>\S+)\s+->\s+(?P<reason>.*)"
)
FLOOR = re.compile(r"below catch floor [+-]?[0-9.]+ < ([0-9.]+)")


def arm_of(grade: str) -> str:
    return "left" if grade == "A" else "right"


def reachable(x: float, arm: str) -> bool:
    """Lateral membership at the station (dy = 0 is in every R10 cell)."""
    if not (X_CLEAN[0] <= x <= X_CLEAN[1]):
        return False
    return any(lo <= 0.0 <= hi for lo, hi in R10[arm].values())


def belt_candidate(row: dict) -> bool:
    """The selector's own two z gates and the belt-centre gate.

    `bed_diag_report`'s `on_belt` only excludes the `off belt x=` reason, so a
    fruit that fell off the line (`below belt z=0.02`) counts as stock there.
    """
    return not row["reason"].startswith(("off belt", "below belt", "above belt"))


def parse(path: Path):
    text = path.read_text(errors="replace")
    blocks, cur = [], None
    for line in text.splitlines():
        if "[bed-sel]" not in line:
            continue
        m = HEAD.search(line)
        if m:
            cur = {
                "t": float(m["t"]), "live": int(m["live"]),
                "on_belt_hdr": int(m["on_belt"]), "window": int(m["win"]),
                "pick": m["pick"], "pump_next": float(m["pump"]),
                "lag": float(m["lag"]), "rows": [],
            }
            blocks.append(cur)
            continue
        r = ROW.search(line)
        if r and cur is not None:
            cur["rows"].append(
                {k: (float(r[k]) if k in ("along", "x", "z", "r") else r[k])
                 for k in ("cat", "along", "x", "z", "r", "grade", "reason")}
            )
    floors = [float(v) for v in FLOOR.findall(text)]
    floor = max(set(floors), key=floors.count) if floors else 0.399
    return blocks, floor


def analyse(path: Path, label: str):
    blocks, floor = parse(path)
    out = {"log": label, "floor": floor, "selections": []}
    for i, b in enumerate(blocks):
        cands = []
        for row in b["rows"]:
            if not belt_candidate(row):
                continue
            arm = arm_of(row["grade"])
            cands.append({**row, "arm": arm, "reachable": reachable(row["x"], arm)})
        usable = [c for c in cands if c["along"] >= floor]
        leaving = [c for c in cands if c["along"] < floor]
        dt = (blocks[i + 1]["t"] - b["t"]) / TICK if i + 1 < len(blocks) else None
        out["selections"].append({
            "i": i, "t": b["t"], "window": b["window"], "pick": b["pick"],
            "lag": b["lag"], "pump_next": b["pump_next"],
            "n_live": len(b["rows"]), "on_belt_hdr": b["on_belt_hdr"],
            "n_line": len(cands), "n_usable": len(usable),
            "n_usable_reach": sum(1 for c in usable if c["reachable"]),
            "n_leaving": len(leaving),
            "usable_along": [round(c["along"], 3) for c in usable],
            "leaving_along": [round(c["along"], 3) for c in leaving],
            # the only finite arrival: the feeder clock (+1 tick to land)
            "t_feed_ticks": max(0.0, -b["lag"]) / TICK + 1.0,
            "dt_to_next_block": dt,
        })
    return out


def stats(vals, unit=""):
    vals = sorted(vals)
    if not vals:
        return "n=0"
    n = len(vals)
    q = lambda p: vals[min(n - 1, int(round(p * (n - 1))))]
    return (f"n={n} p0={vals[0]:.0f} p25={q(.25):.0f} p50={q(.5):.0f} "
            f"p75={q(.75):.0f} p90={q(.9):.0f} max={vals[-1]:.0f}{unit}")


def summary(run, lines):
    s = run["selections"]
    picks = [x for x in s if x["pick"] != "none"]
    starved = [x for x in s if x["pick"] == "none"]
    lines.append(f"== {run['log']}  floor={run['floor']:.3f} m  blocks={len(s)}"
                 f"  picks={len(picks)}  starved-rounds={len(starved)}")
    lines.append(f"   on-belt candidates (window={run['floor']:.3f}): "
                 f"{stats([x['n_line'] for x in s])}")
    lines.append(f"   of them usable (along>=floor):           "
                 f"{stats([x['n_usable'] for x in s])}"
                 f"   leaving (along<floor, t_enter=inf): {stats([x['n_leaving'] for x in s])}")
    lines.append(f"   usable count at picks: {stats([x['n_usable'] for x in picks])}"
                 f"   at rounds: {stats([x['n_usable'] for x in starved])}")
    lines.append("   window distribution (picks): "
                 + str({k: sum(1 for x in picks if x["window"] == k)
                        for k in sorted({x["window"] for x in picks})}))
    lines.append("   usable along span (m, picks with >=2): "
                 + stats([int(round((max(x["usable_along"]) - min(x["usable_along"])) * 1000))
                          for x in picks if len(x["usable_along"]) > 1], " mm"))
    lines.append("   usable along max: "
                 + stats([int(round(max(x['usable_along']) * 1000)) for x in picks if x['usable_along']], " mm")
                 + f"   belt spawn_y {SPAWN_Y:.2f} m -> nothing is ever above the band")
    lines.append("   feeder clock  max(0,-lag) x 120 + 1 tick: "
                 f"picks {stats([x['t_feed_ticks'] for x in picks if x['t_feed_ticks'] > 1])}"
                 f"   rounds {stats([x['t_feed_ticks'] for x in starved])}")
    for h in (30, 60, 90):
        n = sum(1 for x in s if x["n_usable"] == 0 and x["t_feed_ticks"] <= h)
        z = sum(1 for x in s if x["n_usable"] == 0)
        lines.append(f"   0 usable at t: {z}; a usable fruit within {h:2d} ticks: "
                     f"**0 structural** (no live fruit can enter) / feeder says {n}")
    over = [x for x in s if x["on_belt_hdr"] != x["n_line"]]
    lines.append(f"   header on_belt vs the selector's own rows: differ on "
                 f"{len(over)} of {len(s)} blocks (hdr median "
                 f"{stats([x['on_belt_hdr'] for x in s]).split('p50=')[1].split()[0]}"
                 f" vs true median {stats([x['n_line'] for x in s]).split('p50=')[1].split()[0]})")
    lines.append(f"   pump lag: picks {min(x['lag'] for x in picks):+.2f}..{max(x['lag'] for x in picks):+.2f} s"
                 f"   rounds {min((x['lag'] for x in starved), default=float('nan')):+.2f}"
                 f"..{max((x['lag'] for x in starved), default=float('nan')):+.2f} s")
    lines.append(f"   measured recovery at the rounds: "
                 f"{sorted({x['dt_to_next_block'] for x in starved})} ticks")
    return lines


def transition_visibility(runs, lines):
    """Was the next pick's chosen fruit already on the belt one transition earlier?"""
    for run in runs:
        picks = [x for x in run["selections"] if x["pick"] != "none"]
        vis = tot = 0
        for a, b in zip(picks, picks[1:]):
            along = float(b["pick"].split("@")[1])
            back = along - BELT * (b["t"] - a["t"])
            tot += 1
            if any(abs(r - back) <= 0.06 for r in a["usable_along"] + a["leaving_along"]):
                vis += 1
        lines.append(f"   {run['log']}: next target visible one transition earlier: "
                     f"{vis}/{tot}  (projection {BELT * 16.6:.2f} m vs a "
                     f"{SPAWN_Y - (-0.70):.2f} m belt)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[2]
    logs = [
        ("A per-pick (p56/p2)", root / "logs/p56/p2/A_1.log"),
        ("B continuous (p56/p2)", root / "logs/p56/p2/B_1.log"),
        ("Q12 QUEUE_MAX=12 (p56/p3)", root / "logs/p56/p3/Q12_s77.log"),
    ]
    runs = [analyse(p, lbl) for lbl, p in logs if p.exists()]
    lines = ["P57 phase 1 candidate census - belt 0.12 m/s, tick 1/120 s,",
             f"catch floor 0.399 m, pump floor pick_y+0.10 = {PUMP_FLOOR:.2f} m, spawn_y {SPAWN_Y:.2f} m.",
             "t_enter = 0 if along >= floor else INF (the belt runs -Y: a fruit below",
             "the floor is leaving the band). The only finite arrival is a release.",
             ""]
    for run in runs:
        summary(run, lines)
        lines.append("")
    lines.append("== the pre-decision question")
    transition_visibility(runs, lines)
    text = "\n".join(lines)
    print(text)
    if args.json:
        Path(args.json).write_text(json.dumps(runs, indent=1))


if __name__ == "__main__":
    main()
