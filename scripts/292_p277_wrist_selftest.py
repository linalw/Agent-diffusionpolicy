#!/usr/bin/env python3
"""P277: exercise `wrist.WristRig` on a synthetic wrist frame (no simulator).

The design claim to test is small and specific: **the prior must be a preference,
not a filter.** P276 measured the prior going 80 mm wrong (the coast cap), so a
gate *around* it would miss the fruit exactly when the wrist is needed. This stub
renders a sphere 80 mm away from the prior, adds a flat "finger" patch, and checks
that

* `prior` and `colour` find the sphere (cluster nearest the prior, plausible size);
* `raster` - P214's image-space disk, kept as the control - does **not**, which is
  the 44-62 mm bench error reproduced offline;
* `off` does nothing, and the instrument counts a rejection reason.

Usage: python3 scripts/292_p277_wrist_selftest.py [-v]
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from fruit_sorting import wrist as W  # noqa: E402

W_PX, H_PX = 320, 240
FOCAL, APX, APY = 0.035, 0.048, 0.036
#: the jaw sits **on the fruit** (that is where a wrist camera looks), and the
#: camera is 6 cm behind it along the approach axis - the shipped `_wrist_back`.
JAW = np.array([0.000, 0.000, 1.180])
BACK = 0.06
EYE = JAW + np.array([0.0, 0.0, BACK])

#: the fruit: 6 cm diameter, 12 cm in front of the eye, 8 cm off the prior's y
SPHERE_C = np.array([0.000, 0.000, 1.180])
SPHERE_R = 0.030
#: the "prior" the tracker would hand in: **80 mm away** (a coasted estimate) -
#: after P277's first cell the aim and the gate no longer read it at all
PRIOR = np.array([0.000, 0.080, 1.180])
#: a flat patch (a finger plate) closer to the camera, a different colour
PLANE_Z = 0.060
PLANE_X = (0.020, 0.045)
PLANE_Y = (-0.010, 0.015)


def fx_fy():
    fx = W_PX * FOCAL / APX
    fy = H_PX * FOCAL / APY
    return fx, fy, (W_PX - 1) * 0.5, (H_PX - 1) * 0.5


def render(sphere: bool = True):
    """Depth in the camera's own convention (`backproject`: z along -Z)."""
    fx, fy, cx, cy = fx_fy()
    vv, uu = np.mgrid[0:H_PX, 0:W_PX]
    dx = (uu - cx) / fx
    dy = -(vv - cy) / fy
    depth = np.full((H_PX, W_PX), 1.0, dtype=np.float32)  # background: far
    rgb = np.zeros((H_PX, W_PX, 3), dtype=np.uint8)
    rgb[..., :] = 30  # background colour

    # --- sphere -------------------------------------------------------- #
    if not sphere:
        c = None
    else:
        c = SPHERE_C - EYE
    if c is not None:
        a = dx * dx + dy * dy + 1.0
        b = dx * c[0] + dy * c[1] - c[2]
        cc = float(c @ c) - SPHERE_R ** 2
        disc = b * b - a * cc
        hit = disc > 0
        z = np.full(dx.shape, np.nan)
        z[hit] = (b[hit] - np.sqrt(disc[hit])) / a[hit]
        order = hit & (z > 0) & (z < depth)
        depth[order] = z[order].astype(np.float32)
        rgb[order] = (210, 120, 40)  # an orange-ish fruit

    # --- finger plate (flat, close, grey) ------------------------------ #
    pz = PLANE_Z
    xs = dx * pz
    ys = dy * pz
    plate = (
        (xs >= PLANE_X[0]) & (xs <= PLANE_X[1])
        & (ys >= PLANE_Y[0]) & (ys <= PLANE_Y[1])
        & (pz < depth)
    )
    depth[plate] = pz
    rgb[plate] = (150, 150, 150)
    return depth, rgb


class FakeArray:
    def __init__(self, a):
        self._a = a

    def numpy(self):
        return self._a


class FakeSensor:
    def __init__(self, depth, rgb):
        self.depth, self.rgb = depth, rgb

    def get_data(self, name):
        if name == "distance_to_image_plane":
            return [FakeArray(self.depth)]
        if name == "rgb":
            return [FakeArray(self.rgb)]
        return None


class StubModel:
    """`CameraModel` with the pose handed in by the scene's aim."""

    def __init__(self, width, height, focal, ax, ay, rotation, translation):
        self.width, self.height = int(width), int(height)
        self.focal, self.aperture_x, self.aperture_y = focal, ax, ay
        self.rotation = np.eye(3)
        self.translation = np.zeros(3)
        self.meters_per_unit = 1.0

    def update_pose(self, scene, path):
        self.translation = np.asarray(scene.eye, dtype=float)

    def intrinsics(self, height, width):
        fx = width * self.focal / self.aperture_x
        fy = height * self.focal / self.aperture_y
        return fx, fy, (width - 1) * 0.5, (height - 1) * 0.5

    def backproject(self, depth, pixels):
        u = pixels[:, 0].astype(float)
        v = pixels[:, 1].astype(float)
        fx, fy, cx, cy = self.intrinsics(depth.shape[0], depth.shape[1])
        z = depth[pixels[:, 1], pixels[:, 0]].astype(float)
        cam = np.stack([(u - cx) / fx * z, -(v - cy) / fy * z, -z], axis=1)
        return cam @ self.rotation.T + self.translation


