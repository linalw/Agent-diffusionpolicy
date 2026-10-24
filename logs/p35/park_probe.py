#!/usr/bin/env python3
"""P35 phase 1: the inactive arm's park sweep - link poses + rendered silhouettes.

One process, two passes, both read-only:

**Pass A (the shipped head camera).** For `ready` plus a one-joint sweep on each
of the seven joints (three magnitudes, both signs, clipped to the limits) and a
few multi-joint folds, per side: teleport the inactive arm, settle, then record

  * `link_pose` of every `openarm_<side>_link1..7` + `..._ee_tcp` + both fingers
    for **both** arms (the parked one and the active one at its `grasp` pose,
    which is where the direct env's first model call has it);
  * the rendered `instance_id_segmentation` + `distance_to_image_plane`, reduced
    to the inactive arm's boolean silhouette, the active arm's, and the depth
    frame (`uint8`/`float16` under `park_masks.npz`);
  * the joint hold (`|q_measured - q_commanded|max` after the settle), the
    lowest link origin, and whether any link origin is inside the belt's slab
    footprint - so a pose the solver rejects is visible, not assumed.

A read is accepted only when two consecutive renders are identical
(segmentation **and** depth): this build's `instance_id_segmentation` returns
`None` until primed and can be one render behind, which is exactly the
stale-frame trap P34-B hit (`logs/p34/B_READ.md` section 3).

**Pass B (the candidate cameras).** The same shortlisted parks rendered from
`FRUIT_CAMERAS` (default: the shipped pose plus the six `212 --levers` camera
moves), each as its own `RtxCamera` + `CameraSensor` at the shipped focal,
aperture and resolution. The shipped pose is rendered through a *new* camera too:
its mask must equal the head camera's, which is the check that a second camera
reproduces the shipped view before any other pose is priced. (`scripts/
217_arm_park_map.py --cameras` reads these; the analytic capsule model it can
also compute was measured to be optimistic by up to +1.00 on the left arm's
silhouette and is not used for the decision.)

    scripts/154_claim_run.sh logs/p35/10_park_sweep.log \
      env HEADLESS=1 FRUIT_CAMERA_RES=240,424 \
      scripts/run.sh logs/p35/park_probe.py

Writes `logs/p35/park_sweep.json` + `logs/p35/park_masks.npz`.
"""

from __future__ import annotations

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

from isaacsim.core.rendering_manager import RenderingManager  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402

from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.common import look_at_quat  # noqa: E402
from fruit_sorting.control import ArmController  # noqa: E402
from fruit_sorting.scene import SortingScene  # noqa: E402

OUT_JSON = os.path.join(ROOT, "logs/p35/park_sweep.json")
OUT_NPZ = os.path.join(ROOT, "logs/p35/park_masks.npz")
LINKS = [f"link{i}" for i in range(1, 8)] + ["ee_tcp", "left_finger", "right_finger",
         "hand"]
BODY_LINK = "openarm_body_link"
SETTLE = int(os.environ.get("PROBE_SETTLE", "90"))
MAGS = tuple(float(v) for v in os.environ.get("PROBE_MAGS", "0.25,0.5,0.8").split(","))
SIDES = tuple(s for s in os.environ.get("PROBE_SIDES", "left,right").split(",") if s)
DO_CAMERAS = os.environ.get("PROBE_CAMERAS_PASS", "1") == "1"
CAM_PARKS = tuple(
    p for p in os.environ.get(
        "PROBE_CAM_PARKS", "ready,j2+025,j2+050,j2+080,j1+025,j2-080"
    ).split(",") if p
)
#: The camera alternatives: the shipped pose plus the `212 --levers` set.
CAMS = {
    "shipped": {},
    "z180": dict(eye=[0.05, 0.0, 1.80]),
    "z220": dict(eye=[0.05, 0.0, 2.20]),
    "ym025": dict(eye=[0.05, -0.25, 2.00]),
    "yp025": dict(eye=[0.05, 0.25, 2.00]),
    "xm010": dict(eye=[-0.10, 0.0, 2.00]),
    "xp012": dict(eye=[0.17, 0.0, 2.00]),
}


