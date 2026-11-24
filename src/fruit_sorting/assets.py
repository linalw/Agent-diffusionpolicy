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


#: P227: the **single gripper arm** option (`FRUIT_ARM_KIND=franka`). The
#: Franka Emika Panda ships with the public Isaac asset pack (a 7-DoF arm + the
#: 2-finger `panda_hand`, reach 0.855 m) and is the arm most of the tactile /
#: diffusion-grasping papers use; the measured asset read is
#: `logs/p226/franka_probe.log` (9 DOFs: `panda_joint1..7` + `panda_finger_joint1/2`;
#: links `panda_link0..7`, `panda_hand`, `panda_leftfinger`, `panda_rightfinger`).
FRANKA_USD = os.environ.get(
    "FRANKA_USD",
    isaac_asset("Robots/FrankaRobotics/FrankaPanda/franka.usd"),
)


def robot_kind() -> str:
    """Which arm the scene authors: `openarm` (shipped) or `franka`."""
    kind = os.environ.get("FRUIT_ARM_KIND", "openarm").strip().lower()
    if kind not in ("openarm", "franka"):
        raise ValueError(f"FRUIT_ARM_KIND={kind!r}: expected 'openarm' or 'franka'")
    return kind


#: How far the output-belt side rails' box bottom sits *inside* the slab [m]
#: (`conveyor.OutputBelt.build` authors the bottom at `belt_top - this`), so the
#: shipped 0.05 m rail stands 3.5 cm proud of the belt surface. One number, two
#: readers: the builder (`conveyor.py`) and the payload-clearance report
#: (`tasks._payload_clearance`), which used to hard-code the resulting 0.035 and
#: was therefore blind to `FRUIT_OUTPUT_RAIL_HEIGHT` and to a removed rail (P70).
OUTPUT_RAIL_INSET: float = 0.015

# --------------------------------------------------------------------------- #
# P123: the third output body (`FRUIT_OUTPUT_LANES=3`, default off)
#
# A destination is a physical output body - a belt + chute + tray - and the
# shipped cell has two (`logs/p122/SPEC.md` R0/R2). These are the measured
# numbers of the third, chosen by `logs/p123/METHOD.md` section 3 and pinned by
# `logs/p123/PREREG.md`; the comment on `SceneConfig.output_lanes` says why each
# one is load-bearing. **P127: the flip was tried and reverted a second time** - the
# 20-attempt battery reads 44/80 on three lanes against 58/80 on two (4/4 seeds
# worse); 3 stays opt-in.
# --------------------------------------------------------------------------- #
#: |y| band of the third slab (the inboard side of the -Y belt, 30 mm of air).
OUTPUT_LANE3_BELT_Y: tuple[float, float] = (0.280, 0.395)
#: Its x range: upstream end 0.480 keeps every place transit upstream of the body.
OUTPUT_LANE3_BELT_X: tuple[float, float] = (0.480, 1.200)
#: The commanded release point (the delivered point is +48 mm x, -35 mm y of it).
OUTPUT_LANE3_PLACE: tuple[float, float] = (0.480, -0.300)
#: Its own tray's |y| band (0.14 m wide, 50 mm clear of the narrowed -Y tray).
OUTPUT_LANE3_TRAY_Y: tuple[float, float] = (0.260, 0.400)
#: The -Y tray's half width when the third lane takes 50 mm of its 0.34 m.
OUTPUT_LANE1_TRAY_HALF_WITH_THIRD: float = 0.100


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


