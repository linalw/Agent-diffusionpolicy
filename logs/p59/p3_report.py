"""P59 phase 3 report — the same-tree 45-block control and the cap-5 re-read.

    python3 logs/p59/p3_report.py

Answers the three questions P59 phase 3 was dispatched for:

  1. **Is the phase-2 cap-5 arm same-tree comparable?** The control's own tree
     pins (`logs/p59/p3/header.txt`, `tree_md5_after.txt`) are compared against
     the pins the phase-2 batch recorded (`logs/p59/p2/header.txt`,
     `p2/tree_md5_after.txt`) - on the files the arm actually reads.
  2. **Does ANY behavioural counter differ** between the shipped control (cap 4)
     and cap 5 - `sel_gap` multiset, starved rounds, `skipped`, `placed`,
     `window==0`, wall per pick - and what is the depth difference.
  3. **The post-profile direct number**: the control's placed count per seed and
     pooled, as a **branch** of the shipped configuration (the loop is not
     reproducible - AGENTS section 3b), with the carried-not-placed (`cnp`)
     class named.

The reading rules of `logs/p59/PREREG_P2.md` are applied verbatim and are
binding: `placed` is the summary parse (`[rl] rollout success k/n`), never the
running counter; starvation is asserted from the ABSENCE of
`waiting for a candidate` / `no candidate` lines and from `sel_gap >= 169`,
never from `gap_ticks_mean`; `supply_skipped` is not the drop counter;
`on_belt` is not a catch metric (`on_belt = admitted + below_window`).

Read-only: it opens logs and prints. No state, no store, no `configs/`, no `src/`.
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

P3_DIR = "logs/p59/p3"
P2_DIR = "logs/p59/p2"
#: the physical catch floor: `_dynamic_select_floor()`'s 0.399 m
CATCH_FLOOR = 0.399
#: the pin files the two batches recorded, and what the arm actually reads
PINS = ("src/fruit_sorting/rl_env.py", "src/fruit_sorting/tasks.py",
        "src/fruit_sorting/fruits.py", "src/fruit_sorting/scene.py",
        "src/fruit_sorting/control.py", "src/fruit_sorting/meshes.py",
        "src/fruit_sorting/policy/trigger.py",
        "src/fruit_sorting/policy/runtime.py",
        "configs/arm_parks.json", "configs/motion_reference.json",
        "configs/motion_reference_twoline.json",
        "scripts/110_rl_rollout.py", "scripts/113_rl_report.py",
        "scripts/154_claim_run.sh")
#: the arms' claims, as the `[supply] direct profile` row must print them
CLAIMS = {
    "C": ("band=on(4)(default)", "target_from=0.35(default)"),
    "A": ("band=on(5(explicit))(default)", "target_from=0.35(default)"),
}
STARVE_STRINGS = ("waiting for a candidate", "no candidate")
STARVE_GAP = 169          # PREREG_P2 E2: sel_gap >= 169 ticks = a skipped feed round


def fm(x, nd=1):
    return "n/a" if x is None else f"{x:.{nd}f}"


def med(vals):
    return st.median(vals) if vals else None


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


def read_pins(path):
    """`md5  path` lines of a batch's pin file -> {path: md5}."""
    out = {}
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8", errors="ignore"):
        bits = line.split()
        if len(bits) == 2 and re.fullmatch(r"[0-9a-f]{32}", bits[0]):
            out[bits[1]] = bits[0]
    return out


def gaps_multiset(gaps):
    out = {}
    for g in gaps:
        out[g] = out.get(g, 0) + 1
    return dict(sorted(out.items()))


def fisher(a, n1, c, n2):
    """Two-sided Fisher exact (the P2 report's form, lifted to module level)."""
    from math import comb
    tot, k = n1 + n2, a + c

    def p(x):
        return comb(n1, x) * comb(n2, k - x) / comb(tot, k)

    p0 = p(a)
    lo, hi = max(0, k - n2), min(n1, k)
    return sum(p(x) for x in range(lo, hi + 1) if p(x) <= p0 * 1.0000001)


