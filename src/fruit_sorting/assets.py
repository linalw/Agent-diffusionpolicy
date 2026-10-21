"""Asset locations and robot constants."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

# The Isaac Sim 6.0 public asset root. Set FRUIT_ASSET_ROOT to point at a local
# mirror or a Nucleus server instead.
ASSET_ROOT = os.environ.get(
    "FRUIT_ASSET_ROOT",
    "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.0",
)


def isaac_asset(rel_path: str) -> str:
    return f"{ASSET_ROOT}/Isaac/{rel_path.lstrip('/')}"


# --------------------------------------------------------------------------- #
# OpenArm bimanual: an open-source humanoid upper-body dual-arm platform with
# 2x 7-DoF arms and a 1-DoF parallel gripper per arm.
#   https://github.com/enactic/openarm
#
# `FRUIT_ROBOT_USD` swaps in a *flattened* local copy of the asset. The shipped
# asset is instanced, and its finger `collisions/` subtree is an instance proxy:
# PhysX never parses the finger collision meshes (measured: the collision Xform's
# world bound is empty, while the visual mesh has geometry), and new colliders
# cannot be authored onto an instance proxy (`Cannot create prim spec ... authoring
# to an instance proxy is not allowed`). Flattening bakes the real collision meshes
# into a local USD (`assets/openarm_flat/`, 559 MB) that the scene can reference,
# which is what lets the robot's *own* fingers collide.
#
# The shipped `openarm` hand grips with those fingers (see `OpenArmHand`), so the
# local de-instanced copy is the default asset when it is present. The remote
# instanced fallback (and the remote asset generally) *cannot* serve that hand:
# its finger subtree is an instance proxy, `scene._add_finger_colliders` authors
# nothing onto it, and the hand would silently be the old "fruit floats" one.
# `assert_finger_colliders` therefore fails the build when the de-instanced asset
# could not be given colliders - see `scene.build`. For
# `FRUIT_GRIPPER_KIND=kinematic`, which brings its own pad bodies, the remote
# fallback is fine.
# --------------------------------------------------------------------------- #
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OPENARM_FLAT_USD = os.path.join(
    _REPO_ROOT, "assets", "openarm_flat", "openarm_flat_deinst.usda"
)


# --------------------------------------------------------------------------- #
# Shipped contact material for the OpenArm finger faces (v7 directive).
#
# `scene.py` authors the PhysX material from these two variables when it builds
# the cell; the measured dynamic winner (every 8/10 batch since P3-face) runs
# the compliant contact (`FRUIT_FINGER_COMPLIANCE=30000`, damping 80), which is
# what fixes the A4 strawberry crush. They are set as process defaults here -
# every entry script imports this configuration module before the scene is
# built - so the shipped scenario does not depend on the launcher; an explicit
# environment value still wins.
# --------------------------------------------------------------------------- #
os.environ.setdefault("FRUIT_FINGER_COMPLIANCE", "30000")
os.environ.setdefault("FRUIT_FINGER_CONTACT_DAMPING", "80")


def _default_robot_usd() -> str:
    override = os.environ.get("FRUIT_ROBOT_USD")
    if override:
        return override
    if os.environ.get("FRUIT_GRIPPER_KIND", "openarm") == "openarm" and os.path.exists(
        OPENARM_FLAT_USD
    ):
        return OPENARM_FLAT_USD
    return isaac_asset("Robots/OpenArm/openarm_bimanual/openarm_bimanual.usd")


OPENARM_BIMANUAL_USD = _default_robot_usd()


@dataclass(frozen=True)
class FingerColliderVerdict:
    """What `scene._add_finger_colliders` managed to author this build.

    ``enabled`` counts finger-mesh prims that got an enabled CollisionAPI,
    ``skipped`` counts those the authoring API refused (instance proxies in the
    instanced fallback), and ``roots`` counts the finger `visuals` roots found.
    The shipped `openarm` hand is only real when every found root was enabled.
    """

    enabled: int = 0
    skipped: int = 0
    roots: int = 0

    @property
    def ok(self) -> bool:
        return self.enabled > 0 and self.skipped == 0


class FingerColliderError(RuntimeError):
    """`openarm` hand with no finger colliders - the build must not continue."""


def finger_collider_failure(
    verdict: FingerColliderVerdict, asset_path: str
) -> str | None:
    """The fail-fast message for a bad verdict, or None when the hand is real.

    Simulator-free so the guard logic is testable offline
    (`scripts/432_finger_collider_guard_test.py`). The P1 gate found that on a
    fresh checkout the 1.1 GB de-instanced asset is missing, the instanced
    fallback is selected, its finger collision subtree is an instance proxy
    PhysX never parses, and the default silently ran the old "fruit floats"
    configuration. This cannot be allowed to happen again, so the caller turns
    the message into a build failure.
    """
    if verdict.ok:
        return None
    return (
        "FRUIT_GRIPPER_KIND=openarm needs the de-instanced robot asset: the hand "
        "holds the payload only through UsdPhysics.CollisionAPI on the robot's "
        "own finger meshes, and none could be authored here (the fruit would "
        "float).\n"
        f"  asset in use:                 {asset_path}\n"
        f"  expected de-instanced asset:  {OPENARM_FLAT_USD}\n"
        f"  authoring verdict:            {verdict.enabled} collider(s) enabled, "
        f"{verdict.skipped} skipped, {verdict.roots} finger visual root(s)\n"
        "Fix one of these and re-run:\n"
        f"  * make the de-instanced asset available at the expected path, or\n"
        "  * point FRUIT_ROBOT_USD at a de-instanced copy, or\n"
        "  * run the pad hand deliberately: FRUIT_GRIPPER_KIND=kinematic."
    )


def assert_finger_colliders(verdict: FingerColliderVerdict, asset_path: str) -> None:
    """Raise `FingerColliderError` when the openarm hand got no finger colliders."""
    message = finger_collider_failure(verdict, asset_path)
    if message is not None:
        raise FingerColliderError(message)


OPENARM_ARM_JOINTS = [
    f"openarm_{side}_joint{i}" for side in ("left", "right") for i in range(1, 8)
]
OPENARM_GRIPPER_JOINTS = [
    f"openarm_{side}_finger_joint{i}" for side in ("left", "right") for i in (1, 2)
]
OPENARM_FINGER_LINKS = {
    "left": ["openarm_left_left_finger", "openarm_left_right_finger"],
    "right": ["openarm_right_left_finger", "openarm_right_right_finger"],
}
OPENARM_TCP_LINKS = {"left": "openarm_left_ee_tcp", "right": "openarm_right_ee_tcp"}

# Gripper stroke sampled from the joint limits logged by scripts/02_load_robot.py.
OPENARM_FINGER_JOINT_MAX = 0.044


@dataclass
class SceneConfig:
    """Geometry of the sorting cell, in meters, with the robot at the origin.

    The robot faces ``+X``. The main conveyor runs along ``Y``, **across the
    robot's front**, so the robot stands beside the line like a worker; fruit
    travel along ``-Y`` past the pick station at ``(pick_x, pick_y)``. Two
    output conveyors, one per side and raised above the main belt, take the
    sorted fruit away along ``+X``.

    Dimensions were calibrated against the real OpenArm workspace measured by
    ``scripts/12_reach_calibration.py``: shoulders at ``(0, +/-0.0935, 1.448)``
    m and a TCP reach radius of ~0.68 m (p90 0.63 m). The belt surface sits at
    ``z = 1.17`` m.
    """

    # Robot mounting. Raised so the fingertips (which hang 0.076 m below the jaw
    # centre) reach a fruit's equator without clipping the belt: the wrist cannot
    # descend below ~1.24 m at the pick pose, so the fingertips bottom out at
    # ~1.164 m, which has to sit just above the belt surface.
    table_top_z: float = 0.79
    robot_base_z: float = 0.79
    pedestal_center_xy: tuple[float, float] = (-0.10, 0.0)
    pedestal_size: tuple[float, float] = (0.40, 0.70)

    # Conveyor.
    #
    # Layout v2: the belt runs **left-right across the robot's front** (along Y),
    # so the robot stands beside the line the way a worker does, instead of at
    # its end. Fruit travel along -Y and pass the pick station at
    # ``(pick_x, pick_y)``.
    #
    # This is the one arrangement that needs the wrist turned: the OpenArm's jaws
    # open along the shoulder axis (the robot's local Y). End-on to a belt v1
    # that axis already lay across the flow; crossing the front it would lie
    # *along* the flow, so the grasp attitude is re-solved top-down with the jaws
    # closing along X (`scripts/52_calibrate_waypoints_oriented.py`,
    # ``topdown_x``). Measured feasible before any of this was built: both arms
    # hold a straight-down tool with the jaws along X with a **2.1 mm** residual
    # at this station (scripts/97_reach_probe.py).
    #
    # The belt surface sits at z = 1.17 m: the jaw centre cannot descend much
    # below belt_top + 0.05, so fruit must sit high enough for the fingers to
    # straddle them.
    belt_center: tuple[float, float, float] = (0.34, 0.0, 1.14)
    #: (width across the line [X], length along the line [Y], thickness [Z]).
    #: Wider than v1's 0.34 m and with the guide rails off: a smooth belt wide
    #: enough that no rail is needed to keep 5-7 cm fruit on it.
    belt_size: tuple[float, float, float] = (0.46, 1.60, 0.06)
    # Commanded surface velocity, along the belt (-Y).
    #
    # The shipped default (v7 directive) is the dynamic line's measured band,
    # **0.12 m/s**: the moving catch was measured at 0.06-0.12 m/s (7-8/10, the
    # residual failures in the first-lift grip, not in the belt speed) and the
    # owner asked for the line to move ("still letting the belt stop?").
    # `FRUIT_BELT_SPEED` overrides the magnitude in m/s (the sign is the belt
    # direction); 0.06 restores the old P1 feed.
    belt_speed: float = field(
        default_factory=lambda: -abs(float(os.environ.get("FRUIT_BELT_SPEED", "0.12")))
    )
    belt_friction: float = 0.9
    #: Cleats turn the belt into a track. They travel with the belt and push
    #: fruit along, which is how a real cleated conveyor carries produce. Off by
    #: default since the belt was authored as a body and carries by friction.
    cleat_count: int = 14
    cleat_spacing: float = 0.18
    cleat_width: float = 0.022
    cleat_height: float = 0.020
    #: Fraction of the commanded surface velocity that fruit actually reach.
    transport_efficiency: float = 0.40
    #: Guide rails funnel fruit along the centre line. With the belt widened they
    #: are no longer required, and the user asked for a clear belt; `FRUIT_RAILS=1`
    #: restores them (they run along Y now).
    rails: bool = field(default_factory=lambda: os.environ.get("FRUIT_RAILS", "0") == "1")

    # Fruit spawn / removal window along the belt (Y), and the pick station.
    #: Spawn *inside* the upstream end: at 0.80 a fruit starts on the belt's very
    #: edge and half of them fall off before the line carries them (measured,
    #: logs/362: 4 of 6 released).
    spawn_y: float = 0.68
    #: Recycle *inside* the downstream end: at -0.80 a fruit reaches the very end
    #: of the belt and drops off before the recycle check catches it, which the
    #: spawner counts as `fell_off` (measured, logs/363: 4 of 6 released).
    despawn_y: float = -0.70
    #: Station X: the belt centre line and the point the hand reaches for.
    pick_x: float = 0.34
    #: Station Y: where along the line the robot picks.
    pick_y: float = 0.0
    #: Lateral scatter of a spawned fruit across the belt [X]. This is the
    #: pre-v9 fixed line's value; the shipped scattered supply
    #: (`FRUIT_SUPPLY_SCATTER=1`) draws `FRUIT_SUPPLY_LATERAL` instead (default
    #: +/-0.12 m) and falls back to this only with `FRUIT_SUPPLY_SCATTER=0`.
    lateral_jitter: float = 0.005
    #: Guide-rail channel half width (across the belt, X), only used with rails.
    #: Must clear the OPEN gripper (+/-0.066 m) or the fingers jam against them.
    belt_channel_x: float = 0.13
    #: Release period of the pre-v9 fixed line (0.19 m of travel at 0.12 m/s).
    #: The scattered supply replaces it with a sampled `FRUIT_SUPPLY_GAP_*` of
    #: belt travel; this remains the `FRUIT_SUPPLY_SCATTER=0` fallback.
    spawn_period_s: float = 1.6

    #: Jaw-centre height above the belt at the pick pose, in metres. The wrist
    #: cannot descend much with the jaws across the belt and the tool straight
    #: down (measured minimum ~belt_top + 0.08 at the station,
    #: scripts/97_reach_probe.py: 2.1 mm residual at +0.095, 22 mm at +0.06), so
    #: the pick pose is aimed here and the *pads* - which are placed on the fruit's
    #: measured centre by the kinematic gripper - do the grasping.
    grasp_clearance: float = field(
        default_factory=lambda: float(os.environ.get("FRUIT_GRASP_Z", "0.095"))
    )

    # Pick nest. The jaw centre cannot descend below about belt_top + 0.05 m
    # (measured in scripts/63_grasp_reach.py; the pads are centred on the jaw
    # centre and the arm runs out of workspace), so a fruit lying on the belt has
    # its equator *below* the pad band and the pads close on its shoulder and
    # squeeze it out. A narrow ridge raises the fruit's equator into the band.
    # It has to be narrower than the fruit so the fingers can pass on both sides:
    # the pads close at +-d/2 in y, the ridge is +-0.007 m.
    #: Pick-platform height. 0.015 m is enough to bring a fruit's equator into the
    #: pad band while staying below the fingertips. Set FRUIT_NEST=0.015 for
    #: physical grasping; 0 keeps the plain belt.
    nest_height: float = field(default_factory=lambda: float(os.environ.get("FRUIT_NEST", "0")))
    #: Ridge half width. Keep it below the fruit's radius so the pads can pass on
    #: both sides (FRUIT_NEST_WIDTH raises it to make a wide platform instead).
    nest_half_width_y: float = field(
        default_factory=lambda: float(os.environ.get("FRUIT_NEST_WIDTH", "0.010"))
    )
    nest_length_x: float = 0.16
    nest_ramp_length_x: float = 0.14
    # Output conveyors. Two short belts, one on each side of the robot and
    # *above* the main belt, running along +X: the robot lifts the fruit off the
    # main line and sets it down on the moving line beside it, which then carries
    # it away. This replaces the old pair of output bins (a pop-up pick lifter
    # and a belt gate had propped up that layout; both are gone).
    #
    # Clearances (measured/derived against the shipped geometry, reported by
    # scripts/422_v3_layout_probe.py and by the builder messages):
    #   * underside (1.30) over the main belt top (1.17): 13 cm;
    #   * underside over the tallest fruit on the main belt (7 cm -> 1.24): 6 cm;
    #   * inner edge (y=0.425) clear of the robot pedestal (y=+-0.35): 7.5 cm;
    #   * the -X support legs stand 10 mm clear of the main belt's side frame
    #     rail (face-to-face) and 34.5 mm clear of the slab; the +X pair is inset
    #     under the belt so the discharge chute at the end face is clear;
    #   * each belt discharges at +X over a chute into a tray (below).
    #: Lateral offset of each belt centre from the robot (Y). Sides are index 0
    #: (+Y, left arm) and index 1 (-Y, right arm), matching the old bin labels.
    output_belt_y: float = 0.55
    #: Belt surface height. The main belt top is 1.17, so the raised line runs
    #: 18 cm above the line the robot picks from.
    output_belt_top_z: float = 1.35
    #: Centre along X. The belt is long enough that the release point (below)
    #: sits over the upstream half and the fruit still has 0.5-0.7 m of travel.
    output_belt_center_x: float = 0.65
    #: (length along X - the carrying direction, width along Y, thickness Z).
    output_belt_size: tuple[float, float, float] = (1.10, 0.25, 0.05)
    #: Surface velocity along +X, away from the robot's working side. Defaults to
    #: the main belt's speed (the raised output line must not be slower than the
    #: line feeding it, or placed fruit back up at the release point);
    #: `FRUIT_OUTPUT_SPEED` overrides it explicitly.
    output_belt_speed: float = field(
        default_factory=lambda: float(os.environ.get("FRUIT_OUTPUT_SPEED", "0.10"))
    )
    output_belt_friction: float = 0.9
    #: Where the robot releases, relative to the belt: `output_place_x` along the
    #: belt, `output_place_y` across it, `output_place_clearance` above the
    #: surface. This is the **transfer waypoint** the carry leg ends at (the
    #: OpenArm finger plates need the height to clear the rail while crossing it);
    #: on the shipped line the hand then descends with the payload to the
    #: finger-limited clearance before the jaws open (`tasks.py::_place_low`,
    #: `FRUIT_PLACE_LOW`), so the *released* height is measured, not this number.
    #: **Not** the belt centre: the measured TCP reach is 0.678 m from
    #: the shoulder (scripts/12_reach_calibration.py) and IK measured
    #: (`scripts/422_v3_layout_probe.py`, `logs/422/423`) shows the release point
    #: at the centre (0.65, +-0.55) leaves a 211 mm residual and even (0.43, +-0.55)
    #: 13-40 mm; the reach boundary at this height sits at about
    #: `y_off = 0.41` from the shoulder (y = +-0.50). The place point is
    #: therefore pulled towards the robot, and the belt carries the fruit the
    #: rest of the way.
    output_place_x: float = field(
        default_factory=lambda: float(os.environ.get("FRUIT_OUTPUT_PLACE_X", "0.43"))
    )
    output_place_y: float = field(
        default_factory=lambda: float(os.environ.get("FRUIT_OUTPUT_PLACE_Y", "0.50"))
    )
    output_place_clearance: float = 0.10

    # Discharge at the +X end of each output belt. A placed fruit is carried to
    # the end of the belt; without anything there it fell to the floor and the
    # spawner counted that as `fell_off`. Real line hardware ends the belt in a
    # chute over a collection tray, so that is what is built here: a short steep
    # sheet from the belt's top corner into a shallow tray on a stand. Nothing
    # moves the fruit except gravity and contact; the spawner only classifies the
    # outcome (`FruitSpawner.update`: a fruit settled in the tray is `discharged`,
    # a normal end-of-line event, not `fell_off`).
    #:
    #: Chute angle from horizontal and the height of its lower edge [m]. 55 deg
    #: slides every fruit in the pool (worst kinetic friction 1.05, tan 55 =
    #: 1.43) and the lower edge sits above the tray rim, so the chute never
    #: touches the tray.
    output_chute_angle_deg: float = 55.0
    output_chute_end_z: float = 1.12
    #: Outer tray footprint (x, y), floor top, wall height and the stand under
    #: it [m]. The tray floor sits at 0.92 so the discharge is compact and inside
    #: the observer camera's view; the walls are shallow (0.14).
    output_tray_center_x: float = 1.65
    output_tray_size: tuple[float, float] = (0.60, 0.34)
    output_tray_floor_top_z: float = 0.92
    output_tray_wall_height: float = 0.14
    output_tray_wall_thickness: float = 0.02
    output_tray_stand_height: float = 0.90
    #: Sheet-steel chute friction; the tray is a coarser surface so fruit stop.
    output_chute_friction: float = 0.25
    output_tray_friction: float = 0.50
    #: Seconds a fruit must sit (nearly) still in the tray before the spawner
    #: recycles it. Long enough for a clip to show that it landed and stayed.
    output_tray_dwell_s: float = field(
        default_factory=lambda: float(os.environ.get("FRUIT_TRAY_DWELL_S", "3.0"))
    )

    # Output-belt support legs and the main belt's side frame rail. The legs
    # stand clear of the rail: `output_belt_inner_leg_x` is derived from the rail's
    # outer face, and `OutputBelt.build` prints the true face clearance. (An
    # earlier placement put the -X leg's x-span through the rail by 14.5 mm - both
    # visual-only, but the render showed it and the audit claimed a clearance.)
    output_belt_leg_size: float = 0.05
    main_frame_rail_offset: float = 0.012
    main_frame_rail_width: float = 0.025

    # Head camera (single RGB-D camera mounted on a short mast above the torso,
    # standing in for a humanoid head). It looks across and slightly upstream of
    # the belt, so incoming fruit and the station are both in frame.
    head_camera_z: float = 2.00
    head_camera_forward: float = 0.05
    head_camera_target: tuple[float, float, float] = (0.34, 0.22, 1.10)
    camera_focal_length: float = 0.016  # 16 mm on a meter stage
    camera_aperture: tuple[float, float] = (0.036, 0.02025)
    camera_resolution: tuple[int, int] = (480, 848)  # (height, width)

    # Fruit population
    num_fruits: int = 16
    #: Optional size restriction for focused experiments: "small" limits the pool
    #: to the 2-4.5 cm classes (strawberry/lychee/small kiwi), "large" to >= 5 cm.
    size_filter: str = field(default_factory=lambda: os.environ.get("FRUIT_SIZE_FILTER", ""))
    fruit_dimensions: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            # name -> (min diameter m, max diameter m)
            #
            # Capped at 7 cm: the OpenArm gripper's finger faces are only 7.6 cm
            # apart at full opening, so larger fruit need a wider gripper. The
            # design targets 2-9 cm; the simulation pool covers what the hardware
            # in the asset catalogue can actually hold.
            "strawberry": (0.030, 0.045),
            "lychee": (0.028, 0.038),
            "kiwi": (0.050, 0.068),
            "tomato": (0.050, 0.068),
            "apple": (0.062, 0.070),
            "orange": (0.060, 0.070),
            "peach": (0.058, 0.070),
            "pear": (0.058, 0.070),
        }
    )
    grades: tuple[str, ...] = ("A", "B", "C")

    def __post_init__(self) -> None:
        """Apply the optional size restriction to the fruit pool."""
        if "FRUIT_OUTPUT_SPEED" not in os.environ:
            # The output line must keep up with the main belt: a slower raised
            # belt lets placed fruit queue at the release point (P2 plan).
            self.output_belt_speed = max(self.output_belt_speed, abs(self.belt_speed))
        if self.size_filter == "small":
            keep = ("strawberry", "lychee", "kiwi", "tomato")
            self.fruit_dimensions = {
                name: (lo, min(hi, 0.045))
                for name, (lo, hi) in self.fruit_dimensions.items()
                if name in keep and lo < 0.045
            }
        elif self.size_filter == "large":
            self.fruit_dimensions = {
                name: (max(lo, 0.055), hi)
                for name, (lo, hi) in self.fruit_dimensions.items()
                if hi >= 0.055
            }

    # ------------------------------------------------------------------ #
    # Output-line geometry (derived)
    # ------------------------------------------------------------------ #
    @property
    def output_belt_drop_points(self) -> tuple[tuple[float, float], ...]:
        """Release points (x, y) of the two output belts: 0 = +Y, 1 = -Y."""
        return (
            (float(self.output_place_x), float(self.output_place_y)),
            (float(self.output_place_x), -float(self.output_place_y)),
        )

    @property
    def output_place_z(self) -> float:
        """Pad-centre height the fruit is released from [m]."""
        return float(self.output_belt_top_z) + float(self.output_place_clearance)

    @property
    def output_belt_x_range(self) -> tuple[float, float]:
        half = float(self.output_belt_size[0]) / 2.0
        return (
            float(self.output_belt_center_x) - half,
            float(self.output_belt_center_x) + half,
        )

    def on_output_belt(self, position, margin: float = 0.06) -> bool:
        """Is `position` on (or within `margin` of) either output belt?"""
        x = float(position[0])
        y = abs(float(position[1]))
        z = float(position[2])
        x0, x1 = self.output_belt_x_range
        half_width = float(self.output_belt_size[1]) / 2.0
        return (
            x0 - margin <= x <= x1 + margin
            and abs(y - float(self.output_belt_y)) <= half_width + margin
            and z >= float(self.output_belt_top_z) - margin
        )

    # ------------------------------------------------------------------ #
    # Output-line discharge (derived)
    # ------------------------------------------------------------------ #
    @property
    def output_belt_end_x(self) -> float:
        """x of each belt's +X end face (the discharge lip)."""
        return float(self.output_belt_center_x) + float(self.output_belt_size[0]) / 2.0

    @property
    def output_belt_inner_leg_x(self) -> float:
        """x of the centre of the -X support leg.

        Placed so the leg's outer face clears the main belt's side frame rail
        (whose outer face sits at `rail centre - half width`) by 10 mm. The
        earlier placement was outside the *slab* but inside the rail's x-span
        and passed through it by 14.5 mm.
        """
        rail_centre = (
            float(self.belt_center[0])
            - float(self.belt_size[0]) / 2.0
            - float(self.main_frame_rail_offset)
        )
        rail_outer_face = rail_centre - float(self.main_frame_rail_width) / 2.0
        return rail_outer_face - 0.010 - float(self.output_belt_leg_size) / 2.0

    @property
    def output_belt_outer_leg_x(self) -> float:
        """x of the centre of the +X support leg.

        Inset under the belt (50 mm of face to the end face) so the discharge
        chute, which starts at the end face, is clear of it.
        """
        return self.output_belt_end_x - 0.075

    @property
    def output_chute_top(self) -> tuple[float, float]:
        """(x, z) of the chute's upper edge: the belt's end face, 6 mm below the top.

        The sheet's upper edge is flush with the belt's end-face plane and 6 mm
        below the belt top, so there is no seam gap at the transfer. Its lower
        upstream corner then tucks ~5 mm under the belt (inside the belt slab's
        end volume, invisible; measured on the built stage, `logs/484`). That tuck
        is deliberate: the first build sat the edge 10 mm downstream at belt-top
        height, and a 2.8 cm fruit wedged in the open seam and stalled (probe
        `logs/478`). Both colliders are non-dynamic, so the overlap produces no
        solver response.
        """
        return (self.output_belt_end_x, float(self.output_belt_top_z) - 0.006)

    @property
    def output_chute_bottom(self) -> tuple[float, float]:
        """(x, z) of the chute's lower edge, above the tray rim."""
        run = (float(self.output_belt_top_z) - float(self.output_chute_end_z)) / math.tan(
            math.radians(float(self.output_chute_angle_deg))
        )
        return (self.output_chute_top[0] + run, float(self.output_chute_end_z))

    def on_output_discharge(self, position, margin: float = 0.05) -> bool:
        """Is `position` on either output belt's discharge chute or tray?

        Used to suppress the `fell_off` classification: a fruit sliding down the
        chute or resting in the tray is on the line's end hardware, not on the
        floor. The z band starts at the tray floor, so a fruit that *misses* the
        hardware and lands on the floor still counts as fallen.
        """
        x = float(position[0])
        y = float(abs(position[1]) - float(self.output_belt_y))
        z = float(position[2])
        x1 = float(self.output_tray_center_x) + float(self.output_tray_size[0]) / 2.0 + margin
        half_y = float(self.output_tray_size[1]) / 2.0 + margin
        return (
            self.output_belt_end_x - 0.05 <= x <= x1
            and abs(y) <= half_y
            and float(self.output_tray_floor_top_z) - margin <= z
            <= float(self.output_belt_top_z) + 0.05
        )

    def on_output_tray(self, position, margin: float = 0.04) -> bool:
        """Is `position` inside either discharge tray (between hull and rim)?"""
        x = float(position[0])
        y = float(abs(position[1]) - float(self.output_belt_y))
        z = float(position[2])
        half_x = float(self.output_tray_size[0]) / 2.0 - float(self.output_tray_wall_thickness)
        half_y = float(self.output_tray_size[1]) / 2.0 - float(self.output_tray_wall_thickness)
        rim = float(self.output_tray_floor_top_z) + float(self.output_tray_wall_height)
        return (
            abs(x - float(self.output_tray_center_x)) <= half_x + margin
            and abs(y) <= half_y + margin
            and float(self.output_tray_floor_top_z) - margin <= z <= rim + margin
        )

    #: Largest object the OpenArm 1-DoF parallel gripper can straddle. Measured
    #: at the pick pose (scripts/36_static_grasp.py): the link origins are
    #: 0.098 m apart at full opening, which leaves 0.0758 m between the finger
    #: faces. Keep a small margin for off-centre fruit.
    gripper_max_object: float = 0.072

    #: Distance from the jaw centre down to the fingertips. Put the fingertips at
    #: the fruit's equator and the fingers straddle it.
    finger_length: float = 0.076
    grasp_palm_offset: float = 0.076
