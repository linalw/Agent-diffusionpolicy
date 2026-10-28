"""P58 phase 2 (offline): the catchable segment's occupancy at every selection.

Read-only over existing logs. Parses the `[bed-sel]` blocks (`FRUIT_BED_DIAG=1`,
`tasks.py::bed_diag_report`) and, for each selection instant, counts the bodies
in

  band     = [pick_y + FRUIT_SUPPLY_TARGET_FROM(0.35), spawn_y + 0.05 = 0.73]
             the window `_approach_depth()` counts (fruits.py:2504-2523) - the
             P57 band interlock's depth input;
  segment  = [pick_y + _dynamic_select_floor() 0.399, spawn_y 0.68]
             the window the moving catch can still meet.

Both windows are the same bodies read at two thresholds; the segment is 0.281 m
of the 0.33 m band and 0.05 m of the band sits below the floor (a body that is
already past the point the schedule can meet). Nothing is ever above
`spawn_y + 0.05`, so the segment's upstream edge is the release point.

    python3 logs/p58/segment_census.py [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

BELT = 0.12          # m/s, `cleated belt built: ... surface velocity -0.12 m/s`
TICK = 1.0 / 120.0
PICK_Y = 0.0
SPAWN_Y = 0.68
BAND_LO = PICK_Y + 0.35   # fruits.py:661 FRUIT_SUPPLY_TARGET_FROM
BAND_HI = SPAWN_Y + 0.05  # fruits.py:2521
SEG_LO = PICK_Y + 0.399   # _dynamic_select_floor at lead 0.189, 1.5 s, 0.03
SEG_HI = SPAWN_Y

HEAD = re.compile(
    r"\[bed-sel\] attempt (?P<att>\d+) t=(?P<t>[0-9.]+) live=(?P<live>\d+) "
    r"on_belt=(?P<on_belt>\d+) admitted=(?P<adm>\d+) window=(?P<win>\d+) "
    r"pick=(?P<pick>\S+)"
)
ROW = re.compile(
    r"\[bed-sel\]\s+(?P<cat>\S+)\s+along=(?P<along>[+-][0-9.]+)\s+"
    r"x=(?P<x>[0-9.]+)\s+z=(?P<z>[0-9.]+)\s+r=(?P<r>[0-9.]+)\s+"
    r"grade=(?P<grade>\S+)\s+->\s+(?P<reason>.*)"
)
CONT = re.compile(r"\[cont\] pick (?P<n>\d+)/(?P<tot>\d+):.*gap_ticks=(?P<gap>\d+)")


def on_belt(row) -> bool:
    """`bed_diag_report`'s own gate: a fruit off the belt / fallen is not stock."""
    return not row["reason"].startswith(("off belt", "below belt", "above belt"))


def parse(path: Path):
    blocks, cur = [], None
    for line in path.read_text(errors="replace").splitlines():
        m = HEAD.search(line)
        if m:
            cur = {
                "attempt": int(m["att"]), "t": float(m["t"]),
                "live": int(m["live"]), "on_belt": int(m["on_belt"]),
                "admitted": int(m["adm"]), "window": int(m["win"]),
                "pick": m["pick"], "rows": [],
            }
            blocks.append(cur)
            continue
        r = ROW.search(line)
        if r and cur is not None:
            cur["rows"].append({
                "cat": r["cat"], "along": float(r["along"]), "x": float(r["x"]),
                "grade": r["grade"], "reason": r["reason"],
            })
    gaps = [int(m["gap"]) for m in CONT.finditer(path.read_text(errors="replace"))]
    return blocks, gaps


def analyse(path: Path, label: str):
    blocks, gaps = parse(path)
    out = {"log": label, "selections": []}
    for i, b in enumerate(blocks):
        rows = [r for r in b["rows"] if on_belt(r)]
        band = [r for r in rows if BAND_LO <= r["along"] <= BAND_HI]
        seg = [r for r in rows if SEG_LO <= r["along"] <= SEG_HI]
        out["selections"].append({
            "i": i, "att": b["attempt"], "t": b["t"], "pick": b["pick"],
            "window": b["window"], "on_belt": b["on_belt"],
            "admitted": b["admitted"], "live": b["live"],
            "n_band": len(band), "n_seg": len(seg),
            "seg_along": sorted(round(r["along"], 3) for r in seg),
            "band_along": sorted(round(r["along"], 3) for r in band),
            "below_floor_in_band": sum(1 for r in band if r["along"] < SEG_LO),
            "gap_ticks": gaps[i - 1] if 0 < i <= len(gaps) else None,
        })
    return out


