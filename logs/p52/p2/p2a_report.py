"""The P52 phase-2 lane-A readout: T0 (shipped) vs TG (contact-gated 1.5x).

    python3 logs/p52/p2/p2a_report.py --dir logs/p52/p2 --a A --b B

A = T0 (both knobs unset) · B = TG (`FRUIT_POLICY_TIME_SCALE=1.5
FRUIT_POLICY_RETIME_GATE=1`), both on the P43 scenario and N = 3 x 15.

The endpoints are the PREREG's (`logs/p52/PREREG_DRAFT.md` section 1.4), read in
this order:

**P1 the speed** - the placed episodes' `ticks=` (simulated ticks of the whole
episode, the census's section 3 metric). Median and mean per arm, the per-seed
paired difference (same seed = the same spawn set), and the percentage fall.
Pass: TG falls **>= 8 %** vs T0.

**P2 the placements** - the right-arm placed proportion (the arm the park
covers; the left is the documented no-op and the closed grip class), the per-run
counts, and a one-sided 95 % Newcombe lower bound on the difference. Pass:
**>= -0.10**.

**P3 the failure reasons** - the per-arm reason histogram; a reason T0 never
produced is new. Pass: **none new**.

**P4 the wall and the gate** - the per-episode app wall (the `[rl] run wall end`
row / episodes) and the gate's duty cycle from the `[retime] episode` rows (the
share of decisions clamped to 1.0). Reports, not gates: the loop is
primitive-bound (P43 L2) and the duty cycle is the mechanism's own prevalence.

Nothing here is a cross-configuration rate: every count is one attractor, so the
per-episode ticks and the per-run counts are the measurements and the rates are
labelled samples.
"""

from __future__ import annotations

import argparse
import glob
import math
import os
import re
import statistics

EPISODE = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(-?\d+) arm=(\w+) "
    r"success=(\w+) grasped=(\w+) placed=(\w+) ticks=(\d+)(?: decision=(\d+))? "
    r"reward=([-+0-9.eE]+) notes=(\[[^\]]*\])"
)
WALL = re.compile(r"\[rl\] run wall end [0-9.]+ duration ([0-9.]+)s")
ACQ = re.compile(
    r"\[acq\] (\w+) idx=(\d+): setup\[premove=([0-9.]+) axis=([0-9.]+) "
    r"hover=([0-9.]+) wait=([0-9.]+) catchup=([0-9.]+)\]s catchup=(\d+)t"
)
RETIME_EP = re.compile(
    r"\[retime\] episode (\d+): s=([0-9.]+) gate=(\d+) decisions=(\d+) "
    r"gated=(\d+) \(([0-9.]+)%\) ticks=(\d+) gated_ticks=(\d+) "
    r"\(([0-9.]+)%\) by_force_ticks=(\d+) by_finger_ticks=(\d+) "
    r"force_max=([0-9.]+)N"
)
RETIME_ROW = re.compile(
    r"\[retime\] ep=(\d+) decision=(\d+) s=([0-9.]+) s_eff=([0-9.]+) "
    r"contact=(\d) force=([0-9.]+)N finger=([0-9.]+)mm"
)


# --------------------------------------------------------------------------- #
def parse(path: str) -> dict:
    rows, retime, wall, acq = [], [], None, []
    for line in open(path, encoding="utf-8", errors="ignore"):
        found = EPISODE.search(line)
        if found:
            rows.append(
                {
                    "index": int(found.group(1)),
                    "category": found.group(2),
                    "diameter": float(found.group(3)),
                    "arm": found.group(5),
                    "success": found.group(6) == "True",
                    "grasped": found.group(7) == "True",
                    "placed": found.group(8) == "True",
                    "ticks": int(found.group(9)),
                    "decision": int(found.group(10)) if found.group(10) else None,
                    "notes": found.group(12),
                }
            )
            continue
        found = ACQ.search(line)
        if found:
            acq.append(
                {
                    "arm": found.group(1),
                    "premove": float(found.group(3)),
                    "axis": float(found.group(4)),
                    "hover": float(found.group(5)),
                    "wait": float(found.group(6)),
                    "catchup_s": float(found.group(7)),
                    "catchup_t": int(found.group(8)),
                }
            )
            continue
        found = RETIME_EP.search(line)
        if found:
            retime.append(
                {
                    "episode": int(found.group(1)),
                    "s": float(found.group(2)),
                    "gate": int(found.group(3)),
                    "decisions": int(found.group(4)),
                    "gated": int(found.group(5)),
                    "gated_share": float(found.group(6)) / 100.0,
                    "ticks": int(found.group(7)),
                    "gated_ticks": int(found.group(8)),
                    "gated_tick_share": float(found.group(9)) / 100.0,
                    "by_force_ticks": int(found.group(10)),
                    "by_finger_ticks": int(found.group(11)),
                    "force_max": float(found.group(12)),
                }
            )
            continue
        found = WALL.search(line)
        if found:
            wall = float(found.group(1))
    return {"rows": rows, "retime": retime, "wall": wall, "acq": acq}


