"""P54 report: the shipped direct config (ACQ off) vs ACQ=1.

    python3 logs/p54/p54_report.py --dir logs/p54/p1 --a A --b B

Reads, per log, in **line order** (so a mechanism row is attached to its own
episode and never to a neighbour):

  * `[rl] episode N: <fruit> grade=.. d=..cm .. arm=..` - the env line,
  * `[acq] <arm> idx=N: ... catchup=Nt res=Xmm ... close_start=(x,y,z)mm ...` -
    the ACQ mechanism row (`FRUIT_ACQ_DIAG=1`): the catch-up residual and the
    close-start tip-fruit offset,
  * `[rl] episode N: .. success=.. grasped=.. placed=.. ticks=.. notes=[..]` -
    the outcome row (first one per index wins; the direct log prints one env row
    and one outcome row per episode, and a duplicated row must never become a
    second episode),
  * `[rl] trigger=..` - the resolved trigger settings (the manipulation check),
  * `[rl] rollout: .. seeds=[N]` - the seed, and `[rl] run wall end .. duration Xs`.

**One trap this report exists to avoid.** The fire note's `, lead=..s/reach=..`
suffix is printed **only when the ACQ knob is on** (`rl_env.py:3802-3806`), so the
note *text* differs between the arms by construction. The failure-reason keys are
therefore taken with the whole `intercept trigger (...)` stamp removed: a
difference in the stamp is the knob's own signature, not a new failure mode.

Prints the endpoints registered in `logs/p54/PREREG.md`§3: E1 (the right-arm
placed delta, rate_A - rate_B, bar >= -0.10), E2 (the never-held acquisition class
plus its mechanism), E3 (failure reasons both directions), the left arm as its own
row, and the per-seed pairs.
"""

from __future__ import annotations

import argparse
import glob
import math
import os
import re
import statistics as st

ENV_ROW = re.compile(
    r"\[rl\] episode (\d+): (\w+) grade=(\w+) d=([\d.]+)cm bin=(-?\d+) arm=(\w+)"
)
OUT_ROW = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(-?\d+) arm=(\w+) success=(\w+) "
    r"grasped=(\w+) placed=(\w+) ticks=(\d+)(?: decision=(\d+))? "
    r"reward=([-+0-9.eE]+) notes=(\[.*?\])(?: presentation|$)"
)
ACQ_ROW = re.compile(
    r"\[acq\] (\w+) idx=(\d+): "
    r"setup\[premove=(\S+) axis=(\S+) hover=(\S+) wait=(\S+) catchup=(\S+)\]s "
    r"catchup=(\d+)t res=(\S+)mm last=\(([^)]*)\)mm \| "
    r"close_start=\(([^)]*)\)mm vx0=(\S+) latch=(\w+)"
)
TRIG_ROW = re.compile(r"\[rl\] trigger=(\w+) lead=([\d.]+)s lateral=([\d.]+) "
                      r"reach=([\d.]+) finger=([\d.]+) frame=(\w+) encoder=(\w+) "
                      r"present=(\w+)( acq=on\(([^)]*)\))?")
FIRE_LEAD = re.compile(r"lead=([\d.]+)s/reach=([\d.]+)")
STAMP = re.compile(r"intercept trigger \([^)]*\)")
DY = re.compile(r"dy=([-+0-9.]+)cm")
DX = re.compile(r"dx=([-+0-9.]+)cm")
T_ARR = re.compile(r"t_arrive=([\d.]+)s")
SEED_ROW = re.compile(r"\[rl\] rollout: .*seeds=\[(\d+)\]")
WALL_ROW = re.compile(r"\[rl\] run wall end \S+ duration ([\d.]+)s")
POLICY_GATE = "policy closed on the fruit"


def say(*a):
    print(" ".join(str(x) for x in a), flush=True)


def floats(text):
    out = []
    for part in text.split(","):
        part = part.strip()
        try:
            out.append(float(part))
        except ValueError:
            out.append(float("nan"))
    return out


