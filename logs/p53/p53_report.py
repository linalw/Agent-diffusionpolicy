"""P53 report: the emission cells T0 / C1 / C2 from the batch logs and stores.

    python3 logs/p53/p53_report.py --dir logs/p53/p3 --stores /tmp/opencode/p53/raw

Reads
  * `[rl] episode ...` - one row per episode (outcome, ticks, arm, class),
  * `[emit] episode ...` - the P53 emission census (applied ticks, decisions,
    out-of-range joint-steps before/after the clamp),
  * `[rl] run wall end ... duration` - the app wall per run,
  * the `--record` stores (`rollout_*.npz` + `index.json`) - the same-tick
    `(action, joint_positions)` pair, i.e. the **lead residual** (the dither).

The task-space conversion is `logs/p52/p2b_feasibility.py`'s own:
`p50 |cmd - achieved| [rad] x 0.30 m` (the lever `logs/p44/CAP_CENSUS.md`
section 1.1 measures), so the numbers here are comparable to the census's
**19.3 mm** and to its **13.1 % of joint-steps / 74.3 % of ticks**.

The dither has one confound to name: a recorded frame is taken on the 30 Hz
observation grid, so with `hold = 1` *every* recorded frame is a chunk-boundary
frame (the first waypoint of a fresh chunk, the largest lead), while with
`hold = 2` every second frame is an intra-chunk one. The residual is therefore
also reported split by the command's own step size (a **fixed** 0.02 rad cut on
`max|Δa|`, so the two arms are cut at the same place), and the command's own
path rate (`max|Δa| x 30 Hz`) is printed beside it.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import statistics

import numpy as np

EPISODE = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(-?\d+) arm=(\w+) "
    r"success=(\w+) grasped=(\w+) placed=(\w+) ticks=(\d+)(?: decision=(\d+))? "
    r"reward=([-+0-9.eE]+) notes=(\[[^\]]*\])"
)
EMIT = re.compile(
    r"\[emit\] episode (\d+): hold=(\d+) clamp=(\d+) ticks=(\d+) decisions=(\d+) "
    r"out_pre=(\d+)/(\d+) \([\d.]+%\) out_post=(\d+)/(\d+) \([\d.]+%\) "
    r"ticks_with_overshoot=(\d+) overshoot_max=([\d.]+)mrad"
)
WALL = re.compile(r"\[rl\] run wall end \S+ duration ([\d.]+)s")

#: The 22-D dof layout (`rl_env.py`): left = 0,2,..,12; right = 1,3,..,13.
ARM_DOF = {
    "left": [0, 2, 4, 6, 8, 10, 12],
    "right": [1, 3, 5, 7, 9, 11, 13],
}
LEVER_M = 0.30
SMOOTH_CUT = 0.02  # rad, max|Δa| between two 30 Hz frames


def say(*a):
    print(" ".join(str(x) for x in a), flush=True)


def read_log(path: str) -> dict:
    out = {"episodes": [], "emit": [], "wall": None}
    for line in open(path, encoding="utf-8", errors="ignore"):
        m = EPISODE.search(line)
        if m:
            out["episodes"].append(
                {
                    "index": int(m.group(1)),
                    "category": m.group(2),
                    "diameter": float(m.group(3)),
                    "arm": m.group(5),
                    "success": m.group(6) == "True",
                    "grasped": m.group(7) == "True",
                    "placed": m.group(8) == "True",
                    "ticks": int(m.group(9)),
                }
            )
            continue
        m = EMIT.search(line)
        if m:
            out["emit"].append(
                {
                    "index": int(m.group(1)),
                    "hold": int(m.group(2)),
                    "clamp": int(m.group(3)),
                    "ticks": int(m.group(4)),
                    "decisions": int(m.group(5)),
                    "pre": int(m.group(6)),
                    "post": int(m.group(8)),
                    "with_over": int(m.group(10)),
                    "over_max": float(m.group(11)),
                }
            )
            continue
        m = WALL.search(line)
        if m:
            out["wall"] = float(m.group(1))
    return out


def load(directory: str, labels: list[str]) -> dict:
    arms = {label: [] for label in labels}
    for path in sorted(glob.glob(os.path.join(directory, "*.log"))):
        stem = os.path.basename(path)[:-4]
        if "_" not in stem:
            continue
        label, run = stem.rsplit("_", 1)
        if label not in arms or not run.isdigit():
            continue
        rows = read_log(path)
        rows["run"] = int(run)
        rows["file"] = os.path.basename(path)
        arms[label].append(rows)
    return arms


def store_rows(root: str, label: str) -> list[tuple[np.ndarray, np.ndarray, str]]:
    """(joint_positions, action, arm) per recorded episode of one arm."""
    out = []
    for run_dir in sorted(glob.glob(os.path.join(root, f"{label}_*"))):
        for index_path in sorted(
            glob.glob(os.path.join(run_dir, "**", "index.json"), recursive=True)
        ):
            try:
                rows = json.load(open(index_path, encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(rows, dict):
                rows = rows.get("episodes", [])
            base = os.path.dirname(index_path)
            for row in rows:
                path = os.path.join(base, row.get("file", ""))
                if not os.path.isfile(path):
                    continue
                with np.load(path) as data:
                    if "action" not in data or "joint_positions" not in data:
                        continue
                    out.append(
                        (
                            np.asarray(data["joint_positions"], dtype=float),
                            np.asarray(data["action"], dtype=float),
                            str(row.get("arm", "right")),
                        )
                    )
    return out


def residual_table(rows, name: str, cut: float = SMOOTH_CUT) -> dict:
    """Same-tick |cmd - achieved|, the census's own metric (P2B section 1.2)."""
    r0, steps, achieved = [], [], []
    for q, a, arm in rows:
        if q.ndim != 2 or q.shape[1] != 22 or a.ndim != 2 or len(a) < 8:
            continue
        idx = ARM_DOF.get(arm, ARM_DOF["right"])
        Q = q[:, idx][:, :7]
        A = a[:, :7]
        n = min(len(Q), len(A))
        r0.append(np.abs(A[:n] - Q[:n]))
        da = np.abs(np.diff(A[:n], axis=0))
        dq = np.abs(np.diff(Q[:n], axis=0))
        # aligned with the rows: the episode's first frame has no step of its
        # own, and it is never a "slow" one, so it carries +inf.
        steps.append(
            np.r_[np.inf, da.max(1)] if da.size else np.full(n, np.inf)
        )
        if dq.size:
            achieved.append(dq.max(1))
    if not r0:
        return {}
    R = np.concatenate(r0)
    S = np.concatenate(steps) if steps else np.zeros(0)
    Qr = np.concatenate(achieved) if achieved else np.zeros(0)
    finite = S[np.isfinite(S)] if S.size else np.zeros(0)
    out = {
        "name": name,
        "frames": int(R.shape[0]),
        "p50_mrad": float(np.median(R) * 1e3),
        "p90_mrad": float(np.percentile(R, 90) * 1e3),
        "p50_mm": float(np.median(R) * LEVER_M * 1e3),
        "p90_mm": float(np.percentile(R, 90) * LEVER_M * 1e3),
        "step_p50": float(np.median(finite)) if finite.size else float("nan"),
        "rate_p50": float(np.median(finite) * 30.0) if finite.size else float("nan"),
        "rate_p90": float(np.percentile(finite, 90) * 30.0) if finite.size else float("nan"),
        "achieved_p50": float(np.median(Qr) * 30.0) if Qr.size else float("nan"),
        "achieved_p90": float(np.percentile(Qr, 90) * 30.0) if Qr.size else float("nan"),
    }
    if S.size == R.shape[0]:
        smooth = S <= cut
        out["smooth_share"] = float(smooth.mean())
        out["smooth_p50_mm"] = (
            float(np.median(R[smooth]) * LEVER_M * 1e3) if smooth.any() else float("nan")
        )
    return out


