#!/usr/bin/env python3
"""P42 phase 2: read the bounded pre-close centring (`FRUIT_SEAT_CENTRE=0.010`).

    python3 logs/p42/p3/centre_compare.py > logs/p42/p3/CENTRE_READ.txt

Read-only. Two questions, in the pre-registered order
(`logs/p42/PREREG.md` section 3):

**1. Evaluability (PREREG section 2, mandatory).** The lever's own legs must read
`coherent=False` at the close. The `[seat] centre` row prints that flag from the
*close's own* local variable - the one that decides whether the close re-aims the
jaw at the fruit's live centre every tick - so this read is not inferred from the
carry bookkeeping (whose `[diag] carry-assist ... coherent=` row reads a
different variable, `self._coherent[side]`, and is explained in the output).

**2. The physics-stream identity.** Everything except the instrument prints, the
control vs the lever. A correction that is *absorbed* (the coherent close re-aims
at the fruit every tick) shows up as an identical stream; a branch move shows up
as a first-difference row.

Also printed: the per-grip correction the lever commanded, and the freeze seat
(`|d_xy|`, `asym`) on both arms side by side, plus the class table and the span -
so the levers's "moved the seat by X" and "the class did/did not move" statements
are read off one file.

One run per arm is one deterministic branch (or, for a knob whose command is
absorbed, the *same* branch), and no count here is a rate.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import statistics as st
from pathlib import Path

_SP = importlib.util.spec_from_file_location(
    "seat_parse", Path("logs/p42/p2/seat_parse.py")
)
seat_parse = importlib.util.module_from_spec(_SP)
_SP.loader.exec_module(seat_parse)  # type: ignore[union-attr]

CENTRE = re.compile(
    r"\[seat\] centre (?P<side>\w+) idx=(?P<idx>-?\d+) "
    r"d=\(\s*(?P<dx>[-+0-9.]+)\s*,\s*(?P<dy>[-+0-9.]+)\s*\)mm "
    r"applied=\(\s*(?P<cx>[-+0-9.]+)\s*,\s*(?P<cy>[-+0-9.]+)\s*\)mm "
    r"m=(?P<m>[-+0-9.]+)mm coherent=(?P<coherent>\w+)"
)
RUN = re.compile(
    r"\[run\] attempt (?P<idx>\d+): grasped=(?P<grasped>\w+) "
    r"placed=(?P<placed>\w+) lift=(?P<lift>[-+0-9.]+) m"
)
SPECIES = re.compile(
    r"\[run\]\s+(?P<species>[a-z]+)\s+arm=(?P<arm>\w+)\s+grasped=(?P<grasped>\w+) "
    r"placed=(?P<placed>\w+)"
)
STATS = re.compile(
    r"\[stats\] attempts=(?P<attempts>\d+) successes=(?P<successes>\d+) "
    r"diverted=(?P<diverted>\d+) success_rate=(?P<rate>\d+)%.*?"
    r"sim=(?P<sim>[-+0-9.]+)s total, (?P<per>[-+0-9.]+)s/attempt"
)
COHERENT_DIAG = re.compile(r"carry-assist .*coherent=(?P<c>\w+)")

#: Print-only rows that differ by *which* instrument is armed, not by behaviour
#: (the same filter as `logs/p42/p2/identity.py`, plus this phase's own
#: `[seat] centre` row).
FILTER_SUBSTRINGS = ("[seat]", "[trace]", "[drive]", "[diag]", "[carry]")
FILTER_LITERALS = ("finger drive profile=",)


def physics_rows(path: Path) -> list[str]:
    out = []
    for line in path.read_text(errors="replace").splitlines():
        if not line.startswith("[fruit]"):
            continue
        if any(s in line for s in FILTER_SUBSTRINGS):
            continue
        if any(s in line for s in FILTER_LITERALS):
            continue
        out.append(line)
    return out


def centre_rows(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(errors="replace").splitlines():
        m = CENTRE.search(line)
        if m:
            out.append(
                {
                    "side": m["side"],
                    "fruit": int(m["idx"]),
                    "d": (float(m["dx"]), float(m["dy"])),
                    "c": (float(m["cx"]), float(m["cy"])),
                    "m": float(m["m"]),
                    "coherent": m["coherent"] == "True",
                }
            )
    return out


def coherent_diag(path: Path) -> tuple[int, int]:
    """(False count, True count) of the *carry* bookkeeping's `coherent=` rows."""
    f = t = 0
    for line in path.read_text(errors="replace").splitlines():
        m = COHERENT_DIAG.search(line)
        if m:
            if m["c"] == "True":
                t += 1
            else:
                f += 1
    return f, t


