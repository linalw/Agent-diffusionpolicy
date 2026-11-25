"""The wrist view as a **second measurement of the same fruit** (P277).

The head camera owns the approach. Through the descent and the close the arm sits
between the lens and the fruit, so the measurement stops and the filter coasts -
P276 measured exactly what that costs: `FRUIT_PERCEPTION_COAST_S` 1.0 s at
0.08 m/s leaves the estimate **80 mm** upstream, and the pads close on air
(20/20 -> 9/19).

An eye-in-hand camera does not have that blind spot: it is mounted at the jaw, so
the fruit it is about to grasp is the one thing it cannot miss. P135 measured it
as **the best sensor in the project** - 3.54 mm position, 0.90 mm diameter
against the head's 1.98 / 2.37 - and then could not use it, because a second
`instance_id_segmentation` annotator takes the head camera's mask away (P213), and
this build supports **one annotated camera per run**.

So the question this module answers is not "is the wrist accurate" but **"can the
fruit be isolated in the wrist frame without an instance mask"**. Three
compatible answers, all reading only the depth (and, for one of them, the colour):

``raster``
    P214's bench, kept as the **control**: project the prior into the image and
    take a fixed pixel disk around it. Measured there at 44-62 mm centre error -
    a disk is a cone in the world, so at 0.1 m it swallows the belt and the hand.

``prior``
    **3D ball**: back-project the depth, keep the points within
    ``prior_radius + margin`` of the prior centre, then a trimmed sphere fit. The
    same information the disk was reaching for, expressed in the frame the fit
    lives in, so the gate is a ball and not a cone.

``colour``
    the 3D ball **and** a colour test: the head's own accepted mask supplies a
    colour model (mean/std in RGB) for *this* fruit, and wrist pixels far from it
    are dropped. This is the "colour segmenter" P214 named as the second view's
    missing piece, built on the one camera that can label the fruit.

Every method is truth-free: the prior is the tracker's own prediction, the colour
model comes from the head's own mask, and the fit uses depth only. The wrist's
answer is fed back into the **same** `FruitTracker` as a measurement, which is
what keeps `predict_at` fresh through the contact phase.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np

from .common import look_at_quat, say
from .perception import CameraModel, _fit_sphere

#: Parameters a wrist RGB-D camera is usually specified with in manipulation
#: papers: 640x480 at 30 Hz, a ~69 deg horizontal field of view (the D435-class
#: colour stream), near range 3 cm. The depth stream of the common sensors is
#: wider; this is the conservative end and the one a sphere fit needs.
PAPER_PRESET = {
    #: (height, width) - the tuple order the scene's `CameraSensor` uses. 640x480
    #: landscape is the common wrist RGB-D stream.
    "res": (480, 640),
    "focal": 0.035,
    "aperture": (0.048, 0.036),
    "hz": 30.0,
}

MODES = ("off", "raster", "prior", "colour", "learned")


def wrist_spec_from_env(default_res=(240, 424), default_focal=0.035,
                        default_aperture=(0.036, 0.02025)):
    """`(resolution, focal, aperture_x, aperture_y, hz)` for the wrist pair."""
    preset = os.environ.get("FRUIT_WRIST_PRESET", "shipped").strip().lower()
    if preset == "paper":
        res = PAPER_PRESET["res"]
        focal = PAPER_PRESET["focal"]
        ap = PAPER_PRESET["aperture"]
        hz = PAPER_PRESET["hz"]
    else:
        res = default_res
        focal = default_focal
        ap = default_aperture
        hz = 30.0
    res_raw = os.environ.get("FRUIT_WRIST_RES", "").strip()
    if res_raw:
        res = tuple(int(v) for v in res_raw.split(","))
    ap_raw = os.environ.get("FRUIT_WRIST_APERTURE", "").strip()
    if ap_raw:
        ap = tuple(float(v) for v in ap_raw.split(","))
    hz = float(os.environ.get("FRUIT_WRIST_HZ", str(hz)) or hz)
    return tuple(res), float(focal), float(ap[0]), float(ap[1]), hz


def mode_from_env() -> str:
    raw = os.environ.get("FRUIT_WRIST", "off").strip().lower()
    if raw not in MODES:
        raise ValueError(
            f"FRUIT_WRIST must be one of {MODES}, got {os.environ.get('FRUIT_WRIST')!r}"
        )
    return raw


def pool_rgb(rgb, h: int, w: int) -> np.ndarray:
    """`(H, W, 3)` -> `(3, h, w)`. Channels-first **before** pooling, or the
    channel axis is treated as height (the same defect the trainer hit)."""
    a = np.asarray(rgb, dtype=np.float32)[..., :3].transpose(2, 0, 1)
    return pool_any(a, h, w)


def pool_depth(depth, h: int, w: int) -> np.ndarray:
    return pool_any(np.asarray(depth, dtype=np.float32), h, w)


def pool_any(a: np.ndarray, h: int, w: int) -> np.ndarray:
    """Mean-pool an image (and its channel axis) to (h, w)."""
    a = np.asarray(a, dtype=np.float32)
    h0, w0 = a.shape[-2:]
    fy, fx = max(1, h0 // h), max(1, w0 // w)
    if fy > 1 or fx > 1:
        a = a[..., : fy * h, : fx * w]
        a = a.reshape(*a.shape[:-2], h, fy, w, fx).mean(axis=(-3, -1))
    return a


def upscale_mask(mask: np.ndarray, shape) -> np.ndarray:
    """Nearest-neighbour upscale of a low-res boolean mask to `shape`."""
    h, w = int(shape[0]), int(shape[1])
    ys = (np.arange(h) * mask.shape[0] // h).clip(0, mask.shape[0] - 1)
    xs = (np.arange(w) * mask.shape[1] // w).clip(0, mask.shape[1] - 1)
    return mask[ys][:, xs]


def _build_seg_net(h: int, w: int, meta: dict):
    """The same architecture `scripts/293_p279_wrist_seg_train.py` trains."""
    import torch.nn as nn

    class TinySeg(nn.Module):
        def __init__(self):
            super().__init__()
            self.e1 = nn.Sequential(nn.Conv2d(4, 16, 3, padding=1), nn.ReLU(),
                                    nn.Conv2d(16, 16, 3, padding=1), nn.ReLU())
            self.e2 = nn.Sequential(nn.Conv2d(16, 32, 3, stride=2, padding=1), nn.ReLU(),
                                    nn.Conv2d(32, 32, 3, padding=1), nn.ReLU())
            self.e3 = nn.Sequential(nn.Conv2d(32, 64, 3, stride=2, padding=1), nn.ReLU(),
                                    nn.Conv2d(64, 64, 3, padding=1), nn.ReLU())
            self.d2 = nn.ConvTranspose2d(64, 32, 2, stride=2)
            self.d1 = nn.ConvTranspose2d(64, 16, 2, stride=2)
            self.out = nn.Conv2d(32, 1, 1)

        def forward(self, z):
            a = self.e1(z)
            b = self.e2(a)
            c = self.e3(b)
            u = torch_cat(torch_relu(self.d2(c)), b)
            v = torch_cat(torch_relu(self.d1(u)), a)
            return self.out(v)

    return TinySeg()


def torch_cat(a, b):
    import torch

    return torch.cat([a, b], 1)


def torch_relu(a):
    import torch

    return torch.relu(a)


class WristRig:
    """One arm's wrist camera: aim it, render it, and measure without a mask."""

    def __init__(self, scene, task, side: str, mode: str, spec=None, render=None):
        self.scene = scene
        self.task = task
        self.side = side
        self.mode = mode
        if spec is None:
            cfg = getattr(task, "cfg", None)
            spec = wrist_spec_from_env(
                default_focal=(
                    float(getattr(cfg, "camera_focal_length", 0.035))
                    if cfg is not None else 0.035
                ),
                default_aperture=(
                    tuple(getattr(cfg, "camera_aperture", (0.036, 0.02025)))
                    if cfg is not None else (0.036, 0.02025)
                ),
            )
        self.spec = spec
        #: **the render is not optional.** `set_wrist_pose` writes USD attributes;
        #: without a render between it and `get_data` the sensor returns the frame
        #: from its *build-time* pose - measured: two runs 12 cm apart returned the
        #: same picture (a distant belt and one finger), which is why every earlier
        #: wrist number was measured on the wrong view.
        self._render_fn = render
        self.renders = 0
        self.models: dict[tuple[int, int], CameraModel] = {}
        #: instruments
        self.attempts = 0
        self.accepted = 0
        self.rejected = 0
        self.reasons: dict[str, int] = {}
        self.last = None
        self.pixels = 0
        self.rms = float("nan")
        self.margin = float(os.environ.get("FRUIT_WRIST_GATE_MARGIN", "0.035"))
        self.min_pixels = int(os.environ.get("FRUIT_WRIST_MIN_PX", "40"))
        self.max_rms = float(os.environ.get("FRUIT_WRIST_MAX_RMS", "0.004"))
        self.stride = max(1, int(os.environ.get("FRUIT_WRIST_STRIDE", "2")))
        self.probe_r = int(os.environ.get("FRUIT_WRIST_PROBE_R", "35"))
        self.colour_tol = float(os.environ.get("FRUIT_WRIST_COLOUR_TOL", "3.0"))
        #: how far from the prior the wrist will look at all (a guard, not a gate)
        self.reach = float(os.environ.get("FRUIT_WRIST_REACH", "0.20"))
        self.eps = float(os.environ.get("FRUIT_WRIST_CLUSTER_EPS", "0.012"))
        #: **the range gate is what makes this usable.** The camera is 6 cm behind
        #: the jaw, so the fruit is 3-20 cm away; a background cluster at 1 m is
        #: excluded outright. Measured without it: 26 % of measurements accepted,
        #: diameter p50 1.9 cm (the pool is 3-7) and |e| p50 **307 mm** - the
        #: selector was locking onto the belt and the background.
        self.range_m = float(os.environ.get("FRUIT_WRIST_RANGE", "0.25"))
        self.min_pixels_big = int(os.environ.get("FRUIT_WRIST_MIN_PX_BIG", "250"))
        self.dia_tol = float(os.environ.get("FRUIT_WRIST_DIA_TOL", "0.020"))
        #: **the last gate, and the one that removes the bad tail.** The fruit being
        #: grasped is next to the pads, so it is within a few centimetres of the jaw.
        #: Measured before it: accepted fits ranged 4.3 mm to **894 mm** - the far
        #: ones are a lock on the belt or a neighbour, and they are what turn the
        #: tracker into garbage.
        self.jaw_max = float(os.environ.get("FRUIT_WRIST_JAW_MAX", "0.12"))
        #: one frame per attempt, for the eye. A PPM plus an .npy: no image library
        #: is assumed, and `ffmpeg` reads PPM.
        self.dump_dir = os.environ.get("FRUIT_WRIST_DUMP", "").strip()
        self.dumps = 0
        #: P279: **the collection pass for a learned segmenter.** Armed with
        #: `FRUIT_WRIST_LABELS=<dir>`, the run authors the wrist **with** the
        #: instance annotator (so the head loses its mask - that is fine here, the
        #: goal is truth-fed on this pass), poses/renders per observation and
        #: writes `rgb.npy` + `depth.npy` + `mask.npy` per frame. The result is the
        #: only way to get wrist labels in this build: one annotated camera at a
        #: time (P213), so the labels are collected when the *wrist* holds it.
        self.label_dir = os.environ.get("FRUIT_WRIST_LABELS", "").strip()
        self.saved = 0
        self.label_max = int(os.environ.get("FRUIT_WRIST_LABELS_MAX", "1200"))

    # -- aim ---------------------------------------------------------- #
    def aim(self, target=None) -> np.ndarray | None:
        """Put the camera behind/above the jaw, looking at the **jaw**.

        Aiming at the prior was the first design and the probe cell killed it:
        the prior is the number that goes wrong (P276: 80 mm of coast), and a
        wrist pointed 80 mm away puts the fruit at the frame's edge or outside it
        - `no points near the prior (0)` was 146 of 238 attempts. The jaw is the
        robot's own state (a real cell has it exactly), and the fruit being
        grasped is the thing next to the pads, so the camera looks there.
        `FRUIT_WRIST_AIM=prior` restores the old form for an A/B.
        """
        arm = self.task.arms[self.side]
        entry = getattr(self.scene, "wrist_cameras", {}).get(self.side)
        if entry is None:
            return None
        jaw = np.asarray(arm.jaw_centre(), dtype=float)
        axis = np.asarray(arm.approach_axis(), dtype=float)
        axis = axis / max(float(np.linalg.norm(axis)), 1e-9)
        rot = self.task._quat_matrix(np.asarray(arm.tcp_pose()[1], dtype=float))
        side_vec = np.asarray(rot[:, 0], dtype=float)
        #: **Which side of the jaw the camera sits on.** `approach_axis()` points
        #: *up* (+z) here - measured: `axis=(0.00,0.00,+1.00)` with the jaw at
        #: z=1.241 and the fruit at z~1.20. The shipped expression put the eye at
        #: `jaw - back*axis`, i.e. 6 cm **below** the jaw, looking up at the back of
        #: the hand: the dumped frame showed the belt and one finger, no fruit - and
        #: that is the origin of P135/P214's 44-62 mm "noisy" wrist. The camera has
        #: to be **above** the jaw looking **down** at the fruit.
        _sign = -1.0 if os.environ.get(
            "FRUIT_WRIST_EYE", "above"
        ).strip().lower() == "below" else 1.0
        eye = (
            jaw
            + _sign * float(getattr(self.task, "_wrist_back", 0.06)) * axis
            + float(getattr(self.task, "_wrist_side", 0.045)) * side_vec
        )
        if target is None:
            mode = os.environ.get("FRUIT_WRIST_AIM", "jaw").strip().lower()
            if mode == "prior":
                target = getattr(self, "_last_prior", None)
            if target is None:
                # 3 cm **toward the fruit**: below the jaw, since the axis points up.
                target = jaw - 0.03 * axis
        self.scene.set_wrist_pose(self.side, eye, np.asarray(target, dtype=float))
        if os.environ.get("FRUIT_WRIST_GEOM", "0").strip() == "1":
            say(
                f"[wrist] geom jaw=({jaw[0]:+.3f},{jaw[1]:+.3f},{jaw[2]:+.3f}) "
                f"axis=({axis[0]:+.2f},{axis[1]:+.2f},{axis[2]:+.2f}) "
                f"eye=({eye[0]:+.3f},{eye[1]:+.3f},{eye[2]:+.3f}) "
                f"target=({target[0]:+.3f},{target[1]:+.3f},{target[2]:+.3f})"
            )
        return eye

    def _jaw(self) -> np.ndarray | None:
        try:
            return np.asarray(self.task.arms[self.side].jaw_centre(), dtype=float)
        except Exception:  # noqa: BLE001 - a stub task has no jaw
            return None

    def _render(self) -> None:
        fn = self._render_fn
        if fn is None:
            from isaacsim.core.rendering_manager import RenderingManager

            session = getattr(self.task, "_active_session", None)
            bridged = (
                session is not None
                and session.relay.participant()
                and session.bridge.serving
            )
            if bridged:
                session.bridge.call(RenderingManager.render)
            else:
                RenderingManager.render()
        else:
            fn()
        self.renders += 1

    # -- read --------------------------------------------------------- #
    def _frame(self):
        entry = getattr(self.scene, "wrist_cameras", {}).get(self.side)
        if entry is None:
            return None, None, None
        sensor = entry[1]
        raw = sensor.get_data("distance_to_image_plane")
        depth = None
        if raw is not None:
            depth = np.asarray(raw[0].numpy(), dtype=np.float32)
            if depth.ndim == 3:
                depth = depth[..., 0]
        rgb = None
        if self.mode in ("colour", "learned") or self.dump_dir:
            raw_rgb = sensor.get_data("rgb")
            if raw_rgb is not None:
                rgb = np.asarray(raw_rgb[0].numpy())
        return depth, rgb, entry

    def _model(self, shape, path):
        key = (int(shape[0]), int(shape[1]))
        model = self.models.get(key)
        if model is None:
            _res, focal, ax, ay, _hz = self.spec
            model = CameraModel(
                key[1], key[0], focal, ax, ay, np.eye(3), np.zeros(3)
            )
            self.models[key] = model
        model.update_pose(self.scene, path)
        return model

    def _cluster_near(self, points, prior_pos):
        """The connected blob nearest the prior whose size is a fruit.

        **Voxel connectivity, not a ball around a seed.** The first version grew a
        `eps` ball from the nearest point and read `diameter 19 mm vs 60 mm` on a
        real 6 cm fruit 89 times: a 12 mm ball can never hold a 60 mm object, so
        every component was a shard of it. A voxel grid plus a 26-neighbour flood
        fill is the standard way and is what the fit needs.
        """
        if len(points) < self.min_pixels:
            return None
        if len(points) > 12000:
            step = int(math.ceil(len(points) / 12000.0))
            points = points[::step]
        keys = np.floor(points / self.eps).astype(np.int64)
        uniq, inv = np.unique(keys, axis=0, return_inverse=True)
        if len(uniq) == 0:
            return None
        lookup = {tuple(k): i for i, k in enumerate(uniq)}
        seen = np.zeros(len(uniq), dtype=bool)
        neigh = [
            (dx, dy, dz)
            for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
            if (dx, dy, dz) != (0, 0, 0)
        ]
        prior = np.asarray(prior_pos, dtype=float)
        best = None
        best_cost = float("inf")
        comps = 0
        for i in range(len(uniq)):
            if seen[i]:
                continue
            stack = [i]
            seen[i] = True
            members = []
            while stack:
                j = stack.pop()
                members.append(j)
                kx, ky, kz = uniq[j]
                for d in neigh:
                    m = lookup.get((kx + d[0], ky + d[1], kz + d[2]))
                    if m is not None and not seen[m]:
                        seen[m] = True
                        stack.append(m)
            comps += 1
            if comps > 200:
                break
            sel = np.isin(inv, members)
            cluster = points[sel]
            if len(cluster) < self.min_pixels_big:
                continue
            centre, radius, _rms = _fit_sphere(cluster, trim=2.5)
            if centre is None or not math.isfinite(radius):
                continue
            if not (0.008 <= radius <= 0.045):
                continue
            cost = float(np.linalg.norm(np.asarray(centre) - prior))
            if cost < best_cost:
                best_cost = cost
                best = cluster
        return best

    def _dump(self, rgb, depth) -> None:
        try:
            os.makedirs(self.dump_dir, exist_ok=True)
            stem = os.path.join(self.dump_dir, f"wrist_{self.side}_{self.dumps:02d}")
            with open(stem + ".npy", "wb") as fh:
                np.save(fh, np.asarray(depth))
            if rgb is not None:
                img = np.asarray(rgb)[..., :3].astype(np.uint8)
                h, w = img.shape[:2]
                with open(stem + ".ppm", "wb") as fh:
                    fh.write(b"P6\n%d %d\n255\n" % (w, h))
                    fh.write(img.tobytes())
            self.dumps += 1
            say(f"[wrist] dumped {stem}.ppm")
        except Exception as exc:  # noqa: BLE001 - a dump must never kill the cell
            say(f"[wrist] dump failed: {type(exc).__name__}: {exc}")

    def _reject(self, why: str):
        self.rejected += 1
        self.reasons[why] = self.reasons.get(why, 0) + 1
        return None

    # -- the learned mask (P279) -------------------------------------- #
    @staticmethod
    def _seg_net():
        """The trained segmenter, loaded once per process (None if absent)."""
        cached = getattr(WristRig, "_seg_cache", None)
        if cached is not None:
            return cached
        path = os.environ.get("FRUIT_WRIST_SEG", "checkpoints/wrist_seg.pt")
        WristRig._seg_cache = False
        try:
            import torch

            from . import wrist as _self

            meta_path = os.path.splitext(path)[0] + ".json"
            with open(meta_path) as fh:
                meta = json.load(fh)
            net = _self._build_seg_net(int(meta["h"]), int(meta["w"]), meta)
            net.load_state_dict(torch.load(path, map_location="cpu"))
            net.eval()
            WristRig._seg_cache = (net, meta, torch)
            say(f"[wrist] segmenter {path} (val IoU {meta.get('val_iou'):.3f})")
        except Exception as exc:  # noqa: BLE001 - a missing net is a named refusal
            say(f"[wrist] segmenter unavailable ({type(exc).__name__}: {exc})")
        return WristRig._seg_cache

    def _learned_mask(self, rgb, depth):
        """Run the segmenter on one wrist frame; returns a boolean mask or None."""
        loaded = self._seg_net()
        if not loaded:
            return None
        net, meta, torch = loaded
        h, w = int(meta["h"]), int(meta["w"])
        scale = float(meta.get("depth_scale", 0.30))
        img = pool_rgb(rgb, h, w) / 255.0
        d = pool_depth(depth, h, w)
        d = np.clip(np.nan_to_num(d, nan=1.0), 0.0, scale) / scale
        x = np.concatenate([img, d[None]], axis=0)[None].astype(np.float32)
        with torch.no_grad():
            logits = net(torch.from_numpy(x))
            prob = torch.sigmoid(logits)[0, 0].numpy()
        small = prob > 0.5
        if small.shape != depth.shape:
            from .wrist import upscale_mask

            small = upscale_mask(small, depth.shape)
        return small

    def capture(self, sample_prim: str) -> bool:
        """One labelled wrist frame for the segmenter dataset (P279)."""
        if not self.label_dir:
            return False
        if self.saved >= self.label_max:
            return False
        eye = self.aim(None)
        if eye is None:
            return False
        self._render()
        entry = getattr(self.scene, "wrist_cameras", {}).get(self.side)
        if entry is None:
            return False
        sensor = entry[1]
        raw_d = sensor.get_data("distance_to_image_plane")
        raw_rgb = sensor.get_data("rgb")
        if raw_d is None or raw_rgb is None:
            return False
        depth = np.asarray(raw_d[0].numpy(), dtype=np.float32)
        if depth.ndim == 3:
            depth = depth[..., 0]
        rgb = np.asarray(raw_rgb[0].numpy())[..., :3].astype(np.uint8)
        mask = None
        raw_seg = sensor.get_data("instance_id_segmentation")
        if raw_seg is not None:
            seg = np.asarray(raw_seg[0].numpy())
            while seg.ndim > 2:
                seg = seg[..., 0]
            info = raw_seg[1] if isinstance(raw_seg, tuple) and len(raw_seg) > 1 else {}
            labels = info.get("idToLabels", {}) if isinstance(info, dict) else {}
            target = 0
            for key, value in labels.items():
                if sample_prim and sample_prim in str(value):
                    target = int(key)
                    break
            if target:
                mask = (seg == target)
        if mask is None or int(mask.sum()) < 30:
            return False
        try:
            os.makedirs(self.label_dir, exist_ok=True)
            stem = os.path.join(self.label_dir, f"{self.side}_{self.saved:05d}")
            np.save(stem + "_rgb.npy", rgb)
            np.save(stem + "_depth.npy", depth)
            np.save(stem + "_mask.npy", mask)
            self.saved += 1
        except Exception as exc:  # noqa: BLE001 - a capture must never kill the cell
            say(f"[wrist] label save failed: {type(exc).__name__}: {exc}")
            return False
        return True

    # -- measure ------------------------------------------------------ #
    def measure(self, prior_pos, prior_radius: float, colour_model=None):
        """One wrist measurement near `prior_pos`, or None (with a counted reason)."""
        if self.mode == "off":
            return None
        anchor = self._jaw()
        if anchor is None:
            anchor = prior_pos
        if anchor is None:
            return None
        self._last_prior = prior_pos
        self.attempts += 1
        eye = self.aim(None)
        if eye is None:
            return self._reject("no wrist camera")
        self._render()
        depth, rgb, entry = self._frame()
        if depth is None or depth.ndim != 2:
            return self._reject("no depth")
        path = f"/World/WristCamera_{self.side}"
        if self.dump_dir and self.dumps < int(os.environ.get("FRUIT_WRIST_DUMP_MAX", "4")):
            self._dump(rgb, depth)
        model = self._model(depth.shape[:2], path)
        h, w = depth.shape[:2]
        fx, fy, cx, cy = model.intrinsics(h, w)

        # camera-frame prior (for the raster gate) - `backproject` returns world
        _proj = prior_pos if (self.mode == "raster" and prior_pos is not None) else anchor
        p_cam = (np.asarray(_proj, dtype=float) - model.translation) @ model.rotation
        if float(p_cam[2]) >= -0.03:
            return self._reject("prior behind the camera")

        if self.mode == "raster":
            u = float(cx - fx * p_cam[0] / p_cam[2])
            v = float(cy + fy * p_cam[1] / p_cam[2])
            vv, uu = np.mgrid[0:h, 0:w]
            sel = (uu - u) ** 2 + (vv - v) ** 2 <= self.probe_r ** 2
            py, px = np.nonzero(sel)
            if len(px) == 0:
                return self._reject("empty disk")
            pix = np.stack([px, py], axis=1)
            z = depth[py, px].astype(float)
            finite = np.isfinite(z) & (z > 0.03)
            points = model.backproject(depth, pix[finite])
        else:
            #: **The prior is a preference, not a filter.** It is the thing that
            #: can be wrong (P276: 80 mm of coast), so a ball around it would miss
            #: exactly when the wrist is needed. Back-project everything, keep the
            #: loose neighbourhood, then isolate by colour, by the learned mask, or
            #: by connected components.
            py, px = np.mgrid[0:h:self.stride, 0:w:self.stride]
            pix = np.stack([px.ravel(), py.ravel()], axis=1)
            z = depth[pix[:, 1], pix[:, 0]].astype(float)
            finite = np.isfinite(z) & (z > 0.03)
            if int(finite.sum()) < self.min_pixels:
                return self._reject("no valid depth")
            sub = pix[finite]
            points = model.backproject(depth, sub)
            keep = (
                np.linalg.norm(points - np.asarray(anchor, float), axis=1)
                <= self.reach
            )
            keep &= np.linalg.norm(points - eye, axis=1) <= self.range_m
            if int(keep.sum()) < self.min_pixels:
                self.pixels = int(keep.sum())
                return self._reject(f"no points near the prior ({int(keep.sum())})")
            points = points[keep]
            sub = sub[keep]
            if self.mode == "colour" and colour_model is not None and rgb is not None:
                mean, std = colour_model
                cols = rgb[sub[:, 1], sub[:, 0]].astype(float)
                d = np.abs(cols - np.asarray(mean, float)) / np.maximum(
                    np.asarray(std, float), 6.0
                )
                cmask = d.max(axis=1) <= self.colour_tol
                if int(cmask.sum()) >= self.min_pixels:
                    points = points[cmask]
                    sub = sub[cmask]
            elif self.mode == "learned":
                if rgb is None:
                    return self._reject("learned needs rgb")
                m = self._learned_mask(rgb, depth)
                if m is None:
                    return self._reject("no segmenter")
                msub = np.asarray(m)[sub[:, 1], sub[:, 0]].astype(bool)
                points = points[msub]
                sub = sub[msub]
                if len(points) < self.min_pixels:
                    self.pixels = int(len(points))
                    return self._reject(f"mask covered {len(points)} px")
            if self.mode != "learned":
                #: the mask **is** the isolation; a cluster pass on top of it would
                #: only re-introduce the merge the mask removed.
                points = self._cluster_near(points, anchor)
                if points is None:
                    return self._reject("no plausible cluster")
        if len(points) < self.min_pixels:
            self.pixels = int(len(points))
            return self._reject(f"too few points ({len(points)})")
        centre, radius, rms = _fit_sphere(np.asarray(points, dtype=float), trim=2.5)
        if centre is None or not math.isfinite(radius) or radius <= 0.005:
            return self._reject("degenerate fit")
        if rms > self.max_rms:
            self.rms = float(rms)
            return self._reject(f"rms {rms * 1000:.1f} mm")
        if not (0.008 <= radius <= 0.045):
            return self._reject(f"radius {2 * radius * 1000:.0f} mm")
        if len(points) < self.min_pixels_big:
            self.pixels = int(len(points))
            return self._reject(f"small cluster ({len(points)} px)")
        if anchor is not None and float(
            np.linalg.norm(np.asarray(centre) - anchor)
        ) > self.jaw_max:
            return self._reject(
                f"far from the jaw ({float(np.linalg.norm(np.asarray(centre) - anchor)) * 1000:.0f} mm)"
            )
        if prior_radius and prior_radius > 0.010:
            #: the fruit's size is known from the approach (the head measured it);
            #: a cluster that disagrees is not this fruit.
            if abs(2.0 * radius - 2.0 * float(prior_radius)) > self.dia_tol:
                return self._reject(
                    f"diameter {2 * radius * 1000:.0f} vs {2 * float(prior_radius) * 1000:.0f} mm"
                )
        self.accepted += 1
        self.pixels = int(len(points))
        self.rms = float(rms)
        self.last = {
            "position": np.asarray(centre, dtype=float),
            "radius": float(radius),
            "diameter": float(2.0 * radius),
            "rms": float(rms),
            "pixels": int(len(points)),
            "mode": self.mode,
            "eye": np.asarray(eye, dtype=float),
        }
        return self.last

    def summary(self) -> str:
        if self.attempts == 0:
            return f"mode={self.mode} no measurements"
        top = sorted(self.reasons.items(), key=lambda kv: -kv[1])[:3]
        why = "; ".join(f"{k} x{v}" for k, v in top) if top else "none"
        return (
            f"mode={self.mode} attempts={self.attempts} accepted={self.accepted} "
            f"rejected={self.rejected} reasons=[{why}] "
            f"px_med={self.pixels} rms_med={self.rms * 1000:.2f}mm"
        )


def colour_model_from_mask(rgb, mask):
    """`(mean, std)` in RGB for the pixels a head mask selected - or None."""
    if rgb is None or mask is None:
        return None
    m = np.asarray(mask).astype(bool)
    if m.sum() < 20:
        return None
    colours = np.asarray(rgb)[m].astype(float)
    return colours.mean(axis=0), np.maximum(colours.std(axis=0), 6.0)
