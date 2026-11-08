#!/usr/bin/env python3
"""P131 census - is the ring's over-closure the aperture *law* or the *drive*?

Reads the `[cage]` rows of P130's freeze-off cells (`F5`, `F6`) and P108's
freeze-on controls (`B_s5`, `B_s6`) and answers, per attempt, the one question
the phase turns on:

    the commanded aperture `aper` against the law that actually set it.

The record's `pinch_width` law for the four-pad ring is `0.98 x the widest
horizontal extent`, but the dynamic close does not end there: the two-jaw
two-phase ramp's load target is `deep = 0.97 x min(radial, axial)` (the fruit's
*height* on an upright fruit).  For a flat fruit (apple, peach, tomato, orange,
lychee) `min` is the axial extent, so the ramp drives the ring 5-13 % inside the
fruit's width.  The census computes, from the pool's own mesh profiles
(`meshes.axis_extent`, no simulator), the fruit's radial and axial extents and
compares:

  `ramp = 0.97 * min(R, A)`   the two-jaw load target the close actually ran to
  `law  = 0.98 * R`           the ring's own widest-horizontal law

A **law** failure is `aper ~ ramp < law` on a *seated* ring (the fruit between
the pads, `off <= 15 mm`); a **drive** failure is the measured pad span below
the commanded aperture (`sep < aper`, only visible in the cells that carry the
P131 `sep=` field).  A ring that *missed* the fruit (large `off`) also reads
`aper < dia - 4 mm` but has no fruit between its pads - P110's `dia` threshold
cannot tell the two apart, and the strawberry's class `dia` is its **height**
(its width is `0.792 d`), so the census reports the corrected comparison too.

    python3 logs/p131/census.py logs/p130/F5.log logs/p130/F6.log \
        logs/p108/B_s5.log logs/p108/B_s6.log

Plain python (the `pxr` import is stubbed - the mesh profiles are pure
arithmetic), no simulator, no store, no reference.
"""

from __future__ import annotations

import os
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

# --- stub pxr just enough to import fruit_sorting.meshes -------------------- #
for _name in ("pxr",):
    _mod = types.ModuleType(_name)
    _mod.__path__ = []
    sys.modules.setdefault(_name, _mod)
for _sub in ("Gf", "Sdf", "Usd", "UsdGeom", "UsdPhysics", "UsdShade"):
    _m = types.ModuleType(f"pxr.{_sub}")
    _m.__path__ = []
    sys.modules.setdefault(f"pxr.{_sub}", _m)
    setattr(sys.modules["pxr"], _sub, _m)
sys.modules["pxr"].__path__ = []

import numpy as np  # noqa: E402

from fruit_sorting.meshes import FRUIT_SHAPES, axis_extent  # noqa: E402

#: The two `[cage]` grammars: P108 predates P111's `off0/off/aper_min` fields.
CAGE_MODERN = re.compile(
    r"\[cage\] idx=(\d+) arm=(\w+) species=(\w+) dia=(\d+)mm approach=(\d+)t "
    r"clr=([-+0-9.]+)mm aper_min=([0-9.]+)mm close=(\d+)t "
    r"bat=([-+0-9.]+)mm bat_rel=([-+0-9.]+)mm off0=([-+0-9.]+)mm "
    r"off=([-+0-9.]+)mm pads=(\d)/4 f=\(([^)]*)\) F=([0-9.]+)N "
    r"aper=([0-9.]+)mm"
)
CAGE_OLD = re.compile(
    r"\[cage\] idx=(\d+) arm=(\w+) species=(\w+) dia=(\d+)mm approach=(\d+)t "
    r"clr=([-+0-9.]+)mm aper_min=([0-9.]+)mm close=(\d+)t "
    r"bat=([-+0-9.]+)mm bat_rel=([-+0-9.]+)mm pads=(\d)/4 f=\(([^)]*)\) "
    r"F=([0-9.]+)N aper=([0-9.]+)mm"
)
#: P131 adds `law= ext= deep= sep=`; older rows stop at `aper=`.
CAGE_NEW_TAIL = re.compile(r"aper=([0-9.]+)mm law=(\w+) ext=([0-9.]+)mm "
                           r"deep=([0-9.]+)mm sep=([0-9.]+)mm")