def pool_cut(store_map: dict) -> float:
    """The split between "nearly held" and "moving" frames, pooled over the arms.

    One fixed cut for every arm, taken from the *pooled* distribution so it
    cannot favour either side: a recorded frame is on the 30 Hz grid, and with
    `hold = 1` every frame is a chunk-boundary frame while with `hold = 2` every
    second one is intra-chunk. Cutting at the pooled median compares like with
    like without letting an arm choose its own threshold.
    """
    steps = []
    for rows in store_map.values():
        for q, a, arm in rows:
            if a.ndim != 2 or a.shape[1] < 7 or len(a) < 8:
                continue
            steps.append(np.abs(np.diff(a[:, :7], axis=0)).max(1))
    if not steps:
        return SMOOTH_CUT
    return float(np.median(np.concatenate(steps)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="logs/p53/p3")
    ap.add_argument("--stores", default="/tmp/opencode/p53/raw")
    ap.add_argument("--arms", default="T0,C1,C2")
    args = ap.parse_args()
    labels = [x for x in args.arms.split(",") if x]

    arms = load(args.dir, labels)
    for label in labels:
        if not arms[label]:
            say(f"no {label}_<run>.log in {args.dir}")
            return 2

    say("=" * 96)
    say("P53 - the policy's own emission defect: T0 (shipped) / C1 (clamp) / C2 (hold 2)")
    say("=" * 96)

    # ---- per-run table ---------------------------------------------------- #
    say()
    say("[1] per run (placed = the gate's outcome; ticks = simulated ticks)")
    say(f"  {'arm':<4s} {'run':<4s} {'placed':>7s} {'right':>6s} {'left':>5s} "
        f"{'ticks_p50':>10s} {'decisions':>10s} {'wall_s':>7s}")
    per_run = {}
    for label in labels:
        for rows in sorted(arms[label], key=lambda r: r["run"]):
            eps = rows["episodes"]
            placed = [e for e in eps if e["placed"]]
            right = [e for e in eps if e["arm"] == "right"]
            left = [e for e in eps if e["arm"] == "left"]
            dec = [em["decisions"] for em in rows["emit"] if em["decisions"]]
            per_run[(label, rows["run"])] = {
                "placed": len(placed),
                "n": len(eps),
                "right": sum(1 for e in right if e["placed"]),
                "n_right": len(right),
                "left": sum(1 for e in left if e["placed"]),
                "n_left": len(left),
                "ticks": statistics.median([e["ticks"] for e in placed]) if placed else float("nan"),
                "decisions": statistics.median(dec) if dec else float("nan"),
                "wall": rows["wall"],
            }
            r = per_run[(label, rows["run"])]
            say(f"  {label:<4s} {rows['run']:<4d} {r['placed']:>3d}/{r['n']:<3d} "
                f"{r['right']:>3d}/{r['n_right']:<2d} "
                f"{r['left']:>2d}/{r['n_left']:<2d} "
                f"{r['ticks']:>10.0f} {r['decisions']:>10.0f} {r['wall']:>7.1f}")

    # ---- pooled ----------------------------------------------------------- #
    say()
    say("[2] pooled per arm")
    say(f"  {'arm':<4s} {'placed':>9s} {'right':>9s} {'left':>8s} {'cnp':>5s} "
        f"{'no-grasp':>9s} {'ticks_p50':>10s} {'dec_p50':>8s} "
        f"{'wall/ep':>8s} {'sim_s/ep':>9s}")
    pooled = {}
    for label in labels:
        eps = [e for rows in arms[label] for e in rows["episodes"]]
        placed = [e for e in eps if e["placed"]]
        cnp = [e for e in eps if e["grasped"] and not e["placed"]]
        nog = [e for e in eps if not e["grasped"]]
        right = [e for e in eps if e["arm"] == "right"]
        left = [e for e in eps if e["arm"] == "left"]
        walls = [rows["wall"] for rows in arms[label] if rows["wall"]]
        ticks = [e["ticks"] for e in eps]
        dec = [em["decisions"] for rows in arms[label] for em in rows["emit"] if em["decisions"]]
        pooled[label] = {
            "n": len(eps),
            "placed": len(placed),
            "right": sum(1 for e in right if e["placed"]),
            "n_right": len(right),
            "left": sum(1 for e in left if e["placed"]),
            "n_left": len(left),
            "cnp": len(cnp),
            "nograsp": len(nog),
            "ticks_p50": statistics.median(ticks) if ticks else float("nan"),
            "dec_p50": statistics.median(dec) if dec else float("nan"),
            "wall_ep": (sum(walls) / len(eps)) if (walls and eps) else float("nan"),
            "sim_ep": (statistics.median(ticks) / 120.0) if ticks else float("nan"),
        }
        p = pooled[label]
        say(f"  {label:<4s} {p['placed']:>3d}/{p['n']:<3d} "
            f"{p['right']:>3d}/{p['n_right']:<2d} {p['left']:>2d}/{p['n_left']:<2d} "
            f"{p['cnp']:>5d} {p['nograsp']:>9d} {p['ticks_p50']:>10.0f} "
            f"{p['dec_p50']:>8.0f} {p['wall_ep']:>8.1f} {p['sim_ep']:>9.2f}")

    # ---- per-seed deltas (E1's bar is per run) ---------------------------- #
    say()
    say("[3] per-run delta against T0 (the registered bar: placed >= T0 - 1)")
    runs = sorted({rows["run"] for rows in arms[labels[0]]})
    for label in labels[1:]:
        deltas = []
        for run in runs:
            a = per_run.get((labels[0], run))
            b = per_run.get((label, run))
            if a is None or b is None:
                continue
            d = b["placed"] - a["placed"]
            deltas.append(d)
            say(f"  {label} vs T0, seed-run {run}: {b['placed']} vs {a['placed']} "
                f"({d:+d}/15) {'OK' if d >= -1 else 'FAIL'}")
        if deltas:
            say(f"  {label}: deltas {deltas} sum {sum(deltas):+d} "
                f"min {min(deltas):+d} "
                f"{'PASS' if min(deltas) >= -1 else 'FAIL'} (the -1/15 per-run bar)")

    # ---- the emission census --------------------------------------------- #
    say()
    say("[4] the emission census (the `[emit]` rows): out-of-range joint-steps")
    say(f"  {'arm':<4s} {'episodes':>8s} {'ticks':>8s} {'dec':>6s} {'hold':>4s} "
        f"{'clamp':>5s} {'out_pre':>16s} {'out_post':>16s} "
        f"{'ticks>stop':>10s} {'over_max':>9s}")
    for label in labels:
        rows = [em for r in arms[label] for em in r["emit"]]
        if not rows:
            say(f"  {label:<4s} (no [emit] rows - diag off)")
            continue
        ticks = sum(r["ticks"] for r in rows)
        pre = sum(r["pre"] for r in rows)
        post = sum(r["post"] for r in rows)
        with_over = sum(r["with_over"] for r in rows)
        over_max = max(r["over_max"] for r in rows)
        say(f"  {label:<4s} {len(rows):>8d} {ticks:>8d} "
            f"{sum(r['decisions'] for r in rows):>6d} "
            f"{rows[0]['hold']:>4d} {rows[0]['clamp']:>5d} "
            f"{pre:>6d}/{7 * ticks:<8d} {post:>6d}/{7 * ticks:<8d} "
            f"{with_over:>5d}/{ticks:<8d} {over_max:>9.1f}")
        say(f"       pre {pre / (7 * ticks):.1%} of joint-steps, "
            f"on {with_over / ticks:.1%} of ticks; "
            f"post {post / (7 * ticks):.1%}")

    # ---- the dither (the store) ------------------------------------------ #
    say()
    say("[5] the dither: same-tick |cmd - achieved| from the stores "
        "(P2B's own metric)")
    say(f"  {'arm':<8s} {'frames':>7s} {'p50_mrad':>9s} {'p90_mrad':>9s} "
        f"{'task_p50':>9s} {'task_p90':>9s} {'slow_share':>10s} "
        f"{'slow_p50':>10s} {'cmd_rate':>9s} {'achieved':>9s}")
    store_map = {label: store_rows(args.stores, label) for label in labels}
    cut = pool_cut(store_map)
    say(f"       (the 'slow' half is `max|da| <= {cut:.3f} rad` between two 30 Hz "
        f"frames = {cut * 30.0:.2f} rad/s, the pooled median)")
    for label in labels:
        rows = store_map[label]
        if not rows:
            say(f"  {label:<8s} (no store under {args.stores})")
            continue
        for subset, name in (
            ("all", label),
            ("right", f"{label}/right"),
            ("left", f"{label}/left"),
        ):
            part = rows if subset == "all" else [r for r in rows if r[2] == subset]
            table = residual_table(part, name, cut)
            if not table:
                say(f"  {name:<8s} (no frames)")
                continue
            say(f"  {name:<8s} {table['frames']:>7d} {table['p50_mrad']:>9.1f} "
                f"{table['p90_mrad']:>9.1f} {table['p50_mm']:>8.1f}mm "
                f"{table['p90_mm']:>8.1f}mm {table.get('smooth_share', 0):>9.1%} "
                f"{(str(round(table.get('smooth_p50_mm', float('nan')), 1)) + 'mm'):>10s} "
                f"{table['rate_p50']:>8.2f}/s {table['achieved_p50']:>8.2f}/s")

    # ---- failure notes ---------------------------------------------------- #
    say()
    say("[6] failure notes (the raw note text of every non-placed episode)")
    for label in labels:
        counts: dict[str, int] = {}
        for rows in arms[label]:
            for e in rows["episodes"]:
                if e["placed"]:
                    continue
                key = ("cnp" if e["grasped"] else "no-grasp") + ":" + e["category"]
                counts[key] = counts.get(key, 0) + 1
        say(f"  {label}: {dict(sorted(counts.items())) or 'none'}")

    say()
    say("[7] the file set")
    for label in labels:
        for rows in sorted(arms[label], key=lambda r: r["run"]):
            say(f"  {label}_{rows['run']}.log  episodes={len(rows['episodes'])} "
                f"emit_rows={len(rows['emit'])} wall={rows['wall']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
