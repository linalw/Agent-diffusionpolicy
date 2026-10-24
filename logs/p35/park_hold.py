#!/usr/bin/env python3
"""P35 phase 1: how well a candidate park *holds* over an episode's length.

`logs/p35/park_probe.py` measures each pose 90 ticks after the teleport. A park
is held for a whole episode (~30 s = 3600 ticks), so this probe steps 900 ticks
at the candidate pose and reports the joint drift against the settled vector at
every sample: a pose the drives cannot hold shows up as a growing error, and a
pose that touches the belt shows up as a step change (the shipped build has
`enabledSelfCollisions=0`, so the arms cannot collide with each other, but the
conveyor is a real collider).

    scripts/154_claim_run.sh logs/p35/30_park_hold.log \
      env HEADLESS=1 scripts/run.sh logs/p35/park_hold.py

Writes `logs/p35/park_hold.json`.
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

from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402

from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.control import ArmController  # noqa: E402
from fruit_sorting.scene import SortingScene  # noqa: E402

OUT = os.path.join(ROOT, "logs/p35/park_hold.json")
PARKS = tuple(os.environ.get("HOLD_PARKS", "ready,back,side_deep").split(","))
TICKS = int(os.environ.get("HOLD_TICKS", "900"))
SAMPLE = int(os.environ.get("HOLD_SAMPLE", "150"))


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    belt_top = float(cfg.belt_center[2]) + float(cfg.belt_size[2]) / 2.0
    wps = json.load(open(os.path.join(ROOT, "configs/waypoints.json"), encoding="utf-8"))
    sweep = json.load(open(os.path.join(ROOT, "logs/p35/park_sweep.json"),
                           encoding="utf-8"))
    side = "left"
    rows = {r["name"]: r for r in sweep["sides"][side]}
    arms = {s: ArmController(scene, s) for s in ("left", "right")}
    arms["right"].set_gripper(arms["right"].OPEN)
    arms["right"].teleport_joints(np.asarray(wps["arms"]["right"]["grasp"], dtype=float))
    arm = arms[side]
    arm.set_gripper(arm.OPEN)
    out = {"belt_top": belt_top, "ticks": TICKS, "side": side, "parks": {}}
    for park in PARKS:
        if park not in rows:
            print(f"[hold] {park}: not in the sweep, skipped")
            continue
        q = np.asarray(rows[park]["q"], dtype=float)
        arm.teleport_joints(q, settle=90)
        q0 = np.asarray(arm.joint_positions(), dtype=float)
        samples = []
        for k in range(0, TICKS + 1, SAMPLE):
            if k:
                SimulationManager.step(steps=SAMPLE)
            qm = np.asarray(arm.joint_positions(), dtype=float)
            jaw = np.asarray(arm.jaw_centre(), dtype=float)
            samples.append(dict(tick=k, drift=float(np.max(np.abs(qm - q0))),
                                drift_cmd=float(np.max(np.abs(qm - q))),
                                jaw=[float(v) for v in jaw]))
        drifts = [s["drift"] for s in samples]
        out["parks"][park] = dict(q=[float(v) for v in q0], samples=samples,
                                  drift_max=float(max(drifts)),
                                  drift_end=float(drifts[-1]),
                                  jaw_drop=float(samples[0]["jaw"][2] - samples[-1]["jaw"][2]))
        print(f"[hold] {park}: drift_max={max(drifts):.4f} end={drifts[-1]:.4f} "
              f"jaw_drop={out['parks'][park]['jaw_drop']:+.4f} m "
              f"jaw_end={np.round(samples[-1]['jaw'], 3).tolist()}")
        print("        " + " ".join(f"{s['tick']}:{s['drift']:.4f}" for s in samples))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"[hold] wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
