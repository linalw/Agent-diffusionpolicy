#!/usr/bin/env python3
"""P17-B stub check: the capture-side levers (H1 the slide gate + H2 the
two-sided freeze gate), offline.

Tier-C-level implementation evidence - NOT a substitute for the pre-registered
Stage-M screen (`logs/p17/CAPTURE_LEVER_DESIGN.md` section 4; the screen is a
separate lane and needs the simulator). Layers:

1. Source checks: the eleven knobs are read exactly once each with the shipped
   defaults; the six H1 helpers and the three H2 helpers are defined exactly
   once; the call sites (hold + probe-1 target/tick/phase, the freeze commit +
   the horizon fallback) are the gated ones; the row helpers are pure
   reporting (no control-side writes); `slide_on`/`two_sided_gate` are the
   dynamic-capture scoped booleans.
2. The knob resolution: the REAL `__init__` assignment statements are exec'd
   under env values (unset / the screen values / off forms / negative and
   zero clamps) against an independent reference.
3. Default-off byte-identity: the REAL `_slide_gate_target` passes the shipped
   target through unchanged while unlatched (and never fires a step record);
   the REAL `_freeze2_step` returns False until the sustained run reaches the
   tick floor; the row helpers print nothing with the diag off; the caller
   blocks are gated on `slide_on` / `two_sided_gate` (source).
4. The slide-gate logic on synthetic drift sequences: the REAL
   `_slide_gate_observe` is driven with synthetic hand-frame/world drift
   vectors - a stationary sequence (no trigger), an over-band slide (triggers
   after exactly `_TICKS` samples with the reference rate/drift), the bounded
   steps of the REAL `_slide_gate_target` (clip at `_STEP_MM`, convergence,
   the recorded step), the max count (a second trigger then no third), the
   release (rate back under the band) and the recovery window (drift beyond
   `_WINDOW_MM` suppresses the trigger).
5. The two-sided gate's truth table: the REAL `_freeze2_split` on the shipped
   2-key and the D2 4-key tactile forms, malformed keys, empties; the REAL
   `_freeze2_step`'s sustained-run commit, run reset/max and the floor edge.
6. The rows' formats: the REAL `[slide]`/`[freeze2]` statements are exec'd
   with synthetic bindings and checked against independent reference strings;
   diag off = no output.
7. `rl_env.TASKS_MD5 == md5(tasks.py)`.

Run:  python3 logs/p17i/check_slide_gate.py
Exit code 0 = all checks PASS.
"""

from __future__ import annotations

import ast
import hashlib
import os
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
TASKS = ROOT / "src" / "fruit_sorting" / "tasks.py"
RL_ENV = ROOT / "src" / "fruit_sorting" / "rl_env.py"

failures: list[str] = []

#: The row helpers' `say` sink (cleared/read by the row-format checks).
SAY_OUT: list[str] = []


