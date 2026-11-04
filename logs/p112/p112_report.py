#!/usr/bin/env python3
"""P112 report - the three-jaw ring's battery: enclosure, count, class, guards.

Offline.  Reads the scripted single-arm cells (`logs/p112/{C,T}_s<seed>.log`) and
answers the registration's clauses in its own order:

1. **The clean enclosure** (P110's split, applied to **3** pads): a `[cage]` row
   with `pads == 3` that is not a **jam** (the descent's `end > 15 mm`) and not
   an **over-closure** (`aper < dia - 4 mm` or `F > 3 x cap x 1.5`).
2. **The count**, per seed and pooled, with the exact two-sided Fisher test
   against the shipped hand (a 20-attempt cell is one draw - the record's rule).
3. **The class**: the ring's `[cage] off0 -> off` centring read, the `[carry]`
   grip split (seated / never-seated), the no-contact/ejection class and the
   crush guard (`sep@loss - dia`).
4. **The landing** (`FRUIT_PLACE_TRACE` `on_belt` on payload-present releases),
   **the budgets** (each descent's `end`/`|v|max` against 105's own gate) and
   **the slots** (attempts delivered vs 20).

    python3 logs/p112/p112_report.py            # every cell
    python3 logs/p112/p112_report.py --check    # asserts the 8 cells exist
    python3 logs/p112/p112_report.py --same A B # [fruit]-stream identity
"""

from __future__ import annotations

import glob
import math
import os
import re
import statistics as st
import sys

ARMS = ("C", "T")
SEEDS = (5, 6, 101, 202)
PAD_CAP = 4.90

CAGE = re.compile(
    r"\[cage\] idx=\d+ arm=\w+ species=(?P<sp>\w+) dia=(?P<dia>\d+)mm .*?"
    r"(?:off0=(?P<off0>[-+0-9.]+)mm off=(?P<off>[-+0-9.]+)mm )?pads=(?P<pads>\d)/(?P<np>\d) "
    r"f=\((?P<f>[^)]*)\) F=(?P<F>[0-9.]+)N aper=(?P<aper>[-0-9.]+)mm"
)
CARRY = re.compile(
    r"\[carry\] \w+ (?P<leg>\w+): .*?force@onset=(?P<fo>[-+0-9.]+|n/a)N.*?"
    r"force_min=(?P<fmin>[-+0-9.]+)N .*?fmax=(?P<fmax>[-+0-9.]+)N"
    r"(?:.*?sep@loss=(?P<seploss>[-+0-9.]+)mm)?"
)
CARRY_SEP = re.compile(
    r"\[carry\] \w+ (?P<leg>\w+): .*?dia=(?P<dia>[-+0-9.]+)mm .*?"
    r"sep@loss=(?P<seploss>[-+0-9.]+)mm"
)
RUN = re.compile(r"\[run\] attempt \d+: (?P<body>.*)")
STATS = re.compile(r"\[stats\] attempts=(?P<att>\d+) successes=(?P<succ>\d+)")
END = re.compile(r"approach\(cartesian\): [0-9.]+ cm, \d+ samples: steps=\d+.*?end=([0-9.]+) mm")
NOTE = re.compile(r"notes=\[(.*?)\]")
TRACE = re.compile(r"place trace (?P<side>\w+): release_bottom=(?P<rb>[-+0-9.]+)mm "
                   r".*?on_belt=(?P<on>\w+)")
SPEC = re.compile(r"\[motion\] approach\(cartesian\): [0-9.]+ cm, \d+ samples: "
                  r"steps=\d+, \|v\|max=(?P<v>[0-9.]+)")


def cells(arm: str) -> list[str]:
    out = []
    for s in SEEDS:
        p = f"logs/p112/{arm}_s{s}.log"
        if os.path.exists(p):
            out.append(p)
    return out


