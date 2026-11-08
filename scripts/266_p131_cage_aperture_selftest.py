#!/usr/bin/env python3
"""P131 selftest: the four-pad ring's **aperture law** (`FRUIT_CAGE_APERTURE`).

    python3 scripts/266_p131_cage_aperture_selftest.py

No simulator (the `247`/`253`/`257`/`258` stub-the-imports pattern): the real
`cage_hand` module and the real `CageHand.aperture_extent` run, and the `tasks`
wiring is pinned from the source.

Why each item matters.

1. **The shipped path is bit for bit.**  `FRUIT_CAGE_APERTURE` unset resolves
   `shipped`; the four-pad branch then returns exactly the expression P107
   shipped (`max over the hand's x/y of axis_extent`), and the cage3 law is
   unchanged under every mode.  The acceptance's 421-line replay depends on it.
2. **The two variants are the laws the phase registers.**  `max_extent` is the
   mesh's largest axis (the height on a pear, the width on an apple);
   `pad_axes` is the max over the ring's **own** four pad axes in the cage base
   frame - equal to the shipped law for a top-down hand, and different for a
   tilted one (the case P112's law hook exists for).
3. **The law is not free-standing.**  P130 measured that the *two-jaw* dynamic
   close's load target (`0.97 x min(radial, axial)`) is what the freeze-off ring
   actually runs to; so the task must route `deep` through the hand's stated
   extent **only** for a radial hand with the variant armed, and drop the
   two-jaw 2.5 mm interference floor for that hand.  Unset keeps the shipped
   expression exactly.
4. **The probe can tell the two hypotheses apart.**  The `[cage]` row carries
   `law= ext= deep= sep=`, where `sep` is the measured pad span at the flush:
   `sep == aper` is the law, `sep < aper` is a drive overshoot.

Exit 0 on pass, 1 on the first failure.  Run by `scripts/selfcheck.sh`.
"""

from __future__ import annotations

import ast
import hashlib
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# --- stub pxr / isaacsim just enough to import fruit_sorting.cage_hand ------ #
for name in (
    "pxr",
    "pxr.Gf",
    "pxr.Sdf",
    "pxr.Usd",
    "pxr.UsdGeom",
    "pxr.UsdPhysics",
    "pxr.UsdShade",
    "isaacsim",
    "isaacsim.core",
    "isaacsim.core.experimental",
    "isaacsim.core.experimental.prims",
):
    mod = types.ModuleType(name)
    mod.__path__ = []
    sys.modules.setdefault(name, mod)
sys.modules["isaacsim.core.experimental.prims"].RigidPrim = types.SimpleNamespace

import numpy as np  # noqa: E402

FAILED = []


def check(ok: bool, text: str) -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {text}")
    if not ok:
        FAILED.append(text)


def discharge() -> None:
    os.environ.pop("FRUIT_CAGE_APERTURE", None)


