#!/usr/bin/env python3
"""P35 phase 2: the arm-park A/B report (the per-call check + the P33 endpoints).

    python3 logs/p35/park_ab_report.py --dir logs/p35/B_ab --a A --b B

Read-only. Parses the `A_N.log` / `B_N.log` written by `scripts/112_rl_ab.sh`:

  * the episode rows through the pinned W7-B parser (`logs/w7/B_ab_report.py`),
    so the class definitions are the W7-B/W7-C/P33 convention (ok / no-contact =
    `grasped=False` / carried-not-placed = `grasped=True, placed=False`),
  * the `[park]` rows (the manipulation check of `logs/p35/PREREG.md` section 2,
    amended by `logs/p35/B_PREREG_AMEND.md` and re-issued by
    `logs/p35/C_PREREG_AMEND.md`): M1 (held vs the pose the reset achieved) and
    M2a (the arm term at the band's worst call) are the gate of record over the
    **+0.30..+0.40** band; M2b (the episode-relative `rel`) is reported - its
    denominator is a **running** `px*d^2` maximum, updated on every non-stale
    call, so a band call is normalised against another call's geometry, and the
    small (22-47 px) masks make its 0.85 bar a raster-drift readout,
  * the `[align]` counters (`FRUIT_RESET_ALIGN_DIAG=1`): the first call's
    along/x and the depth-corrected `pfc`/`pcm` pair.

Prints, per arm: the check, the per-arm/class split, the composite failure mass
(carried + no-contact), the cycle, the failure reasons; then the **exact-instance**
pairing (same run, episode, species, diameter, arm - the P33 convention), the
class-transition matrix with the carried-class conversions (the primary
endpoint), the one-sided sign test, and the right-arm `x < 0.26` outer-band
subgroup.
"""

from __future__ import annotations

import argparse
import glob
import math
import os
import re
import statistics as st
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "w7"))

import B_ab_report as mech  # noqa: E402  (the pinned W7-B parser)

PARK = re.compile(
    r"\[park\] episode (\d+) arm=(\w+) inactive=(\w+) park=(\S+) "
    r"m1_hold=(\S+) m1_hold_ok=(-?\d+) m1_cmd=(\S+) "
    r"m2_arm=(\S+) m2_arm_ok=(-?\d+) m2_rel=(\S+) m2_rel_ok=(-?\d+) "
    r"m2_ok=(-?\d+) m2_vis=(\S+) band=(\S+) band_x=(\S+) band_px=(-?\d+) "
    r"band_disc=(\S+) band_vis=(\S+) arm_px=(-?\d+) band_frac=(\S+) "
    r"band_calls=(\d+) stale_skipped=(\d+) worst_arm_at=(\S+) "
    r"worst_vis_at=(\S+) min_frac=(\S+) max_frac=(\S+) drift=(\S+) "
    r"calls=(\d+) q=(\S+) q_settled=(\S+) top=(.*)$"
)
ALIGN = re.compile(
    r"\[align\] episode (\d+) knob=\d+ y0=(\S+) reset=(\S+) steps=\d+ jaw=(\S+) "
    r"settle=\d+ first=(\S+) x=(\S+) first_d=(\S+) first_px=(-?\d+) "
    r"first_vis_call=(-?\d+) hidden=(\d+) zone_n=(\d+) zone_zero=(\d+) "
    r"zone_px=(-?\d+) px_max=(-?\d+) pfc=(-?\d+) pcm=(-?\d+) calls=(\d+)"
)
def fnum(text: str, default: float = float("nan")) -> float:
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def klass(e: dict) -> str:
    if e.get("success"):
        return "ok"
    if e.get("success") is False and not e.get("grasped"):
        return "no-contact"
    if e.get("success") is False and e.get("grasped") and not e.get("placed"):
        return "carried"
    return "other"


def sign_test_p(better: int, worse: int) -> float:
    n = better + worse
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(better, n + 1)) / (2.0 ** n)


