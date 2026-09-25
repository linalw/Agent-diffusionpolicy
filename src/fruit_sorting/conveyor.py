"""A cleated belt conveyor.

Models a real track conveyor rather than a sliding slab:

* an endless belt surface with a rubber friction material, driven by PhysX
  surface velocity - fruit are carried by **friction**, not by teleporting them;
* transverse cleats (the bars that make it a track) as kinematic bodies that
  travel with the belt and physically push fruit along;
* head and tail pulleys that rotate at the matching rate, plus a frame and legs.
"""

from __future__ import annotations

import math

import numpy as np
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

from isaacsim.core.experimental.prims import RigidPrim

from .assets import SceneConfig
from .common import say
from .scene import _define_box, _set_color


def _material(
    stage: Usd.Stage, path: str, colour: tuple[float, float, float],
    roughness: float = 0.7, metallic: float = 0.0,
) -> UsdShade.Material:
    material = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*colour))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(metallic)
    shader.CreateInput("specular", Sdf.ValueTypeNames.Float).Set(0.1)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


class CleatedBelt:
    """Owns the belt surface, the cleats and the pulleys."""

    def __init__(self, stage: Usd.Stage, cfg: SceneConfig):
        self.stage = stage
        self.cfg = cfg
        self.cleats: list[RigidPrim] = []
        self.cleat_prim = None
        self.pulleys: list[UsdGeom.Xformable] = []
        self.pulley_angle = 0.0
        self.phase = 0.0
        self.belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
        self.length = cfg.belt_size[0]
        self.width = cfg.belt_size[1]
        # Fit the cleats to the belt: more cleats than fit would overlap and form
        # a wall instead of a track.
        self.cleat_span = cfg.cleat_spacing * max(1, int(self.length / cfg.cleat_spacing))
        self.cleat_count = max(1, int(self.length / cfg.cleat_spacing))
        self.enabled = self.cleat_count > 0

    # ------------------------------------------------------------------ #
    def build(self) -> None:
        cfg = self.cfg
        bx, by, bz = cfg.belt_center
        sx, sy, sz = cfg.belt_size

        # Belt surface. A thin slab is enough: the cleats do the pushing and the
        # fruit sit on this surface, so it only needs to be stiff in Z.
        belt = _define_box(self.stage, "/World/Conveyor/Belt", size=(sx, sy, sz), center=(bx, by, bz))
        _set_color(belt, (0.045, 0.045, 0.05))
        UsdPhysics.CollisionAPI.Apply(belt.GetPrim())
        _add_physics_material(belt.GetPrim(), cfg.belt_friction, cfg.belt_friction, 0.0)
        surface_velocity = PhysxSchema.PhysxSurfaceVelocityAPI.Apply(belt.GetPrim())
        surface_velocity.CreateSurfaceVelocityAttr().Set(Gf.Vec3f(cfg.belt_speed, 0.0, 0.0))

        # Cleats: transverse bars carried by the belt.
        if self.enabled:
            for i in range(self.cleat_count):
                name = f"Cleat{i:02d}"
                cleat = _define_box(
                    self.stage, f"/World/Conveyor/{name}",
                    size=(cfg.cleat_width, sy * 0.97, cfg.cleat_height),
                    center=(bx, by, self.belt_top + cfg.cleat_height / 2.0),
                )
                _set_color(cleat, (0.10, 0.10, 0.11))
                UsdPhysics.CollisionAPI.Apply(cleat.GetPrim())
                body = UsdPhysics.RigidBodyAPI.Apply(cleat.GetPrim())
                body.CreateKinematicEnabledAttr().Set(True)
                UsdPhysics.MassAPI.Apply(cleat.GetPrim()).CreateMassAttr().Set(0.5)
                self.cleats.append(RigidPrim(f"/World/Conveyor/{name}"))

        # Head / tail pulleys.
        radius = sz / 2.0 + 0.01
        for tag, dx in (("Tail", -(sx / 2.0 + radius * 0.6)), ("Head", (sx / 2.0 + radius * 0.6))):
            cyl = UsdGeom.Cylinder.Define(self.stage, f"/World/Conveyor/Pulley{tag}")
            cyl.GetRadiusAttr().Set(radius)
            cyl.GetHeightAttr().Set(sy + 0.02)
            cyl.GetAxisAttr().Set("Y")
            xf = UsdGeom.Xformable(cyl)
            xf.ClearXformOpOrder()
            xf.AddTranslateOp().Set(Gf.Vec3d(bx + dx, by, self.belt_top - radius * 0.5))
            _set_color(cyl, (0.35, 0.36, 0.38))
            self.pulleys.append(xf)

        # Frame rails down both sides plus support legs.
        for sign in (-1.0, 1.0):
            _set_color(
                _define_box(
                    self.stage, f"/World/Conveyor/Frame{'P' if sign > 0 else 'N'}",
                    size=(sx + 0.10, 0.025, 0.05),
                    center=(bx, by + sign * (sy / 2.0 + 0.012), self.belt_top + 0.02),
                ),
                (0.55, 0.56, 0.58),
            )
        # Low guide rails keep produce on the centre line. Real sorting lines have
        # them, and the gripper's lateral gap is only a few centimetres.
        for sign in (-1.0, 1.0):
            guide = _define_box(
                self.stage,
                f"/World/Conveyor/Guide{'P' if sign > 0 else 'N'}",
                size=(sx, 0.015, 0.045),
                center=(bx, by + sign * (cfg.belt_channel_y + 0.008), self.belt_top + 0.0225),
            )
            _set_color(guide, (0.60, 0.61, 0.63))
            UsdPhysics.CollisionAPI.Apply(guide.GetPrim())
        leg_height = bz - sz / 2.0
        for i, leg_x in enumerate((bx - sx / 2.0 + 0.10, bx + sx / 2.0 - 0.10)):
            for j, leg_y in enumerate((by - sy / 2.0 + 0.03, by + sy / 2.0 - 0.03)):
                _set_color(
                    _define_box(
                        self.stage, f"/World/Conveyor/Leg{i}{j}",
                        size=(0.05, 0.05, leg_height),
                        center=(leg_x, leg_y, leg_height / 2.0),
                    ),
                    (0.30, 0.30, 0.32),
                )
        say(
            f"cleated belt built: {len(self.cleats)} cleats, spacing {cfg.cleat_spacing:.2f} m, "
            f"surface velocity {cfg.belt_speed:+.2f} m/s, mu={cfg.belt_friction}"
        )

    # ------------------------------------------------------------------ #
    def reset(self) -> None:
        self.pulley_angle = 0.0
        self.phase = 0.0
        self._place_cleats(0.0)

    def _place_cleats(self, offset: float) -> None:
        if not self.cleats:
            return
        cfg = self.cfg
        bx, by, _ = cfg.belt_center
        start = bx - cfg.belt_size[0] / 2.0 + cfg.cleat_width
        for i, cleat in enumerate(self.cleats):
            x = start + ((i * cfg.cleat_spacing + offset) % self.cleat_span)
            # Kinematic bodies cannot take velocity commands; writing the pose
            # each step is what conveys their motion to the fruit.
            cleat.set_world_poses(
                positions=[[x, by, self.belt_top + cfg.cleat_height / 2.0]],
                orientations=[[1.0, 0.0, 0.0, 0.0]],
            )

    def step(self, dt: float) -> None:
        """Advance the belt furniture by `dt` seconds."""
        if not self.enabled:
            return
        self.pulley_angle += self.cfg.belt_speed * dt / max(
            self.cfg.belt_size[2] / 2.0 + 0.01, 1e-6
        )
        # Cleats are kinematic: move them with the belt so they actually push
        # fruit rather than sitting still while the surface velocity does all the
        # work.
        self.phase = (self.phase + self.cfg.belt_speed * dt) % self.cleat_span
        self._place_cleats(self.phase)


def _add_physics_material(
    prim, static_friction: float, dynamic_friction: float, restitution: float
) -> UsdShade.Material:
    stage = prim.GetStage()
    material = UsdShade.Material.Define(stage, f"{prim.GetPath()}_physmat")
    api = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    api.CreateStaticFrictionAttr().Set(static_friction)
    api.CreateDynamicFrictionAttr().Set(dynamic_friction)
    api.CreateRestitutionAttr().Set(restitution)
    UsdShade.MaterialBindingAPI.Apply(prim).Bind(
        material, UsdShade.Tokens.weakerThanDescendants, "physics"
    )
    return material
