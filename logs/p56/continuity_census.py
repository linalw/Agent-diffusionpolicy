#!/usr/bin/env python3
"""P56 phase 1: the continuity census (offline; two measured runs, no simulator).

Reads the two 12-episode direct-interface recordings
  `logs/p54/video_fed/video.json`         (FRUIT_DIRECT_FEED=1, the live feeder)
  `logs/p54/video_continuous/video.json`  (shipped: no feeder)
and reports the quantities P56's design has to move:

  * the **inter-attempt gap** in *sim* ticks: `start_tick[k+1] - (start_tick[k] +
    ticks[k])`, i.e. everything the reset spends between one episode's last
    policy tick and the next episode's first one. The driver writes
    `start_tick` immediately before `env.reset()` (`scripts/121_policy_video.py`),
    so this is the reset's own sim span.
  * the **starvation** read: the reset's target-selection loop runs in
    `for _ in range(30)` rounds and breaks at round 0 whenever a candidate
    exists (`rl_env.reset`), so `rounds > 0` shows up as a gap > 140 ticks.
  * the **belt stock at selection**: the direct selector is the shipped
    farthest-upstream rule (`select_target(..., direct=True)` ->
    `_balance_arm(usable)`), so the episode line's `y=` *is* the along-position of
    the most-upstream live fruit at/above the catch floor, i.e. the stocked depth
    from the station. `spawn_y = 0.68` (`assets.py`) is the release point, so
    depth/spawn_y is the fraction of the release band that is stocked.
  * the **arrival wait**: `t_arrive` from the trigger note (the belt travel the
    pick still has to pay after selection).
  * the wall: the kit's own `[<s>]` clock at shutdown minus the identical
    startup, so `sim/wall` is comparable across the two runs.

Usage: python3 logs/p56/continuity_census.py [--json]
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = {
    "fed": ROOT / "logs/p54/video_fed",
    "unfed": ROOT / "logs/p54/video_continuous",
}
DT = 120.0          # control ticks per simulated second
SPAWN_Y = 0.68      # `assets.py: spawn_y` - the release point on the main belt
PICK_Y = 0.0        # `assets.py: pick_y` - the station
# `rl_env.reset`'s own accounting, all three matched to the measured gap below:
FEED_ROUND_TICKS = 30     # `for _ in range(30): self.advance(1)` per selection round
TELEPORT_SETTLE = 30      # `Arm.teleport_joints(..., settle=30)` (`control.py:552`)
N_TELEPORTS = 3           # both arms parked + the active arm to `grasp`
RESET_SETTLE = 20         # `FRUIT_RESET_SETTLE` default (`rl_env.py:1247`)
RESET_TICKS = (
    FEED_ROUND_TICKS + N_TELEPORTS * TELEPORT_SETTLE + RESET_SETTLE
)
#: Ticks a *continued* pick cannot avoid: the new pick's arm must still be
#: teleported to `grasp` (the training distribution's frame 0) and settled.
CONTINUE_TICKS_SAME_ARM = TELEPORT_SETTLE + RESET_SETTLE          # 50
CONTINUE_TICKS_SWITCH = 2 * TELEPORT_SETTLE + RESET_SETTLE        # 80


def _kit_seconds(log: Path, needle: str) -> float | None:
    """The kit's own `[<s>]` clock at the line containing `needle`."""
    if not log.exists():
        return None
    pat = re.compile(r"^\[([0-9.]+)s\]")
    for line in log.read_text(errors="replace").splitlines():
        if needle in line:
            m = pat.match(line)
            if m:
                return float(m.group(1))
    return None


def _startup_seconds(log: Path) -> float | None:
    """`Simulation App Startup Complete` - the identical pre-run offset."""
    return _kit_seconds(log, "Simulation App Startup Complete")


