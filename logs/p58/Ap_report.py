"""P58 phase 3a report — cell A': the supply triple on the SHIPPED per-pick interface.

    python3 logs/p58/Ap_report.py --dir logs/p58/p3a

Reads the three `logs/p58/p3a/Ap_<seed>.log` files and prints the endpoints
registered in `logs/p58/PREREG_A_APRIME.md` §2 (written before the first run):

  E1  the selection-clock boundary: sel_gap = 120*(t_{k+1}-t_k) - ticks_k,
      every gap <= 141 ticks (140 within the 2-dp print quantization); the
      literal `> 140` count is reported beside it.
  E2  the owner's object: pooled `on_belt` median >= 8 AND every run's final
      cumulative `skipped` <= 60.
  E3  `window>=1` at 45/45 selections (the per-pick census is an upper bound,
      PREREG §E3 / P58 amendment A1.1).
  E4  no failure reason outside A_p1 (the same-scenario control) + the P43/P54
      baseline, under scripts/113_rl_report.py's normalisation.
  G1-G3 the cell's construction checks.

Reported, never gated: placed (counts, no rate), wall/pick, admitted/lag, the
`[feed]` pump rows, the supply provenance.

Read-only: it opens logs and prints. No state, no store, no `configs/`.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import statistics as st

EPISODE = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(-?\d+) arm=(\w+) "
    r"success=(\w+) grasped=(\w+) placed=(\w+) ticks=(\d+)(?: decision=(\d+))? "
    r"reward=([-+0-9.eE]+) notes=(\[[^\]]*\])"
)
BED = re.compile(
    r"\[bed-sel\] attempt (\d+) t=([\d.]+) live=(\d+) on_belt=(\d+) "
    r"admitted=(\d+) window=(\d+) pick=(\S+) pump_next=([\d.]+) "
    r"lag=([-+0-9.]+) rebased=(\d+) dropped=([\d.]+)s skipped=(\d+) "
    r"refused=(\d+) placed=(\d+)"
)
FEED = re.compile(
    r"\[feed\] (\w+): updates=(\d+) ticks=(\d+) stride=(\d+) "
    r"released=([-+]\d+) placed=([-+]\d+) skipped=([-+]\d+)"
)
WALL = re.compile(r"\[rl\] run wall end ([\d.]+) duration ([\d.]+)s")
ROLLOUT = re.compile(r"\[rl\] rollout success (\d+)/(\d+)")
SUPPLY = re.compile(r"\[supply\] .*")
TRIGGER = re.compile(r"\[rl\] trigger=\S+.*")


def reasons_of(rows) -> set[str]:
    """`scripts/113_rl_report.py`'s normalisation (digits -> '#'), verbatim."""
    out: set[str] = set()
    for row in rows:
        if row["success"]:
            continue
        text = row["notes"].strip("[]").strip()
        out.add("empty note" if not text else re.sub(r"[-+0-9.]+", "#", text))
    return out


def fragments_of(rows) -> set[str]:
    out: set[str] = set()
    for row in rows:
        if row["success"]:
            continue
        text = row["notes"].strip("[]").strip()
        if not text:
            out.add("empty note")
            continue
        for frag in text.split("', '"):
            out.add(re.sub(r"[-+0-9.]+", "#", frag.strip(" '\"[]")))
    return out


