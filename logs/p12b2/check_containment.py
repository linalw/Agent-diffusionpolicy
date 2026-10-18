"""Offline regression test for the P12-B.2 S4 containment bundle (no simulator).

`conveyor.py` imports Isaac Sim, so this test stubs the heavy modules first (the
`scripts/172_supply_selftest.py` pattern) and then runs the **real**
`CleatedBelt.build()` against a recording fake stage:

1. **Knob resolution** - `FRUIT_BELT_CONTAINMENT` unset/"0" -> off, "1" -> on,
   read **once** at construction (flipping the env afterwards changes nothing).
2. **Knob-off byte-identity** - with the knob off, `build()` defines exactly the
   9 shipped prims (pinned paths + sizes + centres); no containment geometry,
   no stage call. This is the "no prims added" pin.
3. **Knob-on part list** - `build()` defines the 9 shipped prims plus the three
   containment prims, and each authored prim matches `containment_parts()`
   exactly; the placements are pinned to the numbers.
4. **No-obstruction clearances** (pure arithmetic over `SceneConfig`): the
   transport lane (the fruit ride + the drift tail), the catch's reach band,
   the open hand's +/-0.066 m span, the two-line stations, the place paths and
   the despawn lane. Every number the scoping record requires is asserted here.
5. **Source shape** - the env knob is read exactly once and the builder call is
   guarded by it (so the shipped path cannot author containment geometry).

Run: `python3 logs/p12b2/check_containment.py` (offline; the simulator battery
is the separate lane, deferred).
"""

from __future__ import annotations

import math
import os
import sys
import types

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

# --- stub pxr / isaacsim just enough to import fruit_sorting.conveyor -------- #
for name in ("pxr", "isaacsim", "isaacsim.core", "isaacsim.core.experimental"):
    sys.modules.setdefault(name, types.ModuleType(name))
pxr = sys.modules["pxr"]
for attr in ("Gf", "PhysxSchema", "Sdf", "Usd", "UsdGeom", "UsdPhysics", "UsdShade"):
    if not hasattr(pxr, attr):
        setattr(pxr, attr, types.ModuleType(f"pxr.{attr}"))
pxr.Gf.Vec3f = lambda *a: tuple(float(v) for v in a)
pxr.Gf.Vec3d = lambda *a: tuple(float(v) for v in a)
pxr.Gf.Quatf = lambda *a: tuple(float(v) for v in a)
pxr.Sdf.ValueTypeNames = types.SimpleNamespace(Color3f="Color3f", Float="Float")


class _Attr:
    def __init__(self, on_set=None):
        self._on_set = on_set

    def Set(self, value):
        if self._on_set is not None:
            self._on_set(value)
        return True


class _Connectable:
    def ConnectToSource(self, *args, **kwargs):
        return self


class _ApplyAPI:
    def __init__(self, prim=None):
        self.prim = prim

    def Apply(self, prim):
        return _ApplyAPI(prim)

    def Bind(self, *args, **kwargs):
        return self

    def CreateKinematicEnabledAttr(self):
        return _Attr()

    def CreateMassAttr(self):
        return _Attr()

    def CreateStaticFrictionAttr(self):
        return _Attr()

    def CreateDynamicFrictionAttr(self):
        return _Attr()

    def CreateRestitutionAttr(self):
        return _Attr()


class _Prim:
    """A Cube/Cylinder-like prim that records its authoring."""

    def __init__(self, stage, path, kind):
        self.stage = stage
        self.path = path
        self.kind = kind
        self.size = None
        self.translate = None
        self.scale = None

    def GetPrim(self):
        return self

    def GetStage(self):
        return self.stage

    def GetPath(self):
        return self.path

    def GetSizeAttr(self):
        return _Attr(lambda v: setattr(self, "size", v))

    def GetRadiusAttr(self):
        return _Attr()

    def GetHeightAttr(self):
        return _Attr()

    def GetAxisAttr(self):
        return _Attr()

    def ClearXformOpOrder(self):
        return None

    def AddTranslateOp(self):
        return _Attr(lambda v: setattr(self, "translate", tuple(float(x) for x in v)))

    def AddScaleOp(self):
        return _Attr(lambda v: setattr(self, "scale", tuple(float(x) for x in v)))


