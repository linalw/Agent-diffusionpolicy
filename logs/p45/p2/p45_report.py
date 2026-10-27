"""P45 phase 2 report: the mass x speed battery, per arm and per battery.

    python3 logs/p45/p2/p45_report.py            # every battery present
    python3 logs/p45/p2/p45_report.py A          # the acceptance, seed 5
    python3 logs/p45/p2/p45_report.py B          # the pear battery, seed 5

Prints exactly the PREREG_DRAFT §3 endpoints, per arm and arm-vs-control:

* **E1** `placed` / `cnp` / no-grasp from the `[run] attempt` rows, and the
  `[stats]` `s/attempt`.
* **E2 the fling** - the `release trace:` row's peak `|v|`, **restricted to
  in-hand payloads**: the attempt's `place trace` must read `on_belt=True` or
  `release_bottom >= 0`. The unrestricted peak is printed beside it, because the
  free-fall rows (4.7-4.8 m/s from the place height) are what the restriction
  removes and a cell that *converts* losses would otherwise read as an
  improvement (`MASS_CENSUS.md` §4.3).
* **E3 the walk** - `[carry]` `clean_slip_max` (p50/max, arm-vs-control only) and
  the `force_min == 0` leg count.
* **E4 the cycle** - `s/attempt`, the `[cycle]` block means, and **every leg's
  tick counts verbatim** against C (an exact null, not a tolerance: a moved
  count is an implementation defect, not physics).
* **E5** the failure notes, so a new `fruit did not follow the gripper` row or a
  new reason is visible.

Also prints the arm's `mass_scale=` banner and the one-shot mass/inertia
read-back, so a log that lost its knob is caught rather than read as a null.

Nothing here writes outside stdout.
"""

from __future__ import annotations

import os
import re
import statistics
import sys

ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
)
OUT = os.path.join(ROOT, "logs", "p45", "p2")

BATTERIES = {
    "A": ("the acceptance, seed 5", "accept_s5"),
    "B": ("the pear battery, seed 5", "pear_s5"),
}
ARMS = ["C", "M50", "M25", "M50S", "M25S"]
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
RELEASE = re.compile(r"release trace: (\d+) ticks, peak \|v\|=([\d.]+) m/s at t=(\d+) "
                     r"\(([\w ]+), gap=([\d.]+)mm\).*?events=(\d+)")
PLACE = re.compile(r"place trace (\w+): release_bottom=([-\d.]+)mm .*?on_belt=(\w+)")
CARRY_DIAG = re.compile(
    r"\[carry\] (\w+) (\w+): ticks=(\d+)/(\d+) clean_slip_max=([\d.]+)mm "
    r"in-hand_vmax=([\d.]+) onset_row=(-?\d+|None) force@onset=([\w/.-]+)N "
    r"sep@onset=([\w/.-]+)mm contacts@onset=(\d+|None) min_contacts=(\d+) "
    r"force_min=(-?[\d.]+)N loss_row=(-?\d+|None) sep@loss=([\w/.-]+)mm "
    r"sep_end=([\d.]+)mm guard=(\d+) events=(\d+) holds=(\d+)"
)
MASS_BANNER = re.compile(r"\[physics\] FRUIT_MASS_SCALE=([\d.]+): mass_scale=([\d.]+)")
READBACK = re.compile(r"\[physics\] mass readback \(P45\): (.*)")
TARGET = re.compile(r"\[task\] target (\w+) \(grade (\w+), ([\d.]+) cm\) with (\w+) arm")
GRIP_NOTE = "fruit did not follow the gripper"