def read_arm(directory: str, label: str) -> dict[int, dict]:
    """{run: {"eps": [...], "park": {ep: row}, "align": {ep: row}}}"""
    out: dict[int, dict] = {}
    for path in sorted(glob.glob(os.path.join(directory, f"{label}_*.log"))):
        stem = os.path.basename(path)[:-4]
        try:
            run = int(stem.rsplit("_", 1)[1])
        except (IndexError, ValueError):
            continue
        rec = {"eps": mech.parse_log(path), "park": {}, "align": {},
               "path": path}
        for line in open(path, encoding="utf-8", errors="replace"):
            m = PARK.search(line)
            if m:
                rec["park"][int(m.group(1))] = {
                    "arm": m.group(2), "inactive": m.group(3), "park": m.group(4),
                    "m1_hold": fnum(m.group(5)), "m1_hold_ok": int(m.group(6)),
                    "m1_cmd": fnum(m.group(7)),
                    "m2_arm": fnum(m.group(8)), "m2_arm_ok": int(m.group(9)),
                    "m2_rel": fnum(m.group(10)), "m2_rel_ok": int(m.group(11)),
                    "m2_ok": int(m.group(12)), "m2_vis": fnum(m.group(13)),
                    "band": fnum(m.group(14)), "band_x": fnum(m.group(15)),
                    "band_px": int(m.group(16)), "band_disc": fnum(m.group(17)),
                    "band_vis": fnum(m.group(18)), "arm_px": int(m.group(19)),
                    "band_frac": fnum(m.group(20)), "band_calls": int(m.group(21)),
                    "stale_skipped": int(m.group(22)),
                    "worst_arm_at": fnum(m.group(23)), "worst_vis_at": fnum(m.group(24)),
                    "min_frac": fnum(m.group(25)), "max_frac": fnum(m.group(26)),
                    "drift": fnum(m.group(27)), "calls": int(m.group(28)),
                    "q": m.group(29), "q_settled": m.group(30), "top": m.group(31),
                }
                continue
            m = ALIGN.search(line)
            if m:
                rec["align"][int(m.group(1))] = {
                    "reset": fnum(m.group(3)), "first": fnum(m.group(5)),
                    "x": fnum(m.group(6)), "first_px": int(m.group(8)),
                    "hidden": int(m.group(10)), "zone_n": int(m.group(11)),
                    "zone_zero": int(m.group(12)), "zone_px": int(m.group(13)),
                    "px_max": int(m.group(14)), "pfc": int(m.group(15)),
                    "pcm": int(m.group(16)), "calls": int(m.group(17)),
                }
        out[run] = rec
    return out


def qvec(text: str) -> list[float]:
    return [fnum(v) for v in text.split(",") if v]


def read_refs() -> tuple[list[float], list[float]]:
    """(`ready`, `back`) left-arm vectors, from the shipped configs."""
    import json
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
    with open(os.path.join(root, "configs/waypoints.json"), encoding="utf-8") as fh:
        ready = [float(v) for v in json.load(fh)["arms"]["left"]["ready"]]
    with open(os.path.join(root, "configs/arm_parks.json"), encoding="utf-8") as fh:
        back = [float(v) for v in json.load(fh)["parks"]["back"]["left"]]
    return ready, back


def m1_prime(row: dict, ready: list[float], back: list[float]) -> tuple[float, float, int]:
    """(d_back, d_ready, pass) - is the realized pose the park and not `ready`?"""
    q = qvec(row.get("q_settled") or row.get("q") or "")
    if len(q) != 7:
        return float("nan"), float("nan"), 0
    d_back = max(abs(a - b) for a, b in zip(q, back))
    d_ready = max(abs(a - b) for a, b in zip(q, ready))
    ok = int(d_back <= 0.15 and d_ready >= 0.30
             and row["drift"] == row["drift"] and row["drift"] <= 0.02)
    return d_back, d_ready, ok


