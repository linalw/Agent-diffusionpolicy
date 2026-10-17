#!/usr/bin/env python3
"""P10-D.1: the knob-off byte-inert proof on the REAL battery checkpoint.

`check_gdp_stub.py` proves the inertness checkpoint-free (fake model, CPU);
this one-off repeats it on the checkpoint the battery actually runs
(`checkpoints/moe_v13s/policy_best.pt`, fp16, CUDA if available) and captures
a real `[gdp]` diag row:

  1. `FRUIT_POLICY_SEED=11` (the battery's `AB_POLICY_SEED`), GDP off:
     `act()` must equal a manual `ddim_sample` call with the same noise draw,
     bit-for-bit.
  2. Two fresh processes/runners with the same seed: GDP off == GDP off and
     GDP on K=2 == GDP on K=2 (reproducibility of the selection), and the
     K=2 chunk is one of the two candidate chains.
  3. One `FRUIT_POLICY_GDP_DIAG=1` act() row on the real model.

Run:  python3 logs/p10d1/check_gdp_real_inert.py | tee logs/p10d1/20_real_inert.txt
"""

from __future__ import annotations

import contextlib
import io
import os
import pathlib
import re
import sys

import numpy as np
import torch

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

os.environ["FRUIT_POLICY_SEED"] = "11"  # the battery's AB_POLICY_SEED default

from fruit_sorting.policy.runtime import GDPSettings, PolicyRunner  # noqa: E402

CKPT = ROOT / "checkpoints" / "moe_v13s" / "policy_best.pt"
CAM = (240, 424)

failures: list[str] = []


def check(label: str, ok: bool) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def make_runner(device: str) -> PolicyRunner:
    runner = PolicyRunner(str(CKPT), device=device)
    rgb = np.zeros((*CAM, 3), dtype=np.uint8)
    depth = np.zeros(CAM, dtype=np.float32)
    runner.push_frame(rgb, depth)
    runner.push_frame(rgb, depth)
    return runner


def main() -> int:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"checkpoint {CKPT.relative_to(ROOT)}  device {device}  "
          f"FRUIT_POLICY_SEED={os.environ['FRUIT_POLICY_SEED']}")
    proprio = np.zeros(25, dtype=np.float32)
    goal = np.zeros(8, dtype=np.float32)

    # 1. GDP off == the manual shipped call with the same noise draw ---------- #
    runner = make_runner(device)
    check("runner resolved GDP off", runner.gdp.enabled is False)
    chunk = runner.act(proprio, goal, num_steps=16)

    manual_runner = make_runner(device)
    condition = manual_runner._condition(proprio, goal)
    shape = (1, manual_runner.config["action_dim"], manual_runner.action_horizon)
    sample = manual_runner.schedule.ddim_sample(
        manual_runner.model, condition, shape, num_steps=16,
        dtype=torch.float16 if manual_runner.use_half else torch.float32,
        generator=manual_runner.generator,
    )
    manual = manual_runner.normalizer.denormalize_action(
        sample[0].float().transpose(0, 1).cpu().numpy()
    )
    check("GDP off == manual ddim_sample with the same draw, bit-for-bit",
          np.array_equal(chunk, manual))

    # 2. same-seed reproducibility, and K=2 is a candidate chain -------------- #
    # `manual_runner.generator` has consumed draw 0 (candidate 0's noise), so
    # the next ddim_sample on it reproduces candidate 1's chain.
    cand1_sample = manual_runner.schedule.ddim_sample(
        manual_runner.model, condition, shape, num_steps=16,
        dtype=torch.float16 if manual_runner.use_half else torch.float32,
        generator=manual_runner.generator,
    )
    cand1 = manual_runner.normalizer.denormalize_action(
        cand1_sample[0].float().transpose(0, 1).cpu().numpy()
    )

    runner_a = make_runner(device)
    runner_b = make_runner(device)
    runner_a.gdp = GDPSettings(enabled=True, k=2, diag=True)
    runner_b.gdp = GDPSettings(enabled=True, k=2, diag=True)
    buf_a, buf_b = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf_a):
        chunk_a = runner_a.act(proprio, goal, num_steps=16)
    with contextlib.redirect_stdout(buf_b):
        chunk_b = runner_b.act(proprio, goal, num_steps=16)
    # The diag row carries wall-clock `cost_ms`, which cannot repeat; compare
    # the rows with the timing field normalized out.
    strip_costs = lambda text: re.sub(r"cost_ms=[0-9.,]+", "cost_ms=*", text)  # noqa: E731
    check("GDP on K=2 is reproducible across runners (same seed; chunks "
          "bitwise, diag rows equal modulo the wall-cost field)",
          np.array_equal(chunk_a, chunk_b)
          and strip_costs(buf_a.getvalue()) == strip_costs(buf_b.getvalue()))
    row = [l for l in buf_a.getvalue().splitlines() if l.startswith("[gdp]")]
    print(f"  real [gdp] row: {row[0] if row else 'MISSING'}")
    chosen = int(row[0].split("chosen=")[1].split(" ")[0]) if row else -1
    check("the K=2 chunk is the candidate chain the diag row names "
          f"(chosen={chosen})",
          (chosen == 0 and np.array_equal(chunk_a, chunk))
          or (chosen == 1 and np.array_equal(chunk_a, cand1)))

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed.")
        return 1
    print("PASS: real-checkpoint inertness + reproducibility checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
