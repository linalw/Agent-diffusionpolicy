#!/usr/bin/env python3
"""P66 phase 4 report: the place leg's **rail-crossing** clearance read.

Closes gate (a) of `logs/p66/P3_RESULTS.md`: does the lowered lift (the 0.20 m
rung, `FRUIT_LIFT_DZ=-0.08`) clip the output rail **at the crossing**?

The instrument (`[carry]` row, `FRUIT_CARRY_DIAG=1`), all three off the same
per-tick `_payload_clearance` pair:

* `clr=`     - the **sample** at the first tick whose `|payload y|` reaches the
  inner rail's centreline (`_output_rail_y` = 0.4125 m shipped - the y the
  +33 mm access floor of record was measured at, `logs/p30a/RAILS_DESIGN.md`),
  with its tick (`/t302`);
* `clr_win=` - the **minimum** over the ticks inside the rail's 25 mm footprint
  (the transfer segment; it opens ~4 ticks before the centreline, so it can
  catch a clip between the crossing sample and the release), also with its tick;
* `clr_min=` - the leg minimum, unchanged (P3's `clr`, same spelling).

Reduction invariant, asserted on every row (`--check`): `clr_min <= clr_win`
(the leg contains the window) and `clr_win <= clr` (the window contains the
crossing tick) - which is what makes the three fields mutually auditable.

**Admissible population**: a payload still in the hand when it went over the
rail. `held` = `clean_slip_max <= 50 mm` (P61's escape convention) **and**
(`loss_row is None or loss_row >= the crossing tick`). A payload that has left
the grip reads the belt, not the hand, so its number is not evidence about the
lift height; those rows are listed and excluded, with the reason named.

    python3 logs/p66/p4_report.py            # print
    python3 logs/p66/p4_report.py --check    # + structural assertions
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P60_REPORT = "logs/p60/p3/report.py"
ARMS = ("control", "L2")
SEED = 77
CELL = [f"logs/p66/p4/{a}_{SEED}.log" for a in ARMS]
#: the access floor of record (`logs/p30a/RAILS_DESIGN.md`): the placed payload
#: must stay this far above the inner rail's top
RAIL_FLOOR_MM = 33.0
#: P61's escape convention: `clean_slip_max > 50 mm` = the payload left the grip
ESCAPE_MM = 50.0
RUNG_DZ = {"control": 0.08, "L2": -0.08}
RUNG_H = {"control": 0.36, "L2": 0.20}

_RE_CLR = re.compile(r"clr=(n/a|[+-]?[\d.]+)mm@(\w+)(?:/t(\d+))?")
_RE_CLR_WIN = re.compile(r"clr_win=(n/a|[+-]?[\d.]+)mm@(\w+)(?:/t(\d+))?")
_RE_CLR_MIN = re.compile(r"clr_min=(n/a|[+-]?[\d.]+)mm@(\w+)")
_RE_DZ_ROW = re.compile(
    r"\[grasp\] lift_dz: dz=([+-][\d.]+)\((default|explicit)\) m above the 0\.28 base "
    r"-> ([\d.]+) m above floor"
)


def load_p60():
    spec = importlib.util.spec_from_file_location("p60_report", ROOT / P60_REPORT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _field(m) -> tuple[float | None, str | None, int | None]:
    if not m or m.group(1) == "n/a":
        return None, None, None
    tick = int(m.group(3)) if (m.lastindex or 0) >= 3 and m.group(3) else None
    return float(m.group(1)), m.group(2), tick


def load_log(path: str, p60) -> dict:
    text = (ROOT / path).read_text(errors="replace")
    eps = p60.parse_direct(str(ROOT / path))
    for ep in eps:
        ep["oc"] = p60.outcome(ep)
        for leg in ep["legs"]:
            line = leg["line"]
            leg["clr"], leg["clr_surface"], leg["clr_tick"] = _field(_RE_CLR.search(line))
            leg["clr_win"], leg["win_surface"], leg["win_tick"] = _field(
                _RE_CLR_WIN.search(line)
            )
            leg["clr_min"], leg["min_surface"], _ = _field(_RE_CLR_MIN.search(line))
    dz_row = None
    for line in text.splitlines():
        m = _RE_DZ_ROW.search(line)
        if m:
            dz_row = dict(dz=float(m.group(1)), origin=m.group(2), target=float(m.group(3)))
            break
    return dict(eps=eps, dz_row=dz_row, text=text)


def place_legs(eps):
    return [
        dict(leg, ep=ep)
        for ep in eps
        for leg in ep["legs"]
        if leg["name"].startswith("place")
    ]


def held_class(leg: dict) -> str:
    """`held` / the reason the leg is not evidence about the lift height."""
    if leg.get("clr_tick") is None and leg.get("win_tick") is None:
        return "no-crossing"
    slip = leg.get("clean_slip")
    if slip is not None and slip > ESCAPE_MM:
        return "escaped(slip)"
    loss, tick = leg.get("loss_row"), leg.get("clr_tick")
    if loss is not None and tick is not None and loss < tick:
        return "escaped(loss-before-x)"
    return "held"


def fmt(v, nd=0) -> str:
    return "n/a" if v is None else f"{v:+.{nd}f}"


def spread(vals, nd=0) -> str:
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return "n/a"
    if len(vals) == 1:
        return f"{vals[0]:+.{nd}f}"
    return f"{statistics.median(vals):+.{nd}f} [{vals[0]:+.{nd}f}..{vals[-1]:+.{nd}f}]"


def verdict_of(worst: float | None) -> str:
    if worst is None:
        return "no data"
    if worst < 0.0:
        return "CLIPPING (< 0 mm)"
    if worst < RAIL_FLOOR_MM:
        return "MARGINAL (0..+33 mm)"
    return "CLEAR (>= +33 mm)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    p60 = load_p60()

    data = {}
    problems: list[str] = []
    for arm, path in zip(ARMS, CELL):
        if not (ROOT / path).exists():
            print(f"missing log: {path}")
            return 1
        d = load_log(path, p60)
        d["legs"] = place_legs(d["eps"])
        d["lifts"] = [
            leg for ep in d["eps"] for leg in ep["legs"] if leg["name"] == "grasp_lift"
        ]
        data[arm] = d
        for leg in d["legs"]:
            tag = f"{path} {leg['side']} {leg['name']}"
            a, b, c = leg["clr_min"], leg["clr_win"], leg["clr"]
            if a is None:
                problems.append(f"{tag}: no clr_min (every place leg has a leg min)")
            if b is not None and a is not None and b > a + 1e-9:
                problems.append(f"{tag}: clr_win {b:+.0f} > clr_min {a:+.0f}")
            if c is not None and b is not None and b > c + 1e-9:
                problems.append(f"{tag}: clr_win {b:+.0f} > clr {c:+.0f} "
                                f"(the window contains the crossing tick)")
            if c is not None and b is None:
                problems.append(f"{tag}: crossing without a window sample")
            if c is not None and leg["clr_surface"] != "rail":
                problems.append(f"{tag}: crossing surface {leg['clr_surface']} is not the rail")
            if c is not None and leg["clr_tick"] is None:
                problems.append(f"{tag}: crossing tick missing")
            if c is None and leg["clr_tick"] is not None:
                problems.append(f"{tag}: crossing tick without a sample")
        for leg in d["lifts"]:
            if leg["clr"] is not None or leg["clr_win"] is not None:
                problems.append(f"{path} lift leg {leg['side']} carries a crossing field")

    print("# P66 phase 4 - the place leg's rail-crossing clearance (gate (a))")
    print(f"# cell: {CELL}, seed {SEED}, FRUIT_CARRY_DIAG=1, the phase-3 scenario verbatim")
    print("# floor of record: +33 mm to the inner rail's top (`logs/p30a/RAILS_DESIGN.md`)")
    print("# crossing |y| = 0.4125 m (the rail's centreline, `_output_rail_y`)\n")

    print("== 0 - the arms, from their own rows ==")
    for arm in ARMS:
        row, eps = data[arm]["dz_row"], data[arm]["eps"]
        print(f"  {arm:8s} episodes={len(eps):2d} placed={sum(1 for e in eps if e['oc'] == 'placed'):2d} "
              f"cnp={sum(1 for e in eps if e['oc'] == 'cnp'):2d} "
              f"never={sum(1 for e in eps if e['oc'] == 'never-held'):2d} | "
              f"lift legs={len(data[arm]['lifts']):2d} place legs={len(data[arm]['legs']):2d} | "
              f"dz={row['dz']:+.2f}({row['origin']}) -> lift end {row['target']:.3f} m "
              f"(= belt_top + {RUNG_H[arm]:.2f})")
    print()

    print("== 1 - every place leg ==")
    print("  arm      ep side  fruit        oc       class                 "
          "slip    clr(tick)        clr_win(tick)     clr_min        loss")
    for arm in ARMS:
        for leg in data[arm]["legs"]:
            ep, cls = leg["ep"], held_class(leg)
            x = "n/a" if leg["clr"] is None else f"{leg['clr']:+.0f}mm/t{leg['clr_tick']}"
            w = "n/a" if leg["clr_win"] is None else f"{leg['clr_win']:+.0f}mm/t{leg['win_tick']}"
            m = "n/a" if leg["clr_min"] is None else f"{leg['clr_min']:+.0f}mm@{leg['min_surface']}"
            slip = leg.get("clean_slip")
            print(f"  {arm:8s} {ep['idx']:2d} {leg['side'][:4]:5s} {ep['fruit'][:12]:12s} "
                  f"{ep['oc'][:8]:8s} {cls:21s} {fmt(slip)} "
                  f"{'':4s} {x:14s} {w:17s} {m:14s} {leg.get('loss_row')}")
    print()

    print("== 2 - THE READ: the crossing clearance on the legs that were still held "
          "(the gate) ==")
    worst_all: dict[tuple[str, str], float | None] = {}
    for arm in ARMS:
        for side in ("left", "right"):
            legs = [l for l in data[arm]["legs"] if l["side"] == side]
            held = [l for l in legs if held_class(l) == "held"]
            other = [l for l in legs if held_class(l) != "held"]
            xs = [l["clr"] for l in held if l["clr"] is not None]
            ws = [l["clr_win"] for l in held if l["clr_win"] is not None]
            ms = [l["clr_min"] for l in held if l["clr_min"] is not None]
            worst = min(xs + ws) if (xs or ws) else None
            worst_all[(arm, side)] = worst
            print(f"  {arm:8s} {side:5s}: held n={len(held)} | crossing {spread(xs)} mm | "
                  f"window min {spread(ws)} mm | leg min {spread(ms)} mm")
            print(f"           worst of the two reductions: {fmt(worst)} mm -> "
                  f"{verdict_of(worst)}")
            neg = [l for l in held if (l["clr"] is not None and l["clr"] < 0)
                   or (l["clr_win"] is not None and l["clr_win"] < 0)]
            print(f"           negative held legs: {len(neg)}/{len(held)}"
                  + ("  " + ", ".join(
                      f"ep{l['ep']['idx']} {l['name']}" for l in neg) if neg else ""))
            if other:
                print(f"           excluded n={len(other)}: "
                      + ", ".join(
                          f"ep{l['ep']['idx']} {l['name']} {held_class(l)} "
                          f"x={fmt(l['clr'])} win={fmt(l['clr_win'])}"
                          for l in other))
    print()

    print("== 3 - the right arm: the same configuration in both arms (the knob's scope "
          "is left-only) ==")
    for side in ("left", "right"):
        a = [l["clr"] for l in data["control"]["legs"]
             if l["side"] == side and held_class(l) == "held" and l["clr"] is not None]
        b = [l["clr"] for l in data["L2"]["legs"]
             if l["side"] == side and held_class(l) == "held" and l["clr"] is not None]
        print(f"  {side:5s}: control {spread(a)} mm (n={len(a)}) | "
              f"L2 {spread(b)} mm (n={len(b)})")
    print("  (the right arm's lift is untouched - `resolve_lift_dz` emits `{'left': dz}` - "
          "so its two columns are\n   the same configuration on two branches: the spread "
          "is the reading's own branch noise.)")
    print()

    print("== 4 - the arithmetic the rung can and cannot buy (derived, not measured) ==")
    belt_top = 1.17
    transfer = 1.35 + 0.10 + 0.08  # output_belt_top_z + place_clearance + the hand's add
    y_place, y_x = 0.50, 0.4125
    f = y_x / y_place
    print(f"  the place target is (0.43, +-{y_place:.2f}, {transfer:.2f}); the leg is a "
          f"straight line from the lift end")
    print(f"  the crossing is {f * 100:.1f} % of the y span, so")
    print(f"    z_crossing = transfer - {1 - f:.3f} * (transfer - lift_end)")
    for arm in ARMS:
        z_lift = belt_top + RUNG_H[arm]
        z_x = transfer - (1 - f) * (transfer - z_lift)
        print(f"  {arm:8s} lift_end {z_lift:.3f} -> z_crossing {z_x:.3f} m "
              f"({(z_x - (transfer - (1 - f) * (transfer - (belt_top + 0.36)))) * 1000:+.0f} mm "
              f"vs the 0.36 m rung)")
    dz = (RUNG_H["control"] - RUNG_H["L2"])
    print(f"  => raising the lift end by {dz * 1000:.0f} mm buys only "
          f"{(1 - f) * dz * 1000:.0f} mm at the crossing; lowering the *transfer* by "
          f"1 mm costs 1.00 mm there.")
    print()

    print("== 5 - VERDICT ==")
    print(f"  floor {RAIL_FLOOR_MM:.0f} mm (the access floor of record)")
    for arm in ARMS:
        for side in ("left", "right"):
            w = worst_all[(arm, side)]
            print(f"  {arm:8s} {side:5s} worst {fmt(w)} mm -> {verdict_of(w)}")
    gate = worst_all[("L2", "left")]
    print(f"  gate (a) on the arm the lever exists for (left, 0.20 m): "
          f"{'PASS' if (gate is not None and gate >= RAIL_FLOOR_MM) else 'FAIL'}"
          + ("" if gate is None else f" ({fmt(gate)} mm vs +{RAIL_FLOOR_MM:.0f} mm)"))

    if args.check:
        print()
        print("== checks ==")
        checks = [
            (f"{arm}: every place leg prints a leg minimum",
             all(l["clr_min"] is not None for l in data[arm]["legs"]))
            for arm in ARMS
        ] + [
            (f"{arm}: no lift leg carries a crossing field",
             all(l["clr"] is None and l["clr_win"] is None for l in data[arm]["lifts"]))
            for arm in ARMS
        ] + [
            (f"{arm}: every crossing sample is a rail sample",
             all(l["clr_surface"] in (None, "rail") for l in data[arm]["legs"]))
            for arm in ARMS
        ] + [
            ("clr_min <= clr_win <= clr on every row (no problems)", not problems),
            ("the 0.20 m arm's own row says 1.370 m (the rung is what ran)",
             abs(data["L2"]["dz_row"]["target"] - (1.17 + 0.20)) < 1e-9),
            ("the control's own row says 1.530 m (the shipped height)",
             abs(data["control"]["dz_row"]["target"] - (1.17 + 0.36)) < 1e-9),
        ]
        for what, ok in checks:
            print(f"  {'ok  ' if ok else 'FAIL'} {what}")
        if problems:
            for pr in problems:
                print(f"  !! {pr}")
            print("\nFAIL: checks failed")
            return 1
        print("\nPASS: the crossing read is consistent on every row")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