def parse(path: str) -> dict:
    p = {
        "path": path, "rows": [], "bed": [], "feed": [], "wall": None,
        "rollout": None, "trigger": None, "env_ready": None, "supply": None,
        "cont_rows": 0, "events": [], "starved_reset": 0, "wedged": False,
    }
    for line in open(path, encoding="utf-8", errors="ignore"):
        if "[fruit]" not in line and "[feed]" not in line:
            continue
        if "[cont]" in line:
            p["cont_rows"] += 1
            continue
        m = EPISODE.search(line)
        if m:
            p["rows"].append({
                "index": int(m.group(1)), "category": m.group(2),
                "diameter": float(m.group(3)), "arm": m.group(5),
                "success": m.group(6) == "True",
                "grasped": m.group(7) == "True",
                "placed": m.group(8) == "True",
                "ticks": int(m.group(9)),
                "reward": float(m.group(11)), "notes": m.group(12),
            })
            p["events"].append(("ep", p["rows"][-1]))
            continue
        m = BED.search(line)
        if m:
            p["bed"].append({
                "attempt": int(m.group(1)), "t": float(m.group(2)),
                "live": int(m.group(3)), "on_belt": int(m.group(4)),
                "admitted": int(m.group(5)), "window": int(m.group(6)),
                "pick": m.group(7), "lag": float(m.group(9)),
                "rebased": int(m.group(10)), "dropped": float(m.group(11)),
                "skipped": int(m.group(12)),
            })
            p["events"].append(("bed", p["bed"][-1]))
            continue
        m = FEED.search(line)
        if m:
            p["feed"].append({"arm": m.group(1), "updates": int(m.group(2)),
                              "ticks": int(m.group(3)), "stride": int(m.group(4))})
            continue
        m = WALL.search(line)
        if m:
            p["wall"] = float(m.group(2))
            continue
        m = ROLLOUT.search(line)
        if m:
            p["rollout"] = (int(m.group(1)), int(m.group(2)))
            continue
        if p["supply"] is None and SUPPLY.search(line):
            p["supply"] = SUPPLY.search(line).group(0).strip()
            continue
        if p["trigger"] is None and TRIGGER.search(line):
            p["trigger"] = line.split("[fruit]", 1)[-1].strip()
        if p["env_ready"] is None and "[rl] env ready:" in line:
            p["env_ready"] = line.split("[rl] env ready:", 1)[1].strip()
        if "no graspable fruit reached the selection window" in line:
            p["starved_reset"] += 1
    if p["wall"] is None and p["rows"]:
        p["wedged"] = True
    return p


def sel_gaps(p: dict) -> list[int]:
    """PREREG §E1: the selection-clock boundary, over consecutive selections."""
    gaps, last_bed, last_ep = [], None, None
    for kind, x in p["events"]:
        if kind == "ep":
            last_ep = x
        else:
            if last_bed is not None and last_ep is not None:
                g = 120.0 * (x["t"] - last_bed["t"]) - last_ep["ticks"]
                if g >= 0:
                    gaps.append(int(round(g)))
            last_bed, last_ep = x, None
    return gaps


def load(directory: str, pattern: str) -> dict[int, dict]:
    out = {}
    for path in sorted(glob.glob(os.path.join(directory, pattern))):
        stem = os.path.basename(path)[:-4]
        seed = stem.rsplit("_", 1)[-1]
        if seed.isdigit():
            out[int(seed)] = parse(path)
    return out


def fm(x, nd=1):
    return "n/a" if x is None else f"{x:.{nd}f}"


