#!/usr/bin/env python3
"""P111 census - what the compliant closure actually did, per arm.

Offline.  Reads the scripted single-arm cells and answers four questions the
report needs, none of which the `[stats]` row can:

1. **Was the ring on the payload at all?**  The `[cage] off0=` instrument (the
   payload's distance from the ring's axis at the close's start) separates the
   attempts into **in-ring** (`off0 < 20 mm`) and **off-ring** (the arm never got
   there: 85-820 mm measured).  The two are different failure classes and only
   the first can say anything about centring.
2. **Did the payload stay?**  `off - off0` over the in-ring rows: negative = the
   payload moved *toward* the ring's axis, positive = it was carried away during
   the close (the grip/slip read).
3. **The grip, by class**: `[carry]` `force@onset` / `force_min` / `fmax` on the
   `grasp_lift` legs, split into seated (a pad loaded) and never-seated.
4. **The count, per seed and pooled**, with the exact two-sided Fisher test for
   the arm pairs (a 20-attempt cell is one draw: the record's own rule).

Usage:
    python3 logs/p111/census.py
    python3 logs/p111/census.py --check     # asserts every cell exists
"""

from __future__ import annotations

import glob
import math
import os
import re
import statistics as st
import sys

ARMS = ("C", "R", "T1", "T2", "T4", "S1")
SEEDS = (5, 6, 101, 202)
CAP = 4.90

CAGE = re.compile(
    r"\[cage\] idx=\d+ arm=\w+ species=\w+ dia=(?P<dia>\d+)mm .*?"
    r"(?:off0=(?P<off0>[-+0-9.]+)mm off=(?P<off>[-+0-9.]+)mm )?pads=(?P<pads>\d)/4 "
    r"f=\((?P<f>[^)]*)\) F=(?P<F>[0-9.]+)N aper=(?P<aper>[0-9.]+)mm"
)
CARRY = re.compile(
    r"\[carry\] \w+ grasp_lift: .*?force@onset=(?P<fo>[-+0-9.]+|n/a)N.*?"
    r"force_min=(?P<fmin>[-+0-9.]+)N .*?fmax=(?P<fmax>[-+0-9.]+)N"
)
RUN = re.compile(r"\[run\] attempt \d+: (?P<body>.*)")
STATS = re.compile(r"\[stats\] attempts=(?P<att>\d+) successes=(?P<succ>\d+)")
END = re.compile(r"approach\(cartesian\): [0-9.]+ cm, \d+ samples: steps=\d+.*?end=([0-9.]+) mm")
NOTE = re.compile(r"notes=\[(.*?)\]")


#: C and R are P108's `S`/`E` arms.  `logs/p111/{C,R}_s5.log` are this tree's
#: replays and are `[fruit]`-stream **byte-identical** to `logs/p108/{S,E}_s5.log`
#: (621/621, 531/531 with the phase's rows dropped; the 19 `[cage]` rows identical
#: with `off0`/`off` stripped), so P108's other seeds are admissible controls
#: (P95's rule: prove the replay, then reuse).  The fallback is what makes the
#: four-seed pooling possible without six more cells.
P108_FALLBACK = {"C": "logs/p108/S_s{}.log", "R": "logs/p108/E_s{}.log"}


def cells(arm: str) -> list[str]:
    out = []
    for s in SEEDS:
        mine = f"logs/p111/{arm}_s{s}.log"
        if os.path.exists(mine):
            out.append(mine)
        elif arm in P108_FALLBACK and os.path.exists(P108_FALLBACK[arm].format(s)):
            out.append(P108_FALLBACK[arm].format(s))
    return out


def read(path: str) -> dict:
    text = open(path, errors="replace").read()
    ends = [float(m.group(1)) for m in END.finditer(text)]
    cage = []
    for i, m in enumerate(CAGE.finditer(text)):
        d = {
            k: (v if k == "f" else (float(v) if v is not None else float("nan")))
            for k, v in m.groupdict().items()
        }
        d["end"] = ends[i] if i < len(ends) else float("nan")
        d["pads"] = int(d["pads"])
        d["dia"] = int(d["dia"])
        cage.append(d)
    legs = [m.groupdict() for m in CARRY.finditer(text)]
    stats = STATS.search(text)
    notes = {}
    for m in RUN.finditer(text):
        body = m["body"]
        for note in NOTE.findall(body):
            if note.strip():
                key = re.sub(r"\d+", "N", note.strip())
                notes[key] = notes.get(key, 0) + 1
    placed = sum(1 for ln in text.splitlines()
                 if "[run] attempt" in ln and "placed=True" in ln)
    return {
        "path": path,
        "cage": cage,
        "legs": legs,
        "placed": placed,
        "att": int(stats["att"]) if stats else 0,
        "notes": notes,
    }


def fisher(a: int, na: int, b: int, nb: int) -> float:
    """Two-sided Fisher's exact test on a 2x2 (placed / not)."""
    def logc(n, k):
        return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)

    def p(x):
        return math.exp(logc(na, x) + logc(nb, b + a - x) - logc(na + nb, a + b))

    lo = max(0, a + b - nb)
    hi = min(a + b, na)
    obs = p(a)
    return sum(p(x) for x in range(lo, hi + 1) if p(x) <= obs + 1e-12)