END_ROW = re.compile(r"approach\(cartesian\): [0-9.]+ cm, \d+ samples: steps=\d+.*?end=([0-9.]+) mm")
CARRY = re.compile(
    r"\[carry\] \w+ grasp_lift:.*?sep_end=([0-9.]+)mm dia=([0-9.]+) "
    r"sep_max=([0-9.]+)@.*?gap_start=([0-9.]+)mm"
)
ATTEMPT_START = re.compile(r"\[run\] attempt (\d+): picking")
ATTEMPT_END = re.compile(
    r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+) lift=([-+0-9.]+) m "
    r"force=([0-9.]+) N"
)

PAD_CAP = 4.90
#: "The fruit is between the pads": every seated row in the record reads
#: `off <= 10.1 mm`, every miss reads `off >= 92 mm` - 15 mm is the empty middle.
SEATED_MM = 15.0
#: P110's split (the `pads >= 3` gate and the `dia - 4` over-closure term) is
#: kept verbatim for continuity; the phase's corrected term is `R - 4`, where
#: `R` is the fruit's horizontal (radial) extent - the width the pads close on.


def pct(v, q: float) -> float:
    return float(np.percentile(np.asarray(v, dtype=float), q)) if len(v) else float("nan")


def mesh_extents(species: str, dia_mm: float) -> tuple[float, float]:
    """(radial, axial) extents of the class profile at that class diameter [mm]."""
    shape = FRUIT_SHAPES[species]
    d = float(dia_mm) / 1000.0
    radial = axis_extent(shape, d, np.array([1.0, 0.0, 0.0])) * 1000.0
    axial = axis_extent(shape, d, np.array([0.0, 0.0, 1.0])) * 1000.0
    return radial, axial


