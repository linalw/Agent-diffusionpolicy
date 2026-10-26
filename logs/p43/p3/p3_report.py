#!/usr/bin/env python3
"""P43 phase 3: the arm park re-measured on the P41 grip-profile tree.

    python3 logs/p43/p3/p3_report.py --dir logs/p43/p3 --a A --b B
    python3 logs/p43/p3/p3_report.py --self-test

Read-only. Parses the `A_N.log` / `B_N.log` written by `scripts/112_rl_ab.sh`
(the P43 phase-3 batch) through the pinned parsers:

  * the episode rows through `scripts/113_rl_report.py` (the `P37.read_dir`
    loader, so the class definitions are the W7-B/W7-C/P33 convention:
    ok / no-contact = `grasped=False` / carried-not-placed = `grasped=True,
    placed=False`),
  * the `[park]` rows through `logs/p35/park_ab_report.py` (the P35 instrument).

The registered analysis is `logs/p43/PREREG_DRAFT.md` L3 (phase 3), as amended
by the Oracle: **P2 (right-arm placed) is the primary**, the right-arm carried
class is the branch-A contrast, and **P3 (the pooled rate) is an
arm-standardised report only** - P37 showed the pooled rate moves with the
realised arm mix (58.7 -> 65.3 %) at a flat right-arm rate, so it is not a test.

The endpoint order is the registered one:

  P8  the check (read FIRST, gates the read): M1-held + M1-applied + M2a on the
      park arm, the shipped-pose negative on the control, and the band census.
  P0  the baseline read (P0b: publish it regardless) -> branch A / branch B.
  P1  branch A only: exact two-sided Fisher on the right-arm carried 2x2.
  P2  the primary: right-arm placed, delta >= -MARGIN, standardised signs agree.
  P3  the pooled placed rate, raw and arm-standardised (report only).
  P4  the left arm (the park's no-op guard).
  P5  new failure reasons (113's number normalisation).
  P6  the median cycle (bar: not worse by > 5 %).
  P7  the run level (B >= A in >= 4/5 runs on the primary).
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import math
import os
import re
import statistics as st
import sys
from collections import Counter

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P37 = _load("p37_report", os.path.join(REPO, "logs/p37/p37_report.py"))
PARK = P37.PARKMOD                       # logs/p35/park_ab_report.py
RL = P37.RL                              # scripts/113_rl_report.py
klass = PARK.klass
read_refs = PARK.read_refs
qvec = PARK.qvec
fnum = PARK.fnum
plate = P37.plate

#: Pre-registered constants (PREREG_DRAFT L3.2/L3.3 + PARK_STATUS 3).
MARGIN = 0.10            # P2: right-arm placed non-inferiority
CYCLE_BAR = 1.05         # P6 (P37's S4 bar)
LEFT_GUARD = 0.05        # P4: the left arm may not regress by more than this
BRANCH_A_BASE = 0.40     # P0: A's right carried rate at/above this -> branch A
M1_HOLD_MAX = 0.02       # rad, vs the pose the reset ACHIEVED
M1_BACK_MAX = 0.15       # max|q - back|   (is it the park?)
M1_READY_MIN = 0.30      # max|q - ready|  (and not the shipped pose?)
M1_READY_MAX = 0.15      # max|q - ready|  (arm A: is it the shipped pose?)
DRIFT_MAX = 0.02
M2_MAX_FRAC = 0.10
RUN_LEVEL_MIN = 4        # P7: B >= A in >= 4/5 runs


# --------------------------------------------------------------------- math -- #
def fisher_two_sided(a1: int, a0: int, b1: int, b0: int) -> float:
    """Exact two-sided Fisher (the "sum of tables no more likely" convention)."""
    n = a1 + a0 + b1 + b0
    row1, col1 = a1 + a0, a1 + b1
    if n == 0 or row1 == 0 or col1 == 0:
        return 1.0
    lo, hi = max(0, col1 - (n - row1)), min(row1, col1)

    def prob(k: int) -> float:
        return (math.comb(row1, k) * math.comb(n - row1, col1 - k)
                / math.comb(n, col1))

    obs = prob(a1)
    return min(1.0, sum(prob(k) for k in range(lo, hi + 1)
                        if prob(k) <= obs * (1.0 + 1e-9)))


def fisher_one_sided_greater_a(a1: int, a0: int, b1: int, b0: int) -> float:
    """One-sided P(X >= a1) under the margins: **A** carries more than B.

    X = arm A's count of the positive class, X ~ Hypergeom(n, col1, row1). This
    is the registered direction of the carried contrast (the park must *reduce*
    the carried class), so a small p is evidence for the park.
    """
    n = a1 + a0 + b1 + b0
    row1, col1 = a1 + a0, a1 + b1
    if n == 0 or row1 == 0 or col1 == 0:
        return 1.0
    hi = min(row1, col1)
    return min(1.0, sum(math.comb(row1, k) * math.comb(n - row1, col1 - k)
                        for k in range(a1, hi + 1))
               / math.comb(n, col1))


def mh_cmh(tables: list[tuple[int, int, int, int]]) -> dict:
    """Mantel-Haenszel OR + CMH chi-square (1 df) over (a1, a0, b1, b0) strata."""
    num = den = 0.0
    dev = var = 0.0
    for a1, a0, b1, b0 in tables:
        n = a1 + a0 + b1 + b0
        if n < 2:
            continue
        row1, col1 = a1 + a0, a1 + b1
        num += a1 * b0 / n
        den += a0 * b1 / n
        exp = row1 * col1 / n
        dev += a1 - exp
        var += row1 * col1 * (n - row1) * (n - col1) / (n * n * (n - 1))
    or_ = (num / den) if den else float("nan")
    chi2 = (dev * dev / var) if var else float("nan")
    # 1-df chi-square survival = 2 * (1 - Phi(sqrt(chi2))) = erfc(sqrt(chi2/2))
    p = math.erfc(math.sqrt(max(0.0, chi2) / 2.0)) if chi2 == chi2 else float("nan")
    return {"or": or_, "chi2": chi2, "p": p}


def arm_standardised(a: list[dict], b: list[dict], w_right: float) -> dict:
    """Pooled placed rate at a FIXED arm mix (report only, P3).

    `w_right` is the share of episodes given to the right arm; the left gets the
    rest. The realised mix differs between arms (the arm follows the fruit's
    grade and the streams diverge), which is exactly why the raw pooled rate is
    not a test (P37: 58.7 -> 65.3 % at a flat right rate).
    """
    out = {}
    for label, rows in (("a", a), ("b", b)):
        right = [r for r in rows if r["arm"] == "right"]
        left = [r for r in rows if r["arm"] == "left"]
        pr = (sum(1 for r in right if plate(r)) / len(right)) if right else float("nan")
        pl = (sum(1 for r in left if plate(r)) / len(left)) if left else float("nan")
        out[label] = {"right": pr, "left": pl,
                      "rate": w_right * pr + (1.0 - w_right) * pl}
        out[label + "_n"] = (len(right), len(left))
    out["delta"] = out["b"]["rate"] - out["a"]["rate"]
    return out


# --------------------------------------------------------------- endpoints -- #
def rate(rows: list[dict]) -> float:
    return (sum(1 for r in rows if plate(r)) / len(rows)) if rows else float("nan")


def carried(rows: list[dict]) -> int:
    return sum(1 for r in rows if klass(r) == "carried")


def nocontact(rows: list[dict]) -> int:
    return sum(1 for r in rows if klass(r) == "no-contact")


def class_table(label: str, rows: list[dict]) -> None:
    def one(name: str, sel: list[dict]) -> str:
        c = Counter(klass(r) for r in sel)
        return (f"  {name:5s} n={len(sel):3d} ok={c['ok']:3d} "
                f"carried={c['carried']:3d} no-grasp={c['no-contact']:3d} "
                f"other={c['other']:3d} | placed {c['ok']}/{len(sel)}"
                f" = {100.0 * c['ok'] / len(sel) if sel else float('nan'):5.1f}%"
                f" | carried rate "
                f"{100.0 * c['carried'] / len(sel) if sel else float('nan'):5.1f}%")

    print(f"== arm {label}: the classes")
    print(one("all", rows))
    print(one("left", [r for r in rows if r["arm"] == "left"]))
    print(one("right", [r for r in rows if r["arm"] == "right"]))


# ------------------------------------------------------------------- check -- #
def check_arm(label: str, recs: list[dict], ready: list[float],
              back: list[float], parked: bool) -> dict:
    """P8 on one arm: the `[park]` rows, banded and inactive=left."""
    pop = [r for r in recs if r["arm"] == "right" and r["park"]["band_calls"] > 0]
    if not pop:
        return {"label": label, "n": 0, "ok": False, "missing": len(
            [r for r in recs if r["arm"] == "right" and r["park"] is None])}
    hold = [r for r in pop
            if r["park"]["m1_hold_ok"] == 1
            and r["park"]["m1_hold"] == r["park"]["m1_hold"]
            and r["park"]["m1_hold"] <= M1_HOLD_MAX]
    m2 = [r for r in pop
          if r["park"]["max_frac"] == r["park"]["max_frac"]
          and 0.0 <= r["park"]["max_frac"] < M2_MAX_FRAC]
    applied_settled, applied_q = [], []
    for r in pop:
        for field, sink in (("q_settled", applied_settled), ("q", applied_q)):
            q = qvec(r["park"].get(field) or "")
            if len(q) != 7:
                continue
            d_back = max(abs(x - y) for x, y in zip(q, back))
            d_ready = max(abs(x - y) for x, y in zip(q, ready))
            drift = r["park"]["drift"]
            if parked:
                good = (d_back <= M1_BACK_MAX and d_ready >= M1_READY_MIN
                        and drift == drift and drift <= DRIFT_MAX)
            else:
                good = d_ready <= M1_READY_MAX
            sink.append((r, d_back, d_ready, drift, good))
    hidden = sum(1 for r in recs if r["arm"] == "right"
                 for call in r["calls"] if call["px"] == 0)
    calls = sum(len(r["calls"]) for r in recs if r["arm"] == "right")
    arm_px = sum(1 for r in recs if r["arm"] == "right"
                 for call in r["calls"] if call["arm_px"] > 0)
    app_s = [t for t in applied_settled if t[4]]
    app_q = [t for t in applied_q if t[4]]
    print(f"== arm {label}: the manipulation check (P8) - {len(pop)} banded, "
          f"right-active episodes (inactive=left)")
    print(f"  M1-held vs the pose the reset ACHIEVED (<= {M1_HOLD_MAX} rad): "
          f"{len(hold)}/{len(pop)} | median "
          f"{st.median([r['park']['m1_hold'] for r in pop]):.3f} rad | "
          f"achieved-vs-commanded residual median "
          f"{st.median([r['park']['m1_cmd'] for r in pop]):.3f} rad")
    if parked:
        print(f"  M1-applied, P35 read (`q_settled`, nearest reference + drift): "
              f"{len(app_s)}/{len(pop)} | |q-back| median "
              f"{st.median([t[1] for t in applied_settled]):.3f} | |q-ready| "
              f"median {st.median([t[2] for t in applied_settled]):.3f} | drift "
              f"max {max(t[3] for t in applied_settled):.3f} rad")
        print(f"  M1-applied, P37 read (`q`, the first non-stale call): "
              f"{len(app_q)}/{len(pop)} | |q-back| median "
              f"{st.median([t[1] for t in applied_q]):.3f} | |q-ready| median "
              f"{st.median([t[2] for t in applied_q]):.3f}")
    else:
        print(f"  the shipped-pose negative (|q-ready| <= {M1_READY_MAX}): "
              f"{len(app_s)}/{len(pop)} | |q-ready| median "
              f"{st.median([t[2] for t in applied_settled]):.3f} | "
              f"|q-back| median {st.median([t[1] for t in applied_settled]):.3f}")
    print(f"  M2a the arm term at the band's WORST call (< {M2_MAX_FRAC}): "
          f"{len(m2)}/{len(pop)} | worst-call median "
          f"{st.median([r['park']['max_frac'] for r in pop]):.3f} "
          f"(max {max(r['park']['max_frac'] for r in pop):.3f})"
          + ("" if parked else "  [the CONTROL readout - fails by design]"))
    print(f"  band census (inactive=left): fully hidden {hidden}/{calls} = "
          f"{100.0 * hidden / calls if calls else float('nan'):5.1f}% | any "
          f"inactive-arm pixel {arm_px}/{calls} = "
          f"{100.0 * arm_px / calls if calls else float('nan'):5.1f}%")
    # The gate is arm-specific and that is the whole point of the contrast:
    # the control must hold its achieved `ready` pose and must NOT carry the
    # park; its M2a and its band census are the pre-treatment readout (P35:
    # 0/51 and 68.1 % fully hidden), not gate items.
    ok = ((len(hold) == len(pop) and len(app_s) == len(pop)
           and len(app_q) == len(pop) and len(m2) == len(pop) and hidden == 0)
          if parked else (len(hold) == len(pop) and len(app_s) == len(pop)))
    print(f"  -> arm {label} check: {'PASS' if ok else 'FAIL'}"
          f" ({'M1-held + M1-applied + M2a + 0 fully-hidden calls' if parked else 'M1-held + the shipped-pose negative'})")
    return {"label": label, "n": len(pop), "ok": ok, "hold": len(hold),
            "m2": len(m2), "applied": len(app_s), "hidden": hidden,
            "calls": calls, "missing": 0}


# -------------------------------------------------------------------- main -- #
def analyse(directory: str, a_label: str, b_label: str) -> dict:
    arms = {a_label: P37.read_dir(directory, a_label),
            b_label: P37.read_dir(directory, b_label)}
    if not arms[a_label] or not arms[b_label]:
        raise SystemExit(f"no {a_label}_*/{b_label}_*.log pairs in {directory}")
    runs = sorted(set(arms[a_label]) & set(arms[b_label]))
    if not runs:
        raise SystemExit("the arms share no run index (A_1.log / B_1.log ...)")
    ready, back = read_refs()

    pooled = {label: [dict(e, run=run) for run in runs
                      for e in arms[label][run]["eps"]]
              for label in (a_label, b_label)}
    right = {label: [e for e in pooled[label] if e["arm"] == "right"]
             for label in (a_label, b_label)}
    left = {label: [e for e in pooled[label] if e["arm"] == "left"]
            for label in (a_label, b_label)}

    # ---- P8: the check, read before any outcome ---------------------------- #
    print("#" * 78)
    print(f"# P43 phase 3 - the arm park on the P41 grip-profile tree "
          f"({directory})")
    print("#" * 78)
    print(f"runs paired: {runs} | episodes per arm: "
          f"{len(pooled[a_label])} / {len(pooled[b_label])}")
    print()
    recs = {}
    for label in (a_label, b_label):
        items = []
        missing = 0
        for run in runs:
            for e in arms[label][run]["eps"]:
                park = arms[label][run]["park"].get(e["index"])
                if park is None:
                    missing += 1
                items.append({"run": run, "ep": e["index"], "arm": e["arm"],
                              "park": park or {"band_calls": -1, "m1_hold": float("nan"),
                                               "m1_hold_ok": 0, "m1_cmd": float("nan"),
                                               "max_frac": float("nan"), "drift": float("nan"),
                                               "q": "", "q_settled": ""},
                              "calls": arms[label][run]["calls"].get(e["index"], [])})
        recs[label] = items
        if missing:
            print(f"  !! arm {label}: {missing} episodes have no [park] row "
                  f"- the read is refused (P36 M2 count invariance)")
    checks = {a_label: check_arm(a_label, recs[a_label], ready, back, parked=False),
              b_label: check_arm(b_label, recs[b_label], ready, back, parked=True)}
    print()
    missing_any = sum(c.get("missing", 0) for c in checks.values())
    p8 = (checks[a_label]["ok"] and checks[b_label]["ok"] and not missing_any)
    print(f"P8 the check: {'PASS' if p8 else 'FAIL'} "
          f"({a_label}: {'PASS' if checks[a_label]['ok'] else 'FAIL'}, "
          f"{b_label}: {'PASS' if checks[b_label]['ok'] else 'FAIL'})")
    print()

    # ---- P0 / P0b: the baseline ------------------------------------------- #
    for label in (a_label, b_label):
        class_table(label, pooled[label])
        print()
    n_r = {label: len(right[label]) for label in (a_label, b_label)}
    car_r = {label: carried(right[label]) for label in (a_label, b_label)}
    ok_r = {label: sum(1 for e in right[label] if plate(e))
            for label in (a_label, b_label)}
    base = car_r[a_label] / n_r[a_label] if n_r[a_label] else float("nan")
    branch = "A" if base >= BRANCH_A_BASE else "B"
    print(f"P0 the baseline: {a_label}'s right-arm carried rate = "
          f"{car_r[a_label]}/{n_r[a_label]} = {base:.3f} -> "
          f"{'BRANCH A (the class contrast is evaluable)' if branch == 'A' else 'BRANCH B (the class contrast is a report only; the placed read carries it)'}")
    print(f"   {b_label}'s right-arm carried rate = {car_r[b_label]}/{n_r[b_label]}"
          f" = {(car_r[b_label] / n_r[b_label]) if n_r[b_label] else float('nan'):.3f}")
    print(f"P0b the post-P41 direct baseline ({a_label}, the shipped env, no park): "
          f"right {ok_r[a_label]}/{n_r[a_label]} placed, {car_r[a_label]} carried | "
          f"left {sum(1 for e in left[a_label] if plate(e))}/{len(left[a_label])} "
          f"placed, {carried(left[a_label])} carried | pooled "
          f"{sum(1 for e in pooled[a_label] if plate(e))}/{len(pooled[a_label])}")
    print(f"    ({b_label}: right {ok_r[b_label]}/{n_r[b_label]} placed, "
          f"{car_r[b_label]} carried | left "
          f"{sum(1 for e in left[b_label] if plate(e))}/{len(left[b_label])} "
          f"placed, {carried(left[b_label])} carried | pooled "
          f"{sum(1 for e in pooled[b_label] if plate(e))}/{len(pooled[b_label])})")
    print()

    # ---- P1: the right-arm carried contrast (branch A) --------------------- #
    p1 = fisher_two_sided(car_r[a_label], n_r[a_label] - car_r[a_label],
                          car_r[b_label], n_r[b_label] - car_r[b_label])
    p1_less = fisher_one_sided_greater_a(car_r[a_label], n_r[a_label] - car_r[a_label],
                                         car_r[b_label], n_r[b_label] - car_r[b_label])
    print(f"P1 the right-arm carried 2x2 (carried / not): "
          f"{a_label} {car_r[a_label]}/{n_r[a_label]} "
          f"({100.0 * base:5.1f}%) vs {b_label} {car_r[b_label]}/{n_r[b_label]} "
          f"({100.0 * car_r[b_label] / n_r[b_label] if n_r[b_label] else float('nan'):5.1f}%) "
          f"| contrast {(car_r[b_label] / n_r[b_label] - base) if n_r[a_label] and n_r[b_label] else float('nan'):+.3f}")
    print(f"   exact two-sided Fisher p = {p1:.4g} | one-sided "
          f"(B fewer carried) p = {p1_less:.4g} | "
          f"{'significant' if p1 <= 0.05 else 'NOT significant'} at 0.05"
          + ("  [the branch-A gate]" if branch == "A"
             else "  [a REPORT in branch B - not the gate]"))
    print()

    # ---- P2: the primary (right-arm placed) ------------------------------- #
    d_place = ((ok_r[b_label] / n_r[b_label]) - (ok_r[a_label] / n_r[a_label])
               if n_r[a_label] and n_r[b_label] else float("nan"))
    p_place = fisher_two_sided(ok_r[a_label], n_r[a_label] - ok_r[a_label],
                               ok_r[b_label], n_r[b_label] - ok_r[b_label])
    p_ni = P37.exact_noninferiority_p(ok_r[b_label], n_r[b_label],
                                      ok_r[a_label], n_r[a_label], margin=MARGIN)
    lo_new = P37.newcombe_lower(ok_r[b_label], n_r[b_label],
                                ok_r[a_label], n_r[a_label])
    species = P37.standardise(right[a_label], right[b_label],
                              key=lambda row: row["category"])
    bounds = P37.tertile_bounds(right[a_label] + right[b_label])
    diam = P37.standardise(right[a_label], right[b_label],
                           key=P37.tertile_key(bounds))
    std_delta = (species["rate"] - species["rate_a"]
                 if species["rate"] == species["rate"] else float("nan"))
    diam_delta = (diam["rate"] - diam["rate_a"]
                  if diam["rate"] == diam["rate"] else float("nan"))
    signs_agree = (std_delta == std_delta and diam_delta == diam_delta
                   and (std_delta >= 0) == (d_place >= 0)
                   and (diam_delta >= 0) == (d_place >= 0))
    p2 = d_place >= -MARGIN and signs_agree
    print(f"P2 the PRIMARY - right-arm placed: {a_label} {ok_r[a_label]}/{n_r[a_label]} "
          f"= {ok_r[a_label] / n_r[a_label]:.3f} -> {b_label} "
          f"{ok_r[b_label]}/{n_r[b_label]} = {ok_r[b_label] / n_r[b_label]:.3f} "
          f"| delta {d_place:+.3f} (bar >= -{MARGIN})")
    print(f"   exact two-sided Fisher p = {p_place:.4g} | exact non-inferiority "
          f"p at margin {MARGIN} = {p_ni:.4g} | Newcombe one-sided 95% lower "
          f"bound {lo_new:+.3f}")
    print(f"   standardised to {a_label}'s weights: species "
          f"{species['rate_a']:.3f} -> {species['rate']:.3f} "
          f"({std_delta:+.3f}, coverage {species['coverage']:.2f}) | diameter "
          f"tertiles {diam['rate_a']:.3f} -> {diam['rate']:.3f} "
          f"({diam_delta:+.3f}, coverage {diam['coverage']:.2f}) "
          f"[cuts {bounds[0]:.2f}/{bounds[1]:.2f} cm]")
    print(f"   -> P2 {'PASS' if p2 else 'FAIL'}"
          f"{'' if signs_agree else ' (the standardised deltas do not agree in sign)'}")
    print()

    # ---- P3: the pooled rate, arm-standardised (a REPORT) ------------------ #
    raw_a, raw_b = rate(pooled[a_label]), rate(pooled[b_label])
    mix_a = len(right[a_label]) / len(pooled[a_label])
    mix_b = len(right[b_label]) / len(pooled[b_label])
    std50 = arm_standardised(pooled[a_label], pooled[b_label], 0.5)
    stdA = arm_standardised(pooled[a_label], pooled[b_label], mix_a)
    print(f"P3 the pooled placed rate (REPORT ONLY - not a test, P37): raw "
          f"{a_label} {raw_a:.3f} -> {b_label} {raw_b:.3f} "
          f"({raw_b - raw_a:+.3f}); realised right-arm mix "
          f"{mix_a:.3f} -> {mix_b:.3f}")
    print(f"   arm-standardised at 50/50: {std50['a']['rate']:.3f} -> "
          f"{std50['b']['rate']:.3f} ({std50['delta']:+.3f}) | at {a_label}'s mix "
          f"({mix_a:.3f}): {stdA['a']['rate']:.3f} -> {stdA['b']['rate']:.3f} "
          f"({stdA['delta']:+.3f})")
    print(f"   (the raw number moves with the mix: right "
          f"{a_label} {std50['a']['right']:.3f} vs {b_label} "
          f"{std50['b']['right']:.3f}; left {std50['a']['left']:.3f} vs "
          f"{std50['b']['left']:.3f})")
    print()

    # ---- P4: the left arm (the no-op guard) ------------------------------- #
    lp_a = sum(1 for e in left[a_label] if plate(e)) / max(1, len(left[a_label]))
    lp_b = sum(1 for e in left[b_label] if plate(e)) / max(1, len(left[b_label]))
    p4 = (lp_b - lp_a) >= -LEFT_GUARD
    print(f"P4 the left arm (the park's no-op guard - the left has no park "
          f"vector): placed {a_label} {lp_a:.3f} ({len(left[a_label])}) -> "
          f"{b_label} {lp_b:.3f} ({len(left[b_label])}) | delta {lp_b - lp_a:+.3f} "
          f"(bar >= -{LEFT_GUARD}) -> {'PASS' if p4 else 'FAIL'} | carried "
          f"{carried(left[a_label])} -> {carried(left[b_label])}")
    print()

    # ---- P5: new failure reasons ------------------------------------------ #
    nov = P37.novelty(pooled[a_label], pooled[b_label])
    nov_r = P37.novelty(right[a_label], right[b_label])
    print("P5 new failure reasons (113's number normalisation):")
    for label in (a_label, b_label):
        print(f"   {label}: {len(nov['a'] if label == a_label else nov['b'])} "
              f"distinct")
    print(f"   NEW in {b_label}: {nov['new'] or 'none'}")
    for reason in nov["new"]:
        print(f"     {nuance(reason)}: {dict(nov['counts'][reason])} "
              f"episodes {nov['episodes'][reason]}")
    p5 = not nov["new"]
    extra = "" if not nov_r["new"] else (
        f" (the right arm alone also reads {len(nov_r['new'])} new)")
    print(f"   -> P5 {'PASS' if p5 else 'FAIL'}{extra}")
    print()

    # ---- P6: the cycle ---------------------------------------------------- #
    cyc_a, cyc_b = P37.cycle_med(pooled[a_label]), P37.cycle_med(pooled[b_label])
    cyc_ar, cyc_br = P37.cycle_med(right[a_label]), P37.cycle_med(right[b_label])
    p6 = bool(cyc_a == cyc_a and cyc_a > 0 and cyc_b <= CYCLE_BAR * cyc_a)
    print(f"P6 median cycle: pooled {cyc_a:.0f} -> {cyc_b:.0f} ticks "
          f"({100.0 * (cyc_b / cyc_a - 1.0) if cyc_a else float('nan'):+.1f}%, bar "
          f"<= +{100.0 * (CYCLE_BAR - 1.0):.0f}%) -> {'PASS' if p6 else 'FAIL'} | "
          f"right arm only {cyc_ar:.0f} -> {cyc_br:.0f}")
    print()

    # ---- P7: the run level ------------------------------------------------ #
    print(f"P7 the run level (the primary per seed pair; branch {branch}):")
    better = worse = ties = 0
    tables = []
    for run in runs:
        ra = [e for e in arms[a_label][run]["eps"] if e["arm"] == "right"]
        rb = [e for e in arms[b_label][run]["eps"] if e["arm"] == "right"]
        oa = sum(1 for e in ra if plate(e))
        ob = sum(1 for e in rb if plate(e))
        ca, cb = carried(ra), carried(rb)
        tables.append((ob, len(rb) - ob, oa, len(ra) - oa))
        # branch A: fewer carried is better; branch B: more placed is better
        if branch == "A":
            tag = "B" if cb < ca else ("A" if cb > ca else "=")
            detail = f"carried {ca} -> {cb}"
        else:
            tag = "B" if ob > oa else ("A" if ob < oa else "=")
            detail = f"placed {oa}/{len(ra)} -> {ob}/{len(rb)}"
        if tag == "B":
            better += 1
        elif tag == "A":
            worse += 1
        else:
            ties += 1
        print(f"   run {run}: right placed {oa}/{len(ra)} -> {ob}/{len(rb)} | "
              f"carried {ca} -> {cb} | {detail} -> {tag}")
    p7 = better >= RUN_LEVEL_MIN
    print(f"   {b_label} better in {better}/{len(runs)} runs, worse in {worse}, "
          f"tied {ties} | one-sided sign p = "
          f"{PARK.sign_test_p(better, worse):.4f} | bar >= {RUN_LEVEL_MIN}/5 -> "
          f"{'PASS' if p7 else 'FAIL'}")
    mh = mh_cmh(tables)
    print(f"   run-stratified placed (Mantel-Haenszel over the {len(runs)} "
          f"pairs): OR {mh['or']:.3f} | CMH chi2 {mh['chi2']:.2f}, p {mh['p']:.4g}")
    print()

    # ---- the verdict ------------------------------------------------------ #
    print("=" * 78)
    carried_better = car_r[b_label] < car_r[a_label]
    placed_better = d_place > 0
    print(f"falsifiers: P8 check {'PASS' if p8 else 'FAIL'} | right placed "
          f"delta {d_place:+.3f} ({'PASS' if d_place > -MARGIN else 'FAIL'}) | "
          f"new reasons {'none' if p5 else 'PRESENT'} | carried "
          f"{'better' if carried_better else 'not better'} / placed "
          f"{'better' if placed_better else 'not better'}")
    if not p8:
        verdict = ("NO OUTCOME CLAIM (P8 failed: the check is the attribution; "
                   "the batch is still the current-tree baseline)")
    elif d_place <= -MARGIN:
        verdict = "NOT ADOPTED (the right-arm placed delta breaks the margin)"
    elif not p5:
        verdict = "NOT ADOPTED (a new failure reason appears)"
    elif branch == "A" and p1 > 0.05:
        verdict = ("NOT ADOPTED (branch A: the carried contrast is not "
                   "significant at this n)")
    elif not carried_better and not placed_better:
        verdict = ("NOT ADOPTED (neither the carried class nor the placed "
                   "rate improves)")
    elif not p7:
        verdict = "NOT ADOPTED (the run level disagrees: < 4/5)"
    elif branch == "A":
        verdict = ("ADOPTED (branch A: the check passes, the carried contrast "
                   "is significant, right placed is non-inferior, the run "
                   "level agrees)")
    else:
        verdict = (f"ADOPTED - branch B (P0 = {base:.3f} < {BRANCH_A_BASE}: the "
                   f"carried contrast is a REPORT, the placed/run-level read "
                   f"carries the decision). The report reads carried "
                   f"{car_r[a_label]}/{n_r[a_label]} -> "
                   f"{car_r[b_label]}/{n_r[b_label]} (contrast "
                   f"{car_r[b_label] / n_r[b_label] - base:+.3f}, p = {p1:.3g}) "
                   f"- stronger than the branch required, but not the gate")
    print(f"VERDICT: {verdict}")
    for name, value in (("P1", p1), ("P2", p2), ("P4", p4), ("P5", p5),
                        ("P6", p6), ("P7", p7), ("P8", p8)):
        print(f"   {name}: {'PASS' if value else 'FAIL'}"
              + (f" (p = {value:.4g})" if name == "P1" else ""))
    print("=" * 78)
    return {"p1": p1, "p2": p2, "p4": p4, "p5": p5, "p6": p6, "p7": p7,
            "p8": p8, "branch": branch, "delta": d_place, "verdict": verdict}


def nuance(text: str) -> str:
    return text[:70] + ("..." if len(text) > 70 else "")


# ---------------------------------------------------------------- self-test -- #
def self_test() -> int:
    bad = 0

    def check(name: str, got, want, tol: float = 1e-3) -> None:
        nonlocal bad
        ok = (abs(got - want) <= tol) if isinstance(want, float) else (got == want)
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: {got!r}"
              + ("" if ok else f" (want {want!r})"))
        bad += int(not ok)

    print("== the exact Fisher (known tables)")
    check("[[3,1],[1,3]] two-sided", fisher_two_sided(3, 1, 1, 3), 0.4857)
    check("[[1,9],[9,1]] two-sided", fisher_two_sided(1, 9, 9, 1), 0.001089)
    check("[[0,10],[10,0]] two-sided", fisher_two_sided(0, 10, 10, 0), 1.08e-5, 1e-6)
    check("[[10,10],[10,10]] two-sided", fisher_two_sided(10, 10, 10, 10), 1.0)
    check("one-sided (A carries more) on [[1,9],[9,1]]",
          fisher_one_sided_greater_a(1, 9, 9, 1), 1.0, 1e-4)
    check("one-sided (A carries more) on [[9,1],[1,9]]",
          fisher_one_sided_greater_a(9, 1, 1, 9), 0.000547, 1e-5)

    print("== the Mantel-Haenszel / CMH")
    mh = mh_cmh([(1, 9, 9, 1), (1, 9, 9, 1)])
    check("MH OR on two [[1,9],[9,1]] strata", mh["or"], 1 / 81, 1e-4)
    check("CMH p is small", mh["p"] < 0.01, True)
    mh0 = mh_cmh([(5, 5, 5, 5), (5, 5, 5, 5)])
    check("MH OR on the identity strata", mh0["or"], 1.0, 1e-9)
    check("CMH chi2 on the identity strata", mh0["chi2"], 0.0, 1e-9)

    print("== the arm-standardised pooled")
    mk = lambda arm, ok, n: [{"arm": arm, "success": i < ok, "placed": i < ok}
                             for i in range(n)]  # noqa: E731
    # Identical per-arm rates (right 0.4, left 0.1) and a DIFFERENT arm mix:
    # A 50/50, B two-thirds right. The raw pooled rate moves (0.25 -> 0.30)
    # with no per-arm change at all - the P37 artifact the standardisation
    # removes.
    rows_a = mk("right", 4, 10) + mk("left", 1, 10)
    rows_b = mk("right", 8, 20) + mk("left", 1, 10)
    s = arm_standardised(rows_a, rows_b, 0.5)
    check("the per-arm right rate is identical",
          s["b"]["right"], s["a"]["right"], 1e-9)
    check("50/50 standardised A", s["a"]["rate"], 0.25, 1e-9)
    check("50/50 standardised B (the mix removed)", s["b"]["rate"], 0.25, 1e-9)
    check("the raw pooled rate still moved", rate(rows_b) - rate(rows_a),
          0.05, 1e-9)
    s75 = arm_standardised(rows_a, rows_b, 0.75)
    check("75/25 standardised B", s75["b"]["rate"], 0.75 * 0.4 + 0.25 * 0.1, 1e-9)

    print("== the branch rule")
    for base, want in ((0.40, "A"), (0.39, "B"), (0.0, "B"), (0.667, "A")):
        check(f"base {base} -> branch", "A" if base >= BRANCH_A_BASE else "B", want)

    print("== the class definitions (the W7-B convention)")
    check("ok", klass({"success": True, "grasped": True, "placed": True}), "ok")
    check("carried", klass({"success": False, "grasped": True, "placed": False}),
          "carried")
    check("no-contact", klass({"success": False, "grasped": False,
                               "placed": False}), "no-contact")
    print(f"\n{'PASS' if not bad else f'{bad} FAILURES'}")
    return 0 if not bad else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default="logs/p43/p3")
    ap.add_argument("--a", default="A")
    ap.add_argument("--b", default="B")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    try:
        analyse(args.dir, args.a, args.b)
    except SystemExit as exc:
        print(exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
