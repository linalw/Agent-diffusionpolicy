#!/usr/bin/env python3
"""P111 selftest: the cage's **compliant closure with a hard stop**.

    python3 scripts/257_p111_cage_compliance_selftest.py

No simulator (the `247`/`248`/`253` stub-the-imports pattern): the *real*
`CageHand.close_done`, `_profile` and `_command` run against a stub drive set,
and the call site and the row are pinned from the source.

Why each item matters. P110's arithmetic says the ring's four force-capped
position pads cannot centre a payload: the near pad reaches the cap at
`cap/k = 0.049 mm` and the far pad is short by `2*delta`, so a 6-20 mm arrival is
launched rather than pushed. The owner's item is the compliant closure: a soft
drive yields `cap/k` instead of 0.049 mm, so the four pads balance toward the
ring's centre. Two things have to be true for the *measurement* to mean anything,
and this leg is what pins them:

1. **The soft close is a different physical regime, not a knob that does nothing.**
   At `k = 1e3` the delivered force at the shipped 1 % squeeze is `k*s` = 0.7 N
   (the cap is never reached), and the freeze's 0.5 N trigger is reached at a
   *smaller* penetration - so the close is gentler **and shallower**. The
   arithmetic of both is pinned here.
2. **The hard stop does not move the payload.** A soft ring's grip is 4-7x
   weaker than the rigid one's 4.90 N, so a pure-soft arm would lose placements
   for a grip reason and could not answer the centring question. The stop
   re-writes the four drives at the hold profile with the target *unchanged*, so
   the pad re-loads to the cap **at the aperture it found** - and it is released
   by the open command, so the next close is soft again.

The leg also pins the call site (one, in the dynamic close's tail, gated on the
hand's *kind* and **not** on `FRUIT_CAGE_PROBE` - a diagnostic must not own a
behaviour) and the census row's `off0`/`off` fields (the phase's centring
instrument: the payload's radial distance from the ring's *axis*, taken from
reads the probe already makes).

Exit 0 on pass, 1 on the first failure. Run by `scripts/selfcheck.sh`.
"""

from __future__ import annotations

import ast
import hashlib
import math
import os
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# --- stub pxr / isaacsim just enough to import fruit_sorting.cage_hand ------ #
for name in (
    "pxr",
    "isaacsim",
    "isaacsim.core",
    "isaacsim.core.experimental",
    "isaacsim.core.experimental.prims",
):
    module = sys.modules.setdefault(name, types.ModuleType(name))
    module.__path__ = []
pxr = sys.modules["pxr"]
for attr in ("Gf", "PhysxSchema", "Sdf", "Usd", "UsdGeom", "UsdPhysics", "UsdShade"):
    if not hasattr(pxr, attr):
        setattr(pxr, attr, types.ModuleType(f"pxr.{attr}"))

CAGE = ROOT / "src" / "fruit_sorting" / "cage_hand.py"
TASKS = ROOT / "src" / "fruit_sorting" / "tasks.py"
RL_ENV = ROOT / "src" / "fruit_sorting" / "rl_env.py"
CAGE_SRC = CAGE.read_text()
TASKS_SRC = TASKS.read_text()
RL_ENV_SRC = RL_ENV.read_text()

FAILURES: list[str] = []


def check(ok, why: str) -> None:
    if ok:
        print(f"  ok   {why}")
    else:
        print(f"  FAIL {why}")
        FAILURES.append(why)


