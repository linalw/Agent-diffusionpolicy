"""Report a fast-loop A/B run directory written by `scripts/127_rtc_ab.sh`.

    python3 scripts/129_rtc_report.py logs/v5b/rtc_ab --runs 3

Reads `E<exec>_<mode>_run<k>.log` (plus optional `_timing.log`) with
``mode in {legacy, rtc, vlash}``; the P4 labels ``E<e>_rtc0`` / ``E<e>_rtc1``
are accepted as legacy / rtc. Prints:

* per-run and pooled success counts per arm, with the per-fruit-class table;
* the paired difference against the same-execute-steps legacy arm per run;
* the wall-clock and control-step latency, the executed-stream step/jerk and
  the decision rate from the timing logs (`FRUIT_RTC_REPORT=1`), if present;
* the trigger/RTC/VLASH configuration from each run's own `[rl] rollout:` line
  (the manifest is keyed by seed and is rewritten by every arm that runs it) and
  the source md5s from the run-labeled manifest snapshots
  (`<run log>.manifest.json`, written by `127_rtc_ab.sh`; older batches fall
  back to the config in the log and do not quote tree digests).

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

RUN_RE = re.compile(r"^(E\d+)_(rtc[01]|legacy|rtc|vlash)_run(\d+)\.log$")
TIMING_RE = re.compile(r"^(E\d+)_(rtc[01]|legacy|rtc|vlash)_timing\.log$")
SUCCESS_RE = re.compile(r"rollout success (\d+)/(\d+)")
EPISODE_RE = re.compile(
    r"\[rl\] episode \d+: (?P<fruit>\S+) d=.*?success=(?P<success>True|False) "
    r".*?ticks=(?P<ticks>\d+) decision=(?P<decision>\d+)"
)
WALL_RE = re.compile(r"run wall end ([\d.]+) duration ([\d.]+)s")
MANIFEST_RE = re.compile(r"\[rl\] manifest: (\S+)")
#: The run's own configuration echo (`110_rl_rollout.py`). It is written by every
#: run and is specific to it, unlike the manifest path: the manifest is keyed by
#: (presentation, ablate, seed), so every arm that runs the same seed rewrites
#: the same file and the report must never read another arm's settings from it.
#: The per-run manifest snapshot (`<run log>.manifest.json`, written next to the
#: log by `127_rtc_ab.sh`) is preferred when present.
ROLLOUT_RE = re.compile(
    r"\[rl\] rollout: .*?ckpt=(?P<ckpt>\S+) execute_steps=(?P<execute_steps>\d+).*?"
    r"rtc=(?P<rtc>on|off)"
    r"(?: schedule=(?P<schedule>\S+) delay=(?P<delay>\d+)"
    r" horizon=(?P<horizon>\d+) guidance=(?P<guidance>\d+))?"
    r"(?: vlash=(?P<vlash>on|off))?"
    r"(?: track=(?P<track>on|off))?"
    r" trigger=(?P<trigger>\S+) trigger_present=(?P<trigger_present>on|off)"
)
RTC_EP_HEAD = re.compile(
    r"\[rtc\]\s+boundaries=(\d+) median=([\d.]+) within=(nan|[\d.]+)"
)
RTC_SUMMARY_RE = re.compile(r"\[rtc\] summary:.*")

#: The `[rtc]` per-episode fields after the head; each may be absent (old logs).
RTC_FIELDS = {
    "switches": (r"switches=(\d+)", int),
    "step_median": (r"step=([\d.]+)", float),
    "jerk_median": (r"jerk=([\d.]+)", float),
    "decisions": (r"decisions=(\d+)", int),
    "rate": (r"rate=([\d.]+)/s", float),
    "policy_ms": (r"policy_ms=([\d.]+)", float),
    "policy_ms_per_step": (r"policy_ms/step=([\d.]+)", float),
    "control_ms": (r"control_ms=([\d.]+)", float),
}


def normalize_mode(mode: str) -> str:
    if mode == "rtc0":
        return "legacy"
    if mode == "rtc1":
        return "rtc"
    return mode


def parse_rollout(text: str) -> dict:
    """The `[rl] rollout:` line of one run: its own RTC/trigger configuration.

    This is the run's authoritative config record. The manifest next to it is
    keyed by (presentation, ablate, seed), so runs of different arms with the
    same seed overwrite each other's manifest - the config must never be read
    from that shared file.
    """
    line = next((ln for ln in text.splitlines() if "[rl] rollout:" in ln), None)
    if not line:
        return {}
    match = ROLLOUT_RE.search(line)
    if not match:
        return {}
    return {key: value for key, value in match.groupdict().items() if value is not None}


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
        "manifest_snapshot": None,
        "rollout": {},
        "sources": {},
        "rtc_settings": None,
        "trigger": None,
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
    result["rollout"] = parse_rollout(text)
    step = result["rollout"].get("execute_steps")
    if step is not None:
        result["execute_steps"] = int(step)
    manifest = MANIFEST_RE.search(text)
    if manifest:
        result["manifest"] = manifest.group(1)
        # Prefer the run-labeled snapshot written next to the log by
        # `127_rtc_ab.sh`; the path printed in the log is shared per seed and
        # may have been rewritten by a later arm (or batch).
        snapshot = os.path.splitext(path)[0] + ".manifest.json"
        manifest_path = snapshot if os.path.exists(snapshot) else manifest.group(1)
        if os.path.exists(snapshot):
            result["manifest_snapshot"] = snapshot
        try:
            with open(manifest_path, encoding="utf-8") as fh:
                payload = json.load(fh)
            result["sources"] = payload.get("sources", {})
            result["rtc_settings"] = payload.get("rtc")
            result["trigger"] = payload.get("trigger")
            result["camera_res"] = str(payload.get("camera_res", ""))
            result["checkpoint_md5"] = str(payload.get("checkpoint_md5", ""))[:8]
        except OSError:
            pass
    for line in text.splitlines():
        head = RTC_EP_HEAD.search(line)
        if not head:
            continue
        row = {
            "boundaries": int(head.group(1)),
            "boundary_median": float(head.group(2)),
            "within_median": float(head.group(3)),
        }
        for key, (pattern, cast) in RTC_FIELDS.items():
            found = re.search(pattern, line)
            if found:
                row[key] = cast(found.group(1))
        result["rtc_episodes"].append(row)
    summary = RTC_SUMMARY_RE.search(text)
    if summary:
        result["rtc_summary"] = summary.group(0)
        rate = re.search(r"decisions/s=([\d.]+)", summary.group(0))
        if rate:
            result["summary_rate"] = float(rate.group(1))
    return result


def median(values):
    values = sorted(values)
    if not values:
        return float("nan")
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return 0.5 * (values[middle - 1] + values[middle])


MODE_RANK = {"legacy": 0, "rtc": 1, "vlash": 2}


def _arm_sort(key):
    arm, mode = key[0], key[1]
    return (int(arm[1:]), MODE_RANK.get(mode, 9))


def _median_field(rows, name):
    values = [r[name] for r in rows if name in r]
    return median(values) if values else float("nan")


def _fmt(value, fmt="%.4f"):
    return "n/a" if value != value else fmt % value


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
            runs[(match.group(1), normalize_mode(match.group(2)),
                  int(match.group(3)))] = parse_log(path)
            continue
        match = TIMING_RE.match(name)
        if match:
            timings[(match.group(1), normalize_mode(match.group(2)))] = parse_log(path)

    if not runs:
        raise SystemExit(f"no E*_<mode>_run*.log under {args.directory}")
    arm_keys = sorted(
        {(arm, mode) for (arm, mode, _run) in runs},
        key=_arm_sort,
    )

    print(f"=== fast-loop A/B: {args.directory} ({args.runs} runs per arm)")
    print()
    print(f"{'arm':<14s} " + " ".join(f"run{i + 1:<4d}" for i in range(args.runs))
          + f"{'pooled':>9s} {'rate':>6s} {'ticks':>7s} {'wall s':>7s}")
    pooled: dict[tuple[str, str], list[int]] = {}
    for arm, mode in arm_keys:
        counts = []
        ticks = []
        walls = []
        for run in range(1, args.runs + 1):
            row = runs.get((arm, mode, run))
            counts.append(f"{row['success']}/{row['total']}" if row else "-")
            if row:
                ticks.append(row["ticks"] / max(row["episodes"], 1))
                if row["duration"]:
                    walls.append(row["duration"])
        ok = sum(runs[(arm, mode, run)]["success"] for run in range(1, args.runs + 1)
                 if (arm, mode, run) in runs)
        n = sum(runs[(arm, mode, run)]["total"] for run in range(1, args.runs + 1)
                if (arm, mode, run) in runs)
        pooled[(arm, mode)] = [ok, n]
        print(f"{arm + '_' + mode:<14s} " + " ".join(f"{c:<8s}" for c in counts)
              + f"{ok:>4d}/{n:<4d} {100.0 * ok / n if n else 0:5.1f}% "
              + f"{median(ticks):7.0f} {median(walls):7.0f}")

    print()
    print("per-class (pooled, successes/total):")
    classes = sorted({
        fruit for row in runs.values() for fruit in row["classes"]
    })
    print(f"{'arm':<16s}" + "".join(f"{fruit:>12s}" for fruit in classes))
    for arm, mode in arm_keys:
        cells = []
        for fruit in classes:
            ok = sum(runs[(arm, mode, run)]["classes"][fruit][0]
                     for run in range(1, args.runs + 1) if (arm, mode, run) in runs)
            n = sum(runs[(arm, mode, run)]["classes"][fruit][1]
                    for run in range(1, args.runs + 1) if (arm, mode, run) in runs)
            cells.append(f"{ok}/{n}")
        print(f"{arm + '_' + mode:<16s}" + "".join(f"{cell:>12s}" for cell in cells))

    print()
    print("configuration per arm (each run's own `[rl] rollout:` line):")
    for arm, mode in arm_keys:
        row = next(
            (runs[(arm, mode, run)] for run in range(1, args.runs + 1)
             if (arm, mode, run) in runs),
            None,
        )
        if not row:
            continue
        cfg = row["rollout"]
        if not cfg:
            # Pre-P4 logs have no rollout echo; fall back to the manifest (which,
            # for those old batches, is the only record available).
            print(f"  {arm}_{mode}: camera={row['camera_res']} "
                  f"ckpt={row['checkpoint_md5']} rtc={row['rtc_settings']} "
                  f"trigger={row['trigger']}")
            continue
        rtc_text = cfg.get("rtc", "?")
        if rtc_text == "on":
            rtc_text = (
                f"on(delay={cfg.get('delay', '?')}, horizon={cfg.get('horizon', '?')},"
                f" schedule={cfg.get('schedule', '?')}, guidance={cfg.get('guidance', '?')})"
            )
        ckpt = cfg.get("ckpt", "?")
        if row["manifest_snapshot"] and row["checkpoint_md5"]:
            ckpt = f"{ckpt} md5={row['checkpoint_md5']}"
        print(f"  {arm}_{mode}: camera={row['camera_res']} ckpt={ckpt} "
              f"exec={cfg.get('execute_steps', row['execute_steps'])} "
              f"rtc={rtc_text} vlash={cfg.get('vlash', '?')} "
              f"track={cfg.get('track', '?')} trigger={cfg.get('trigger', '?')}")

    print()
    snapshots = [row for row in runs.values() if row["manifest_snapshot"]]
    if snapshots:
        print("tree (from each run's run-labeled manifest):")
        source_names = sorted({name for row in snapshots for name in row["sources"]})
        for name in source_names:
            digests = sorted({
                row["sources"].get(name, "")[:8] for row in snapshots
            })
            flag = "" if len(digests) <= 1 else "  <-- DIFFERENT ACROSS RUNS"
            print(f"  {name:<42s} {' '.join(digests)}{flag}")
        if len(snapshots) < len(runs):
            print(f"  note: {len(runs) - len(snapshots)} run(s) have no run-labeled "
                  "manifest snapshot and are not in this table")
    else:
        print("tree: no run-labeled manifest snapshots in this batch; digests are not "
              "quoted.")
        print("      the manifest path printed in each log is keyed by seed and can be "
              "rewritten by")
        print("      another arm or batch - use the batch pin (e.g. tree_before.sha256) "
              "instead.")

    print()
    print("paired vs legacy per run (same seed, same execute_steps):")
    exec_values = sorted({int(arm[1:]) for arm, _ in arm_keys})
    for exec_arm in exec_values:
        for run in range(1, args.runs + 1):
            legacy = runs.get((f"E{exec_arm}", "legacy", run))
            for mode in ("rtc", "vlash"):
                candidate = runs.get((f"E{exec_arm}", mode, run))
                if legacy and candidate:
                    print(
                        f"  E={exec_arm} {mode} run{run}: legacy "
                        f"{legacy['success']}/{legacy['total']}  {mode} "
                        f"{candidate['success']}/{candidate['total']}"
                        f"  delta {candidate['success'] - legacy['success']:+d}"
                    )
        a = pooled.get((f"E{exec_arm}", "legacy"))
        for mode in ("rtc", "vlash"):
            b = pooled.get((f"E{exec_arm}", mode))
            if a and b and a[1] and b[1]:
                print(
                    f"  E={exec_arm} pooled: legacy {a[0]}/{a[1]} "
                    f"({100.0 * a[0] / a[1]:.0f}%)  {mode} {b[0]}/{b[1]} "
                    f"({100.0 * b[0] / b[1]:.0f}%)  "
                    f"delta {100.0 * (b[0] / b[1] - a[0] / a[1]):+.0f} pt"
                )

    if timings:
        print()
        print("timing runs (report on; not part of the rate table):")
        print(f"{'arm':<16s} {'step med':>9s} {'jerk med':>9s} {'bnd med':>8s} "
              f"{'within':>8s} {'dec/s':>6s} {'policy ms':>9s} "
              f"{'ms/step':>8s} {'control ms':>10s}")
        for arm, mode in sorted(timings, key=_arm_sort):
            row = timings[(arm, mode)]
            episodes = row["rtc_episodes"]
            # Decision rate: the run summary is over the policy phase (the
            # right denominator); the per-episode field of old logs is diluted
            # by the scripted primitive's carry ticks.
            rate = row.get("summary_rate")
            if rate is None:
                rate = _median_field(episodes, "rate")
            print(f"{arm + '_' + mode:<16s} "
                  f"{_fmt(_median_field(episodes, 'step_median')):>9s} "
                  f"{_fmt(_median_field(episodes, 'jerk_median')):>9s} "
                  f"{_fmt(_median_field(episodes, 'boundary_median')):>8s} "
                  f"{_fmt(_median_field(episodes, 'within_median')):>8s} "
                  f"{_fmt(rate, '%.1f'):>6s} "
                  f"{_fmt(_median_field(episodes, 'policy_ms'), '%.2f'):>9s} "
                  f"{_fmt(_median_field(episodes, 'policy_ms_per_step'), '%.2f'):>8s} "
                  f"{_fmt(_median_field(episodes, 'control_ms'), '%.2f'):>10s}")
            if row["rtc_summary"]:
                print(f"    {row['rtc_summary']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
