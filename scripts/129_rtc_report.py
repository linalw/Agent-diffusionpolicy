"""Report an RTC A/B run directory written by `scripts/127_rtc_ab.sh`.

    python3 scripts/129_rtc_report.py logs/rtc/ab --runs 3

Reads `E<exec>_rtc<0|1>_run<k>.log` (plus optional `_timing.log`) and prints:

* per-run and pooled success counts per arm, with the per-fruit-class table;
* the paired RTC - legacy difference per execute-steps, per run (same seed);
* the wall-clock and control-step latency from the timing logs, if present;
* the executed-stream boundary jump medians from the report lines, if present.

One run is one sample: the verdict lines only compare pooled counts and the
per-run paired signs, never a single run.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
from collections import defaultdict

RUN_RE = re.compile(r"^(E\d+)_rtc([01])_run(\d+)\.log$")
TIMING_RE = re.compile(r"^(E\d+)_rtc([01])_timing\.log$")
SUCCESS_RE = re.compile(r"rollout success (\d+)/(\d+)")
EPISODE_RE = re.compile(
    r"\[rl\] episode \d+: (?P<fruit>\S+) d=.*?success=(?P<success>True|False) "
    r".*?ticks=(?P<ticks>\d+) decision=(?P<decision>\d+)"
)
WALL_RE = re.compile(r"run wall end ([\d.]+) duration ([\d.]+)s")
MANIFEST_RE = re.compile(r"\[rl\] manifest: (\S+)")
RTC_EP_RE = re.compile(
    r"\[rtc\]\s+boundaries=(\d+) median=([\d.]+) within=([\d.]+) "
    r"switches=(\d+) policy_ms=([\d.]+) control_ms=([\d.]+)"
)
RTC_SUMMARY_RE = re.compile(r"\[rtc\] summary:.*")


def parse_log(path: str) -> dict:
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    result = {
        "success": None,
        "total": None,
        "classes": defaultdict(lambda: [0, 0]),
        "episodes": 0,
        "ticks": 0,
        "decision": 0,
        "duration": None,
        "rtc_episodes": [],
        "rtc_summary": None,
        "manifest": None,
        "sources": {},
        "rtc_settings": None,
        "camera_res": "",
        "checkpoint_md5": "",
        "execute_steps": None,
    }
    for match in SUCCESS_RE.finditer(text):
        result["success"] = int(match.group(1))
        result["total"] = int(match.group(2))
    for match in EPISODE_RE.finditer(text):
        fruit = match.group("fruit")
        result["classes"][fruit][1] += 1
        if match.group("success") == "True":
            result["classes"][fruit][0] += 1
        result["episodes"] += 1
        result["ticks"] += int(match.group("ticks"))
        result["decision"] += int(match.group("decision"))
    wall = WALL_RE.search(text)
    if wall:
        result["duration"] = float(wall.group(2))
    step = re.search(r"execute_steps=(\d+)", text)
    if step:
        result["execute_steps"] = int(step.group(1))
    manifest = MANIFEST_RE.search(text)
    if manifest:
        result["manifest"] = manifest.group(1)
        try:
            with open(manifest.group(1), encoding="utf-8") as fh:
                payload = json.load(fh)
            result["sources"] = payload.get("sources", {})
            result["rtc_settings"] = payload.get("rtc")
            result["camera_res"] = str(payload.get("camera_res", ""))
            result["checkpoint_md5"] = str(payload.get("checkpoint_md5", ""))[:8]
        except OSError:
            pass
    for match in RTC_EP_RE.finditer(text):
        result["rtc_episodes"].append(
            {
                "boundaries": int(match.group(1)),
                "boundary_median": float(match.group(2)),
                "within_median": float(match.group(3)),
                "switches": int(match.group(4)),
                "policy_ms": float(match.group(5)),
                "control_ms": float(match.group(6)),
            }
        )
    summary = RTC_SUMMARY_RE.search(text)
    if summary:
        result["rtc_summary"] = summary.group(0)
    return result


def median(values):
    values = sorted(values)
    if not values:
        return float("nan")
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return 0.5 * (values[middle - 1] + values[middle])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    runs: dict[tuple[str, str, int], dict] = {}
    timings: dict[tuple[str, str], dict] = {}
    for path in sorted(glob.glob(os.path.join(args.directory, "*.log"))):
        name = os.path.basename(path)
        match = RUN_RE.match(name)
        if match:
            runs[(match.group(1), match.group(2), int(match.group(3)))] = parse_log(path)
            continue
        match = TIMING_RE.match(name)
        if match:
            timings[(match.group(1), match.group(2))] = parse_log(path)

    if not runs:
        raise SystemExit(f"no E*_rtc*_run*.log under {args.directory}")
    arm_keys = sorted(
        {(arm, rtc) for (arm, rtc, _run) in runs},
        key=lambda key: (int(key[0][1:]), int(key[1])),
    )
    exec_values = sorted({int(arm[1:]) for arm, _ in arm_keys})

    print(f"=== RTC A/B: {args.directory} ({args.runs} runs per arm)")
    print()
    print(f"{'arm':<10s} " + " ".join(f"run{i + 1:<4d}" for i in range(args.runs))
          + f"{'pooled':>9s} {'rate':>6s} {'ticks':>7s} {'wall s':>7s}")
    pooled: dict[tuple[str, str], list[int]] = {}
    for arm, rtc in arm_keys:
        counts = []
        ticks = []
        walls = []
        for run in range(1, args.runs + 1):
            row = runs.get((arm, rtc, run))
            counts.append(f"{row['success']}/{row['total']}" if row else "-")
            if row:
                ticks.append(row["ticks"] / max(row["episodes"], 1))
                if row["duration"]:
                    walls.append(row["duration"])
        ok = sum(runs[(arm, rtc, run)]["success"] for run in range(1, args.runs + 1)
                 if (arm, rtc, run) in runs)
        n = sum(runs[(arm, rtc, run)]["total"] for run in range(1, args.runs + 1)
                if (arm, rtc, run) in runs)
        pooled[(arm, rtc)] = [ok, n]
        print(f"{arm}_rtc{rtc:<4s} " + " ".join(f"{c:<8s}" for c in counts)
              + f"{ok:>4d}/{n:<4d} {100.0 * ok / n if n else 0:5.1f}% "
              + f"{median(ticks):7.0f} {median(walls):7.0f}")

    print()
    print("per-class (pooled, successes/total):")
    classes = sorted({
        fruit for row in runs.values() for fruit in row["classes"]
    })
    header = f"{'arm':<12s}" + "".join(f"{fruit:>12s}" for fruit in classes)
    print(header)
    for arm, rtc in arm_keys:
        cells = []
        for fruit in classes:
            ok = sum(runs[(arm, rtc, run)]["classes"][fruit][0]
                     for run in range(1, args.runs + 1) if (arm, rtc, run) in runs)
            n = sum(runs[(arm, rtc, run)]["classes"][fruit][1]
                    for run in range(1, args.runs + 1) if (arm, rtc, run) in runs)
            cells.append(f"{ok}/{n}")
        print(f"{arm}_rtc{rtc:<6s}" + "".join(f"{cell:>12s}" for cell in cells))

    print()
    print("configuration and tree (from each run's manifest):")
    source_names = sorted({name for row in runs.values() for name in row["sources"]})
    for name in source_names:
        digests = sorted({
            row["sources"].get(name, "")[:8] for row in runs.values() if row["sources"]
        })
        flag = "" if len(digests) <= 1 else "  <-- DIFFERENT ACROSS RUNS"
        print(f"  {name:<42s} {' '.join(digests)}{flag}")
    for arm, rtc in arm_keys:
        row = next(
            (runs[(arm, rtc, run)] for run in range(1, args.runs + 1)
             if (arm, rtc, run) in runs),
            None,
        )
        if row:
            print(
                f"  {arm}_rtc{rtc}: camera={row['camera_res']} "
                f"ckpt={row['checkpoint_md5']} rtc={row['rtc_settings']}"
            )

    print()
    print("paired RTC - legacy per run (same seed, same execute_steps):")
    for exec_arm in exec_values:
        for run in range(1, args.runs + 1):
            legacy = runs.get((f"E{exec_arm}", "0", run))
            rtc = runs.get((f"E{exec_arm}", "1", run))
            if legacy and rtc:
                print(
                    f"  E={exec_arm} run{run}: legacy {legacy['success']}/{legacy['total']}"
                    f"  rtc {rtc['success']}/{rtc['total']}"
                    f"  delta {rtc['success'] - legacy['success']:+d}"
                )
        a = pooled.get((f"E{exec_arm}", "0"))
        b = pooled.get((f"E{exec_arm}", "1"))
        if a and b and a[1] and b[1]:
            print(
                f"  E={exec_arm} pooled: legacy {a[0]}/{a[1]} "
                f"({100.0 * a[0] / a[1]:.0f}%)  rtc {b[0]}/{b[1]} "
                f"({100.0 * b[0] / b[1]:.0f}%)  "
                f"delta {100.0 * (b[0] / b[1] - a[0] / a[1]):+.0f} pt"
            )

    if timings:
        print()
        print("timing runs (report on; not part of the rate table):")
        print(f"{'arm':<12s} {'control_ms med':>14s} {'policy_ms med':>14s} "
              f"{'boundary med':>13s} {'within med':>11s}")
        for arm, rtc in sorted(timings, key=lambda k: (int(k[0][1:]), int(k[1]))):
            row = timings[(arm, rtc)]
            controls = [e["control_ms"] for e in row["rtc_episodes"]]
            policies = [e["policy_ms"] for e in row["rtc_episodes"]]
            boundaries = [e["boundary_median"] for e in row["rtc_episodes"]]
            within = [e["within_median"] for e in row["rtc_episodes"]
                      if e["within_median"] == e["within_median"]]
            print(f"{arm}_rtc{rtc:<4s} {median(controls):14.1f} "
                  f"{median(policies):14.1f} {median(boundaries):13.4f} "
                  f"{median(within):11.4f}")
        for (arm, rtc), row in sorted(timings.items()):
            if row["rtc_summary"]:
                print(f"  {arm}_rtc{rtc}: {row['rtc_summary']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
