#!/usr/bin/env python3
"""P41 phase 3 - the force-cap census, re-derived from the claimed logs.

    python3 logs/p41/p3/mf_table.py logs/p41/p3/accept_control.log \
        logs/p41/p3/accept_mf30.log logs/p41/p3/accept_mf60.log \
        logs/p41/p3/pear_mf30.log logs/p41/p3/twoline_mf30.log

Read-only. Per run: the attempt outcomes (placed / carried-not-placed /
no-grasp) from the `[run]` summary rows (the only per-arm source, since the
two-line battery has no `[carry]` rows), the per-leg `[carry]` classes
(`clean_slip` > 5 mm = escape, and a leg whose minimum contact count is 0 = the
W8-B no-contact/never-held class), the held legs' force floor (`force_min`), the
escape legs' force at the slip onset, and - where a `pry_sep_max*.txt` from
`logs/w8/B_metric.py` is given - the **escape legs'** pad-span maximum. The
mechanical open stop is `JAW_SEPARATION_OFFSET + 2 * OPEN` = 98 mm, so "a pry"
is a span near 98; a held leg's span is just the fruit's own diameter and is
not a pry.

The question: at the raised cap, does an escape still pry the pads toward that
stop (the W8-B signature: 17/31 escapes; 98.3-98.5 mm at the 10 N cap), or does
the drive hold them closed while the payload leaves some other way?
"""
from __future__ import annotations

import re
import statistics
import sys

ATTEMPT = re.compile(
    r"\[run\] attempt (\d+): (?:picking (\w+) grade (\w+) into output lane (\d+)"
    r"|(no eligible fruit))"
)
RESULT = re.compile(
    r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+) lift=([+-][0-9.]+) m "
    r"force=([0-9.]+) N notes=(\[.*\])"
)
SUMMARY = re.compile(
    r"\[run\]\s+(\w+)\s+arm=(\w+)\s+grasped=(\w+) placed=(\w+) lift=([+-][0-9.]+) N=([0-9.]+)"
)
CARRY = re.compile(r"\[carry\] (\w+) (\w+): (.*)$")
FIELDS = re.compile(r"(\S+)=(\S+)")
TRACE = re.compile(
    r"^\s*trace_\d+_(\w+)_scripted_(ok|fail)\.json\s+(\w+)\s+(ok|fail)\s+leg\d+\s+"
    r"n=\d+\s+(\S+)\s+slip_max=\s*([0-9.]+)mm.*?sep=\s*([0-9.]+)/"
)
OPEN_STOP = 98.0


def parse(path: str) -> dict:
    attempts: dict[int, dict] = {}
    summary: list[dict] = []
    stats = None
    for line in open(path, encoding="utf-8", errors="replace"):
        match = ATTEMPT.search(line)
        if match:
            attempts[int(match.group(1))] = {
                "fruit": match.group(2),
                "legs": [],
                "outcome": None,
            }
            continue
        match = RESULT.search(line)
        if match:
            index = int(match.group(1))
            attempts.setdefault(index, {"fruit": "?", "legs": []})["outcome"] = {
                "placed": match.group(3) == "True",
                "grasped": match.group(2) == "True",
                "notes": match.group(6).strip("[]"),
            }
            continue
        match = SUMMARY.search(line)
        if match:
            summary.append(
                {
                    "fruit": match.group(1),
                    "arm": match.group(2),
                    "grasped": match.group(3) == "True",
                    "placed": match.group(4) == "True",
                }
            )
            continue
        match = CARRY.search(line)
        if match:
            values = dict(FIELDS.findall(match.group(3)))
            # The carry row is attributed to the attempt it follows.
            target = attempts[max(attempts)] if attempts else None
            if target is not None:
                target["legs"].append(
                    {
                        "side": match.group(1),
                        "leg": match.group(2),
                        "slip": float(values.get("clean_slip_max", "1e9")[:-2]),
                        "fmin": values.get("force_min", "n/a"),
                        "fonset": values.get("force@onset", "n/a"),
                        "sep_onset": values.get("sep@onset", "n/a"),
                        "contacts": values.get("min_contacts", "?"),
                    }
                )
            continue
        if "[stats]" in line:
            stats = line.strip()
    return {"attempts": attempts, "summary": summary, "stats": stats}


