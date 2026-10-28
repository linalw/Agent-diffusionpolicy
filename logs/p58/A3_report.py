"""P58 phase 3c report — cell A‴: the DECIDER (`FRUIT_SUPPLY_BAND_INTERLOCK=0`).

    python3 logs/p58/A3_report.py

Reads `logs/p58/p3c/A3_<seed>.log` (the cell), the same-family controls
`logs/p58/p3a/Ap_<seed>.log` (A′, triple at `BAND_MAX=3`),
`logs/p58/p3b/A2_<seed>.log` (A″, triple at `BAND_MAX=4`) and phase 1's arm A
(`logs/p58/p1/A_<seed>.log`, the shipped line with no clock pair) / arm B (the
full stack), and prints the endpoints registered in
`logs/p58/PREREG_A_APRIME3.md` §2 (written before the first run):

  E1  zero starved feed rounds: sel_gap = 120*(t_{k+1}-t_k) - ticks_k, no gap
      >= 169 anywhere; 139-141 is the ±1 print quantisation of a 140-tick
      boundary and is NOT a failure. The starved-round count is reported with
      each event's mechanism, and `starved_reset` (the reset's own retry path)
      is reported beside it, not pooled into it.
  E2  every run's final cumulative `skipped` <= 60 AND pooled `on_belt` median
      >= 8 — with the per-block identity `on_belt = admitted + below_window`
      verified as the instrument check (Oracle 1: `on_belt` alone is not the
      stock endpoint), and `admitted` median printed beside it.
  E3  `window >= 1` at 45/45 AND the composition: pooled `window` mean >= 2.38,
      `window == 1` <= 9/45, and the below-window (past-station) share from the
      `[bed-sel]` candidate rows, per block and pooled.
  E4  no failure reason outside phase-1 arm A + the P43/P54 baseline + A′ + A″
      (113's normalisation); reported also against A‴'s own difference from A″.
  P1-P4 the registered predictions (mechanism attribution, not gates).

Reported, never gated: the `window` distribution, placed counts with the arm
split, wall/pick, the simulated span, `[feed]` rows, admitted/lag/live.

Read-only: it opens logs and prints. No state, no store, no `configs/`.
"""

from __future__ import annotations

import glob
import importlib.util
import os
import re
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ap", os.path.join(HERE, "Ap_report.py"))
ap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ap)  # reuse the A' parser/normaliser verbatim

CELL_DIR = "logs/p58/p3c"
APRIME_DIR = "logs/p58/p3a"        # A'   — paired control at BAND_MAX=3
ADPRIME_DIR = "logs/p58/p3b"       # A''  — paired control at BAND_MAX=4
P1_DIR = "logs/p58/p1"             # phase 1 arms A (shipped) / B (stack)

#: a `[bed-sel]` candidate row: `[fruit] [bed-sel]   pear  along=+0.559 x=... -> chosen`
CAND = re.compile(r"\[bed-sel\]\s+(\S+)\s+along=([-+0-9.]+)\s+x=([-+0-9.]+)"
                  r".*?->\s*(.*)$")
ATTEMPT = re.compile(r"\[bed-sel\] attempt (\d+)")


def fm(x, nd=1):
    return "n/a" if x is None else f"{x:.{nd}f}"


def med(vals):
    return st.median(vals) if vals else None


def wdist(vals):
    return {k: sum(1 for v in vals if v == k) for k in sorted(set(vals))}


