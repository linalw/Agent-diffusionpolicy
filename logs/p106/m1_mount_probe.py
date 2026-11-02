#!/usr/bin/env python3
"""P106 M1/M2a: the Allegro 16-DoF USD mounted on the OpenArm flange.

**What this is.** A standalone probe scene - the cell's *environment* and the real
OpenArm articulation, but no conveyor, no camera, no scheduler, no policy - in
which the Allegro asset is referenced under the left flange, welded, driven and
then asked the two things M1 and M2a owe:

* **M1** the mount reads back: DOF count/order, per-joint drive, the tool offset
  that replaces `_pad_standoff`'s 70 mm, a close on a fruit and a lift read by the
  primitive's own test (`fruit_z - z_before > 4 mm`), and a per-finger force read.
* **M2a** P104's pull protocol, in-scene: a 5 N/s axial ramp with gravity to a
  40 N cap, scored on the sustained break-away, the 2 mm criterion, the creep at
  the operating load, and the fingers' own travel (do they pry?).

**Phases** (`P106_PHASE`), so a mount error is found before a battery is spent:

    A  mount + frame census (no fruit)
    B  the grasp sweep (curl x seat offset x torque cap) - finds a seat that loads
       every finger, and reports the hand's own grasp radius per curl
    C  close -> lift -> pull, per fruit

    FRUIT_FINGER_COLLIDERS=0 P106_PHASE=C scripts/run.sh logs/p106/m1_mount_probe.py

**Two measured hazards this probe works around, both recorded in METHOD.md:**

1. `stage.RemovePrim` does **not** defeat a prim that comes from a reference: the
   asset's `root_joint` (world -> mount) survived and PhysX snapped the hand to the
   world origin, which exploded the whole articulation (arm joint 1 read -82 rad
   and a +0.3 command moved it -34). `prim.SetActive(False)` is the fix.
2. `ArmController.move_to` from the hanging rest pose stalls 0.19-0.33 m short of
   a pick-height target (measured twice, with and without a linear waypoint ramp),
   so the arm is placed by **teleporting to the shipped `ready` waypoint** and then
   raised with a straight-line move. The pull test needs a held pose, not a station.
"""

from __future__ import annotations

import json
import os
import sys
import time

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 320, "height": 240})

import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

from isaacsim.core.experimental.prims import Articulation, RigidPrim
from isaacsim.core.simulation_manager import SimulationManager

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say, substeps
from fruit_sorting.control import ArmController
from fruit_sorting.fdlimit import raise_fd_limit
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.meshes import FRUIT_SHAPES
from fruit_sorting.scene import SortingScene

raise_fd_limit()

DT = 1.0 / 120.0
PHASE = os.environ.get("P106_PHASE", "A").upper()
ALLEGRO_LOCAL = os.environ.get("P106_ALLEGRO_USD", "/tmp/allegro.usd")
SIDE = os.environ.get("P106_SIDE", "left")
FINGERS = ("index", "middle", "ring", "thumb")

#: Mount transform in the flange (ee_tcp) frame. Identity is the measured
#: alignment: the asset's +z (finger extension) is the flange's -z, i.e. down the
#: tool axis, so the fingers hang below the flange with no correction.
MOUNT_RPY = [float(v) for v in os.environ.get("P106_MOUNT_RPY", "0,0,0").split(",")]
MOUNT_XYZ = [float(v) for v in os.environ.get("P106_MOUNT_XYZ", "0,0,0").split(",")]
WELD = os.environ.get("P106_WELD", "1") == "1"
#: The hand's own drive, authored before play. 0 = the asset's own values.
HAND_K = float(os.environ.get("P106_HAND_K", "0"))
HAND_C = float(os.environ.get("P106_HAND_C", "0"))
HAND_CAP = float(os.environ.get("P106_HAND_CAP", "0"))

#: Arm pose: the shipped calibrated waypoint (`configs/waypoints.json`), then a
#: straight lift so the hand clears the scene floor.
POSE = os.environ.get("P106_POSE", "ready")
#: The scene has no belt (only the environment floor), so the shipped `ready`
#: waypoint already leaves the hand in free space; a raise is opt-in and, when it
#: does not converge, would tilt the tool axis (measured: 30 deg at `1.45`).
LIFT_TO = float(os.environ.get("P106_LIFT_TO", "0"))

FRUITS = tuple(f.strip() for f in os.environ.get("P106_FRUITS", "pear,orange,strawberry").split(",") if f.strip())
REPEATS = int(os.environ.get("P106_REPEATS", "3"))
SEED = int(os.environ.get("P106_SEED", "5"))