def trace_rows(path: str) -> list[dict]:
    """The B_metric rows, with the class and the span maximum."""
    try:
        rows = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return []
    out = []
    for line in rows:
        match = TRACE.search(line)
        if match:
            out.append(
                {
                    "arm": match.group(3),
                    "class": match.group(5),
                    "slip": float(match.group(6)),
                    "sep_max": float(match.group(7)),
                }
            )
    return out


def report(path: str, trace_path: str | None) -> None:
    parsed = parse(path)
    attempts = parsed["attempts"]
    summary = parsed["summary"]
    per_arm: dict[str, dict[str, int]] = {}
    kind_counts = {"placed": 0, "cnp": 0, "no-grasp": 0}
    for row in summary:
        slot = per_arm.setdefault(row["arm"], {"placed": 0, "attempts": 0})
        slot["attempts"] += 1
        if row["placed"]:
            slot["placed"] += 1
            kind_counts["placed"] += 1
        elif row["grasped"]:
            kind_counts["cnp"] += 1
        else:
            kind_counts["no-grasp"] += 1
    legs = {"held": 0, "escape": 0, "never-held": 0}
    held_fmin: list[float] = []
    escapes: list[dict] = []
    for attempt in attempts.values():
        for leg in attempt["legs"]:
            contacts = leg["contacts"]
            never = contacts.isdigit() and int(contacts) == 0
            if never and leg["slip"] > 5.0:
                legs["never-held"] += 1
                continue
            if leg["slip"] > 5.0:
                legs["escape"] += 1
                escapes.append({**leg, "fruit": attempt["fruit"]})
            else:
                legs["held"] += 1
                try:
                    held_fmin.append(float(leg["fmin"][:-1]))
                except ValueError:
                    pass
    print(f"== {path} ==")
    arms = " ".join(
        f"{name}={row['placed']}/{row['attempts']}"
        for name, row in sorted(per_arm.items())
    )
    print(
        f"  attempts={sum(kind_counts.values())} placed={kind_counts['placed']} "
        f"cnp={kind_counts['cnp']} no-grasp={kind_counts['no-grasp']} | {arms}"
    )
    if parsed["stats"]:
        print(f"  {parsed['stats'].replace('[fruit] ', '')}")
    if any(legs.values()):
        print(
            f"  carry legs: held={legs['held']} escape={legs['escape']} "
            f"never-held={legs['never-held']}"
        )
    if held_fmin:
        print(
            f"  held-leg force_min: median {statistics.median(held_fmin):.2f} N "
            f"range {min(held_fmin):.2f}-{max(held_fmin):.2f} N (n={len(held_fmin)})"
        )
    for leg in escapes:
        print(
            f"  ESCAPE {leg['fruit']:<10} {leg['side']:<5} {leg['leg']:<10} "
            f"clean_slip={leg['slip']:7.1f}mm F@onset={leg['fonset']:>6} "
            f"sep@onset={leg['sep_onset']:>6} Fmin={leg['fmin']:>5}"
        )
    if trace_path:
        rows = trace_rows(trace_path)
        if rows:
            print("  trace (W8-B) per leg: class, slip_max, sep_max [mm]")
            for row in rows:
                print(
                    f"    {row['arm']:<5} {row['class']:<11} "
                    f"slip_max={row['slip']:8.2f} sep_max={row['sep_max']:5.1f}"
                    + (
                        f"  <- {100.0 * row['sep_max'] / OPEN_STOP:.0f} % of the "
                        f"{OPEN_STOP:.0f} mm open stop"
                        if row["class"] == "escape" and row["sep_max"] > 60.0
                        else ""
                    )
                )
            escape_spans = [row["sep_max"] for row in rows if row["class"] == "escape"]
            if escape_spans:
                print(
                    f"  escape sep_max: {min(escape_spans):.1f}-{max(escape_spans):.1f} mm "
                    f"on {len(escape_spans)} escape leg(s) "
                    f"({100.0 * max(escape_spans) / OPEN_STOP:.0f} % of the open stop)"
                )
    print()


def main(argv: list[str]) -> int:
    traces = {
        # the 10 N arm's trace is P41 phase 2's, from the byte-identical branch
        "accept_control": "logs/p41/p2/pry_sep_max.txt",
        "accept_mf30": "logs/p41/p3/pry_sep_max_mf30.txt",
        "accept_mf60": "logs/p41/p3/pry_sep_max_mf60.txt",
    }
    for path in argv:
        key = path.rsplit("/", 1)[-1].removesuffix(".log")
        report(path, traces.get(key))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
