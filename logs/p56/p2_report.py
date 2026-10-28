#!/usr/bin/env python3
"""P56 phase 2 report: the pre-registered endpoints P1-P6 (logs/p56/PREREG.md 2).

    python3 logs/p56/p2_report.py --dir logs/p56/p2

Reads only the logs (`A_<n>.log` = the shipped per-pick loop, `B_<n>.log` = the
continuous episode) plus each run's recorder index (`store/<arm>/.../index.json`)
for P5. No simulator, no `src/` import: the report can be re-derived from the
evidence directory alone.

Lines it parses (all pre-existing formats except the two P56 instruments):
  `[rl] episode N: ... success= ... placed= ... ticks= ... reward= ... notes=[...]`
  `[grasp] episode N pick=k/n arm=a t0=T q_err_max=E`      (P56, FRUIT_GRASP_DIAG)
  `[bed-sel] attempt N t=T live=L on_belt=B admitted=A window=W pick=...`
  `[cont] pick k/n: ... gap_ticks=G ...`  /  `[cont] episode N: picks=.. placed=..`
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics as st

EPISODE = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(-?\d+) arm=(\w+) "
    r"success=(\w+) grasped=(\w+) placed=(\w+) ticks=(\d+)(?: decision=(\d+))? "
    r"reward=([-+0-9.eE]+) notes=(\[[^\]]*\])"
)
GRASP = re.compile(
    r"\[grasp\] episode (\d+) pick=(\d+)/(\d+) arm=(\w+) t0=([\d.]+) "
    r"q_err_max=([\d.]+)"
)
BEDSEL = re.compile(
    r"\[bed-sel\] attempt (\d+) t=([\d.]+) live=(\d+) on_belt=(\d+) "
    r"admitted=(\d+) window=(\d+) pick=(\S+)"
)
CONT_PICK = re.compile(r"\[cont\] pick (\d+)/(\d+):.*gap_ticks=(\d+)")
CONT_WAIT = re.compile(
    r"\[cont\] pick (\d+)/(\d+): waiting for a candidate \(round (\d+)/40\)"
)
CONT_EP = re.compile(
    r"\[cont\] episode (\d+): picks=(\d+)/(\d+) placed=(\d+) reward=([-+0-9.eE]+) "
    r"ticks=(\d+) gap_ticks=([-+0-9.eE]+) gaps=(\[[^\]]*\])"
)
WALL = re.compile(r"\[rl\] run wall end [\d.]+ duration ([\d.]+)s")
ROLLOUT = re.compile(r"\[rl\] rollout success (\d+)/(\d+)")


def reasons(rows) -> set[str]:
    """`scripts/113_rl_report.py`'s normalisation (digits -> '#')."""
    out: set[str] = set()
    for row in rows:
        if row["success"]:
            continue
        text = row["notes"].strip("[]").strip()
        out.add("empty note" if not text else re.sub(r"[-+0-9.]+", "#", text))
    return out


def parse(path: str) -> dict:
    rows, grasps, beds, cont_picks, waits = [], [], [], [], []
    cont_ep = None
    wall = None
    rollout = None
    for line in open(path, encoding="utf-8", errors="ignore"):
        if "[fruit]" not in line:
            continue
        m = EPISODE.search(line)
        if m:
            rows.append(
                {
                    "index": int(m.group(1)),
                    "category": m.group(2),
                    "arm": m.group(5),
                    "success": m.group(6) == "True",
                    "grasped": m.group(7) == "True",
                    "placed": m.group(8) == "True",
                    "ticks": int(m.group(9)),
                    "reward": float(m.group(11)),
                    "notes": m.group(12),
                }
            )
            continue
        m = GRASP.search(line)
        if m:
            grasps.append(
                {
                    "index": int(m.group(1)),
                    "pick": int(m.group(2)),
                    "of": int(m.group(3)),
                    "arm": m.group(4),
                    "t0": float(m.group(5)),
                    "err": float(m.group(6)),
                }
            )
            continue
        m = BEDSEL.search(line)
        if m:
            beds.append(
                {
                    "attempt": int(m.group(1)),
                    "t": float(m.group(2)),
                    "live": int(m.group(3)),
                    "on_belt": int(m.group(4)),
                    "admitted": int(m.group(5)),
                    "window": int(m.group(6)),
                    "pick": m.group(7),
                }
            )
            continue
        m = CONT_WAIT.search(line)
        if m:
            waits.append({"pick": int(m.group(1)), "round": int(m.group(3))})
            continue
        m = CONT_PICK.search(line)
        if m:
            cont_picks.append({"pick": int(m.group(1)), "gap": int(m.group(3))})
            continue
        m = CONT_EP.search(line)
        if m:
            cont_ep = {
                "picks": int(m.group(2)),
                "target": int(m.group(3)),
                "placed": int(m.group(4)),
                "reward": float(m.group(5)),
                "ticks": int(m.group(6)),
                "gap_mean": float(m.group(7)),
                "gaps": [int(v) for v in re.findall(r"\d+", m.group(8))],
            }
            continue
        m = WALL.search(line)
        if m:
            wall = float(m.group(1))
            continue
        m = ROLLOUT.search(line)
        if m:
            rollout = (int(m.group(1)), int(m.group(2)))
    return {
        "rows": rows,
        "grasps": grasps,
        "beds": beds,
        "cont_picks": cont_picks,
        "waits": waits,
        "cont_ep": cont_ep,
        "wall": wall,
        "rollout": rollout,
    }


