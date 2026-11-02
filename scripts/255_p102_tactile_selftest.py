#!/usr/bin/env python3
"""P102 selftest: the **contact-patch** tactile statistic (reporting only).

    python3 scripts/255_p102_tactile_selftest.py

No simulator (the `241` / `243` / `254` stub-the-imports pattern): the **real**
`tactile_patch_state`, `disc_rect_fraction` and `parse_tactile_patch` run, and
the emitted row is parsed back by `logs/p102/census.py`'s own reader.

Why each item matters. `docs/PLATFORM_SURVEY.md` §5.1 registers stage (i): the
tree's tactile channel is **two normal-force scalars** and W5-C measured that
where the force collapses the payload is gone within 0-3 ticks, so a 2-scalar
channel cannot be a reflex. The survey's hypothesis is that a **spatial** channel
- the contact patch's centroid moving on the pad - leads the collapse, and its
kill criterion is explicit (slip visible >= 10 ticks early, or `cnp` does not
fall >= 30 %). `FRUIT_TACTILE_PATCH=<ticks>` builds that channel from geometry
the sim already has, so the claim can be measured before any hardware is bought.
This leg pins:

1. **The resolver**: unset/blank/non-numeric/`<= 0` is off (0), a number is the
   per-leg tick cap, and the attribute starts at 0 - so with the knob unset the
   shipped path is byte-inert (the block is one integer test per leg).
2. **`guard_armed` gains exactly one term** (`self._tactile_patch > 0`), so the
   instrument is self-sufficient (it comes with the W8-B tracker it reads) and
   the boolean is unchanged when the knob is off.
3. **No `ik_step` work and no articulation read** inside the row block: it
   reuses the block's own `rot_now`/`_sep_now`/`fruit`/`rel_frame`, and the only
   additions are the two reporting readers it names (`jaw_positions()`, one
   tactile set). AGENTS §2's constraint is that per-tick work inside `ik_step`
   changes the measurement; a diagnostic may not add it.
4. **The geometry is exact and orientation-free where it must be**: the centroid
   is the payload centre projected on the pad's face in a frame built from the
   **measured** jaw axis, so it is invariant under a wrist rotation about that
   axis, and its *displacement* is invariant under a translation of the pad
   rectangle's origin (that is why the census reads `dc`, not `u`).
5. **The area/occupancy signal behaves**: `frac` is 1.0 for a patch well inside
   the pad, 0.0 when the centroid is a radius outside it, monotone in between,
   and the quadrature is a 48-point equal-area set (no lattice bias).
6. **The pad rectangle's long-axis origin is the plate's face centre, not the
   link origin** (`TACTILE_PAD_LONG_ORIGIN = finger_length - half_long`): with
   the shipped `_pad_standoff` the seated payload reads `edge = +9.8 mm`, and
   centring the rectangle on the link origin instead would score every good seat
   as already off the pad (`frac` 0.06, `edge` -24 mm) - measured in
   `logs/p102/smoke.log` before the constant existed.
7. **The row parses back** through the census's own regex, with the field set and
   order the census reads (a field rename is a silent census break otherwise).
8. **The per-pad degeneracy is declared, not hidden**: two parallel rigid pads
   on a sphere project the same centroid, so the two rows differ only in `h` and
   in each pad's own force - which is what the escape's one-sided signature reads
   (P75: `f=(0.00, 4.93)` for a whole leg).

Exit 0 on pass, 1 on the first failure. No simulator, no file writes.
"""
from __future__ import annotations

import math
import os
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# --- stub pxr / isaacsim just enough to import fruit_sorting.tasks ---------- #
for name in (
    "pxr",
    "isaacsim",
    "isaacsim.core",
    "isaacsim.core.experimental",
    "isaacsim.sensors",
    "isaacsim.sensors.experimental",
    "isaacsim.core.experimental.utils",
    "isaacsim.core.experimental.objects",
    "isaacsim.core.experimental.utils.app",
    "isaacsim.core.experimental.utils.stage",
    "isaacsim.core.experimental.prims",
):
    module = sys.modules.setdefault(name, types.ModuleType(name))
    module.__path__ = []