def med(vals):
    return st.median(vals) if vals else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="logs/p58/p3a")
    ap.add_argument("--pattern", default="Ap_*.log")
    ap.add_argument("--control-dir", default="logs/p58/p1",
                    help="P58 phase 1's arm A (the same-scenario per-pick control)")
    ap.add_argument("--stack-dir", default="logs/p58/p1",
                    help="P58 phase 1's arm B (the full stack, continuous episode)")
    args = ap.parse_args()

    cell = load(args.dir, args.pattern)
    ctrl = load(args.control_dir, "A_*.log")
    stack = load(args.stack_dir, "B_*.log")
    seeds = sorted(cell)
    print("# P58 phase 3a report — cell A': the supply triple on the SHIPPED per-pick interface")
    print(f"# dir {args.dir}  seeds {seeds}  logs {len(cell)}")
    print(f"# control (phase 1 arm A, same scenario, per-pick, no triple): "
          f"{sorted(ctrl)}  |  stack (phase 1 arm B, continuous): {sorted(stack)}")
    if not seeds:
        print("no Ap_<seed>.log files")
        return 2

    # ------------------------------------------------------------ runs table --
    print("\n== the runs (unit = one pick = one `[rl] episode ... success=` row) ==")
    for seed in seeds:
        p = cell[seed]
        rows, bed = p["rows"], p["bed"]
        placed = sum(1 for r in rows if r["placed"])
        ln = sum(1 for r in rows if r["arm"] == "left")
        ro = sum(1 for r in rows if r["arm"] == "right")
        lok = sum(1 for r in rows if r["arm"] == "left" and r["placed"])
        rok = sum(1 for r in rows if r["arm"] == "right" and r["placed"])
        g = sel_gaps(p)
        print(f"  A' seed {str(seed):>3s}: picks={len(rows):2d} placed={placed:2d} "
              f"(left {lok}/{ln}, right {rok}/{ro}) bed_rows={len(bed):2d} "
              f"feed_rows={len(p['feed']):2d} cont_rows={p['cont_rows']} "
              f"on_belt med {fm(med([b['on_belt'] for b in bed]), 0)} "
              f"skipped_final {bed[-1]['skipped'] if bed else 'n/a'} "
              f"gap max {max(g) if g else 'n/a'} wall={fm(p['wall'])}s"
              + ("  WEDGED (no wall row)" if p["wedged"] else "")
              + (f"  starved_reset={p['starved_reset']}" if p["starved_reset"] else ""))

    # ------------------------------------------------------- manipulation check --
    print("\n== manipulation check (PREREG §1: the triple on, the shipped interface) ==")
    for seed in seeds:
        p = cell[seed]
        print(f"  A' seed {str(seed):>3s}: {p['env_ready']}")
        print(f"                  {p['trigger']}")

    print("\n== supply provenance (PREREG §4, read-only) ==")
    ok_prov = True
    for seed in seeds:
        p = cell[seed]
        s = p["supply"] or "MISSING"
        patch = "patch=on" in s
        grades = "grades=A:0.375,B:0.375,C:0.25" in s
        n_bed = len(p["bed"])
        n_feed = len(p["feed"])
        # the BED regex itself *requires* `skipped=`, so n_bed == 15 proves the
        # column is present on all 15 rows (PREREG §4).
        ok_prov &= patch and grades and n_bed == 15 and n_feed > 0
        print(f"  seed {str(seed):>3s}: patch=on {patch}  grades_balanced {grades}  "
              f"[bed-sel] rows {n_bed}/15 with the skipped= column parsed  "
              f"[feed] rows {n_feed} (the cadence ran: {n_feed > 0})")

    # -------------------------------------------------------------------- E1 ---
    print("\n== E1 the selection-clock boundary (PREREG §E1: every gap <= 141 ticks) ==")
    print("   sel_gap_k = 120*(t_{k+1}-t_k) - ticks_k  (no [cont] rows in this cell)")
    e1 = True
    all_gaps = []
    for label, table in (("A'", cell), ("A ctl", ctrl)):
        for seed in sorted(table):
            g = sel_gaps(table[seed])
            if not g:
                continue
            all_gaps += g
            over = [x for x in g if x > 140]
            retry = [x for x in g if x >= 169]
            print(f"  {label:6s} seed {str(seed):>3s}: n={len(g)} min={min(g)} "
                  f"med={fm(med(g), 0)} max={max(g)}  >140: {len(over)} {over} "
                  f"  >=169 (a starved feed round): {len(retry)}")
    for seed in seeds:
        g = sel_gaps(cell[seed])
        if not g or max(g) > 141:
            e1 = False
    print(f"  E1  {'PASS' if e1 else 'FAIL'}")

    # -------------------------------------------------------------------- E2 ---
    print("\n== E2 the stock and the scheduler (PREREG §E2) ==")
    print("   bar: pooled `on_belt` median >= 8  AND  every run's final cumulative `skipped` <= 60")
    pooled_on = [b["on_belt"] for seed in seeds for b in cell[seed]["bed"]]
    pooled_win = [b["window"] for seed in seeds for b in cell[seed]["bed"]]
    ctrl_on = [b["on_belt"] for seed in sorted(ctrl) for b in ctrl[seed]["bed"]]
    stack_on = [b["on_belt"] for seed in sorted(stack) for b in stack[seed]["bed"]]
    per_run_on = {s: med([b["on_belt"] for b in cell[s]["bed"]]) for s in seeds}
    per_run_sk = {s: (cell[s]["bed"][-1]["skipped"] if cell[s]["bed"] else None) for s in seeds}
    e2_on = (med(pooled_on) or 0) >= 8
    e2_sk = all(v is not None and v <= 60 for v in per_run_sk.values())
    e2 = e2_on and e2_sk
    print(f"  on_belt median: A' pooled {fm(med(pooled_on), 1)} "
          f"(per run {({s: round(v, 1) for s, v in per_run_on.items()})})")
    print(f"                  control (phase-1 A) pooled {fm(med(ctrl_on), 1)}  "
          f"stack (phase-1 B) pooled {fm(med(stack_on), 1)}")
    print(f"  final cumulative skipped: A' {per_run_sk}")
    print(f"                  control (phase-1 A) "
          f"{ {s: (ctrl[s]['bed'][-1]['skipped'] if ctrl[s]['bed'] else None) for s in sorted(ctrl)} }"
          f"  stack (phase-1 B) "
          f"{ {s: (stack[s]['bed'][-1]['skipped'] if stack[s]['bed'] else None) for s in sorted(stack)} }")
    print(f"  E2a on_belt median >= 8 : {'PASS' if e2_on else 'FAIL'}")
    print(f"  E2b every run skipped <= 60: {'PASS' if e2_sk else 'FAIL'}")
    print(f"  E2  {'PASS' if e2 else 'FAIL'}")

    # -------------------------------------------------------------------- E3 ---
    print("\n== E3 window>=1 at every selection (PREREG §E3: 45/45) ==")
    n_win = sum(1 for w in pooled_win if w >= 1)
    wdist = {k: sum(1 for w in pooled_win if w == k) for k in sorted(set(pooled_win))}
    e3 = n_win == 45
    print(f"  A': window>=1 {n_win}/{len(pooled_win)} = "
          f"{(n_win / len(pooled_win)) if pooled_win else 0:.1%}  distribution {wdist}")
    ctrl_w = [b["window"] for s in sorted(ctrl) for b in ctrl[s]["bed"]]
    stack_w = [b["window"] for s in sorted(stack) for b in stack[s]["bed"]]
    print(f"  control (phase-1 A) window>=1 {sum(1 for w in ctrl_w if w >= 1)}/{len(ctrl_w)}  "
          f"distribution { {k: sum(1 for w in ctrl_w if w == k) for k in sorted(set(ctrl_w))} }")
    print(f"  stack   (phase-1 B) window>=1 {sum(1 for w in stack_w if w >= 1)}/{len(stack_w)}  "
          f"distribution { {k: sum(1 for w in stack_w if w == k) for k in sorted(set(stack_w))} }")
    print(f"  E3  {'PASS' if e3 else 'FAIL'}   (a starved retry round is invisible in this "
          f"census on the per-pick path - PREREG §E3/A1.1 - and is read by E1)")

    # -------------------------------------------------------------------- E4 ---
    print("\n== E4 no new failure reason (113's normalisation) ==")
    ra = reasons_of([r for s in seeds for r in cell[s]["rows"]])
    rctl = reasons_of([r for s in sorted(ctrl) for r in ctrl[s]["rows"]])
    baseline = set()
    for root in ("logs/p43/p3", "logs/p54/p1"):
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            if name.endswith(".log"):
                baseline |= reasons_of(parse(os.path.join(root, name))["rows"])
    new = sorted(ra - (rctl | baseline))
    print(f"  A' keys ({len(ra)}):")
    for k in sorted(ra):
        print(f"    - {k[:200]}")
    print(f"  control (phase-1 A) keys: {len(rctl)}  |  P43/P54 baseline keys: {len(baseline)}")
    print(f"  NEW in A' (vs control + baseline): {new or 'none'}")
    print(f"  missing in A' (vs control): {sorted(rctl - ra) or 'none'}")
    fa = fragments_of([r for s in seeds for r in cell[s]["rows"]])
    fc = fragments_of([r for s in sorted(ctrl) for r in ctrl[s]["rows"]])
    print(f"  A' fragments: {sorted(fa)}")
    print(f"  A' fragments not in control: {sorted(fa - fc) or 'none'}")
    e4 = not new
    print(f"  E4  {'PASS' if e4 else 'FAIL'}")

    # -------------------------------------------------------- reported: placed --
    print("\n== reported only: the placed count (branches; NO rate claim) ==")
    tot = sum(1 for s in seeds for r in cell[s]["rows"] if r["placed"])
    n = sum(len(cell[s]["rows"]) for s in seeds)
    lok = sum(1 for s in seeds for r in cell[s]["rows"] if r["arm"] == "left" and r["placed"])
    ln = sum(1 for s in seeds for r in cell[s]["rows"] if r["arm"] == "left")
    rok = sum(1 for s in seeds for r in cell[s]["rows"] if r["arm"] == "right" and r["placed"])
    rn = sum(1 for s in seeds for r in cell[s]["rows"] if r["arm"] == "right")
    print(f"  A': placed {tot}/{n} (left {lok}/{ln}, right {rok}/{rn})")
    for s in seeds:
        rows = cell[s]["rows"]
        print(f"    seed {str(s):>3s}: {sum(1 for r in rows if r['placed'])}/{len(rows)} "
              f"(left {sum(1 for r in rows if r['arm'] == 'left' and r['placed'])}"
              f"/{sum(1 for r in rows if r['arm'] == 'left')}, "
              f"right {sum(1 for r in rows if r['arm'] == 'right' and r['placed'])}"
              f"/{sum(1 for r in rows if r['arm'] == 'right')})")
    for label, table in (("control", ctrl), ("stack", stack)):
        if not table:
            continue
        t = sum(1 for s in table for r in table[s]["rows"] if r["placed"])
        m = sum(len(table[s]["rows"]) for s in table)
        print(f"  phase-1 {label}: placed {t}/{m}")

    # --------------------------------------------------------- reported: wall --
    print("\n== reported only: the wall per pick ==")
    walls = [cell[s]["wall"] for s in seeds]
    picks = [len(cell[s]["rows"]) for s in seeds]
    if all(w is not None for w in walls) and all(picks):
        print(f"  A' walls {[round(w) for w in walls]}s  per pick "
              f"{[round(w / p) for w, p in zip(walls, picks)]}  pooled "
              f"{sum(walls):.0f}s / {sum(picks)} = {sum(walls) / sum(picks):.2f} s/pick")
    for label, table in (("control", ctrl), ("stack", stack)):
        if not table:
            continue
        w = [table[s]["wall"] for s in sorted(table)]
        p = [len(table[s]["rows"]) for s in sorted(table)]
        if all(x is not None for x in w):
            print(f"  phase-1 {label}: {sum(w):.0f}s / {sum(p)} = {sum(w) / sum(p):.2f} s/pick")

    # -------------------------------------------- reported: admitted / lag / feed --
    print("\n== reported: the mechanism columns ==")
    for seed in seeds:
        bed = cell[seed]["bed"]
        if not bed:
            continue
        print(f"  seed {str(seed):>3s}: admitted med {fm(med([b['admitted'] for b in bed]), 0)} "
              f"lag med {fm(med([b['lag'] for b in bed]), 2)}s "
              f"rebased {sum(b['rebased'] for b in bed)} "
              f"dropped {sum(b['dropped'] for b in bed):.1f}s "
              f"live med {fm(med([b['live'] for b in bed]), 0)}")
        if cell[seed]["feed"]:
            f = cell[seed]["feed"]
            print(f"                 [feed] rows {len(f)}: updates "
                  f"{min(x['updates'] for x in f)}-{max(x['updates'] for x in f)} "
                  f"ticks {min(x['ticks'] for x in f)}-{max(x['ticks'] for x in f)} "
                  f"stride {sorted({x['stride'] for x in f})}")
        else:
            print("                 [feed] rows 0  <-- the cadence did NOT run")
    for label, table in (("control", ctrl), ("stack", stack)):
        if not table:
            continue
        bed = [b for s in sorted(table) for b in table[s]["bed"]]
        if bed:
            print(f"  phase-1 {label}: on_belt med {fm(med([b['on_belt'] for b in bed]), 0)} "
                  f"live med {fm(med([b['live'] for b in bed]), 0)} "
                  f"admitted med {fm(med([b['admitted'] for b in bed]), 0)} "
                  f"lag med {fm(med([b['lag'] for b in bed]), 2)}s")

    # ------------------------------------------------------------ falsifiers --
    print("\n== falsifiers (PREREG §5) ==")
    g1 = any(len(cell[s]["rows"]) != 15 or cell[s]["wedged"] for s in seeds)
    g2 = any(cell[s]["cont_rows"] for s in seeds)
    print(f"  G1 every run delivers 15 picks, no wedge : {'FIRES' if g1 else 'does not fire'} "
          f"({ {s: len(cell[s]['rows']) for s in seeds} })")
    print(f"  G2 [cont] rows in a log (not the shipped interface): "
          f"{'FIRES' if g2 else 'does not fire'} "
          f"({ {s: cell[s]['cont_rows'] for s in seeds} })")
    print(f"  G3 tree pins stable: see {args.dir}/Ap_header.txt vs Ap_tree_md5_after.txt")

    # --------------------------------------------------------------- verdict --
    print("\n== verdict ==")
    print(f"  E1 {'PASS' if e1 else 'FAIL'} | E2 {'PASS' if e2 else 'FAIL'} "
          f"(on_belt {'PASS' if e2_on else 'FAIL'}, skipped {'PASS' if e2_sk else 'FAIL'}) "
          f"| E3 {'PASS' if e3 else 'FAIL'} | E4 {'PASS' if e4 else 'FAIL'} "
          f"| supply provenance {'OK' if ok_prov else 'CHECK'}")
    if e1 and e2 and e3 and e4:
        v = "E1-E4 PASS -> the triple is FLIPPABLE for `direct` (the continuous episode is not load-bearing)"
    elif e1 and e3 and e4 and not e2:
        v = ("E2 FAIL with E1/E3 passing -> the continuous episode is doing work beyond the clock; "
             "the full stack is the owner's call and the triple alone is not")
    elif not e3:
        v = "E3 FAIL -> DO NOT FLIP"
    elif not e1:
        v = "E1 FAIL -> the per-pick boundary starves; DO NOT FLIP (E2's stock read is still reported)"
    else:
        v = "E4 FAIL -> a new failure reason; DO NOT FLIP"
    print(f"  {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
