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
import os

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
        #: Belt extent along the line (Y) and across it (X).
        self.length = cfg.belt_size[1]
        self.width = cfg.belt_size[0]
        #: Current belt surface speed. The pick station stops the belt while the
        #: jaws close, exactly as a real sorting line indexes at the pick point.
        self.speed = cfg.belt_speed
        #: Surface velocity is *ramped* rather than stepped: a real conveyor has a
        #: finite drive acceleration, and an instantaneous step from 0.34 m/s to 0
        #: tips the fruit and demands an unbounded friction impulse. The pick loop
        #: already waits for the fruit to settle after indexing, so the extra
        #: ``v^2 / 2a`` of travel (~3 cm at the defaults) is harmless.
        self.target_speed = cfg.belt_speed
        self.ramp_enabled = os.environ.get("FRUIT_BELT_RAMP", "1") == "1"
        self.accel = float(os.environ.get("FRUIT_BELT_ACCEL", "2.0"))
        #: Belt encoder [m/s]: the speed the belt *furniture* actually travels,
        #: differenced from the cleat phase each step rather than read back from the
        #: commanded surface velocity. In this build the two agree by construction
        #: (the cleats are kinematic, so they cannot slip) - the useful part is that
        #: they now also agree with what the *fruit* do: measured, a fruit riding the
        #: belt travels at 1.01-1.14x this reading (`logs/173`), which is the
        #: "encoder + physics prior" the design notes call 方案 3 (v_object = v_belt,
        #: omega ~ 0). Before the belt was authored as a body the fruit received
        #: ~18 % of it, so the prior would have been badly wrong.
        self.encoder_speed = float(cfg.belt_speed)
        # Fit the cleats to the belt: more cleats than fit would overlap and form
        # a wall instead of a track.
        # Cleats live upstream of the pick nest only: a kinematic bar travelling
        # through the nest would smash it, and the fruit only needs pushing as far
        # as the nest. Upstream is +Y (the flow is -Y).
        self.cleat_start = cfg.pick_y + 0.28
        upstream_end = cfg.belt_center[1] + cfg.belt_size[1] / 2.0
        usable = max(0.0, upstream_end - self.cleat_start)
        self.cleat_count = max(1, int(usable / cfg.cleat_spacing))
        self.cleat_span = cfg.cleat_spacing * self.cleat_count
        self.enabled = self.cleat_count > 0
        # Cleats are **off by default** now. They were introduced when the belt's
        # surface velocity did not actually drag anything (`conveyor`'s authoring
        # note), i.e. as a workaround for a bug, and they cost more than they give:
        # a 20 mm cleat meets a 30-70 mm fruit *above* its own centre, so it spins
        # the fruit and jams the small ones (measured: a 30 mm strawberry spent 330
        # ticks stationary against a cleat, `logs/176`-era probe run, while the
        # smooth belt in the same probe transported every fruit with a spin ratio
        # of **0.01-0.02** and 12 stalled ticks in total). With the surface velocity
        # fixed the belt carries by friction on its own. `FRUIT_CLEATS=1` restores
        # the cleated track.
        if os.environ.get("FRUIT_CLEATS", "0") != "1":
            self.cleat_count = 0
            self.enabled = False

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
        # The belt slab must be a *kinematic rigid body*, not a static collider:
        # PhysX only applies `PhysxSurfaceVelocityAPI` to a collider that belongs
        # to a body. Measured (`logs/171`): with the slab static, a fruit resting
        # on it (z = belt_top + r) travels at **18 %** of the commanded surface
        # speed and spins - which is what the old `transport_efficiency = 0.40`
        # was papering over. With it kinematic the same fruit travels at
        # **0.97-1.23x** the surface speed. `FRUIT_BELT_KINEMATIC=0` restores the
        # static slab to reproduce the old crawl.
        if os.environ.get("FRUIT_BELT_KINEMATIC", "1") == "1":
            body = UsdPhysics.RigidBodyAPI.Apply(belt.GetPrim())
            body.CreateKinematicEnabledAttr().Set(True)
            UsdPhysics.MassAPI.Apply(belt.GetPrim()).CreateMassAttr().Set(50.0)
        surface_velocity = PhysxSchema.PhysxSurfaceVelocityAPI.Apply(belt.GetPrim())
        surface_velocity.CreateSurfaceVelocityAttr().Set(
            Gf.Vec3f(0.0, self._surface_attr_speed(cfg.belt_speed), 0.0)
        )

        if cfg.nest_height > 0.0:
            self._build_pick_nest()

        # Cleats: transverse bars carried by the belt (across the line, X).
        if self.enabled:
            for i in range(self.cleat_count):
                name = f"Cleat{i:02d}"
                cleat = _define_box(
                    self.stage, f"/World/Conveyor/{name}",
                    size=(sx * 0.97, cfg.cleat_width, cfg.cleat_height),
                    center=(bx, by, self.belt_top + cfg.cleat_height / 2.0),
                )
                _set_color(cleat, (0.10, 0.10, 0.11))
                UsdPhysics.CollisionAPI.Apply(cleat.GetPrim())
                body = UsdPhysics.RigidBodyAPI.Apply(cleat.GetPrim())
                body.CreateKinematicEnabledAttr().Set(True)
                UsdPhysics.MassAPI.Apply(cleat.GetPrim()).CreateMassAttr().Set(0.5)
                self.cleats.append(RigidPrim(f"/World/Conveyor/{name}"))

        # Head / tail pulleys. Their axis runs across the belt (X).
        radius = sz / 2.0 + 0.01
        for tag, dy in (("Tail", -(sy / 2.0 + radius * 0.6)), ("Head", (sy / 2.0 + radius * 0.6))):
            cyl = UsdGeom.Cylinder.Define(self.stage, f"/World/Conveyor/Pulley{tag}")
            cyl.GetRadiusAttr().Set(radius)
            cyl.GetHeightAttr().Set(sx + 0.02)
            cyl.GetAxisAttr().Set("X")
            xf = UsdGeom.Xformable(cyl)
            xf.ClearXformOpOrder()
            xf.AddTranslateOp().Set(Gf.Vec3d(bx, by + dy, self.belt_top - radius * 0.5))
            _set_color(cyl, (0.35, 0.36, 0.38))
            self.pulleys.append(xf)

        # Frame rails down both sides (along Y) plus support legs.
        rail_width = float(cfg.main_frame_rail_width)
        rail_offset = float(cfg.main_frame_rail_offset)
        for sign in (-1.0, 1.0):
            _set_color(
                _define_box(
                    self.stage, f"/World/Conveyor/Frame{'P' if sign > 0 else 'N'}",
                    size=(rail_width, sy + 0.10, 0.05),
                    center=(bx + sign * (sx / 2.0 + rail_offset), by, self.belt_top + 0.02),
                ),
                (0.55, 0.56, 0.58),
            )
        # Guide rails keep produce on the centre line. Optional in v2: with the
        # belt widened and no rails the line still carries straight (measured).
        if cfg.rails:
            rail_height = float(os.environ.get("FRUIT_RAIL_HEIGHT", "0.075"))
            for sign in (-1.0, 1.0):
                guide = _define_box(
                    self.stage,
                    f"/World/Conveyor/Guide{'P' if sign > 0 else 'N'}",
                    size=(0.015, sy, rail_height),
                    center=(
                        bx + sign * (cfg.belt_channel_x + 0.008),
                        by,
                        self.belt_top + rail_height / 2.0,
                    ),
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
    def _build_pick_nest(self) -> None:
        """A flat pick platform that lifts fruit into the pad band.

        Geometry, from the measured numbers (scripts/49, 55, 63):

        * the arm can lower the jaw centre to about ``belt_top + 0.05``;
        * the pads' working faces span ``jaw - 0.027 .. jaw + 0.005``, and the
          fingertips hang to ``jaw - 0.03``;
        * a fruit on the belt has its equator at ``belt_top + d/2``, which is
          *below* the pad faces, so the pads press it down onto the belt instead
          of pinching it (confirmed visually: logs/gripper_view/close_front.png).

        So the platform only has to raise the fruit until
        ``platform + d/2 >= jaw - 0.027`` while keeping the platform below the
        fingertips (``jaw - 0.03``). A 1.5 cm platform satisfies both for every
        fruit in the pool (d >= 2.8 cm). It is deliberately *wide*: a narrow ridge
        is stable only for large fruit and let everything else roll off
        (drifts of 46 mm and more in logs/68-81).
        """
        cfg = self.cfg
        bx, by, _ = cfg.belt_center
        top = self.belt_top + cfg.nest_height
        length = cfg.nest_length_x
        platform = _define_box(
            self.stage,
            "/World/Conveyor/PickPlatform",
            size=(cfg.nest_half_width_y * 2.0, length, cfg.nest_height),
            center=(bx, cfg.pick_y + 0.02, self.belt_top + cfg.nest_height / 2.0),
        )
        _set_color(platform, (0.20, 0.55, 0.85))
        UsdPhysics.CollisionAPI.Apply(platform.GetPrim())
        _add_physics_material(platform.GetPrim(), 0.8, 0.8, 0.0)

        # Ramp: a thin plate tilted so its downstream (-Y) edge meets the platform
        # top. It comes in from upstream (+Y).
        ramp_length = cfg.nest_ramp_length_x
        ramp = _define_box(
            self.stage,
            "/World/Conveyor/NestRamp",
            size=(cfg.nest_half_width_y * 2.0, ramp_length, 0.006),
            center=(bx, cfg.pick_y + 0.02 + length / 2.0 + ramp_length / 2.0,
                    top - cfg.nest_height / 2.0),
        )
        _set_color(ramp, (0.25, 0.6, 0.9))
        UsdPhysics.CollisionAPI.Apply(ramp.GetPrim())
        ramp_xf = UsdGeom.Xformable(ramp)
        angle = float(np.arctan2(cfg.nest_height, ramp_length))
        ramp_xf.AddRotateXOp().Set(-np.degrees(angle))
        say(
            f"pick platform: top z={top:.3f} m at y={cfg.pick_y:.2f}, "
            f"{cfg.nest_half_width_y * 2000:.0f} mm wide, {length:.2f} m long, "
            f"ramp {ramp_length:.2f} m"
        )

    # ------------------------------------------------------------------ #
    def set_speed(self, speed: float) -> None:
        """Request a new belt surface velocity; `step()` ramps towards it."""
        self.target_speed = float(speed)
        if not self.ramp_enabled:
            self._apply_speed(self.target_speed)

    def _surface_attr_speed(self, speed: float) -> float:
        """API value that makes the *world* belt surface speed equal `speed`.

        Measured (`logs/365`): with the belt authored as a unit cube scaled by
        `belt_size`, `PhysxSurfaceVelocityAPI` is interpreted in the collider's
        scaled local frame, so a value of `speed` along the Y axis (scale 1.60)
        produced a world surface speed of `1.60 * speed` - the fruit rode at
        0.096 m/s against a commanded 0.060, which is exactly `0.060 * 1.60`.
        Dividing by the axis scale makes the commanded number the delivered one.
        """
        scale = float(self.cfg.belt_size[1]) or 1.0
        return float(speed) / scale

    def _apply_speed(self, speed: float) -> None:
        self.speed = float(speed)
        prim = self.stage.GetPrimAtPath("/World/Conveyor/Belt")
        if prim.IsValid():
            api = PhysxSchema.PhysxSurfaceVelocityAPI(prim)
            api.GetSurfaceVelocityAttr().Set(
                Gf.Vec3f(0.0, self._surface_attr_speed(self.speed), 0.0)
            )

    def stop(self) -> None:
        self.set_speed(0.0)

    def hold(self) -> None:
        """Stop the belt and make it take effect *now*, without the ramp.

        The grasp primitive indexes a fruit and then advances physics directly
        (`SimulationManager.step`), never calling `step()`, so a ramped `stop()`
        never reached the collider: the surface velocity stayed at its previous
        value and the fruit was dragged off the station ("fruit would not stay on
        the pick nest", logs/385). Applying the zero immediately is what the
        primitive needs; the scripted line keeps the ramped `stop()`.
        """
        self.target_speed = 0.0
        self._apply_speed(0.0)

    def start(self) -> None:
        self.set_speed(self.cfg.belt_speed)

    # ------------------------------------------------------------------ #
    def reset(self) -> None:
        self.pulley_angle = 0.0
        self.phase = 0.0
        self._place_cleats(0.0)

    def _place_cleats(self, offset: float) -> None:
        if not self.cleats:
            return
        cfg = self.cfg
        bx = cfg.belt_center[0]
        start = self.cleat_start
        for i, cleat in enumerate(self.cleats):
            y = start + ((i * cfg.cleat_spacing + offset) % self.cleat_span)
            # Kinematic bodies cannot take velocity commands; writing the pose
            # each step is what conveys their motion to the fruit.
            cleat.set_world_poses(
                positions=[[bx, y, self.belt_top + cfg.cleat_height / 2.0]],
                orientations=[[1.0, 0.0, 0.0, 0.0]],
            )

    def step(self, dt: float) -> None:
        """Advance the belt furniture by `dt` seconds."""
        # The ramp must run even with the cleats off: `step` is the only place the
        # commanded speed reaches the collider, so an early return for "no cleats"
        # meant `stop()`/`start()` were *never applied* on the v2 default belt - the
        # evaluator's grasp primitive stopped the line once and the belt stayed
        # stopped for the rest of the run (measured, logs/386: two episodes in
        # eighteen minutes). Speeding the belt is independent of whether there is
        # furniture to move.
        if self.ramp_enabled and self.speed != self.target_speed:
            delta = self.target_speed - self.speed
            limit = max(self.accel, 1e-3) * dt
            self._apply_speed(self.speed + max(-limit, min(limit, delta)))
        if not self.enabled:
            return
        self.pulley_angle += self.speed * dt / max(
            self.cfg.belt_size[2] / 2.0 + 0.01, 1e-6
        )
        # Cleats are kinematic: move them with the belt so they actually push
        # fruit rather than sitting still while the surface velocity does all the
        # work.
        previous_phase = self.phase
        self.phase = (self.phase + self.speed * dt) % self.cleat_span
        self.encoder_speed = (self.phase - previous_phase) / max(dt, 1e-9)
        if self.encoder_speed > self.cleat_span / 2.0:
            self.encoder_speed -= self.cleat_span / dt
        elif self.encoder_speed < -self.cleat_span / 2.0:
            self.encoder_speed += self.cleat_span / dt
        self._place_cleats(self.phase)


class OutputBelt:
    """One raised output line: a short belt running along +X beside the robot.

    Built like the main belt's slab - a **kinematic rigid body**, because PhysX
    only applies ``PhysxSurfaceVelocityAPI`` to a collider that belongs to a body
    (measured on the main belt, `logs/171`: a static slab carried fruit at 18 %
    of the commanded speed) - plus a simple frame and legs. The surface carries
    along +X, away from the robot's working side.

    Unlike the main belt there is no indexing stop and no cleats: the output line
    only has to keep moving. At its +X end it discharges over a chute into a
    shallow collection tray (`_build_discharge`), which is the line's real
    end-of-line destination.
    """

    def __init__(self, stage: Usd.Stage, cfg: SceneConfig, index: int, sign: float):
        self.stage = stage
        self.cfg = cfg
        self.index = int(index)
        #: +1 = the +Y belt (left arm), -1 = the -Y belt (right arm).
        self.sign = float(sign)
        self.root = f"/World/OutputBelt{'P' if self.sign > 0 else 'N'}"
        self.belt_path = f"{self.root}/Belt"
        cx, _, sz = (cfg.output_belt_center_x, 0.0, cfg.output_belt_size[2])
        self.center = (
            float(cx),
            self.sign * float(cfg.output_belt_y),
            float(cfg.output_belt_top_z) - float(sz) / 2.0,
        )
        self.speed = float(cfg.output_belt_speed)

    # ------------------------------------------------------------------ #
    def _surface_attr_speed(self, speed: float) -> float:
        """API value that makes the *world* surface speed equal `speed`.

        Same measured quirk as the main belt (`conveyor.py`'s
        ``_surface_attr_speed``): the slab is a unit cube scaled by its size and
        the surface velocity is interpreted in the scaled local frame, so the
        value has to be divided by the axis scale (here the X length).
        """
        scale = float(self.cfg.output_belt_size[0]) or 1.0
        return float(speed) / scale

    def build(self) -> None:
        cfg = self.cfg
        sx, sy, sz = cfg.output_belt_size
        bx, by, bz = self.center

        belt = _define_box(self.stage, self.belt_path, size=(sx, sy, sz), center=(bx, by, bz))
        _set_color(belt, (0.045, 0.045, 0.05))
        UsdPhysics.CollisionAPI.Apply(belt.GetPrim())
        _add_physics_material(
            belt.GetPrim(), cfg.output_belt_friction, cfg.output_belt_friction, 0.0
        )
        UsdPhysics.RigidBodyAPI.Apply(belt.GetPrim()).CreateKinematicEnabledAttr().Set(True)
        UsdPhysics.MassAPI.Apply(belt.GetPrim()).CreateMassAttr().Set(50.0)
        surface_velocity = PhysxSchema.PhysxSurfaceVelocityAPI.Apply(belt.GetPrim())
        surface_velocity.CreateSurfaceVelocityAttr().Set(
            Gf.Vec3f(self.surface_attr_speed, 0.0, 0.0)
        )

        # Side rails along X: a small keeper at the outer edges of the slab, so a
        # fruit that lands slightly off-centre meets a rail rather than the floor.
        # They are real colliders - the main belt's guide rails are too - bound to
        # a metal friction material; without the CollisionAPI the comment was
        # false (the boxes were colour only).
        for side_sign in (-1.0, 1.0):
            rail_y = by + side_sign * (sy / 2.0 + 0.0125)
            rail = _define_box(
                self.stage,
                f"{self.root}/Frame{'P' if side_sign > 0 else 'N'}",
                size=(sx, 0.025, 0.05),
                center=(bx, rail_y, cfg.output_belt_top_z + 0.01),
            )
            _set_color(rail, (0.55, 0.56, 0.58))
            UsdPhysics.CollisionAPI.Apply(rail.GetPrim())
            _add_physics_material(rail.GetPrim(), 0.40, 0.35, 0.0)

        # Legs down to the floor. The -X pair is placed by `SceneConfig` just
        # outside the main belt's frame rail (whose outer face is at x=0.0855) so
        # the leg no longer passes through it - the old placement cleared the
        # *slab* but ran 14.5 mm through the rail. The +X pair is inset under the
        # belt so the discharge chute, which starts at the belt's end face, has it
        # clear. The audit line below prints the true face clearances.
        leg_half = float(cfg.output_belt_leg_size) / 2.0
        leg_xs = (float(cfg.output_belt_inner_leg_x), float(cfg.output_belt_outer_leg_x))
        leg_ys = (by - (sy / 2.0 - 0.03), by + (sy / 2.0 - 0.03))
        leg_height = float(cfg.output_belt_top_z) - float(sz)
        for i, leg_x in enumerate(leg_xs):
            for j, leg_y in enumerate(leg_ys):
                _set_color(
                    _define_box(
                        self.stage,
                        f"{self.root}/Leg{i}{j}",
                        size=(cfg.output_belt_leg_size, cfg.output_belt_leg_size, leg_height),
                        center=(leg_x, leg_y, leg_height / 2.0),
                    ),
                    (0.30, 0.30, 0.32),
                )

        self._build_discharge()

        main_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
        tallest = max(hi for _, hi in cfg.fruit_dimensions.values())
        pedal_y = abs(cfg.pedestal_center_xy[1]) + cfg.pedestal_size[1] / 2.0
        # Face clearance, not centre distance. The old audit printed
        # `belt_edge - leg_centre = 0.035 m` while the leg's x-span ran through the
        # rail; both parts are visual-only, but the claim was wrong.
        inner_x, outer_x = leg_xs
        rail_outer_face = (
            cfg.belt_center[0] - cfg.belt_size[0] / 2.0 - cfg.main_frame_rail_offset
        ) - cfg.main_frame_rail_width / 2.0
        slab_edge = cfg.belt_center[0] - cfg.belt_size[0] / 2.0
        say(
            f"output belt {'P' if self.sign > 0 else 'N'} ({self.index}): "
            f"{sx:.2f}x{sy:.2f}x{sz:.2f} m at ({bx:.2f},{by:+.2f}), top "
            f"{cfg.output_belt_top_z:.2f}, surface {cfg.output_belt_speed:+.2f} m/s along +X | "
            f"underside clears main belt top by "
            f"{(cfg.output_belt_top_z - sz) - main_top:.3f} m, tallest fruit by "
            f"{(cfg.output_belt_top_z - sz) - (main_top + tallest):.3f} m; "
            f"inner edge clears the pedestal by "
            f"{(cfg.output_belt_y - sy / 2.0) - pedal_y:.3f} m; "
            f"legs: -X pair x=[{inner_x - leg_half:.4f},{inner_x + leg_half:.4f}] clear the main "
            f"belt frame rail's outer face (x={rail_outer_face:.4f}) by "
            f"{rail_outer_face - (inner_x + leg_half):+.4f} m and the slab edge "
            f"(x={slab_edge:.3f}) by {slab_edge - (inner_x + leg_half):+.4f} m; "
            f"+X pair x=[{outer_x - leg_half:.4f},{outer_x + leg_half:.4f}] leaves the "
            f"discharge chute (x>={cfg.output_belt_end_x:.3f}) "
            f"{cfg.output_belt_end_x - (outer_x + leg_half):+.4f} m clear"
        )

    # ------------------------------------------------------------------ #
    def _build_discharge(self) -> None:
        """Chute and collection tray at the +X end of this belt.

        A short steep sheet hangs off the belt's top corner and drops a fruit
        that reaches the end into a shallow tray on a stand. Nothing teleports
        the fruit: it slides and falls by gravity and contact, and the tray is
        what the spawner's recycle counts as the end of the output line
        (`FruitSpawner.update` -> `on_output_tray` -> `discharged`).
        """
        cfg = self.cfg
        by = self.center[1]
        (x0, z0) = cfg.output_chute_top
        (x1, z1) = cfg.output_chute_bottom
        angle = math.radians(float(cfg.output_chute_angle_deg))
        angle_deg = float(np.degrees(angle))
        thickness = 0.006
        width = float(cfg.output_belt_size[1]) - 0.01
        length = math.hypot(x1 - x0, z0 - z1)
        # The slab is centred so that its *top surface* runs through the two edge
        # points (`centre = surface midpoint - normal * thickness/2`): the sheet
        # starts 6 mm below the belt top at the belt's end face (no seam gap to
        # wedge a small fruit in; ~5 mm of its lower upstream corner tucks
        # invisibly under the belt end - both colliders are non-dynamic).
        normal = np.array([math.sin(angle), 0.0, math.cos(angle)])
        surface_mid = np.array([(x0 + x1) / 2.0, 0.0, (z0 + z1) / 2.0])
        centre = surface_mid - normal * (thickness / 2.0)

        def angled_box(path: str, size, centre_xyz):
            """A box scaled, then rotated about Y, then translated.

            ``_define_box`` authors [translate, scale]; appending a rotation after
            that applies the rotation to the *unit* cube and the non-uniform scale
            then shears it - measured on the first build of this chute: its world
            AABB was 8 mm tall instead of the 0.28 m slope. Authoring the ops in
            [translate, rotate, scale] order gives scale -> rotate -> translate.
            """
            prim = _define_box(self.stage, path, size=size, center=centre_xyz)
            xf = UsdGeom.Xformable(prim)
            xf.ClearXformOpOrder()
            xf.AddTranslateOp().Set(Gf.Vec3d(*centre_xyz))
            xf.AddRotateYOp().Set(angle_deg)
            xf.AddScaleOp().Set(Gf.Vec3f(*size))
            return prim

        chute = angled_box(
            f"{self.root}/Chute",
            (length, width, thickness),
            (float(centre[0]), by, float(centre[2])),
        )
        _set_color(chute, (0.62, 0.63, 0.65))
        UsdPhysics.CollisionAPI.Apply(chute.GetPrim())
        _add_physics_material(
            chute.GetPrim(),
            float(cfg.output_chute_friction),
            float(cfg.output_chute_friction) * 0.8,
            0.0,
        )

        # Side lips keep an off-centre fruit on the sheet.
        lip_h, lip_t = 0.035, 0.012
        for side_sign in (-1.0, 1.0):
            lip_centre = surface_mid + normal * (lip_h / 2.0)
            lip = angled_box(
                f"{self.root}/ChuteLip{'P' if side_sign > 0 else 'N'}",
                (length, lip_t, lip_h),
                (
                    float(lip_centre[0]),
                    by + side_sign * (width / 2.0 + lip_t / 2.0),
                    float(lip_centre[2]),
                ),
            )
            _set_color(lip, (0.55, 0.56, 0.58))
            UsdPhysics.CollisionAPI.Apply(lip.GetPrim())

        # Tray: open shallow box on a stand, under the chute's discharge.
        tx = float(cfg.output_tray_center_x)
        tray_sx, tray_sy = (float(v) for v in cfg.output_tray_size)
        wall = float(cfg.output_tray_wall_thickness)
        floor_top = float(cfg.output_tray_floor_top_z)
        wall_h = float(cfg.output_tray_wall_height)
        floor = _define_box(
            self.stage, f"{self.root}/TrayFloor",
            size=(tray_sx, tray_sy, 0.02), center=(tx, by, floor_top - 0.01),
        )
        _set_color(floor, (0.30, 0.32, 0.35))
        UsdPhysics.CollisionAPI.Apply(floor.GetPrim())
        _add_physics_material(
            floor.GetPrim(), float(cfg.output_tray_friction), float(cfg.output_tray_friction), 0.0
        )
        for side_sign in (-1.0, 1.0):
            walls = (
                _define_box(
                    self.stage,
                    f"{self.root}/TrayEnd{'P' if side_sign > 0 else 'N'}",
                    size=(wall, tray_sy, wall_h),
                    center=(tx + side_sign * (tray_sx / 2.0 - wall / 2.0), by, floor_top + wall_h / 2.0),
                ),
                _define_box(
                    self.stage,
                    f"{self.root}/TraySide{'P' if side_sign > 0 else 'N'}",
                    size=(tray_sx, wall, wall_h),
                    center=(tx, by + side_sign * (tray_sy / 2.0 - wall / 2.0), floor_top + wall_h / 2.0),
                ),
            )
            for part in walls:
                _set_color(part, (0.40, 0.42, 0.45))
                UsdPhysics.CollisionAPI.Apply(part.GetPrim())
                _add_physics_material(
                    part.GetPrim(),
                    float(cfg.output_tray_friction),
                    float(cfg.output_tray_friction),
                    0.0,
                )
        stand = _define_box(
            self.stage, f"{self.root}/TrayStand",
            size=(tray_sx - 0.14, tray_sy - 0.08, float(cfg.output_tray_stand_height)),
            center=(tx, by, float(cfg.output_tray_stand_height) / 2.0),
        )
        _set_color(stand, (0.33, 0.34, 0.36))
        UsdPhysics.CollisionAPI.Apply(stand.GetPrim())

        say(
            f"discharge {'P' if self.sign > 0 else 'N'}: chute {cfg.output_chute_angle_deg:.0f} deg "
            f"from ({x0:.3f},{z0:.3f}) to ({x1:.3f},{z1:.3f}) m "
            f"(sheet {length:.2f} m long, {width:.2f} m wide); tray {tray_sx:.2f}x{tray_sy:.2f} m "
            f"centre x={tx:.2f} on the {cfg.output_tray_stand_height:.2f} m stand, floor z="
            f"{floor_top:.2f}, rim z={floor_top + wall_h:.2f}, "
            f"{cfg.output_tray_dwell_s:.1f} s settle dwell"
        )

    # ------------------------------------------------------------------ #
    def reset(self) -> None:
        """Nothing to reset: the surface speed is constant (no cleats)."""

    def stop(self) -> None:
        self.speed = 0.0
        self._apply()

    def start(self) -> None:
        self.speed = float(self.cfg.output_belt_speed)
        self._apply()

    def _apply(self) -> None:
        prim = self.stage.GetPrimAtPath(self.belt_path)
        if prim.IsValid():
            api = PhysxSchema.PhysxSurfaceVelocityAPI(prim)
            api.GetSurfaceVelocityAttr().Set(
                Gf.Vec3f(self._surface_attr_speed(self.speed), 0.0, 0.0)
            )

    @property
    def surface_attr_speed(self) -> float:
        return self._surface_attr_speed(self.cfg.output_belt_speed)


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
