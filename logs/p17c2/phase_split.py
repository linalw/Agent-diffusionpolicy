#!/usr/bin/env python3
"""P18-C part 2: the phase-aware separability read (hold vs probe-1).

The part-1 script (`threshold_analysis.py`) evaluates a detector over the whole
monitored span.  This part separates the two phases because they differ in *two*
ways that decide the calibration:

  * sampling: the trace samples `hold` every 2 ticks and `probe1` every tick, so
    a trace-level run of m samples is m ticks on probe1 and m..2m ticks on hold;
  * mechanism: the hold walks are long sustained slides, the ok transients are
    short probe-1 spikes.

Reads the same corpora via `threshold_analysis` and prints:
  P1  per class/phase: the per-attempt max rate + the max run above thresholds;
  P2  the "sustained rate at run length L" per attempt (the resolution-robust
      statistic: the highest rate a run of >= L samples sustains);
  P3  the candidate gate rules evaluated phase-aware (probe1 rows = ticks; hold
      rows weighted 1..2 ticks) with the confusion on the controls;
  P4  the ok-class hold-phase headroom (the highest hold rate an ok attempt
      reaches - the threshold a hold-phase fire needs).

Usage:  python3 logs/p17c2/phase_split.py > logs/p17c2/phase_split_tables.txt
"""
from __future__ import annotations

import importlib.util
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ta", HERE / "threshold_analysis.py")
ta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ta)

THRESHOLDS = [40, 60, 80, 100, 120, 150, 200, 250, 300]


def max_run(rates, thr):
    best = run = 0
    for r in rates:
        run = run + 1 if r >= thr else 0
        best = max(best, run)
    return best


def sustained(rates, L):
    """The highest rate sustained over >= L consecutive samples (0 if none)."""
    best = 0.0
    for i in range(len(rates) - L + 1):
        best = max(best, min(rates[i:i + L]))
    return best


def phase_rates(a, phase):
    return [r for r, p in zip(a["rates_world"], a["phases"]) if p == phase]


def pct(vals, q):
    if not vals:
        return float("nan")
    vals = sorted(vals)
    k = min(len(vals) - 1, max(0, int(round(q / 100.0 * (len(vals) - 1)))))
    return vals[k]


