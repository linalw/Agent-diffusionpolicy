#!/usr/bin/env python3
"""P70 selftest: the output station's **height** knob and the clearance report.

P70's brief is the owner's "remove the output belts' side rails and lower the
output belt's height as appropriate". **P71 adopted half of it**: the rails are
gone by default (``FRUIT_OUTPUT_RAILS`` now defaults to ``none``; ``both``
restores) and the belt top stays at the shipped 1.35 m. So this file pins the
*arithmetic and the wiring* plus the two defaults:

1. **The knob** `FRUIT_OUTPUT_BELT_TOP_Z` (metres, default **1.35**, byte-inert
   at the default): a `field(default_factory=...)` read like the other scene
   knobs (so a bare literal cannot creep back), and a non-number raising at
   construction.
2. **The consumers that move with it** - the ones derived from the belt top,
   each asserted 1:1 or invariant with its own reason: `output_place_z` (the
   place **transfer** pose, and through it the release), `output_chute_top`
   (1:1, the 6 mm seam kept), `output_chute_bottom` (z invariant - the run
   shortens), `on_output_discharge`'s z band (1:1), `on_output_belt`'s z test
   (1:1). Plus the AST census of `output_belt_top_z`'s read sites, so a **new**
   consumer has to be declared (the P43/P44 pattern), and the two files that
   must reach it only through a property (`rl_env.py` via `output_place_z`,
   `fruits.py` via `on_output_belt`/`on_output_discharge`).
3. **The clearance instrument** (`tasks._payload_clearance`) reads the
   **authored** rail: `output_rail_proud = output_rail_height - OUTPUT_RAIL_INSET`
   when the inner rail is kept, and the **belt top** (the slab's inboard top
   edge) when it is dropped. The old literal `+ 0.035` made the field of record
   blind to `FRUIT_OUTPUT_RAIL_HEIGHT` and to `FRUIT_OUTPUT_RAILS` - the P69
   `B_PREREG.md` §2.3 precondition. At the shipped geometry the reported
   surface is unchanged to 1e-12 m, i.e. the row (1 mm) is byte-identical.
4. **The arithmetic, re-derived** (why the height cannot be what fixes a
   crossing): the crossing fraction `f = rail centreline / |place y| = 0.825`,
   the `z_crossing = f * transfer + (1 - f) * lift_end` identity, and therefore
   `d clr / d(belt top) = f - 1 = -0.175` - **lowering the belt raises the
   crossing clearance at 0.175:1** (the payload descends 82.5 % of the drop,
   the obstacle 100 %), while **removing the inner rail is 1:1** by its own
   proud height. 40 mm of lowering buys +7.0 mm; the rails buy +35 mm.
5. **The audit that bounds the lowering**: the slab's underside over the main
   belt (`T - 0.05`) against the tallest main-belt fruit at the instance scale
   (`1.17 + 0.0899`), which is 40 mm at the shipped 1.35 - so 40 mm is the
   biggest lowering the build's own print leaves.

Exit 0 on pass, 1 on the first failure.
"""
from __future__ import annotations

import ast
import math
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fruit_sorting.assets import OUTPUT_RAIL_INSET, SceneConfig  # noqa: E402

SRC = ROOT / "src" / "fruit_sorting"
KNOB = "FRUIT_OUTPUT_BELT_TOP_Z"
KNOBS = (KNOB, "FRUIT_OUTPUT_RAILS", "FRUIT_OUTPUT_RAIL_HEIGHT", "FRUIT_OUTPUT_PLACE_Y")


def check(cond: bool, what: str) -> None:
    if not cond:
        print(f"FAIL: {what}")
        raise SystemExit(1)
    print(f"ok: {what}")


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(float(a) - float(b)) <= tol


def config(**env: str) -> SceneConfig:
    """A `SceneConfig` with the four output-station knobs set explicitly."""
    saved = {k: os.environ.get(k) for k in KNOBS}
    try:
        for k in KNOBS:
            os.environ.pop(k, None)
        os.environ.update(env)
        return SceneConfig()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def load_method(name: str, path: Path) -> tuple:
    """Compile one method from source (tasks.py imports the simulator)."""
    src = path.read_text(encoding="utf-8")
    node = next(
        n
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.FunctionDef) and n.name == name
    )
    ns: dict = {"np": np}
    exec(  # noqa: S102 - a pinned, self-owned source file
        compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"),
        ns,
    )
    return ns[name], src


