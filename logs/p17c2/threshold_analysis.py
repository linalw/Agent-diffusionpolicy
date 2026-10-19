#!/usr/bin/env python3
"""P18-C: the slide gate's trigger threshold - the data-driven calibration check.

The P17-B hold/probe-1 slide gate (`FRUIT_DYNAMIC_SLIDE_GATE`, default off) fires
when the payload's hand-frame drift *rate* stays above
`FRUIT_DYNAMIC_SLIDE_GATE_MMPS` (default 60) for
`FRUIT_DYNAMIC_SLIDE_GATE_TICKS` (default 3) consecutive per-tick samples while
the accumulated hand-frame drift is inside `FRUIT_DYNAMIC_SLIDE_GATE_WINDOW_MM`
(default 60).  The Oracle's Gate review (`logs/p17i/ORACLE_GATE.md` item 8) found
the trigger fired on 7/20 attempts at seed 11 including 3 that placed, with peaks
up to 275 mm/s - i.e. the 60 mm/s threshold may sit *inside* the ok population's
per-tick transient range.  This tool recomputes the per-tick rate from the
on-disk traces and decides whether a separating (threshold, ticks, window) triple
exists.

The rate recipe (the gate's own, `_slide_gate_observe`): the payload centre minus
the pads' measured centre in the *world* frame, per tick, over `CONTROL_DT`; the
accumulated drift is the same vector in the hand frame against the phase span's
first sample.  On this asset the OpenArm hand's `pad_centre()` *is*
`arm.jaw_centre()` (`kinematic_gripper.OpenArmHand`), and the trace's `jaw` field
is `(jaw_left + jaw_right) / 2` from the same `arm.jaw_positions()` - so the trace
reproduces the gate's `rel_world` exactly:

    rel_world(t) = fruit(t) - jaw(t)          [world, m]
    rate(t)      = |rel_world(t) - rel_world(t-1)| / dt      [mm/s]
    drift(t)     = |hand_rel(t) - hand_rel(ref)|             [mm]
                   hand_rel = rot.T @ (fruit - jaw)   (the trace's own field)

The mission's hand-frame variant `|hand_rel(t) - hand_rel(t-1)| / dt` is computed
as a sensitivity column.  Trace sampling: the `hold` phase is sampled every *2*
ticks (24 rows / 48 ticks) while the gate samples every tick; `probe1` (the first
`takeoff_probe` block) is sampled every tick (60 rows / 60 ticks) and matches the
gate sample-for-sample.  The hold's 2-tick sampling is a resolution limit carried
through the analysis (it can only *understate* the gate's true peak); section
"VALIDATION" measures it against the gate's own `[slide]` rows on the gate-ON
corpora.

Corpora (all read-only):
  * controls  - logs/p14b/traces_{s11,s5,s23} + the P14-B classification
                (ok / carried / B1 / B2, `trace_p14b_analysis.py`'s rule);
  * gate-ON   - logs/p17i/traces_p_{s11,s5,s23} + the `[run]`/`[biarm]` labels
                (ok / no-grasp / carried); traces_m1 == traces_p_s11 (byte
                identical, the M1 screen run *is* the stage-P seed-11 primary).

Usage:  python3 logs/p17c2/threshold_analysis.py > logs/p17c2/threshold_tables.txt
Writes only under logs/p17c2/.
"""
from __future__ import annotations

import glob
import json
import math
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent

# --------------------------------------------------------------------------- #
# corpora
# --------------------------------------------------------------------------- #
CONTROL = [
    ("s11", ROOT / "logs/p14b/10_seed11_trace.log", ROOT / "logs/p14b/traces_s11"),
    ("s5", ROOT / "logs/p14b/11_seed5_trace.log", ROOT / "logs/p14b/traces_s5"),
    ("s23", ROOT / "logs/p14b/12_seed23_trace.log", ROOT / "logs/p14b/traces_s23"),
]
GATE = [
    ("s11", ROOT / "logs/p17i/50_seed11_slide.log", ROOT / "logs/p17i/traces_p_s11"),
    ("s5", ROOT / "logs/p17i/52_seed5_slide.log", ROOT / "logs/p17i/traces_p_s5"),
    ("s23", ROOT / "logs/p17i/54_seed23_slide.log", ROOT / "logs/p17i/traces_p_s23"),
]

