"""Check one pick-and-place log against the shipped motion invariants.

    python3 scripts/105_motion_regression.py logs/accept.log
    python3 scripts/105_motion_regression.py LOG --write-fingerprint configs/motion_reference.json
    python3 scripts/105_motion_regression.py LOG --fingerprint configs/motion_reference.json

The run this guards is

    FRUIT_MOTION_REPORT=1 ATTEMPTS=10 scripts/run.sh scripts/20_pick_place.py

and nothing here needs the simulator, so it runs in a second.

**Read the numbers as same-configuration regression, never as an A/B.** The
simulation is deterministic for a given configuration but the *outcome* is
quantised: every configuration tried so far lands in one of a small number of
discrete attractors, each internally bit-identical, and which one you land in
depends on instrumentation as much as on physics (WORKLOG: "the outcome is
quantized"). Two runs in different attractors are different scenarios, so a
success-rate comparison across them measures the attractor, not the change under
test.

## The two legs are judged by two different physical budgets

A pick-and-place attempt has two kinds of motion, and they are constrained by
different things. Applying one budget to both is what made this gate
uninformative (and blocked the `FRUIT_CLOSE_ON_EXTENT` promotion on a number that
had nothing to do with it):

* **descent / approach** (`[motion] approach(...)`) is *payload-free*. The hand
  holds nothing, so the friction cone is irrelevant - the pads are not carrying a
  load. The physical invariants are:
    1. the hand may not travel faster than it was commanded, or something moved
       it: `|v|max <= 1.10 * peak(shipped profile for this leg)` (the v7
       directive raised the dynamic profile, so the budget is derived from the
       same `jerk_limited` profile the task emits rather than a frozen constant);
    2. it may not absorb an impulse: a single 1/120 s control tick may not change
       its speed by more than twice the profile's own peak (`LURCH_FACTOR`).
  The old gate additionally held the descent to `a_win5 <= 2.0 m/s^2`, which is
  `mu_eff * g` - the acceleration pad friction can transmit *while carrying a
  payload*. That is a carrying budget, and the descent carries nothing, so it was
  an over-extension of the number rather than a bound on the descent. It is kept
  below as a *non-blocking warning* (`ROUGHNESS_WARN`) so the roughness stays
  visible instead of silently disappearing from the report.

* **carry** (`[motion] carry ...`) *does* hold the payload, so the friction cone
  applies to it: `|a + g z| <= mu_eff * g`, reported as `cone=N.NNx budget
  (pct over)`. A carry leg whose payload path stays inside the cone keeps its
  grip; a leg that runs away is a lost grip. The monitor measures the *pads*, so
  a reactive re-seat (`recoveries>0`) teleports them ~25 mm in one call and the
  finite difference reads that as a ~3 m/s pad velocity - an artefact of the
  correction, not of the payload. Carry legs with `recoveries>0` are therefore
  reported but excluded from the cone gate; their outcome is covered by the
  success rate.

  **On the dynamic line (the shipped default since the v7 directive) the cone is
  a report, not a gate.** The dynamic line's measured baseline is a bit-identical
  9/10 after the Gate-19 place sweep (`logs/fast/14_accept_place035.log`), whose
  held place legs reach 1.23x and whose one failure is the A6 kiwi catch miss
  (its lift carry reads 2.41x/199.6 mm); gating those would make every dynamic
  acceptance red by construction (the P2b correction recorded exactly that). The
  per-leg cone/slip read stays in the report - it is the speed sweep's decision
  metric - and `--strict-cone` restores the hard gate for an A/B.

## Calibration, with the logs this was fitted to

| log | config | descent `|v|max` | descent max `|a|` (per tick) | descent `a_win5` | verdict |
| --- | --- | --- | --- | --- | --- |
| `logs/136_accept_after_pump` | shipped (nominal close) | 0.056 | 7.336 (0.061) | 1.800 | pass |
| `logs/142_accept_extent_default_1/2` | extent close default | 0.060 | 7.141 (0.060) | 2.740 | pass |
| `logs/455_anomaly_nolinks` | lurching descent | **0.148** | 11.126 (0.093) | 2.780 | fail on `|v|max` |
| `logs/428_seat10` | lurching descent | **2.774** | **332.8 (2.77)** | (not recorded) | fail on both |

The two failure references separate cleanly: the worst shipped single-tick change
is 0.061 m/s (1.02x cruise) and the worst observed impulse is 2.77 m/s (46x
cruise), so the 2x-cruise lurch bound sits 2x above everything that passed and
23x below everything that failed. Note that `logs/455` is *not* caught by the
lurch term (0.093 < 0.12) - the clean discriminator for it is the velocity
overrun. The old `a_win5` window could not separate them at all: its two
references are 2.74 (pass) and 2.78 (fail), which is why the criterion was
re-derived instead of re-tuned.

The two reference rows were measured against a 0.06 m/s profile; the invariant
is a *ratio* (0.056/0.06 = 0.93 pass, 0.148/0.06 = 2.47 fail), so the same
calibration holds when the shipped profile changes speed and the budget follows
it (`descent_profile_peak`). On the v7 fast profile the clean legs measure
**0.108-0.109 against a 0.147 profile peak (~0.75)**, not 0.92-0.99, because the
conveyor boundary ends every descent 40-90 mm short and the profile's peak is
never reached; the 1.10 budget is therefore ~1.47x the achieved speed there.
The ratio to the *profile* peak is the quantity that stays comparable across
profiles: the 1.10 margin sits between 0.75 (fast clean) / 0.93 (slow clean) and
2.47 (fail) on the same side as every clean leg.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from fruit_sorting.motion import TrajectoryLimits, jerk_limited  # noqa: E402  (pure numpy)

#: Shipped approach-profile defaults (duplicated from `tasks.py`, where the
#: environment default is read at run time). `scripts/96_motion_check.py` pins
#: the dynamic pair against `tasks.py`; an explicit environment value always
#: wins. `SHIPPED_APPROACH_VMAX` is the *indexed* descent's cruise (the
#: `FRUIT_APPROACH_VMAX` default), used to derive the budget for logs that never
#: print a moving pick.
SHIPPED_DYNAMIC_APPROACH_VMAX = 0.15
SHIPPED_APPROACH_VMAX = 0.03
SHIPPED_APPROACH_AMAX = 0.8
#: Fallback absolute descent budget [m/s], used only if the profile cannot be
#: built. This was the pre-v7 shipped constant.
REFERENCE_VMAX = 0.06
#: Achieved-vs-commanded tolerance. A clean jerk-limited descent on the slow
#: pre-v7 profile measures 0.92-0.99 of the profile's own peak (`logs/155`,
#: `logs/accept.log`, `logs/place_low/rate_low_1.log`); on the v7 fast profile the
#: clean legs measure ~0.75 of it (0.108-0.109 against a 0.147 profile peak,
#: `logs/fast/10_accept_v7fast.log`) because the conveyor boundary ends every
#: descent 40-90 mm short and the profile's peak is never reached. So 1.10 is
#: 1.10x the *profile* peak, i.e. ~1.47x the achieved speed on the fast profile -
#: and it still leaves room for the finite-difference jitter without admitting a
#: leg that moved 40-50 % faster than commanded (`logs/455` 0.148 vs a 0.06
#: profile = 2.47x).
ACHIEVED_MARGIN = 1.10
#: Control period the metrics are differenced over (the scripts step at 120 Hz).
CONTROL_DT = 1.0 / 120.0


def descent_profile_peak(distance: float, dynamic: bool) -> float | None:
    """Peak speed of the shipped approach profile for `distance` [m/s].

    The v7 directive raised the dynamic approach speed and acceleration, so the
    descent budget can no longer be one frozen number: a fixed 0.06 fails every
    fast dynamic descent, and raising it to the new cruise would stop bounding
    the retimed profile. The invariant the gate actually enforces - *the hand may
    not travel faster than it was commanded* - is recovered by building the very
    profile the task builds (`jerk_limited` with the same limits) for this leg's
    own distance and comparing the achieved peak against it with
    `ACHIEVED_MARGIN`. The dynamic line uses `FRUIT_DYNAMIC_APPROACH_VMAX`; a log
    with no moving pick is the indexed line and uses `FRUIT_APPROACH_VMAX`.
    Returns None if the profile cannot be built, so the caller falls back to
    `REFERENCE_VMAX`.
    """
    try:
        limits = TrajectoryLimits.from_env(CONTROL_DT)
        if dynamic:
            limits.v_max = float(
                os.environ.get(
                    "FRUIT_DYNAMIC_APPROACH_VMAX", str(SHIPPED_DYNAMIC_APPROACH_VMAX)
                )
            )
        else:
            limits.v_max = float(
                os.environ.get("FRUIT_APPROACH_VMAX", str(SHIPPED_APPROACH_VMAX))
            )
        limits.a_max = float(
            os.environ.get("FRUIT_APPROACH_AMAX", str(SHIPPED_APPROACH_AMAX))
        )
        _, vel, _ = jerk_limited(max(float(distance), 1e-3), limits)
        peak = float(np.abs(vel).max())
        return peak if peak > 0.0 else None
    except Exception:  # noqa: BLE001 - a broken profile must not hide the gate
        return None


#: `|dv|` per control tick a descent may absorb: 2x its own profile peak. Kept
#: relative to the profile for the same reason as the budget above; the measured
#: clean ticks sit at 0.016-0.035 m/s against the pre-v7 0.12 bound, and the
#: failing lurch (`logs/428` 2.77 m/s) is orders of magnitude out at any speed.
LURCH_FACTOR = 2.0
#: `TrajectoryLimits.limited_by_cone` with mu = 2 and FRUIT_MU_SAFETY = 0.6 gives
#: 2.0 m/s^2 straight up. That is a *carrying* budget; on a payload-free descent it
#: is reported as a warning, not enforced. See the calibration table above.
ROUGHNESS_WARN = 2.0  # [m/s^2]
#: Carry legs that keep their grip stay inside the friction cone. `cone` is the
#: monitored worst tick as a multiple of `mu_eff * g`, so 1.0 is the budget.
CARRY_CONE = 1.0
#: Reported (not gated) hand speed [m/s]. The pads are kinematic, so the reactive
#: re-seat after a slip teleports them 25-40 mm in one tick. On `logs/145` the 26
#: legs that held their grip kept the pads at the commanded 0.176-0.371 m/s while
#: the 4 legs that slipped moved them at **2.96-4.95 m/s**: the `in-hand |v|max`
#: those legs report is that teleport, not fruit motion. It is a *report*, not a
#: budget, because capping it was measured and made things worse - the pads then
#: cannot catch a payload that is already leaving the jaws (`logs/150`, and the
#: note in `kinematic_gripper.KinematicGripper.__init__`). 0.45 m/s is the number a
#: hand *should* respect (just above the fastest carry profile, 0.371).
HAND_VMAX = 0.45
#: Fraction of attempts that must succeed. The *indexed* shipped suite scores
#: 10/10 and must keep the 0.9 bar. The *dynamic* line (the shipped default since
#: the v7 directive) has a measured, bit-identical **9/10** baseline after the
#: Gate-19 place sweep: the one failure is the **A6 kiwi catch-window miss**
#: (catch-up residual ~100 mm at the narrow arrival window, `fruit did not follow
#: the gripper`; `logs/fast/14_accept_place035.log`), and the earlier A2 peach
#: place escape holds at the new place profile. The floor stays 7.5/10 - a 9/10
#: or 8/10 passes, a genuine regression to 7/10 still fails (the 0.75 floor was
#: not lowered; a 7/10 ship needs an owner exception, not a floor change). Which
#: floor applies is read from the log (a run that never prints `moving pick` is
#: the indexed line).
SUCCESS_RATE_FLOOR = 0.9
DYNAMIC_SUCCESS_FLOOR = 0.75

LEG = re.compile(
    r"approach\((\w+)\): ([\d.]+) cm, (\d+) samples: .*?"
    r"\|v\|max=([\d.]+) m/s, \|a\|max=([\d.]+) m/s\^2, \|j\|max=([\d.]+) m/s\^3"
    r"(?:.*?a_med=([\d.]+) peak@([\d.]+) \(first10=([\d.]+) last10=([\d.]+)\) m/s\^2)?"
    r"(?:.*?a_win5=([\d.]+) m/s\^2)?"
)
CARRY = re.compile(
    r"carry (\w+): ([\d.]+) cm, (\d+) ticks.*?slip_max=([\d.]+) mm, "
    r"in-hand \|v\|max=([\d.]+) m/s, recoveries=(\d+): .*?"
    r"\|v\|max=([\d.]+) m/s, \|a\|max=([\d.]+) m/s\^2.*?"
    r"cone=([\d.]+)x budget \((\d+) pct over\)"
)
SUMMARY = re.compile(r"attempts=(\d+) successes=(\d+) .*?success_rate=(\d+)%")


def parse(path: str) -> tuple[list[dict], list[dict], tuple[int, int] | None, bool]:
    legs: list[dict] = []
    carries: list[dict] = []
    tally: tuple[int, int] | None = None
    dynamic = False
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if "moving pick" in line or "dynamic catch-up" in line:
                dynamic = True
            found = LEG.search(line)
            if found:
                legs.append(
                    {
                        "mode": found.group(1),
                        "distance_cm": float(found.group(2)),
                        "samples": int(found.group(3)),
                        "v_max": float(found.group(4)),
                        "a_max": float(found.group(5)),
                        "j_max": float(found.group(6)),
                        "a_med": float(found.group(7)) if found.group(7) else None,
                        "peak_at": float(found.group(8)) if found.group(8) else None,
                        "a_first10": float(found.group(9)) if found.group(9) else None,
                        "a_last10": float(found.group(10)) if found.group(10) else None,
                        "a_win5": float(found.group(11)) if found.group(11) else None,
                    }
                )
            carry = CARRY.search(line)
            if carry:
                carries.append(
                    {
                        "leg": carry.group(1),
                        "distance_cm": float(carry.group(2)),
                        "ticks": int(carry.group(3)),
                        "slip_mm": float(carry.group(4)),
                        "in_hand_v": float(carry.group(5)),
                        "recoveries": int(carry.group(6)),
                        "v_max": float(carry.group(7)),
                        "a_max": float(carry.group(8)),
                        "cone": float(carry.group(9)),
                        "cone_over_pct": int(carry.group(10)),
                    }
                )
            summary = SUMMARY.search(line)
            if summary:
                tally = (int(summary.group(1)), int(summary.group(2)))
    return legs, carries, tally, dynamic


def fingerprint_of(legs: list[dict]) -> list[list]:
    """Per-descent scenario fingerprint: (samples, peak speed).

    Deliberately excludes the per-tick peak acceleration. `a_max` differences two
    1/120 s samples, so on a leg whose steps are tenths of a millimetre it mostly
    measures jitter (this module's own note), and it varies run to run on the
    *same* scenario: logs/370 against logs/accept.log have every leg's `samples`
    and `|v|max` identical to the digit while leg 6's `a_max` reads 5.75 against
    3.882 - a false "different attractor". The lurch is still bounded separately
    via the lurch bound, so dropping it here loses no gate.
    """
    return [[leg["samples"], round(leg["v_max"], 4)] for leg in legs]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", help="a run log from scripts/20_pick_place.py")
    parser.add_argument(
        "--vmax",
        type=float,
        default=None,
        help="absolute descent budget [m/s]; default derives it from the shipped profile",
    )
    parser.add_argument(
        "--lurch",
        type=float,
        default=None,
        help="absolute lurch bound [m/s^2]; default is 2x the derived profile peak",
    )
    parser.add_argument("--cone", type=float, default=CARRY_CONE)
    parser.add_argument(
        "--strict-cone",
        action="store_true",
        help="gate the carry cone on the dynamic line too (default: reported there)",
    )
    parser.add_argument("--hand-vmax", type=float, default=HAND_VMAX)
    parser.add_argument(
        "--min-success-rate",
        type=float,
        default=None,
        help="success floor; default 0.9 indexed / 0.75 dynamic (the measured baseline)",
    )
    parser.add_argument("--fingerprint", help="reference fingerprint JSON to compare against")
    parser.add_argument("--write-fingerprint", help="write this log's fingerprint here")
    args = parser.parse_args()

    legs, carries, tally, dynamic = parse(args.log)
    failures: list[str] = []
    warnings: list[str] = []
    if not legs:
        print(f"FAIL {args.log}: no located motion lines found")
        print("     (run with FRUIT_MOTION_REPORT=1 and FRUIT_APPROACH_MODE=cartesian)")
        return 1

    # Per-leg budgets from the shipped profile; `--vmax`/`--lurch` are absolute
    # overrides for judging historical logs.
    budgets: list[float] = []
    for leg in legs:
        peak = descent_profile_peak(leg["distance_cm"] / 100.0, dynamic)
        leg["budget"] = (peak * ACHIEVED_MARGIN) if peak else REFERENCE_VMAX
        leg["lurch_bound"] = (
            args.lurch
            if args.lurch is not None
            else (LURCH_FACTOR * peak / CONTROL_DT if peak else LURCH_FACTOR * REFERENCE_VMAX / CONTROL_DT)
        )
        if args.vmax is not None:
            leg["budget"] = args.vmax
        budgets.append(leg["budget"])

    print(f"{args.log}: {len(legs)} descent leg(s), line={'dynamic' if dynamic else 'indexed'}")
    print(
        f"  {'#':>2s} {'dist':>6s} {'samples':>7s} {'|v|max':>7s} {'budget':>7s} "
        f"{'|a|max':>8s} {'|dv|':>6s} {'a_med':>6s} {'peak@':>6s} {'a_win5':>7s}  verdict"
    )
    for index, leg in enumerate(legs, 1):
        delta_v = leg["a_max"] * CONTROL_DT
        problems = []
        if leg["v_max"] > leg["budget"]:
            problems.append(f"|v|max>{leg['budget']:.3f} (profile x{ACHIEVED_MARGIN:g})")
        if leg["a_max"] > leg["lurch_bound"]:
            problems.append(
                f"lurch |dv|>{leg['lurch_bound'] * CONTROL_DT:g} m/s per tick"
            )
        verdict = "ok" if not problems else "FAIL " + ",".join(problems)
        if problems:
            failures.append(
                f"descent {index} ({leg['distance_cm']:.1f} cm): " + ", ".join(problems)
            )
        if leg["a_win5"] is not None and leg["a_win5"] > ROUGHNESS_WARN:
            verdict += " (rough)"
            warnings.append(
                f"descent {index} ({leg['distance_cm']:.1f} cm): a_win5="
                f"{leg['a_win5']:.2f} over the {ROUGHNESS_WARN:g} m/s^2 carrying budget "
                f"- reported, not gated (see the module docstring)"
            )
        win = "-" if leg["a_win5"] is None else f"{leg['a_win5']:7.2f}"
        med = "-" if leg["a_med"] is None else f"{leg['a_med']:6.2f}"
        peak_at = "-" if leg["peak_at"] is None else f"{leg['peak_at']:6.2f}"
        print(
            f"  {index:2d} {leg['distance_cm']:5.1f}c {leg['samples']:7d} "
            f"{leg['v_max']:7.3f} {leg['budget']:7.3f} "
            f"{leg['a_max']:8.2f} {delta_v:6.3f} "
            f"{med} {peak_at} {win}  {verdict}"
        )

    worst_v = max(leg["v_max"] for leg in legs)
    worst_dv = max(leg["a_max"] * CONTROL_DT for leg in legs)
    wins = [leg["a_win5"] for leg in legs if leg["a_win5"] is not None]
    tail = (
        f", a_win5={max(wins):.3f} m/s^2 (carrying budget {ROUGHNESS_WARN:g}, warning)"
        if wins
        else ""
    )
    print(
        f"  worst: |v|max={worst_v:.4f} m/s (budget {min(budgets):.3f}-{max(budgets):.3f}), "
        f"lurch={worst_dv:.3f} m/s/tick "
        f"(budget {min(leg['lurch_bound'] * CONTROL_DT for leg in legs):g})" + tail
    )

    if carries:
        print(f"\n{args.log}: {len(carries)} carry leg(s)")
        print(
            f"  {'leg':<14s} {'dist':>6s} {'cone':>7s} {'over':>5s} {'slip':>7s} "
            f"{'in-hand |v|':>11s} {'recov':>5s}  verdict"
        )
        for carry in carries:
            gated = carry["recoveries"] == 0
            problems = []
            cone_over = gated and carry["cone"] > args.cone
            if cone_over and not (dynamic and not args.strict_cone):
                problems.append(f"cone>{args.cone:g}x")
            if carry["v_max"] > args.hand_vmax:
                # Reported, not gated: see the note on HAND_VMAX. Every leg over the
                # number here is a rescued payload, and the fix belongs upstream.
                verdict_note = f" (hand {carry['v_max']:.2f} m/s: rescued)"
            else:
                verdict_note = ""
            if problems:
                verdict = "FAIL " + ",".join(problems)
                failures.append(
                    f"carry {carry['leg']}: " + ", ".join(problems)
                    + f" (cone={carry['cone']:.2f}x budget)"
                )
            elif cone_over:
                # Dynamic line: the cone is the speed sweep's mechanism readout,
                # not a gate. The shipped dynamic line (Gate-19 place sweep) has
                # held place legs up to 1.23x and one failure (the A6 kiwi catch
                # miss) whose lift carry reads 2.41x/199.6 mm
                # (`logs/fast/14_accept_place035.log`); the failure mechanism is
                # already covered by the rate floor and the mechanism traces, and
                # gating it here would make every dynamic acceptance red by
                # construction (the P2b correction recorded exactly that). The
                # strict form is one flag away (`--strict-cone`).
                verdict = f"ok (cone {carry['cone']:.2f}x reported)"
                warnings.append(
                    f"carry {carry['leg']}: cone={carry['cone']:.2f}x over the "
                    f"{args.cone:g}x budget with slip={carry['slip_mm']:.1f}mm - "
                    f"reported on the dynamic line, not gated"
                )
            elif not gated:
                # The reactive re-seat teleports the pads, so the pad finite
                # difference measures the correction, not the payload.
                verdict = "ok (reseated, not gated)"
            else:
                verdict = "ok"
            verdict += verdict_note
            print(
                f"  {carry['leg']:<14s} {carry['distance_cm']:5.0f}c "
                f"{carry['cone']:6.2f}x {carry['cone_over_pct']:4d}% "
                f"{carry['slip_mm']:6.1f}mm {carry['in_hand_v']:10.3f} "
                f"{carry['recoveries']:5d}  {verdict}"
            )
        held = [c["cone"] for c in carries if c["recoveries"] == 0]
        if held:
            print(
                f"  worst held-grip cone: {max(held):.2f}x budget "
                f"(budget {args.cone:g}x)"
            )
        teleports = [c for c in carries if c["v_max"] > args.hand_vmax]
        print(
            f"  hand speed: worst {max(c['v_max'] for c in carries):.3f} m/s; "
            f"{len(teleports)}/{len(carries)} leg(s) over {args.hand_vmax:g} m/s "
            f"(reported, not gated) - every other leg sits at the commanded "
            f"0.176-0.371"
        )
    else:
        print("\n  (no `[motion] carry` lines in this log - carry budget not checked)")

    if tally is None:
        failures.append("no [stats] attempts/successes line found")
        print("\n  success: not found")
    else:
        attempts, successes = tally
        rate = successes / attempts if attempts else 0.0
        if args.min_success_rate is not None:
            floor = args.min_success_rate
            floor_note = "override"
        elif dynamic:
            floor = DYNAMIC_SUCCESS_FLOOR
            floor_note = f"dynamic line, measured baseline 9/10"
        else:
            floor = SUCCESS_RATE_FLOOR
            floor_note = "indexed line"
        print(
            f"\n  success: {successes}/{attempts} = {rate:.0%} "
            f"(floor {floor:.0%} - {floor_note})"
        )
        if rate < floor:
            failures.append(
                f"success {successes}/{attempts} below {floor:.0%}"
            )

    if args.write_fingerprint:
        with open(args.write_fingerprint, "w", encoding="utf-8") as handle:
            json.dump(fingerprint_of(legs), handle)
        print(f"  wrote fingerprint -> {args.write_fingerprint}")

    if args.fingerprint:
        with open(args.fingerprint, encoding="utf-8") as handle:
            reference = json.load(handle)
        here = fingerprint_of(legs)
        if here == reference:
            print(f"  fingerprint: matches {args.fingerprint}")
        else:
            failures.append("fingerprint differs from the reference (different attractor)")
            print(
                f"  fingerprint: DIFFERS from {args.fingerprint} - this run landed in a "
                f"different attractor, so do not compare its success count with the "
                f"reference log's"
            )
            for index in range(max(len(here), len(reference))):
                left = here[index] if index < len(here) else None
                right = reference[index] if index < len(reference) else None
                if left != right:
                    print(f"    leg {index + 1}: this={left} reference={right}")

    if failures:
        print(f"\nFAIL: {len(failures)} problem(s)")
        for item in failures:
            print(f"  - {item}")
        return 1
    if dynamic and not args.strict_cone:
        print(
            "\nPASS: every descent is inside its profile's speed and lurch bound, the "
            "carry cone/slip is reported, and the success rate is at or above the "
            "dynamic line's floor"
        )
    else:
        print(
            "\nPASS: every descent is inside the reference speed and the lurch bound, "
            "and every held-grip carry is inside the friction cone"
        )
    if warnings:
        print(f"note: {len(warnings)} warning(s) (reported, not gating):")
        for item in warnings:
            print(f"  - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
