#!/usr/bin/env python3
"""P42 phase 1: parse the `[seat]` census rows and print the seat table.

Read-only. Joins, per grip:

* the `[seat] ... freeze ...` row (t=0, the close freeze) and its four bounded
  carry samples (`grasp_lift@2/8/20`, `place0@2`),
* the attempt's outcome (`[run] attempt N: grasped=.. placed=..`) and the
  species/arm table (`[run]   pear  arm=left ...`),
* the per-leg slip (`[motion] carry <leg>: ... slip_max=.. in-hand |v|max=..`).

Usage:
    python3 logs/p42/p2/seat_parse.py logs/p42/p2/seat_accept.log [more.log ...]

Prints one row per grip and then the pooled axis statistics, split by outcome
class. Nothing here is a rate: one claimed run is one deterministic branch (or,
for an instrumented run, one branch of its own).
"""

from __future__ import annotations

import re
import statistics as st
import sys
from pathlib import Path

def _vec(prefix: str) -> str:
    """Three signed floats inside parentheses, as named groups `<prefix>x/y/z`."""
    return (
        rf"\(\s*(?P<{prefix}x>[-+0-9.]+)\s*,\s*(?P<{prefix}y>[-+0-9.]+)"
        rf"\s*,\s*(?P<{prefix}z>[-+0-9.]+)\s*\)"
    )


SEAT = re.compile(
    r"\[seat\]\s+(?P<side>\w+)\s+(?:a=(?P<attempt>-?\d+)\s+)?idx=(?P<idx>-?\d+)\s+"
    r"(?P<when>\S+)\s+t=(?P<t>-?\d+)\s+"
    rf"d={_vec('d')}mm\s+\|d\|=(?P<dnorm>[-+0-9.]+)mm\s+"
    rf"tool={_vec('tool')}mm\s+drift={_vec('drift')}mm\s+"
    r"F=\(\s*(?P<f1>[-+0-9.]+)\s*,\s*(?P<f2>[-+0-9.]+)\s*\)N\s+"
    r"n=(?P<n>-?\d+)\s+asym=(?P<asym>[-+0-9.]+)\s+"
    r"cmd=(?P<cmd>[-+0-9.]+)mm\s+sep=(?P<sep>[-+0-9.]+)mm\s+"
    r"faces=(?P<faces>[-+0-9.]+)mm\s+tilt=(?P<tilt>[-+0-9.]+)deg"
)
ATTEMPT = re.compile(
    r"\[run\] attempt (?P<idx>\d+): grasped=(?P<grasped>\w+) "
    r"placed=(?P<placed>\w+) lift=(?P<lift>[-+0-9.]+) m force=(?P<force>[-+0-9.]+) N"
)
SPECIES = re.compile(
    r"\[run\]\s+(?P<species>[a-z]+)\s+arm=(?P<arm>\w+)\s+grasped=(?P<grasped>\w+) "
    r"placed=(?P<placed>\w+) lift=(?P<lift>[-+0-9.]+) N=(?P<force>[-+0-9.]+)"
)
CARRY = re.compile(
    r"\[motion\] carry (?P<leg>\S+): .*?slip_max=(?P<slip>[-+0-9.]+) mm, "
    r"in-hand \|v\|max=(?P<vmax>[-+0-9.]+) m/s"
)
STATS = re.compile(
    r"\[stats\] attempts=(?P<attempts>\d+) successes=(?P<successes>\d+) "
    r"diverted=(?P<diverted>\d+) success_rate=(?P<rate>\d+)%"
)


