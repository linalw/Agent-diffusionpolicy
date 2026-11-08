#!/usr/bin/env python3
"""P132 selftest: the serrated pad face's **unset path** and its geometry.

    python3 scripts/267_p132_serr_selftest.py

No simulator.  The fixture's pure geometry functions are lifted out of
`logs/p132/fixture.py` with `ast` (the module top-level needs Isaac, so only its
constants and pure functions are compiled), and the shipped hand is pinned from
the source: **no `serr` token exists in `src/`** and `FRUIT_FINGER_FACE` still
defaults to `flat`, so the phase's negative built nothing on the robot.

Why each item matters.

1. **The shipped path is bit for bit.**  `FRUIT_FINGER_FACE` unset resolves
   `flat`, and `_add_contact_faces` is reached only for a non-`flat` value.  The
   acceptance's 421-line replay depends on it; the phase adds no face.
2. **The fixture's default is the four faces the report read.**  A re-run with no
   env must produce `flat,serr,serr45,lip20`, or the table's provenance is gone.
3. **The tooth is the brief's.**  5 crests, 1.0 mm high, 8 mm pitch, 60 deg
   flanks (`serr`) and 45 deg (`serr45`); the crests sit on the fruit's **widest
   row**, not the pad's face centre (the pear's widest is 8.0 mm below the pose
   origin, the strawberry's 4.5 mm above it).
4. **The lip is fixture-only and only extends downward.**  `lip20`'s plate top is
   byte-equal to the shipped top; its distal plane is exactly 9.5 mm lower.  The
   hand's distal plane (80.5 mm) is the belt constraint and nothing buildable
   moves it.
5. **The facet frame is the corrected one.**  `cross(tan, nf)` (right-handed) is
   in the source; P117's `(tan, nf, w_axis)` left-handed frame rotated one pad's
   box 90 deg (a 62 mm thickness) and is what the phase's METHOD section 2
   records.

Exit 0 on pass, 1 on the first failure.  Run by `scripts/selfcheck.sh`.
"""

from __future__ import annotations

import ast
import math
import os
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

for name in (
    "pxr",
    "pxr.Gf",
    "pxr.Sdf",
    "pxr.Usd",
    "pxr.UsdGeom",
    "pxr.UsdPhysics",
    "pxr.UsdShade",
):
    mod = types.ModuleType(name)
    mod.__path__ = []
    sys.modules.setdefault(name, mod)

FAILED = []


def check(ok: bool, text: str) -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {text}")
    if not ok:
        FAILED.append(text)


def fixture_namespace() -> dict:
    """Compile the fixture's constants and pure functions, skip its app/imports."""
    path = ROOT / "logs/p132/fixture.py"
    tree = ast.parse(path.read_text())
    body = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            # `raise_fd_limit()` and `simulation_app = SimulationApp(...)`
            continue
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
            # the `if __name__ == "__main__"` block
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = getattr(node, "targets", [getattr(node, "target", None)])
            names = {t.id for t in targets if isinstance(t, ast.Name)}
            if "simulation_app" in names:
                continue
        body.append(node)
    module = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(module)
    ns: dict = {"__name__": "p132_fixture_pure", "__file__": str(path), "math": math, "os": os}
    exec(compile(module, str(path), "exec"), ns)  # noqa: S102 - pinned local source
    return ns


