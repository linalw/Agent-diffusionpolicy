"""P58 phase 3b report — cell A'': A' plus ONE free knob (`FRUIT_SUPPLY_BAND_MAX=4`).

    python3 logs/p58/A2_report.py

Reads `logs/p58/p3b/A2_<seed>.log` (the cell), `logs/p58/p3a/Ap_<seed>.log` (A',
the paired control) and phase 1's arms A/B (`logs/p58/p1/`), and prints the
endpoints registered in `logs/p58/PREREG_A_APRIME2.md` §2 (written before the
first run):

  E1  zero starved feed rounds: sel_gap = 120*(t_{k+1}-t_k) - ticks_k, no gap
      >= 169 anywhere; 139-141 is the +-1 print quantisation of a 140-tick
      boundary and is NOT a failure (the A' literal `<= 141` bar is replaced).
      The starved-round count is reported, with each event's mechanism.
  E2  pooled `on_belt` median >= 8 AND every run's final cumulative `skipped`
      <= 60.
  E3  `window >= 1` at 45/45 selections.
  E4  no failure reason outside phase-1 arm A + the P43/P54 baseline (113's
      normalisation); reported also against A''s own difference from A'.
  P1-P4 the registered predictions (the cap-binds mechanism check).

Reported, never gated: the `window` distribution (the object the cap moves),
placed counts with the arm split, wall/pick and the simulated span.

Read-only: it opens logs and prints. No state, no store, no `configs/`.
"""

from __future__ import annotations

import glob
import importlib.util
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ap", os.path.join(HERE, "Ap_report.py"))
ap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ap)  # reuse the A' parser/normaliser verbatim

CELL_DIR = "logs/p58/p3b"
CTRL_DIR = "logs/p58/p3a"          # A' — the paired control
P1_DIR = "logs/p58/p1"             # phase 1 arms A (control) / B (stack)


def load(directory: str, pattern: str) -> dict[int, dict]:
    out = {}
    for path in sorted(glob.glob(os.path.join(directory, pattern))):
        stem = os.path.basename(path)[:-4]
        seed = stem.rsplit("_", 1)[-1]
        if seed.isdigit():
            out[int(seed)] = ap.parse(path)
    return out


def fm(x, nd=1):
    return "n/a" if x is None else f"{x:.{nd}f}"


def med(vals):
    return st.median(vals) if vals else None


def wdist(vals):
    return {k: sum(1 for v in vals if v == k) for k in sorted(set(vals))}