def parse(path: Path):
    seats: dict[tuple[int, str], list[dict]] = {}
    order: list[tuple[int, str]] = []
    attempts: dict[int, dict] = {}
    species_rows: list[dict] = []
    legs_by_attempt: dict[int, list[dict]] = {}
    stats = None
    pending_legs: list[dict] = []
    for line in path.read_text(errors="replace").splitlines():
        m = SEAT.search(line)
        if m:
            # `a=` (the attempt ordinal, from `FRUIT_EPISODE_INDEX`) is present
            # on logs written after the phase-1 format fix; without it the group
            # order *is* the attempt order, which is only equivalent when there
            # is one grip per attempt (the report prints the counts so a reader
            # can see which form was parsed).
            # `-1` = the log predates the phase-1 format fix; the ordinals are
            # re-derived below from the first appearance of each grip.
            attempt = int(m["attempt"]) if m["attempt"] is not None else -1
            key = (attempt, m["side"], int(m["idx"]))
            row = {
                "attempt": attempt,
                "side": m["side"],
                "fruit": int(m["idx"]),
                "when": m["when"],
                "t": int(m["t"]),
                "d": tuple(float(m[f"d{a}"]) for a in "xyz"),
                "dnorm": float(m["dnorm"]),
                "tool": tuple(float(m[f"tool{a}"]) for a in "xyz"),
                "drift": tuple(float(m[f"drift{a}"]) for a in "xyz"),
                "f": (float(m["f1"]), float(m["f2"])),
                "n": int(m["n"]),
                "asym": float(m["asym"]),
                "cmd": float(m["cmd"]),
                "sep": float(m["sep"]),
                "faces": float(m["faces"]),
                "tilt": float(m["tilt"]),
            }
            if key not in seats:
                seats[key] = []
                order.append(key)
            seats[key].append(row)
            continue
        m = CARRY.search(line)
        if m:
            # The attempt's `[run] attempt N:` line is printed at its *end*, so
            # carry legs accumulate here and are claimed by the next one.
            pending_legs.append(
                {"leg": m["leg"], "slip": float(m["slip"]), "vmax": float(m["vmax"])}
            )
            continue
        m = ATTEMPT.search(line)
        if m:
            idx = int(m["idx"])
            attempts[idx] = {
                "grasped": m["grasped"] == "True",
                "placed": m["placed"] == "True",
                "lift": float(m["lift"]),
            }
            legs_by_attempt[idx] = pending_legs
            pending_legs = []
            continue
        m = SPECIES.search(line)
        if m:
            species_rows.append(
                {
                    "species": m["species"],
                    "arm": m["arm"],
                    "placed": m["placed"] == "True",
                }
            )
            continue
        m = STATS.search(line)
        if m:
            stats = m.groupdict()

    if any(key[0] < 0 for key in order):
        # Pre-fix logs: one attempt per grip in stream order (the report prints
        # the two counts so a mismatch is visible rather than silent).
        renumber = {}
        ordinal = 0
        for key in order:
            grip = (key[1], key[2])
            if grip not in renumber:
                renumber[grip] = ordinal
                ordinal += 1
            renumber[key] = (renumber[grip], key[1], key[2])
        order = [renumber[key] for key in order]
        seats = {renumber[key]: rows for key, rows in seats.items()}
        for key, rows in seats.items():
            for row in rows:
                row["attempt"] = key[0]

    return seats, order, attempts, species_rows, legs_by_attempt, stats


def cls_of(row: dict) -> str:
    if row.get("placed"):
        return "placed"
    if row.get("grasped"):
        return "escape"
    return "no_grasp"


def compact(values: list[float]) -> str:
    """`median [min, max]` with no n (for the narrow per-ordinal table)."""
    if not values:
        return "n/a"
    return f"{st.median(values):+.1f} [{min(values):+.1f},{max(values):+.1f}]"


def axis_stats(values: list[float]) -> str:
    if not values:
        return "n/a"
    if len(values) == 1:
        return f"{values[0]:+.1f} (n=1)"
    return (
        f"med {st.median(values):+.1f} [{min(values):+.1f}, {max(values):+.1f}] "
        f"(n={len(values)})"
    )


