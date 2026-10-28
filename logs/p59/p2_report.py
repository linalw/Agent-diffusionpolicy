"""P59 phase 2 report — the two catch-margin arms (cap 5 / upstream edge 0.40).

    python3 logs/p59/p2_report.py

Reads `logs/p59/p2/{A,B}_<seed>.log` (the phase-2 arms) and the registered
controls, with the same composition arithmetic as `logs/p58/A3_report.py`
(which itself reuses `Ap_report.py`'s parser):

  * `logs/p58/p3b/A2_<seed>.log` — the cap-4 cell (the shipped profile's
    measured control: window 2.38, ==1 9/45, skipped 8/4/9, 0 starves);
  * `logs/p58/p1/A_<seed>.log`  — the pre-profile burst control (window 2.57
    pooled over 51 selections, ==1 4/45 over the three full runs).

Endpoints are `logs/p59/PREREG_P2.md` §"Endpoints" (written before the runs):

  E1 window mean >= 2.57 AND window==1 <= 4/45
  E2 zero starved feed rounds (sel_gap >= 169) in every run
  E3 final cumulative `skipped` <= 20 in every run
  E4 no new failure reason (scripts/113_rl_report.py's normalisation)
  E5 wall reported only

The reading rules of §"The reading rules" are applied verbatim: `placed` is the
summary line's parse (never the running counter); starvation is asserted from
the ABSENCE of `waiting for a candidate` / `no candidate` lines, never from
`gap_ticks_mean`; `supply_skipped` is not read as the drop counter; `on_belt`
is not read as a catch metric (`on_belt = admitted + below_window (+ above)`).

Read-only: it opens logs and prints. No state, no store, no `configs/`.
"""

from __future__ import annotations

import glob
import hashlib
import importlib.util
import os
import re
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
spec = importlib.util.spec_from_file_location(
    "a3", os.path.join(ROOT, "logs/p58/A3_report.py"))
a3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a3)          # brings Ap_report through as a3.ap
ap = a3.ap

P2_DIR = "logs/p59/p2"
CAP4_DIR = "logs/p58/p3b"            # A'' — the shipped profile's measured cell
BURST_DIR = "logs/p58/p1"            # pre-profile burst control
#: the physical catch floor: `_dynamic_select_floor()`'s 0.399 m — the upstream
#: edge of the only 0.281 m of belt the moving catch can actually draw from.
CATCH_FLOOR = 0.399

#: the arm's claim, as the row must print it (P59 gate-1 remediation row)
CLAIMS = {
    "A": ("band=on(5(explicit))(default)", "target_from=0.35(default)"),
    "B": ("band=on(4)(default)", "target_from=0.40(explicit)"),
}
STARVE_STRINGS = ("waiting for a candidate", "no candidate")


def fm(x, nd=1):
    return "n/a" if x is None else f"{x:.{nd}f}"


def med(vals):
    return st.median(vals) if vals else None


def wdist(vals):
    return {k: sum(1 for v in vals if v == k) for k in sorted(set(vals))}


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(directory, pattern):
    out = {}
    for path in sorted(glob.glob(os.path.join(directory, pattern))):
        stem = os.path.basename(path)[:-4]
        seed = stem.rsplit("_", 1)[-1]
        if seed.isdigit():
            out[int(seed)] = ap.parse(path)
    return out


def profile_row(path):
    """The `[supply] direct profile:` row (NOT the scatter-pool `[supply]` row)."""
    for line in open(path, encoding="utf-8", errors="ignore"):
        if "[supply] direct profile:" in line:
            return line.split("[supply]", 1)[1].strip()
    return None


def starve_lines(path):
    n = 0
    for line in open(path, encoding="utf-8", errors="ignore"):
        if any(s in line for s in STARVE_STRINGS):
            n += 1
    return n


def sel_gaps(p):
    return ap.sel_gaps(p)


def occupancy(bl, band_lo):
    """(station-window occ, catchable-band occ) at each selection instant."""
    win, band = [], []
    for b in bl:
        w = bd = 0
        for _name, along, reason in b["cands"]:
            if reason.startswith(("off belt", "above belt", "below belt")):
                continue
            if -0.05 <= along <= 0.45:
                w += 1
            if band_lo <= along <= 0.68:
                bd += 1
        win.append(w)
        band.append(bd)
    return win, band


