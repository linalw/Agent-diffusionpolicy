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

    The robot faces ``+X``. The conveyor runs along ``Y`` in front of the robot,
    downstream toward ``+Y``. Bins sit at the far end of the conveyor.

    Dimensions were calibrated against the real OpenArm workspace measured by
    ``scripts/12_reach_calibration.py``: shoulders at ``(0, +/-0.0935, 1.448)``
    and a TCP reach radius of ~0.68 m (p90 0.63 m). The TCP cannot go below
    ``z = 0.90 m``, so the belt surface sits at ``z = 0.95 m`` and the bins are
    raised on stands.
    """

    # Robot mounting
    table_top_z: float = 0.75
    robot_base_z: float = 0.75
    pedestal_center_xy: tuple[float, float] = (-0.10, 0.0)
    pedestal_size: tuple[float, float] = (0.40, 0.70)

    # Conveyor. Width is limited to the reachable band: at belt height the TCP
    # can only reach |horizontal offset| <= ~0.46 m from the shoulders.
    belt_center: tuple[float, float, float] = (0.28, 0.0, 0.93)
    belt_size: tuple[float, float, float] = (0.32, 2.40, 0.06)
    # Commanded PhysX surface velocity along +Y. Measured belt transport is about
    # 2/3 of this value because the surface-velocity solver clamps the tangential
    # force by Coulomb friction, so 0.30 gives ~0.20 m/s of real transport.
    belt_speed: float = 0.30
    belt_friction: float = 0.9

    # Fruit spawn / removal window along the belt, and the arm picking window
    spawn_y: float = -1.05
    # Recycle fruit before they roll off the downstream end of the belt (y = 1.2).
    despawn_y: float = 1.05
    pick_y_range: tuple[float, float] = (-0.35, 0.35)
    spawn_period_s: float = 1.6

    # Output bins (raised on stands so the TCP can reach into them)
    bin_positions: tuple[tuple[float, float], ...] = ((-0.08, 0.52), (-0.08, -0.52))
    bin_size_xy: float = 0.28
    bin_height: float = 0.22
    bin_stand_height: float = 0.80

    # Head camera (single RGB-D camera mounted on a short mast above the torso,
    # standing in for a humanoid head)
    head_camera_z: float = 1.72
    head_camera_forward: float = 0.15
    head_camera_target: tuple[float, float, float] = (0.34, 0.0, 0.92)
    camera_focal_length: float = 0.016  # 16 mm on a meter stage
    camera_aperture: tuple[float, float] = (0.036, 0.02025)
    camera_resolution: tuple[int, int] = (480, 848)  # (height, width)

    # Fruit population
    num_fruits: int = 12
    fruit_dimensions: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            # name -> (min diameter m, max diameter m)
            "strawberry": (0.030, 0.045),
            "lychee": (0.028, 0.038),
            "kiwi": (0.050, 0.070),
            "tomato": (0.050, 0.070),
            "apple": (0.070, 0.090),
            "orange": (0.070, 0.085),
            "peach": (0.060, 0.080),
            "pear": (0.060, 0.080),
        }
    )
    grades: tuple[str, ...] = ("A", "B", "C")
