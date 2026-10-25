"""P38 phase 1: the delivered-x distribution, the tail, and the S3-class census.

    python3 logs/p38/drift_census.py            # -> stdout (logs/p38/drift_census.txt)
    python3 logs/p38/drift_census.py --self-test

Read-only, offline. Nothing here touches the simulator, `src/`, `configs/` or a
shipped default; every number comes from a committed log.

**What is measured.** The supply draws each fruit's across-the-belt position
from `FRUIT_SUPPLY_X_MIN..MAX` (0.20-0.36 m, `fruits.py`), but the *delivered*
x is what the station sees, and the trigger's lateral gate admits only
`|x - jaw_x| <= FRUIT_POLICY_TRIGGER_LATERAL` (0.16 m against the station's
0.333 m jaw line, `trigger.py`) - i.e. only `x >= 0.173`. Three populations:

* **`[1]` the station-zone x, scripted lines** - one sample per attempt from
  the primitive's `wait step=0 fruit_x=` row (`tasks.py:7775` prints steps
  0-5 at the wait loop's start). This is the fruit the attempt actually got.
* **`[2]` the station-zone x, direct lines** - one sample per episode from the
  `[park] call ... x=` census rows (P35/P36/P37 batches only; the census is
  off elsewhere). `x` is the band target's live position, and the `along=`
  field shows it is constant while the fruit crosses the band.
* **`[3]` the on-belt frames** - the `[supply] lateral x:` summary line each
  `171_supply_probe` run writes (min/p10/p50/p90/max over every on-belt frame),
  quoted per scenario; it is the *design* reading (all along positions pooled,
  no selection), not the station-zone one.

**The comparison baseline** is the spawn band itself: the draw is
`rng.uniform(x_min, x_max)` in `FruitSpawner.respawn` (`fruits.py:1089`), so
under no drift the delivered x is uniform on the band. `[1]`/`[2]` report a
two-sided Kolmogorov-Smirnov distance to that uniform and the tail counts
`x < 0.173` (systematically unfirable), `x < 0.20` (below the spawn floor),
`x > 0.36` (above the spawn ceiling) and `x > 0.39` (the reach band's upper
edge). A drift that is a *shift* moves the median; a drift that is a *tail*
leaves the median and stretches one end - the two are reported separately
because they have different levers (`PREREG.md`).

**`[4]` the S3-class census.** Every direct-loop log that prints
`[rl] episode <n>: ... success=` is an episode. A `timeout: no grasp within
1500 ticks` note with no `[acq]` row in the same episode is a **never-fired**
attempt: the scripted primitive never ran, so no fruit was ever closed on. The
census counts those per batch next to the fire-path (`[acq]`) attempts, and
names the target's x where the park census recorded it. `x-edge refuse` rows
(the R2.3/R7-A reach-cliff guard) are counted too; the guard is default off, so
they only exist in the guard runs.

**Buckets** come from the log's own provenance line, never from the file name:

* `[supply] scatter ... lateral x=LO-HI` -> the spawn band,
  plus `patch=on` / `wave=on` / `rows=` (the bed) for the schedule;
* `[biarm] two-line scheduler` -> the two-line path (its own stations);
* otherwise the single-arm shared-station line.

Reach-anywhere runs (`logs/r10/`, `logs/r11/`) are **excluded** from `[1]`:
that selector chooses by minimum fruit travel to a clipping-into-the-band
intercept (`tasks.py:_reach_anywhere_select`), so its selection is correlated
with x and it is not the shipped selection population. Their exclusion is
printed with the file list.
"""

from __future__ import annotations

import glob
import os
import re
import statistics
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: Directories that hold .npz recordings (2.4 GB) rather than text logs.
SKIP_DIRS = ("record_probe_a",)
#: The reach-anywhere selector (R10-A/R11-A, opt-in) - excluded from [1] (see
#: the module docstring). It is not a shipped default and its selection is
#: x-correlated.
EXCLUDE_PREFIXES = ("logs/r10/", "logs/r11/")

#: The trigger's lateral gate and the station jaw line it is measured from
#: (`trigger.py` `TriggerSettings.lateral` = 0.16, the direct env's
#: `_trigger_station` x = 0.333). A fruit is firable only when both hold, so the
#: delivered-x admission floor is `jaw_x - lateral` = 0.173.
TRIGGER_LATERAL = 0.16
STATION_JAW_X = 0.333
ADMIT_X = STATION_JAW_X - TRIGGER_LATERAL
#: The measured top-down reach band (`scripts/174_station_reach.py`,
#: `logs/v3/60_station_reach_edge.log`): ~6 mm residual x = 0.18-0.39, the
#: cliff at x >= 0.42.
REACH_LO = 0.18
REACH_HI = 0.39
#: `fruits.SUPPLY_X_MIN/MAX` - the shipped spawn band, the no-drift baseline.
SPAWN_LO = 0.20
SPAWN_HI = 0.36