def summary(table):
    bed = [b for s in sorted(table) for b in table[s]["bed"]]
    rows = [r for s in sorted(table) for r in table[s]["rows"]]
    win = [b["window"] for b in bed]
    gaps = [g for s in sorted(table) for g in ap.sel_gaps(table[s])]
    walls = [table[s]["wall"] for s in sorted(table)]
    picks = [len(table[s]["rows"]) for s in sorted(table)]
    ticks = [sum(r["ticks"] for r in table[s]["rows"]) for s in sorted(table)]
    comp = a3.composition(table)          # asserts block<->attempt alignment
    below, bad = comp["below"], len(comp["identity_bad"])
    return {
        "bed": bed, "rows": rows, "win": win, "gaps": gaps,
        "on": [b["on_belt"] for b in bed], "adm": [b["admitted"] for b in bed],
        "live": [b["live"] for b in bed],
        "starves": [g for g in gaps if g >= STARVE_GAP],
        "skipped": {s: (table[s]["bed"][-1]["skipped"]
                        if table[s]["bed"] else None) for s in sorted(table)},
        "placed": sum(1 for r in rows if r["placed"]), "n": len(rows),
        "summ": {s: table[s]["rollout"] for s in sorted(table)},
        "wall": (sum(walls) / sum(picks)
                 if all(w is not None for w in walls) and sum(picks) else None),
        "ticks_per_pick": (sum(ticks) / sum(picks)) if sum(picks) else None,
        "below": below, "below_per_block": below / len(bed) if bed else None,
        "identity_bad": bad,
        "cnp": [r for r in rows if r["grasped"] and not r["placed"]],
        "nogr": [r for r in rows if not r["grasped"]],
    }


def line(label, S):
    win = S["win"]
    print(f"  {label:24s}: sel {len(win):2d}  window mean "
          f"{fm(sum(win) / len(win) if win else None, 2)}  "
          f"==1 {sum(1 for x in win if x == 1):2d}/{len(win)}  "
          f"==0 {sum(1 for x in win if x == 0):2d}  "
          f"dist {dict(sorted((k, sum(1 for v in win if v == k)) for k in sorted(set(win))))}")
    print(f"  {'':24s}  sel_gap multiset {S['gaps'] if len(S['gaps']) <= 12 else gaps_multiset(S['gaps'])}  "
          f"starved {len(S['starves'])}/{len(S['gaps'])}  skipped {S['skipped']}")
    print(f"  {'':24s}  on_belt mean {fm(sum(S['on']) / len(S['on']) if S['on'] else None, 2)}  "
          f"admitted mean {fm(sum(S['adm']) / len(S['adm']) if S['adm'] else None, 2)}  "
          f"live med {fm(med(S['live']), 0)}  below-window {fm(S['below_per_block'], 2)}/block  "
          f"identity mismatches {S['identity_bad']}  placed {S['placed']}/{S['n']}  "
          f"wall/pick {fm(S['wall'], 2)}s  ticks/pick {fm(S['ticks_per_pick'], 1)}")