def read(path: str) -> dict:
    rows = {"cycles": [], "attempts": [], "carries": [], "stats": None,
            "releases": [], "places": [], "carry_diag": [], "lines": [],
            "mass_banner": None, "readback": None, "segments": []}
    if not os.path.exists(path):
        return rows
    segment: dict | None = None
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("[fruit]"):
                rows["lines"].append(line)
            if m := TARGET.search(line):
                segment = {"class": m.group(1), "grade": m.group(2),
                           "diameter": float(m.group(3)), "arm": m.group(4),
                           "carry": [], "cycle": None, "release": None,
                           "place": None}
                rows["segments"].append(segment)
            if m := CYCLE.search(line):
                seg = {}
                for part in m.group(1).split():
                    name, _, value = part.partition("=")
                    seg[name] = float(value.rstrip("s"))
                rows["cycles"].append(seg)
                if segment is not None:
                    segment["cycle"] = seg
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
                    "acmd": float(m.group(5)),
                    "in_hand": float(m.group(7)), "recoveries": int(m.group(8)),
                    "hand_v": float(m.group(9)),
                    "cone": float(m.group(11)), "over": int(m.group(12)),
                })
            if m := RELEASE.search(line):
                rows["releases"].append({
                    "ticks": int(m.group(1)), "peak": float(m.group(2)),
                    "phase": m.group(4).strip(), "events": int(m.group(6)),
                })
                if segment is not None:
                    segment["release"] = rows["releases"][-1]
            if m := PLACE.search(line):
                rows["places"].append({
                    "side": m.group(1), "bottom": float(m.group(2)),
                    "on_belt": m.group(3) == "True",
                })
                if segment is not None:
                    segment["place"] = rows["places"][-1]
            if m := CARRY_DIAG.search(line):
                row = {
                    "side": m.group(1), "leg": m.group(2),
                    "ticks": int(m.group(3)),
                    "clean_slip_max": float(m.group(5)),
                    "in_hand_vmax": float(m.group(6)),
                    "force_min": float(m.group(12)),
                    "loss_row": None if m.group(13) == "None" else int(m.group(13)),
                }
                rows["carry_diag"].append(row)
                if segment is not None:
                    segment["carry"].append(row)
            if m := MASS_BANNER.search(line):
                rows["mass_banner"] = m.group(1)
            elif m := READBACK.search(line):
                rows["readback"] = m.group(1)
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
    placed = sum(1 for a in rows["attempts"] if a["placed"])
    cnp = sum(1 for a in rows["attempts"] if a["grasped"] and not a["placed"])
    nograsp = sum(1 for a in rows["attempts"] if not a["grasped"])
    return {"grip_note": grip, "notes": notes, "placed": placed, "cnp": cnp,
            "nograsp": nograsp, "n": len(rows["attempts"])}


def in_hand_peaks(rows: dict) -> list[float]:
    """The release peaks of attempts whose payload was still in hand.

    The release trace and the place trace are emitted once per attempt, in that
    order (the release block ends before the landing report), so pairing them by
    index is exact. Restricted exactly as the PREREG says: `on_belt=True` **or**
    `release_bottom >= 0`.
    """
    n = min(len(rows["releases"]), len(rows["places"]))
    return [
        rows["releases"][i]["peak"] for i in range(n)
        if rows["places"][i]["on_belt"] or rows["places"][i]["bottom"] >= 0.0
    ]


def matched_tick_null(base: dict, rows: dict) -> tuple[int, int, list[str]]:
    """E4's exact null on the attempts that are the *same leg geometry*.

    A leg is tick-clocked by its profile, so a mass change cannot move its
    duration **when the leg is the same leg** - and the leg is only the same leg
    when the arm, the class and (for the place) the lane match. A mass cell that
    changes the transport changes *which* fruit is presented, and then the place
    distance (and therefore its tick count) legitimately moves with it: that is a
    moved branch, not a timing leak. So the null is evaluated per attempt index
    on the (class, arm) matches, and the mismatches are reported beside it.
    Returns `(identical, compared, detail)`.
    """
    same = compared = 0
    detail: list[str] = []
    for index, (a, b) in enumerate(zip(base.get("segments", []), rows.get("segments", []))):
        if (a["class"], a["arm"]) != (b["class"], b["arm"]):
            continue
        compared += 1
        ka = [(d["leg"], d["ticks"]) for d in a["carry"]]
        kb = [(d["leg"], d["ticks"]) for d in b["carry"]]
        if ka == kb:
            same += 1
        else:
            detail.append(f"attempt {index + 1} ({a['class']}/{a['arm']}): C {ka} vs {kb}")
    return same, compared, detail


def selection_signature(rows: dict) -> str:
    """The ordered (class, arm) sequence - confound #6 of the PREREG."""
    return " ".join(
        f"{s['class']}/{s['arm'][0]}" for s in rows.get("segments", [])
    )