CURLS = [float(v) for v in os.environ.get("P106_CURLS", "0.4,0.6,0.8,1.0,1.2").split(",")]
#: The thumb's curl as a fraction of the fingers' (its chain is shorter and its
#: base is rotated 90 deg).
THUMB_FRAC = float(os.environ.get("P106_THUMB_FRAC", "0.50"))
#: The thumb's **abduction** (`thumb_joint_0`, limits +0.279..+1.571 rad) is what
#: brings it across the palm to oppose the fingers; its curl (joints 1..3) only
#: folds it. Both are swept, because the 3+1 topology's opposition lives in the
#: abduction joint.
THUMB0 = [float(v) for v in os.environ.get("P106_THUMB0", "0.3,0.8,1.2,1.5").split(",")]
#: Torque cap [N.m] on each of the 16 hand joints - the knob that sets the
#: per-contact force (P41's c/k mechanism, in torque form).
CAPS = [float(v) for v in os.environ.get("P106_CAPS", "0.10,0.20,0.30,0.45,0.60").split(",")]
SWEEP_CAP = float(os.environ.get("P106_SWEEP_CAP", "0.30"))
#: Seat offsets from the fitted grasp centre [m] along the tool axis.
OFFSETS_Z = [float(v) for v in os.environ.get("P106_OFFSET_Z", "-0.02,0.0,+0.02").split(",")]
#: Lateral offsets in the flange-x direction [m].
LATERAL = [float(v) for v in os.environ.get("P106_LATERAL", "-0.02,0.0,+0.02").split(",")]

CLOSE_TICKS = int(os.environ.get("P106_CLOSE_TICKS", "150"))
PIN_TICKS = int(os.environ.get("P106_PIN_TICKS", "260"))
SETTLE_TICKS = int(os.environ.get("P106_SETTLE_TICKS", "90"))
RATE = float(os.environ.get("P106_RATE", "5.0"))
F_MAX = float(os.environ.get("P106_F_MAX", "40.0"))
BREAK_M = float(os.environ.get("P106_BREAK_MM", "2.0")) / 1000.0
EXIT_M = float(os.environ.get("P106_EXIT_MM", "30.0")) / 1000.0
LIFT_M = float(os.environ.get("P106_LIFT_MM", "60.0")) / 1000.0
#: The chosen seat (phase C), from phase B's best cell unless overridden.
SEAT_CURL = float(os.environ.get("P106_SEAT_CURL", "1.0"))
SEAT_THUMB0 = float(os.environ.get("P106_SEAT_THUMB0", "0.8"))
SEAT_DZ = float(os.environ.get("P106_SEAT_DZ", "0.0"))
SEAT_LAT = float(os.environ.get("P106_SEAT_LAT", "0.0"))
SEAT_CAP = float(os.environ.get("P106_SEAT_CAP", "0.30"))
#: The commanded **over-curl** past the just-touching posture [rad]. This is the
#: analogue of P104's `INTERFERENCE` (5 mm inside the measured extent): the seat
#: is found from the posture whose fingertips just touch the payload, so closing
#: to *that* posture has zero interference and the payload simply falls on
#: release (measured: creep 1112 mm). The grip comes from the over-curl.
CLOSE_EXTRA = float(os.environ.get("P106_CLOSE_EXTRA", "0.02"))
#: The close is **closed-loop on the drive's delivered torque**: the curl ramps
#: until a finger joint carries `TAU_TARGET` [N.m], then holds. That is the only
#: way to land a stated per-contact force on a hand whose drive is a stiff
#: position servo - the torque *cap* is a step function (measured: 0.47 N.m -> no
#: contact, 0.48 -> 10.5 N per contact), which is
#: `docs/HAND_STAGE_PLAN.md` section 1.4's warning measured. `TAU / LEVER` is the
#: equivalent contact force, so 0.22 N.m ~ 4.9 N - the pinch's own per-face value.
TARGET_TOTAL = float(os.environ.get("P106_TARGET_TOTAL", "18.0"))
TAU_TARGET = float(os.environ.get("P106_TAU_TARGET", "0.22"))


#: The seat's posture must be one the geometry sweep measured, or `seat_by_posture`
#: silently falls back to a *different* posture's tips while the drives command
#: this one (measured: phase K read all-zero contact forces from exactly that).
CURLS = sorted(set(CURLS + [SEAT_CURL]))
THUMB0 = sorted(set(THUMB0 + [SEAT_THUMB0]))


def euler_quat(rpy_deg: list[float]) -> np.ndarray:
    r, p, y = np.deg2rad(rpy_deg)
    cr, sr = np.cos(r / 2), np.sin(r / 2)
    cp, sp = np.cos(p / 2), np.sin(p / 2)
    cy, sy = np.cos(y / 2), np.sin(y / 2)
    return np.array([
        cr * cp * cy + sr * sp * sy,
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
    ])


def quat_axis(q: np.ndarray, k: int) -> np.ndarray:
    w, x, y, z = q
    m = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])
    return m[:, k]


def opposition(tp: dict[str, np.ndarray]) -> tuple[np.ndarray, float, float, float]:
    """Seat for a 3+1 grasp: the midpoint between the finger cluster and the thumb.

    The four-tip centroid is the wrong seat for this topology - the thumb sits
    100-170 mm from the fingers, so the centroid lands outside the grasp and the
    payload touches two fingers only (measured: the first sweep's cells read
    index 3.1 N with the other three at 0). The seat that can load all four is
    the midpoint of the three fingers' centroid and the thumb tip, and the
    distance between them is the widest object the hand can pinch -- its
    **opposition span**.
    """
    fingers = np.array([tp[k] for k in ("index", "middle", "ring")])
    fc = fingers.mean(axis=0)
    th = tp["thumb"]
    seat = 0.5 * (fc + th)
    opp = float(np.linalg.norm(th - fc))
    span_f = max(float(np.linalg.norm(fingers[i] - fingers[j]))
                 for i in range(3) for j in range(i + 1, 3))
    return seat, opp, span_f, float(np.linalg.norm(th - seat))


