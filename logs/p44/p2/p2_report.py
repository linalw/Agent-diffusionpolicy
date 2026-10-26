"""P44 phase 2 report: the speed cells, per arm and per battery.

    python3 logs/p44/p2/p2_report.py                 # every battery present
    python3 logs/p44/p2/p2_report.py A C             # battery A, pear battery

Parses the `[cycle]` decomposition, `[stats]`, the per-attempt `[run]` rows, the
failure notes, the `[motion] carry`/`approach` legs and the force-servo rows of
the batch logs, and prints one block per (battery, arm).

The **grip guard** (PREREG E4) is the pillar, so it is printed per arm as four
counts, all of them exact (no thresholds): attempts with a `fruit did not follow
the gripper` note, attempts whose carry was rescued (`recoveries>0`), force-servo
rows whose `Fmin` is 0.00 N (the loaded-slide signature, P43's `force_min = 0`),
and the placed count. The legacy `slip_max` is **not** printed as a slip read
(W8-B: it is frame-contaminated); W8-B's `clean_slip` is an offline
re-derivation and is not attempted here.

Nothing here writes outside stdout.
"""

from __future__ import annotations

import os
import re
import statistics
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
OUT = os.path.join(ROOT, "logs", "p44", "p2")

BATTERIES = {
    "A": ("acceptance seed 5", "accept_s5"),
    "B": ("acceptance seed 6", "accept_s6"),
    "C": ("pear battery seed 5", "pear_s5"),
    "D": ("two-line dense seed 5", "twoline_s5"),
}
ARMS = ["C", "S1", "S2", "S3", "S13"]
BLOCKS = ["prepose", "hover", "descent", "close", "grip", "lift", "place",
          "release", "return", "end", "total"]

CYCLE = re.compile(r"\[cycle\] attempt \d+: (.+)")
STATS = re.compile(r"\[stats\] attempts=(\d+) successes=(\d+) diverted=(\d+) "
                   r"success_rate=(\d+)% sim=([\d.]+)s total, ([\d.]+)s/attempt")
ATTEMPT = re.compile(r"\[run\] attempt (\d+)(?: \((\w+)\))?: grasped=(\w+) placed=(\w+) "
                     r"lift=([+-][\d.]+) m force=([\d.]+) N (?:sim=[\d.\-s]+ )?notes=\[(.*?)\]")
CARRY = re.compile(r"\[motion\] carry (\w+): ([\d.]+) cm, (\d+) ticks, "
                   r"\|v\|cmd=([\d.]+) \|a\|cmd=([\d.]+), slip_max=([\d.]+) mm, "
                   r"in-hand \|v\|max=([\d.]+) m/s, recoveries=(\d+): steps=\d+, "
                   r"\|v\|max=([\d.]+) m/s, \|a\|max=([\d.]+) m/s\^2, .*?"
                   r"cone=([\d.]+)x budget \((\d+) pct over\)")
APPROACH = re.compile(r"\[motion\] approach\(cartesian\): ([\d.]+) cm, (\d+) samples: "
                      r".*?\|v\|max=([\d.]+) m/s")
FORCE = re.compile(r"force servo: (\w+): ref=([\d.]+)N F\[([\d.]+),([\d.]+)\]N")
GRIP_NOTE = "fruit did not follow the gripper"


def read(path: str) -> dict:
    rows = {"cycles": [], "attempts": [], "carries": [], "approaches": [],
            "force": [], "stats": None, "lines": [], "raw": 0}
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            rows["raw"] += 1
            if line.startswith("[fruit]") or line.startswith("[biarm]"):
                rows["lines"].append(line)
            if m := CYCLE.search(line):
                seg = {}
                for part in m.group(1).split():
                    name, _, value = part.partition("=")
                    seg[name] = float(value.rstrip("s"))
                rows["cycles"].append(seg)
            if m := STATS.search(line):
                rows["stats"] = {
                    "attempts": int(m.group(1)), "successes": int(m.group(2)),
                    "diverted": int(m.group(3)), "rate": int(m.group(4)),
                    "sim": float(m.group(5)), "s_per_attempt": float(m.group(6)),
                }
            if m := ATTEMPT.search(line):
                rows["attempts"].append({
                    "index": int(m.group(1)), "arm": m.group(2),
                    "grasped": m.group(3) == "True",
                    "placed": m.group(4) == "True", "lift": float(m.group(5)),
                    "force": float(m.group(6)), "notes": m.group(7).strip(),
                })
            if m := CARRY.search(line):
                rows["carries"].append({
                    "leg": m.group(1), "cm": float(m.group(2)),
                    "ticks": int(m.group(3)), "vcmd": float(m.group(4)),
                    "acmd": float(m.group(5)), "slip_legacy": float(m.group(6)),
                    "in_hand": float(m.group(7)), "recoveries": int(m.group(8)),
                    "hand_v": float(m.group(9)),
                    "vmax": float(m.group(9)), "amax": float(m.group(10)),
                    "cone": float(m.group(11)), "over": int(m.group(12)),
                })
            if m := APPROACH.search(line):
                rows["approaches"].append({
                    "cm": float(m.group(1)), "samples": int(m.group(2)),
                    "vmax": float(m.group(3)),
                })
            if m := FORCE.search(line):
                rows["force"].append({
                    "arm": m.group(1), "ref": float(m.group(2)),
                    "fmin": float(m.group(3)), "fmax": float(m.group(4)),
                })
    return rows