RE_PROVENANCE = re.compile(
    r"(?P<head>\[supply\] scatter .*?)lateral x=(?P<lo>[0-9.]+)-(?P<hi>[0-9.]+) m"
    r"(?P<rest>.*)$"
)
RE_TWOLINE = re.compile(r"\[biarm\] two-line scheduler:")
RE_BIARM = re.compile(r"\[biarm\]")
RE_WAIT0 = re.compile(r"\[task\]   wait step=0 fruit_y=(?P<y>[-+0-9.]+) fruit_x=(?P<x>[-+0-9.]+)")
RE_TARGET = re.compile(r"\[task\] target (?P<cat>\w+) \(grade (?P<grade>\w), (?P<d>[0-9.]+) cm\)")
RE_PARK = re.compile(r"\[park\] call ep=(?P<ep>\d+) n=(?P<n>\d+) along=(?P<along>[-+0-9.]+) x=(?P<x>[-+0-9.]+)")
RE_EPISODE_END = re.compile(
    r"\[rl\] episode (?P<ep>\d+): (?P<cat>\w+) d=[0-9.]+cm bin=(?P<bin>\d) "
    r"arm=(?P<arm>\w+) success=(?P<success>\w+) grasped=(?P<grasped>\w+) "
    r"placed=(?P<placed>\w+) ticks=(?P<ticks>\d+) decision=(?P<decision>\d+)"
)
RE_TRIGGER = re.compile(r"\[rl\] trigger=(?P<mode>\w+) .*?lateral=(?P<lat>[0-9.]+)")
RE_NOTES = re.compile(r"notes=\[(?P<notes>.*)\] presentation=")
#: The intercept note's lateral offset `dx = fruit_x - station_x` [cm]; the
#: station x it is measured from is `_trigger_station` (the jaw centre at the
#: reset), so `fruit_x - dx` recovers it per episode.
RE_TRIGGER_DX = re.compile(r"intercept trigger \(dy=[-+0-9.]+cm, dx=(?P<dx>[-+0-9.]+)cm")
RE_SUPPLY_LATERAL = re.compile(
    r"\[supply\] lateral x: min (?P<min>[-+0-9.]+) p10 (?P<p10>[-+0-9.]+) "
    r"p50 (?P<p50>[-+0-9.]+) p90 (?P<p90>[-+0-9.]+) max (?P<max>[-+0-9.]+) m"
)


# --------------------------------------------------------------------------- #
# statistics
# --------------------------------------------------------------------------- #
def pct(values: list[float], q: float) -> float:
    """Linear-interpolated percentile (numpy's default, no numpy here)."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def ks_uniform(values: list[float], lo: float, hi: float) -> float:
    """Two-sided KS distance to `uniform(lo, hi)` (the spawn band baseline)."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    n = len(ordered)
    d = 0.0
    for i, v in enumerate(ordered):
        cdf = min(max((v - lo) / (hi - lo), 0.0), 1.0)
        d = max(d, abs(cdf - i / n), abs(cdf - (i + 1) / n))
    return d


def describe(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "sd": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "p1": pct(values, 1),
        "p5": pct(values, 5),
        "p10": pct(values, 10),
        "p50": pct(values, 50),
        "p90": pct(values, 90),
        "p95": pct(values, 95),
        "p99": pct(values, 99),
        "max": max(values),
        "lt_admit": sum(1 for v in values if v < ADMIT_X),
        "lt_spawn_lo": sum(1 for v in values if v < SPAWN_LO),
        "gt_spawn_hi": sum(1 for v in values if v > SPAWN_HI),
        "gt_reach_hi": sum(1 for v in values if v > REACH_HI),
        "ks": ks_uniform(values, SPAWN_LO, SPAWN_HI),
    }


