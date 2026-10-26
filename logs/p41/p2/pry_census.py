#!/usr/bin/env python3
"""P41 phase 2 - the jaw-pry census, re-derived from the claimed logs.

    python3 logs/p41/p2/pry_census.py logs/p41/p2/accept_preprofile.log \
        logs/p41/p2/accept_profile.log logs/p41/p2/pear_profile.log

Read-only. For each attempt: the fruit/grade/lane, the per-carry-leg `[carry]`
row (clean_slip, force and pad span at the slip onset, the **pad span at the
tick contact is lost**, the end span, the leg's force floor and contact count),
the force servo's own trip count, and the outcome (`grasped`/`placed`, which
is the cnp class when the two disagree).

The question the census answers: at the profile's ~9.9 N pinch, does an
escape still spread the pads toward their 98-99 mm limit (the W8-B signature
of 17/31 escapes)? `jaw_separation()` is the span between the finger link
origins, whose pad faces sit at the origins (`ArmController.FINGER_FACE_OFFSET`
= 0.0), so the mechanical limit is `JAW_SEPARATION_OFFSET + 2 * OPEN` =
0.010 + 2 * 0.044 = 0.098 m.
"""
from __future__ import annotations

import re
import sys

ATTEMPT = re.compile(r"^.*\[run\] attempt (\d+): picking (\w+) grade (\w+) into output lane (\d+)")
RESULT = re.compile(
    r"^.*\[run\] attempt (\d+): grasped=(\w+) placed=(\w+) lift=([+-][0-9.]+) m "
    r"force=([0-9.]+) N notes=(\[.*\])"
)
CARRY = re.compile(r"^.*\[carry\] (\w+) (\w+): (.*)$")
SERVO = re.compile(r"^.*\[task\] force servo: (\w+): .*trips=(\d+)")
FIELDS = re.compile(r"(\S+)=(\S+)")


def parse(path: str) -> list[dict]:
    attempts: list[dict] = []
    current = None
    for line in open(path, encoding="utf-8", errors="replace"):
        match = ATTEMPT.match(line)
        if match:
            current = {
                "attempt": int(match.group(1)),
                "fruit": match.group(2),
                "grade": match.group(3),
                "lane": int(match.group(4)),
                "legs": [],
                "trips": {},
                "outcome": None,
            }
            attempts.append(current)
            continue
        if current is None:
            continue
        match = CARRY.match(line)
        if match:
            values = dict(FIELDS.findall(match.group(3)))
            current["legs"].append(
                {
                    "side": match.group(1),
                    "leg": match.group(2),
                    "slip": values.get("clean_slip_max", "?"),
                    "vmax": values.get("in-hand_vmax", "?"),
                    "onset_row": values.get("onset_row", "?"),
                    "force_onset": values.get("force@onset", "?"),
                    "sep_onset": values.get("sep@onset", "?"),
                    "sep_loss": values.get("sep@loss", "?"),
                    "sep_end": values.get("sep_end", "?"),
                    "loss_row": values.get("loss_row", "?"),
                    "fmin": values.get("force_min", "?"),
                    "min_contacts": values.get("min_contacts", "?"),
                }
            )
            continue
        match = SERVO.match(line)
        if match:
            current["trips"][match.group(1)] = int(match.group(2))
            continue
        match = RESULT.match(line)
        if match:
            current["outcome"] = {
                "grasped": match.group(2) == "True",
                "placed": match.group(3) == "True",
                "lift": float(match.group(4)),
                "force": float(match.group(5)),
                "notes": match.group(6),
            }
    return attempts


def main(paths: list[str]) -> int:
    for path in paths:
        print(f"== {path} ==")
        attempts = parse(path)
        for attempt in attempts:
            outcome = attempt["outcome"] or {}
            if outcome.get("placed"):
                kind = "placed"
            elif outcome.get("grasped"):
                kind = "cnp"  # grasped, carried, not placed
            elif outcome:
                kind = "no-grasp"
            else:
                kind = "-"
            trips = "/".join(
                f"{side[0]}{count}" for side, count in sorted(attempt["trips"].items())
            )
            print(
                f"att {attempt['attempt']:>2} {attempt['fruit']:<10} {attempt['grade']} "
                f"lane{attempt['lane']} -> {kind:<8} trips={trips or '-':<6} "
                f"lift={outcome.get('lift', float('nan')):+.3f} "
                f"N={outcome.get('force', float('nan')):5.2f} notes={outcome.get('notes', '-')}"
            )
            for leg in attempt["legs"]:
                print(
                    f"    {leg['side']:<5} {leg['leg']:<10} "
                    f"clean_slip={leg['slip']:>9} in-hand_vmax={leg['vmax']:>5} "
                    f"F@onset={leg['force_onset']:>6} sep@onset={leg['sep_onset']:>6} "
                    f"loss_row={leg['loss_row']:>4} sep@loss={leg['sep_loss']:>6} "
                    f"sep_end={leg['sep_end']:>6} Fmin={leg['fmin']:>5} "
                    f"contacts(min)={leg['min_contacts']:>2}"
                )
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