def permutation_p(x, y, n=40000, seed=1):
    """Two-sided permutation test on the difference of means (Monte Carlo)."""
    import random
    r = random.Random(seed)
    obs = abs(sum(x) / len(x) - sum(y) / len(y))
    pool = list(x) + list(y)
    k = len(x)
    c = 0
    for _ in range(n):
        r.shuffle(pool)
        if abs(sum(pool[:k]) / k - sum(pool[k:]) / (len(pool) - k)) >= obs - 1e-12:
            c += 1
    return (c + 1) / (n + 1)


def fisher(a, n1, c, n2):
    from math import comb
    tot, k = n1 + n2, a + c

    def p(x):
        return comb(n1, x) * comb(n2, k - x) / comb(tot, k)

    p0 = p(a)
    lo, hi = max(0, k - n2), min(n1, k)
    return sum(p(x) for x in range(lo, hi + 1) if p(x) <= p0 * 1.0000001)


REL = re.compile(r"released=([-+]\d+)")


def feeder_rate(p):
    """`[feed]` deltas: releases and feed-ticks over the attempt slices."""
    rel = 0
    for line in open(p["path"], encoding="utf-8", errors="ignore"):
        if "[feed]" in line:
            m = REL.search(line)
            if m:
                rel += int(m.group(1))
    tk = sum(x["ticks"] for x in p["feed"])
    return rel, tk, (120.0 * rel / tk if tk else None)


def along_hist(table):
    """Where the live bodies sit at the selection instants (one candidate census).

    Bins: past the station (<0), just downstream of it (0..0.15), the
    not-yet-catchable approach (0.15..0.399), the catchable aperture
    (0.399..0.68), above the spawn (>0.68). Off-belt / raised-lane bodies are
    excluded (not on the main belt).
    """
    bins = [0, 0, 0, 0, 0]
    tot = 0
    for s in sorted(table):
        for b in a3.blocks(table[s]["path"]):
            for _name, along, reason in b["cands"]:
                if reason.startswith(("off belt", "above belt", "below belt")):
                    continue
                tot += 1
                if along < 0.0:
                    bins[0] += 1
                elif along < 0.15:
                    bins[1] += 1
                elif along < CATCH_FLOOR:
                    bins[2] += 1
                elif along <= 0.68:
                    bins[3] += 1
                else:
                    bins[4] += 1
    return bins, tot


def summary(table, band_lo):
    """Pooled endpoints for one arm/control table."""
    bed = [b for s in sorted(table) for b in table[s]["bed"]]
    rows = [r for s in sorted(table) for r in table[s]["rows"]]
    win = [b["window"] for b in bed]
    on = [b["on_belt"] for b in bed]
    adm = [b["admitted"] for b in bed]
    rel = tk = 0
    for s in sorted(table):
        r, t, _x = feeder_rate(table[s])
        rel += r
        tk += t
    comp = a3.composition(table)
    gaps = [g for s in sorted(table) for g in sel_gaps(table[s])]
    walls = [table[s]["wall"] for s in sorted(table)]
    picks = [len(table[s]["rows"]) for s in sorted(table)]
    ticks = [sum(r["ticks"] for r in table[s]["rows"]) for s in sorted(table)]
    occ_w, occ_b = [], []
    occ_c = []
    for s in sorted(table):
        w, b = occupancy(a3.blocks(table[s]["path"]), band_lo)
        _w2, c = occupancy(a3.blocks(table[s]["path"]), CATCH_FLOOR)
        occ_w += w
        occ_b += b
        occ_c += c
    return {
        "bed": bed, "rows": rows, "win": win, "on": on, "adm": adm,
        "comp": comp, "gaps": gaps,
        "releases": rel, "feed_ticks": tk,
        "feed_rate": (120.0 * rel / tk if tk else None),
        "lag": med([b["lag"] for b in bed]),
        "rebased": sum(b["rebased"] for b in bed),
        "dropped": sum(b["dropped"] for b in bed),
        "live": med([b["live"] for b in bed]),
        "starves": [g for g in gaps if g >= 169],
        "skipped": {s: (table[s]["bed"][-1]["skipped"]
                        if table[s]["bed"] else None) for s in sorted(table)},
        "placed": sum(1 for r in rows if r["placed"]), "n": len(rows),
        "wall": (sum(walls) / sum(picks)
                 if all(w is not None for w in walls) and sum(picks) else None),
        "ticks_per_pick": (sum(ticks) / sum(picks)) if sum(picks) else None,
        "occ_w": occ_w, "occ_b": occ_b, "occ_catch": occ_c,
    }


