"""Report a policy A/B from the logs `140_policy_ab.sh` writes.

    python3 scripts/141_policy_ab_report.py logs/policy_ab --runs 3

Prints, per arm, each run's episode table, then the per-arm success rate overall and
for the fruit classes that matter, the median and range across runs, and a verdict
based on whether the two arms' rates overlap. Aggregates the *per-episode outcome*,
which is the statistic that survives the harness's run-to-run variation (see the
WORKLOG: the same six episodes came out 6/6 twice with peak lifts differing by 1 cm).
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import statistics

EPISODE = re.compile(r"\[eval\] episode (\d+): (\w+) grade=(\w+) d=([\d.]+)cm")
RESULT = re.compile(
    r"\[eval\] episode (\d+): hybrid grasped=(\w+) placed=(\w+) lift=([+-][\d.]+)cm"
)
SUMMARY = re.compile(r"\[eval\] policy success (\d+)/(\d+)")


def parse(path: str) -> list[dict]:
    rows: dict[int, dict] = {}
    current = None
    for line in open(path, encoding="utf-8", errors="ignore"):
        found = EPISODE.search(line)
        if found:
            current = int(found.group(1))
            rows[current] = {
                "index": current,
                "category": found.group(2),
                "diameter": float(found.group(4)),
            }
            continue
        done = RESULT.search(line)
        if done and int(done.group(1)) in rows:
            row = rows[int(done.group(1))]
            row["grasped"] = done.group(2) == "True"
            row["placed"] = done.group(3) == "True"
            row["lift"] = float(done.group(4))
    return [rows[i] for i in sorted(rows) if "placed" in rows[i]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--classes", default="strawberry,lychee")
    args = parser.parse_args()

    arms: dict[str, list[tuple[str, list[dict]]]] = {}
    for path in sorted(glob.glob(os.path.join(args.directory, "*.log"))):
        stem = os.path.basename(path)[:-4]
        arm = stem.split("_")[0]
        arms.setdefault(arm, []).append((stem, parse(path)))
    if not arms:
        print(f"no logs in {args.directory}")
        return 2

    classes = [c.strip() for c in args.classes.split(",") if c.strip()]
    summary: dict[str, dict[str, list[float]]] = {}
    for arm, runs in sorted(arms.items()):
        print(f"=== arm {arm}")
        for name, rows in runs:
            line = "  ".join(
                f"{r['index']}:{r['category'][:4]}/{r['diameter']:.1f}/"
                f"{'ok' if r['placed'] else 'FAIL'}" for r in rows
            )
            ok = sum(1 for r in rows if r["placed"])
            print(f"  {name:<10s} {ok}/{len(rows)}  {line}")
        overall = [
            (sum(1 for r in rows if r["placed"]) / len(rows)) if rows else 0.0
            for _, rows in runs
        ]
        summary[arm] = {"overall": overall}
        for category in classes:
            rates = []
            for _, rows in runs:
                subset = [r for r in rows if r["category"] == category]
                if subset:
                    rates.append(sum(1 for r in subset if r["placed"]) / len(subset))
            summary[arm][category] = rates

    print()
    header = f"{'arm':<6s} {'runs':>5s} {'overall median':>15s} {'range':>12s}"
    for category in classes:
        header += f" {category + ' median':>18s}"
    print(header)
    for arm, data in summary.items():
        overall = data["overall"]
        line = (
            f"{arm:<6s} {len(overall):5d} "
            f"{statistics.median(overall):15.0%} "
            f"{min(overall):5.0%}-{max(overall):<6.0%}"
        )
        for category in classes:
            rates = data.get(category) or [0.0]
            line += f" {statistics.median(rates):18.0%}"
        print(line)

    if len(summary) == 2:
        arms_sorted = sorted(summary)
        a, b = arms_sorted
        print()
        overlap = True
        for key in ["overall"] + classes:
            left = summary[a].get(key) or []
            right = summary[b].get(key) or []
            if not left or not right:
                continue
            lo_a, hi_a = min(left), max(left)
            lo_b, hi_b = min(right), max(right)
            separated = hi_a < lo_b or hi_b < lo_a
            print(
                f"  {key:<11s} {a}: {statistics.median(left):.0%} "
                f"[{lo_a:.0%}, {hi_a:.0%}]   {b}: {statistics.median(right):.0%} "
                f"[{lo_b:.0%}, {hi_b:.0%}]   {'SEPARATED' if separated else 'overlapping'}"
            )
            overlap = overlap and not separated
        print()
        if overlap:
            print("verdict: the arms' rates overlap, so this sample does not separate")
            print("         them - run more episodes or more runs per arm")
        else:
            print("verdict: the arms' rates are separated on at least one statistic")
            print("         above; quote the statistic and the range, not a single run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