def profile_params(rows: dict) -> dict[str, list[tuple[float, float]]]:
    """Per leg, the **commanded** profile caps actually used: `(|v|cmd, |a|cmd)`.

    This is E4's real implementation-defect test. A leg's *duration* also depends
    on its **distance**, and a mass change moves where the fruit is picked, so a
    tick count can move for a legitimate reason; the profile caps cannot. If an
    arm's `(v, a)` set equals C's on every leg, no mass value reached a control
    path - the tick movement is geometry.
    """
    out: dict[str, list[tuple[float, float]]] = {}
    for leg in rows["carries"]:
        out.setdefault(leg["leg"], []).append((leg["vcmd"], leg["acmd"]))
    return {leg: sorted(set(vals)) for leg, vals in out.items()}


def leg_distances(rows: dict) -> dict[str, list[float]]:
    """Per leg, the carried distance in cm - the term that explains a tick move."""
    out: dict[str, list[float]] = {}
    for leg in rows["carries"]:
        out.setdefault(leg["leg"], []).append(leg["cm"])
    return out


def class_split(rows: dict) -> dict[str, tuple[int, int]]:
    """Per class: `(attempts, carried-not-placed)` - PREREG confound #5.

    The pool's mass span is 1:16 inside one scenario and the selection is
    grade-then-position, so an arm's class mix can differ from the control's
    simply because the branch differs. Any per-class read has to be visible
    beside the count (the P1/P2 `200_composition_audit.py` lesson).
    """
    out: dict[str, list[int]] = {}
    for seg, att in zip(rows.get("segments", []), rows["attempts"]):
        slot = out.setdefault(seg["class"], [0, 0])
        slot[0] += 1
        if att["grasped"] and not att["placed"]:
            slot[1] += 1
    return {name: (n, c) for name, (n, c) in out.items()}


def standardised_cnp(base: dict, rows: dict) -> tuple[float, float, int]:
    """`cnp` standardised to the control's class mix, over the **common** classes.

    Returns `(C rate, arm rate, common attempts)`. Classes an arm never attempted
    cannot be standardised (there is no denominator), so the read is over the
    intersection and the size of that intersection is reported: a standardised
    number over 3 of 8 classes is not a standardisation of the battery.
    """
    a = class_split(base)
    b = class_split(rows)
    common = [name for name in a if name in b]
    weight = sum(a[name][0] for name in common)
    if weight == 0:
        return float("nan"), float("nan"), 0
    base_rate = sum(a[name][1] for name in common) / weight
    arm_rate = sum(
        a[name][0] * (b[name][1] / b[name][0]) for name in common if b[name][0]
    ) / weight
    return base_rate, arm_rate, weight


def f(value: float, width: int = 6, digits: int = 2) -> str:
    if value != value:
        return " " * width
    return f"{value:{width}.{digits}f}"


