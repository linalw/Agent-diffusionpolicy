#!/usr/bin/env python3
"""P31-A stub check: the direct loop's WAIT GATE (`FRUIT_WAIT_GATE`), offline.

Implementation evidence for `logs/p31/WAIT_GATE_DESIGN.md`. No simulator: the
real `rl_env.py` source is parsed, and the knob resolver, the predicate and the
hold path are *executed* against fake objects, so the checks pin the shipped
tree rather than a copy.

Layers:

1. **The knob resolution** - the real `WaitGateSettings.from_env` (extracted by
   AST and exec'd), over `FRUIT_WAIT_GATE` unset / 0 / off / 1, the sub-knobs,
   the `warm` floor, the `past` clamp, and the malformed-sub-knob-with-the-gate-
   off case (must not raise: the default path returns before parsing).
2. **The default-off byte inertness** - statement identity against the base
   commit for `sample_chunk`, `act` and `_finalize`: every base simple statement
   survives verbatim and every base control-flow test survives verbatim (so no
   condition was rewritten), and every *new* simple statement is dominated by
   `self._wait_gate_on` or `self._wait_gate_hold_chunk` (or is itself that
   guard), so with the gate unset the only executed addition is one False branch
   test per chunk. The new methods are reachable only through the gate.
3. **The predicate** - `skips()` at, just below and just above `dist`; a NaN
   position; the `warm` gate; `past = 0` (no downstream term) and `past > 0`
   (gates strictly past the bound); `dist = 0` (the upstream term off); and a
   full fruit transit (0.60 -> -0.20 m in 1 mm steps) with the transition count,
   which is the hysteresis argument: one crossing per boundary, no chatter.
4. **The hold semantics** - `_wait_gate_hold` executed on a fake env: the scope
   refusals (presentation / rtc / ablate / dagger / event / recorder), the
   `warm` guard before the first chunk has executed, a (horizon, dim) chunk that
   is the last action *repeated* (a hold, not a zero action and not a motion),
   the counters, and the resume latch.
5. **The no-model-call ordering** - in `sample_chunk` the gate's `return` sits
   before the `policy.act` call and after the `rtc`/`ablate`/`ready` guards, so a
   held call cannot sample the model, and the ablation/RTC/handoff paths are
   untouched.
6. **The `[gate]` row** - the real `_wait_gate_report` executed with synthetic
   counters: the field layout, the `along0=-` rule for a never-held episode, and
   the `calls` field being the P30-B counter.
7. **Provenance** - the manifest block, the outcome keys, the `[gate]` row only
   under `_DIAG`, the per-episode reset, and `TASKS_MD5 == md5(tasks.py)`
   (unchanged: this phase does not touch `tasks.py`).

Run:  python3 logs/p31/check_wait_gate.py
Exit code 0 = all checks PASS.
"""

from __future__ import annotations

import ast
import collections
import dataclasses
import hashlib
import os
import pathlib
import subprocess
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
RL_ENV = ROOT / "src" / "fruit_sorting" / "rl_env.py"
TASKS = ROOT / "src" / "fruit_sorting" / "tasks.py"
BASE_COMMIT = "b1acbfe"   # the P31-A base (branch tip before this phase)

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' - ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def note(text: str) -> None:
    print(f"         {text}")


def _parse(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(), filename=str(path))


def _class(tree: ast.Module, name: str) -> ast.ClassDef:
    hits = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == name]
    if len(hits) != 1:
        raise SystemExit(f"{name}: expected exactly one class, found {len(hits)}")
    return hits[0]


def _method(tree: ast.Module, cls: str, name: str) -> ast.FunctionDef:
    owner = _class(tree, cls)
    hits = [
        n for n in owner.body
        if isinstance(n, ast.FunctionDef) and n.name == name
    ]
    if len(hits) != 1:
        raise SystemExit(f"{cls}.{name}: expected one definition, found {len(hits)}")
    return hits[0]