def label_of(labels: dict, ident: int) -> str:
    value = labels.get(str(ident), labels.get(ident, "?"))
    return str(value)[:72]


def seg_read(sensor):
    raw = sensor.get_data("instance_id_segmentation")
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
    labels = info.get("idToLabels", {}) if isinstance(info, dict) else {}
    return seg, labels


def depth_read(sensor) -> np.ndarray:
    from fruit_sorting.common import to_numpy

    raw = sensor.get_data("distance_to_image_plane")
    if raw is None:
        return np.full((1, 1), np.nan, dtype=np.float32)
    depth = np.asarray(to_numpy(raw))
    if depth.ndim == 3:
        depth = depth[..., 0]
    return depth.astype(np.float32)


def render(sensor, tries: int = 10):
    """Render until two consecutive passes agree, then return that frame.

    Two things make a single read insufficient on this build: the
    `instance_id_segmentation` annotator returns `(None, ...)` until it is
    primed, and the annotated frame can be one render behind, so a read taken
    while the arm is still settling describes the *previous* pose. Requiring two
    consecutive identical segmentation+depth frames makes "the mask belongs to
    the pose whose link origins we also read" a check, not an assumption.
    """
    prev = None
    seg, labels, depth = None, {}, None
    for _ in range(tries):
        RenderingManager.render()
        seg, labels = seg_read(sensor)
        depth = depth_read(sensor)
        if seg is None or not seg.size:
            prev = None
            continue
        if prev is not None:
            pseg, pdepth = prev
            if np.array_equal(seg, pseg) and depth.shape == pdepth.shape and \
                    np.allclose(depth, pdepth, atol=1e-3, equal_nan=True):
                return seg, labels, depth
        prev = (seg, depth)
    raise RuntimeError("the annotated frame never stabilised (segmentation+depth)")


def link_rows(scene, side: str) -> dict:
    out = {}
    for name in LINKS:
        pose, quat = scene.link_pose(f"openarm_{side}_{name}")
        out[name] = [float(v) for v in np.asarray(pose, float)]
        out[name + "_q"] = [float(v) for v in np.asarray(quat, float)]
    return out


def candidates(side: str, arm: ArmController, ready: np.ndarray) -> list[dict]:
    lo = np.asarray(arm.arm_lo, float)
    hi = np.asarray(arm.arm_hi, float)
    out = [dict(name="ready", q=[float(v) for v in ready])]
    for j in range(7):
        for mag in MAGS:
            for sign in (1.0, -1.0):
                q = ready.copy()
                q[j] = float(np.clip(q[j] + sign * mag, lo[j], hi[j]))
                out.append(dict(name=f"j{j + 1}{'+' if sign > 0 else '-'}{int(round(mag * 100)):03d}",
                                q=[float(v) for v in q]))
    # The multi-joint folds: the "tuck the arm at the side" shapes a human park
    # would take, plus a scaled ladder of the deepest one so the cost/benefit
    # curve of the fold is measured, not extrapolated. Deltas are joint-indexed
    # (1..7) and clipped to the limits by the same code as the sweep.
    folds = {
        "side": {1: 0.6, 2: -0.5, 4: 0.4},
        "side_deep": {1: 0.9, 2: -0.8, 4: 0.7, 6: -0.4},
        "back": {1: -0.5, 2: -0.6, 4: -0.5},
        "low": {2: -0.7, 4: 0.6, 5: 0.5},
        "high": {2: 0.6, 4: 0.5},
        "fold_hi": {1: 0.7, 2: -0.7, 4: 0.55, 5: 0.3},
    }
    deep = folds["side_deep"]
    for frac in (0.40, 0.55, 0.70, 0.85):
        folds[f"fold_{int(round(frac * 100)):02d}"] = {j: d * frac for j, d in deep.items()}
    for name, deltas in folds.items():
        q = ready.copy()
        for j, d in deltas.items():
            q[j - 1] = float(np.clip(q[j - 1] + d, lo[j - 1], hi[j - 1]))
        out.append(dict(name=name, q=[float(v) for v in q]))
    return out