def _belt_upstream_extension() -> float:
    """P225t: the belt's **upstream** extension [m] (`FRUIT_BELT_UPSTREAM`).

    Measured boundary this prices: the belt's transit is 1.60 m / 0.12 m·s^-1 =
    **13.3 s** (the fruit's spawn-to-despawn window), while a direct episode is
    7-11 s, and the acquisition failures are end-of-line (`[fall]
    y = -0.86..-0.90`) or a joint-limit chase. Extending the belt on its
    **upstream** side keeps the downstream end (the despawn line at -0.70) and
    the station fixed, so every window, floor and reach term is unchanged; the
    fruit simply spawns `d` metres farther back and the selector has `d` metres
    more runway. It is a scene change (the belt's collider grows), so the default
    is 0 (the shipped scene, byte for byte) and a nonzero value is a measured
    cell - it owes both motion references and a store re-baseline if shipped.
    """
    try:
        return max(0.0, float(os.environ.get("FRUIT_BELT_UPSTREAM", "0") or 0.0))
    except Exception:  # noqa: BLE001 - a malformed value is the shipped scene
        return 0.0


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
    belt_center: tuple[float, float, float] = field(
        default_factory=lambda: (0.34, 0.5 * _belt_upstream_extension(), 1.14)
    )
    #: (width across the line [X], length along the line [Y], thickness [Z]).
    #: Wider than v1's 0.34 m and with the guide rails off: a smooth belt wide
    #: enough that no rail is needed to keep 5-7 cm fruit on it.
    belt_size: tuple[float, float, float] = field(
        default_factory=lambda: (0.46, 1.60 + _belt_upstream_extension(), 0.06)
    )
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
    spawn_y: float = field(
        default_factory=lambda: 0.68 + _belt_upstream_extension()
    )
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
    #   * underside over the tallest fruit on the main belt (P32 phase 3: the
    #     pear body, 8.4 cm = 1.20 W, -> 1.254): 4.6 cm *nominal* (4.0 cm at
    #     the meshes' 1.06 x 1.01 per-instance bound); 1.4 cm against the 3.2 cm
    #     stem bound (`meshes.fruit_height`/`stem_over_top`/`INSTANCE_SCALE_MAX`);
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
    #:
    #: `FRUIT_OUTPUT_BELT_TOP_Z` (P70, default 1.35 = the shipped geometry,
    #: byte-inert) lowers the **whole** output station: the slab moves 1:1
    #: (`conveyor.OutputBelt.build`: the slab, both rails - whose bottom is
    #: `top - OUTPUT_RAIL_INSET` - the support legs and the chute), and every
    #: derived height in this file moves with it (`output_place_z`, i.e. the
    #: place *transfer* pose, the release height of `tasks._place_low`, the
    #: chute top, the discharge envelope, the `on_output_belt` z test and the
    #: place-trace floor). The **main** belt, the pick station and the lift's
    #: base (`main belt top + 0.28 + dz`) do not move, so a lower output line
    #: lengthens the place leg's descent and changes the place transit's
    #: straight line - see `logs/p70/RESULTS.md` for the sign of the crossing.
    #: The **binding audit** is the slab's underside over the main belt: at the
    #: shipped 1.35 it clears the tallest pear body by 46 mm nominal / 40 mm at
    #: the 1.0706 instance scale (`conveyor.OutputBelt.build`'s print), so the
    #: auditing budget is 40 mm of lowering before a main-belt fruit touches it.
    output_belt_top_z: float = field(
        default_factory=lambda: float(os.environ.get("FRUIT_OUTPUT_BELT_TOP_Z", "1.35"))
    )
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
    #: Which of each output belt's two side rails is authored (P30-A).
    #:
    #: ``both`` - a 25 mm thick, 50 mm tall keeper along X at *each* edge of each
    #:   output belt. The inner one's outer face is flush with the slab's inner
    #:   edge (|y| = 0.425) and stands 35 mm above the belt top, so it is the hard
    #:   edge the payload crosses on its way to the release. This was the shipped
    #:   geometry up to P71; ``FRUIT_OUTPUT_RAILS=both`` still restores it.
    #: ``outer`` - drop the robot-side rail, keep the far-side one.
    #: ``inner`` - the mirror image, for completeness.
    #: ``none`` - **the shipped default since P71**: no rail on either edge. The
    #:   payload's crossing surface falls through to the slab's inboard top edge,
    #:   i.e. the belt top plane (`tasks._payload_clearance` reports it as
    #:   `@obelt`), which is the rail box's `0.05 - 0.015` proud height measured
    #:   1:1: **+35 mm at an identical crossing tick** (`logs/p70/RESULTS.md` §3,
    #:   the same 5.6 cm kiwi on the same arm: `+30 @rail / t275` ->
    #:   `+65 @obelt / t275`), and behaviourally inert on that scenario (same
    #:   placed count, no contact signature; `logs/p71/RESULTS.md`).
    #:
    #: **Why the default moved (P71)**: the low direct lift (`FRUIT_LIFT_DZ=-0.08`
    #: above `tasks.jaw_target`'s `belt_top + 0.28`, i.e. `belt_top + 0.20`) is
    #: the only measured lever that fixes the left arm's 25 deg carry rotation
    #: (`logs/p66/P3_RESULTS.md`: left placed 0/25 -> 14/25 at N = 5), and it
    #: failed the +33 mm crossing floor at the rail (`+5 / +0 mm`). Removing the
    #: rail is **1:1** with the crossing while the belt height is only **0.175:1**
    #: and costs placements (`logs/p70/RESULTS.md` §2), so the rail is the lever
    #: that lets both ship.
    #:
    #: **What removal gives up**: the ledge a short release lands on (96.6 %
    #: placed over the 234 logged releases that land on its top face, vs 47.6 %
    #: for releases inboard of it - `logs/p30a/RESULTS.md`). That class is
    #: **not exercised** on the shipped scenarios: 16/16 in-hand releases sit
    #: 116-122 mm outboard of the slab's inner edge, 0 in the ledge band
    #: (`logs/p70/RESULTS.md` §4). A scenario that *does* land releases there gets
    #: a fall instead of a park, and the G2 fixture for it is registered, not run
    #: (`logs/p69/B_PREREG.md` §8).
    output_rails: str = field(
        default_factory=lambda: os.environ.get("FRUIT_OUTPUT_RAILS", "none").strip().lower()
    )
    #: Output-belt side-rail height above the rail box's bottom [m]. The box's
    #: bottom sits 15 mm inside the slab, so the shipped 0.05 stands 35 mm proud
    #: of the belt top. ``FRUIT_OUTPUT_RAIL_HEIGHT`` lowers the containment
    #: without removing it; the payload-clearance report in `tasks.py`
    #: (`_payload_clearance`) assumes the shipped 0.035 m, so a lowered rail is
    #: reported conservatively (it is a report, not a gate).
    output_rail_height: float = field(
        default_factory=lambda: float(os.environ.get("FRUIT_OUTPUT_RAIL_HEIGHT", "0.05"))
    )
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
        default_factory=lambda: float(
            os.environ.get(
                "FRUIT_OUTPUT_PLACE_X",
                "-0.10" if os.environ.get("FRUIT_OUTPUT_BINS", "0").strip() == "1" else "0.43",
            )
        )
    )
    output_place_y: float = field(
        default_factory=lambda: float(
            os.environ.get(
                "FRUIT_OUTPUT_PLACE_Y",
                "0.55" if os.environ.get("FRUIT_OUTPUT_BINS", "0").strip() == "1" else "0.50",
            )
        )
    )
    output_place_clearance: float = 0.10

    # ------------------------------------------------------------------ #
    # P226: the **side-bin** layout (`FRUIT_OUTPUT_BINS=1`, default off).
    #
    # The owner's cell: one gripper arm, a bin on each side of the robot
    # instead of the two raised output belts - which is also what removes the
    # belts' shadow over the approach. The pose is **measured**, not guessed:
    # P90's own NAT probe over x -0.10..0.05, |y| 0.40..0.65, z 1.05/1.20 puts
    # the best cell at `x = -0.10, |y| = 0.60, z = 1.20` with **6.0 mm** residual
    # and **+0.405 rad** joint margin (all four over-belt cells at that height
    # were 105-225 mm; the side of the robot is where this arm has workspace).
    # The bins sit behind the head camera's x (=0.05), so they do not shade the
    # belt at all. Floor 0.95, rim 1.15 (below the belt's fruit top, 1.20);
    # the release is at `output_place_z` 1.20 (the jaw), so the payload drops
    # 0.05 m past the rim onto the bin floor.
    # ------------------------------------------------------------------ #
    output_bins: bool = field(
        default_factory=lambda: os.environ.get("FRUIT_OUTPUT_BINS", "0").strip() == "1"
    )
    #: P227: the side-bin geometry **at the height the Panda can reach**. The
    #: first pass put the floor at 0.95 / rim 1.15 and the place jaw at 1.20, but
    #: the arm's jaw stays 130-200 mm high there (the position-only IK cannot
    #: descend at those poses; `logs/p226/bin_height_grid.log`). The grid at
    #: z 1.25/1.32 passes **every** cell at 2.6-2.9 mm with 0.46-1.27 rad
    #: margin, so the bins move up: floor 1.10, rim 1.26 (a shallow tray, the
    #: hand's pads sit inside its mouth at the release), place jaw 1.30.
    bin_center_x: float = -0.10
    bin_center_y: float = 0.55
    bin_size: tuple[float, float] = (0.34, 0.30)
    bin_floor_top_z: float = 1.10
    #: P227ac **owner decision C (2026-11-24): a SHALLOW rim.** With the place
    #: height taken from the bin's own floor (decision B) the accompanied descent
    #: puts the fingertips at `floor + 0.040..0.055`, i.e. **1.140-1.155** - so a
    #: 0.16 m wall (rim 1.26) meant the hand went 10.5-12.0 cm below the rim on
    #: every place. A **0.030 m** wall (rim **1.13**) sits just under the lowest
    #: fingertip, so the hand stays at or above the rim while the payload still
    #: descends to 3.8-3.9 cm above the floor: the free fall stays ~0.04 m and the
    #: pads no longer enter the box. `FRUIT_BIN_WALL_HEIGHT` restores the deep form
    #: (e.g. 0.16) for a cell that wants it.
    bin_wall_height: float = field(
        default_factory=lambda: float(
            os.environ.get("FRUIT_BIN_WALL_HEIGHT", "0.03") or 0.03
        )
    )

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

    #: **The third output body** (`FRUIT_OUTPUT_LANES=3`; default 2 = the shipped
    #: scene, byte for byte, no body authored - P127 kept it off). P123: a destination is a
    #: *physical* output body - a belt + chute + tray (`logs/p122/SPEC.md` R0) - so
    #: a third destination is a scene build. The measured winner of
    #: `logs/p123/METHOD.md` section 3 is a third line **inboard on -Y** with its
    #: slab **x-offset downstream**, and both terms are load-bearing:
    #:
    #: * `|y| 0.280..0.395` is the inboard band P90's `NAT` (position-only) solve
    #:   covers at x 0.43-0.48 - the reach box's inner half; the shipped slab's
    #:   inner edge is 0.425, so the two belts leave 30 mm of air, and a pool fruit
    #:   (29.6 mm at the smallest) cannot pass between them.
    #: * `x 0.480..1.200` puts every place transit **upstream** of the new body:
    #:   the payload (which hangs `+48 mm` downstream of the jaw, `logs/p122`) is
    #:   at x 0.436 at the worst moment it crosses the lane's y band, 44 mm
    #:   upstream of the belt's edge. So the third body is never a transit
    #:   obstacle - neither for the scripted transfer (horizontal at the transfer
    #:   height) nor for the direct low lift (which loses `0.30 mm` of clearance
    #:   per mm inboard, P90 `COST.md` section 1, and would have paid 44 mm) - and
    #:   it is also downstream of the supplied fruit's x band (0.148..0.413), so
    #:   it adds no camera occlusion of the arrival (the P35/P36 lever).
    #: * place `(0.480, -0.300)`: the delivered point is `+0.048 x / -0.035 y`
    #:   from it, i.e. (0.528, -0.336), 56/59 mm inside the 0.115 m slab - 7 sd of
    #:   the measured spread - and 48 mm downstream of the slab's upstream edge.
    #: * its own **tray** (0.14 m wide, x 1.35..1.95, |y| 0.260..0.400) sits 50 mm
    #:   from the shipped -Y tray, which therefore narrows from 0.34 to 0.20 m
    #:   (centred) when the third lane is on. A third *target* on an existing belt
    #:   is the same destination (`logs/p122/SPEC.md` R2); a third *tray* is one.
    output_lanes: int = field(
        default_factory=lambda: int(os.environ.get("FRUIT_OUTPUT_LANES", "2"))
    )

    # Head camera (single RGB-D camera mounted on a short mast above the torso,
    # standing in for a humanoid head). It looks across and slightly upstream of
    # the belt, so incoming fruit and the station are both in frame.
    #: P144: an optional **explicit** head-camera eye. ``None`` keeps the shipped
    #: `(head_camera_forward, 0, head_camera_z)`; `FRUIT_HEAD_CAMERA` can pick a
    #: measured alternative (see `head_camera_override`).
    head_camera_eye: tuple[float, float, float] | None = None
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
        # P114: the scenario descriptor's geometry, when armed. Unset
        # (`FRUIT_SCENARIO` absent) is one environment lookup and nothing else,
        # so every shipped/probe construction is byte-identical. The descriptor
        # can only move the *data* fields a new pipeline would otherwise edit
        # here (the station and the release point); the lane hardware (the two
        # output belts, the tray, the camera) is still built by the scene code -
        # that is the honest boundary and `logs/p114/COUPLING.md` names it.
        from .scenario import resolve_scenario

        scenario = resolve_scenario()
        if scenario is not None:
            if "x" in scenario.pick:
                self.pick_x = float(scenario.pick["x"])
            if "y" in scenario.pick:
                self.pick_y = float(scenario.pick["y"])
            if "speed_m_s" in scenario.belt:
                self.belt_speed = -abs(float(scenario.belt["speed_m_s"]))
            if "x" in scenario.place:
                self.output_place_x = float(scenario.place["x"])
            if "y" in scenario.place:
                self.output_place_y = float(scenario.place["y"])
        if "FRUIT_OUTPUT_SPEED" not in os.environ:
            # The output line must keep up with the main belt: a slower raised
            # belt lets placed fruit queue at the release point (P2 plan).
            self.output_belt_speed = max(self.output_belt_speed, abs(self.belt_speed))
        # P30-A: fail at construction (every entry script builds a SceneConfig)
        # rather than deep in `OutputBelt.build`.
        _ = self.output_rail_keep
        # P123: the third output body is a scene build; only 2 (shipped) or 3
        # lanes exist, so a typo fails here instead of authoring a half scene.
        _ = self.output_lane_layout()
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
    def output_lane_layout(self) -> tuple[dict, ...]:
        """Every output body as data: belt, place point, tray, chute, prim root.

        One reader for the builders (`conveyor.OutputBelt`, `scene`), the tests
        (`on_output_belt` / `on_output_discharge` / `on_output_tray`), the drop
        points the arms read and the store manifest (`scene_provenance`), so a
        lane cannot be half-added. With `output_lanes <= 2` the two entries are
        the shipped scalars **exactly** (same centre, size, place point, tray,
        leg x), which is what keeps the shipped scene, its prints, its `[fruit]`
        stream and its manifests byte-identical.

        The third entry (P123, `FRUIT_OUTPUT_LANES=3`) is
        :data:`OUTPUT_LANE3_*`: inboard on -Y, x-offset downstream, own tray.
        """
        lanes: list[dict] = []
        third = int(self.output_lanes) >= 3
        if int(self.output_lanes) not in (2, 3):
            raise ValueError(
                f"FRUIT_OUTPUT_LANES={self.output_lanes!r}: expected 2 (shipped) or 3"
            )
        for index, sign in ((0, 1.0), (1, -1.0)):
            half_width = float(self.output_tray_size[1]) / 2.0
            if third and index == 1:
                # the third lane's own tray needs the room: 0.34 -> 0.20 m wide
                half_width = OUTPUT_LANE1_TRAY_HALF_WITH_THIRD
            lanes.append(
                {
                    "index": index,
                    "side": "+y" if sign > 0 else "-y",
                    "sign": sign,
                    "root": f"/World/OutputBelt{'P' if sign > 0 else 'N'}",
                    "belt_center": (
                        float(self.output_belt_center_x),
                        sign * float(self.output_belt_y),
                        float(self.output_belt_top_z) - float(self.output_belt_size[2]) / 2.0,
                    ),
                    "belt_size": tuple(float(v) for v in self.output_belt_size),
                    "place": (
                        float(self.output_place_x),
                        sign * float(self.output_place_y),
                    ),
                    "tray_center": (
                        float(self.output_tray_center_x),
                        sign * float(self.output_belt_y),
                    ),
                    "tray_size": (float(self.output_tray_size[0]), 2.0 * half_width),
                    "leg_xs": (
                        float(self.output_belt_inner_leg_x),
                        float(self.output_belt_outer_leg_x),
                    ),
                }
            )
        if third:
            x0, x1 = (float(v) for v in OUTPUT_LANE3_BELT_X)
            y0, y1 = (float(v) for v in OUTPUT_LANE3_BELT_Y)
            ty0, ty1 = (float(v) for v in OUTPUT_LANE3_TRAY_Y)
            sx, _sy, sz = (float(v) for v in self.output_belt_size)
            lanes.append(
                {
                    "index": 2,
                    "side": "-y",
                    "sign": -1.0,
                    "root": "/World/OutputBelt2",
                    "belt_center": (
                        (x0 + x1) / 2.0,
                        -(y0 + y1) / 2.0,
                        float(self.output_belt_top_z) - sz / 2.0,
                    ),
                    "belt_size": (x1 - x0, y1 - y0, sz),
                    "place": (float(OUTPUT_LANE3_PLACE[0]), float(OUTPUT_LANE3_PLACE[1])),
                    "tray_center": (
                        float(self.output_tray_center_x),
                        -(ty0 + ty1) / 2.0,
                    ),
                    "tray_size": (float(self.output_tray_size[0]), ty1 - ty0),
                    # the -X leg clears the main belt's x-span (ends at 0.570):
                    # the new slab starts at 0.480, so the leg moves with it.
                    "leg_xs": (x0 + 0.020, float(self.output_belt_outer_leg_x)),
                }
            )
        return tuple(lanes)

    @property
    def output_belt_drop_points(self) -> tuple[tuple[float, float], ...]:
        """Release points (x, y) of the output bodies: 0 = +Y, 1 = -Y, [2 inboard]."""
        return tuple(tuple(float(v) for v in lane["place"]) for lane in self.output_lane_layout())

    @property
    def output_place_z(self) -> float:
        """Pad-centre height the fruit is released from [m].

        P226: with `FRUIT_OUTPUT_BINS=1` the release is at the **bin's** jaw
        height (1.20, the measured reachable cell), not above the belt; an
        explicit `FRUIT_OUTPUT_PLACE_Z` always wins.
        """
        _z = os.environ.get("FRUIT_OUTPUT_PLACE_Z", "").strip()
        if _z:
            return float(_z)
        if os.environ.get("FRUIT_OUTPUT_BINS", "0").strip() == "1":
            return 1.30
        return float(self.output_belt_top_z) + float(self.output_place_clearance)

    @property
    def output_belt_x_range(self) -> tuple[float, float]:
        half = float(self.output_belt_size[0]) / 2.0
        return (
            float(self.output_belt_center_x) - half,
            float(self.output_belt_center_x) + half,
        )

    def output_lane_of(self, position, margin: float = 0.06) -> int | None:
        """Which output belt `position` is on (or within `margin` of), else None.

        P226: with the side bins the body is the **bin's volume** (floor to rim,
        footprint + margin), so the release score and the fell_off suppression
        read the same way they do on a belt.
        """
        x = float(position[0])
        z = float(position[2])
        if os.environ.get("FRUIT_OUTPUT_BINS", "0").strip() == "1":
            hx = float(self.bin_size[0]) / 2.0 + margin
            hy = float(self.bin_size[1]) / 2.0 + margin
            for index, sign in ((0, 1.0), (1, -1.0)):
                if (
                    abs(x - float(self.bin_center_x)) <= hx
                    and abs(float(position[1]) - sign * float(self.bin_center_y)) <= hy
                    and float(self.bin_floor_top_z) - margin
                    <= z
                    <= float(self.bin_floor_top_z) + float(self.bin_wall_height) + margin
                ):
                    return index
            return None
        for lane in self.output_lane_layout():
            _cx, cy, _cz = (float(v) for v in lane["belt_center"])
            _sx, sy, _sz = (float(v) for v in lane["belt_size"])
            if (
                self.output_belt_x_range[0] - margin <= x <= self.output_belt_x_range[1] + margin
                and abs(float(position[1]) - cy) <= sy / 2.0 + margin
                and z >= float(self.output_belt_top_z) - margin
            ):
                return int(lane["index"])
        return None

    def on_output_belt(self, position, margin: float = 0.06) -> bool:
        """Is `position` on (or within `margin` of) an output belt?"""
        return self.output_lane_of(position, margin) is not None

    # ------------------------------------------------------------------ #
    # Output-line discharge (derived)
    # ------------------------------------------------------------------ #
    @property
    def output_rail_keep(self) -> tuple[bool, bool]:
        """(inner, outer): which side rail of each output belt is authored.

        ``inner`` is the robot-facing rail (the one whose outer face is flush
        with the slab's inner edge, |y| = ``output_belt_y - width/2``), ``outer``
        the far-side one. Raises on an unknown mode so a typo in
        ``FRUIT_OUTPUT_RAILS`` fails the build instead of silently authoring the
        shipped geometry (P30-A).
        """
        mode = str(self.output_rails).strip().lower()
        modes = {
            "both": (True, True),
            "outer": (False, True),
            "inner": (True, False),
            "none": (False, False),
        }
        if mode not in modes:
            raise ValueError(
                f"FRUIT_OUTPUT_RAILS={self.output_rails!r}: expected one of "
                f"{sorted(modes)}"
            )
        return modes[mode]

    @property
    def output_rail_proud(self) -> float:
        """Height of an authored rail's top above the belt surface [m].

        The box's bottom is `OUTPUT_RAIL_INSET` inside the slab, so the shipped
        ``output_rail_height = 0.05`` stands **0.035 m** proud - the number
        `tasks._payload_clearance` reports the transit clearance against. A
        lowered rail reports the lowered top (a flush rail, 0.015, reports 0.0
        and the belt surface becomes the binding one); a removed rail is not
        read from here at all (the caller tests `output_rail_keep[0]`).
        """
        return float(self.output_rail_height) - OUTPUT_RAIL_INSET

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
        """Is `position` on an output belt's discharge chute or tray?

        Used to suppress the `fell_off` classification: a fruit sliding down the
        chute or resting in the tray is on the line's end hardware, not on the
        floor. The z band starts at the tray floor, so a fruit that *misses* the
        hardware and lands on the floor still counts as fallen.
        """
        x = float(position[0])
        z = float(position[2])
        for lane in self.output_lane_layout():
            _tx, ty = (float(v) for v in lane["tray_center"])
            _sx2, sy2 = (float(v) for v in lane["tray_size"])
            x1 = float(self.output_tray_center_x) + float(self.output_tray_size[0]) / 2.0 + margin
            half_y = sy2 / 2.0 + margin
            if (
                self.output_belt_end_x - 0.05 <= x <= x1
                and abs(float(position[1]) - ty) <= half_y
                and float(self.output_tray_floor_top_z) - margin <= z
                <= float(self.output_belt_top_z) + 0.05
            ):
                return True
        return False

    def output_tray_of(self, position, margin: float = 0.04) -> int | None:
        """Which discharge tray `position` is inside (between hull and rim), else None.

        P123's tray census: with three bodies there are three trays, and "which
        tray did it end in" is the destination (`logs/p122/SPEC.md` R0). The
        shipped two-tray answer is identical to `on_output_tray`'s boolean.
        """
        x = float(position[0])
        z = float(position[2])
        wall = float(self.output_tray_wall_thickness)
        rim = float(self.output_tray_floor_top_z) + float(self.output_tray_wall_height)
        for lane in self.output_lane_layout():
            _tx, ty = (float(v) for v in lane["tray_center"])
            _sx2, sy2 = (float(v) for v in lane["tray_size"])
            half_x = float(self.output_tray_size[0]) / 2.0 - wall
            half_y = sy2 / 2.0 - wall
            if (
                abs(x - float(self.output_tray_center_x)) <= half_x + margin
                and abs(float(position[1]) - ty) <= half_y + margin
                and float(self.output_tray_floor_top_z) - margin <= z <= rim + margin
            ):
                return int(lane["index"])
        return None

    def on_output_tray(self, position, margin: float = 0.04) -> bool:
        """Is `position` inside an output belt's discharge tray (hull to rim)?"""
        return self.output_tray_of(position, margin) is not None

    #: Largest object the OpenArm 1-DoF parallel gripper can straddle. Measured
    #: at the pick pose (scripts/36_static_grasp.py): the link origins are
    #: 0.098 m apart at full opening, which leaves 0.0758 m between the finger
    #: faces. Keep a small margin for off-centre fruit.
    gripper_max_object: float = 0.072

    #: Distance from the jaw centre down to the fingertips. Put the fingertips at
    #: the fruit's equator and the fingers straddle it.
    finger_length: float = 0.076
    grasp_palm_offset: float = 0.076