def fmt_row(label: str, s: dict) -> str:
    if not s.get("n"):
        return f"{label:<34s} n=0"
    return (
        f"{label:<34s} n={s['n']:4d}  mean {s['mean']:.3f} sd {s['sd']:.3f}  "
        f"min {s['min']:.3f} p1 {s['p1']:.3f} p5 {s['p5']:.3f} p10 {s['p10']:.3f} "
        f"p50 {s['p50']:.3f} p90 {s['p90']:.3f} p95 {s['p95']:.3f} p99 {s['p99']:.3f} "
        f"max {s['max']:.3f}  "
        f"<{ADMIT_X:.3f} {s['lt_admit']}  <{SPAWN_LO:.2f} {s['lt_spawn_lo']}  "
        f">{SPAWN_HI:.2f} {s['gt_spawn_hi']}  >{REACH_HI:.2f} {s['gt_reach_hi']}  "
        f"KS {s['ks']:.3f}"
    )


# --------------------------------------------------------------------------- #
# the log walk
# --------------------------------------------------------------------------- #
def candidates() -> dict[str, list[str]]:
    """Files containing any of the patterns this report reads (one grep pass)."""
    pattern = (
        r"\[task\]   wait step=0 |\[park\] call |\[supply\] lateral x: "
        r"|\[rl\] episode "
    )
    found: dict[str, list[str]] = {"wait": [], "park": [], "supply": [], "episode": []}
    try:
        out = subprocess.run(
            ["grep", "-rlE", "--include=*.log", pattern, "logs"],
            cwd=ROOT, capture_output=True, text=True, timeout=900,
        ).stdout
    except Exception as exc:  # noqa: BLE001 - fall back to a plain walk
        print(f"[census] grep shortlist failed ({exc}); walking every .log")
        out = "\n".join(
            os.path.relpath(path, ROOT)
            for path in glob.glob(os.path.join(ROOT, "logs", "**", "*.log"), recursive=True)
        )
    for line in out.splitlines():
        rel = line.strip()
        if not rel or any(part in rel for part in SKIP_DIRS):
            continue
        if "\x00" in rel:
            continue
        found["all"] = found.get("all", []) + [rel]
    return found


def bucket_of(path: str, provenance: tuple[float, float] | None,
              twoline: bool, biarm: bool) -> str:
    """Scenario bucket from the log's own provenance + scheduler banner."""
    lo, hi = provenance[:2] if provenance else (SPAWN_LO, SPAWN_HI)
    band = f"{lo:.2f}-{hi:.2f}"
    sched = "scatter"
    # the schedule flags can sit either side of the band on the provenance line
    rest = provenance[2] if provenance and len(provenance) > 2 else ""
    if "rows=" in rest:
        sched = "bed"
    elif "patch=on" in rest:
        sched = "patch"
    elif "wave=on" in rest:
        sched = "wave"
    arm = "twoline" if twoline else ("biarm" if biarm else "single")
    return f"{arm}/{sched}/x{band}"


def read_file(path: str) -> dict:
    """One streaming pass: provenance, banner, wait rows, park rows, episodes."""
    out = {
        "provenance": None,
        "twoline": False,
        "biarm": False,
        "waits": [],
        "park": {},
        "episodes": [],
        "trigger": None,
        "x_refuse": 0,
        "refuse_x": [],
        "lateral": None,
        "trigger_dx": {},
    }
    last_target: str | None = None
    episode_no: int | None = None
    try:
        with open(os.path.join(ROOT, path), "r", errors="replace") as handle:
            for line in handle:
                if "[supply] scatter" in line and out["provenance"] is None:
                    m = RE_PROVENANCE.search(line)
                    if m:
                        out["provenance"] = (
                            float(m.group("lo")),
                            float(m.group("hi")),
                            m.group("head") + m.group("rest"),
                        )
                if "[biarm]" in line:
                    out["biarm"] = True
                    if RE_TWOLINE.search(line):
                        out["twoline"] = True
                elif "[rl] episode " in line and "success=" in line:
                    m = RE_EPISODE_END.search(line)
                    if m:
                        notes = RE_NOTES.search(line)
                        dxm = RE_TRIGGER_DX.search(line)
                        if dxm:
                            out["trigger_dx"][int(m.group("ep"))] = (
                                float(dxm.group("dx")) / 100.0
                            )
                        out["episodes"].append(
                            {
                                "ep": int(m.group("ep")),
                                "cat": m.group("cat"),
                                "arm": m.group("arm"),
                                "success": m.group("success") == "True",
                                "grasped": m.group("grasped") == "True",
                                "placed": m.group("placed") == "True",
                                "ticks": int(m.group("ticks")),
                                "decision": int(m.group("decision")),
                                "timeout": "timeout: no grasp within" in line,
                                "notes": notes.group("notes") if notes else "",
                            }
                        )
                elif "[rl] episode " in line and " grade=" in line:
                    m = re.search(r"\[rl\] episode (\d+):", line)
                    if m:
                        episode_no = int(m.group(1))
                elif "intercept trigger (dy=" in line:
                    m = RE_TRIGGER_DX.search(line)
                    if m and episode_no is not None:
                        out["trigger_dx"][episode_no] = float(m.group("dx")) / 100.0
                elif "[task] target " in line:
                    m = RE_TARGET.search(line)
                    if m:
                        last_target = m.group("cat")
                elif "[task]   wait step=0 " in line:
                    m = RE_WAIT0.search(line)
                    if m:
                        out["waits"].append(
                            (float(m.group("y")), float(m.group("x")), last_target)
                        )
                elif "[park] call" in line:
                    m = RE_PARK.search(line)
                    if m:
                        ep = int(m.group("ep"))
                        out["park"].setdefault(ep, []).append(
                            (float(m.group("along")), float(m.group("x")))
                        )
                elif "[rl] trigger=" in line and out["trigger"] is None:
                    m = RE_TRIGGER.search(line)
                    if m:
                        out["trigger"] = (m.group("mode"), float(m.group("lat")))
                if "x-edge refuse: fruit x=" in line:
                    out["x_refuse"] += 1
                    m = re.search(r"x-edge refuse: fruit x=([-+0-9.]+)", line)
                    if m:
                        out["refuse_x"].append(float(m.group(1)))
                if out["lateral"] is None and "[supply] lateral x:" in line:
                    m = RE_SUPPLY_LATERAL.search(line)
                    if m:
                        out["lateral"] = (
                            float(m.group("min")), float(m.group("p10")),
                            float(m.group("p50")), float(m.group("p90")),
                            float(m.group("max")),
                        )
    except OSError as exc:
        print(f"[census] skip {path}: {exc}")
    return out