def report(path: Path) -> None:
    seats, order, attempts, species_rows, legs, stats = parse(path)
    print("=" * 100)
    print(f"{path}   md5-free read; {len(order)} grips, {len(attempts)} attempts")
    if len(order) != len(attempts):
        print(
            f"  NOTE: {len(order)} grips vs {len(attempts)} attempts. The attempt join "
            "uses the `[seat] a=` field when the log carries it; a log without it is "
            "joined by group order, which is only equivalent at one grip per attempt."
        )
    if stats:
        print(
            "  [stats] attempts={attempts} successes={successes} "
            "diverted={diverted} rate={rate}%".format(**stats)
        )
    print()
    header = (
        f"{'a':>3} {'idx':>5} {'arm':<5} {'species':<10} {'class':<8} "
        f"{'dx':>7} {'dy':>7} {'dz':>7} {'|d|':>6} "
        f"{'toolx':>7} {'toolz':>7} {'F1':>5} {'F2':>5} {'asym':>5} "
        f"{'cmd':>6} {'sep':>6} {'faces':>6} {'tilt':>5} "
        f"{'drift_f':>7} {'m_slip_l':>9} {'m_slip_p':>9}"
    )
    print(header)
    print("-" * len(header))
    print(
        "  m_slip_* = the LEGACY `[motion] carry ... slip_max` (frame-contaminated:\n"
        "  25.6-104.7 mm of ghost slip on *placed* carries, AGENTS section 2) - shown\n"
        "  only so a reader can see why it is not the discriminator; `drift_f` is this\n"
        "  instrument's own frame-free freeze->last-sample displacement."
    )
    bucket: dict[str, dict[str, list[float]]] = {}
    for key in order:
        idx, side, fruit = key
        rows = seats[key]
        freeze = rows[0]
        last = rows[-1]
        meta = attempts.get(idx, {})
        sp = species_rows[idx] if idx < len(species_rows) else {}
        cls = cls_of({**meta, "grasped": meta.get("grasped", False)})
        legs_a = legs.get(idx, [])
        slip_lift = next((l["slip"] for l in legs_a if l["leg"] == "grasp_lift"), None)
        slip_place = next((l["slip"] for l in legs_a if l["leg"].startswith("place")), None)
        drift_norm = (
            sum(c * c for c in last["drift"]) ** 0.5 if last is not rows[0] else 0.0
        )
        print(
            f"{idx:>3} {fruit:>5} {side:<5} {sp.get('species', '?'):<10} {cls:<8} "
            f"{freeze['d'][0]:>+7.1f} {freeze['d'][1]:>+7.1f} {freeze['d'][2]:>+7.1f} "
            f"{freeze['dnorm']:>6.1f} "
            f"{freeze['tool'][0]:>+7.1f} {freeze['tool'][2]:>+7.1f} "
            f"{freeze['f'][0]:>5.2f} {freeze['f'][1]:>5.2f} {freeze['asym']:>5.2f} "
            f"{freeze['cmd']:>6.1f} {freeze['sep']:>6.1f} {freeze['faces']:>+6.1f} "
            f"{freeze['tilt']:>5.1f} "
            f"{drift_norm:>7.1f} "
            f"{'-' if slip_lift is None else f'{slip_lift:.1f}':>9} "
            f"{'-' if slip_place is None else f'{slip_place:.1f}':>10}"
        )
        b = bucket.setdefault(cls, {"dx": [], "dy": [], "dz": [], "dn": [], "asym": [], "faces": [], "drift": []})
        b["dx"].append(freeze["d"][0])
        b["dy"].append(freeze["d"][1])
        b["dz"].append(freeze["d"][2])
        b["dn"].append(freeze["dnorm"])
        b["asym"].append(freeze["asym"])
        b["faces"].append(freeze["faces"])
        b["drift"].append(drift_norm)
    print()
    for cls in ("placed", "escape", "no_grasp"):
        b = bucket.get(cls)
        if not b:
            continue
        print(f"[{cls}] n={len(b['dx'])}")
        for axis in ("dx", "dy", "dz", "dn", "asym", "faces", "drift"):
            print(f"   {axis:<6} {axis_stats(b[axis])}")
    print()
    print("drift by sample ordinal, per class (world mm; `drift` = d - d_freeze,")
    print("i.e. minus the payload's displacement in the hand frame):")
    print(
        f"  {'class':<9} {'k':>2} {'leg':<11} {'n':>2}  {'drift_x':<22} "
        f"{'drift_y':<22} {'drift_z':<22} {'|drift|':<22} {'n<2':>4}"
    )
    by_ord: dict[tuple[str, int], list[dict]] = {}
    legname: dict[int, str] = {}
    for key in order:
        rows = seats[key]
        meta = attempts.get(key[0], {})
        cls = cls_of({"grasped": meta.get("grasped", False), "placed": meta.get("placed", False)})
        for k, row in enumerate(rows):
            leg = re.sub(r"@-?\d+$", "", row["when"])
            legname[k] = leg
            by_ord.setdefault((cls, k), []).append(row)
    for cls in ("placed", "escape", "no_grasp"):
        ks = sorted(k for (c, k) in by_ord if c == cls)
        for k in ks:
            rows = by_ord[(cls, k)]
            one_sided = sum(1 for r in rows if r["n"] < 2)
            print(
                f"  {cls:<9} {k:>2} {legname.get(k, '?'):<11} {len(rows):>2}  "
                f"{compact([r['drift'][0] for r in rows]):<22} "
                f"{compact([r['drift'][1] for r in rows]):<22} "
                f"{compact([r['drift'][2] for r in rows]):<22} "
                f"{compact([sum(c * c for c in r['drift']) ** 0.5 for r in rows]):<22} "
                f"{one_sided:>4}"
            )
    print()
    print("per-grip sample stream (freeze then the scheduled carry ticks):")
    for key in order:
        idx, side, fruit = key
        rows = seats[key]
        meta = attempts.get(idx, {})
        sp = species_rows[idx] if idx < len(species_rows) else {}
        cls = cls_of(meta | {"grasped": meta.get("grasped", False)})
        chain = " -> ".join(
            f"{r['when']}:d=({r['d'][0]:+.1f},{r['d'][1]:+.1f},{r['d'][2]:+.1f}) "
            f"dr=({r['drift'][0]:+.1f},{r['drift'][1]:+.1f},{r['drift'][2]:+.1f}) "
            f"F=({r['f'][0]:.1f},{r['f'][1]:.1f}) n={r['n']}"
            for r in rows
        )
        print(f"  {idx:>2} {fruit:>5} {side:<5} {sp.get('species', '?'):<10} {cls:<8} {chain}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    for arg in argv[1:]:
        report(Path(arg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