class _Stage:
    """Records every defined prim by path."""

    def __init__(self):
        self.prims: dict[str, _Prim] = {}

    def _define(self, kind, path):
        prim = _Prim(self, path, kind)
        self.prims[path] = prim
        return prim

    def GetPrimAtPath(self, path):
        return self.prims.get(path, _Prim(self, path, "Missing"))


pxr.UsdGeom.Cube = types.SimpleNamespace(
    Define=lambda stage, path: stage._define("Cube", path)
)
pxr.UsdGeom.Cylinder = types.SimpleNamespace(
    Define=lambda stage, path: stage._define("Cylinder", path)
)
pxr.UsdGeom.Xformable = lambda prim: prim
pxr.UsdPhysics.CollisionAPI = _ApplyAPI()
pxr.UsdPhysics.RigidBodyAPI = _ApplyAPI()
pxr.UsdPhysics.MassAPI = _ApplyAPI()
pxr.UsdPhysics.MaterialAPI = _ApplyAPI()


class _Shader:
    def CreateIdAttr(self, _):
        return _Attr()

    def CreateInput(self, *args):
        return _Attr()

    def ConnectableAPI(self):
        return _Connectable()


class _Material:
    def GetPrim(self):
        return _Prim(None, "/mat", "Material")

    def CreateSurfaceOutput(self):
        return _Connectable()


pxr.UsdShade.Material = types.SimpleNamespace(Define=lambda stage, path: _Material())
pxr.UsdShade.Shader = types.SimpleNamespace(Define=lambda stage, path: _Shader())
pxr.UsdShade.MaterialBindingAPI = _ApplyAPI()
pxr.UsdShade.Tokens = types.SimpleNamespace(weakerThanDescendants="weakerThanDescendants")


class _SurfaceVelocity:
    def Apply(self, prim):
        return self

    def CreateSurfaceVelocityAttr(self):
        return _Attr()


pxr.PhysxSchema.PhysxSurfaceVelocityAPI = _SurfaceVelocity()

app_mod = types.ModuleType("isaacsim.core.experimental.utils.app")
app_mod.update_app = lambda **kwargs: None
sys.modules.setdefault("isaacsim.core.experimental.utils.app", app_mod)
utils_mod = types.ModuleType("isaacsim.core.experimental.utils")
sys.modules.setdefault("isaacsim.core.experimental.utils", utils_mod)
stage_mod = types.ModuleType("isaacsim.core.experimental.utils.stage")
sys.modules.setdefault("isaacsim.core.experimental.utils.stage", stage_mod)
objects_mod = types.ModuleType("isaacsim.core.experimental.objects")
objects_mod.DistantLight = object
objects_mod.GroundPlane = object
sys.modules.setdefault("isaacsim.core.experimental.objects", objects_mod)
prims_mod = types.ModuleType("isaacsim.core.experimental.prims")
prims_mod.RigidPrim = object
prims_mod.Articulation = object
sys.modules.setdefault("isaacsim.core.experimental.prims", prims_mod)
rtx_mod = types.ModuleType("isaacsim.sensors.experimental.rtx")
rtx_mod.CameraSensor = object
rtx_mod.RtxCamera = object
sys.modules.setdefault("isaacsim.sensors.experimental.rtx", rtx_mod)

from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.conveyor import (  # noqa: E402
    CleatedBelt,
    _CONTAINMENT_FENCE_THICKNESS,
    _CONTAINMENT_FENCE_X,
    _CONTAINMENT_HEIGHT,
    _CONTAINMENT_KEEPER_THICKNESS,
    containment_parts,
)