RESULT_RE = re.compile(
    r"\[biarm\] result (\w+) index=(\d+) (\w+) grasped=(\w+) placed=(\w+) "
    r"lift=([+-][0-9.]+) force=([0-9.]+) sim=([0-9.]+)s"
)
ATT_RE = re.compile(
    r"\[run\] attempt (\d+) \((\w+)\): grasped=(\w+) placed=(\w+) "
    r"lift=([+-][0-9.]+) m force=([0-9.]+) N sim=([0-9.]+)s notes=(.*)"
)
WIN_RE = re.compile(
    r"\[run\] attempt (\d+) \((\w+)\): picking (\w+) grade (\w+) .* sim=([0-9.]+)-([0-9.]+)s"
)
SLIDE_RESP_RE = re.compile(
    r"\[slide\] (\w+) idx=(\d+) (\w+) response=(\d+)/(\d+) trig@(\d+) "
    r"rate=([0-9.]+)mm/s drift=([0-9.]+)mm step=([0-9.]+)mm post=([0-9.]+)mm/s end=(\w+)"
)
SLIDE_SUM_RE = re.compile(
    r"\[slide\] (\w+) idx=(\d+) (\w+) summary ticks=(\d+) events=(\d+) "
    r"rate_max=([0-9.]+)mm/s drift_max=([0-9.]+)mm"
)

THRESHOLDS = [40, 60, 80, 100, 120, 150, 200, 250, 300]
DT = 1.0 / 120.0


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
def parse_log(path: Path):
    results, wins, slide = [], [], []
    for ln, line in enumerate(open(path, errors="replace"), 1):
        m = RESULT_RE.search(line)
        if m:
            results.append(dict(
                side=m.group(1), index=int(m.group(2)), species=m.group(3),
                grasped=m.group(4) == "True", placed=m.group(5) == "True",
                lift=float(m.group(6)), force=float(m.group(7)),
                sim=float(m.group(8)), line=ln))
        m = WIN_RE.search(line)
        if m:
            wins.append(dict(att=int(m.group(1)), side=m.group(2),
                             species=m.group(3), grade=m.group(4),
                             t0=float(m.group(5)), t1=float(m.group(6)), line=ln))
        m = SLIDE_RESP_RE.search(line)
        if m:
            slide.append(dict(kind="resp", side=m.group(1), idx=int(m.group(2)),
                              phase=m.group(3), used=int(m.group(4)),
                              budget=int(m.group(5)), trig_tick=int(m.group(6)),
                              trig_rate=float(m.group(7)), trig_drift=float(m.group(8)),
                              step=float(m.group(9)), post=float(m.group(10)),
                              end=m.group(11), line=ln))
            continue
        m = SLIDE_SUM_RE.search(line)
        if m:
            slide.append(dict(kind="sum", side=m.group(1), idx=int(m.group(2)),
                              phase=m.group(3), ticks=int(m.group(4)),
                              events=int(m.group(5)), rate_max=float(m.group(6)),
                              drift_max=float(m.group(7)), line=ln))
    return results, wins, slide


def probe_blocks(rows):
    """Split takeoff_probe rows at the t-jumps (the P14-B analyzer's rule)."""
    blocks = []
    for r in rows:
        if r["phase"] != "takeoff_probe":
            continue
        if blocks and r["t"] - blocks[-1][-1]["t"] <= 0.02:
            blocks[-1].append(r)
        else:
            blocks.append([r])
    return blocks


def load_attempt(path: Path):
    """One trace file -> the monitored span's rate/drift sequences + the labels."""
    d = json.load(open(path))
    rows = d["rows"]
    holds = [r for r in rows if r["phase"] == "hold"]
    blocks = probe_blocks(rows)
    p1 = blocks[0] if blocks else []
    span = holds + p1
    if not holds:
        return None
    ref = holds[0]["hand_rel"]
    rates_world, rates_hand, drifts, phases = [], [], [], []
    for i, r in enumerate(span):
        phases.append(r["phase"])
        drifts.append(math.dist(r["hand_rel"], ref) * 1000.0)
        if i == 0:
            rates_world.append(0.0)          # the gate's first sample: reference
            rates_hand.append(0.0)
            continue
        a = span[i - 1]
        dt = r["t"] - a["t"]
        rw = [r["fruit"][k] - r["jaw"][k] for k in range(3)]
        rw0 = [a["fruit"][k] - a["jaw"][k] for k in range(3)]
        rates_world.append(math.dist(rw, rw0) / dt * 1000.0)
        rates_hand.append(math.dist(r["hand_rel"], a["hand_rel"]) / dt * 1000.0)
    n_hold = len(holds)
    return dict(
        file=path.name, arm=d.get("arm"), outcome=d.get("outcome"),
        rows=rows, span=span, phases=phases, rates_world=rates_world,
        rates_hand=rates_hand, drifts=drifts, n_hold=n_hold, n_p1=len(p1),
        n_blocks=len(blocks), t0=rows[0]["t"], t1=rows[-1]["t"],
    )