def read_log(path: str) -> dict:
    out = {"episodes": {}, "trigger": None, "wall": None, "seed": None}
    current = None
    for line in open(path, encoding="utf-8", errors="replace"):
        m = TRIG_ROW.search(line)
        if m:
            out["trigger"] = {
                "mode": m.group(1), "lead": float(m.group(2)),
                "lateral": float(m.group(3)), "reach": float(m.group(4)),
                "acq": m.group(9) is not None,
                "acq_args": (m.group(10) or "").strip(),
            }
            continue
        m = SEED_ROW.search(line)
        if m:
            out["seed"] = int(m.group(1))
            continue
        m = ENV_ROW.search(line)
        if m:
            current = int(m.group(1))
            out["episodes"].setdefault(
                current,
                {"index": current, "fruit": m.group(2), "grade": m.group(3),
                 "diameter": float(m.group(4)), "arm": m.group(6),
                 "acq": None, "success": None, "notes": ""},
            )
            continue
        m = ACQ_ROW.search(line)
        if m and current is not None:
            ep = out["episodes"].setdefault(current, {"index": current})
            if ep.get("acq") is None:
                ep["acq"] = {
                    "arm": m.group(1),
                    "premove_s": float(m.group(3)),
                    "hover_s": float(m.group(5)),
                    "wait_s": float(m.group(6)),
                    "catchup_s": float(m.group(7)),
                    "catchup_ticks": int(m.group(8)),
                    "residual_mm": float(m.group(9)),
                    "last_mm": floats(m.group(10)),
                    "close_start_mm": floats(m.group(11)),
                    "latch": m.group(13),
                }
            continue
        m = OUT_ROW.search(line)
        if m:
            index = int(m.group(1))
            ep = out["episodes"].setdefault(index, {"index": index})
            if ep.get("success") is not None:  # first row wins
                continue
            notes = m.group(12)
            lead = FIRE_LEAD.search(notes)
            dy, dx, ta = DY.search(notes), DX.search(notes), T_ARR.search(notes)
            ep.update(
                fruit=ep.get("fruit", m.group(2)),
                diameter=ep.get("diameter", float(m.group(3))),
                arm=ep.get("arm", m.group(5)),
                success=m.group(6) == "True",
                grasped=m.group(7) == "True",
                placed=m.group(8) == "True",
                ticks=int(m.group(9)),
                decision=int(m.group(10)) if m.group(10) else None,
                notes=notes,
                fire_lead=float(lead.group(1)) if lead else None,
                fire_reach=float(lead.group(2)) if lead else None,
                fire_dy=float(dy.group(1)) if dy else None,
                fire_dx=float(dx.group(1)) if dx else None,
                t_arrive=float(ta.group(1)) if ta else None,
            )
            continue
        m = WALL_ROW.search(line)
        if m:
            out["wall"] = float(m.group(1))
    out["episodes"] = [e for e in out["episodes"].values()
                       if e.get("success") is not None]
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
    for label in arms:
        arms[label].sort(key=lambda r: r["run"])
    return arms


def sign_p(better: int, worse: int) -> float:
    n = better + worse
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(better, n + 1)) / (2.0 ** n)


def fisher_p(a_ok: int, a_n: int, b_ok: int, b_n: int) -> float:
    """Two-sided Fisher exact on a 2x2 (`a_ok` of `a_n` vs `b_ok` of `b_n`)."""
    def hyper(x, n1, n2, k):
        return math.comb(n1, x) * math.comb(n2, k - x) / math.comb(n1 + n2, k)
    n1, n2 = a_n, b_n
    k = a_ok + b_ok
    if n1 == 0 or n2 == 0:
        return float("nan")
    obs = hyper(a_ok, n1, n2, k)
    lo = max(0, k - n2)
    hi = min(k, n1)
    return min(1.0, sum(hyper(x, n1, n2, k) for x in range(lo, hi + 1)
                        if hyper(x, n1, n2, k) <= obs * (1 + 1e-9)))


def counts(eps):
    right = [e for e in eps if e["arm"] == "right"]
    left = [e for e in eps if e["arm"] == "left"]
    return {
        "n": len(eps), "placed": sum(1 for e in eps if e["placed"]),
        "n_right": len(right), "right": sum(1 for e in right if e["placed"]),
        "n_left": len(left), "left": sum(1 for e in left if e["placed"]),
        "never": sum(1 for e in eps if not e["grasped"]),
        "cnp": sum(1 for e in eps if e["grasped"] and not e["placed"]),
    }