def add_cameras(scene, cam, base_res, names):
    """One extra RtxCamera + CameraSensor per candidate camera pose."""
    from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera

    out = {}
    for name in names:
        c = dict(cam)
        c.update(CAMS[name])
        cam_obj = RtxCamera(f"/World/P35Cam_{name}", tick_rate=30.0,
                            positions=[tuple(c["eye"])],
                            orientations=[look_at_quat(tuple(c["eye"]), tuple(c["target"]))])
        cam_obj.camera.set_focal_lengths(float(c["focal"]))
        cam_obj.camera.set_apertures(tuple(c["aperture"]))
        cam_obj.camera.set_focus_distances(1.0)
        cam_obj.camera.set_clipping_ranges(0.01, 50.0)
        sensor = CameraSensor(cam_obj, resolution=tuple(base_res),
                              annotators=["rgb", "distance_to_image_plane",
                                          "instance_id_segmentation"])
        out[name] = dict(sensor=sensor, eye=list(map(float, c["eye"])),
                         target=list(map(float, c["target"])), focal=float(c["focal"]),
                         aperture=list(map(float, c["aperture"])), res=list(base_res))
        print(f"[probe] camera {name}: eye={c['eye']} target={c['target']}")
    for _ in range(3):
        RenderingManager.render()
        for name, spec in out.items():
            seg_read(spec["sensor"])
    return out


