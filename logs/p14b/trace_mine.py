#!/usr/bin/env python3
"""P14-B: phase-level first-departure mining over an existing FRUIT_DYNAMIC_TRACE
corpus (the dry run of the trace-run analysis, on the W5-C dense two-line traces).

For each attempt JSON (the `_dynamic_trace_dump` schema: {arm, scripted, outcome,
rows:[...]}) it computes, from the per-tick rows:

  * the reference = the LAST `hold` row's hand_rel (the payload in the hand frame
    just before the probe).  NB the `grip` row's hand_rel is junk on this tree -
    the call site passes `fruit=rest` (a pre-close snapshot) - so it is never
    used as a reference;
  * per phase from the hold onward: the max cumulative |hand_rel - ref| [mm], the
    max phase-local drift (from the phase's own first row), the min force and the
    min contacts;
  * the first departure: the first row after the hold whose hand_rel has moved
    > 2 mm from the reference (the W8-B crossing scale) - reported with its
    phase, t, and the force/contacts there;
  * the close freeze geometry: the last `close` row's sep, gap_cmd,
    sep - gap_cmd, offset_z, hand_rel_z (the last close row is a live-fruit row);
  * the probe: the takeoff_probe blocks (one per probe cycle) with the fruit's
    z rise [mm] and the sep/gap_cmd at the block's last row;
  * the takeoff: the fruit's z at the first and last row.

Run:  python3 -B logs/p14b/trace_mine.py [trace-dir]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def segments(rows):
    out = []
    for i, r in enumerate(rows):
        if out and out[-1][0] == r["phase"]:
            out[-1][1].append((i, r))
        else:
            out.append((r["phase"], [(i, r)]))
    return out


def analyze(path: Path):
    d = json.load(open(path))
    rows = d["rows"]
    if not rows:
        return None
    arm = d.get("arm", "?")
    out = d.get("outcome", "?")
    holds = [(i, r) for i, r in enumerate(rows) if r["phase"] == "hold"]
    ref_i, ref_row = holds[-1] if holds else (0, rows[0])
    ref = ref_row["hand_rel"]

    first_dep = None
    for i, r in enumerate(rows):
        if i <= ref_i or r["phase"] == "grip":
            continue  # the `grip` row's hand_rel is junk (fruit=rest at its site)
        if dist(r["hand_rel"], ref) > 0.002:
            first_dep = (i, r)
            break

    phases = []
    for ph, rs in segments(rows):
        if rs[-1][0] < ref_i or ph == "grip":
            continue  # pre-hold: the payload is not in the hand yet; grip: junk row
        cum = max(dist(r["hand_rel"], ref) * 1000 for _, r in rs)
        local = max(dist(r["hand_rel"], rs[0][1]["hand_rel"]) * 1000 for _, r in rs)
        fmin = min(r["force"] for _, r in rs)
        cmin = min(r["contacts"] for _, r in rs)
        phases.append((ph, len(rs), cum, local, fmin, cmin))

    close = [r for r in rows if r["phase"] == "close"]
    freeze = close[-1] if close else None
    probes = []
    for ph, rs in segments(rows):
        if ph != "takeoff_probe":
            continue
        z0, z1 = rs[0][1]["fruit"][2], rs[-1][1]["fruit"][2]
        probes.append((len(rs), (z1 - z0) * 1000, rs[-1][1]["sep"] * 1000, rs[-1][1]["gap_cmd"] * 1000))
    takeoff = [r for r in rows if r["phase"] == "takeoff"]
    carry = [r for r in rows if r["phase"] == "carry"]
    return {
        "file": path.name, "arm": arm, "outcome": out, "n": len(rows), "ref": ref,
        "phases": phases, "first_dep": first_dep, "freeze": freeze, "probes": probes,
        "takeoff_z": None if not takeoff else (takeoff[0]["fruit"][2], takeoff[-1]["fruit"][2]),
        "carry_ticks": len(carry),
        "carry_fmin": None if not carry else min(r["force"] for r in carry),
        "carry_drift": None if not carry else max(dist(r["hand_rel"], ref) * 1000 for r in carry),
    }


def main():
    tdir = Path(sys.argv[1] if len(sys.argv) > 1 else "logs/w5/traces_dense")
    files = sorted(tdir.glob("*.json"))
    print(f"== trace corpus: {tdir} ({len(files)} attempts) ==")
    print()
    print("| file | arm | out | rows | freeze sep/gap/delta | freeze off_z | hrel_z | probes (n, dz, sep, gap) "
          "| first departure (phase, t, cum drift) | carry ticks, Fmin, cum drift |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for f in files:
        a = analyze(f)
        if a is None:
            continue
        fr = a["freeze"]
        fr_txt = "-" if not fr else "%.1f/%.1f/%+.1f" % (
            fr["sep"] * 1000, fr["gap_cmd"] * 1000, (fr["sep"] - fr["gap_cmd"]) * 1000)
        off_z = "-" if not fr else "%+.1f" % (fr["offset"][2] * 1000)
        hrel_z = "-" if not fr else "%+.1f" % (fr["hand_rel"][2] * 1000)
        pr = "; ".join("%d, %+.1f, %.1f, %.1f" % p for p in a["probes"])
        fd = a["first_dep"]
        fd_txt = "-" if not fd else "%s t=%.3f %+.1f mm F=%.2f c=%d" % (
            fd[1]["phase"], fd[1]["t"], dist(fd[1]["hand_rel"], a["ref"]) * 1000,
            fd[1]["force"], fd[1]["contacts"])
        print(
            f"| {a['file']} | {a['arm']} | {a['outcome']} | {a['n']} | {fr_txt} | {off_z} | {hrel_z} "
            f"| {pr} | {fd_txt} | {a['carry_ticks']}, {a['carry_fmin']:.2f}, {a['carry_drift']:.1f} |"
        )
    print()
    print("== per-phase detail (phase, rows, cum drift mm, local drift mm, min force N, min contacts) ==")
    for f in files:
        a = analyze(f)
        if a is None:
            continue
        print(f"\n-- {a['file']} ({a['arm']}, {a['outcome']}) --")
        for ph, n, cum, local, fmin, cmin in a["phases"]:
            print(f"   {ph:14s} rows={n:4d} cum={cum:9.1f} local={local:9.1f} Fmin={fmin:6.2f} cmin={cmin}")
        if a["takeoff_z"]:
            print(f"   takeoff z: {a['takeoff_z'][0]:.4f} -> {a['takeoff_z'][1]:.4f}")


if __name__ == "__main__":
    main()