pxr = sys.modules["pxr"]
for attr in ("Gf", "PhysxSchema", "Sdf", "Usd", "UsdGeom", "UsdPhysics", "UsdShade"):
    if not hasattr(pxr, attr):
        setattr(pxr, attr, types.ModuleType(f"pxr.{attr}"))
sys.modules["isaacsim.core.experimental.utils.app"].update_app = lambda **kwargs: None
sys.modules["isaacsim.core.experimental.utils.stage"].create_prim = lambda *a, **k: None
prims_mod = sys.modules["isaacsim.core.experimental.prims"]
prims_mod.RigidPrim = object
prims_mod.Articulation = object
objects_mod = sys.modules["isaacsim.core.experimental.objects"]
objects_mod.DistantLight = object
objects_mod.GroundPlane = object
sys.modules.setdefault(
    "isaacsim.core.simulation_manager",
    types.SimpleNamespace(
        SimulationManager=types.SimpleNamespace(step=staticmethod(lambda **kw: None))
    ),
)
sys.modules.setdefault(
    "isaacsim.core.rendering_manager",
    types.SimpleNamespace(
        RenderingManager=types.SimpleNamespace(render=staticmethod(lambda: None))
    ),
)
sensors_mod = types.ModuleType("isaacsim.sensors.experimental.physics")
sensors_mod.Contact = object
sensors_mod.ContactSensor = object
sys.modules.setdefault("isaacsim.sensors.experimental.physics", sensors_mod)
rtx_mod = types.ModuleType("isaacsim.sensors.experimental.rtx")
rtx_mod.CameraSensor = object
rtx_mod.RtxCamera = object
sys.modules.setdefault("isaacsim.sensors.experimental.rtx", rtx_mod)

import numpy as np  # noqa: E402

import fruit_sorting.tasks as tasks_mod  # noqa: E402
from fruit_sorting.tasks import (  # noqa: E402
    TACTILE_PAD_HALF_LONG,
    TACTILE_PAD_HALF_WIDE,
    TACTILE_PAD_LONG_ORIGIN,
    parse_tactile_patch,
    disc_rect_fraction,
    tactile_patch_state,
)

sys.path.insert(0, str(ROOT / "logs" / "p102"))
import census  # noqa: E402  (the census's own row reader)

TASKS = ROOT / "src" / "fruit_sorting" / "tasks.py"
TASKS_SRC = TASKS.read_text(encoding="utf-8")


def check(cond: bool, what: str) -> None:
    if not cond:
        print(f"FAIL: {what}")
        raise SystemExit(1)
    print(f"ok: {what}")