def check_block(label: str, arm: dict[int, dict], ready: list[float],
                back: list[float]) -> None:
    """The Gate-1 P0 check: M1 held-vs-achieved, M2 at the band's worst call."""
    rows = [(run, ep, arm[run]["park"][ep]) for run in sorted(arm)
            for ep in sorted(arm[run]["park"])]
    if not rows:
        print(f"== arm {label}: no [park] rows")
        return
    print(f"== arm {label}: the manipulation check ({len(rows)} episodes)")
    banded = [r for _, _, r in rows if r["band_calls"] > 0]
    for side in ("left", "right"):
        sel = [r for _, _, r in rows if r["inactive"] == side]
        sb = [r for r in sel if r["band_calls"] > 0]
        print(f"  inactive={side:5s}: n={len(sel)} with_band={len(sb)} "
              f"park={sorted({r['park'] for r in sel})}")
        if not sb:
            continue
        print(f"      M1 held vs the pose the reset ACHIEVED (<=0.02 rad): "
              f"{sum(r['m1_hold_ok'] for r in sb)}/{len(sb)} | "
              f"median {st.median([r['m1_hold'] for r in sb]):.3f} rad | "
              f"achieved-vs-commanded residual median "
              f"{st.median([r['m1_cmd'] for r in sb]):.3f} rad")
        if side == "left":
            triples = [m1_prime(r, ready, back) for r in sb]
            print(f"      M1 applied+stable (nearest reference + drift): "
                  f"{sum(t[2] for t in triples)}/{len(sb)} | "
                  f"|q-back| median={st.median([t[0] for t in triples]):.3f} "
                  f"|q-ready| median={st.median([t[1] for t in triples]):.3f} "
                  f"drift max={max(r['drift'] for r in sb):.3f} rad")
        print(f"      M2a the arm term at the band's WORST call (<0.10): "
              f"{sum(r['m2_arm_ok'] for r in sb)}/{len(sb)} | "
              f"worst-call median {st.median([r['m2_arm'] for r in sb]):.3f} "
              f"(max {max(r['m2_arm'] for r in sb):.3f})")
        print(f"      M2b visibility at the WORST call (rel >= 0.85): "
              f"{sum(r['m2_rel_ok'] for r in sb)}/{len(sb)} | "
              f"median {st.median([r['m2_rel'] for r in sb]):.3f} "
              f"(min {min(r['m2_rel'] for r in sb):.3f}) | "
              f"disc-relative `vis` median {st.median([r['m2_vis'] for r in sb]):.3f} "
              f"(report only)")
        print(f"      M2 both: {sum(1 for r in sb if r['m2_ok'] == 1)}/{len(sb)} | "
              f"band +{min(r['band'] for r in sb):.3f}..{max(r['band'] for r in sb):.3f} "
              f"| band_calls median "
              f"{st.median([r['band_calls'] for r in sb]):.0f} | stale skipped "
              f"{sum(r['stale_skipped'] for r in sb)}")
    if banded:
        print(f"  band calls per episode: median="
              f"{st.median([r['band_calls'] for r in banded]):.0f} "
              f"({min(r['band_calls'] for r in banded)}-"
              f"{max(r['band_calls'] for r in banded)})")


CALL = re.compile(
    r"\[park\] call ep=(\d+) n=(\d+) along=(\S+) x=(\S+) px=(-?\d+) "
    r"disc=(\S+) vis=(\S+) rel=(\S+) arm_px=(-?\d+) tgt_px=(-?\d+) "
    r"frac=(\S+) ok=(-?\d+) top=(.*)$"
)


def band_census(label: str, directory: str) -> None:
    """The band's per-call census, split by which arm is inactive.

    Two terms that need no normalisation and no bar: the share of band calls on
    which the target's mask is **empty** (fully hidden, by whoever) and the
    share on which the inactive arm contributes **any** pixel inside the
    target's projected-disc bbox. Both are exact counts, so they carry neither
    the `rel` bias (a running `px*d^2` maximum, updated per non-stale call) nor
    the `vis` (analytic-disc size) bias.
    """
    paths = [p for p in sorted(glob.glob(os.path.join(directory, f"{label}_*.log")))
             if os.path.basename(p)[:-4].rsplit("_", 1)[1].isdigit()]
    per_side: dict[str, dict] = {}
    for path in paths:
        run = int(os.path.basename(path)[:-4].rsplit("_", 1)[1])
        side_of: dict[int, str] = {}
        for line in open(path, encoding="utf-8", errors="replace"):
            m = PARK.search(line)
            if m:
                side_of[int(m.group(1))] = m.group(3)
        for line in open(path, encoding="utf-8", errors="replace"):
            m = CALL.search(line)
            if not m:
                continue
            side = side_of.get(int(m.group(1)), "?")
            rec = per_side.setdefault(side, {"calls": 0, "hidden": 0,
                                             "arm_any": 0, "ratio": 0.0})
            rec["calls"] += 1
            px, arm = int(m.group(5)), int(m.group(9))
            rec["hidden"] += int(px == 0)
            rec["arm_any"] += int(arm > 0)
            if px > 0 and arm >= 0:
                rec["ratio"] = max(rec["ratio"], arm / float(px))
    if not per_side:
        print(f"== arm {label}: no [park] call rows")
        return
    print(f"== arm {label}: the band census (per-call, exact counts)")
    for side in sorted(per_side):
        r = per_side[side]
        print(f"  inactive={side:5s}: {r['calls']:5d} calls | fully hidden "
              f"{r['hidden']}/{r['calls']} = {100.0 * r['hidden'] / r['calls']:5.1f}% | "
              f"any inactive-arm pixel {r['arm_any']}/{r['calls']} = "
              f"{100.0 * r['arm_any'] / r['calls']:5.1f}% | worst arm/target "
              f"pixel ratio {r['ratio']:.2f}")