def _notes_to_fields(notes: list[str]) -> dict:
    out = {"t_arrive": None, "dx": None, "dy": None, "trigger": ""}
    for note in notes:
        if note.startswith("intercept trigger"):
            m = re.search(r"t_arrive=([0-9.]+)s", note)
            if m:
                out["t_arrive"] = float(m.group(1))
            m = re.search(r"dx=(-?[0-9.]+)cm", note)
            if m:
                out["dx"] = float(m.group(1)) / 100.0
            m = re.search(r"dy=(-?[0-9.]+)cm", note)
            if m:
                out["dy"] = float(m.group(1)) / 100.0
            out["trigger"] = "intercept"
        elif note.startswith("learned close"):
            out["trigger"] = out["trigger"] or "policy_close"
    return out


def census(name: str) -> dict:
    run = RUNS[name]
    data = json.loads((run / "video.json").read_text())
    eps = data["episodes"]
    log = run.with_suffix(".log")

    gaps, depth, wait, ticks = [], [], [], []
    for i, ep in enumerate(eps):
        ticks.append(int(ep["ticks"]))
        if i + 1 < len(eps):
            nxt = eps[i + 1]
            gaps.append(int(nxt["start_tick"]) - (int(ep["start_tick"]) + int(ep["ticks"])))
        fields = _notes_to_fields(list(ep.get("notes") or []))
        if fields["t_arrive"] is not None:
            wait.append(fields["t_arrive"])
    # `y=` (the selected fruit's along at selection) is the stocked depth.
    for line in log.read_text(errors="replace").splitlines():
        m = re.search(r"\[rl\] episode \d+: \w+ grade=\w d=[0-9.]+cm bin=\d arm=\w+ y=([+-][0-9.]+)", line)
        if m:
            depth.append(float(m.group(1)))

    total_span = sum(ticks) + sum(gaps)
    sim_s = total_span / DT
    arms = [str(ep.get("arm", "")) for ep in eps]
    switches = sum(1 for i in range(len(arms) - 1) if arms[i] != arms[i + 1])
    #: The unfed line calls `spawner.update` only in the reset's feed rounds
    #: (`rl_env.reset`'s `for _ in range(30)`), so its release schedule runs on
    #: 30 ticks per episode out of the whole span. The fed line runs it from
    #: `advance` (`rl_env.advance`'s `FRUIT_DIRECT_FEED` block), i.e. every tick.
    unfed = name == "unfed"
    update_ticks = FEED_ROUND_TICKS * len(eps) if unfed else total_span
    placed = sum(1 for ep in eps if ep.get("placed"))
    success = sum(1 for ep in eps if ep.get("success"))
    end = _kit_seconds(log, "Simulation App Shutting Down")
    start = _startup_seconds(log)
    wall = (end - start) if (end is not None and start is not None) else None

    def stats(values):
        if not values:
            return None
        return {
            "n": len(values),
            "min": min(values),
            "median": statistics.median(values),
            "mean": statistics.fmean(values),
            "max": max(values),
        }

    return {
        "run": name,
        "episodes": len(eps),
        "ticks": stats(ticks),
        "gap_ticks": stats(gaps),
        "gap_unique": sorted(set(gaps)),
        "feed_rounds": [max(0, (g - RESET_TICKS) // FEED_ROUND_TICKS) for g in gaps],
        "span_ticks": total_span,
        "span_sim_s": sim_s,
        "gap_share": sum(gaps) / total_span if total_span else None,
        "depth_m": stats(depth),
        "depth_frac_of_spawn": stats([d / SPAWN_Y for d in depth]),
        "arrival_wait_s": stats(wait),
        "arrival_share": (statistics.fmean(wait) * DT / statistics.fmean(ticks)) if wait and ticks else None,
        "placed": placed,
        "success": success,
        "placed_per_sim_min": placed / (sim_s / 60.0) if sim_s else None,
        "arms": arms,
        "arm_switches": switches,
        "arm_switch_share": switches / max(1, len(arms) - 1),
        "feeder_update_ticks": update_ticks,
        "feeder_update_share": update_ticks / total_span if total_span else None,
        "wall_s": wall,
        "wall_per_pick_s": (wall / len(eps)) if wall else None,
        "sim_per_wall": (sim_s / wall) if wall else None,
        "reset_ticks_code": RESET_TICKS,
        "continue_ticks_same_arm": CONTINUE_TICKS_SAME_ARM,
        "continue_ticks_switch": CONTINUE_TICKS_SWITCH,
    }


def main() -> int:
    out = {name: census(name) for name in RUNS}
    if "--json" in sys.argv:
        print(json.dumps(out, indent=2))
        return 0
    for name, c in out.items():
        print(f"== {c['run']}  ({c['episodes']} episodes)")
        print(f"   per-episode ticks   {c['ticks']}")
        print(f"   inter-attempt gap   {c['gap_ticks']}  unique={c['gap_unique']} "
              f"extra feed rounds={c['feed_rounds']}")
        print(f"   sim span            {c['span_ticks']} ticks = {c['span_sim_s']:.1f} s; "
              f"gap share {c['gap_share']:.3%}")
        print(f"   stocked depth (y)   {c['depth_m']}")
        print(f"     as a fraction of spawn_y=0.68: {c['depth_frac_of_spawn']}")
        print(f"   arrival wait        {c['arrival_wait_s']} s  "
              f"(mean share of the cycle {c['arrival_share']:.1%})")
        print(f"   placed {c['placed']}/{c['episodes']}  success {c['success']}/{c['episodes']}  "
              f"placed/min (sim) {c['placed_per_sim_min']:.2f}")
        print(f"   arm switches        {c['arm_switches']}/{len(c['arms']) - 1} "
              f"({c['arm_switch_share']:.0%})  arms={c['arms']}")
        print(f"   spawner.update on   {c['feeder_update_ticks']} of {c['span_ticks']} ticks "
              f"= {c['feeder_update_share']:.2%} of the span")
        if c["wall_s"]:
            print(f"   wall {c['wall_s']:.1f} s  = {c['wall_per_pick_s']:.1f} s/pick  "
                  f"sim/wall {c['sim_per_wall']:.3f}")
        print(f"   code arithmetic     reset={c['reset_ticks_code']} ticks "
              f"(30 feed + 3x30 teleport + 20 settle)")
        print()
    a, b = out["fed"], out["unfed"]
    print("== the two runs side by side")
    print(f"   gap              {a['gap_ticks']['mean']:.0f} vs {b['gap_ticks']['mean']:.0f} ticks")
    print(f"   stocked depth    {a['depth_m']['median']:.3f} vs {b['depth_m']['median']:.3f} m "
          f"(median), min {a['depth_m']['min']:.3f} vs {b['depth_m']['min']:.3f}")
    print(f"   arrival wait     {a['arrival_wait_s']['median']:.2f} vs {b['arrival_wait_s']['median']:.2f} s (median)")
    if a["wall_s"] and b["wall_s"]:
        print(f"   wall             {a['wall_s']:.1f} vs {b['wall_s']:.1f} s  "
              f"({(a['wall_s'] / b['wall_s'] - 1) * 100:+.1f} %)  "
              f"per sim-s {a['sim_per_wall'] and (a['wall_s'] / a['span_sim_s']):.2f} vs "
              f"{(b['wall_s'] / b['span_sim_s']):.2f}")
    # What a continued pick can save: the reset minus the re-pose it cannot skip.
    print()
    print("== the reset's 140 ticks, and what continuity can remove")
    print(f"   feed round (30)          removable: selection reads the live belt")
    print(f"   inactive-arm park (30)   removable only when the arm does not switch")
    print(f"   active-arm teleport (30) NOT removable: the pick starts at `grasp`")
    print(f"   reset settle (20)        NOT removable: the teleport must settle")
    for label, t in (("same-arm continue", CONTINUE_TICKS_SAME_ARM),
                     ("arm-switch continue", CONTINUE_TICKS_SWITCH)):
        saved = RESET_TICKS - t
        print(f"   {label:22s} {t:3d} ticks -> saves {saved:3d} ticks = "
              f"{saved / DT:.2f} s = {saved / (a['ticks']['mean'] + RESET_TICKS):.2%} of a pick")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