def main() -> int:
    import argparse
    apx = argparse.ArgumentParser()
    apx.add_argument("--cell-dir", default=CELL_DIR,
                     help="cell A'' logs (default logs/p58/p3b)")
    apx.add_argument("--pattern", default="A2_*.log")
    args = apx.parse_args()
    cell = load(args.cell_dir, args.pattern)
    apr = load(CTRL_DIR, "Ap_*.log")
    ctrl = load(P1_DIR, "A_*.log")
    stack = load(P1_DIR, "B_*.log")
    seeds = sorted(cell)
    print("# P58 phase 3b report — cell A'': A' + FRUIT_SUPPLY_BAND_MAX=3 -> 4")
    print(f"# cell {args.cell_dir} seeds {seeds} logs {len(cell)}  |  "
          f"A' (paired control) {sorted(apr)}  |  phase-1 A {sorted(ctrl)}  |  "
          f"phase-1 B {sorted(stack)}")
    if not seeds:
        print("no A2_<seed>.log files")
        return 2

    # ------------------------------------------------------------- runs table --
    print("\n== the runs (unit = one pick = one `[rl] episode ... success=` row) ==")
    for seed in seeds:
        p = cell[seed]
        rows, bed = p["rows"], p["bed"]
        placed = sum(1 for r in rows if r["placed"])
        ln = sum(1 for r in rows if r["arm"] == "left")
        ro = sum(1 for r in rows if r["arm"] == "right")
        lok = sum(1 for r in rows if r["arm"] == "left" and r["placed"])
        rok = sum(1 for r in rows if r["arm"] == "right" and r["placed"])
        g = ap.sel_gaps(p)
        print(f"  A'' seed {str(seed):>3s}: picks={len(rows):2d} placed={placed:2d} "
              f"(left {lok}/{ln}, right {rok}/{ro}) bed_rows={len(bed):2d} "
              f"feed_rows={len(p['feed']):2d} cont_rows={p['cont_rows']} "
              f"on_belt med {fm(med([b['on_belt'] for b in bed]), 0)} "
              f"skipped_final {bed[-1]['skipped'] if bed else 'n/a'} "
              f"gap max {max(g) if g else 'n/a'} wall={fm(p['wall'])}s "
              f"ticks={sum(r['ticks'] for r in rows)}"
              + ("  WEDGED (no wall row)" if p["wedged"] else "")
              + (f"  starved_reset={p['starved_reset']}" if p["starved_reset"] else ""))
    for label, table in (("A' (BAND_MAX=3)", apr), ("phase-1 A (no triple)", ctrl),
                         ("phase-1 B (stack, cont)", stack)):
        for seed in sorted(table):
            p = table[seed]
            rows, bed = p["rows"], p["bed"]
            g = ap.sel_gaps(p)
            print(f"  [{label}] seed {str(seed):>3s}: picks={len(rows):2d} "
                  f"placed={sum(1 for r in rows if r['placed']):2d} "
                  f"on_belt med {fm(med([b['on_belt'] for b in bed]), 0)} "
                  f"skipped_final {bed[-1]['skipped'] if bed else 'n/a'} "
                  f"gap max {(max(g) if g else 'n/a') if p['cont_rows'] == 0 else 'n/a (cont)'} "
                  f"wall={fm(p['wall'])}s")

    # --------------------------------------------- manipulation / construction --
    print("\n== manipulation + construction check (PREREG §1.1, G2, G4) ==")
    for seed in seeds:
        p = cell[seed]
        print(f"  A'' seed {str(seed):>3s}: {p['env_ready']}")
        print(f"                   {p['trigger']}")
    g2 = any(cell[s]["cont_rows"] for s in seeds)
    print(f"  G2 [cont] rows in a log (not the shipped interface): "
          f"{'FIRES' if g2 else 'does not fire'} "
          f"({ {s: cell[s]['cont_rows'] for s in seeds} })")
    g4 = any("FRUIT_SUPPLY_TARGET_FROM" in open(cell[s]["path"], errors="ignore").read()
             for s in seeds)
    print(f"  G4 FRUIT_SUPPLY_TARGET_FROM in a log (two variables): "
          f"{'FIRES' if g4 else 'does not fire'}")

    print("\n== supply provenance (PREREG §2, read-only; the A' check verbatim) ==")
    ok_prov = True
    for seed in seeds:
        p = cell[seed]
        s = p["supply"] or "MISSING"
        patch = "patch=on" in s
        grades = "grades=A:0.375,B:0.375,C:0.25" in s
        n_bed, n_feed = len(p["bed"]), len(p["feed"])
        ok_prov &= patch and grades and n_bed == 15 and n_feed > 0
        print(f"  seed {str(seed):>3s}: patch=on {patch}  grades_balanced {grades}  "
              f"[bed-sel] rows {n_bed}/15  [feed] rows {n_feed}")
        print(f"                  supply: {s[:180]}")

    # --------------------------------------------------------------------- E1 ---
    print("\n== E1 zero starved feed rounds (PREREG §E1: no gap >= 169, starved count 0) ==")
    print("   sel_gap_k = 120*(t_{k+1}-t_k) - ticks_k ; 139-141 = a 140-tick boundary "
          "within the 2-dp print quantization (NOT a failure)")
    e1 = True
    for label, table in (("A''", cell), ("A'", apr), ("A ctl", ctrl)):
        for seed in sorted(table):
            g = ap.sel_gaps(table[seed])
            if not g:
                continue
            starve = [x for x in g if x >= 169]
            if label == "A''" and starve:
                e1 = False
            print(f"  {label:6s} seed {str(seed):>3s}: n={len(g)} min={min(g)} "
                  f"med={fm(med(g), 0)} max={max(g)}  in 139-141: "
                  f"{sum(1 for x in g if 139 <= x <= 141)}/{len(g)}  "
                  f">140: {sum(1 for x in g if x > 140)}  >=169 (a starved feed "
                  f"round): {len(starve)} {starve if starve else ''}")
    n_starve = sum(len([x for x in ap.sel_gaps(cell[s]) if x >= 169]) for s in seeds)
    n_bounds = sum(len(ap.sel_gaps(cell[s])) for s in seeds)
    print(f"  pooled: {n_starve} starved feed round(s) over {n_bounds} boundaries "
          f"({100.0 * n_starve / n_bounds if n_bounds else 0:.1f} %)  "
          f"[A': 1 over 42 = 2.4 %]")
    print(f"  E1  {'PASS' if (e1 and n_starve == 0) else 'FAIL'}")

    # the mechanism of any starve that did fire: pair each bed row with the
    # episode that follows it, then read the *next* bed row (the retried one).
    for seed in seeds:
        p = cell[seed]
        seq = p["events"]
        for k in range(len(seq) - 1):
            if seq[k][0] != "bed" or seq[k + 1][0] != "ep":
                continue
            ep = seq[k + 1][1]
            nxt = None
            for j in range(k + 1, len(seq)):
                if seq[j][0] == "bed":
                    nxt = seq[j][1]
                    break
            if nxt is None:
                continue
            gap = int(round(120.0 * (nxt["t"] - seq[k][1]["t"]) - ep["ticks"]))
            if gap >= 169:
                b = seq[k][1]
                print(f"  STARVE seed {str(seed)} boundary {b['attempt']}->{nxt['attempt']}: "
                      f"gap {gap} ticks ({gap / 120.0:.2f} s)")
                print(f"    preceding selection: on_belt={b['on_belt']} live={b['live']} "
                      f"admitted={b['admitted']} window={b['window']} pick={b['pick']} "
                      f"skipped={b['skipped']}")
                print(f"    starved pick      : {ep['index']} {ep['category']} "
                      f"d={ep['diameter']}cm arm={ep['arm']} ticks={ep['ticks']}")
                print(f"    next selection    : on_belt={nxt['on_belt']} live={nxt['live']} "
                      f"admitted={nxt['admitted']} window={nxt['window']} pick={nxt['pick']} "
                      f"skipped={nxt['skipped']}")

    # --------------------------------------------------------------------- E2 ---
    print("\n== E2 the stock and the scheduler (PREREG §2 E2) ==")
    print("   bar: pooled `on_belt` median >= 8  AND  every run's final cumulative `skipped` <= 60")
    pooled_on = [b["on_belt"] for s in seeds for b in cell[s]["bed"]]
    per_run_on = {s: med([b["on_belt"] for b in cell[s]["bed"]]) for s in seeds}
    per_run_sk = {s: (cell[s]["bed"][-1]["skipped"] if cell[s]["bed"] else None) for s in seeds}
    e2_on = (med(pooled_on) or 0) >= 8
    e2_sk = all(v is not None and v <= 60 for v in per_run_sk.values())
    e2 = e2_on and e2_sk
    for label, table in (("A''", cell), ("A'", apr), ("phase-1 A", ctrl), ("phase-1 B", stack)):
        on = [b["on_belt"] for s in sorted(table) for b in table[s]["bed"]]
        sk = {s: (table[s]["bed"][-1]["skipped"] if table[s]["bed"] else None)
              for s in sorted(table)}
        print(f"  {label:10s}: on_belt pooled med {fm(med(on), 1)} (mean "
              f"{fm(sum(on) / len(on) if on else None, 2)}) per-run "
              f"{({s: round(v, 1) for s, v in per_run_on.items()} if label == 'A''' else '')}"
              f"  skipped_final {sk}")
    print(f"  E2a on_belt median >= 8 : {'PASS' if e2_on else 'FAIL'}  "
          f"({fm(med(pooled_on), 1)}; per run "
          f"{ {s: round(v, 1) for s, v in per_run_on.items()} })")
    print(f"  E2b every run skipped <= 60: {'PASS' if e2_sk else 'FAIL'}  ({per_run_sk})")
    print(f"  E2  {'PASS' if e2 else 'FAIL'}")

    # --------------------------------------------------------------------- E3 ---
    print("\n== E3 window>=1 at every selection (PREREG §2 E3: 45/45) ==")
    pooled_win = [b["window"] for s in seeds for b in cell[s]["bed"]]
    n_win = sum(1 for w in pooled_win if w >= 1)
    e3 = n_win == 45
    print(f"  A'': window>=1 {n_win}/{len(pooled_win)}  distribution {wdist(pooled_win)}  "
          f"mean {fm(sum(pooled_win) / len(pooled_win) if pooled_win else None, 2)}  "
          f"window==1 at {sum(1 for w in pooled_win if w == 1)}/{len(pooled_win)}  "
          f"max {max(pooled_win) if pooled_win else 'n/a'}")
    for seed in seeds:
        w = [b["window"] for b in cell[seed]["bed"]]
        print(f"    seed {str(seed):>3s}: {wdist(w)}  mean "
              f"{fm(sum(w) / len(w) if w else None, 2)}")
    for label, table in (("A' (BAND_MAX=3)", apr), ("phase-1 A", ctrl), ("phase-1 B", stack)):
        w = [b["window"] for s in sorted(table) for b in table[s]["bed"]]
        print(f"  {label:20s}: window>=1 {sum(1 for x in w if x >= 1)}/{len(w)}  "
              f"distribution {wdist(w)}  mean {fm(sum(w) / len(w) if w else None, 2)}  "
              f"window==1 at {sum(1 for x in w if x == 1)}/{len(w)}  "
              f"max {max(w) if w else 'n/a'}")
    print(f"  E3  {'PASS' if e3 else 'FAIL'}")

    # --------------------------------------------------------------------- E4 ---
    print("\n== E4 no new failure reason (113's normalisation; PREREG §2 E4) ==")
    ra2 = ap.reasons_of([r for s in seeds for r in cell[s]["rows"]])
    rap = ap.reasons_of([r for s in sorted(apr) for r in apr[s]["rows"]])
    rctl = ap.reasons_of([r for s in sorted(ctrl) for r in ctrl[s]["rows"]])
    baseline = set()
    for root in ("logs/p43/p3", "logs/p54/p1"):
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            if name.endswith(".log"):
                baseline |= ap.reasons_of(ap.parse(os.path.join(root, name))["rows"])
    new = sorted(ra2 - (rctl | baseline))
    print(f"  A'' keys ({len(ra2)}):")
    for k in sorted(ra2):
        print(f"    - {k[:200]}")
    print(f"  control (phase-1 A) keys: {len(rctl)}  |  P43/P54 baseline keys: {len(baseline)}")
    print(f"  NEW in A'' (vs phase-1 A + baseline): {new or 'none'}")
    print(f"  A'' keys not in A' (the knob's own signature): {sorted(ra2 - rap) or 'none'}")
    print(f"  A' keys not in A'': {sorted(rap - ra2) or 'none'}")
    print(f"  missing in A'' (vs phase-1 A): {sorted(rctl - ra2) or 'none'}")
    fa2 = ap.fragments_of([r for s in seeds for r in cell[s]["rows"]])
    fap = ap.fragments_of([r for s in sorted(apr) for r in apr[s]["rows"]])
    print(f"  A'' fragments: {sorted(fa2)}")
    print(f"  A'' fragments not in A': {sorted(fa2 - fap) or 'none'}")
    e4 = not new
    print(f"  E4  {'PASS' if e4 else 'FAIL'}")

    # --------------------------------------------------------- reported: placed --
    print("\n== reported only: the placed count (branches; NO rate claim) ==")
    tot = sum(1 for s in seeds for r in cell[s]["rows"] if r["placed"])
    n = sum(len(cell[s]["rows"]) for s in seeds)
    lok = sum(1 for s in seeds for r in cell[s]["rows"] if r["arm"] == "left" and r["placed"])
    ln = sum(1 for s in seeds for r in cell[s]["rows"] if r["arm"] == "left")
    rok = sum(1 for s in seeds for r in cell[s]["rows"] if r["arm"] == "right" and r["placed"])
    rn = sum(1 for s in seeds for r in cell[s]["rows"] if r["arm"] == "right")
    print(f"  A'': placed {tot}/{n} (left {lok}/{ln}, right {rok}/{rn})")
    for s in seeds:
        rows = cell[s]["rows"]
        print(f"    seed {str(s):>3s}: {sum(1 for r in rows if r['placed'])}/{len(rows)} "
              f"(left {sum(1 for r in rows if r['arm'] == 'left' and r['placed'])}"
              f"/{sum(1 for r in rows if r['arm'] == 'left')}, "
              f"right {sum(1 for r in rows if r['arm'] == 'right' and r['placed'])}"
              f"/{sum(1 for r in rows if r['arm'] == 'right')})")
    for label, table in (("A' (BAND_MAX=3)", apr), ("phase-1 control", ctrl),
                         ("phase-1 stack", stack)):
        t = sum(1 for s in table for r in table[s]["rows"] if r["placed"])
        m = sum(len(table[s]["rows"]) for s in table)
        lo = sum(1 for s in table for r in table[s]["rows"] if r["arm"] == "left")
        rok2 = sum(1 for s in table for r in table[s]["rows"]
                   if r["arm"] == "right" and r["placed"])
        rn2 = sum(1 for s in table for r in table[s]["rows"] if r["arm"] == "right")
        print(f"  {label:20s}: placed {t}/{m}  (right {rok2}/{rn2}, left {t - rok2}/{lo})")

    # ----------------------------------------------------------- reported: wall --
    print("\n== reported only: the wall per pick and the simulated span ==")
    walls = [cell[s]["wall"] for s in seeds]
    picks = [len(cell[s]["rows"]) for s in seeds]
    ticks = [sum(r["ticks"] for r in cell[s]["rows"]) for s in seeds]
    if all(w is not None for w in walls) and all(picks):
        print(f"  A'' walls {[round(w) for w in walls]}s  per pick "
              f"{[round(w / p, 1) for w, p in zip(walls, picks)]}  pooled "
              f"{sum(walls):.0f}s / {sum(picks)} = {sum(walls) / sum(picks):.2f} s/pick  "
              f"ticks/pick {[round(t / p) for t, p in zip(ticks, picks)]} "
              f"pooled {sum(ticks) / sum(picks):.0f}")
    for label, table in (("A' (BAND_MAX=3)", apr), ("phase-1 control", ctrl),
                         ("phase-1 stack", stack)):
        w = [table[s]["wall"] for s in sorted(table)]
        p = [len(table[s]["rows"]) for s in sorted(table)]
        t = [sum(r["ticks"] for r in table[s]["rows"]) for s in sorted(table)]
        if all(x is not None for x in w):
            print(f"  {label:20s}: {sum(w):.0f}s / {sum(p)} = {sum(w) / sum(p):.2f} s/pick  "
                  f"ticks/pick {round(sum(t) / sum(p))}")

    # ---------------------------------------- reported: admitted / lag / feed --
    print("\n== reported: the mechanism columns ==")
    for seed in seeds:
        bed = cell[seed]["bed"]
        if not bed:
            continue
        print(f"  seed {str(seed):>3s}: admitted med {fm(med([b['admitted'] for b in bed]), 0)} "
              f"(mean {fm(sum(b['admitted'] for b in bed) / len(bed), 2)}) "
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

    # ----------------------------------------------- registered predictions P1-P4 --
    print("\n== registered predictions (PREREG §3) ==")
    p1 = (max(pooled_win) >= 4) and (sum(pooled_win) / len(pooled_win) > 2.02)
    print(f"  P1 the cap binds: max(window) {max(pooled_win) if pooled_win else 'n/a'} >= 4 "
          f"and mean {fm(sum(pooled_win) / len(pooled_win) if pooled_win else None, 2)} "
          f"> A' 2.02 : {'HOLDS' if p1 else 'FAILS (the cap is not the binding term)'}")
    p2 = n_starve == 0
    print(f"  P2 starves 1/42 -> 0/42 : {'HOLDS' if p2 else 'FAILS'} ({n_starve}/{n_bounds})")
    p3on = med(pooled_on) is not None and 9 <= med(pooled_on) <= 11
    print(f"  P3 no over-stock: on_belt median in 9-11 ({fm(med(pooled_on), 1)}) "
          f"and skipped <= 60 : {'HOLDS' if (p3on and e2_sk) else 'DOES NOT FULLY HOLD'}")
    p4 = (sum(walls) / sum(picks) <= 35.1) if (all(w is not None for w in walls) and sum(picks)) else False
    print(f"  P4 wall <= 35.1 s/pick (A' 34.07 + 3 %) : "
          f"{'HOLDS' if p4 else 'FAILS'} "
          f"({(sum(walls) / sum(picks)) if (all(w is not None for w in walls) and sum(picks)) else float('nan'):.2f})")

    # ---------------------------------------------------------------- verdict --
    print("\n== verdict ==")
    print(f"  E1 {'PASS' if (e1 and n_starve == 0) else 'FAIL'} | "
          f"E2 {'PASS' if e2 else 'FAIL'} (on_belt {'PASS' if e2_on else 'FAIL'}, "
          f"skipped {'PASS' if e2_sk else 'FAIL'}) | "
          f"E3 {'PASS' if e3 else 'FAIL'} | E4 {'PASS' if e4 else 'FAIL'} | "
          f"supply provenance {'OK' if ok_prov else 'CHECK'} | "
          f"G2 {'FIRES' if g2 else 'clear'} | G4 {'FIRES' if g4 else 'clear'}")
    if not e2:
        v = ("E2 FAIL -> `on_belt`/`skipped` degraded: the cap raise is buying the window "
             "by over-stocking. STOP (PREREG §4).")
    elif e1 and n_starve == 0 and e2 and e3 and e4:
        v = ("E1-E4 PASS -> the triple + BAND_MAX=4 is the FLIPPABLE unit for `direct` "
             "(the continuous episode is not load-bearing and the boundary is free at "
             "the higher ceiling)")
    elif not e1:
        v = ("E1 FAIL -> a starve remains; report its mechanism and DO NOT FLIP "
             "(the starve is not the ceiling's)")
    elif not e3:
        v = "E3 FAIL -> DO NOT FLIP"
    else:
        v = "E4 FAIL -> a new failure reason; DO NOT FLIP"
    print(f"  {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
