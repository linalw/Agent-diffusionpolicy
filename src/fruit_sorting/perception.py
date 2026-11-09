"""Model-based fruit measurement from the rendered RGB-D and the instance mask (P135).

The shipped catch reads the fruit's centre, diameter, velocity and grade from
the simulator's rigid-body state.  That is the one thing a real cell cannot
hand you.  This module replaces that read with a measurement the *model* makes:

1. render the head camera (RGB + `distance_to_image_plane` + `instance_id_segmentation`);
2. select the pixels of the target instance (the mask's label is the prim path);
3. back-project those pixels through the camera's **calibration** - the pinhole
   intrinsics from the authored focal length / aperture and the camera prim's
   world pose - into world points;
4. fit a sphere to the point cloud by least squares (the payloads are modelled
   as spheres/ellipsoids, and the equatorial disc is what the close law needs),
   with a trim pass so a stray background pixel cannot move the centre.

The output is `{position, diameter, radius, rms, pixels, depth_m}`: position and
diameter, exactly the two quantities the grasp consumes, and nothing from the
simulator's state.  The velocity is the tracker's job (`tracking.FruitTracker`),
because no single frame measures one.

Calibration is data the cell legitimately owns: the camera's mount pose and its
lens.  The ground truth is used **only** by the bench (`FRUIT_TRACK_DIAG`'s
`err=` column), never by the estimate.
"""

from __future__ import annotations

import math
import os

import numpy as np


class CameraModel:
    """A pinhole camera with a world pose - the cell's calibration."""

    def __init__(self, width, height, focal, aperture_x, aperture_y,
                 rotation, translation, meters_per_unit: float = 1.0):
        #: The authored lens. `fx`/`fy` are derived per frame from the frame's
        #: own shape, so a `FRUIT_CAMERA_RES` override cannot desynchronise the
        #: calibration from the pixels (the policy runs at 240x424 while the
        #: scene authors 480x848).
        self.width = int(width)
        self.height = int(height)
        self.focal = float(focal)
        self.aperture_x = float(aperture_x)
        self.aperture_y = float(aperture_y)
        #: World <- camera rotation (columns are the camera's axes in world).
        self.rotation = np.asarray(rotation, dtype=float)
        self.translation = np.asarray(translation, dtype=float)
        self.meters_per_unit = float(meters_per_unit)

    # ------------------------------------------------------------------ #
    @classmethod
    def from_scene(cls, scene, cfg, resolution=None) -> "CameraModel":
        """Build the calibration from the authored lens and the camera's prim."""
        from pxr import Usd, UsdGeom

        if resolution is None:
            resolution = (
                int(cfg.camera_resolution[1]),
                int(cfg.camera_resolution[0]),
            )
        width, height = int(resolution[0]), int(resolution[1])
        focal = float(cfg.camera_focal_length)
        aperture_x, aperture_y = (float(v) for v in cfg.camera_aperture)
        prim = scene.stage.GetPrimAtPath("/World/HeadCamera")
        if not prim.IsValid():
            raise RuntimeError("the head camera prim is not in the stage")
        matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(
            Usd.TimeCode.Default()
        )
        translation = np.array(matrix.ExtractTranslation(), dtype=float)
        # USD transforms row vectors (`p_world = p_local * M`), so the camera's
        # local axes in world are the *columns* of M's rotation block.
        rotation = np.array(
            [[matrix[i][j] for j in range(3)] for i in range(3)], dtype=float
        ).T
        try:
            meters = float(UsdGeom.GetStageMetersPerUnit(scene.stage))
        except Exception:  # noqa: BLE001 - older USD has no helper
            meters = float(scene.stage.GetMetadata("metersPerUnit") or 1.0)
        return cls(
            width, height, focal, aperture_x, aperture_y,
            rotation, translation, meters,
        )

    # ------------------------------------------------------------------ #
    def intrinsics(self, height: int, width: int):
        """`(fx, fy, cx, cy)` for a frame of this shape."""
        fx = width * self.focal / self.aperture_x
        fy = height * self.focal / self.aperture_y
        return fx, fy, (width - 1) * 0.5, (height - 1) * 0.5

    def backproject(self, depth: np.ndarray, pixels: np.ndarray) -> np.ndarray:
        """World points for `pixels` (N x 2, (u, v)) at their depth values."""
        u = pixels[:, 0].astype(float)
        v = pixels[:, 1].astype(float)
        fx, fy, cx, cy = self.intrinsics(depth.shape[0], depth.shape[1])
        z = depth[pixels[:, 1], pixels[:, 0]].astype(float) * self.meters_per_unit
        cam = np.stack(
            [
                (u - cx) / fx * z,
                -(v - cy) / fy * z,
                -z,
            ],
            axis=1,
        )
        return cam @ self.rotation.T + self.translation