def best_seat(pts: np.ndarray, radius: float, step_m: float = 0.005,
              box_m: float = 0.05) -> tuple[np.ndarray, int, list[float]]:
    """The seat that puts the most fingertips on a payload of `radius`.

    A sphere of radius r touches a fingertip when the tip's contact point is at r
    from the centre; the tip *link origin* sits ~12 mm inside the pad surface, so
    the test is `|d - r| <= 0.012`. A coarse grid (±50 mm, 5 mm) over the tip
    centroid is enough - the hand's own tip geometry is the only thing that
    decides it, and this makes the seat a *measured* consequence of the posture
    instead of a hand-picked midpoint that loaded two fingers (the first sweep
    read index+thumb only, `logs/p106/METHOD.md`).
    """
    pts = np.asarray(pts, dtype=float)
    c = pts.mean(axis=0)
    best = (c, -1, 1e9, [0.0] * 4)
    n = int(round(box_m / step_m))
    for ix in range(-n, n + 1):
        for iy in range(-n, n + 1):
            for iz in range(-n, n + 1):
                cand = c + np.array([ix, iy, iz]) * step_m
                d = np.linalg.norm(pts - cand, axis=1)
                touch = np.abs(d - radius) <= 0.012
                count = int(np.count_nonzero(touch))
                err = float(np.sum(np.abs(d - radius)))
                if count > best[1] or (count == best[1] and err < best[2]):
                    best = (cand, count, err, d.tolist())
    return best[0], best[1], best[3]


def tip_census(points: np.ndarray) -> tuple[np.ndarray, float, float, float]:
    """Seat, span, and how far the four fingertips are from a common sphere.

    The **seat** is the centroid of the four contact points. The **span** is the
    largest pairwise distance - the widest payload the fingertips straddle. The
    **equidistance residual** is `max|d_i - mean(d_i)| / mean(d_i)` about the
    centroid: 0 means the four points lie on a sphere around the seat (a radial
    grasp), and >0 is exactly the 3+1 non-radiality the plan predicts. A sphere
    *fit* was tried first and rejected: four near-coplanar tips make the
    algebraic problem singular (`r_fit` read 233-1404 mm, `logs/p106/`), so the
    residual is the honest, well-conditioned form of the same question.
    """
    p = np.asarray(points, dtype=float)
    seat = p.mean(axis=0)
    d = np.linalg.norm(p - seat, axis=1)
    span = max(float(np.linalg.norm(p[i] - p[j])) for i in range(len(p)) for j in range(i + 1, len(p)))
    eq = float((d.max() - d.min()) / max(d.mean(), 1e-9))
    return seat, span, eq, float(d.mean())