def main() -> int:
    print("=" * 100)
    print("P38 phase 1 - the delivered-x distribution and the S3-class census")
    print("read-only analysis of committed logs; no simulator, no src/ change")
    print("=" * 100)
    print(
        f"baselines: spawn band [{SPAWN_LO:.2f}, {SPAWN_HI:.2f}] (fruits.SUPPLY_X_MIN/MAX); "
        f"trigger admission x >= {ADMIT_X:.3f} (jaw {STATION_JAW_X:.3f} - lateral "
        f"{TRIGGER_LATERAL:.2f}); top-down reach band [{REACH_LO:.2f}, {REACH_HI:.2f}] "
        f"(174/60, 6 mm)"
    )

    files = candidates().get("all", [])
    print(f"\nshortlisted {len(files)} logs (grep for the four row patterns)")
    scripted: dict[str, list] = {}
    direct: dict[str, list] = {}
    excluded: list[str] = []
    park_along_spread: list[float] = []
    episode_files: list[tuple[str, dict]] = []
    supply_runs: list[tuple[str, dict]] = []
    refuse_total = 0
    refuse_files: list[tuple[str, int, list]] = []
    park_cache: dict[str, dict] = {}
    off_belt = 0
    unclassified = 0

    for path in sorted(files):
        if any(path.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
            data = read_file(path)
            if data["waits"]:
                excluded.append(f"{path}  ({len(data['waits'])} wait rows)")
                continue
        data = read_file(path)
        provenance = data["provenance"]
        if provenance is None and (data["waits"] or data["park"]):
            # no [supply] provenance line: a pre-v9 fixed-line run (spawn within
            # +/-5 mm of the belt centre, delivered 0.308-0.394 - WORKLOG "The
            # fixed line, measured"), or a run whose banner predates the field.
            # Its x cannot be compared to the spawn band, so it is skipped.
            unclassified += 1
            if data["episodes"]:
                episode_files.append((path, data))
            continue
        bucket = bucket_of(path, provenance, data["twoline"], data["biarm"])
        if data["episodes"] and (data["park"] or data["trigger"]):
            # the direct interface: its own label, whatever the provenance says
            bucket = bucket.replace("single/", "direct/", 1)

        if data["waits"]:
            for along, x, cat in data["waits"]:
                if not (0.05 <= x <= 0.60):
                    # the primitive's row prints whatever sample the driver
                    # selected; x outside the main belt is a placed / output-line
                    # body (a selector escape), not a delivered-x sample
                    off_belt += 1
                    continue
                scripted.setdefault(bucket, []).append(
                    {"x": x, "along": along, "cat": cat, "path": path}
                )
        if data["park"]:
            # one sample per episode: the median of its band calls (x is
            # constant across the band; the spread is reported once, below)
            cats = {e["ep"]: e["cat"] for e in data["episodes"]}
            arms = {e["ep"]: e["arm"] for e in data["episodes"]}
            for ep, rows in data["park"].items():
                vals = [x for _, x in rows]
                park_along_spread.append(max(v for v, _ in rows) - min(v for v, _ in rows))
                direct.setdefault(bucket, []).append(
                    {
                        "x": statistics.median(vals),
                        "along": min(v for v, _ in rows),
                        "cat": cats.get(ep),
                        "arm": arms.get(ep),
                        "path": path,
                        "ep": ep,
                    }
                )
            park_cache[path] = data
        if data["episodes"]:
            episode_files.append((path, data))
        if data["lateral"]:
            supply_runs.append((path, data))
        if data["x_refuse"]:
            refuse_total += data["x_refuse"]
            refuse_files.append((path, data["x_refuse"], data["refuse_x"]))

    # ---- [1] the scripted station-zone x ---------------------------------- #
    print("\n" + "-" * 100)
    print("[1] the station-zone delivered x - scripted lines, one sample per attempt")
    print("    source: [task]   wait step=0 fruit_x= (the primitive's wait loop, tasks.py:7775)")
    print("    DEDUPED: bit-identical replays of one attempt share its (x, along) to 4 dp,")
    print("    so the distribution is over unique attempts; `raw` counts the replays too.")
    print("-" * 100)
    for bucket in sorted(scripted):
        rows = scripted[bucket]
        unique = {}
        for row in rows:
            unique.setdefault((round(row["x"], 4), round(row["along"], 4)), row)
        values = [row["x"] for row in unique.values()]
        s = describe(values)
        print(fmt_row(bucket, s) + f"  raw {len(rows)}")
        below = [row for row in unique.values() if row["x"] < ADMIT_X]
        if below:
            print(f"    attempts below the admission floor: {len(below)}")
            for row in sorted(below, key=lambda r: r["x"]):
                print(
                    f"      x={row['x']:.3f} along={row['along']:+.3f} "
                    f"{row['cat'] or '?'} {row['path']}"
                )
        below_floor = [row for row in unique.values() if row["x"] < SPAWN_LO]
        if below_floor:
            cats = {}
            for row in below_floor:
                cats[row["cat"] or "?"] = cats.get(row["cat"] or "?", 0) + 1
            print(
                f"    attempts below the spawn floor {SPAWN_LO:.2f}: {len(below_floor)}"
                f" ({len(below_floor) / len(values) * 100:.2f}%), by class {cats}"
            )
    if off_belt:
        print(f"\n    excluded {off_belt} rows with x outside the main belt (selector escapes)")
    if unclassified:
        print(
            f"\n    skipped {unclassified} logs with no [supply] provenance line "
            "(pre-v9 fixed-line / banner-less): their spawn x is not the band"
        )
    if excluded:
        print("\n    excluded (the reach-anywhere selector, x-correlated - see the docstring):")
        for line in excluded:
            print(f"      {line}")

    # ---- [2] the direct station-zone x ------------------------------------ #
    print("\n" + "-" * 100)
    print("[2] the station-zone delivered x - direct lines, one sample per episode")
    print("    source: [park] call ... x= (the band census; P35/P36/P37 batches only)")
    print("-" * 100)
    for bucket in sorted(direct):
        rows = direct[bucket]
        values = [row["x"] for row in rows]
        s = describe(values)
        print(fmt_row(bucket, s))
        below = [row for row in rows if row["x"] < ADMIT_X]
        if below:
            print(f"    episodes below the admission floor: {len(below)}")
            for row in sorted(below, key=lambda r: r["x"]):
                print(
                    f"      x={row['x']:.3f} ep={row['ep']} {row['cat'] or '?'} {row['path']}"
                )
        lo = [row for row in rows if row["x"] < SPAWN_LO]
        if lo:
            cats = {}
            for row in lo:
                cats[row["cat"] or "?"] = cats.get(row["cat"] or "?", 0) + 1
            print(
                f"    episodes below the spawn floor {SPAWN_LO:.2f}: {len(lo)}"
                f" ({len(lo) / len(values) * 100:.2f}%), by class {cats}"
            )
    if park_along_spread:
        print(
            f"\n    within-episode `along` span of the band census: "
            f"median {statistics.median(park_along_spread):.3f} m "
            f"(max {max(park_along_spread):.3f}) - x is constant over it"
        )

    # ---- [3] the on-belt frames ------------------------------------------- #
    print("\n" + "-" * 100)
    print("[3] the on-belt frames - the [supply] lateral x: summary each probe run writes")
    print("    (all along positions pooled, no selection: the DESIGN reading)")
    print("-" * 100)
    for path, data in sorted(supply_runs, key=lambda item: item[0]):
        lat = data["lateral"]
        lo = data["provenance"][0] if data["provenance"] else float("nan")
        hi = data["provenance"][1] if data["provenance"] else float("nan")
        sched = bucket_of(path, data["provenance"], False, False).split("/")[1]
        print(
            f"  {path:<46s} {sched:<8s} band {lo:.2f}-{hi:.2f}  "
            f"min {lat[0]:+.3f} p10 {lat[1]:+.3f} p50 {lat[2]:+.3f} "
            f"p90 {lat[3]:+.3f} max {lat[4]:+.3f}"
        )
    if not supply_runs:
        print("  none")

    # ---- [4] the S3-class census ------------------------------------------ #
    print("\n" + "-" * 100)
    print("[4] the S3-class census - direct-loop episodes, never-fired attempts")
    print("    a timeout with no [acq] row in the same episode = the primitive never ran")
    print("-" * 100)
    armed = [(p, d) for p, d in episode_files if d["trigger"] and d["trigger"][0] != "off"]
    legacy = [(p, d) for p, d in episode_files if not (d["trigger"] and d["trigger"][0] != "off")]
    print(
        f"  {len(episode_files)} direct-loop logs: {len(armed)} with the arrival trigger, "
        f"{len(legacy)} pre-trigger / trigger-off"
    )
    #: The lateral gate selects the population: 0.06 is the pre-W4 calibration
    #: (the documented no-fire class on the x = 0.20-0.36 band), 0.16 the
    #: shipped W4 value, 0.20 the W4 sweep's widened cell. A log with any
    #: `x-edge refuse` row ran the opt-in reach-cliff guard, whose refusal is a
    #: *high*-x class and absent from the shipped default: split it out.
    by_gate: dict[tuple[float, bool], dict[str, dict]] = {}
    nofire_rows: list[tuple[str, dict]] = []
    for path, data in armed:
        eps = data["episodes"]
        gate = round(data["trigger"][1], 2)
        guard = data["x_refuse"] > 0
        group = os.path.dirname(path) or "logs"
        g = by_gate.setdefault((gate, guard), {}).setdefault(
            group, {"eps": 0, "ok": 0, "cnp": 0, "to": 0}
        )
        g["eps"] += len(eps)
        g["ok"] += sum(1 for e in eps if e["placed"])
        g["cnp"] += sum(1 for e in eps if e["grasped"] and not e["placed"])
        g["to"] += sum(1 for e in eps if e["timeout"])
        for e in eps:
            if e["timeout"]:
                nofire_rows.append((path, e))
    print("\n  per batch, grouped by the trigger's lateral gate and the reach guard:")
    for gate, guard in sorted(by_gate):
        label = (
            " <- the shipped interface (W4 gate, guard off)"
            if abs(gate - 0.16) < 1e-9 and not guard
            else (
                " <- pre-W4 (the refused outer band)"
                if abs(gate - 0.06) < 1e-9
                else (" <- guard on (the high-x cliff refusal, opt-in)" if guard else "")
            )
        )
        tot = {"eps": 0, "ok": 0, "cnp": 0, "to": 0}
        print(f"\n    lateral {gate:.2f}, x-edge guard {'on' if guard else 'off'}{label}")
        for group in sorted(by_gate[(gate, guard)]):
            g = by_gate[(gate, guard)][group]
            for key in tot:
                tot[key] += g[key]
            print(
                f"      {group:<46s} eps {g['eps']:4d}  placed {g['ok']:4d}  "
                f"carried-not-placed {g['cnp']:4d}  never-fired {g['to']:3d} = "
                f"{g['to'] / max(1, g['eps']) * 100:4.1f}%"
            )
        print(
            f"      {'TOTAL':<46s} eps {tot['eps']:4d}  placed {tot['ok']:4d}  "
            f"carried-not-placed {tot['cnp']:4d}  never-fired {tot['to']:3d} = "
            f"{tot['to'] / max(1, tot['eps']) * 100:4.1f}%"
        )
    print("\n  every never-fired episode (the S3 class), with its notes and target x:")
    if not nofire_rows:
        print("    none")
    for path, e in sorted(nofire_rows, key=lambda item: item[0]):
        rows = (park_cache.get(path) or {}).get("park", {}).get(e["ep"], [])
        xs = [x for _, x in rows]
        extra = (
            f" target x={statistics.median(xs):.3f} (band calls {len(xs)})"
            if xs
            else " target x not recorded (no park census in this batch)"
        )
        notes = e.get("notes", "")
        print(
            f"    {path} ep {e['ep']}: {e['cat']} arm={e['arm']} ticks={e['ticks']} "
            f"decision={e['decision']}{extra}"
        )
        if notes and notes != "timeout: no grasp within 1500 ticks":
            print(f"      other notes: [{notes}]")
    if legacy:
        legacy_eps = sum(len(d["episodes"]) for _, d in legacy)
        legacy_to = sum(sum(1 for e in d["episodes"] if e["timeout"]) for _, d in legacy)
        print(
            f"\n  pre-trigger / trigger-off logs (the historical no-fire class, NOT the "
            f"current interface): {len(legacy)} logs, {legacy_eps} episodes, "
            f"{legacy_to} timeouts ({legacy_to / max(1, legacy_eps) * 100:.1f}%) - "
            "these are the runs before the arrival trigger, where the policy gate was "
            "the dominant no-fire mechanism, not the lateral tail"
        )
        legacy_batches: dict[str, list[int]] = {}
        for path, d in legacy:
            key = os.path.dirname(path) or "logs"
            row = legacy_batches.setdefault(key, [0, 0])
            row[0] += len(d["episodes"])
            row[1] += sum(1 for e in d["episodes"] if e["timeout"])
        for key in sorted(legacy_batches):
            eps, to = legacy_batches[key]
            if to:
                print(f"    {key:<44s} eps {eps:4d}  timeout {to:3d} = {to / eps * 100:4.1f}%")

    print("\n  the reach-cliff refusal rows (`x-edge refuse`, guard runs only):")
    if not refuse_files:
        print("    none (FRUIT_POLICY_TRIGGER_X_MAX is default off)")
    for path, count, xs in refuse_files:
        print(f"    {path}: {count} rows, x={['%.3f' % v for v in xs[:6]]}")

    # ---- [5b] the per-arm admission floor --------------------------------- #
    print("\n" + "-" * 100)
    print("[5b] the trigger's station x per arm, and the x each arm can admit")
    print("     source: the intercept note's dx = fruit_x - station_x, paired with the")
    print("     same episode's band-census x (`_trigger_station` = jaw centre at reset)")
    print("-" * 100)
    per_arm: dict[str, list[float]] = {}
    for buckets in (direct,):
        for items in buckets.values():
            for item in items:
                if not item.get("arm"):
                    continue
                data = park_cache.get(item["path"])
                if not data:
                    continue
                dx = data["trigger_dx"].get(item.get("ep"))
                if dx is None:
                    continue
                per_arm.setdefault(item["arm"], []).append(item["x"] - dx)
    for arm in sorted(per_arm):
        values = sorted(per_arm[arm])
        median = statistics.median(values)
        floor = median - TRIGGER_LATERAL
        print(
            f"  {arm:<6s} n={len(values):4d}  station x median {median:.4f} "
            f"(p10 {values[int(0.1 * len(values))]:.4f} "
            f"p90 {values[int(0.9 * len(values))]:.4f})  ->  admission floor "
            f"x >= {floor:.4f}"
        )
        for buckets in (direct,):
            pool = [item["x"] for items in buckets.values() for item in items]
            if pool:
                below = sum(1 for x in pool if x < floor)
                print(
                    f"         direct episodes below that floor: {below}/{len(pool)} = "
                    f"{below / len(pool) * 100:.2f}% (all arms pooled)"
                )
                break

    # ---- [5] the drift arithmetic ----------------------------------------- #
    print("\n" + "-" * 100)
    print("[5] the drift arithmetic - baseline-free tail counts (no drift => none)")
    print("    any delivered x below the spawn floor 0.20 (or above 0.36) is a drift")
    print("    excursion by definition: the draw is rng.uniform(0.20, 0.36).")
    print("-" * 100)
    for label, table in (("scripted", scripted), ("direct", direct)):
        row = []
        for bucket in sorted(table):
            items = table[bucket]
            unique = {}
            for item in items:
                if label == "scripted":
                    # a bit-identical replay reproduces (x, along) to 4 dp
                    key = (round(item["x"], 4), round(item["along"], 4))
                else:
                    # one sample per (log, episode); replays are different runs
                    key = (item["path"], item.get("ep"))
                unique.setdefault(key, item)
            values = [item["x"] for item in unique.values()]
            if len(values) < 5:
                continue
            s = describe(values)
            row.append((bucket, s))
        if not row:
            continue
        print(f"  {label}:")
        for bucket, s in row:
            print(
                f"    {bucket:<34s} n={s['n']:4d}  p50 {s['p50']:.3f}  "
                f"P(x<0.173) {s['lt_admit']:3d} = {s['lt_admit'] / s['n'] * 100:5.2f}%   "
                f"P(x<0.20) {s['lt_spawn_lo']:3d} = {s['lt_spawn_lo'] / s['n'] * 100:5.2f}%   "
                f"P(x>0.36) {s['gt_spawn_hi']:3d} = {s['gt_spawn_hi'] / s['n'] * 100:5.2f}%"
            )
    print(
        "\n  reading: a *shift* moves p50 off the band's centre "
        f"{(SPAWN_LO + SPAWN_HI) / 2:.3f}; a *tail* leaves p50 and stretches one end. "
        "The patch/bed schedules do not draw uniformly on the band (a pair's first\n"
        "  member is drawn from [x_min, x_max - sep]), so read the tail counts, not the KS."
    )
    print("\nDONE")
    return 0


# --------------------------------------------------------------------------- #
def self_test() -> int:
    """Parse the three row shapes and the arithmetic on synthetic lines."""
    wait = (
        "[fruit] [task]   wait step=0 fruit_y=0.2403 fruit_x=+0.3653 "
        "fruit_z=1.1974 dy=+0.2399"
    )
    m = RE_WAIT0.search(wait)
    assert m and abs(float(m.group("x")) - 0.3653) < 1e-9, wait
    park = (
        "[fruit] [park] call ep=6 n=1 along=+0.399 x=0.159 px=177 disc=139 "
        "vis=1.273 rel=0.972 arm_px=14"
    )
    m = RE_PARK.search(park)
    assert m and int(m.group("ep")) == 6 and abs(float(m.group("x")) - 0.159) < 1e-9, park
    ep = (
        "[fruit] [rl] episode 6: kiwi d=6.3cm bin=1 arm=right success=False "
        "grasped=False placed=False ticks=1500 decision=1500 reward=0.0000 "
        "notes=['timeout: no grasp within 1500 ticks'] presentation=direct ablate=none"
    )
    m = RE_EPISODE_END.search(ep)
    assert m and m.group("success") == "False" and int(m.group("ticks")) == 1500, ep
    assert "timeout: no grasp within" in ep
    prov = (
        "[fruit] [supply] scatter pool=16 seed=5 gaps=0.10-0.35 m lateral "
        "x=0.20-0.36 m stream=on target=0 wave=off grades=A:0.5,B:0.3,C:0.2 "
        "classes=strawberry:2,lychee:2 patch=on slice=0.14-0.22 pair=0.60 sep=0.085-0.12"
    )
    m = RE_PROVENANCE.search(prov)
    assert m and abs(float(m.group("lo")) - 0.20) < 1e-9, prov
    assert "patch=on" in m.group("rest")
    bedprov = (
        "[fruit] [supply] scatter pool=40 seed=5 rows=2 abreast (0.16 m) + "
        "conditional mid at x=0.28 pitch=0.130-0.150 m lateral x=0.20-0.36 m stream=on"
    )
    m = RE_PROVENANCE.search(bedprov)
    assert m and "rows=" in (m.group("head") + m.group("rest")), bedprov
    trig = (
        "[fruit] [rl] trigger=arrival lead=0.90s lateral=0.160 reach=0.20 "
        "finger=0.040 frame=station encoder=on present=off acq=on"
    )
    m = RE_TRIGGER.search(trig)
    assert m and m.group("mode") == "arrival" and abs(float(m.group("lat")) - 0.16) < 1e-9
    # KS on a perfect uniform grid is ~0; on a shifted one it is the shift.
    grid = [SPAWN_LO + (SPAWN_HI - SPAWN_LO) * i / 99 for i in range(100)]
    assert ks_uniform(grid, SPAWN_LO, SPAWN_HI) < 0.011, ks_uniform(grid, SPAWN_LO, SPAWN_HI)
    shifted = [v - 0.02 for v in grid]
    # a pure 0.02 m shift of a 0.16 m-wide uniform gives D = shift/width = 0.125
    assert 0.11 < ks_uniform(shifted, SPAWN_LO, SPAWN_HI) < 0.14, ks_uniform(
        shifted, SPAWN_LO, SPAWN_HI
    )
    assert abs(pct([0.0, 1.0], 50) - 0.5) < 1e-12
    s = describe([0.159, 0.30, 0.36, 0.20])
    assert s["lt_admit"] == 1 and s["lt_spawn_lo"] == 1 and s["gt_spawn_hi"] == 0
    print("drift_census --self-test PASS (parsers, KS, percentiles, tail counts)")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main())
