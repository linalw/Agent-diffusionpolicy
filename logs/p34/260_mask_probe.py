#!/usr/bin/env python3
"""P34 phase 2 follow-up: *which* instance hides the target in the direct env's
frames - the arm-occlusion attribution (read-only, one episode).

    scripts/154_claim_run.sh logs/p34/260_mask_probe.log \
      env HEADLESS=1 FRUIT_CAMERA_RES=240,424 ... \
      scripts/run.sh logs/p34/260_mask_probe.py

The A/B's `[align]` row measures the *target mask* at the first model call and
in the fire zone. A zero mask there can be (a) a real occluder - the arm or a
fruit ahead of the target - or (b) the env's target-id lookup losing the fruit.
This probe separates them: at the reset and every observation tick it reads the
instance segmentation the env's `_observe` just used and ranks the instance ids
*inside the target's projected bbox* (the camera model of
`scripts/212_occlusion_map.py`, validated on the demo masks). The winner's
label is the occluder (an arm-link prim path vs another fruit's).

Prints one `[probe]` line per observation tick: the target's along, the
analytic belt-only visibility (212), the env's own target mask pixels, and the
top-3 instances inside the projected bbox with their pixel counts and labels.
Every read is after the env's `_observe`, so it is the frame the policy saw.

Scenario: the P34 A/B's (`FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1`,
balanced mix, arrival trigger + ACQ); `FRUIT_RESET_ALIGN` from the environment
(0 = control, 1 = aligned) so both cases can be probed.
"""

from __future__ import annotations

import importlib.util
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

# The app must exist before the env's Isaac imports (same order as
# `scripts/110_rl_rollout.py`), and the fd limit before the first camera read.
from isaacsim import SimulationApp  # noqa: E402

from fruit_sorting.fdlimit import raise_fd_limit  # noqa: E402

raise_fd_limit()
simulation_app = SimulationApp(
    {"headless": os.environ.get("HEADLESS", "1") == "1",
     "width": 640, "height": 480}
)

from fruit_sorting.rl_env import SortingRLEnv  # noqa: E402


def load_map():
    path = os.path.join(ROOT, "scripts", "212_occlusion_map.py")
    spec = importlib.util.spec_from_file_location("occlusion_map_212", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def seg_read(scene):
    raw = scene.camera_sensor.get_data("instance_id_segmentation")
    if raw is None:
        return None, {}
    seg = np.asarray(raw[0].numpy())
    if seg.ndim == 3:
        seg = seg[..., 0]
    info = raw[1] if isinstance(raw, tuple) and len(raw) > 1 else {}
    labels = info.get("idToLabels", {}) if isinstance(info, dict) else {}
    return seg, labels


def label_of(labels: dict, ident: int) -> str:
    value = labels.get(str(ident), labels.get(ident, "?"))
    return str(value)[:56]


def main() -> int:
    omap = load_map()
    env = SortingRLEnv(
        presentation="direct",
        seed=77,
        checkpoint="checkpoints/moe_v13s/policy_best.pt",
        execute_steps=4,
        ddim_steps=16,
        verbose=False,
    )
    env.reset(77)
    sample = env._sample
    print(f"[probe] reset knob={int(env._reset_align)} step={env._step} "
          f"prim={getattr(sample, 'prim_path', None)} "
          f"fruit={np.asarray(env.spawner.position(sample), dtype=float)}")
    for it in range(400):
        if env._done:
            break
        # `sample_chunk` renders the frame at this control step (if due) and
        # then samples; the mask read after it is the frame the call saw.
        chunk = env.sample_chunk()
        mask = env._last_mask
        mask_px = -1 if mask is None else int(np.asarray(mask).sum())
        fruit = np.asarray(env.spawner.position(sample), dtype=float)
        along = float(fruit[1]) - float(env._expert_jaw_y)
        vis = omap.visible_fraction(float(fruit[0]), float(fruit[1]),
                                    float(sample.diameter))
        top = "-"
        seg, labels = seg_read(env.scene)
        bbox = vis.get("bbox")
        if seg is not None and bbox is not None and bbox[0] == bbox[0]:
            r0, r1 = int(max(0, bbox[2])), int(min(seg.shape[0], bbox[3] + 1))
            c0, c1 = int(max(0, bbox[0])), int(min(seg.shape[1], bbox[1] + 1))
            if r1 > r0 and c1 > c0:
                ids, counts = np.unique(seg[r0:r1, c0:c1], return_counts=True)
                order = np.argsort(-counts)[:3]
                top = " | ".join(
                    f"{int(ids[i])}:{int(counts[i])}px:{label_of(labels, int(ids[i]))}"
                    for i in order
                )
        print(f"[probe] it={it:3d} step={env._step:4d} calls={int(env._infer_calls)} "
              f"along={along:+.3f} d={float(sample.diameter)*1000:.0f}mm "
              f"vis212={float(vis.get('vis', float('nan'))):.2f} "
              f"target_px={mask_px:4d} bbox_ids={top}")
        if env._step >= 8 and along < 0.10:
            break
        env.act(chunk, execute_steps=4)
    print("[probe] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
