"""Randomized fruit objects and the conveyor spawner.

Fruit quality attributes (grade, ripeness, defects) are NOT perceived - the task
scope for now is pick-and-sort of moving fruit, so those attributes are drawn at
random and used only as task labels.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass

import numpy as np
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.experimental.prims import RigidPrim

from .assets import SceneConfig
from .common import say
from .meshes import FRUIT_SHAPES, author_fruit, author_stem, make_material


def tune_contact_body(prim) -> None:
    """Contact-stability tuning for a fruit rigid body.

    The kinematic pads model the grip by *interfering* with the fruit: their
    faces are commanded ~2 % inside its diameter, so every tick PhysX depenetrates
    the fruit back out. With the default (unlimited) depenetration velocity that
    ejection is violent - the payload rattles inside the closed pads at
    0.3-0.5 m/s with a ~5 mm swing (measured, logs/266) - which is both what the
    slip monitor kept reacting to and what makes the grasp look twitchy.
    Capping the depenetration speed turns the same contact into a gentle, damped
    push, and a little body damping removes the residual ringing.

    All three are opt-in through the environment so the default stays the plain
    PhysX behaviour unless asked otherwise.
    """
    api = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
    api.CreateEnableCCDAttr().Set(False)
    for name, env, default in (
        ("MaxDepenetrationVelocity", "FRUIT_MAX_DEPEN_VELOCITY", "0"),
        ("LinearDamping", "FRUIT_LINEAR_DAMPING", "0"),
        ("AngularDamping", "FRUIT_ANGULAR_DAMPING", "0"),
    ):
        value = float(os.environ.get(env, default))
        if value <= 0.0:
            continue
        create = getattr(api, f"Create{name}Attr", None)
        if create is None:
            say(f"warning: PhysX rigid-body attribute {name} is not available here")
            continue
        create().Set(value)


@dataclass
class FruitSample:
    """Metadata attached to one spawned fruit."""

    index: int
    prim_path: str
    category: str
    diameter: float
    mass: float
    friction: float
    grade: str
    ripeness: float
    defective: bool
    parked: bool = True
    #: Set once the gripper has closed on this fruit, so the belt stops driving it.
    held: bool = False
    #: Set while the gripper is carrying this fruit (see ``attach``).
    attached: bool = False


def _preview_material(stage: Usd.Stage, path: str, rgb: tuple[float, float, float], roughness: float = 0.45):
    material = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*rgb))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


class FruitSpawner:
    """Owns a fixed pool of fruit rigid bodies recycled onto the belt."""

    # Approximate visual colour per category (roughness differs for fuzzy fruit).
    CATEGORY_STYLE = {
        "strawberry": ((0.85, 0.12, 0.14), 0.55),
        "lychee": ((0.80, 0.25, 0.22), 0.65),
        "kiwi": ((0.45, 0.32, 0.16), 0.85),
        "tomato": ((0.88, 0.20, 0.12), 0.35),
        "apple": ((0.80, 0.10, 0.12), 0.30),
        "orange": ((0.92, 0.50, 0.10), 0.75),
        "peach": ((0.95, 0.60, 0.45), 0.80),
        "pear": ((0.72, 0.78, 0.25), 0.45),
    }

    def __init__(self, stage: Usd.Stage, cfg: SceneConfig, root: str = "/World/Fruits", seed: int = 0):
        self.stage = stage
        self.cfg = cfg
        self.root = root
        self.rng = random.Random(seed)
        self.samples: list[FruitSample] = []
        self.active: list[FruitSample] = []
        self._rigids: dict[int, RigidPrim] = {}
        self._attach_offset: dict[int, np.ndarray] = {}
        self._cursor = 0
        self._next_release = 0.0
        #: Index of the fruit the task is currently working on: it must never be
        #: recirculated, otherwise the pads end up chasing a *parked* body (measured,
        #: logs/351: pads and "fruit" both at x = -1.5 m while the arm was at the
        #: pick station).
        self.protected: int | None = None
        self._waited: dict[int, float] = {}
        self._last_sim_time = 0.0
        #: Seconds each fruit has been sitting still in a discharge tray; the
        #: spawner recycles it once the dwell passes `cfg.output_tray_dwell_s`.
        self._tray_dwell: dict[int, float] = {}
        self.stats = {"released": 0, "reached_end": 0, "fell_off": 0, "discharged": 0}
        #: Set to a CleatedBelt so the cleats advance with the physics loop.
        self.belt = None
        stage.DefinePrim(root, "Xform")

    # ------------------------------------------------------------------ #
    def create_pool(self) -> None:
        categories = list(self.cfg.fruit_dimensions.keys())
        for i in range(self.cfg.num_fruits):
            category = categories[i % len(categories)]
            self._create_fruit(i, category)
        say(f"created {len(self.samples)} fruit rigid bodies")

    def _create_fruit(self, index: int, category: str) -> None:
        lo, hi = self.cfg.fruit_dimensions[category]
        diameter = self.rng.uniform(lo, hi)
        # Mass roughly scales with volume; density ~ 700 kg/m^3 (fruit is buoyant).
        mass = float(700.0 * (4.0 / 3.0) * np.pi * (diameter / 2.0) ** 3)
        friction = self.rng.uniform(0.4, 1.1)

        path = f"{self.root}/Fruit_{index:02d}"
        # Real fruit geometry: a procedural mesh at the final size, authored with
        # no Scale op (PhysX mis-cooks scaled shapes - see WORKLOG).
        shape = FRUIT_SHAPES[category]
        base = shape.colors[self.rng.randrange(len(shape.colors))]
        colour = tuple(
            float(np.clip(c + self.rng.uniform(-0.05, 0.05), 0.0, 1.0)) for c in base
        )
        fruit_mesh = author_fruit(self.stage, path, shape, diameter, self.rng, colour)
        author_stem(self.stage, f"{path}_stem", shape, diameter, self.rng)

        xform = UsdGeom.Xformable(fruit_mesh)
        xform.ClearXformOpOrder()
        xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, -5.0))

        prim = fruit_mesh.GetPrim()
        # Mass follows the volume of the actual shape, not just the diameter.
        mass = float(shape.density * (4.0 / 3.0) * np.pi * (diameter / 2.0) ** 3 * 0.82)
        friction = self.rng.uniform(*shape.friction)
        UsdPhysics.RigidBodyAPI.Apply(prim)
        mass_api = UsdPhysics.MassAPI.Apply(prim)
        mass_api.CreateMassAttr().Set(mass)

        phys_material = UsdShade.Material.Define(self.stage, f"{path}_physmat")
        phys_api = UsdPhysics.MaterialAPI.Apply(phys_material.GetPrim())
        phys_api.CreateStaticFrictionAttr().Set(friction)
        phys_api.CreateDynamicFrictionAttr().Set(friction)
        phys_api.CreateRestitutionAttr().Set(self.rng.uniform(0.02, 0.2))
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(
            phys_material, UsdShade.Tokens.weakerThanDescendants, "physics"
        )

        rigid_api = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
        rigid_api.CreateEnableCCDAttr().Set(False)
        # Sleeping is the reason a closing gripper can pass straight through a
        # fruit: a body PhysX has put to sleep is not woken by the approaching
        # finger, so the pads close to their commanded gap with zero contact.
        # FRUIT_NO_SLEEP=1 keeps every fruit awake (sleepThreshold 0 = never
        # sleep). Note it must be sleepThreshold, *not* stabilizationThreshold:
        # setting the latter to 0 leaves the body permanently stabilised, which
        # also ignores contacts (see scripts/43_fruit_vs_box.py).
        # Sleeping is the default-on guard whenever the kinematic gripper is in
        # use (a sleeping body is not woken by the approaching pads, which reads
        # as "the gripper closed on air"). FRUIT_NO_SLEEP=0 disables it.
        no_sleep = os.environ.get("FRUIT_NO_SLEEP")
        if no_sleep is None:
            no_sleep = "1" if os.environ.get("FRUIT_KINEMATIC_GRIPPER", "1") == "1" else "0"
        if no_sleep == "1":
            rigid_api.CreateSleepThresholdAttr().Set(0.0)
        tune_contact_body(prim)

        self.samples.append(
            FruitSample(
                index=index,
                prim_path=path,
                category=category,
                diameter=diameter,
                mass=mass,
                friction=friction,
                grade=self.rng.choice(self.cfg.grades),
                ripeness=self.rng.uniform(0.4, 1.0),
                defective=self.rng.random() < 0.12,
                parked=False,
            )
        )

    # ------------------------------------------------------------------ #
    def refresh_rigids(self) -> None:
        """(Re)build rigid prim handles; call after the simulation starts."""
        for sample in self.samples:
            self._rigids[sample.index] = RigidPrim(sample.prim_path)

    def rescale(self, sample: FruitSample, category: str, diameter: float) -> None:
        """Change a recycled fruit's category/size (rebuilds its mesh)."""
        lo, hi = self.cfg.fruit_dimensions[category]
        sample.category = category
        sample.diameter = float(np.clip(diameter, lo, hi))
        shape = FRUIT_SHAPES[category]
        sample.mass = float(
            shape.density * (4.0 / 3.0) * np.pi * (sample.diameter / 2.0) ** 3 * 0.82
        )
        sample.friction = self.rng.uniform(*shape.friction)
        sample.grade = self.rng.choice(self.cfg.grades)
        sample.ripeness = self.rng.uniform(0.4, 1.0)
        sample.defective = self.rng.random() < 0.12

        # Re-author the mesh at the new size rather than scaling the prim.
        stage = self.stage
        stem_path = f"{sample.prim_path}_stem"
        if stage.GetPrimAtPath(stem_path).IsValid():
            stage.RemovePrim(stem_path)
        stage.RemovePrim(sample.prim_path)
        base = shape.colors[self.rng.randrange(len(shape.colors))]
        colour = tuple(
            float(np.clip(c + self.rng.uniform(-0.05, 0.05), 0.0, 1.0)) for c in base
        )
        mesh = author_fruit(stage, sample.prim_path, shape, sample.diameter, self.rng, colour)
        author_stem(stage, stem_path, shape, sample.diameter, self.rng)
        xform = UsdGeom.Xformable(mesh)
        xform.ClearXformOpOrder()
        xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, -5.0))
        prim = mesh.GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(prim)
        UsdPhysics.MassAPI.Apply(prim).CreateMassAttr().Set(sample.mass)
        phys_material = UsdShade.Material.Define(stage, f"{sample.prim_path}_physmat")
        phys_api = UsdPhysics.MaterialAPI.Apply(phys_material.GetPrim())
        phys_api.CreateStaticFrictionAttr().Set(sample.friction)
        phys_api.CreateDynamicFrictionAttr().Set(sample.friction)
        phys_api.CreateRestitutionAttr().Set(self.rng.uniform(0.02, 0.2))
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(
            phys_material, UsdShade.Tokens.weakerThanDescendants, "physics"
        )
        tune_contact_body(prim)

    def respawn(self, sample: FruitSample, along: float | None = None, x_jitter: float = 0.10) -> None:
        """Drop a fruit onto the belt at the upstream end.

        ``along`` overrides the along-the-line (Y) spawn position. The fruit is
        placed a few centimetres above the surface and falls onto it, so the
        physics engine never has to resolve an interpenetration.
        """
        cfg = self.cfg
        y = cfg.spawn_y if along is None else along
        x = cfg.belt_center[0] + self.rng.uniform(-cfg.lateral_jitter, cfg.lateral_jitter)
        z = cfg.belt_center[2] + cfg.belt_size[2] / 2.0 + sample.diameter / 2.0 + 0.03
        rigid = self._rigids[sample.index]
        rigid.set_world_poses(
            positions=[[x, y, z]],
            orientations=[[1.0, 0.0, 0.0, 0.0]],
        )
        rigid.set_velocities(
            linear_velocities=[[0.0, cfg.belt_speed, 0.0]],
            angular_velocities=[[0.0, 0.0, 0.0]],
        )
        sample.parked = False
        sample.held = False
        sample.attached = False
        self._tray_dwell.pop(sample.index, None)

    # ------------------------------------------------------------------ #
    # Conveyor feeding
    # ------------------------------------------------------------------ #
    def park(self, sample: FruitSample) -> None:
        """Move a fruit out of the scene.

        Each fruit gets its own far-away slot: parking several bodies at the same
        point makes them interpenetrate and PhysX resolves that with explosive
        contact forces.
        """
        rigid = self._rigids[sample.index]
        x = 60.0 + 3.0 * sample.index
        rigid.set_world_poses(positions=[[x, 0.0, -50.0]], orientations=[[1.0, 0.0, 0.0, 0.0]])
        rigid.set_velocities(linear_velocities=[[0.0, 0.0, 0.0]], angular_velocities=[[0.0, 0.0, 0.0]])
        sample.parked = True
        self._tray_dwell.pop(sample.index, None)

    def reset(self) -> None:
        """Park every fruit and restart the release schedule."""
        for sample in self.samples:
            self.park(sample)
        self.active = []
        self._cursor = 0
        self._next_release = 0.0
        self._tray_dwell.clear()
        app_utils.update_app(steps=1)

    def release_next(self) -> FruitSample:
        """Randomize and drop the next queued fruit at the belt entrance."""
        sample = self.samples[self._cursor % len(self.samples)]
        self._cursor += 1
        # The feeder's next slot can already be occupied by a fruit that is
        # sitting in a discharge tray. `respawn` teleports it upstream (that is
        # the recycle), so classify it first: a tray fruit is the output line's
        # end, never `fell_off`. Without this, the scheduled release stole a
        # tray fruit *before* the settle dwell could count it (seen in the clip
        # run `logs/481`: the fruit vanished from the tray with no event).
        if not sample.parked and sample.index in self._rigids and not sample.held:
            pos = self.position(sample)
            if self.cfg.on_output_tray(pos):
                self.stats["discharged"] += 1
                say(
                    f"[belt] {sample.category} (index {sample.index}) discharged to the tray "
                    f"at x={float(pos[0]):.2f} (recycled by the feeder schedule)"
                )
        self.respawn(sample)
        if sample not in self.active:
            self.active.append(sample)
        self.stats["released"] += 1
        return sample

    def update(self, sim_time: float) -> list[FruitSample]:
        """Release on schedule and recycle fruit that reached the downstream end."""
        released = []
        # Recirculation. A fruit that waits in the queue window without being
        # picked for FRUIT_MAX_WAIT_S seconds of simulated time goes back to the
        # feeder (park -> released again later), which is what a return line does
        # and what keeps the queue from growing without bound now that the gate
        # presents one fruit at a time.
        dt = max(0.0, float(sim_time) - float(getattr(self, "_last_sim_time", sim_time)))
        self._last_sim_time = float(sim_time)
        wait_limit = float(os.environ.get("FRUIT_MAX_WAIT_S", "60"))
        if wait_limit > 0.0:
            for sample in list(self.active):
                if sample.parked or sample.held or sample.index == self.protected:
                    continue
                pos = self.position(sample)
                along = float(pos[1])
                lateral = float(pos[0])
                # Only fruit still *on the main belt* count as queued: a fruit on
                # the raised output line is at the same along-position but off the
                # centre line, and parking those emptied the output bins in the
                # v2 layout (seen in logs/292, where recirculation fired on
                # already-placed fruit).
                on_belt = abs(lateral - self.cfg.belt_center[0]) < 0.30
                if on_belt and self.cfg.pick_y - 0.10 <= along <= self.cfg.pick_y + 0.45:
                    waited = float(getattr(self, "_waited", {}).get(sample.index, 0.0)) + dt
                    self._waited[sample.index] = waited
                    if waited > wait_limit:
                        self.stats["recirculated"] = self.stats.get("recirculated", 0) + 1
                        say(
                            f"[belt] recirculating {sample.category} (index {sample.index}): "
                            f"waited {waited:.0f}s at the gate"
                        )
                        self.park(sample)
                        self.active.remove(sample)
                        self._waited.pop(sample.index, None)
                elif hasattr(self, "_waited"):
                    self._waited[sample.index] = 0.0
        # Line-full interlock. With a gate at the pick station the fruit behind it
        # queue up, and every queued body joins one contact island with the belt
        # and the cleats: the step time grew until the simulation ran at ~0.1x
        # real time (logs/275, 35 min for four attempts). Real lines do not push
        # product into a full buffer either, so the release is held while the
        # queue just upstream of the gate is already `FRUIT_QUEUE_MAX` deep.
        queue_max = int(os.environ.get("FRUIT_QUEUE_MAX", "6"))
        gate_y = self.cfg.pick_y
        queued = 0
        for sample in self.active:
            if sample.parked or sample.held:
                continue
            pos = self.position(sample)
            along = float(pos[1])
            # Only fruit still on the main belt are in the queue. Fruit sitting
            # on the raised output conveyors are off the centre line, and counting
            # them held the release interlock shut, so the line starved after the
            # output bins began to fill ("no eligible fruit", logs/295).
            if (
                abs(float(pos[0]) - self.cfg.belt_center[0]) < 0.30
                and gate_y - 0.05 <= along <= gate_y + 0.45
            ):
                queued += 1
        if sim_time >= self._next_release and queued < queue_max:
            released.append(self.release_next())
            self._next_release = sim_time + self.cfg.spawn_period_s
        self.enforce_transport()
        tray_dwell_s = float(self.cfg.output_tray_dwell_s)
        for sample in list(self.active):
            if sample.parked:
                self.active.remove(sample)
                continue
            pos = self.position(sample)
            along = float(pos[1])
            # End of the output line. A fruit that has settled in a discharge
            # tray has finished its cycle; the tray is real end-of-line hardware
            # (`conveyor.OutputBelt._build_discharge`), so this is counted as
            # `discharged`, not as a fruit that fell off. The dwell is for the
            # clip and for the tray to actually hold the fruit for a moment.
            if not sample.held and self.cfg.on_output_tray(pos):
                speed = float(np.linalg.norm(self.velocity(sample)))
                if speed < 0.05:
                    dwell = self._tray_dwell.get(sample.index, 0.0) + dt
                    self._tray_dwell[sample.index] = dwell
                    if dwell >= tray_dwell_s:
                        self.stats["discharged"] += 1
                        say(
                            f"[belt] {sample.category} (index {sample.index}) discharged to the "
                            f"tray at x={float(pos[0]):.2f} (settled {dwell:.1f}s)"
                        )
                        self.park(sample)
                        self.active.remove(sample)
                else:
                    self._tray_dwell[sample.index] = 0.0
                continue
            # A fruit still on the chute is between the belt top and the tray:
            # not on the main belt, not on the floor. Suppress `fell_off` while it
            # is inside the discharge envelope, or it would be recycled mid-slide.
            fell_off = float(pos[2]) < self.cfg.belt_center[2] - 0.25
            if fell_off and not sample.held and self.cfg.on_output_discharge(pos):
                fell_off = False
            # Recycle fruit that reached the end of the line, or that fell off
            # the belt for any reason (small round fruit can escape).
            if along < self.cfg.despawn_y or fell_off:
                self.stats["fell_off" if fell_off else "reached_end"] += 1
                self.park(sample)
                self.active.remove(sample)
        return released

    def enforce_transport(self, dt: float = 1.0 / 120.0) -> None:
        """Keep fruit moving on the belt.

        Transport itself is physical: the belt's surface velocity plus the rubber
        friction material carry the fruit, and the cleats push them along. This
        method only wakes a fruit that PhysX has put to sleep (a sleeping body
        ignores conveyor contact forces), so nothing freezes mid-belt.
        """
        if self.belt is not None:
            self.belt.step(dt)
        # Follow the belt's *current* speed: at the pick station the line is
        # stopped, and nudging fruit then would push it out of the jaws.
        speed = self.belt.speed if self.belt is not None else self.cfg.belt_speed
        expected = speed * self.cfg.transport_efficiency
        if abs(expected) < 1e-6:
            return
        for sample in self.active:
            if sample.parked or sample.held:
                continue
            pos = self.position(sample)
            on_belt = (
                abs(pos[2] - (self.cfg.belt_center[2] + self.cfg.belt_size[2] / 2.0 + sample.diameter / 2.0))
                < 0.03
            )
            if not on_belt:
                continue
            vel = self.velocity(sample)
            if abs(float(vel[1])) < 0.02:
                self._rigids[sample.index].set_velocities(
                    linear_velocities=[[0.0, expected, 0.0]],
                    angular_velocities=[[0.0, 0.0, 0.0]],
                )

    def prime(self, count: int = 2) -> None:
        """Pre-load a few fruit so the belt is not empty at t=0."""
        for _ in range(count):
            sample = self.release_next()
            # Space the pre-loaded fruit downstream (-Y), not past the upstream end.
            self.respawn(sample, along=self.cfg.spawn_y - 0.30 * (len(self.active) - 1))
        app_utils.update_app(steps=1)

    def position(self, sample: FruitSample) -> np.ndarray:
        pos = self._rigids[sample.index].get_world_poses()[0]
        return np.asarray(pos.numpy() if hasattr(pos, "numpy") else pos)[0]

    def stop(self, sample: FruitSample) -> None:
        """Zero a fruit's velocity so it stays where the gripper found it."""
        self._rigids[sample.index].set_velocities(
            linear_velocities=[[0.0, 0.0, 0.0]], angular_velocities=[[0.0, 0.0, 0.0]]
        )

    def place(self, sample: FruitSample, position: np.ndarray) -> None:
        """Teleport a fruit to an exact position and hold it there."""
        self._rigids[sample.index].set_world_poses(
            positions=[np.asarray(position, dtype=float).tolist()],
            orientations=[[1.0, 0.0, 0.0, 0.0]],
        )
        self.stop(sample)

    # ------------------------------------------------------------------ #
    # Grasp attachment
    # ------------------------------------------------------------------ #
    def attach(self, sample: FruitSample, gripper_point: np.ndarray) -> None:
        """Attach a fruit to the gripper.

        The OpenArm finger collision meshes do not reliably contact small fruit
        in this build (see WORKLOG), so a closed, centred grasp is represented by
        attaching the fruit to the gripper and carrying it kinematically. The
        recorded offset is the fruit's position relative to the gripper point at
        the moment of the grasp, so the payload keeps its pose in the hand.
        """
        position = self.position(sample).copy()
        self._attach_offset[sample.index] = position - np.asarray(gripper_point, dtype=float)
        sample.attached = True
        sample.held = True

    def detach(self, sample: FruitSample) -> None:
        sample.attached = False
        self._attach_offset.pop(sample.index, None)

    def follow(self, sample: FruitSample, gripper_point: np.ndarray) -> None:
        """Place an attached fruit at the gripper, preserving the grasp offset."""
        if not sample.attached:
            return
        offset = self._attach_offset[sample.index]
        target = np.asarray(gripper_point, dtype=float) + offset
        self._rigids[sample.index].set_world_poses(
            positions=[target.tolist()], orientations=[[1.0, 0.0, 0.0, 0.0]]
        )
        self._rigids[sample.index].set_velocities(
            linear_velocities=[[0.0, 0.0, 0.0]], angular_velocities=[[0.0, 0.0, 0.0]]
        )

    def velocity(self, sample: FruitSample) -> np.ndarray:
        vel = self._rigids[sample.index].get_velocities()[0]
        return np.asarray(vel.numpy() if hasattr(vel, "numpy") else vel)[0]

    def angular(self, sample: FruitSample) -> np.ndarray:
        """World angular velocity of one fruit [rad/s].

        The transport probe needs it to say whether a fruit is being *carried*
        (`|omega| * r == |v|`, i.e. rolling on the belt) or *pushed* (no rotation),
        and the encoder-prior design in the notes assumes the second.
        """
        vel = self._rigids[sample.index].get_velocities()[1]
        return np.asarray(vel.numpy() if hasattr(vel, "numpy") else vel)[0]

    def fruit_pose(self, sample: FruitSample) -> tuple[np.ndarray, np.ndarray]:
        """World position and quaternion (w, x, y, z) of one fruit."""
        positions, orientations = self._rigids[sample.index].get_world_poses()
        return (
            np.asarray(
                positions.numpy() if hasattr(positions, "numpy") else positions
            )[0],
            np.asarray(
                orientations.numpy() if hasattr(orientations, "numpy") else orientations
            )[0],
        )

    def enable_contact_tracking(self, threshold: float = 0.05) -> int:
        """Turn on PhysX contact tracking for every fruit body.

        One call per body at setup, not per tick - the solver then accumulates the
        net contact force for free, and `net_contact_forces` only has to read it.
        Fruit reads are the *safe* class of readback: unlike arm-link reads they do
        not change the run (see the WORKLOG).
        """
        count = 0
        for rigid in self._rigids.values():
            try:
                rigid.set_enabled_contact_tracking(True, threshold=threshold)
                count += 1
            except Exception:  # noqa: BLE001
                continue
        return count

    def net_contact_forces(self) -> dict[int, list[float]]:
        """Net contact force on every live fruit [N], keyed by sample index."""
        out: dict[int, list[float]] = {}
        for sample in self.active:
            if sample.parked:
                continue
            rigid = self._rigids.get(sample.index)
            if rigid is None:
                continue
            try:
                force = rigid.get_net_contact_forces()
                array = np.asarray(force.numpy() if hasattr(force, "numpy") else force)
                out[sample.index] = array.reshape(-1)[:3].astype(float).tolist()
            except Exception:  # noqa: BLE001
                out[sample.index] = [0.0, 0.0, 0.0]
        return out

    def state(self) -> list[dict]:
        """Observation of all live fruit - the input to the slow loop's selector."""
        out = []
        for sample in self.active:
            if sample.parked:
                continue
            out.append(
                {
                    "index": sample.index,
                    "prim_path": sample.prim_path,
                    "category": sample.category,
                    "diameter": sample.diameter,
                    "mass": sample.mass,
                    "friction": sample.friction,
                    "grade": sample.grade,
                    "ripeness": sample.ripeness,
                    "defective": sample.defective,
                    "position": self.position(sample),
                    "velocity": self.velocity(sample),
                }
            )
        return out

    def positions(self) -> np.ndarray:
        out = []
        for sample in self.samples:
            pos = self._rigids[sample.index].get_world_poses()[0]
            out.append(np.asarray(pos.numpy() if hasattr(pos, "numpy") else pos)[0])
        return np.asarray(out)