# --------------------------------------------------------------------------- #
# The pins.
# --------------------------------------------------------------------------- #
#: The shipped build's prim list (`FRUIT_BELT_CONTAINMENT` off): path -> (kind,
#: size, centre). Captured from the pre-change tree; the knob-off build must
#: reproduce it exactly (rounded to 1e-6), i.e. the containment bundle adds
#: nothing.
SHIPPED_PRIMS = {
    "/World/Conveyor/Belt": ("Cube", (0.46, 1.60, 0.06), (0.34, 0.0, 1.14)),
    "/World/Conveyor/FrameN": ("Cube", (0.025, 1.70, 0.05), (0.098, 0.0, 1.19)),
    "/World/Conveyor/FrameP": ("Cube", (0.025, 1.70, 0.05), (0.582, 0.0, 1.19)),
    "/World/Conveyor/Leg00": ("Cube", (0.05, 0.05, 1.11), (0.21, -0.77, 0.555)),
    "/World/Conveyor/Leg01": ("Cube", (0.05, 0.05, 1.11), (0.21, 0.77, 0.555)),
    "/World/Conveyor/Leg10": ("Cube", (0.05, 0.05, 1.11), (0.47, -0.77, 0.555)),
    "/World/Conveyor/Leg11": ("Cube", (0.05, 0.05, 1.11), (0.47, 0.77, 0.555)),
    "/World/Conveyor/PulleyHead": ("Cylinder", None, (0.34, 0.824, 1.15)),
    "/World/Conveyor/PulleyTail": ("Cylinder", None, (0.34, -0.824, 1.15)),
}

#: The containment bundle's exact placements (shipped geometry), from the
#: P12-B.2 scoping record section S4: keeper y ~= -0.79, fences x <= 0.13 /
#: >= 0.43, heights in the 40-60 mm band.
EXPECTED_KEEPER_SIZE = (0.46, 0.02, 0.05)
EXPECTED_KEEPER_CENTER = (0.34, -0.79, 1.195)
EXPECTED_FENCES = {
    "/World/Conveyor/SideFenceN": ((0.015, 1.56, 0.05), (0.1225, 0.0, 1.195)),
    "/World/Conveyor/SideFenceP": ((0.015, 1.56, 0.05), (0.4375, 0.0, 1.195)),
}

#: The delivered supply band (`fruits.py`; the scoping's section 1.2) and the
#: open hand's span (`assets.py:251`), the fall path's free-fall baseline and
#: the waypoint constants the place-path checks use.
SUPPLY_BAND_X = (0.20, 0.36)
HAND_SPAN = 0.066
FINGERTIP_HANG = 0.0814
PAD_STANDOFF_MAX = 0.090  # 70 mm shipped + the S3 arm's +20 mm
FRUIT_RADIUS_MAX = 0.035  # the 70 mm classes
FRUIT_RADIUS_MIN = 0.014  # the 28 mm lychee
TRANSFER_LIFT = 0.08  # FRUIT_OPENARM_TRANSFER_LIFT (shipped)
PLACE_LOW_FINGER_MARGIN = 0.005  # FRUIT_PLACE_LOW_FINGER_MARGIN (shipped)


def approx(a, b, tol=1e-6):
    return abs(float(a) - float(b)) <= tol


def vec_approx(a, b, tol=1e-6):
    return len(a) == len(b) and all(approx(x, y, tol) for x, y in zip(a, b))


def build(env_value):
    """Build a CleatedBelt on a fresh recording stage with the knob set."""
    os.environ.pop("FRUIT_BELT_CONTAINMENT", None)
    if env_value is not None:
        os.environ["FRUIT_BELT_CONTAINMENT"] = env_value
    stage = _Stage()
    belt = CleatedBelt(stage, SceneConfig())
    belt.build()
    return belt, stage


