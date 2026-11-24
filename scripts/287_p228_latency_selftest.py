#!/usr/bin/env python3
"""P228 (Stage 0) selfcheck leg: `FRUIT_EVAL_LATENCY`.

Pins, offline:

1. the resolver table - unset/`""`/`0` off, `auto`, a positive integer, and a
   hard error on a negative, non-numeric, non-finite or fractional value (a typo
   must not read as "off");
2. the control period - `rl_env.CONTROL_DT` equals the literal `tasks.py`
   carries as `CONTROL_DT`. This module cannot import `tasks` at module scope
   (it pulls Isaac Sim in) and this leg runs without a simulator, so the pin is
   on the source text;
3. the injector **executed** on a stub: `d` ticks advanced one at a time, each
   with `enforce_transport`, `_tick`/`_step` moved with the physics, and
   **nothing observed or recorded** (the observation must stay at `t_obs` - a
   real deployment cannot see the frames it did not wait for);
4. a decision that did not call the model (a held/gated chunk) pays nothing;
5. `auto` converts the measured wall (26.4 ms at DDIM-16 -> 3 ticks);
6. the call site sits in `act()` **before** the execution loop, and the RTC
   combination is refused (the chunker already models the same delay).

    python3 scripts/287_p228_latency_selftest.py
"""
from __future__ import annotations

import os
import re
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fruit_sorting import rl_env  # noqa: E402


def main() -> int:
    R = rl_env.resolve_eval_latency
    assert R(None) == ("off", 0)
    assert R("") == ("off", 0)
    assert R("0") == ("off", 0)
    assert R("auto") == ("auto", 0)
    assert R(" AUTO ") == ("auto", 0)
    assert R("4") == ("fixed", 4)
    for bad in ("-1", "abc", "nan", "inf", "1.5", "4ms"):
        try:
            R(bad)
        except ValueError:
            continue
        raise AssertionError(f"FRUIT_EVAL_LATENCY={bad!r} must be refused")

    # (2) the period, pinned against tasks.py's own literal
    root = os.path.join(os.path.dirname(__file__), "..")
    tasks = open(os.path.join(root, "src/fruit_sorting/tasks.py"), encoding="utf-8").read()
    m = re.search(r"^CONTROL_DT = 1\.0 / (\d+\.?\d*)$", tasks, re.M)
    assert m, "tasks.py no longer carries `CONTROL_DT = 1.0 / <n>`"
    assert abs(rl_env.CONTROL_DT - 1.0 / float(m.group(1))) < 1e-12, (
        "the env's control period drifted from tasks.py's"
    )

    # (3) the injector, executed on a stub
    o = object.__new__(rl_env.SortingRLEnv)
    o._eval_latency_mode, o._eval_latency_ticks = "fixed", 3
    o._infer_this_decision = True
    o._last_infer_ms = 26.4
    o._done = False
    o._tick, o._step = 10, 40
    o._lat_decisions = o._lat_ticks = o._lat_max = 0

    class _Spawner:
        n = 0

        def enforce_transport(self) -> None:
            _Spawner.n += 1

    o.spawner = _Spawner()
    # the row's displacement field reads the cell's own belt speed
    o.cfg = types.SimpleNamespace(belt_speed=0.12)
    advanced: list[int] = []
    said: list[str] = []
    o.advance = lambda n: advanced.append(int(n))
    o._say = lambda s: said.append(s)
    o._observe = lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("the latency pause must not observe")
    )
    o._record_tick = lambda: (_ for _ in ()).throw(
        AssertionError("the latency pause must not record (no action is applied)")
    )

    o._inject_latency()
    assert advanced == [1, 1, 1], advanced
    assert (o._tick, o._step) == (13, 43), (o._tick, o._step)
    assert _Spawner.n == 3, _Spawner.n
    assert (o._lat_ticks, o._lat_max, o._lat_decisions) == (3, 3, 1)
    assert said and said[-1].startswith("[lat] d=3 "), said
    assert "belt_mm=3.0" in said[-1], said[-1]  # 0.12 m/s x 3 ticks = 3 mm

    # (4) no model call, no delay
    o._infer_this_decision = False
    advanced.clear()
    o._inject_latency()
    assert advanced == [], "a held/gated chunk must not pay the inference delay"

    # (5) auto: the measured wall / the control period (on a decision that *did*
    # call the model - the previous check left the flag False)
    o._infer_this_decision = True
    o._eval_latency_mode = "auto"
    assert o._latency_ticks_for_decision() == 3, o._latency_ticks_for_decision()

    # (6) the call site and the refusal
    src = open(os.path.join(root, "src/fruit_sorting/rl_env.py"), encoding="utf-8").read()
    assert "self._inject_latency()" in src
    i = src.index("    def act(")
    j = src.index("        self._inject_latency()", i)
    assert j < src.index("        for index in range(steps):", i), (
        "the latency must land after the observation and before the first action"
    )
    assert "cannot be combined with FRUIT_RTC" in src
    # an evaluation lever must not silently corrupt a training store
    assert "FRUIT_EVAL_LATENCY is an evaluation lever and cannot be combined" in src
    print("P228 eval latency: ok (d advances the world; no observation, no recording)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