# --------------------------------------------------------------------------- #
# Store provenance: the scene's collider set (P72)
# --------------------------------------------------------------------------- #
#: P144: measured head-camera alternatives. `coverage` is the fraction of a whole
#: scripted cycle (approach + grasp + place) in which the target fruit is the nearest
#: surface at its own pixel, from `logs/p143/camera_search.py` over 155 samples:
#:
#:   head_now    14.6 %   (approach 27.8, place  0.0)   <- the shipped pose
#:   down_x_160  81.4 %   (approach 83.0, place 79.5)
#:   down_high   78.8 %   (approach 85.2, place 71.1)
#:   down_x_140  68.1 %   (approach 56.8, place 75.4)
HEAD_CAMERA_POSES: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
    "head_now": ((0.05, 0.00, 2.00), (0.34, 0.22, 1.10)),
    "down_x_160": ((1.60, 0.00, 2.00), (0.34, 0.00, 1.15)),
    "down_high": ((1.20, 0.00, 2.30), (0.40, 0.00, 1.15)),
    "down_x_140": ((1.40, 0.00, 1.75), (0.34, 0.00, 1.20)),
    # P162: a **close oblique station view**. The measured limit of every pose
    # above is the fruit's pixel size: 0.9-1.5 m away it is 4-15 px in a 240x424
    # frame (and 1-4 px in the 128x128 the policy sees). At 0.55 m it is 20-40 px
    # natively - the same order as the wrist camera P135 measured at contact
    # (1684-3241 px masks), but with the whole station (fruit + both fingers +
    # the belt) in frame.
    "near_x_80": ((0.80, 0.30, 1.50), (0.33, 0.00, 1.20)),
}