def align_block(label: str, arm: dict[int, dict]) -> None:
    rows = [arm[run]["align"][ep] for run in sorted(arm)
            for ep in sorted(arm[run]["align"])]
    if not rows:
        print(f"== arm {label}: no [align] rows")
        return
    firsts = [r["first"] for r in rows if r["first"] == r["first"]]
    print(f"== arm {label}: [align] first-call counters (n={len(rows)})")
    print(f"  first along median={st.median(firsts):+.3f} "
          f"({min(firsts):+.3f}..{max(firsts):+.3f}) | "
          f"first_px=0 on {sum(1 for r in rows if r['first_px'] == 0)}/{len(rows)} | "
          f"pfc median={st.median([r['pfc'] for r in rows]):.0f} "
          f"pcm median={st.median([r['pcm'] for r in rows]):.0f} | "
          f"zone zero-mask median={st.median([r['zone_zero'] for r in rows]):.0f}"
          f"/{st.median([r['zone_n'] for r in rows]):.0f}")


def outcome_block(label: str, eps: list[dict]) -> None:
    left = [e for e in eps if e["arm"] == "left"]
    right = [e for e in eps if e["arm"] == "right"]
    ok = sum(1 for e in eps if e.get("success"))
    print(f"== arm {label}: pooled {ok}/{len(eps)}"
          f" | left {sum(1 for e in left if e.get('success'))}/{len(left)}"
          f" | right {sum(1 for e in right if e.get('success'))}/{len(right)}"
          f" | median cycle {st.median([e['ticks'] for e in eps]):.0f} ticks")
    for name, sel in (("left", left), ("right", right)):
        cls = {"ok": 0, "no-contact": 0, "carried": 0, "other": 0}
        for e in sel:
            cls[klass(e)] += 1
        print(f"  {name:5s}: n={len(sel)} ok={cls['ok']} "
              f"no-grasp={cls['no-contact']} carried-not-placed={cls['carried']} "
              f"other={cls['other']} | composite(carried+no-grasp)="
              f"{cls['carried'] + cls['no-contact']}")


