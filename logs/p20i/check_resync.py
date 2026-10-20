#!/usr/bin/env python3
"""P20-C stub check: the B1c feeder re-anchor (`FRUIT_READY_SKIP_RESYNC`), offline.

Tier-C-level implementation evidence - NOT a substitute for the pre-registered
Tier-A battery (`logs/p20/B1C_DESIGN.md` section 5; the battery is a separate
lane and needs the simulator). Layers:

1. Source checks: the knob is read exactly once (default `"0"`, in `__init__`);
   the P9-A knobs keep one read each; the two helpers are defined exactly once;
   the credit is inside the *skip* branch, after the placebo hold, exactly once;
   the `[ready]` credit suffix is gated on the flag while the P9-A field string
   is untouched (knob-off byte identity); the class constants match the stage
   lengths the real call sites use (`_transit_to` `ticks=90`, `_catch_up_drive`
   `ticks=20` and its `gap <= 0.01` early-out). `fruits.py` gains **no**
   `_supply_shift` / `advance_supply_clock` (the design's four-site form is
   absent, so the offset cannot be applied twice), and the schedule cursor
   `_next_release` is still only written by the shipped sites (AST).
2. Knob resolution: the REAL `__init__` assignment is exec'd over env states.
3. The debit arithmetic: the REAL `_ready_transit_ticks` is exec'd over the
   `dg` band the battery runs at (`FRUIT_READY_SKIP_DG=0.02`, where
   `_catch_up_drive`'s 20-tick ramp is present iff `dg > 0.01`) plus the settle
   override, against an independent reference. The design's flat
   `20 + 90 + settle` is shown to over-credit by 20 ticks on the `dg <= 0.01`
   rows - the code-level deviation.
4. The credit: the REAL `_resync_supply_clock` over a fake spawner - knob off
   returns 0 and never touches the spawner (a raising mock proves it); knob on
   moves `_next_release` by exactly `ticks/120` s and accumulates exactly;
   `ticks <= 0`, an absent spawner, and a non-pump (fixed-line) supply credit
   nothing.
5. End-to-end at the skip site: the REAL `debt = ...` assignment and the REAL
   `if debt > 0:` block are exec'd with a fake task and the real methods -
   credited exactly once per skip, `FRUIT_READY_SKIP_HOLD` cancels one-for-one
   (the placebo credits zero), the cumulative readout is the integer sum.
6. The re-anchor itself, against a faithful model of `_pump_supply`'s schedule
   algebra (`while sim_time >= _next_release`, `late = sim_time - _next_release`,
   `along = spawn_y - late*v`, the `pick_y + 0.10` floor drop, `burst_max`) on
   the shipped gap band, pumped at the attempt boundaries a skipping single arm
   produces:
   * control (shipped clock) vs re-anchored (cursor form, through the REAL
     `_resync_supply_clock`) -> identical `late`/`along` streams, identical
     due / released / past counts and gap-draw consumption;
   * the design's `_supply_shift` form -> identical to the cursor form (the
     algebraic equivalence the implementation relies on);
   * un-anchored lever -> a different stream, and the virtual pump clock sits
     `(k+1) * 230` ticks behind the control at slot `k` = 0.23 m of belt per
     gap, 1.84 m by slot 8 (the cumulative debt the re-anchor zeroes).

Run:  python3 logs/p20i/check_resync.py
Exit code 0 = all checks PASS.
"""

from __future__ import annotations

import ast
import hashlib
import math
import os
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TASKS = ROOT / "src" / "fruit_sorting" / "tasks.py"
FRUITS = ROOT / "src" / "fruit_sorting" / "fruits.py"
RL_ENV = ROOT / "src" / "fruit_sorting" / "rl_env.py"

failures: list[str] = []


def check(label: str, ok: bool) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def find_def(tree: ast.Module, name: str) -> ast.FunctionDef:
    hits = [
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name
    ]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one def {name}, found {len(hits)}")
    return hits[0]


def compile_defs(names: list[str], namespace: dict) -> None:
    """Exec the named defs (decorators stripped) out of tasks.py."""
    body = []
    for name in names:
        node = find_def(TREE, name)
        node.decorator_list = []
        body.append(node)
    exec(compile(ast.Module(body=body, type_ignores=[]), str(TASKS), "exec"), namespace)  # noqa: S102