def read(path: str) -> dict:
    text = open(path, errors="replace").read()
    ends = [float(m.group(1)) for m in END.finditer(text)]
    cage = []
    for i, m in enumerate(CAGE.finditer(text)):
        d = {k: v for k, v in m.groupdict().items()}
        for k in ("off0", "off", "F", "aper"):
            d[k] = float(d[k]) if d[k] not in (None, "") else float("nan")
        d["pads"] = int(d["pads"])
        d["np"] = int(d["np"])
        d["dia"] = int(d["dia"])
        d["end"] = ends[i] if i < len(ends) else float("nan")
        cage.append(d)
    legs = []
    for m in CARRY.finditer(text):
        d = {}
        for k, v in m.groupdict().items():
            d[k] = v if k == "leg" else (
                float(v) if v not in (None, "", "n/a") else float("nan"))
        legs.append(d)
    sep = {}
    for m in CARRY_SEP.finditer(text):
        sep.setdefault(m["leg"], []).append(
            float(m["seploss"]) - float(m["dia"]) * 1000.0
        )
    stats = STATS.search(text)
    notes = {}
    for m in RUN.finditer(text):
        for note in NOTE.findall(m["body"]):
            if note.strip():
                key = re.sub(r"\d+", "N", note.strip())
                notes[key] = notes.get(key, 0) + 1
    placed = sum(1 for ln in text.splitlines()
                 if "[run] attempt" in ln and "placed=True" in ln)
    trace = [m.groupdict() for m in TRACE.finditer(text)]
    return dict(path=path, cage=cage, legs=legs, sep=sep, placed=placed,
                att=int(stats["att"]) if stats else 0,
                succ=int(stats["succ"]) if stats else 0,
                notes=notes, trace=trace,
                vmax=[float(m.group(1)) for m in SPEC.finditer(text)])


def fisher(a: int, na: int, b: int, nb: int) -> float:
    def logc(n, k):
        return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)

    def p(x):
        return math.exp(logc(na, x) + logc(nb, b + a - x) - logc(na + nb, a + b))

    lo, hi = max(0, a + b - nb), min(a + b, na)
    obs = p(a)
    return sum(p(x) for x in range(lo, hi + 1) if p(x) <= obs + 1e-12)