def classify_control(att, res):
    """The P14-B rule (`trace_p14b_analysis.py:369`)."""
    if att["outcome"] == "ok":
        return "ok"
    if res and res["grasped"] and not res["placed"]:
        return "carried"
    return "B1" if att["n_blocks"] >= 2 else "B2"


def classify_gate(res):
    if res["placed"]:
        return "ok"
    return "carried" if res["grasped"] else "no-grasp"


# --------------------------------------------------------------------------- #
# the detector (the gate's logic on a sample sequence)
# --------------------------------------------------------------------------- #
def detect(rates, drifts, thr, ticks, window, max_resp=2):
    """Replay the gate's trigger logic over the samples; return the fire indices.

    Same state machine as `_slide_gate_observe`: a sample at or above `thr`
    extends the run, below resets it; a run of `ticks` fires while the drift is
    inside `window` and the per-attempt response budget is not exhausted.
    (The latched/release state is not modelled - the question here is only
    whether an attempt fires at all.)
    """
    run, used, fires = 0, 0, []
    for i, (r, dr) in enumerate(zip(rates, drifts)):
        if used >= max_resp:
            break
        if r >= thr:
            run += 1
        else:
            run = 0
        if run >= ticks and dr <= window:
            fires.append(i)
            used += 1
            run = 0
    return fires


def max_run(rates, thr):
    best = run = 0
    for r in rates:
        run = run + 1 if r >= thr else 0
        best = max(best, run)
    return best


def pct(vals, q):
    if not vals:
        return float("nan")
    vals = sorted(vals)
    k = min(len(vals) - 1, max(0, int(round(q / 100.0 * (len(vals) - 1)))))
    return vals[k]


# --------------------------------------------------------------------------- #
# load the corpora
# --------------------------------------------------------------------------- #
def load_corpus(spec, kind):
    attempts = []
    for seed, logpath, tdir in spec:
        results, wins, slide = parse_log(logpath)
        files = sorted(Path(tdir).glob("*.json"))
        assert len(files) == len(results), (logpath, len(files), len(results))
        for k, f in enumerate(files):
            att = load_attempt(f)
            if att is None:
                continue
            res = results[k]
            att["seed"], att["k"] = seed, k + 1
            att["res"] = res
            att["win"] = [w for w in wins if w["side"] == res["side"]
                          and w["t0"] - 1e-6 <= att["t0"] and att["t1"] <= w["t1"] + 1e-6]
            # pairing checks: file's own arm/outcome vs the k-th result row
            att["pair_arm_ok"] = (att["arm"] == res["side"])
            att["pair_out_ok"] = ((att["outcome"] == "ok") == res["placed"])
            att["pair_win_ok"] = bool(att["win"])
            if kind == "control":
                att["cls"] = classify_control(att, res)
            else:
                att["cls"] = classify_gate(res)
            att["slide"] = slide
            attempts.append(att)
    return attempts


# --------------------------------------------------------------------------- #
# the gate's own rows (gate-ON corpora): per-arm attempt pairing + validation
# --------------------------------------------------------------------------- #
def gate_rows_by_arm(slide):
    """Order the [slide] rows per arm into per-attempt (hold, probe1) blocks."""
    per_arm = {}
    for row in slide:
        per_arm.setdefault(row["side"], []).append(row)
    out = {}
    for side, rows in per_arm.items():
        pairs, cur = [], {}
        for row in rows:
            if row["kind"] == "sum":
                cur[row["phase"]] = row
                if "hold" in cur and "probe1" in cur:
                    pairs.append(cur)
                    cur = {}
            # a response row is attached to the pair it belongs to (ignored here)
        out[side] = pairs
    return out


