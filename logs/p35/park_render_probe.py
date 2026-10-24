#!/usr/bin/env python3
"""P35 phase 1: the rendered visible fraction of a static fruit proxy per park.

The offline map (`scripts/217_arm_park_map.py`) predicts, from the rendered arm
silhouette + the depth frame, how much of a fruit's disc the parked arm covers.
This probe checks that prediction with the *other* rendered quantity: fruit-sized
spheres placed on the belt at the map's own poses, whose own instance mask gives
the visible pixel count directly. It is the "label dump to confirm" of the plan,
and it is also the only rendered fruit measurement in this phase that does not
suffer the first-call frame lag: the spheres are static and every read is taken
after two identical renders.

    scripts/154_claim_run.sh logs/p35/50_proxy_render.log \
      env HEADLESS=1 FRUIT_CAMERA_RES=240,424 \
      scripts/run.sh logs/p35/park_render_probe.py

Writes `logs/p35/proxy_render.json`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from isaacsim import SimulationApp  # noqa: E402

from fruit_sorting.fdlimit import raise_fd_limit  # noqa: E402

raise_fd_limit()
simulation_app = SimulationApp(
    {"headless": os.environ.get("HEADLESS", "1") == "1", "width": 640, "height": 480}
)

from pxr import Gf, UsdGeom  # noqa: E402
from isaacsim.core.rendering_manager import RenderingManager  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402

from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.common import say  # noqa: E402
from fruit_sorting.control import ArmController  # noqa: E402
from fruit_sorting.scene import SortingScene, _set_color  # noqa: E402

OUT = os.path.join(ROOT, "logs/p35/proxy_render.json")
PARKS = tuple(os.environ.get("PROXY_PARKS", "ready,back,side_deep").split(","))
#: (name, x, y, d) on the belt top. y is the raw belt coordinate; the direct
#: env's `along` subtracts the active arm's jaw y (~0.00 for the right arm at
#: `grasp`), so these read as the map's along within a centimetre.
PROXIES = (
    ("pear", 0.219, 0.399, 0.068),
    ("outer_mid", 0.190, 0.350, 0.058),
    ("outer_edge", 0.230, 0.400, 0.058),
    ("inner", 0.300, 0.400, 0.058),
)


def load_212():
    path = os.path.join(ROOT, "scripts", "212_occlusion_map.py")
    spec = importlib.util.spec_from_file_location("occlusion_map_212", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def seg_read(scene):
    raw = scene.camera_sensor.get_data("instance_id_segmentation")
    if raw is None:
        return None, {}
    try:
        arr = raw[0]
    except Exception:
        return None, {}
    if arr is None or not hasattr(arr, "numpy"):
        return None, {}
    seg = np.asarray(arr.numpy())
    if seg.ndim == 3:
        seg = seg[..., 0]
    info = raw[1] if isinstance(raw, tuple) and len(raw) > 1 else {}
    return seg, info.get("idToLabels", {}) if isinstance(info, dict) else {}


def render(scene, tries: int = 10):
    prev = None
    seg, labels = None, {}
    for _ in range(tries):
        RenderingManager.render()
        seg, labels = seg_read(scene)
        if seg is None or not seg.size:
            prev = None
            continue
        if prev is not None and np.array_equal(seg, prev):
            return seg, labels
        prev = seg
    raise RuntimeError("the segmentation never stabilised")


def main() -> int:
    omap = load_212()
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    belt_top = float(cfg.belt_center[2]) + float(cfg.belt_size[2]) / 2.0
    stage = scene.stage
    for name, x, y, d in PROXIES:
        sphere = UsdGeom.Sphere.Define(stage, f"/World/Proxy_{name}")
        sphere.GetRadiusAttr().Set(float(d) / 2.0)
        xf = UsdGeom.Xformable(sphere)
        xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(Gf.Vec3d(float(x), float(y), belt_top + float(d) / 2.0 + 0.001))
        _set_color(sphere, (0.9, 0.1, 0.1))
    say(f"[proxy] {len(PROXIES)} spheres placed")

    wps = json.load(open(os.path.join(ROOT, "configs/waypoints.json"), encoding="utf-8"))
    parks = json.load(open(os.path.join(ROOT, "configs/arm_parks.json"), encoding="utf-8"))
    sweep = json.load(open(os.path.join(ROOT, "logs/p35/park_sweep.json"), encoding="utf-8"))
    arms = {s: ArmController(scene, s) for s in ("left", "right")}
    for s, a in arms.items():
        a.set_gripper(a.OPEN)
        a.teleport_joints(np.asarray(wps["arms"][s]["ready"], dtype=float))
    arms["right"].teleport_joints(np.asarray(wps["arms"]["right"]["grasp"], dtype=float))
    SimulationManager.step(steps=20)

    cam = dict(eye=[float(cfg.head_camera_forward), 0.0, float(cfg.head_camera_z)],
               target=[float(v) for v in cfg.head_camera_target],
               focal=float(cfg.camera_focal_length),
               aperture=[float(v) for v in cfg.camera_aperture],
               res=[int(v) for v in os.environ.get(
                   "FRUIT_CAMERA_RES", f"{cfg.camera_resolution[0]},{cfg.camera_resolution[1]}"
               ).split(",")])
    out = {"camera": cam, "belt_top": belt_top,
           "proxies": [dict(name=n, x=x, y=y, d=d) for n, x, y, d in PROXIES], "parks": {}}
    # The analytic unoccluded area per proxy: the same window/ray model 212 uses.
    for p in out["proxies"]:
        r = omap.visible_fraction(p["x"], p["y"], p["d"])
        p["aw"] = float(r["area_without"])
        p["belt_vis"] = float(r["vis"])
        p["bbox"] = [float(v) for v in r["bbox"]]
    print("[proxy] " + " ".join(
        f"{p['name']}:x={p['x']} y={p['y']} d={p['d']*1000:.0f} aw={p['aw']:.0f} "
        f"belt={p['belt_vis']:.2f}" for p in out["proxies"]))

    for park in PARKS:
        row = next((r for r in sweep["sides"]["left"] if r["name"] == park), None)
        if row is None:
            print(f"[proxy] {park}: not in the sweep")
            continue
        arms["left"].teleport_joints(np.asarray(row["q"], float), settle=90)
        seg, labels = render(scene)
        res = {}
        for p in out["proxies"]:
            ids = [int(k) for k, v in labels.items() if f"Proxy_{p['name']}" in str(v)]
            px = int(np.isin(seg, ids).sum()) if ids else 0
            vis = px / p["aw"] if p["aw"] > 0 else float("nan")
            res[p["name"]] = dict(px=px, vis=float(vis), ids=ids)
            print(f"[proxy] {park:>10s} {p['name']:>10s} ids={ids} px={px:4d} "
                  f"aw={p['aw']:.0f} visible={vis:.3f}")
        out["parks"][park] = res
    # A label dump once, so the ids above are traceable.
    seg, labels = render(scene)
    out["labels"] = {str(k): str(v) for k, v in sorted(
        labels.items(), key=lambda kv: int(kv[0]))}
    print(f"[proxy] labels: {len(out['labels'])} ids; "
          f"proxy rows: {[v for v in out['labels'].values() if 'Proxy_' in v]}")
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"[proxy] wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