def default_of(fn: ast.FunctionDef, arg: str):
    args = fn.args.args
    defaults = fn.args.defaults
    offset = len(args) - len(defaults)
    for index, node in enumerate(args):
        if node.arg == arg and index >= offset:
            return ast.literal_eval(defaults[index - offset])
    return "<missing>"


def class_constant(name: str):
    for node in ast.walk(TREE):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    return "<missing>"


# --------------------------------------------------------------------------- #
# The schedule model: `FruitSpawner._pump_supply`'s scattered path.
# --------------------------------------------------------------------------- #
class Feeder:
    """`_pump_supply`'s schedule algebra, with the two compensation forms.

    `shift` is the design's `advance_supply_clock` form (`t = sim_time +
    _supply_shift` at the four schedule sites). Leaving `shift` at 0 and letting
    `_next_release` carry the offset (the implemented cursor form) is the same
    algebra with `t = sim_time` - which is what the equivalence check proves.
    """

    def __init__(self, gaps, *, spawn_y=0.68, speed=0.12, pick_y=0.0, burst_max=6):
        self._next_release = 0.0
        self.shift = 0.0
        self.gaps = list(gaps)
        self.drawn = 0
        self.spawn_y = spawn_y
        self.speed = speed
        self.floor = pick_y + 0.10
        self.burst_max = burst_max
        self.rows = []  # (late, along, pump virtual time) per released slot
        self.counts = []  # (due, released, past) per pump
        self.lates = []  # every due slot's lateness

    @property
    def supply(self):
        return type("Supply", (), {"scatter": True, "stream": True})()

    def period(self) -> float:
        gap = self.gaps[self.drawn]
        self.drawn += 1
        return gap / self.speed

    def pump(self, sim_time: float):
        released = due = past = 0
        t = sim_time + self.shift
        while t >= self._next_release and released < self.burst_max:
            due += 1
            per = self.period()
            late = t - self._next_release
            along = self.spawn_y - min(late * self.speed, 1.60)
            self._next_release += per
            self.lates.append(late)
            if along < self.floor:
                past += 1
                continue
            released += 1
            self.rows.append((late, along, t))
        self.counts.append((due, released, past))
        return self.counts[-1]


class Edge:
    """The spawner surface `_resync_supply_clock` reads, plus the cursor."""

    def __init__(self, cursor=0.0, scatter=True, stream=True):
        self._next_release = cursor
        self.supply = type("Supply", (), {"scatter": scatter, "stream": stream})()


class RaisingSpawner:
    """Any attribute touch is a failure (the knob-off byte-inert proof)."""

    def __getattr__(self, name):  # pragma: no cover - only on a regression
        raise AssertionError(f"spawner.{name} touched with the knob off")


class FakeTask:
    """The `self` the two real helpers run against."""

    def __init__(self, resync: bool, spawner):
        self._ready_skip_resync = resync
        self._ready_skip_credit = 0
        self.spawner = spawner


TREE = ast.parse(TASKS.read_text(encoding="utf-8"))


