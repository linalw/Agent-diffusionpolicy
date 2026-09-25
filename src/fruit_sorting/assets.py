"""Asset locations and robot constants."""

from __future__ import annotations

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
# --------------------------------------------------------------------------- #
OPENARM_BIMANUAL_USD = isaac_asset("Robots/OpenArm/openarm_bimanual/openarm_bimanual.usd")

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

    The robot faces ``+X``. The conveyor runs along ``X``, end-on to the robot,
    with fruit travelling toward the robot (``-X``) so they pass between the
    gripper jaws. Bins sit either side of the belt at the picking station.

    Dimensions were calibrated against the real OpenArm workspace measured by
    ``scripts/12_reach_calibration.py``: shoulders at ``(0, +/-0.0935, 1.448)``
    m and a TCP reach radius of ~0.68 m (p90 0.63 m). The TCP cannot descend
    below ``z = 0.90`` m, and the finger links span about 8 cm *below* the jaw
    centre, so the belt surface sits at ``z = 1.01`` m and the bins stand on
    0.86 m pedestals.
    """

    # Robot mounting
    table_top_z: float = 0.75
    robot_base_z: float = 0.75
    pedestal_center_xy: tuple[float, float] = (-0.10, 0.0)
    pedestal_size: tuple[float, float] = (0.40, 0.70)

    # Conveyor.
    #
    # The OpenArm gripper's jaws open along the shoulder axis (the robot's local
    # Y). Fruit must therefore travel perpendicular to that, i.e. along the
    # robot's facing direction X, so a fruit moving down the belt passes between
    # the jaws instead of hitting one of them. The belt is end-on to the robot.
    #
    # Belt surface at z = 1.01 m: the gripper's jaw centre cannot go below
    # ~0.976 m (the wrist bottom is ~0.898 m and the jaws sit 0.078 m above the
    # tool point), so fruit must sit high enough for the fingers to straddle them.
    belt_center: tuple[float, float, float] = (0.95, 0.0, 1.14)
    belt_size: tuple[float, float, float] = (1.60, 0.34, 0.06)
    # Commanded PhysX surface velocity. Transport runs at roughly 2/3 of the
    # command because the surface-velocity solver clamps tangential force by
    # Coulomb friction. Negative: fruit travel toward the robot (-X).
    #
    # Kept deliberately slow: one `app_utils.update_app()` advances several
    # hundred milliseconds of simulated time on this machine, so a fast belt
    # would jump past the gripper in a handful of control iterations.
    belt_speed: float = -0.34
    belt_friction: float = 0.9
    #: Cleats turn the belt into a track. They travel with the belt and push
    #: fruit along, which is how a real cleated conveyor carries produce.
    cleat_count: int = 14
    cleat_spacing: float = 0.18
    cleat_width: float = 0.022
    cleat_height: float = 0.020
    #: Fraction of the commanded surface velocity that fruit actually reach.
    #: Lower than 1 because the cleats only push intermittently and the fruit
    #: slip against the belt between cleats.
    transport_efficiency: float = 0.40

    # Fruit spawn / removal window along the belt, and the arm picking window.
    spawn_x: float = 1.62
    despawn_x: float = 0.24
    pick_x: float = 0.34
    spawn_y_jitter: float = 0.005
    #: Guide rails funnel fruit along the centre line so they arrive between the
    #: jaws. The finger gap is only ~6.5 cm, so lateral drift breaks the grasp.
    belt_channel_y: float = 0.045
    spawn_period_s: float = 1.6

    # Output bins (raised on stands so the TCP can reach into them)
    bin_positions: tuple[tuple[float, float], ...] = ((0.34, 0.44), (0.34, -0.44))
    bin_size_xy: float = 0.28
    bin_height: float = 0.22
    bin_stand_height: float = 1.02

    # Head camera (single RGB-D camera mounted on a short mast above the torso,
    # standing in for a humanoid head)
    head_camera_z: float = 1.86
    head_camera_forward: float = 0.15
    head_camera_target: tuple[float, float, float] = (0.60, 0.0, 1.15)
    camera_focal_length: float = 0.016  # 16 mm on a meter stage
    camera_aperture: tuple[float, float] = (0.036, 0.02025)
    camera_resolution: tuple[int, int] = (480, 848)  # (height, width)

    # Fruit population
    num_fruits: int = 12
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

    #: Largest object the OpenArm 1-DoF parallel gripper can straddle. Measured
    #: at the pick pose (scripts/36_static_grasp.py): the link origins are
    #: 0.098 m apart at full opening, which leaves 0.0758 m between the finger
    #: faces. Keep a small margin for off-centre fruit.
    gripper_max_object: float = 0.072

    #: How far above the fruit's centre the jaw centre must sit for the finger
    #: span to straddle the fruit. Measured in scripts/45_grasp_height_test.py:
    #: contact stops happening above ~0.06 m and is reliable at 0.03-0.04 m.
    grasp_palm_offset: float = 0.040