def blocks(path: str) -> list[dict]:
    """One entry per `[bed-sel] attempt` block: its candidate rows and reasons.

    Aligned 1:1 with `Ap_report.parse(path)["bed"]` (same file, same order) —
    the report asserts that alignment before using it.
    """
    out: list[dict] = []
    cur = None
    for line in open(path, encoding="utf-8", errors="ignore"):
        if "[bed-sel]" not in line:
            continue
        if ATTEMPT.search(line):
            cur = {"cands": [], "below_window": 0, "below_catch": 0,
                   "usable": 0, "chosen": 0, "off_belt": 0, "above_belt": 0}
            out.append(cur)
            continue
        if cur is None:
            continue
        m = CAND.search(line)
        if not m:
            continue
        reason = m.group(4).strip()
        cur["cands"].append((m.group(1), float(m.group(2)), reason))
        if reason.startswith("below window"):
            cur["below_window"] += 1
        elif reason.startswith("below catch floor"):
            cur["below_catch"] += 1
        elif reason.startswith("usable"):
            cur["usable"] += 1
        elif reason.startswith("chosen"):
            cur["chosen"] += 1
        elif reason.startswith("above belt"):
            # on the raised output conveyor / stacked: counted in `on_belt`
            # (the census's on-belt total) but not a below-window body, so it is
            # the third term of the identity `on_belt = admitted + below + above`.
            cur["above_belt"] += 1
        elif reason.startswith("off belt"):
            cur["off_belt"] += 1
    return out


def composition(table: dict[int, dict]) -> dict:
    """Pooled + per-run below-window census and the `on_belt` identity check."""
    tot_blocks = tot_below = tot_cands = tot_above = 0
    identity_bad: list[str] = []
    per_run = {}
    for seed in sorted(table):
        p = table[seed]
        bl = blocks(p["path"])
        assert len(bl) == len(p["bed"]), (
            f"{p['path']}: {len(bl)} blocks vs {len(p['bed'])} attempt rows")
        below = sum(b["below_window"] for b in bl)
        cands = sum(len(b["cands"]) for b in bl)
        for b, row in zip(bl, p["bed"]):
            if row["on_belt"] != (row["admitted"] + b["below_window"]
                                  + b["above_belt"]):
                identity_bad.append(
                    f"seed {seed} attempt {row['attempt']}: on_belt "
                    f"{row['on_belt']} != admitted {row['admitted']} + below "
                    f"{b['below_window']} + above {b['above_belt']}")
        tot_blocks += len(bl)
        tot_below += below
        tot_cands += cands
        tot_above += sum(b["above_belt"] for b in bl)
        per_run[seed] = {"blocks": len(bl), "below": below, "cands": cands,
                         "per_block": below / len(bl) if bl else None,
                         "share_of_cands": below / cands if cands else None,
                         "chosen": sum(b["chosen"] for b in bl)}
    return {"per_run": per_run, "blocks": tot_blocks, "below": tot_below,
            "cands": tot_cands, "above": tot_above,
            "per_block": tot_below / tot_blocks if tot_blocks else None,
            "share_of_cands": tot_below / tot_cands if tot_cands else None,
            "identity_bad": identity_bad}


def load(directory: str, pattern: str) -> dict[int, dict]:
    out = {}
    for path in sorted(glob.glob(os.path.join(directory, pattern))):
        stem = os.path.basename(path)[:-4]
        seed = stem.rsplit("_", 1)[-1]
        if seed.isdigit():
            out[int(seed)] = ap.parse(path)
    return out


