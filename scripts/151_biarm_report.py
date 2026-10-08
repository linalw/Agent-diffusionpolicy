"""Summarise one or more bimanual (F2) pick-and-place run logs.

    python3 scripts/151_biarm_report.py logs/biarm/10_rate_biarm_1.log
    python3 scripts/151_biarm_report.py logs/biarm/1*_rate_biarm_*.log

Pure offline reporting over the driver's `[run] attempt ...` lines plus the
`[biarm]` summary/clearance lines and `[stats]`. It prints:

* the per-attempt table (arm, fruit, grade, grasped/placed, lift, force, sim
  span, failure notes), so the failure taxonomy is visible per arm;
* per-arm and pooled attempt/success counts (the dynamic gate's floor is 0.75
  of ten attempts; state the branch/attractor caveat when comparing runs);
* the throughput: simulated-clock span, seconds per attempt, fruit per minute;
* the minimum inter-arm link separation, when `FRUIT_BIARM_TRACE=1` recorded
  one (`[biarm] clearance trace:` lines).
"""

from __future__ import annotations

import re
import sys

PICK = re.compile(
    r"\[run\] attempt (?P<slot>\d+) \((?P<arm>\w+)\): picking (?P<fruit>\w+) "
    r"grade (?P<grade>\w+) into output lane (?P<lane>\d+) at "
    r"\((?P<x>[-\d.]+), (?P<y>[+\-\d.]+)\) sim=(?P<t0>[\d.]+)-(?P<t1>[\d.]+)s"
)
OUTCOME = re.compile(
    r"\[run\] attempt (?P<slot>\d+) \((?P<arm>\w+)\): grasped=(?P<grasped>True|False) "
    r"placed=(?P<placed>True|False) lift=(?P<lift>[+\-\d.]+) m "
    r"force=(?P<force>[\d.]+) N sim=(?P<span>[\d.]+)s notes=(?P<notes>\[.*\])"
)
STATS = re.compile(
    r"\[stats\] attempts=(?P<attempts>\d+) successes=(?P<successes>\d+) "
    r".*?sim=(?P<sim>[\d.]+)s total"
)
BIARM = re.compile(
    r"\[biarm\] (?P<slots>\d+) pipelined slots, (?P<attempts>\d+) attempts, "
    r"(?P<successes>\d+) successes, (?P<span>[\d.]+)s sim span, "
    r"(?P<per_attempt>[\d.]+)s/attempt, (?P<per_success>[\d.]+)s/success, "
    r"(?P<rate>[\d.]+) fruits/min; per arm left=(?P<l_s>\d+)/(?P<l_a>\d+) "
    r"right=(?P<r_s>\d+)/(?P<r_a>\d+)"
)
CLEARANCE = re.compile(
    r"\[biarm\] clearance trace: min link separation (?P<mm>[-\d.]+) mm "
    r"at t=(?P<t>[\d.]+)s \((?P<left>\w+) vs (?P<right>\w+)\), (?P<n>\d+) samples"
)
BIARM_RESULT = re.compile(
    r"\[biarm\] result (?P<arm>\w+) index=(?P<index>\d+) (?P<fruit>\w+) "
    r"grasped=(?P<grasped>True|False) placed=(?P<placed>True|False) "
    r"lift=(?P<lift>[+\-\d.]+) force=(?P<force>[\d.]+) sim=(?P<span>[\d.]+)s "
    r"notes=(?P<notes>\[.*\])"
)


