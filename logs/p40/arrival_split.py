#!/usr/bin/env python3
"""P40 lane B / TASK 2: is the arrival wait supply-bound or arm-bound?

Both ticks are already printed:

  selector / station commit
      two-line   `[biarm] left: station acquired at t=16.4s` - the scheduler's
                 lock-on; the attempt's own first tick is `[run] attempt N: ...
                 sim=a-bs` and the two agree (checked, see `t_acq`)
      single arm `[run] attempt N: picking <fruit> grade <G> ...` - the selection
                 commit, whose tick is the attempt start `sim=a`.  The single arm
                 has no scheduler, so there is no `station acquired` row.

  arrival
      `[task] fruit at pick point: dy=+0.1889 m arrived=True after 51 steps`
      with `[task]   intercept handover: ... dy=+0.1889 m lead=0.189 m`.
      This is the *handover* break (`dy <= lead` ~ 0.189 m), not the pick
      station: the moving catch starts the descent while the fruit is still
      0.19 m upstream.  `after N steps` is the wait loop's tick count (1 tick =
      1/120 s), and the loop re-commands one fixed joint target per tick, so the
      **arm is stationary for the whole wait**.

Supporting rows, all per attempt:
  `[task] at pick pose after 0.87 s`             pre-pose block
  `[cycle] attempt N: prepose=. hover=. descent=. close=. grip=. ...`
                                                 the same blocks plus the hover
                                                 move; single arm only in the
                                                 `[cycle]`-instrumented
                                                 `logs/g/20_rate_single_1.log`
  `[task]   wait step=0 fruit_y=... dy=+...`      the fruit's along-position at
                                                 the wait loop's first tick
                                                 (also prints steps 1-5: six
                                                 consecutive ticks, so the
                                                 belt speed is measurable
                                                 inside one attempt)
  `[task] dynamic descent: waited N ticks (...)`  the handover wait after the
                                                 arrival (inside `descent`)

Pairing rules (each is printed so it can be audited):
  * two-line: the two arms' wait loops overlap, so `wait step=0` rows and
    arrival rows interleave; they are paired in file order (monotone) and then
    adjacent transpositions are taken where they reduce the belt identity's
    residual (2-opt; the concurrent-wait starts at a batch's beginning are the
    only crossings in this corpus).  `[cycle]` rows are printed in *completion*
    order, so the k-th cycle row pairs with the k-th arrival, and the cycle row
    is tied to the attempt index by its `total` vs the attempt's printed span.
  * single arm: everything is serial, so attempt k, cycle k and arrival k pair
    positionally.

The identity used to resolve/verify the pairing, `(dy0 - dy_arr)/0.12 ==
N/120`, is *not* the only evidence that the wait is belt travel: the
within-attempt `wait step=0..5` slope (1.0 mm/tick = 0.12 m/s) and the
`[cycle] descent` reconciliation (wait + handover wait + approach) are
independent of it.
"""
from __future__ import annotations

import re
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BELT = 0.12   # m/s, the shipped encoder speed (`[stats] encoder=-0.120 m/s`)
DT = 1.0 / 120.0

CORPUS = [
    ("logs/p39/p3/accept_C.log", "single"),
    ("logs/p39/p3/pear_C.log", "single"),
    ("logs/p39/p3/twoline_C.log", "twoline"),
    ("logs/p32/A0_bed_twoline_1.log", "twoline"),
    ("logs/w7/10_dense_twoline_1.log", "twoline"),
    ("logs/g/20_rate_single_1.log", "single"),
    ("logs/p32/D1_accept_pear.log", "single"),
    # extension: the P35/P36/P37 acceptance no-harm logs (deduped - see
    # `regrasp_yield.py`'s corpus note)
    ("logs/p35/B_accept_no_harm.log", "single"),
    ("logs/p35/C_accept_no_harm.log", "single"),
    ("logs/p37/accept_no_harm.log", "single"),
]

RE_CYCLE = re.compile(r"\[cycle\] attempt (\d+): (.*)$")
RE_SEG = re.compile(r"(\w+)=([0-9.]+)s")
RE_ACQ = re.compile(r"\[biarm\] (\w+): station acquired at t=([0-9.]+)s")
RE_TARGET = re.compile(r"\[task\] target (\w+) \(grade (\w), ([0-9.]+) cm\) with (\w+) arm")
RE_POSE = re.compile(r"\[task\] at pick pose after ([0-9.]+) s")
RE_WAIT = re.compile(
    r"\[task\]   wait step=(\d+) fruit_y=([-0-9.]+) .* dy=([-+0-9.]+)")