def _parents(root: ast.AST) -> dict[int, ast.AST]:
    table: dict[int, ast.AST] = {}
    for node in ast.walk(root):
        for child in ast.iter_child_nodes(node):
            table[id(child)] = node
    return table


def _mentions_gate(test: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Attribute) and n.attr in ("_wait_gate_on", "_wait_gate_hold_chunk")
        for n in ast.walk(test)
    )


def _dominated(node: ast.AST, parents: dict[int, ast.AST]) -> bool:
    """True when some enclosing `if` tests the gate flag (the guard itself counts)."""
    cur = parents.get(id(node))
    while cur is not None:
        if isinstance(cur, ast.If) and _mentions_gate(cur.test):
            return True
        cur = parents.get(id(cur))
    return False


def _simple(func: ast.FunctionDef) -> collections.Counter:
    """Multiset of the function's *simple* statements (no compound containers)."""
    compound = (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.FunctionDef,
                ast.ClassDef, ast.AsyncFor, ast.AsyncWith)
    return collections.Counter(
        ast.dump(n) for n in ast.walk(func)
        if isinstance(n, ast.stmt) and not isinstance(n, compound)
    )


def _tests(func: ast.FunctionDef) -> collections.Counter:
    """Multiset of every control-flow test / iterator source in the function."""
    out: collections.Counter = collections.Counter()
    for n in ast.walk(func):
        if isinstance(n, (ast.If, ast.While)):
            out[ast.unparse(n.test)] += 1
        elif isinstance(n, (ast.For, ast.AsyncFor)):
            out[ast.unparse(n.iter)] += 1
    return out


def _base_source() -> str:
    return subprocess.run(
        ["git", "show", f"{BASE_COMMIT}:src/fruit_sorting/rl_env.py"],
        cwd=str(ROOT), capture_output=True, text=True, check=True,
    ).stdout


# --------------------------------------------------------------------------- #
# 1. The knob resolution (the real resolver, exec'd)
# --------------------------------------------------------------------------- #
print("1. knob resolution (the real `WaitGateSettings.from_env`)")
tree = _parse(RL_ENV)
settings_src = ast.unparse(_class(tree, "WaitGateSettings"))
ns: dict = {"os": os, "dataclass": dataclasses.dataclass}
exec(settings_src, ns)  # noqa: S102 - the real shipped source
WaitGateSettings = ns["WaitGateSettings"]

MATRIX = [
    ({}, False, 0.35, 0.0, 1, False),
    ({"FRUIT_WAIT_GATE": "0"}, False, 0.35, 0.0, 1, False),
    ({"FRUIT_WAIT_GATE": "off"}, False, 0.35, 0.0, 1, False),
    ({"FRUIT_WAIT_GATE": "true"}, False, 0.35, 0.0, 1, False),
    ({"FRUIT_WAIT_GATE": "1"}, True, 0.35, 0.0, 1, False),
    ({"FRUIT_WAIT_GATE": "1", "FRUIT_WAIT_GATE_DIST": "0.25",
      "FRUIT_WAIT_GATE_PAST": "0.10", "FRUIT_WAIT_GATE_DIAG": "1"},
     True, 0.25, 0.10, 1, True),
    ({"FRUIT_WAIT_GATE": "1", "FRUIT_WAIT_GATE_WARM": "0"},
     True, 0.35, 0.0, 1, False),           # the warm floor: 1
    ({"FRUIT_WAIT_GATE": "1", "FRUIT_WAIT_GATE_PAST": "-0.2"},
     True, 0.35, 0.0, 1, False),           # past clamped at 0
]
KNOBS = (
    "FRUIT_WAIT_GATE", "FRUIT_WAIT_GATE_DIST", "FRUIT_WAIT_GATE_PAST",
    "FRUIT_WAIT_GATE_WARM", "FRUIT_WAIT_GATE_DIAG",
)
saved = {k: os.environ.get(k) for k in KNOBS}
for env, on, dist, past, warm, diag in MATRIX:
    for key in KNOBS:
        os.environ.pop(key, None)
    os.environ.update(env)
    s = WaitGateSettings.from_env()
    ok = (s.enabled, round(s.dist, 4), round(s.past, 4), s.warm, s.diag) == (
        on, dist, past, warm, diag
    )
    check(f"{env or 'unset'} -> {s.summary()}", ok,
          f"expected enabled={on} dist={dist} past={past} warm={warm} diag={diag}")

