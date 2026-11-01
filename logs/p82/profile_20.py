"""P82 profile build (I2): run the scripted line with the arbiter timers loaded.

    P82_TIMERS=logs/p82/R1.timers.json \\
      ATTEMPTS=20 SEED=5 FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 \\
      scripts/run.sh logs/p82/profile_20.py

This is **not** a shipped entry point. It installs `logs/p82/timers.py` (per-round
/ per-step wall timers at the `bimanual` arbiter boundary — never inside
`ik_step`) and then executes `scripts/20_pick_place.py` unchanged, so the physics,
the control loop, the supply and every print are the shipped ones. The timers
write JSON to `$P82_TIMERS` and never touch stdout, so the profiled run's log
stays byte-comparable with the canonical record — which is the admissibility test
(METHOD §3): a profiled run whose `[fruit]` stream matches the record has not
moved the run.

Why the module is executed with `run_name="p82_entry"` and `main()` called here
rather than through `run_path(..., run_name="__main__")`: the entry's `__main__`
block ends with `simulation_app.close()`, and this Kit build tears the process
down from C without running the interpreter's shutdown path, so an `atexit`
writer never fired (measured: the first smoke produced no JSON). Calling `main()`
here lets the summary be written **before** the app is closed, with the whole
`main()` span measured as well.
"""

from __future__ import annotations

import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)

import timers  # noqa: E402  (logs/p82/timers.py)

timers.install()

TARGET = os.path.join(ROOT, "scripts", "20_pick_place.py")
namespace = runpy.run_path(TARGET, run_name="p82_entry")

timers.mark_main_start()
code = namespace["main"]()
timers.mark_main_end()
timers.write()
namespace["simulation_app"].close()
raise SystemExit(code)