RE_INTERCEPT = re.compile(
    r"\[task\]   intercept handover: fruit_y=([-0-9.]+) dy=([-+0-9.]+) m "
    r"lead=([0-9.]+) m .*queue=(\d+)")
RE_ARRIVE = re.compile(
    r"\[task\] fruit at pick point: dy=([-+0-9.]+) m arrived=(\w+) after (\d+) steps")
RE_DESCENT = re.compile(
    r"\[task\] dynamic descent: waited (\d+) ticks, intercept=([-+0-9.]+) m "
    r"\(station ([-+0-9.]+)")
RE_APPROACH = re.compile(r"\[motion\] approach\(cartesian\): ([0-9.]+) cm, (\d+) samples")
RE_S_PICK = re.compile(r"\[run\] attempt (\d+): picking (\w+) grade (\w)")
RE_S_OUT = re.compile(
    r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+).*notes=\[(.*?)\]"
    r"(?: sim=([0-9.]+)-([0-9.]+)s)?")
RE_T_PICK = re.compile(
    r"\[run\] attempt (\d+) \((\w+)\): picking (\w+) grade (\w) .* sim=([0-9.]+)-([0-9.]+)s")
RE_T_OUT = re.compile(
    r"\[run\] attempt (\d+) \((\w+)\): grasped=(\w+) placed=(\w+).*sim=([0-9.]+)s")


def read(path: Path) -> list[str]:
    return path.read_text(errors="replace").splitlines()


def collect(lines: list[str]) -> tuple[list[dict], list[dict], list[dict]]:
    """(wait-step rows, arrivals, descents) in file order; cycles too."""
    waits, arrives, descents, cycles, poses = [], [], [], [], []
    for i, line in enumerate(lines):
        m = RE_CYCLE.search(line)
        if m:
            cycles.append({"line": i, "idx": int(m.group(1)),
                           **{k: float(v) for k, v in RE_SEG.findall(m.group(2))}})
            continue
        m = RE_POSE.search(line)
        if m:
            poses.append({"line": i, "prepose": float(m.group(1))})
            continue
        m = RE_WAIT.search(line)
        if m:
            waits.append({"line": i, "step": int(m.group(1)),
                          "y": float(m.group(2)), "dy": float(m.group(3))})
            continue
        m = RE_INTERCEPT.search(line)
        if m:
            arrives.append({"line": i, "stage": "icept", "dy": float(m.group(2)),
                            "lead": float(m.group(3)), "queue": int(m.group(4))})
            continue
        m = RE_ARRIVE.search(line)
        if m:
            arrives.append({"line": i, "stage": "arrive", "dy": float(m.group(1)),
                            "arrived": m.group(2) == "True",
                            "steps": int(m.group(3))})
            continue
        m = RE_DESCENT.search(line)
        if m:
            descents.append({"line": i, "waited": int(m.group(1)),
                             "intercept": float(m.group(2)),
                             "station": float(m.group(3))})
            continue
        m = RE_APPROACH.search(line)
        if m:
            descents.append({"line": i, "approach_samples": int(m.group(2))})
    return waits, arrives, descents, cycles, poses


def slope_of(waits: list[dict], first: dict) -> float | None:
    """Belt slope over the `wait step=0..5` run that starts at `first`."""
    run = [w for w in waits if w["step"] == 0 and w["line"] == first["line"]]
    if not run:
        return None
    same = [w for w in waits
            if w["line"] >= first["line"] and w["step"] <= 5
            and w["line"] <= first["line"] + 30]
    # keep only the consecutive run: steps must increase by 1 from `first`
    seq = [first]
    for w in same:
        if w["line"] > seq[-1]["line"] and w["step"] == seq[-1]["step"] + 1:
            seq.append(w)
    if len(seq) < 2:
        return None
    d_t = (seq[-1]["step"] - seq[0]["step"]) * DT
    return (seq[-1]["y"] - seq[0]["y"]) / d_t if d_t else None


