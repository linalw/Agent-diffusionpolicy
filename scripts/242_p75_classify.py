#!/usr/bin/env python3
"""P75: read the `[place-trace]` rows and classify each place-leg escape.

The trace is `FRUIT_PLACE_ONSET_TRACE=<ticks>` in `src/fruit_sorting/tasks.py`
(one row per tick for the first `<ticks>` ticks of every `place*` leg). This
module holds the **classification rule that `logs/p75/METHOD.md` pins before the
run**, so the verdict cannot be chosen after seeing the rows:

    (c) command transient : the commanded-vs-achieved TCP error, or a commanded
                            speed step, appears >= 2 ticks BEFORE the in-hand
                            displacement crosses the 2 mm trigger;
    (a) expulsion         : the measured pad separation drops >= 1 mm, or the
                            tactile contact is lost / halves, at or BEFORE the
                            displacement crosses the trigger;
    (b) slip at constant sep : the displacement crosses with the separation and
                            the force still inside those bands (the residual
                            class: a genuine slide through the gap).

Priority is (c) -> (a) -> (b), because a boundary step that precedes everything
is the *cause* the other two definitions would also accept as a predecessor. A
leg whose displacement never crosses the trigger inside the traced window is
`none` (no escape read).

Usage:
    python3 scripts/242_p75_classify.py logs/p75/direct/A_77.log [more.log ...]
    python3 scripts/242_p75_classify.py --window 12 logs/p75/direct/A_77.log

No simulator, no imports from `src/`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

#: The 2 mm in-hand displacement trigger. It is the repo's own
#: `FRUIT_CARRY_GUARD_TRIGGER` default (0.002 m), i.e. the threshold at which
#: the W8-B instrumentation already calls a leg "slipping".
D_TRIGGER_MM = 2.0
#: A measured pad-separation drop of this much counts as "the pads moved".
SEP_DROP_MM = 1.0
#: Contact loss: the weaker face falls below this fraction of its leg-start value
#: (or the contact count reads 0).
F_DROP_FRAC = 0.5
#: Commanded-vs-achieved TCP error: a boundary transient is an error **above the
#: leg's own steady state** by this much. The baseline is the median of the last
#: third of the traced ticks, so a leg that simply tracks with a large constant
#: error is not a transient, and a leg whose error starts high and decays is.
ERR_MM = 20.0
#: A commanded-speed discontinuity at the leg boundary. The **achieved** side is
#: deliberately not a separate clause: `v_ach` runs at 0.095-0.099 m/s for the
#: first ticks of a *clean* leg while `v_cmd` is still 0.000 (the arm closing the
#: previous leg's 19.4 mm residual), so an `v_ach >= k*v_cmd` clause fires on
#: every leg - measured on the smoke, withdrawn in `logs/p75/METHOD.md`
#: AMENDMENT A1. The achieved-side transient is `tcp_err`'s job (it *is* the
#: integral of that gap), so no information is lost.
V_STEP = 0.10
#: How many ticks "before" the displacement a boundary symptom must be to own
#: the leg (2 = the ordering must be visible, not a same-tick coincidence).
LEAD_TICKS = 2
#: AMENDMENT A3: the pad-shell offset. On a **held** grip this trace measures
#: `sep - gap` = +10.7/+11.0 mm (both cells' clean legs); on a grip whose jaws
#: have been pushed to the mechanical open stop it reads +25..+31 mm. A leg that
#: is **already** single-sided (`n < 2`) with an offset at/above this bound has
#: no live pinch at its first tick - its "collapse" happened before the window,
#: so the in-window first-crossing test has no room to fire and would fall
#: through to (b). Reported as `a0` (expulsion, inherited at the boundary)
#: rather than silently folded into either neighbour.
BOUNDARY_SHELL_MM = 20.0

TRACE_RE = re.compile(
    r"\[place-trace\] (?P<side>\w+) (?P<leg>\w+) t=(?P<t>\d+) "
    r"\|d\|=(?P<d>[-\d.]+)mm "
    r"d=\((?P<dx>[-+\d.]+),(?P<dy>[-+\d.]+),(?P<dz>[-+\d.]+)\)mm "
    r"sep=(?P<sep>[-\d.]+)mm gap=(?P<gap>[-\d.]+)mm "
    r"f=\((?P<f0>[-\d.]+),(?P<f1>[-\d.]+)\)N n=(?P<n>\d+) "
    r"tcp_err=(?P<err>[-\d.]+)mm v_cmd=(?P<vcmd>[-\d.]+) "
    r"v_ach=(?P<vach>[-\d.]+) q_margin=(?P<qm>[-\d.]+)@j(?P<qj>\d+)"
)
CARRY_RE = re.compile(
    r"\[carry\] (?P<side>\w+) (?P<leg>\w+): ticks=(?P<ticks>\d+)/\d+ "
    r"clean_slip_max=(?P<slip>[-\d.]+)mm"
)
EP_RE = re.compile(r"\[rl\] episode (\d+):")
ATTITUDE_RE = re.compile(
    r"\[attitude\] (?P<side>\w+) (?P<leg>\w+): tilt=(?P<tilt>[-\d.]+)deg.*?"
    r"pad_fruit_dz=(?P<dz>[-+][\d.]+)mm"
)


def parse_trace(line: str) -> dict | None:
    m = TRACE_RE.search(line)
    if m is None:
        return None
    return {
        "side": m.group("side"),
        "leg": m.group("leg"),
        "t": int(m.group("t")),
        "d": float(m.group("d")),
        "dx": float(m.group("dx")),
        "dy": float(m.group("dy")),
        "dz": float(m.group("dz")),
        "sep": float(m.group("sep")),
        "gap": float(m.group("gap")),
        "f0": float(m.group("f0")),
        "f1": float(m.group("f1")),
        "n": int(m.group("n")),
        "err": float(m.group("err")),
        "vcmd": float(m.group("vcmd")),
        "vach": float(m.group("vach")),
        "qm": float(m.group("qm")),
        "qj": int(m.group("qj")),
    }


def parse_carry(line: str) -> dict | None:
    m = CARRY_RE.search(line)
    if m is None:
        return None
    out = {
        "side": m.group("side"),
        "leg": m.group("leg"),
        "ticks": int(m.group("ticks")),
        "slip": float(m.group("slip")),
    }
    for key, pat, cast in (
        ("sep_end", r"sep_end=([-\d.]+)mm", float),
        ("force_min", r"force_min=([-\d.]+)N", float),
        ("loss_row", r"loss_row=(-|\d+)", str),
        ("onset_row", r"onset_row=(-|\d+)", str),
        ("sep0", r"sep@onset=([-\d.]+|n/a)mm", str),
        ("res_end", r"res_end=([-\d.]+|n/a)mm", str),
    ):
        mm = re.search(pat, line)
        out[key] = cast(mm.group(1)) if mm is not None else None
    return out


def parse_attitude(line: str) -> dict | None:
    m = ATTITUDE_RE.search(line)
    if m is None:
        return None
    return {
        "side": m.group("side"),
        "leg": m.group("leg"),
        "tilt": float(m.group("tilt")),
        "pad_fruit_dz": float(m.group("dz")),
    }


def _first(ticks: list[dict], pred) -> int | None:
    for row in ticks:
        if pred(row):
            return int(row["t"])
    return None


def classify(ticks: list[dict], **kw) -> dict:
    """Apply the pinned rule to one leg's traced ticks (sorted by `t`).

    Pure: no I/O, so the selfcheck leg can exercise it on synthetic sequences.
    """
    opts = {
        "d_trigger": D_TRIGGER_MM,
        "sep_drop": SEP_DROP_MM,
        "f_drop_frac": F_DROP_FRAC,
        "err_mm": ERR_MM,
        "v_step": V_STEP,
        "lead": LEAD_TICKS,
    }
    opts.update(kw)
    if not ticks:
        return {"cls": "none", "n": 0, "why": "no traced ticks"}
    ticks = sorted(ticks, key=lambda r: r["t"])
    first = ticks[0]
    sep0 = float(first["sep"])
    f0 = min(float(first["f0"]), float(first["f1"]))
    f_strong0 = max(float(first["f0"]), float(first["f1"]))
    #: The force reference is the **stronger** face at t = 0, not the weaker:
    #: a grip that is already single-sided at the leg's first tick (`f=(0, 14)`)
    #: would otherwise read "collapsed" against its own zero. A leg whose
    #: stronger face also reads < 2 N has no live pinch at the boundary at all -
    #: that is the `boundary_open` flag below, reported separately.
    f_ref = max(f0, 1.0)
    sep_gap0 = float(first["sep"]) - float(first["gap"])
    boundary_open = bool(
        int(first["n"]) < 2 and sep_gap0 >= BOUNDARY_SHELL_MM
    )
    err0 = float(first["err"])
    #: The leg's own steady-state tracking error: the median of the last third of
    #: the traced window. A boundary transient is an error above it, so a leg
    #: that tracks with a large constant error cannot be read as a transient.
    tail = sorted(float(r["err"]) for r in ticks[max(0, len(ticks) - max(3, len(ticks) // 3)):])
    err_ss = tail[len(tail) // 2] if tail else err0
    err_lim = err_ss + opts["err_mm"]

    t_d = _first(ticks, lambda r: r["d"] >= opts["d_trigger"])
    t_sep = _first(ticks, lambda r: r["sep"] <= sep0 - opts["sep_drop"])
    t_f = _first(
        ticks,
        lambda r: (max(r["f0"], r["f1"]) < opts["f_drop_frac"] * max(f_strong0, 2.0))
        or r["n"] == 0,
    )
    t_err = _first(ticks, lambda r: r["err"] >= err_lim)
    t_v: int | None = None
    prev = None
    for row in ticks:
        if prev is not None:
            if abs(row["vcmd"] - prev["vcmd"]) >= opts["v_step"]:
                t_v = int(row["t"])
                break
        prev = row
    geom = [t for t in (t_sep, t_f) if t is not None]
    t_geom = min(geom) if geom else None
    cmd = [t for t in (t_err, t_v) if t is not None]
    t_cmd = min(cmd) if cmd else None

    out = {
        "n": len(ticks),
        "sep0": sep0,
        "f0": f0,
        "f_strong0": f_strong0,
        "boundary_open": boundary_open,
        "sep_gap0": sep_gap0,
        "err0": err0,
        "err_ss": err_ss,
        "err_lim": err_lim,
        "d_end": float(ticks[-1]["d"]),
        "t_d": t_d,
        "t_sep": t_sep,
        "t_f": t_f,
        "t_geom": t_geom,
        "t_err": t_err,
        "t_vstep": t_v,
        "t_cmd": t_cmd,
    }
    if t_d is None:
        out["cls"] = "none"
        out["why"] = f"no {opts['d_trigger']:.1f} mm displacement in {len(ticks)} traced ticks"
        return out
    if boundary_open:
        out["cls"] = "a0"
        out["why"] = (
            f"the pinch is already failed at t=0 (n={first['n']}, "
            f"f=({first['f0']:.2f},{first['f1']:.2f}) N, sep-gap="
            f"{sep_gap0:+.1f} mm); displacement crosses at t={t_d}"
        )
        return out
    if t_cmd is not None and t_cmd <= t_d - opts["lead"]:
        out["cls"] = "c"
        which = "tcp_err" if t_cmd == t_err else "v_step"
        out["why"] = f"{which} at t={t_cmd}, displacement at t={t_d} (+{t_d - t_cmd})"
        return out
    if t_geom is not None and t_geom <= t_d:
        out["cls"] = "a"
        which = "sep_drop" if t_geom == t_sep else "force_drop"
        out["why"] = f"{which} at t={t_geom}, displacement at t={t_d}"
        return out
    out["cls"] = "b"
    out["why"] = (
        f"displacement at t={t_d} with sep within {opts['sep_drop']:.1f} mm and "
        f"force above {opts['f_drop_frac']:.0%} of its leg-start value"
        + (f" (geometry moves later, t={t_geom})" if t_geom is not None else "")
    )
    return out


def legs(path: Path) -> list[dict]:
    """Group one log's trace rows **per leg instance**, with its preceding lift row.

    A new group starts at every `t=0` row: the same leg name recurs once per
    episode (`left place0` appears on every left pick), so keying on the name
    alone would concatenate a whole run into one sequence and manufacture
    onsets at the seams - which is exactly the false positive the first version
    of this reader produced.
    """
    groups: list[dict] = []
    open_idx: dict[tuple[str, str], int] = {}
    lift: dict[str, dict] = {}
    att: dict[str, dict] = {}
    cur_ep = -1
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        ep = EP_RE.search(line)
        if ep is not None:
            cur_ep = int(ep.group(1))
        tr = parse_trace(line)
        if tr is not None:
            key = (tr["side"], tr["leg"])
            if tr["t"] == 0 or key not in open_idx:
                groups.append(
                    {
                        "side": tr["side"],
                        "leg": tr["leg"],
                        "ticks": [tr],
                        "lift": lift.get(tr["side"]),
                        "lift_dz": (att.get(tr["side"]) or {}).get("pad_fruit_dz"),
                        "row": None,
                        "ep": cur_ep,
                        "idx": len(groups),
                    }
                )
                open_idx[key] = len(groups) - 1
            else:
                groups[open_idx[key]]["ticks"].append(tr)
            continue
        at = parse_attitude(line)
        if at is not None:
            if at["leg"] == "grasp_lift":
                att[at["side"]] = at
            continue
        cr = parse_carry(line)
        if cr is None:
            continue
        if cr["leg"] == "grasp_lift":
            lift[cr["side"]] = cr
        elif cr["leg"].startswith("place"):
            key = (cr["side"], cr["leg"])
            if key in open_idx:
                groups[open_idx[key]]["row"] = cr
    return groups


def main(argv: list[str]) -> int:
    window = 0
    files: list[str] = []
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--window":
            window = int(args.pop(0))
        else:
            files.append(a)
    if not files:
        print(__doc__)
        return 2
    total = {"a0": 0, "a": 0, "b": 0, "c": 0, "none": 0}
    for name in files:
        path = Path(name)
        print(f"== {path}")
        for leg in legs(path):
            res = classify(leg["ticks"])
            total[res["cls"]] += 1
            lift = leg["lift"] or {}
            row = leg["row"] or {}
            t0 = leg["ticks"][0]
            print(
                f"  {leg['side']:5s} {leg['leg']:6s} traced={res['n']:3d} "
                f"t0(sep={res['sep0']:.1f} gap={t0['gap']:.1f} "
                f"f=({t0['f0']:.2f},{t0['f1']:.2f}) n={t0['n']} "
                f"err={res['err0']:.1f}) "
                f"lift(slip={lift.get('slip')} sep_end={lift.get('sep_end')} "
                f"fmin={lift.get('force_min')} dz={leg.get('lift_dz')}) "
                f"place(slip_max={row.get('slip')} onset={row.get('onset_row')} "
                f"loss={row.get('loss_row')} sep_end={row.get('sep_end')}) "
                f"| t_d={res['t_d']} t_sep={res['t_sep']} t_f={res['t_f']} "
                f"t_cmd={res['t_cmd']} d_end={res['d_end']:.1f}mm "
                f"=> {res['cls'].upper()}"
            )
            print(f"        why: {res['why']}")
            if window:
                print(
                    f"      {'t':>3} {'d':>7} {'dx':>7} {'dy':>7} {'dz':>7} "
                    f"{'sep':>7} {'gap':>7} {'fmin':>6} {'n':>2} "
                    f"{'err':>7} {'vcmd':>6} {'vach':>6}"
                )
                for row in leg["ticks"][:window]:
                    print(
                        f"      {row['t']:3d} {row['d']:7.2f} {row['dx']:+7.2f} "
                        f"{row['dy']:+7.2f} {row['dz']:+7.2f} {row['sep']:7.2f} "
                        f"{row['gap']:7.2f} {min(row['f0'], row['f1']):6.2f} "
                        f"{row['n']:2d} {row['err']:7.2f} {row['vcmd']:6.3f} "
                        f"{row['vach']:6.3f}"
                    )
    print(
        f"\ntotals: a0={total['a0']} a={total['a']} b={total['b']} "
        f"c={total['c']} none={total['none']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