# A malformed sub-knob must be inert while the gate is off, and raise only when on.
for key in KNOBS:
    os.environ.pop(key, None)
os.environ["FRUIT_WAIT_GATE_DIST"] = "not-a-number"
try:
    off = WaitGateSettings.from_env()
    inert = off.enabled is False
except Exception as exc:  # noqa: BLE001
    inert = False
    note(f"raised with the gate off: {exc!r}")
check("a malformed DIST is never parsed while the gate is off", inert)
os.environ["FRUIT_WAIT_GATE"] = "1"
raised = False
try:
    WaitGateSettings.from_env()
except ValueError:
    raised = True
check("the same malformed DIST raises once the gate is on", raised)
for key in KNOBS:
    if saved[key] is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = saved[key]

check("the dataclass is frozen (an arm cannot be mutated at runtime)",
      type(WaitGateSettings()).__dataclass_params__.frozen)
check("summary() names every knob", all(
    key in WaitGateSettings(enabled=True).summary()
    for key in ("dist=", "past=", "warm=", "diag=")))
check("an off gate summarises as off", WaitGateSettings().summary() == "wait_gate=off")
check("the shipped default is the measured threshold",
      WaitGateSettings(enabled=True).dist == 0.35)

# --------------------------------------------------------------------------- #
# 2. Default-off byte inertness (statement identity vs the base commit)
# --------------------------------------------------------------------------- #
print()
print(f"2. default-off byte inertness (statement identity vs {BASE_COMMIT})")
base_tree = ast.parse(_base_source())
for name in ("sample_chunk", "act", "_finalize"):
    base_fn = _method(base_tree, "SortingRLEnv", name)
    new_fn = _method(tree, "SortingRLEnv", name)
    base_simple, new_simple = _simple(base_fn), _simple(new_fn)
    missing = base_simple - new_simple
    check(f"`{name}`: every base statement survives verbatim", not missing,
          f"{sum(missing.values())} missing" if missing else
          f"{sum(base_simple.values())} base statements")
    base_tests, new_tests = _tests(base_fn), _tests(new_fn)
    lost_tests = base_tests - new_tests
    check(f"`{name}`: every base branch condition survives verbatim",
          not lost_tests, f"{sorted(lost_tests)}" if lost_tests else "")
    added = new_simple - base_simple
    parents = _parents(new_fn)
    offenders = []
    for node in ast.walk(new_fn):
        if not isinstance(node, ast.stmt) or isinstance(node, ast.FunctionDef):
            continue
        if ast.dump(node) not in added:
            continue
        if not _dominated(node, parents):
            offenders.append((node.lineno, ast.unparse(node)[:70]))
    check(f"`{name}`: every new statement is gate-dominated", not offenders,
          f"{offenders}" if offenders else f"{sum(added.values())} new, all dominated")

# Reachability: each new method's call sites must be gate-dominated, or inside a
# method that is (transitively) reached only through the gate.
NEW_METHODS = ("_wait_gate_active", "_wait_gate_along", "_wait_gate_hold",
               "_wait_gate_report")
all_parents = _parents(tree)
sites_of = {}
for meth in NEW_METHODS:
    sites_of[meth] = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == meth
    ]
