"""Randomized fruit objects and the conveyor spawner.

Fruit quality attributes (grade, ripeness, defects) are NOT perceived - the task
scope for now is pick-and-sort of moving fruit, so those attributes are drawn at
random and used only as task labels.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.experimental.prims import RigidPrim

from .assets import SceneConfig
from .common import say
from .meshes import FRUIT_SHAPES, author_fruit, author_stem, make_material


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
        self.stats = {"released": 0, "reached_end": 0, "fell_off": 0}
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
        # NOTE: do not zero sleepThreshold / stabilizationThreshold here. Setting
        # stabilizationThreshold to 0 leaves the body permanently stabilised, and
        # such a body ignores contacts - the gripper closes straight through it
        # (see scripts/43_fruit_vs_box.py: a static box of the same size blocks
        # the fingers, the fruit does not).

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
        PhysxSchema.PhysxRigidBodyAPI.Apply(prim)

    def respawn(self, sample: FruitSample, y: float | None = None, x_jitter: float = 0.10) -> None:
        """Drop a fruit onto the belt at the upstream end.

        The fruit is placed a few centimetres above the surface and falls onto
        it, so the physics engine never has to resolve an interpenetration.
        """
        cfg = self.cfg
        x = cfg.spawn_x if y is None else y
        y = self.rng.uniform(-cfg.spawn_y_jitter, cfg.spawn_y_jitter)
        z = cfg.belt_center[2] + cfg.belt_size[2] / 2.0 + sample.diameter / 2.0 + 0.03
        rigid = self._rigids[sample.index]
        rigid.set_world_poses(
            positions=[[x, y, z]],
            orientations=[[1.0, 0.0, 0.0, 0.0]],
        )
        rigid.set_velocities(
            linear_velocities=[[cfg.belt_speed, 0.0, 0.0]],
            angular_velocities=[[0.0, 0.0, 0.0]],
        )
        sample.parked = False
        sample.held = False
        sample.attached = False

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

    def reset(self) -> None:
        """Park every fruit and restart the release schedule."""
        for sample in self.samples:
            self.park(sample)
        self.active = []
        self._cursor = 0
        self._next_release = 0.0
        app_utils.update_app(steps=1)

    def release_next(self) -> FruitSample:
        """Randomize and drop the next queued fruit at the belt entrance."""
        sample = self.samples[self._cursor % len(self.samples)]
        self._cursor += 1
        self.respawn(sample)
        if sample not in self.active:
            self.active.append(sample)
        self.stats["released"] += 1
        return sample

    def update(self, sim_time: float) -> list[FruitSample]:
        """Release on schedule and recycle fruit that reached the downstream end."""
        released = []
        if sim_time >= self._next_release:
            released.append(self.release_next())
            self._next_release = sim_time + self.cfg.spawn_period_s
        self.enforce_transport()
        for sample in list(self.active):
            if sample.parked:
                self.active.remove(sample)
                continue
            pos = self.position(sample)
            x = float(pos[0])
            # Recycle fruit that reached the end of the line, or that fell off
            # the belt for any reason (small round fruit can escape low rails).
            fell_off = float(pos[2]) < self.cfg.belt_center[2] - 0.25
            if x < self.cfg.despawn_x or fell_off:
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
        expected = self.cfg.belt_speed * self.cfg.transport_efficiency
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
            if abs(float(vel[0])) < 0.02:
                self._rigids[sample.index].set_velocities(
                    linear_velocities=[[expected, 0.0, 0.0]],
                    angular_velocities=[[0.0, 0.0, 0.0]],
                )

    def prime(self, count: int = 2) -> None:
        """Pre-load a few fruit so the belt is not empty at t=0."""
        for _ in range(count):
            sample = self.release_next()
            # Space the pre-loaded fruit downstream along the belt, not past its
            # upstream end.
            self.respawn(sample, y=self.cfg.spawn_x - 0.30 * (len(self.active) - 1))
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