def block_means(rows: dict) -> dict:
    if not rows["cycles"]:
        return {}
    out = {}
    for name in BLOCKS:
        vals = [c[name] for c in rows["cycles"] if name in c]
        out[name] = statistics.mean(vals) if vals else float("nan")
    out["n"] = len(rows["cycles"])
    return out


def guard(rows: dict) -> dict:
    grip = sum(1 for a in rows["attempts"] if GRIP_NOTE in a["notes"])
    notes = sorted({a["notes"] for a in rows["attempts"] if a["notes"]})
    rescued = sum(1 for c in rows["carries"] if c["recoveries"] > 0)
    fzero = sum(1 for f in rows["force"] if f["fmin"] <= 0.0)
    placed = sum(1 for a in rows["attempts"] if a["placed"])
    grasped = sum(1 for a in rows["attempts"] if a["grasped"])
    # `cnp` = the W8-B carry class: the payload was held and not placed. The
    # note test above is a *closure* test (`tasks.py`: `if not result.grasped:
    # notes.append(...)`), so it also covers the never-held acquisition class;
    # `nograsp` separates them, and `fzero` must equal their sum.
    cnp = sum(1 for a in rows["attempts"] if a["grasped"] and not a["placed"])
    nograsp = sum(1 for a in rows["attempts"] if not a["grasped"])
    return {
        "grip_note": grip, "notes": notes, "rescued": rescued, "fzero": fzero,
        "placed": placed, "grasped": grasped, "cnp": cnp, "nograsp": nograsp,
        "n": len(rows["attempts"]),
    }


def fmt(value: float, width: int = 5, digits: int = 2) -> str:
    if value != value:  # nan
        return " " * width
    return f"{value:{width}.{digits}f}"


def report(battery: str) -> None:
    label, prefix = BATTERIES[battery]
    print("=" * 108)
    print(f"battery {battery}: {label}  (logs/p44/p2/{prefix}_*.log)")
    print("=" * 108)
    header = (
        f"{'arm':<4s} {'placed':>7s} {'cnp':>4s} {'sim':>6s} {'s/att':>6s} "
        + " ".join(f"{b:>6s}" for b in BLOCKS)
        + f" {'cone':>5s} {'>cone':>5s} {'hand>':>5s} {'resc':>4s} {'note':>4s} "
        f"{'nograsp':>7s} {'F0':>3s}"
    )
    print(header)
    print("-" * len(header))
    for arm in ARMS:
        path = os.path.join(OUT, f"{prefix}_{arm}.log")
        rows = read(path)
        if not rows["attempts"] and not rows["cycles"] and rows["stats"] is None:
            print(f"{arm:<4s} {'MISSING':>7s}  ({path})")
            continue
        means = block_means(rows)
        g = guard(rows)
        stats = rows["stats"] or {}
        cones = [c["cone"] for c in rows["carries"]]
        over = sum(1 for c in rows["carries"] if c["over"] > 0)
        hand = sum(1 for c in rows["carries"] if c["hand_v"] > 0.45)
        placed = f"{g['placed']}/{g['n']}"
        print(
            f"{arm:<4s} {placed:>7s} {g['cnp']:>4d} "
            f"{stats.get('sim', float('nan')):6.1f} {stats.get('s_per_attempt', float('nan')):6.2f} "
            + " ".join(fmt(means.get(b, float('nan'))) for b in BLOCKS)
            + f" {(max(cones) if cones else float('nan')):5.2f} {over:>5d} {hand:>5d} "
            f"{g['rescued']:>4d} {g['grip_note']:>4d} {g['nograsp']:>7d} {g['fzero']:>3d}"
        )
        if g["notes"]:
            print(f"       notes: {g['notes']}")
    print()


def byte_identity(record: str, ours: str, title: str, drop: str = "") -> None:
    """C must replay the record's `[fruit]` stream (the default-off proof)."""
    if not (os.path.exists(record) and os.path.exists(ours)):
        print(f"byte-identity ({title}): skipped (record or C log missing)")
        return
    kept = (lambda text: not drop or drop not in text)
    a = [line for line in read(record)["lines"] if kept(line)]
    b = [line for line in read(ours)["lines"] if kept(line)]
    same = sum(1 for x, y in zip(a, b) if x == y)
    print(f"byte-identity ({title}): {os.path.relpath(record, ROOT)}")
    print(f"  reference {len(a)} lines, ours {len(b)} lines, identical prefix {same}")
    if a == b:
        print("  IDENTICAL - the shipped path is byte-unchanged with every cell unset")
    else:
        for index, (x, y) in enumerate(zip(a, b)):
            if x != y:
                print(f"  first difference at line {index + 1}:")
                print(f"    ref : {x.rstrip()}")
                print(f"    ours: {y.rstrip()}")
                break
    print()


def main() -> int:
    wanted = [a for a in sys.argv[1:] if a in BATTERIES] or list(BATTERIES)
    for battery in wanted:
        report(battery)
    if "A" in wanted:
        byte_identity(os.path.join(ROOT, "logs", "p43", "p2", "post_revert_accept_unset.log"),
                      os.path.join(OUT, "accept_s5_C.log"), "C, acceptance seed 5")
    if "C" in wanted:
        byte_identity(os.path.join(ROOT, "logs", "p43", "p2", "d0_pear_A_s5.log"),
                      os.path.join(OUT, "pear_s5_C.log"), "C, pear seed 5 (the [bed] census rows dropped)",
                      drop="[bed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
