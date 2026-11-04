#!/usr/bin/env python3
"""P112 selftest: the **three-jaw** ring (`cage3`) and its aperture law.

    python3 scripts/258_p112_cage3_selftest.py

No simulator (the `247`/`253`/`257` stub-the-imports pattern): the real
`cage_hand` module and the real `CageHand.aperture_extent` run, and the `tasks`
wiring is pinned from the source.

Why each item matters.

1. **A third kind is a kind, not a fork.**  `cage3` has to share the authoring,
   the closure, the instrument and the probe with `cage4` - the phase's whole
   claim is a *contact count*, so a second code path would confound it.  The
   leg pins the pad geometry (3 x 120 deg, a 20 mm plate) and that the four-pad
   geometry is untouched (bit-for-bit: 4 x 90 deg, 26 mm).
2. **The aperture law is the hand's, and it is the phase's design change.**  The
   four-pad ring closes on the payload's **widest** horizontal extent
   (`pinch_width`'s own cage branch), which is why its opposed pair can never
   load (P111 measured the V-block).  A three-pad ring closes on the
   **narrowest of its own three pad axes** - the only law that loads all three on
   a non-round fruit - and the leg executes both against a real fruit profile.
3. **The shipped path is inert.**  `FRUIT_GRIPPER_KIND` unset stays `openarm`,
   `cage_enabled()` is False, and `pinch_width` returns the shipped expression
   when the hand states no law (the `getattr` is None for `OpenArmHand`).
4. The four call sites that mean "this hand is a radial ring" read
   `CAGE_KINDS`, not a single kind; one that still compared `== CAGE_KIND` would
   silently skip the three-jaw's probe, its close window and its hand
   construction.

Exit 0 on pass, 1 on the first failure.  Run by `scripts/selfcheck.sh`.
"""

from __future__ import annotations

import ast
import hashlib
import math
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# --- stub pxr / isaacsim just enough to import fruit_sorting.cage_hand ------ #
for name in (
    "pxr",
    "isaacsim",
    "isaacsim.core",
    "isaacsim.core.experimental",
    "isaacsim.core.experimental.prims",
):
    mod = types.ModuleType(name)
    mod.__path__ = []
    sys.modules.setdefault(name, mod)
for sub in ("Gf", "Sdf", "Usd", "UsdGeom", "UsdPhysics", "UsdShade"):
    mod = types.ModuleType(f"pxr.{sub}")
    mod.__path__ = []
    sys.modules.setdefault(f"pxr.{sub}", mod)
    setattr(sys.modules["pxr"], sub, mod)
sys.modules["pxr"].__path__ = []
prim = types.SimpleNamespace
sys.modules["isaacsim.core.experimental.prims"].RigidPrim = prim

import numpy as np  # noqa: E402

FAILED = []


def check(ok: bool, text: str) -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {text}")
    if not ok:
        FAILED.append(text)