def load(directory: str, labels: tuple[str, str]) -> dict[str, dict[int, dict]]:
    arms: dict[str, dict[int, dict]] = {label: {} for label in labels}
    for path in sorted(glob.glob(os.path.join(directory, "*.log"))):
        stem = os.path.basename(path)[:-4]
        if "_" not in stem:
            continue
        label, run = stem.rsplit("_", 1)
        if label in arms and run.isdigit():
            arms[label][int(run)] = parse(path)
    return arms


# --------------------------------------------------------------------------- #
def sign_test_p(better: int, worse: int) -> float:
    n = better + worse
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(better, n + 1)) / (2.0 ** n)


def newcombe_lower(p1: int, n1: int, p2: int, n2: int) -> float:
    """One-sided 95 % Newcombe (hybrid score) lower bound for p2 - p1."""
    if n1 == 0 or n2 == 0:
        return float("nan")
    r1, r2 = p1 / n1, p2 / n2
    z = 1.959963984540054
    # Wilson score intervals
    def wilson(x: int, n: int) -> tuple[float, float]:
        p = x / n
        den = 1.0 + z * z / n
        centre = (p + z * z / (2 * n)) / den
        half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
        return centre - half, centre + half

    l1, u1 = wilson(p1, n1)
    l2, u2 = wilson(p2, n2)
    diff = r2 - r1
    return diff - math.sqrt(max(0.0, (r2 - l2) ** 2 + (u1 - r1) ** 2))


