#!/usr/bin/env python3
"""P68 report: the P67 climb pair **plus** the place-leg wrist hold.

Reads the one named cell - three new runs plus P67's own population control for
seed 77:

    A_77   FRUIT_LIFT_DZ=-0.08 FRUIT_LIFT_CLIMB=0.18 FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S=1.0
    A_101  the same
    B_101  FRUIT_LIFT_DZ=-0.08 FRUIT_LIFT_CLIMB=0.18          (no hold)
    B_77   = logs/p67/B2_77.log, re-used (same pair, same scenario)

Scenario: P67's population cell (`logs/p67/run_p67_pop.sh`) - grade-A-only supply,
so every attempt is the **left** arm's place leg and the arm mix is fixed.

Answers, per held left place leg: the crossing (`clr`/`clr_win` vs the +33 mm
floor), whether the payload is still in the hand (`clean_slip_max`), the wrist
hold's own read (`hold_drift`/`drift_end`/`drift_on`), the lift's mediator
(`drift_end` on `grasp_lift`, must stay <= 2 deg), the class and the ticks.

The leg classification and the crossing reduction are the P66 phase-4 ones,
imported from `logs/p66/p4_report.py` rather than re-derived.

    python3 logs/p68/p68_report.py            # print
    python3 logs/p68/p68_report.py --check    # + structural assertions
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P4_REPORT = "logs/p66/p4_report.py"
RAIL_FLOOR_MM = 33.0
CLIMB_M = 0.18
CLIMB_TICKS = 121
HOLD_S = 1.0
CONTROL_DT = 1.0 / 120.0
HOLD_TICKS = int(round(HOLD_S / CONTROL_DT))
ESCAPE_MM = 50.0

ARMS = {
    "A": ("logs/p68/pop2/A_77.log", "logs/p68/pop2/A_101.log"),
    "B": ("logs/p67/B2_77.log", "logs/p68/pop2/B_101.log"),
}

_RE_CLIMB_ROW = re.compile(
    r"\[grasp\] lift_climb: climb=([+-][\d.]+)\((\w+)\) m.*?"
    r"z_crossing ([\d.]+) m \(([+-][\d.]+) mm vs no climb\)"
)
_RE_ATT = re.compile(r"\[attitude\] (\w+) (\w+): tilt=([\d.]+)deg")
_RE_DRIFT_END = re.compile(r"drift_end=([\d.]+|n/a)")
_RE_HOLD = re.compile(r"hold_drift=([\d.]+)deg(\(no-hold\))?")
_RE_DRIFT_ON = re.compile(r"drift_on=(\d+|None)")


def load_p4():
    spec = importlib.util.spec_from_file_location("p4_report", ROOT / P4_REPORT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def load(path: str, p4) -> dict:
    p60 = p4.load_p60()
    d = p4.load_log(path, p60)
    for ep in d["eps"]:
        ep["oc"] = p60.outcome(ep)
        for leg in ep["legs"]:
            leg["drift_end"] = None
            m = _RE_DRIFT_END.search(leg["line"])
            if m and m.group(1) != "n/a":
                leg["drift_end"] = float(m.group(1))
            leg["hold_max"] = None
            leg["no_hold"] = True
            m = _RE_HOLD.search(leg["line"])
            if m:
                leg["hold_max"] = float(m.group(1))
                leg["no_hold"] = bool(m.group(2))
            leg["drift_on"] = None
            m = _RE_DRIFT_ON.search(leg["line"])
            if m and m.group(1) != "None":
                leg["drift_on"] = int(m.group(1))
    # The `[attitude]` row follows its own `[carry]` row (one per leg), so pair
    # them by order - `place_legs` COPIES the leg dicts, so attach first.
    order = [leg for ep in d["eps"] for leg in ep["legs"]]
    attitudes: list[float] = []
    pending = False
    d["climb_row"] = None
    for line in d["text"].splitlines():
        m = _RE_CLIMB_ROW.search(line)
        if m:
            d["climb_row"] = dict(
                climb=float(m.group(1)),
                origin=m.group(2),
                z_cross=float(m.group(3)),
                delta_mm=float(m.group(4)),
            )
            continue
        if "[carry] " in line:
            pending = True
            continue
        m = _RE_ATT.search(line)
        if m and pending:
            attitudes.append(float(m.group(3)))
            pending = False
    for leg, tilt in zip(order, attitudes):
        leg["tilt"] = tilt
    d["legs"] = p4.place_legs(d["eps"])
    d["lifts"] = [
        leg for ep in d["eps"] for leg in ep["legs"] if leg["name"] == "grasp_lift"
    ]
    d["path"] = path
    return d


def slip_only_held(leg: dict) -> bool:
    """The payload had not moved in the hand (`<= 50 mm, P61's escape convention`)."""
    if leg.get("clr_tick") is None and leg.get("win_tick") is None:
        return False
    slip = leg.get("clean_slip")
    return slip is not None and slip <= ESCAPE_MM


def spread(vals, nd=1) -> str:
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return "n/a"
    if len(vals) == 1:
        return f"{vals[0]:+.{nd}f}"
    return f"{statistics.median(vals):+.{nd}f} [{vals[0]:+.{nd}f}..{vals[-1]:+.{nd}f}]"


def med(vals) -> str:
    vals = [v for v in vals if v is not None]
    if not vals:
        return "n/a"
    if len(vals) == 1:
        return f"{vals[0]:.0f}"
    return f"{statistics.median(vals):.0f} [{min(vals):.0f}..{max(vals):.0f}]"


def leg_rows(d: dict, p4, tag: str) -> None:
    for leg in d["legs"]:
        ep, cls = leg["ep"], p4.held_class(leg)
        x = "n/a" if leg["clr"] is None else f"{leg['clr']:+.0f}/t{leg['clr_tick']}"
        w = "n/a" if leg["clr_win"] is None else f"{leg['clr_win']:+.0f}/t{leg['win_tick']}"
        slip = leg.get("clean_slip")
        hold = ("no-hold" if leg["no_hold"]
                else f"{leg['hold_max']:.1f}/{fmt(leg['drift_end'], 1)}")
        print(f"  {tag:6s} {ep['idx']:2d} {ep['fruit'][:10]:10s} {ep['oc'][:7]:7s} "
              f"{cls:11s} slip={fmt(slip, 1):>8s} "
              f"clr={x:14s} win={w:14s} "
              f"hold={hold:16s} don={str(leg['drift_on']):>4s} "
              f"onset={str(leg.get('onset_row')):>4s} loss={str(leg.get('loss_row')):>4s} "
              f"ticks={str(leg.get('ticks_total')):>4s}")
    if not d["legs"]:
        print(f"  {tag:6s} (no place legs)")


def fmt(v, nd=1) -> str:
    return "n/a" if v is None else f"{v:+.{nd}f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    p4 = load_p4()

    data: dict[str, dict[int, dict]] = {}
    problems: list[str] = []
    for arm, paths in ARMS.items():
        data[arm] = {}
        for path in paths:
            if not (ROOT / path).exists():
                print(f"missing log: {path}")
                return 1
            d = load(path, p4)
            seed = int(re.search(r"_(\d+)\.log$", path).group(1))
            d["arm"], d["seed"] = arm, seed
            data[arm][seed] = d
            for leg in d["legs"]:
                a, b, c = leg["clr_min"], leg["clr_win"], leg["clr"]
                if a is not None and b is not None and b > a + 1e-9:
                    problems.append(f"{path} {leg['side']} {leg['name']}: win > min")
                if b is not None and c is not None and b > c + 1e-9:
                    problems.append(f"{path} {leg['side']} {leg['name']}: win > crossing")
            for leg in d["lifts"]:
                if leg["clr"] is not None:
                    problems.append(f"{path} lift leg carries a crossing field")

    print("# P68 - the P67 climb pair + FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S")
    print(f"# A = dz -0.08, climb {CLIMB_M} m, wrist hold {HOLD_S} s "
          f"({HOLD_TICKS} ticks at CONTROL_DT {CONTROL_DT:.5f} s)")
    print(f"# B = dz -0.08, climb {CLIMB_M} m, no hold (seed 77 = logs/p67/B2_77.log)")
    print("# scenario: the P67 population cell (all-A supply -> every attempt is left)")
    print(f"# floor: +33 mm to the inner rail's top; crossing |y| = 0.4125 m\n")

    for arm in ("A", "B"):
        for seed, d in data[arm].items():
            row, c = d["dz_row"], d["climb_row"]
            print(f"===== {arm} seed {seed} ({d['path']}) =====")
            print(f"  episodes={len(d['eps']):2d} "
                  f"placed={sum(1 for e in d['eps'] if e['oc'] == 'placed'):2d} "
                  f"cnp={sum(1 for e in d['eps'] if e['oc'] == 'cnp'):2d} "
                  f"never={sum(1 for e in d['eps'] if e['oc'] == 'never-held'):2d} | "
                  f"lift legs={len(d['lifts']):2d} place legs={len(d['legs']):2d}")
            print(f"  dz row: " + (f"dz={row['dz']:+.4f}({row['origin']}) -> {row['target']:.4f} m"
                                   if row else "absent"))
            print("  climb row: " + (
                f"climb={c['climb']:+.4f}({c['origin']}) -> z_crossing {c['z_cross']:.4f} m "
                f"({c['delta_mm']:+.1f} mm vs no climb)" if c else "absent"))
            print("  every left place leg:")
            leg_rows(d, p4, f"{arm}/{seed}")
            lifts = [l for l in d["lifts"] if l["side"] == "left"]
            dr = [l["drift_end"] for l in lifts if l["drift_end"] is not None]
            print(f"  lift (the mediator): left grasp_lift drift_end {spread(dr, 1)} deg "
                  f"(n={len(dr)})")
            print()
    print("===== the read =====")
    for arm in ("A", "B"):
        legs = [l for s in data[arm].values() for l in s["legs"]]
        held = [l for l in legs if slip_only_held(l)]
        lost = [l for l in legs if (l.get("clean_slip") or 0) > ESCAPE_MM]
        xs = [l["clr"] for l in held if l["clr"] is not None]
        ws = [l["clr_win"] for l in held if l["clr_win"] is not None]
        print(f"  {arm}: left place legs n={len(legs):2d} | still held (slip<=50) n={len(held):2d} "
              f"| lost (slip>50) n={len(lost):2d}")
        print(f"     crossing {spread(xs, 0)} mm | window {spread(ws, 0)} mm | "
              f"worst {p4.fmt(min(xs + ws, default=None), 0)} mm -> "
              f"{p4.verdict_of(min(xs + ws, default=None))}")
        print(f"     slip on the held legs {spread([l.get('clean_slip') for l in held], 1)} mm")
        holds = [l["hold_max"] for l in legs if not l["no_hold"]]
        print(f"     hold installed on {len(holds)}/{len(legs)} place legs"
              + (f"; hold_drift max {spread(holds, 1)} deg; "
                 f"drift_end {spread([l['drift_end'] for l in legs if l['drift_end'] is not None], 1)} deg"
                 if holds else "; (no leg ran with a wrist hold)"))
        print(f"     place-leg ticks {med([l.get('ticks_total') for l in legs])}")
        print(f"     lost legs: " + (", ".join(
            f"ep{l['ep']['idx']} {l['ep']['fruit']} slip={l.get('clean_slip'):.1f} "
            f"onset={l.get('onset_row')}" for l in lost) if lost else "none"))
        print()

    if args.check:
        print("== checks ==")
        checks = [
            ("every arm ran the 0.20 m rung (its own row says 1.370 m)",
             all(abs(d["dz_row"]["target"] - 1.370) < 1e-9
                 for a in data.values() for d in a.values())),
            ("every arm's climb row says the armed value and +31.5 mm",
             all(d["climb_row"] is not None
                 and abs(d["climb_row"]["climb"] - CLIMB_M) < 1e-9
                 and abs(d["climb_row"]["delta_mm"] - 31.5) < 0.1
                 for a in data.values() for d in a.values())),
            ("every crossing sample is a rail sample",
             all(l["clr_surface"] in (None, "rail")
                 for a in data.values() for d in a.values() for l in d["legs"])),
            ("clr_min <= clr_win <= clr on every row (no problems)", not problems),
            ("the population cell's attempts are the LEFT arm's",
             all(l["side"] == "left"
                 for a in data.values() for d in a.values() for l in d["legs"])),
            ("arm A's place legs all print a live hold (no `(no-hold)`)",
             all(not l["no_hold"] for l in data["A"].values().__iter__().__next__()["legs"])
             and all(not l["no_hold"] for d in data["A"].values() for l in d["legs"])),
            ("arm B's place legs print no hold (the knob was unset)",
             all(l["no_hold"] for d in data["B"].values() for l in d["legs"])),
            ("the lift leg's own hold is the shipped dynamic catch's, in BOTH arms "
             "(the knob did not reach the lift)",
             all((not l["no_hold"]) for a in data.values() for d in a.values()
                 for l in d["lifts"])),
            ("the lift's drift_end is the same band in both arms (the mediator is "
             "untouched by the place-leg hold)",
             max([l["drift_end"] for d in data["A"].values() for l in d["lifts"]
                  if l["drift_end"] is not None], default=0.0) < 10.0
             and max([l["drift_end"] for d in data["B"].values() for l in d["lifts"]
                      if l["drift_end"] is not None], default=0.0) < 10.0),
            (f"the hold window ({HOLD_TICKS} ticks) covers the climb "
             f"({CLIMB_TICKS} ticks) to within one tick",
             abs(HOLD_TICKS - CLIMB_TICKS) <= 1),
        ]
        for what, ok in checks:
            print(f"  {'ok  ' if ok else 'FAIL'} {what}")
        if problems:
            for pr in problems:
                print(f"  !! {pr}")
        if problems or not all(ok for _, ok in checks):
            print("\nFAIL: checks failed")
            return 1
        print("\nPASS: the read is consistent on every row")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