def head_camera_override(cfg) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """The head camera's ``(eye, target)``, honouring `FRUIT_HEAD_CAMERA`.

    Unset resolves to the configuration's own pose, byte-identical to the shipped
    camera; an unknown name raises (a silent fallback would make a recollection
    indistinguishable from a shipped one).
    """
    explicit = getattr(cfg, "head_camera_eye", None)
    default_eye = (
        tuple(float(v) for v in explicit)
        if explicit is not None
        else (float(cfg.head_camera_forward), 0.0, float(cfg.head_camera_z))
    )
    target = tuple(float(v) for v in cfg.head_camera_target)
    name = os.environ.get("FRUIT_HEAD_CAMERA", "").strip()
    if not name:
        return default_eye, target
    if name not in HEAD_CAMERA_POSES:
        raise ValueError(
            f"FRUIT_HEAD_CAMERA={name!r} is not one of {sorted(HEAD_CAMERA_POSES)}"
        )
    eye, aim = HEAD_CAMERA_POSES[name]
    return tuple(float(v) for v in eye), tuple(float(v) for v in aim)


def _arm_provenance() -> dict:
    """The arm asset a store or checkpoint belongs to (P227t).

    `scene_provenance`'s `arm` block: the **kind**, the USD, the arm's own
    joint names (the action space's order), its finger joints/links, the TCP
    link and the jaw law. Written by the same one builder both manifest writers
    call, so a shard and a rollout manifest cannot disagree. The **shipped**
    OpenArm keeps its usual shape; a `FRUIT_ARM_KIND=franka` store names the
    Panda. A manifest **without** this key predates P227t and is an OpenArm
    store on every tree that had no other arm.
    """
    kind = robot_kind()
    usd = str(FRANKA_USD if kind == "franka" else OPENARM_BIMANUAL_USD)
    try:
        from .control import arm_specs
    except Exception:  # noqa: BLE001 - the offline manifest path has no simulator
        # `control` imports `isaacsim`; the CPU selfcheck's manifest probes run
        # without it. A *real* writer (the collector, the direct env) always has
        # it, so this branch only ever appears in an offline probe.
        return {"kind": kind, "usd": usd, "resolved": False}
    specs = arm_specs()
    spec = specs[0]
    return {
        "kind": kind,
        "usd": usd,
        "resolved": True,
        "labels": [s.side for s in specs],
        "arm_joints": list(spec.arm_joint_names),
        "finger_joints": list(spec.finger_joint_names),
        "finger_links": list(spec.finger_link_names),
        "tcp_link": str(spec.tcp_link),
        "open_value": float(spec.open_value),
        "jaw": {
            "offset": float(spec.jaw_offset),
            "per_joint": float(spec.jaw_per_joint),
            "face_offset": float(spec.finger_face_offset),
        },
    }


