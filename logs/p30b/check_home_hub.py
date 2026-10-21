#!/usr/bin/env python3
"""P30-B stub check: the HOME-HUB control flow (`FRUIT_HOME_HUB`), offline.

Tier-C-level implementation evidence for `logs/p30b/HOME_HUB_DESIGN.md`. No
simulator: the real `tasks.py` / `rl_env.py` sources are parsed (and the knob
predicate is *executed*), so the checks pin the shipped tree, not a copy.

Layers:

1. **The knob resolution** - the real `home_hub_enabled` method, extracted by
   AST and exec'd against a fake `self`, over
   `FRUIT_HOME_HUB` (unset / 0 / 1) x `scripted` (True/False) x session
   (None / object) x two-line (False/True). Only the single-arm scripted row
   with `=1` resolves True; unset and `=0` are False on every row.
2. **The default-off statement identity** - every statement node of the base
   commit's `_grasp_carry_place_impl` (`e1b9936`) still occurs in the working
   tree's function (AST multiset, so re-indentation and wrapping are free; a
   deleted or rewritten statement fails). The base 60-tick retreat/settle
   block is the `orelse` of the new `if hub:` - i.e. with the knob off the
   shipped branch runs unchanged. Every P30-B statement (`hub` assignment,
   `hub_marks` writes, `at_hub`/`hub_return_s` writes, `_hub_report` calls) is
   dominated by a test on `hub`, so the knob-off path reads no extra
   simulation time and prints nothing.
3. **The leg ordering** - `acquire (grip) -> hub_carry -> place -> release ->
   hub_wait -> return`, verified by source line order: the carrying-hub mark
   sits between the `grasp_lift` and `place` carries, the return sits after
   the release mark, and the success `[hub]` row is emitted after `placed` is
   known.
4. **The failure path** - inside `if not result.grasped:` the hub return, the
   `at_hub`/`hub_return_s` writes and the `flow=fail` row all run before
   `return result`.
5. **The diagnostic row** - `_hub_report` prints the three leg keys and the
   model's call count (`infer`), reading `policy_inference_calls`; the
   `[cycle]`-comparable accounting subtracts `hub_return_s` in `note_result`.
6. **The policy counter** - `rl_env` increments at the single synchronous
   inference site (`policy.act` in `sample_chunk`), adds the RTC chunker's
   completions, publishes to the task before `grasp_carry_place`, exposes
   `policy_inferences` in the outcome, resets per episode, and
   `TASKS_MD5 == md5(tasks.py)`.
7. **The hub geometry** - from `configs/waypoints.json` and the
   `SceneConfig` constants: the carrying hub (`grasp_lift`) clears the output
   belt top and the waiting hub (`ready`) does not (so the two hubs cannot be
   one pose).

Run:  python3 logs/p30b/check_home_hub.py
Exit code 0 = all checks PASS.
"""

from __future__ import annotations

import ast
import collections
import hashlib
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TASKS = ROOT / "src" / "fruit_sorting" / "tasks.py"
RL_ENV = ROOT / "src" / "fruit_sorting" / "rl_env.py"
WAYPOINTS = ROOT / "configs" / "waypoints.json"
BASE_COMMIT = "e1b9936"

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' - ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def note(text: str) -> None:
    print(f"         {text}")


def _parse(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(), filename=str(path))


def _func(tree: ast.Module, name: str) -> ast.FunctionDef:
    hits = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(hits) != 1:
        raise SystemExit(f"{name}: expected exactly one definition, found {len(hits)}")
    return hits[0]


def _parents(root: ast.AST) -> dict[int, ast.AST]:
    table: dict[int, ast.AST] = {}
    for node in ast.walk(root):
        for child in ast.iter_child_nodes(node):
            table[id(child)] = node
    return table


def _under_hub(node: ast.AST, parents: dict[int, ast.AST]) -> bool:
    """True when some enclosing `if` tests exactly the name `hub`."""
    cur = parents.get(id(node))
    while cur is not None:
        if isinstance(cur, ast.If) and isinstance(cur.test, ast.Name) and cur.test.id == "hub":
            return True
        cur = parents.get(id(cur))
    return False


def _stmt_dumps(func: ast.FunctionDef) -> collections.Counter:
    """Multiset of every statement node's AST dump (recursive)."""
    return collections.Counter(
        ast.dump(node) for node in ast.walk(func) if isinstance(node, ast.stmt)
    )


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