def main() -> int:
    os.environ.pop("FRUIT_GRIPPER_KIND", None)
    from fruit_sorting import cage_hand as ch
    from fruit_sorting.meshes import FRUIT_SHAPES

    print("1. two kinds, one module: the geometry of each, and the default off")
    check(ch.CAGE_KINDS == ("cage4", "cage3"), f"`CAGE_KINDS` is (cage4, cage3) ({ch.CAGE_KINDS})")
    check(ch.hand_kind() == "openarm", "unset `FRUIT_GRIPPER_KIND` resolves `openarm`")
    check(not ch.cage_enabled(), "and `cage_enabled()` is False (the shipped path)")
    check(ch.pad_thetas("cage3") == (0.0, 120.0, 240.0),
          "cage3's pads are at 3 x 120 deg")
    check(ch.pad_thetas("cage4") == (0.0, 90.0, 180.0, 270.0),
          "cage4's pads are unchanged at 4 x 90 deg")
    check(abs(ch.pad_width_of("cage3") - 0.020) < 1e-12,
          f"cage3's plate is 20.0 mm wide ({ch.pad_width_of('cage3') * 1000:.1f})")
    check(abs(ch.pad_width_of("cage4") - ch.PAD_WIDTH) < 1e-12,
          "cage4's plate width is the module's own constant (bit-for-bit)")
    legal = ch.MIN_FACE_R * math.sqrt(3.0)
    check(ch.pad_width_of("cage3") <= legal,
          f"20.0 mm <= the 120 deg neighbour bound at the closed aperture "
          f"({legal * 1000:.1f} mm) -> the plates cannot collide")
    check(abs(ch.CAGE_PLATE_LENGTH - 0.060) < 1e-12,
          "the plate length stays the measured 60.0 mm (the palm bound, P107)")
    check(abs(ch.GRASP_STANDOFF - (ch.DISTAL_Z - ch.LIP)) < 1e-12,
          "the tool offset is still DISTAL_Z - LIP = 70.0 mm")

    print("\n2. the aperture law: widest for four pads, the narrowest OWN axis for three")
    rot, rq = np.eye(3), np.eye(3)
    shape = FRUIT_SHAPES["kiwi"]
    d = 0.06
    h4 = types.SimpleNamespace(thetas=ch.pad_thetas("cage4"))
    h3 = types.SimpleNamespace(thetas=ch.pad_thetas("cage3"))
    w4 = ch.CageHand.aperture_extent(h4, shape, d, rot, rq)
    w3 = ch.CageHand.aperture_extent(h3, shape, d, rot, rq)
    from fruit_sorting.meshes import axis_extent
    widest = max(axis_extent(shape, d, np.array([1.0, 0.0, 0.0])),
                 axis_extent(shape, d, np.array([0.0, 1.0, 0.0])))
    check(abs(w4 - widest) < 1e-9,
          f"cage4 returns the widest horizontal extent ({w4 * 1000:.2f} mm)")
    ext3 = [axis_extent(shape, d, np.array([math.cos(math.radians(t)),
                                            math.sin(math.radians(t)), 0.0]))
            for t in ch.pad_thetas("cage3")]
    check(abs(w3 - min(ext3)) < 1e-9,
          f"cage3 returns the min over its own three pad axes ({w3 * 1000:.2f} mm)")
    check(w3 <= w4 + 1e-12,
          f"and that is <= the widest ({w3 * 1000:.2f} <= {w4 * 1000:.2f} mm): the ring "
          f"can load all three")
    # The case the law exists for: the fruit on the belt with its **own long
    # axis horizontal**, pointing at pad 0 (a surface of revolution's horizontal
    # extent is a *circle* only while the fruit stands upright - measured
    # `anisotropy` 1.000 in the fixture's first smoke, `METHOD.md` section 2).
    q = np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]])
    ext_w = [axis_extent(shape, d, q.T @ np.array([math.cos(math.radians(t)),
                                                   math.sin(math.radians(t)), 0.0]))
             for t in ch.pad_thetas("cage3")]
    check(max(ext_w) / min(ext_w) > 1.02,
          f"laid on its side the kiwi reads {min(ext_w) * 1000:.1f}-"
          f"{max(ext_w) * 1000:.1f} mm across three axes (anisotropic)")
    w3s = ch.CageHand.aperture_extent(h3, shape, d, np.eye(3), q)
    w4s = ch.CageHand.aperture_extent(h4, shape, d, np.eye(3), q)
    check(abs(w3s - min(ext_w)) < 1e-9,
          f"cage3 takes the narrow axis ({w3s * 1000:.2f} mm)")
    check(w3s < w4s - 1e-6,
          f"and it is *below* cage4's widest ({w3s * 1000:.2f} < {w4s * 1000:.2f} mm): "
          f"only the three-pad ring can close onto all its pads")

    print("\n3. the wiring: one law hook, and the ring predicate is a *set*")
    src = (ROOT / "src" / "fruit_sorting" / "tasks.py").read_text()
    check(src.count('getattr(hand, "aperture_extent"') == 1,
          "exactly one `aperture_extent` hook in `tasks.py`")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "pinch_width")
    body = ast.get_source_segment(src, fn) or ""
    check(body.index("aperture_extent") < body.index("widest = 0.0"),
          "the hook precedes the shipped widest-extent loop (it can only override)")
    check("RIGID_TOOL_HANDS = (\"openarm\", *CAGE_KINDS)" in src,
          "`RIGID_TOOL_HANDS` is built from `CAGE_KINDS`")
    check(src.count("in CAGE_KINDS") >= 4,
          f"every ring predicate reads `CAGE_KINDS` ({src.count('in CAGE_KINDS')} sites)")
    check("== CAGE_KIND)" not in src and "!= CAGE_KIND" not in src,
          "no site still compares against the single `CAGE_KIND`")
    cage_src = (ROOT / "src" / "fruit_sorting" / "cage_hand.py").read_text()
    check("if len(pts) != 4:" in cage_src,
          "`apertures()` has the three-pad branch (the inscribed diameter)")

    print("\n4. the probe and the phase's own record")
    md5 = hashlib.md5((ROOT / "logs" / "p112" / "PREREG.md").read_bytes()).hexdigest()
    pinned = (ROOT / "logs" / "p112" / "PREREG.md5").read_text().split()[0]
    check(md5 == pinned, f"the PREREG is at its pinned md5 ({pinned[:8]})")
    fix = ROOT / "logs" / "p112" / "fixture_report.txt"
    check(fix.exists(), "the fixture's report exists (the phase's decisive test)")

    print()
    if FAILED:
        print(f"FAIL: {len(FAILED)} check(s)")
        return 1
    print("PASS: P112 three-jaw ring (the kind, the aperture law, the wiring)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