def scene_provenance(
    cfg,
    lift_dz: dict | None = None,
    lift_dz_defaulted: bool = False,
) -> dict:
    """The scene's **collider set**, as a store manifest's `scene` block (P72).

    P71's close-out named this as the gap: the two flips change the geometry a
    store was recorded in - `FRUIT_OUTPUT_RAILS` `both` -> `none` removes the
    two inner rail boxes from the output belts, and the low direct lift changes
    the carry height - and the collector's `[fruit]` stream moves by an 8 mm
    release `y` at the same attempt because the collider set moves the solver
    ordering (`logs/p71/RESULTS.md` section 1, P30-A's precedent). A pre-P71
    shard was distinguishable only by its `assets.py` md5 pin, which also moves
    for every unrelated edit to that file, and the direct lift already carries
    its own `lift_dz` field while the *scene* had none. The `physics` block
    (P41) covers the finger drive only.

    Same shape and same builders-from-two-paths rule as
    `finger_physics_provenance`: one function, called by the collector's shard
    manifest **and** the direct env's rollout manifest, so they cannot drift
    apart. Everything here is a *derived* read of the scene config - no
    simulator, no articulation, no state - so it is written before the first
    episode and cannot fail a build.

    Fields, and why each is needed to tell two stores apart:

    * `output_rails` - the resolved mode string (`both`/`outer`/`inner`/`none`)
      and `rail_keep`, the resolved `(inner, outer)` pair. The pair, not the
      string, is what the geometry builder reads; `none` is the shipped default
      since P71.
    * `rail_height` / `rail_proud` / `rail_inset` - the authored box, its height
      **above** the belt surface (`height - inset`, 0.035 shipped) and the inset
      that makes the boxes' bottoms sit inside the slab. `rail_proud` is what
      `_payload_clearance` reports a kept rail against, so a manifest without
      it cannot reconstruct a pre-P71 clearance row.
    * `output_belt.top_z` / `y` / `size` / `inboard_edge_y` - the plate the
      payload lands on and the **corner** it crosses: `inboard_edge_y =
      |y| - size[1]/2` (0.425 shipped) is the P72 `clr_edge` threshold. The
      belt height is a `FRUIT_OUTPUT_BELT_TOP_Z` knob (P70/P71 keeps 1.35).
    * `output_lanes` - **every** output body (P123): belt centre/size, place
      point, tray centre/size and prim root, one entry per lane. Two entries are
      the shipped scene; `FRUIT_OUTPUT_LANES=3` adds the inboard -Y body and
      narrows the -Y tray, and that store's collider set is a different scene.
    * `lift` - the **direct** rung, `{dz: {arm: m}, defaulted: bool}` the
      `[grasp] lift_dz:` row's own resolution, or `None` on a path that has no
      lift rung (every scripted collector shard: the knob is `SortingRLEnv`-
      only). `None` is therefore "not a direct run", not "the 0.36 m rung".

    A manifest **without** this key predates P72 (the `arm_park.defaulted`
    convention): it may be either geometry.
    """
    keep = tuple(bool(v) for v in cfg.output_rail_keep)
    size = [float(v) for v in cfg.output_belt_size]
    block = {
        "output_rails": str(cfg.output_rails),
        "rail_keep": {"inner": keep[0], "outer": keep[1]},
        "rail_height": float(cfg.output_rail_height),
        "rail_proud": float(cfg.output_rail_proud),
        "rail_inset": float(OUTPUT_RAIL_INSET),
        "output_belt": {
            "top_z": float(cfg.output_belt_top_z),
            "y": float(cfg.output_belt_y),
            "size": size,
            "inboard_edge_y": abs(float(cfg.output_belt_y)) - size[1] / 2.0,
        },
        #: P123: every output **body** (belt + chute + tray), so a store names
        #: the collider set it was recorded in - a third lane moves the solver
        #: ordering exactly as the rails did (P71). Two entries = the shipped
        #: scene; a manifest without the key predates P123.
        #: P144: **which camera the store was recorded through**. A policy trained
        #: on one view is out of distribution on another, so a store (or a
        #: checkpoint) that does not name its camera cannot be mixed. Unset is the
        #: shipped pose and the block then reads `name: "shipped"`.
        "head_camera": {
            "name": os.environ.get("FRUIT_HEAD_CAMERA", "").strip() or "shipped",
            "eye": list(head_camera_override(cfg)[0]),
            "target": list(head_camera_override(cfg)[1]),
        },
        "output_lanes": [
            {
                "index": int(lane["index"]),
                "side": str(lane["side"]),
                "root": str(lane["root"]),
                "belt_center": [float(v) for v in lane["belt_center"]],
                "belt_size": [float(v) for v in lane["belt_size"]],
                "place": [float(v) for v in lane["place"]],
                "tray_center": [float(v) for v in lane["tray_center"]],
                "tray_size": [float(v) for v in lane["tray_size"]],
            }
            for lane in cfg.output_lane_layout()
        ],
        #: P188: the **authored finger plate** - the pad's width and the distal
        #: plane's offset. Both are build-time collider re-authorings (the USD
        #: asset is never edited), so a store must name them to be reproducible:
        #: the plate's width sets the pads' lateral coverage, which is the
        #: right arm's binding term (`dlat` 19-26 mm against 61 mm).
        "finger": {
            "pad_wide": float(os.environ.get("FRUIT_FINGER_PAD_WIDE", "0") or 0.0),
            "tip_delta": os.environ.get("FRUIT_FINGER_TIP_DELTA", ""),
        },
        #: P227t: **which arm asset** the store was recorded with. A Panda store
        #: and an OpenArm store are otherwise distinguishable only by an
        #: `assets.py` md5 that moves for every unrelated edit: the joints a
        #: policy's action space is expressed in are the arm's, so the two
        #: cannot be mixed (`FRUIT_ARM_KIND`). Everything here is the resolved
        #: `ArmSpec` plus the USD path - no simulator read.
        "arm": _arm_provenance(),
        "lift": None,
    }
    if lift_dz is not None:
        block["lift"] = {
            "dz": {str(side): float(offset) for side, offset in lift_dz.items()},
            "defaulted": bool(lift_dz_defaulted),
        }
    return block