# --------------------------------------------------------------------------- #
# 1. The knob resolution (the real predicate, exec'd)
# --------------------------------------------------------------------------- #
print("1. knob resolution (the real `home_hub_enabled`)")
tasks_tree = _parse(TASKS)
predicate = ast.unparse(_func(tasks_tree, "home_hub_enabled"))
namespace = {"os": os}
exec(predicate, namespace)  # noqa: S102 - the real shipped source
resolved = namespace["home_hub_enabled"]


class _Fake:
    def __init__(self, session=None, two_line=False):
        self._active_session = session
        self._two_line = two_line

    def two_line_enabled(self):
        return self._two_line


rows = []
for env in ("unset", "0", "1"):
    os.environ.pop("FRUIT_HOME_HUB", None)
    if env != "unset":
        os.environ["FRUIT_HOME_HUB"] = env
    for scripted in (True, False):
        for session in (None, object()):
            for two_line in (False, True):
                rows.append(
                    (
                        env,
                        scripted,
                        session is not None,
                        two_line,
                        bool(resolved(_Fake(session, two_line), scripted)),
                    )
                )
os.environ.pop("FRUIT_HOME_HUB", None)
expected = [
    (env, scripted, sess, two_line,
     env == "1" and scripted and not sess and not two_line)
    for env, scripted, sess, two_line, _ in rows
]
check("truth table matches the single-arm scripted scope", rows == expected)
on = [r for r in rows if r[4]]
check("exactly one enabled row (env=1, scripted, no session, single arm)", len(on) == 1,
      f"{on}")
check("unset is off on every row", not any(r[4] for r in rows if r[0] == "unset"))
check("explicit 0 is off on every row", not any(r[4] for r in rows if r[0] == "0"))
check("the two-line and coop scopes stay out", not any(
    r[4] for r in rows if r[2] or r[3]
))

# --------------------------------------------------------------------------- #
# 2. Default-off statement identity vs the base commit
# --------------------------------------------------------------------------- #
print("2. default-off statement identity (vs %s)" % BASE_COMMIT)
base_text = subprocess.run(
    ["git", "-C", str(ROOT), "show", f"{BASE_COMMIT}:src/fruit_sorting/tasks.py"],
    capture_output=True, text=True,
)
impl = _func(tasks_tree, "_grasp_carry_place_impl")
head_impl = None
if base_text.returncode == 0:
    head_impl = _func(ast.parse(base_text.stdout), "_grasp_carry_place_impl")
    now_dumps = _stmt_dumps(impl)
    base_nodes = [
        n for n in ast.walk(head_impl)
        if isinstance(n, ast.stmt) and n is not head_impl
    ]
    missing = [n for n in base_nodes if ast.dump(n) not in now_dumps]
    # A compound statement whose body *grew* by an `if hub:` branch is an
    # additive extension, not a rewrite: the shipped children still survive.
    extended = [
        n for n in missing
        if isinstance(n, (ast.If, ast.For, ast.While, ast.With, ast.Try))
    ]
    rewritten = [n for n in missing if n not in extended]
    stray_children = [
        child
        for parent in extended
        for child in parent.body + parent.orelse + getattr(parent, "finalbody", [])
        if isinstance(child, ast.stmt) and ast.dump(child) not in now_dumps
    ]
    check("every base statement survives, or is a container extended by hub code",
          not rewritten and not stray_children,
          f"{len(missing)} changed, {len(extended)} extended container(s), "
          f"{len(rewritten)} rewritten")
    for parent in extended:
        note(f"extended container: {ast.unparse(parent)[:70]!r}")
    added = now_dumps - _stmt_dumps(head_impl)
    note(f"statements added by P30-B: {sum(added.values())} node(s)")
else:
    note(f"base commit {BASE_COMMIT} unavailable; statement-identity layer skipped")

parents = _parents(impl)
hub_assign = [
    n for n in ast.walk(impl)
    if isinstance(n, ast.Assign)
    and any(isinstance(t, ast.Name) and t.id == "hub" for t in n.targets)
]
check("one `hub = self.home_hub_enabled(scripted)` assignment",
      len(hub_assign) == 1
      and "home_hub_enabled" in ast.unparse(hub_assign[0]))

new_writes = [
    n for n in ast.walk(impl)
    if isinstance(n, ast.Assign)
    and any(
        isinstance(t, ast.Attribute) and t.attr in {"at_hub", "hub_return_s"}
        for t in n.targets
    )
]
check("at_hub/hub_return_s writes exist and are hub-guarded",
      bool(new_writes) and all(_under_hub(n, parents) for n in new_writes))

