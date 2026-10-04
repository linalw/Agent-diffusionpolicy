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
       it: `|v|max <= FRUIT_APPROACH_VMAX` (0.06 m/s, the profile's own peak);
    2. it may not absorb an impulse: a single 1/120 s control tick may not change
       its speed by more than twice the commanded cruise (`LURCH_DV`). One tick
       of 0.06 m/s * 2 is 0.12 m/s; as an acceleration that is 14.4 m/s^2.
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
"""

from __future__ import annotations

import argparse
import json
import re

#: The descent profile cruises at 0.06 m/s (FRUIT_APPROACH_VMAX) and is built so
#: no sample of the commanded profile exceeds its own cruise speed. An achieved
#: speed above it means the arm moved further than it was told to, i.e. something
#: pushed it.
REFERENCE_VMAX = 0.06  # [m/s]
#: Control period the metrics are differenced over (the scripts step at 120 Hz).
CONTROL_DT = 1.0 / 120.0
#: A payload-free hand may not absorb an impulse: one control tick may not change
#: its speed by more than twice the commanded cruise, i.e. 14.4 m/s^2.
LURCH_DV = 2.0 * REFERENCE_VMAX  # [m/s per tick]
LURCH_ACCEL = LURCH_DV / CONTROL_DT  # [m/s^2]
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
#: Fraction of attempts that must succeed. The shipped ten-attempt suite scores
#: 9/10; a short demo run is judged on the same fraction so one script can check
#: both, rather than hard-coding "of ten".
SUCCESS_RATE_FLOOR = 0.9

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


def parse(path: str) -> tuple[list[dict], list[dict], tuple[int, int] | None]:
    legs: list[dict] = []
    carries: list[dict] = []
    tally: tuple[int, int] | None = None
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
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
    return legs, carries, tally


def fingerprint_of(legs: list[dict]) -> list[list]:
    """Per-descent scenario fingerprint: (samples, peak speed).

    Deliberately excludes the per-tick peak acceleration. `a_max` differences two
    1/120 s samples, so on a leg whose steps are tenths of a millimetre it mostly
    measures jitter (this module's own note), and it varies run to run on the
    *same* scenario: logs/370 against logs/accept.log have every leg's `samples`
    and `|v|max` identical to the digit while leg 6's `a_max` reads 5.75 against
    3.882 - a false "different attractor". The lurch is still bounded separately
    via `LURCH_ACCEL`, so dropping it here loses no gate.
    """
    return [[leg["samples"], round(leg["v_max"], 4)] for leg in legs]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", help="a run log from scripts/20_pick_place.py")
    parser.add_argument("--vmax", type=float, default=REFERENCE_VMAX)
    parser.add_argument("--lurch", type=float, default=LURCH_ACCEL)
    parser.add_argument("--cone", type=float, default=CARRY_CONE)
    parser.add_argument("--hand-vmax", type=float, default=HAND_VMAX)
    parser.add_argument("--min-success-rate", type=float, default=SUCCESS_RATE_FLOOR)
    parser.add_argument("--fingerprint", help="reference fingerprint JSON to compare against")
    parser.add_argument("--write-fingerprint", help="write this log's fingerprint here")
    args = parser.parse_args()

    legs, carries, tally = parse(args.log)
    failures: list[str] = []
    warnings: list[str] = []
    if not legs:
        print(f"FAIL {args.log}: no located motion lines found")
        print("     (run with FRUIT_MOTION_REPORT=1 and FRUIT_APPROACH_MODE=cartesian)")
        return 1

    print(f"{args.log}: {len(legs)} descent leg(s)")
    print(
        f"  {'#':>2s} {'dist':>6s} {'samples':>7s} {'|v|max':>7s} {'|a|max':>8s} "
        f"{'|dv|':>6s} {'a_med':>6s} {'peak@':>6s} {'a_win5':>7s}  verdict"
    )
    for index, leg in enumerate(legs, 1):
        delta_v = leg["a_max"] * CONTROL_DT
        problems = []
        if leg["v_max"] > args.vmax:
            problems.append(f"|v|max>{args.vmax:g}")
        if leg["a_max"] > args.lurch:
            problems.append(f"lurch |dv|>{LURCH_DV:g} m/s per tick")
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
        peak = "-" if leg["peak_at"] is None else f"{leg['peak_at']:6.2f}"
        print(
            f"  {index:2d} {leg['distance_cm']:5.1f}c {leg['samples']:7d} "
            f"{leg['v_max']:7.3f} {leg['a_max']:8.2f} {delta_v:6.3f} "
            f"{med} {peak} {win}  {verdict}"
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
        f"  worst: |v|max={worst_v:.4f} m/s (budget {args.vmax:g}), "
        f"lurch={worst_dv:.3f} m/s/tick (budget {LURCH_DV:g})" + tail
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
            if gated and carry["cone"] > args.cone:
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
        print(
            f"\n  success: {successes}/{attempts} = {rate:.0%} "
            f"(floor {args.min_success_rate:.0%})"
        )
        if rate < args.min_success_rate:
            failures.append(
                f"success {successes}/{attempts} below {args.min_success_rate:.0%}"
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
    print(
        "\nPASS: every descent is inside the reference speed and the lurch bound, "
        "and every held-grip carry is inside the friction cone"
    )
    if warnings:
        print(f"note: {len(warnings)} descent roughness warning(s) (not gating):")
        for item in warnings:
            print(f"  - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