def supply_provenance(plan) -> dict:
    """The supply **band and mix** a store was recorded under (P93).

    P92's re-entry named this as its one provenance prerequisite before any
    recollection: the *delivered* lateral position is where the closed class's
    rate lives (`logs/p92/RESULTS.md` section 2 - the band's top is where the
    pinch is taken at the reach edge), so a store recorded under a 0.20-0.33 m
    band and one recorded under 0.20-0.36 m must be distinguishable from their
    own metadata.

    What exists today, measured rather than assumed:

    * the **collector's** shard manifest already carries `supply.x_min` /
      `supply.x_max` and both mixes next to the schedule flags
      (`datasets/v12d_s02/manifest.json` reads `x_max: 0.36`), so a
      *collection* store is already distinguishable;
    * the **direct env's** rollout manifest carries only its P58 profile block
      (`cadence`/`band_interlock`/`band_max`/`target_from`/`direct_feed`/
      `continuous`/`defaulted`) - no band, no mix - so a direct/rollout store
      under a different band is **not** distinguishable today. That is the gap.

    One builder, the same builders-from-two-paths rule as
    `finger_physics_provenance` (P41) and `scene_provenance` (P72): both manifest
    writers call **this** function and cannot drift apart. Everything here is a
    read of the resolved `fruits.SupplyPlan` - no simulator, no articulation, no
    state - so it is written before the first episode and cannot fail a build.

    Fields:

    * `x_min` / `x_max` - the **planned** lateral band. The *delivered* x is the
      plan plus a per-instance release offset (P38/P50: the control's own
      `0.36 -> 0.3908` is +31 mm), so this is a bound on the draw, never a
      bound on what the pads met.
    * `gap_min` / `gap_max` - the along-schedule draws, so two stores at the
      same band but different density (P1's `FRUIT_SUPPLY_PATCH_DENSITY`) are
      distinguishable too.
    * `grades` / `classes` - the two mixes as `{name: weight}`. The grade mix is
      what the pure routing sends to each arm (W3), so it moves the per-arm
      occupancy without moving one trajectory.
    * `schedule` - the **resolved** branch name (`bed` > `patch` > `wave` >
      `scatter`, then `fixed`). This is the branch order the spawner's own
      `respawn` reads; the flags themselves are already in both manifests, and
      the resolved name is the one field a reader can compare at a glance (the
      P33-phase-3 "patch and wave both on means the patch branch" trap).

    A manifest **without** `supply.band` predates P93 (the `arm_park.defaulted`
    / `scene` convention): it may have been recorded under either band, and the
    `x_min`/`x_max` fields the collector already writes are then the witness.
    """
    schedule = "fixed"
    for name in ("bed", "patch", "wave", "scatter"):
        if bool(getattr(plan, name, False)):
            schedule = name
            break
    return {
        "x_min": float(plan.x_min),
        "x_max": float(plan.x_max),
        "gap_min": float(plan.gap_min),
        "gap_max": float(plan.gap_max),
        "grades": {str(k): float(v) for k, v in plan.grades},
        "classes": {str(k): float(v) for k, v in plan.classes},
        "schedule": schedule,
    }


