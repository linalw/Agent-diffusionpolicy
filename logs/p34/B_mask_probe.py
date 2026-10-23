#!/usr/bin/env python3
"""P34-B: the direct reset's first-call pose + rendered-mask probe.

One episode, a handful of model calls, read-only. The A/B's `[align]` row
measures the *along* and the target-mask pixels; this probe adds the missing
half - **the arm's pose** (the reset's joint vector and the first call's) and
**which instance owns the target's projected bbox** - so the reset's
presentation can be compared with the training store's frame-0 pose.

    scripts/154_claim_run.sh <log> env HEADLESS=1 ... \
      FRUIT_RESET_ALIGN=1 FRUIT_RESET_ALIGN_ALONG=0.441 FRUIT_RESET_SETTLE=20 \
      FRUIT_RESET_ALIGN_DIAG=1 scripts/run.sh logs/p34/B_mask_probe.py

Prints one `[probe]` line per model call: the target's along/x/d, the analytic
belt-only visibility (212), the env's own target mask (`target_px`, the frame
the call conditioned on), the top-3 instance ids inside the fruit's projected
bbox with their labels, and the active arm's 7 joints. The `[probe] first` line
summarises the first call.

The 4-tick staleness of the step-0 observation (P34 read §3) is reported, not
avoided: `it=0` is the frame *before* the reset returns, `it=1` (step 4) is the
first model call.
"""

from __future__ import annotations

import importlib.util
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

# The app must exist before the env's Isaac imports, and the fd limit before
# the first camera read (same order as `scripts/110_rl_rollout.py`).
from isaacsim import SimulationApp  # noqa: E402

from fruit_sorting.fdlimit import raise_fd_limit  # noqa: E402

raise_fd_limit()
simulation_app = SimulationApp(
    {"headless": os.environ.get("HEADLESS", "1") == "1",
     "width": 640, "height": 480}
)

from fruit_sorting.rl_env import SortingRLEnv  # noqa: E402

CALLS = int(os.environ.get("PROBE_CALLS", "4"))
SEED = int(os.environ.get("PROBE_SEED", "77"))
LABELS = os.environ.get("PROBE_LABELS", "0") == "1"
EPISODES = int(os.environ.get("PROBE_EPISODES", "1"))


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
    return str(value)[:44]


def joints(arm) -> str:
    return ",".join(f"{v:+.3f}" for v in np.asarray(arm.joint_positions(), float))


def main() -> int:
    omap = load_map()
    env = SortingRLEnv(
        presentation="direct",
        seed=SEED,
        checkpoint="checkpoints/moe_v13s/policy_best.pt",
        execute_steps=4,
        ddim_steps=16,
        verbose=False,
    )
    env.reset(SEED)
    for ep in range(EPISODES):
        if ep:
            env.reset()
        arm = env.task.arms[env._active]
        sample = env._sample
        fruit = np.asarray(env.spawner.position(sample), dtype=float)
        print(f"[probe] reset ep={env._episode} knob={int(env._reset_align)} "
              f"aim={env._reset_align_along:.3f} settle={int(env._reset_settle)} "
              f"arm={env._active} steps={int(env._align_steps)} "
              f"along_reset={float(fruit[1]) - float(env._expert_jaw_y):+.3f} "
              f"x={float(fruit[0]):.3f} d={float(sample.diameter)*1000:.0f}mm "
              f"q={joints(arm)}")
        if LABELS:
            want = getattr(sample, "prim_path", None)
            seg, lab = seg_read(env.scene)
            hits = [(k, str(v)[:40]) for k, v in (lab or {}).items()
                    if want and want in str(v)]
            print(f"[probe] labels ep={env._episode} want={want} n_labels="
                  f"{len(lab or {})} hits={hits[:4]} "
                  f"mask_sum={-1 if env._last_mask is None else int(np.asarray(env._last_mask).sum())}")
        first = None
        px_max = -1
        frac_max = 0.0
        for it in range(CALLS + 1):
            if env._done:
                break
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
            aw = float(vis.get("area_without", 0.0) or 0.0)
            print(f"[probe] ep={env._episode} it={it} step={env._step:4d} "
                  f"calls={int(env._infer_calls)} "
                  f"along={along:+.3f} x={float(fruit[0]):.3f} "
                  f"d={float(sample.diameter)*1000:.0f}mm "
                  f"vis212={float(vis.get('vis', float('nan'))):.2f} aw={aw:.0f} "
                  f"target_px={mask_px:4d} q={joints(arm)} bbox_ids={top}")
            px_max = max(px_max, mask_px)
            if aw > 0 and mask_px > 0:
                frac_max = max(frac_max, mask_px / aw)
            if it == 1:
                first = dict(along=along, x=float(fruit[0]), px=mask_px, aw=aw,
                             vis212=float(vis.get("vis", float("nan"))), bbox=top,
                             q=[float(v) for v in arm.joint_positions()])
            env.act(chunk, execute_steps=4)
        if first is not None:
            vis = (first["px"] / first["aw"]) if first["aw"] > 0 and first["px"] > 0 else 0.0
            frac = (first["px"] / px_max) if px_max > 0 and first["px"] > 0 else 0.0
            f_abs = first["px"] / first["aw"] if first["aw"] > 0 and first["px"] > 0 else 0.0
            f_rel = f_abs / frac_max if frac_max > 0 else 0.0
            print(f"[probe] first ep={env._episode} arm={env._active} "
                  f"along={first['along']:+.3f} x={first['x']:.3f} "
                  f"px={first['px']} px_max={px_max} first_frac={frac:.3f} "
                  f"first_aw_frac={f_abs:.3f} first_rel={f_rel:.3f} "
                  f"aw={first['aw']:.0f} rendered_vis={vis:.3f} "
                  f"vis212={first['vis212']:.2f} "
                  f"q={','.join(f'{v:+.3f}' for v in first['q'])} bbox={first['bbox']}")
    print("[probe] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