def validate(attempts, label):
    print(f"-- {label}: pairing --")
    bad = [a for a in attempts if not (a["pair_arm_ok"] and a["pair_out_ok"] and a["pair_win_ok"])]
    print(f"   attempts={len(attempts)}  arm/outcome/window mismatches={len(bad)}")
    for a in bad:
        print(f"   !! seed={a['seed']} {a['file']} arm={a['pair_arm_ok']} "
              f"out={a['pair_out_ok']} win={a['pair_win_ok']} res={a['res']['side']}/"
              f"{a['res']['grasped']}/{a['res']['placed']}")


def main():
    control = load_corpus(CONTROL, "control")
    gate = load_corpus(GATE, "gate")
    validate(control, "controls (P14-B)")
    validate(gate, "gate-ON (stage P)")

    # ---------------- pairing of the gate's [slide] rows to attempts ---------- #
    print("\n-- gate-ON: the [slide] rows vs the traces --")
    for seed, logpath, tdir in GATE:
        _, _, slide = parse_log(logpath)
        pairs = gate_rows_by_arm(slide)
        n_att = {s: sum(1 for a in gate if a["seed"] == seed and a["arm"] == s) for s in pairs}
        print(f"   seed {seed}: summary pairs {({s: len(v) for s, v in pairs.items()})} "
              f"vs attempts {n_att}")
        # per-arm pairing check: the k-th pair's idx == the k-th attempt's index
        for side, prs in pairs.items():
            att = sorted([a for a in gate if a["seed"] == seed and a["arm"] == side],
                         key=lambda a: a["k"])
            mism = [(k + 1, prs[k]["hold"]["idx"], att[k]["res"]["index"])
                    for k in range(min(len(prs), len(att)))
                    if prs[k]["hold"]["idx"] != att[k]["res"]["index"]]
            print(f"     {side}: pairs={len(prs)} attempts={len(att)} idx mismatches={len(mism)}"
                  + (f" {mism[:4]}" if mism else ""))

    # ---------------- VALIDATION: trace recomputation vs the gate's rows ------ #
    print("\n-- VALIDATION: my trace rate vs the gate's own [slide] rate_max --")
    print("| seed | att | arm | class | phase | gate rate_max | trace max (world) | "
          "trace max (hand) | gate drift_max | trace drift_max |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    val_rows = []
    for seed, logpath, tdir in GATE:
        _, _, slide = parse_log(logpath)
        pairs = gate_rows_by_arm(slide)
        for side, prs in pairs.items():
            att = sorted([a for a in gate if a["seed"] == seed and a["arm"] == side],
                         key=lambda a: a["k"])
            for k, pr in enumerate(prs):
                if k >= len(att):
                    continue
                a = att[k]
                for ph, tph in (("hold", "hold"), ("probe1", "takeoff_probe")):
                    g = pr[ph]
                    idx = [i for i, p in enumerate(a["phases"]) if p == tph]
                    if not idx:
                        continue
                    tw = max(a["rates_world"][i] for i in idx)
                    th = max(a["rates_hand"][i] for i in idx)
                    td = max(a["drifts"][i] for i in idx)
                    val_rows.append((g["rate_max"], tw, th, g["drift_max"], td, ph))
                    print(f"| {seed} | {a['k']} | {side} | {a['cls']} | {ph} | "
                          f"{g['rate_max']:.1f} | {tw:.1f} | {th:.1f} | "
                          f"{g['drift_max']:.1f} | {td:.1f} |")
    if val_rows:
        hold = [v for v in val_rows if v[5] == "hold"]
        p1 = [v for v in val_rows if v[5] == "probe1"]
        for name, rows in (("hold", hold), ("probe1", p1)):
            if not rows:
                continue
            rel = [(tw / g) for g, tw, _, _, _, _ in rows if g > 1.0]
            relh = [(th / g) for g, _, th, _, _, _ in rows if g > 1.0]
            reld = [(td / gd) for g, _, _, gd, td, _ in rows if gd > 0.1]
            print(f"\n   {name}: n={len(rows)}  trace_world/gate ratio "
                  f"median={statistics.median(rel):.3f} (min {min(rel):.3f} max {max(rel):.3f})"
                  f"  trace_hand/gate median={statistics.median(relh):.3f}"
                  f"  drift ratio median={statistics.median(reld):.3f}")

    # ---------------- the gate's own rate_max per class (true per-tick) ------- #
    print("\n-- gate-ON: the gate's own per-attempt rate_max by class (true per-tick) --")
    print("| seed | att | arm | class | hold rate_max | probe1 rate_max | fired |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    gate_own = {}
    for seed, logpath, tdir in GATE:
        _, _, slide = parse_log(logpath)
        pairs = gate_rows_by_arm(slide)
        for side, prs in pairs.items():
            att = sorted([a for a in gate if a["seed"] == seed and a["arm"] == side],
                         key=lambda a: a["k"])
            for k, pr in enumerate(prs):
                if k >= len(att):
                    continue
                a = att[k]
                fired = pr["hold"]["events"] + pr["probe1"]["events"] > 0
                gate_own[(seed, a["k"])] = dict(
                    hold=pr["hold"]["rate_max"], p1=pr["probe1"]["rate_max"],
                    fired=fired, cls=a["cls"])
                print(f"| {seed} | {a['k']} | {side} | {a['cls']} | "
                      f"{pr['hold']['rate_max']:.1f} | {pr['probe1']['rate_max']:.1f} | "
                      f"{'YES' if fired else 'no'} |")

    # ---------------- distributions ------------------------------------------ #
    def table_dist(name, attempts, key="rates_world"):
        print(f"\n== {name}: per-tick drift-rate distributions (hold + probe1) ==")
        print("| class | n | att-max p50 | att-max p90 | att-max max | sample p50 | "
              "sample p90 | sample p99 | sample max |")
        print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        classes = ["ok", "carried", "B1", "B2", "no-grasp"]
        for cls in classes:
            sel = [a for a in attempts if a["cls"] == cls]
            if not sel:
                continue
            att_max = [max(a[key]) for a in sel]
            pooled = [r for a in sel for r in a[key]]
            print(f"| {cls} | {len(sel)} | {pct(att_max,50):.1f} | {pct(att_max,90):.1f} | "
                  f"{max(att_max):.1f} | {pct(pooled,50):.1f} | {pct(pooled,90):.1f} | "
                  f"{pct(pooled,99):.1f} | {max(pooled):.1f} |")

    table_dist("controls (P14-B, unbiased)", control)
    table_dist("gate-ON (stage P, branch-shifted)", gate)

    # ---------------- sustained-run table ------------------------------------ #
    def table_runs(name, attempts):
        print(f"\n== {name}: max sustained run (samples) above candidate thresholds ==")
        print("| class | n | " + " | ".join(f">={t}" for t in THRESHOLDS) + " |")
        print("| --- | --- | " + " | ".join("---" for _ in THRESHOLDS) + " |")
        for cls in ["ok", "carried", "B1", "B2", "no-grasp"]:
            sel = [a for a in attempts if a["cls"] == cls]
            if not sel:
                continue
            med = [statistics.median([max_run(a["rates_world"], t) for a in sel])
                   for t in THRESHOLDS]
            print(f"| {cls} | {len(sel)} | " + " | ".join(f"{m:.1f}" for m in med) + " |")
        print("\n   (cells = median max-run length in samples; a *sample* is 1 tick on "
              "probe1 and 2 ticks on hold)")

    table_runs("controls (P14-B)", control)
    table_runs("gate-ON (stage P)", gate)

    # ---------------- the gate's own rule (60 mm/s, 3 samples) --------------- #
    print("\n== the shipped rule (>=60 mm/s for >=3 samples, window 60 mm) ==")
    for name, attempts in (("controls", control), ("gate-ON", gate)):
        print(f"-- {name} --")
        print("| class | n | fired | fraction |")
        print("| --- | --- | --- | --- |")
        for cls in ["ok", "carried", "B1", "B2", "no-grasp"]:
            sel = [a for a in attempts if a["cls"] == cls]
            if not sel:
                continue
            fired = [a for a in sel if detect(a["rates_world"], a["drifts"], 60, 3, 60)]
            print(f"| {cls} | {len(sel)} | {len(fired)} | {len(fired)/len(sel):.2f} |")

    # ---------------- separability search ------------------------------------ #
    print("\n== the separability search (controls; the unbiased sample) ==")
    print("Target = no-grasp (B1+B2).  FP counted on ok.  Fired-carried reported.")
    print("| thr | ticks | window | caught no-grasp | caught B1 | FP on ok | fired carried |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    oks = [a for a in control if a["cls"] == "ok"]
    ngs = [a for a in control if a["cls"] in ("B1", "B2")]
    b1s = [a for a in control if a["cls"] == "B1"]
    car = [a for a in control if a["cls"] == "carried"]
    best = []
    for thr in [40, 50, 60, 70, 80, 90, 100, 120, 150, 200, 250, 300]:
        for ticks in [1, 2, 3, 4, 5, 6, 8]:
            for window in [40, 60, 80, 100, 1e9]:
                cng = sum(1 for a in ngs if detect(a["rates_world"], a["drifts"], thr, ticks, window))
                cb1 = sum(1 for a in b1s if detect(a["rates_world"], a["drifts"], thr, ticks, window))
                fp = sum(1 for a in oks if detect(a["rates_world"], a["drifts"], thr, ticks, window))
                fc = sum(1 for a in car if detect(a["rates_world"], a["drifts"], thr, ticks, window))
                best.append((fp, cng, cb1, fc, thr, ticks, window))
    # print the Pareto-relevant rows: FP <= 1 with the highest no-grasp recall
    sel = [b for b in best if b[0] <= 1]
    sel.sort(key=lambda b: (-b[1], -b[2], b[0], b[4]))
    for b in sel[:24]:
        w = "off" if b[6] > 1e8 else f"{b[6]:.0f}"
        print(f"| {b[4]} | {b[5]} | {w} | {b[1]}/{len(ngs)} | {b[2]}/{len(b1s)} | "
              f"{b[0]}/{len(oks)} | {b[3]}/{len(car)} |")
    print("\n   (rows sorted by no-grasp recall; only FP<=1 shown; "
          f"{len(sel)} of {len(best)} triples qualify)")

    # the same search with the hand-frame rate (the mission's recipe) - sensitivity
    print("\n-- the same search with the hand-frame rate (sensitivity) --")
    selh = []
    for thr in [40, 50, 60, 70, 80, 90, 100, 120, 150, 200, 250, 300]:
        for ticks in [1, 2, 3, 4, 5, 6, 8]:
            for window in [60, 1e9]:
                cng = sum(1 for a in ngs if detect(a["rates_hand"], a["drifts"], thr, ticks, window))
                fp = sum(1 for a in oks if detect(a["rates_hand"], a["drifts"], thr, ticks, window))
                selh.append((fp, cng, thr, ticks, window))
    selh = [b for b in selh if b[0] <= 1]
    selh.sort(key=lambda b: (-b[1], b[0], b[2]))
    for b in selh[:12]:
        w = "off" if b[4] > 1e8 else f"{b[4]:.0f}"
        print(f"   thr={b[2]} ticks={b[3]} window={w}: no-grasp {b[1]}/{len(ngs)}, "
              f"FP {b[0]}/{len(oks)}")

    # ---------------- the trace detector vs the gate's actual fires ----------- #
    print("\n== CALIBRATION: the trace detector vs the gate's actual fires (gate-ON) ==")
    print("The gate's own fire decision comes from its [slide] response rows (true "
          "per-tick sampling);\nmy detector runs on the traces (hold sampled every 2 "
          "ticks).  Branch note: the gate's\nresponse changes the trajectory after a "
          "fire, so agreement is a calibration read, not an identity.")
    for name, attempts, own in (("gate-ON", gate, gate_own),):
        for thr, ticks, window in ((60, 3, 60), (80, 2, 60), (90, 2, 60), (60, 4, 60),
                                   (60, 8, 60)):
            tp = fp = fn = tn = 0
            misses, extras = [], []
            for a in attempts:
                key = (a["seed"], a["k"])
                if key not in own:
                    continue
                gfire = own[key]["fired"]
                tfire = bool(detect(a["rates_world"], a["drifts"], thr, ticks, window))
                if gfire and tfire:
                    tp += 1
                elif gfire and not tfire:
                    fn += 1
                    misses.append(f"{a['seed']}/{a['k']}({a['cls']})")
                elif tfire and not gfire:
                    fp += 1
                    extras.append(f"{a['seed']}/{a['k']}({a['cls']})")
                else:
                    tn += 1
            print(f"   ({thr},{ticks},{'off' if window>1e8 else int(window)}): "
                  f"gate fires={tp+fn} trace fires={tp+fp} agree {tp} | "
                  f"missed-by-trace {fn} [{','.join(misses)}] | "
                  f"trace-only {fp} [{','.join(extras)}] | both-quiet {tn}")

    # ---------------- where the fires happen (hold vs probe1) --------------- #
    print("\n== where the candidate rules fire (controls; hold vs probe1, run length) ==")
    print("| rule | class | fired | in hold | in probe1 | median run (samples) | "
          "max run (samples) | window-bound (drift > window at fire) |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for thr, ticks, window in ((60, 3, 60), (80, 2, 60), (90, 2, 60), (60, 8, 60)):
        for cls in ("ok", "carried", "B1", "B2"):
            sel = [a for a in control if a["cls"] == cls]
            fired = [a for a in sel if detect(a["rates_world"], a["drifts"], thr, ticks, window)]
            if not fired:
                continue
            inhold = sum(1 for a in fired if a["phases"][
                detect(a["rates_world"], a["drifts"], thr, ticks, window)[0]] == "hold")
            inp1 = len(fired) - inhold
            runs = [max_run(a["rates_world"], thr) for a in fired]
            # window binding: the drift at the fire sample vs the window
            wbind = 0
            for a in fired:
                i = detect(a["rates_world"], a["drifts"], thr, ticks, window)[0]
                if window < 1e8 and a["drifts"][i] > window * 0.8:
                    wbind += 1
            print(f"| {thr}/{ticks} | {cls} | {len(fired)} | {inhold} | {inp1} | "
                  f"{statistics.median(runs):.0f} | {max(runs)} | {wbind} |")

    # ---------------- the window condition: does it ever bind? -------------- #
    print("\n== does the drift window (60 mm) ever bind? ==")
    for thr, ticks in ((60, 3), (80, 2), (60, 8)):
        bind = tot = 0
        for a in control:
            fires = detect(a["rates_world"], a["drifts"], thr, ticks, 60)
            fires_off = detect(a["rates_world"], a["drifts"], thr, ticks, 1e9)
            tot += 1
            if len(fires) != len(fires_off):
                bind += 1
        print(f"   ({thr},{ticks}): attempts where the 60 mm window changes the fire "
              f"count: {bind}/{tot}")
    mx = max(max(a["drifts"]) for a in control)
    print(f"   controls: max drift reached inside hold+probe1 = {mx:.1f} mm "
          f"(the window is 60 mm)")

    # ---------------- per-attempt detail at the shipped rule ----------------- #
    detail("controls (P14-B)", control, 60, 3, 60)
    detail("controls (P14-B)", control, 80, 2, 60)
    detail("gate-ON (stage P)", gate, 60, 3, 60)

    return control, gate, gate_own


def detail(name, attempts, thr, ticks, window):
    print(f"\n== per-attempt detail at ({thr} mm/s, {ticks} samples, window "
          f"{'off' if window > 1e8 else int(window)} mm) - {name} ==")
    print("| seed | att | arm | class | species | hold rows | p1 rows | max run "
          f">={thr} | max rate | drift@fire | phase@fire | fired | outcome |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for a in sorted(attempts, key=lambda a: (a["seed"], a["k"])):
        fires = detect(a["rates_world"], a["drifts"], thr, ticks, window)
        run = max_run(a["rates_world"], thr)
        mr = max(a["rates_world"])
        dd = f"{a['drifts'][fires[0]]:.1f}" if fires else "-"
        ph = a["phases"][fires[0]] if fires else "-"
        print(f"| {a['seed']} | {a['k']} | {a['arm']} | {a['cls']} | "
              f"{a['res']['species']} | {a['n_hold']} | {a['n_p1']} | {run} | "
              f"{mr:.1f} | {dd} | {ph} | {'YES' if fires else 'no'} | "
              f"{'placed' if a['res']['placed'] else ('carried' if a['res']['grasped'] else 'no-grasp')} |")


if __name__ == "__main__":
    main()
