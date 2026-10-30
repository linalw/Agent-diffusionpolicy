#!/usr/bin/env python3
"""P67 report: the place-leg **climb** re-shape of P66's rail-crossing gate.

Reads two same-batch A/B pairs and answers the two questions the P66 phase-4 gate
left open - does the crossing (`clr=`) clear the **+33 mm** floor of record, and
does the attitude still hold (`drift_end` on the lift legs).

The **registered cell** (`logs/p67/run_p67.sh`, the phase-3/P4 scenario verbatim):

    A  FRUIT_LIFT_DZ=-0.08                       (the P66 L2 arm, no climb)
    B  FRUIT_LIFT_DZ=-0.08 FRUIT_LIFT_CLIMB=0.18 (the re-shape)

The **population cell** (`logs/p67/run_p67_pop.sh`, a recorded deviation: the
registered cell drew only two left attempts and both payloads left the hand inside
the climb, leaving gate (a) with no left read). Its supply is grade-A only, so
every attempt is the left arm's place leg - the crossing geometry is unchanged
(bin 0, drop point y = +0.50, rail centreline |y| = 0.4125):

    A2 FRUIT_LIFT_DZ=-0.08
    B2 A2 + FRUIT_LIFT_CLIMB=0.18

The leg classification, the crossing reduction and the +33 mm floor are the P66
phase-4 ones, imported from `logs/p66/p4_report.py` rather than re-derived.

    python3 logs/p67/p67_report.py            # print
    python3 logs/p67/p67_report.py --check    # + structural assertions
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P4_REPORT = "logs/p66/p4_report.py"
SEED = 77
RAIL_FLOOR_MM = 33.0
CLIMB_M = 0.18
#: the climb's own tick count at the place profile, from the pinned pure
#: `tasks.lift_climb_commands` (`scripts/237_p67_climb_selftest.py` prints it)
CLIMB_TICKS = 121
ESCAPE_MM = 50.0

CELLS = {
    "registered": {"arms": ("A", "B"), "prefix": ""},
    "population": {"arms": ("A2", "B2"), "prefix": ""},
}

_RE_CLIMB_ROW = re.compile(
    r"\[grasp\] lift_climb: climb=([+-][\d.]+)\((\w+)\) m.*?"
    r"z_crossing ([\d.]+) m \(([+-][\d.]+) mm vs no climb\)"
)
_RE_ATT = re.compile(r"\[attitude\] (\w+) (\w+): tilt=([\d.]+)deg")
_RE_DRIFT_END = re.compile(r"drift_end=([\d.]+|n/a)")


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
    # The `[attitude]` row follows its own `[carry]` row (one per leg), so pair
    # them by order rather than by (side, name): the same leg name occurs once per
    # episode, and `place_legs` COPIES the leg dicts (`dict(leg, ep=ep)`), so the
    # values have to be attached to the originals before those lists are built.
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


def slip_only_held(leg: dict, p4) -> bool:
    """A weaker admissibility than P66's: the payload is still *in place*.

    `p4.held_class` also requires tactile contact at the crossing tick, which
    excludes a payload that is still being carried on one pad (`loss_row` is a
    `contacts == 0` row, and a single-sided contact can still hold). This form
    asks only that the payload has not moved in the hand (`<= 50 mm`, P61's
    escape convention) and has crossed the rail at all.
    """
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


def cell_rows(d: dict, p4) -> None:
    for leg in d["legs"]:
        ep, cls = leg["ep"], p4.held_class(leg)
        x = "n/a" if leg["clr"] is None else f"{leg['clr']:+.0f}mm/t{leg['clr_tick']}"
        w = "n/a" if leg["clr_win"] is None else f"{leg['clr_win']:+.0f}mm/t{leg['win_tick']}"
        slip = leg.get("clean_slip")
        t = leg.get("tilt")
        print(f"  {d['arm']:3s} {ep['idx']:2d} {leg['side'][:4]:5s} {ep['fruit'][:10]:10s} "
              f"{ep['oc'][:7]:7s} {cls:20s} "
              f"{'n/a' if slip is None else f'{slip:7.1f}'} "
              f"{str(leg.get('ticks_total')):>5s}  {x:16s} {w:16s} "
              f"{'n/a' if t is None else f'{t:.1f}'}")


def read_side(d: dict, side: str, p4) -> dict:
    legs = [l for l in d["legs"] if l["side"] == side]
    strict = [l for l in legs if p4.held_class(l) == "held"]
    slip = [l for l in legs if slip_only_held(l, p4)]
    return dict(
        n=len(legs),
        strict=strict,
        slip=slip,
        xs=[l["clr"] for l in strict if l["clr"] is not None],
        ws=[l["clr_win"] for l in strict if l["clr_win"] is not None],
        xs_slip=[l["clr"] for l in slip if l["clr"] is not None],
        ws_slip=[l["clr_win"] for l in slip if l["clr_win"] is not None],
        ticks=[l.get("ticks_total") for l in legs if l.get("ticks_total")],
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    p4 = load_p4()

    data: dict[str, dict[str, dict]] = {}
    problems: list[str] = []
    for cell, spec in CELLS.items():
        data[cell] = {}
        for arm in spec["arms"]:
            path = f"logs/p67/{arm}_{SEED}.log"
            if not (ROOT / path).exists():
                print(f"missing log: {path}")
                return 1
            d = load(path, p4)
            d["arm"] = arm
            data[cell][arm] = d
            for leg in d["legs"]:
                a, b, c = leg["clr_min"], leg["clr_win"], leg["clr"]
                if a is not None and b is not None and b > a + 1e-9:
                    problems.append(f"{path} {leg['side']} {leg['name']}: win > min")
                if b is not None and c is not None and b > c + 1e-9:
                    problems.append(f"{path} {leg['side']} {leg['name']}: win > crossing")
            for leg in d["lifts"]:
                if leg["clr"] is not None:
                    problems.append(f"{path} lift leg carries a crossing field")

    print("# P67 - the place-leg climb re-shape (P66 phase-4 gate (a) re-read)")
    print(f"# seed {SEED}, FRUIT_CARRY_DIAG=1, FRUIT_LIFT_DZ=-0.08 in every arm")
    print(f"# climb = {CLIMB_M} m (derived: z_cross = transfer - 0.175*(transfer - lift_end - climb);")
    print("#   +33 mm needs z_cross 1.533 -> climb 0.179, see scripts/237_p67_climb_selftest.py)")
    print(f"# floor: +33 mm to the inner rail's top; crossing |y| = 0.4125 m\n")

    for cell, spec in CELLS.items():
        print(f"===== {cell} cell ({spec['arms'][0]} = control, "
              f"{spec['arms'][1]} = + {CLIMB_M} m climb) =====")
        for arm in spec["arms"]:
            d = data[cell][arm]
            row = d["dz_row"]
            c = d["climb_row"]
            print(f"  {arm}: episodes={len(d['eps']):2d} "
                  f"placed={sum(1 for e in d['eps'] if e['oc'] == 'placed'):2d} "
                  f"cnp={sum(1 for e in d['eps'] if e['oc'] == 'cnp'):2d} "
                  f"never={sum(1 for e in d['eps'] if e['oc'] == 'never-held'):2d} | "
                  f"lift legs={len(d['lifts']):2d} place legs={len(d['legs']):2d} | "
                  f"dz={row['dz']:+.2f}({row['origin']}) -> lift end {row['target']:.3f} m")
            print("     climb row: " + (
                f"climb={c['climb']:+.4f}({c['origin']}) -> z_crossing {c['z_cross']:.4f} m "
                f"({c['delta_mm']:+.1f} mm vs no climb)"
                if c else "absent (the knob is unset - the shipped place leg)"))
        print()
        print("  the attitude the lift still holds (the mediator; the lift leg is untouched):")
        for arm in spec["arms"]:
            d = data[cell][arm]
            left = [l["drift_end"] for l in d["lifts"]
                    if l["side"] == "left" and l["drift_end"] is not None]
            print(f"    {arm} left grasp_lift drift_end {spread(left)} deg (n={len(left)})")
        print()
        print("  every place leg:")
        print("  arm ep side  fruit      oc      class                "
              "slip( mm) ticks  clr(tick)        clr_win(tick)    tilt")
        for arm in spec["arms"]:
            cell_rows(data[cell][arm], p4)
        print()
        print("  the crossing (held = P66's convention: slip <= 50 mm AND contact at the")
        print("  crossing tick; slip-only = the payload had not moved in the hand):")
        for arm in spec["arms"]:
            for side in ("left", "right"):
                r = read_side(data[cell][arm], side, p4)
                if r["n"] == 0:
                    continue
                print(f"    {arm:3s} {side:5s}: legs n={r['n']:2d} | strict n={len(r['strict']):2d} "
                      f"crossing {p4.spread(r['xs'])} win {p4.spread(r['ws'])} -> "
                      f"{p4.verdict_of(min((r['xs'] + r['ws']), default=None))}")
                print(f"    {'':3s} {'':5s}  slip-only n={len(r['slip']):2d} "
                      f"crossing {p4.spread(r['xs_slip'])} win {p4.spread(r['ws_slip'])} -> "
                      f"{p4.verdict_of(min((r['xs_slip'] + r['ws_slip']), default=None))}")
        print()
        print("  the ticks the place legs cost:")
        for side in ("left", "right"):
            a = read_side(data[cell][spec["arms"][0]], side, p4)["ticks"]
            b = read_side(data[cell][spec["arms"][1]], side, p4)["ticks"]
            if a and b:
                print(f"    {side:5s}: {spec['arms'][0]} {statistics.median(a):.0f} "
                      f"(n={len(a)}) | {spec['arms'][1]} {statistics.median(b):.0f} "
                      f"(n={len(b)}) | net "
                      f"{statistics.median(b) - statistics.median(a):+.0f} ticks = "
                      f"{(statistics.median(b) - statistics.median(a)) / 120:+.2f} s")
        print(f"    (the climb segment alone is {CLIMB_TICKS} ticks; the transit itself")
        print("     shortens because it starts 0.18 m higher, so quote the NET.)")
        print()

    print("===== VERDICT =====")
    print(f"  floor {RAIL_FLOOR_MM:.0f} mm (P30-A's access floor of record)")
    for cell, spec in CELLS.items():
        for arm in spec["arms"]:
            for side in ("left", "right"):
                r = read_side(data[cell][arm], side, p4)
                if r["n"] == 0:
                    continue
                w = min(r["xs_slip"] + r["ws_slip"], default=None)
                print(f"  {cell:10s} {arm:3s} {side:5s}: slip-only worst {p4.fmt(w)} mm -> "
                      f"{p4.verdict_of(w)}")

    if args.check:
        print()
        print("== checks ==")
        checks = [
            ("every control arm ran the 0.20 m rung (its own row says 1.370 m)",
             all(abs(data[c][s["arms"][0]]["dz_row"]["target"] - 1.370) < 1e-9
                 for c, s in CELLS.items())),
            ("every control arm has no climb row (the knob was unset)",
             all(data[c][s["arms"][0]]["climb_row"] is None for c, s in CELLS.items())),
            ("every climb arm's row says the armed value",
             all(data[c][s["arms"][1]]["climb_row"] is not None
                 and abs(data[c][s["arms"][1]]["climb_row"]["climb"] - CLIMB_M) < 1e-9
                 for c, s in CELLS.items())),
            ("the climb row's crossing agrees with the formula (+31.5 mm)",
             all(abs(data[c][s["arms"][1]]["climb_row"]["delta_mm"] - 31.5) < 0.1
                 for c, s in CELLS.items())),
            ("every crossing sample is a rail sample",
             all(l["clr_surface"] in (None, "rail")
                 for c, s in CELLS.items() for a in s["arms"]
                 for l in data[c][a]["legs"])),
            ("clr_min <= clr_win <= clr on every row (no problems)", not problems),
            ("no lift leg carries a crossing field",
             all(l["clr"] is None
                 for c, s in CELLS.items() for a in s["arms"]
                 for l in data[c][a]["lifts"])),
            ("the population cell's attempts are the LEFT arm's",
             all(l["side"] == "left"
                 for a in CELLS["population"]["arms"]
                 for l in data["population"][a]["legs"])),
        ]
        for what, ok in checks:
            print(f"  {'ok  ' if ok else 'FAIL'} {what}")
        if problems:
            for pr in problems:
                print(f"  !! {pr}")
        if problems or not all(ok for _, ok in checks):
            print("\nFAIL: checks failed")
            return 1
        print("\nPASS: the climb read is consistent on every row")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
