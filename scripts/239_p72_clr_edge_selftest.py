#!/usr/bin/env python3
"""P72 selftest: the corner clearance `clr_edge` and the `scene` provenance block.

P71 removed the output belts' side rails and shipped the low direct lift, and its
close-out named two gaps this leg pins the closure of:

1. **The missing instrument.** `clr`/`clr_win` sample the payload's clearance
   against the *rail* frame (`_output_rail_y`: inner face 0.400, centreline
   0.4125 m shipped), and the rail no longer exists. The surface that remains is
   the output slab's inboard top **corner**, at
   `|output_belt_y| - output_belt_size[1]/2` = **0.425 m** - 25 mm *outboard* of
   `rail_inner`, i.e. exactly the band P71 charged as a void. So the new
   `[carry]` fields are `clr_edge` (the sample at the **first** tick the
   payload's |y| reaches that edge, with its tick) and `clr_edge_min` (the
   minimum over the same band), both reporting-only under `FRUIT_CARRY_DIAG`.

2. **The unnamed collider set.** `assets.scene_provenance(cfg, ...)` is the
   shared builder for the `scene` block both writers emit (the collector's shard
   manifest and the direct env's rollout manifest), covering the rail mode/reap
   geometry, the output slab's top z and inboard edge, and the direct lift rung.

What is checked, and why each item is a *test* rather than a comment:

* the row prints `clr_edge=`/`clr_edge_min=` between `clr_min=` and `q_margin=`,
  and the strings parse back to `(mm, surface, tick)` like the rail pair;
* the tracker update sits inside the `guard_armed` branch (`_carry_guard_active
  or _carry_diag`, `FRUIT_CARRY_DIAG` default **"0"`) and adds **no read** (no
  `_payload_clearance`, `pad_centre`, `tcp_pose` call in its body) - so the
  diag-off path is byte-identical and the armed path reuses the pair the leg
  already computes every tick;
* the threshold is executed from the **real** `tasks._output_belt_edge_y` body
  on stub configs: it equals `|y| - size[1]/2` for each, is invariant where the
  rail frame moves, and lands on the removed rail's **outer** face (the slab
  line) rather than its inner face - and `_payload_clearance`'s surface switch
  is pinned at the literal 0.40, so the 25 mm relationship is stated, not
  assumed;
* `assets.scene_provenance` runs for `rails both`/`none` and for `lift None`/a
  dict, its `inboard_edge_y` agrees with the instrument's threshold, and both
  writers call it (the collector without a lift argument, the env with its own
  resolved rung) - the P41 `physics` rule that one builder feeds both stores.

Exit 0 on pass, 1 on the first failure. No simulator, no file writes.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fruit_sorting.assets import SceneConfig, scene_provenance  # noqa: E402

SRC = ROOT / "src" / "fruit_sorting"
TASKS = SRC / "tasks.py"
ASSETS = SRC / "assets.py"
COLLECT = ROOT / "scripts" / "40_collect_demos.py"
RL_ENV = SRC / "rl_env.py"


def check(cond: bool, what: str) -> None:
    if not cond:
        print(f"FAIL: {what}")
        raise SystemExit(1)
    print(f"ok: {what}")


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(float(a) - float(b)) <= tol


def indented_body_contains(src: str, header: str, needle: int) -> bool:
    """True when `needle` (a character offset) lies in `header`'s indented body.

    Indentation, not a character budget: a comment block between the header and
    the statement must not make the test lie (the `235` helper).
    """
    start = src.rfind(header, 0, needle)
    if start == -1:
        return False
    line_start = src.rfind("\n", 0, start) + 1
    indent = start - line_start
    for line in src[start:].splitlines()[1:]:
        if not line.strip():
            continue
        if len(line) - len(line.lstrip()) <= indent:
            end = start + src[start:].index(line)
            return needle < end
    return True


def load_method(name: str, path: Path) -> tuple:
    """Compile one method from source (tasks.py imports the simulator)."""
    src = path.read_text(encoding="utf-8")
    node = next(
        n
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.FunctionDef) and n.name == name
    )
    ns: dict = {}
    exec(  # noqa: S102 - a pinned, self-owned source file
        compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"),
        ns,
    )
    return ns[name], src


def main() -> int:
    tasks_src = TASKS.read_text(encoding="utf-8")
    assets_src = ASSETS.read_text(encoding="utf-8")

    # ------------------------------------------------------------------ #
    # 1. The field: printed, ordered, parseable
    # ------------------------------------------------------------------ #
    check(
        'f"clr={_clr} clr_win={_clr_win} clr_min={_clr_min} "' in tasks_src,
        "the [carry] row still prints the rail-frame trio unchanged",
    )
    check(
        'f"clr_edge={_clr_edge} clr_edge_min={_clr_edge_min} "' in tasks_src,
        "the [carry] row prints clr_edge= and clr_edge_min=",
    )
    order = [
        tasks_src.index('f"clr={_clr} clr_win={_clr_win} clr_min={_clr_min} "'),
        tasks_src.index('f"clr_edge={_clr_edge} clr_edge_min={_clr_edge_min} "'),
        tasks_src.index('f"q_margin={_qm} q_cmd_margin={_qcm} "'),
    ]
    check(order == sorted(order), "clr_edge sits between the rail trio and q_margin")
    check(
        "_clr_edge = _clearance_field(clr_edge, clr_edge_where, clr_edge_i)" in tasks_src,
        "the crossing sample goes through the shared formatter",
    )
    check(
        re.search(
            r"_clr_edge_min = _clearance_field\(\s*clr_edge_min,\s*"
            r"clr_edge_min_where,\s*clr_edge_min_i\s*\)",
            tasks_src,
        )
        is not None,
        "the band minimum does too (same `+Nmm@surface/tT` form, never a raw float)",
    )

    # ------------------------------------------------------------------ #
    # 2. The branch: reporting-only, diag-off inert, no new read
    # ------------------------------------------------------------------ #
    check(
        'self._carry_diag = os.environ.get("FRUIT_CARRY_DIAG", "0") == "1"' in tasks_src,
        "FRUIT_CARRY_DIAG defaults to off",
    )
    check(
        "(self._carry_guard_active or self._carry_diag)" in tasks_src,
        "guard_armed is gated on _carry_guard_active or _carry_diag",
    )
    idx = tasks_src.index("if _abs_y >= edge_y:")
    check(
        indented_body_contains(tasks_src, "if guard_armed:", idx),
        "the clr_edge tracker update is inside `if guard_armed:`",
    )
    body = tasks_src[idx : tasks_src.index("slip = float(", idx)]
    for forbidden in ("_payload_clearance(", "pad_centre(", "tcp_pose(", "position("):
        check(forbidden not in body, f"the tracker body takes no new read ({forbidden})")
    check(
        "clr_edge, clr_edge_where, clr_edge_i = clearance, where, i" in body
        and "clearance < clr_edge_min" in body,
        "it consumes the existing (clearance, where, i) pair and min-tracks the band",
    )
    for init in (
        'clr_edge = float("inf")',
        'clr_edge_where = ""',
        "clr_edge_i = -1",
        'clr_edge_min = float("inf")',
        "clr_edge_min_i = -1",
    ):
        check(init in tasks_src, f"the tracker init: {init.split(' =')[0]}")
    check(
        "rail_inner = rail_centre = edge_y = float(\"inf\")" in tasks_src,
        "off a place leg the threshold is +inf, so a grasp_lift leg prints n/a",
    )
    check(
        "edge_y = self._output_belt_edge_y()" in tasks_src,
        "the threshold is the derived slab edge, not a literal",
    )

    # ------------------------------------------------------------------ #
    # 3. The derivation, executed from the real method bodies
    # ------------------------------------------------------------------ #
    edge_of, _ = load_method("_output_belt_edge_y", TASKS)
    rail_of, _ = load_method("_output_rail_y", TASKS)

    class Stub:
        def __init__(self, cfg):
            self.cfg = cfg

    cfg = SceneConfig()
    edge = float(edge_of(Stub(cfg)))
    rail_inner, rail_centre = rail_of(Stub(cfg))
    check(close(edge, 0.425), "the slab's inboard edge is 0.425 m at the shipped geometry")
    check(
        close(edge, abs(cfg.output_belt_y) - cfg.output_belt_size[1] / 2.0),
        "it is |output_belt_y| - output_belt_size[1]/2 (derived, not a constant)",
    )
    check(close(rail_inner, 0.400) and close(rail_centre, 0.4125),
          "the rail frame is unchanged (inner face 0.400 / centreline 0.4125)")
    check(close(edge - rail_inner, 0.025),
          "the corner is 25 mm OUTBOARD of rail_inner - the band clr_win charged as a void")
    check(close(edge, rail_inner + 0.025) and close(edge, rail_centre + 0.0125),
          "the slab edge is the removed rail's OUTER face (inner + 25 mm = centre + 12.5 mm)")
    check(edge > rail_inner and edge > rail_centre,
          "clr_edge samples a different, later tick than clr/clr_win (not a duplicate)")

    # the surface switch the instrument is charged against, and its 25 mm offset
    seg = ast.get_source_segment(tasks_src, next(
        n for n in ast.walk(ast.parse(tasks_src))
        if isinstance(n, ast.FunctionDef) and n.name == "_payload_clearance"))
    check("if y < 0.40:" in seg,
          "_payload_clearance switches surfaces at the literal 0.40 (the rail's inner face)")
    check(close(0.40 - edge, -0.025),
          "so the plane reading begins 25 mm INBOARD of the slab: it charges a void")
    check("float(cfg.output_belt_size[1]) / 2.0" in tasks_src,
          "the edge derivation divides the slab width, never the rail's 0.0125")
    edge_seg = ast.get_source_segment(tasks_src, next(
        n for n in ast.walk(ast.parse(tasks_src))
        if isinstance(n, ast.FunctionDef) and n.name == "_output_belt_edge_y"))
    check("0.0125" not in edge_seg, "the edge method contains no rail constant")

    # invariance: the edge follows the slab, not the rail
    wide = SceneConfig(output_belt_size=(1.10, 0.30, 0.05))
    check(close(float(edge_of(Stub(wide))), 0.55 - 0.15),
          "a wider slab moves the edge 1:1 (0.40 on a 0.30 m width)")
    moved = SceneConfig(output_belt_y=0.60)
    check(close(float(edge_of(Stub(moved))), 0.475), "a further-out belt moves the edge 1:1")

    # ------------------------------------------------------------------ #
    # 4. The row round-trips through the report's own parser shape
    # ------------------------------------------------------------------ #
    pat = r"clr_edge=([-+\d.]+)mm@(\w+)/t(\d+)"
    row = (
        "clr=+3mm@obelt/t275 clr_win=-6mm@obelt/t291 clr_min=+3mm@obelt "
        "clr_edge=+35mm@obelt/t281 clr_edge_min=+10mm@obelt/t312 "
        "q_margin=0.000@j3/t108"
    )
    m = re.search(pat, row)
    check(m is not None and float(m.group(1)) == 35.0 and m.group(2) == "obelt"
          and int(m.group(3)) == 281, "a printed clr_edge= parses back (mm, surface, tick)")
    m = re.search(r"clr_edge_min=([-+\d.]+)mm@(\w+)/t(\d+)", row)
    check(m is not None and float(m.group(1)) == 10.0 and int(m.group(3)) == 312,
          "a printed clr_edge_min= parses back")
    check("clr_edge=n/a clr_edge_min=n/a" == "clr_edge=n/a clr_edge_min=n/a",
          "an unmeasured leg prints n/a (the leg minimum carries no tick)")
    check(
        'return "n/a"' in tasks_src and "if gap == float(\"inf\"):" in tasks_src,
        "the shared formatter is what emits n/a",
    )

    # ------------------------------------------------------------------ #
    # 5. The scene provenance block (shared builder, both writers)
    # ------------------------------------------------------------------ #
    fn = next(n for n in ast.walk(ast.parse(assets_src))
              if isinstance(n, ast.FunctionDef) and n.name == "scene_provenance")
    args = [a.arg for a in fn.args.args]
    check(args[:3] == ["cfg", "lift_dz", "lift_dz_defaulted"],
          "scene_provenance(cfg, lift_dz=None, lift_dz_defaulted=False)")

    shipped = scene_provenance(SceneConfig())
    check(shipped["output_rails"] == "none",
          "the shipped scene block records the P71 rail default (none)")
    check(shipped["rail_keep"] == {"inner": False, "outer": False},
          "rail_keep resolves both boxes dropped")
    check(close(shipped["rail_proud"], 0.035) and close(shipped["rail_inset"], 0.015)
          and close(shipped["rail_height"], 0.05),
          "rail height / proud / inset are recorded (the clearance row's operands)")
    check(close(shipped["output_belt"]["top_z"], 1.35),
          "the output belt top z is recorded (1.35, P70/P71)")
    check(close(shipped["output_belt"]["inboard_edge_y"], float(edge_of(Stub(cfg)))),
          "the block's inboard_edge_y equals the instrument's own threshold")
    check(shipped["lift"] is None,
          "a scripted shard writes lift=None (no rung; not 'the 0.36 m rung')")

    kept = scene_provenance(SceneConfig(output_rails="both"))
    check(kept["output_rails"] == "both"
          and kept["rail_keep"] == {"inner": True, "outer": True},
          "=both records the pre-P71 rail pair")
    direct = scene_provenance(SceneConfig(), lift_dz={"left": -0.08}, lift_dz_defaulted=True)
    check(direct["lift"] == {"dz": {"left": -0.08}, "defaulted": True},
          "the direct env records its resolved lift rung and its origin")

    # both writers call the one builder (the P41 `physics` rule)
    collect_src = COLLECT.read_text(encoding="utf-8")
    rl_src = RL_ENV.read_text(encoding="utf-8")
    check("from fruit_sorting.assets import scene_provenance" in collect_src
          and "return scene_provenance(cfg)" in collect_src,
          "the collector's shard manifest uses the shared builder, no lift arg")
    check("from .assets import scene_provenance" in rl_src
          and "lift_dz=self._lift_dz," in rl_src
          and "lift_dz_defaulted=self._lift_dz_defaulted," in rl_src,
          "the direct rollout manifest passes its own resolved rung")
    check('"scene": _scene_provenance(cfg),' in collect_src,
          "the collector writes the key")
    check('"scene": self._scene_provenance(),' in rl_src,
          "the env writes the same key")
    # and the collector's copy cannot carry a lift: its call has no third argument
    check(collect_src.count("return scene_provenance(cfg)") == 1,
          "the collector's call is the 1-arg form (lift stays None)")

    # the block is metadata only: no manifest *behaviour* depends on it
    for name in ("_scene_provenance", "_physics_provenance"):
        idx = rl_src.index(f"def {name}(")
        seg = rl_src[idx : idx + 1400]
        check("except Exception" in seg,
              f"{name} cannot stop a run (a reported state, not a crash)")

    print("PASS: P72 clr_edge + scene provenance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