def reasons(notes: str) -> list[str]:
    """The note list as failure-reason keys (digits normalised, like 113)."""
    body = notes.strip()
    if body.startswith("[") and body.endswith("]"):
        body = body[1:-1]
    out = []
    for item in body.split("',") if "'," in body else body.split(","):
        text = item.strip().strip("'\" ")
        if not text:
            continue
        text = re.sub(r"[-+]?\d*\.?\d+", "#", text)
        out.append(text)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="logs/p52/p2")
    ap.add_argument("--a", default="A")
    ap.add_argument("--b", default="B")
    ap.add_argument("--a-name", default="T0")
    ap.add_argument("--b-name", default="TG")
    args = ap.parse_args()

    arms = load(args.dir, (args.a, args.b))
    runs = sorted(set(arms[args.a]) & set(arms[args.b]))
    if not runs:
        print(f"no {args.a}_*/{args.b}_*.log pairs in {args.dir}")
        return 2
    names = {args.a: args.a_name, args.b: args.b_name}

    print("=" * 78)
    print(f"P52 phase 2 lane A: {args.a_name} (shipped) vs {args.b_name} "
          f"(contact-gated s) - {len(runs)} paired runs")
    print("=" * 78)
    print(f"  runs found: {runs}")
    for label in (args.a, args.b):
        for run in runs:
            arm = arms[label][run]
            print(f"  {names[label]} run {run}: {len(arm['rows'])} episodes, "
                  f"wall {arm['wall']}, retime rows {len(arm['retime'])}")

    # ---- P1: the speed ---------------------------------------------------- #
    print()
    print("-" * 78)
    print("P1  THE SPEED: placed-episode ticks (sim time)")
    print("-" * 78)
    placed = {
        label: [r for run in runs for r in arms[label][run]["rows"] if r["placed"]]
        for label in (args.a, args.b)
    }
    for label in (args.a, args.b):
        rows = placed[label]
        if not rows:
            print(f"  {names[label]}: no placed episodes")
            continue
        ticks = [r["ticks"] for r in rows]
        print(f"  {names[label]}: n={len(rows)}  median {statistics.median(ticks):.0f}  "
              f"mean {statistics.mean(ticks):.1f}  sd "
              f"{statistics.pstdev(ticks) if len(ticks) > 1 else 0:.1f}  "
              f"min {min(ticks)}  max {max(ticks)}")
    fall = None
    if placed[args.a] and placed[args.b]:
        a_med = statistics.median([r["ticks"] for r in placed[args.a]])
        b_med = statistics.median([r["ticks"] for r in placed[args.b]])
        a_mean = statistics.mean([r["ticks"] for r in placed[args.a]])
        b_mean = statistics.mean([r["ticks"] for r in placed[args.b]])
        fall = 1.0 - b_med / a_med
        fall_mean = 1.0 - b_mean / a_mean
        print(f"  median {a_med:.0f} -> {b_med:.0f} ticks  = {fall:+.1%}")
        print(f"  mean   {a_mean:.1f} -> {b_mean:.1f} ticks  = {fall_mean:+.1%}")
        print(f"  P1 bar: {args.b_name} falls >= 8 %  ->  "
              f"{'PASS' if fall >= 0.08 else 'FAIL'} ({fall:+.1%})")
    # per-seed paired
    print("  per-seed paired (placed episodes only, seeds are the spawn sets):")
    deltas = []
    for run in runs:
        ra = [r["ticks"] for r in arms[args.a][run]["rows"] if r["placed"]]
        rb = [r["ticks"] for r in arms[args.b][run]["rows"] if r["placed"]]
        if ra and rb:
            d = statistics.median(rb) - statistics.median(ra)
            deltas.append(d)
            print(f"    seed-run {run}: {statistics.median(ra):.0f} -> "
                  f"{statistics.median(rb):.0f}  ({d:+.0f} ticks)")
        else:
            print(f"    seed-run {run}: no placed episode in one arm "
                  f"(a={len(ra)}, b={len(rb)})")

    # ---- P2: the placements ---------------------------------------------- #
    print()
    print("-" * 78)
    print("P2  THE PLACEMENTS (right arm = the park's population)")
    print("-" * 78)
    right = {
        label: [r for run in runs for r in arms[label][run]["rows"] if r["arm"] == "right"]
        for label in (args.a, args.b)
    }
    left = {
        label: [r for run in runs for r in arms[label][run]["rows"] if r["arm"] == "left"]
        for label in (args.a, args.b)
    }
    for label in (args.a, args.b):
        rr, ll = right[label], left[label]
        rp = sum(1 for r in rr if r["placed"])
        lp = sum(1 for r in ll if r["placed"])
        print(f"  {names[label]}: right placed {rp}/{len(rr)} "
              f"({rp / len(rr) if rr else 0:.1%})   left {lp}/{len(ll)} "
              f"({lp / len(ll) if ll else 0:.1%})   "
              f"pooled placed {sum(1 for r in rr + ll if r['placed'])}/{len(rr) + len(ll)}")
        per_run = []
        for run in runs:
            rows_ = [r for r in arms[label][run]["rows"] if r["arm"] == "right"]
            per_run.append(f"{sum(1 for r in rows_ if r['placed'])}/{len(rows_)}")
        print(f"    per-run right: {per_run}")
    p2_ok = None
    if right[args.a] and right[args.b]:
        p1c = sum(1 for r in right[args.a] if r["placed"])
        p2c = sum(1 for r in right[args.b] if r["placed"])
        n1, n2 = len(right[args.a]), len(right[args.b])
        delta = p2c / n2 - p1c / n1
        lb = newcombe_lower(p1c, n1, p2c, n2)
        p2_ok = delta >= -0.10
        print(f"  delta placed(right) {delta:+.3f}  one-sided 95 % Newcombe lower "
              f"{lb:+.3f}")
        print(f"  P2 bar: >= -0.10  ->  {'PASS' if p2_ok else 'FAIL'}")
        # run level
        better = worse = 0
        for run in runs:
            ra = [r for r in arms[args.a][run]["rows"] if r["arm"] == "right"]
            rb = [r for r in arms[args.b][run]["rows"] if r["arm"] == "right"]
            ca = sum(1 for r in ra if r["placed"]) / len(ra) if ra else 0.0
            cb = sum(1 for r in rb if r["placed"]) / len(rb) if rb else 0.0
            if cb > ca + 1e-9:
                better += 1
            elif cb < ca - 1e-9:
                worse += 1
        print(f"  run level: {args.b_name} better {better}, worse {worse} "
              f"(one-sided sign p = {sign_test_p(better, worse):.3f})")

    # ---- P3: the failure reasons ----------------------------------------- #
    print()
    print("-" * 78)
    print("P3  THE FAILURE REASONS")
    print("-" * 78)
    reason_sets = {}
    for label in (args.a, args.b):
        counts: dict[str, int] = {}
        for run in runs:
            for r in arms[label][run]["rows"]:
                if r["placed"]:
                    continue
                for key in reasons(r["notes"]):
                    counts[key] = counts.get(key, 0) + 1
        reason_sets[label] = counts
        print(f"  {names[label]}:")
        if not counts:
            print("    (none)")
        for key, count in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"    {count:3d}  {key}")
    new = sorted(set(reason_sets[args.b]) - set(reason_sets[args.a]))
    print(f"  new under {args.b_name}: "
          f"{new if new else 'none'}")
    p3_ok = not new
    print(f"  P3 bar: no new reason  ->  {'PASS' if p3_ok else 'FAIL'}")

    # ---- P3b: the class split (per arm side) ----------------------------- #
    print()
    print("  the outcome classes (placed | carried-not-placed | no-grasp):")
    for label in (args.a, args.b):
        table: dict[str, dict[str, int]] = {}
        for run in runs:
            for r in arms[label][run]["rows"]:
                key = ("placed" if r["placed"]
                       else "cnp" if r["grasped"] else "no-grasp")
                cell = table.setdefault(r["arm"], {"placed": 0, "cnp": 0, "no-grasp": 0})
                cell[key] += 1
        for side in sorted(table):
            cell = table[side]
            n = sum(cell.values())
            print(f"    {names[label]:3s} {side:5s} n={n:2d}  placed {cell['placed']:2d}  "
                  f"cnp {cell['cnp']:2d}  no-grasp {cell['no-grasp']:2d}")

    # ---- P4: the wall and the gate --------------------------------------- #
    print()
    print("-" * 78)
    print("P4  THE WALL and THE GATE'S DUTY CYCLE (reports)")
    print("-" * 78)
    for label in (args.a, args.b):
        walls = [arms[label][run]["wall"] for run in runs]
        eps = sum(len(arms[label][run]["rows"]) for run in runs)
        total = sum(w for w in walls if w)
        print(f"  {names[label]}: wall {total:.0f}s over {eps} episodes = "
              f"{total / eps if eps else 0:.1f} s/episode")
        retime = [row for run in runs for row in arms[label][run]["retime"]]
        if retime:
            dec = sum(r["decisions"] for r in retime)
            gat = sum(r["gated"] for r in retime)
            tks = sum(r["ticks"] for r in retime)
            gtk = sum(r["gated_ticks"] for r in retime)
            print(f"    gate: {len(retime)} episodes instrumented, "
                  f"{gat}/{dec} decisions gated "
                  f"({gat / dec if dec else 0:.1%}), "
                  f"{gtk}/{tks} ticks ({gtk / tks if tks else 0:.1%}), "
                  f"by force {sum(r['by_force_ticks'] for r in retime)} ticks / "
                  f"by finger {sum(r['by_finger_ticks'] for r in retime)} ticks "
                  f"(the finger criterion is a subset), "
                  f"peak force max {max(r['force_max'] for r in retime):.1f} N")
            print(f"    gate per run: "
                  + ", ".join(
                      f"{sum(1 for r in arms[label][run]['retime'] if r['gated'])}"
                      f"/{sum(r['decisions'] for r in arms[label][run]['retime'])}"
                      for run in runs))
        else:
            print("    gate: not instrumented (control arm)")

    print()
    print("-" * 78)
    print("P5  WHERE THE TIME IS (the mechanism; reports)")
    print("-" * 78)
    for label in (args.a, args.b):
        rows = placed[label]
        if not rows:
            continue
        pol = [r["decision"] for r in rows if r["decision"]]
        tot = [r["ticks"] for r in rows]
        scr = [r["ticks"] - r["decision"] for r in rows if r["decision"]]
        print(f"  {names[label]}: placed {len(rows)}  "
              f"policy phase (decision=) {statistics.median(pol):.0f} ticks "
              f"({statistics.median(pol) / 120.0:.2f} s, "
              f"{statistics.median(pol) / statistics.median(tot):.0%} of the episode)  "
              f"scripted remainder {statistics.median(scr):.0f} ticks "
              f"({statistics.median(scr) / 120.0:.2f} s)")
        acq = [a for run in runs for a in arms[label][run]["acq"]]
        if acq:
            print(f"    [acq] n={len(acq)}  premove {statistics.median([a['premove'] for a in acq]):.2f}  "
                  f"axis {statistics.median([a['axis'] for a in acq]):.2f}  "
                  f"hover {statistics.median([a['hover'] for a in acq]):.2f}  "
                  f"wait {statistics.median([a['wait'] for a in acq]):.2f}  "
                  f"catchup {statistics.median([a['catchup_s'] for a in acq]):.2f}s / "
                  f"{statistics.median([a['catchup_t'] for a in acq]):.0f}t")

    print()
    print("=" * 78)
    print("VERDICTS")
    print("=" * 78)
    print(f"  P1 speed (>= 8 % fewer placed-episode ticks): "
          f"{'PASS' if (fall is not None and fall >= 0.08) else 'FAIL'}"
          + (f"  ({fall:+.1%})" if fall is not None else "  (unmeasurable)"))
    print(f"  P2 placements (right >= -0.10): "
          f"{'PASS' if p2_ok else 'FAIL' if p2_ok is not None else 'n/a'}")
    print(f"  P3 no new failure reason: {'PASS' if p3_ok else 'FAIL'}")
    print(f"  P4 wall / gate duty cycle: reported (not gated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
