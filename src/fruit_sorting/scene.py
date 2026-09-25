"""Builds the bimanual fruit-sorting cell in Isaac Sim 6.

Layout (robot at the origin, facing +X):

    +Y  downstream
     ^      [ bin B ]
     |   ============== conveyor ==============
     |            (robot arms reach over it)
     |      [ pedestal + OpenArm upper body ]
     |      [ bin A ]

One RGB-D camera is mounted above the torso where a humanoid head would be; that
is the single camera available to the policy.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

import isaacsim.core.experimental.utils.app as app_utils
import isaacsim.core.experimental.utils.stage as stage_utils
from isaacsim.core.experimental.objects import DistantLight, GroundPlane
from isaacsim.core.experimental.prims import Articulation, RigidPrim
from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera

from .assets import OPENARM_BIMANUAL_USD, OPENARM_TCP_LINKS, SceneConfig
from .common import look_at_quat, say, to_numpy


def _define_box(stage: Usd.Stage, path: str, size: tuple[float, float, float], center: tuple[float, float, float]):
    """Axis-aligned box authored as a unit cube plus a scale xform."""
    prim = UsdGeom.Cube.Define(stage, path)
    prim.GetSizeAttr().Set(1.0)
    xformable = UsdGeom.Xformable(prim)
    xformable.ClearXformOpOrder()
    xformable.AddTranslateOp().Set(Gf.Vec3d(*center))
    xformable.AddScaleOp().Set(Gf.Vec3f(*size))
    return prim


def _set_color(prim, rgba: tuple[float, float, float]) -> None:
    """Give a prim a simple preview-surface material of the given colour."""
    usd_prim = prim.GetPrim()
    stage = usd_prim.GetStage()
    mat_path = f"{usd_prim.GetPath()}_mat"
    material = UsdShade.Material.Define(stage, mat_path)
    shader = UsdShade.Shader.Define(stage, f"{mat_path}/shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*rgba))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.6)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    UsdShade.MaterialBindingAPI.Apply(usd_prim).Bind(material)


def _add_physics_material(prim, static_friction: float, dynamic_friction: float, restitution: float = 0.0):
    usd_prim = prim.GetPrim()
    stage = usd_prim.GetStage()
    mat_path = f"{usd_prim.GetPath()}_physmat"
    material = UsdShade.Material.Define(stage, mat_path)
    api = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    api.CreateStaticFrictionAttr().Set(static_friction)
    api.CreateDynamicFrictionAttr().Set(dynamic_friction)
    api.CreateRestitutionAttr().Set(restitution)
    UsdShade.MaterialBindingAPI.Apply(usd_prim).Bind(material)
    return material


@dataclass
class SortingScene:
    """Handles to everything in the cell."""

    cfg: SceneConfig
    stage: Usd.Stage | None = None
    robot: Articulation | None = None
    camera: RtxCamera | None = None
    camera_sensor: CameraSensor | None = None
    belt_prim_path: str = "/World/Conveyor/Belt"
    bin_paths: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    DEFAULT_PARTS = ("environment", "pedestal", "robot", "conveyor", "bins", "camera")

    def build(self, parts: tuple[str, ...] | None = None) -> "SortingScene":
        parts = self.DEFAULT_PARTS if parts is None else parts
        stage_utils.create_new_stage()
        stage = stage_utils.get_current_stage()
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        self.stage = stage
        say("stage created (meters, Z-up)")

        builders = {
            "environment": self._add_environment,
            "pedestal": self._add_pedestal,
            "robot": self._add_robot,
            "conveyor": self._add_conveyor,
            "bins": self._add_bins,
            "camera": self._add_head_camera,
        }
        for name in parts:
            say(f"building part: {name}")
            builders[name]()
        say(f"scene built (parts={list(parts)})")
        return self

    def _add_environment(self) -> None:
        GroundPlane("/World/GroundPlane", positions=[0.0, 0.0, 0.0])
        key = DistantLight("/World/KeyLight", positions=[2.0, -2.0, 4.0])
        key.set_intensities(900.0)
        fill = DistantLight("/World/FillLight", positions=[-2.0, 3.0, 3.0])
        fill.set_intensities(350.0)
        dome = DistantLight("/World/TopLight", positions=[0.0, 0.0, 6.0])
        dome.set_intensities(250.0)
        say("lighting added")

    def _add_pedestal(self) -> None:
        cfg = self.cfg
        height = cfg.table_top_z
        sx, sy = cfg.pedestal_size
        prim = _define_box(
            self.stage,
            "/World/Pedestal",
            size=(sx, sy, height),
            center=(cfg.pedestal_center_xy[0], cfg.pedestal_center_xy[1], height / 2.0),
        )
        _set_color(prim, (0.35, 0.37, 0.40))
        UsdPhysics.CollisionAPI.Apply(prim.GetPrim())
        say(f"pedestal top at z={height:.2f} m")

    def _add_robot(self) -> None:
        prim = self.stage.DefinePrim("/World/OpenArm", "Xform")
        prim.GetReferences().AddReference(OPENARM_BIMANUAL_USD)
        UsdGeom.Xformable(prim).ClearXformOpOrder()
        UsdGeom.Xformable(prim).AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, self.cfg.robot_base_z))
        say("robot referenced (first run downloads the asset)")

    def _add_conveyor(self) -> None:
        cfg = self.cfg
        belt = _define_box(self.stage, self.belt_prim_path, size=cfg.belt_size, center=cfg.belt_center)
        _set_color(belt, (0.12, 0.13, 0.15))
        UsdPhysics.CollisionAPI.Apply(belt.GetPrim())
        _add_physics_material(belt, cfg.belt_friction, cfg.belt_friction)

        # PhysX surface velocity moves whatever rests on the collision surface.
        surface_velocity = PhysxSchema.PhysxSurfaceVelocityAPI.Apply(belt.GetPrim())
        surface_velocity.CreateSurfaceVelocityAttr().Set(Gf.Vec3f(cfg.belt_speed, 0.0, 0.0))

        # Low side rails keep fruit from drifting off the belt without blocking
        # the downward gripper approach.
        bx, by, bz = cfg.belt_center
        sx, sy, sz = cfg.belt_size
        belt_top = bz + sz / 2.0
        for name, y_sign in (("RailNeg", -1.0), ("RailPos", 1.0)):
            rail = _define_box(
                self.stage,
                f"/World/Conveyor/{name}",
                size=(sx, 0.02, 0.04),
                center=(bx, by + y_sign * (sy / 2.0 + 0.01), belt_top + 0.02),
            )
            _set_color(rail, (0.55, 0.56, 0.58))
            UsdPhysics.CollisionAPI.Apply(rail.GetPrim())

        # Support legs at both ends of the frame.
        leg_height = bz - sz / 2.0
        for i, leg_x in enumerate((bx - sx / 2.0 + 0.08, bx + sx / 2.0 - 0.08)):
            for j, leg_y in enumerate((by - sy / 2.0 + 0.05, by + sy / 2.0 - 0.05)):
                leg = _define_box(
                    self.stage,
                    f"/World/Conveyor/Leg{i}{j}",
                    size=(0.04, 0.04, leg_height),
                    center=(leg_x, leg_y, leg_height / 2.0),
                )
                _set_color(leg, (0.30, 0.30, 0.32))
        say(
            f"conveyor added, belt surface z={belt_top:.3f}, surface velocity="
            f"{cfg.belt_speed:+.2f} m/s along X, span_x={sx:.2f} m"
        )

    def _add_bins(self) -> None:
        cfg = self.cfg
        size = cfg.bin_size_xy
        stand = cfg.bin_stand_height
        height = cfg.bin_height
        thickness = 0.02
        for idx, (bx, by) in enumerate(self.cfg.bin_positions):
            pedestal = _define_box(
                self.stage,
                f"/World/Bins/Bin{idx}_stand",
                size=(size, size, stand),
                center=(bx, by, stand / 2.0),
            )
            _set_color(pedestal, (0.28, 0.29, 0.31))
            UsdPhysics.CollisionAPI.Apply(pedestal.GetPrim())

            color = (0.20, 0.45, 0.28) if idx == 0 else (0.45, 0.30, 0.18)
            floor = _define_box(
                self.stage,
                f"/World/Bins/Bin{idx}_floor",
                size=(size, size, thickness),
                center=(bx, by, stand + thickness / 2.0),
            )
            _set_color(floor, color)
            UsdPhysics.CollisionAPI.Apply(floor.GetPrim())

            half = size / 2.0
            walls = (
                (0.0, half, (size, thickness, height)),
                (0.0, -half, (size, thickness, height)),
                (half, 0.0, (thickness, size, height)),
                (-half, 0.0, (thickness, size, height)),
            )
            for j, (dx, dy, wall_size) in enumerate(walls):
                wall = _define_box(
                    self.stage,
                    f"/World/Bins/Bin{idx}_wall{j}",
                    size=wall_size,
                    center=(bx + dx, by + dy, stand + thickness + height / 2.0),
                )
                _set_color(wall, color)
                UsdPhysics.CollisionAPI.Apply(wall.GetPrim())
            self.bin_paths.append(f"/World/Bins/Bin{idx}_floor")
        say(
            f"bins added at {self.cfg.bin_positions}, rim z="
            f"{stand + thickness + height:.2f} m"
        )

    def _add_head_camera(self) -> None:
        cfg = self.cfg
        annotators = [
            a.strip()
            for a in os.environ.get(
                "FRUIT_CAMERA_ANNOTATORS",
                # NOTE: the "instance_segmentation" and "pointcloud" annotators
                # segfault this Isaac Sim 6.0.1-rc build headless. Use
                # "instance_id_segmentation" for per-prim masks instead; it gives
                # the same per-fruit instance information.
                "rgb,distance_to_image_plane,instance_id_segmentation,bounding_box_2d_tight",
            ).split(",")
            if a.strip()
        ]
        resolution = tuple(
            int(v) for v in os.environ.get("FRUIT_CAMERA_RES", f"{cfg.camera_resolution[0]},{cfg.camera_resolution[1]}").split(",")
        )
        eye = (cfg.head_camera_forward, 0.0, cfg.head_camera_z)
        target = cfg.head_camera_target

        # Head mast + housing: a physical-looking mount for the camera. Both are
        # visual-only so the arms cannot collide with the robot's own head.
        mast = _define_box(
            self.stage,
            "/World/HeadMast",
            size=(0.03, 0.03, 0.22),
            center=(0.05, 0.0, cfg.head_camera_z - 0.11),
        )
        _set_color(mast, (0.20, 0.21, 0.23))
        housing = _define_box(
            self.stage,
            "/World/HeadHousing",
            size=(0.10, 0.13, 0.08),
            center=(eye[0] - 0.06, 0.0, eye[2]),
        )
        _set_color(housing, (0.16, 0.17, 0.19))

        self.camera = RtxCamera(
            "/World/HeadCamera",
            tick_rate=30.0,
            positions=[eye],
            orientations=[look_at_quat(eye, target)],
        )
        # OpenUSD optics are in tenths of a scene unit.
        self.camera.camera.set_focal_lengths(cfg.camera_focal_length)
        self.camera.camera.set_apertures(cfg.camera_aperture)
        self.camera.camera.set_focus_distances(1.0)
        self.camera.camera.set_clipping_ranges(0.01, 50.0)
        self.camera_sensor = CameraSensor(
            self.camera,
            resolution=resolution,
            annotators=annotators,
        )
        say(f"head camera at {eye} looking at {target}, res={resolution}, annotators={annotators}")

    # ------------------------------------------------------------------ #
    # Runtime
    # ------------------------------------------------------------------ #
    def start(self, physics_dt: float = 1.0 / 120.0, warmup_steps: int = 60) -> None:
        """Start physics and instantiate the articulation handle."""
        import carb

        from isaacsim.core.simulation_manager import SimulationManager

        # Pin the simulation to a fixed timestep. Otherwise Kit advances physics
        # by wall-clock time, so a slow frame (camera + sensors + IK) makes the
        # world jump many physics steps at once and the belt appears to teleport.
        settings = carb.settings.get_settings()
        settings.set("/app/player/useFixedTimeStep", True)
        settings.set("/app/player/fixedTimeStep", physics_dt)

        say("setting tensor backend = torch")
        SimulationManager.set_backend("torch")
        say("switching physics engine = physx")
        SimulationManager.switch_physics_engine("physx")
        say(f"setting physics dt = {physics_dt:.5f}s")
        SimulationManager.set_physics_dt(physics_dt)
        say("play(commit=True)")
        app_utils.play(commit=True)
        say(f"warm-up {warmup_steps} steps")
        app_utils.update_app(steps=warmup_steps)
        if self.stage.GetPrimAtPath("/World/OpenArm").IsValid():
            self.robot = Articulation("/World/OpenArm")
            say(f"simulation running, dt={physics_dt:.5f}s, joints={len(self.robot.joint_names)}")
        else:
            say(f"simulation running, dt={physics_dt:.5f}s (no robot in this scene)")

    def step(self, n: int = 1) -> None:
        app_utils.update_app(steps=n)

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #
    def report_robot(self) -> None:
        for side, link in OPENARM_TCP_LINKS.items():
            pose, _ = self.link_pose(link)
            say(f"TCP {side:5s} at {np.round(pose, 4).tolist()}")

    def _link_handle(self, link_name: str):
        """Cache a RigidPrim handle for one articulation link (root pose reads only cover the base)."""
        if not hasattr(self, "_link_handles"):
            self._link_handles = {}
        if link_name not in self._link_handles:
            index = list(self.robot.link_names).index(link_name)
            paths = self.robot.link_paths
            if paths and isinstance(paths[0], (list, tuple)):
                paths = paths[0]
            path = paths[index]
            if isinstance(path, (list, tuple)):
                path = path[0]
            self._link_handles[link_name] = RigidPrim(str(path))
        return self._link_handles[link_name]

    def link_pose(self, link_name: str) -> tuple[np.ndarray, np.ndarray]:
        positions, orientations = self._link_handle(link_name).get_world_poses()
        return to_numpy(positions)[0], to_numpy(orientations)[0]

    def capture(self, path: str) -> dict[str, np.ndarray]:
        from PIL import Image

        images = {
            "rgb": to_numpy(self.camera_sensor.get_data("rgb")),
            "depth": to_numpy(self.camera_sensor.get_data("distance_to_image_plane")),
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if images["rgb"] is not None:
            Image.fromarray(images["rgb"][..., :3].astype(np.uint8)).save(path)
            say(f"saved {path}")
        if images["depth"] is not None:
            depth = images["depth"][..., 0].astype(np.float32)
            finite = np.isfinite(depth) & (depth > 0.0)
            if np.any(finite):
                lo, hi = np.percentile(depth[finite], [2, 98])
                norm = np.clip((depth - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
                norm[~finite] = 0.0
                Image.fromarray((norm * 255).astype(np.uint8)).save(path.replace(".png", "_depth.png"))
                say(f"depth valid={int(finite.sum())}/{finite.size} range=[{lo:.2f},{hi:.2f}] m")
        return images