mark_assigns = [n for n in ast.walk(impl) if isinstance(n, ast.Assign) and any(
    isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
    and t.value.id == "hub_marks" for t in n.targets)]
check("every `hub_marks[...]` write is hub-guarded",
      len(mark_assigns) == 5 and all(_under_hub(n, parents) for n in mark_assigns),
      f"{len(mark_assigns)} writes")
mark_names = [n for n in ast.walk(impl) if isinstance(n, ast.Name) and n.id == "hub_marks"]
mark_reads = [
    n for n in mark_names
    if not isinstance(parents.get(id(n)), (ast.Subscript, ast.AnnAssign))
    and not (
        isinstance(parents.get(id(n)), ast.Call)
        and _call_name(parents[id(n)]) == "_hub_report"
    )
]
check("the marks are only written and handed to `_hub_report` (never read as control)",
      not mark_reads, f"{len(mark_reads)} stray references")

report_calls = [n for n in ast.walk(impl) if _call_name(n) == "_hub_report"]
check("every `[hub]` row is hub-guarded", len(report_calls) == 2 and all(
    _under_hub(n, parents) for n in report_calls), f"{len(report_calls)} calls")

# The base retreat/settle block must be the hub `if`'s orelse, unchanged.
hub_ifs = [
    n for n in ast.walk(impl)
    if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == "hub"
    and n.orelse
]
check("one success-path `if hub:` wraps the shipped retreat/settle tail", len(hub_ifs) == 1)
shipped_tail = []
if hub_ifs:
    orelse = hub_ifs[0].orelse
    check("its orelse is the shipped `if retreat > 0.0:` block",
          len(orelse) == 1 and isinstance(orelse[0], ast.If)
          and "retreat" in ast.unparse(orelse[0].test))
    if orelse and isinstance(orelse[0], ast.If):
        shipped_tail = orelse[0]
        if head_impl is not None:
            base_tail = [
                n for n in ast.walk(head_impl)
                if isinstance(n, ast.If) and ast.dump(n) == ast.dump(shipped_tail)
            ]
            check("the shipped retreat/settle branch is byte-identical (AST)",
                  len(base_tail) == 1)

# --------------------------------------------------------------------------- #
# 3. Leg ordering (source order in the real function)
# --------------------------------------------------------------------------- #
print("3. hub leg ordering")


def _lines(nodes, name):
    return sorted(n.lineno for n in nodes if _call_name(n) == name)


lift_calls = [n for n in ast.walk(impl) if _call_name(n) == "_carry"
              and len(n.args) >= 3 and isinstance(n.args[2], ast.Constant)
              and n.args[2].value == "grasp_lift"]
place_calls = [n for n in ast.walk(impl) if _call_name(n) == "_carry"
               and len(n.args) >= 3 and isinstance(n.args[2], ast.JoinedStr)]
hub_carry_marks = [n for n in ast.walk(impl) if isinstance(n, ast.Assign) and any(
    isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
    and t.slice.value == "hub_carry" for t in n.targets)]
hub_place_marks = [n for n in ast.walk(impl) if isinstance(n, ast.Assign) and any(
    isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
    and t.slice.value == "hub_place" for t in n.targets)]
hub_wait_marks = [n for n in ast.walk(impl) if isinstance(n, ast.Assign) and any(
    isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
    and t.slice.value == "hub_wait" for t in n.targets)]
return_calls = [n for n in ast.walk(impl) if _call_name(n) == "_hub_return"]
cycle_marks = [n for n in ast.walk(impl) if _call_name(n) == "_cycle_mark"]

lift_line = lift_calls[0].lineno if lift_calls else -1
place_line = place_calls[0].lineno if place_calls else -1
carry_hub_line = hub_carry_marks[0].lineno if hub_carry_marks else -1
place_hub_line = hub_place_marks[0].lineno if hub_place_marks else -1
check("the carrying hub sits between the grasp_lift and the place leg",
      lift_line < carry_hub_line < place_line < place_hub_line,
      f"lift={lift_line} hub={carry_hub_line} place={place_line} "
      f"hub_place={place_hub_line}")

release_marks = [n for n in ast.walk(impl) if _call_name(n) == "_cycle_mark"
                 and isinstance(n.args[0], ast.Constant)
                 and n.args[0].value == "release"]