def main() -> int:
    source = TASKS.read_text(encoding="utf-8")
    fruits_source = FRUITS.read_text(encoding="utf-8")
    rl_source = RL_ENV.read_text(encoding="utf-8")

    print("== source checks ==")
    check(
        'FRUIT_READY_SKIP_RESYNC is read exactly once, default "0"',
        source.count('os.environ.get("FRUIT_READY_SKIP_RESYNC"') == 1
        and 'os.environ.get("FRUIT_READY_SKIP_RESYNC", "0") == "1"' in source,
    )
    check(
        "the P9-A knobs keep one read each (SKIP / SKIP_DG / SKIP_HOLD / SETTLE)",
        source.count('os.environ.get("FRUIT_READY_SKIP"') == 1
        and source.count('os.environ.get("FRUIT_READY_SKIP_DG"') == 1
        and source.count('os.environ.get("FRUIT_READY_SKIP_HOLD"') == 1
        and source.count('os.environ.get("FRUIT_READY_SETTLE"') == 1,
    )
    check(
        "the two helpers are defined exactly once",
        source.count("def _ready_transit_ticks(") == 1
        and source.count("def _resync_supply_clock(") == 1,
    )
    check(
        "the cumulative-credit accumulator starts at 0",
        "self._ready_skip_credit = 0" in source,
    )
    check(
        "the debit is `_ready_transit_ticks(dg) - max(0, hold)`, exactly once, "
        "inside the knob guard",
        source.count("debt = self._ready_transit_ticks(dg) - max(0, hold)") == 1
        and source.count("if self._ready_skip_resync:") == 1,
    )
    skip_at = source.index("if skip and err <= self.READY_SKIP_TOL")
    transit_at = source.index("        self._transit_to(", skip_at)
    block = source[skip_at:transit_at]
    check(
        "the credit sits inside the skip branch, after the placebo hold, once",
        block.index("for _ in range(max(0, hold)):")
        < block.index("if self._ready_skip_resync:")
        < block.index("debt = self._ready_transit_ticks(dg)")
        < block.index("self._resync_supply_clock(debt)")
        < block.index("return stats"),
    )
    check(
        "the credit is added to the cumulative readout exactly once",
        source.count("self._ready_skip_credit += int(ticks)") == 1,
    )
    check(
        "the [ready] credit suffix is gated on the knob; the P9-A fields intact",
        'f" credit={int(self._ready_skip_credit)}"' in source
        and "if self._ready_skip_resync" in source
        and "f\"rec={stats['rec']} end_err={stats['end_err']:.4f}\"" in source,
    )
    for const, value in (
        ("READY_TRANSIT_BLEND_TICKS", 90),
        ("READY_CATCH_UP_TICKS", 20),
        ("READY_CATCH_UP_TOL", 0.01),
    ):
        got = class_constant(const)
        check(f"{const} == {value} (got {got!r})", got == value)
    check(
        "the constants still match the real call-site defaults "
        "(`_transit_to` ticks=90, `_catch_up_drive` ticks=20)",
        default_of(find_def(TREE, "_transit_to"), "ticks") == 90
        and default_of(find_def(TREE, "_catch_up_drive"), "ticks") == 20,
    )
    check(
        "`_catch_up_drive`'s no-op early-out is still the literal `gap <= 0.01`",
        "if gap <= 0.01:\n            return False" in source,
    )
    check(
        "fruits.py gains no `_supply_shift` / `advance_supply_clock` "
        "(the design form is absent - no double credit)",
        "_supply_shift" not in fruits_source
        and "advance_supply_clock" not in fruits_source,
    )
    enclosing = sorted(
        {
            fn.name
            for fn in ast.walk(ast.parse(fruits_source))
            if isinstance(fn, ast.FunctionDef)
            for node in ast.walk(fn)
            if isinstance(node, (ast.Assign, ast.AugAssign))
            and any(
                isinstance(tgt, ast.Attribute)
                and tgt.attr == "_next_release"
                and isinstance(tgt.value, ast.Name)
                and tgt.value.id == "self"
                for tgt in (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
            )
        }
    )
    check(
        f"the schedule cursor is only written by the shipped sites ({enclosing})",
        enclosing == ["__init__", "_pump_supply", "reset", "update"],
    )
    check(
        "the pump's four schedule sites are still on `sim_time` "
        "(so the cursor offset is the whole re-anchor)",
        "while sim_time >= self._next_release and len(released) "
        "< self.supply.burst_max:" in fruits_source
        and "late = float(sim_time) - float(self._next_release)" in fruits_source
        and "self._next_release = max(self._next_release, sim_time + period)"
        in fruits_source
        and "self._next_release = max(\n                    self._next_release, "
        "sim_time + self._release_period()" in fruits_source,
    )

    print("== knob resolution (the REAL __init__ statement) ==")
    assign = next(
        node
        for node in ast.walk(TREE)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(t, ast.Attribute) and t.attr == "_ready_skip_resync"
            for t in node.targets
        )
    )
    assign_mod = compile(ast.Module(body=[assign], type_ignores=[]), str(TASKS), "exec")
    for value, expected in [
        (None, False),
        ("0", False),
        ("1", True),
        ("true", False),  # only the literal "1" arms it (the P9-A convention)
        ("yes", False),
    ]:
        saved = os.environ.get("FRUIT_READY_SKIP_RESYNC")
        if value is None:
            os.environ.pop("FRUIT_READY_SKIP_RESYNC", None)
        else:
            os.environ["FRUIT_READY_SKIP_RESYNC"] = value
        fake = type("Fake", (), {})()
        exec(assign_mod, {"os": os}, {"self": fake})  # noqa: S102
        if saved is None:
            os.environ.pop("FRUIT_READY_SKIP_RESYNC", None)
        else:
            os.environ["FRUIT_READY_SKIP_RESYNC"] = saved
        check(
            f"env {value!r} -> _ready_skip_resync={fake._ready_skip_resync} "
            f"(expected {expected})",
            fake._ready_skip_resync is expected,
        )

    # The real helpers, bound onto the fake task class.
    control_dt = eval(  # noqa: S307 - this file's own literal, read from tasks.py
        compile(
            ast.Expression(
                next(
                    node.value
                    for node in TREE.body
                    if isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "CONTROL_DT"
                            for t in node.targets)
                )
            ),
            str(TASKS),
            "eval",
        )
    )
    ns: dict = {"os": os, "CONTROL_DT": control_dt}
    compile_defs(["_ready_settle", "_ready_transit_ticks", "_resync_supply_clock"], ns)
    FakeTask.READY_TRANSIT_BLEND_TICKS = class_constant("READY_TRANSIT_BLEND_TICKS")
    FakeTask.READY_CATCH_UP_TICKS = class_constant("READY_CATCH_UP_TICKS")
    FakeTask.READY_CATCH_UP_TOL = class_constant("READY_CATCH_UP_TOL")
    FakeTask._ready_settle = ns["_ready_settle"]
    FakeTask._ready_transit_ticks = ns["_ready_transit_ticks"]
    FakeTask._resync_supply_clock = ns["_resync_supply_clock"]
    check(
        f"CONTROL_DT is {control_dt!r} s (120 Hz)",
        abs(control_dt - 1.0 / 120.0) < 1e-15,
    )

    print("== the debit arithmetic (the REAL _ready_transit_ticks) ==")

    def reference(dg: float, settle: int) -> int:
        catch_up = 20 if dg > 0.01 else 0
        return catch_up + 90 + settle

    rows = [
        # (dg, FRUIT_READY_SETTLE, expected ticks)
        (0.0004, None, 210),  # the measured no-op residual: no catch-up ramp
        (0.01, None, 210),  # exactly at `_catch_up_drive`'s early-out
        (0.0101, None, 230),  # one tick past it: the 20-tick ramp returns
        (0.0131, None, 230),  # the measured j1 residual (`logs/610`)
        (0.0135, None, 230),  # the B1 battery's steady `dg` (DG=0.02)
        (0.02, None, 230),  # the battery's tolerance edge
        (0.0135, "60", 170),  # the B2 settle override rides along
        (0.0004, "60", 150),
    ]
    for dg, settle, expected in rows:
        saved = os.environ.get("FRUIT_READY_SETTLE")
        if settle is None:
            os.environ.pop("FRUIT_READY_SETTLE", None)
        else:
            os.environ["FRUIT_READY_SETTLE"] = settle
        task = FakeTask(False, None)
        got = task._ready_transit_ticks(dg)
        ref = reference(dg, int(settle) if settle else 120)
        if saved is None:
            os.environ.pop("FRUIT_READY_SETTLE", None)
        else:
            os.environ["FRUIT_READY_SETTLE"] = saved
        check(
            f"dg={dg} settle={settle or 120} -> {got} ticks "
            f"(reference {ref}, {got / 120.0:.3f} s of belt)",
            got == ref == expected,
        )
    design = 20 + 90 + 120
    check(
        "the design's flat `20 + 90 + settle` = 230 is exact only for dg > 0.01 "
        f"(it over-credits the dg<=0.01 rows by {design - 210} ticks)",
        design == 230 and FakeTask(False, None)._ready_transit_ticks(0.0004) == 210,
    )

    print("== the credit (the REAL _resync_supply_clock) ==")
    off = FakeTask(False, RaisingSpawner())
    got = off._resync_supply_clock(230)
    check("knob off: returns 0 and never touches the spawner", got == 0)
    check("knob off: the cumulative readout stays 0", off._ready_skip_credit == 0)

    edge = Edge(cursor=12.345)
    task = FakeTask(True, edge)
    before = edge._next_release
    check("knob on: the call reports the ticks credited", task._resync_supply_clock(230) == 230)
    check(
        "knob on: the cursor moves by exactly 230 * CONTROL_DT s",
        abs((before - edge._next_release) - 230 * control_dt) < 1e-15,
    )
    check("knob on: the cumulative readout is the tick count", task._ready_skip_credit == 230)
    task._resync_supply_clock(210)
    check(
        "a second skip accumulates exactly (230 + 210 = 440 ticks)",
        task._ready_skip_credit == 440
        and abs((before - edge._next_release) - 440 * control_dt) < 1e-15,
    )
    check("ticks <= 0 credits nothing", task._resync_supply_clock(0) == 0
          and task._resync_supply_clock(-5) == 0 and task._ready_skip_credit == 440)
    check(
        "an absent spawner credits nothing",
        FakeTask(True, None)._resync_supply_clock(230) == 0,
    )
    fixed = FakeTask(True, Edge(scatter=False))
    fixed_before = fixed.spawner._next_release
    check(
        "the fixed (non-pump) line credits nothing and keeps its cursor",
        fixed._resync_supply_clock(230) == 0
        and fixed.spawner._next_release == fixed_before,
    )
    nostream = FakeTask(True, Edge(stream=False))
    check(
        "`stream=False` (no pump) credits nothing",
        nostream._resync_supply_clock(230) == 0,
    )

    print("== the skip site (the REAL debt block, exec'd) ==")
    ready_move = find_def(TREE, "_ready_move")
    debt_if = next(
        node
        for node in ast.walk(ready_move)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Attribute)
        and node.test.attr == "_ready_skip_resync"
    )
    site_mod = compile(
        ast.Module(body=[debt_if], type_ignores=[]), str(TASKS), "exec"
    )

    def skip_site(resync: bool, dg: float, hold: int, repeats: int = 1):
        feeder = Feeder([0.2] * 50)
        task = FakeTask(resync, feeder)
        if not resync:
            # the knob-off byte-inert proof: any call here is a failure
            def boom(*_args, **_kwargs):  # pragma: no cover - regression only
                raise AssertionError("the re-anchor ran with the knob off")

            task._ready_transit_ticks = boom
            task._resync_supply_clock = boom
        error = None
        for _ in range(repeats):
            try:
                exec(site_mod, {}, {"self": task, "dg": dg, "hold": hold})  # noqa: S102
            except AssertionError as exc:  # pragma: no cover - regression only
                error = str(exc)
                break
        return task, feeder, error

    task, feeder, _err = skip_site(True, 0.0135, 0)
    check(
        "knob on, HOLD=0: one skip credits 230 ticks exactly once",
        task._ready_skip_credit == 230
        and abs(feeder._next_release + 230 * control_dt) < 1e-15,
    )
    task, feeder, _err = skip_site(True, 0.0135, 230)
    check(
        "the placebo (HOLD=230) cancels the debt one-for-one: 0 ticks, cursor intact",
        task._ready_skip_credit == 0 and feeder._next_release == 0.0,
    )
    task, feeder, _err = skip_site(True, 0.0135, 100)
    check(
        "a partial hold credits the remainder (230 - 100 = 130)",
        task._ready_skip_credit == 130,
    )
    task, feeder, _err = skip_site(True, 0.0004, 0)
    check(
        "a skip with dg <= 0.01 credits 210 (no catch-up ramp was removed)",
        task._ready_skip_credit == 210,
    )
    task, feeder, _err = skip_site(True, 0.0135, 0, repeats=5)
    check(
        "five skips credit 5 * 230 = 1150 ticks, no drift",
        task._ready_skip_credit == 1150
        and abs(feeder._next_release + 1150 * control_dt) < 1e-15,
    )
    task, feeder, error = skip_site(False, 0.0135, 0, repeats=5)
    check(
        "knob off at the site: no credit, the cursor untouched, neither helper "
        f"called (byte-inert; error={error!r})",
        error is None
        and task._ready_skip_credit == 0
        and feeder._next_release == 0.0,
    )

    print("== the re-anchor end-to-end (schedule model, shipped gap band) ==")
    D = 230 * control_dt
    SLOTS = 10
    spacing = 18.5
    rng = random.Random(11)
    gaps = [rng.uniform(0.10, 0.35) for _ in range(400)]

    control = Feeder(gaps)
    anchored = Feeder(gaps)
    shiftform = Feeder(gaps)
    unanchored = Feeder(gaps)
    anchored_task = FakeTask(True, anchored)
    credits: list[int] = []
    skip_times: list[float] = []
    for slot in range(SLOTS):
        t_control = 30.0 + spacing * slot
        t_skip = t_control - (slot + 1) * D
        control.pump(t_control)
        # the implemented form: the credit is applied at the ready skip, then
        # the driver pumps at the *shorter* attempt boundary.
        anchored_task._resync_supply_clock(230)
        credits.append(anchored_task._ready_skip_credit)
        skip_times.append(t_skip)
        anchored.pump(t_skip)
        # the design's form: the same ticks as a shift on the pump clock.
        shiftform.shift = (slot + 1) * D
        shiftform.pump(t_skip)
        unanchored.pump(t_skip)

    def streams_equal(a: Feeder, b: Feeder) -> bool:
        if len(a.rows) != len(b.rows) or a.counts != b.counts or a.drawn != b.drawn:
            return False
        return all(
            math.isclose(x[0], y[0], abs_tol=1e-9)
            and math.isclose(x[1], y[1], abs_tol=1e-9)
            for x, y in zip(a.rows, b.rows)
        )

    got = anchored_task._ready_skip_credit
    check(
        f"10 skips credit 10 * 230 = 2300 ticks ({got} read back)",
        got == 10 * 230,
    )
    check(
        "control vs re-anchored: identical due/released/past per pump "
        f"({control.counts == anchored.counts}, {len(control.rows)} released slots)",
        control.counts == anchored.counts,
    )
    check(
        "control vs re-anchored: identical late/along streams "
        f"({len(control.rows)} slots, {control.drawn} gaps drawn)",
        streams_equal(control, anchored),
    )
    check(
        "the design's shift form is identical to the cursor form (the deviation "
        "is algebraic, not behavioural)",
        streams_equal(shiftform, anchored),
    )
    check(
        "the un-anchored lever is NOT the control stream (the mechanism fires)",
        not streams_equal(control, unanchored),
    )
    virtual = [t + c * control_dt for t, c in zip(skip_times, credits)]
    check(
        "the re-anchored pump instant equals the control's at every slot "
        "(virtual clock invariant, max |delta| = "
        f"{max(abs(v - (30.0 + spacing * s)) for s, v in enumerate(virtual)):.2e} s)",
        all(
            abs(v - (30.0 + spacing * slot)) < 1e-9
            for slot, v in enumerate(virtual)
        ),
    )
    debt_m = [round((slot + 1) * 230 * control_dt * 0.12, 3) for slot in range(SLOTS)]
    check(
        f"the cumulative debt is 0.23 m/gap and reaches {debt_m[7]:.2f} m at "
        f"slot 7 (the design's 1.84 m by slot 8): {debt_m}",
        abs(debt_m[0] - 0.23) < 1e-9 and abs(debt_m[7] - 1.84) < 1e-9,
    )

    print("== pins ==")
    live = hashlib.md5(TASKS.read_bytes()).hexdigest()
    pin = None
    for line in rl_source.splitlines():
        if line.startswith("TASKS_MD5 = "):
            pin = line.split('"')[1]
    check(f"rl_env TASKS_MD5 == live tasks.py md5 ({live})", pin == live)
    print(f"    tasks.py md5 {live}")
    print(f"    fruits.py md5 {hashlib.md5(FRUITS.read_bytes()).hexdigest()}")
    print(f"    rl_env.py md5 {hashlib.md5(RL_ENV.read_bytes()).hexdigest()}")

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} check(s) failed)")
        return 1
    print("RESULT: PASS (all checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
