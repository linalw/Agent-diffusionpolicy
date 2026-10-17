#!/usr/bin/env python3
"""P10-D Task A: the two-line selection-allocation offline replay (Tier C).

    python3 logs/p10d/selection_replay.py [logs...]

Defaults to the P10-C battery logs (`logs/p10c/10_armA_diag.log`,
`20_armB_1.log`, `21_armB_2.log`, `22_armB_diag.log`) plus any seed logs
present (`50..53_seed*`). Pure text parsing; no simulator; nothing written
except stdout (redirected into `logs/p10d/10_selection_replay.txt`).

The question (BIMANUAL.md mechanism table row 2 / L2): given the same supply,
does changing *which* eligible fruit each lane takes reduce the starved polls
and the interval?

What the logs allow (see `replay_common.py` for the measurement limit):

1. Every selection instant is the arm's `station acquired` row, and the chosen
   fruit's position at that instant is reconstructed from its own wait rows +
   the attempt's `[cycle]` pre-pose/hover marks:
   `y_sel = y_wait0 + v * (prepose + hover)`, `v = 0.12 m/s`. Validated
   internally: every y_sel lands inside `[floor, station+0.85]` on all 20
   attempts, and the wait-loop arithmetic closes to <= 2 ticks.
2. The shipped two-line rule is *nearest-usable-above-the-floor* (code path:
   `select_target` with `prefer_lane` + pure routing returns `usable[0]`, the
   min-along candidate above `_dynamic_select_floor()` ~ 0.40 m; the
   *farthest-upstream* rule is the single-arm `_balance_arm` path, which the
   two-line never calls). The replay therefore treats "shipped" as nearest-first
   and evaluates the alternatives against it.
3. Candidate positions other than the chosen fruit are NOT logged (positions
   are printed only for the selected fruit), and the feeder's backlog release
   spawns fruit *mid-belt* at their virtual positions (`_pump_supply`), so
   backward propagation from a later pick does not prove presence at an earlier
   instant. Section "reconstruction soundness" measures this: the same-lane
   test (a later pick of the same lane propagated into a starved instant's
   window - impossible if the model were sound) fires on 19/41 starved polls.
   The exact candidate set is therefore NOT reconstructible from these logs;
   the report states every bound it uses instead.
"""

from __future__ import annotations

import glob
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from replay_common import (  # noqa: E402
    BELT_V,
    STATION,
    parse,
    starved_instants,
)

FLOOR_ABS = 0.399  # lead (~0.189 printed) + v*1.5 + margin 0.03, the shipped floor
WINDOW_TOP = 0.85  # select_target's upstream window edge (pick_y + 0.85)
PROP_BOUND_S = 10.0