# --------------------------------------------------------------------------- #
# 1. The knob
# --------------------------------------------------------------------------- #
src_scene = (SRC / "assets.py").read_text(encoding="utf-8")
tree_scene = ast.parse(src_scene)
cls = next(
    n for n in tree_scene.body if isinstance(n, ast.ClassDef) and n.name == "SceneConfig"
)
field_node = next(
    n
    for n in cls.body
    if isinstance(n, ast.AnnAssign) and getattr(n.target, "id", "") == "output_belt_top_z"
)
check(
    isinstance(field_node.value, ast.Call)
    and getattr(field_node.value.func, "id", "") == "field"
    and "default_factory" in {k.arg for k in field_node.value.keywords},
    "the belt top is a `field(default_factory=...)`, not a literal",
)
check(KNOB in ast.get_source_segment(src_scene, field_node), f"the field reads {KNOB}")
check(close(config().output_belt_top_z, 1.35), "unset -> the shipped 1.35 m")
check(close(config(**{KNOB: "1.31"}).output_belt_top_z, 1.31), "=1.31 resolves to 1.31 m")
check(close(config(**{KNOB: "1.40"}).output_belt_top_z, 1.40), "=1.40 resolves to 1.40 m")
for bad in ("", "abc"):
    try:
        config(**{KNOB: bad})
    except ValueError:
        pass
    else:
        check(False, f"FRUIT_OUTPUT_BELT_TOP_Z={bad!r} must raise")
print("ok: a non-number raises at construction")

# The **rails default** (P71): `none`, with `both` the documented restore. The
# shipped 1.35 m height is deliberately unchanged (P70 measured the height as a
# 0.175:1 lever that costs placements; the rail is the 1:1 one).
check(config().output_rails == "none", "unset -> FRUIT_OUTPUT_RAILS=none (the P71 default)")
check(config().output_rail_keep == (False, False), "the P71 default authors no rail at all")
check(config(FRUIT_OUTPUT_RAILS="both").output_rail_keep == (True, True),
      "=both restores the pre-P71 shipped rail pair")
rails_field = next(
    n
    for n in cls.body
    if isinstance(n, ast.AnnAssign) and getattr(n.target, "id", "") == "output_rails"
)
_rails_seg = ast.get_source_segment(src_scene, rails_field)
check(
    "default_factory=" in _rails_seg and '"FRUIT_OUTPUT_RAILS", "none"' in _rails_seg,
    "the rails default is the env-read default_factory, and it reads `none`",
)

# --------------------------------------------------------------------------- #
# 2. The consumers that move (and the two that do not)
# --------------------------------------------------------------------------- #
shipped, low = config(), config(**{KNOB: "1.31"})
dz = low.output_belt_top_z - shipped.output_belt_top_z
check(close(dz, -0.04), "the test's dose is -40 mm")

check(close(shipped.output_place_z, 1.45), "shipped output_place_z = 1.45 m")
check(close(low.output_place_z - shipped.output_place_z, dz),
      "output_place_z (the place transfer -> the release) moves 1:1")
check(close(low.output_place_z + 0.08 - (shipped.output_place_z + 0.08), dz),
      "the place target z (output_place_z + the hand's 0.08) moves 1:1")
check(close(shipped.output_chute_top[1], 1.35 - 0.006), "the chute top is belt top - 6 mm (the seam)")
check(close(low.output_chute_top[1] - shipped.output_chute_top[1], dz), "the chute top moves 1:1")
check(close(low.output_chute_bottom[1], shipped.output_chute_bottom[1]),
      "the chute's lower edge (and the tray) does not move - only the run shortens")
check(low.output_chute_bottom[0] < shipped.output_chute_bottom[0],
      "the chute's run gets shorter by the same 40 mm / tan(angle)")

fixed_z = 1.396  # inside the shipped discharge envelope (top 1.40), outside the -40 mm one (1.36)
inside_shipped = shipped.on_output_discharge(
    np.array([shipped.output_belt_end_x + 0.10, 0.55, fixed_z])
)
inside_low = low.on_output_discharge(np.array([low.output_belt_end_x + 0.10, 0.55, fixed_z]))
check(bool(inside_shipped) and not bool(inside_low),
      "the discharge envelope's top follows the belt (one absolute point crosses out)")

low_z = 1.28  # below the shipped belt by more than the 60 mm margin, inside the lowered one's
check(
    not bool(shipped.on_output_belt(np.array([0.43, 0.55, low_z])))
    and bool(low.on_output_belt(np.array([0.43, 0.55, low_z]))),
    "on_output_belt's z test follows the belt (the `placed` classifier's surface)",
)
check(close(shipped.output_tray_floor_top_z, 0.92) and close(shipped.output_chute_end_z, 1.12),
      "the tray floor and the chute's end z are absolute - they do not move")