def stats(vals, unit=""):
    vals = sorted(vals)
    if not vals:
        return "n=0"
    n = len(vals)
    q = lambda p: vals[min(n - 1, int(round(p * (n - 1))))]
    return (f"n={n} p0={vals[0]}{unit} p25={q(.25)}{unit} p50={q(.5)}{unit} "
            f"p75={q(.75)}{unit} p90={q(.9)}{unit} max={vals[-1]}{unit}")


def dist(vals, hi=6):
    return {k: sum(1 for v in vals if v == k) for k in range(0, hi + 1)
            if any(v == k for v in vals)}


def report(run, lines):
    s = run["selections"]
    lines.append(f"== {run['log']}  selections={len(s)}")
    lines.append("   band  [0.350, 0.730] bodies/selection: "
                 + stats([x["n_band"] for x in s]) + f"   dist {dist([x['n_band'] for x in s])}")
    lines.append("   SEG   [0.399, 0.680] bodies/selection: "
                 + stats([x["n_seg"] for x in s]) + f"   dist {dist([x['n_seg'] for x in s])}")
    lines.append("   header window (usable+chosen): "
                 + stats([x["window"] for x in s]) + f"   dist {dist([x['window'] for x in s])}")
    lines.append("   on_belt bodies: " + stats([x["on_belt"] for x in s]))
    g = [x["gap_ticks"] for x in s if x["gap_ticks"] is not None]
    if g:
        lines.append("   belt travel between selections (gap ticks): "
                     + stats(g) + f"   = {stats(g)[0:0]}" +
                     stats([int(round(v * BELT / 120.0 * 1000)) for v in g], " mm"))
    empty = [x for x in s if x["n_seg"] == 0]
    lines.append(f"   EMPTY SEGMENT: {len(empty)}/{len(s)} selections")
    for x in empty:
        lines.append(
            f"     att {x['att']:2d} t={x['t']:6.2f} segment=0 band={x['n_band']} "
            f"(below floor {x['below_floor_in_band']}) on_belt={x['on_belt']} "
            f"window={x['window']} pick={x['pick']} band_along={x['band_along']}"
        )
    one = [x for x in s if x["n_seg"] == 1]
    lines.append(f"   exactly ONE body in the segment: {len(one)}/{len(s)}")
    for x in one:
        lines.append(f"     att {x['att']:2d} t={x['t']:6.2f} seg_along={x['seg_along']} "
                     f"band={x['n_band']} gap={x['gap_ticks']}")
    lines.append("")


def required_interval(lines):
    seg = SPAWN_Y - SEG_LO
    lines.append("== the arithmetic (code sites: tasks.py:5971-6004, tasks.py:6065-6086,")
    lines.append("   fruits.py:2504-2523, assets.py:236-244, assets.py:214-218)")
    lines.append(f"   segment = spawn_y {SPAWN_Y:.3f} - (pick_y {PICK_Y:+.3f} + floor {SEG_LO:.3f})"
                 f" = {seg:.3f} m")
    lines.append(f"   residence = {seg:.3f} / {BELT:.2f} = {seg / BELT:.2f} s")
    lines.append(f"   a pick consumes {15.0 * BELT:.2f} m; required release interval "
                 f"<= segment/belt = {seg / BELT:.2f} s  (spacing <= {seg:.3f} m)")
    lines.append("")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[2]
    logs = [
        ("cadence-on (p57/cad_s77)", root / "logs/p57/cad_s77.log"),
        ("band interlock (p57/band_s77)", root / "logs/p57/band_s77.log"),
        ("band + video (p57/video_band)", root / "logs/p57/video_band.log"),
        ("per-pick control (p56/p2/A_1)", root / "logs/p56/p2/A_1.log"),
        ("continuous control (p56/p2/B_1)", root / "logs/p56/p2/B_1.log"),
        ("QUEUE_MAX=12 (p56/p3/Q12_s77)", root / "logs/p56/p3/Q12_s77.log"),
    ]
    runs = [analyse(p, lbl) for lbl, p in logs if p.exists()]
    lines = ["P58 phase 2 segment census - belt 0.12 m/s, tick 1/120 s,",
             f"band {BAND_LO:.3f}..{BAND_HI:.3f} (the interlock's window),",
             f"segment {SEG_LO:.3f}..{SEG_HI:.3f} (the selector's floor .. spawn_y).", ""]
    required_interval(lines)
    for run in runs:
        report(run, lines)
    text = "\n".join(lines)
    print(text)
    if args.json:
        Path(args.json).write_text(json.dumps(runs, indent=1))


if __name__ == "__main__":
    main()