# Seed: a method whose call sites are all directly gate-dominated.
gated = {
    meth for meth in NEW_METHODS
    if sites_of[meth] and all(_dominated(s, all_parents) for s in sites_of[meth])
}
for _ in range(len(NEW_METHODS) + 1):   # fixpoint: callees of gated methods
    for meth in NEW_METHODS:
        if meth in gated or not sites_of[meth]:
            continue
        enclosing = set()
        for site in sites_of[meth]:
            cur = all_parents.get(id(site))
            while cur is not None and not isinstance(cur, ast.FunctionDef):
                cur = all_parents.get(id(cur))
            if isinstance(cur, ast.FunctionDef):
                enclosing.add(cur.name)
        if enclosing and enclosing <= gated:
            gated.add(meth)
for meth in NEW_METHODS:
    check(f"`{meth}`: called once, only reachable through the gate",
          len(sites_of[meth]) == 1 and meth in gated,
          f"{len(sites_of[meth])} site(s), gated={meth in gated}")

init_src = ast.unparse(_method(tree, "SortingRLEnv", "__init__"))
check("`_wait_gate_on` is cached once from the resolved settings",
      "self._wait_gate_on = bool(self.wait_gate.enabled)" in init_src)
check("the resolver is read once, in __init__", init_src.count("WaitGateSettings") == 1)

# --------------------------------------------------------------------------- #
# 3. The predicate: edges, warm, past, and a full fruit transit
# --------------------------------------------------------------------------- #
print()
print("3. the predicate (the real `skips`)")
g = WaitGateSettings(enabled=True)
check("just above dist -> skip", g.skips(0.3501) is True)
check("exactly at dist -> run (strict `>`, the boundary is inside the zone)",
      g.skips(0.35) is False)
check("below dist -> run", g.skips(0.3499) is False)
check("NaN position -> run (the safe fallback)", g.skips(float("nan")) is False)
check("no warm chunk yet -> run", g.skips(5.0, warm=False) is False)
check("an off gate never skips", WaitGateSettings().skips(5.0) is False)
check("past=0 does not gate downstream", g.skips(-5.0) is False)
gp = WaitGateSettings(enabled=True, past=0.10)
check("past>0 gates strictly past the bound", gp.skips(-0.1001) is True)
check("past>0 at the bound -> run", gp.skips(-0.10) is False)
check("past>0 just inside -> run", gp.skips(-0.0999) is False)
check("dist=0 disables the upstream term",
      WaitGateSettings(enabled=True, dist=0.0).skips(5.0) is False)


def _transitions(settings, lo=-0.20, hi=0.60, step=0.001):
    """The predicate over a fruit riding downstream in 1 mm steps (0.12 m/s)."""
    states = []
    x = hi
    while x >= lo:
        states.append(settings.skips(x))
        x -= step
    return sum(1 for a, b in zip(states, states[1:]) if a != b), states


n_one, states_one = _transitions(g)
check("one-sided gate: exactly one transition over the transit", n_one == 1,
      f"{n_one} (skip={states_one.count(True)} of {len(states_one)} samples)")
n_two, states_two = _transitions(gp)
check("with the past term: exactly two transitions (far -> zone -> past)", n_two == 2,
      f"{n_two}")
check("the zone is contiguous (no chatter)", all(
    not (states_two[i] and not states_two[i + 1] and states_two[i + 2])
    for i in range(len(states_two) - 2)))

# --------------------------------------------------------------------------- #
# 4. The hold semantics (the real `_wait_gate_hold`, executed)
# --------------------------------------------------------------------------- #
print()
print("4. hold semantics (the real `_wait_gate_hold`, executed)")
hold_ns: dict = {"np": np}
for name in ("_wait_gate_hold", "_wait_gate_along", "_wait_gate_active"):
    exec(ast.unparse(_method(tree, "SortingRLEnv", name)), hold_ns)  # noqa: S102
hold = hold_ns["_wait_gate_hold"]


