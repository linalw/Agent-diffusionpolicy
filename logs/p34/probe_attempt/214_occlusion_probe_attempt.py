"""P34 phase 1: the rendered with/without-output-belt occlusion probe.

    FRUIT_SCENE_PARTS=environment,pedestal,conveyor,output_belts,camera \
      scripts/154_claim_run.sh logs/p34/30_probe_with.log scripts/run.sh scripts/214_occlusion_probe.py
    FRUIT_SCENE_PARTS=environment,pedestal,conveyor,camera \
      scripts/154_claim_run.sh logs/p34/31_probe_without.log scripts/run.sh scripts/214_occlusion_probe.py

One render per run: the head camera's annotators do not refresh a second time in
this build (measured: hiding the belt roots and re-rendering returned a
bit-identical frame, with and without a physics step in between), so the pair is
two runs. The scene is the shipped one **without the robot** (the arm is a
second occluder, measured separately from the recorded demos), with a row of
fruit placed on the main belt at fixed along positions and re-materialised pure
red so the fruit mask is a colour threshold - no dependence on the instance-id
numbering. `--with-belts` / `--without-belts` only tags the output.

The two runs are deterministic (same seed, same explicit positions, fixed
stepping), so the fruit sit at the same poses; `scripts/215_occlusion_report.py`
compares the red area per fruit between the two JSONs and prints the measured
visible fraction against `scripts/212_occlusion_map.py`'s analytic value.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

HEADLESS = os.environ.get("HEADLESS", "1") == "1"

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

simulation_app = SimulationApp({"headless": HEADLESS, "width": 640, "height": 480})

import numpy as np
from PIL import Image
from pxr import UsdShade

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say, to_numpy
from fruit_sorting.fruits import FruitSpawner, _preview_material
from fruit_sorting.scene import SortingScene
from isaacsim.core.rendering_manager import RenderingManager
from isaacsim.core.simulation_manager import SimulationManager
import isaacsim.core.experimental.utils.app as app_utils

DT = 1.0 / 120.0
OUT = os.environ.get("OUT_DIR", "logs/p34")
TAG = os.environ.get("PROBE_TAG", "with")
#: Probe along positions (world Y) and across-belt x. Two x columns, alternating,
#: so neighbours never touch.
PROBES = [
    (0.30, 0.28), (0.38, 0.34), (0.44, 0.24), (0.49, 0.34), (0.54, 0.24),
    (0.59, 0.34), (0.65, 0.24), (0.71, 0.34), (0.77, 0.24),
]


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    cfg = SceneConfig()
    parts = tuple(
        p for p in os.environ.get(
            "FRUIT_SCENE_PARTS",
            "environment,pedestal,conveyor,output_belts,camera",
        ).split(",") if p
    )
    scene = SortingScene(cfg).build(parts=parts)
    scene.start(physics_dt=DT, warmup_steps=60)
    # The pool must be created *after* `start()`: with it created before
    # `play(commit=True)` the bodies read back at the right poses but are never
    # rendered (measured: the fruit's own instance id appears in no pixel).
    spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "5")))
    spawner.create_pool()
    spawner.refresh_rigids()
    spawner.reset()

    samples = list(spawner.samples)[: len(PROBES)]
    red = _preview_material(scene.stage, "/World/Looks/ProbeRed", (1.0, 0.02, 0.02), 0.9)
    for sample, (y, x) in zip(samples, PROBES):
        spawner.respawn(sample, along=y, x=x)
        UsdShade.MaterialBindingAPI.Apply(
            scene.stage.GetPrimAtPath(sample.prim_path)
        ).Bind(red)
    for _ in range(40):
        SimulationManager.step(steps=1)
    app_utils.update_app(steps=0)
    for sample in samples:
        spawner.stop(sample)
    for _ in range(4):
        SimulationManager.step(steps=1)
    app_utils.update_app(steps=0)
    RenderingManager.render()
    app_utils.update_app(steps=0)
    rgb = np.asarray(to_numpy(scene.camera_sensor.get_data("rgb")))[..., :3]
    Image.fromarray(rgb.astype(np.uint8)).save(f"{OUT}/40_{TAG}.png")

    eye = np.array([cfg.head_camera_forward, 0.0, cfg.head_camera_z])
    tgt = np.array(cfg.head_camera_target, float)
    zax = eye - tgt
    zax /= np.linalg.norm(zax)
    xax = np.cross(np.array([0.0, 0.0, 1.0]), zax)
    xax /= np.linalg.norm(xax)
    rot = np.stack([xax, np.cross(zax, xax), zax], axis=1)
    h, w = rgb.shape[:2]
    fx = (w / 2.0) * cfg.camera_focal_length / (cfg.camera_aperture[0] / 2.0)
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0

    def project(p):
        pc = rot.T @ (np.asarray(p, float) - eye)
        return (cx + fx * (pc[0] / -pc[2]), cy - fx * (pc[1] / -pc[2])) if pc[2] < 0 else None

    # The red mask: the probe fruit are the only red objects (the scene is grey).
    r = rgb[..., 0].astype(float)
    g = rgb[..., 1].astype(float)
    b = rgb[..., 2].astype(float)
    redmask = (r > 80.0) & (r > 1.6 * g) & (r > 1.6 * b)
    say(f"[probe] red pixels in the frame: {int(redmask.sum())}")
    rows = []
    print("\n| fruit | y | x | d | red px | bbox px | frame |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for sample in samples:
        p = np.asarray(spawner.position(sample), dtype=float)
        uv = project(p)
        area = -1
        bbox_px = 0
        if uv is not None:
            half = int(12 + 2.2 * fx * float(sample.diameter) / max(np.linalg.norm(p - eye), 0.2))
            u0, u1 = max(0, int(uv[0]) - half), min(w, int(uv[0]) + half + 1)
            v0, v1 = max(0, int(uv[1]) - half), min(h, int(uv[1]) + half + 1)
            area = int(redmask[v0:v1, u0:u1].sum())
            bbox_px = int((u1 - u0) * (v1 - v0))
        rows.append(dict(y=float(p[1]), x=float(p[0]), z=float(p[2]),
                         d=float(sample.diameter), red=area, bbox=bbox_px,
                         category=sample.category, parts=list(parts)))
        print(f"| {sample.category} | {p[1]:+.3f} | {p[0]:.3f} | "
              f"{float(sample.diameter)*1000:.0f} | {area} | {bbox_px} | {TAG} |")
    with open(f"{OUT}/40_probe_{TAG}.json", "w", encoding="utf-8") as fh:
        json.dump(dict(tag=TAG, parts=list(parts), rows=rows,
                       res=[int(h), int(w)], fx=fx), fh, indent=1)
    say(f"[probe] wrote {OUT}/40_probe_{TAG}.json")
    app_utils.pause()
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