def main() -> int:
    ap_ok = True
    data = {}
    for arm in ARMS:
        got = {}
        for p in cells(arm):
            seed = int(re.search(r"_s(\d+)\.log$", p).group(1))
            got[seed] = read(p)
        if got:
            data[arm] = got
    if "--check" in sys.argv:
        missing = []
        for arm in ARMS:
            for seed in SEEDS:
                if not os.path.exists(f"logs/p111/{arm}_s{seed}.log") and arm in (
                    "T1", "T2", "T4", "S1"
                ):
                    missing.append(f"logs/p111/{arm}_s{seed}.log")
        print(f"cells present: "
              f"{ {a: sorted(d) for a, d in data.items()} }")
        if missing:
            print(f"missing (not run by design is fine): {len(missing)}")
            for m in missing:
                print("   ", m)
            return 1
        return 0

    print("P111 census - the compliant closure, arm by arm")
    print("=" * 100)

    # ---------------------------------------------------------------- #
    print("\n1. THE RING ON THE PAYLOAD  (`off0`, the close-time offset [mm])")
    print("=" * 100)
    print(f"  {'arm':4s} {'rows':>5} {'in-ring':>8} {'off-ring':>9} "
          f"{'off0 p50':>9} {'off0 p90':>9} {'off0 max':>9}")
    for arm, per in data.items():
        rows = [r for s in per.values() for r in s["cage"]]
        instr = [r for r in rows if r["off0"] == r["off0"]]
        inr = [r["off0"] for r in instr if r["off0"] < 20.0]
        out = [r for r in instr if r["off0"] >= 20.0]
        q = lambda v, p: sorted(v)[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))] if v else float("nan")
        print(f"  {arm:4s} {len(rows):>5} {len(inr):>8} {len(out):>9} "
              f"{q(inr, 50):>9.1f} {q(inr, 90):>9.1f} "
              f"{(max(r['off0'] for r in rows) if rows else float('nan')):>9.1f}")
    print("  (`off-ring` rows are the arm-never-arrived class: the payload 85-820 mm")
    print("   from the ring's axis when the close starts.  Only `in-ring` rows can")
    print("   say anything about centring.)")

    # ---------------------------------------------------------------- #
    print("\n2. DID THE PAYLOAD STAY?  (`off - off0` over the in-ring rows [mm])")
    print("=" * 100)
    print(f"  {'arm':4s} {'n':>4} {'p50':>7} {'p90':>7} {'> 5 mm':>7} {'< -2 mm':>8}")
    for arm, per in data.items():
        rows = [r for s in per.values() for r in s["cage"] if r["off0"] < 20.0]
        d = [r["off"] - r["off0"] for r in rows]
        if not d:
            continue
        q = lambda p: sorted(d)[min(len(d) - 1, int(round(p / 100 * (len(d) - 1))))]
        print(f"  {arm:4s} {len(d):>4} {q(50):>+7.1f} {q(90):>+7.1f} "
              f"{sum(1 for v in d if v > 5):>7} {sum(1 for v in d if v < -2):>8}")
    print("  (positive = the payload was carried AWAY from the ring's axis during")
    print("   the close, i.e. the ring did not hold it; negative = it moved in.)")

    # ---------------------------------------------------------------- #
    print("\n3. THE GRIP, BY CLASS  (`[carry] grasp_lift` rows)")
    print("=" * 100)
    print(f"  {'arm':4s} {'legs':>5} {'seated':>7} {'never':>6} "
          f"{'fmin p50':>9} {'fmax p50':>9} {'fmax>cap':>9}")
    for arm, per in data.items():
        legs = [l for s in per.values() for l in s["legs"]]
        if not legs:
            continue
        seated = [l for l in legs if float(l["fmax"]) > 1.0]
        never = [l for l in legs if float(l["fmax"]) <= 1.0]
        fmin = [float(l["fmin"]) for l in seated]
        fmax = [float(l["fmax"]) for l in seated]
        print(f"  {arm:4s} {len(legs):>5} {len(seated):>7} {len(never):>6} "
              f"{(st.median(fmin) if fmin else float('nan')):>9.2f} "
              f"{(st.median(fmax) if fmax else float('nan')):>9.2f} "
              f"{sum(1 for v in fmax if v > CAP * 1.5):>9}")

    # ---------------------------------------------------------------- #
    print("\n4. THE COUNT, per seed and pooled")
    print("=" * 100)
    print(f"  {'arm':4s} " + " ".join(f"{'s%d' % s:>8}" for s in SEEDS)
          + f" {'pooled':>10} {'rate':>6}")
    for arm, per in data.items():
        row = []
        for s in SEEDS:
            if s in per:
                row.append(f"{per[s]['placed']:>3}/{per[s]['att']:<4}")
            else:
                row.append(f"{'-':>8}")
        pl = sum(v["placed"] for v in per.values())
        at = sum(v["att"] for v in per.values())
        print(f"  {arm:4s} " + " ".join(f"{r:>8}" for r in row)
              + f" {pl:>4}/{at:<5} {(100 * pl / at if at else 0):>5.1f}%")
    print("\n  the exact two-sided Fisher test on the arm pairs (pooled):")
    pairs = [("R", a) for a in ("T1", "T2", "T4")] + [("C", "R"), ("T2", "T4"), ("T1", "T4")]
    for a, b in pairs:
        if a not in data or b not in data:
            continue
        pa = sum(v["placed"] for v in data[a].values())
        na = sum(v["att"] for v in data[a].values())
        pb = sum(v["placed"] for v in data[b].values())
        nb = sum(v["att"] for v in data[b].values())
        if not (na and nb):
            continue
        print(f"    {a} {pa}/{na} vs {b} {pb}/{nb}:  p = {fisher(pa, na, pb, nb):.3f}")

    # ---------------------------------------------------------------- #
    print("\n5. THE FAILURE NOTES (digit-normalised, per arm)")
    print("=" * 100)
    for arm, per in data.items():
        agg = {}
        for v in per.values():
            for k, n in v["notes"].items():
                agg[k] = agg.get(k, 0) + n
        if agg:
            print(f"  {arm:4s} " + ", ".join(
                f"{k}x{n}" for k, n in sorted(agg.items(), key=lambda kv: -kv[1])[:4]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