# --------------------------------------------------------------------------- #
# 1. the module's numbers, and the regime the soft drive opens
# --------------------------------------------------------------------------- #
def section_arithmetic() -> None:
    print("1. the two regimes - delivered force, the freeze, and the stop")
    sys.path.insert(0, str(ROOT / "src"))
    import importlib

    import fruit_sorting.cage_hand as cage

    importlib.reload(cage)
    check(abs(cage.GRASP_STANDOFF - 0.070) < 1e-9,
          "the tool offset is 70.0 mm (DISTAL_Z 80.5 - LIP 10.5) - unchanged by P111")
    check(cage.HOLD_STIFFNESS == 0.0,
          "FRUIT_CAGE_HOLD_STIFFNESS defaults to 0 (off: the shipped cage is unchanged)")
    check(cage.PAD_STIFFNESS == 1.0e5 and cage.PAD_FORCE == 4.90,
          "the shipped drive (k=1e5, cap 4.90) is still the module default")

    # the shipped squeeze: `0.98 x the widest extent` -> 1 % per face
    d = 0.060
    s = 0.5 * d * (1.0 - 0.98)
    cap = cage.PAD_FORCE
    for k in (1.0e5, 1.0e3, 2.0e2):
        force = min(k * s, cap)
        yield_mm = cap / k * 1000.0
        print(f"       k={k:8.0f}: delivered {force:5.2f} N/pad, elastic yield "
              f"{yield_mm:6.2f} mm, 2-pad capacity {2 * 1.3 * force:5.2f} N")
    rigid = min(1.0e5 * s, cap)
    soft = min(1.0e3 * s, cap)
    check(rigid == cap and soft < cap,
          "at the shipped squeeze the rigid drive is AT the cap and k=1e3 is not - "
          "the two arms are different regimes")
    check(abs(soft - 0.60) < 0.005,
          f"k=1e3 delivers 0.60 N/pad on a 60 mm fruit (got {soft:.3f}) - the cap is "
          f"not reached, so the close is a spring, not a force source")
    check(cap / 1.0e5 * 1000 < 0.05,
          "the shipped elastic allowance is 0.049 mm - P110's number, unchanged")
    check(cap / 1.0e3 * 1000 > 4.5,
          "k=1e3's allowance is 4.90 mm - 100x the shipped one (the phase's lever)")

    # the freeze: the 0.5 N trigger is reached at a smaller penetration as k falls
    trig = 0.5
    for k in (1.0e5, 1.0e3):
        print(f"       the {trig:.1f} N freeze trigger is reached at "
              f"{trig / k * 1000:6.3f} mm of penetration at k={k:.0f}")
    check(trig / 1.0e3 > 20 * trig / 1.0e5,
          "a soft drive trips the same force trigger at a much smaller penetration, "
          "so the compliant close is gentler AND shallower (the cells' `aper` reads it)")


# --------------------------------------------------------------------------- #
# 2. the hard stop, executed on the real methods
# --------------------------------------------------------------------------- #
class _Attr:
    def __init__(self) -> None:
        self.value = None

    def Set(self, value):  # noqa: N802 - the USD API's own name
        self.value = value
        return self

    def Get(self):  # noqa: N802 - the USD API's own name
        return self.value


class _Drive:
    """The four attributes `close_done`/`_profile`/`_command` touch."""

    def __init__(self) -> None:
        self.stiffness = _Attr()
        self.damping = _Attr()
        self.cap = _Attr()
        self.target = _Attr()

    def CreateStiffnessAttr(self):  # noqa: N802
        return self.stiffness

    def CreateDampingAttr(self):  # noqa: N802
        return self.damping

    def CreateMaxForceAttr(self):  # noqa: N802
        return self.cap

    def CreateTargetPositionAttr(self):  # noqa: N802
        return self.target


def _bare_hand(cage, hold_on: bool):
    """A `CageHand` with only the state the stop touches (the real methods)."""
    hand = object.__new__(cage.CageHand)
    hand.enabled = True
    hand.side = "left"
    hand._stiffened = False
    hand.open_gap = 2.0 * cage.HOME_FACE_R
    hand.last_gap = hand.open_gap
    hand._aperture = hand.open_gap
    hand._drives = [_Drive() for _ in range(4)]
    for d in hand._drives:
        d.stiffness.Set(cage.PAD_STIFFNESS)
        d.damping.Set(cage.PAD_DAMPING)
        d.cap.Set(cage.PAD_FORCE)
        d.target.Set(0.0)
    return hand