def main() -> int:
    if "--same" in sys.argv:
        a, b = sys.argv[sys.argv.index("--same") + 1:][:2]
        fa = [ln for ln in open(a, errors="replace") if ln.startswith("[fruit]")]
        fb = [ln for ln in open(b, errors="replace") if ln.startswith("[fruit]")]
        drop = ("[cage]", "[carry]", "[motion]", "[cycle]", "[place-trace]",
                "place trace", "release profile", "direct profile")
        fa = [ln for ln in fa if not any(d in ln for d in drop)]
        fb = [ln for ln in fb if not any(d in ln for d in drop)]
        same = sum(1 for x, y in zip(fa, fb) if x == y)
        print(f"[fruit]-stream identity (instrumentation rows dropped): "
              f"{same}/{len(fa)} vs {len(fb)}")
        return 0 if same == min(len(fa), len(fb)) and len(fa) == len(fb) else 1

    data = {a: {int(re.search(r"_s(\d+)\.log$", p).group(1)): read(p)
                for p in cells(a)} for a in ARMS}
    if "--check" in sys.argv:
        # D2: the treatment is registered at four seeds, the shipped control at
        # two (it is the *reference*, not an arm of the comparison - P111's shape).
        need = {"C": (5, 6), "T": SEEDS}
        miss = [f"logs/p112/{a}_s{s}.log" for a, seeds in need.items() for s in seeds
                if s not in data[a]]
        print(f"cells present: { {a: sorted(d) for a, d in data.items()} }")
        if miss:
            print("missing:", *miss, sep="\n  ")
            return 1
        return 0

    print("P112 report - the three-jaw ring (cage3) against the shipped hand")
    print("=" * 100)

    # ---------------------------------------------------------------- 1
    print("\n1. THE CLEAN ENCLOSURE  (`[cage]` rows, P110's split on 3 pads)")
    print("=" * 100)
    print(f"  {'arm':4s} {'rows':>5} {'pads 0:1:2:3':>14} {'raw=3':>6} "
          f"{'jam':>4} {'over':>5} {'CLEAN':>7} {'share':>7}")
    clean_all = {}
    for arm, per in data.items():
        rows = [r for s in per.values() for r in s["cage"]]
        hist = {k: 0 for k in range(0, 5)}
        for r in rows:
            hist[min(4, r["pads"])] += 1
        jam, over, clean = [], [], []
        for r in rows:
            if r["pads"] < r["np"]:
                continue
            if r["end"] == r["end"] and r["end"] > 15.0:
                jam.append(r)
            elif r["aper"] < r["dia"] - 4.0 or r["F"] > r["np"] * PAD_CAP * 1.5:
                over.append(r)
            else:
                clean.append(r)
        clean_all[arm] = clean
        n = len(rows)
        print(f"  {arm:4s} {n:>5} {' : '.join(str(hist[k]) for k in range(4)):>14} "
              f"{hist[3] + hist[4]:>6} {len(jam):>4} {len(over):>5} {len(clean):>7} "
              f"{(100 * len(clean) / n if n else 0):>6.1f}%")
    print("  (raw=3 is P107/P108's endpoint; jam = the descent's `end > 15 mm`, i.e.")
    print("   the plates blocked on the payload; over = `aper < dia-4 mm` or")
    print("   `F > 3*cap*1.5`.  Only CLEAN is the registered endpoint.)")

    # ---------------------------------------------------------------- 2
    print("\n2. THE COUNT  (placed / attempts, per seed and pooled)")
    print("=" * 100)
    print(f"  {'arm':4s} " + " ".join(f"{f's{s}':>10}" for s in SEEDS) + f" {'pooled':>12}")
    for arm, per in data.items():
        cellsn = []
        for s in SEEDS:
            if s in per:
                cellsn.append((per[s]["placed"], per[s]["att"]))
        line = f"  {arm:4s} " + " ".join(f"{p:>4d}/{n:<5d}" for p, n in cellsn)
        tp, tn = sum(p for p, _ in cellsn), sum(n for _, n in cellsn)
        line += f" {tp:>5d}/{tn:<4d} {100 * tp / tn:5.1f}%" if tn else ""
        print(line)
    cp = sum(d["placed"] for d in data.get("C", {}).values())
    cn = sum(d["att"] for d in data.get("C", {}).values())
    tp = sum(d["placed"] for d in data.get("T", {}).values())
    tn = sum(d["att"] for d in data.get("T", {}).values())
    if cn and tn:
        print(f"  exact two-sided Fisher, pooled: p = {fisher(cp, cn, tp, tn):.3f}")
        print("  per seed:")
        for s in SEEDS:
            if s in data["C"] and s in data["T"]:
                a, na = data["C"][s]["placed"], data["C"][s]["att"]
                b, nb = data["T"][s]["placed"], data["T"][s]["att"]
                print(f"    seed {s:3d}: C {a}/{na} vs T {b}/{nb}  delta {b / nb - a / na:+.3f}"
                      f"  p = {fisher(a, na, b, nb):.3f}")

    # ---------------------------------------------------------------- 3
    print("\n3. THE CLASS  (centring, grip, ejection, crush)")
    print("=" * 100)
    print(f"  {'arm':4s} {'in-ring':>8} {'off0 p50':>9} {'off-off0':>9} "
          f"{'>-2mm':>7} {'legs':>5} {'seated':>7} {'fmin p50':>9} {'sep-dia<0':>10}")
    for arm, per in data.items():
        rows = [r for s in per.values() for r in s["cage"]]
        inr = [r for r in rows if r["off0"] == r["off0"] and r["off0"] < 20.0]
        d = [r["off"] - r["off0"] for r in inr if r["off"] == r["off"]]
        legs = [l for s in per.values() for l in s["legs"] if l["leg"] == "grasp_lift"]
        seated = [l for l in legs if l["fmax"] > 1.0]
        seps = [v for s in per.values() for lst in s["sep"].values() for v in lst]
        print(f"  {arm:4s} {len(inr):>8} "
              f"{(st.median([r['off0'] for r in inr]) if inr else float('nan')):>9.1f} "
              f"{(st.median(d) if d else float('nan')):>+9.2f} "
              f"{sum(1 for v in d if v < -2.0):>7} {len(legs):>5} {len(seated):>7} "
              f"{(st.median([l['fmin'] for l in seated]) if seated else float('nan')):>9.2f} "
              f"{sum(1 for v in seps if v < -15.0):>10}")
    print("  (a negative `off-off0` is the payload moving TOWARD the ring's axis;")
    print("   `sep-dia<0` counts legs past the -15 mm crush rule.)")

    # ---------------------------------------------------------------- 4
    print("\n4. THE GUARDS  (landing, budgets, slots, new reasons)")
    print("=" * 100)
    for arm, per in data.items():
        ntr = sum(len(s["trace"]) for s in per.values())
        present = [t for s in per.values() for t in s["trace"] if float(t["rb"]) >= 0.0]
        lost = sum(1 for t in present if str(t["on"]) == "False")
        upstream = ntr - len(present)
        vmax = max((v for s in per.values() for v in s["vmax"]), default=float("nan"))
        att = sum(s["att"] for s in per.values())
        print(f"  {arm:4s} place traces {ntr:>3} (payload present {len(present)}, "
              f"off-belt {lost}; upstream-lost {upstream})  "
              f"descents |v|max {vmax:.3f} (budget 0.160-0.161)  "
              f"attempts {att}/{10 * len(per)}")
    keys = {}
    for arm, per in data.items():
        for s in per.values():
            for k, v in s["notes"].items():
                keys.setdefault(k, {}).setdefault(arm, 0)
                keys[k][arm] += v
    if keys:
        print("\n  failure-reason keys (digits normalised):")
        for k, per in sorted(keys.items()):
            print(f"    {k[:78]:78s} C={per.get('C', 0):3d} T={per.get('T', 0):3d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
