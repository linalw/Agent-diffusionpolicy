"""P4-A wait/bottleneck audit (offline, no simulator).

Parses existing pick-and-place logs and quantifies *why arms wait for fruit*:
candidate availability upstream of the selection floor, starved/empty slots,
inter-placement interval and lock-on decomposition, cycle versus wait, pool
burst/release/recycle accounting, and composition. Two-line interval/lock-on
tables are produced by ``scripts/186_w6_report.py`` itself (subprocess, quoted
verbatim); this script adds the availability/cycle/schedule layer 186 does not
cover.

    python3 scripts/201_p4a_wait_audit.py --self-test
    python3 scripts/201_p4a_wait_audit.py --out logs/p4

Single-arm log grammar used (see ``scripts/20_pick_place.py``):
* ``[run] attempt N: no eligible fruit; active=[(cat, y, dia), ...] stats={...}``
  (the ``active`` tuples are category / along-belt y / diameter - the pool the
  selector refused, in full);
* ``[run] attempt N: picking <cat> grade <G> ...`` + the outcome line
  ``[run] attempt N: grasped=.. placed=.. .. sim=t0-t1s``;
* ``[cycle] attempt M: prepose=.. hover=.. descent=.. ... total=..`` (M is
  1-based: cycle M belongs to run slot M-1);
* ``[motion] approach(cartesian): .. cm, N samples`` (N ticks at 120 Hz);
* ``[stats] attempts=.. successes=.. .. sim=..s total, ..s/attempt, .. gate_open=..``.

The selection floor is ``pick_y + _dynamic_select_floor()`` with
``_dynamic_select_floor = pick_lead + |v| * setup + margin`` (see
``src/fruit_sorting/tasks.py``). It is computed here by importing the
Isaac-free ``fruit_sorting.motion`` profile; if that import fails the script
falls back to the documented 0.40 m and records which provenance was used.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import statistics
import subprocess
import sys

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(REPO, "src"))

EMPTY = re.compile(
    r"\[run\] attempt (?P<slot>\d+): no eligible fruit; "
    r"active=(?P<active>\[.*?\]) stats=(?P<stats>\{.*?\})"
)
PICK = re.compile(
    r"\[run\] attempt (?P<slot>\d+): picking (?P<cat>\w+) grade (?P<grade>\w+)"
)
OUTCOME = re.compile(
    r"\[run\] attempt (?P<slot>\d+): grasped=(?P<g>\w+) placed=(?P<p>\w+)"
    r".*?sim=(?P<t0>[\d.]+)-(?P<t1>[\d.]+)s"
)
CYCLE = re.compile(r"\[cycle\] attempt (?P<n>\d+): (?P<body>.*?) total=(?P<total>[\d.]+)s")
SEG = re.compile(r"(?P<name>\w+)=(?P<dur>[\d.]+)s")
APPROACH = re.compile(r"\[motion\] approach\(cartesian\): [\d.]+ cm, (?P<n>\d+) samples")
STATS = re.compile(
    r"\[stats\] attempts=(?P<att>\d+) successes=(?P<ok>\d+).*?"
    r"sim=(?P<sim>[\d.]+)s total, (?P<spa>[\d.]+)s/attempt.*?gate_open=(?P<gate>[\d.]+)s"
)
ENCODER = re.compile(r"encoder=([+\-\d.]+) m/s nominal \(command ([+\-\d.]+)")
SUMMARY_ARM = re.compile(
    r"\[run\]\s+(?P<cat>\w+)\s+arm=(?P<arm>\w+)\s+grasped=(?P<g>\w+) "
    r"placed=(?P<p>\w+).*?sim=(?P<span>[\d.]+)s"
)

TWO_POOLED = re.compile(r"pooled : n=\d+ mean ([\d.]+)s p50 ([\d.]+)s p90 ([\d.]+)s")
TWO_LOCK = re.compile(r"(left|right)\s*: n=\d+ mean ([\d.]+)s.*?\(retries per interval: \[(.*?)\]\)")
TWO_STARVED = re.compile(r"starved slots: left (\d+), right (\d+)")
TWO_TPUT = re.compile(
    r"throughput \(batch span ([\d.]+)s\): (\d+)/(\d+) placed = ([\d.]+) placed/min"
    r"(?:; placement window ([\d.]+)s -> ([\d.]+) placed/min steady state)?"
)
TWO_SPAN = re.compile(r"(left|right)\s*: span ([\d.]+)s, idle ([\d.]+)s \((\d+)%\), (\d+)/(\d+) placed")


def selection_floor(speed: float = 0.12) -> tuple[float, str]:
    """Moving-catch selection floor above the station [m] + provenance note."""
    try:
        from fruit_sorting.motion import TrajectoryLimits, jerk_limited

        limits = TrajectoryLimits.from_env(1.0 / 120.0)
        limits.v_max = 0.15
        positions, _, _ = jerk_limited(max(0.06, 1e-3), limits)
        t_desc = len(positions) / 120.0
        lead = min(speed * (0.4 + t_desc + 0.15) + 0.03, 0.80)
        floor = lead + abs(speed) * 1.5 + 0.03
        return floor, f"computed(motion.py t_desc={t_desc:.3f}s lead={lead:.3f}m)"
    except Exception as exc:  # noqa: BLE001 - offline fallback, recorded
        return 0.40, f"fallback(documented ~0.40m; motion import failed: {exc!r})"


def parse_singlearm(path: str, floor: float) -> dict:
    slots: dict[int, dict] = {}
    cycles: dict[int, dict] = {}
    approaches: list[float] = []
    stats_line: dict | None = None
    encoder = None
    arm_rows: list[dict] = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            m = EMPTY.search(line)
            if m:
                slots[int(m.group("slot"))] = {
                    "empty": True,
                    "active": ast.literal_eval(m.group("active")),
                    "stats": ast.literal_eval(m.group("stats")),
                }
                continue
            m = PICK.search(line)
            if m and "picking" in line:
                slots.setdefault(int(m.group("slot")), {}).update(
                    {"empty": False, "cat": m.group("cat"), "grade": m.group("grade")}
                )
                continue
            m = OUTCOME.search(line)
            if m and "grasped=" in line and "lift=" in line:
                slots.setdefault(int(m.group("slot")), {}).update(
                    {
                        "grasped": m.group("g") == "True",
                        "placed": m.group("p") == "True",
                        "t0": float(m.group("t0")),
                        "t1": float(m.group("t1")),
                    }
                )
                continue
            m = CYCLE.search(line)
            if m:
                cycles[int(m.group("n"))] = {
                    seg.group("name"): float(seg.group("dur"))
                    for seg in SEG.finditer(m.group("body"))
                }
                continue
            m = APPROACH.search(line)
            if m:
                approaches.append(int(m.group("n")) / 120.0)
                continue
            m = STATS.search(line)
            if m:
                stats_line = {k: float(m.group(k)) for k in ("att", "ok", "sim", "spa", "gate")}
                continue
            m = ENCODER.search(line)
            if m:
                encoder = (float(m.group(1)), float(m.group(2)))
                continue
            m = SUMMARY_ARM.search(line)
            if m:
                arm_rows.append(
                    {"arm": m.group("arm"), "placed": m.group("p") == "True",
                     "span": float(m.group("span"))}
                )
    ordered = [dict(slot=s, **v) for s, v in sorted(slots.items())]
    empties = [r for r in ordered if r.get("empty")]
    real = [r for r in ordered if not r.get("empty") and "t0" in r]
    for row in empties:
        live = row["active"]
        ys = [t[1] for t in live]
        row["n_live"] = len(live)
        row["max_y"] = max(ys) if ys else None
        row["n_above_floor"] = sum(1 for y in ys if y >= floor)
        row["shortfall_m"] = (floor - max(ys)) if ys else None
    spans = [r["t1"] - r["t0"] for r in real]
    gaps = [b["t0"] - a["t1"] for a, b in zip(real, real[1:])]
    # `[cycle]` counts real attempts, not slots: the i-th real attempt owns
    # cycle i+1 (slot+1 works only when no slot was ever empty).
    cyc_list = [cycles.get(i + 1, {}) for i, _r in enumerate(real)]
    cyc_hit = sum(1 for c in cyc_list if c)
    block_mean = {}
    if cyc_hit:
        names = {k for c in cyc_list for k in c}
        for name in sorted(names):
            vals = [c[name] for c in cyc_list if name in c]
            block_mean[name] = round(statistics.fmean(vals), 3) if vals else 0.0
    wait_in_descent = None
    if block_mean.get("descent") and len(approaches) >= len(real) and real:
        paired = approaches[: len(real)]
        wait_in_descent = {
            "descent_block_mean_s": block_mean["descent"],
            "motion_approach_mean_s": round(statistics.fmean(paired), 3),
            "wait_mean_s": round(block_mean["descent"] - statistics.fmean(paired), 3),
            "n_paired": len(paired),
        }
    last_stats = empties[-1]["stats"] if empties else None
    # Wall accounting: the `[stats] sim=` line sums attempt spans only
    # (`stats["sim_time"]` accumulates inside `task.run`), so it hides the
    # inter-attempt gap (go_ready transit + the 60-step feed + selection).
    # The outcome windows are true sim time - wall rate comes from them.
    wall = None
    if real:
        placed_n = sum(1 for r in real if r.get("placed"))
        wall_span = real[-1]["t1"] - real[0]["t0"]
        wall = {
            "first_t0_s": round(real[0]["t0"], 1),
            "last_t1_s": round(real[-1]["t1"], 1),
            "prime_s": round(real[0]["t0"], 1),
            "wall_per_slot_s": round((real[-1]["t1"]) / len(ordered), 2),
            "wall_placed_per_min": round(placed_n / real[-1]["t1"] * 60.0, 2),
            "span_placed_per_min": (
                round(placed_n / sum(spans) * 60.0, 2) if spans else None
            ),
        }
    return {
        "slots": len(ordered),
        "real_attempts": len(real),
        "empty_slots": len(empties),
        "empty_fraction": round(len(empties) / len(ordered), 4) if ordered else None,
        "empty_max_y": [r["max_y"] for r in empties],
        "empty_n_live": [r["n_live"] for r in empties],
        "empty_n_above_floor": [r["n_above_floor"] for r in empties],
        "empty_shortfall_m": [r["shortfall_m"] for r in empties],
        "pool_last_seen": last_stats,
        "cadence_s_per_attempt": round(statistics.fmean(spans), 2) if spans else None,
        "inter_attempt_gap_s": round(statistics.fmean(gaps), 3) if gaps else None,
        "cycle_block_mean_s": block_mean,
        "cycle_matched": f"{cyc_hit}/{len(real)}",
        "wait_in_descent_s": wait_in_descent,
        "approach_legs": len(approaches),
        "run_stats": stats_line,
        "encoder": encoder,
        "arm_summary": arm_rows,
        "wall": wall,
    }


def parse_twoline(path: str, workdir: str) -> dict:
    """Run 186 verbatim; keep its stdout as the interval/lock-on record."""
    out = os.path.join(workdir, os.path.basename(path).replace(".log", "_186.txt"))
    proc = subprocess.run(
        [sys.executable, os.path.join(REPO, "scripts", "186_w6_report.py"), path],
        capture_output=True, text=True, cwd=REPO,
    )
    text = proc.stdout + proc.stderr
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(text)
    rec: dict = {"report": out, "rc": proc.returncode}
    m = TWO_POOLED.search(text)
    if m:
        rec["pooled_interval_s"] = tuple(float(m.group(i)) for i in (1, 2, 3))
    locks = {}
    for arm, mean, retries in TWO_LOCK.findall(text):
        vals = [int(v) for v in retries.split(",") if v.strip().isdigit()]
        locks[arm] = {"lockon_mean_s": float(mean), "retries_per_interval": vals,
                      "retries_total": sum(vals)}
    rec["lockon"] = locks
    m = TWO_STARVED.search(text)
    if m:
        rec["starved"] = {"left": int(m.group(1)), "right": int(m.group(2))}
    m = TWO_TPUT.search(text)
    if m:
        rec["throughput"] = {
            "batch_span_s": float(m.group(1)), "placed": int(m.group(2)),
            "slots": int(m.group(3)), "batch_per_min": float(m.group(4)),
            "window_s": float(m.group(5)) if m.group(5) else None,
            "window_per_min": float(m.group(6)) if m.group(6) else None,
        }
    rec["arm_spans"] = [
        {"arm": a, "span_s": float(s), "idle_s": float(i), "idle_pct": int(p),
         "placed": int(pl), "attempts": int(at)}
        for a, s, i, p, pl, at in TWO_SPAN.findall(text)
    ]
    return rec


def self_test() -> int:
    import tempfile

    tmp = tempfile.mkdtemp(prefix="p4a_", dir="/tmp/opencode")
    floor, _prov = selection_floor()
    assert 0.35 <= floor <= 0.45, f"floor {floor} outside the documented band"
    log = os.path.join(tmp, "t.log")
    with open(log, "w", encoding="utf-8") as fh:
        fh.write(
            "[fruit] [run] attempt 0: no eligible fruit; "
            "active=[('apple', 0.249, 0.068), ('apple', -0.078, 0.063)] "
            "stats={'released': 9, 'reached_end': 0, 'fell_off': 0, "
            "'discharged': 0, 'supply_skipped': 3}\n"
            "[fruit] [run] attempt 1: picking apple grade A into output lane 0 at (0.43, 0.5)\n"
            "[fruit] [run] attempt 1: grasped=True placed=True lift=+0.302 m "
            "force=4.47 N notes=[] sim=27.3-42.9s\n"
            "[fruit] [cycle] attempt 1: prepose=0.88s hover=0.78s descent=2.61s "
            "close=1.18s grip=1.56s lift=1.79s place=2.62s release=2.32s "
            "return=0.67s end=0.00s total=15.62s\n"
            "[fruit] [motion] approach(cartesian): 5.7 cm, 89 samples: steps=89\n"
            "[fruit] [stats] attempts=2 successes=1 diverted=0 success_rate=50% "
            "sim=30.0s total, 15.0s/attempt, 30.0s/success gate_open=0.0s total, "
            "queue_peak=0 recirculated=0 encoder=-0.120 m/s nominal (command -0.120, no cleats\n"
        )
    rec = parse_singlearm(log, floor)
    assert rec["slots"] == 2, rec
    assert rec["empty_slots"] == 1 and rec["real_attempts"] == 1, rec
    assert rec["empty_max_y"] == [0.249], rec
    assert rec["empty_n_above_floor"] == [0], rec
    assert abs(rec["empty_shortfall_m"][0] - (floor - 0.249)) < 1e-9, rec
    assert rec["pool_last_seen"]["released"] == 9, rec
    assert rec["cycle_block_mean_s"]["descent"] == 2.61, rec
    assert rec["wait_in_descent_s"]["n_paired"] == 1, rec
    assert abs(rec["wait_in_descent_s"]["wait_mean_s"] - (2.61 - 89 / 120.0)) < 1e-3, rec
    assert rec["cadence_s_per_attempt"] == 15.6, rec
    print(f"self-test OK (floor={floor:.3f}m provenance: {_prov})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--out", default="logs/p4")
    ap.add_argument("--belt", type=float, default=0.12)
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    floor, prov = selection_floor(args.belt)
    single = [
        "logs/p1c/D0_apple_d100.log",
        "logs/p1c/D1_apple_d160.log",
        "logs/p1c/D3_apple_d160_long.log",
        "logs/w6/20_battery_single.log",
        "logs/p2d/70_single_d150.log",
        "logs/p2d/71_single_control.log",
        "logs/p/60_accept_noharm.log",
    ]
    # 186 also reads single-arm logs with windows (intervals + spans, no
    # lock-on); run it on those too as the harness cross-check.
    single_186 = list(single)
    two = [
        "logs/w6/10_battery_twoline_1.log",
        "logs/p/00_control.log",
        "logs/p2d/52_d160.log",
        "logs/p2d/60_wave_d150.log",
        "logs/p2d/61_wave_control.log",
        "logs/w7/10_dense_twoline_1.log",
    ]
    os.makedirs(args.out, exist_ok=True)
    single_out = {"floor_m": round(floor, 4), "floor_provenance": prov,
                  "belt_m_s": args.belt, "logs": {}}
    for path in single:
        full = os.path.join(REPO, path)
        if not os.path.exists(full):
            single_out["logs"][path] = {"missing": True}
            continue
        single_out["logs"][path] = parse_singlearm(full, floor)
    with open(os.path.join(args.out, "10_singlearm_availability.json"), "w",
              encoding="utf-8") as fh:
        json.dump(single_out, fh, indent=2)
    two_out = {"logs": {}}
    for path in two + single_186:
        full = os.path.join(REPO, path)
        if not os.path.exists(full):
            two_out["logs"][path] = {"missing": True}
            continue
        two_out["logs"][path] = parse_twoline(full, args.out)
    with open(os.path.join(args.out, "11_twoline_wait.json"), "w",
              encoding="utf-8") as fh:
        json.dump(two_out, fh, indent=2)
    print(f"floor={floor:.3f}m ({prov})")
    print(f"wrote {args.out}/10_singlearm_availability.json "
          f"({len(single_out['logs'])} logs)")
    print(f"wrote {args.out}/11_twoline_wait.json ({len(two_out['logs'])} logs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
