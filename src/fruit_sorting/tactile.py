"""Point tactile sensing on the gripper fingers.

Each finger link carries a contact sensor, so we get the contact force and the
contact point on that finger - the point-tactile signal the gripper provides.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from isaacsim.sensors.experimental.physics import Contact, ContactSensor
from isaacsim.core.experimental.prims import RigidPrim

from .common import say, to_numpy

FINGER_LINK_NAMES = {
    "left": ["openarm_left_left_finger", "openarm_left_right_finger"],
    "right": ["openarm_right_left_finger", "openarm_right_right_finger"],
}


@dataclass
class TactileReading:
    """Aggregated tactile state for one gripper."""

    side: str
    normal_force: float = 0.0
    contact_count: int = 0
    #: True when at least one finger sensor is attached to a valid rigid body.
    valid: bool = False
    fingertip_forces: dict[str, float] = field(default_factory=dict)

    @property
    def in_contact(self) -> bool:
        return self.contact_count > 0


class GripperTactile:
    """Contact sensors on the four finger links."""

    def __init__(self, root: str = "/World/Tactile"):
        self.root = root
        self.sensors: dict[str, ContactSensor] = {}
        self._prims: dict[str, object] = {}
        self._paths: dict[str, str] = {}

    def attach(
        self,
        robot=None,
        finger_links: dict[str, list[str]] | None = None,
        stage=None,
        robot_root: str = "/World/OpenArm",
    ) -> None:
        """Create contact sensors and force readers on the finger links.

        Pass either the articulation (`robot`, after the simulation has started)
        or the USD `stage` (before `play()`, which is what makes the contact
        views valid).
        """
        finger_links = finger_links or FINGER_LINK_NAMES
        finger_paths: dict[str, list[str]] = {}
        if robot is not None:
            link_paths = list(robot.link_paths)
            if link_paths and isinstance(link_paths[0], (list, tuple)):
                link_paths = link_paths[0]
            link_paths = [str(p[0] if isinstance(p, (list, tuple)) else p) for p in link_paths]
            link_names = list(robot.link_names)
            for side, names in finger_links.items():
                finger_paths[side] = [link_paths[link_names.index(n)] for n in names]
        else:
            for side, names in finger_links.items():
                finger_paths[side] = [f"{robot_root}/{n}" for n in names]

        for side, links in finger_paths.items():
            for i, link_path in enumerate(links):
                sensor_path = f"{link_path}/tactile_{i}"
                contact = Contact(sensor_path, min_threshold=0.0, max_threshold=1e6, radius=-1.0)
                self.sensors[f"{side}_{i}"] = ContactSensor(contact)
                # The IsaacContactSensor reports is_valid=False on this build, so
                # the net contact force from the rigid-body view is the reliable
                # signal. Contact tracking must be enabled before the physics
                # views are built, i.e. during authoring before play().
                prim = RigidPrim(link_path)
                prim.set_enabled_contact_tracking(True, threshold=1e-4)
                self._prims[f"{side}_{i}"] = prim
                self._paths[f"{side}_{i}"] = link_path
        say(
            f"attached {len(self.sensors)} tactile contact sensors "
            f"and {len(self._prims)} per-finger force readers"
        )

    def refresh(self) -> None:
        """Rebuild the force readers after the simulation starts.

        Rigid prims created during authoring have no physics contact view, so the
        handles must be recreated once the simulation is playing.
        """
        for key, path in self._paths.items():
            prim = RigidPrim(path)
            prim.set_enabled_contact_tracking(True, threshold=1e-4)
            self._prims[key] = prim
        say(f"refreshed {len(self._prims)} contact-force readers")

    def read(self) -> dict[str, TactileReading]:
        readings: dict[str, TactileReading] = {}
        for key, sensor in self.sensors.items():
            side = key.rsplit("_", 1)[0]
            reading = readings.setdefault(side, TactileReading(side=side))
            try:
                sample = sensor.get_sensor_reading()
            except Exception:  # noqa: BLE001
                reading.fingertip_forces[key] = 0.0
                continue
            # ContactSensorReading: .value is the summed contact force [N],
            # .in_contact is the boolean contact flag, .is_valid says whether the
            # sensor is attached to a rigid body at all.
            valid = bool(getattr(sample, "is_valid", False))
            magnitude = float(getattr(sample, "value", 0.0) or 0.0) if valid else 0.0
            in_contact = bool(getattr(sample, "in_contact", False)) if valid else False
            reading.valid = reading.valid and valid if reading.fingertip_forces else valid
            reading.normal_force += magnitude
            reading.contact_count += int(in_contact)
            reading.fingertip_forces[key] = magnitude
        return readings

    def summary(self) -> str:
        readings = self.read()
        return "  ".join(
            f"{side}: F={r.normal_force:6.2f}N n={r.contact_count}" for side, r in sorted(readings.items())
        )