def gaps_of(parsed: dict) -> list[int]:
    """The inter-pick gap in sim ticks, from the per-pick clock and ticks.

    `[grasp] t0` is `_episode_t0` (set *after* the per-pick setup), so
    `gap(k) = t0(k+1) - (t0(k) + ticks(k)/120)` is the same quantity in both
    arms: the shipped arm's whole reset block, the continuous arm's continuation
    block. Cross-checked against the `[cont] ... gap_ticks=` rows.
    """
    grasps = parsed["grasps"]
    rows = {r["index"]: r for r in parsed["rows"]}
    out = []
    for a, b in zip(grasps, grasps[1:]):
        prev = rows.get(a["index"])
        if prev is None:
            continue
        out.append(int(round((b["t0"] - (a["t0"] + prev["ticks"] / 120.0)) * 120.0)))
    return out


def sim_span(parsed: dict) -> float:
    """Sim seconds from the first pick's clock start to the last pick's end.

    Includes the inter-pick gaps (the term the mode removes), excludes the first
    pick's setup - equal in both arms, so the placed/min comparison is like for
    like.
    """
    grasps, rows = parsed["grasps"], parsed["rows"]
    if not grasps or not rows:
        return float("nan")
    by_index = {r["index"]: r for r in rows}
    first, last = grasps[0], grasps[-1]
    end = last["t0"] + by_index[last["index"]]["ticks"] / 120.0
    return end - first["t0"]