class FakeScene:
    def __init__(self, sensor):
        self.wrist_cameras = {"right": (None, sensor)}
        self.eye = EYE
        self.aims = []

    def set_wrist_pose(self, side, position, target):
        self.eye = np.asarray(position, dtype=float)
        self.aims.append((side, np.asarray(position, float), np.asarray(target, float)))


class FakeArm:
    def jaw_centre(self):
        return JAW

    def approach_axis(self):
        #: the **measured** value on this arm: +z, i.e. "up", not "down". The sign
        #: is the whole P277 geometry lesson - it put the first camera under the
        #: hand looking at the back of the fingers.
        return np.array([0.0, 0.0, 1.0])

    def tcp_pose(self):
        return JAW, np.array([1.0, 0.0, 0.0, 0.0])


class FakeTask:
    _wrist_back = BACK
    _wrist_side = 0.0

    def __init__(self):
        self.arms = {"right": FakeArm()}

    @staticmethod
    def _quat_matrix(quat):
        return np.eye(3)


def rig(mode: str, sphere: bool = True) -> W.WristRig:
    depth, rgb = render(sphere=sphere)
    scene = FakeScene(FakeSensor(depth, rgb))
    r = W.WristRig(scene, FakeTask(), "right", mode,
                   spec=((W_PX, H_PX), FOCAL, APX, APY, 30.0),
                   render=lambda: None)   # the render is the caller's job
    return r


def main(argv):
    verbose = "-v" in argv
    W.CameraModel = StubModel  # the only substitution
    depth, rgb = render()

    # 0. the frame really holds a 6 cm sphere, with the prior 8 cm off
    fg = depth < 0.5
    assert fg.sum() > 200, int(fg.sum())

    # 1. `prior`: a preference, not a filter - the sphere is found anyway
    r = rig("prior")
    det = r.measure(PRIOR, SPHERE_R, colour_model=None)
    assert det is not None, f"prior mode failed: {r.summary()}"
    err = float(np.linalg.norm(det["position"] - SPHERE_C))
    dia = det["diameter"]
    print(f"  prior : err {err * 1000:.1f} mm, dia {dia * 100:.1f} cm, "
          f"{det['pixels']} px, rms {det['rms'] * 1000:.2f} mm")
    assert err < 0.004, f"prior centre error {err * 1000:.1f} mm"
    assert abs(dia - 2 * SPHERE_R) < 0.008, dia

    # 2. `colour`: the same, with the fruit's colour model (the plate is grey)
    r2 = rig("colour")
    mean = np.array([210.0, 120.0, 40.0])
    det2 = r2.measure(PRIOR, SPHERE_R, colour_model=(mean, np.full(3, 6.0)))
    assert det2 is not None, f"colour mode failed: {r2.summary()}"
    err2 = float(np.linalg.norm(det2["position"] - SPHERE_C))
    print(f"  colour: err {err2 * 1000:.1f} mm, {det2['pixels']} px")
    assert err2 < 0.004, err2

    # 3. `raster` (P214's control): it still projects the **prior**, so an 8 cm-off
    #    prior lands the disk elsewhere - the reason the control is a control
    r3 = rig("raster")
    det3 = r3.measure(PRIOR, SPHERE_R, colour_model=None)
    print(f"  raster: {'rejected - ' + str(r3.reasons) if det3 is None else 'FOUND ' + str(det3['position'])}")
    assert det3 is None, "the raster control was expected to miss (that is P214's error)"

    # 4. `off`: no measurement, no camera aim at all
    r4 = rig("off")
    assert r4.measure(PRIOR, SPHERE_R) is None
    assert r4.attempts == 0
    assert not r4.scene.aims

    # 5. P277's correction, as a test: a prior **40 cm** off still finds the fruit,
    #    because the aim and the gate are anchored on the jaw (the robot's own
    #    state), not on the estimate that goes wrong.
    r5 = rig("prior")
    far = np.array([0.0, 0.40, 1.180])
    det5 = r5.measure(far, SPHERE_R)
    assert det5 is not None, f"a far prior must not blind the wrist: {r5.summary()}"
    err5 = float(np.linalg.norm(det5["position"] - SPHERE_C))
    print(f"  prior 40 cm off: err {err5 * 1000:.1f} mm (the prior does not steer)")

    # 5b. a frame with the jaw but no fruit is a counted rejection, not a raise
    r6 = rig("prior", sphere=False)
    assert r6.measure(PRIOR, SPHERE_R) is None
    assert r6.rejected == 1 and r6.reasons, r6.summary()

    # 6. the summary is legible
    print(f"  summary: {r.summary()}")
    assert "mode=prior" in r.summary() and "accepted=1" in r.summary()

    # 7. the paper preset actually is the common wrist spec
    os.environ["FRUIT_WRIST_PRESET"] = "paper"
    res, focal, ax, ay, hz = W.wrist_spec_from_env()
    hfov = 2.0 * np.degrees(np.arctan(ax / (2.0 * focal)))
    print(f"  paper preset: {res[1]}x{res[0]} (WxH), {hz:.0f} Hz, HFOV {hfov:.1f} deg")
    assert tuple(res) == (480, 640) and abs(hfov - 68.9) < 1.0, (res, hfov)
    os.environ.pop("FRUIT_WRIST_PRESET")

    if verbose:
        print("  detections:", det)
    print("wrist ok (prior is a preference; raster misses; colour and off behave)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
