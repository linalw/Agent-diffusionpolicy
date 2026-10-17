#!/usr/bin/env python3
"""P10-D.1 stub check: the GDP OoD-scored population selection, offline.

Tier-C-level implementation evidence - NOT a substitute for the pre-registered
Tier-A battery (`logs/p10d1/PREREG_GDP_AB.md`; the simulator A/B is a separate
lane). Layers:

1. Source checks: the three knobs are read exactly once each with the
   documented defaults; the shipped `self.schedule.ddim_sample` call site is
   untouched; the GDP branch is gated on `self.gdp.enabled and self.gdp.k > 1`;
   the RTC sampler/chunker do not read the GDP knobs; `rl_env.TASKS_MD5` still
   matches `tasks.py` (the mission says tasks.py must not change).
2. `GDPSettings.from_env` resolution: default off, K default 2, K clamped to
   1..4, diag default off.
3. The selection rule on synthetic score vectors: min wins; ties -> the first.
4. The scored sampler is chain-identical to `DiffusionSchedule.ddim_sample`
   (same noise draw, same update order) on a checkpoint-free fake model, and
   its per-step scores are the Stein norms the paper's eq. (4) names.
5. The knob-off byte-inert proof (PREREG kill 1): `act()` with GDP off == a
   direct shipped `ddim_sample` call with the same noise draw == `act()` with
   GDP on/K=1, bitwise chunk equality plus identical generator states.
6. The GDP path end-to-end on a switching fake model: K candidates are drawn
   sequentially (candidate 0 = the shipped first draw), the lower-score
   candidate wins and the winner's chunk is reproduced independently; a tie
   selects the first candidate; K=4 samples four candidates.
7. The `[gdp]` diag row: exact format from the pure formatter and the
   regex-parse of the row captured from `act()` (per-candidate scores, chosen
   index, finger spread, wall cost per candidate).

Run:  python3 logs/p10d1/check_gdp_stub.py
Exit code 0 = all checks PASS.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import os
import pathlib
import re
import sys

import numpy as np
import torch

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fruit_sorting.policy.data import Normalizer
from fruit_sorting.policy.diffusion import DiffusionSchedule
from fruit_sorting.policy.runtime import (
    GDP_K_MAX,
    GDP_K_MIN,
    GDPSettings,
    PolicyRunner,
    _finger_spread,
    ddim_sample_scored,
    gdp_diag_line,
    select_gdp_candidate,
)

RUNTIME = ROOT / "src" / "fruit_sorting" / "policy" / "runtime.py"
TASKS = ROOT / "src" / "fruit_sorting" / "tasks.py"
RL_ENV = ROOT / "src" / "fruit_sorting" / "rl_env.py"

KNOBS = ("FRUIT_POLICY_GDP", "FRUIT_POLICY_GDP_K", "FRUIT_POLICY_GDP_DIAG")

failures: list[str] = []


def check(label: str, ok: bool) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def md5(path: pathlib.Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def resolve(**env: str) -> GDPSettings:
    """GDPSettings.from_env() under a clean knob environment."""
    old = {key: os.environ.get(key) for key in KNOBS}
    try:
        for key in KNOBS:
            os.environ.pop(key, None)
        os.environ.update(env)
        return GDPSettings.from_env()
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class FakeModel:
    """Checkpoint-free stand-in for `ConditionalUNet1D.denoise`.

    Returns a constant tensor; the constant comes from `values`, consumed one
    entry per call (the last repeats), so a run can switch its "noise" level
    between candidates. The resulting per-step Stein norm is
    `|value| * sqrt(numel)`, deterministic and candidate-discriminating.
    """

    def __init__(self, values: list[float]):
        self.values = list(values)
        self.calls = 0

    def denoise(self, sample, condition, timesteps):
        value = self.values[min(self.calls, len(self.values) - 1)]
        self.calls += 1
        return torch.full_like(sample, float(value))


def make_normalizer() -> Normalizer:
    return Normalizer(
        action_mean=np.zeros(9, dtype=np.float32),
        action_std=np.ones(9, dtype=np.float32),
        obs_mean=np.zeros(25, dtype=np.float32),
        obs_std=np.ones(25, dtype=np.float32),
        goal_mean=np.zeros(8, dtype=np.float32),
        goal_std=np.ones(8, dtype=np.float32),
    )


def make_runner(model, gdp: GDPSettings, seed: int = 11) -> PolicyRunner:
    """A tiny checkpoint-free PolicyRunner on CPU with identity normalizer.

    Same `__new__` shape as `scripts/128_rtc_selftest.py`, plus the P10-D1
    `gdp` field that `act` reads.
    """
    runner = PolicyRunner.__new__(PolicyRunner)
    runner.device = "cpu"
    runner.use_half = False
    runner.default_steps = 4
    runner.config = {"action_dim": 9, "action_horizon": 8}
    runner.model = model
    runner.schedule = DiffusionSchedule(100, device="cpu", beta_schedule="cosine")
    runner.normalizer = make_normalizer()
    runner.obs_horizon = 2
    runner.action_horizon = 8
    runner.image_size = 8
    runner.generator = torch.Generator(device="cpu").manual_seed(seed)
    runner._frames = [np.zeros((8, 8, 2), dtype=np.float32) for _ in range(2)]
    runner.gdp = gdp
    return runner


PROPRIO = np.zeros(25, dtype=np.float32)
GOAL = np.zeros(8, dtype=np.float32)
SHAPE = (1, 9, 8)
NUMEL = float(9 * 8)


def main() -> int:
    # ---- 1. source checks -------------------------------------------------- #
    print("== 1. source checks ==")
    source = RUNTIME.read_text(encoding="utf-8")
    check('`FRUIT_POLICY_GDP` read exactly once, default "0"',
          source.count('os.environ.get("FRUIT_POLICY_GDP"') == 1
          and 'os.environ.get("FRUIT_POLICY_GDP", "0")' in source)
    check('`FRUIT_POLICY_GDP_K` read exactly once, default "2"',
          source.count('os.environ.get("FRUIT_POLICY_GDP_K"') == 1
          and 'os.environ.get("FRUIT_POLICY_GDP_K", "2")' in source)
    check('`FRUIT_POLICY_GDP_DIAG` read exactly once, default "0"',
          source.count('os.environ.get("FRUIT_POLICY_GDP_DIAG"') == 1
          and 'os.environ.get("FRUIT_POLICY_GDP_DIAG", "0")' in source)
    check("`self.gdp = GDPSettings.from_env()` set exactly once (in __init__)",
          source.count("self.gdp = GDPSettings.from_env()") == 1)
    check("the shipped `self.schedule.ddim_sample(` call site is unchanged "
          "(exactly one)",
          source.count("self.schedule.ddim_sample(") == 1)
    check("the GDP branch is gated on `self.gdp.enabled and self.gdp.k > 1`",
          source.count("if self.gdp.enabled and self.gdp.k > 1:") == 1)
    check("exactly one `[gdp]` print site",
          source.count("print(gdp_diag_line(") == 1)
    tree = ast.parse(source)
    rtc_classes = {
        node.name: ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    }
    check("the RTC sampler/chunker never read the GDP knobs",
          "gdp" not in rtc_classes["RTCSampler"].lower()
          and "gdp" not in rtc_classes["RealtimeChunker"].lower())
    check("`_gdp_sample` reads no environment variables (resolution happens "
          "once in from_env)",
          "environ" not in ast.unparse(
              next(node for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef) and node.name == "_gdp_sample")
          ))
    sys.path.insert(0, str(ROOT / "src"))
    import fruit_sorting.rl_env as rl_env
    check("`rl_env.TASKS_MD5` still matches `tasks.py` (tasks.py untouched)",
          rl_env.TASKS_MD5 == md5(TASKS))

    # ---- 2. knob resolution ------------------------------------------------ #
    print("== 2. GDPSettings.from_env resolution ==")
    default = resolve()
    check("default: off, K=2, diag off",
          default.enabled is False and default.k == 2 and default.diag is False)
    check("`FRUIT_POLICY_GDP=1` enables; `=0` does not",
          resolve(FRUIT_POLICY_GDP="1").enabled is True
          and resolve(FRUIT_POLICY_GDP="0").enabled is False)
    check("`FRUIT_POLICY_GDP_K=1` keeps K=1 (the shipped path)",
          resolve(FRUIT_POLICY_GDP_K="1").k == 1)
    check("K clamps low: 0 -> 1, -3 -> 1",
          resolve(FRUIT_POLICY_GDP_K="0").k == 1
          and resolve(FRUIT_POLICY_GDP_K="-3").k == 1)
    check("K passes through: 2 -> 2, 3 -> 3, 4 -> 4",
          [resolve(FRUIT_POLICY_GDP_K=str(v)).k for v in (2, 3, 4)] == [2, 3, 4])
    check("K clamps high: 5 -> 4, 7 -> 4, 99 -> 4",
          [resolve(FRUIT_POLICY_GDP_K=str(v)).k for v in (5, 7, 99)] == [4, 4, 4])
    check("the clamp constants are 1..4", (GDP_K_MIN, GDP_K_MAX) == (1, 4))
    check("diag resolves: 1 -> True, 0 -> False",
          resolve(FRUIT_POLICY_GDP_DIAG="1").diag is True
          and resolve(FRUIT_POLICY_GDP_DIAG="0").diag is False)
    check("summary() names all three fields",
          resolve(FRUIT_POLICY_GDP="1", FRUIT_POLICY_GDP_DIAG="1").summary()
          == "gdp=on k=2 diag=on")

    # ---- 3. the selection rule --------------------------------------------- #
    print("== 3. select_gdp_candidate on synthetic scores ==")
    check("min wins", select_gdp_candidate([0.5, 0.3, 0.7]) == 1)
    check("ties -> the first candidate",
          select_gdp_candidate([0.4, 0.4]) == 0
          and select_gdp_candidate([0.2, 0.1, 0.1]) == 1
          and select_gdp_candidate([0.3, 0.2, 0.2, 0.4]) == 1)
    check("K=1 -> index 0", select_gdp_candidate([0.9]) == 0)

    # ---- 4. the scored sampler is chain-identical -------------------------- #
    print("== 4. ddim_sample_scored chain identity + score form ==")
    schedule = DiffusionSchedule(100, device="cpu", beta_schedule="cosine")
    condition = (
        torch.zeros(1, 2, 2, 8, 8),
        torch.zeros(1, 8),
        torch.zeros(1, 25),
    )
    gen_a = torch.Generator(device="cpu").manual_seed(3)
    gen_b = torch.Generator(device="cpu").manual_seed(3)
    plain = schedule.ddim_sample(
        FakeModel([0.7]), condition, SHAPE, num_steps=4,
        dtype=torch.float32, generator=gen_a,
    )
    scored, scores = ddim_sample_scored(
        schedule, FakeModel([0.7]), condition, SHAPE, num_steps=4,
        dtype=torch.float32, generator=gen_b,
    )
    check("the scored chain equals the shipped chain bit-for-bit",
          torch.equal(plain, scored))
    check("one score per denoising step, all finite",
          len(scores) == 4 and all(np.isfinite(s) for s in scores))
    check("scores are the Stein norms |eps| * sqrt(numel)",
          all(abs(s - 0.7 * np.sqrt(NUMEL)) < 1e-4 for s in scores))

    # ---- 5. the knob-off byte-inert proof (PREREG kill 1) ------------------ #
    print("== 5. knob-off byte-inert proof ==")
    runner_off = make_runner(FakeModel([0.7]), GDPSettings(enabled=False, k=2))
    chunk_off = runner_off.act(PROPRIO, GOAL, num_steps=4)
    state_off = runner_off.generator.get_state()

    runner_manual = make_runner(FakeModel([0.7]), GDPSettings(enabled=False, k=2))
    cond_manual = runner_manual._condition(PROPRIO, GOAL)
    sample_manual = runner_manual.schedule.ddim_sample(
        runner_manual.model, cond_manual, SHAPE, num_steps=4,
        dtype=torch.float32, generator=runner_manual.generator,
    )
    chunk_manual = runner_manual.normalizer.denormalize_action(
        sample_manual[0].float().transpose(0, 1).cpu().numpy()
    )
    check("GDP off == a direct shipped ddim_sample call, bit-for-bit",
          np.array_equal(chunk_off, chunk_manual))
    check("GDP off consumes exactly the shipped one noise draw",
          torch.equal(state_off, runner_manual.generator.get_state()))

    runner_k1 = make_runner(FakeModel([0.7]), GDPSettings(enabled=True, k=1))
    chunk_k1 = runner_k1.act(PROPRIO, GOAL, num_steps=4)
    check("GDP on with K=1 == the shipped path, bit-for-bit (same draw)",
          np.array_equal(chunk_k1, chunk_off)
          and torch.equal(runner_k1.generator.get_state(), state_off))

    check("the class-level default is disabled (checkpoint-free fixtures)",
          PolicyRunner.gdp.enabled is False and PolicyRunner.gdp.k == 2)
    runner_nogdp = make_runner(FakeModel([0.7]), GDPSettings(enabled=True, k=2))
    del runner_nogdp.gdp  # a 128_rtc_selftest-style runner: no instance attr
    chunk_nogdp = runner_nogdp.act(PROPRIO, GOAL, num_steps=4)
    check("a runner without the instance `gdp` resolves disabled and takes "
          "the shipped path",
          np.array_equal(chunk_nogdp, chunk_off))

    # ---- 6. the GDP path end-to-end ---------------------------------------- #
    print("== 6. GDP selection end-to-end (switching fake model) ==")
    # Candidate 0's chain sees value 1.0 (4 calls), candidate 1 sees 0.5, so
    # candidate 1 has the lower Stein score and must win.
    runner_g = make_runner(
        FakeModel([1.0] * 4 + [0.5] * 4),
        GDPSettings(enabled=True, k=2, diag=True),
    )
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        chunk_g = runner_g.act(PROPRIO, GOAL, num_steps=4)
    check("K=2 consumes two sequential noise draws (2 x 4 denoise calls)",
          runner_g.model.calls == 8)

    cand0 = make_runner(FakeModel([1.0]), GDPSettings(enabled=False)).act(
        PROPRIO, GOAL, num_steps=4
    )
    runner_c1 = make_runner(FakeModel([0.5]), GDPSettings(enabled=False))
    torch.randn(SHAPE, generator=runner_c1.generator)  # consume draw 0
    cand1 = runner_c1.act(PROPRIO, GOAL, num_steps=4)
    check("the lower-score candidate (index 1) is the executed chunk",
          np.array_equal(chunk_g, cand1) and not np.array_equal(chunk_g, cand0))

    runner_tie = make_runner(
        FakeModel([0.5] * 8), GDPSettings(enabled=True, k=2, diag=True)
    )
    with contextlib.redirect_stdout(io.StringIO()):
        chunk_tie = runner_tie.act(PROPRIO, GOAL, num_steps=4)
    cand_tie = make_runner(FakeModel([0.5]), GDPSettings(enabled=False)).act(
        PROPRIO, GOAL, num_steps=4
    )
    check("a tie selects the first candidate",
          np.array_equal(chunk_tie, cand_tie))

    runner_k4 = make_runner(
        FakeModel([0.5] * 16), GDPSettings(enabled=True, k=4, diag=True)
    )
    buf4 = io.StringIO()
    with contextlib.redirect_stdout(buf4):
        runner_k4.act(PROPRIO, GOAL, num_steps=4)
    row4 = [l for l in buf4.getvalue().splitlines() if l.startswith("[gdp]")]
    check("K=4 samples four candidates and prints one 4-candidate row",
          runner_k4.model.calls == 16 and len(row4) == 1
          and row4[0].startswith("[gdp] k=4 chosen=0 "))

    # ---- 7. the [gdp] diag row --------------------------------------------- #
    print("== 7. the [gdp] diag row ==")
    exact = gdp_diag_line(
        2, 1, [0.8123, 0.8001], [0.021, 0.0175], [11.8, 12.1]
    )
    check("the pure formatter's exact row",
          exact == "[gdp] k=2 chosen=1 scores=0.8123,0.8001 "
                   "fingers=0.0210,0.0175 cost_ms=11.8,12.1")
    rows = [l for l in buf.getvalue().splitlines() if l.startswith("[gdp]")]
    check("exactly one row per GDP selection", len(rows) == 1)
    match = re.fullmatch(
        r"\[gdp\] k=(\d+) chosen=(\d+) scores=([0-9.,]+) "
        r"fingers=([0-9.,]+) cost_ms=([0-9.,]+)",
        rows[0] if rows else "",
    )
    check("the row parses (k, chosen, scores, fingers, cost_ms)",
          match is not None)
    if match:
        k_row = int(match.group(1))
        chosen_row = int(match.group(2))
        score_vals = [float(v) for v in match.group(3).split(",")]
        finger_vals = [float(v) for v in match.group(4).split(",")]
        cost_vals = [float(v) for v in match.group(5).split(",")]
        check("chosen=1, K=2, the winner has the lower score",
              k_row == 2 and chosen_row == 1 and len(score_vals) == 2
              and score_vals[0] > score_vals[1]
              and abs(score_vals[0] - np.sqrt(NUMEL)) < 1e-3
              and abs(score_vals[1] - 0.5 * np.sqrt(NUMEL)) < 1e-3)
        check("one finger spread + one wall cost per candidate",
              len(finger_vals) == 2 and len(cost_vals) == 2
              and all(c >= 0.0 for c in cost_vals))

    chunk_probe = np.zeros((4, 9), dtype=np.float32)
    chunk_probe[:, 7] = [0.044, 0.014, 0.030, 0.030]
    check("`_finger_spread` reads the finger channel (index 7)",
          abs(_finger_spread(chunk_probe) - 0.030) < 1e-6)

    # ---- md5s --------------------------------------------------------------- #
    print("== md5s ==")
    print(f"  runtime.py {md5(RUNTIME)}")
    print(f"  tasks.py   {md5(TASKS)} (rl_env.TASKS_MD5 {rl_env.TASKS_MD5})")
    print(f"  rl_env.py  {md5(RL_ENV)}")

    print()
    if failures:
        print(f"STUB FAIL: {len(failures)} check(s) failed:")
        for label in failures:
            print(f"  - {label}")
        return 1
    print("STUB PASS: all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