def _fit_sphere_known_radius(points: np.ndarray, radius: float, centre0,
                             iterations: int = 8):
    """Least-squares centre with the radius **fixed** [m].

    During the descent the hand occludes the fruit and the visible cap shrinks;
    a free fit then has almost no curvature to work with and its centre drifts
    *along the view axis* (measured: the z error grows 11 -> 44 mm as the mask
    goes 48 -> 22 px). The radius does not change, so fixing it removes that
    degree of freedom and the cap only has to locate the centre.
    """
    c = np.asarray(centre0, dtype=float).copy()
    rms = float("nan")
    for _ in range(max(1, int(iterations))):
        delta = points - c
        distance = np.maximum(np.linalg.norm(delta, axis=1), 1e-9)
        residual = distance - float(radius)
        jacobian = -delta / distance[:, None]
        normal = jacobian.T @ jacobian + 1e-9 * np.eye(3)
        step = np.linalg.solve(normal, -jacobian.T @ residual)
        c = c + step
        rms = float(np.sqrt(np.mean(residual ** 2)))
        if float(np.linalg.norm(step)) < 1e-9:
            break
    return c, rms


def _fit_sphere(points: np.ndarray, iterations: int = 3, trim: float = 2.5):
    """Least-squares sphere through `points`, with a trimmed refit.

    ``|p - c|^2 = r^2`` is linear in ``(c, k)`` with ``k = r^2 - |c|^2``:
    ``2 p . c + k = |p|^2``.  The trimmed refit drops points further than
    ``trim * rms`` from the first fit, which is what a background pixel that
    leaked into the mask needs.
    """
    keep = np.ones(len(points), dtype=bool)
    centre = None
    radius = float("nan")
    rms = float("nan")
    for _ in range(max(1, iterations)):
        p = points[keep]
        if len(p) < 8:
            break
        a = np.concatenate([2.0 * p, np.ones((len(p), 1))], axis=1)
        b = np.einsum("ij,ij->i", p, p)
        solution, *_ = np.linalg.lstsq(a, b, rcond=None)
        centre = solution[0:3]
        k = float(solution[3])
        radius = math.sqrt(max(0.0, float(np.dot(centre, centre)) + k))
        residual = np.abs(np.linalg.norm(points - centre, axis=1) - radius)
        rms = float(np.sqrt(np.mean(residual[keep] ** 2)))
        if not math.isfinite(rms) or rms <= 0.0:
            break
        keep = residual <= max(trim * rms, 3e-4)
    return centre, radius, rms


