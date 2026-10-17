#!/usr/bin/env python3
"""W7-B A/B: the acquisition-readout aggregate over `logs/w7/B_ab`.

    python3 logs/w7/B_ab_report.py [--dir logs/w7/B_ab] [--a A] [--b B]

Read-only. Parses each `A_N.log` / `B_N.log` written by `scripts/112_rl_ab.sh`
(the direct-presentation rollout logs) and prints, per arm:

  * the per-run episode table (fruit/arm/success/grasped/placed + fire dx;
    a policy-gate fire has no trigger stamp, printed `gate`),
  * the pooled outcomes, the left/right split and the per-class
    trigger-path / policy-gate split (the knob only reaches the trigger path),
  * the mechanism readouts from the `FRUIT_ACQ_DIAG=1` `[acq]` lines:
    the setup stage *stamps* (time-to-park = the `hover` stamp; the handover
    hold = `wait` - `hover`; summing premove+axis+hover double-counts the
    premove whenever the attitude servo converges immediately), the
    close-start tip-fruit offset, the walk-latch state, the first-contact and
    freeze evidence, the joint-limit margin,
  * the classes: no-contact (grasped=False) vs carried-not-placed
    (grasped=True, placed=False) vs ok, per arm.

The mechanism readouts are the primary evidence (a direct rate is one sample;
see AGENTS section 2); `113_rl_report.py` owns the outcome/sign-test verdict.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import statistics as st
import sys

EP_ENV = re.compile(
    r"\[rl\] episode (\d+): (\w+) grade=(\w+) d=([\d.]+)cm bin=(-?\d+) arm=(\w+)"
)
EP_OUT = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(-?\d+) arm=(\w+) success=(\w+) "
    r"grasped=(\w+) placed=(\w+) ticks=(\d+)(?: decision=(\d+))? reward=([-+0-9.eE]+) "
    r"notes=(\[.*?\])(?: presentation|$)"
)
TRIG = re.compile(
    r"intercept trigger \(dy=([-+0-9.]+)cm, dx=([-+0-9.]+)cm, t_arrive=([0-9.]+)s.*?"
    r"finger=[0-9.]+(?:, lead=([0-9.]+)s/reach=([0-9.]+))?\)"
)
ACQ = re.compile(
    r"\[acq\] (\w+) idx=(\d+): "
    r"setup\[premove=(\S+) axis=(\S+) hover=(\S+) wait=(\S+) catchup=(\S+)\]s "
    r"catchup=(\d+)t res=(\S+)mm last=\(([^)]*)\)mm \| "
    r"close_start=\(([^)]*)\)mm vx0=(\S+) latch=(\w+) \| "
    r"contact=(.*?) freeze=(.*?) span=(\S+)->(\S+)mm Fmax=(\S+) \| "
    r"q2=(\S+)/(\S+) clip_min=(\S+)mrad@j(\S+)"
)


def _floats(text):
    out = []
    for part in text.split(","):
        part = part.strip()
        try:
            out.append(float(part))
        except ValueError:
            out.append(float("nan"))
    return out


def parse_log(path):
    eps = []
    for line in open(path, encoding="utf-8", errors="replace"):
        m = EP_ENV.search(line)
        if m:
            eps.append({
                "ep": int(m.group(1)), "fruit": m.group(2), "grade": m.group(3),
                "d": float(m.group(4)), "arm": m.group(6), "acq": None,
            })
            continue
        m = ACQ.search(line)
        if m and eps and eps[-1].get("success") is None:
            eps[-1]["acq"] = {
                "arm": m.group(1), "idx": int(m.group(2)),
                "premove_s": float(m.group(3)), "axis_s": float(m.group(4)),
                "hover_s": float(m.group(5)), "wait_s": float(m.group(6)),
                "catchup_s": float(m.group(7)), "catchup_ticks": int(m.group(8)),
                "residual_mm": float(m.group(9)),
                "last_mm": _floats(m.group(10)),
                "close_start_mm": _floats(m.group(11)),
                "vx0": float(m.group(12)), "latch": m.group(13),
                "contact": m.group(14).strip(), "freeze": m.group(15).strip(),
                "span0_mm": float(m.group(16)), "span1_mm": float(m.group(17)),
                "fmax": float(m.group(18)), "q2": float(m.group(19)),
                "q2_hi": float(m.group(20)), "clip_min_mrad": float(m.group(21)),
                "clip_joint": int(m.group(22)),
            }
            continue
        m = EP_OUT.search(line)
        if m and eps and eps[-1]["ep"] == int(m.group(1)):
            rec = eps[-1]
            rec.update(
                success=m.group(6) == "True", grasped=m.group(7) == "True",
                placed=m.group(8) == "True", ticks=int(m.group(9)),
                notes=m.group(12),
            )
            trig = TRIG.search(m.group(12))
            if trig:
                rec["dx"] = float(trig.group(2))
                rec["t_arrive"] = float(trig.group(3))
                rec["lead"] = float(trig.group(4)) if trig.group(4) else None
                rec["reach"] = float(trig.group(5)) if trig.group(5) else None
    return eps


def fmt_list(vals, spec="{:+.1f}"):
    return "[" + ",".join(spec.format(v) for v in vals) + "]"


def dx_cell(e):
    """Fire-time `dx` cell (fixed width 6).

    A trigger-path attempt carries the intercept-trigger stamp and a value; a
    policy-gate fire (`finger < 0.030 and |jaw-fruit|xy < 0.06`) has no trigger
    stamp at all, so print `gate` instead of the old `+nan`; anything else
    (no outcome note) prints `-`.
    """
    dx = e.get("dx")
    if dx is not None:
        return f"{dx:+.1f}cm"
    if "policy closed on the fruit" in (e.get("notes") or ""):
        return " gate "
    return "  -   "


def summarize(label, eps):
    left = [e for e in eps if e["arm"] == "left"]
    right = [e for e in eps if e["arm"] == "right"]
    ok = [e for e in eps if e.get("success")]
    noc = [e for e in eps if e.get("success") is False and not e.get("grasped")]
    carried = [e for e in eps if e.get("success") is False and e.get("grasped")
               and not e.get("placed")]
    print(f"== {label}: {len(ok)}/{len(eps)} ok | left {sum(1 for e in left if e.get('success'))}/{len(left)} "
          f"right {sum(1 for e in right if e.get('success'))}/{len(right)} | "
          f"no-contact {len(noc)} carried-not-placed {len(carried)}")
    # The knob only reaches the trigger path: a policy-gate fire has no trigger
    # stamp, so the class split is part of the readout (see `dx_cell`).
    for cls, pred in (
        ("no-contact", lambda e: e.get("success") is False and not e.get("grasped")),
        ("carried-not-placed", lambda e: e.get("success") is False
         and e.get("grasped") and not e.get("placed")),
    ):
        for arm in ("left", "right"):
            sel = [e for e in eps if e["arm"] == arm and pred(e)]
            if not sel:
                continue
            trig = sum(1 for e in sel if e.get("dx") is not None)
            gate = sum(1 for e in sel if e.get("dx") is None
                       and "policy closed on the fruit" in (e.get("notes") or ""))
            extra = "" if trig + gate == len(sel) else f" + {len(sel) - trig - gate} no-note"
            print(f"  {arm} {cls}: {len(sel)} = {trig} trigger-path + {gate} policy-gate{extra}")
    for e in eps:
        a = e.get("acq")
        core = (f"  ep{e['ep']:2d} {e['fruit']:10s} {e['arm']:5s} d={e['d']:.1f} "
                f"success={str(e.get('success')):5s} grasped={str(e.get('grasped')):5s} "
                f"placed={str(e.get('placed')):5s} dx={dx_cell(e)}")
        if a is None:
            print(core + "  [no acq line]")
            continue
        print(core + (
            "  | stamps p/a/h/w/c={:.2f}/{:.2f}/{:.2f}/{:.2f}/{:.2f}s "
            "catchup={}t res={:.1f}mm close_start_y={:+.1f}mm latch={} contact={} "
            "freeze={} q2clip={:+.1f}@j{}").format(
                a["premove_s"], a["axis_s"], a["hover_s"], a["wait_s"], a["catchup_s"],
                a["catchup_ticks"], a["residual_mm"], a["close_start_mm"][1], a["latch"],
                a["contact"], a["freeze"], a["clip_min_mrad"], a["clip_joint"]))
    # distribution of the left close-start offsets (the acquisition error)
    for arm in ("left", "right"):
        offs = [e["acq"]["close_start_mm"][1] for e in eps
                if e["arm"] == arm and e.get("acq")]
        if offs:
            abs_sorted = sorted(abs(v) for v in offs)
            p90 = abs_sorted[int(0.9 * (len(abs_sorted) - 1))]
            print(f"  {arm} close-start |y| mm: n={len(offs)} "
                  f"median={st.median(abs(v) for v in offs):.1f} "
                  f"p90={p90:.1f} "
                  f"max={max(abs(v) for v in offs):.1f} {fmt_list(offs)}")
    # The `[acq]` stage values are *stamps* from the fire. `axis_s` equals
    # `premove_s` when the attitude servo converges immediately, so the old
    # `premove+axis+hover` sum double-counted the premove: the time to park is
    # the `hover` stamp and the handover hold is `wait` - `hover`.
    acq_rows = [e["acq"] for e in eps if e.get("acq")]
    if acq_rows:
        parks = [a["hover_s"] for a in acq_rows]
        holds = [a["wait_s"] - a["hover_s"] for a in acq_rows]
        axis_extra = [a["axis_s"] - a["premove_s"] for a in acq_rows]
        nz = [v for v in axis_extra if v > 0.005]
        print(f"  time to park (hover stamp): median={st.median(parks):.2f}s "
              f"min={min(parks):.2f} max={max(parks):.2f}")
        print(f"  hold at hover (wait-hover): median={st.median(holds):.2f}s "
              f"min={min(holds):.2f} max={max(holds):.2f}")
        print(f"  attitude-servo extra (axis-premove): n>5ms={len(nz)}/{len(axis_extra)}"
              + (f" max={max(nz):.2f}s" if nz else ""))
    leads = [e["lead"] for e in eps if e.get("lead") is not None]
    if leads:
        print(f"  effective lead at fire: median={st.median(leads):.2f}s "
              f"min={min(leads):.2f} max={max(leads):.2f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default="logs/w7/B_ab")
    ap.add_argument("--a", default="A")
    ap.add_argument("--b", default="B")
    args = ap.parse_args()
    found = 0
    for label in (args.a, args.b):
        eps = []
        for path in sorted(glob.glob(os.path.join(args.dir, f"{label}_*.log"))):
            eps.extend(parse_log(path))
        if not eps:
            continue
        found += 1
        print(f"== arm {label}")
        summarize(label, eps)
        print()
    return 0 if found else 2


if __name__ == "__main__":
    raise SystemExit(main())