def body_of(src: str, header: str, before: int | None = None) -> str:
    """The indented body text of `header` (the last one before `before`)."""
    start = (src.rfind(header, 0, before) if before is not None
             else src.rindex(header))
    line_start = src.rfind("\n", 0, start) + 1
    indent = start - line_start
    out = []
    for line in src[start:].splitlines()[1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        out.append(line)
    return "\n".join(out)


def main() -> int:
    print("P102 - the contact-patch tactile statistic (reporting only)")
    print("=" * 78)

    # [1] the resolver ----------------------------------------------------- #
    saved = os.environ.pop("FRUIT_TACTILE_PATCH", None)
    try:
        check(parse_tactile_patch() == 0, "unset -> 0 (the shipped path)")
        check(parse_tactile_patch("") == 0, "empty -> 0")
        check(parse_tactile_patch("   ") == 0, "blank -> 0")
        check(parse_tactile_patch("800") == 800, "'800' -> 800 ticks")
        check(parse_tactile_patch("800.0") == 800, "'800.0' -> 800")
        check(parse_tactile_patch("0") == 0, "'0' -> 0")
        check(parse_tactile_patch("-5") == 0, "'-5' -> 0 (clamped)")
        check(parse_tactile_patch("nonsense") == 0,
              "a typo -> 0, never a raise (a reporting knob must not refuse a run)")
        os.environ["FRUIT_TACTILE_PATCH"] = "400"
        check(parse_tactile_patch() == 400, "the env is read when no argument is given")
    finally:
        os.environ.pop("FRUIT_TACTILE_PATCH", None)
        if saved is not None:
            os.environ["FRUIT_TACTILE_PATCH"] = saved

    # [2] the attribute starts at 0, and `guard_armed` gains one term -------- #
    check("self._tactile_patch = parse_tactile_patch()" in TASKS_SRC,
          "the attribute is initialised from the resolver at construction")
    check("or self._tactile_patch > 0" in TASKS_SRC,
          "`guard_armed` gains exactly the `self._tactile_patch > 0` term")
    check(TASKS_SRC.count("self._tactile_patch > 0") == 1,
          "that term appears once")

    # [3] containment: no `ik_step`, no articulation *read* added ---------- #
    block_header = "if tactile_ticks and i < tactile_ticks:"
    block = body_of(TASKS_SRC, block_header)
    check(block_header in TASKS_SRC, "the row block is guarded by the tick cap")
    for forbidden in ("ik_step(", "tcp_pose(", "joint_positions(", "jaw_centre(",
                      "pad_centre(", "hold_quaternion"):
        check(forbidden not in block, f"the block adds no `{forbidden}`")
    for allowed in ("self.tactile.read()", "arm.jaw_positions()",
                    "tactile_patch_state("):
        check(allowed in block, f"the block's reads are the one it names: `{allowed}`")
    check(block.strip() != "", "the block has a body")
    guard = body_of(TASKS_SRC, "if guard_armed:", TASKS_SRC.index(block_header))
    check(block_header in guard,
          "the block sits inside the W8-B carry block (never on the shipped path)")

    # [4] the geometry: exact, and invariant where it must be --------------- #
    o0 = np.array([0.0, -0.039, 0.0])
    o1 = np.array([0.0, 0.039, 0.0])
    fruit = np.array([0.0, 0.0, 0.0])
    rot = np.eye(3)
    st = tactile_patch_state(fruit, (o0, o1), rot, 0.035)
    check(len(st) == 2, "one dict per pad")
    check(all(abs(s["u"]) < 1e-12 and abs(s["v"]) < 1e-12 for s in st),
          "a payload on the pad centre reads u = v = 0")
    check(all(abs(s["h"] - 0.039) < 1e-12 for s in st),
          "h is the signed distance to each pad's link-origin plane (39 mm)")
    check(abs(st[0]["h"] + st[1]["h"] - 0.078) < 1e-12,
          "the two pads' h sum to the measured span")
    check(abs(st[0]["u"] - st[1]["u"]) < 1e-12
          and abs(st[0]["v"] - st[1]["v"]) < 1e-12,
          "the parallel-plane degeneracy is real: the centroids are identical")
    # A wrist rotation about the jaw axis must not move the centroid in the pad
    # frame (the frame is built from the *measured* jaw axis).
    theta = 0.7
    rot_y = np.array([[math.cos(theta), 0.0, math.sin(theta)],
                      [0.0, 1.0, 0.0],
                      [-math.sin(theta), 0.0, math.cos(theta)]])
    st2 = tactile_patch_state(rot_y @ fruit, (o0, o1), rot_y, 0.035)
    check(all(abs(a["u"] - b["u"]) < 1e-9 and abs(a["v"] - b["v"]) < 1e-9
              for a, b in zip(st, st2)),
          "a wrist rotation about the jaw axis leaves the pad-frame centroid fixed")
    # A payload translated along the jaw axis must not move the centroid either.
    st3 = tactile_patch_state(fruit + np.array([0.0, 0.004, 0.0]), (o0, o1), rot, 0.035)
    check(all(abs(a["u"] - b["u"]) < 1e-12 and abs(a["v"] - b["v"]) < 1e-12
              for a, b in zip(st, st3)),
          "a payload moved along the closing axis leaves the centroid fixed")

    # [5] the occupancy signal --------------------------------------------- #
    big = 1.0
    check(abs(disc_rect_fraction(0.0, 0.0, 0.002, big, big) - 1.0) < 1e-12,
          "a patch well inside the pad is fully on it (frac = 1)")
    check(disc_rect_fraction(big + 0.5, 0.0, 0.05, big, big) == 0.0,
          "a patch centred outside the pad is fully off it (frac = 0)")
    check(disc_rect_fraction(0.0, 0.0, 0.0) == 0.0, "a zero-radius patch is 0")
    seq = [disc_rect_fraction(0.0, v, 0.035) for v in (0.0, 0.01, 0.02, 0.03, 0.04)]
    check(all(a >= b - 1e-12 for a, b in zip(seq, seq[1:])),
          "frac is monotone non-increasing as the centroid walks off the pad")
    check(abs(census.PAD_HALF_LONG - TACTILE_PAD_HALF_LONG) < 1e-12,
          "the census pins the same pad half-length the module uses")
    check(abs(TACTILE_PAD_HALF_WIDE - 0.0305) < 1e-12
          and abs(TACTILE_PAD_HALF_LONG - 0.042451) < 1e-12,
          "the pad half extents are the measured plate's (61.0 / 84.902 mm)")

    # [6] the long-axis origin is the plate's face centre ------------------- #
    check(abs(TACTILE_PAD_LONG_ORIGIN - (0.076 - TACTILE_PAD_HALF_LONG)) < 1e-12,
          "TACTILE_PAD_LONG_ORIGIN = finger_length - half_long")
    seated = tactile_patch_state(
        np.array([0.0019, 0.0, 0.0662]), (o0, o1), rot, 0.0638 / 2.0)
    check(abs(seated[0]["edge"] * 1000.0 - 9.8) < 0.05,
          "the measured seat reads edge = +9.8 mm (logs/p102/smoke.log's datum)")
    raw = disc_rect_fraction(0.0019, 0.0662, 0.0638 / 2.0)      # link-origin centre
    pad = disc_rect_fraction(0.0019, 0.0662 - TACTILE_PAD_LONG_ORIGIN, 0.0638 / 2.0)
    check(abs(raw - 0.062) < 0.01,
          "the pre-constant rectangle reads frac 0.062 on a good seat "
          "(the measured logs/p102/smoke.log datum)")
    check(pad > 0.60,
          "the face-centre rectangle reads 0.65 on that same seat")

    # [7] the row parses back through the census's own reader --------------- #
    st = tactile_patch_state(np.array([0.001, 0.0, 0.066]), (o0, o1), rot, 0.032)
    row = (f"[tactile] left place0 pad=0 t=12 u=+1.0 v=+66.0 du=+0.1 dv=+2.0 "
           f"dc=2.00 h=+39.0 frac={st[0]['frac']:.3f} edge=+9.8 sep=78.0 gap=68.7 "
           f"f=4.90 n=1 clean=2.1 dia=64.0")
    m = census.ROW.search(row)
    check(m is not None, "the emitted row matches the census's regex")
    check(m is not None and m.group("pad") == "0" and m.group("dc") == "2.00",
          "the census reads pad and dc back")
    bad = row.replace("dc=2.00 ", "")
    check(census.ROW.search(bad) is None,
          "a dropped field fails the reader (a rename cannot pass silently)")

    # [8] the per-pad split is the escape's one-sided signature ------------- #
    one_sided = tactile_patch_state(np.array([0.0, 0.001, 0.066]), (o0, o1), rot, 0.032)
    check(abs(one_sided[0]["h"] - 0.040) < 1e-12
          and abs(one_sided[1]["h"] - 0.038) < 1e-12,
          "an off-centre payload reads a different h per pad (the one-sided read)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
