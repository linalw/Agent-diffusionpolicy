#!/usr/bin/env python3
"""P10-D.1 offline wall-cost measurement for the GDP knob (no simulator).

Loads the battery's checkpoint (`checkpoints/moe_v13s/policy_best.pt`) and
times, on this machine's RTX 5090 (or CPU if the GPU is unavailable):

  - the shipped per-candidate cost: one DDIM-16 `ddim_sample` chain;
  - the GDP per-candidate cost: `ddim_sample_scored` (the same chain plus the
    per-step Stein-norm bookkeeping the selection reads);
  - the end-to-end `act()` cost with the knob off and with K=2 (condition
    build + 2 candidates + selection), the quantity the control loop pays per
    re-plan.

The report places these against the mechanism menu's "~12 ms each" claim
(`docs/papers/MECHANISMS.md` item #5; the repo's earlier DDIM-8-class number -
the shipped DDIM-16 was recorded at 23.69 ms/chunk in the WORKLOG benchmark
ladder), the 1/120 s tick (8.33 ms) and the shipped re-plan window
(`EXECUTE_STEPS=4` control steps = 33.3 ms), with the overrun stated plainly.

Run:  python3 logs/p10d1/measure_gdp_cost.py | tee logs/p10d1/10_wall_cost.txt
"""

from __future__ import annotations

import pathlib
import statistics
import subprocess
import sys
import time

import numpy as np
import torch

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fruit_sorting.policy.runtime import (
    GDPSettings,
    PolicyRunner,
    ddim_sample_scored,
)

CKPT = ROOT / "checkpoints" / "moe_v13s" / "policy_best.pt"
CAM = (240, 424)  # the battery camera (FRUIT_CAMERA_RES=240,424)
TICK_MS = 1000.0 / 120.0  # 1/120 s control tick
REPLAN_WINDOW_MS = 4.0 * TICK_MS  # EXECUTE_STEPS=4 control steps per re-plan


def gpu_status() -> str:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() or "n/a"
    except Exception:
        return "n/a"


def time_call(fn, iters: int, device: str) -> list[float]:
    times = []
    for _ in range(iters):
        if device == "cuda":
            torch.cuda.synchronize()
        start = time.perf_counter()
        fn()
        if device == "cuda":
            torch.cuda.synchronize()
        times.append((time.perf_counter() - start) * 1e3)
    return times


def fmt_stats(times: list[float]) -> str:
    ordered = sorted(times)
    return (
        f"median {statistics.median(times):7.2f}  mean {statistics.mean(times):7.2f}  "
        f"p90 {ordered[int(0.9 * (len(ordered) - 1))]:7.2f}  "
        f"min {min(times):7.2f}  max {max(times):7.2f}"
    )


def main() -> int:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    iters = 30 if device == "cuda" else 5
    print("== P10-D.1 GDP wall cost (offline, checkpoint only, no simulator) ==")
    print(f"checkpoint : {CKPT.relative_to(ROOT)}")
    print(f"device     : {device}"
          + (f" ({torch.cuda.get_device_name(0)})" if device == "cuda" else ""))
    print(f"torch      : {torch.__version__}")
    print(f"gpu before : {gpu_status()}")
    print(f"iters      : {iters} (warmup 3)")
    print()

    runner = PolicyRunner(str(CKPT), device=device)
    # The battery camera resolution: two zero frames + zero proprio/goal give a
    # real-shaped condition through the real `_condition` path.
    rgb = np.zeros((*CAM, 3), dtype=np.uint8)
    depth = np.zeros(CAM, dtype=np.float32)
    runner.push_frame(rgb, depth)
    runner.push_frame(rgb, depth)
    proprio = np.zeros(25, dtype=np.float32)
    goal = np.zeros(8, dtype=np.float32)
    condition = runner._condition(proprio, goal)
    shape = (1, runner.config["action_dim"], runner.action_horizon)
    print(f"dtype      : {'fp16' if runner.use_half else 'fp32'}  "
          f"DDIM steps: 16  chunk shape: {shape}")
    print()

    shipped = lambda: runner.schedule.ddim_sample(  # noqa: E731
        runner.model, condition, shape, num_steps=16,
        dtype=torch.float16 if runner.use_half else torch.float32,
        generator=runner.generator,
    )
    scored = lambda: ddim_sample_scored(  # noqa: E731
        runner.schedule, runner.model, condition, shape, num_steps=16,
        dtype=torch.float16 if runner.use_half else torch.float32,
        generator=runner.generator,
    )

    for _ in range(3):
        shipped()
        scored()
    if device == "cuda":
        torch.cuda.synchronize()

    t_shipped = time_call(shipped, iters, device)
    t_scored = time_call(scored, iters, device)

    runner.gdp = GDPSettings(enabled=False, k=2)
    t_act_off = time_call(
        lambda: runner.act(proprio, goal, num_steps=16), iters, device
    )
    runner.gdp = GDPSettings(enabled=True, k=2)
    t_act_k2 = time_call(
        lambda: runner.act(proprio, goal, num_steps=16), iters, device
    )
    print(f"gpu after  : {gpu_status()}")
    print()

    print("per-candidate sampling (one DDIM-16 chain):")
    print(f"  shipped ddim_sample        : {fmt_stats(t_shipped)}")
    print(f"  GDP ddim_sample_scored     : {fmt_stats(t_scored)}")
    print()
    print("end-to-end act() (condition build + sampling + selection):")
    print(f"  GDP off (1 candidate)      : {fmt_stats(t_act_off)}")
    print(f"  GDP on  K=2 (2 candidates) : {fmt_stats(t_act_k2)}")
    print()

    med = statistics.median(t_shipped)
    med_scored = statistics.median(t_scored)
    med_k2 = statistics.median(t_act_k2)
    print("against the claims:")
    print(f"  menu claim ~12 ms/candidate : measured {med:.2f} ms -> "
          f"{med / 12.0:.2f}x the claim")
    print(f"  1/120 s tick 8.33 ms        : measured {med:.2f} ms -> "
          f"{med / TICK_MS:.2f}x the tick "
          f"({'OVER' if med > TICK_MS else 'inside'})")
    print(f"  re-plan window 33.3 ms      : K=2 act {med_k2:.2f} ms -> "
          f"{med_k2 / REPLAN_WINDOW_MS:.2f}x the window "
          f"({'OVER' if med_k2 > REPLAN_WINDOW_MS else 'inside'})")
    print(f"  scoring overhead            : {med_scored - med:+.2f} ms/candidate "
          f"({100.0 * (med_scored - med) / med:+.1f} % of the shipped chain)")
    print(f"  K=2 vs K=1 act              : {med_k2 - statistics.median(t_act_off):+.2f} ms "
          f"({med_k2 / statistics.median(t_act_off):.2f}x)")
    print()
    print("notes:")
    print("  - the simulator loop is stepped, not wall-clocked: the sampling cost")
    print("    changes the wall time per attempt, not the simulated-time cycle;")
    print("    the battery's kill-3 (+5 % cycle) is therefore a sim-clock check.")
    print("  - this host ran no simulator during the measurement; nvidia-smi")
    print("    before/after is printed above (a busy GPU inflates the numbers -")
    print("    the distill lane's first pass read 41.6 ms/chunk under contention).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