def side_masks(seg, labels, side):
    mask = np.zeros(seg.shape, dtype=bool)
    counts = {}
    for ident in np.unique(seg):
        lab = label_of(labels, int(ident))
        if f"openarm_{side}_" in lab:
            sel = seg == ident
            mask |= sel
            counts[lab] = int(sel.sum())
    return mask, counts


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    belt_top = float(cfg.belt_center[2]) + float(cfg.belt_size[2]) / 2.0
    wps = json.load(open(os.path.join(ROOT, "configs/waypoints.json"), encoding="utf-8"))
    arms = {s: ArmController(scene, s) for s in ("left", "right")}
    for s, a in arms.items():
        a.set_gripper(a.OPEN)
        a.teleport_joints(np.asarray(wps["arms"][s]["ready"], dtype=float))
    SimulationManager.step(steps=20)

    cam = dict(
        eye=[float(cfg.head_camera_forward), 0.0, float(cfg.head_camera_z)],
        target=[float(v) for v in cfg.head_camera_target],
        focal=float(cfg.camera_focal_length),
        aperture=[float(v) for v in cfg.camera_aperture],
        res=[int(v) for v in os.environ.get(
            "FRUIT_CAMERA_RES", f"{cfg.camera_resolution[0]},{cfg.camera_resolution[1]}"
        ).split(",")],
    )
    print(f"[probe] head camera {cam}")

    out = dict(camera=cam, belt_top=belt_top,
               belt_x=[0.11, 0.57], belt_y=[-0.80, 0.80], settle=SETTLE,
               sides={}, cameras={})
    masks = {}
    for side in SIDES:
        other = "right" if side == "left" else "left"
        ready = np.asarray(wps["arms"][side]["ready"], dtype=float)
        arm = arms[side]
        # The active arm sits where the direct env's first model call has it.
        arms[other].teleport_joints(np.asarray(wps["arms"][other]["grasp"], dtype=float))
        rows = []
        for cand in candidates(side, arm, ready):
            q = np.asarray(cand["q"], float)
            arm.teleport_joints(q, settle=SETTLE)
            qm = np.asarray(arm.joint_positions(), float)
            seg, labels, depth = render(scene.camera_sensor)
            mask, counts = side_masks(seg, labels, side)
            mask_other, _ = side_masks(seg, labels, other)
            poses = link_rows(scene, side)
            poses_other = link_rows(scene, other)
            zmin = min(poses[f"{n}"][2] for n in LINKS[:8])
            inbelt = []
            for n in LINKS[:8]:
                p = poses[n]
                if (belt_top - 0.06 <= p[2] <= belt_top + 0.02
                        and 0.11 <= p[0] <= 0.57 and -0.80 <= p[1] <= 0.80):
                    inbelt.append(n)
            # Parked-arm clearance to the active arm: the smallest link-origin
            # gap between the two chains (the build has enabledSelfCollisions=0,
            # so nothing else would report an overlap).
            a_pts = np.array([poses[n] for n in LINKS[:8]], float)
            b_pts = np.array([poses_other[n] for n in LINKS[:8]], float)
            dmin = float(np.min(np.linalg.norm(a_pts[:, None, :] - b_pts[None, :, :], axis=-1)))
            # The torso is its own link (`openarm_body_link`): with the two arms'
            # self-collisions disabled, a fold that crosses the body would be
            # silent in the simulator, so it is measured here.
            body = np.asarray(scene.link_pose(BODY_LINK)[0], float)
            body_gap = float(np.min(np.linalg.norm(a_pts - body[None, :], axis=-1)))
            row = dict(name=cand["name"], q=[float(v) for v in q],
                       q_measured=[float(v) for v in qm],
                       hold=float(np.max(np.abs(qm - q))),
                       poses=poses, poses_other=poses_other,
                       arm_px=int(mask.sum()), active_px=int(mask_other.sum()),
                       link_px=counts,
                       zmin=float(zmin), in_belt_footprint=inbelt,
                       other_link_gap=dmin, body=[float(v) for v in body],
                       body_gap=body_gap,
                       jaw=[float(v) for v in np.asarray(arm.jaw_centre(), float)])
            rows.append(row)
            masks[f"{side}:{cand['name']}"] = mask
            masks[f"{side}:{cand['name']}:active"] = mask_other
            masks[f"{side}:{cand['name']}:depth"] = depth.astype(np.float16)
            print(f"[probe] {side} {cand['name']:>10s} arm_px={row['arm_px']:5d} "
                  f"hold={row['hold']:.4f} zmin={row['zmin']:.3f} "
                  f"gap={row['other_link_gap']:.3f} body={row['body_gap']:.3f} "
                  f"jaw={np.round(row['jaw'], 3).tolist()}")
        out["sides"][side] = rows
        for s2, a2 in arms.items():
            a2.teleport_joints(np.asarray(wps["arms"][s2]["ready"], dtype=float))
        SimulationManager.step(steps=20)

    if DO_CAMERAS:
        cams = add_cameras(scene, cam, cam["res"], list(CAMS))
        out["cameras"] = {name: {k: v for k, v in spec.items() if k != "sensor"}
                          for name, spec in cams.items()}
        by_name = {r["name"]: r for r in out["sides"].get("left", [])}
        by_name_r = {r["name"]: r for r in out["sides"].get("right", [])}
        for side in SIDES:
            other = "right" if side == "left" else "left"
            src = by_name if side == "left" else by_name_r
            for park in CAM_PARKS:
                if park not in src:
                    continue
                arms[side].teleport_joints(np.asarray(src[park]["q"], float), settle=SETTLE)
                arms[other].teleport_joints(
                    np.asarray(wps["arms"][other]["grasp"], dtype=float), settle=SETTLE)
                for cname, spec in cams.items():
                    seg, labels, depth = render(spec["sensor"])
                    mask, counts = side_masks(seg, labels, side)
                    mask_other, _ = side_masks(seg, labels, other)
                    key = f"cam:{side}:{park}:{cname}"
                    masks[key] = mask
                    masks[key + ":active"] = mask_other
                    masks[key + ":depth"] = depth.astype(np.float16)
                    out["cameras_rows"] = out.get("cameras_rows", [])
                    print(f"[probe] cam {side} {park} {cname} arm_px={int(mask.sum())}")
        for s2, a2 in arms.items():
            a2.teleport_joints(np.asarray(wps["arms"][s2]["ready"], dtype=float))
        SimulationManager.step(steps=20)

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    np.savez_compressed(OUT_NPZ,
                        shape=np.asarray(next(iter(masks.values())).shape),
                        **{k.replace(":", "__"): v for k, v in masks.items()})
    print(f"[probe] wrote {OUT_JSON} + {OUT_NPZ} ({len(masks)} arrays)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
