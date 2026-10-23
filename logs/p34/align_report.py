#!/usr/bin/env python3
"""P34 phase 2: the reset-alignment A/B report (the manipulation check + the
arm occlusion), read-only over `logs/p34/A_ab/A_N.log` / `B_N.log`.

    python3 logs/p34/align_report.py --dir logs/p34/A_ab --a A --b B

Prints, per arm:

  * the **manipulation check** (`logs/p34/PREREG.md` section 2): the first
    model call's along (target 0.399 +- 0.02) and the analytic visible
    fraction of `scripts/212_occlusion_map.py` at that call's (x, along,
    diameter) (target >= 0.90), with the rendered target-mask pixels over the
    analytic unoccluded area as the cross-check, and the pass share;
  * the **first-view run**: the reset-return along, the travel to the first
    call, the fully-hidden model calls to the first visible frame, and the
    first visible call index (the correction that retires the phase-1
    "33 model calls" - the reset travel is not model calls);
  * the **arm occlusion at the fire zone**: the `[align]` zone counters over
    along 0.15-0.30 (P34 phase 1's arm window) - the zero-target-mask
    fraction and the rendered visible fraction (zone px over the analytic
    unoccluded projected area at the zone's mid along);
  * the outcome classes (ok / no-grasp / carried-not-placed) per arm and lane,
    and the pre-registered criterion lines: the primary pairing, the unpaired
    left counts, and the section-5 bullet that fires. The *middle* bullet
    (`placed up or mass down`) is the section-4 relocation guard, not a win
    condition - see the comment at the verdict branch.

The outcome pairing and the class-transition matrix are cross-checked against the
pinned W8/W7 tools (`logs/w8/A_pairs.py` species-only key, `logs/w7/C_class_split.py`);
this script owns the manipulation check, the occlusion, and the same-fruit
pairing that adds the arm and a diameter guard (`PAIR_D_TOL`).
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import os
import re
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "logs", "w7"))

import B_ab_report as mech  # noqa: E402  (the pinned W7-B outcome parser)

ALIGN = re.compile(
    r"\[align\] episode (\d+) knob=(\d+) y0=(\S+) reset=(\S+) steps=(\d+) "
    r"jaw=(\S+) first=(\S+) x=(\S+) first_d=(\S+) first_px=(-?\d+) "
    r"first_vis_call=(-?\d+) hidden=(\d+) zone_n=(\d+) zone_zero=(\d+) "
    r"zone_px=(-?\d+) calls=(\d+)"
)


def _num(text: str) -> float:
    try:
        return float(text)
    except ValueError:
        return float("nan")


def load_map():
    """The phase-1 visibility map, imported by path (its name starts with 212)."""
    path = os.path.join(ROOT, "scripts", "212_occlusion_map.py")
    spec = importlib.util.spec_from_file_location("occlusion_map_212", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def klass(e: dict) -> str:
    if e.get("success"):
        return "ok"
    if e.get("success") is False and not e.get("grasped"):
        return "no-grasp"
    if e.get("success") is False and e.get("grasped") and not e.get("placed"):
        return "carried"
    return "other"


def arm_data(directory: str, label: str) -> tuple[list[dict], dict[int, dict]]:
    """The parsed outcome rows + {episode index: align row} for one arm."""
    rows: list[dict] = []
    align: dict[int, dict] = {}
    for path in sorted(glob.glob(os.path.join(directory, f"{label}_*.log"))):
        run = int(os.path.basename(path)[:-4].rsplit("_", 1)[1])
        eps = mech.parse_log(path)
        for e in eps:
            e["run"] = run
        rows.extend(eps)
        for line in open(path, encoding="utf-8", errors="replace"):
            m = ALIGN.search(line)
            if not m:
                continue
            rec = {
                "ep": int(m.group(1)), "knob": int(m.group(2)),
                "y0": _num(m.group(3)), "reset": _num(m.group(4)),
                "steps": int(m.group(5)), "jaw": _num(m.group(6)),
                "first": _num(m.group(7)), "x": _num(m.group(8)),
                "d": _num(m.group(9)), "first_px": int(m.group(10)),
                "first_vis_call": int(m.group(11)), "hidden": int(m.group(12)),
                "zone_n": int(m.group(13)), "zone_zero": int(m.group(14)),
                "zone_px": int(m.group(15)), "calls": int(m.group(16)),
                "run": run,
            }
            # The episode index repeats across runs: key by (run, ep).
            align[(run, rec["ep"])] = rec
    return rows, align


def pct(values, q):
    vals = sorted(v for v in values if v == v)
    if not vals:
        return float("nan")
    k = (len(vals) - 1) * q / 100.0
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


#: The +Y belt's band edges vs diameter, from `logs/p34/10_map.txt` (x is a
#: null +-0.01 m, so one column serves): `vis < 0.99` (the near edge) and
#: `vis < 0.01` (fully hidden). Linear in d between the four measured sizes.
NEAR99 = ((0.031, 0.475), (0.045, 0.465), (0.058, 0.450), (0.069, 0.440))
NEAR01 = ((0.031, 0.510), (0.045, 0.510), (0.058, 0.515), (0.069, 0.520))
CALL_MM = 4.0  # belt travel per model call at 0.12 m/s and execute_steps=4


def edge(table, d: float) -> float:
    if d <= table[0][0]:
        return table[0][1]
    if d >= table[-1][0]:
        return table[-1][1]
    for (d0, y0), (d1, y1) in zip(table, table[1:]):
        if d0 <= d <= d1:
            return y0 + (y1 - y0) * (d - d0) / (d1 - d0)
    return float("nan")



def sign_test_p(better: int, worse: int) -> float:
    """One-sided P(X >= better), X ~ Bin(better + worse, 0.5)."""
    import math

    n = better + worse
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(better, n + 1)) / (2.0 ** n)


#: The same-fruit pairing's diameter guard, **metres**. This is a loose guard
#: (0.05 m = 50 mm), *not* a 0.5 mm identity check - an earlier docstring said
#: 0.5 mm and was wrong. On the P34 batch it is inert (every retained pair
#: matched at the store's 0.1 mm resolution); it is kept as written because the
#: report of record (`logs/p34/A_align.txt`) was produced with it.
PAIR_D_TOL = 0.05


def pair_left(rows_a: list[dict], rows_b: list[dict]) -> dict:
    """The same-fruit pairing (the P33 protocol), pooled and left-only.

    Same-fruit = the same (run, episode) **and** species, diameter
    (+-`PAIR_D_TOL` metres, a 0.05 m *guard*, not the 0.5 mm identity check an
    earlier docstring claimed) and arm. On the P34 batch the guard is inert:
    every retained pair matched exactly at the store's 0.1 mm resolution, so
    the effective key is (run, episode, species, arm). The pinned `A_pairs.py`
    (species only, no arm key) is quoted as the looser cross-check.
    """
    idx_a = {(e["run"], e["ep"]): e for e in rows_a}
    idx_b = {(e["run"], e["ep"]): e for e in rows_b}
    out: dict[str, dict] = {}
    for scope in ("all", "left"):
        trans: dict[tuple[str, str], int] = {}
        b_only = a_only = 0
        ok_b = ok_a = 0
        pairs = excluded = 0
        for key, a in idx_a.items():
            b = idx_b.get(key)
            if b is None:
                continue
            if scope == "left" and a.get("arm") != "left":
                continue
            if (a.get("fruit") != b.get("fruit")
                    or a.get("arm") != b.get("arm")
                    or abs(float(a.get("d", 0.0)) - float(b.get("d", 0.0)))
                    > PAIR_D_TOL):
                excluded += 1
                continue
            pairs += 1
            ka, kb = klass(a), klass(b)
            trans[(ka, kb)] = trans.get((ka, kb), 0) + 1
            if ka == "ok" and kb != "ok":
                a_only += 1
            if kb == "ok" and ka != "ok":
                b_only += 1
            if ka == "carried" and kb == "ok":
                ok_b += 1
            if kb == "carried" and ka == "ok":
                ok_a += 1
        out[scope] = {"pairs": pairs, "excluded": excluded, "b_only": b_only,
                      "a_only": a_only, "carried_b_only": ok_b,
                      "carried_a_only": ok_a}
        print(f"   pairing ({scope}): {pairs} same-fruit pairs, {excluded} excluded; "
              f"outcome B-only {b_only} / A-only {a_only} (p={sign_test_p(b_only, a_only):.4f}); "
              f"carried->ok B-only {ok_b} / A-only {ok_a}")
        if trans:
            cells = ", ".join(f"{k[0]}->{k[1]} {v}" for k, v in sorted(trans.items()))
            print(f"     transitions: {cells}")
    return out


def report_arm(name: str, rows: list[dict], align: dict, omap) -> dict:
    print(f"\n== arm {name}")
    n = len(rows)
    classes = {"ok": 0, "no-grasp": 0, "carried": 0, "other": 0}
    for e in rows:
        classes[klass(e)] += 1
    print(f"   episodes={n} classes ok={classes['ok']} no-grasp={classes['no-grasp']} "
          f"carried={classes['carried']} other={classes['other']}")
    for arm in ("left", "right"):
        sel = [e for e in rows if e.get("arm") == arm]
        if not sel:
            continue
        c = {"ok": 0, "no-grasp": 0, "carried": 0, "other": 0}
        for e in sel:
            c[klass(e)] += 1
        print(f"   {arm:5s}: n={len(sel)} ok={c['ok']} no-grasp={c['no-grasp']} "
              f"carried={c['carried']} other={c['other']}")
    ticks = [e["ticks"] for e in rows if e.get("ticks") is not None]
    if ticks:
        print(f"   cycle ticks: p50 {st.median(ticks):.0f} ({min(ticks)}-{max(ticks)})")

    # ---- the manipulation check ------------------------------------------ #
    eps = []
    for (run, ep), a in sorted(align.items()):
        row = next((e for e in rows if e["run"] == run and e["ep"] == ep), None)
        if row is None:
            continue
        vis = omap.visible_fraction(a["x"], a["first"], a["d"]) if a["first"] == a["first"] else {}
        area = float(vis.get("area_without", float("nan")))
        eps.append({
            **a,
            "fruit": row.get("fruit"), "arm": row.get("arm"),
            "vis": float(vis.get("vis", float("nan"))),
            "area": area,
            "mask_vis": (a["first_px"] / area) if area > 0 else float("nan"),
            "along_ok": abs(a["first"] - 0.399) <= 0.02,
            "vis_ok": float(vis.get("vis", 0.0)) >= 0.90,
            # The analytic hidden run from the first *model* call (belt only):
            # calls until the fruit is fully hidden / fully visible. This is the
            # phase-1 "33 model calls" question, measured from the first call.
            "hidden_full": max(0.0, (a["first"] - edge(NEAR01, a["d"]))
                               * 1000.0 / CALL_MM),
            "hidden_vis": max(0.0, (a["first"] - edge(NEAR99, a["d"]))
                              * 1000.0 / CALL_MM),
            "full_hidden_first": bool(a["first"] >= edge(NEAR01, a["d"])),
        })
    if eps:
        firsts = [e["first"] for e in eps]
        vises = [e["vis"] for e in eps]
        masks = [e["mask_vis"] for e in eps]
        passed = [e for e in eps if e["along_ok"] and e["vis_ok"]]
        print(f"\n   -- the manipulation check (first model call) --")
        print(f"   first along: p10 {pct(firsts,10):+.3f} p50 {st.median(firsts):+.3f} "
              f"p90 {pct(firsts,90):+.3f} (min {min(firsts):+.3f} max {max(firsts):+.3f})")
        print(f"   vis(212)   : p10 {pct(vises,10):.2f} p50 {st.median(vises):.2f} "
              f"p90 {pct(vises,90):.2f} (min {min(vises):.2f} max {max(vises):.2f})")
        print(f"   mask/area  : p10 {pct(masks,10):.2f} p50 {st.median(masks):.2f} "
              f"p90 {pct(masks,90):.2f} (the rendered cross-check)")
        print(f"   PASS (|along-0.399|<=0.02 AND vis>=0.90): {len(passed)}/{len(eps)} "
              f"= {len(passed)/len(eps):.0%}")
        # Per-run counts (the pre-registered `>= 12/15 in each run`).
        per_run = {}
        for e in eps:
            per_run.setdefault(e["run"], [0, 0])
            per_run[e["run"]][1] += 1
            if e["along_ok"] and e["vis_ok"]:
                per_run[e["run"]][0] += 1
        print("   per run  : " + "  ".join(
            f"r{r} {c}/{t}" for r, (c, t) in sorted(per_run.items())))
        # The reset->first call travel (the shipped reset's own offset).
        off = [e["reset"] - e["first"] for e in eps
               if e["reset"] == e["reset"] and e["first"] == e["first"]]
        if off:
            print(f"   reset->first travel: p50 {st.median(off)*1000:.1f} mm "
                  f"({min(off)*1000:.1f}-{max(off)*1000:.1f} mm; {st.median(off)/0.12:.2f} s at 0.12 m/s)")
        resets = [e["reset"] for e in eps if e["reset"] == e["reset"]]
        if resets:
            print(f"   reset along: p50 {st.median(resets):+.3f} (p10 {pct(resets,10):+.3f} "
                  f"p90 {pct(resets,90):+.3f})")
        steps = [e["steps"] for e in eps]
        print(f"   alignment steps: p50 {st.median(steps):.0f} (max {max(steps)})")
        # ---- the first-view run: hidden model calls ---------------------- #
        hidden = [e["hidden"] for e in eps]
        first_vis = [e["first_vis_call"] for e in eps]
        print(f"   fully-hidden model calls to the first visible frame: "
              f"p50 {st.median(hidden):.0f} p90 {pct(hidden,90):.0f} (max {max(hidden)}); "
              f"first-visible call index p50 "
              f"{st.median([v for v in first_vis if v >= 0]) if any(v >= 0 for v in first_vis) else -1:.0f}")
        # The analytic run from the first model call (belt only, 212): the
        # phase-1 "33 model calls" was the reset travel, where no model runs.
        hf = [e["hidden_full"] for e in eps]
        hv = [e["hidden_vis"] for e in eps]
        nf = sum(1 for e in eps if e["full_hidden_first"])
        print(f"   analytic from the first call: fully hidden calls p50 "
              f"{st.median(hf):.0f} p90 {pct(hf,90):.0f}; to vis>0.99 p50 "
              f"{st.median(hv):.0f} p90 {pct(hv,90):.0f}; fully hidden at the "
              f"first call {nf}/{len(eps)}")
        calls = [e["calls"] for e in eps]
        print(f"   model calls per attempt: p50 {st.median(calls):.0f} "
              f"(p10 {pct(calls,10):.0f} p90 {pct(calls,90):.0f})")
        # ---- the arm occlusion at the fire zone -------------------------- #
        zn = sum(e["zone_n"] for e in eps)
        zz = sum(e["zone_zero"] for e in eps)
        zvis = []
        for e in eps:
            if e["zone_px"] <= 0 or e["first"] != e["first"]:
                continue
            mid = omap.visible_fraction(e["x"], 0.225, e["d"])
            area = float(mid.get("area_without", float("nan")))
            if area > 0:
                zvis.append(e["zone_px"] / area)
        print(f"   fire-zone (0.15-0.30) target mask: n={zn} calls, zero-mask "
              f"{zz}/{zn} = {(zz/zn if zn else float('nan')):.0%}, rendered visible "
              f"fraction p50 {st.median(zvis) if zvis else float('nan'):.2f} "
              f"(p10 {pct(zvis,10) if zvis else float('nan'):.2f})")
        for lane in ("left", "right"):
            sel = [e for e in eps if e.get("arm") == lane]
            ln = sum(e["zone_n"] for e in sel)
            lz = sum(e["zone_zero"] for e in sel)
            if ln:
                print(f"     {lane:5s}: {len(sel)} eps, zone {lz}/{ln} zero "
                      f"= {lz/ln:.0%}")
    return {"n": n, "classes": classes, "rows": rows,
            "manip": eps, "passed": sum(1 for e in eps if e["along_ok"] and e["vis_ok"])}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default="logs/p34/A_ab")
    ap.add_argument("--a", default="A")
    ap.add_argument("--b", default="B")
    args = ap.parse_args()
    omap = load_map()
    rows_a, align_a = arm_data(args.dir, args.a)
    rows_b, align_b = arm_data(args.dir, args.b)
    if not rows_a or not rows_b:
        print(f"no logs under {args.dir} for {args.a}/{args.b}")
        return 1
    A = report_arm(args.a, rows_a, align_a, omap)
    B = report_arm(args.b, rows_b, align_b, omap)
    print("\n== the same-fruit pairing (the P33 protocol; A = control, B = aligned)")
    pairing = pair_left(rows_a, rows_b)

    # ---- the pre-registered criteria ------------------------------------- #
    print("\n== the pre-registered criteria (PREREG.md sections 2/4/5)")
    share_a = A["passed"] / max(1, len(A["manip"]))
    share_b = B["passed"] / max(1, len(B["manip"]))
    bar = share_b >= 0.90
    print(f"   manipulation check: A {share_a:.0%} ({A['passed']}/{len(A['manip'])}) | "
          f"B {share_b:.0%} ({B['passed']}/{len(B['manip'])}) -> "
          f"{'PASS' if bar else 'FAIL'} (bar: B >= 90 %)")
    left = {}
    for arm, data in ((args.a, A), (args.b, B)):
        sel = [e for e in data["rows"] if e.get("arm") == "left"]
        c = {"ok": 0, "no-grasp": 0, "carried": 0}
        for e in sel:
            k = klass(e)
            if k in c:
                c[k] += 1
        left[arm] = {"n": len(sel), **c}
        print(f"   left {arm}: n={len(sel)} ok={c['ok']} no-grasp={c['no-grasp']} "
              f"carried={c['carried']}")
    ok_up = left[args.b]["ok"] > left[args.a]["ok"]
    mass_down = ((left[args.b]["carried"] + left[args.b]["no-grasp"])
                 < (left[args.a]["carried"] + left[args.a]["no-grasp"]))
    lpair = pairing["left"]
    paired_favors_b = lpair["carried_b_only"] > lpair["carried_a_only"]
    print(f"   left placed {args.a} {left[args.a]['ok']} -> {args.b} {left[args.b]['ok']} "
          f"[{'up' if ok_up else 'not up'}]; failure mass "
          f"{left[args.a]['carried']+left[args.a]['no-grasp']} -> "
          f"{left[args.b]['carried']+left[args.b]['no-grasp']} "
          f"[{'down' if mass_down else 'not down'}]; paired carried-class "
          f"B-only {lpair['carried_b_only']} / A-only {lpair['carried_a_only']} "
          f"[{'favors B' if paired_favors_b else 'does not favor B'}]")
    if not bar:
        print("   VERDICT: IMPLEMENTATION FAILURE (the manipulation check does not "
              "pass; the A/B does not test the hypothesis)")
    elif paired_favors_b and ok_up:
        print("   VERDICT: POSITIVE by the pre-registered primary (the left's paired "
              "carried conversion favors B and the left's placed count is up) - the "
              "adoption gate still needs the P33 protocol's own re-baseline")
    elif ok_up or mass_down:
        # The *middle* branch: the unpaired placed/composite moved. It is the
        # relocation guard of PREREG section 4 (a carried -> no-grasp shuffle
        # must not pass), NOT a win condition - the pre-registered positive
        # needs the paired carried class to favor B (the branch above). On the
        # P34 batch this fires on 3 episodes (28 -> 25, 1 -> 2) and the primary
        # does not move, so the read of record is "no measured improvement".
        print("   VERDICT: NO MEASURED IMPROVEMENT of the primary endpoint - the "
              "unpaired left counts move within noise (see the numbers above) and "
              "the paired carried class does not favor B; the falsifier fires for "
              "the outcome claim")
    else:
        print("   VERDICT: THE FALSIFIER FIRES - the early view is not the mechanism "
              "(the manipulation check passed and the left did not move)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