def main() -> int:
    checks = 0

    def check(condition: bool, text: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            raise AssertionError(text)

    cfg = SceneConfig()
    bx, by, bz = (float(v) for v in cfg.belt_center)
    sx, sy, sz = (float(v) for v in cfg.belt_size)
    belt_top = bz + sz / 2.0
    end_y = by - sy / 2.0
    top_y = by + sy / 2.0
    check(approx(end_y, -0.80) and approx(top_y, 0.80) and approx(belt_top, 1.17),
          "shipped belt geometry (ends -0.80/+0.80, top 1.17)")

    # --- 1. the knob resolution + read-once -------------------------------- #
    belt_off, stage_off = build(None)
    check(not belt_off.containment, "FRUIT_BELT_CONTAINMENT unset -> off")
    belt_zero, _ = build("0")
    check(not belt_zero.containment, "FRUIT_BELT_CONTAINMENT=0 -> off")
    belt_on, stage_on = build("1")
    check(belt_on.containment, "FRUIT_BELT_CONTAINMENT=1 -> on")
    os.environ["FRUIT_BELT_CONTAINMENT"] = "0"
    check(belt_on.containment, "the knob is read once (flipping the env later is inert)")
    os.environ.pop("FRUIT_BELT_CONTAINMENT", None)

    # --- 2. knob-off byte-identity: the shipped prim list, nothing added --- #
    off_paths = set(stage_off.prims)
    check(off_paths == set(SHIPPED_PRIMS), f"knob-off prim set is the shipped 9 ({sorted(off_paths)})")
    for path, (kind, size, center) in SHIPPED_PRIMS.items():
        prim = stage_off.prims[path]
        check(prim.kind == kind, f"{path}: kind {prim.kind} != {kind}")
        if size is not None:
            check(vec_approx(prim.scale, size), f"{path}: size {prim.scale} != {size}")
        check(vec_approx(prim.translate, center), f"{path}: centre {prim.translate} != {center}")
    for path in off_paths:
        check(
            not any(tag in path for tag in ("Keeper", "Fence", "Containment")),
            f"knob-off authored a containment prim: {path}",
        )

    # --- 3. knob-on: the part list, placements, authored prims ------------- #
    on_paths = set(stage_on.prims)
    check(
        on_paths == set(SHIPPED_PRIMS) | set(EXPECTED_FENCES) | {"/World/Conveyor/BeltEndKeeper"},
        f"knob-on prim set is shipped + 3 ({sorted(on_paths - set(SHIPPED_PRIMS))})",
    )
    parts = containment_parts(cfg)
    check(len(parts) == 3, "containment_parts returns keeper + 2 fences")
    keeper, fence_n, fence_p = parts
    check(keeper["path"] == "/World/Conveyor/BeltEndKeeper", "keeper path")
    check(vec_approx(keeper["size"], EXPECTED_KEEPER_SIZE), "keeper size 0.46 x 0.020 x 0.050")
    check(vec_approx(keeper["center"], EXPECTED_KEEPER_CENTER), "keeper centre (0.34, -0.79, 1.195)")
    check(
        vec_approx(stage_on.prims["/World/Conveyor/BeltEndKeeper"].scale, EXPECTED_KEEPER_SIZE)
        and vec_approx(stage_on.prims["/World/Conveyor/BeltEndKeeper"].translate, EXPECTED_KEEPER_CENTER),
        "authored keeper matches containment_parts",
    )
    for part in (fence_n, fence_p):
        expected = EXPECTED_FENCES[part["path"]]
        check(vec_approx(part["size"], expected[0]), f"{part['path']}: size {part['size']}")
        check(vec_approx(part["center"], expected[1]), f"{part['path']}: centre {part['center']}")
        check(
            vec_approx(stage_on.prims[part["path"]].scale, expected[0])
            and vec_approx(stage_on.prims[part["path"]].translate, expected[1]),
            f"authored {part['path']} matches containment_parts",
        )
    # The shipped prims are unchanged by the knob (only 3 prims added).
    for path in SHIPPED_PRIMS:
        check(
            vec_approx(stage_on.prims[path].translate, stage_off.prims[path].translate),
            f"knob-on moved a shipped prim: {path}",
        )

    # --- 4. the no-obstruction clearances ---------------------------------- #
    keeper_y0 = keeper["center"][1] - keeper["size"][1] / 2.0
    keeper_y1 = keeper["center"][1] + keeper["size"][1] / 2.0
    keeper_top = keeper["center"][2] + keeper["size"][2] / 2.0
    fence_n_x = fence_n["center"][0] + _CONTAINMENT_FENCE_THICKNESS / 2.0  # inner face
    fence_p_x = fence_p["center"][0] - _CONTAINMENT_FENCE_THICKNESS / 2.0  # inner face

    # 4a. the keeper: at the belt end, the belt's width, on the belt top.
    check(approx(keeper_y0, end_y), "keeper's downstream face is flush with the belt end (-0.80)")
    check(approx(keeper_y1, -0.78), "keeper's upstream face at -0.78")
    check(approx(keeper_top, belt_top + _CONTAINMENT_HEIGHT), "keeper top at belt_top + 50 mm")
    check(
        keeper["size"][2] >= FRUIT_RADIUS_MAX + 0.015,
        "keeper height stands above the largest fruit's centre (35 mm) by >= 15 mm",
    )

    # 4b. the despawn lane: the feeder recycles at `along < despawn_y` and the
    # keeper's face is downstream of it, so every fruit crosses the threshold
    # before contact (the keeper converts a would-be `fell_off` into the next
    # `update()`'s `reached_end`; it does not dam the belt).
    despawn_y = float(cfg.despawn_y)
    check(approx(despawn_y, -0.70), "despawn line -0.70")
    check(keeper_y1 < despawn_y, "the keeper's upstream face is downstream of the despawn line")
    stop_min = keeper_y1 + FRUIT_RADIUS_MIN  # deepest stop: the smallest fruit
    stop_max = keeper_y1 + FRUIT_RADIUS_MAX
    check(stop_max < despawn_y, f"a fruit stops past the despawn line (worst {stop_max:+.3f} < -0.70)")
    check(
        despawn_y - stop_max >= 0.04,
        f"despawn-lane margin >= 40 mm (worst {1000 * (despawn_y - stop_max):.0f} mm)",
    )
    check(stop_min < despawn_y, "the smallest fruit also stops past the despawn line")
    check(
        despawn_y - stop_min >= 0.06,
        f"smallest-fruit margin >= 60 mm ({1000 * (despawn_y - stop_min):.0f} mm)",
    )
    check(
        keeper_y0 <= end_y + 1e-9,
        "the keeper takes no belt length (its downstream face is the end face)",
    )

    # 4c. the transport lane: the fruit ride. A fruit in the supply band with
    # the pool's largest radius clears both fences; the drift tail (x = 0.148,
    # the measured extreme) may touch the -X fence - that is containment, and
    # it is only contact for r >= 18 mm (documented residual).
    band_lo, band_hi = SUPPLY_BAND_X
    ride_left = band_lo - FRUIT_RADIUS_MAX - fence_n_x
    ride_right = fence_p_x - (band_hi + FRUIT_RADIUS_MAX)
    check(ride_left >= 0.03, f"band fruit clear the -X fence by {1000 * ride_left:.0f} mm")
    check(ride_right >= 0.03, f"band fruit clear the +X fence by {1000 * ride_right:.0f} mm")
    drift_tail = 0.148  # measured drift extreme (scoping section 1.2)
    drift_touch_r = drift_tail - fence_n_x
    check(
        abs(drift_touch_r - 0.018) < 1e-9,
        "the drift tail contacts the -X fence only for r >= 18 mm (containment, not a fall)",
    )
    check(
        drift_tail + FRUIT_RADIUS_MAX >= fence_n_x,
        "the drift tail cannot pass the -X fence (it is caught, not lost)",
    )

    # 4d. the open hand's span: at the delivered band's edges the +/-0.066 m
    # span reaches 0.134-0.266 / 0.294-0.426; the fences clear those by 4 mm
    # (the scoping's binding budget). At the pick point (0.34) the span is
    # 0.274-0.406: 144/24 mm.
    left_span = (band_lo - HAND_SPAN, band_lo + HAND_SPAN)
    right_span = (band_hi - HAND_SPAN, band_hi + HAND_SPAN)
    check(approx(left_span[0], 0.134) and approx(right_span[1], 0.426), "hand spans 0.134/0.426")
    check(
        approx(left_span[0] - fence_n_x, 0.004),
        f"band-edge hand span clears the -X fence by 4 mm ({1000 * (left_span[0] - fence_n_x):.1f} mm)",
    )
    check(
        approx(fence_p_x - right_span[1], 0.004),
        f"band-edge hand span clears the +X fence by 4 mm ({1000 * (fence_p_x - right_span[1]):.1f} mm)",
    )
    pick_span = (bx - HAND_SPAN, bx + HAND_SPAN)
    check(approx(pick_span[0], 0.274) and approx(pick_span[1], 0.406), "pick-point span 0.274/0.406")
    check(
        pick_span[0] - fence_n_x >= 0.14 and fence_p_x - pick_span[1] >= 0.02,
        "pick-point span clears both fences (>=144 / >=24 mm)",
    )

    # 4e. the catch's reach band (scripts/174): the fences sit outside the
    # measured reachable x band; the hand-span check above is the binding one.
    reach_band = (0.186, 0.386)
    check(
        fence_n_x + _CONTAINMENT_FENCE_THICKNESS <= reach_band[0]
        and fence_p_x >= reach_band[1],
        "the fences sit outside the measured reach band (x 0.186-0.386)",
    )

    # 4f. the two-line stations: the fences run along Y at a fixed x, outside
    # the hand's span (the same 4 mm check as 4d); the keeper is 0.68 m
    # downstream of the right station and 0.78 m of the left.
    station_left, station_right = 0.00, -0.10
    check(
        station_left - keeper_y1 >= 0.68 and station_right - keeper_y1 >= 0.68,
        "the keeper is >= 0.68 m downstream of both two-line stations",
    )
    check(
        fence_n["size"][1] >= 1.5,
        f"the fences cover the stations' stretch (y span {fence_n['size'][1]:.2f} m)",
    )

    # 4g. the place paths. The carry waypoints are at z = 1.53 (grasp_lift:
    # belt_top + 0.28 + 0.08; place: output_belt_top_z + 0.10 + 0.08); the
    # payload's lowest point is jaw - standoff - r, the fingertips jaw - 81.4
    # mm. The carry crosses the +X fence's plane at the place waypoint
    # (x = 0.43, y = +/-0.50) at that height; the place descent's fingertips
    # stop at output_belt_top_z + 5 mm; the ready pose's fingertips at
    # belt_top + 0.20 - 81.4 mm.
    carry_z = belt_top + 0.28 + TRANSFER_LIFT
    place_z = float(cfg.output_belt_top_z) + float(cfg.output_place_clearance) + TRANSFER_LIFT
    check(approx(carry_z, 1.53) and approx(place_z, 1.53), "carry/place waypoint z = 1.53")
    place_x = float(cfg.output_place_x)
    place_y = float(cfg.output_place_y)
    check(approx(place_x, 0.43) and abs(place_y - 0.50) < 1e-9, "place waypoint (0.43, +/-0.50)")
    payload_low = carry_z - PAD_STANDOFF_MAX - FRUIT_RADIUS_MAX
    check(
        payload_low - keeper_top >= 0.18,
        f"carried payload clears the fence top by >= 180 mm ({1000 * (payload_low - keeper_top):.0f} mm)",
    )
    fingertips_low = place_z - FINGERTIP_HANG
    place_low_fingertips = float(cfg.output_belt_top_z) + PLACE_LOW_FINGER_MARGIN
    check(
        place_low_fingertips - keeper_top >= 0.13,
        f"place descent fingertips clear the fence top by >= 130 mm "
        f"({1000 * (place_low_fingertips - keeper_top):.0f} mm)",
    )
    ready_fingertips = belt_top + 0.20 - FINGERTIP_HANG
    check(
        ready_fingertips - keeper_top >= 0.06,
        f"ready-pose fingertips clear the fence top by >= 60 mm "
        f"({1000 * (ready_fingertips - keeper_top):.0f} mm)",
    )
    check(fingertips_low > keeper_top, "carry fingertips clear the fence top")

    # 4h. static-scene neighbours: the fences sit inside the belt's width and
    # clear the main frame rails; the fence ends clear the pulley crowns.
    belt_x0, belt_x1 = bx - sx / 2.0, bx + sx / 2.0
    fence_n_x0 = fence_n["center"][0] - _CONTAINMENT_FENCE_THICKNESS / 2.0
    fence_p_x1 = fence_p["center"][0] + _CONTAINMENT_FENCE_THICKNESS / 2.0
    check(belt_x0 < fence_n_x0 and fence_p_x1 < belt_x1, "the fences sit inside the belt width")
    rail_center = bx - (sx / 2.0 + float(cfg.main_frame_rail_offset))
    rail_inner = rail_center + float(cfg.main_frame_rail_width) / 2.0
    check(
        fence_n_x0 - rail_inner >= 0.004,
        f"the -X fence clears the main frame rail's inner face by "
        f"{1000 * (fence_n_x0 - rail_inner):.1f} mm",
    )
    pulley_r = sz / 2.0 + 0.01
    pulley_y = sy / 2.0 + pulley_r * 0.6
    pulley_z = belt_top - pulley_r * 0.5
    crown_dy = math.sqrt(max(pulley_r**2 - (belt_top - pulley_z) ** 2, 0.0))
    crown_y = pulley_y - crown_dy
    fence_y1 = fence_n["center"][1] + fence_n["size"][1] / 2.0
    check(
        crown_y - fence_y1 >= 0.009,
        f"the fence ends clear the pulley crown at the belt top by "
        f"{1000 * (crown_y - fence_y1):.1f} mm",
    )

    # --- 5. the source shape: one env read, guarded authoring -------------- #
    source = open(os.path.join(ROOT, "src", "fruit_sorting", "conveyor.py"), encoding="utf-8").read()
    check(
        source.count('os.environ.get("FRUIT_BELT_CONTAINMENT"') == 1,
        "the knob is read exactly once in conveyor.py",
    )
    check(
        "if self.containment:\n            self._build_containment()" in source,
        "the containment authoring is guarded by `if self.containment`",
    )

    print(
        "containment check: keeper y=[-0.800,-0.780] z-top 1.220 (h 50 mm); "
        "fences x-inner 0.130/0.430, x-span [0.115,0.130]/[0.430,0.445], "
        "y=[-0.780,+0.780]; clearances: hand-span at the band edges "
        f"{1000 * (left_span[0] - fence_n_x):.0f}/{1000 * (fence_p_x - right_span[1]):.0f} mm, "
        f"despawn lane {1000 * (despawn_y - stop_max):.0f}-{1000 * (despawn_y - stop_min):.0f} mm, "
        f"carried payload {1000 * (payload_low - keeper_top):.0f} mm, "
        f"place fingertips {1000 * (place_low_fingertips - keeper_top):.0f} mm, "
        f"pulley crowns {1000 * (crown_y - fence_y1):.1f} mm, "
        f"frame rail {1000 * (fence_n_x0 - rail_inner):.1f} mm"
    )
    print(f"containment selftest ok ({checks} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