def report(battery: str) -> None:
    label, prefix = BATTERIES[battery]
    print("=" * 116)
    print(f"battery {battery}: {label}   (logs/p45/p2/{prefix}_*.log)")
    print("=" * 116)
    base_ticks: dict[str, list[int]] = {}
    base_fling = base_place = base_satt = None
    base_rows: dict = {}
    for arm in ARMS:
        path = os.path.join(OUT, f"{prefix}_{arm}.log")
        rows = read(path)
        if not rows["lines"]:
            print(f"{arm:<5s} MISSING ({os.path.relpath(path, ROOT)})")
            continue
        means = block_means(rows)
        g = guard(rows)
        stats = rows["stats"] or {}
        peaks = in_hand_peaks(rows)
        all_peaks = [r["peak"] for r in rows["releases"]]
        fmin0 = [d for d in rows["carry_diag"] if d["force_min"] <= 0.0]
        slips = sorted(d["clean_slip_max"] for d in rows["carry_diag"])
        escapes = sum(1 for s in slips if s > 50.0)
        ticks: dict[str, list[int]] = {}
        for leg in rows["carry_diag"]:
            ticks.setdefault(leg["leg"], []).append(leg["ticks"])
        if arm == "C":
            base_ticks = ticks
            base_fling = max(peaks) if peaks else float("nan")
            base_place = g["placed"]
            base_satt = stats.get("s_per_attempt", float("nan"))
            base_rows = rows

        print()
        print(f"--- {arm}   banner mass_scale={rows['mass_banner'] or 'unset'}"
              f"   legs={stats.get('attempts', 0)} attempts")
        if rows["readback"]:
            print(f"  readback: {rows['readback']}")
        fling = f"  E2 fling (in hand, n={len(peaks)})"
        if peaks:
            delta = "" if base_fling is None or base_fling != base_fling else \
                f"  delta={max(peaks) - base_fling:+.3f}  ratio={max(peaks) / base_fling:.2f}x"
            print(f"{fling}: max={max(peaks):.3f} median={statistics.median(peaks):.3f} "
                  f"min={min(peaks):.3f}{delta}")
        else:
            print(f"{fling}: none (no payload was in hand at a release)")
        print(f"     unrestricted peaks ({len(all_peaks)}): "
              + " ".join(f"{p:.3f}" for p in all_peaks))
        print(f"  E1 placed {g['placed']}/{g['n']} (C {base_place})  cnp {g['cnp']}  "
              f"no-grasp {g['nograsp']}  s/att {stats.get('s_per_attempt', float('nan')):.2f} "
              f"(C {base_satt:.2f})  sim {stats.get('sim', float('nan')):.1f}s  "
              f"diverted {stats.get('diverted', 0)}")
        print("  E4 blocks: " + " ".join(
            f"{k}={means.get(k, float('nan')):.2f}" for k in BLOCKS if k != "total"))
        if arm != "C" and base_rows:
            same, compared, detail = matched_tick_null(base_rows, rows)
            print(f"  E4 tick null (same class+arm attempts): {same}/{compared} "
                  f"identical leg-tick tuples")
            for line in detail:
                print(f"     MOVED {line}")
            params = profile_params(rows)
            base_params = profile_params(base_rows)
            print("  E4 profile family (commanded |v| per leg, C vs arm): " + "; ".join(
                f"{leg} C{min(v for v, _ in base_params[leg]):.3f}-"
                f"{max(v for v, _ in base_params[leg]):.3f} vs "
                f"{min(v for v, _ in params[leg]):.3f}-"
                f"{max(v for v, _ in params[leg]):.3f}"
                for leg in sorted(params) if leg in base_params))
            ceilings = {
                leg: max(v for v, _ in params[leg]) - max(v for v, _ in base_params[leg])
                for leg in params if leg in base_params
            }
            worst = max(abs(d) for d in ceilings.values()) if ceilings else 0.0
            if worst <= 0.005:
                print("     -> the same profile family as C (every leg's commanded "
                      f"ceiling within 5 mm/s): no control path sees the mass")
            else:
                print("     -> commanded ceiling moved by "
                      + ", ".join(f"{leg} {d:+.3f}" for leg, d in ceilings.items())
                      + " (expected for the FRUIT_SPEED_ALL cell: lift 0.30->0.36, "
                        "place 0.35->0.52)")
            base_cm = leg_distances(base_rows)
            cm = leg_distances(rows)
            print("  E4 leg distances cm (the tick explainer): " + "; ".join(
                f"{leg} C{min(base_cm[leg]):.0f}-{max(base_cm[leg]):.0f} "
                f"vs {min(cm[leg]):.0f}-{max(cm[leg]):.0f}"
                for leg in sorted(cm) if leg in base_cm))
        print(f"  selection: {selection_signature(rows)}")
        tick_bits = []
        for leg in ("grasp_lift", "place0", "place1"):
            vals = ticks.get(leg, [])
            if not vals:
                continue
            bit = f"{leg} [{' '.join(str(v) for v in vals)}]"
            if base_ticks and leg in base_ticks:
                ref = base_ticks[leg]
                same = vals == ref
                bit += f" {'SAME' if same else 'MOVED vs C ' + str(ref)}"
            tick_bits.append(bit)
        print("  E4 leg ticks: " + "; ".join(tick_bits))
        print(f"  E3 walk: clean_slip_max p50 "
              f"{statistics.median(slips) if slips else float('nan'):.1f}mm "
              f"max {max(slips) if slips else float('nan'):.1f}mm (n={len(slips)} legs); "
              f"escapes (>50mm) {escapes}/{len(slips)}; "
              f"force_min==0 on {len(fmin0)}/{len(rows['carry_diag'])} legs "
              f"{[d['leg'] for d in fmin0]}")
        cones = [c["cone"] for c in rows["carries"]]
        over = sum(1 for c in rows["carries"] if c["over"] > 0)
        print(f"  report: cone max {(max(cones) if cones else float('nan')):.2f}x "
              f"({over} legs over budget); in-hand |v|max > 0.45 on "
              f"{sum(1 for c in rows['carries'] if c['in_hand'] > 0.45)} legs; "
              f"rescued {sum(1 for c in rows['carries'] if c['recoveries'] > 0)}")
        print(f"  E5 notes: grip-note {g['grip_note']}  {g['notes'] if g['notes'] else ''}")
        split = class_split(rows)
        print("  per class (attempts/cnp): " + " ".join(
            f"{name} {n}/{c}" for name, (n, c) in sorted(split.items())))
        if arm != "C" and base_rows:
            base_rate, arm_rate, weight = standardised_cnp(base_rows, rows)
            print(f"  class-standardised cnp over the {weight} common attempts: "
                  f"C {base_rate:.3f} vs {arm_rate:.3f} "
                  f"({(arm_rate - base_rate) * 10:+.1f} attempts of 10)")
    print()