def main() -> int:
    cell = load(CELL_DIR, "A3_*.log")
    apr = load(APRIME_DIR, "Ap_*.log")
    adpr = load(ADPRIME_DIR, "A2_*.log")
    ctrl = load(P1_DIR, "A_*.log")
    stack = load(P1_DIR, "B_*.log")
    seeds = sorted(cell)
    print("# P58 phase 3c report — cell A''': A' with FRUIT_SUPPLY_BAND_INTERLOCK 1 -> 0")
    print("# (the clock pair FRUIT_FEED_CADENCE=1 + FRUIT_DIRECT_FEED=1, shipped "
          "station-window pacing at queue_max=6)")
    print(f"# cell {CELL_DIR} seeds {seeds} logs {len(cell)}  |  A' {sorted(apr)}  |  "
          f"A'' {sorted(adpr)}  |  phase-1 A {sorted(ctrl)}  |  phase-1 B {sorted(stack)}")
    if not seeds:
        print("no A3_<seed>.log files")
        return 2

    # ------------------------------------------------------------- runs table --
    print("\n== the runs (unit = one pick = one `[rl] episode ... success=` row) ==")
    for seed in seeds:
        p = cell[seed]
        rows, bed = p["rows"], p["bed"]
        g = ap.sel_gaps(p)
        lok = sum(1 for r in rows if r["arm"] == "left" and r["placed"])
        ln = sum(1 for r in rows if r["arm"] == "left")
        rok = sum(1 for r in rows if r["arm"] == "right" and r["placed"])
        rn = sum(1 for r in rows if r["arm"] == "right")
        print(f"  A''' seed {str(seed):>3s}: picks={len(rows):2d} "
              f"placed={sum(1 for r in rows if r['placed']):2d} "
              f"(left {lok}/{ln}, right {rok}/{rn}) bed_rows={len(bed):2d} "
              f"feed_rows={len(p['feed']):2d} cont_rows={p['cont_rows']} "
              f"on_belt med {fm(med([b['on_belt'] for b in bed]), 0)} "
              f"admitted med {fm(med([b['admitted'] for b in bed]), 0)} "
              f"skipped_final {bed[-1]['skipped'] if bed else 'n/a'} "
              f"gap max {max(g) if g else 'n/a'} wall={fm(p['wall'])}s "
              f"ticks={sum(r['ticks'] for r in rows)}"
              + ("  WEDGED (no wall row)" if p["wedged"] else "")
              + (f"  starved_reset={p['starved_reset']}" if p["starved_reset"] else ""))
    for label, table in (("A' (interlock 1, cap 3)", apr),
                         ("A'' (interlock 1, cap 4)", adpr),
                         ("phase-1 A (shipped, no pair)", ctrl),
                         ("phase-1 B (stack)", stack)):
        for seed in sorted(table):
            p = table[seed]
            rows, bed = p["rows"], p["bed"]
            g = ap.sel_gaps(p)
            print(f"  [{label}] seed {str(seed):>3s}: picks={len(rows):2d} "
                  f"placed={sum(1 for r in rows if r['placed']):2d} "
                  f"on_belt med {fm(med([b['on_belt'] for b in bed]), 0)} "
                  f"admitted med {fm(med([b['admitted'] for b in bed]), 0)} "
                  f"skipped_final {bed[-1]['skipped'] if bed else 'n/a'} "
                  f"gap max {(max(g) if g else 'n/a') if p['cont_rows'] == 0 else 'n/a (cont)'} "
                  f"wall={fm(p['wall'])}s")

    # --------------------------------------------- manipulation / construction --
    print("\n== manipulation + construction check (PREREG §1.1, G2, G4) ==")
    for seed in seeds:
        p = cell[seed]
        print(f"  A''' seed {str(seed):>3s}: {p['env_ready']}")
        print(f"                   {p['trigger']}")
    g2 = any(cell[s]["cont_rows"] for s in seeds)
    print(f"  G2 [cont] rows in a log (not the shipped interface): "
          f"{'FIRES' if g2 else 'does not fire'} "
          f"({ {s: cell[s]['cont_rows'] for s in seeds} })")
    g4 = any("FRUIT_SUPPLY_TARGET_FROM" in open(cell[s]["path"], errors="ignore").read()
             for s in seeds)
    print(f"  G4 FRUIT_SUPPLY_TARGET_FROM in a log (two variables): "
          f"{'FIRES' if g4 else 'does not fire'}")
    band = any("FRUIT_SUPPLY_BAND_MAX" in open(cell[s]["path"], errors="ignore").read()
               for s in seeds)
    print(f"  FRUIT_SUPPLY_BAND_MAX mentioned in a log (inert off; registered "
          f"unset): {'YES <-- check' if band else 'no'}")

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
    print("\n== E1 starved feed rounds (PREREG §E1: no gap >= 169, starved count 0) ==")
    print("   sel_gap_k = 120*(t_{k+1}-t_k) - ticks_k ; 139-141 = a 140-tick boundary "
          "within the 2-dp print quantization (NOT a failure)")
    e1 = True
    for label, table in (("A'''", cell), ("A'", apr), ("A''", adpr), ("A ctl", ctrl)):
        for seed in sorted(table):
            g = ap.sel_gaps(table[seed])
            if not g:
                continue
            starve = [x for x in g if x >= 169]
            if label == "A'''" and starve:
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
          f"[A' 1/42 = 2.4 %; A'' 0/42; control 0/42]")
    n_reset = sum(cell[s]["starved_reset"] for s in seeds)
    print(f"  starved_reset (the reset's own retry path, NOT pooled into E1): "
          f"{n_reset} ({ {s: cell[s]['starved_reset'] for s in seeds} })")
    print(f"  E1  {'PASS' if (e1 and n_starve == 0) else 'FAIL'}")

    # the mechanism of any starve that did fire
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
    print("   bar: every run's final cumulative `skipped` <= 60  AND  pooled "
          "`on_belt` median >= 8")
    pooled_on = [b["on_belt"] for s in seeds for b in cell[s]["bed"]]
    per_run_on = {s: med([b["on_belt"] for b in cell[s]["bed"]]) for s in seeds}
    per_run_sk = {s: (cell[s]["bed"][-1]["skipped"] if cell[s]["bed"] else None) for s in seeds}
    e2_on = (med(pooled_on) or 0) >= 8
    e2_sk = all(v is not None and v <= 60 for v in per_run_sk.values())
    e2 = e2_on and e2_sk
    # the instrument check: on_belt == admitted + below_window, per block
    comp = composition(cell)
    print(f"  instrument check `on_belt = admitted + below_window + above_belt` "
          f"per block: "
          f"{'HOLDS on all ' + str(comp['blocks']) + ' blocks' if not comp['identity_bad'] else 'MISMATCHES'}")
    for bad in comp["identity_bad"][:6]:
        print(f"    MISMATCH {bad}")
    for label, table in (("A'''", cell), ("A'", apr), ("A''", adpr),
                         ("phase-1 A", ctrl), ("phase-1 B", stack)):
        on = [b["on_belt"] for s in sorted(table) for b in table[s]["bed"]]
        adm = [b["admitted"] for s in sorted(table) for b in table[s]["bed"]]
        sk = {s: (table[s]["bed"][-1]["skipped"] if table[s]["bed"] else None)
              for s in sorted(table)}
        print(f"  {label:12s}: on_belt pooled med {fm(med(on), 1)} (mean "
              f"{fm(sum(on) / len(on) if on else None, 2)})  admitted med "
              f"{fm(med(adm), 1)} (mean {fm(sum(adm) / len(adm) if adm else None, 2)})"
              f"  skipped_final {sk}"
              + (f"  per-run on_belt "
                 f"{ {s: round(v, 1) for s, v in per_run_on.items()} }"
                 if label == "A'''" else ""))
    e2a = f"on_belt median >= 8 : {'PASS' if e2_on else 'FAIL'}"
    print(f"  E2a {e2a}  ({fm(med(pooled_on), 1)}; per run "
          f"{ {s: round(v, 1) for s, v in per_run_on.items()} })")
    print(f"  E2b every run skipped <= 60: {'PASS' if e2_sk else 'FAIL'}  ({per_run_sk})")
    print(f"  E2  {'PASS' if e2 else 'FAIL'}")

    # --------------------------------------------------------------------- E3 ---
    print("\n== E3 window>=1 at every selection AND the composition (PREREG §2 E3) ==")
    pooled_win = [b["window"] for s in seeds for b in cell[s]["bed"]]
    n_win = sum(1 for w in pooled_win if w >= 1)
    e3_w = n_win == len(pooled_win) and len(pooled_win) == 45
    wmean = sum(pooled_win) / len(pooled_win) if pooled_win else None
    wone = sum(1 for w in pooled_win if w == 1)
    e3_mean = wmean is not None and wmean >= 2.38
    e3_one = wone <= 9
    for label, table in (("A'''", cell), ("A'", apr), ("A''", adpr),
                         ("phase-1 A", ctrl), ("phase-1 B", stack)):
        w = [b["window"] for s in sorted(table) for b in table[s]["bed"]]
        print(f"  {label:12s}: window>=1 {sum(1 for x in w if x >= 1)}/{len(w)}  "
              f"distribution {wdist(w)}  mean "
              f"{fm(sum(w) / len(w) if w else None, 2)}  window==1 at "
              f"{sum(1 for x in w if x == 1)}/{len(w)}  max {max(w) if w else 'n/a'}")
    for seed in seeds:
        w = [b["window"] for b in cell[seed]["bed"]]
        print(f"    A''' seed {str(seed):>3s}: {wdist(w)}  mean "
              f"{fm(sum(w) / len(w) if w else None, 2)}  window==1 at "
              f"{sum(1 for x in w if x == 1)}/{len(w)}")
    print(f"  E3a window>=1 at 45/45: {'PASS' if e3_w else 'FAIL'} ({n_win}/{len(pooled_win)})")
    print(f"  E3b window mean >= 2.38 (the cap-4 cell): "
          f"{'PASS' if e3_mean else 'FAIL'} ({fm(wmean, 2)})")
    print(f"  E3c window==1 <= 9/45: {'PASS' if e3_one else 'FAIL'} ({wone}/{len(pooled_win)})")
    e3 = e3_w and e3_mean and e3_one
    print(f"  E3  {'PASS' if e3 else 'FAIL'}")

    print("\n  -- the composition: below-window (past-station) `[bed-sel]` rows --")
    print("     per block = the block's rows whose reason contains 'below window'; "
          "pooled = total / blocks")
    rowsc = []
    for label, table in (("A''' (interlock 0)", cell), ("A' (cap 3)", apr),
                         ("A'' (cap 4)", adpr), ("phase-1 A", ctrl),
                         ("phase-1 B (stack)", stack)):
        c = composition(table)
        rowsc.append((label, c))
        per = c["per_run"]
        print(f"  {label:20s}: pooled {c['below']}/{c['blocks']} = "
              f"{fm(c['per_block'], 2)} per block  "
              f"({100.0 * (c['share_of_cands'] or 0):.1f} % of "
              f"{c['cands']} candidate rows)  per run "
              f"{ {s: round(v['per_block'], 2) for s, v in per.items()} }")
    print(f"  identity mismatches (all arms): "
          f"{sum(len(c['identity_bad']) for _, c in rowsc)}")

    # --------------------------------------------------------------------- E4 ---
    print("\n== E4 no new failure reason (113's normalisation; PREREG §2 E4) ==")
    r3 = ap.reasons_of([r for s in seeds for r in cell[s]["rows"]])
    r2 = ap.reasons_of([r for s in sorted(adpr) for r in adpr[s]["rows"]])
    r1 = ap.reasons_of([r for s in sorted(apr) for r in apr[s]["rows"]])
    rctl = ap.reasons_of([r for s in sorted(ctrl) for r in ctrl[s]["rows"]])
    baseline = set()
    for root in ("logs/p43/p3", "logs/p54/p1"):
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            if name.endswith(".log"):
                baseline |= ap.reasons_of(ap.parse(os.path.join(root, name))["rows"])
    new = sorted(r3 - (rctl | baseline | r1 | r2))
    print(f"  A''' keys ({len(r3)}):")
    for k in sorted(r3):
        print(f"    - {k[:200]}")
    print(f"  control (phase-1 A) keys: {len(rctl)}  |  P43/P54 baseline: {len(baseline)}"
          f"  |  A' {len(r1)}  |  A'' {len(r2)}")
    print(f"  NEW in A''' (vs all of the above): {new or 'none'}")
    print(f"  A''' keys not in A'' (this knob's own signature): {sorted(r3 - r2) or 'none'}")
    print(f"  A'' keys not in A''': {sorted(r2 - r3) or 'none'}")
    print(f"  missing in A''' (vs phase-1 A): {sorted(rctl - r3) or 'none'}")
    f3 = ap.fragments_of([r for s in seeds for r in cell[s]["rows"]])
    f2 = ap.fragments_of([r for s in sorted(adpr) for r in adpr[s]["rows"]])
    print(f"  A''' fragments: {sorted(f3)}")
    print(f"  A''' fragments not in A'': {sorted(f3 - f2) or 'none'}")
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
    print(f"  A''': placed {tot}/{n} (left {lok}/{ln}, right {rok}/{rn})")
    for s in seeds:
        rows = cell[s]["rows"]
        print(f"    seed {str(s):>3s}: {sum(1 for r in rows if r['placed'])}/{len(rows)} "
              f"(left {sum(1 for r in rows if r['arm'] == 'left' and r['placed'])}"
              f"/{sum(1 for r in rows if r['arm'] == 'left')}, "
              f"right {sum(1 for r in rows if r['arm'] == 'right' and r['placed'])}"
              f"/{sum(1 for r in rows if r['arm'] == 'right')})")
    for label, table in (("A' (cap 3)", apr), ("A'' (cap 4)", adpr),
                         ("phase-1 A", ctrl), ("phase-1 B", stack)):
        t = sum(1 for s in table for r in table[s]["rows"] if r["placed"])
        m = sum(len(table[s]["rows"]) for s in table)
        ro = sum(1 for s in table for r in table[s]["rows"] if r["arm"] == "right")
        rok2 = sum(1 for s in table for r in table[s]["rows"]
                   if r["arm"] == "right" and r["placed"])
        print(f"  {label:12s}: placed {t}/{m}  (right {rok2}/{ro}, left {t - rok2}/{m - ro})")

    # ----------------------------------------------------------- reported: wall --
    print("\n== reported only: the wall per pick and the simulated span ==")
    walls = [cell[s]["wall"] for s in seeds]
    picks = [len(cell[s]["rows"]) for s in seeds]
    ticks = [sum(r["ticks"] for r in cell[s]["rows"]) for s in seeds]
    wall_pp = None
    if all(w is not None for w in walls) and all(picks):
        wall_pp = sum(walls) / sum(picks)
        print(f"  A''' walls {[round(w) for w in walls]}s  per pick "
              f"{[round(w / p, 1) for w, p in zip(walls, picks)]}  pooled "
              f"{sum(walls):.0f}s / {sum(picks)} = {wall_pp:.2f} s/pick  "
              f"ticks/pick {[round(t / p) for t, p in zip(ticks, picks)]} "
              f"pooled {sum(ticks) / sum(picks):.0f}")
    for label, table in (("A' (cap 3)", apr), ("A'' (cap 4)", adpr),
                         ("phase-1 A", ctrl), ("phase-1 B", stack)):
        w = [table[s]["wall"] for s in sorted(table)]
        p = [len(table[s]["rows"]) for s in sorted(table)]
        t = [sum(r["ticks"] for r in table[s]["rows"]) for s in sorted(table)]
        if all(x is not None for x in w):
            print(f"  {label:12s}: {sum(w):.0f}s / {sum(p)} = {sum(w) / sum(p):.2f} s/pick  "
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

    # ------------------------------- the mechanism: feeder rate + occupancy shape --
    print("\n== mechanism: the feeder rate and the occupancy shape (registered as "
          "reported) ==")
    print("   the release rate is the *same* across the clock-pair arms; what moves "
          "is where the bodies sit")
    REL = re.compile(r"released=([-+]\d+)")

    def feeder_rate(p):
        rel = sum(int(REL.search(l).group(1)) for l in
                  open(p["path"], errors="ignore")
                  if "[feed]" in l and REL.search(l))
        tk = sum(x["ticks"] for x in p["feed"])
        return rel, tk, (120.0 * rel / tk if tk else None)

    def occupancy(bl):
        """(station-window occ, catchable-band occ) at each selection instant.

        The station window is `_queue_depth`'s region (`along = -0.05..+0.45`,
        `FRUIT_QUEUE_MAX=6`); the catchable band is `_approach_depth`'s
        (`along = +0.35..spawn_y`, the interlock's region). Bodies on the raised
        output conveyor / stacked / fallen are **not** on the main belt and are
        excluded (the same way `_queue_depth` skips the output conveyors).
        """
        win, band = [], []
        for b in bl:
            w = bd = 0
            for _name, along, reason in b["cands"]:
                if reason.startswith(("off belt", "above belt", "below belt")):
                    continue
                if -0.05 <= along <= 0.45:
                    w += 1
                if 0.35 <= along <= 0.68:
                    bd += 1
            win.append(w)
            band.append(bd)
        return win, band

    for label, table in (("A''' (interlock 0)", cell), ("A' (cap 3)", apr),
                         ("A'' (cap 4)", adpr), ("phase-1 A", ctrl),
                         ("phase-1 B (stack)", stack)):
        rel = tk = 0
        rate = []
        win = []
        band = []
        for s in sorted(table):
            r, t, _x = feeder_rate(table[s])
            rel += r
            tk += t
            if _x is not None:
                rate.append(_x)
            w, b2 = occupancy(blocks(table[s]["path"]))
            win += w
            band += b2
        rate_all = 120.0 * rel / tk if tk else None
        print(f"  {label:20s}: releases {rel} over {tk} feed-ticks = "
              f"{fm(rate_all, 2)}/sim-s"
              + (f" (per run {[round(x, 2) for x in rate]})" if rate else
                 "  <-- the cadence does not run (no [feed] rows)")
              + f"  |  station-window occ med {fm(med(win), 0)} mean "
                f"{fm(sum(win) / len(win) if win else None, 2)} max "
                f"{max(win) if win else 'n/a'}  |  catchable band occ med "
                f"{fm(med(band), 0)} mean {fm(sum(band) / len(band) if band else None, 2)} "
                f"max {max(band) if band else 'n/a'}")
    for label, table in (("A'''", cell), ("A'", apr), ("A''", adpr),
                         ("phase-1 A", ctrl), ("phase-1 B", stack)):
        w = [b["window"] for s in sorted(table) for b in table[s]["bed"]]
        sd = st.pstdev(w) if len(w) > 1 else None
        print(f"  {label:12s}: window mean {fm(sum(w) / len(w) if w else None, 2)} "
              f"sd {fm(sd, 2)}  ==1 {sum(1 for x in w if x == 1)}/{len(w)}  "
              f">=3 {sum(1 for x in w if x >= 3)}/{len(w)}")

    def fisher(a: int, n1: int, c: int, n2: int) -> float:
        """Two-sided Fisher exact on [[a, n1-a], [c, n2-c]] (no scipy here)."""
        from math import comb
        tot, k = n1 + n2, a + c
        def p(x):
            return comb(n1, x) * comb(n2, k - x) / comb(tot, k)
        p0 = p(a)
        lo = max(0, k - n2)
        hi = min(n1, k)
        return sum(p(x) for x in range(lo, hi + 1) if p(x) <= p0 * 1.0000001)

    star = {label: sum(1 for s in table for g in ap.sel_gaps(table[s])
                       if g >= 169)
            for label, table in (("A'''", cell), ("A'", apr), ("A''", adpr),
                                 ("ctl", ctrl))}
    bounds = {label: sum(len(ap.sel_gaps(table[s])) for s in table)
              for label, table in (("A'''", cell), ("A'", apr), ("A''", adpr),
                                   ("ctl", ctrl))}
    s3, b3 = star["A'''"], bounds["A'''"]
    s2, b2 = star["A''"], bounds["A''"]
    s1, b1 = star["A'"], bounds["A'"]
    sc, bc = star["ctl"], bounds["ctl"]
    print(f"  boundary starves (>= 169 ticks): A''' {s3}/{b3}, A' {s1}/{b1}, "
          f"A'' {s2}/{b2}, control {sc}/{bc}")
    print(f"  Fisher exact (two-sided) A''' vs A'': p = {fisher(s3, b3, s2, b2):.4f}"
          f"   A''' vs A': p = {fisher(s3, b3, s1, b1):.4f}")
    waits = [int(round((g - 140) / 30)) for s in seeds for g in ap.sel_gaps(cell[s])
             if g >= 169]
    print(f"  wait length at the {s3} events, in 30-tick feed rounds (the reset's "
          f"loop): every gap is 140 + 30k -> k = {waits}")

    # ----------------------------------------------- registered predictions P1-P4 --
    print("\n== registered predictions (PREREG §3) ==")
    p1 = all(14 <= len(cell[s]["feed"]) <= 15 for s in seeds)
    print(f"  P1 the clock pair runs: [feed] rows "
          f"{ {s: len(cell[s]['feed']) for s in seeds} } in 14-15 : "
          f"{'HOLDS' if p1 else 'FAILS'}")
    p2 = sum(1 for s in seeds if (per_run_sk[s] or 0) > 39) >= 2
    print(f"  P2 the station window is the binding pacer: skipped "
          f"{ {s: per_run_sk[s] for s in seeds} }; > 39 in >= 2 runs : "
          f"{'HOLDS' if p2 else 'FAILS (the interlock is not load-bearing for the scheduler)'}")
    p3 = (comp["per_block"] is not None) and comp["per_block"] < 3.0
    p4 = wall_pp is not None and wall_pp <= 35.40
    p3s = "HOLDS" if p3 else "FAILS (the composition is not the interlock's)"
    print(f"  P3 the interlock owns the past-station composition: below-window "
          f"{fm(comp['per_block'], 2)} per block < 3.0 : {p3s}")
    print(f"  P4 wall/pick <= 35.40 s (A''): {'HOLDS' if p4 else 'FAILS'} "
          f"({fm(wall_pp, 2)})")

    # ---------------------------------------------------------------- verdict --
    print("\n== verdict (PREREG §4; the FIRST clause that applies decides) ==")
    print(f"  E1 {'PASS' if (e1 and n_starve == 0) else 'FAIL'} | "
          f"E2 {'PASS' if e2 else 'FAIL'} (on_belt {'PASS' if e2_on else 'FAIL'}, "
          f"skipped {'PASS' if e2_sk else 'FAIL'}) | "
          f"E3 {'PASS' if e3 else 'FAIL'} (window>=1 {n_win}/45, mean {fm(wmean, 2)}, "
          f"==1 {wone}/45) | E4 {'PASS' if e4 else 'FAIL'} | "
          f"supply provenance {'OK' if ok_prov else 'CHECK'} | "
          f"G2 {'FIRES' if g2 else 'clear'} | G4 {'FIRES' if g4 else 'clear'}")
    print(f"  below-window share {fm(comp['per_block'], 2)} per block "
          f"(A'' 6.24, A' 5.20, control 0.20)")
    allpass = (e1 and n_starve == 0 and e2 and e3 and e4 and not g2 and not g4)
    if allpass and (wmean or 0) >= 2.38:
        v = ("B1 -> the clock pair (FRUIT_FEED_CADENCE + FRUIT_DIRECT_FEED) is the "
             "FLIPPABLE unit for `direct`; the interlock stays OFF")
    elif (not e2) or n_starve >= 1:
        v = ("B2 -> the interlock is LOAD-BEARING; the triple (+ BAND_MAX=4) is the "
             "unit, with A''s one starve carried as a recorded deviation")
    elif e2 and n_starve == 0 and ((wmean or 0) < 2.38 or wone > 9):
        v = ("B3 -> E2 holds and no starve, but the composition does not reach the "
             "cap-4 cell: NO FLIP; report and stop")
    else:
        v = ("B3 (residual clause) -> NO FLIP; report and stop")
    print(f"  {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