def pairs_block(a: dict[int, dict], b: dict[int, dict], la: str, lb: str,
                x_max: float | None = None) -> None:
    """Exact-instance pairing + the class transitions (the primary endpoint)."""
    runs = sorted(set(a) & set(b))
    counts = {"both_ok": 0, "both_fail": 0, "b_only": 0, "a_only": 0,
              "excluded": 0, "missing": 0}
    trans: dict[tuple[str, str], list[str]] = {}
    rows: list[str] = []
    for run in runs:
        ea = {e["ep"]: e for e in a[run]["eps"]}
        eb = {e["ep"]: e for e in b[run]["eps"]}
        for ep in sorted(set(ea) & set(eb)):
            ra, rb = ea[ep], eb[ep]
            if ra.get("success") is None or rb.get("success") is None:
                counts["missing"] += 1
                continue
            exact = (ra["fruit"] == rb["fruit"]
                     and round(ra["d"], 3) == round(rb["d"], 3)
                     and ra["arm"] == rb["arm"])
            if not exact:
                counts["excluded"] += 1
                continue
            x = fnum(a[run]["park"].get(ep, {}).get("band_x"))
            if x != x:
                x = fnum(a[run]["align"].get(ep, {}).get("x"))
            if x_max is not None and not (x == x and x < x_max):
                continue
            oa, ob = bool(ra["success"]), bool(rb["success"])
            key = ("both_ok" if oa and ob else "a_only" if oa else
                   "b_only" if ob else "both_fail")
            counts[key] += 1
            trans.setdefault((klass(ra), klass(rb)), []).append(
                f"  run{run} ep{ep:2d} {ra['fruit']:10s} {ra['d']:4.1f}cm "
                f"{ra['arm']:5s} x={x:.3f} {la}={klass(ra):11s} "
                f"{lb}={klass(rb):11s} {key}")
    n = counts["b_only"] + counts["a_only"]
    p = sign_test_p(counts["b_only"], counts["a_only"])
    scope = "" if x_max is None else f" (x < {x_max:.2f})"
    usable = sum(counts[k] for k in ("both_ok", "both_fail", "b_only", "a_only"))
    print(f"== exact-instance pairs{scope}: {usable} usable "
          f"(excluded {counts['excluded']} fruit-class, missing {counts['missing']})")
    print(f"  both_ok={counts['both_ok']} both_fail={counts['both_fail']} "
          f"{lb}-only={counts['b_only']} {la}-only={counts['a_only']} "
          f"| one-sided sign p={p:.4f}")
    for pair in sorted(trans):
        tag = "  <== flip" if pair[0] != pair[1] else ""
        print(f"  {pair[0]:11s} -> {pair[1]:11s} {len(trans[pair]):3d}{tag}")
    print(f"  carried-class conversions: {lb}-only "
          f"{len(trans.get(('carried', 'ok'), []))}, {la}-only "
          f"{len(trans.get(('ok', 'carried'), []))} | no-grasp-class: "
          f"{lb}-only {len(trans.get(('no-contact', 'ok'), []))}, {la}-only "
          f"{len(trans.get(('ok', 'no-contact'), []))}")
    for line in rows:
        print(line)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default="logs/p35/B_ab")
    ap.add_argument("--a", default="A")
    ap.add_argument("--b", default="B")
    ap.add_argument("--x-max", type=float, default=0.26,
                    help="the outer-band subgroup (right-arm x < this)")
    args = ap.parse_args()

    a = read_arm(args.dir, args.a)
    b = read_arm(args.dir, args.b)
    if not a or not b:
        print(f"no {args.a}_*/{args.b}_*.log pairs in {args.dir}")
        return 2
    ready, back = read_refs()
    runs = sorted(set(a) & set(b))
    print(f"runs paired: {runs} | episodes per arm: "
          f"{sum(len(a[r]['eps']) for r in runs)} / "
          f"{sum(len(b[r]['eps']) for r in runs)}")
    print()

    for label, arm in ((args.a, a), (args.b, b)):
        check_block(label, arm, ready, back)
        print()
    for label in (args.a, args.b):
        band_census(label, args.dir)
        print()
    for label, arm in ((args.a, a), (args.b, b)):
        align_block(label, arm)
        print()

    eps_a = [e for r in runs for e in a[r]["eps"]]
    eps_b = [e for r in runs for e in b[r]["eps"]]
    for label, eps in ((args.a, eps_a), (args.b, eps_b)):
        outcome_block(label, eps)
        print()

    # ---- the right arm's subgroup and the exact pairing -------------------- #
    right_a = [e for e in eps_a if e["arm"] == "right"]
    right_b = [e for e in eps_b if e["arm"] == "right"]
    print("== the right arm (the lever's population: grade B/C)")
    for label, sel in ((args.a, right_a), (args.b, right_b)):
        outer = []
        for run in runs:
            for e in (a if label == args.a else b)[run]["eps"]:
                if e["arm"] != "right":
                    continue
                x = fnum((a if label == args.a else b)[run]["park"].get(e["ep"], {}).get("band_x"))
                if x != x:
                    x = fnum((a if label == args.a else b)[run]["align"].get(e["ep"], {}).get("x"))
                if x == x and x < args.x_max:
                    outer.append((e, x))
        ok = sum(1 for e, _ in outer if e.get("success"))
        car = sum(1 for e, _ in outer if klass(e) == "carried")
        noc = sum(1 for e, _ in outer if klass(e) == "no-contact")
        print(f"  {label}: right ok {sum(1 for e in sel if e.get('success'))}/{len(sel)} "
              f"| x<{args.x_max:.2f}: n={len(outer)} ok={ok} carried={car} "
              f"no-grasp={noc}")
    print()
    pairs_block(a, b, args.a, args.b)
    print()
    pairs_block(a, b, args.a, args.b, x_max=args.x_max)
    print()

    # ---- failure reasons --------------------------------------------------- #
    def reasons(eps):
        out = set()
        for e in eps:
            if e.get("success"):
                continue
            text = (e.get("notes") or "[]").strip("[]").strip()
            key = "empty note" if not text else re.sub(r"[-+0-9.]+", "#", text)
            out.add(key)
        return out

    ra, rb = reasons(eps_a), reasons(eps_b)
    print("== failure reasons")
    print(f"  {args.a}: {sorted(ra) or 'none'}")
    print(f"  {args.b}: {sorted(rb) or 'none'}")
    print(f"  NEW in {args.b}: {sorted(rb - ra) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
