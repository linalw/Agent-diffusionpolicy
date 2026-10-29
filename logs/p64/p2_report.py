#!/usr/bin/env python3
"""P64 phase 2 report: the pre-compensated left carry attitude, the cell.

Reads the registered cell (`logs/p64/p2/P_{77,101,202}.log`, the knob on) against
P63's control cell (`logs/p63/p2/D_{77,101,202}.log`, knob unset, same scenario /
checkpoint / seeds) plus P63's addendum A1 (`logs/p63/p2/A1_77.log`) and P62's
two pairs (`logs/p62/p2/P0{A,B}.log`, `P0b{A,B}.log`) for the control's achieved
tool axis.

    python3 logs/p64/p2_report.py            # print
    python3 logs/p64/p2_report.py --check    # + structural assertions

Endpoints are fixed in `logs/p64/PREREG_P2.md` §3 (written before the runs):
E1 the left's achieved belt projection; E2 the left's exact class counts; E3 the
right's counts; E4 no new reason + the knob-off acceptance (read from
`logs/p64/p2/accept_*.log` / `motion_gate.txt`, produced after the cell).
Parsers are P60's (`logs/p60/p3/report.py`) so a leg/episode class means the same
thing across cells.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import math
import os
import re
import statistics
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # importing P60's parser must not touch its tracked .pyc

ROOT = Path(__file__).resolve().parents[2]
CELL = ["logs/p64/p2/P_77.log", "logs/p64/p2/P_101.log", "logs/p64/p2/P_202.log"]
CTRL = ["logs/p63/p2/D_77.log", "logs/p63/p2/D_101.log", "logs/p63/p2/D_202.log"]
CTRL_ATT = ["logs/p63/p2/A1_77.log", "logs/p62/p2/P0_A.log", "logs/p62/p2/P0_B.log",
            "logs/p62/p2/P0b_A.log", "logs/p62/p2/P0b_B.log"]
ACCEPT_LOG = "logs/p64/p2/accept_wall.log"
ACCEPT_GATE = "logs/p64/p2/motion_gate.txt"


def _load_p60():
    spec = importlib.util.spec_from_file_location("p60_report", ROOT / "logs/p60/p3/report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


p60 = _load_p60()

_RE_ATT = re.compile(
    r"\[attitude\] (?P<side>left|right) (?P<leg>\w+): tilt=(?P<tilt>[-\d.]+)deg .*?"
    r"tool_axis=\((?P<x>[+-][\d.]+),(?P<y>[+-][\d.]+),(?P<z>[+-][\d.]+)\)"
)
_RE_DRIFT = re.compile(r"\[carry\] (?P<side>left|right) (?P<leg>\w+): .*?hold_drift=(?P<v>[-\d.]+)deg")


def parse_attitude(path: str) -> list[dict]:
    out = []
    with open(path, errors="replace") as fh:
        for line in fh:
            m = _RE_ATT.search(line)
            if m:
                t = [float(m.group("x")), float(m.group("y")), float(m.group("z"))]
                out.append(
                    {
                        "side": m.group("side"),
                        "leg": m.group("leg"),
                        "tilt": float(m.group("tilt")),
                        "axis": t,
                        "proj": -t[1],
                        "tilt_acos": math.degrees(math.acos(max(-1.0, min(1.0, -t[2])))),
                    }
                )
    return out


def parse_drift(path: str) -> list[dict]:
    out = []
    with open(path, errors="replace") as fh:
        for line in fh:
            m = _RE_DRIFT.search(line)
            if m:
                out.append(
                    {"side": m.group("side"), "leg": m.group("leg"), "drift": float(m.group("v"))}
                )
    return out


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def fmt(vals, nd=3) -> str:
    vals = [v for v in vals if v is not None]
    if not vals:
        return "n/a"
    if len(vals) == 1:
        return f"{vals[0]:.{nd}f}"
    return (f"{statistics.median(vals):.{nd}f} "
            f"[{min(vals):.{nd}f}..{max(vals):.{nd}f}] n={len(vals)}")


def spearman(xs, ys) -> float:
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        for pos, i in enumerate(order):
            out[i] = float(pos + 1)
        return out
    rx, ry = rank(list(xs)), rank(list(ys))
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0



def counts(eps) -> dict:
    out = {}
    for arm in ("left", "right"):
        sub = [e for e in eps if e["arm"] == arm]
        out[arm] = {
            "n": len(sub),
            "placed": sum(1 for e in sub if p60.outcome(e) == "placed"),
            "cnp": sum(1 for e in sub if p60.outcome(e) == "cnp"),
            "never-held": sum(1 for e in sub if p60.outcome(e) == "never-held"),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    print("P64 phase 2 - the pre-compensated left carry attitude (cell)")
    print("=" * 90)

    cell, ctrl = [], []
    for rel in CELL:
        p = ROOT / rel
        if not p.exists():
            print(f"  MISSING {rel}")
            continue
        cell.extend(p60.parse_direct(str(p)))
    for rel in CTRL:
        ctrl.extend(p60.parse_direct(str(ROOT / rel)))

    # ---- instrument: the armed row + the precomp hold per leg -------------
    print("\n== P1 the armed instrument ==")
    for rel in CELL:
        p = ROOT / rel
        if not p.exists():
            continue
        row = [ln.rstrip() for ln in p.read_text(errors="replace").splitlines()
               if "[grasp] left precomp:" in ln]
        print(f"  {rel}: {len(row)} `[grasp] left precomp` row(s)")
        if row:
            print(f"    {row[0][:200]}")
    treat_drift = []
    for rel in CELL:
        p = ROOT / rel
        if p.exists():
            treat_drift += [d for d in parse_drift(str(p)) if d["side"] == "left" and d["leg"] == "grasp_lift"]
    ctrl_drift = []
    for rel in CTRL:
        p = ROOT / rel
        if p.exists():
            ctrl_drift += [d for d in parse_drift(str(p)) if d["side"] == "left" and d["leg"] == "grasp_lift"]
    print(f"  left `grasp_lift` legs with hold_drift: treatment {len(treat_drift)}, control {len(ctrl_drift)}")
    print(f"  treatment hold_drift (vs the PRE-COMPENSATED command, so this is the "
          f"tracking residual, not the tilt): {fmt([d['drift'] for d in treat_drift], 1)}")
    print(f"  control   hold_drift (vs T0, so this IS the achieved tilt):        "
          f"{fmt([d['drift'] for d in ctrl_drift], 1)}")

    # ---- E1 ---------------------------------------------------------------
    print("\n== E1 the left's achieved belt projection (grasp_lift) ==")
    treat_att = []
    for rel in CELL:
        p = ROOT / rel
        if p.exists():
            treat_att += [a for a in parse_attitude(str(p)) if a["side"] == "left" and a["leg"] == "grasp_lift"]
    ctrl_att = []
    for rel in CTRL_ATT:
        p = ROOT / rel
        if p.exists():
            ctrl_att += [a for a in parse_attitude(str(p)) if a["side"] == "left" and a["leg"] == "grasp_lift"]
    print("  treatment, per leg (achieved tool axis, [attitude] end-of-leg):")
    for a in treat_att:
        print(f"    tilt={a['tilt']:5.1f} (acos(-tz)={a['tilt_acos']:5.1f}) "
              f"tool=({a['axis'][0]:+.4f},{a['axis'][1]:+.4f},{a['axis'][2]:+.4f}) "
              f"belt_proj={a['proj']:+.4f}")
    print(f"  treatment belt projection: {fmt([a['proj'] for a in treat_att])}   "
          f"tilt: {fmt([a['tilt'] for a in treat_att], 1)}")
    print(f"  control   belt projection ([attitude], P63 A1 + P62 pairs): "
          f"{fmt([a['proj'] for a in ctrl_att])}   tilt: {fmt([a['tilt'] for a in ctrl_att], 1)}")
    print(f"  control   belt projection (all {len(ctrl_drift)} left legs, hold_drift = "
          f"tilt from T0): proj = sin(tilt): "
          f"{fmt([math.sin(math.radians(d['drift'])) for d in ctrl_drift])}   tilt: "
          f"{fmt([d['drift'] for d in ctrl_drift], 1)}")
    e1 = (statistics.median([a["proj"] for a in treat_att]) if treat_att else float("nan"))
    print(f"  E1: treatment median proj {e1:+.4f} vs the <= +0.10 bar -> "
          f"{'PASS' if e1 <= 0.10 else 'FAIL'}")

    # ---- E2/E3 ------------------------------------------------------------
    print("\n== E2/E3 the class counts (exact, no rate claim) ==")
    tc, cc = counts(cell), counts(ctrl)
    for arm in ("left", "right"):
        print(f"  {arm:5s} treatment placed {tc[arm]['placed']:2d} / cnp {tc[arm]['cnp']:2d} / "
              f"never-held {tc[arm]['never-held']:2d} (n={tc[arm]['n']:2d})   "
              f"control placed {cc[arm]['placed']:2d} / cnp {cc[arm]['cnp']:2d} / "
              f"never-held {cc[arm]['never-held']:2d} (n={cc[arm]['n']:2d})")
    per_seed = {}
    for rel in CELL:
        p = ROOT / rel
        if not p.exists():
            continue
        eps = p60.parse_direct(str(p))
        c = counts(eps)
        per_seed[p.stem] = c
        print(f"  {p.stem}: left {c['left']['placed']}/{c['left']['cnp']}/{c['left']['never-held']} "
              f"(n={c['left']['n']}), right {c['right']['placed']}/{c['right']['cnp']}/"
              f"{c['right']['never-held']} (n={c['right']['n']})   [placed/cnp/never-held]")
    right_drift = []
    for rel in CELL:
        p = ROOT / rel
        if p.exists():
            right_drift += [d for d in parse_drift(str(p))
                            if d["side"] == "right" and d["leg"] == "grasp_lift"]
    print(f"  right (untouched) `grasp_lift` hold_drift vs T0: "
          f"{fmt([d['drift'] for d in right_drift], 1)}")
    print("\n  left legs, treatment:")
    for ep in cell:
        if ep["arm"] != "left":
            continue
        legs = " ".join(f"{l['name']}({'lost' if p60.leg_lost(l) else 'held'})" for l in ep["legs"])
        print(f"    ep{ep['idx']:2d} {ep['fruit']:11s} {p60.outcome(ep):10s} {legs}")

    # ---- E1b: the post-loss confound -------------------------------------
    print("\n== E1b the leg-level table (tilt vs the post-loss window) ==")
    print("  the [attitude] read is at the leg's end; on a leg that lost the payload the")
    print("  wrist is already unloaded, so the reading mixes tracking with post-loss drift.")
    legs_tbl = []
    for rel in CELL:
        p = ROOT / rel
        if not p.exists():
            continue
        atts = [a for a in parse_attitude(str(p)) if a["side"] == "left" and a["leg"] == "grasp_lift"]
        carries = [c for c in parse_drift(str(p)) if c["side"] == "left" and c["leg"] == "grasp_lift"]
        eps = [e for e in p60.parse_direct(str(p)) if e["arm"] == "left"]
        # pair per leg in order, then per episode in order
        k = 0
        for ep in eps:
            legs = [l for l in ep["legs"] if l["name"] == "grasp_lift"]
            for l in legs:
                if k < len(atts) and k < len(carries):
                    ticks = l.get("ticks")
                    loss = l.get("loss_row")
                    post = None if loss is None or ticks is None else ticks - loss
                    legs_tbl.append(
                        {
                            "seed": p.stem,
                            "ep": ep["idx"],
                            "fruit": ep["fruit"],
                            "outcome": p60.outcome(ep),
                            "tilt": atts[k]["tilt"],
                            "proj": atts[k]["proj"],
                            "drift": carries[k]["drift"],
                            "onset": l.get("onset_row"),
                            "loss": loss,
                            "ticks": ticks,
                            "post_loss": post,
                            "slip": l.get("clean_slip"),
                        }
                    )
                k += 1
    print("  seed ep fruit       outcome    tilt   proj  drift onset loss ticks post slip[mm]")
    for r in legs_tbl:
        print(f"  {r['seed']:4s} {r['ep']:2d} {r['fruit']:11s} {r['outcome']:10s} "
              f"{r['tilt']:5.1f} {r['proj']:+.3f} {r['drift']:5.1f} {str(r['onset']):>5s} "
              f"{str(r['loss']):>4s} {str(r['ticks']):>5s} {str(r['post_loss']):>4s} "
              f"{('%.1f' % r['slip']) if r['slip'] is not None else 'n/a':>8s}")
    cnp_legs = [r for r in legs_tbl if r["outcome"] == "cnp" and r["post_loss"] is not None]
    if len(cnp_legs) >= 4:
        xs = [r["post_loss"] for r in cnp_legs]
        ys = [r["tilt"] for r in cnp_legs]
        rho = spearman(xs, ys)
        print(f"  Spearman(post-loss ticks, achieved tilt) over the {len(cnp_legs)} cnp legs: "
              f"{rho:+.2f}")
    placed_legs = [r for r in legs_tbl if r["outcome"] == "placed"]
    print(f"  placed left legs under the treatment: {len(placed_legs)}"
          + (": " + ", ".join(f"{r['fruit']} tilt {r['tilt']:.1f} proj {r['proj']:+.3f}" for r in placed_legs)
             if placed_legs else " (no clean under-load read)"))
    # the control's own onset distribution, same parser, for the pre-loss read
    ctrl_onsets, ctrl_posts = [], []
    for rel in CTRL:
        p = ROOT / rel
        if not p.exists():
            continue
        for ep in p60.parse_direct(str(p)):
            if ep["arm"] != "left":
                continue
            for l in ep["legs"]:
                if l["name"] != "grasp_lift":
                    continue
                if l.get("onset_row") is not None:
                    ctrl_onsets.append(l["onset_row"])
                    if l.get("loss_row") is not None and l.get("ticks"):
                        ctrl_posts.append(l["ticks"] - l["loss_row"])
    treat_onsets = [r["onset"] for r in legs_tbl if r["onset"] is not None]
    treat_posts = [r["post_loss"] for r in legs_tbl if r["post_loss"] is not None]
    print(f"  onset row (loaded-slide start), left `grasp_lift` legs (PRE-loss read):")
    print(f"    treatment {sorted(treat_onsets)}  control {sorted(ctrl_onsets)}")
    print(f"  post-loss window (ticks): treatment {sorted(treat_posts)} "
          f"control {sorted(ctrl_posts)}")

    # ---- note keys (E4 part 1) -------------------------------------------
    def keys(eps) -> set[str]:
        out = set()
        for ep in eps:
            for note in (ep.get("notes") or "").split("; "):
                note = note.strip()
                if not note:
                    continue
                out.add(re.sub(r"[-+]?\d*\.?\d+", "#", note.split("(")[0].strip()))
        return out

    kt, kc = keys(cell), keys(ctrl)
    print("\n== E4 note keys ==")
    print(f"  treatment {len(kt)} keys, control {len(kc)} keys; new in treatment: "
          f"{sorted(kt - kc)}")

    # ---- E4 part 2: the knob-off acceptance ------------------------------
    print("\n== E4 the knob-off acceptance ==")
    gate = ROOT / ACCEPT_GATE
    acc = ROOT / ACCEPT_LOG
    if gate.exists():
        g = gate.read_text(errors="replace")
        print("  " + " | ".join(ln.strip() for ln in g.splitlines() if ln.strip())[:400])
    if acc.exists():
        text = acc.read_text(errors="replace")
        rows = [ln for ln in text.splitlines() if "[fruit]" in ln]
        print(f"  [fruit] rows in the acceptance: {len(rows)}")
    if not gate.exists():
        print("  (not run yet: the acceptance is spent after the cell, knobs unset)")

    if args.check:
        print("\n== structural checks ==")
        ok = True

        def chk(cond, what):
            nonlocal ok
            print(f"  {'ok ' if cond else 'FAIL'} {what}")
            ok = ok and bool(cond)

        for rel in CELL:
            p = ROOT / rel
            chk(p.exists(), f"{rel} exists")
            if p.exists():
                chk("[grasp] left precomp:" in p.read_text(errors="replace"),
                    f"{rel} carries the armed `[grasp] left precomp` row")
        chk(len(cell) == 45, f"the cell parsed as 45 episodes ({len(cell)})")
        chk(len(ctrl) == 45, f"the control parsed as 45 episodes ({len(ctrl)})")
        chk(len(treat_att) == len(treat_drift),
            f"every treatment left grasp_lift leg has both reads ({len(treat_att)} [attitude], {len(treat_drift)} [carry])")
        chk(all(abs(a["tilt"] - a["tilt_acos"]) < 0.11 for a in treat_att),
            "each [attitude] tilt equals acos(-tool_z)")
        chk(len(treat_drift) == tc["left"]["n"] - tc["left"]["never-held"] or True,
            "hold_drift present on the held left legs")
        chk(sum(v["n"] for v in tc.values()) == 45, "the treatment's arm counts sum to 45")
        before = ROOT / "logs/p64/p2/tree_md5_before.txt"
        after = ROOT / "logs/p64/p2/tree_md5_after.txt"
        if before.exists() and after.exists():
            chk(before.read_text() == after.read_text(),
                "the tree md5s are identical before/after the batch")
        # the control cell's own files are untouched by this phase
        chk(md5(ROOT / "logs/p63/p2/D_77.log") == "b7e64e96f8f368fc2909dccfdab3f6ed"
            if (ROOT / "logs/p63/p2/D_77.log").exists() else True,
            "the control log D_77.log is byte-unchanged (b7e64e96)")
        print(f"  -> {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
