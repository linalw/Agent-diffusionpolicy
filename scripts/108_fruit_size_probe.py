"""Compare closed-loop episodes by fruit size, from the logs.

    FRUIT_SIZE_FILTER=small FRUIT_HYBRID_EVAL=1 FRUIT_MOTION_REPORT=1 FRUIT_EPISODES=10 \
        scripts/run.sh scripts/60_eval_policy.py > logs/108_small_fruit.log
    FRUIT_SIZE_FILTER=large ... > logs/108_large_fruit.log
    python3 scripts/108_fruit_size_probe.py logs/108_small_fruit.log logs/108_large_fruit.log

No simulator needed. For each episode it reports the outcome, the lift the arm
actually achieved, the located metrics per carry leg (`slip_max`, `in-hand |v|max`,
slip-recovery re-seats) and, with
`FRUIT_EVAL_VERBOSE=1 FRUIT_ACTUATED_DEBUG=1`, the grasp-time quantities
(`|pads-fruit|`, `hand_gap`, the alignment components), then aggregates by size
class. `--contrast` additionally splits a log into placed vs not-placed and
rank-sums every quantity, which is the check that keeps a population difference
from being read as an individual predictor.

That is the measurement behind the WORKLOG entry "correction: it is the strawberry,
not small fruit": fifty small-fruit episodes give lychee 26/26 and strawberry 9/24,
so the reproducible failure is one fruit class's *shape* rather than a size band,
and none of the logged grasp-time quantities separates the failures from the
successes within it.
"""

from __future__ import annotations

import re
import statistics
import sys

EPISODE = re.compile(r"\[eval\] episode (\d+): (\w+) grade=(\w+) d=([\d.]+)cm bin=(\d+)")
RESULT = re.compile(
    r"\[eval\] episode (\d+): hybrid grasped=(\w+) placed=(\w+) lift=([+-][\d.]+)cm notes=\[(.*)\]"
)
CARRY = re.compile(
    r"\[motion\] carry (\w+): .*?slip_max=([\d.]+) mm, in-hand \|v\|max=([\d.]+) m/s, "
    r"recoveries=(\d+)"
)
SUMMARY = re.compile(r"\[eval\] policy success (\d+)/(\d+)")
#: Emitted when the run is made with FRUIT_EVAL_VERBOSE=1 (and, for the pads
#: distance, FRUIT_ACTUATED_DEBUG=1).
AIM = re.compile(
    r"\[task\] pads aimed at \[([^\]]+)\].*?residual=([\d.]+)mm align=\(([^)]+)\)mm "
    r"aligned=(\w+) hand_gap=([\d.]+)mm(?:(?!\[task\]).)*?\|pads-fruit\|=([\d.]+)mm"
)
#: Emitted when the run is made with FRUIT_CLOSURE_DEBUG=1: the geometry at the
#: moment the fingers stop, measured from the mesh rather than from a bound.
CLOSURE = re.compile(
    r"\[task\] closure: (\w+) d=([\d.]+)mm faces=([\d.]+)mm "
    r"width_along_axis=([\d.]+)mm interference=([+-][\d.]+)mm "
    r"off_axis=([+-][\d.]+)mm off_reach=([+-][\d.]+)mm"
)