def main() -> int:
    for key in list(os.environ):
        if key.startswith("P132_"):
            os.environ.pop(key)

    from fruit_sorting.meshes import FRUIT_SHAPES

    ns = fixture_namespace()
    print("1. the shipped hand is untouched (the shape's unset path)")
    scene_src = (ROOT / "src/fruit_sorting/scene.py").read_text()
    check('os.environ.get("FRUIT_FINGER_FACE", "flat")' in scene_src,
          "`FRUIT_FINGER_FACE` still defaults to `flat` in scene.py")
    check('face_shape not in ("", "flat", "none", "0")' in scene_src,
          "`_add_contact_faces` is still gated on a non-flat face")
    hits = []
    for path in sorted((ROOT / "src/fruit_sorting").glob("*.py")):
        if re.search(r"\bserr", path.read_text(), re.IGNORECASE):
            hits.append(path.name)
    check(not hits, f"no `serr` token in src/fruit_sorting/*.py (hits: {hits})")

    print("2. the fixture's default is the four registered faces")
    check(tuple(ns["PROFILES"]) == ("flat", "serr", "serr45", "lip20"),
          f"default profiles = {tuple(ns['PROFILES'])}")
    check(ns["SERR_TEETH"] == 5, f"SERR_TEETH = {ns['SERR_TEETH']}")
    check(abs(ns["SERR_PITCH"] - 0.008) < 1e-12, f"SERR_PITCH = {ns['SERR_PITCH'] * 1000:.1f} mm")
    check(abs(ns["SERR_HEIGHT"] - 0.001) < 1e-12, f"SERR_HEIGHT = {ns['SERR_HEIGHT'] * 1000:.1f} mm")
    check(abs(ns["LIP_EXTRA"] - 0.0095) < 1e-12, f"LIP_EXTRA = {ns['LIP_EXTRA'] * 1000:.1f} mm")
    check(ns["WALK_ROLL"] is False, "`P132_WALK_ROLL` defaults off")

    print("3. the tooth geometry (the brief's, at the wallet)")
    tooth = ns["tooth_polyline"]
    run60 = ns["SERR_HEIGHT"] / math.tan(math.radians(60.0))
    run45 = ns["SERR_HEIGHT"] / math.tan(math.radians(45.0))
    check(abs(run60 - 0.0005774) < 1e-6, f"60 deg flank run = {run60 * 1000:.4f} mm")
    check(abs(run45 - 0.001) < 1e-12, f"45 deg flank run = {run45 * 1000:.4f} mm")
    u0 = -0.0399
    poly = tooth(0.04245, u0, 0.008, 0.001, 60.0, 5)
    crests = [(u, d) for (u, d) in poly if abs(d + 0.001) < 1e-12]
    check(len(crests) == 5, f"5 crests in the authored polyline ({len(crests)})")
    check(all(abs(d + 0.001) < 1e-12 for _, d in crests), "every crest is 1.0 mm toward the payload")
    pitch = [crests[i + 1][0] - crests[i][0] for i in range(len(crests) - 1)]
    check(all(abs(p - 0.008) < 1e-9 for p in pitch), f"crest pitch = {[round(p * 1000, 3) for p in pitch]} mm")
    check(all(d >= -0.001 - 1e-12 for _, d in poly), "no tooth depth outside [-1, 0] mm")
    mono = all(poly[i + 1][0] > poly[i][0] for i in range(len(poly) - 1))
    check(mono, "the polyline is monotone in u")
    poly45 = tooth(0.04245, u0, 0.008, 0.001, 45.0, 5)
    c45 = [(u, d) for (u, d) in poly45 if abs(d + 0.001) < 1e-12]
    check(len(c45) == 5, "serr45 has the same 5 crests")

    print("4. the tooth sits on the fruit's widest row, not the face centre")
    pear = FRUIT_SHAPES["pear"]
    straw = FRUIT_SHAPES["strawberry"]
    z_pear = ns["widest_local_z"](pear, 0.0606)
    z_straw = ns["widest_local_z"](straw, 0.0372)
    check(z_pear < -0.006, f"pear widest row {z_pear * 1000:+.1f} mm below the pose origin")
    check(z_straw > 0.002, f"strawberry widest row {z_straw * 1000:+.1f} mm above it")
    # the station's u0 is (fruit_z + widest) - (JAW_Z - pad_z_centre)
    jaw = 1.30
    standoff = 0.070
    for shape, dia, label in ((pear, 0.0606, "pear"), (straw, 0.0372, "strawberry")):
        _plate, pad_z, _extra = ns["plate_geometry"]("serr")
        u_w = (jaw - standoff) + ns["widest_local_z"](shape, dia) - (jaw - pad_z)
        poly_w = ns["depth_polyline"]("serr", dia / 2.0, _plate / 2.0, u_w)
        travel, ustar = ns["contact_travel"](poly_w, dia / 2.0, u_w)
        check(abs(ustar - u_w) < 0.004,
              f"{label}: contact at u*={ustar * 1000:+.1f} mm vs the widest {u_w * 1000:+.1f} mm")

    print("5. the lip is fixture-only and only extends downward")
    len_f, z_f, x_f = ns["plate_geometry"]("flat")
    len_l, z_l, x_l = ns["plate_geometry"]("lip20")
    check(abs(len_f - 0.0849) < 1e-12, f"flat plate {len_f * 1000:.1f} mm")
    check(abs(len_l - 0.0944) < 1e-12, f"lip20 plate {len_l * 1000:.1f} mm")
    top_f = z_f - len_f / 2.0
    top_l = z_l - len_l / 2.0
    check(abs(top_f - top_l) < 1e-12, f"the plate top is unchanged ({top_l * 1000:+.2f} mm)")
    check(abs((z_l + len_l / 2.0) - (z_f + len_f / 2.0) - 0.0095) < 1e-12,
          "the distal plane moves down by exactly 9.5 mm")

    print("6. the fixture's facet frame is the corrected right-handed one")
    fix_src = (ROOT / "logs/p132/fixture.py").read_text()
    check("w_seg = np.cross(tan, nf)" in fix_src, "the per-segment frame is `cross(tan, nf)`")
    check("_quat_from_columns(tan, nf, w_seg)" in fix_src, "the box is oriented by that frame")
    check("PAD_Z_CENTRE" not in fix_src, "the old flat `PAD_Z_CENTRE` is gone")

    print()
    if FAILED:
        print(f"FAIL: {len(FAILED)} check(s) failed")
        return 1
    print("PASS: the serrated face's unset path and geometry are pinned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