def analyse(path: str) -> dict:
    data = parse(path)
    atts = sorted(data.attempts, key=lambda a: a.t0)
    out = {"path": path, "attempts": [], "starved": [], "violations": [], "fills": []}

    for a in atts:
        b = a.block
        if b is None or not b.waits:
            continue
        w0 = b.waits[0]
        tw = a.t_wait
        if tw is None:
            continue
        y_sel = w0["y"] + BELT_V * (tw - a.t0)
        lead = b.handover["lead"] if b.handover else 0.189
        floor = STATION[a.arm] + lead + 0.21
        arr_steps = b.pickpoint["steps"] if b.pickpoint else None
        t_h = (tw + arr_steps / 120.0) if arr_steps is not None else None
        y_h = b.handover["y"] if b.handover else None
        # arithmetic closure check: y_sel - y_handover should equal v*(t_h - t0)
        closure = None
        if t_h is not None and y_h is not None:
            closure = (y_sel - y_h) - BELT_V * (t_h - a.t0)
        out["attempts"].append(
            {
                "slot": a.slot,
                "arm": a.arm,
                "fruit": a.fruit,
                "grade": a.grade,
                "t0": a.t0,
                "t1": a.t1,
                "span": a.span,
                "y_sel": y_sel,
                "floor": floor,
                "headroom": y_sel - floor,
                "window_frac": (y_sel - floor) / (WINDOW_TOP - FLOOR_ABS),
                "queue": b.handover["queue"] if b.handover else None,
                "lead": lead,
                "y_handover": y_h,
                "wait_steps": arr_steps,
                "t_handover": t_h,
                "travel": (y_sel - y_h) if y_h is not None else None,
                "prepose_hover": (tw - a.t0),
                "placed": a.placed,
                "grasped": a.grasped,
                "notes": a.notes,
                "closure": closure,
            }
        )

    si = starved_instants(data)
    out["starved"] = si

    # ---- reconstruction-soundness test ---------------------------------- #
    # Same-lane later picks must NOT propagate into a starved instant's window:
    # the arm would have taken them. A hit means the backward propagation is
    # invalid there (the feeder spawned the fruit between the two instants at a
    # virtual mid-belt position), so the log cannot pin the candidate set.
    for arm, t_s in si:
        lo = STATION[arm] + FLOOR_ABS
        hi = STATION[arm] + WINDOW_TOP
        for a in atts:
            if a.arm != arm or a.block is None or not a.block.waits:
                continue
            tw = a.t_wait
            if tw is None or tw <= t_s or (tw - t_s) > PROP_BOUND_S:
                continue
            y_ts = a.block.waits[0]["y"] + BELT_V * (tw - t_s)
            if lo <= y_ts <= hi:
                out["violations"].append(
                    {"arm": arm, "t": t_s, "later_slot": a.slot, "y_at_ts": y_ts}
                )

    # ---- cross-lane propagation candidates (UNSOUND; kept for the record) - #
    for arm, t_s in si:
        other = "right" if arm == "left" else "left"
        lo = STATION[arm] + FLOOR_ABS
        hi = STATION[arm] + WINDOW_TOP
        prov = []
        for a in atts:
            if a.arm != other or a.block is None or not a.block.waits:
                continue
            tw = a.t_wait
            if tw is None or tw <= t_s or (tw - t_s) > PROP_BOUND_S:
                continue
            y_ts = a.block.waits[0]["y"] + BELT_V * (tw - t_s)
            if lo <= y_ts <= hi:
                prov.append(
                    {
                        "fruit": a.fruit,
                        "grade": a.grade,
                        "slot": a.slot,
                        "y_at_ts": y_ts,
                        "dt": tw - t_s,
                    }
                )
        out["fills"].append({"arm": arm, "t": t_s, "cross_candidates": prov})

    # ---- starvation bursts ---------------------------------------------- #
    bursts: list[dict] = []
    for arm, t in si:
        if bursts and bursts[-1]["arm"] == arm and (t - bursts[-1]["end"]) <= 0.51:
            bursts[-1]["end"] = t
            bursts[-1]["n"] += 1
        else:
            bursts.append({"arm": arm, "start": t, "end": t, "n": 1})
    out["bursts"] = bursts
    return out