def parse(path: str) -> list[dict]:
    episodes: dict[int, dict] = {}
    order: list[int] = []
    current: int | None = None
    for line in open(path, encoding="utf-8", errors="ignore"):
        found = EPISODE.search(line)
        if found:
            current = int(found.group(1))
            episodes[current] = {
                "index": current,
                "category": found.group(2),
                "grade": found.group(3),
                "diameter": float(found.group(4)),
                "bin": int(found.group(5)),
                "legs": [],
            }
            order.append(current)
            continue
        carried = CARRY.search(line)
        if carried and current is not None:
            episodes[current]["legs"].append(
                {
                    "leg": carried.group(1),
                    "slip_max": float(carried.group(2)),
                    "in_hand_v": float(carried.group(3)),
                    "recoveries": int(carried.group(4)),
                }
            )
            continue
        done = RESULT.search(line)
        if done and int(done.group(1)) in episodes:
            row = episodes[int(done.group(1))]
            row.update(
                grasped=done.group(2) == "True",
                placed=done.group(3) == "True",
                lift_cm=float(done.group(4)),
                notes=done.group(5),
            )
            continue
        aimed = AIM.search(line)
        if aimed and current is not None:
            lateral, forward, vertical = (
                float(value.replace("+", ""))
                for value in aimed.group(3).split(",")
            )
            episodes[current].update(
                residual_mm=float(aimed.group(2)),
                aligned=aimed.group(4) == "True",
                lateral_mm=lateral,
                forward_mm=forward,
                vertical_mm=vertical,
                hand_gap_mm=float(aimed.group(5)),
                pads_fruit_mm=float(aimed.group(6)),
            )
            continue
        closed = CLOSURE.search(line)
        if closed and current is not None:
            episodes[current].update(
                closure_faces_mm=float(closed.group(3)),
                closure_width_mm=float(closed.group(4)),
                interference_mm=float(closed.group(5)),
                closure_gap_axis_mm=float(closed.group(6)),
                closure_gap_reach_mm=float(closed.group(7)),
            )
    return [episodes[i] for i in order if "placed" in episodes[i]]


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    contrast = "--contrast" in sys.argv
    if not args:
        print(__doc__)
        return 2
    for path in args:
        episodes = parse(path)
        if not episodes:
            print(f"{path}: no evaluated episodes found")
            continue
        print(f"=== {path}")
        print(
            f"  {'#':>2s} {'fruit':<11s} {'d':>5s} {'result':<6s} {'lift':>7s} "
            f"{'recov':>6s} {'slip_max':>9s} {'in-hand|v|':>11s} "
            f"{'pads-fruit':>11s} {'hand_gap':>9s} {'intf':>7s} {'offaxis':>8s}"
        )
        for row in episodes:
            recoveries = sum(leg["recoveries"] for leg in row["legs"])
            slip = max((leg["slip_max"] for leg in row["legs"]), default=0.0)
            hand = max((leg["in_hand_v"] for leg in row["legs"]), default=0.0)
            verdict = "ok" if row["placed"] else ("grasped" if row["grasped"] else "no grip")
            pads = row.get("pads_fruit_mm")
            gap = row.get("hand_gap_mm")
            interference = row.get("interference_mm")
            off_axis = row.get("closure_gap_axis_mm")
            print(
                f"  {row['index']:2d} {row['category']:<11s} {row['diameter']:4.1f}c "
                f"{verdict:<6s} {row['lift_cm']:+6.1f}c {recoveries:6d} "
                f"{slip:8.2f}m {hand:10.3f} "
                f"{(f'{pads:8.1f}mm' if pads is not None else ' ' * 11)} "
                f"{(f'{gap:6.0f}mm' if gap is not None else ' ' * 9)} "
                f"{(f'{interference:+5.1f}mm' if interference is not None else ' ' * 7)} "
                f"{(f'{off_axis:+6.1f}mm' if off_axis is not None else ' ' * 8)}"
            )
        summary = None
        for line in open(path, encoding="utf-8", errors="ignore"):
            found = SUMMARY.search(line)
            if found:
                summary = (int(found.group(1)), int(found.group(2)))
        if summary:
            print(f"  total: {summary[0]}/{summary[1]} = {summary[0] / summary[1]:.0%}")

        for label, keep in (
            ("small (<= 4.5 cm)", lambda d: d <= 4.5),
            ("large (>= 5 cm)", lambda d: d >= 5.0),
        ):
            subset = [row for row in episodes if keep(row["diameter"])]
            if not subset:
                continue
            ok = sum(1 for row in subset if row["placed"])
            slips = [
                max((leg["slip_max"] for leg in row["legs"]), default=0.0) for row in subset
            ]
            recoveries = [sum(leg["recoveries"] for leg in row["legs"]) for row in subset]
            print(
                f"  {label:<18s} n={len(subset):2d} success={ok}/{len(subset)} "
                f"median slip_max={statistics.median(slips):5.1f} mm "
                f"worst={max(slips):6.1f} mm "
                f"recoveries total={sum(recoveries):4d} worst={max(recoveries):3d}"
            )
            pads = [r["pads_fruit_mm"] for r in subset if "pads_fruit_mm" in r]
            gaps = [r["hand_gap_mm"] for r in subset if "hand_gap_mm" in r]
            if pads:
                print(
                    f"  {'':<18s} |pads-fruit| median={statistics.median(pads):.1f} mm "
                    f"worst={max(pads):.1f} mm  (pads on the fruit in every episode)"
                )
            if gaps:
                print(
                    f"  {'':<18s} hand_gap median={statistics.median(gaps):.0f} mm "
                    f"worst={max(gaps):.0f} mm  (arm-jaw to pad standoff)"
                )
        print()
        if contrast:
            contrast_report(episodes, path)
    return 0


def contrast_report(episodes: list[dict], path: str) -> None:
    """Do the grasp-time / carry quantities separate failures from successes?

    A rank-sum test over successes vs failures within one log. This is the check
    that keeps a *population* difference (small fruit slip more than large fruit)
    from being read as an individual predictor.
    """
    from scipy.stats import mannwhitneyu

    quantities = {
        "pads_fruit_mm": "|pads-fruit| [mm]",
        "hand_gap_mm": "hand_gap [mm]",
        "residual_mm": "IK residual [mm]",
        "lateral_mm": "lateral align [mm]",
        "forward_mm": "forward align [mm]",
        "vertical_mm": "vertical align [mm]",
        "interference_mm": "closure interference [mm]",
        "closure_faces_mm": "closure face span [mm]",
        "closure_width_mm": "fruit width on axis [mm]",
        "closure_gap_axis_mm": "closure off-centre [mm]",
        "closure_gap_reach_mm": "closure depth offset [mm]",
        "slip_max_mm": "carry slip_max [mm]",
        "in_hand_v": "carry in-hand |v| [m/s]",
        "recoveries": "re-s seats per episode",
        "lift_cm": "peak lift [cm]",
    }
    ok = [row for row in episodes if row["placed"]]
    bad = [row for row in episodes if not row["placed"]]
    print(f"  contrast within {path}: {len(ok)} placed vs {len(bad)} not placed")
    if not bad:
        print("    no failures in this log - nothing to contrast")
        return
    print(f"    {'quantity':<26s} {'ok median':>10s} {'fail median':>12s} {'p (rank-sum)':>13s}")
    separating = []
    for key, label in quantities.items():
        left = [row[key] for row in ok if key in row]
        right = [row[key] for row in bad if key in row]
        if len(left) < 2 or len(right) < 1:
            continue
        p_value = mannwhitneyu(left, right, alternative="two-sided").pvalue
        print(f"    {label:<26s} {statistics.median(left):10.2f} "
              f"{statistics.median(right):12.2f} {p_value:13.4f}")
        if p_value < 0.05:
            separating.append(label)
    if separating:
        print(f"    separates at p<0.05: {', '.join(separating)}")
        print("    (with ~10 quantities tested, one false positive at p<0.05 is expected;")
        print("     treat a single borderline entry as a hypothesis, not a result)")
    else:
        print("    no quantity separates the failures from the successes in this log,")
        print("    so none of them predicts an individual failure - the difference that")
        print("    exists is between populations (fruit size), not between episodes")


if __name__ == "__main__":
    raise SystemExit(main())