def parse(path: str) -> dict:
    picks: dict[int, dict] = {}
    rows: list[dict] = []
    live_rows: list[dict] = []
    summary: dict | None = None
    clearance: dict | None = None
    stats: dict | None = None
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            found = PICK.search(line)
            if found:
                picks[int(found.group("slot"))] = found.groupdict()
                continue
            found = BIARM_RESULT.search(line)
            if found:
                values = found.groupdict()
                live_rows.append(
                    {
                        "slot": len(live_rows),
                        "arm": values["arm"],
                        "fruit": values["fruit"],
                        "grasped": values["grasped"] == "True",
                        "placed": values["placed"] == "True",
                        "lift": float(values["lift"]),
                        "force": float(values["force"]),
                        "span": float(values["span"]),
                        "notes": values["notes"],
                    }
                )
                continue
            found = OUTCOME.search(line)
            if found:
                values = found.groupdict()
                rows.append(
                    {
                        "slot": int(values["slot"]),
                        "arm": values["arm"],
                        "grasped": values["grasped"] == "True",
                        "placed": values["placed"] == "True",
                        "lift": float(values["lift"]),
                        "force": float(values["force"]),
                        "span": float(values["span"]),
                        "notes": values["notes"],
                    }
                )
                continue
            found = BIARM.search(line)
            if found:
                summary = found.groupdict()
                continue
            found = CLEARANCE.search(line)
            if found:
                values = found.groupdict()
                if clearance is None or float(values["mm"]) < float(clearance["mm"]):
                    clearance = values
                continue
            found = STATS.search(line)
            if found:
                stats = found.groupdict()
    return {
        "picks": picks,
        "rows": rows,
        "live_rows": live_rows,
        "summary": summary,
        "clearance": clearance,
        "stats": stats,
    }


def failure_reason(notes: str) -> str:
    if notes in ("[]", ""):
        return "-"
    # Keep the first reason, stripped of the list/quote punctuation.
    text = notes.strip("[]")
    first = text.split(",")[0].strip().strip("'\"")
    return first or "-"


def report(path: str) -> bool:
    data = parse(path)
    rows = data["rows"]
    live = bool(data["live_rows"])
    if not rows and live:
        # A batch that was killed (or a log read mid-run) still has the
        # per-attempt `[biarm] result` lines.
        rows = data["live_rows"]
    print(f"=== {path}")
    if not rows:
        print("  no attempt result lines found")
        return False
    print(
        f"{'slot':>4} {'arm':<5} {'fruit':<10} {'grade':<5} {'grasp':<5} {'place':<5} "
        f"{'lift':>7} {'force':>6} {'sim':>6}  notes"
    )
    for row in sorted(rows, key=lambda item: item["slot"]):
        pick = data["picks"].get(row["slot"], {})
        fruit = row.get("fruit") or pick.get("fruit", "?")
        grade = pick.get("grade", "?")
        print(
            f"{row['slot']:>4} {row['arm']:<5} {fruit:<10} "
            f"{grade:<5} {str(row['grasped']):<5} {str(row['placed']):<5} "
            f"{row['lift']:>+7.3f} {row['force']:>6.2f} {row['span']:>6.1f}  "
            f"{failure_reason(row['notes'])}"
        )
    per_arm: dict[str, list[int]] = {}
    for row in rows:
        slot = per_arm.setdefault(row["arm"], [0, 0])
        slot[0] += 1
        slot[1] += int(row["grasped"] and row["placed"])
    attempts = len(rows)
    successes = sum(1 for row in rows if row["grasped"] and row["placed"])
    print(
        f"  pooled: {successes}/{attempts} = {successes / attempts * 100:.0f}% "
        f"(gate floor 0.75; branches differ run to run - quote per-arm counts)"
    )
    for arm in sorted(per_arm):
        total, won = per_arm[arm]
        print(f"  {arm:<5}: {won}/{total}")
    if data["summary"]:
        s = data["summary"]
        print(
            f"  throughput: span={float(s['span']):.1f}s sim, "
            f"{float(s['per_attempt']):.1f}s/attempt, "
            f"{float(s['per_success']):.1f}s/success, {float(s['rate']):.2f} fruits/min "
            f"({int(s['slots'])} pipelined slots)"
        )
    elif data["stats"]:
        s = data["stats"]
        print(
            f"  [stats]: attempts={s['attempts']} successes={s['successes']} "
            f"sim={s['sim']}s"
        )
    if data["clearance"]:
        c = data["clearance"]
        print(
            f"  clearance: min link-origin separation {float(c['mm']):.0f} mm at "
            f"t={float(c['t']):.2f}s ({c['left']} vs {c['right']}), {c['n']} samples"
        )
    return True


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    ok = True
    for path in argv:
        ok = report(path) and ok
        print()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
