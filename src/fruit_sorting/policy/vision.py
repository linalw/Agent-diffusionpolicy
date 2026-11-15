"""P163: the policy's foveal view - project the target and crop around it.

The measured defect this answers (P161): in the shipped 240x424 frame the target
fruit is **4 px** before the close (0 px at a demonstration's first frame), and
after the loader's 128x128 downsample it is **0-1 px** - below any measured
regime for a learned policy. The goal vector (`FRUIT_GOAL_SOURCE=perception`) is
accurate to 1-3 mm, so it can *point* the crop: project the fruit's 3-D position
into the camera and cut a `crop x crop` window there, resized to the model's
`image_size`.

The projection is validated in `logs/p145` against the instance mask: with the
camera looking down -Z and the image's v axis *down*,
``u = fx * X/(-Z) + cx``, ``v = -fy * Y/(-Z) + cy`` lands on the fruit's mask
centroid to **1.3 px median (p90 2.1)** over 38 frames of a
`FRUIT_HEAD_CAMERA=down_x_160` episode (the goal *snapshot* is constant per
episode; the crop must use the frame's own `fruit_position`, not the goal).
"""

from __future__ import annotations

import os

import numpy as np

#: The authored lens (`assets.SceneConfig`), in scene units (metres).
FOCAL = 0.016
APERTURE = (0.036, 0.02025)

#: `FRUIT_HEAD_CAMERA` poses that the crop can be used with (eye, target).
_POSES = {
    "head_now": ((0.05, 0.00, 2.00), (0.34, 0.22, 1.10)),
    "down_x_160": ((1.60, 0.00, 2.00), (0.34, 0.00, 1.15)),
    "down_high": ((1.20, 0.00, 2.30), (0.40, 0.00, 1.15)),
    "down_x_140": ((1.40, 0.00, 1.75), (0.34, 0.00, 1.20)),
}


def camera_pose(eye=None, target=None) -> tuple[np.ndarray, np.ndarray]:
    """The camera's `(eye, target)`; unset reads `FRUIT_HEAD_CAMERA`."""
    if eye is None or target is None:
        name = os.environ.get("FRUIT_HEAD_CAMERA", "").strip()
        if name:
            if name not in _POSES:
                raise ValueError(f"FRUIT_HEAD_CAMERA={name!r} is not one of {sorted(_POSES)}")
            eye, target = _POSES[name]
        else:
            eye, target = _POSES["head_now"]
    return np.asarray(eye, dtype=float), np.asarray(target, dtype=float)


def camera_rotation(eye, target) -> np.ndarray:
    """World <- camera rotation (columns = the camera's x, y, z axes in world).

    A USD camera looks down its local **-Z** with **+Y** up, so the columns are
    `(right, up, -forward)`.
    """
    eye = np.asarray(eye, dtype=float)
    forward = np.asarray(target, dtype=float) - eye
    norm = float(np.linalg.norm(forward))
    forward = forward / norm if norm > 1e-9 else np.array([1.0, 0.0, 0.0])
    up_hint = np.array([0.0, 0.0, 1.0])
    right = np.cross(forward, up_hint)
    rn = float(np.linalg.norm(right))
    right = right / rn if rn > 1e-9 else np.array([0.0, 1.0, 0.0])
    up = np.cross(right, forward)
    return np.stack([right, up, -forward], axis=1)


def project(
    point,
    eye=None,
    target=None,
    width: int = 424,
    height: int = 240,
) -> tuple[float, float] | None:
    """Project a world point into the camera's pixels, or ``None`` if behind."""
    eye, target = camera_pose(eye, target)
    rot = camera_rotation(eye, target)
    pc = rot.T @ (np.asarray(point, dtype=float)[:3] - eye)
    if -pc[2] <= 1e-6:
        return None
    fx = width * FOCAL / APERTURE[0]
    fy = height * FOCAL / APERTURE[1]
    u = fx * (pc[0] / -pc[2]) + 0.5 * (width - 1)
    v = -fy * (pc[1] / -pc[2]) + 0.5 * (height - 1)
    return float(u), float(v)


def foveal_window(
    uv: tuple[float, float] | None,
    width: int,
    height: int,
    crop: int,
) -> tuple[int, int, int, int]:
    """The clamped square window `(x0, y0, x1, y1)` around `uv`."""
    crop = int(max(8, min(int(crop), min(width, height))))
    if uv is None:
        cx, cy = width * 0.5, height * 0.5
    else:
        cx, cy = uv
    x0 = int(round(cx - crop * 0.5))
    y0 = int(round(cy - crop * 0.5))
    x0 = max(0, min(x0, width - crop))
    y0 = max(0, min(y0, height - crop))
    return x0, y0, x0 + crop, y0 + crop


def crop_and_resize(img: np.ndarray, window, size: int) -> np.ndarray:
    """Crop `window` from `img` and resize to `size` (bilinear, PIL-free)."""
    x0, y0, x1, y1 = window
    patch = img[y0:y1, x0:x1]
    if patch.shape[0] == size and patch.shape[1] == size:
        return patch
    # nearest-neighbour is exact enough for a down/upsample of <= 8x and keeps
    # this module dependency-free; the loader's own downsample uses PIL.
    yi = np.clip((np.arange(size) * patch.shape[0] // size), 0, patch.shape[0] - 1)
    xi = np.clip((np.arange(size) * patch.shape[1] // size), 0, patch.shape[1] - 1)
    return patch[yi][:, xi]