def main() -> int:
    rows: list[dict] = []
    print("=" * 134)
    print("PER-ATTEMPT: commit -> arrival, and what the gap is made of")
    print("=" * 134)
    for rel, kind in CORPUS:
        path = ROOT / rel
        if not path.exists():
            print(f"{rel}: MISSING")
            continue
        lines = read(path)
        waits, arrives, descents, cycles, poses = collect(lines)
        # ---- attempts -----------------------------------------------------
        atts: dict[int, dict] = {}
        if kind == "single":
            for line in lines:
                m = RE_S_PICK.search(line)
                if m:
                    atts[int(m.group(1))] = {"idx": int(m.group(1)), "fruit": m.group(2),
                                             "grade": m.group(3), "arm": ""}
                    continue
                m = RE_S_OUT.search(line)
                if m and int(m.group(1)) in atts:
                    atts[int(m.group(1))].update(
                        grasped=m.group(2) == "True", placed=m.group(3) == "True",
                        notes=m.group(4),
                        sim_start=float(m.group(5)) if m.group(5) else None,
                        span=None, sim_end=float(m.group(6)) if m.group(6) else None)
        else:
            for line in lines:
                m = RE_T_PICK.search(line)
                if m:
                    atts[int(m.group(1))] = {
                        "idx": int(m.group(1)), "fruit": m.group(3),
                        "grade": m.group(4), "arm": m.group(2),
                        "sim_start": float(m.group(5)),
                        "sim_end": float(m.group(6))}
                    continue
                m = RE_T_OUT.search(line)
                if m and int(m.group(1)) in atts:
                    atts[int(m.group(1))].update(
                        grasped=m.group(3) == "True", placed=m.group(4) == "True",
                        span=float(m.group(5)))
        # ---- pair the rows to the attempts --------------------------------
        # The two-line interleaves, so the rows cannot be paired by position.
        # The `wait step=0` row is emitted at the wait loop's first tick, i.e.
        # at `sim_start + pre-pose + hover`, all of which the attempt prints
        # itself - so the wait0 rows, sorted by file position, pair with the
        # attempts sorted by that *entry tick*.  No dy and no tick count is
        # used, so the belt identity checked afterwards is an independent test.
        # The arrival is then matched to the attempt by its own printed tick
        # count against the wait that the attempt's fruit position implies,
        # `(dy0 - lead)/0.12`.
        first0 = [w for w in waits if w["step"] == 0]
        arr_rows = [a for a in arrives if a["stage"] == "arrive"]
        for a in atts.values():
            a["cycle"] = None
        if kind == "twoline":
            free = [i for i in atts if atts[i].get("span")]
            for c in cycles:
                best, bd = None, 1e9
                for idx in free:
                    d = abs(atts[idx]["span"] - c.get("total", -99))
                    if d < bd:
                        best, bd = idx, d
                if best is not None:
                    free.remove(best)
                    atts[best]["cycle"] = c
        else:
            cyc_iter = list(cycles)
            for k, i in enumerate(sorted(atts)):
                atts[i]["cycle"] = cyc_iter[k] if k < len(cyc_iter) else None
                if k < len(poses):
                    atts[i]["_pose"] = poses[k]["prepose"]
        by_cycle = [a for a in atts.values()
                    if a.get("cycle") or kind == "single"]
        # The scheduler's lock-on tick vs the attempt's own first tick: for each
        # arm, its k-th `target ... with <arm> arm` row belongs to its k-th
        # attempt, and the commit is the last `station acquired` row before it.
        if kind == "twoline":
            acq_rows, tgt_rows = {"left": [], "right": []}, {"left": [], "right": []}
            for line_no, line in enumerate(lines):
                ma = RE_ACQ.search(line)
                if ma:
                    acq_rows[ma.group(1)].append((line_no, float(ma.group(2))))
                    continue
                mt = RE_TARGET.search(line)
                if mt:
                    tgt_rows[mt.group(4)].append(line_no)
            for arm in ("left", "right"):
                idxs = sorted(i for i in atts if atts[i].get("arm") == arm)
                for k, i in enumerate(idxs):
                    if k >= len(tgt_rows[arm]):
                        continue
                    prev = [t for ln, t in acq_rows[arm] if ln < tgt_rows[arm][k]]
                    atts[i]["t_acq"] = prev[-1] if prev else None
        if kind == "twoline" and all(a.get("sim_start") is not None for a in by_cycle):
            for a in by_cycle:
                a["entry_tick"] = (a["sim_start"] + a["cycle"].get("prepose", 0.0)
                                   + a["cycle"].get("hover", 0.0))
            by_entry = sorted(by_cycle, key=lambda a: a["entry_tick"])
        else:
            # single arm: serial, so log order is time order (checked - every
            # attempt's belt residual comes out at 0 ms with this pairing)
            by_entry = sorted(by_cycle, key=lambda a: a["idx"])
        for a, w in zip(by_entry, first0):
            a["wait0"] = w
        # arrival <- attempt, by the printed tick count vs the implied wait
        lead0 = 0.189
        cand = []
        for a in by_cycle:
            if "wait0" not in a:
                continue
            implied = (a["wait0"]["dy"] - lead0) / BELT
            for arr in arr_rows:
                cand.append((abs(arr["steps"] * DT - implied), a["idx"], arr))
        cand.sort(key=lambda c: c[0])
        taken_a, taken_r = set(), set()
        for err, idx, arr in cand:
            if idx in taken_a or id(arr) in taken_r:
                continue
            taken_a.add(idx)
            taken_r.add(id(arr))
            atts[idx].setdefault("_match_err", err)
            atts[idx]["arr"] = arr
        for a in by_cycle:
            a["match_err"] = a.get("_match_err")
        print(f"\n{rel}  [{kind}]  attempts={len(atts)}  paired={len(by_cycle)}")
        print("  att arm   fruit       commit  entry prepose hover   wait  gap  "
              "  dy0    dy_arr  belt   resid slope  descent-wait")
        for a in by_cycle:
            c = a.get("cycle") or {}
            arr = a.get("arr") or {}
            w0 = a.get("wait0") or {}
            prepose = c.get("prepose") if c else a.get("_pose")
            hover = c.get("hover")
            wait = arr.get("steps", 0) * DT
            gap = (prepose or 0.0) + (hover or 0.0) + wait
            dy0 = w0.get("dy")
            dya = arr.get("dy")
            belt = (dy0 - dya) / BELT if dy0 is not None else None
            resid = wait - belt if belt is not None else None
            sl = slope_of(waits, w0) if w0 else None
            a.update(prepose=prepose, hover=hover, wait=wait, gap=gap, dy0=dy0,
                     dya=dya, belt_wait=belt, resid=resid, slope=sl,
                     commit=a.get("sim_start"),
                     descent=(c.get("descent") if c else None),
                     entry=a.get("entry_tick"),
                     dresid=((c.get("descent") - wait) if c.get("descent") else None),
                     impl_commit=(dy0 + BELT * ((prepose or 0.0) + (hover or 0.0))
                                  if dy0 is not None else None),
                     checks=[])
            if resid is not None and abs(resid) > 2 * DT + 1e-9:
                a["checks"].append(f"belt residual {resid*1000:+.0f} ms")
            if not (0.185 <= dya <= 0.191):
                a["checks"].append(f"arrival dy {dya:+.4f}")
            if a.get("span") and gap > a["span"] + 0.05:
                a["checks"].append(f"gap {gap:.2f} > span {a['span']:.2f}")
            if a.get("t_acq") is not None and a.get("sim_start") is not None \
                    and abs(a["t_acq"] - a["sim_start"]) > 0.05:
                a["checks"].append(
                    f"lock-on {a['t_acq']:.1f}s != attempt start {a['sim_start']:.1f}s")
            if a["dresid"] is not None and not (1.00 <= a["dresid"] <= 2.10):
                # `[cycle] descent` = this wait + the handover wait (0.48-0.70 s)
                # + the approach (0.73-0.75 s) + the track/axis/settle block, so
                # the remainder is 1.0-2.1 s on every printed attempt; this is an
                # independent check on the wait magnitude, and hence on the
                # arrival->attempt match (the descents themselves span 1.8-4.9 s).
                a["checks"].append(f"descent-wait {a['dresid']:.2f} outside 1.0-2.1")
            cmt = "-" if a.get("commit") is None else f"{a['commit']:6.1f}"
            ent = "-" if a.get("entry") is None else f"{a['entry']:6.1f}"
            drs = "-" if a["dresid"] is None else f"{a['dresid']:5.2f}"
            print(f"  {a['idx']:3d} {a['arm']:5s} {a['fruit']:10s} {cmt:>6s} "
                  f"{ent:>6s} {(prepose or 0):6.2f} "
                  f"{(hover if hover else -1):5.2f} "
                  f"{wait:5.2f} {gap:5.2f} "
                  f"{(dy0 if dy0 is not None else float('nan')):+6.3f} "
                  f"{dya:+6.3f} "
                  f"{(belt if belt is not None else float('nan')):6.2f} "
                  f"{(resid*1000 if resid is not None else float('nan')):+5.0f}"
                  f" {(sl if sl else float('nan')):6.4f} {drs:>5s}"
                  + ("" if not a["checks"] else "  CHECK: " + "; ".join(a["checks"])))
            rows.append({"file": rel, "line": kind, **a})

    # ---- pooled ---------------------------------------------------------
    print("\n" + "=" * 134)
    print("POOLED")
    print("=" * 134)

    def q(vals, frac):
        v = sorted(vals)
        return v[min(len(v) - 1, int(round(frac * (len(v) - 1))))]

    for line, label in (("single", "single arm"), ("twoline", "two-line")):
        sel = [r for r in rows if r["line"] == line and r.get("wait")]
        if not sel:
            continue
        # comparable across every log: pre-pose + wait (no hover term)
        base = [r["prepose"] + r["wait"] for r in sel if r.get("prepose")]
        gaps = [r["gap"] for r in sel if r.get("prepose")]
        waits = [r["wait"] for r in sel]
        belts = [r["belt_wait"] for r in sel if r.get("belt_wait") is not None]
        resids = [r["resid"] for r in sel if r.get("resid") is not None]
        slopes = [r["slope"] for r in sel if r.get("slope")]
        print(f"\n{label}: n={len(sel)}   (per-log medians below)")
        print(f"  pre-pose + wait   median {st.median(base):5.2f}s  "
              f"p90 {q(base,0.9):5.2f}s  range {min(base):.2f}-{max(base):.2f}")
        print(f"  the printed wait  median {st.median(waits):5.2f}s  "
              f"p90 {q(waits,0.9):5.2f}s  range {min(waits):.2f}-{max(waits):.2f}")
        print(f"  belt travel in it median {st.median(belts):5.2f}s  "
              f"(dy0-dy_arr)/0.12   residual median "
              f"{st.median(resids)*1000:+.0f} ms, max |residual| "
              f"{max(abs(x) for x in resids)*1000:.0f} ms")
        print(f"  within-attempt belt slope from `wait step=0..5`: "
              f"median {st.median(slopes):.4f} m/s  range "
              f"{min(slopes):.4f}-{max(slopes):.4f} (nominal 0.120)")
        if line == "twoline":
            arm_blk = [r["prepose"] + r["hover"] for r in sel if r.get("hover")]
            gaps_h = [r["gap"] for r in sel if r.get("hover")]
            impl = [r["impl_commit"] for r in sel if r.get("impl_commit")]
            print(f"  full gap (with hover) median {st.median(gaps_h):5.2f}s  "
                  f"p90 {q(gaps_h,0.9):5.2f}s")
            print(f"  arm block (pre-pose+hover) median {st.median(arm_blk):5.2f}s "
                  f"range {min(arm_blk):.2f}-{max(arm_blk):.2f} "
                  f"= {st.median(arm_blk)/st.median(gaps_h)*100:.0f}% of the gap")
            print(f"  implied commit distance (dy at commit, hover frame) median "
                  f"{st.median(impl):.3f} m  range {min(impl):.3f}-{max(impl):.3f}"
                  f"   -> belt time from commit "
                  f"{(st.median(impl)-0.189)/BELT:.2f}s vs gap "
                  f"{st.median(gaps_h):.2f}s")
        else:
            hv = [r["hover"] for r in sel if r.get("hover")]
            impl = [r["impl_commit"] for r in sel if r.get("impl_commit")]
            print(f"  implied commit distance (lower bound: no hover term) median "
                  f"{st.median(impl):.3f} m  range {min(impl):.3f}-{max(impl):.3f}"
                  f"   (shipped selector floor = lead + 0.12*1.5 + 0.03 = "
                  f"{0.189 + BELT*1.5 + 0.03:.3f} m)")
            if hv:
                print(f"  hover block (printed only in the [cycle] log): "
                      f"median {st.median(hv):5.2f}s  -> full gap there "
                      f"median {st.median([r['gap'] for r in sel if r.get('hover')]):5.2f}s")
            else:
                print("  hover block: unprinted (no [cycle] in this log)")
    print("\nper log:")
    for rel, _k in CORPUS:
        sel = [r for r in rows if r["file"] == rel and r.get("wait")]
        if not sel:
            continue
        base = [r["prepose"] + r["wait"] for r in sel if r.get("prepose")]
        waits = [r["wait"] for r in sel]
        print(f"  {rel:34s} n={len(sel):2d}  wait median {st.median(waits):5.2f}s "
              f"p90 {q(waits,0.9):5.2f}s   pre-pose+wait median "
              f"{st.median(base):5.2f}s  max belt residual "
              f"{max(abs(r['resid']) for r in sel if r.get('resid') is not None)*1000:5.0f} ms")
    print("\n`arrived=True after N steps` is the *handover* break (dy <= lead "
          "~0.189 m), not the pick station; the wait loop re-commands one fixed "
          "joint target per tick, so the arm is stationary while it waits.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