def line(label, S):
    win = S["win"]
    print(f"  {label:26s}: sel {len(win):2d}  window mean {fm(sum(win) / len(win) if win else None, 2)}  "
          f"==1 {sum(1 for x in win if x == 1):2d}/{len(win)}  "
          f">=3 {sum(1 for x in win if x >= 3):2d}  dist {wdist(win)}")
    print(f"  {'':26s}  on_belt med {fm(med(S['on']), 0)} (mean {fm(sum(S['on']) / len(S['on']) if S['on'] else None, 2)})  "
          f"admitted med {fm(med(S['adm']), 0)} (mean {fm(sum(S['adm']) / len(S['adm']) if S['adm'] else None, 2)})  "
          f"live med {fm(S['live'], 0)}  below-window {fm(S['comp']['per_block'], 2)}/block  "
          f"starves {len(S['starves'])}/{len(S['gaps'])}  skipped {S['skipped']}  "
          f"placed {S['placed']}/{S['n']}  wall/pick {fm(S['wall'], 2)}")
    print(f"  {'':26s}  feeder: releases {S['releases']} over {S['feed_ticks']} feed-ticks = "
          f"{fm(S['feed_rate'], 2)}/sim-s  lag med {fm(S['lag'], 2)}s  rebased {S['rebased']}  "
          f"dropped {fm(S['dropped'], 1)}s  station-window occ mean "
          f"{fm(sum(S['occ_w']) / len(S['occ_w']) if S['occ_w'] else None, 2)}  "
          f"interlock-band occ mean {fm(sum(S['occ_b']) / len(S['occ_b']) if S['occ_b'] else None, 2)}  "
          f"catchable-aperture occ mean "
          f"{fm(sum(S['occ_catch']) / len(S['occ_catch']) if S['occ_catch'] else None, 2)}  "
          f"sum(window) {sum(win)}")


