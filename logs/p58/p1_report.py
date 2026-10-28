"""P58 phase 1 report: the continuous-supply stack vs the shipped direct config.

    python3 logs/p58/p1_report.py --dir logs/p58/p1

Reads the six logs `logs/p58/run_batch.sh` writes and prints the endpoints
registered in `logs/p58/PREREG.md` §2 (written before the first run):

  P1  the pickable-band stock (`[bed-sel]` `window>=1` share, pooled <= 95 % bar)
      and the longest inter-pick gap per B run (`[cont]` `gap_ticks`, <= 140);
      A's gaps are 140 by construction (the P56 census), reported as such.
  P2  no new failure reason in B (113's normalisation, the P43/P54 baseline).
  P3  the scripted no-harm: `logs/p58/p3_accept.log` vs `logs/p34/73_accept_no_harm.log`.
  P4  the placed count, reported only (branches; no rate claim).
  P5  the wall per pick, reported.
  F1-F4 the falsifiers of PREREG §3.

The unit is one **pick** = one `[rl] episode ... success=` row: arm A runs
`--episodes 15`, arm B `--episodes 1` + `FRUIT_DIRECT_CONTINUOUS=15`, so both
deliver 15 picks and the report asserts that count before it pools anything.

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
CONT_PICK = re.compile(
    r"\[cont\] pick (\d+)/(\d+): (\w+) grade=(\w+) y=([-+0-9.]+) "
    r"gap_ticks=(\d+) placed_so_far=(\d+)"
)
CONT_SUM = re.compile(
    r"\[cont\] episode (\d+): picks=(\d+)/(\d+) placed=(\d+) "
    r"reward=([-+0-9.eE]+) ticks=(\d+) gap_ticks=([-+0-9.naif]+) gaps=(\[[^\]]*\])"
)
CONT_WAIT = re.compile(r"\[cont\] pick (\d+)/(\d+): waiting for a candidate \(round (\d+)/40\)")
WALL = re.compile(r"\[rl\] run wall end ([\d.]+) duration ([\d.]+)s")
ROLLOUT = re.compile(r"\[rl\] rollout success (\d+)/(\d+)")
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
    """The note fragments (split on `, `), i.e. the named failure classes."""
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
        "path": path, "rows": [], "bed": [], "cont": [], "cont_sum": None,
        "waits": [], "wall": None, "rollout": None, "trigger": None,
        "env_ready": None, "cont_enabled": None, "events": [],
        "starved_reset": 0, "wedged": False,
    }
    for line in open(path, encoding="utf-8", errors="ignore"):
        if "[fruit]" not in line:
            continue
        m = EPISODE.search(line)
        if m:
            p["rows"].append({
                "index": int(m.group(1)),
                "category": m.group(2),
                "diameter": float(m.group(3)),
                "arm": m.group(5),
                "success": m.group(6) == "True",
                "grasped": m.group(7) == "True",
                "placed": m.group(8) == "True",
                "ticks": int(m.group(9)),
                "reward": float(m.group(11)),
                "notes": m.group(12),
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
        m = CONT_PICK.search(line)
        if m:
            p["cont"].append({"pick": int(m.group(1)), "n": int(m.group(2)),
                              "gap": int(m.group(6))})
            continue
        m = CONT_SUM.search(line)
        if m:
            p["cont_sum"] = {
                "picks": int(m.group(2)), "target": int(m.group(3)),
                "placed": int(m.group(4)), "reward": float(m.group(5)),
                "ticks": int(m.group(6)),
                "gaps": [int(x) for x in m.group(8).strip("[]").split(",") if x.strip()],
            }
            continue
        m = CONT_WAIT.search(line)
        if m:
            p["waits"].append((int(m.group(1)), int(m.group(3))))
            continue
        m = WALL.search(line)
        if m:
            p["wall"] = float(m.group(2))
            continue
        m = ROLLOUT.search(line)
        if m:
            p["rollout"] = (int(m.group(1)), int(m.group(2)))
            continue
        if p["trigger"] is None and TRIGGER.search(line):
            p["trigger"] = line.strip()
        if p["env_ready"] is None and "[rl] env ready:" in line:
            p["env_ready"] = line.split("[rl] env ready:", 1)[1].strip()
        if p["cont_enabled"] is None and "[cont] enabled:" in line:
            p["cont_enabled"] = line.split("[cont] enabled:", 1)[1].strip()
        if "no graspable fruit reached the selection window" in line:
            p["starved_reset"] += 1
    if p["wall"] is None and p["rows"]:
        p["wedged"] = True
    return p


def load(directory: str) -> dict[str, dict[int, dict]]:
    arms: dict[str, dict[int, dict]] = {"A": {}, "B": {}}
    for path in sorted(glob.glob(os.path.join(directory, "*.log"))):
        stem = os.path.basename(path)[:-4]
        label, _, seed = stem.partition("_")
        if label in arms and seed.isdigit():
            arms[label][int(seed)] = parse(path)
    return arms


def fm(x, nd=1):
    return "n/a" if x is None else f"{x:.{nd}f}"


def median(vals):
    return st.median(vals) if vals else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="logs/p58/p1")
    ap.add_argument("--p3-log", default="logs/p58/p3_accept.log")
    ap.add_argument("--p3-ref", default="logs/p41/p2/accept_profile.log",
                    help="the P41 same-tree no-harm re-record (PREREG amendment A3)")
    ap.add_argument("--p3-xref", default="logs/p53/03b_accept_noharm_run.log",
                    help="cross-check: the unfiltered same-tree record (A2/A3)")
    ap.add_argument("--p3-old", default="logs/p34/73_accept_no_harm.log",
                    help="the pre-P41 record the phase registered; diagnostic only")
    ap.add_argument("--p3-outer", default="logs/p58/p3_accept_outer.log")
    args = ap.parse_args()

    arms = load(args.dir)
    seeds = sorted(set(arms["A"]) & set(arms["B"]))
    print("# P58 phase 1 report — the continuous-supply stack vs the shipped direct config")
    print(f"# dir {args.dir}   seeds {seeds}   logs {sum(len(v) for v in arms.values())}")
    if not seeds:
        print("no A_<seed>/B_<seed> log pairs")
        return 2

    # ------------------------------------------------------------- raw table --
    print("\n== the runs (unit = one pick = one `[rl] episode ... success=` row) ==")
    runs = {}
    for label in ("A", "B"):
        for seed in seeds:
            p = arms[label][seed]
            rows = p["rows"]
            placed = sum(1 for r in rows if r["placed"])
            arm_left = sum(1 for r in rows if r["arm"] == "left")
            arm_right = sum(1 for r in rows if r["arm"] == "right")
            left_ok = sum(1 for r in rows if r["arm"] == "left" and r["placed"])
            right_ok = sum(1 for r in rows if r["arm"] == "right" and r["placed"])
            gaps = [c["gap"] for c in p["cont"]]
            gaps_sum = p["cont_sum"]["gaps"] if p["cont_sum"] else []
            bed = p["bed"]
            win = [b["window"] for b in bed]
            runs[(label, seed)] = dict(p=p, rows=rows, placed=placed,
                                       left=arm_left, right=arm_right,
                                       left_ok=left_ok, right_ok=right_ok,
                                       gaps=gaps, gaps_sum=gaps_sum, bed=bed,
                                       win=win)
            print(
                f"  {label} seed {str(seed):>3s}: picks={len(rows):2d} placed={placed:2d} "
                f"(left {left_ok}/{arm_left}, right {right_ok}/{arm_right}) "
                f"bed_rows={len(bed):2d} window>=1={sum(1 for w in win if w >= 1):2d}"
                f"/{len(win):2d} "
                f"gaps={gaps if gaps else 'n/a (per-episode)'} "
                f"longest={max(gaps) if gaps else 140} "
                f"wall={fm(p['wall'])}s  ({fm(p['wall'] / len(rows) if rows else None)} s/pick)"
                + ("  WEDGED (no wall row)" if p["wedged"] else "")
                + (f"  starved_reset={p['starved_reset']}" if p["starved_reset"] else "")
            )
    for label in ("A", "B"):
        for seed in seeds:
            r = runs[(label, seed)]
            assert r["p"]["cont"] or label == "A", f"{label}_{seed}: no [cont] rows"
            if r["gaps"] and r["gaps_sum"]:
                assert r["gaps"] == r["gaps_sum"], (
                    f"{label}_{seed}: gap rows {r['gaps']} != summary {r['gaps_sum']}")

    # ------------------------------------------------ the manipulation check --
    print("\n== B accounting (the multi-pick `[cont]` row vs the per-pick rows) ==")
    for seed in seeds:
        p = runs[("B", seed)]["p"]
        if not p["cont_sum"]:
            print(f"  B seed {str(seed):>3s}: no [cont] summary row")
            continue
        cs = p["cont_sum"]
        s_ticks = sum(r["ticks"] for r in runs[("B", seed)]["rows"])
        s_reward = sum(r["reward"] for r in runs[("B", seed)]["rows"])
        print(f"  B seed {str(seed):>3s}: picks={cs['picks']}/{cs['target']} placed={cs['placed']} "
              f"ticks_total={cs['ticks']} sum(per-pick ticks)={s_ticks} "
              f"equal={cs['ticks'] == s_ticks} | reward_total={cs['reward']:.6f} "
              f"sum={s_reward:.6f} abs_diff={abs(cs['reward'] - s_reward):.2e} "
              f"(per-pick rows are printed to 4 dp, so the sum is a rounded sum)")
    print("\n== manipulation check (PREREG §1: ACQ unset, park unset, B's stack on) ==")
    for label in ("A", "B"):
        for seed in seeds:
            p = runs[(label, seed)]["p"]
            print(f"  {label} seed {str(seed):>3s}: {p['env_ready']}")
            print(f"                 {p['trigger']}")
            if label == "B":
                print(f"                 [cont] enabled:{p['cont_enabled']}")

    # ------------------------------------------------- P1 the primary endpoint --
    print("\n== P1 the pickable-band stock (primary) ==")
    pooled = {}
    for label in ("A", "B"):
        bed = [b for seed in seeds for b in runs[(label, seed)]["bed"]]
        win = [b["window"] for b in bed]
        pooled[label] = dict(
            n_sel=len(bed),
            n_win=sum(1 for w in win if w >= 1),
            share=(sum(1 for w in win if w >= 1) / len(win)) if win else float("nan"),
            on_belt=median([b["on_belt"] for b in bed]),
            live=median([b["live"] for b in bed]),
            admitted=median([b["admitted"] for b in bed]),
            lag=median([b["lag"] for b in bed]),
            empty=sum(1 for b in bed if b["pick"] == "none"),
            skipped_max=max([b["skipped"] for b in bed], default=0),
            window_counts={k: sum(1 for w in win if w == k) for k in sorted(set(win))},
        )
        d = pooled[label]
        print(
            f"  arm {label}: window>=1 at {d['n_win']}/{d['n_sel']} = {d['share']:.1%} "
            f"| window distribution {d['window_counts']} | pick=none {d['empty']} "
            f"| on_belt med {fm(d['on_belt'], 0)} live med {fm(d['live'], 0)} "
            f"admitted med {fm(d['admitted'], 0)} lag med {fm(d['lag'], 2)}s "
            f"| skipped max {d['skipped_max']}"
        )
    b_gaps = [g for seed in seeds for g in runs[("B", seed)]["gaps"]]
    b_longest = {seed: max(runs[("B", seed)]["gaps"]) for seed in seeds}
    print(f"  B gaps pooled: n={len(b_gaps)} {b_gaps}")
    print(f"  B longest gap per run: {b_longest}")
    print(f"  A gaps: 140 by construction on every boundary (per-episode reset; "
          f"P56 census 14/14), not re-measured; A starved resets: "
          f"{[runs[('A', s)]['p']['starved_reset'] for s in seeds]}")
    p1_share = pooled["B"]["share"] >= 0.95
    p1_gap = all(g <= 140 for g in b_longest.values()) and bool(b_longest)
    p1 = p1_share and p1_gap
    print(f"  P1a window>=1 share >= 95 % (B pooled) : {'PASS' if p1_share else 'FAIL'} "
          f"({pooled['B']['n_win']}/{pooled['B']['n_sel']} = {pooled['B']['share']:.1%})")
    print(f"  P1b longest gap <= 140 ticks (every B): {'PASS' if p1_gap else 'FAIL'} {b_longest}")
    print(f"  P1  {'PASS' if p1 else 'FAIL'}")

    # ------------------- P1 secondary: the selection-clock gap (amendment A1.2) --
    print("\n  P1 secondary (amendment A1.2, reported not gated): the selection-clock gap")
    print("    sel_gap_k = 120*(t_{k+1}-t_k) - ticks_k; A expected 140 + 30*retries,")
    print("    B expected 50/110 (teleport) + the printed gap; B's empty-round rows offset by 30.")
    for label in ("A", "B"):
        for seed in seeds:
            p = runs[(label, seed)]["p"]
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
            over = [g for g in gaps if g > 200]
            print(f"    {label} seed {str(seed):>3s}: n={len(gaps)} min={min(gaps) if gaps else None} "
                  f"med={fm(median(gaps), 0)} max={max(gaps) if gaps else None} "
                  f">200={len(over)} {gaps}")

    # -------------------------------------------------- P2 the failure reasons --
    print("\n== P2 no new failure reason (113's normalisation) ==")
    ra = reasons_of([r for seed in seeds for r in runs[("A", seed)]["rows"]])
    rb = reasons_of([r for seed in seeds for r in runs[("B", seed)]["rows"]])
    baseline = set()
    for root in ("logs/p43/p3", "logs/p54/p1"):
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            if name.endswith(".log"):
                baseline |= reasons_of(parse(os.path.join(root, name))["rows"])
    new = sorted(rb - (ra | baseline))
    print(f"  A keys ({len(ra)}):")
    for k in sorted(ra):
        print(f"    - {k[:200]}")
    print(f"  B keys ({len(rb)}):")
    for k in sorted(rb):
        print(f"    - {k[:200]}")
    print(f"  P43/P54 baseline keys: {len(baseline)}")
    print(f"  NEW in B (vs A + baseline): {new or 'none'}")
    print(f"  missing in B (vs A): {sorted(ra - rb) or 'none'}")
    fa = fragments_of([r for seed in seeds for r in runs[("A", seed)]["rows"]])
    fb = fragments_of([r for seed in seeds for r in runs[("B", seed)]["rows"]])
    print(f"  A fragments: {sorted(fa)}")
    print(f"  B fragments: {sorted(fb)}")
    print(f"  B fragments not in A: {sorted(fb - fa) or 'none'}  (the raw class names)")
    p2 = not new
    print(f"  P2  {'PASS' if p2 else 'FAIL'}")

    # per-pair novelty (F3 is about every pair, this is the per-run read)
    print("\n  per-seed new keys (B_seed vs A_seed + baseline):")
    per_pair = {}
    for seed in seeds:
        ra_s = reasons_of(runs[("A", seed)]["rows"])
        rb_s = reasons_of(runs[("B", seed)]["rows"])
        per_pair[seed] = sorted(rb_s - (ra_s | baseline))
        print(f"    seed {seed}: {per_pair[seed] or 'none'}")
    f3 = all(per_pair[s] for s in seeds)

    # -------------------------------------------------------- P4 placed count --
    print("\n== P4 the placed count (reported only; branches, no rate claim) ==")
    for label in ("A", "B"):
        tot = sum(runs[(label, s)]["placed"] for s in seeds)
        n = sum(len(runs[(label, s)]["rows"]) for s in seeds)
        lo = sum(runs[(label, s)]["left_ok"] for s in seeds)
        ln = sum(runs[(label, s)]["left"] for s in seeds)
        ro = sum(runs[(label, s)]["right_ok"] for s in seeds)
        rn = sum(runs[(label, s)]["right"] for s in seeds)
        print(f"  arm {label}: placed {tot}/{n}  (left {lo}/{ln}, right {ro}/{rn})")
    for label in ("A", "B"):
        print("  " + f"arm {label} per run: " + "  ".join(
            f"{s}:{runs[(label, s)]['placed']}/{len(runs[(label, s)]['rows'])}" for s in seeds))

    # ------------------------------------------------------------- P5 the wall --
    print("\n== P5 the wall per pick (reported) ==")
    for label in ("A", "B"):
        walls = [runs[(label, s)]["p"]["wall"] for s in seeds]
        picks = [len(runs[(label, s)]["rows"]) for s in seeds]
        if all(w is not None for w in walls) and picks and all(picks):
            print(f"  arm {label}: walls {[round(w) for w in walls]}s  "
                  f"per pick {[round(w / n) for w, n in zip(walls, picks)]}  "
                  f"pooled {sum(walls):.0f}s / {sum(picks)} picks = "
                  f"{sum(walls) / sum(picks):.1f} s/pick")

    # ------------------------------------------------- P3 the scripted no-harm --
    print("\n== P3 the scripted no-harm (accept.sh, all knobs unset) ==")
    ok_p3 = False
    fp = None
    if os.path.exists(args.p3_outer):
        text = open(args.p3_outer, encoding="utf-8", errors="ignore").read()
        m = re.search(r"fingerprint: (\w+)", text)
        fp = m.group(1) if m else None
        print(f"  motion gate: fingerprint: {fp}")
        for line in text.splitlines():
            if line.startswith("[stats]") or "[run] summary" in line:
                print(f"  {line.strip()}")
    else:
        print(f"  MISSING {args.p3_outer}")

    def fruit_lines(path):
        return [ln for ln in open(path, encoding="utf-8", errors="ignore") if "[fruit]" in ln]

    # the opt-in diagnostic rows the P41 comparator strips (PREREG amendment A3)
    EXCL = re.compile(r"\[diag\]|\[carry\]|\[seat\]|\[attitude\]|\[pry\]|\[grip\]|\[release\]")

    def filt(lines):
        return [ln for ln in lines if not EXCL.search(ln)]

    if os.path.exists(args.p3_log) and os.path.exists(args.p3_ref):
        got, ref = fruit_lines(args.p3_log), fruit_lines(args.p3_ref)
        g, r = filt(got), filt(ref)
        same = g == r
        print(f"  [fruit] lines: got {len(got)} (filtered {len(g)})  "
              f"reference {len(ref)} (filtered {len(r)})  {args.p3_ref}  identical={same}")
        if not same:
            limit = min(len(g), len(r))
            first = next((i for i in range(limit) if g[i] != r[i]), None)
            print(f"  first differing filtered [fruit] line index: {first} of {limit}")
            if first is not None:
                print(f"    got: {g[first].strip()[:220]}")
                print(f"    ref: {r[first].strip()[:220]}")
        p3 = fp == "matches" and same
        if os.path.exists(args.p3_xref):
            xr = fruit_lines(args.p3_xref)
            print(f"  cross-check (unfiltered): {args.p3_xref}: "
                  f"got {len(got)} / ref {len(xr)}  identical={got == xr}")
        if os.path.exists(args.p3_old):
            old = fruit_lines(args.p3_old)
            print(f"  DIAGNOSTIC (amendment A2/A3): vs the pre-P41 record {args.p3_old}: "
                  f"got {len(got)} / registered {len(old)} lines, identical={got == old} "
                  f"- not gated; that file is pre-P41 and no post-P41 tree reproduces it")
    else:
        print("  MISSING P3 log or reference")
        p3 = False
    print(f"  P3  {'PASS' if p3 else 'FAIL'}")

    # ------------------------------------------------------------ falsifiers --
    print("\n== falsifiers (PREREG §3) ==")
    f1 = not p1
    f2 = any(g > 200 for g in b_gaps) or any(runs[("B", s)]["p"]["wedged"] for s in seeds)
    print(f"  F1 P1 fails -> nothing adopted          : {'FIRES' if f1 else 'does not fire'}")
    print(f"  F2 any B gap > 200 ticks -> not continuous: {'FIRES' if f2 else 'does not fire'} "
          f"(longest {b_longest})")
    print(f"  F3 a new reason in every seed pair       : {'FIRES' if f3 else 'does not fire'} "
          f"({ {s: (v or 'none') for s, v in per_pair.items()} })")
    print(f"  F4 P3 fails -> a shipped path moved      : {'FIRES' if not p3 else 'does not fire'}")

    print("\n== verdict ==")
    print(f"  P1 {'PASS' if p1 else 'FAIL'} | P2 {'PASS' if p2 else 'FAIL'} | "
          f"P3 {'PASS' if p3 else 'FAIL'} | P4 reported | P5 reported")
    adopted = p1 and p2 and p3 and not f2 and not f3
    print(f"  adoption gate (F1-F4 clear and P1 passes): "
          f"{'PASS — proceed to the Oracle 1 adoption decision' if adopted else 'FAIL — not adopted'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