class _FakeEnv:
    def __init__(self, along=0.60, last=None, settings=None, **scope):
        self.wait_gate = settings or WaitGateSettings(enabled=True, diag=True)
        self._wait_gate_on = bool(self.wait_gate.enabled)
        self.presentation = scope.get("presentation", "direct")
        self.rtc = scope.get("rtc", None)
        self.ablate = scope.get("ablate", "none")
        self.dagger = scope.get("dagger", None)
        self._event = scope.get("event", False)
        self._recorder = scope.get("recorder", None)
        self.action_horizon = 16
        self._last_action = np.zeros(9, dtype=np.float32) if last is None else last
        self._infer_calls = scope.get("infer_calls", 1)
        self._expert_jaw_y = -0.002
        self._sample = scope.get("sample", object())
        self._wait_gate_skipped = 0
        self._wait_gate_held = 0
        self._wait_gate_hold_chunk = False
        self._wait_gate_open = False
        self._wait_gate_resumed = False
        self._wait_gate_along0 = float("nan")
        self._along = along
        self.spawner = self

    def position(self, sample):   # `_wait_gate_along` reads spawner.position()[1]
        return np.array([0.30, self._along, 1.19])


class _Rec:
    recording = True


# Bind the real (exec'd) methods onto the fake so the chain is the shipped one.
for _name in ("_wait_gate_hold", "_wait_gate_along", "_wait_gate_active"):
    setattr(_FakeEnv, _name, hold_ns[_name])


last = np.linspace(0.1, 0.9, 9).astype(np.float32)
env = _FakeEnv(last=last)
chunk = hold(env)
check("a far fruit returns a held chunk", chunk is not None)
check("the held chunk is (action_horizon, action_dim)", chunk.shape == (16, 9),
      f"{chunk.shape}")
check("every held row is the last applied action (a hold, not a motion)",
      np.array_equal(chunk, np.repeat(last[None, :], 16, axis=0)))
check("the held chunk is not a zero action", float(np.abs(chunk).max()) > 0.0)
check("the skip is counted", env._wait_gate_skipped == 1)
check("the chunk is marked as a hold (act books its ticks)", env._wait_gate_hold_chunk)
check("the gate records the along at the first held call",
      abs(env._wait_gate_along0 - 0.602) < 1e-9,
      f"along0={env._wait_gate_along0:.3f} (fruit 0.600 - station -0.002)")
check("a second far call holds again and keeps along0",
      hold(env) is not None and abs(env._wait_gate_along0 - 0.602) < 1e-9
      and env._wait_gate_skipped == 2)
env._along = 0.30
check("the fruit entering the zone resumes the model", hold(env) is None)
check("the resume is latched",
      env._wait_gate_resumed is True and env._wait_gate_open is False)
env._along = 0.60
hold(env)
check("a recycle back upstream re-arms the gate (a new wait is a new hold)",
      env._wait_gate_skipped == 3)

cold = _FakeEnv(infer_calls=0)
check("before the first chunk executes the gate does not hold (warm guard)",
      hold(cold) is None, "the held action would be the zeros from reset")

for label, scope in (
    ("handoff presentation", {"presentation": "handoff"}),
    ("RTC", {"rtc": object()}),
    ("the zero ablation", {"ablate": "zero"}),
    ("the scripted ablation", {"ablate": "scripted"}),
    ("the DAgger expert", {"dagger": object()}),
    ("event-triggered replanning", {"event": True}),
    ("an active recorder", {"recorder": _Rec()}),
):
    check(f"the gate refuses {label}", hold(_FakeEnv(**scope)) is None)

# The accounting invariant: replay the measured transit through the real
# predicate + the real hold method, with the driver's loop shape
# (sample_chunk -> act(4 ticks)), and check that the books balance. Two cases,
# both from `logs/p31/31_wait_anatomy.txt` section 6: a fired attempt (the fruit
# stops at the fire band) and a no-fire attempt (the fruit rides to the belt end).
print()
print("4b. the accounting invariant (loop replays of the measured transits)")


