#!/usr/bin/env python3
"""P103 selftest: the patch-triggered **slip re-grip** (`FRUIT_SLIP_REGRIP`).

    python3 scripts/256_p103_regrip_selftest.py

No simulator (the `241` / `243` / `254` / `255` stub-the-imports pattern): the
**real** `parse_slip_regrip` runs, and the shipped re-seat block, the trigger's
guard clause and the action's wiring are pinned **as source facts** so a later
edit cannot quietly arm them on a path this phase did not measure.

Why each item matters. P102 measured the **signal** (a patch tactile sees the
loaded slide 21-113 ticks before the pinch is lost, 6 of 6 escapes) and priced
the **reaction** but did not build it (`logs/p102/RESULTS.md` §6). P103 builds
it out of the tree's own parts: the trigger is P102's channel, the action is the
shipped `slip_enabled` re-seat, and the scope is a two-line session. This leg
pins:

1. **The resolver**: unset/blank/`0` is off; a number is the trigger in metres;
   anything `0 < mm < 1` raises (P102's held legs read `dc_max` median 0.02 mm /
   p90 0.10 mm over 60 legs - a sub-millimetre threshold is the seat's noise);
   negative/`nan`/`inf`/non-numeric raise at construction.
2. **The attribute starts at 0 and the flag at False**, i.e. with the knob unset
   the shipped path is byte-inert (`_slip_regrip_active` is one bool per attempt
   and the per-tick branch is one bool).
3. **`guard_armed` gains exactly one term** (`self._slip_regrip_active`), so the
   trigger is self-sufficient: the W8-B tracker's `clean_slip` - the shipped
   abort ceiling's operand - comes with it.
4. **The trigger's own terms, in the registered order**: the **seat** test
   (P102's: `max(f0, f1) > 1 N` *and* `edge > -TACTILE_PAD_HALF_LONG`), the
   threshold, the `slip_react_max` ceiling - and **no** cooldown, no per-leg cap
   (the registered per-tick shape, `logs/p103/PREREG.md` §0.2).
5. **The action is the shipped re-seat and not a copy**: the `[regrip]` branch
   computes `target = fruit - rot @ slip_ref`, `correction = target - pads`,
   re-bases `commands[i + 1 :]` and writes `_grip_centre`/`_closed_gap` - the
   same five expressions the `slip_enabled` block uses, and the shipped block
   itself is **unchanged** (`scripts/255`'s body-of check on the `slip_enabled`
   body).
6. **The scope is a session predicate**: `_slip_regrip_active` is resolved per
   attempt from `self.two_line_enabled()`, so a single-arm, shared-station,
   direct or hybrid path cannot arm it.
7. **The row grammar**: one first-fire row and one per-leg `done` row, with the
   field set and order `logs/p103/p103_report.py` reads (a rename is a silent
   ledger break otherwise), parsed back through that report's own regexes.

Exit 0 on pass, 1 on the first failure. No simulator, no file writes.
"""
from __future__ import annotations

import os
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# --- stub pxr / isaacsim just enough to import fruit_sorting.tasks ---------- #
for name in (
    "pxr",
    "isaacsim",
    "isaacsim.core",
    "isaacsim.core.experimental",
    "isaacsim.sensors",
    "isaacsim.sensors.experimental",
    "isaacsim.core.experimental.utils",
    "isaacsim.core.experimental.objects",
    "isaacsim.core.experimental.utils.app",
    "isaacsim.core.experimental.utils.stage",
    "isaacsim.core.experimental.prims",
):
    module = sys.modules.setdefault(name, types.ModuleType(name))
    module.__path__ = []
pxr = sys.modules["pxr"]
for attr in ("Gf", "PhysxSchema", "Sdf", "Usd", "UsdGeom", "UsdPhysics", "UsdShade"):
    if not hasattr(pxr, attr):
        setattr(pxr, attr, types.ModuleType(f"pxr.{attr}"))
sys.modules["isaacsim.core.experimental.utils.app"].update_app = lambda **kwargs: None
sys.modules["isaacsim.core.experimental.utils.stage"].create_prim = lambda *a, **k: None
prims_mod = sys.modules["isaacsim.core.experimental.prims"]
prims_mod.RigidPrim = object
prims_mod.Articulation = object
objects_mod = sys.modules["isaacsim.core.experimental.objects"]
objects_mod.DistantLight = object
objects_mod.GroundPlane = object
sys.modules.setdefault(
    "isaacsim.core.simulation_manager",
    types.SimpleNamespace(
        SimulationManager=types.SimpleNamespace(step=staticmethod(lambda **kw: None))
    ),
)
sys.modules.setdefault(
    "isaacsim.core.rendering_manager",
    types.SimpleNamespace(
        RenderingManager=types.SimpleNamespace(render=staticmethod(lambda: None))
    ),
)
sensors_mod = types.ModuleType("isaacsim.sensors.experimental.physics")
sensors_mod.Contact = object
sensors_mod.ContactSensor = object
sys.modules.setdefault("isaacsim.sensors.experimental.physics", sensors_mod)
rtx_mod = types.ModuleType("isaacsim.sensors.experimental.rtx")
rtx_mod.CameraSensor = object
rtx_mod.RtxCamera = object
sys.modules.setdefault("isaacsim.sensors.experimental.rtx", rtx_mod)