def summary(battery: str) -> None:
    """One compact table per battery - the numbers the results doc quotes."""
    label, prefix = BATTERIES[battery]
    print("-" * 116)
    print(f"SUMMARY {battery}: {label}")
    header = (f"{'arm':<6s}{'mass':>7s}{'placed':>8s}{'cnp':>5s}{'s/att':>7s}"
              f"{'fling_max':>10s}{'fling_med':>10s}{'n':>4s}"
              f"{'slip_p50':>9s}{'esc>50':>8s}{'F0':>7s}{'grip':>5s}")
    print(header)
    print("-" * len(header))
    for arm in ARMS:
        rows = read(os.path.join(OUT, f"{prefix}_{arm}.log"))
        if not rows["lines"]:
            continue
        g = guard(rows)
        stats = rows["stats"] or {}
        peaks = in_hand_peaks(rows)
        slips = sorted(d["clean_slip_max"] for d in rows["carry_diag"])
        fmin0 = sum(1 for d in rows["carry_diag"] if d["force_min"] <= 0.0)
        mass = rows["mass_banner"] or "1.0"
        placed = "{}/{}".format(g["placed"], g["n"])
        fling_max = max(peaks) if peaks else float("nan")
        fling_med = statistics.median(peaks) if peaks else float("nan")
        slip_p50 = statistics.median(slips) if slips else float("nan")
        escapes = "{}/{}".format(sum(1 for s in slips if s > 50.0), len(slips))
        fzero = "{}/{}".format(fmin0, len(rows["carry_diag"]))
        satt = stats.get("s_per_attempt", float("nan"))
        print(f"{arm:<6s}{mass:>7s}{placed:>8s}{g['cnp']:>5d}{satt:7.2f}"
              f"{fling_max:10.3f}{fling_med:10.3f}{len(peaks):>4d}"
              f"{slip_p50:9.1f}{escapes:>8s}{fzero:>7s}{g['grip_note']:>5d}")
    print()


def byte_identity(record: str, ours: str, title: str, drop: str = "") -> None:
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
        print("  IDENTICAL - the shipped path is byte-unchanged with the knob unset")
    else:
        for index, (x, y) in enumerate(zip(a, b)):
            if x != y:
                print(f"  first difference at line {index + 1}:")
                print(f"    ref : {x.rstrip()}")
                print(f"    ours: {y.rstrip()}")
                break
        else:
            print(f"  prefix identical; ours has {len(b) - len(a)} extra/removed tail lines")
    print()


def main() -> int:
    wanted = [a for a in sys.argv[1:] if a in BATTERIES] or list(BATTERIES)
    for battery in wanted:
        report(battery)
        summary(battery)
    if "A" in wanted:
        # The P44 amend F battery ran the same scenario with the same five
        # instruments and no mass knob, so it is the byte-identity record.
        byte_identity(os.path.join(ROOT, "logs", "p44", "p2", "amend_F_C.log"),
                      os.path.join(OUT, "accept_s5_C.log"),
                      "C vs the P44 amend-F record, acceptance seed 5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
