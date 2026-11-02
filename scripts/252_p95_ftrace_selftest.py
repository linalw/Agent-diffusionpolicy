#!/usr/bin/env python3
"""P95 fruit-trace selftest (offline; a selfcheck leg).

Pins the shape of `FRUIT_FRUIT_TRACE=<max rows>` - the **selected fruit's
per-tick trace** - and of the two switches that ride it
(`FRUIT_FRUIT_TRACE_ARM`, `FRUIT_FRUIT_TRACE_NOOP`), without a simulator.

Why the instrument exists: P93 left one open item - a payload already at **2.4x
belt speed with 4.2-4.7 rad/s of spin when the descent leg starts** - and no
trace covered the wait/pre-pose window (`FRUIT_DYNAMIC_TRACE`'s first row *is*
the leg's start). P95 traced the whole attempt and found the kick: the *other*
arm's pads, 2 mm from the fruit's surface, at that arm's own pre-pose.

What this leg checks:

1. **The switch table.** Unset/empty/`0` = off; `1` = every tick (the documented
   "1 means unlimited" form); `N > 1` = a per-attempt cap of N. `_fruit_trace`'s
   factory is **None** (no attempt-local list is ever created on the shipped
   path) and the hook is one `if self._fruit_trace_on:` read in `_step_sim`.
2. **The hook is in `_step_sim`, never in `ik_step`** (AGENTS section 2: per-tick
   work inside `ik_step` moves the run even when it is two array copies).
3. **The default path is fruit-only.** The tick body's calls are to
   `spawner.position/velocity/angular` and `spawner.active` only; every
   articulation read (`jaw_positions`, `tcp_position`, `jaw_separation`) sits
   inside the `if self._fruit_trace_arm:` gate, and that gate is exactly one
   block.
4. **The no-op control arm.** `FRUIT_FRUIT_TRACE_NOOP=1` returns **before any
   readback** - the `rows.append(None)` site precedes the first `position(` call
   in the function - so it is the "same hook, same per-tick work, no reads"
   control the P-proximity probe used (`FRUIT_PROXIMITY_TRACE=2`, `logs/451`).
5. **Arming and flushing are single-sited**: one `self._fruit_trace = []` (with
   the sample), one `self._fruit_trace = None` in the flush, one call site in
   `_run_impl` and one in `note_result`; the trace is **attempt-local** (the
   two-line runs two attempts on two threads).
6. **The row shape, executed.** The real `_fruit_trace_tick` body runs on a stub
   task with two stub fruit: the row carries `phase/t/p/v/w/s/spin/belt/held/nb`,
   the neighbour filter is 0.15 m, neighbours sort nearest-first and cap at four,
   and the `arm` block appears only when the switch is on.
7. **The phase label is the existing cycle mark** (`self._cycle_marks[-1][0]`),
   so the table joins the `[cycle]` breakdown with no new bookkeeping, and the
   label is empty when `FRUIT_CYCLE_REPORT` is off.
8. **Off-path inertness**: nothing else in `tasks.py` reads the three knobs, and
   the flush is a no-op when nothing is armed.

Exit 0 on pass, 1 on the first failure.
"""
from __future__ import annotations

import re
import textwrap
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FAILS: list[str] = []
CHECKS = 0


def check(cond, msg: str) -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILS.append(msg)


def grab(src: str, name: str) -> str:
    """The whole `def name(...)` block, at whatever indent it lives (method or not)."""
    i = src.index(f"def {name}(")
    line_start = src.rfind("\n", 0, i) + 1
    indent = i - line_start
    out = []
    for line in src[i:].splitlines(keepends=True):
        if out and re.match(rf"^\s{{0,{indent}}}def ", line):
            break
        out.append(line)
    return "".join(out)


class StubFruit:
    """The fields `_fruit_trace_tick` reads off a `FruitSample`."""

    def __init__(self, index, pos, vel, omega, dia=0.06, mass=0.12, cat="kiwi"):
        self.index = index
        self.category = cat
        self.diameter = dia
        self.mass = mass
        self.position = np.asarray(pos, dtype=float)
        self.velocity_v = np.asarray(vel, dtype=float)
        self.omega = np.asarray(omega, dtype=float)
        self.parked = False
        self.attached = False
        self.held = False


class StubSpawner:
    def __init__(self, fruits):
        self.active = fruits
        self.belt = type("B", (), {"encoder_speed": -0.12})()

    def position(self, sample):
        return sample.position

    def velocity(self, sample):
        return sample.velocity_v

    def angular(self, sample):
        return sample.omega


class StubArm:
    def __init__(self, jaw):
        self._jaw = np.asarray(jaw, dtype=float)

    def jaw_positions(self):
        return self._jaw - [0.049, 0, 0], self._jaw + [0.049, 0, 0]

    def tcp_position(self):
        return self._jaw + [0, 0, 0.06]

    def jaw_separation(self):
        return 0.098


