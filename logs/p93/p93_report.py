"""P93 report: the four-seed supply-band battery, its classes, guards and verdict.

    python3 logs/p93/p93_report.py              # all sections, stdout
    python3 logs/p93/p93_report.py --check      # exit != 0 if an input is missing

Read-only. The class split is `logs/p92/census.py`'s classifier, unchanged, so
P92's census and this report cannot drift apart (a `cnp` is a payload that left a
pinch that existed; a `never_held` is a close that never made one; the attempt's
own `[carry]` row is the evidence). Wall and interval are `logs/p80/p80lib.py`'s.

Seeds 5 and 6 are P92's cells (`logs/p92/{C5,T5,C6,T6}.log`, committed); seeds
101 and 202 are this phase's. The endpoints, the guards and the decision rule
are `logs/p93/PREREG.md`'s (section numbers below are that document's).
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "logs/p92"))
import census  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "p80lib", os.path.join(ROOT, "logs/p80/p80lib.py"))
p80lib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p80lib)

#: (seed, control log, treatment log). Seed 5/6 are the committed P92 cells.
SEEDS = ((5, "logs/p92/C5.log", "logs/p92/T5.log"),
         (6, "logs/p92/C6.log", "logs/p92/T6.log"),
         (101, "logs/p93/C101.log", "logs/p93/T101.log"),
         (202, "logs/p93/C202.log", "logs/p93/T202.log"))
CELL = {5: ("C5", "T5"), 6: ("C6", "T6"), 101: ("C101", "T101"), 202: ("C202", "T202")}
LANDING = re.compile(
    r"\[task\]   place trace \w+: release_bottom=(?P<bottom>[+\-\d.]+)mm .*?"
    r"on_belt=(?P<ok>True|False)")
LATERAL = re.compile(r"\[fruit\] \[supply\].*?lateral x=(?P<xmin>[\d.]+)-(?P<xmax>[\d.]+) m")
BUDGET_LEG = re.compile(r"^ +\d+ +[\d.]+c")
#: P92's control batches, for the replay clause at seeds 5/6 (G5, recorded)
RECORD = {5: "logs/p91/C5.log", 6: "logs/p91/C6.log"}


def path(p: str) -> str:
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def f(v, nd=2):
    return "-" if v is None else f"{v:.{nd}f}"


def cell(p: str) -> dict:
    if not os.path.exists(path(p)):
        return {"missing": True, "path": p}
    d = census.parse(path(p))
    m = p80lib.metrics(path(p))
    text = open(path(p), errors="replace").read()
    lat = LATERAL.search(text)
    traces = [{"bottom": float(t["bottom"]), "on_belt": t["ok"] == "True"}
              for t in LANDING.finditer(text)]
    bud = os.path.splitext(p)[0] + ".budgets"
    legs = over = None
    fp = None
    if os.path.exists(path(bud)):
        bt = open(path(bud), errors="replace").read()
        rows = [ln for ln in bt.splitlines() if BUDGET_LEG.match(ln)]
        legs = len(rows)
        over = [ln for ln in rows if not ln.rstrip().endswith(" ok")]
        mm = re.search(r"fingerprint: (matches|DIFFERS)", bt)
        fp = mm.group(1) if mm else None
    return {"missing": False, "path": p, "attempts": d["attempts"], "noelig": d["noelig"],
            "diverts": d["diverts"], "metrics": m, "traces": traces,
            "lateral": (float(lat["xmin"]), float(lat["xmax"])) if lat else None,
            "cls": [a["cls"] for a in d["attempts"]],
            "legs": legs, "over": over, "fp": fp}


def n(c: dict, name: str) -> int:
    return c["cls"].count(name)


def xstats(c: dict) -> dict:
    xs = sorted(a["x"] for a in c["attempts"] if a["x"] is not None)
    k = len(xs)
    return {"n": k, "min": xs[0] if k else None,
            "p50": xs[int(0.5 * k)] if k else None,
            "max": xs[-1] if k else None}


def replay(seed: int) -> tuple[bool, str]:
    rec, cur = path(RECORD[seed]), path(SEEDS[0][1] if seed == 5 else SEEDS[1][1])
    a = [ln for ln in open(rec, errors="replace").read().splitlines() if "fruit]" in ln]
    b = [ln for ln in open(cur, errors="replace").read().splitlines() if "fruit]" in ln]
    if len(a) != len(b):
        return False, f"line count {len(a)} vs {len(b)}"
    same = sum(1 for x, y in zip(a, b) if x == y)
    norm = sum(1 for x, y in zip(a, b)
               if x == y or re.sub(r"\((explicit|two-line|default|scope-off)\)", "(o)", x)
               == re.sub(r"\((explicit|two-line|default|scope-off)\)", "(o)", y))
    return norm == len(a), f"{norm}/{len(a)} identical (modulo a profile row's origin label)"


def main(argv) -> int:
    check = "--check" in argv
    bad = 0
    print("=" * 104)
    print("P93 - the re-entry: the supply band's top, four seeds (PREREG logs/p93/PREREG.md)")
    print("=" * 104)

    data = {}
    for seed, c, t in SEEDS:
        data[(seed, "C")] = cell(c)
        data[(seed, "T")] = cell(t)

    # ---- 0 the manipulation ---------------------------------------------- #
    print("\n## 0 the manipulation (PREREG section 2: the build row and the delivered x)")
    print(f"  {'seed':4s} {'arm':3s} {'supply lateral row':>20s} {'n':>3s} {'min':>7s} "
          f"{'p50':>7s} {'max':>7s} {'>0.36':>6s} {'>=0.39':>7s}")
    for seed in (5, 6, 101, 202):
        for arm in ("C", "T"):
            c = data[(seed, arm)]
            if c["missing"]:
                print(f"  {seed:<4d} {arm:3s} MISSING"); bad += 1; continue
            x = xstats(c)
            n36 = sum(1 for a in c["attempts"] if a["x"] is not None and a["x"] > 0.36)
            n39 = sum(1 for a in c["attempts"] if a["x"] is not None and a["x"] >= 0.39)
            lat = f"{c['lateral'][0]:.2f}-{c['lateral'][1]:.2f}" if c["lateral"] else "?"
            print(f"  {seed:<4d} {arm:3s} {lat:>20s} {x['n']:3d} {f(x['min'], 4):>7s} "
                  f"{f(x['p50'], 4):>7s} {f(x['max'], 4):>7s} {n36:6d} {n39:7d}")

    # ---- 1 the class census ---------------------------------------------- #
    print("\n## 1 the class census (PREREG section 3; primary = the never-held class)")
    print(f"  {'seed':4s} {'arm':3s} {'att':>3s} {'placed':>6s} {'cnp':>4s} {'never':>5s} "
          f"{'other':>5s} {'div':>3s} {'starve':>6s} {'s/att':>6s}")
    for seed in (5, 6, 101, 202):
        for arm in ("C", "T"):
            c = data[(seed, arm)]
            if c["missing"]:
                continue
            other = len(c["cls"]) - n(c, "success") - n(c, "cnp") - n(c, "never_held")
            st = c["metrics"]["stats"]
            print(f"  {seed:<4d} {arm:3s} {len(c['cls']):3d} {n(c, 'success'):6d} "
                  f"{n(c, 'cnp'):4d} {n(c, 'never_held'):5d} {other:5d} "
                  f"{len(c['diverts']):3d} {c['noelig']['left'] + c['noelig']['right']:6d} "
                  f"{f(st['per_attempt']):>6s}")
    pooled = {}
    for arm in ("C", "T"):
        have = [data[(s, arm)] for s in (5, 6, 101, 202) if not data[(s, arm)]["missing"]]
        pooled[arm] = {"n": sum(len(c["cls"]) for c in have),
                       "placed": sum(n(c, "success") for c in have),
                       "cnp": sum(n(c, "cnp") for c in have),
                       "never": sum(n(c, "never_held") for c in have),
                       "cells": len(have)}
    print(f"\n  pooled control   : {pooled['C']['placed']}/{pooled['C']['n']} placed "
          f"({pooled['C']['cells']} cells); cnp {pooled['C']['cnp']}, "
          f"never-held {pooled['C']['never']}")
    print(f"  pooled treatment : {pooled['T']['placed']}/{pooled['T']['n']} placed "
          f"({pooled['T']['cells']} cells); cnp {pooled['T']['cnp']}, "
          f"never-held {pooled['T']['never']}")

    # ---- 2 the per-seed ledgers ------------------------------------------ #
    print("\n## 2 the per-seed ledger (the class clause and the count clause)")
    print(f"  {'seed':4s} {'never C->T':>11s} {'placed C->T':>13s} {'cnp C->T':>10s} "
          f"{'chase C->T':>12s}  class / count / guard")
    chase = {}
    for seed in (5, 6, 101, 202):
        c, t = data[(seed, "C")], data[(seed, "T")]
        if c["missing"] or t["missing"]:
            print(f"  {seed:<4d} incomplete"); bad += 1; continue
        cn, tn = n(c, "never_held"), n(t, "never_held")
        cp, tp = n(c, "success"), n(t, "success")
        cc, tc = n(c, "cnp"), n(t, "cnp")
        ch = (c["metrics"]["stats"], t["metrics"]["stats"])
        chc = sum(1 for a in c["attempts"] if "closed" not in str(a))  # placeholder
        # the chase set: the force servo's `closed > 0` rows, per cell
        def chase_count(cell_):
            txt = open(path(cell_["path"]), errors="replace").read()
            tot = 0
            for ln in txt.splitlines():
                if "force servo:" in ln:
                    tot += len([m for m in re.findall(r"closed=([\d.]+)mm", ln)
                                if float(m) > 0])
            return tot
        cch, tch = chase_count(c), chase_count(t)
        chase[seed] = (cch, tch)
        verdicts = []
        verdicts.append("class PASS" if tn <= cn else "class FAIL")
        verdicts.append("count PASS" if tp >= cp else "count FAIL")
        verdicts.append("cnp PASS" if tc <= cc else "cnp FAIL")
        print(f"  {seed:<4d} {cn:4d} -> {tn:<4d} {cp:4d} -> {tp:<4d} "
              f"{cc:4d} -> {tc:<4d} {cch:4d} -> {tch:<4d}  " + " / ".join(verdicts))

    # ---- 3 the delivered side -------------------------------------------- #
    print("\n## 3 the delivered side (read, never the decision's basis)")
    print(f"  {'seed':4s} {'arm':3s} {'pooled int':>10s} {'p90':>6s} {'L int':>6s} "
          f"{'R int':>6s} {'win/min':>7s} {'batch/min':>9s} {'wall s':>7s} "
          f"{'placed/min wall':>15s}")
    for seed in (5, 6, 101, 202):
        for arm in ("C", "T"):
            c = data[(seed, arm)]
            if c["missing"]:
                continue
            m = c["metrics"]; s = m["stats"]; a = m["per_arm"]
            wpm = (60.0 * m["placed"] / s["wall"]) if s["wall"] else None
            print(f"  {seed:<4d} {arm:3s} {f(m['pooled']['mean']):>10s} "
                  f"{f(m['pooled']['p90']):>6s} "
                  f"{f(a.get('left', {}).get('interval_mean')):>6s} "
                  f"{f(a.get('right', {}).get('interval_mean')):>6s} "
                  f"{f(m['window_rate']):>7s} {f(m['batch_rate']):>9s} "
                  f"{f(s['wall'], 1):>7s} {f(wpm):>15s}")

    # ---- 4 the guards ----------------------------------------------------- #
    print("\n## 4 guards (PREREG section 4)")
    ok = True
    for seed in (5, 6, 101, 202):
        for arm in ("C", "T"):
            c = data[(seed, arm)]
            if c["missing"]:
                continue
            guest = [x for x in c["traces"] if x["bottom"] >= 0.0]
            off = [x for x in guest if not x["on_belt"]]
            print(f"  G2 landing {CELL[seed][0 if arm == 'C' else 1]:5s}: "
                  f"{len(guest)} payload-present releases, on belt "
                  f"{len(guest) - len(off)}/{len(guest)} "
                  f"({'PASS' if not off else 'FAIL'})")
            ok &= not off
    for seed in (5, 6, 101, 202):
        for arm in ("C", "T"):
            tag = CELL[seed][0 if arm == "C" else 1]
            c = data[(seed, arm)]
            if c["missing"]:
                continue
            if c["legs"] is None:
                print(f"  G3 budgets {tag:5s}: budgets file missing "
                      f"(run logs/p93/gates.sh)"); continue
            verdict = "PASS" if not c["over"] else "FAIL"
            print(f"  G3 budgets {tag:5s}: {c['legs']} descent legs, "
                  f"{len(c['over'])} over budget ({verdict}) | fingerprint "
                  f"{c['fp'] or 'n/a'} (recorded, not gated)")
            if c["over"]:
                for ln in c["over"]:
                    print(f"      {ln.strip()}")
    for seed in (5, 6):
        same, how = replay(seed)
        print(f"  G5 the control replays its P91 record (seed {seed}): {how} "
              f"({'PASS' if same else 'FAIL'})")
        ok &= same
    print("  G5 seeds 101/202: a fresh seed has no record to replay (P84's rule) - read "
          "as its own cell, stated not invented")
    short = [CELL[s][0 if a == "C" else 1] for s in (5, 6, 101, 202) for a in ("C", "T")
             if not data[(s, a)]["missing"] and len(data[(s, a)]["cls"]) != 20]
    cells20 = sum(1 for s in (5, 6, 101, 202) for a in ("C", "T")
                  if not data[(s, a)]["missing"] and len(data[(s, a)]["cls"]) == 20)
    print(f"  G6 attempts: {cells20}/8 cells at 20 attempts"
          f"{'' if not short else ' - short: ' + ','.join(short)} "
          f"{'PASS' if cells20 == 8 and not short else 'incomplete'}")
    ok &= cells20 == 8 and not short
    for seed in (5, 6, 101, 202):
        for arm in ("C", "T"):
            c = data[(seed, arm)]
            if c["missing"]:
                continue
            for ln in c["diverts"]:
                print(f"    {CELL[seed][0 if arm == 'C' else 1]} diversion: "
                      f"{ln.get('fruit')} index={ln.get('index')} after {ln.get('n')}")

    # ---- 5 the verdict ---------------------------------------------------- #
    print("\n## 5 the verdict (PREREG section 5, applied to the numbers above)")
    cls_clause = pooled["T"]["never"] <= pooled["C"]["never"]
    per_seed_class = all(n(data[(s, "T")], "never_held") <= n(data[(s, "C")], "never_held")
                         for s in (5, 6, 101, 202)
                         if not (data[(s, "C")]["missing"] or data[(s, "T")]["missing"]))
    count_clause = (pooled["T"]["placed"] >= pooled["C"]["placed"]) and all(
        n(data[(s, "T")], "success") >= n(data[(s, "C")], "success")
        for s in (5, 6, 101, 202)
        if not (data[(s, "C")]["missing"] or data[(s, "T")]["missing"]))
    cnp_ok = all(n(data[(s, "T")], "cnp") <= n(data[(s, "C")], "cnp")
                 for s in (5, 6, 101, 202)
                 if not (data[(s, "C")]["missing"] or data[(s, "T")]["missing"]))
    print(f"  1 class: pooled never-held {pooled['C']['never']} -> {pooled['T']['never']} "
          f"({'PASS' if cls_clause else 'FAIL'}), per seed "
          f"{[(s, n(data[(s, 'C')], 'never_held'), n(data[(s, 'T')], 'never_held')) for s in (5, 6, 101, 202)]} "
          f"({'PASS' if per_seed_class else 'FAIL'})")
    print(f"  2 count: pooled placed {pooled['C']['placed']} -> {pooled['T']['placed']} "
          f"({'PASS' if count_clause else 'FAIL'})")
    print(f"  3 guards: G2 {'PASS' if ok else 'FAIL'} | G1 cnp per seed "
          f"{'PASS' if cnp_ok else 'FAIL'} | G3 read in section 4 | G5/G6 above | "
          f"G7/G8 external (selfcheck, accept, 211)")
    adopt = cls_clause and per_seed_class and count_clause and cnp_ok and ok
    print(f"  -> {'ADOPT (subject to G3/G7/G8, section 4 and the phase record)' if adopt else 'NOT ADOPTED'}")
    if check:
        print(f"\n[check] missing inputs: {bad}")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
