#!/usr/bin/env python3
"""Aggregate a py-spy speedscope record into a text table (P82, I1).

    python3 logs/p82/ps_agg.py logs/p82/R3.speedscope.json.gz > logs/p82/R3.profile.txt
    python3 logs/p82/ps_agg.py --thread MainThread R3.speedscope.json

Three views of the same samples (py-spy runs at 100 Hz with `--idle`, so the
weights are 0.01 s each and a thread's weight sum is wall seconds):

1. **per thread** - the wall each thread saw, and how it split. This is the only
   view that answers "where does the wall go": the two attempt threads are parked
   in `TickRelay.request`'s condition wait ~95 % of the time and one
   `ThreadPoolExecutor` worker is parked on its queue, so a *thread-pooled* total
   is dominated by parks. The main thread is the arbiter and it is the one whose
   split matters.
2. **the caller stack** - the top `leaf <- ...` chains, which is how the same
   buckets are read back by eye (`step <- schedule <- alive`, `wait <- get <-
   pump <- serve_while`).
3. **buckets** - the registered P82 buckets (METHOD §2), per thread and for the
   whole process.
"""

from __future__ import annotations

import json
import sys
from collections import Counter

BUCKETS = {
    # blocking / parked
    "wait": {"wait", "_wait_permit", "get", "acquire", "sleep", "join", "_worker",
             "serve_while", "pump", "wait_for"},
    # the physics step itself (SimulationManager.step is one PhysX simulate call)
    "physics": {"step", "step_patch", "timed_step"},
    # render / camera
    "render": {"render", "_tick_frame", "update_app", "_render"},
    # the two arms' control work
    "control_ik": {
        "ik_step", "tcp_position", "tcp_pose", "dof_positions", "dof_velocities",
        "get_jacobian_matrices", "set_dof_positions", "set_dof_position_targets",
        "quaternion_error", "_approach", "_carry", "_carry_leg", "_carry",
        "solve_to", "grasp_lift", "place0", "place1", "close", "release", "lift",
        "move_to", "_hold_with_gripper", "_blend_to", "_ready_transit", "_servo",
        "jerk_limited", "advance_to", "_run_impl", "_grasp_carry_place_impl",
        "grasp_carry_place", "run", "_dynamic_aim", "_reach_prepare_aim",
        "hold_quaternion", "capture_hold_pose", "gripper", "jaw_separation",
        "set_jaw", "open_width", "close_gap", "grasp_gap",
    },
    # fruit / spawner state reads
    "fruit_state": {
        "state", "position", "position_quat", "scan_despawn", "update",
        "select_target", "_dynamic_select_floor", "bed_stats_line", "_feed_tick",
        "_pump_supply", "sample", "refresh_rigids",
    },
    # the arbiter's own Python work
    "arbiter": {"schedule", "request", "pause", "resume", "release", "register",
                "arm", "enter", "call", "expect", "participant", "_notify"},
    # USD/scene bookkeeping the app runs inside our step (not our code)
    "app_callbacks": {"_on_usd_changed", "invoke", "_on_objects_changed",
                      "_on_usd_objects_changed", "on_changes", "stage_changed_notice",
                      "copy", "_init_from_data", "__getitem__", "allocate"},
    # start-up only
    "boot": {"_add_robot", "build", "main", "_start_app", "__init__", "<module>",
             "start", "warmup", "create_pool", "prime", "go_ready"},
}


def bucket_of(name: str) -> str:
    for bucket, names in BUCKETS.items():
        if name in names:
            return bucket
    return "other"


def main(argv: list[str]) -> int:
    only = None
    if len(argv) >= 2 and argv[0] == "--thread":
        only, argv = argv[1], argv[2:]
    path = argv[0]
    # the records are kept gzipped (12.5 MB -> 183 kB): a speedscope JSON is mostly
    # repeated frame indices, and `py-spy` writes them uncompressed.
    if path.endswith(".gz"):
        import gzip

        with gzip.open(path, "rt", encoding="utf-8") as handle:
            data = json.load(handle)
    else:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    names = [frame.get("name", "?") for frame in data["shared"]["frames"]]

    rows = []
    global_bucket = Counter()
    global_total = 0.0
    for profile in data["profiles"]:
        label = profile.get("name") or "thread"
        weights = profile.get("weights") or [1.0] * len(profile["samples"])
        total = 0.0
        bucket = Counter()
        stacks = Counter()
        self_time = Counter()
        for sample, weight in zip(profile["samples"], weights):
            if not sample:
                continue
            leaf = names[sample[-1]]
            total += weight
            bucket[bucket_of(leaf)] += weight
            self_time[leaf] += weight
            stacks[tuple(names[i] for i in sample[-5:])] += weight
        if total:
            rows.append((label, total, bucket, stacks, self_time))
            global_total += total
            for name, value in bucket.items():
                global_bucket[name] += value

    def fmt(bucket, total, order=("physics", "control_ik", "arbiter", "fruit_state",
                                  "render", "wait", "app_callbacks", "boot", "other")):
        parts = []
        for name in order:
            value = bucket.get(name, 0.0)
            if value / max(total, 1e-9) >= 0.005:
                parts.append(f"{name}={value / max(total, 1e-9):.1%}")
        return ", ".join(parts)

    print(f"file: {path}")
    print(f"samples: {sum(len(p['samples']) for p in data['profiles'])} at "
          f"{(data['profiles'][0]['weights'] or [0.01])[0]} s each "
          f"({len(data['profiles'])} threads)")
    print("\n== per thread (wall sampled, bucket shares) ==")
    for label, total, bucket, _stacks, _self in sorted(rows, key=lambda r: -r[1]):
        if only and only not in label:
            continue
        print(f"{label[:52]:52s} {total:8.1f} s  {fmt(bucket, total)}")

    for label, total, bucket, stacks, self_time in sorted(rows, key=lambda r: -r[1]):
        if only and only not in label:
            continue
        if total < 1.0:
            continue
        print(f"\n== {label} ({total:.1f} s sampled) ==")
        print("  top caller chains (leaf <- caller):")
        for stack, value in stacks.most_common(8):
            if value / total < 0.005:
                break
            print(f"    {value:8.1f} s {value / total:6.1%}  {' <- '.join(reversed(stack))}")
        print("  top leaf frames:")
        for name, value in self_time.most_common(8):
            if value / total < 0.005:
                break
            print(f"    {value:8.1f} s {value / total:6.1%}  {name}")

    print(f"\n== process total ({global_total:.1f} s over "
          f"{sum(len(p['samples']) for p in data['profiles'])} samples) ==")
    for name, value in global_bucket.most_common():
        print(f"  {name:14s} {value:8.1f} s {value / max(global_total, 1e-9):6.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