check(close(shipped.output_place_clearance, 0.10) and close(OUTPUT_RAIL_INSET, 0.015),
      "the release clearance and the rail inset stay at 0.10 / 0.015")

# The AST census: every `output_belt_top_z` read site, by enclosing scope.
census: set[str] = set()
for path in sorted(SRC.rglob("*.py")):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    stack: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_ClassDef(self, node):  # noqa: N802
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        def visit_FunctionDef(self, node):  # noqa: N802
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        def visit_Attribute(self, node):  # noqa: N802
            if node.attr == "output_belt_top_z":
                census.add(f"{path.name}:{'.'.join(stack) or '<module>'}")
            self.generic_visit(node)

    Visitor().visit(tree)
expected = {
    "assets.py:SceneConfig.output_place_z",
    "assets.py:SceneConfig.on_output_belt",
    "assets.py:SceneConfig.output_chute_top",
    "assets.py:SceneConfig.output_chute_bottom",
    "assets.py:SceneConfig.on_output_discharge",
    "conveyor.py:OutputBelt.__init__",
    "conveyor.py:OutputBelt.build",
    "tasks.py:PickAndPlaceTask._grasp_carry_place_impl",
    "tasks.py:PickAndPlaceTask._payload_clearance",
    "tasks.py:PickAndPlaceTask._place_low",
    "tasks.py:PickAndPlaceTask._place_trace_report",
}
check(census == expected, f"the read-site census is the declared one ({len(census)} scopes)")
for name in ("rl_env.py", "fruits.py", "scene.py", "bed.py", "bimanual.py", "grasp.py"):
    text = (SRC / name).read_text(encoding="utf-8")
    check("output_belt_top_z" not in text, f"{name} reaches the belt top only through a property")
check("cfg.output_place_z" in (SRC / "rl_env.py").read_text(encoding="utf-8"),
      "rl_env sees the height through output_place_z (the transfer / lift-climb row)")

# --------------------------------------------------------------------------- #
# 3. The clearance instrument reads the authored rail
# --------------------------------------------------------------------------- #
clearance_fn, tasks_src = load_method("_payload_clearance", SRC / "tasks.py")


class Stub:
    """The smallest object `_payload_clearance` reads."""

    belt_top = 1.170

    def __init__(self, cfg: SceneConfig) -> None:
        self.cfg = cfg

    @staticmethod
    def _shape_support(sample, down) -> float:  # noqa: ANN001
        return 0.020


def clearance(cfg: SceneConfig, y: float, z: float = 1.500) -> tuple:
    return clearance_fn(Stub(cfg), None, np.array([0.43, y, z]))


rails_shipped = config(FRUIT_OUTPUT_RAILS="both")   # the pre-P71 geometry
rails_default = config()                            # the P71 default: no rail
none = config(FRUIT_OUTPUT_RAILS="none")
outer = config(FRUIT_OUTPUT_RAILS="outer")
flush = config(FRUIT_OUTPUT_RAILS="both", FRUIT_OUTPUT_RAIL_HEIGHT="0.015")
g0_dose = config(FRUIT_OUTPUT_RAILS="both", FRUIT_OUTPUT_RAIL_HEIGHT="0.039")

check(rails_default.output_rails == "none" and rails_default.output_rail_keep == (False, False),
      "the unset config authored no rail at all (the P71 default)")
check(clearance(rails_default, 0.4125) == clearance(none, 0.4125),
      "the default reads exactly like an explicit `none`")
v, where = clearance(rails_shipped, 0.4125)
check(where == "output rail" and close(v, 1.480 - 1.385), "rails both: reported against the rail top (1.385)")
check(close(rails_shipped.output_rail_proud, 0.035), "output_rail_proud = 0.05 - 0.015 = 0.035 at the shipped rail")
check(close(clearance(rails_shipped, 0.4125)[0], 1.480 - (rails_shipped.output_belt_top_z + 0.035), tol=1e-12),
      "the shipped rail's surface is belt_top + 0.035 to 1e-12 (the row's mm is unchanged)")
v_none, where_none = clearance(none, 0.4125)
check(where_none == "output belt" and close(v_none, 1.480 - 1.350),
      "rails none: reported against the slab's inboard top edge (the belt top)")