def main() -> int:
    discharge()
    from fruit_sorting import cage_hand as ch
    from fruit_sorting.meshes import FRUIT_SHAPES, axis_extent

    print("1. the resolver: unset is the shipped law, the two variants parse, junk raises")
    check(ch.APERTURE_MODES == ("shipped", "max_extent", "pad_axes"),
          f"`APERTURE_MODES` = {ch.APERTURE_MODES}")
    check(ch.aperture_mode() == "shipped", "unset `FRUIT_CAGE_APERTURE` resolves `shipped`")
    for mode in ch.APERTURE_MODES:
        os.environ["FRUIT_CAGE_APERTURE"] = mode
        check(ch.aperture_mode() == mode, f"explicit `{mode}` resolves itself")
    os.environ["FRUIT_CAGE_APERTURE"] = "widest"
    try:
        ch.aperture_mode()
        check(False, "an unknown mode raises")
    except SystemExit:
        check(True, "an unknown mode raises")
    discharge()

    print("\n2. `shipped` is the P107 expression bit for bit; the variants are the laws")
    rot, rq = np.eye(3), np.eye(3)
    h4 = types.SimpleNamespace(thetas=ch.pad_thetas("cage4"))
    h3 = types.SimpleNamespace(thetas=ch.pad_thetas("cage3"))
    d = 0.064
    for species in ("apple", "pear", "tomato", "strawberry", "kiwi"):
        shape = FRUIT_SHAPES[species]
        shipped = ch.CageHand.aperture_extent(h4, shape, d, rot, rq)
        old = 0.0
        for axis in (0, 1):
            old = max(old, float(axis_extent(shape, d, rq.T @ rot[:, axis])))
        check(abs(shipped - old) < 1e-12,
              f"{species:11s} unset == the shipped widest-horizontal loop "
              f"({shipped * 1000:.2f} mm)")
        os.environ["FRUIT_CAGE_APERTURE"] = "shipped"
        check(abs(ch.CageHand.aperture_extent(h4, shape, d, rot, rq) - old) < 1e-12,
              f"{species:11s} explicit `shipped` is the same expression")
        os.environ["FRUIT_CAGE_APERTURE"] = "max_extent"
        mx = ch.CageHand.aperture_extent(h4, shape, d, rot, rq)
        want = max(
            float(axis_extent(shape, d, np.array([1.0, 0.0, 0.0]))),
            float(axis_extent(shape, d, np.array([0.0, 0.0, 1.0]))),
        )
        check(abs(mx - want) < 1e-12,
              f"{species:11s} `max_extent` = max(radial, axial) ({mx * 1000:.2f} mm)")
        os.environ["FRUIT_CAGE_APERTURE"] = "pad_axes"
        pa = ch.CageHand.aperture_extent(h4, shape, d, rot, rq)
        check(abs(pa - old) < 1e-12,
              f"{species:11s} `pad_axes` == the shipped axes for a top-down hand")
        discharge()

    # A tilted hand: the base frame is the TCP rotated by the tool correction,
    # so the pads' own axes are not the hand x/y.  The correction below rotates
    # local +Z onto the hand's x; the law must see the rotated axes.
    tilted = np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]])
    corr = ch._quat_from_matrix(tilted)
    hand = types.SimpleNamespace(thetas=ch.pad_thetas("cage4"), _correction=corr)
    shape = FRUIT_SHAPES["pear"]
    os.environ["FRUIT_CAGE_APERTURE"] = "pad_axes"
    pa = ch.CageHand.aperture_extent(hand, shape, d, rot, rq)
    base = rot @ tilted
    want = max(float(axis_extent(shape, d, rq.T @ base[:, axis])) for axis in (0, 1))
    shipped = ch.CageHand.aperture_extent(
        types.SimpleNamespace(thetas=ch.pad_thetas("cage4")), shape, d, rot, rq
    )
    check(abs(pa - want) < 1e-12,
          f"a tilted hand reads the pads' own base axes ({pa * 1000:.2f} mm)")
    check(abs(pa - shipped) > 1e-6,
          f"and that is not the TCP axes ({pa * 1000:.2f} != {shipped * 1000:.2f} mm)")
    discharge()

    print("\n3. the three-pad law is untouched by every mode")
    shape = FRUIT_SHAPES["kiwi"]
    ext3 = [float(axis_extent(shape, d, np.array([np.cos(np.deg2rad(t)),
                                                  np.sin(np.deg2rad(t)), 0.0])))
            for t in ch.pad_thetas("cage3")]
    for mode in ch.APERTURE_MODES:
        os.environ["FRUIT_CAGE_APERTURE"] = mode
        got = ch.CageHand.aperture_extent(h3, shape, d, rot, rq)
        check(abs(got - min(ext3)) < 1e-12,
              f"cage3 `{mode}` is still the min over its own three axes")
    discharge()

    print("\n4. the task wiring: the load target is the law only for an armed radial hand")
    src = (ROOT / "src" / "fruit_sorting" / "tasks.py").read_text()
    check(src.count("aperture_mode()") == 2,
          "two `aperture_mode()` reads in `tasks.py` (the close route + the probe row)")
    check(
        'deep = min_extent * float(os.environ.get("FRUIT_DYNAMIC_CLOSE_DEEP", "0.97"))'
        in src,
        "the shipped `deep` expression is still there, unmodified",
    )
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_grasp_carry_place_impl")
    body = ast.get_source_segment(src, fn) or ""
    check("cage_law_armed" in body, "the close has one `cage_law_armed` resolver")
    check(
        body.index("cage_law_armed = (")
        < body.index("if cage_law_armed:\n                    deep = float(pinch_width)")
        < body.index("min_interference = 0.0"),
        "the law raises `deep`, then drops the two-jaw interference floor",
    )
    check('os.environ.get("FRUIT_GRIPPER_SQUEEZE", "0.98")' in body,
          "the armed load target is the hand's extent at the shipped squeeze")
    check(
        body.count("if cage_law_armed:") == 2,
        "exactly two branches depend on the resolver (deep and the floor)",
    )
    check(
        'min_extent * float(os.environ.get("FRUIT_DYNAMIC_CLOSE_DEEP"' in body,
        "and the unset path keeps the two-jaw `min_extent` target",
    )
    flush = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "_cage_probe_flush")
    fb = ast.get_source_segment(src, flush) or ""
    for field in ("law={", "ext={", "deep={", "sep={"):
        check(field in fb, f"the `[cage]` row carries `{field[:-2]}`")
    check(".separation()" in fb, "`sep` is the measured pad span (not the command)")
    cage_src = (ROOT / "src" / "fruit_sorting" / "cage_hand.py").read_text()
    check("aperture law={aperture_mode()}" in cage_src,
          "the build row names the resolved law")

    print("\n5. the phase's record")
    prereg = ROOT / "logs" / "p131" / "PREREG.md"
    check(prereg.exists(), "the PREREG exists")
    if prereg.exists():
        md5 = hashlib.md5(prereg.read_bytes()).hexdigest()
        pin = (ROOT / "logs" / "p131" / "PREREG.md5")
        if pin.exists():
            pinned = pin.read_text().split()[0]
            check(md5 == pinned, f"the PREREG is at its pinned md5 ({pinned[:8]})")
        else:
            check(False, "the PREREG pin file exists")
    check((ROOT / "logs" / "p131" / "census.txt").exists(),
          "the census exists (the phase's offline decision)")

    print()
    if FAILED:
        print(f"FAIL: {len(FAILED)} check(s)")
        return 1
    print("PASS: P131 cage aperture law (the modes, the bits, the route)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