def parse(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    ends = [float(m.group(1)) for m in (END_ROW.search(l) for l in lines) if m]
    starts = [(i, int(m.group(1))) for i, l in enumerate(lines)
              if (m := ATTEMPT_START.search(l))]
    outcomes = {}
    for l in lines:
        m = ATTEMPT_END.search(l)
        if m:
            outcomes[int(m.group(1))] = (m.group(2) == "True", m.group(3) == "True")
    rows = []
    for i, line in enumerate(lines):
        m = CAGE_MODERN.search(line)
        old = False
        if not m:
            m = CAGE_OLD.search(line)
            old = True
        if not m:
            continue
        g = m.groups()
        species = g[2]
        dia = float(g[3])
        clr = float(g[5])
        if old:
            pads = int(g[10])
            F = float(g[12])
            aper = float(g[13])
            off0 = off = float("nan")
        else:
            off0 = float(g[10])
            off = float(g[11])
            pads = int(g[12])
            F = float(g[14])
            aper = float(g[15])
        law_mode = ext = deep = sep = None
        tail = CAGE_NEW_TAIL.search(line)
        if tail:
            law_mode = tail.group(2)
            ext = float(tail.group(3))
            deep = float(tail.group(4))
            sep = float(tail.group(5))
        # The attempt this row belongs to: the last `picking` line before it.
        attempt = starts[0][1] if starts else -1
        for j, n in starts:
            if j < i:
                attempt = n
        # The next carry leg after the close is this attempt's `grasp_lift`.
        carry = None
        for line2 in lines[i + 1:]:
            mc = CARRY.search(line2)
            if mc:
                carry = dict(sep_end=float(mc.group(1)), sep_max=float(mc.group(3)),
                             gap_start=float(mc.group(4)))
                break
        radial, axial = mesh_extents(species, dia)
        ramp = 0.97 * min(radial, axial)
        law = 0.98 * radial
        rows.append(
            dict(cell=path.name, attempt=attempt, species=species, dia=dia,
                 radial=radial, axial=axial, ramp=ramp, law=law,
                 aper=aper, pads=pads, F=F, off0=off0, off=off, clr=clr,
                 end=ends[len(rows)] if len(rows) < len(ends) else float("nan"),
                 law_mode=law_mode, ext=ext, deep=deep, sep=sep,
                 carry=carry, outcome=outcomes.get(attempt))
        )
    return rows


def classify(r: dict) -> tuple[str, str]:
    """(P110 class, P131 class).  P110 keeps its `pads >= 3` gate and `dia` term."""
    p110 = ""
    if r["pads"] >= 3:
        if not np.isfinite(r["end"]) or r["end"] > 15.0:
            p110 = "jam"
        elif r["aper"] < r["dia"] - 4.0 or r["F"] > 4 * PAD_CAP * 1.5:
            p110 = "crush"
        else:
            p110 = "clean"
    seated = np.isfinite(r["off"]) and r["off"] <= SEATED_MM
    if not np.isfinite(r["off"]):
        seated = None  # P108's grammar has no offset field
    # The aim is separated first: a ring that is not on the fruit also reads
    # `aper < dia - 4` and `end` large, but no closure law can fix it (P107).
    if seated is False:
        p131 = "miss"
    elif not np.isfinite(r["end"]) or r["end"] > 15.0:
        p131 = "jam"
    elif r["aper"] < r["radial"] - 4.0:
        p131 = "over"
    elif r["F"] > 4 * PAD_CAP * 1.5:
        p131 = "crush"
    elif r["pads"] >= 3:
        p131 = "clean"
    elif r["pads"] >= 1:
        p131 = "vblock"
    else:
        p131 = "no-contact"
    return p110, p131


def main() -> int:
    paths = [Path(p) for p in sys.argv[1:]] or [
        ROOT / "logs/p130/F5.log", ROOT / "logs/p130/F6.log",
        ROOT / "logs/p108/B_s5.log", ROOT / "logs/p108/B_s6.log",
    ]
    rows = []
    for p in paths:
        if not p.exists():
            print(f"{p}: missing")
            continue
        rs = parse(p)
        print(f"## {p}: {len(rs)} cage rows")
        rows.extend(rs)
    if not rows:
        return 1

    def freeze_off(r: dict) -> bool:
        """P130/P131 cells are the freeze-off family (`U`/`P`/`M` are P131)."""
        return not r["cell"].startswith("B")

    print("\n1. THE COMMAND AGAINST THE TWO-PHASE RAMP'S LOAD TARGET  (aper / ramp)")
    print("   ramp = 0.97 x min(radial, axial), the two-jaw close's `deep`.")
    print("   The shipped law (F/U) runs to the ramp; the variants route `deep`")
    print("   through the hand's own extent, so their ratio is the law/ramp split.")
    cells = []
    for r in rows:
        if r["cell"] not in cells:
            cells.append(r["cell"])
    for name in cells:
        rs = [r for r in rows if r["cell"] == name]
        ratio = [r["aper"] / r["ramp"] for r in rs]
        print(f"   {name:>11}: n={len(rs):2d}  aper/ramp p50={pct(ratio, 50):.3f} "
              f"p10={pct(ratio, 10):.3f} p90={pct(ratio, 90):.3f}")
    off = [r for r in rows if freeze_off(r) and r["cell"].startswith(("F", "U"))]
    ratios = [r["aper"] / r["ramp"] for r in off]
    near = sum(1 for x in ratios if 0.96 <= x <= 1.02)
    print(f"   shipped-law freeze-off rows (F/U): {near}/{len(ratios)} read aper/ramp "
          f"in [0.96, 1.02] (p50 {pct(ratios, 50):.3f})")

    print("\n2. THE CLASS DIAMETER IS NOT THE WIDTH FOR EVERY CLASS  (R / dia)")
    seen = {}
    for r in rows:
        seen.setdefault(r["species"], []).append(r)
    for group, tag in ((lambda r: freeze_off(r), "freeze off / P131 variants"),
                       (lambda r: r["cell"].startswith("B"), "freeze on ")):
        print(f"   [{tag}]")
        for sp in sorted({r["species"] for r in rows if group(r)}):
            rs = [r for r in rows if group(r) and r["species"] == sp]
            print(f"   {sp:11s} n={len(rs):2d}  "
                  f"R/dia p50={pct([r['radial'] / r['dia'] for r in rs], 50):.3f}  "
                  f"aper/R p50={pct([r['aper'] / r['radial'] for r in rs], 50):.3f}  "
                  f"aper/dia p50={pct([r['aper'] / r['dia'] for r in rs], 50):.3f}")

    print("\n3. P110'S SPLIT (pads >= 3, `dia` term) AND THE CORRECTED SPLIT")
    print("   P131: jam = end > 15 mm; miss = off > 15 mm (the fruit is not between "
          "the pads);")
    print("         over = seated and (aper < R - 4 mm or F > 29.4 N); "
          "clean = pads >= 3 and none of those.")
    for name in cells:
        rs = [r for r in rows if r["cell"] == name]
        p110 = [classify(r)[0] for r in rs]
        p131 = [classify(r)[1] for r in rs]
        ge3 = sum(1 for r in rs if r["pads"] >= 3)
        print(f"   {name:>11}: n={len(rs):2d} pads>=3={ge3:2d} | "
              f"P110 clean={p110.count('clean')} jam={p110.count('jam')} "
              f"crush={p110.count('crush')} | "
              f"P131 clean={p131.count('clean')} jam={p131.count('jam')} "
              f"over={p131.count('over')} vblock={p131.count('vblock')} "
              f"miss={p131.count('miss')} no-contact={p131.count('no-contact')}")
    rs = [r for r in rows if freeze_off(r)]
    p131 = [classify(r)[1] for r in rs]
    print(f"   freeze-off/variant pooled: clean={p131.count('clean')}/{len(rs)} "
          f"over={p131.count('over')} miss={p131.count('miss')} "
          f"vblock={p131.count('vblock')} jam={p131.count('jam')}")

    print("\n4. THE OVER-CLOSURE ROWS, ONE BY ONE  (freeze off; seated)")
    print("   off = payload offset from the ring axis at the close's end; "
          "F/pad = the delivered force")
    for r in rs:
        p110, p131 = classify(r)
        if p131 in ("over", "miss") or (p110 == "crush" and p131 != "crush"):
            out = r["outcome"]
            print(
                f"   att {r['attempt']:>2} {r['species']:11s} d={r['dia']:4.0f} "
                f"R={r['radial']:5.1f} A={r['axial']:5.1f} aper={r['aper']:5.1f} "
                f"aper/ramp={r['aper'] / r['ramp']:.3f} aper/R={r['aper'] / r['radial']:.3f} "
                f"off={r['off']:6.1f} pads={r['pads']} F/pad={r['F'] / max(r['pads'], 1):5.2f} "
                f"{p131:6s} (P110 {p110 or '-':5s}) placed={out[1] if out else '?'}"
            )

    print("\n5. THE DRIVE TEST: does the measured span fall below the command?")
    print("   At the close the command *is* the target; a position drive can only be")
    print("   pushed back by the payload, never pulled through it.  The measured span")
    print("   at the carry leg's end (`sep_end`) is the force servo's chase, so the")
    print("   close's own measured span (`sep=`, P131 cells only) is the honest read.")
    for name in ("F5.log", "F6.log", "B_s5.log", "B_s6.log"):
        rs = [r for r in rows if r["cell"] == name and r["carry"]]
        if not rs:
            continue
        delta = [r["carry"]["sep_end"] - r["aper"] for r in rs]
        print(f"   {name:>9}: sep_end - aper  p10={pct(delta, 10):+6.1f} "
              f"p50={pct(delta, 50):+6.1f} p90={pct(delta, 90):+6.1f} mm  "
              f"(negative = the pads reached inside the command)")
    new = [r for r in rows if r["sep"] is not None]
    if new:
        d = [r["sep"] - r["aper"] for r in new]
        print(f"   P131 cells (sep= measured at the close's flush): n={len(d)} "
              f"p10={pct(d, 10):+6.2f} p50={pct(d, 50):+6.2f} p90={pct(d, 90):+6.2f} mm")
    else:
        print("   P131 cells (sep= at the close's flush): not in the record yet")

    print("\n6. VERDICT")
    freeze_off_rows = [r for r in rows if freeze_off(r)]
    over = [r for r in freeze_off_rows if classify(r)[1] == "over"]
    missed = [r for r in freeze_off_rows if classify(r)[1] == "miss"]
    print(f"   freeze-off/variants: {len(over)}/{len(freeze_off_rows)} seated "
          f"over-closures, {len(missed)}/{len(freeze_off_rows)} misses (the aim).")
    if over:
        print(f"   the over-closure rows read aper/ramp p50 "
              f"{pct([r['aper'] / r['ramp'] for r in over], 50):.3f} and aper/R p50 "
              f"{pct([r['aper'] / r['radial'] for r in over], 50):.3f}: the command "
              f"reached the two-jaw load target, which is below the ring's width.")
        kinds = {}
        for r in over:
            kinds[r["species"]] = kinds.get(r["species"], 0) + 1
        print(f"   by species: {kinds}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
