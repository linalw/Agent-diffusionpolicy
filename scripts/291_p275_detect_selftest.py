#!/usr/bin/env python3
"""P275: execute `FruitPerception.detect_all` on a synthetic frame.

An instrument that is only read by code review is not measured. This stub renders
nothing: it hands `detect_all` a depth image and an instance segmentation built
analytically from three spheres at known centres and radii, so the assertions are
about the **pipeline** (label -> mask -> back-projection -> depth band -> trimmed
fit -> workcell ROI -> calibration bias) rather than about the renderer.

It also pins the property the selector depends on: `detect_all` must **not** touch
the tracked target's filter state (`last_radius`, `last_centre`, `last_estimate`).

Usage: python3 scripts/291_p275_detect_selftest.py [-v]
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from fruit_sorting import perception as P  # noqa: E402

W, H = 160, 120
F = 120.0  # focal length in pixels
CX, CY = W / 2.0, H / 2.0

#: (prim path, centre in the camera frame [m], radius [m], segmentation id)
FRUIT = [
    ("/World/Fruit_00", (0.05, 0.02, 1.20), 0.030, 11),
    ("/World/Fruit_01", (-0.04, -0.03, 1.35), 0.038, 12),
    ("/World/Fruit_02", (0.02, 0.06, 1.60), 0.045, 13),
]
#: a decoy that is labelled but outside the ROI, and one that is not a fruit
DECOY = [("/World/OutputBelt2", (-0.30, 0.55, 1.30), 0.05, 21)]


class FakeCamera:
    """Pinhole: ray -> (t, point on the sphere), and point -> pixel (for building the frame)."""

    width, height = W, H
    meters_per_unit = 1.0

    def intrinsics(self, height, width):
        return (F, F, CX, CY)

    def update_pose(self, scene, path):  # pragma: no cover - not used here
        return None

    def backproject(self, depth, pixels):
        u = pixels[:, 0].astype(float)
        v = pixels[:, 1].astype(float)
        dx = (u - CX) / F
        dy = (v - CY) / F
        dz = np.ones_like(dx)
        z = depth[pixels[:, 1], pixels[:, 0]].astype(float)
        t = z / dz
        return np.stack([t * dx, t * dy, t * dz], axis=1)


def build_frame():
    """A depth image + segmentation whose fruit pixels lie exactly on their spheres."""
    depth = np.full((H, W), 2.5, dtype=np.float32)  # background: far plane
    seg = np.zeros((H, W), dtype=np.int32)
    labels = {"0": "BACKGROUND"}
    for path, centre, radius, ident in FRUIT + DECOY:
        labels[str(ident)] = path
        cx, cy, cz = centre
        uu, vv = np.meshgrid(np.arange(W), np.arange(H))
        dx = (uu - CX) / F
        dy = (vv - CY) / F
        # ray (dx, dy, 1); solve |t d - c|^2 = r^2 for the near root
        dd = dx * dx + dy * dy + 1.0
        b = dx * cx + dy * cy + cz
        c = cx * cx + cy * cy + cz * cz - radius * radius
        disc = b * b - dd * c
        hit = disc > 0
        t = np.full_like(dd, np.nan)
        t[hit] = (b[hit] - np.sqrt(disc[hit])) / dd[hit]
        z = t  # d_z = 1
        order = hit & (np.nan_to_num(np.where(np.isnan(z), np.inf, z), posinf=np.inf)
                       < np.nan_to_num(depth.astype(float), posinf=np.inf))
        depth[order] = z[order].astype(np.float32)
        seg[order] = ident
    return depth, seg, {"idToLabels": labels}


class FakeSensor:
    def __init__(self, depth, seg, info):
        self._depth, self._seg, self._info = depth, seg, info

    def get_data(self, name):
        if name == "distance_to_image_plane":
            return [FakeArray(self._depth)]
        if name == "instance_id_segmentation":
            return (FakeArray(self._seg), self._info)
        if name == "rgb":
            return [FakeArray(np.zeros((H, W, 3), dtype=np.uint8))]
        return None


class FakeArray:
    def __init__(self, a):
        self._a = a

    def numpy(self):
        return self._a


class FakeScene:
    def __init__(self, sensor):
        self.camera_sensor = sensor


class FakeTask:
    _active_session = None

    def _sim_time(self):
        return 1.0


def make_perception(sensor, roi=None):
    obj = object.__new__(P.FruitPerception)
    obj.scene = FakeScene(sensor)
    obj.camera = FakeCamera()
    obj.hz = 30.0
    obj.stride = 1
    obj.min_pixels = 20
    obj.full_pixels = 200
    obj.clip_margin = 2
    obj.trim = 2.5
    obj.shape = "sphere"
    obj.roi = roi
    obj.bias = {"head": np.zeros(3), "wrist": np.zeros(3)}
    obj.failures = 0
    obj.rejected = 0
    obj.renders = 0
    obj.frames = 0
    obj.fixed_fits = 0
    obj.last_error = ""
    # the tracked target's state - must survive a `detect_all` untouched
    obj.last_radius = 0.0123
    obj.last_centre = np.array([9.0, 9.0, 9.0])
    obj.last_estimate = {"sentinel": True}
    obj._render = lambda task: None
    return obj


def main(argv):
    verbose = "-v" in argv
    depth, seg, info = build_frame()
    sensor = FakeSensor(depth, seg, info)

    # 1. no ROI: every labelled fruit is detected, and the decoy is not a fruit
    obj = make_perception(sensor)
    dets = P.FruitPerception.detect_all(obj, FakeTask())
    assert set(dets) == {p for p, *_ in FRUIT}, sorted(dets)
    assert DECOY[0][0] not in dets, "a non-fruit label must not become a candidate"

    # 2. the fit recovers centre and radius
    worst_c = worst_r = 0.0
    for path, centre, radius, _ident in FRUIT:
        got = dets[path]
        dc = float(np.linalg.norm(got["position"] - np.asarray(centre, float)))
        dr = abs(got["diameter"] / 2.0 - radius)
        worst_c = max(worst_c, dc)
        worst_r = max(worst_r, dr)
        print(f"  {path}: centre err {dc * 1000:.2f} mm, radius err {dr * 1000:.2f} mm, "
              f"{got['pixels']} px")
    assert worst_c < 0.002, f"centre error {worst_c * 1000:.2f} mm"
    assert worst_r < 0.002, f"radius error {worst_r * 1000:.2f} mm"

    # 3. the workcell ROI filters a body that is not in the cell
    roi = (-0.20, 0.20, -0.20, 0.20, 1.00, 1.80)
    obj2 = make_perception(sensor, roi=roi)
    dets2 = P.FruitPerception.detect_all(obj2, FakeTask())
    assert set(dets2) == {p for p, *_ in FRUIT}, sorted(dets2)
    assert not any(p == DECOY[0][0] for p in dets2)

    # 3b. an ROI that excludes everything returns an empty dict, not a raise
    obj3 = make_perception(sensor, roi=(5.0, 6.0, 5.0, 6.0, 5.0, 6.0))
    assert P.FruitPerception.detect_all(obj3, FakeTask()) == {}

    # 4. the tracked target's filter state is untouched
    for o in (obj, obj2, obj3):
        assert o.last_radius == 0.0123
        assert np.allclose(o.last_centre, [9.0, 9.0, 9.0])
        assert o.last_estimate == {"sentinel": True}

    # 5. the calibration bias is applied to the returned centre
    obj4 = make_perception(sensor)
    obj4.bias = {"head": np.array([0.010, -0.005, 0.002]), "wrist": np.zeros(3)}
    dets4 = P.FruitPerception.detect_all(obj4, FakeTask())
    # `measure` subtracts the mount bias (it is an offset to remove), and
    # `detect_all` uses the same convention - the sign is part of the contract.
    shift = dets4[FRUIT[0][0]]["position"] - dets[FRUIT[0][0]]["position"]
    assert np.allclose(shift, [-0.010, 0.005, -0.002], atol=1e-9), shift

    # 6. an empty frame (no depth) is an empty dict and one counted failure
    class DeadSensor(FakeSensor):
        def get_data(self, name):
            return None

    obj5 = make_perception(DeadSensor(depth, seg, info))
    assert P.FruitPerception.detect_all(obj5, FakeTask()) == {}
    assert obj5.failures == 1

    if verbose:
        print("  detections:", {k: v["diameter"] for k, v in dets.items()})
    print("detect_all ok (labels -> mask -> fit -> ROI -> bias; filter state untouched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