def stat(values: list[float]) -> str:
    if not values:
        return "n=0"
    return (
        f"n={len(values)} min={min(values):.0f} "
        f"med={st.median(values):.0f} max={max(values):.0f}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="logs/p56/p2")
    ap.add_argument("--picks", type=int, default=15)
    args = ap.parse_args()

    runs: dict[str, list[tuple[str, dict]]] = {"A": [], "B": []}
    for name in sorted(os.listdir(args.dir)):
        m = re.fullmatch(r"([AB])_(\d+)\.log", name)
        if not m:
            continue
        runs[m.group(1)].append(
            (name, parse(os.path.join(args.dir, name)))
        )

    print("== per-run shape (a `--episodes` mix-up would show here) ==")
    bad = 0
    for arm in ("A", "B"):
        for name, p in runs[arm]:
            picks = len(p["rows"])
            ok = picks == args.picks and len(p["grasps"]) == args.picks
            bad += 0 if ok else 1
            print(
                f"  {name:<10s} outcome_rows={picks} grasp_rows={len(p['grasps'])} "
                f"bedsel={len(p['beds'])} distinct_index="
                f"{len({r['index'] for r in p['rows']})} "
                f"rollout={p['rollout']} wall={p['wall']} "
                f"{'OK' if ok else 'SHAPE-MISMATCH'}"
            )
    if bad:
        print(f"  !! {bad} run(s) do not carry {args.picks} picks - the report below is void")

    print("\n== P1 the inter-pick gap (sim ticks; bar: median <= 80, max <= 90) ==")
    for arm in ("A", "B"):
        allg, contg = [], []
        for name, p in runs[arm]:
            g = gaps_of(p)
            allg += g
            contg += [c["gap"] for c in p["cont_picks"]]
            print(f"  {name:<10s} gaps={g}")
        print(f"  {arm}: {stat(allg)}")
        print(
            f"  {arm}: gaps by class "
            f"50={allg.count(50)} 80={allg.count(80)} "
            f"110={allg.count(110)} other={sorted(set(allg) - {50, 80, 110})} "
            f"| starvation rounds="
            f"{sum(len(p['waits']) for _n, p in runs[arm])}"
        )
        if contg:
            print(f"  {arm}: [cont] gap_ticks={contg} ({stat(contg)})")

    print("\n== P2 placed (counts per run; placed/min on the sim span incl. gaps) ==")
    pooled = {}
    for arm in ("A", "B"):
        placed = n = 0
        spans = []
        for name, p in runs[arm]:
            q = sum(1 for r in p["rows"] if r["placed"])
            pl = sum(1 for r in p["rows"] if r["placed"] and r["success"])
            placed += q
            n += len(p["rows"])
            spans.append(sim_span(p))
            print(
                f"  {name:<10s} placed={q}/{len(p['rows'])} success={pl} "
                f"sim_span={sim_span(p):.1f}s  placed/min="
                f"{q / (sim_span(p) / 60.0):.2f}  wall={p['wall']}s "
                f"wall/pick={(p['wall'] or 0) / max(len(p['rows']), 1):.1f}"
            )
        pooled[arm] = (placed, n)
        total = sum(spans)
        print(
            f"  {arm}: pooled placed={placed}/{n} = {placed / max(n, 1):.3f}; "
            f"sim={total:.1f}s -> {placed / (total / 60.0):.2f} placed/min"
        )

    print("\n== P3 the belt stock at every selection ([bed-sel] window) ==")
    for arm in ("A", "B"):
        w, ob, lv = [], [], []
        for name, p in runs[arm]:
            # One block per episode index; a starved transition prints the failed
            # round's block first and the successful selection's after it, so the
            # **last** block per index is the state the pick was selected from.
            last = {}
            for b in p["beds"]:
                last[b["attempt"]] = b
            sel = [last[k] for k in sorted(last)]
            w += [b["window"] for b in sel]
            ob += [b["on_belt"] for b in sel]
            lv += [b["live"] for b in sel]
            print(
                f"  {name:<10s} window={[b['window'] for b in sel]} "
                f"on_belt={[b['on_belt'] for b in sel]} "
                f"(all blocks {len(p['beds'])})"
            )
        if w:
            share = sum(1 for v in w if v >= 2) / len(w)
            print(
                f"  {arm}: window>=2 at {share * 100:.1f}% of picks "
                f"({sum(1 for v in w if v >= 2)}/{len(w)}); "
                f"window med={st.median(w):.0f}; on_belt med={st.median(ob):.0f}; "
                f"live med={st.median(lv):.0f}"
            )

    print("\n== P4 failure reasons (113's normalisation) ==")
    ra = reasons([r for arm in ("A",) for _, p in runs[arm] for r in p["rows"]])
    rb = reasons([r for arm in ("B",) for _, p in runs[arm] for r in p["rows"]])
    baseline = set()
    for root in ("logs/p43/p3", "logs/p54/p1"):
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            if name.endswith(".log"):
                baseline |= reasons(parse(os.path.join(root, name))["rows"])
    print(f"  A: {sorted(ra) or 'none'}")
    print(f"  B: {sorted(rb) or 'none'}")
    print(f"  P43/P54 baseline set: {sorted(baseline) or 'none'}")
    print(f"  NEW in B (vs A): {sorted(rb - ra) or 'none'}")
    print(f"  NEW in B (vs A + baseline): {sorted(rb - (ra | baseline)) or 'none'}")
    print(f"  MISSING in B: {sorted(ra - rb) or 'none'}")

    print("\n== P5 the accounting (15 distinct indices, the npz files, the sums) ==")
    for arm in ("A", "B"):
        for name, p in runs[arm]:
            idx = [r["index"] for r in p["rows"]]
            print(
                f"  {name:<10s} distinct_index={len(set(idx))}/{len(idx)} "
                f"contiguous={idx == list(range(idx[0], idx[0] + len(idx)))}"
            )
            if p["cont_ep"]:
                ce = p["cont_ep"]
                s_ticks = sum(r["ticks"] for r in p["rows"])
                s_reward = sum(r["reward"] for r in p["rows"])
                print(
                    f"  {name:<10s} [cont] picks={ce['picks']}/{ce['target']} "
                    f"placed={ce['placed']} vs rows "
                    f"{sum(1 for r in p['rows'] if r['placed'])}; "
                    f"ticks_total={ce['ticks']} == sum(rows)={s_ticks} "
                    f"{'OK' if ce['ticks'] == s_ticks else 'MISMATCH'}; "
                    f"reward_total={ce['reward']:.6f} vs sum(4dp rows)="
                    f"{s_reward:.4f} (delta {ce['reward'] - s_reward:+.2e})"
                )
    for arm in ("A", "B"):
        root = os.path.join(args.dir, "store", arm)
        for dirpath, _dirs, files in os.walk(root):
            if "index.json" in files:
                path = os.path.join(dirpath, "index.json")
                try:
                    data = json.load(open(path, encoding="utf-8"))
                except Exception as exc:  # noqa: BLE001
                    print(f"  {path}: unreadable ({exc})")
                    continue
                rows = data if isinstance(data, list) else data.get("episodes", [])
                idx = [r.get("index") for r in rows if isinstance(r, dict)]
                npz = [f for f in files if f.startswith("rollout_") and f.endswith(".npz")]
                print(
                    f"  {os.path.relpath(path, args.dir)}: index_rows={len(rows)} "
                    f"distinct_index={len(set(idx))}/{len(idx)} npz={len(npz)} "
                    f"distinct_npz={len(set(npz))}"
                )

    print("\n== per-pick table (arm B: pick | arm | gap | window | on_belt | placed | ticks) ==")
    for name, p in runs["B"]:
        rows = {r["index"]: r for r in p["rows"]}
        beds = {b["attempt"]: b for b in p["beds"]}
        gaps = gaps_of(p)
        waits = {w["pick"]: w["round"] for w in p["waits"]}
        print(f"  {name}:  starvation rounds={len(p['waits'])} at picks "
              f"{sorted(waits)}")
        for i, g in enumerate(p["grasps"]):
            row = rows.get(g["index"], {})
            bed = beds.get(g["index"], {})
            gap = gaps[i - 1] if i else 0
            print(
                f"    pick {g['pick']:>2d}/{g['of']:<2d} ep={g['index']:>2d} "
                f"arm={g['arm']:<5s} gap={gap:>3d} "
                f"wait={waits.get(g['pick'], 0):>2d} "
                f"window={bed.get('window', '-'):>2} "
                f"on_belt={bed.get('on_belt', '-'):>2} "
                f"placed={int(row.get('placed', False))} "
                f"ticks={row.get('ticks', 0):>5d} q_err={g['err']:.4f}"
            )

    print("\n== P6 the policy's start state (|q - grasp|_max; bar: >= 95% <= 0.011 rad) ==")
    for arm in ("A", "B"):
        errs = [g["err"] for name, p in runs[arm] for g in p["grasps"]]
        if not errs:
            print(f"  {arm}: no [grasp] rows (FRUIT_GRASP_DIAG unset?)")
            continue
        within = sum(1 for e in errs if e <= 0.011)
        print(
            f"  {arm}: n={len(errs)} within_0.011={within}/{len(errs)} = "
            f"{within / len(errs) * 100:.1f}%  min={min(errs):.4f} "
            f"med={st.median(errs):.4f} max={max(errs):.4f}"
        )
        per_arm: dict[str, list[float]] = {}
        for _name, p in runs[arm]:
            for g in p["grasps"]:
                per_arm.setdefault(g["arm"], []).append(g["err"])
        for key, vals in sorted(per_arm.items()):
            print(f"     {arm}/{key}: n={len(vals)} med={st.median(vals):.4f} max={max(vals):.4f}")

    print("\n== verdicts ==")
    gap_b = [g for arm in ("B",) for _, p in runs[arm] for g in gaps_of(p)]
    p1 = bool(gap_b) and st.median(gap_b) <= 80 and max(gap_b) <= 90
    pa, pb = pooled.get("A", (0, 0)), pooled.get("B", (0, 0))
    p2 = abs(pb[0] - pa[0]) <= 4
    lastb = {}
    for _name, p in runs["B"]:
        for b in p["beds"]:
            lastb[b["attempt"]] = b
    wb = [lastb[k]["window"] for k in sorted(lastb)]
    p3 = bool(wb) and sum(1 for v in wb if v >= 2) / len(wb) >= 0.90
    p4 = not (rb - (ra | baseline))
    print(f"  P1 gap median<=80 & max<=90      : {'PASS' if p1 else 'FAIL'}")
    print(f"  P2 |placed_B - placed_A| <= 4    : {'PASS' if p2 else 'FAIL'} "
          f"({pb[0]} vs {pa[0]})")
    print(f"  P3 window>=2 at >=90% of B picks : {'PASS' if p3 else 'FAIL'}")
    print(f"  P4 no new reason in B (A+base)   : {'PASS' if p4 else 'FAIL'} "
          f"{sorted(rb - (ra | baseline))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