return_marks = [n for n in ast.walk(impl) if _call_name(n) == "_cycle_mark"
                and isinstance(n.args[0], ast.Constant)
                and n.args[0].value == "return"]
success_return = max(n.lineno for n in return_calls) if return_calls else -1
success_hub_wait = max(n.lineno for n in hub_wait_marks) if hub_wait_marks else -1
check("the waiting hub return runs after the release and before the return mark",
      release_marks[0].lineno < success_return < success_hub_wait
      < return_marks[0].lineno,
      f"release={release_marks[0].lineno} hub_return={success_return} "
      f"hub_wait={success_hub_wait} return_mark={return_marks[0].lineno}")

placed_assigns = [n for n in ast.walk(impl) if isinstance(n, ast.Assign) and any(
    isinstance(t, ast.Attribute) and t.attr == "placed" for t in n.targets)]
ok_rows = [n for n in report_calls if n.args and isinstance(n.args[1], ast.Constant)
           and n.args[1].value == "ok"]
check("the success row is emitted after `result.placed` is computed",
      placed_assigns and ok_rows
      and placed_assigns[0].lineno < ok_rows[0].lineno)

# --------------------------------------------------------------------------- #
# 4. The failure path
# --------------------------------------------------------------------------- #
print("4. failure path")
fail_rows = [n for n in report_calls if n.args and isinstance(n.args[1], ast.Constant)
             and n.args[1].value == "fail"]
check("exactly one failure row", len(fail_rows) == 1)
if fail_rows:
    row = fail_rows[0]
    enclosing = []
    cur = parents.get(id(row))
    while cur is not None:
        enclosing.append(cur)
        cur = parents.get(id(cur))
    not_grasped = [
        n for n in enclosing
        if isinstance(n, ast.If) and ast.unparse(n.test) == "not result.grasped"
    ]
    check("the failure row lives in the `if not result.grasped:` block",
          bool(not_grasped))
    if not_grasped:
        block = not_grasped[0]
        returns = [n for n in ast.walk(block) if isinstance(n, ast.Return)]
        hub_returns = [n for n in ast.walk(block)
                       if isinstance(n, ast.Call) and _call_name(n) == "_hub_return"]
        at_hub = [n for n in ast.walk(block) if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Attribute) and t.attr == "at_hub" for t in n.targets)]
        check("the failure block returns to the hub before ending the attempt",
              bool(hub_returns) and bool(returns)
              and hub_returns[0].lineno < row.lineno < returns[0].lineno)
        check("the failure block marks the attempt at_hub", bool(at_hub))

# --------------------------------------------------------------------------- #
# 5. The diagnostic row and the accounting
# --------------------------------------------------------------------------- #
print("5. diagnostic row and accounting")
report_src = ast.unparse(_func(tasks_tree, "_hub_report"))
for key in ("carry_in=", "hub_to_place=", "place_to_hub=", "infer=", "at_hub="):
    check(f"the row prints {key.rstrip('=')}", key in report_src)
check("the row reads `policy_inference_calls`", "policy_inference_calls" in report_src)

note_result = ast.unparse(_func(tasks_tree, "note_result"))
check("`note_result` subtracts the hub return from the attempt span",
      "hub_return_s" in note_result and "sim_end" in note_result)

# The row itself, executed with a fake task: the field layout and the `-` rule.
row_ns: dict = {}
row_say: list[str] = []
row_ns["say"] = row_say.append
exec(ast.unparse(_func(tasks_tree, "_hub_report")), row_ns)  # noqa: S102
row_fn = row_ns["_hub_report"]


class _RowTask:
    def __init__(self, calls):
        self.stats = {"attempts": 3}
        self.policy_inference_calls = calls


class _RowResult:
    arm = "left"
    placed = True
    at_hub = True


ok_marks = {"grasp": 10.0, "hub_carry": 11.0, "hub_place": 13.0, "hub_wait": 15.5}
row_fn(_RowTask(7), _RowResult(), "ok", ok_marks)
failed = _RowResult()
failed.placed = False
row_fn(_RowTask(None), failed, "fail", {"grasp": 10.0, "hub_carry": 11.0, "hub_wait": 13.5})
check("the success row carries the three legs and the call count",
      row_say
      and "carry_in=1.00s" in row_say[0]
      and "hub_to_place=2.00s" in row_say[0]
      and "place_to_hub=2.50s" in row_say[0]
      and "infer=7" in row_say[0]
      and "at_hub=1" in row_say[0],
      row_say[0] if row_say else "no row")