def rate(k: int, n: int) -> float:
    return (k / n) if n else float("nan")


def is_gate(e) -> bool:
    return POLICY_GATE in (e.get("notes") or "")


def median(vals):
    vals = [v for v in vals if v == v]
    return st.median(vals) if vals else float("nan")


def p90(vals):
    vals = sorted(v for v in vals if v == v)
    if not vals:
        return float("nan")
    return vals[min(len(vals) - 1, int(0.9 * (len(vals) - 1)))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="logs/p54/p1")
    ap.add_argument("--a", default="A")
    ap.add_argument("--b", default="B")
    args = ap.parse_args()
    A, B = args.a, args.b

    arms = load(args.dir, [A, B])
    for label in (A, B):
        if not arms[label]:
            say(f"no {label}_<run>.log in {args.dir}")
            return 2

    say("=" * 100)
    say("P54 phase 1 - the SHIPPED direct config (ACQ off, arm A) vs ACQ=1 (arm B)")
    say("=" * 100)

    # ---- [0] the manipulation check --------------------------------------- #
    say()
    say("[0] the manipulation check (the `[rl] trigger=` row of every file)")
    for label in (A, B):
        for rows in arms[label]:
            t = rows["trigger"]
            if t is None:
                say(f"  {rows['file']:<10s} NO trigger row "
                    f"(episodes={len(rows['episodes'])})")
                continue
            mark = ("acq=ON  " + (t["acq_args"] or "")) if t["acq"] else "acq=off"
            say(f"  {rows['file']:<10s} lead={t['lead']:.2f}s reach={t['reach']:.2f} "
                f"lateral={t['lateral']:.3f} -> {mark}")

    # ---- [1] per run ------------------------------------------------------ #
    say()
    say("[1] per run (placed = the `placed` flag; sim s = ticks/120)")
    say(f"  {'arm':<3s} {'run':<3s} {'seed':<5s} {'placed':>9s} {'right':>7s} "
        f"{'left':>6s} {'never':>6s} {'cnp':>4s} {'ticks_p50':>9s} {'s/att':>6s} "
        f"{'wall_s':>7s}")
    per_run = {}
    for label in (A, B):
        for rows in arms[label]:
            eps = rows["episodes"]
            c = counts(eps)
            t = median([e["ticks"] for e in eps])
            per_run[(label, rows["run"])] = {
                **c, "ticks": t, "sec": t / 120.0, "wall": rows["wall"],
                "seed": rows["seed"], "eps": eps,
            }
            say(f"  {label:<3s} {rows['run']:<3d} "
                f"{(rows['seed'] if rows['seed'] is not None else '-'):<5} "
                f"{c['placed']:>3d}/{c['n']:<3d} "
                f"{c['right']:>3d}/{c['n_right']:<3d} "
                f"{c['left']:>2d}/{c['n_left']:<2d} {c['never']:>6d} {c['cnp']:>4d} "
                f"{t:>9.0f} {t / 120.0:>6.2f} "
                f"{(rows['wall'] if rows['wall'] is not None else float('nan')):>7.1f}")

    # ---- [2] pooled ------------------------------------------------------- #
    say()
    say("[2] pooled per arm")
    say(f"  {'arm':<3s} {'placed':>9s} {'right':>9s} {'left':>8s} {'never-held':>10s} "
        f"{'cnp':>4s} {'ticks_p50':>9s} {'s/att':>6s} {'wall/ep':>8s}")
    pooled = {}
    for label in (A, B):
        eps = [e for rows in arms[label] for e in rows["episodes"]]
        c = counts(eps)
        t = median([e["ticks"] for e in eps])
        walls = [rows["wall"] for rows in arms[label] if rows["wall"]]
        pooled[label] = {**c, "ticks": t, "sec": t / 120.0, "eps": eps,
                         "wall_ep": (sum(walls) / len(eps)) if walls else float("nan")}
        p = pooled[label]
        say(f"  {label:<3s} {p['placed']:>3d}/{p['n']:<3d} "
            f"{p['right']:>3d}/{p['n_right']:<3d} "
            f"{p['left']:>2d}/{p['n_left']:<2d} {p['never']:>10d} {p['cnp']:>4d} "
            f"{p['ticks']:>9.0f} {p['sec']:>6.2f} {p['wall_ep']:>8.1f}")

    # ---- [3] E1 ----------------------------------------------------------- #
    say()
    say("[3] E1 - the right-arm placed delta (registered bar: A - B >= -0.10; "
        "negative = the shipped config is worse)")
    say(f"  {'seed-run':<9s} {'A right':>11s} {'B right':>11s} {'deltaA-B':>9s} "
        f"{'A placed':>10s} {'B placed':>10s} {'dA-B':>5s}")
    right_deltas, placed_deltas = [], []
    runs = sorted({rows["run"] for rows in arms[A]})
    for run in runs:
        a, b = per_run.get((A, run)), per_run.get((B, run))
        if a is None or b is None:
            continue
        # E1 is registered as rate_A - rate_B, so the per-run column uses the
        # same sign as the pooled verdict (negative = A, the shipped config, worse).
        da = rate(a["right"], a["n_right"]) - rate(b["right"], b["n_right"])
        dp = a["placed"] - b["placed"]
        right_deltas.append(da)
        placed_deltas.append(dp)
        say(f"  {run:<9d} {a['right']:>4d}/{a['n_right']:<6d} "
            f"{b['right']:>4d}/{b['n_right']:<6d} {da:>+9.3f} "
            f"{a['placed']:>7d}/{a['n']:<2d} {b['placed']:>7d}/{b['n']:<2d} "
            f"{dp:>+5d}")
    pa, pb = pooled[A], pooled[B]
    e1 = rate(pa["right"], pa["n_right"]) - rate(pb["right"], pb["n_right"])
    say(f"  pooled: A right {pa['right']}/{pa['n_right']} = "
        f"{rate(pa['right'], pa['n_right']):.3f} vs B right "
        f"{pb['right']}/{pb['n_right']} = {rate(pb['right'], pb['n_right']):.3f} "
        f"-> delta {e1:+.3f}")
    say(f"  E1 {'PASS' if e1 >= -0.10 else 'FAIL'} (bar -0.10); per-run right deltas "
        f"{[round(d, 3) for d in right_deltas]}, per-run placed deltas {placed_deltas}")
    worse_runs = sum(1 for d in right_deltas if d < 0)
    say(f"  run level: A's right arm is behind in {worse_runs}/{len(right_deltas)} runs "
        f"(a 3-run design's smallest one-sided sign p is 2^-3 = 0.125, so the run "
        f"level can only be reported, never gated)")

    for side in ("right", "both"):
        better = worse = both_ok = both_fail = mismatched = 0
        for run in runs:
            a_rows = {e["index"]: e for e in per_run[(A, run)]["eps"]
                      if side == "both" or e["arm"] == side}
            b_rows = {e["index"]: e for e in per_run[(B, run)]["eps"]
                      if side == "both" or e["arm"] == side}
            for index in sorted(set(a_rows) & set(b_rows)):
                x, y = a_rows[index], b_rows[index]
                if x.get("fruit") != y.get("fruit"):
                    mismatched += 1
                    continue
                if x["placed"] and y["placed"]:
                    both_ok += 1
                elif x["placed"] and not y["placed"]:
                    worse += 1
                elif y["placed"] and not x["placed"]:
                    better += 1
                else:
                    both_fail += 1
        say(f"  paired ({side}, same fruit): {both_ok} both placed, {both_fail} both fail, "
            f"{better} B-only placed, {worse} A-only placed, {mismatched} excluded "
            f"(fruit differs); sign test (B better) p = {sign_p(better, worse):.4f}")

    # ---- [4] E2a ---------------------------------------------------------- #
    say()
    say("[4] E2a - the never-held class (`grasped=False`), the ACQ knob's own target")
    say(f"  {'arm':<3s} {'side':<6s} {'n':>4s} {'never':>6s} {'rate':>7s} "
        f"{'trigger-path':>13s} {'policy-gate':>12s}")
    for label in (A, B):
        for side in ("right", "left", "both"):
            sel = [e for e in pooled[label]["eps"] if side in (e["arm"], "both")]
            never = [e for e in sel if not e["grasped"]]
            trig = sum(1 for e in never if not is_gate(e))
            gate = sum(1 for e in never if is_gate(e))
            say(f"  {label:<3s} {side:<6s} {len(sel):>4d} {len(never):>6d} "
                f"{rate(len(never), len(sel)):>7.3f} {trig:>13d} {gate:>12d}")
    fp = fisher_p(pa["never"], pa["n"], pb["never"], pb["n"])
    say(f"  never-held pooled: A {pa['never']}/{pa['n']} = {rate(pa['never'], pa['n']):.3f} "
        f"vs B {pb['never']}/{pb['n']} = {rate(pb['never'], pb['n']):.3f} "
        f"(two-sided Fisher p = {fp:.3f})")
    fp_r = fisher_p(
        sum(1 for e in pooled[A]["eps"] if e["arm"] == "right" and not e["grasped"]),
        pa["n_right"],
        sum(1 for e in pooled[B]["eps"] if e["arm"] == "right" and not e["grasped"]),
        pb["n_right"],
    )
    say(f"  right arm only: A "
        f"{sum(1 for e in pooled[A]['eps'] if e['arm'] == 'right' and not e['grasped'])}"
        f"/{pa['n_right']} vs B "
        f"{sum(1 for e in pooled[B]['eps'] if e['arm'] == 'right' and not e['grasped'])}"
        f"/{pb['n_right']} (Fisher p = {fp_r:.3f})")
    for label in (A, B):
        rows = [e for e in pooled[label]["eps"] if not e["grasped"]]
        if not rows:
            say(f"  {label}: no never-held episode")
            continue
        say(f"  {label} never-held rows: " + "; ".join(
            f"ep{e['index']} {e['fruit']} {e['arm']} "
            f"res={'n/a' if not e.get('acq') else round(e['acq']['residual_mm'], 1)}mm "
            f"close_y={'n/a' if not e.get('acq') else round(e['acq']['close_start_mm'][1], 1)}"
            f"mm t_arrive={e.get('t_arrive')} lead={e.get('fire_lead')}"
            for e in rows))

    # ---- [5] E2b: the mechanism ------------------------------------------- #
    say()
    say("[5] E2b - the acquisition mechanism from the `[acq]` rows")
    say(f"  {'arm':<3s} {'side':<6s} {'n':>3s} {'res_p50':>8s} {'res_p90':>8s} "
        f"{'res_max':>8s} {'>6mm':>7s} {'catchup_t':>10s} {'close|y|p50':>12s} "
        f"{'close|y|max':>12s} {'t_arrive':>9s} {'hover':>6s} {'wait':>6s}")
    for label in (A, B):
        for side in ("right", "left", "both"):
            eps = [e for e in pooled[label]["eps"] if side in (e["arm"], "both")]
            res = [e["acq"]["residual_mm"] for e in eps if e.get("acq")]
            tick = [e["acq"]["catchup_ticks"] for e in eps if e.get("acq")]
            cy = [abs(e["acq"]["close_start_mm"][1]) for e in eps
                  if e.get("acq") and len(e["acq"]["close_start_mm"]) > 1]
            ta = [e["t_arrive"] for e in eps if e.get("t_arrive") is not None]
            hov = [e["acq"].get("hover_s") for e in eps
                   if e.get("acq") and e["acq"].get("hover_s") is not None]
            wai = [e["acq"].get("wait_s") for e in eps
                   if e.get("acq") and e["acq"].get("wait_s") is not None]
            if not res:
                say(f"  {label:<3s} {side:<6s} {len(eps):>3d} (no [acq] rows)")
                continue
            over = sum(1 for v in res if v > 6.0)
            say(f"  {label:<3s} {side:<6s} {len(res):>3d} {median(res):>8.2f} "
                f"{p90(res):>8.2f} {max(res):>8.2f} {over:>3d}/{len(res):<3d} "
                f"{median(tick):>10.0f} {median(cy):>12.2f} "
                f"{(max(cy) if cy else float('nan')):>12.2f} {median(ta):>9.2f} "
                f"{median(hov):>6.2f} {median(wai):>6.2f}")
    say("  columns `t_arrive` = the belt time left at the fire tick (the arm's budget); "
        "`hover`/`wait` = the handover's own stamps **from its start** (the primitive's "
        "`t0`), so the fire->handover dispatch sits between the two columns and is not "
        "logged. The measured miss is the `res` column, not this arithmetic.")
    say("  the fire geometry (the knob's own actuation; `lead`/`reach` are only "
        "recorded with ACQ on):")
    for label in (A, B):
        eps = pooled[label]["eps"]
        lead = [e["fire_lead"] for e in eps if e.get("fire_lead") is not None]
        dyv = [abs(e["fire_dy"]) for e in eps if e.get("fire_dy") is not None]
        say(f"    {label}: n_lead={len(lead)}"
            + (f" lead p50={median(lead):.2f}s min={min(lead):.2f} max={max(lead):.2f}"
               if lead else " (not recorded: ACQ off, the shipped 0.90 s)")
            + f" | |dy| p50={median(dyv):.1f}cm max={max(dyv) if dyv else float('nan'):.1f}"
            f" | runaway/zone-fruit rows {sum(1 for v in dyv if v > 40)}/{len(dyv)}")
    say("  never-held subset only:")
    for label in (A, B):
        eps = [e for e in pooled[label]["eps"] if not e["grasped"]]
        if not eps:
            say(f"    {label}: none")
            continue
        vals = [(e["acq"]["residual_mm"], e["acq"]["close_start_mm"][1])
                for e in eps if e.get("acq")]
        if not vals:
            say(f"    {label}: {len(eps)} never-held, no [acq] rows")
            continue
        say(f"    {label}: n={len(vals)} res={[round(v[0], 1) for v in vals]} "
            f"close_y={[round(v[1], 1) for v in vals]}")

    # ---- [6] E3 ----------------------------------------------------------- #
    say()
    say("[6] E3 - failure reasons (the `intercept trigger (...)` stamp removed: its "
        "lead/reach suffix exists only with ACQ on)")
    def reasons(eps):
        out = {}
        for e in eps:
            if e["placed"]:
                continue
            text = STAMP.sub("", e.get("notes") or "")
            # the note list's own syntax is not part of a reason: drop brackets,
            # quotes and separators, then collapse the whitespace they leave.
            text = " ".join(re.sub(r"[\[\]',]+", " ", text).split())
            key = re.sub(r"[-+0-9.]+", "#", text) if text else "trigger-stamp only"
            out[key] = out.get(key, 0) + 1
        return out
    ra, rb = reasons(pooled[A]["eps"]), reasons(pooled[B]["eps"])
    for label, table in ((A, ra), (B, rb)):
        say(f"  {label} ({sum(table.values())} failures): " +
            ("; ".join(f"{k!r} x{v}" for k, v in sorted(table.items())) or "none"))
    new_in_b = sorted(set(rb) - set(ra))
    new_in_a = sorted(set(ra) - set(rb))
    say(f"  B-only keys: {new_in_b or 'none'}")
    say(f"  A-only keys: {new_in_a or 'none'}")
    say(f"  E3 {'PASS' if not new_in_b else 'FAIL'} (baseline = A, the shipped config)")

    # ---- [7] the left arm -------------------------------------------------- #
    say()
    say("[7] the left arm (reported, not an endpoint: the closed carried-not-placed "
        "class, `logs/p42/SIM_LIMIT.md`)")
    for label in (A, B):
        eps = [e for e in pooled[label]["eps"] if e["arm"] == "left"]
        cnp = [e for e in eps if e["grasped"] and not e["placed"]]
        never = [e for e in eps if not e["grasped"]]
        sl = [e["acq"]["residual_mm"] for e in eps if e.get("acq")]
        say(f"  {label}: placed {sum(1 for e in eps if e['placed'])}/{len(eps)}, "
            f"cnp {len(cnp)}, never-held {len(never)}, "
            f"catch-up res p50 {median(sl):.1f}mm, "
            f"s/att {median([e['ticks'] for e in eps]) / 120.0:.2f}")

    # ---- [8] the file set -------------------------------------------------- #
    say()
    say("[8] the file set")
    for label in (A, B):
        for rows in arms[label]:
            say(f"  {rows['file']:<10s} seed={rows['seed']} "
                f"episodes={len(rows['episodes'])} "
                f"acq_rows={sum(1 for e in rows['episodes'] if e.get('acq'))} "
                f"wall={rows['wall']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