def check(label: str, ok: bool) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def _method(tree: ast.Module, cls: str, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == name:
                    return sub
    raise SystemExit(f"STUB FAIL: {cls}.{name} not found in tasks.py")


def _exec_stmts(stmts, ns: dict, filename: str) -> None:
    exec(compile(ast.Module(body=stmts, type_ignores=[]), filename, "exec"), ns)


def _assign_to(stmts: list, attr: str) -> ast.stmt | None:
    out = []
    for st in stmts:
        if isinstance(st, (ast.Assign, ast.AnnAssign)):
            targets = st.targets if isinstance(st, ast.Assign) else [st.target]
            if (
                len(targets) == 1
                and isinstance(targets[0], ast.Attribute)
                and targets[0].attr == attr
            ):
                out.append(st)
    if len(out) != 1:
        return None
    return out[0]


def _name_assign(stmts: list, name: str) -> ast.stmt | None:
    out = []
    for st in stmts:
        if isinstance(st, (ast.Assign, ast.AnnAssign)):
            targets = st.targets if isinstance(st, ast.Assign) else [st.target]
            if (
                len(targets) == 1
                and isinstance(targets[0], ast.Name)
                and targets[0].id == name
            ):
                out.append(st)
    if len(out) != 1:
        return None
    return out[0]


#: attr -> (env name, shipped default, kind, clamp floor). The kind picks the
#: value form: `bool` = `os.environ.get(...) == "1"`; `float`/`int` = a
#: `max(floor, float/int(...))` clamp.
KNOBS: dict[str, tuple[str, str, str, float | None]] = {
    "_slide_gate": ("FRUIT_DYNAMIC_SLIDE_GATE", "0", "bool", None),
    "_slide_gate_mmps": ("FRUIT_DYNAMIC_SLIDE_GATE_MMPS", "60.0", "float", 0.0),
    "_slide_gate_ticks": ("FRUIT_DYNAMIC_SLIDE_GATE_TICKS", "3", "int", 1),
    "_slide_gate_step_mm": ("FRUIT_DYNAMIC_SLIDE_GATE_STEP_MM", "8.0", "float", 0.0),
    "_slide_gate_max": ("FRUIT_DYNAMIC_SLIDE_GATE_MAX", "2", "int", 0),
    "_slide_gate_window_mm": ("FRUIT_DYNAMIC_SLIDE_GATE_WINDOW_MM", "60.0", "float", 0.0),
    "_slide_gate_diag": ("FRUIT_DYNAMIC_SLIDE_GATE_DIAG", "0", "bool", None),
    "_freeze_twosided": ("FRUIT_DYNAMIC_FREEZE_TWOSIDED", "0", "bool", None),
    "_freeze_twosided_force": ("FRUIT_DYNAMIC_FREEZE_TWOSIDED_FORCE", "0.5", "float", 0.0),
    "_freeze_twosided_ticks": ("FRUIT_DYNAMIC_FREEZE_TWOSIDED_TICKS", "3", "int", 1),
    "_freeze_twosided_diag": ("FRUIT_DYNAMIC_FREEZE_TWOSIDED_DIAG", "0", "bool", None),
}
ENVS = tuple(spec[0] for spec in KNOBS.values())


class env_guard:
    """Set the eleven knob envs for the block; restore exactly afterwards."""

    def __init__(self, overrides: dict):
        self.overrides = overrides
        self.prev: dict = {}

    def __enter__(self):
        for name in ENVS:
            self.prev[name] = os.environ.get(name)
            value = self.overrides.get(name)
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def __exit__(self, *exc):
        for name, value in self.prev.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def parse(kind: str, raw: str, floor):
    if kind == "bool":
        return raw == "1"
    if kind == "float":
        return max(float(floor), float(raw))
    return max(int(floor), int(raw))


def main() -> int:
    source = TASKS.read_text(encoding="utf-8")
    tree = ast.parse(source)

    init = _method(tree, "PickAndPlaceTask", "__init__")
    impl = _method(tree, "PickAndPlaceTask", "_grasp_carry_place_impl")

    # ---- 1. source checks ----------------------------------------------------
    print("== 1. source checks ==")
    read_ok = True
    for attr, (name, default, kind, _floor) in KNOBS.items():
        if source.count(f'os.environ.get("{name}"') != 1:
            read_ok = False
            print(f"    {name}: {source.count(chr(34) + name + chr(34))} reads")
            continue
        if kind == "bool":
            literal = f'os.environ.get("{name}", "{default}") == "1"'
        else:
            literal = f'os.environ.get("{name}", "{default}")'
        if literal not in source:
            read_ok = False
            print(f"    {name}: literal missing: {literal}")
    check(
        "all eleven knobs are read exactly once each with the shipped defaults "
        "(bool `== \"1\"`; float/int inside the `max(floor, ...)` clamp)",
        read_ok,
    )
    knob_stmts = []
    for attr in KNOBS:
        stmt = _assign_to(init.body, attr)
        if stmt is None:
            failures.append(f"__init__ assignment for {attr} not found/uniquely")
        else:
            knob_stmts.append(stmt)
    check(
        "each knob attribute is assigned exactly once in `__init__` (AST)",
        len(knob_stmts) == len(KNOBS),
    )
    helper_names = [
        "_slide_gate_observe",
        "_slide_gate_target",
        "_slide_gate_report",
        "_slide_gate_summary",
        "_slide_gate_begin_phase",
        "_slide_gate_end_phase",
        "_slide_gate_tick",
        "_freeze2_split",
        "_freeze2_step",
        "_freeze_twosided_report",
    ]
    helpers = {}
    for name in helper_names:
        hits = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == name
        ]
        if len(hits) != 1:
            failures.append(f"{name}: {len(hits)} definitions")
        else:
            helpers[name] = hits[0]
    check("each of the ten helpers is defined exactly once (AST)",
          len(helpers) == len(helper_names))

    # The scope booleans and their exact definitions.
    scope_src = ast.unparse(impl)
    check(
        "the H1 scope is `slide_on = bool(self._slide_gate and dynamic_capture)`",
        "slide_on = bool(self._slide_gate and dynamic_capture)" in scope_src,
    )
    check(
        "the H2 scope is `two_sided_gate = bool(self._freeze_twosided and "
        "dynamic_capture)`",
        "two_sided_gate = bool(self._freeze_twosided and dynamic_capture)"
        in scope_src,
    )
    # Call sites: the hold and the probe-1 block are the only target/tick
    # callers; the phase helpers bracket them.
    counts = {name: scope_src.count(f"self.{name}(") for name in helper_names}
    counts["_slide_gate_observe"] = source.count("self._slide_gate_observe(")
    check(
        "`_slide_gate_target` is called exactly twice (hold + probe-1), "
        "`_slide_gate_tick` twice, `_slide_gate_begin_phase` once, "
        "`_slide_gate_end_phase` twice, `_slide_gate_observe` once (inside "
        f"`_slide_gate_tick`): {counts}",
        counts["_slide_gate_target"] == 2
        and counts["_slide_gate_tick"] == 2
        and counts["_slide_gate_begin_phase"] == 1
        and counts["_slide_gate_end_phase"] == 2
        and counts["_slide_gate_observe"] == 1,
    )
    check(
        "every H1 call site is gated on `slide_on`: three plain hold blocks + "
        "the four `_regrasp == 0` probe-1 blocks",
        scope_src.count("if slide_on:") == 3
        and scope_src.count("if slide_on and _regrasp == 0:") == 4,
    )
    check(
        "`_freeze2_step` is called exactly once (inside `two_sided_gate`), the "
        "H2 row three times (shipped/straddle/fallback)",
        counts["_freeze2_step"] == 1 and counts["_freeze_twosided_report"] == 3,
    )
    check(
        "the H2 straddle commit is gated `if two_sided_gate and freeze_cmd is "
        "None`; the fallback on `two_sided_gate and freeze_cmd is None and "
        "shipped_depth is not None`",
        "if two_sided_gate and freeze_cmd is None:" in scope_src
        and "if two_sided_gate and freeze_cmd is None and (shipped_depth is "
        "not None):" in scope_src,
    )
    check(
        "the H2 withholding branch remembers the shipped record "
        "(`shipped_depth`/`shipped_tick`/`shipped_span` at the first sustained "
        "contact) and the fallback pins `last_cmd = float(shipped_depth)`",
        "if shipped_depth is None:" in scope_src
        and "shipped_span = float(sep_meas)" in scope_src
        and "last_cmd = float(shipped_depth)" in scope_src,
    )
    # The row helpers are pure reporting: no attribute writes, no stepping.
    row_src = {
        name: ast.unparse(helpers[name])
        for name in ("_slide_gate_report", "_slide_gate_summary",
                     "_freeze_twosided_report")
    }
    check(
        "the row helpers are pure reporting (no `self.<attr> =`, no "
        "`ik_step`/`_step_sim`/`set_dof`)",
        all(
            "ik_step" not in src
            and "_step_sim" not in src
            and "set_dof" not in src
            and not any(
                isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Attribute) for t in n.targets)
                for n in ast.walk(helpers[name])
            )
            for name, src in row_src.items()
        ),
    )
    check(
        "the row helpers are diag-gated (`if not self._slide_gate_diag: "
        "return` / `if not self._freeze_twosided_diag: return`)",
        "if not self._slide_gate_diag:\n            return" in source
        and "if not self._freeze_twosided_diag:\n            return" in source,
    )
    # The fallback row names its commit source.
    check(
        "the H2 row's commit sources are `shipped`/`straddle`/`fallback`",
        '"shipped",' in source and '"straddle",' in source
        and '"fallback",' in source,
    )
    # The monitor reads are the W8-B recipe (TCP quaternion + pad centre).
    tick_src = ast.unparse(helpers["_slide_gate_tick"])
    check(
        "`_slide_gate_tick` reads the TCP quaternion + `pad_centre()` + the "
        "payload position (the W8-B carry-diag recipe) and maps them to the "
        "hand frame",
        "arm.tcp_pose()" in tick_src
        and "pad_centre()" in tick_src
        and "self.spawner.position(sample)" in tick_src
        and "rot_now.T @ rel_world" in tick_src,
    )

    # ---- 2. the knob resolution (real statements, exec'd) --------------------
    print("== 2. knob resolution (real statements, exec'd) ==")

    class _Self:
        pass

    def resolved(overrides: dict) -> dict:
        fake = _Self()
        with env_guard(overrides):
            _exec_stmts(knob_stmts, {"self": fake, "os": os}, str(TASKS))
        return {attr: getattr(fake, attr) for attr in KNOBS}

    def reference(overrides: dict) -> dict:
        out = {}
        for attr, (name, default, kind, floor) in KNOBS.items():
            raw = overrides.get(name, default)
            out[attr] = parse(kind, raw, floor)
        return out

    def make_self(overrides: dict) -> _Self:
        fake = _Self()
        with env_guard(overrides):
            _exec_stmts(knob_stmts, {"self": fake, "os": os}, str(TASKS))
        return fake

    base = resolved({})
    check(
        "unset: the shipped defaults (0/60.0/3/8.0/2/60.0/0 and 0/0.5/3/0)",
        base == reference({})
        and base["_slide_gate"] is False
        and base["_slide_gate_mmps"] == 60.0
        and base["_slide_gate_ticks"] == 3
        and base["_slide_gate_step_mm"] == 8.0
        and base["_slide_gate_max"] == 2
        and base["_slide_gate_window_mm"] == 60.0
        and base["_slide_gate_diag"] is False
        and base["_freeze_twosided"] is False
        and base["_freeze_twosided_force"] == 0.5
        and base["_freeze_twosided_ticks"] == 3
        and base["_freeze_twosided_diag"] is False,
    )
    screen = {
        "FRUIT_DYNAMIC_SLIDE_GATE": "1",
        "FRUIT_DYNAMIC_SLIDE_GATE_MMPS": "80",
        "FRUIT_DYNAMIC_SLIDE_GATE_TICKS": "4",
        "FRUIT_DYNAMIC_SLIDE_GATE_STEP_MM": "6",
        "FRUIT_DYNAMIC_SLIDE_GATE_MAX": "1",
        "FRUIT_DYNAMIC_SLIDE_GATE_WINDOW_MM": "40",
        "FRUIT_DYNAMIC_SLIDE_GATE_DIAG": "1",
        "FRUIT_DYNAMIC_FREEZE_TWOSIDED": "1",
        "FRUIT_DYNAMIC_FREEZE_TWOSIDED_FORCE": "1.5",
        "FRUIT_DYNAMIC_FREEZE_TWOSIDED_TICKS": "5",
        "FRUIT_DYNAMIC_FREEZE_TWOSIDED_DIAG": "1",
    }
    check(
        "screen values resolve exactly (1/80/4/6/1/40/1 and 1/1.5/5/1)",
        resolved(screen) == reference(screen)
        and resolved(screen)["_slide_gate"] is True
        and resolved(screen)["_slide_gate_max"] == 1
        and resolved(screen)["_freeze_twosided_ticks"] == 5,
    )
    off = {name: "0" for name in ENVS}
    check(
        "explicit zeros resolve to the off forms (0.0/0/False)",
        resolved(off) == reference(off)
        and resolved(off)["_slide_gate_mmps"] == 0.0
        and resolved(off)["_slide_gate_max"] == 0
        and resolved(off)["_slide_gate_diag"] is False,
    )
    clamp = {name: "-5" for name in ENVS}
    got = resolved(clamp)
    check(
        "negative values clamp: floats -> 0.0, tick floors -> 1, the response "
        "cap -> 0, bools -> False",
        got == reference(clamp)
        and got["_slide_gate_mmps"] == 0.0
        and got["_slide_gate_ticks"] == 1
        and got["_slide_gate_step_mm"] == 0.0
        and got["_slide_gate_max"] == 0
        and got["_slide_gate_window_mm"] == 0.0
        and got["_freeze_twosided_force"] == 0.0
        and got["_freeze_twosided_ticks"] == 1,
    )
    nonzero = {name: "2" for name in ENVS}
    check(
        "bool knobs read only the literal \"1\" (\"2\" = off)",
        resolved(nonzero) == reference(nonzero)
        and resolved(nonzero)["_slide_gate"] is False
        and resolved(nonzero)["_freeze_twosided_diag"] is False,
    )

    # ---- 3. default-off byte-identity ---------------------------------------
    print("== 3. default-off byte-identity ==")

    # `CONTROL_DT` from the module source (no Isaac import).
    control_dt = None
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "CONTROL_DT"
        ):
            ns: dict = {}
            _exec_stmts([node], ns, str(TASKS))
            control_dt = float(ns["CONTROL_DT"])
    check(f"CONTROL_DT extracted from the module source ({control_dt})",
          control_dt == 1.0 / 120.0)

    fn_ns: dict = {"np": np, "CONTROL_DT": control_dt, "say": SAY_OUT.append}
    for name, fn in helpers.items():
        _exec_stmts([fn], fn_ns, str(TASKS))
    observe = fn_ns["_slide_gate_observe"]
    target = fn_ns["_slide_gate_target"]
    report = fn_ns["_slide_gate_report"]
    summary = fn_ns["_slide_gate_summary"]
    begin_phase = fn_ns["_slide_gate_begin_phase"]
    end_phase = fn_ns["_slide_gate_end_phase"]
    split = fn_ns["_freeze2_split"]
    step = fn_ns["_freeze2_step"]
    freeze_report = fn_ns["_freeze_twosided_report"]

    def bound(overrides: dict) -> _Self:
        """A fake instance with the knobs resolved and the real helpers bound."""
        fake = _Self()
        with env_guard(overrides):
            _exec_stmts(knob_stmts, {"self": fake, "os": os}, str(TASKS))
        for name in helper_names:
            setattr(fake, name, fn_ns[name].__get__(fake))
        return fake

    # The caller's own book literal, exec'd from the impl (the keys the
    # helpers rely on are pinned by using the real template).
    book_stmt = _name_assign(impl.body, "slide_book")
    check("the impl carries one `slide_book` literal (AnnAssign, AST)",
          book_stmt is not None)
    book_ns: dict = {"slide_on": True}
    _exec_stmts([book_stmt], book_ns, str(TASKS))
    book_template = book_ns["slide_book"]
    off_ns: dict = {"slide_on": False}
    _exec_stmts([book_stmt], off_ns, str(TASKS))
    check(
        "the book is allocated only when the gate is armed (`slide_on` False "
        "-> `slide_book` is None; nothing runs on the shipped path)",
        off_ns["slide_book"] is None and isinstance(book_template, dict),
    )

    def make_book():
        return dict(book_template)

    fake_off = bound({})
    t_off = target.__get__(fake_off)
    for vec in (
        (0.0, -0.0216, 1.0),
        (0.3, -0.03, 1.19),
        (0.0, 0.0, 0.0),
    ):
        book = make_book()
        got = t_off(book, np.array(vec), np.array([0.0, -0.05, 1.0]))
        check(
            f"unlatched `_slide_gate_target` returns the shipped target "
            f"unchanged {vec} (and records no step)",
            np.array_equal(got, np.asarray(vec)) and book["trig_step"] == 0.0,
        )
    fake_screen = bound(screen)
    t_screen = target.__get__(fake_screen)
    book = make_book()
    book["latched"] = True
    book["aim"] = np.array([0.0, -0.0216, 1.0])
    got = t_screen(book, np.array([9.0, 9.0, 9.0]), np.array([0.0, -0.05, 1.0]))
    check(
        "the gate-off claim is by call gating, not by value: a latched book "
        "with the knob on does move the aim (the helper itself is "
        "value-transparent when unlatched)",
        float(np.linalg.norm(got - book["aim"])) <= 6e-3 + 1e-12,
    )

    class _Reading:
        def __init__(self, forces):
            self.fingertip_forces = forces

    fake_base = bound({})
    s_base = step.__get__(fake_base)
    book = {"run": 0, "run_max": 0, "face_l": 0.0, "face_r": 0.0}
    outs = [
        s_base(book, _Reading({"left_0": 2.0, "left_1": 2.0}))
        for _ in range(2)
    ]
    check(
        "`_freeze2_step` returns False until the sustained run reaches the "
        "tick floor (2 ready ticks < 3)",
        outs == [False, False] and book["run"] == 2 and book["run_max"] == 2,
    )

    # The row helpers with the diag off print nothing (exec'd, real code).
    SAY_OUT.clear()
    fake_off = bound({})
    book = make_book()
    fake_off._slide_gate_report("left", 0, book, True)
    fake_off._slide_gate_summary("left", 0, book)
    fake_off._freeze_twosided_report(
        "left", 0, "shipped", 0, 0.01, 0.04, (1.0, 1.0), 0, None, None
    )
    check("all three row helpers print nothing with the diags off (default)",
          SAY_OUT == [])

    # ---- 4. the slide-gate logic on synthetic drift sequences --------------
    print("== 4. the slide-gate logic (real helpers, exec'd) ==")

    #: The sequence-test config: the screen knob set with the shipped tick
    #: count and a 6 mm step (the design's bounded-step value), so the
    #: synthetic triggers land on the arithmetic the checks pin.
    seq = {
        "FRUIT_DYNAMIC_SLIDE_GATE": "1",
        "FRUIT_DYNAMIC_SLIDE_GATE_MMPS": "60.0",
        "FRUIT_DYNAMIC_SLIDE_GATE_TICKS": "3",
        "FRUIT_DYNAMIC_SLIDE_GATE_STEP_MM": "6.0",
        "FRUIT_DYNAMIC_SLIDE_GATE_MAX": "2",
        "FRUIT_DYNAMIC_SLIDE_GATE_WINDOW_MM": "60.0",
        "FRUIT_DYNAMIC_SLIDE_GATE_DIAG": "1",
        "FRUIT_DYNAMIC_FREEZE_TWOSIDED": "1",
        "FRUIT_DYNAMIC_FREEZE_TWOSIDED_FORCE": "0.5",
        "FRUIT_DYNAMIC_FREEZE_TWOSIDED_TICKS": "3",
        "FRUIT_DYNAMIC_FREEZE_TWOSIDED_DIAG": "1",
    }

    def slide_sequence(overrides, rels, targets=None):
        """Drive the REAL observe (+target) over synthetic drift vectors.

        `rels` are world-frame payload-minus-pad vectors; the frame is the
        identity, so `rel_frame == rel_world`. Returns (book, events, aims).
        """
        fake = bound(overrides)
        obs = observe.__get__(fake)
        tgt = target.__get__(fake)
        book = make_book()
        events = []
        aims = []
        for i, rel in enumerate(rels):
            events.append(obs(book, np.asarray(rel, float), np.asarray(rel, float)))
            if targets is not None:
                aims.append(
                    tgt(book, np.asarray(targets[i], float), np.asarray(rel, float))
                )
        return book, events, aims

    # A stationary sequence: no trigger, zero rates/drifts.
    rels = [(0.0, 0.0, 1.0)] * 10
    book, events, _ = slide_sequence(seq, rels)
    check(
        "a stationary payload never triggers (10 samples, rate/drift 0)",
        events == [None] * 10
        and book["used"] == 0
        and book["rate_max"] == 0.0
        and book["drift_max"] == 0.0
        and book["ticks"] == 10,
    )

    # An over-band slide at 1.2 mm/tick (144 mm/s): trigger at the 4th sample
    # with _TICKS=3, and the reference rate/drift arithmetic.
    def slide_rels(n, step_mm=1.2):
        return [(0.0, -step_mm * k / 1000.0, 1.0) for k in range(n)]

    book, events, _ = slide_sequence(seq, slide_rels(8))
    check(
        "an over-band slide triggers after exactly `_TICKS` samples "
        f"(events={events[:5]})",
        events[:3] == [None, None, None] and events[3] == "trigger",
    )
    check(
        "the trigger record is the reference arithmetic: rate = 1.2 mm / "
        "(1/120 s) = 144.0 mm/s, drift = 3 * 1.2 mm, tick = 4",
        abs(book["trig_rate"] - 0.144) < 1e-12
        and abs(book["trig_drift"] - 0.0036) < 1e-12
        and book["trig_tick"] == 4
        and book["used"] == 1
        and book["events"] == 1
        and book["latched"] is True,
    )
    check(
        "the latch holds while the rate stays over-band (no further triggers, "
        "one response used)",
        all(e in (None, "trigger") for e in events)
        and events.count("trigger") == 1
        and book["used"] == 1,
    )

    # The bounded steps: the first latched tick clips at exactly `_STEP_MM`.
    rels = slide_rels(8)
    aim0 = (0.0, -0.0216, 1.0)          # the shipped aim (lead applied)
    recentre = (0.0, -0.006, 1.0)       # the payload's measured centre
    targets = [aim0] * 8
    book, events, aims = slide_sequence(seq, rels, targets=targets)
    check("the step case triggered at sample 4", events[3] == "trigger")
    step_len = float(np.linalg.norm(aims[3] - np.asarray(aims[2], float)))
    check(
        f"the first latched tick moves exactly `_STEP_MM`=6 mm toward the "
        f"re-centre point ({step_len * 1000:.3f} mm) and records it",
        abs(step_len - 0.006) < 1e-9
        and abs(book["trig_step"] - 0.006) < 1e-9,
    )
    check(
        "the move direction is toward the payload's measured centre (the aim "
        "sits between the previous command and the recentre point)",
        float(aims[3][1]) > float(aim0[1])
        and float(aims[3][1]) < float(recentre[1]),
    )
    # Convergence: repeated latched ticks approach the recentre point without
    # ever exceeding the step, and the aim stays a bounded move.
    fake = bound(seq)
    tgt = target.__get__(fake)
    book = make_book()
    book["latched"] = True
    book["aim"] = np.array(aim0, float)
    prev = book["aim"].copy()
    max_step_seen = 0.0
    for _ in range(12):
        got = tgt(book, np.array(aim0, float), np.array(recentre, float))
        max_step_seen = max(max_step_seen, float(np.linalg.norm(got - prev)))
        prev = got.copy()
    check(
        "12 latched ticks converge onto the re-centre point with every step "
        "<= `_STEP_MM`",
        float(np.linalg.norm(prev - np.asarray(recentre, float))) < 1e-9
        and max_step_seen <= 0.006 + 1e-12,
    )
    # A zero step knob: the clip is to zero (a bounded, inert response).
    fake_zero = bound({**seq, "FRUIT_DYNAMIC_SLIDE_GATE_STEP_MM": "0"})
    tgt0 = target.__get__(fake_zero)
    book = make_book()
    book["latched"] = True
    book["aim"] = np.array(aim0, float)
    got = tgt0(book, np.array(aim0, float), np.array(recentre, float))
    check("step=0 keeps the aim exactly where it was (bounded to zero)",
          np.array_equal(got, np.array(aim0, float)))

    # The max count: release on the arrest, re-slide, no third response.
    rels = (
        slide_rels(6)                                  # y 0..-6.0 mm; trigger at 4
        + [(0.0, -0.0060, 1.0)]                        # arrest (rate 0) -> release
        + [(0.0, -0.0060 - 0.0012 * k, 1.0) for k in range(1, 6)]  # re-slide 5
        + [(0.0, -0.0120, 1.0)]                        # arrest -> release
        + [(0.0, -0.0120 - 0.0012 * k, 1.0) for k in range(1, 6)]  # re-slide 5
    )
    book, events, _ = slide_sequence({**seq, "FRUIT_DYNAMIC_SLIDE_GATE_MAX": "2"}, rels)
    check(
        f"the response budget caps the count at `_MAX`=2 "
        f"(triggers={events.count('trigger')}, releases={events.count('release')})",
        events.count("trigger") == 2
        and events.count("release") == 2
        and book["used"] == 2,
    )
    check(
        "a third over-band run after the budget is spent does not latch "
        "(the last samples stay None)",
        events[-5:] == [None] * 5,
    )
    # The release is the arrest: the post-response rate is the below-band one,
    # and the aim then walks back to the shipped target (see below).
    book, events, _ = slide_sequence(seq, slide_rels(4) + [(0.0, -0.0036, 1.0)])
    check(
        "the release fires on the first below-band sample and the post-rate "
        f"is that sample's rate (~0 mm/s here; events={events[-2:]})",
        events[3] == "trigger" and events[4] == "release"
        and abs(book["rate"]) < 1e-12 and book["latched"] is False
        and book["releasing"] is True,
    )
    # The walk-back: after the release the aim returns to the shipped target
    # under the same step bound (no single-tick command jump).
    fake_wb = bound(seq)
    tgt_wb = target.__get__(fake_wb)
    book = make_book()
    book["latched"] = False
    book["releasing"] = True
    book["aim"] = np.array(recentre, float)
    shipped = np.array([0.0, -0.0216, 1.0], float)   # the shipped aim (lead applied)
    prev = book["aim"].copy()
    walk_steps = []
    for _ in range(8):
        got = tgt_wb(book, shipped, np.array(recentre, float))
        walk_steps.append(float(np.linalg.norm(got - prev)))
        prev = got.copy()
    check(
        "the release walk-back returns the aim to the shipped target with "
        f"every step <= `_STEP_MM` ({[round(s * 1000, 3) for s in walk_steps]})",
        np.array_equal(prev, shipped)
        and all(s <= 0.006 + 1e-12 for s in walk_steps)
        and book["releasing"] is False,
    )

    # The recovery window: drift beyond `_WINDOW_MM` suppresses the trigger.
    book, events, _ = slide_sequence(
        {**seq, "FRUIT_DYNAMIC_SLIDE_GATE_WINDOW_MM": "3.0"}, slide_rels(8)
    )
    check(
        "drift beyond the recovery window suppresses the trigger "
        "(window 3.0 mm < the 3.6 mm drift at the would-be trigger)",
        "trigger" not in events and book["used"] == 0
        and book["drift_max"] >= 0.0036 - 1e-12,
    )
    book, events, _ = slide_sequence(
        {**seq, "FRUIT_DYNAMIC_SLIDE_GATE_WINDOW_MM": "4.0"}, slide_rels(8)
    )
    check("the same sequence inside the window triggers (boundary check)",
          "trigger" in events)

    # `_TICKS` binds the consecutive-sample count.
    book, events, _ = slide_sequence(
        {**seq, "FRUIT_DYNAMIC_SLIDE_GATE_TICKS": "6"}, slide_rels(10)
    )
    check(
        "`_TICKS`=6 moves the trigger to the 7th sample",
        events[6] == "trigger" and events[:6] == [None] * 6,
    )

    # The phase helpers: begin resets the counters; end reports a still-latched
    # response as `end=phase` and releases it.
    SAY_OUT.clear()
    fake_diag = bound({**seq, "FRUIT_DYNAMIC_SLIDE_GATE_DIAG": "1"})
    book = make_book()
    book["used"] = 1
    book.update(ticks=48, events=1, rate_max=0.144, drift_max=0.005)
    fake_diag._slide_gate_begin_phase(book, "probe1")
    check(
        "`_slide_gate_begin_phase` sets the phase and resets the counters "
        "(the drift reference and the response budget survive)",
        book["phase"] == "probe1" and book["ticks"] == 0
        and book["events"] == 0 and book["rate_max"] == 0.0
        and book["drift_max"] == 0.0 and book["used"] == 1,
    )
    book["latched"] = True
    book.update(trig_tick=4, trig_rate=0.144, trig_drift=0.0036, trig_step=0.006,
                rate=0.09, ticks=12, events=1, rate_max=0.144, drift_max=0.004)
    fake_diag._slide_gate_end_phase("left", 3, book)
    check(
        "`_slide_gate_end_phase` reports a still-latched response as "
        "`end=phase` and releases it, then the summary",
        len(SAY_OUT) == 2 and "end=phase" in SAY_OUT[0]
        and "summary" in SAY_OUT[1]
        and book["latched"] is False,
    )

    # ---- 5. the two-sided gate's truth table --------------------------------
    print("== 5. the two-sided gate's truth table (real helpers, exec'd) ==")

    fake = bound({})
    split_fn = split.__get__(fake)
    cases = [
        ("shipped 2-key, both loaded", {"left_0": 2.0, "left_1": 3.0}, (2.0, 3.0)),
        ("shipped 2-key, one-sided", {"left_0": 2.0, "left_1": 0.0}, (2.0, 0.0)),
        ("shipped 2-key, other side", {"left_0": 0.0, "left_1": 4.0}, (0.0, 4.0)),
        ("D2 4-key (finger + pad faces)", {"left_0": 0.1, "left_1": 0.2,
                                           "left_2": 3.0, "left_3": 4.0}, (3.0, 4.0)),
        ("empty dict", {}, (0.0, 0.0)),
        ("malformed keys ignored", {"left_0": 1.0, "weird": 5.0, "left_x": 7.0},
         (1.0, 0.0)),
    ]
    ok = True
    for label, forces, want in cases:
        got = split_fn(_Reading(forces))
        ok = ok and got == want
        if got != want:
            print(f"    {label}: {got} != {want}")
    check("`_freeze2_split` groups by face on the shipped and D2 key forms "
          "and ignores malformed keys", ok)
    check("a reading without the attribute reads (0.0, 0.0)",
          split_fn(object()) == (0.0, 0.0) and split_fn(None) == (0.0, 0.0))

    s_base = step.__get__(fake)
    book = {"run": 0, "run_max": 0, "face_l": 0.0, "face_r": 0.0}
    readings = [
        {"left_0": 1.0, "left_1": 1.0},   # run 1
        {"left_0": 1.0, "left_1": 1.0},   # run 2
        {"left_0": 1.0, "left_1": 0.0},   # reset
        {"left_0": 1.0, "left_1": 1.0},   # run 1
        {"left_0": 1.0, "left_1": 1.0},   # run 2
        {"left_0": 1.0, "left_1": 1.0},   # run 3 -> commit
    ]
    outs = [s_base(book, _Reading(f)) for f in readings]
    check(
        "`_freeze2_step` commits exactly at the `_TICKS`-th consecutive "
        "two-sided sample and resets on a one-sided one "
        f"({outs})",
        outs == [False, False, False, False, False, True]
        and book["run"] == 3 and book["run_max"] == 3
        and book["face_l"] == 1.0 and book["face_r"] == 1.0,
    )
    book = {"run": 0, "run_max": 0, "face_l": 0.0, "face_r": 0.0}
    check(
        "the floor is inclusive (0.5 N reads ready at the shipped floor, "
        "0.4999 does not)",
        s_base(book, _Reading({"left_0": 0.5, "left_1": 0.5})) is False
        and book["run"] == 1
        and s_base(book, _Reading({"left_0": 0.4999, "left_1": 0.5})) is False
        and book["run"] == 0,
    )
    fake_f5 = bound({**seq, "FRUIT_DYNAMIC_FREEZE_TWOSIDED_TICKS": "5"})
    s_f5 = step.__get__(fake_f5)
    book = {"run": 0, "run_max": 0, "face_l": 0.0, "face_r": 0.0}
    outs = [
        s_f5(book, _Reading({"left_0": 2.0, "left_1": 2.0})) for _ in range(5)
    ]
    check("`_TWOSIDED_TICKS` binds the sustained count (5 ticks -> the 5th "
          "sample commits)", outs == [False, False, False, False, True])

    # ---- 6. the rows' formats ------------------------------------------------
    print("== 6. the rows' formats (real statements, exec'd) ==")

    SAY_OUT.clear()
    fake_diag = bound({
        "FRUIT_DYNAMIC_SLIDE_GATE_DIAG": "1",
        "FRUIT_DYNAMIC_FREEZE_TWOSIDED_DIAG": "1",
    })
    book = make_book()
    book.update(phase="hold", used=1, trig_tick=4, trig_rate=0.144,
                trig_drift=0.0036, trig_step=0.006, rate=0.02)
    fake_diag._slide_gate_report("left", 3, book, True)
    want = (
        "[slide] left idx=3 hold response=1/2 trig@4 rate=144.0mm/s "
        "drift=3.6mm step=6.0mm post=20.0mm/s end=release"
    )
    check(f"the `[slide]` response row matches the reference exactly: {SAY_OUT[-1]}",
          SAY_OUT[-1] == want)
    book.update(phase="probe1", ticks=60, events=1, rate_max=0.144,
                drift_max=0.0051)
    fake_diag._slide_gate_summary("right", 7, book)
    want = (
        "[slide] right idx=7 probe1 summary ticks=60 events=1 "
        "rate_max=144.0mm/s drift_max=5.1mm"
    )
    check(f"the `[slide]` summary row matches the reference exactly: {SAY_OUT[-1]}",
          SAY_OUT[-1] == want)
    fake_diag._freeze_twosided_report(
        "left", 3, "straddle", 27, 0.0683, 0.0701, (1.23, 0.98), 3, 21, 0.0705
    )
    want = (
        "[freeze2] left idx=3 commit=straddle tick=27 depth=68.3mm "
        "span=70.1mm ft=(1.23,0.98)N run=3 ship=21t/70.5mm"
    )
    check(f"the `[freeze2]` straddle row matches the reference exactly: "
          f"{SAY_OUT[-1]}", SAY_OUT[-1] == want)
    fake_diag._freeze_twosided_report(
        "right", 9, "fallback", 21, 0.0705, 0.0712, (3.10, 0.00), 2, 21, 0.0705
    )
    want = (
        "[freeze2] right idx=9 commit=fallback tick=21 depth=70.5mm "
        "span=71.2mm ft=(3.10,0.00)N run=2 ship=21t/70.5mm"
    )
    check(f"the `[freeze2]` fallback row matches the reference exactly: "
          f"{SAY_OUT[-1]}", SAY_OUT[-1] == want)
    fake_diag._freeze_twosided_report(
        "left", 5, "straddle", 18, 0.067, 0.069, (0.9, 0.8), 3, None, None
    )
    check(
        "a straddle commit with no shipped-eligible record prints "
        "`ship=none`",
        SAY_OUT[-1].endswith("run=3 ship=none"),
    )
    fake_diag._freeze_twosided_report(
        "left", 6, "shipped", 18, 0.067, 0.069, (0.9, 0.0), 0, 18, 0.067
    )
    check(
        "the shipped commit (the control read with the diag on) prints its "
        "own record as the shipped one",
        "commit=shipped" in SAY_OUT[-1]
        and SAY_OUT[-1].endswith("ship=18t/67.0mm"),
    )

    # ---- 7. rl_env pin -------------------------------------------------------
    print("== 7. rl_env pin ==")
    digest = hashlib.md5(TASKS.read_bytes()).hexdigest()
    pin = None
    for line in RL_ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("TASKS_MD5"):
            pin = line.split('"')[1]
    check(f"rl_env TASKS_MD5 == live tasks.py md5 ({digest})", pin == digest)

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} check(s) failed)")
        for item in failures:
            print(f"  - {item}")
        return 1
    print(
        "RESULT: PASS (the eleven knobs resolve default-off with the exact "
        "clamps; the unlatched target passes the shipped aim through and the "
        "two-sided helper never commits below its tick floor, so the knob-off "
        "path is byte-inert; the real slide logic triggers on the synthetic "
        "over-band sequences with the reference rate/drift, clips every "
        "re-centring step at `_STEP_MM`, caps the responses at `_MAX`, "
        "releases on the arrest and honours the recovery window; the "
        "two-sided split/commit truth table matches on the shipped and D2 "
        "key forms; the `[slide]`/`[freeze2]` rows match the reference "
        "format and stay silent with the diags off; the pin matches)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