check("the failure row reports absent legs as `-` and `infer=n/a`",
      len(row_say) == 2 and "flow=fail" in row_say[1]
      and "hub_to_place=-" in row_say[1] and "place_to_hub=-" in row_say[1]
      and "infer=n/a" in row_say[1] and "at_hub=1" in row_say[1],
      row_say[1] if len(row_say) > 1 else "no row")

# The driver skips its own `go_ready` for a hub-ended attempt.
driver = ast.parse((ROOT / "scripts" / "20_pick_place.py").read_text())
guards = [
    n for n in ast.walk(driver)
    if isinstance(n, ast.If) and "at_hub" in ast.unparse(n.test)
]
check("the single-arm driver guards its `go_ready` on `at_hub`",
      len(guards) == 1
      and any(_call_name(s) == "go_ready" for s in ast.walk(guards[0]))
      and any("go_ready" in ast.unparse(s) for s in guards[0].body))

# --------------------------------------------------------------------------- #
# 6. The policy counter (rl_env)
# --------------------------------------------------------------------------- #
print("6. policy inference counter")
env_tree = _parse(RL_ENV)
env_src = RL_ENV.read_text()
sample_chunk = ast.unparse(_func(env_tree, "sample_chunk"))
check("one increment at the `policy.act` site",
      sample_chunk.count("self._infer_calls += 1") == 1
      and sample_chunk.index("policy.act") < sample_chunk.index("_infer_calls += 1"))
check("zeroed in reset and in __init__", env_src.count("self._infer_calls = 0") == 2)
counter = ast.unparse(_func(env_tree, "inference_calls"))
check("RTC chunk completions are added", "chunks_sampled" in counter)
run_primitive = ast.unparse(_func(env_tree, "_run_primitive"))
check("published before `grasp_carry_place`",
      run_primitive.index("policy_inference_calls")
      < run_primitive.index("self.task.grasp_carry_place("))
check("`policy_inferences` is in the outcome",
      "policy_inferences" in ast.unparse(_func(env_tree, "_finalize")))

tasks_md5 = hashlib.md5(TASKS.read_bytes()).hexdigest()
pinned = None
for node in ast.walk(env_tree):
    if isinstance(node, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "TASKS_MD5" for t in node.targets
    ):
        pinned = node.value.value
check("TASKS_MD5 matches the working-tree tasks.py", pinned == tasks_md5,
      f"{pinned} vs {tasks_md5}")

# --------------------------------------------------------------------------- #
# 7. The hub geometry (why there are two hubs)
# --------------------------------------------------------------------------- #
print("7. hub geometry")
cfg_text = (ROOT / "src" / "fruit_sorting" / "assets.py").read_text()
cfg = ast.parse(cfg_text)
defaults = {}
for node in ast.walk(cfg):
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        try:
            defaults[node.target.id] = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            pass
belt_top = defaults["belt_center"][2] + defaults["belt_size"][2] / 2.0
output_top = defaults["output_belt_top_z"]
#: The OpenArm fingers hang ~8 cm below the jaw centre
#: (`FRUIT_OPENARM_TRANSFER_LIFT`, and the carry's rail note in `jaw_target`).
hand_drop = 0.08
waypoints = json.loads(WAYPOINTS.read_text())
lift_z = belt_top + 0.28 + hand_drop
check("the carrying hub clears the output belt top with the hand's drop",
      lift_z - hand_drop > output_top,
      f"grasp_lift jaw z={lift_z:.2f} - {hand_drop:.2f} = "
      f"{lift_z - hand_drop:.2f} vs output top {output_top:.2f}")
ready_z = belt_top + 0.20
check("the waiting hub does not (a carried payload would sit in the output belt)",
      ready_z - hand_drop < output_top,
      f"ready jaw z={ready_z:.2f} - {hand_drop:.2f} = "
      f"{ready_z - hand_drop:.2f} vs output top {output_top:.2f}")
check("both hub poses are calibrated waypoints",
      all(name in waypoints["arms"]["left"] for name in ("ready", "grasp_lift"))
      and all(name in waypoints["arms"]["right"] for name in ("ready", "grasp_lift")))

print()
if failures:
    print(f"FAIL: {len(failures)} check(s)")
    for item in failures:
        print(f"  - {item}")
    raise SystemExit(1)
print("PASS: all checks")