def _replay(along0, stop_along, last_action, limit=600):
    """Run the driver's loop over a synthetic transit; return the fake env."""
    env = _FakeEnv(along=along0, last=last_action)
    env._infer_calls = 1          # the first chunk has executed
    chunks = 0
    while env._along - (-0.002) > stop_along and chunks < limit:
        chunk = hold(env)
        if chunk is None:
            env._infer_calls += 1          # `policy.act` ran
        if env._wait_gate_hold_chunk:      # `act` books the held ticks
            env._wait_gate_held += 4
            env._wait_gate_hold_chunk = False
        env._along -= 4 * 0.001            # 0.12 m/s at 120 Hz
        chunks += 1
    env._chunks = chunks
    return env


fired = _replay(0.545, 0.234, last)      # along0 p50 -> the ACQ fire p50
check("fired attempt: every skipped call is 4 held ticks",
      fired._wait_gate_held == 4 * fired._wait_gate_skipped,
      f"held={fired._wait_gate_held} skipped={fired._wait_gate_skipped}")
check("fired attempt: skipped + model calls = the loop's chunk count",
      fired._wait_gate_skipped + fired._infer_calls - 1 == fired._chunks,
      f"{fired._wait_gate_skipped} + {fired._infer_calls - 1} = {fired._chunks}")
check("fired attempt: the gate resumes exactly once",
      fired._wait_gate_resumed is True)
check("fired attempt: ~48 of ~78 chunks skipped at 0.35 m",
      45 <= fired._wait_gate_skipped <= 50,
      f"skipped={fired._wait_gate_skipped} of {fired._chunks} "
      f"({fired._wait_gate_skipped / fired._chunks:.0%})")

no_fire = _replay(0.482, -0.88, last)    # along0 p50 -> the belt end
check("no-fire attempt: every skipped call is 4 held ticks",
      no_fire._wait_gate_held == 4 * no_fire._wait_gate_skipped,
      f"held={no_fire._wait_gate_held} skipped={no_fire._wait_gate_skipped}")
check("no-fire attempt: skipped + model calls = the loop's chunk count",
      no_fire._wait_gate_skipped + no_fire._infer_calls - 1 == no_fire._chunks,
      f"{no_fire._wait_gate_skipped} + {no_fire._infer_calls - 1} = {no_fire._chunks}")
check("no-fire attempt: ~34 of ~341 chunks skipped (the far wait only)",
      32 <= no_fire._wait_gate_skipped <= 35,
      f"skipped={no_fire._wait_gate_skipped} of {no_fire._chunks} "
      f"({no_fire._wait_gate_skipped / no_fire._chunks:.0%})")
check("the post-miss tail is the no-fire attempt's dominant cost (the named "
      "`past` term), not the far wait",
      no_fire._chunks - no_fire._wait_gate_skipped > 8 * no_fire._wait_gate_skipped,
      f"unskipped={no_fire._chunks - no_fire._wait_gate_skipped} vs "
      f"skipped={no_fire._wait_gate_skipped}")

# --------------------------------------------------------------------------- #
# 5. The no-model-call ordering inside `sample_chunk`
# --------------------------------------------------------------------------- #
print()
print("5. the skip site (source order inside `sample_chunk`)")
sc = _method(tree, "SortingRLEnv", "sample_chunk")
lines = {
    "ready": min(
        n.lineno for n in ast.walk(sc)
        if isinstance(n, ast.Attribute) and n.attr == "ready"),
    "rtc": min(
        n.lineno for n in ast.walk(sc)
        if isinstance(n, ast.If) and "self.rtc is not None" in ast.unparse(n.test)),
    "gate": min(
        n.lineno for n in ast.walk(sc)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "self._wait_gate_on"),
    "act": min(
        n.lineno for n in ast.walk(sc)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "act"),
}
check("the gate sits after the ready check", lines["gate"] > lines["ready"])
check("the gate sits after the RTC guard", lines["gate"] > lines["rtc"])
ablate_line = min(
    n.lineno for n in ast.walk(sc)
    if isinstance(n, ast.If) and "ablate" in ast.unparse(n.test))
