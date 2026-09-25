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
        self._cursor = 0
        self._next_release = 0.0
        self.stats = {"released": 0, "reached_end": 0, "fell_off": 0}
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
        sphere = UsdGeom.Sphere.Define(self.stage, path)
        sphere.GetRadiusAttr().Set(diameter / 2.0)

        xform = UsdGeom.Xformable(sphere)
        xform.ClearXformOpOrder()
        # Slightly squash the sphere so fruit are not perfect balls.
        xform.AddScaleOp().Set(
            Gf.Vec3f(
                self.rng.uniform(0.92, 1.0),
                self.rng.uniform(0.92, 1.0),
                self.rng.uniform(0.85, 1.0),
            )
        )
        xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, -5.0))

        rgb, roughness = self.CATEGORY_STYLE[category]
        jitter = tuple(float(np.clip(c + self.rng.uniform(-0.06, 0.06), 0.0, 1.0)) for c in rgb)
        material = _preview_material(self.stage, f"{path}_mat", jitter, roughness)
        UsdShade.MaterialBindingAPI.Apply(sphere.GetPrim()).Bind(material)

        UsdPhysics.CollisionAPI.Apply(sphere.GetPrim())
        UsdPhysics.RigidBodyAPI.Apply(sphere.GetPrim())
        mass_api = UsdPhysics.MassAPI.Apply(sphere.GetPrim())
        mass_api.CreateMassAttr().Set(mass)

        phys_material = UsdShade.Material.Define(self.stage, f"{path}_physmat")
        phys_api = UsdPhysics.MaterialAPI.Apply(phys_material.GetPrim())
        phys_api.CreateStaticFrictionAttr().Set(friction)
        phys_api.CreateDynamicFrictionAttr().Set(friction)
        phys_api.CreateRestitutionAttr().Set(self.rng.uniform(0.02, 0.2))
        UsdShade.MaterialBindingAPI.Apply(sphere.GetPrim()).Bind(phys_material)

        PhysxSchema.PhysxRigidBodyAPI.Apply(sphere.GetPrim()).CreateEnableCCDAttr().Set(True)

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
        """Change a recycled fruit's category/size for domain randomization."""
        lo, hi = self.cfg.fruit_dimensions[category]
        sample.category = category
        sample.diameter = float(np.clip(diameter, lo, hi))
        sample.mass = float(700.0 * (4.0 / 3.0) * np.pi * (sample.diameter / 2.0) ** 3)
        sample.friction = self.rng.uniform(0.4, 1.1)
        sample.grade = self.rng.choice(self.cfg.grades)
        sample.ripeness = self.rng.uniform(0.4, 1.0)
        sample.defective = self.rng.random() < 0.12

        prim = self.stage.GetPrimAtPath(sample.prim_path)
        UsdGeom.Sphere(prim).GetRadiusAttr().Set(sample.diameter / 2.0)
        UsdPhysics.MassAPI(prim).GetMassAttr().Set(sample.mass)
        rgb, roughness = self.CATEGORY_STYLE[category]
        jitter = tuple(float(np.clip(c + self.rng.uniform(-0.06, 0.06), 0.0, 1.0)) for c in rgb)
        material = _preview_material(self.stage, f"{sample.prim_path}_mat", jitter, roughness)
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(material)

    def respawn(self, sample: FruitSample, y: float | None = None, x_jitter: float = 0.10) -> None:
        """Drop a fruit onto the belt at the upstream end.

        The fruit is placed a few centimetres above the surface and falls onto
        it, so the physics engine never has to resolve an interpenetration.
        """
        cfg = self.cfg
        y = cfg.spawn_y if y is None else y
        x = cfg.belt_center[0] + self.rng.uniform(-x_jitter, x_jitter)
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
        for sample in list(self.active):
            if sample.parked:
                self.active.remove(sample)
                continue
            pos = self.position(sample)
            y = float(pos[1])
            # Recycle fruit that reached the end of the line, or that fell off
            # the belt for any reason (small round fruit can escape low rails).
            fell_off = float(pos[2]) < self.cfg.belt_center[2] - 0.25
            if y > self.cfg.despawn_y or fell_off:
                self.stats["fell_off" if fell_off else "reached_end"] += 1
                self.park(sample)
                self.active.remove(sample)
        return released

    def prime(self, count: int = 2) -> None:
        """Pre-load a few fruit so the belt is not empty at t=0."""
        for _ in range(count):
            sample = self.release_next()
            # Space the pre-loaded fruit downstream along the belt, not past its
            # upstream end.
            self.respawn(sample, y=self.cfg.spawn_y + 0.30 * (len(self.active) - 1))
        app_utils.update_app(steps=1)

    def position(self, sample: FruitSample) -> np.ndarray:
        pos = self._rigids[sample.index].get_world_poses()[0]
        return np.asarray(pos.numpy() if hasattr(pos, "numpy") else pos)[0]

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