import fruit_sorting.tasks as tasks_mod  # noqa: E402
from fruit_sorting.tasks import (  # noqa: E402
    SLIP_REGRIP_FLOOR_MM,
    TACTILE_PAD_HALF_LONG,
    parse_slip_regrip,
)

sys.path.insert(0, str(ROOT / "logs" / "p103"))
import p103_report  # noqa: E402  (the report's own row readers)

TASKS = ROOT / "src" / "fruit_sorting" / "tasks.py"
TASKS_SRC = TASKS.read_text(encoding="utf-8")


def check(cond: bool, what: str) -> None:
    if not cond:
        print(f"FAIL: {what}")
        raise SystemExit(1)
    print(f"ok: {what}")


def body_of(src: str, header: str) -> str:
    """The indented body of the **last** line whose stripped text is `header`.

    Line-based on purpose: a substring search would also match the tail of a
    more-indented line (e.g. the same statement nested one block deeper), and
    then the indent arithmetic silently reports the wrong body.
    """
    want = header.strip()
    lines = src.splitlines()
    index = max(i for i, line in enumerate(lines) if line.strip() == want)
    indent = len(lines[index]) - len(lines[index].lstrip())
    out = []
    for line in lines[index + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        out.append(line)
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# 1. the resolver
# --------------------------------------------------------------------------- #
print("-- 1 the resolver")
check(parse_slip_regrip("") == 0.0, "unset/blank is off (0.0)")
check(parse_slip_regrip("0") == 0.0, "`0` is off (0.0)")
check(parse_slip_regrip("2.12") == 0.00212, "`2.12` is 0.00212 m")
check(parse_slip_regrip(" 3 ") == 0.003, "whitespace and an int-like value parse")
check(parse_slip_regrip("1") == 0.001, "the floor itself is accepted")
for bad, why in (
    ("-1", "negative"),
    ("0.5", "below the floor"),
    ("nan", "nan"),
    ("inf", "inf"),
    ("x", "non-numeric"),
):
    try:
        parse_slip_regrip(bad)
    except ValueError:
        print(f"ok: {bad!r} ({why}) raises")
    else:
        check(False, f"{bad!r} ({why}) must raise")
check(SLIP_REGRIP_FLOOR_MM == 1.0, "the floor is 1.0 mm (P102's held-leg p90 is 0.10)")

# --------------------------------------------------------------------------- #
# 2. the attribute defaults: the shipped path is inert
# --------------------------------------------------------------------------- #
print("-- 2 the shipped path is inert")
check("self.slip_regrip_m = parse_slip_regrip()" in TASKS_SRC,
      "the attribute is built by the resolver")
check(re.search(r"self\._slip_regrip_active = False", TASKS_SRC) is not None,
      "the resolved flag starts False")
# comments may *discuss* the removed form; the code must not contain it
_CODE = "\n".join(
    line for line in TASKS_SRC.splitlines()
    if not line.lstrip().startswith("#")
)
check("SLIP_REGRIP_MAX_FIRES" not in _CODE
      and "SLIP_REGRIP_COOLDOWN" not in _CODE,
      "no cooldown / per-leg cap in the code (the registered per-tick shape)")
check("regrip_cool" not in _CODE, "no cooldown counter at all")

# --------------------------------------------------------------------------- #
# 3. guard_armed gains exactly one term
# --------------------------------------------------------------------------- #
print("-- 3 guard_armed")
armed = body_of(TASKS_SRC, "guard_armed = bool(")
check("or self._slip_regrip_active" in armed, "the trigger arms the W8-B block")
check(armed.count("or self._") == 5,
      "exactly five disjuncts (diag/guard, place trace, tactile, fail fast, regrip)")
check("and hand_is_jaw" in armed and "and self._dynamic_capture_active" in armed,
      "and keeps the jaw-hand / dynamic-capture scope")

# --------------------------------------------------------------------------- #
# 4. the trigger's terms
# --------------------------------------------------------------------------- #
print("-- 4 the trigger")
trig = body_of(TASKS_SRC, "if self._slip_regrip_active:")
check("tactile_patch_state(" in trig, "the trigger reads the P102 patch state")
check("arm.jaw_positions()" in trig, "from the measured pad origins")
check("_rg_strong > 1.0" in trig, "the loaded-pinch half of P102's seat test")
check("_rg_state[\"edge\"] > -TACTILE_PAD_HALF_LONG" in trig,
      "the patch-on-the-pad half of P102's seat test")
check("_rg_dc >= self.slip_regrip_m" in trig, "the threshold")
check("guard_slip <= slip_react_max" in trig, "the shipped abort ceiling")
check("regrip_cool" not in trig, "no cooldown")
check(f"{TACTILE_PAD_HALF_LONG:.6f}" not in trig,
      "the half-length is read from the constant, not re-typed")

# --------------------------------------------------------------------------- #
# 5. the action IS the shipped re-seat
# --------------------------------------------------------------------------- #
print("-- 5 the action")
shipped = body_of(TASKS_SRC, "if slip_enabled:")
check("target = fruit - rot @ slip_ref" in shipped, "the shipped target expression")
check("correction = target - pads" in shipped, "the shipped correction")
check("commands[i + 1 :] = (" in shipped, "the shipped command re-base")
check("self._closed_gap[side] = gap_command" in shipped, "the shipped gap write")
check("slip_trigger < slip <= slip_react_max" in shipped,
      "the shipped trigger is unchanged (it still gates on the 25 mm slip)")
act = body_of(TASKS_SRC, "if regrip_pending is not None:")
for expr in (
    "target = fruit - rot @ slip_ref",
    "correction = target - pads",
    "reseated = pads + correction",
    "commands[i + 1 :] = (",
    "self._grip_centre[side] = np.asarray(placed, dtype=float)",
    "self._closed_gap[side] = gap_command",
):
    check(expr in act, f"the [regrip] branch uses the shipped `{expr.split(' =')[0]}`")
check("ik_step(" not in act, "no new IK step in the action")
check("_step_sim(" not in act, "the action costs no extra tick")

# --------------------------------------------------------------------------- #
# 6. the scope is the session predicate
# --------------------------------------------------------------------------- #
print("-- 6 the scope")
scope = body_of(TASKS_SRC, "self._slip_regrip_active = bool(")
check("self.slip_regrip_m > 0.0" in scope, "the threshold gates it")
check("self.two_line_enabled()" in scope, "and the two-line session predicate")
check("scripted" not in scope, "no ambient (env) read")

# --------------------------------------------------------------------------- #
# 7. the row grammar, read back by the report's own regexes
# --------------------------------------------------------------------------- #
print("-- 7 the row grammar")
row = ("[fruit] [regrip] left grasp_lift t=59/159 dc=3.07mm slip=3.07mm "
       "correction=3.06mm seat_f=2.85N seat_edge=+10.5mm seat_frac=0.604")
m = p103_report.REGRIP.search(row)
check(m is not None, "the first-fire row parses")
check(m.group("arm") == "left" and m.group("leg") == "grasp_lift",
      "with its arm and leg")
check(abs(float(m.group("dc")) - 3.07) < 1e-9, "and its dc")
done = ("[fruit] [regrip] left grasp_lift done fires=25 first_t=59/159 "
        "first_dc=3.07mm first_correction=3.06mm clean_slip_max=8.3mm "
        "force_min=0.00N")
m2 = p103_report.REGRIP_END.search(done)
check(m2 is not None, "the per-leg done row parses")
check(int(m2.group("fires")) == 25, "with its fire count")
carry = ("[fruit] [carry] left grasp_lift: ticks=159/159 clean_slip_max=8.3mm "
         "slip_xyz=(2.6,7.9,0.2)mm hold_drift=1.2deg(no-hold) drift_end=0.8 "
         "res_end=5.6mm dz_end=-5.0mm clr=n/a clr_win=n/a clr_min=+50mm@belt "
         "clr_edge=n/a clr_edge_min=n/a q_margin=-0.000@j2/t117 "
         "q_cmd_margin=0.000@j2 q_step_max=0.0300 jaw_z=+0.0094/0.0121 "
         "tilt0=0.6 tilt_end=0.7 tilt_max=0.9 t45=- t75=- tilt_rate=-0.0405/t98 "
         "drift_on=None in-hand_vmax=0.122 onset_row=58 force@onset=3.58N "
         "sep@onset=77.6mm contacts@onset=1 min_contacts=0 force_min=0.00N "
         "loss_row=77 sep@loss=79.5mm sep_end=92.4mm dia=66.4 sep_max=93.7@t138 "
         "gap@sep_max=49.8 sep_min=76.1 fmax=5.32N guard=0 events=0 holds=0 "
         "reseat=0.0mm relief=0 gap_start=64.8mm open_max=0.0mm")
m3 = p103_report.CARRY.search(carry)
check(m3 is not None, "the `[carry]` row the ledger joins on parses")
check(m3.group("arm") == "left" and m3.group("leg") == "grasp_lift",
      "with the arm/leg the fire is matched to")
check(abs(float(m3.group("slip")) - 8.3) < 1e-9, "and its clean_slip_max")
# a `n/a` field must still parse (the never-held leg's `sep_min`)
check(p103_report.CARRY.search(carry.replace("sep_min=76.1", "sep_min=n/a"))
      is not None, "`sep_min=n/a` parses (a never-held leg)")

print("\nP103 slip re-grip: every pin holds")