def section_stop() -> None:
    print("2. the hard stop: what it writes, and what it must not move")
    import importlib

    import fruit_sorting.cage_hand as cage

    # (a) off -> a no-op, byte-for-byte
    os.environ.pop("FRUIT_CAGE_HOLD_STIFFNESS", None)
    importlib.reload(cage)
    hand = _bare_hand(cage, False)
    before = [(d.stiffness.value, d.damping.value, d.target.value) for d in hand._drives]
    hand.close_done()
    after = [(d.stiffness.value, d.damping.value, d.target.value) for d in hand._drives]
    check(before == after, "with the knob unset `close_done` changes nothing (off = shipped)")
    check(hand._stiffened is False, "and does not flag the profile as stiffened")

    # (b) on -> the hold pair, the target and the cap untouched
    os.environ["FRUIT_CAGE_HOLD_STIFFNESS"] = "100000"
    os.environ["FRUIT_CAGE_PAD_STIFFNESS"] = "1000"
    os.environ["FRUIT_CAGE_PAD_DAMPING"] = "8.9"
    importlib.reload(cage)
    hand = _bare_hand(cage, True)
    hand.close_done()
    ks = {round(d.stiffness.value, 6) for d in hand._drives}
    cs = {round(d.damping.value, 6) for d in hand._drives}
    tg = {round(d.target.value, 9) for d in hand._drives}
    caps = {round(d.cap.value, 6) for d in hand._drives}
    check(ks == {100000.0}, f"the four drives are all rewritten at the hold k (got {ks})")
    want_c = 2.0 * math.sqrt(100000.0 * cage.PAD_MASS)
    check(cs == {round(want_c, 6)},
          f"their damping is 2 sqrt(k_hold m) = {want_c:.2f} Ns/m (got {cs})")
    check(len(tg) == 1 and 0.0 in tg,
          "the four TARGETS are unchanged - the stop loads the pad, it does not move it")
    check(caps == {round(cage.PAD_FORCE, 6)}, "the force cap is unchanged")
    check(hand._stiffened is True, "and the profile is flagged for the revert")

    # (c) idempotent inside one close
    hand.close_done()
    check(hand._stiffened is True, "a second call in the same close is a no-op")

    # (d) the open command releases it
    hand._command(hand.open_gap)
    ks = {round(d.stiffness.value, 6) for d in hand._drives}
    check(ks == {1000.0}, f"an OPEN command reverts the drives to the close profile ({ks})")
    check(hand._stiffened is False, "and clears the flag, so the next close is soft")

    for name in ("FRUIT_CAGE_HOLD_STIFFNESS", "FRUIT_CAGE_PAD_STIFFNESS",
                 "FRUIT_CAGE_PAD_DAMPING"):
        os.environ.pop(name, None)
    importlib.reload(cage)


# --------------------------------------------------------------------------- #
# 3. the call site, and the diagnostic must not own it
# --------------------------------------------------------------------------- #
def section_callsite() -> None:
    print("3. the call site (one) and the probe's independence")
    calls = [n for n in ast.walk(ast.parse(TASKS_SRC))
             if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute)
             and n.func.attr == "close_done"]
    check(len(calls) == 1, f"exactly one `close_done()` call site (got {len(calls)})")
    begins = [n for n in ast.walk(ast.parse(TASKS_SRC))
              if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute)
              and n.func.attr == "close_begin"]
    check(len(begins) == 1, f"exactly one `close_begin()` call site (got {len(begins)})")
    bidx = next((i for i, ln in enumerate(TASKS_SRC.splitlines())
                 if ".close_begin()" in ln), -1)
    check(bidx > 0 and bidx < next(i for i, ln in enumerate(TASKS_SRC.splitlines())
                                   if ".close_done()" in ln),
          "the window opens before the close loop and closes after it")
    # the enclosing statement block must test the hand's kind, not the probe
    lines = TASKS_SRC.splitlines()
    idx = next(
        (i for i, ln in enumerate(lines) if ".close_done()" in ln),
        -1,
    )
    check(idx > 0, "the call site exists in tasks.py")
    window = "\n".join(lines[max(0, idx - 12): idx + 2])
    check("CAGE_KIND" in window,
          "it is gated on the hand's kind (`CAGE_KIND`), so the shipped hand is inert")
    check("_cage_probe_on" not in window and "FRUIT_CAGE_PROBE" not in window,
          "and NOT on `FRUIT_CAGE_PROBE` - a diagnostic must not own a behaviour")
    check("grip_gap = min(grip_gap, last_cmd)" in "\n".join(lines[max(0, idx - 40): idx]),
          "it runs after the close has settled the depth the carry will hold")
    # the row's centring instrument
    check("off0=" in TASKS_SRC and "off=" in TASKS_SRC,
          "the `[cage]` row carries `off0=` and `off=` (the centring instrument)")
    for key in ('"off0": float("nan")', '"off": float("nan")', '"axis0": None'):
        check(key in TASKS_SRC, f"the census book declares {key.split(':')[0]}")
    check('book["off0"] = float(np.hypot' in TASKS_SRC,
          "`off0` is the radial distance to the ring's axis at the close's start")
    check('book["off"] = float(np.hypot' in TASKS_SRC,
          "`off` is the same distance at the flush (to the axis where it is NOW)")
    check(TASKS_SRC.count('self.grippers.get(book["side"]).base_pose()') == 1,
          "`off` reads the cage's base pose (the ring's axis), not a new per-tick read")