check("the gate sits after the zero-ablation branch", lines["gate"] > ablate_line)
check("the gate sits before the model call", lines["gate"] < lines["act"])
check("the model call site is still the only `policy.act`",
      ast.unparse(sc).count("policy.act") == 1)
check("the skip does not increment the inference counter",
      ast.unparse(sc).count("self._infer_calls += 1") == 1)

# --------------------------------------------------------------------------- #
# 6. The `[gate]` row (the real printer, executed)
# --------------------------------------------------------------------------- #
print()
print("6. the `[gate]` row")


class _ReportEnv(_FakeEnv):
    def __init__(self, skipped, held, calls, resumed, along0):
        super().__init__()
        self._episode = 7
        self._wait_gate_skipped = skipped
        self._wait_gate_held = held
        self._wait_gate_resumed = resumed
        self._wait_gate_along0 = along0
        self._calls = calls

    def inference_calls(self):
        return self._calls


row_ns: dict = {"np": np}
exec(ast.unparse(_method(tree, "SortingRLEnv", "_wait_gate_report")), row_ns)  # noqa: S102
report = row_ns["_wait_gate_report"]
row = report(_ReportEnv(40, 160, 83, True, 0.545))
print(f"         {row}")
for key in ("skipped=40", "held=160", "calls=83", "along0=+0.545",
            "dist=0.350", "past=0.000", "resumed=1", "episode 7"):
    check(f"the row carries `{key}`", key in row)
never = report(_ReportEnv(0, 0, 120, False, float("nan")))
check("a never-held episode prints `along0=-`", "along0=- " in never + " ", never)

# --------------------------------------------------------------------------- #
# 7. Provenance and plumbing
# --------------------------------------------------------------------------- #
print()
print("7. provenance and plumbing")
manifest_src = ast.unparse(_method(tree, "SortingRLEnv", "_build_manifest"))
check("the manifest records the gate block",
      "'wait_gate': asdict(self.wait_gate)" in manifest_src)
outcome_src = ast.unparse(_method(tree, "SortingRLEnv", "_finalize"))
for key in ("wait_gate_skipped", "wait_gate_held_ticks", "wait_gate_resumed"):
    check(f"the outcome carries `{key}`", key in outcome_src)
check("the `[gate]` row is printed only under `_DIAG`",
      "self._wait_gate_on and self.wait_gate.diag" in outcome_src)
reset_src = ast.unparse(_method(tree, "SortingRLEnv", "reset"))
check("every counter is zeroed per episode", all(
    key in reset_src for key in (
        "self._wait_gate_skipped = 0", "self._wait_gate_held = 0",
        "self._wait_gate_hold_chunk = False", "self._wait_gate_resumed = False")))
check("`inference_calls` is unchanged (the counter is P30-B's)",
      "self._infer_calls" in ast.unparse(_method(tree, "SortingRLEnv", "inference_calls")))
act_src = ast.unparse(_method(tree, "SortingRLEnv", "act"))
check("`act` books the held ticks after the loop",
      "self._wait_gate_held += int(executed)" in act_src)
check("`act` books them once and clears the flag",
      act_src.count("self._wait_gate_hold_chunk = False") == 1)

digest = hashlib.md5(TASKS.read_bytes()).hexdigest()
pin = None
for node in ast.walk(tree):
    if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "TASKS_MD5":
        pin = node.value.value
check("TASKS_MD5 still matches tasks.py (unchanged this phase)", pin == digest,
      f"{pin} vs {digest}")

print()
if failures:
    print(f"FAIL: {len(failures)} check(s) failed")
    for label in failures:
        print(f"  - {label}")
    sys.exit(1)
print("PASS: all checks", f"({sum(1 for _ in [])})" if False else "")