def main() -> int:
    src = (ROOT / "src/fruit_sorting/tasks.py").read_text(encoding="utf-8")

    # ------------------------------------------------------------------ 1
    # the switch table, read exactly as `__init__` reads it
    block = src[src.index('self._fruit_trace_on = max('):]
    block = block[: block.index('self._fruit_trace_noop')]
    check("FRUIT_FRUIT_TRACE" in block, "the knob is `FRUIT_FRUIT_TRACE`")
    check("> 0" in block, "the on-switch is `> 0` (unset/0/empty = off)")
    check("_ftrace_raw == 1" in block and "0 if" in block,
          "`1` means every tick (limit 0), `N > 1` a cap of N")
    check('_fruit_trace = _AttemptLocal("_fruit_trace")' in src,
          "`_fruit_trace` has no factory: no list is created unless an attempt arms it")
    check('_fruit_trace_sample = _AttemptLocal("_fruit_trace_sample")' in src,
          "the traced sample is attempt-local (the two-line runs two attempts at once)")
    check(src.count("self._fruit_trace_on = ") == 1,
          "the on-switch is resolved at exactly one site (`__init__`)")
    check(src.count("if self._fruit_trace_on:") == 3,
          "and read at three: the banner, `_step_sim`'s hook and `_run_impl`'s arming")

    # ------------------------------------------------------------------ 2
    step = grab(src, "_step_sim")
    check("if self._fruit_trace_on:" in step and "_fruit_trace_tick" in step,
          "the hook is in `_step_sim`")
    ik = grab(src, "ik_step") if "def ik_step(" in src else ""
    check("_fruit_trace" not in ik,
          "the hook is NOT inside `ik_step` (AGENTS section 2's per-tick rule)")
    hook = step[step.index("if self._fruit_trace_on:"):]
    check("_ftrace = self._fruit_trace" in hook and "_fruit_trace_tick(_ftrace)" in hook,
          "the hook is one attempt-local read plus one call")
    check(step.count("self._fruit_trace_tick(") == 1, "one hook call in `_step_sim`")

    # ------------------------------------------------------------------ 3
    tick = grab(src, "_fruit_trace_tick")
    gate_at = tick.index("if self._fruit_trace_arm:")
    body, gated = tick[:gate_at], tick[gate_at:]
    for call in ("jaw_positions", "tcp_position", "jaw_separation"):
        check(call in gated, f"{call} is inside the `_fruit_trace_arm` gate")
        check(call not in body, f"{call} does NOT appear on the fruit-only path")
    for call in ("spawner.position", "spawner.velocity", "spawner.angular", "spawner.active"):
        check(call in body, f"the fruit-only path reads {call}")
    check(gated.count("for name, hand in self.arms.items():") == 1,
          "one loop over the arms inside the gate")
    check('row["arm"] = arms' in gated, "the geometry rides the single `arm` key")

    # ------------------------------------------------------------------ 4
    noop_at = tick.index("if self._fruit_trace_noop:")
    check(noop_at < tick.index("spawner.position"),
          "the no-op arm returns before ANY readback (the instrument's control arm)")
    check("rows.append(None)" in tick[noop_at:noop_at + 200],
          "the no-op arm appends a placeholder and nothing else")

    # ------------------------------------------------------------------ 5
    check(src.count("self._fruit_trace = []") == 1, "one arming site")
    check(src.count("self._fruit_trace_sample = sample") == 1, "one sample-binding site")
    check(src.count("self._fruit_trace = None") == 1, "one disarm site (the flush)")
    check(src.count("self._fruit_trace_flush(result)") == 1,
          "the flush has one call site (`note_result`)")
    check("self._fruit_trace_flush(result)" in grab(src, "note_result"),
          "and it is in `note_result` (the attempt thread of both lines)")
    arm_site = src.index("self._fruit_trace = []")
    check("self._fruit_trace_sample = sample" in src[arm_site:arm_site + 400],
          "the sample is bound at the arming site")
    run_impl = grab(src, "_run_impl")
    check("self._fruit_trace = []" in run_impl,
          "armed in `_run_impl`, before the pre-pose (the window P93 could not see)")

    # ------------------------------------------------------------------ 6
    # execute the real tick body on stubs
    ns: dict = {"np": np, "os": __import__("os")}
    ns["say"] = lambda *a, **k: None
    exec(textwrap.dedent(tick), ns)  # noqa: S102 - pinned source
    tick_fn = ns["_fruit_trace_tick"]

    near = StubFruit(1, [0.25, 0.30, 1.20], [0.0, -0.12, 0.0], [0, 0, 0])
    far = StubFruit(2, [0.25, 0.80, 1.20], [0.0, -0.12, 0.0], [0, 0, 0])
    mid = StubFruit(3, [0.30, 0.34, 1.20], [0.01, -0.12, 0.0], [0, 0, 4.0])
    selected = StubFruit(0, [0.25, 0.32, 1.20], [0.0, -0.12, 0.0], [0, 0, 1.0])

    class Task:
        spawner = StubSpawner([selected, near, far, mid])
        arms = {"left": StubArm([0.34, 0.00, 1.30]), "right": StubArm([0.27, -0.10, 1.32])}
        _fruit_trace_sample = selected
        _fruit_trace_limit = 0
        _fruit_trace_arm = False
        _fruit_trace_noop = False
        _cycle_marks = [("start", 0.0), ("hover", 1.0)]

        @staticmethod
        def _sim_time():
            return 12.5

    rows: list = []
    tick_fn(Task(), rows)
    check(len(rows) == 1, "one row per call")
    row = rows[0]
    for key in ("phase", "t", "p", "v", "w", "s", "spin", "belt", "held", "nb"):
        check(key in row, f"the row carries `{key}`")
    check(row["phase"] == "hover", "the phase is the last cycle mark")
    check(row["t"] == 12.5, "`t` is the sim clock")
    check(abs(row["s"] - 0.12) < 1e-6, "`s` is |v|")
    check(abs(row["spin"] - 1.0) < 1e-6, "`spin` is |w|")
    check(row["belt"] == -0.12, "`belt` is the encoder speed (signed)")
    check("arm" not in row, "no arm block with the geometry switch off")
    idx = [n["i"] for n in row["nb"]]
    check(2 not in idx, "a fruit 0.48 m away is not a neighbour (0.15 m filter)")
    check(idx == [1, 3], f"neighbours are nearest-first ({idx})")
    check(all({"i", "cat", "d", "v", "s", "m", "dia"} <= set(n) for n in row["nb"]),
          "each neighbour carries index/category/offset/velocity/speed/mass/diameter")
    check(abs(row["nb"][0]["d"][1] + 20.0) < 1e-6,
          "the offset is in mm, neighbour minus the selected fruit (signed)")

    Task._cycle_marks = None
    rows2 = []
    tick_fn(Task(), rows2)
    check(rows2[0]["phase"] == "", "no cycle report -> empty phase (not an error)")

    Task._fruit_trace_arm = True
    rows3 = []
    tick_fn(Task(), rows3)
    arm = rows3[0]["arm"]
    check(set(arm) == {"left", "right"}, "with the switch on both arms are recorded")
    check({"jaw", "d_jaw", "d_tcp", "d_f0", "d_f1", "sep"} == set(arm["left"]),
          "the arm block carries jaw/tcp/finger distances and the measured span")
    check(arm["left"]["sep"] == 98.0, "`sep` is millimetres")

    Task._fruit_trace_arm = False
    Task._fruit_trace_noop = True
    rows4 = []
    tick_fn(Task(), rows4)
    check(rows4 == [None], "the no-op arm appends a bare placeholder")

    Task._fruit_trace_noop = False
    Task._fruit_trace_limit = 2
    rows5 = []
    for _ in range(4):
        tick_fn(Task(), rows5)
    check(len(rows5) == 2, "the cap stops the trace at N rows")

    # ------------------------------------------------------------------ 7/8
    flush = grab(src, "_fruit_trace_flush")
    check("FRUIT_FRUIT_TRACE_DIR" in flush, "the output dir is overridable per cell")
    check("os.makedirs(out_dir, exist_ok=True)" in flush, "the dir is created on demand")
    check('"[ftrace] attempt' in flush, "one summary row per attempt (the report's table)")
    check("if rows is None:" in flush and "return" in flush,
          "the flush is a no-op when nothing is armed")
    check(flush.index("if rows is None:") < flush.index("os.makedirs"),
          "the no-op check precedes any filesystem work")
    check("left_belt_at" in flush, "the summary names the belt-departure tick")
    check(src.count('os.environ.get("FRUIT_FRUIT_TRACE_ARM"') == 1
          and src.count('os.environ.get("FRUIT_FRUIT_TRACE_NOOP"') == 1,
          "each switch is read exactly once")
    env_names = re.findall(r'os\.environ\.get\("(FRUIT_FRUIT_TRACE[A-Z_]*)"', src)
    check(sorted(set(env_names)) == ["FRUIT_FRUIT_TRACE", "FRUIT_FRUIT_TRACE_ARM",
                                     "FRUIT_FRUIT_TRACE_DIR", "FRUIT_FRUIT_TRACE_NOOP"],
          f"the instrument owns exactly these env names ({sorted(set(env_names))})")

    if FAILS:
        print(f"FAIL: {len(FAILS)} of {CHECKS} checks")
        for msg in FAILS:
            print(f"  - {msg}")
        return 1
    print(f"PASS: {CHECKS} checks (FRUIT_FRUIT_TRACE instrument shape)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