def main() -> int:
    print("# P59 phase 3 report — the same-tree 45-block control and the cap-5 re-read")

    # --------------------------------------------------------------- the pins --
    print("\n== 1. is the cap-5 arm same-tree comparable? (the arm reads these files) ==")
    now = {p: md5(os.path.join(ROOT, p)) for p in PINS if os.path.exists(os.path.join(ROOT, p))}
    p2 = read_pins(os.path.join(ROOT, P2_DIR, "header.txt"))
    p2 |= read_pins(os.path.join(ROOT, P2_DIR, "tree_md5_after.txt"))
    p3 = read_pins(os.path.join(ROOT, P3_DIR, "header.txt"))
    diff = [p for p in PINS if p2.get(p) and p2.get(p) != now.get(p)]
    missing = [p for p in PINS if not p2.get(p)]
    print(f"  current tree {now.get('src/fruit_sorting/rl_env.py', '?')[:8]} "
          f"rl_env / {now.get('src/fruit_sorting/tasks.py', '?')[:8]} tasks / "
          f"{now.get('src/fruit_sorting/fruits.py', '?')[:8]} fruits")
    print(f"  phase-2 batch wrote: rl_env {p2.get('src/fruit_sorting/rl_env.py', 'MISSING')[:8]} / "
          f"tasks {p2.get('src/fruit_sorting/tasks.py', 'MISSING')[:8]} / "
          f"fruits {p2.get('src/fruit_sorting/fruits.py', 'MISSING')[:8]}")
    print(f"  phase-3 batch wrote: rl_env {p3.get('src/fruit_sorting/rl_env.py', 'MISSING')[:8]} / "
          f"tasks {p3.get('src/fruit_sorting/tasks.py', 'MISSING')[:8]} / "
          f"fruits {p3.get('src/fruit_sorting/fruits.py', 'MISSING')[:8]}")
    print(f"  compared files with a phase-2 pin: {len(PINS) - len(missing)}/{len(PINS)}"
          + (f"  (no phase-2 pin: {missing})" if missing else ""))
    print(f"  files whose md5 MOVED since phase 2: {diff or 'none'}")
    a2 = read_pins(os.path.join(ROOT, "logs/p58/p3b/A2_header.txt"))
    d2 = [p for p in PINS if a2.get(p) and a2.get(p) != now.get(p)]
    print(f"  for contrast, the P2 control A2 (logs/p58/p3b) moved "
          f"{len(d2)}/{len(PINS)} of these files: "
          + ", ".join(f"{os.path.basename(p)} {a2[p][:8]}->{now[p][:8]}" for p in d2))
    print(f"  -> cap 5 vs the shipped control is "
          f"{'SAME-TREE' if not diff else 'CROSS-TREE (' + str(diff) + ')'}"
          f"; cap 5 vs A2 is and remains CROSS-TREE ({len(d2)} files differ).")

    arms = {k: load(P3_DIR, f"C_*.log") if k == "C" else load(P2_DIR, "A_*.log")
            for k in ("C", "A")}
    print(f"  control seeds {sorted(arms['C'])}  arm A (cap 5, phase 2) seeds {sorted(arms['A'])}")
    if not arms["C"]:
        print("  missing control logs")
        return 2

    # ------------------------------------------------------- the arm is what it claims --
    print("\n== the arm is what it claims (PREREG_P2 reading rule 5; stop if not) ==")
    bad = []
    for arm in ("C", "A"):
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

    # ------------------------------------------------------------------ the runs --
    print("\n== the runs (unit = one pick = one `[rl] episode ... success=` row) ==")
    for arm in ("C", "A"):
        for seed in sorted(arms[arm]):
            p = arms[arm][seed]
            rows, bed = p["rows"], p["bed"]
            lok = sum(1 for r in rows if r["arm"] == "left" and r["placed"])
            ln = sum(1 for r in rows if r["arm"] == "left")
            rok = sum(1 for r in rows if r["arm"] == "right" and r["placed"])
            rn = sum(1 for r in rows if r["arm"] == "right")
            g = ap.sel_gaps(p)
            sk = bed[-1]["skipped"] if bed else "n/a"
            print(f"  {arm} seed {str(seed):>3s}: picks={len(rows):2d} "
                  f"placed={sum(1 for r in rows if r['placed']):2d} "
                  f"({p['rollout'][0] if p['rollout'] else 'n/a'}/{p['rollout'][1] if p['rollout'] else 'n/a'} summary) "
                  f"(left {lok}/{ln}, right {rok}/{rn}) bed_rows={len(bed):2d} "
                  f"on_belt mean {fm(sum(b['on_belt'] for b in bed) / len(bed) if bed else None, 2)} "
                  f"window mean {fm(sum(b['window'] for b in bed) / len(bed) if bed else None, 2)} "
                  f"==1 {sum(1 for b in bed if b['window'] == 1)}/{len(bed)} "
                  f"skipped_final {sk} gap max {max(g) if g else 'n/a'} "
                  f"wall={fm(p['wall'])}s starve_lines={starve_lines(p['path'])}"
                  + ("  WEDGED" if p["wedged"] else ""))

    # ------------------------------------------------------------------ the table --
    print("\n== the registered table (pooled per arm; a reopening needs these two on one foot) ==")
    S = {}
    for label, table in (("control C (cap 4, shipped)", arms["C"]),
                         ("arm A (cap 5, phase 2)", arms["A"])):
        if not table:
            continue
        S[label] = summary(table)
        line(label, S[label])

    C = S.get("control C (cap 4, shipped)")
    A = S.get("arm A (cap 5, phase 2)")
    if C is None or A is None:
        print("\n  (an arm is missing - the comparison below is partial)")
        return 4
    if A2s := summary(load("logs/p58/p3b", "A2_*.log")) if glob.glob(
            os.path.join(ROOT, "logs/p58/p3b/A2_*.log")) else None:
        S["A2 (cap 4, cross-tree, the old control)"] = A2s
        line("A2 (cross-tree control)", A2s)

    # ------------------------------------------------- does ANY behaviour differ? --
    print("\n== 3b. does any BEHAVIOURAL counter differ? (PREREG_P2 'what a reopening needs' 2) ==")
    inv = [
        ("window==0 (no candidate at all)", sum(1 for x in C["win"] if x == 0),
         sum(1 for x in A["win"] if x == 0)),
        ("window>=1 blocks", sum(1 for x in C["win"] if x >= 1),
         sum(1 for x in A["win"] if x >= 1)),
        ("starved feed rounds (sel_gap>=169)", len(C["starves"]), len(A["starves"])),
        ("sel_gap support / total", (sorted(set(C["gaps"])), len(C["gaps"])),
         (sorted(set(A["gaps"])), len(A["gaps"]))),
    ]
    same = True
    for name, cval, aval in inv:
        eq = cval == aval
        same &= eq
        print(f"  {name:34s}: control {cval}   cap 5 {aval}   {'SAME' if eq else 'DIFFERS'}")
    noise = [
        ("sel_gap counts within the support", gaps_multiset(C["gaps"]), gaps_multiset(A["gaps"])),
        ("skipped (final, summed over seeds)",
         sum(v for v in C["skipped"].values() if v is not None),
         sum(v for v in A["skipped"].values() if v is not None)),
        ("placed (report only)", C["placed"], A["placed"]),
        ("on_belt mean", round(sum(C["on"]) / len(C["on"]), 2),
         round(sum(A["on"]) / len(A["on"]), 2)),
        ("window mean", round(sum(C["win"]) / len(C["win"]), 2),
         round(sum(A["win"]) / len(A["win"]), 2)),
    ]
    for name, cval, aval in noise:
        print(f"  {name:34s}: control {cval}   cap 5 {aval}   "
              f"{'SAME' if cval == aval else 'DIFFERS (magnitude below)'}")
    print(f"  -> the INVARIANTS that the reopening criterion names are "
          f"{'IDENTICAL' if same else 'NOT identical'}; "
          f"the counters that move are the depth and its 1-tick variants.")

    # ------------------------------------------------------- per-seed same-foot --
    print("\n== 3c. the per-seed pairing (the 'non-worse in N/3 seeds' claim, re-read) ==")
    print(f"  {'seed':>4s}  {'sum(window)':>18s}  {'==1':>10s}  {'skipped':>12s}  {'placed':>12s}")
    wins = 0
    for seed in sorted(set(arms["C"]) & set(arms["A"])):
        c, a = arms["C"][seed], arms["A"][seed]
        cw = [b["window"] for b in c["bed"]]
        aw = [b["window"] for b in a["bed"]]
        cs = c["bed"][-1]["skipped"] if c["bed"] else None
        as_ = a["bed"][-1]["skipped"] if a["bed"] else None
        cp = sum(1 for r in c["rows"] if r["placed"])
        apl = sum(1 for r in a["rows"] if r["placed"])
        worse = sum(1 for x in aw if x == 1) > sum(1 for x in cw if x == 1)
        wins += 0 if worse else 1
        print(f"  {seed:>4d}  C {sum(cw):3d} vs A {sum(aw):3d}  "
              f"C {sum(1 for x in cw if x == 1)}/{len(cw)} vs A "
              f"{sum(1 for x in aw if x == 1)}/{len(aw)}  "
              f"C {cs} vs A {as_}  C {cp}/{len(c['rows'])} vs A {apl}/{len(a['rows'])}"
              + ("   <- cap 5 has MORE marginal blocks than the control" if worse else ""))
    print(f"  -> cap 5 is non-worse on `window==1` in {wins}/3 seeds against the "
          f"same-tree control (against the cross-tree A2 it was 3/3).")

    # ------------------------------------------------------------ the depth read --
    print("\n== 3d. the depth difference and the cross-tree control it replaces ==")
    A2 = load("logs/p58/p3b", "A2_*.log")
    for label, table in (("control C (cap 4, same-tree)", arms["C"]),
                         ("arm A (cap 5, same-tree)", arms["A"]),
                         ("A2 (cap 4, CROSS-tree, the P2 control)", A2)):
        if not table:
            continue
        w = [b["window"] for s in sorted(table) for b in table[s]["bed"]]
        if not w:
            continue
        mean = sum(w) / len(w)
        sd = st.stdev(w) if len(w) > 1 else 0.0
        se = sd / (len(w) ** 0.5)
        print(f"  {label:38s}: n {len(w)}  mean {fm(mean, 3)}  sd {fm(sd, 3)}  "
              f"SE {fm(se, 3)}  95 % CI [{fm(mean - 1.96 * se, 3)}, {fm(mean + 1.96 * se, 3)}]  "
              f"==1 {sum(1 for x in w if x == 1)}/{len(w)}  ==0 {sum(1 for x in w if x == 0)}")
    d = sum(A["win"]) / len(A["win"]) - sum(C["win"]) / len(C["win"])
    thr = 1.96 * (st.stdev(A["win"]) ** 2 / len(A["win"])
                  + st.stdev(C["win"]) ** 2 / len(C["win"])) ** 0.5
    print(f"  depth delta (cap 5 - control) = {d:+.3f}; two 45-block arms need "
          f"|delta| >= {thr:.2f} to separate at 95 % (P2_RESULTS §2's power statement) "
          f"-> {'separates' if abs(d) >= thr else 'DOES NOT separate'}")
    print(f"  window==1: control {sum(1 for x in C['win'] if x == 1)}/{len(C['win'])} vs "
          f"cap 5 {sum(1 for x in A['win'] if x == 1)}/{len(A['win'])}  "
          f"Fisher p = {fisher(sum(1 for x in A['win'] if x == 1), len(A['win']), sum(1 for x in C['win'] if x == 1), len(C['win'])):.3f}")
    if A2:
        w2 = [b["window"] for s in sorted(A2) for b in A2[s]["bed"]]
        print(f"  the two CONTROL cells of the same configuration differ by "
              f"{sum(C['win']) / len(C['win']) - sum(w2) / len(w2):+.3f} "
              f"(same-tree {fm(sum(C['win']) / len(C['win']), 3)} vs cross-tree "
              f"{fm(sum(w2) / len(w2), 3)}) - a control-vs-control spread of the same order "
              f"as the arm effect: the depth mean cannot rank the arms at this n.")

    # ------------------------------------------- the post-profile direct number --
    print("\n== 4. the post-profile direct number (a BRANCH of the shipped config, not a rate) ==")
    for seed in sorted(arms["C"]):
        p = arms["C"][seed]
        rows = p["rows"]
        cnp = [r for r in rows if r["grasped"] and not r["placed"]]
        nog = [r for r in rows if not r["grasped"]]
        print(f"  seed {str(seed):>3s}: placed {sum(1 for r in rows if r['placed']):2d}/{len(rows)}  "
              f"summary {p['rollout'][0] if p['rollout'] else 'n/a'}/"
              f"{p['rollout'][1] if p['rollout'] else 'n/a'}  "
              f"cnp {len(cnp)}  no-grasp {len(nog)}  "
              f"left {sum(1 for r in rows if r['arm'] == 'left' and r['placed'])}/"
              f"{sum(1 for r in rows if r['arm'] == 'left')}  "
              f"right {sum(1 for r in rows if r['arm'] == 'right' and r['placed'])}/"
              f"{sum(1 for r in rows if r['arm'] == 'right')}")
    print(f"  pooled: placed {C['placed']}/{C['n']} = {100.0 * C['placed'] / C['n']:.1f} %  "
          f"cnp {len(C['cnp'])}  no-grasp {len(C['nogr'])}  "
          f"left {sum(1 for r in C['rows'] if r['arm'] == 'left' and r['placed'])}/"
          f"{sum(1 for r in C['rows'] if r['arm'] == 'left')}  "
          f"right {sum(1 for r in C['rows'] if r['arm'] == 'right' and r['placed'])}/"
          f"{sum(1 for r in C['rows'] if r['arm'] == 'right')}")
    print(f"  per arm/species (the class the count is dominated by):")
    for arm in ("left", "right"):
        for sp in sorted({r["category"] for r in C["rows"] if r["arm"] == arm}):
            sel = [r for r in C["rows"] if r["arm"] == arm and r["category"] == sp]
            print(f"    {arm:5s} {sp:11s} placed {sum(1 for r in sel if r['placed'])}/{len(sel)}")

    # -------------------------------------------------------------- the classes --
    print("\n== the failure classes (113's normalisation; E4 read) ==")
    rc = ap.reasons_of(C["rows"])
    ra = ap.reasons_of(A["rows"])
    print(f"  control keys ({len(rc)}):")
    for k in sorted(rc):
        print(f"    - {k[:150]}")
    print(f"  control keys not in cap 5: {sorted(rc - ra) or 'none'}")
    print(f"  cap 5 keys not in control: {sorted(ra - rc) or 'none'}")
    print(f"  -> E4 (no new failure reason vs the cap-5 arm + the P43/P54 baseline): "
          f"{'no new key on the control side' if not (rc - ra) else 'see above'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
