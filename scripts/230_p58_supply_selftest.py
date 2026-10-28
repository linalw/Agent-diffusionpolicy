#!/usr/bin/env python3
"""P58 supply-profile selftest (offline; a `scripts/selfcheck.sh` leg).

Pins the **direct presentation's supply profile** resolution and the
caller-owned kwargs it is passed through, without a simulator:

1. `SortingRLEnv._resolve_supply_profile(True)` with a clean environment reads
   every member **on**, `band_max = 4` and every `defaulted` flag `True`.
2. An explicit environment value wins (`FRUIT_FEED_CADENCE=0` etc.) and clears
   the matching `defaulted` flag - that is the documented re-baseline recipe
   (`FRUIT_FEED_CADENCE=0 FRUIT_SUPPLY_BAND_INTERLOCK=0 FRUIT_DIRECT_FEED=0`).
3. `_resolve_supply_profile(False)` is **inert**: every member off / `None`, so
   the scripted line, the handoff presentation and the two-line scheduler are
   byte-unchanged (they do not even reach the new kwargs).
4. The two constructors accept the kwargs (`FruitSpawner(band_interlock=,
   band_max=)`; `PickAndPlaceTask(feed_cadence=)`) - the plumbing the flip uses.
5. The shipped env-var default for `FRUIT_FEED_CADENCE` stays **0** as a *read*,
   so `scripts/213_prepared_next_selftest.py`'s pin keeps its meaning: the flip
   lives in the direct profile, not in the task's default.

Exit 0 on pass, 1 on the first failure. No simulator, no file writes.
"""
from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

MEMBERS = ("cadence", "band_interlock", "feed")

VARS = (
    "FRUIT_FEED_CADENCE",
    "FRUIT_SUPPLY_BAND_INTERLOCK",
    "FRUIT_SUPPLY_BAND_MAX",
    "FRUIT_DIRECT_FEED",
)


def clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in VARS}


def check(cond: bool, what: str) -> None:
    if not cond:
        print(f"FAIL: {what}")
        raise SystemExit(1)
    print(f"ok: {what}")


def main() -> int:
    from fruit_sorting.rl_env import SortingRLEnv

    saved = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(clean_env())

        prof = SortingRLEnv._resolve_supply_profile(True)
        check(prof["cadence"] is True, "direct: cadence on by default")
        check(prof["band_interlock"] is True, "direct: band interlock on by default")
        check(prof["band_max"] == 4, "direct: band_max is 4 (cap 3 is a regression)")
        check(prof["feed"] is True, "direct: live feeder on by default")
        check(all(prof["defaulted"][k] for k in MEMBERS),
              "direct: every member reports defaulted=True")

        os.environ["FRUIT_FEED_CADENCE"] = "0"
        os.environ["FRUIT_SUPPLY_BAND_INTERLOCK"] = "0"
        os.environ["FRUIT_DIRECT_FEED"] = "0"
        os.environ["FRUIT_SUPPLY_BAND_MAX"] = "3"
        off = SortingRLEnv._resolve_supply_profile(True)
        check(off["cadence"] is False and off["band_interlock"] is False
              and off["feed"] is False and off["band_max"] == 3,
              "explicit values win (the pre-P58 re-baseline recipe)")
        check(not any(off["defaulted"][k] for k in MEMBERS)
              and off["defaulted"]["band_max"] is False,
              "explicit values clear every defaulted flag")

        os.environ.clear()
        os.environ.update(clean_env())
        handoff = SortingRLEnv._resolve_supply_profile(False)
        check(handoff["cadence"] is False and handoff["band_interlock"] is False
              and handoff["feed"] is False and handoff["band_max"] is None,
              "non-direct: the resolver is inert (shipped kwargs, None)")

        # 3b: the row's three provenance cases (P59 gate 1's defect).
        shipped = SortingRLEnv._supply_profile_row(prof, prof["feed"])
        check("band=on(4)(default)" in shipped,
              "shipped row prints band=on(4)(default)")
        pre = SortingRLEnv._resolve_supply_profile(True) if False else None
        os.environ.clear(); os.environ.update(clean_env())
        os.environ.update({"FRUIT_FEED_CADENCE": "0",
                           "FRUIT_SUPPLY_BAND_INTERLOCK": "0",
                           "FRUIT_DIRECT_FEED": "0"})
        pre_prof = SortingRLEnv._resolve_supply_profile(True)
        pre_row = SortingRLEnv._supply_profile_row(pre_prof, pre_prof["feed"])
        check("band=off(explicit)" in pre_row and "(4)" not in pre_row,
              "pre-P58 row drops the cap (no misleading (4))")
        os.environ.clear(); os.environ.update(clean_env())
        os.environ["FRUIT_SUPPLY_BAND_MAX"] = "5"
        cap5 = SortingRLEnv._resolve_supply_profile(True)
        cap5_row = SortingRLEnv._supply_profile_row(cap5, cap5["feed"])
        check("band=on(5(explicit))(default)" in cap5_row,
              "a cap override names itself (on(5(explicit))(default))")
        check("target_from=0.35(default)" in shipped
              and cap5["defaulted"]["target_from"] is True,
              "the row and manifest carry target_from provenance")

        # 4-5: static pins (fruits.py/tasks.py import pxr, so no offline import).
        fruits_src = (ROOT / "src/fruit_sorting/fruits.py").read_text(encoding="utf-8")
        tasks_src = (ROOT / "src/fruit_sorting/tasks.py").read_text(encoding="utf-8")
        env_src = (ROOT / "src/fruit_sorting/rl_env.py").read_text(encoding="utf-8")
        check("band_interlock: bool | None = None" in fruits_src
              and "band_max: int | None = None" in fruits_src,
              "FruitSpawner accepts band_interlock / band_max (None = env read)")
        check("feed_cadence: bool | None = None" in tasks_src,
              "PickAndPlaceTask accepts feed_cadence (None = env read)")
        check('os.environ.get("FRUIT_FEED_CADENCE", "0")' in tasks_src,
              'the task keeps the shipped FRUIT_FEED_CADENCE="0" env read')
        check('self._feed_on = bool(self._feed_cadence and self._feed_scope())' in tasks_src,
              "the feed gate is the cadence x scope pair, not the episode knob")
        check("band_interlock=(" in env_src and "feed_cadence=(" in env_src,
              "rl_env passes both kwargs at the construction sites")
        check('"supply": {' in env_src,
              "the manifest carries the supply block")
    finally:
        os.environ.clear()
        os.environ.update(saved)

    print("PASS: P58 supply profile")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