def main():
    control = ta.load_corpus(ta.CONTROL, "control")
    gate = ta.load_corpus(ta.GATE, "gate")

    for name, attempts in (("controls (P14-B)", control), ("gate-ON (stage P)", gate)):
        print(f"== {name}: per-phase per-attempt max rate ==")
        print("| class | n | hold p50 | hold p90 | hold max | probe1 p50 | probe1 p90 | "
              "probe1 max |")
        print("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for cls in ("ok", "carried", "B1", "B2", "no-grasp"):
            sel = [a for a in attempts if a["cls"] == cls]
            if not sel:
                continue
            hm = [max(phase_rates(a, "hold") or [0]) for a in sel]
            pm = [max(phase_rates(a, "takeoff_probe") or [0]) for a in sel]
            print(f"| {cls} | {len(sel)} | {pct(hm,50):.1f} | {pct(hm,90):.1f} | "
                  f"{max(hm):.1f} | {pct(pm,50):.1f} | {pct(pm,90):.1f} | {max(pm):.1f} |")

    for name, attempts in (("controls (P14-B)", control), ("gate-ON (stage P)", gate)):
        print(f"\n== {name}: max run above threshold, by phase (median; samples) ==")
        print("| class | phase | n | " + " | ".join(f">={t}" for t in THRESHOLDS) + " |")
        print("| --- | --- | --- | " + " | ".join("---" for _ in THRESHOLDS) + " |")
        for cls in ("ok", "carried", "B1", "B2", "no-grasp"):
            sel = [a for a in attempts if a["cls"] == cls]
            if not sel:
                continue
            for phase in ("hold", "takeoff_probe"):
                med = [statistics.median([max_run(phase_rates(a, phase), t) for a in sel])
                       for t in THRESHOLDS]
                print(f"| {cls} | {phase} | {len(sel)} | "
                      + " | ".join(f"{m:.1f}" for m in med) + " |")

    print("\n== the sustained-rate statistic (controls): the highest rate a run of "
          ">= L samples holds ==")
    print("| class | L=2 p50 | L=2 max | L=3 p50 | L=3 max | L=5 p50 | L=5 max | "
          "L=10 p50 | L=10 max |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for cls in ("ok", "carried", "B1", "B2"):
        sel = [a for a in control if a["cls"] == cls]
        if not sel:
            continue
        cells = []
        for L in (2, 3, 5, 10):
            v = [sustained(a["rates_world"], L) for a in sel]
            cells += [f"{pct(v,50):.1f}", f"{max(v):.1f}"]
        print(f"| {cls} | " + " | ".join(cells) + " |")

    # phase-aware detector: probe1 rows = 1 tick, hold rows = 1..2 ticks
    def detect_phase_aware(a, thr, ticks, window, hold_weight=2):
        """Return (fired, phase).  probe1 rows count 1 tick; hold rows count
        `hold_weight` ticks (the consistent-walk assumption: 2 = the optimistic
        bound, 1 = the conservative bound)."""
        run, used = 0, 0
        for r, d, p in zip(a["rates_world"], a["drifts"], a["phases"]):
            if used >= 2:
                break
            if r >= thr:
                run += hold_weight if (p == "hold" and hold_weight > 1) else 1
            else:
                run = 0
            if run >= ticks and d <= window:
                return True, p
                # (single-response read: the question is whether it fires at all)
        return False, None

    print("\n== candidate rules, phase-aware (controls) ==")
    print("hold_weight=2 (optimistic: a 2-tick hold sample counts 2 ticks) and "
          "hold_weight=1 (conservative).")
    print("| thr | ticks | window | hw | ok FP | B1 | B2 | carried | no-grasp |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    focus = [(60, 3), (60, 6), (60, 8), (60, 10), (70, 4), (80, 2), (80, 3), (80, 4),
             (90, 2), (90, 3), (90, 4), (100, 3), (100, 4), (120, 3)]
    for thr, ticks in focus:
        for hw in (2, 1):
            for window in (60,):
                fp = sum(1 for a in control if a["cls"] == "ok"
                         and detect_phase_aware(a, thr, ticks, window, hw)[0])
                b1 = sum(1 for a in control if a["cls"] == "B1"
                         and detect_phase_aware(a, thr, ticks, window, hw)[0])
                b2 = sum(1 for a in control if a["cls"] == "B2"
                         and detect_phase_aware(a, thr, ticks, window, hw)[0])
                cr = sum(1 for a in control if a["cls"] == "carried"
                         and detect_phase_aware(a, thr, ticks, window, hw)[0])
                print(f"| {thr} | {ticks} | 60 | {hw} | {fp}/45 | {b1}/5 | "
                      f"{b2}/3 | {cr}/7 | {b1+b2}/8 |")

    print("\n== the fired attempts per candidate (controls) ==")
    for thr, ticks in ((60, 3), (80, 2), (90, 2), (60, 8), (80, 4), (90, 3)):
        for hw in (2, 1):
            fires = []
            for a in control:
                f, ph = detect_phase_aware(a, thr, ticks, 60, hw)
                if f:
                    fires.append(f"{a['seed']}/{a['k']}{a['arm'][0]}:{a['cls']}"
                                 f"({a['res']['species']},{ph[:4]})")
            print(f"   ({thr},{ticks}) hw={hw} [{len(fires)}]: " + "  ".join(fires))

    print("\n== per-seed breakdown of the candidate rules (controls) ==")
    for thr, ticks in ((60, 3), (80, 2), (90, 2), (60, 8)):
        print(f"-- ({thr} mm/s, {ticks} samples) --")
        for seed in ("s11", "s5", "s23"):
            sel = [a for a in control if a["seed"] == seed]
            ok = [a for a in sel if a["cls"] == "ok"]
            b1 = [a for a in sel if a["cls"] == "B1"]
            b2 = [a for a in sel if a["cls"] == "B2"]
            cr = [a for a in sel if a["cls"] == "carried"]
            f = lambda lst: sum(1 for a in lst if detect_phase_aware(a, thr, ticks, 60, 2)[0])
            print(f"   {seed}: ok FP {f(ok)}/{len(ok)}, B1 {f(b1)}/{len(b1)}, "
                  f"B2 {f(b2)}/{len(b2)}, carried {f(cr)}/{len(cr)}")

    print("\n== the threshold margin near the ok boundary (2-sample sustained) ==")
    print("| thr | ok FP (2-sample run) | B1 caught | B2 caught |")
    print("| --- | --- | --- | --- |")
    for thr in (75, 80, 82, 85, 88, 90, 95, 100, 110, 120):
        fp = sum(1 for a in control if a["cls"] == "ok"
                 and max_run(phase_rates(a, "takeoff_probe"), thr) >= 2)
        b1 = sum(1 for a in control if a["cls"] == "B1"
                 and (max_run(phase_rates(a, "takeoff_probe"), thr) >= 2
                      or max_run(phase_rates(a, "hold"), thr) >= 1))
        b2 = sum(1 for a in control if a["cls"] == "B2"
                 and (max_run(phase_rates(a, "takeoff_probe"), thr) >= 2
                      or max_run(phase_rates(a, "hold"), thr) >= 1))
        print(f"| {thr} | {fp}/45 | {b1}/5 | {b2}/3 |")

    print("\n== gate-ON: the fired attempts by class (the gate's own rows) ==")
    for seed, logpath, tdir in ta.GATE:
        results, wins, slide = ta.parse_log(logpath)
        pairs = ta.gate_rows_by_arm(slide)
        for side, prs in pairs.items():
            att = sorted([a for a in gate if a["seed"] == seed and a["arm"] == side],
                         key=lambda a: a["k"])
            for k, pr in enumerate(prs):
                if k >= len(att):
                    continue
                a = att[k]
                if pr["hold"]["events"] + pr["probe1"]["events"] > 0:
                    print(f"   {seed}/{a['k']} {side} {a['cls']:8s} "
                          f"{a['res']['species']:10s} hold {pr['hold']['rate_max']:6.1f} "
                          f"probe1 {pr['probe1']['rate_max']:6.1f} "
                          f"drift_max {max(pr['hold']['drift_max'], pr['probe1']['drift_max']):6.1f} "
                          f"events {pr['hold']['events']+pr['probe1']['events']}")

    print("\n== per-attempt maxes for the walked B1s and the ok headroom ==")
    for a in control:
        if a["cls"] in ("B1", "B2"):
            hr = max(phase_rates(a, "hold") or [0])
            pr = max(phase_rates(a, "takeoff_probe") or [0])
            print(f"   {a['seed']}/{a['k']} {a['arm']} {a['cls']} "
                  f"{a['res']['species']}: hold max {hr:.1f}, probe1 max {pr:.1f}, "
                  f"sustained L2 {sustained(a['rates_world'],2):.1f} "
                  f"L3 {sustained(a['rates_world'],3):.1f} "
                  f"L5 {sustained(a['rates_world'],5):.1f} "
                  f"L10 {sustained(a['rates_world'],10):.1f}")

    # the ok-class hold headroom: the highest hold rate an ok attempt reaches
    print("\n== the ok-class hold headroom (the threshold a hold fire must clear) ==")
    ok_hold = sorted(max(phase_rates(a, "hold") or [0]) for a in control if a["cls"] == "ok")
    print("   ok hold per-attempt max (mm/s), sorted: "
          + ", ".join(f"{v:.0f}" for v in ok_hold))
    print(f"   ok hold max = {ok_hold[-1]:.1f} mm/s (p90 {pct(ok_hold,90):.1f}, "
          f"p99 {pct(ok_hold,99):.1f})")
    for thr in (60, 80, 100, 120, 150):
        n2 = sum(1 for a in control if a["cls"] == "ok"
                 and max_run(phase_rates(a, "hold"), thr) >= 2)
        n1 = sum(1 for a in control if a["cls"] == "ok"
                 and max_run(phase_rates(a, "hold"), thr) >= 1)
        print(f"   ok attempts with a >=2-sample (>=4-tick) hold run above {thr}: {n2}/45; "
              f"a single over-band hold sample: {n1}/45")

    print("\n== the probe-1 headroom ==")
    for thr in (60, 80, 90, 100, 120):
        for L in (2, 3, 5):
            n = sum(1 for a in control if a["cls"] == "ok"
                    and max_run(phase_rates(a, "takeoff_probe"), thr) >= L)
            b = sum(1 for a in control if a["cls"] == "B1"
                    and max_run(phase_rates(a, "takeoff_probe"), thr) >= L)
            print(f"   probe1 run>={L} above {thr}: ok {n}/45, B1 {b}/5")


if __name__ == "__main__":
    main()