def main() -> int:
    print("# P59 phase 2 report — the catch-margin arms (one variable each)")
    header = os.path.join(P2_DIR, "header.txt")
    if os.path.exists(header):
        for ln in open(header, encoding="utf-8", errors="ignore"):
            if ln.startswith("# tree") or ln.startswith("61da390a") or \
                    ln.startswith("1b1e5cdf") or ln.startswith("8ad8ddc8") or \
                    ln.startswith("c7461d41") or ln.startswith("abd2b5f1"):
                print("# " + ln.rstrip())
    after = os.path.join(P2_DIR, "tree_md5_after.txt")
    if os.path.exists(after):
        now = {ln.split()[1]: ln.split()[0]
               for ln in open(after, encoding="utf-8", errors="ignore") if ln.strip()}
        drift = [k for k, v in now.items()
                 if k in ("src/fruit_sorting/rl_env.py", "src/fruit_sorting/tasks.py",
                          "src/fruit_sorting/fruits.py",
                          "src/fruit_sorting/policy/trigger.py")
                 and v != {"src/fruit_sorting/rl_env.py": "1b1e5cdf32f3ccf93d94d8f5835d0a3b",
                           "src/fruit_sorting/tasks.py": "8ad8ddc8a13b6f4d9a96e84791dc04bb",
                           "src/fruit_sorting/fruits.py": "c7461d4104cf2c5f6c5a2daab80fbf32",
                           "src/fruit_sorting/policy/trigger.py": "b09d3cb2389a9f4884a748dbb3461b24"}[k]]
        print(f"# tree pins after the batch: {'STABLE' if not drift else 'DRIFT ' + str(drift)}")

    arms = {k: load(P2_DIR, f"{k}_*.log") for k in ("A", "B")}
    cap4 = load(CAP4_DIR, "A2_*.log")
    burst = load(BURST_DIR, "A_*.log")
    seeds = sorted(set(arms["A"]) | set(arms["B"]))
    print(f"# arms A (cap 5) {sorted(arms['A'])}  B (upstream 0.40) {sorted(arms['B'])}  "
          f"| control A'' {sorted(cap4)}  burst {sorted(burst)}")
    if not arms["A"] or not arms["B"]:
        print("missing arm logs")
        return 2

    # ------------------------------------------------------- the arm is what it claims --
    print("\n== the arm is what it claims (PREREG_P2 reading rule 5; stop if not) ==")
    bad = []
    for arm in ("A", "B"):
        for seed in sorted(arms[arm]):
            row = profile_row(arms[arm][seed]["path"]) or "MISSING"
            ok = all(tok in row for tok in CLAIMS[arm])
            ok &= "cadence=on(default)" in row and "feed=on(default)" in row
            if not ok:
                bad.append((arm, seed, row))
            print(f"  {arm} seed {str(seed):>3s}: {row}   -> {'OK' if ok else 'ARM MISMATCH'}")
    if bad:
        print("  STOP: the row does not name the arm's own variable.")
        return 3

    # --------------------------------------------------------------- the runs --
    print("\n== the runs (unit = one pick = one `[rl] episode ... success=` row) ==")
    for arm in ("A", "B"):
        for seed in sorted(arms[arm]):
            p = arms[arm][seed]
            rows, bed = p["rows"], p["bed"]
            lok = sum(1 for r in rows if r["arm"] == "left" and r["placed"])
            ln = sum(1 for r in rows if r["arm"] == "left")
            rok = sum(1 for r in rows if r["arm"] == "right" and r["placed"])
            rn = sum(1 for r in rows if r["arm"] == "right")
            g = sel_gaps(p)
            print(f"  {arm} seed {str(seed):>3s}: picks={len(rows):2d} "
                  f"placed={sum(1 for r in rows if r['placed']):2d} "
                  f"(left {lok}/{ln}, right {rok}/{rn}) bed_rows={len(bed):2d} "
                  f"feed_rows={len(p['feed']):2d} cont_rows={p['cont_rows']} "
                  f"on_belt med {fm(med([b['on_belt'] for b in bed]), 0)} "
                  f"window mean {fm(sum(b['window'] for b in bed) / len(bed) if bed else None, 2)} "
                  f"==1 {sum(1 for b in bed if b['window'] == 1)}/{len(bed)} "
                  f"skipped_final {bed[-1]['skipped'] if bed else 'n/a'} "
                  f"gap max {max(g) if g else 'n/a'} wall={fm(p['wall'])}s "
                  f"starve_lines={starve_lines(p['path'])}"
                  + ("  WEDGED" if p["wedged"] else ""))

    # ---------------------------------------------------------------- the table --
    print("\n== the registered table (pooled per arm; controls re-read from their logs) ==")
    S = {}
    for label, table, band_lo in (("burst control (pre-P58)", burst, 0.35),
                                  ("control A'' (cap 4)", cap4, 0.35),
                                  ("arm A (cap 5)", arms["A"], 0.35),
                                  ("arm B (upstream 0.40)", arms["B"], 0.40)):
        S[label] = summary(table, band_lo)
        line(label, S[label])

    # note the burst control's own provenance (one aborted 6-pick log in its dir)
    abort = [p for p in glob.glob(os.path.join(BURST_DIR, "A_*aborted*.log"))]
    print(f"  note: the burst-control directory also holds {len(abort)} aborted run(s), "
          f"excluded by the numeric-seed load; PREREG's 2.57 is the pooled 51-selection read.")

    # ------------------------------------------------------------------- E1-E5 --
    print("\n== endpoints (PREREG_P2 §Endpoints) ==")
    c4 = S["control A'' (cap 4)"]
    c4_one = sum(1 for x in c4["win"] if x == 1)
    for arm in ("A", "B"):
        s = S["arm A (cap 5)" if arm == "A" else "arm B (upstream 0.40)"]
        wmean = sum(s["win"]) / len(s["win"]) if s["win"] else None
        wone = sum(1 for x in s["win"] if x == 1)
        e1 = wmean is not None and wmean >= 2.57 and wone <= 4
        e2 = len(s["starves"]) == 0
        e3 = all(v is not None and v <= 20 for v in s["skipped"].values())
        print(f"  arm {arm}: E1 window mean {fm(wmean, 2)} >= 2.57 and ==1 {wone}/{len(s['win'])} <= 4  "
              f"{'PASS' if e1 else 'FAIL'}   (window>=1 {sum(1 for x in s['win'] if x >= 1)}/{len(s['win'])})")
        print(f"         E2 starved feed rounds {len(s['starves'])}/{len(s['gaps'])} (sel_gap>=169) "
              f"{'PASS' if e2 else 'FAIL'}   starve-string lines "
              f"{ {seed: starve_lines(arms[arm][seed]['path']) for seed in sorted(arms[arm])} }")
        print(f"         E3 skipped {s['skipped']} every run <= 20  {'PASS' if e3 else 'FAIL'}")
        print(f"         window==1 vs control A'' {wone}/{len(s['win'])} vs {c4_one}/{len(c4['win'])}  "
              f"Fisher p = {fisher(wone, len(s['win']), c4_one, len(c4['win'])):.3f}  "
              f"| vs burst 4/45 -> {'fewer' if wone < 4 else ('equal' if wone == 4 else 'more')}")
        print(f"         reported only (not registered): permutation p on the `window` mean "
              f"vs control A'' = {permutation_p(s['win'], c4['win']):.2f}; vs burst = "
              f"{permutation_p(s['win'], S['burst control (pre-P58)']['win']):.2f}")

    # --------------------------------------------------------------------- E4 ---
    print("\n== E4 no new failure reason (113's normalisation) ==")
    baseline = set()
    for root in ("logs/p43/p3", "logs/p54/p1"):
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            if name.endswith(".log"):
                baseline |= ap.reasons_of(ap.parse(os.path.join(root, name))["rows"])
    r_c4 = ap.reasons_of([r for s in cap4 for r in cap4[s]["rows"]])
    for arm in ("A", "B"):
        ra = ap.reasons_of([r for s in arms[arm] for r in arms[arm][s]["rows"]])
        new = sorted(ra - (r_c4 | baseline))
        print(f"  arm {arm} keys ({len(ra)}):")
        for k in sorted(ra):
            print(f"    - {k[:150]}")
        print(f"  arm {arm} NEW vs control A'' + the P43/P54 baseline: {new or 'none'}  "
              f"-> E4 {'PASS' if not new else 'FAIL'}")
    ra = ap.reasons_of([r for s in arms["A"] for r in arms["A"][s]["rows"]])
    rb = ap.reasons_of([r for s in arms["B"] for r in arms["B"][s]["rows"]])
    print(f"  A keys not in B: {sorted(ra - rb) or 'none'}")
    print(f"  B keys not in A: {sorted(rb - ra) or 'none'}")

    # ---------------------------------------------------- the starve mechanism ---
    for arm in ("A", "B"):
        for seed in sorted(arms[arm]):
            p = arms[arm][seed]
            seq = p["events"]
            for k in range(len(seq) - 1):
                if seq[k][0] != "bed" or seq[k + 1][0] != "ep":
                    continue
                ep = seq[k + 1][1]
                nxt = next((seq[j][1] for j in range(k + 1, len(seq))
                            if seq[j][0] == "bed"), None)
                if nxt is None:
                    continue
                gap = int(round(120.0 * (nxt["t"] - seq[k][1]["t"]) - ep["ticks"]))
                if gap >= 169:
                    b = seq[k][1]
                    print(f"\n  STARVE arm {arm} seed {seed} boundary {b['attempt']}->{nxt['attempt']}: "
                          f"{gap} ticks ({gap / 120.0:.2f} s)")
                    print(f"    preceding: on_belt={b['on_belt']} live={b['live']} "
                          f"admitted={b['admitted']} window={b['window']} skipped={b['skipped']}")
                    print(f"    starved pick: {ep['index']} {ep['category']} d={ep['diameter']} cm "
                          f"arm={ep['arm']} ticks={ep['ticks']}")
                    print(f"    next: on_belt={nxt['on_belt']} live={nxt['live']} "
                          f"admitted={nxt['admitted']} window={nxt['window']} skipped={nxt['skipped']}")

    # ------------------------------------------------------- composition detail --
    print("\n== composition detail: the below-window (past-station) rows ==")
    for label in ("burst control (pre-P58)", "control A'' (cap 4)",
                  "arm A (cap 5)", "arm B (upstream 0.40)"):
        c = S[label]["comp"]
        print(f"  {label:26s}: below-window {c['below']:3d}/{c['blocks']:2d} = {fm(c['per_block'], 2)} per block "
              f"({100.0 * (c['share_of_cands'] or 0):.1f} % of {c['cands']} candidate rows)  "
              f"identity mismatches {len(c['identity_bad'])}  per run "
              f"{ {s: round(v['per_block'], 2) for s, v in c['per_run'].items()} }")

    print("\n== the along histogram at the selection instants (bodies per bin, "
          "pooled 45 selections, off-belt excluded) ==")
    print("   bins: past station (<0) | 0..0.15 | 0.15..0.399 (approach) | "
          "0.399..0.68 (catchable aperture) | above spawn (>0.68)")
    tables = (("burst control (pre-P58)", burst), ("control A'' (cap 4)", cap4),
              ("arm A (cap 5)", arms["A"]), ("arm B (upstream 0.40)", arms["B"]))
    for label, table in tables:
        bins, tot = along_hist(table)
        print(f"  {label:26s}: {bins}  total {tot}  shares "
              + " ".join(f"{100.0 * b / tot:.1f}%" for b in bins) if tot else "n/a")

    # -------------------------------------------------------------- provenance --
    print("\n== supply provenance (read-only; the P58 check verbatim) ==")
    for arm in ("A", "B"):
        for seed in sorted(arms[arm]):
            p = arms[arm][seed]
            s = p["supply"] or ""
            print(f"  arm {arm} seed {str(seed):>3s}: patch=on {'patch=on' in s}  "
                  f"grades_balanced {'grades=A:0.375,B:0.375,C:0.25' in s}  "
                  f"[bed-sel] {len(p['bed'])}/15  [feed] {len(p['feed'])}  cont_rows {p['cont_rows']}")
            print(f"                  {p['env_ready']}")

    # --------------------------------------------------------------- decision ---
    print("\n== decision rule (PREREG_P2 §Decision rule) ==")
    meet = {}
    for arm in ("A", "B"):
        s = S["arm A (cap 5)" if arm == "A" else "arm B (upstream 0.40)"]
        wmean = sum(s["win"]) / len(s["win"]) if s["win"] else 0.0
        wone = sum(1 for x in s["win"] if x == 1)
        ra = ap.reasons_of([r for s2 in arms[arm] for r in arms[arm][s2]["rows"]])
        e4 = not sorted(ra - (r_c4 | baseline))
        meet[arm] = (wmean >= 2.57 and wone <= 4 and len(s["starves"]) == 0
                     and all(v is not None and v <= 20 for v in s["skipped"].values())
                     and e4)
    print(f"  A meets E1-E4: {meet['A']} | B meets E1-E4: {meet['B']}")
    if meet["A"] and meet["B"]:
        a_on = sum(S["arm A (cap 5)"]["on"]) / len(S["arm A (cap 5)"]["on"])
        b_on = sum(S["arm B (upstream 0.40)"]["on"]) / len(S["arm B (upstream 0.40)"]["on"])
        pick = "A" if a_on <= b_on else "B"
        print(f"  both meet -> fewer bodies: A on_belt {fm(a_on, 2)} vs B {fm(b_on, 2)} -> adopt {pick}")
    elif meet["A"] or meet["B"]:
        print(f"  -> adopt {'A' if meet['A'] else 'B'}")
    else:
        print("  neither meets E1 -> change nothing; record the residual "
              "(the aperture ceiling is the named limit, P33/P56)")
    print(f"  residual read: window mean A {fm(sum(S['arm A (cap 5)']['win']) / len(S['arm A (cap 5)']['win']), 2)} "
          f"/ B {fm(sum(S['arm B (upstream 0.40)']['win']) / len(S['arm B (upstream 0.40)']['win']), 2)} "
          f"vs control A'' {fm(sum(c4['win']) / len(c4['win']), 2)} and burst 2.57; "
          f"window>=1 A {sum(1 for x in S['arm A (cap 5)']['win'] if x >= 1)}/{len(S['arm A (cap 5)']['win'])} "
          f"B {sum(1 for x in S['arm B (upstream 0.40)']['win'] if x >= 1)}/{len(S['arm B (upstream 0.40)']['win'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