def report(paths: list[str]) -> None:
    results = [analyse(p) for p in paths]
    print("# P10-D selection-allocation offline replay (Task A)")
    print("# generated by logs/p10d/selection_replay.py; Tier C, logs only; no simulator")
    print()

    for r in results:
        print(f"== {r['path']}")
        atts = r["attempts"]
        if not atts:
            print("   no attempt geometry found")
            print()
            continue
        print(
            "   slot arm   fruit      t0     y_sel  floor  headroom  h/win  queue  wait  travel  place"
        )
        for a in atts:
            print(
                f"   {a['slot']:>4} {a['arm']:<5} {a['fruit']:<10} {a['t0']:>6.1f} "
                f"{a['y_sel']:>6.3f} {a['floor']:>6.3f} {a['headroom']:>8.3f} "
                f"{a['window_frac']:>5.2f} {str(a['queue']):>5} "
                f"{str(a['wait_steps']):>5} {('%.3f' % a['travel']) if a['travel'] else '-':>7} "
                f"{str(a['placed']):>5}"
            )
        heads = [a["headroom"] for a in atts]
        waits = [a["wait_steps"] for a in atts if a["wait_steps"] is not None]
        queues = [a["queue"] for a in atts if a["queue"] is not None]
        closures = [abs(a["closure"]) for a in atts if a["closure"] is not None]
        print(
            f"   headroom: n={len(heads)} mean {statistics.fmean(heads):.3f} "
            f"p50 {statistics.median(heads):.3f} min {min(heads):.3f} max {max(heads):.3f} m "
            f"(window width {WINDOW_TOP - FLOOR_ABS:.2f} m); arithmetic closure <= "
            f"{max(closures):.4f} m" if closures else ""
        )
        if waits:
            print(
                f"   wait-loop duration (handover - wait entry): mean "
                f"{statistics.fmean(waits) / 120:.2f}s p50 "
                f"{statistics.median(waits) / 120:.2f}s max {max(waits) / 120:.2f}s"
            )
        if queues:
            others = [q - 1 for q in queues]
            print(
                f"   handover queue (chosen fruit included): mean "
                f"{statistics.fmean(queues):.2f} -> other main-belt fruit in the "
                f"station window: mean {statistics.fmean(others):.2f}, "
                f"n>0 in {sum(1 for o in others if o > 0)}/{len(others)} attempts"
            )
        per_arm = {"left": 0, "right": 0}
        for arm, _ in r["starved"]:
            per_arm[arm] += 1
        print(
            f"   starved polls: {len(r['starved'])} "
            f"(left {per_arm['left']}, right {per_arm['right']}); bursts:"
        )
        for b in r["bursts"]:
            print(
                f"     {b['arm']:<5} {b['start']:>6.1f} -> {b['end']:>6.1f}s "
                f"({b['n']} polls, {0.5 * b['n']:.1f}s spin)"
            )
        n_vio = len(r["violations"])
        print(
            f"   reconstruction soundness: same-lane later picks propagating into a "
            f"starved window: {n_vio}/{len(r['starved'])} starved polls "
            f"(must be 0 if backward propagation were sound) -> the exact candidate "
            f"set is NOT reconstructible from these logs (feeder backlog spawns "
            f"mid-belt, tasks.py `_pump_supply`)"
        )
        print()

    # ---- pooled rule table ---------------------------------------------- #
    print("== pooled rule evaluation (all logs)")
    all_atts = [a for r in results for a in r["attempts"]]
    all_starved = [(r["path"], arm, t) for r in results for arm, t in r["starved"]]
    heads = [a["headroom"] for a in all_atts]
    mean_h = statistics.fmean(heads) if heads else None
    print(f"   attempts with geometry: {len(all_atts)}; starved polls: {len(all_starved)}")
    if mean_h is not None:
        print(
            f"   measured headroom mean {mean_h:.3f} m -> the chosen fruit sits "
            f"~{mean_h / BELT_V:.1f}s of travel above the floor; the farthest-first "
            f"choice would add up to {WINDOW_TOP - FLOOR_ABS:.2f} m "
            f"({(WINDOW_TOP - FLOOR_ABS) / BELT_V:.2f}s) per attempt"
        )
    print()
    print("   rule                      starvation              travel / wait            interval (bounded)")
    print("   ----------------------------------------------------------------------------------------------------")
    print(
        f"   shipped nearest-first     {len(all_starved):>3} polls (baseline)   "
        f"floor-bound (mean h {mean_h:.2f} m)   baseline"
    )
    print(
        f"   SPT / nearest-first       same as shipped          identical                  identical"
    )
    print(
        f"   FIFO / farthest-first     fewer polls possible     +0..{WINDOW_TOP - FLOOR_ABS:.2f} m travel        "
        f"next start >= shipped (max(delta, spin) >= spin)"
    )
    print(
        f"   [SPT; FIFO] pair (ETH)    same as FIFO within lane  +FIFO cost                  form inapplicable (disjoint lanes)"
    )
    print(
        f"   primary-then-conditional  only rule that can fill    nearest any-grade         ~0 interval gain; sort purity"
    )
    print(
        f"   (V2 cross-lane fallback)  a starved poll (owner-gated)                          lost; fill rate NOT measurable"
    )
    print()
    print("   Falsifier (pre-registered L2): '<5% of selections change OR starvation/interval")
    print("   unmoved' -> the second clause fires for every within-lane rule: the starved-poll")
    print("   count is invariant to within-lane reordering EXCEPT via re-phasing (FIFO moves")
    print("   the wait inside the attempt: fewer polls, same-or-later next start, P9-D phase")
    print("   re-draw), and nearest-first is the wait-minimal choice (the floor guarantees the")
    print("   setup fits; any farther fruit only delays the handover). The only starvation-")
    print("   moving rule is the cross-lane fallback, which is a routing-semantics change.")
    print()


def main(argv: list[str]) -> int:
    if argv:
        paths = argv
    else:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "p10c")
        paths = [
            os.path.join(base, name)
            for name in ("10_armA_diag.log", "20_armB_1.log", "21_armB_2.log", "22_armB_diag.log")
        ]
        #: the seeds chain's run logs only (`5?-seed` shape): never the
        #: `*_driver.log` shells, and never an in-flight partial log.
        paths += sorted(
            p
            for p in glob.glob(os.path.join(base, "5?_seed*.log"))
            if "_driver" not in os.path.basename(p)
            and os.path.basename(p)[:2] in ("50", "51", "52", "53")
        )
        paths = [p for p in paths if os.path.exists(p)]
    report(paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