def main() -> int:
    wall0 = time.time()
    say(f"[p106] phase={PHASE} side={SIDE} mount_rpy={MOUNT_RPY} mount_xyz={MOUNT_XYZ} "
        f"pose={POSE} lift_to={LIFT_TO} wel={WELD}")

    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "robot"))
    stage = scene.stage
    tcp_path = f"/World/OpenArm/openarm_{SIDE}_ee_tcp"

    # --- the mount ------------------------------------------------------- #
    # The Allegro arrives as its own articulation. Nesting it under the arm's
    # would give PhysX two roots on one chain, so the referenced root drops its
    # ArticulationRootAPI and its own world anchor, and the hand's links merge
    # into the OpenArm articulation through the mount joint.
    mount_path = f"{tcp_path}/Allegro"
    mount = stage.DefinePrim(mount_path, "Xform")
    mount.GetReferences().AddReference(ALLEGRO_LOCAL)
    xf = UsdGeom.Xformable(mount)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*MOUNT_XYZ))
    q = euler_quat(MOUNT_RPY)
    xf.AddOrientOp(UsdGeom.XformOp.PrecisionDouble).Set(
        Gf.Quatd(float(q[0]), float(q[1]), float(q[2]), float(q[3]))
    )
    for prim in Usd.PrimRange(mount, Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)):
        if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            prim.RemoveAPI(UsdPhysics.ArticulationRootAPI)
            say(f"[p106] dropped ArticulationRootAPI on {prim.GetPath()}")
    # `RemovePrim` does NOT defeat a referenced prim; deactivate.
    root_joint = stage.GetPrimAtPath(f"{mount_path}/root_joint")
    if root_joint.IsValid():
        root_joint.SetActive(False)
        say(f"[p106] deactivated the asset's world anchor (active={root_joint.IsActive()})")

    if HAND_K > 0.0:
        n_auth = 0
        for prim in Usd.PrimRange(mount, Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)):
            if prim.GetTypeName() != "PhysicsRevoluteJoint":
                continue
            if not prim.HasAPI(UsdPhysics.DriveAPI, "angular"):
                continue
            drv = UsdPhysics.DriveAPI(prim, "angular")
            drv.CreateStiffnessAttr().Set(float(HAND_K))
            drv.CreateDampingAttr().Set(float(HAND_C))
            if HAND_CAP > 0.0:
                drv.CreateMaxForceAttr().Set(float(HAND_CAP))
            n_auth += 1
        say(f"[p106] hand drives authored k={HAND_K} c={HAND_C} cap={HAND_CAP} on {n_auth} joints")

    if not WELD:
        say("[p106] P106_WELD=0: the hand is NOT welded (isolation control)")
    else:
        weld = UsdPhysics.FixedJoint.Define(stage, f"{mount_path}/mount_weld")
        weld.CreateBody0Rel().SetTargets([Sdf.Path(tcp_path)])
        weld.CreateBody1Rel().SetTargets([Sdf.Path(f"{mount_path}/allegro_mount")])
        weld.CreateLocalPos0Attr().Set(Gf.Vec3f(*MOUNT_XYZ))
        weld.CreateLocalRot0Attr().Set(Gf.Quatf(float(q[0]), float(q[1]), float(q[2]), float(q[3])))
        weld.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
        weld.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))

    spawner = FruitSpawner(stage, cfg, seed=SEED)
    spawner.create_pool()
    # Contact tracking must be armed at *authoring* time: a `RigidPrim` built
    # after play does not get a valid physics contact view on this build
    # (`AssertionError: Physics contact view is not valid`), which is exactly why
    # `scripts/210_squeeze_probe.py` and P104's fixture both arm it before play.
    for sample in spawner.samples:
        try:
            RigidPrim(sample.prim_path).set_enabled_contact_tracking(True, threshold=1e-3)
        except Exception:  # noqa: BLE001
            pass

    scene.start(physics_dt=DT, warmup_steps=60)
    robot = scene.robot
    names = list(robot.dof_names)
    links = list(robot.link_names)
    paths = robot.link_paths
    if isinstance(paths[0], (list, tuple)):
        paths = paths[0]

    def path_of(name: str) -> str:
        p = paths[links.index(name)]
        return str(p[0] if isinstance(p, (list, tuple)) else p)

    def handle(name: str) -> RigidPrim:
        return RigidPrim(path_of(name))

    say(f"[p106] DOF count = {len(names)} (22 before the mount)")
    say(f"[p106] hand dofs = {[n for n in names if n.split('_')[0] in FINGERS]}")
    lo = np.asarray(robot.get_dof_limits()[0].numpy())[0]
    hi = np.asarray(robot.get_dof_limits()[1].numpy())[0]
    for n in ("index_joint_0", "index_joint_1", "thumb_joint_0", "thumb_joint_3"):
        i = names.index(n)
        say(f"[p106] {n:14s} limit=({lo[i]:+.3f},{hi[i]:+.3f}) rad")
    gains = np.asarray(robot.get_dof_gains()[0].numpy())[0]
    damp = np.asarray(robot.get_dof_gains()[1].numpy())[0]
    caps = np.asarray(robot.get_dof_max_efforts().numpy())[0]
    say(f"[p106] hand k readback (index_joint_1) = {float(np.asarray(robot.get_dof_gains()[0].numpy())[0][names.index('index_joint_1')]):.1f} N.m/rad")
    say("[p106] hand drive readback: " + " ".join(
        f"{n}[k={gains[names.index(n)]:.0f},c={damp[names.index(n)]:.0f},cap={caps[names.index(n)]:.2f}]"
        for n in ("index_joint_1", "thumb_joint_1")))
    mass = float(np.sum([float(np.asarray(handle(n).get_masses().numpy())[0]) for n in links
                         if n.split("_")[0] in FINGERS or n in ("palm_link", "allegro_mount")]))
    say(f"[p106] hand mass (sum of its 21 bodies) = {mass:.3f} kg")

    arm = ArmController(scene, SIDE)
    arm.set_gripper(arm.open_value)

    def step(n: int = 1) -> None:
        for _ in range(max(1, int(n))):
            SimulationManager.step(steps=substeps())

    # --- unit check on the merged articulation ---------------------------- #
    i1 = names.index("openarm_left_joint1")
    qb = float(np.asarray(robot.get_dof_positions().numpy())[0][i1])
    robot.set_dof_position_targets(np.array([[qb + 0.3]]), dof_indices=np.array([i1]))
    step(180)
    qa = float(np.asarray(robot.get_dof_positions().numpy())[0][i1])
    say(f"[p106] unit check arm joint1 +0.300 -> {qa-qb:+.4f} (radians if ~+0.3)")
    robot.set_dof_position_targets(np.array([[qb]]), dof_indices=np.array([i1]))
    step(180)
    if os.environ.get("P106_STOP", "0") == "1":
        say(f"[p106] DONE phase={PHASE}(stop) wall={time.time()-wall0:.1f}s")
        return 0

    # --- pose: the shipped waypoint, then a straight lift ----------------- #
    with open(os.path.join(_ROOT, "configs", "waypoints.json")) as fh:
        wp = json.load(fh)
    pose = np.array(wp["arms"][SIDE][POSE], dtype=float)
    arm.teleport_joints(pose, settle=40)
    # The `ready` waypoint's wrist is tilted for the *pad* hand (its jaw frame is
    # not the tool axis). Command the tool axis **straight down** instead: a 180
    # deg rotation about world x maps the flange's +z to world -z, so the lift and
    # the pull are along the tool axis by construction.
    arm.hold_quaternion = np.array([0.0, 1.0, 0.0, 0.0], dtype=float)
    step(30)
    say(f"[p106] arm at waypoint '{POSE}': q={np.round(pose,3)} tcp={np.round(arm.tcp_position(),4)}")

    def linear_move(goal: np.ndarray, waypoints: int = 30, steps: int = 40) -> float:
        start = arm.tcp_position().copy()
        for w in range(1, waypoints + 1):
            p = start + (goal - start) * (w / waypoints)
            for _ in range(steps):
                arm.ik_step(p)
                SimulationManager.step(steps=substeps())
        return float(np.linalg.norm(arm.tcp_position() - goal))

    if float(arm.tcp_position()[2]) < LIFT_TO:
        tgt = arm.tcp_position() + np.array([0.0, 0.0, LIFT_TO - float(arm.tcp_position()[2])])
        e = linear_move(tgt)
        say(f"[p106] flange raised to z={float(arm.tcp_position()[2]):.3f} (residual {e*1000:.1f} mm)")
    step(30)
    tcp_p, tcp_q = arm.tcp_pose()
    tool_axis = quat_axis(tcp_q, 2)
    say(f"[p106] flange pos {np.round(tcp_p,4)}; axes x={np.round(quat_axis(tcp_q,0),3)} "
        f"y={np.round(quat_axis(tcp_q,1),3)} z={np.round(quat_axis(tcp_q,2),3)}")

    # --- fingertip geometry ---------------------------------------------- #
    tip_names = {"index": "index_link_3", "middle": "middle_biotac_tip",
                 "ring": "ring_biotac_tip", "thumb": "thumb_biotac_tip"}
    tip_handle = {k: handle(v) for k, v in tip_names.items()}
    tip_path = {k: path_of(v) for k, v in tip_names.items()}
    # The tree's own contact instrument (`tactile.py`): an **unfiltered** net-force
    # reader on each fingertip link with tracking enabled. A *filtered* view
    # (`contact_filter_paths=[payload]`) is what P104's authored pads use, but on
    # an articulation link this build returns a contact view that reports forces
    # for fingers 60-90 mm away from the payload - so the filter is not isolating
    # as it does for a standalone pad body. Unfiltered + "is the payload within
    # reach" is the honest form.
    #: The hand's drive stiffness, as resolved on the live articulation. The
    #: per-finger load is read from the **tracking error** (`k * (target - q)`):
    #: a finger that is blocked by the payload sits short of its commanded curl,
    #: and that deflection times k is the torque it is applying. This is the
    #: instrument that survives this build - a per-link contact view is what
    #: `tactile.py` uses on the *pads*, but on the hand's links it reads NaN
    #: here (measured), and a filtered view is not isolating (60-90 mm away).
    # The *live* stiffness differs from the authored value (measured: 1145.9
    # N.m/rad against an authored 20), so it is read rather than assumed; the
    # torque read below is therefore `k_live * (target - q)`, an upper bound on
    # the delivered torque when the drive saturates.
    hand_k_live = float(np.asarray(robot.get_dof_gains()[0].numpy())[0][names.index("index_joint_1")])
    LEVER_M = 0.045
    #: The fingertip's own contact patch, for the "where does it touch" read.
    tip_r = {"index": 0.012, "middle": 0.012, "ring": 0.012, "thumb": 0.012}

    def tips() -> dict[str, np.ndarray]:
        return {k: np.asarray(h.get_world_poses()[0].numpy(), dtype=float)[0] for k, h in tip_handle.items()}

    TARGETS: dict[str, tuple[list[float], list[int]]] = {}

    def set_curl(finger_curl: float, cap: float | None = None, thumb0: float = 0.8) -> None:
        idx = [names.index(f"{k}_joint_{j}") for k in ("index", "middle", "ring") for j in (1, 2, 3)]
        tidx = [names.index(f"thumb_joint_{j}") for j in (1, 2, 3)]
        t0 = names.index("thumb_joint_0")
        if cap is not None:
            robot.set_dof_max_efforts(np.array([cap] * len(idx)), dof_indices=np.array(idx))
            robot.set_dof_max_efforts(np.array([cap] * len(tidx)), dof_indices=np.array(tidx))
            robot.set_dof_max_efforts(np.array([cap]), dof_indices=np.array([t0]))
        robot.set_dof_position_targets(np.array([[finger_curl] * len(idx)]), dof_indices=np.array(idx))
        robot.set_dof_position_targets(
            np.array([[finger_curl * THUMB_FRAC] * len(tidx)]), dof_indices=np.array(tidx))
        robot.set_dof_position_targets(np.array([[thumb0]]), dof_indices=np.array([t0]))
        TARGETS.clear()
        for k in ("index", "middle", "ring"):
            TARGETS[k] = ([finger_curl] * 3, [names.index(f"{k}_joint_{j}") for j in (1, 2, 3)])
        TARGETS["thumb"] = ([finger_curl * THUMB_FRAC] * 3,
                            [names.index(f"thumb_joint_{j}") for j in (1, 2, 3)])

    # The grasp geometry per curl: seat, span, and the non-radiality residual.
    say("[p106] posture -> 3+1 opposition span and seat (the hand's own grasp width)")
    seat_by_posture: dict[tuple[float, float], tuple[np.ndarray, float, float, float]] = {}
    for curl in CURLS:
        for t0 in THUMB0:
            set_curl(0.0, thumb0=0.3)
            step(20)
            set_curl(curl, SWEEP_CAP, thumb0=t0)
            step(200)
            tp = tips()
            seat, opp, span_f, half = opposition(tp)
            pts4 = np.array([tp[k] for k in FINGERS])
            seat_by_posture[(curl, t0)] = (pts4, opp, span_f)
            seats = {}
            for r in (0.0303, 0.0329, 0.0186):
                sc, cnt, dists = best_seat(pts4, r)
                seats[r] = (sc, cnt)
            say(f"[p106]   curl={curl:4.2f} thumb0={t0:4.2f} opposition={opp*1000:5.1f}mm "
                f"finger_span={span_f*1000:5.1f}mm "
                f"tips@r30.3={seats[0.0303][1]} tips@r32.9={seats[0.0329][1]} "
                f"tips@r18.6={seats[0.0186][1]} "
                f"flange->seat {np.linalg.norm(seats[0.0303][0] - tcp_p)*1000:5.1f}mm "
                f"along_tool {float(np.dot(seats[0.0303][0] - tcp_p, tool_axis))*1000:+6.1f}mm")
    mid = (CURLS[len(CURLS) // 2], THUMB0[len(THUMB0) // 2])
    pts_mid = seat_by_posture[mid][0]
    centre0, n_mid, _ = best_seat(pts_mid, 0.0303)
    say(f"[p106] tool offset (replaces _pad_standoff 70mm) at {mid}: "
        f"{float(np.dot(centre0 - tcp_p, tool_axis))*1000:.1f} mm along the tool axis, "
        f"{float(np.linalg.norm(centre0 - tcp_p))*1000:.1f} mm from the flange")

    if PHASE == "A":
        say(f"[p106] DONE phase=A wall={time.time()-wall0:.1f}s")
        return 0

    # --- fruits ----------------------------------------------------------- #
    for sample in spawner.samples:
        try:
            RigidPrim(sample.prim_path).set_enabled_contact_tracking(True, threshold=1e-3)
        except Exception:  # noqa: BLE001
            pass
    step(10)
    spawner.refresh_rigids()
    for sample in spawner.samples:
        spawner.park(sample)
    step(20)
    picks: dict[str, object] = {}
    for sample in spawner.samples:
        picks.setdefault(sample.category, sample)

    views: dict[str, RigidPrim] = {}
    view_mode = {"how": "unset"}

    def drive_torque() -> tuple[float, dict[str, float]]:
        """Delivered torque per finger [N.m] = k * (commanded - achieved)."""
        q = np.asarray(robot.get_dof_positions().numpy(), dtype=float)[0]
        per = {}
        for k in FINGERS:
            targets, idxs = TARGETS.get(k, ([], []))
            if not idxs:
                per[k] = 0.0
                continue
            per[k] = float(max(abs(hand_k_live * (t - q[i])) for t, i in zip(targets, idxs)))
        return max(per.values(), default=0.0), per

    def fruit_force(sample) -> float:
        """Total contact force on the payload [N] = the sum of the positive
        per-fingertip reads. The unfiltered fruit view raises on this build
        (`Physics contact view is not valid`), so the filtered per-tip views -
        P104's own recipe - are the instrument, and their sum is the total.
        """
        return float(sum(max(0.0, v) for v in finger_forces(sample).values() if not np.isnan(v)))

    def finger_forces(sample) -> dict[str, float]:
        """Per-finger **blocked** flag expressed as an equivalent [N].

        A finger carrying load sits short of its commanded curl; the deflection
        times the drive stiffness is the torque it applies, `tau / lever` is the
        equivalent tip force, capped at the joint's own torque cap. It reads 0 in
        free space. Reported beside the payload's measured total, not instead.
        """
        c = spawner.position(sample)
        q = np.asarray(robot.get_dof_positions().numpy(), dtype=float)[0]
        out = {}
        for k in FINGERS:
            # Contact force on the payload from this fingertip (P104's recipe: a
            # fruit-side view filtered to the tip body), plus the drive's own
            # tracking error as the independent "is this finger loaded" flag.
            try:
                key = f"{k}:{sample.prim_path}"
                v = views.get(key)
                if v is None:
                    v = RigidPrim(sample.prim_path, contact_filter_paths=[tip_path[k]])
                    views[key] = v
                f = np.asarray(v.get_net_contact_forces().numpy(), dtype=float)[0]
                p = np.asarray(tip_handle[k].get_world_poses()[0].numpy(), dtype=float)[0]
                u = c - p
                u = u / max(float(np.linalg.norm(u)), 1e-9)
                out[k] = float((f @ u) / DT)
                view_mode["how"] = "fruit-view/filter-tip"
            except Exception as exc:  # noqa: BLE001
                view_mode["how"] = f"FAILED: {exc}"
                out[k] = float("nan")
        return out

    def blocked(sample) -> dict[str, float]:
        """Drive tracking error per finger [N-equivalent]: a finger carrying load
        sits short of its commanded curl (`k * (target - q) / lever`)."""
        q = np.asarray(robot.get_dof_positions().numpy(), dtype=float)[0]
        out = {}
        for k in FINGERS:
            targets, idxs = TARGETS.get(k, ([], []))
            if not idxs:
                out[k] = float("nan")
                continue
            tau = max(hand_k_live * (t - q[i]) for t, i in zip(targets, idxs))
            out[k] = float(min(max(tau, 0.0), HAND_CAP if HAND_CAP > 0 else 5.0) / LEVER_M)
        return out

    def settle_and_read(sample, centre, curl, cap, t0=0.8) -> tuple[dict[str, float], dict[str, float], float]:
        """Close on a pinned payload, release it, and read the grasp.

        The third return value is P104's **creep**: the payload's displacement
        over a 0.75 s settle under nothing but its own weight - the operating
        load the cell actually applies (0.17-1.20 N), and the quantity the class
        lives on.
        """
        spawner.place(sample, centre)
        step(3)
        set_curl(0.0, cap, thumb0=0.3)
        step(8)
        # Ramp the curl and stop when the payload's own contact force reaches the
        # target. The payload is pinned (teleported to the seat) while this runs,
        # exactly as P104 pins its payload during the close.
        reached_tau = 0.0
        step_i = 0
        for step_i in range(1, CLOSE_TICKS + 1):
            frac = step_i / float(CLOSE_TICKS)
            set_curl((curl + CLOSE_EXTRA) * frac, cap, thumb0=0.3 + (t0 - 0.3) * frac)
            spawner.place(sample, centre)
            step(1)
            reached_tau, _ = drive_torque()
            if reached_tau >= TAU_TARGET:
                break
        for _ in range(60):
            spawner.place(sample, centre)
            step(1)
        reached_tau, tau_per = drive_torque()
        # Release: the payload hangs on the contacts alone. Creep = its
        # displacement over the settle, before any external ramp.
        p0 = spawner.position(sample).copy()
        step(SETTLE_TICKS)
        creep = float(np.linalg.norm(spawner.position(sample) - p0))
        n = finger_forces(sample)
        c = spawner.position(sample)
        gap = {k: float(np.linalg.norm(np.asarray(tip_handle[k].get_world_poses()[0].numpy(), dtype=float)[0] - c))
               for k in FINGERS}
        return n, gap, creep, reached_tau, tau_per

    rows = []
    if PHASE == "B":
        for category in FRUITS:
            sample = picks.get(category)
            if sample is None:
                continue
            d = float(sample.diameter)
            say(f"[p106] fruit {category} d={d*1000:.1f}mm mass={float(sample.mass)*1000:.1f}g "
                f"mu={float(sample.friction):.3f} (r={d*500:.1f}mm)")
            lat = quat_axis(tcp_q, 0)
            r_fruit = d / 2.0
            for curl in CURLS:
                for t0 in THUMB0:
                    pts4, opp, span_f = seat_by_posture[(curl, t0)]
                    c0, n_touch, dists = best_seat(pts4, r_fruit)
                    for dz in OFFSETS_Z:
                        for dy in LATERAL:
                            centre = c0 + tool_axis * dz + lat * dy
                            n, gap, slip = settle_and_read(sample, centre, curl, SWEEP_CAP, t0)
                        loaded = [k for k, v in n.items() if not np.isnan(v) and v > 1.0]
                        rows.append({"phase": "B", "fruit": category, "curl": curl,
                                     "thumb0": t0, "dz": dz, "lat": dy, "cap": SWEEP_CAP,
                                     "n": n, "loaded": len(loaded), "opposition": opp,
                                     "views": view_mode["how"]})
                        say(f"[p106] B {category:10s} curl={curl:4.2f} t0={t0:4.2f} dz={dz*1000:+5.1f} "
                            f"lat={dy*1000:+5.1f} opp={opp*1000:5.1f} tips@r={n_touch} cap={SWEEP_CAP:4.2f} "
                            f"N=[{', '.join(f'{k}:{v:5.2f}' for k, v in n.items())}] "
                            f"gap=[{', '.join(f'{k}:{v*1000:4.0f}' for k, v in gap.items())}] "
                            f"loaded={len(loaded)} views={view_mode['how']}")
                        set_curl(0.0, SWEEP_CAP)
                        step(20)
                        spawner.park(sample)
                        step(10)
        print("[p106] JSON " + json.dumps(rows))
        say(f"[p106] DONE phase=B rows={len(rows)} wall={time.time()-wall0:.1f}s")
        return 0

    # --- phase K: the torque cap that lands 4.90 N per contact ------------ #
    if PHASE == "K":
        for category in FRUITS:
            sample = picks.get(category)
            if sample is None:
                continue
            d = float(sample.diameter)
            pts4, opp, span_f = seat_by_posture.get(
                (SEAT_CURL, SEAT_THUMB0),
                seat_by_posture[(CURLS[len(CURLS) // 2], THUMB0[len(THUMB0) // 2])])
            c0, n_touch, _ = best_seat(pts4, d / 2.0)
            centre = c0 + tool_axis * SEAT_DZ + quat_axis(tcp_q, 0) * SEAT_LAT
            for cap in CAPS:
                n, gap, _cr, _tau, _tper = settle_and_read(sample, centre, SEAT_CURL, cap, SEAT_THUMB0)
                vals = [v for v in n.values() if not np.isnan(v)]
                pos = [v for v in vals if v > 1.0]
                mean = float(np.mean(pos)) if pos else 0.0
                rows.append({"phase": "K", "fruit": category, "cap": cap, "n": n,
                             "loaded": len(pos), "mean_loaded": mean})
                say(f"[p106] K {category:10s} d={d*1000:5.1f} cap={cap:4.2f} "
                    f"N=[{', '.join(f'{k}:{v:5.2f}' for k, v in n.items())}] "
                    f"loaded={len(pos)} mean={mean:5.2f}N")
                set_curl(0.0, cap, thumb0=0.3)
                step(20)
                spawner.park(sample)
                step(10)
        print("[p106] JSON " + json.dumps(rows))
        say(f"[p106] DONE phase=K rows={len(rows)} wall={time.time()-wall0:.1f}s")
        return 0

    # --- phase C: close, lift, then the pull ------------------------------ #
    for category in FRUITS:
        sample = picks.get(category)
        if sample is None:
            say(f"[p106] WARNING: no {category} in the pool")
            continue
        shape = FRUIT_SHAPES[category]
        d = float(sample.diameter)
        pts4, opp, span_f = seat_by_posture.get(
            (SEAT_CURL, SEAT_THUMB0),
            seat_by_posture[(CURLS[len(CURLS) // 2], THUMB0[len(THUMB0) // 2])])
        c0, n_touch, dists = best_seat(pts4, d / 2.0)
        centre = c0 + tool_axis * SEAT_DZ + quat_axis(tcp_q, 0) * SEAT_LAT
        say(f"[p106] {category} d={d*1000:.1f}mm mass={float(sample.mass)*1000:.1f}g "
            f"mu={float(sample.friction):.3f} seat curl={SEAT_CURL} dz={SEAT_DZ*1000:+.0f} "
            f"opposition={opp*1000:.1f}mm tips_expected={n_touch} cap={SEAT_CAP}")
        for rep in range(REPEATS):
            n, gap, creep, reached_tau, tau_per = settle_and_read(
                sample, centre, SEAT_CURL, SEAT_CAP, SEAT_THUMB0)
            loaded = [k for k, v in n.items() if not np.isnan(v) and v > 1.0]
            say(f"[p106] C close {category} tau={reached_tau:5.3f}N.m "
                f"F_eq=[{', '.join(f'{k}:{v/LEVER_M:5.1f}' for k, v in tau_per.items())}]N "
                f"F_total={fruit_force(sample):5.2f}N "
                f"N=[{', '.join(f'{k}:{v:5.2f}' for k, v in n.items())}] "
                f"loaded={len(loaded)} creep={creep*1000:5.2f}mm "
                f"gap=[{', '.join(f'{k}:{v*1000:4.0f}' for k, v in gap.items())}]")

            # M1's own readback: the primitive's grasp test, not a force read.
            z_before = float(spawner.position(sample)[2])
            tcp0 = arm.tcp_position().copy()
            arm.linear_target = tcp0 + np.array([0.0, 0.0, LIFT_M])
            linear_move(arm.linear_target, waypoints=20, steps=30)
            step(40)
            z_after = float(spawner.position(sample)[2])
            dz_lift = z_after - z_before
            say(f"[p106] C lift {category} flange_up={float(arm.tcp_position()[2]-tcp0[2])*1000:+.1f}mm "
                f"fruit_dz={dz_lift*1000:+.1f}mm grasped={dz_lift > 0.004}")

            # The axial pull: the arm holds, the payload is loaded down the tool
            # axis (P104's protocol, in-scene).
            rigid = spawner._rigids[sample.index]
            start = spawner.position(sample).copy()
            weight = float(sample.mass) * 9.81
            applied = 0.0
            f_break = float("nan")
            f_exit = float("nan")
            disp_at = 0.0
            max_disp = 0.0
            pry = float("nan")
            tip0 = tips()
            for _ in range(int(round(F_MAX / (RATE * DT)))):
                applied = min(F_MAX, applied + RATE * DT)
                rigid.apply_forces(np.array([tool_axis * applied], dtype=float))
                step(1)
                disp = float(np.linalg.norm(spawner.position(sample) - start))
                max_disp = max(max_disp, disp)
                if np.isnan(f_break) and disp >= BREAK_M:
                    f_break = applied + weight
                    disp_at = disp
                    pry = max(float(np.linalg.norm(tips()[k] - tip0[k])) for k in FINGERS) * 1000.0
                if not np.isnan(f_break) and max_disp >= EXIT_M:
                    f_exit = applied + weight
                    break
            # Creep at the operating load is read *before* the ramp (the settle
            # above); this row records the displacement at the 2 mm tick.
            rows.append({"phase": "C", "form": "allegro", "fruit": category, "rep": rep,
                         "d_mm": d * 1000.0, "mass_g": float(sample.mass) * 1000.0,
                         "mu": float(sample.friction), "creep_mm": creep * 1000.0,
                         "tau": tau_per, "tau_max": reached_tau,
                         "n_fingers": len(loaded),
                         "n": n, "loaded": len(loaded), "curl": SEAT_CURL, "cap": SEAT_CAP,
                         "lift_mm": dz_lift * 1000.0, "grasped": bool(dz_lift > 0.004),
                         "f_break": f_break, "disp_mm": disp_at * 1000.0,
                         "f_exit": f_exit, "max_disp_mm": max_disp * 1000.0, "pry_mm": pry})
            say(f"[p106] C pull {category:10s} F2mm={f_break:6.2f}N Fexit={f_exit:6.2f}N "
                f"max={max_disp*1000:5.1f}mm pry={pry:6.2f}mm")

            set_curl(0.0, SEAT_CAP)
            step(20)
            spawner.park(sample)
            step(10)

    print("[p106] JSON " + json.dumps(rows))
    say(f"[p106] DONE phase={PHASE} rows={len(rows)} wall={time.time()-wall0:.1f}s")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    sys.exit(code)
