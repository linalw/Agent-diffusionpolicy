#!/usr/bin/env python3
"""P37 design-only power check for the pre-registered non-inferiority primary.

    python3 logs/p37/power_check.py            # -> logs/p37/power_check.txt

**No outcome data is read**: this script only simulates the *design* - the
right-arm placed/ok count of the base arm A and the candidate arm B over the
pre-registered N = 5 x 15 batch - to state what the pre-registered bar can and
cannot distinguish. It is the P36 `power_check.py` analogue (design-only, so its
mtime carries no data dependence).

The primary (`PREREG.md` section 6): the candidate's pooled right-arm placed/ok
rate must not be below the base's by more than the pre-registered margin
`MARGIN = 0.10` absolute:

    pass  <=>  ok_B / n_B  >=  ok_A / n_A - MARGIN

Both counts are sampled (the base is the batch's own arm A, so its rate is a
sample too). `n_A = n_B = 50` is the expected right-arm denominator: P35's
right share was 51/75 = 68 %, P36's 64 %, and the arm is set by the fruit grade,
so 75 episodes give ~45-52 right-arm episodes. The `n = 40` row is the
low-denominator sensitivity.

The run-level direction (reported, not gated) is `B_run_ok >= A_run_ok` per run
with ~10 right-arm episodes per run.
"""

from __future__ import annotations

import random

SEED = 20261024
DRAWS = 20000
MARGIN = 0.10
P_BASE = 0.94  # P35 C batch: right 47/50; P36 cell 2: 29/30


def _binom(rng: random.Random, n: int, p: float) -> int:
    return sum(1 for _ in range(n) if rng.random() < p)


def simulate(n: int, p_cand: float, runs: int = 5) -> dict:
    rng = random.Random(SEED)
    passes = 0
    better_or_equal_runs = 0
    pooled = []
    for _ in range(DRAWS):
        ok_a = _binom(rng, n, P_BASE)
        ok_b = _binom(rng, n, p_cand)
        rate_a = ok_a / n
        rate_b = ok_b / n
        passes += 1 if rate_b >= rate_a - MARGIN else 0
        pooled.append((ok_a, ok_b))
        per = n // runs
        wins = 0
        for _ in range(runs):
            if _binom(rng, per, p_cand) >= _binom(rng, per, P_BASE):
                wins += 1
        better_or_equal_runs += 1 if wins == runs else 0
    return {
        "pass": passes / DRAWS,
        "all_runs_ge": better_or_equal_runs / DRAWS,
        "median_delta": sorted((b - a) for a, b in pooled)[DRAWS // 2] / n,
    }


def main() -> int:
    print("P37 power check - the non-inferiority primary (design only, no data)")
    print(f"draws={DRAWS}  margin={MARGIN:.2f}  base right ok p={P_BASE:.2f}  seed={SEED}")
    print()
    print("p_cand is the candidate's TRUE right-arm placed rate; n = right-arm episodes/arm")
    for n in (40, 50):
        print(f"\n--- n = {n} per arm ---")
        print(f"{'p_cand':>7} {'P(pass)':>9} {'P(B>=A in 5/5 runs)':>20} {'median delta (B-A)':>19}")
        for p_cand in (0.94, 0.90, 0.85, 0.80, 0.75, 0.60, 0.45):
            row = simulate(n, p_cand)
            print(
                f"{p_cand:7.2f} {row['pass']:9.3f} {row['all_runs_ge']:20.3f} "
                f"{row['median_delta']:+19.3f}"
            )
    print()
    print("Reading (pre-registered):")
    print(f"  * false-erasure rate: at p_cand = p_base the test FAILS in "
          f"{1 - simulate(50, P_BASE)['pass']:.1%} of batches (n = 50) - the")
    print("    one-sided 0.10 margin spends that much on a preserved win;")
    print("  * the erasure state (the parked win gone: p ~ 0.45, the P35 control's")
    print(f"    0.45 right rate) passes in {simulate(50, 0.45)['pass']:.1%} of batches;")
    print("  * a candidate at the margin (0.84) is the ambiguous cell and is")
    print("    reported as such, not rounded to a pass or a fail.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
