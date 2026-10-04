"""Unit checks for fruit_sorting.motion - no Isaac Sim needed.

    python3 scripts/96_motion_check.py     (numpy only)

Verifies that the jerk-limited profile really respects its bounds and that the
friction-cone budget behaves like the physics says it should.
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from fruit_sorting.motion import (  # noqa: E402
    MotionMonitor,
    TrajectoryLimits,
    accel_budget,
    cone_scale,
    jerk_limited,
    min_jerk_ramp,
    mirror_across_xz,
    top_down_quaternion,
)

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "ok  " if condition else "FAIL"
    print(f"[{status}] {name}{(' - ' + detail) if detail else ''}")
    if not condition:
        FAILURES.append(name)


def profile_bounds(distance: float, limits: TrajectoryLimits) -> None:
    pos, vel, acc = jerk_limited(distance, limits)
    dt = limits.dt
    jerk = np.diff(acc) / dt if len(acc) > 1 else np.zeros(0)
    print(
        f"  d={distance:+.3f} m -> {len(pos):4d} steps ({len(pos) * dt:.2f} s), "
        f"|v|={np.abs(vel).max():.3f} (limit {limits.v_max:.3f}), "
        f"|a|={np.abs(acc).max():.3f} (limit {limits.a_max:.3f}), "
        f"|j|={np.abs(jerk).max() if len(jerk) else 0.0:.1f} (limit {limits.j_max:.1f})"
    )
    check(f"  endpoint d={distance:+.3f}", abs(pos[-1] - distance) < 1e-9)
    check(f"  starts/ends at rest d={distance:+.3f}",
          abs(vel[0]) < 1e-9 and abs(vel[-1]) < 1e-9)
    check(f"  |v| <= v_max d={distance:+.3f}", np.abs(vel).max() <= limits.v_max + 1e-6)
    check(f"  |a| <= a_max d={distance:+.3f}", np.abs(acc).max() <= limits.a_max + 1e-6)
    check(f"  |j| <= j_max d={distance:+.3f}",
          len(jerk) == 0 or np.abs(jerk).max() <= limits.j_max + 1e-6)


def main() -> int:
    print("== jerk-limited profiles ==")
    limits = TrajectoryLimits(v_max=0.30, a_max=2.0, j_max=25.0)
    for distance in (0.012, 0.05, 0.25, 0.78, -0.40):
        profile_bounds(distance, limits)

    print("\n== friction-cone acceleration budget ==")
    mu_eff = 1.2  # FRUIT_MU_SAFETY 0.6 * pad mu 2.0
    for name, direction in (
        ("horizontal", (1.0, 0.0, 0.0)),
        ("straight up", (0.0, 0.0, 1.0)),
        ("straight down", (0.0, 0.0, -1.0)),
        ("diagonal up", (1.0, 0.0, 1.0)),
    ):
        budget = accel_budget(direction, mu_eff)
        print(f"  {name:>14}: a_max = {budget:6.2f} m/s^2")
    check("horizontal budget = g*sqrt(mu^2-1)", abs(accel_budget((1, 0, 0), mu_eff) - 9.81 * np.sqrt(mu_eff**2 - 1)) < 1e-9)
    check("upward budget = g*(mu-1)", abs(accel_budget((0, 0, 1), mu_eff) - 9.81 * (mu_eff - 1)) < 1e-9)
    check("cone_scale zeroes an over-budget accel",
          cone_scale(np.array([20.0, 0.0, 0.0]), mu_eff) * 20.0 <= accel_budget((1, 0, 0), mu_eff) + 1e-9)
    check("cone_scale leaves a safe accel alone",
          abs(cone_scale(np.array([0.5, 0.0, 0.0]), mu_eff) - 1.0) < 1e-9)

    print("\n== cone-limited move (the lift leg) ==")
    direction = np.array([0.0, 0.0, 1.0])
    carrying = limits.limited_by_cone(direction, mu_eff)
    print(
        f"  requested v={limits.v_max:.2f} a={limits.a_max:.2f} j={limits.j_max:.1f}"
        f" -> carrying v={carrying.v_max:.2f} a={carrying.a_max:.2f} j={carrying.j_max:.1f}"
    )
    profile_bounds(0.25, carrying)

    print("\n== grasp attitude helpers (top-down / mirrored) ==")

    def _rot(q):
        w, x, y, z = (float(v) for v in q)
        return np.array(
            [
                [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
            ]
        )

    q_right = top_down_quaternion("x")
    q_left = mirror_across_xz(q_right)
    r_right = _rot(q_right)
    r_left = _rot(q_left)
    print(f"  right closes along {np.round(r_right[:, 1], 3).tolist()}, "
          f"fingers {np.round(r_right[:, 2], 3).tolist()}")
    print(f"  left  closes along {np.round(r_left[:, 1], 3).tolist()}, "
          f"fingers {np.round(r_left[:, 2], 3).tolist()}")
    check("top-down x closes the jaws along X", np.allclose(r_right[:, 1], [1, 0, 0], atol=1e-9))
    check("top-down x points the fingers straight down",
          np.allclose(r_right[:, 2], [0, 0, -1], atol=1e-9))
    check("the mirror stays a rotation (det = +1)", abs(np.linalg.det(r_left) - 1.0) < 1e-9)
    check("the mirror swaps the closing axis to -X on the left arm",
          np.allclose(r_left[:, 1], [-1, 0, 0], atol=1e-9))
    check("mirroring twice is the identity",
          np.allclose(_rot(mirror_across_xz(q_left)), r_right, atol=1e-9))

    print("\n== min-jerk jaw blend ==")
    ramp = min_jerk_ramp(0.09, 0.0314, 60)
    vel = np.diff(ramp) * 120.0
    acc = np.diff(vel) * 120.0
    linear = np.linspace(0.09, 0.0314, 61)[1:]
    linear_step = abs((linear[0] - 0.09) * 120.0)
    print(f"  jaw 0.090 -> 0.0314 m in 60 ticks: |v|max={np.abs(vel).max():.3f} m/s, "
          f"|a|max={np.abs(acc).max():.2f} m/s^2")
    print(f"  first-tick jaw speed: quintic {abs(vel[0]):.4f} m/s vs linear ramp "
          f"{linear_step:.4f} m/s")
    # The quintic is C2 (starts at zero velocity); only its *sampled* first step is
    # non-zero, so compare it against what the linear ramp does.
    check("jaw blend starts far more gently than a linear ramp",
          abs(vel[0]) < 0.2 * linear_step)

    print("\n== monitor on a synthetic carry ==")
    monitor = MotionMonitor("synthetic lift", mu_eff=mu_eff)
    pos, vel, acc = jerk_limited(0.25, carrying)
    for i, p in enumerate(pos):
        monitor.add(i * carrying.dt, [0.0, 0.0, 1.18 + float(p)], [0.0, 0.0, 1.18 + float(p) - 0.001])
    print("  " + MotionMonitor.format(monitor.summary()))

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed: {FAILURES}")
        return 1
    print("all motion checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
