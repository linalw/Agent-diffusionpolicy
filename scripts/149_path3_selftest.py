"""Offline selftest for the path-3 event-triggered replanning rule.

The method `SortingRLEnv._event_horizon` is pure bookkeeping over two action
chunks; the simulator is not needed. This pins the pre-registered rule
(`logs/path3/PREREGISTRATION.md`): the online median `m` of the chunk-to-chunk
continuity sets `hi = 1.5 m`, `lo = 0.5 m`; continuity >= hi -> min horizon,
<= lo -> max horizon, otherwise the default; consecutive chunks compare new
index `i` with previous index `prev_exec + i` on the 7 arm channels.
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from fruit_sorting.rl_env import SortingRLEnv  # noqa: E402


def _bare_env() -> SortingRLEnv:
    env = object.__new__(SortingRLEnv)
    env._event_min = 2
    env._event_max = 6
    env._event_default = 4
    env._prev_chunk = None
    env._prev_exec = 0
    env._event_continuities = []
    env._event_horizons = []
    env._step = 0
    env._say = lambda *args, **kwargs: None  # type: ignore[method-assign]
    return env


def main() -> int:
    failures: list[str] = []
    env = _bare_env()

    # No previous chunk: default horizon, no continuity recorded.
    if env._event_horizon(None) != 4:
        failures.append("first chunk (None) should use the default horizon")
    if env._event_continuities:
        failures.append("no continuity should be recorded without a previous chunk")

    prev = np.zeros((16, 9), dtype=np.float64)
    env._prev_chunk = prev
    env._prev_exec = 2
    env._event_continuities = [1e-3] * 12
    new = np.zeros((16, 9), dtype=np.float64)
    # new[i] and prev[2+i] are the same absolute step; displace the arms.
    new[:6, :7] = 0.05  # ||0.05 * 7|| = 0.132 -> well above 1.5 * 1e-3
    if env._event_horizon(new) != 2:
        failures.append("high continuity must shorten the horizon to the minimum")
    env._prev_chunk = prev
    env._prev_exec = 2
    env._event_continuities = [0.05] * 12
    new = np.zeros((16, 9), dtype=np.float64)
    new[:6, :7] = 1e-4  # ~2.6e-4 << 0.5 * 0.05
    if env._event_horizon(new) != 6:
        failures.append("low continuity must extend the horizon to the maximum")
    env._prev_chunk = prev
    env._prev_exec = 2
    env._event_continuities = [0.02] * 12
    new = np.zeros((16, 9), dtype=np.float64)
    new[:6, :7] = 0.01  # 0.026 inside [0.01, 0.03] -> default
    if env._event_horizon(new) != 4:
        failures.append("mid continuity must keep the default horizon")
    # Overlap bound: prev_exec near the end of the previous chunk.
    env._prev_chunk = prev
    env._prev_exec = 15
    env._event_continuities = [0.02]
    if env._event_horizon(new) != 4:
        failures.append("no overlap must fall back to the default horizon")
    # The histories are exposed for reporting.
    if not env._event_horizons or not env._event_continuities:
        failures.append("horizon/continuity histories must be recorded")

    if failures:
        print("path3 event selftest FAIL")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("path3 event selftest PASS (median rule, bounds, alignment bookkeeping)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