class FruitPerception:
    """One camera + one target instance -> (centre, diameter), per observation.

    The object caches the last estimate and refuses to spend a render more often
    than `hz`; the tracker interpolates between observations, which is what a
    30 Hz camera in a 120 Hz control loop needs.
    """

    def __init__(self, scene, cfg, hz: float = 30.0, stride: int = 2,
                 trim: float = 2.5, min_pixels: int = 60,
                 full_pixels: int = 120):
        self.scene = scene
        self.camera = CameraModel.from_scene(scene, cfg)
        self.hz = max(1.0, float(hz))
        self.stride = max(1, int(stride))
        self.trim = float(trim)
        #: A cap smaller than this does not constrain the centre along the view
        #: axis (the hand occludes the fruit as it descends: measured, the fit's
        #: z drifts 11 -> 44 mm as the mask shrinks 48 -> 22 px). Refusing the
        #: frame and letting the filter predict is strictly better than feeding
        #: it a sliver - see `measure`'s contract.
        self.min_pixels = max(8, int(min_pixels))
        #: A cap at least this big is trusted to set the *radius*; smaller caps
        #: only locate the centre, with the radius held (see the fit below).
        self.full_pixels = max(self.min_pixels, int(full_pixels))
        self.last_radius = None
        self.last_centre = None
        self.fixed_fits = 0
        self.rejected = 0
        self.last_t = -1e9
        self.last_estimate = None
        self.renders = 0
        self.frames = 0
        self.failures = 0
        self.last_error = ""

    # ------------------------------------------------------------------ #
    def _render(self, task) -> None:
        """One render, on whichever thread owns the stage (two-line bridge)."""
        from isaacsim.core.rendering_manager import RenderingManager

        session = getattr(task, "_active_session", None)
        bridged = (
            session is not None
            and session.relay.participant()
            and session.bridge.serving
        )
        if bridged:
            session.bridge.call(RenderingManager.render)
        else:
            RenderingManager.render()

    def _mask(self, prim_path: str):
        raw = self.scene.camera_sensor.get_data("instance_id_segmentation")
        if raw is None:
            return None
        seg = np.asarray(raw[0].numpy())
        while seg.ndim > 2:
            seg = seg[..., 0]
        info = raw[1] if isinstance(raw, tuple) and len(raw) > 1 else {}
        labels = info.get("idToLabels", {}) if isinstance(info, dict) else {}
        target = 0
        for key, value in labels.items():
            if prim_path in str(value):
                target = int(key)
                break
        if target == 0:
            return None
        return seg == target

    def measure(self, task, sample, force: bool = False):
        """One model-based measurement, or **None** when there is no fresh one.

        The contract is deliberate: `None` means "the filter must predict", not
        "reuse the last answer". A cached position fed back as a measurement
        would be a lie the filter cannot see, and inside the camera period it
        would be counted four times at the 120 Hz control rate.

        `force=True` is for the one tick that matters - the descent's start,
        which seeds the filter. Without it the anchor lands inside the 30 Hz
        period three times out of four and no filter is ever created (measured:
        93 accepted frames and not one accepted anchor frame).
        """
        now = float(task._sim_time())
        if not force and now - self.last_t < 1.0 / self.hz - 1e-9:
            return None
        self.last_t = now
        try:
            self._render(task)
            raw_rgb = self.scene.camera_sensor.get_data("rgb")
            raw_depth = self.scene.camera_sensor.get_data(
                "distance_to_image_plane"
            )
            if raw_rgb is None or raw_depth is None:
                self.failures += 1
                self.last_error = "no frame"
                return None
            depth = np.asarray(raw_depth[0].numpy(), dtype=np.float32)
            if depth.ndim == 3:
                # The annotator can hand back a trailing channel dimension.
                depth = depth[..., 0]
            if depth.ndim != 2:
                self.failures += 1
                self.last_error = f"depth shape {depth.shape}"
                return None
            mask = self._mask(sample.prim_path)
            if mask is None:
                self.failures += 1
                self.last_error = "target not in frame"
                return None
            pixels = np.argwhere(mask)[:, ::-1]  # (u, v)
            if len(pixels) < self.min_pixels:
                self.failures += 1
                self.rejected += 1
                self.last_error = f"occluded ({len(pixels)} px < {self.min_pixels})"
                return None
            pixels = pixels[:: self.stride]
            self.renders += 1
            points = self.camera.backproject(depth, pixels)
            # The belt and everything behind the fruit are far; keep the band
            # around the mask's median depth so a hole in the mask or a specular
            # dropout cannot drag the fit.
            z = depth[pixels[:, 1], pixels[:, 0]].astype(float)
            finite = np.isfinite(z) & (z > 0.05)
            if not np.any(finite):
                self.failures += 1
                self.last_error = "no finite depth"
                return None
            band = np.abs(z - np.median(z[finite])) <= 0.05
            points = points[finite & band]
            if len(points) < 12:
                self.failures += 1
                self.last_error = "too few depth points"
                return None
            if (
                self.last_radius is not None
                and self.last_centre is not None
                and len(points) < self.full_pixels
            ):
                # Partial view: the radius is a property of the fruit, not of the
                # frame. Hold it and let the cap locate the centre only.
                centre, rms = _fit_sphere_known_radius(
                    points, self.last_radius, self.last_centre
                )
                radius = float(self.last_radius)
                self.fixed_fits += 1
            else:
                centre, radius, rms = _fit_sphere(points, trim=self.trim)
                if self.last_radius is not None and abs(
                    radius - self.last_radius
                ) > 0.25 * self.last_radius:
                    # A *full* cap that fits a very different sphere is a
                    # different object (or a badly segmented one): refuse it and
                    # let the filter carry the state.
                    self.failures += 1
                    self.rejected += 1
                    self.last_error = (
                        f"radius jump {2 * radius * 1000:.1f} vs "
                        f"{2 * self.last_radius * 1000:.1f} mm"
                    )
                    return None
                self.last_radius = float(radius)
            if centre is None or not math.isfinite(radius) or radius <= 0.005:
                self.failures += 1
                self.last_error = "degenerate fit"
                return None
            self.last_centre = np.asarray(centre, dtype=float).copy()
            self.frames += 1
            self.last_estimate = {
                "position": np.asarray(centre, dtype=float),
                "diameter": float(2.0 * radius),
                "radius": float(radius),
                "rms": float(rms),
                "pixels": int(len(points)),
                "depth_m": float(np.median(z[finite]) * self.camera.meters_per_unit),
                "depth_raw": float(np.median(z[finite])),
                "t": now,
            }
            return self.last_estimate
        except Exception as exc:  # noqa: BLE001 - a perception fault must not kill the cell
            self.failures += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None

    # ------------------------------------------------------------------ #
    def summary(self) -> dict:
        return {
            "renders": int(self.renders),
            "frames": int(self.frames),
            "failures": int(self.failures),
            "rejected": int(self.rejected),
            "fixed_fits": int(self.fixed_fits),
            "last_error": self.last_error,
            "fx": self.camera.intrinsics(
                self.camera.height, self.camera.width
            )[0],
            "fy": self.camera.intrinsics(
                self.camera.height, self.camera.width
            )[1],
            "meters_per_unit": self.camera.meters_per_unit,
        }


def perception_from_env(scene, cfg) -> FruitPerception:
    """Build the module once per run (the camera does not move)."""
    return FruitPerception(
        scene,
        cfg,
        hz=float(os.environ.get("FRUIT_PERCEPTION_HZ", "30")),
        stride=int(os.environ.get("FRUIT_PERCEPTION_STRIDE", "2")),
        trim=float(os.environ.get("FRUIT_PERCEPTION_TRIM", "2.5")),
        min_pixels=int(os.environ.get("FRUIT_PERCEPTION_MIN_PX", "60")),
        full_pixels=int(os.environ.get("FRUIT_PERCEPTION_FULL_PX", "120")),
    )