def attempts(path: Path):
    rows = {}
    species = []
    stats = None
    for line in path.read_text(errors="replace").splitlines():
        m = RUN.search(line)
        if m:
            rows[int(m["idx"])] = (m["grasped"] == "True", m["placed"] == "True")
            continue
        m = SPECIES.search(line)
        if m:
            species.append(
                (m["species"], m["arm"], m["placed"] == "True")
            )
            continue
        m = STATS.search(line)
        if m:
            stats = m.groupdict()
    return rows, species, stats


def freeze_key(path: Path):
    """(side, fruit) -> the `[seat] ... freeze` row, in stream order."""
    seats, order, _a, _s, _l, _st = seat_parse.parse(path)
    out = {}
    for key in order:
        _idx, side, fruit = key
        out.setdefault((side, fruit), [r for r in seats[key] if "freeze" in r["when"]][0])
    return out


def med(vals):
    return st.median(vals) if vals else float("nan")


def rng(vals):
    return f"[{min(vals):+.1f},{max(vals):+.1f}]" if vals else "n/a"


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    ctrl, treat = Path(argv[1]), Path(argv[2])
    c_name = ctrl.name
    t_name = treat.name

    print("=" * 96)
    print(f"CONTROL {ctrl}")
    print(f"LEVER   {treat}")
    print("=" * 96)

    # ---- 1. the evaluability read (PREREG section 2) --------------------- #
    rows = centre_rows(treat)
    print()
    print("== 1. EVALUABILITY: does the close re-aim over the one-shot command?")
    print(f"  `[seat] centre` rows in the lever run: {len(rows)} "
          f"(one per grip, as registered)")
    n_true = sum(1 for r in rows if r["coherent"])
    print(f"  close local `coherent=` reads: True {n_true} / False {len(rows) - n_true}")
    cf, ct = coherent_diag(treat)
    print(f"  the carry bookkeeping's `[diag] carry-assist ... coherent=` rows: "
          f"False {cf} / True {ct}")
    print("  NOTE these are two different variables: the close's own local flag")
    print("  (printed above, and the one that gates the per-tick `ik_step`) vs")
    print("  `self._coherent[side]`, which the carry diag prints and which is only")
    print("  ever set True when the pre-grasp servo's `pad_error <= 20 mm`.")
    print("  PREREG section 2's premise was that the second being False means the")
    print("  close is non-coherent; the first is what decides it.")
    print()

    # ---- 2. the physics-stream identity --------------------------------- #
    lh, rh = physics_rows(ctrl), physics_rows(treat)
    print("== 2. PHYSICS STREAM (everything minus the instrument prints)")
    print(f"  A {c_name}: {len(lh)} rows")
    print(f"  B {t_name}: {len(rh)} rows")
    diff = None
    for i, (a, b) in enumerate(zip(lh, rh)):
        if a != b:
            diff = i
            break
    if diff is None and len(lh) == len(rh):
        print(f"  IDENTICAL on all {len(lh)} rows  <- the correction is absorbed")
    else:
        at = min(len(lh), len(rh)) if diff is None else diff
        print(f"  FIRST DIFFERENCE at row {at}")
        for k in range(max(0, at - 2), min(at + 3, len(lh), len(rh))):
            print(f"    A[{k}]: {lh[k]}")
            print(f"    B[{k}]: {rh[k]}")
    print()

    # ---- 3. what the lever commanded, and where the seat ended up -------- #
    print("== 3. THE CORRECTION AND THE FREEZE SEAT")
    print("  d_pre  = the offset the lever READ, pads-fruit, at the correction")
    print("           instant (the value it then corrects: corr = clip(-d_pre,+-m))")
    print("  |frz|  = the same grip's freeze `|d_xy|` (18-22 close ticks later)")
    print("  ctrl   = the control's freeze `|d_xy|` for the same (arm, fruit)")
    print()
    print(f"  {'arm':<6} {'fruit':>5} {'d_pre(x,y)':>16} {'|d_pre|':>8} "
          f"{'applied':>16} {'|frz|':>6} {'ctrl':>6} {'frz-ctrl':>9}")
    fz_c = freeze_key(ctrl)
    fz_t = freeze_key(treat)
    pre, frz, ctrl_f, delta = [], [], [], []
    for r in rows:
        key = (r["side"], r["fruit"])
        row_t = fz_t.get(key)
        row_c = fz_c.get(key)
        d_pre = (r["d"][0] ** 2 + r["d"][1] ** 2) ** 0.5
        pre.append(d_pre)
        if row_t is None:
            print(f"  {r['side']:<6} {r['fruit']:>5} "
                  f"({r['d'][0]:+7.1f},{r['d'][1]:+7.1f}) {d_pre:>8.2f} "
                  f"({r['c'][0]:+7.1f},{r['c'][1]:+7.1f}) {'-':>6} {'-':>6} {'-':>9}")
            continue
        d_frz = (row_t["d"][0] ** 2 + row_t["d"][1] ** 2) ** 0.5
        frz.append(d_frz)
        if row_c is None:
            print(f"  {r['side']:<6} {r['fruit']:>5} "
                  f"({r['d'][0]:+7.1f},{r['d'][1]:+7.1f}) {d_pre:>8.2f} "
                  f"({r['c'][0]:+7.1f},{r['c'][1]:+7.1f}) {d_frz:>6.2f} {'-':>6} {'-':>9}")
            continue
        d_c = (row_c["d"][0] ** 2 + row_c["d"][1] ** 2) ** 0.5
        ctrl_f.append(d_c)
        delta.append(d_frz - d_c)
        print(f"  {r['side']:<6} {r['fruit']:>5} "
              f"({r['d'][0]:+7.1f},{r['d'][1]:+7.1f}) {d_pre:>8.2f} "
              f"({r['c'][0]:+7.1f},{r['c'][1]:+7.1f}) {d_frz:>6.2f} {d_c:>6.2f} "
              f"{d_frz - d_c:>+9.2f}")
    print()
    print(f"  |d_pre|          : median {med(pre):.2f} mm {rng(pre)} (n={len(pre)})")
    print(f"  |d_frz| (lever)  : median {med(frz):.2f} mm {rng(frz)} (n={len(frz)})")
    print(f"  |d_frz| (control): median {med(ctrl_f):.2f} mm {rng(ctrl_f)} "
          f"(n={len(ctrl_f)} paired)")
    print(f"  per-pair change  : median {med(delta):+.2f} mm {rng(delta)} "
          f"(n={len(delta)})")
    print()

    # ---- 4. the seat table, both arms ----------------------------------- #
    for label, path in (("CONTROL", ctrl), ("LEVER", treat)):
        seats, order, atts, species_rows, legs, stats = seat_parse.parse(path)
        bucket: dict[str, dict[str, list[float]]] = {}
        for key in order:
            idx, side, fruit = key
            freeze = [r for r in seats[key] if "freeze" in r["when"]][0]
            meta = atts.get(idx, {})
            grasped = bool(meta.get("grasped", False))
            placed = bool(meta.get("placed", False))
            cls = "placed" if placed else ("escape" if grasped else "no_grasp")
            b = bucket.setdefault(cls, {"xy": [], "asym": [], "n1": 0})
            b["xy"].append((freeze["d"][0] ** 2 + freeze["d"][1] ** 2) ** 0.5)
            b["asym"].append(freeze["asym"])
            b["n1"] += 0 if freeze["n"] >= 2 else 1
        print(f"== 4. FREEZE SEAT, {label} ({path.name})")
        print(f"  {'class':<9} {'n':>2} {'|d_xy| med [range]':>28} "
              f"{'asym med [range]':>24} {'n<2':>4}")
        for cls in ("placed", "escape", "no_grasp"):
            b = bucket.get(cls)
            if not b:
                continue
            print(
                f"  {cls:<9} {len(b['xy']):>2} "
                f"{med(b['xy']):>8.2f} {rng(b['xy']):>19} "
                f"{med(b['asym']):>8.2f} {rng(b['asym']):>15} {b['n1']:>4}"
            )
        allxy = [v for b in bucket.values() for v in b["xy"]]
        allasym = [v for b in bucket.values() for v in b["asym"]]
        print(f"  pooled    {len(allxy):>2} {med(allxy):>8.2f} {rng(allxy):>19} "
              f"{med(allasym):>8.2f} {rng(allasym):>15}")
        print()

    # ---- 5. the walk, both arms ----------------------------------------- #
    print("== 5. THE WALK (drift = d - d_freeze; |drift| mm by sample ordinal)")
    for label, path in (("CONTROL", ctrl), ("LEVER", treat)):
        seats, order, atts, species_rows, legs, stats = seat_parse.parse(path)
        by: dict[tuple[str, int], list[float]] = {}
        one: dict[tuple[str, int], int] = {}
        for key in order:
            idx, side, fruit = key
            meta = atts.get(idx, {})
            grasped = bool(meta.get("grasped", False))
            placed = bool(meta.get("placed", False))
            cls = "placed" if placed else ("escape" if grasped else "no_grasp")
            for k, row in enumerate(seats[key]):
                by.setdefault((cls, k), []).append(
                    sum(c * c for c in row["drift"]) ** 0.5
                )
                one[(cls, k)] = one.get((cls, k), 0) + (0 if row["n"] >= 2 else 1)
        cells = []
        for cls in ("placed", "escape"):
            for k in sorted(k for (c, k) in by if c == cls):
                v = by[(cls, k)]
                cells.append(
                    f"{cls}@{k}={med(v):.1f}{rng(v)}(n={len(v)},n<2={one[(cls, k)]})"
                )
        print(f"  {label:<8} " + "  ".join(cells))
    print()

    # ---- 6. the class table and the span -------------------------------- #
    print("== 6. CLASS AND SPAN")
    for label, path in (("CONTROL", ctrl), ("LEVER", treat)):
        atts, species, stats = attempts(path)
        placed = sum(1 for g, p in atts.values() if p)
        grasped = sum(1 for g, p in atts.values() if g)
        cnp = grasped - placed
        nogr = len(atts) - grasped
        arms = {}
        for _sp, arm, p in species:
            a = arms.setdefault(arm, [0, 0])
            a[0] += 1
            a[1] += 1 if p else 0
        per_arm = " ".join(
            f"{arm}={arms[arm][1]}/{arms[arm][0]}" for arm in ("left", "right") if arm in arms
        )
        print(
            f"  {label:<8} {path.name}: attempts={len(atts)} placed={placed} "
            f"cnp={cnp} no_grasp={nogr} | per-arm placed/attempts {per_arm}"
        )
        if stats:
            print(
                f"           [stats] {stats['successes']}/{stats['attempts']} = "
                f"{stats['rate']}%, diverted={stats['diverted']}, "
                f"{stats['sim']} s total, {stats['per']} s/attempt"
            )
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