check(close(v_none - v, none.output_rail_proud), "removing the inner rail is 1:1 with its proud height (+35 mm)")
check(clearance(outer, 0.4125)[1] == "output belt", "`outer` (inner rail dropped) reads the belt top too")
check(close(clearance(flush, 0.4125)[0], v_none), "a flush rail (0.015) reads the same as none at the crossing")
check(close(clearance(g0_dose, 0.4125)[0] - v, 0.011),
      "the G0 dose (h = 0.039) buys +11 mm, as measured")
check(clearance(rails_shipped, 0.430)[1] == "output rail" and clearance(rails_shipped, 0.390)[1] == "main belt",
      "the y brackets are unchanged (0.40 main / 0.46 rail window)")
check("+ 0.035" not in tasks_src,
      "the hard-coded `belt_top + 0.035` is gone from the report")
seg = ast.get_source_segment(tasks_src, next(
    n for n in ast.walk(ast.parse(tasks_src))
    if isinstance(n, ast.FunctionDef) and n.name == "_payload_clearance"))
check("output_rail_keep" in seg and "output_rail_proud" in seg,
      "the instrument reads the rail's keep flag and its derived proud height")

# --------------------------------------------------------------------------- #
# 4. The crossing arithmetic (derived, not assumed)
# --------------------------------------------------------------------------- #
cfg = config()
rail_inner = abs(cfg.output_belt_y) - (cfg.output_belt_size[1] / 2.0 + 0.0125) - 0.0125
rail_centre = abs(cfg.output_belt_y) - (cfg.output_belt_size[1] / 2.0 + 0.0125)
place_y = abs(cfg.output_belt_drop_points[0][1])
f = rail_centre / place_y
check(close(rail_inner, 0.400) and close(rail_centre, 0.4125), "rail faces 0.400 / 0.4125 m")
check(close(f, 0.825), "crossing fraction f = 0.825 of the |y| span")
main_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
check(close(main_top, 1.170), "main belt top 1.170")
lift_end = main_top + 0.28 + 0.08  # tasks.jaw_target grasp_lift + the hand's add
check(close(lift_end, 1.530), "the scripted lift end is 1.530 m (independent of the output height)")


def z_crossing(top_z: float) -> float:
    transfer = top_z + cfg.output_place_clearance + 0.08
    return f * transfer + (1.0 - f) * lift_end


check(close(z_crossing(1.35), 1.530), "z_crossing at the shipped 1.35 is the transfer itself (1.530)")
check(close(z_crossing(1.31), 1.4970, tol=1e-6), "z_crossing at 1.31 is 1.4970 m (-33.0 mm)")
check(close(z_crossing(1.31) - z_crossing(1.35), f * dz),
      "the crossing follows the transfer pose at f = 0.825")
slope = f - 1.0
check(close(slope, -0.175), "d clr / d(belt top) = f - 1 = -0.175 (the obstacle moves 1:1, the payload 0.825)")
gain_40 = -slope * 0.040
check(close(gain_40, 0.007), "40 mm of lowering buys +7.0 mm of crossing clearance - the SIGN is positive")
gain_rails = rails_shipped.output_rail_proud
check(close(gain_rails, 0.035) and gain_rails > gain_40,
      "removing the rails (+35 mm, 1:1) is 5x the biggest admissible lowering (+7 mm)")
check(close(gain_rails + gain_40, 0.042), "cell B (no rails at 1.31) nets +42 mm against the shipped rail case")

# --------------------------------------------------------------------------- #
# 5. The audit that bounds the lowering
# --------------------------------------------------------------------------- #
slab = cfg.output_belt_size[2]
pear_instance = 0.0899  # conveyor's print: pear 1.20 W x 0.070 m x 1.0706 (INSTANCE_SCALE_MAX)


def underside(top_z: float) -> float:
    return (top_z - slab) - (main_top + pear_instance)


check(close(underside(1.35), 0.0401, tol=2e-4),
      "the shipped underside clears the tallest main-belt fruit by 40 mm at the instance scale")
check(close(underside(1.31), 0.0001, tol=2e-3),
      "40 mm of lowering spends that whole budget - it is the lever's endpoint, not a free parameter")
check(underside(1.33) > 0.019, "a 20 mm lowering keeps ~20 mm of it (the conservative pick)")
bed_cut = main_top + 0.10  # fruits._free_sample's bed-only "not on the main belt" cut
check(min(1.31 + 0.014, 1.35 + 0.014) > bed_cut + 0.03,
      "the bed's placed-fruit exclusion still clears at 1.31 (>= 30 mm)")

print("\nall P70 pins pass")