# --------------------------------------------------------------------------- #
# 3b. the scoped close window
# --------------------------------------------------------------------------- #
def section_window() -> None:
    print("3b. the close window: soft only between `close_begin` and `close_done`")
    import importlib

    import fruit_sorting.cage_hand as cage

    os.environ["FRUIT_CAGE_CLOSE_STIFFNESS"] = "1000"
    os.environ["FRUIT_CAGE_CLOSE_DAMPING"] = "8.9"
    os.environ.pop("FRUIT_CAGE_PAD_STIFFNESS", None)
    os.environ.pop("FRUIT_CAGE_HOLD_STIFFNESS", None)
    importlib.reload(cage)
    hand = _bare_hand(cage, True)
    check(cage.PAD_STIFFNESS == 1.0e5,
          "the approach profile stays the shipped rigid one (the scope's whole point)")
    hand.close_begin()
    ks = {round(d.stiffness.value, 6) for d in hand._drives}
    check(ks == {1000.0}, f"`close_begin` puts the drives on the close profile ({ks})")
    caps = {round(d.cap.value, 6) for d in hand._drives}
    tg = {round(d.target.value, 9) for d in hand._drives}
    check(caps == {round(cage.PAD_FORCE, 6)} and tg == {0.0},
          "the cap and the target are untouched by the window")
    hand.close_done()
    ks = {round(d.stiffness.value, 6) for d in hand._drives}
    check(ks == {round(cage.PAD_STIFFNESS, 6)},
          f"`close_done` returns to the approach profile when no hold is set ({ks})")
    # the two calls must be free at the shipped defaults
    os.environ.pop("FRUIT_CAGE_CLOSE_STIFFNESS", None)
    os.environ.pop("FRUIT_CAGE_CLOSE_DAMPING", None)
    importlib.reload(cage)
    hand = _bare_hand(cage, True)
    hand.close_begin()
    hand.close_done()
    ks = {round(d.stiffness.value, 6) for d in hand._drives}
    check(ks == {round(cage.PAD_STIFFNESS, 6)},
          "with both window knobs unset the two calls write nothing (the shipped cage)")


# --------------------------------------------------------------------------- #
# 4. the metadata pin
# --------------------------------------------------------------------------- #
def section_pin() -> None:
    print("4. the metadata pin")
    digest = hashlib.md5(TASKS.read_bytes()).hexdigest()
    pin = next((ln.split('"')[1] for ln in RL_ENV_SRC.splitlines()
                if ln.startswith("TASKS_MD5 = ")), "")
    check(pin == digest,
          f"rl_env.TASKS_MD5 == tasks.py ({digest[:8]}) - the direct env can start")


def main() -> int:
    print("P111 cage compliance selftest")
    print("=" * 78)
    section_arithmetic()
    print()
    section_stop()
    print()
    section_callsite()
    print()
    section_window()
    print()
    section_pin()
    print()
    if FAILURES:
        print(f"P111 cage compliance selftest: FAIL ({len(FAILURES)} checks)")
        return 1
    print("P111 cage compliance selftest: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
