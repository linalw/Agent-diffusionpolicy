#!/usr/bin/env python3
"""P16-I: the H1 screen's trace analysis (1 run x 20 attempts) + the on-disk control.

Adapted from `logs/p14b/trace_p14b_analysis.py` (verbatim metric definitions; do
NOT edit that file - this is a copy for the H1's trace dir).  The corpus:

  * H1:  `logs/p16i/20_h1_trace.log` + `logs/p16i/traces_h1/`  (the completed
    descent: FRUIT_DYNAMIC_ARRIVE_TOL=0.006 FRUIT_DYNAMIC_ARRIVE_MAX=24
    FRUIT_DYNAMIC_ARRIVE_DIAG=1 on the mass base at SEED 11);
  * CTRL: `logs/p14b/10_seed11_trace.log` + `logs/p14b/traces_s11/` (the
    on-disk traced mass base at SEED 11, read-only here).

The P14-B readouts re-derived identically:
  * the per-row hand-frame payload drift |hand_rel - ref| [mm], ref = the LAST
    `hold` row; the hold walk = the drift change across the hold (from the last
    close row, the freeze);
  * the first departure (>2 mm) + its bracket; the probe sub-blocks; the
    untraced gaps; the close freeze geometry; the carry block.

The P16-I additions:
  * the `[arrive]`/`[boundary]` rows (H1 log) - the descent `end=` shortfall
    (start=), the settled gap, the ticks, the belt/reach margins;
  * the first catch-up row's residual against the desired tip (fruit_z + 10 mm)
    - the design's inheritance endpoint;
  * the catch-up row count per attempt;
  * the falls (`lowest payload point` <= -1000 mm rows, partials -100..-1000).

Writes only under logs/p16i/ (the per-row drift curves to logs/p16i/curves_h1/).

Run:  python3 -B logs/p16i/trace_p16i_analysis.py > logs/p16i/31_tables_h1.txt
"""
from __future__ import annotations

import csv
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # the repo root
P16I = Path(__file__).resolve().parent              # logs/p16i
P14B = ROOT / "logs/p14b"                           # the control (read-only)

SEEDS_H1 = [
    ("s11", "20_h1_trace.log", "traces_h1"),
]
CTRL = ("s11", "10_seed11_trace.log", "traces_s11")

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
CARRY_RE = re.compile(
    r"\[carry\] (\w+) (grasp_lift|place1): ticks=(\d+)/(\d+) clean_slip_max=([0-9.]+)mm "
    r"in-hand_vmax=([0-9.]+) onset_row=(\S+) force@onset=(\S+)N sep@onset=(\S+)mm "
    r"contacts@onset=(\S+) min_contacts=(\d+) force_min=([0-9.]+)N loss_row=(\S+) "
)
ARRIVE_RE = re.compile(
    r"\[arrive\] (\w+) idx=(\d+) start=([0-9.]+)mm settled=([0-9.]+)mm "
    r"ticks=(\d+) dx=([+-][0-9.]+)mm dy=([+-][0-9.]+)mm dz=([+-][0-9.]+)mm"
)
BOUNDARY_RE = re.compile(
    r"\[boundary\] (\w+) idx=(\d+) end=([0-9.]+)mm reach_dn=([+-][0-9.]+)mm "
    r"reach_up=([+-][0-9.]+)mm belt_margin=([+-][0-9.]+)mm"
)
END_RE = re.compile(r"approach\(cartesian\): [0-9.]+ cm, [0-9]+ samples: .* end=([0-9.]+) mm")
CLEAR_RE = re.compile(
    r"\[motion\] carry (grasp_lift|place0|place1) clearance: "
    r"lowest payload point ([+-][0-9.]+) mm to the (.*)"
)
CATCH_RE = re.compile(r"dynamic catch-up: residual=([0-9.]+) mm")
DESCEND_RE = re.compile(r"dynamic descent: waited (\d+) ticks, intercept=([+-][0-9.]+) m .* t_desc=([0-9.]+) s")

PAD_LIFT = 0.010  # the desired tip is fruit_z + 10 mm (FRUIT_PAD_LIFT default)


def dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def parse_log(path: Path):
    results, atts, wins, carries = [], [], [], []
    arrives, boundaries, ends, clears, catches, descends = [], [], [], [], [], []
    for ln, line in enumerate(open(path), 1):
        m = RESULT_RE.search(line)
        if m:
            results.append(dict(
                side=m.group(1), index=int(m.group(2)), species=m.group(3),
                grasped=m.group(4) == "True", placed=m.group(5) == "True",
                lift=float(m.group(6)), force=float(m.group(7)),
                sim=float(m.group(8)), line=ln))
        m = ATT_RE.search(line)
        if m:
            atts.append(dict(
                att=int(m.group(1)), side=m.group(2), grasped=m.group(3) == "True",
                placed=m.group(4) == "True", lift=float(m.group(5)),
                force=float(m.group(6)), sim=float(m.group(7)), line=ln))
        m = WIN_RE.search(line)
        if m:
            wins.append(dict(
                att=int(m.group(1)), side=m.group(2), species=m.group(3),
                grade=m.group(4), t0=float(m.group(5)), t1=float(m.group(6)),
                line=ln))
        m = CARRY_RE.search(line)
        if m:
            carries.append(dict(
                side=m.group(1), leg=m.group(2), ticks=int(m.group(3)),
                clean_slip_max=float(m.group(5)), onset_row=m.group(7),
                loss_row=m.group(13), line=ln))
        m = ARRIVE_RE.search(line)
        if m:
            arrives.append(dict(
                side=m.group(1), idx=int(m.group(2)), start=float(m.group(3)),
                settled=float(m.group(4)), ticks=int(m.group(5)),
                dx=float(m.group(6)), dy=float(m.group(7)), dz=float(m.group(8)),
                line=ln))
        m = BOUNDARY_RE.search(line)
        if m:
            boundaries.append(dict(
                side=m.group(1), idx=int(m.group(2)), end=float(m.group(3)),
                reach_dn=float(m.group(4)), reach_up=float(m.group(5)),
                belt_margin=float(m.group(6)), line=ln))
        m = END_RE.search(line)
        if m:
            ends.append(dict(end=float(m.group(1)), line=ln))
        m = CLEAR_RE.search(line)
        if m:
            clears.append(dict(leg=m.group(1), mm=float(m.group(2)),
                               surface=m.group(3).strip(), line=ln))
        m = CATCH_RE.search(line)
        if m:
            catches.append(dict(residual=float(m.group(1)), line=ln))
        m = DESCEND_RE.search(line)
        if m:
            descends.append(dict(waited=int(m.group(1)), intercept=float(m.group(2)),
                                 t_desc=float(m.group(3)), line=ln))
    return dict(results=results, atts=atts, wins=wins, carries=carries,
                arrives=arrives, boundaries=boundaries, ends=ends, clears=clears,
                catches=catches, descends=descends)


def seg_phases(rows):
    segs = []
    for i, r in enumerate(rows):
        if segs and segs[-1][0] == r["phase"]:
            segs[-1][1].append(i)
        else:
            segs.append((r["phase"], [i]))
    return segs


def probe_blocks(rows):
    """Split the takeoff_probe rows into sub-blocks at the t-jumps (the
    untraced re-seat windows)."""
    blocks = []
    for i, r in enumerate(rows):
        if r["phase"] != "takeoff_probe":
            continue
        if blocks and r["t"] - rows[blocks[-1][-1]]["t"] <= 0.02:
            blocks[-1].append(i)
        else:
            blocks.append([i])
    return blocks


def analyze(path: Path):
    d = json.load(open(path))
    rows = d["rows"]
    if not rows:
        return None
    arm, outcome = d.get("arm", "?"), d.get("outcome", "?")
    holds = [i for i, r in enumerate(rows) if r["phase"] == "hold"]
    ref_i = holds[-1] if holds else 0
    ref = rows[ref_i]["hand_rel"]

    def dr(r):
        return dist(r["hand_rel"], ref) * 1000.0

    # per-phase table (the trace_mine.py rule: segments whose last row is at
    # or after the reference; the grip row is junk and excluded)
    phases = []
    for ph, idxs in seg_phases(rows):
        if idxs[-1] < ref_i or ph == "grip":
            continue
        cum = max(dr(rows[i]) for i in idxs)
        local = max(dist(rows[i]["hand_rel"], rows[idxs[0]]["hand_rel"]) * 1000 for i in idxs)
        fmin = min(rows[i]["force"] for i in idxs)
        cmin = min(rows[i]["contacts"] for i in idxs)
        phases.append(dict(phase=ph, n=len(idxs), cum=cum, local=local,
                           fmin=fmin, cmin=cmin,
                           t0=rows[idxs[0]]["t"], t1=rows[idxs[-1]]["t"]))

    # the first departure + its bracket (the last row <= 2 mm before it)
    fd = None
    prev = None
    for i, r in enumerate(rows):
        if i <= ref_i or r["phase"] == "grip":
            continue
        if dr(r) > 2.0:
            fd = dict(i=i, row=r, drift=dr(r),
                      prev_i=None if prev is None else prev[0],
                      prev_row=None if prev is None else prev[1],
                      prev_drift=None if prev is None else prev[2])
            break
        prev = (i, r, dr(r))

    # probe sub-blocks + their edge states
    blocks = probe_blocks(rows)
    blk = []
    for idxs in blocks:
        first, last = rows[idxs[0]], rows[idxs[-1]]
        blk.append(dict(
            n=len(idxs), t0=first["t"], t1=last["t"],
            z0=first["fruit"][2], z1=last["fruit"][2],
            d_first=dr(first), d_last=dr(last), d_max=max(dr(rows[i]) for i in idxs),
            f_first=first["force"], f_last=last["force"],
            c_first=first["contacts"], c_last=last["contacts"],
            fmin=min(rows[i]["force"] for i in idxs),
            cmin=min(rows[i]["contacts"] for i in idxs),
            sep_last=last["sep"], gap_last=last["gap_cmd"],
        ))

    # the untraced gaps: between consecutive probe blocks, probe-last ->
    # takeoff-first, and takeoff-last -> carry-first
    def row_of_phase(ph, which):
        rr = [i for i, r in enumerate(rows) if r["phase"] == ph]
        return None if not rr else (rr[0] if which == "first" else rr[-1])

    gaps = []
    edges = [(idxs[-1], blocks[k + 1][0]) for k, idxs in enumerate(blocks[:-1])]
    t0_i = row_of_phase("takeoff", "first")
    c0_i = row_of_phase("carry", "first")
    if blocks and t0_i is not None:
        edges.append((blocks[-1][-1], t0_i))
    t1_i = row_of_phase("takeoff", "last")
    if t1_i is not None and c0_i is not None:
        edges.append((t1_i, c0_i))
    for a_i, b_i in edges:
        a, b = rows[a_i], rows[b_i]
        gaps.append(dict(
            a_i=a_i, b_i=b_i, a_phase=a["phase"], b_phase=b["phase"],
            dt=b["t"] - a["t"],
            d_a=dr(a), d_b=dr(b),
            f_a=a["force"], f_b=b["force"],
            c_a=a["contacts"], c_b=b["contacts"],
            disp=dist(b["hand_rel"], a["hand_rel"]) * 1000,
        ))

    # the close freeze geometry + the close-start offset
    close = [r for r in rows if r["phase"] == "close"]
    freeze = None
    if close:
        fr, first = close[-1], close[0]
        freeze = dict(sep=fr["sep"], gap=fr["gap_cmd"], delta=fr["sep"] - fr["gap_cmd"],
                      off_z=fr["offset"][2], hrel_z=fr["hand_rel"][2],
                      start_off_z=first["offset"][2], n=len(close),
                      t0=first["t"], t1=fr["t"])

    carry = [r for r in rows if r["phase"] == "carry"]
    takeoff = [r for r in rows if r["phase"] == "takeoff"]
    total = max((p["cum"] for p in phases), default=0.0)

    # the freeze-reference walk (dfz): the payload's displacement since the
    # close's last row; the hold walk = its change across the hold segment
    close_idx = [i for i, r in enumerate(rows) if r["phase"] == "close"]
    fr_row = rows[close_idx[-1]] if close_idx else rows[0]

    def dfz(r):
        return dist(r["hand_rel"], fr_row["hand_rel"]) * 1000.0

    hold_idx = [i for i, r in enumerate(rows) if r["phase"] == "hold"]
    hold_walk = None
    if hold_idx:
        hold_walk = dfz(rows[hold_idx[-1]]) - dfz(rows[hold_idx[0]])
    # the release: the first post-freeze row whose contact is out for >= 4
    # consecutive rows (F < 0.5 N and contacts == 0); the preceding row is the
    # near edge of the bracket
    rel = None
    if close_idx:
        k0 = close_idx[-1] + 1
        for i in range(k0, len(rows) - 3):
            if rows[i]["phase"] == "grip":
                continue
            if all(rows[j]["force"] < 0.5 and rows[j]["contacts"] == 0
                   for j in range(i, i + 4)):
                prev = rows[i - 1] if i > k0 else None
                rel = dict(i=i, row=rows[i], prev=prev, dfz=dfz(rows[i]))
                break
    # the first walk row (dfz > 2 mm) from the freeze
    walk = None
    if close_idx:
        for i in range(close_idx[-1] + 1, len(rows)):
            if rows[i]["phase"] == "grip":
                continue
            if dfz(rows[i]) > 2.0:
                walk = dict(i=i, row=rows[i])
                break

    # -- P16-I additions ---------------------------------------------------- #
    # the catch-up phase rows (the post-descent solver; the arrival loop is not
    # traced, so on H1 these are the residual catch-up ticks only)
    catch_idx = [i for i, r in enumerate(rows) if r["phase"] == "catchup"]
    first_catch_res = None
    if catch_idx:
        off = rows[catch_idx[0]]["offset"]
        first_catch_res = dist(off, [0.0, 0.0, PAD_LIFT]) * 1000.0
    desc_idx = [i for i, r in enumerate(rows) if r["phase"] == "descent"]
    descent_res = None
    if desc_idx:
        off = rows[desc_idx[0]]["offset"]
        descent_res = dist(off, [0.0, 0.0, PAD_LIFT]) * 1000.0

    return dict(file=path.name, arm=arm, outcome=outcome, n=len(rows), ref_i=ref_i,
                ref=ref, phases=phases, fd=fd, blocks=blk, gaps=gaps,
                freeze=freeze, hold_walk=hold_walk, release=rel, walk=walk,
                fr_rel=fr_row["hand_rel"],
                carry_n=len(carry),
                carry_fmin=None if not carry else min(r["force"] for r in carry),
                carry_drift=None if not carry else max(dr(r) for r in carry),
                takeoff_n=len(takeoff),
                takeoff_fmin=None if not takeoff else min(r["force"] for r in takeoff),
                takeoff_drift=None if not takeoff else max(dr(r) for r in takeoff),
                takeoff_z=None if not takeoff else (takeoff[0]["fruit"][2], takeoff[-1]["fruit"][2]),
                total=total, n_blk=len(blocks),
                catchup_n=len(catch_idx), first_catch_res=first_catch_res,
                descent_res=descent_res)


def bracket_label(a):
    fd = a["fd"]
    if fd is None:
        return "none (<=2 mm all attempt)"
    r, p = fd["row"], fd["prev_row"]
    if p is None:
        return f"{r['phase']} (no predecessor)"
    if p["phase"] == r["phase"]:
        if r["phase"] == "takeoff_probe":
            for k, blk in enumerate(a["blocks"]):
                if blk["t0"] - 1e-9 <= r["t"] <= blk["t1"] + 1e-9:
                    return f"probe block {k + 1} (inside)"
            return "takeoff_probe (inside)"
        return f"{r['phase']} (inside)"
    return f"gap {p['phase']}->{r['phase']} (untraced)"


def fmt_dep(a):
    fd = a["fd"]
    if fd is None:
        return "-"
    r = fd["row"]
    return ("%s t=%.3f d=%.1f F=%.2f c=%d" %
            (r["phase"], r["t"], fd["drift"], r["force"], r["contacts"]))


def short(a):
    return (a["file"].replace("trace_", "").replace("_scripted", "")
            .replace(".json", ""))


def stats(vals):
    if not vals:
        return "-"
    return "n=%d  min %.1f / med %.1f / max %.1f" % (
        len(vals), min(vals), statistics.median(vals), max(vals))


def classify(results, atts, wins, all_rows, files, tdir, base):
    """The P14-B pairing + class rule, reused for both corpora."""
    gl_by_side = {}
    for c in all_rows["carries"]:
        if c["leg"] == "grasp_lift":
            gl_by_side.setdefault(c["side"], []).append(c)
    atts_by_side = {}
    for cand in atts:
        atts_by_side.setdefault(cand["side"], []).append(cand)
    for side in atts_by_side:
        atts_by_side[side].sort(key=lambda c: c["att"])
    out = []
    for k, f in enumerate(files):
        a = analyze(f)
        if a is None:
            continue
        rows = json.load(open(f))["rows"]
        res = results[k] if k < len(results) else None
        att = None
        if res is not None:
            # the H1 log has two identical left-apple no-grasp lines (lift
            # +0.000, force 0.00); the sim span is the exact tiebreak (it is
            # the same number on the result and the [run] outcome line).
            cands = [c for c in atts
                     if (c["side"] == res["side"] and c["grasped"] == res["grasped"]
                         and c["placed"] == res["placed"]
                         and abs(c["lift"] - res["lift"]) < 1e-6)]
            cands.sort(key=lambda c: (abs(c["sim"] - res["sim"]), c["att"]))
            for cand in cands:
                win = [w for w in wins if w["att"] == cand["att"] and w["side"] == cand["side"]]
                if win and win[0]["species"] == res["species"]:
                    att = cand
                    break
        checks = []
        if res is not None:
            checks.append(("side", a["arm"] == res["side"]))
            checks.append(("outcome", (a["outcome"] == "ok") == res["placed"]))
            if att is not None:
                w = [w for w in wins if w["att"] == att["att"] and w["side"] == att["side"]][0]
                checks.append(("window", w["t0"] - 1e-6 <= rows[0]["t"] and rows[-1]["t"] <= w["t1"] + 1e-6))
                checks.append(("species", w["species"] == res["species"]))
        a["pair"] = dict(k=k + 1, res=res, att=att, checks=checks,
                         ok=all(v for _, v in checks))
        a["cls"] = ("ok" if a["outcome"] == "ok"
                    else "carried" if (res and res["grasped"] and not res["placed"])
                    else "B1" if a["n_blk"] >= 2 else "B2")
        a["carry_log"] = None
        if att is not None:
            rank = [c["att"] for c in atts_by_side[att["side"]]].index(att["att"])
            gl = gl_by_side.get(att["side"], [])
            if rank < len(gl):
                a["carry_log"] = gl[rank]
        out.append(a)
    return out


def corpus_table(rows, title):
    print(f"== {title} ==")
    print()
    print("| # | file | arm | out | cls | catchup rows | first catchup res mm | hold walk mm | total drift mm | first departure |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for k, a in enumerate(rows, 1):
        print("| %d | %s | %s | %s | %s | %d | %s | %s | %.1f | %s |" % (
            k, short(a), a["arm"], a["outcome"], a["cls"], a["catchup_n"],
            "-" if a["first_catch_res"] is None else "%.1f" % a["first_catch_res"],
            "-" if a["hold_walk"] is None else "%.1f" % a["hold_walk"],
            a["total"], fmt_dep(a)))
    print()


def class_walk_table(rows, title):
    print(f"== {title} ==")
    print()
    print("| class | n | hold walk mm (min/med/max) | first catchup res mm (min/med/max) | catchup rows (min/med/max) |")
    print("| --- | --- | --- | --- | --- |")
    for cls in ["ok", "carried", "B1", "B2"]:
        hw, cr, cn = [], [], []
        for a in rows:
            if a["cls"] != cls:
                continue
            if a["hold_walk"] is not None:
                hw.append(a["hold_walk"])
            if a["first_catch_res"] is not None:
                cr.append(a["first_catch_res"])
            cn.append(a["catchup_n"])
        print("| %s | %d | %s | %s | %s |" % (
            cls, len([a for a in rows if a["cls"] == cls]), stats(hw), stats(cr), stats(cn)))
    print()


def main():
    curves_dir = P16I / "curves_h1"
    curves_dir.mkdir(exist_ok=True)
    all_rows = []

    # ---------------- H1 (the screen run) ---------------------------------- #
    for seed, logname, tdir in SEEDS_H1:
        log = P16I / logname
        parsed = parse_log(log)
        results, atts, wins, carries = (parsed["results"], parsed["atts"],
                                        parsed["wins"], parsed["carries"])
        files = sorted((P16I / tdir).glob("*.json"))
        print(f"== seed {seed} (H1): {logname} ==")
        print(f"   [biarm] result lines: {len(results)}; trace files: {len(files)}; "
              f"[run] attempt lines: {len(atts)}; [carry] rows: {len(carries)}; "
              f"[arrive] rows: {len(parsed['arrives'])}; [boundary] rows: {len(parsed['boundaries'])}")
        if len(results) != len(files):
            print("   !! count mismatch - pairing is not 1:1")
        h1_rows = classify(results, atts, wins, parsed, files, tdir, P16I)
        # pairing verification
        bad = [a["file"] for a in h1_rows if not a["pair"]["ok"]]
        print(f"   pairing checks: {sum(1 for a in h1_rows if a['pair']['ok'])}/{len(h1_rows)} ok"
              + (f"; FAILED: {bad}" if bad else ""))
        print()

        # the per-attempt table (the P14-B shape, H1)
        print("| # | file | arm | out | cls | species | [run] att | lift | [carry] clean_slip |")
        print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for k, a in enumerate(h1_rows, 1):
            res = a["pair"]["res"]
            att = a["pair"]["att"]
            cl = a["carry_log"]
            print("| %d | %s | %s | %s | %s | %s | %s | %+.3f | %s |" % (
                k, short(a), a["arm"], a["outcome"], a["cls"],
                res["species"] if res else "?", att["att"] if att else "?",
                res["lift"] if res else 0.0,
                ("%.1f" % cl["clean_slip_max"]) if cl else "?"))
        print()

        all_rows.extend([(seed, a) for a in h1_rows])

    # ---------------- the H1 master table ---------------------------------- #
    print("== A. the per-attempt master table (H1, 20 attempts) ==")
    print()
    print("| seed | file | arm | out | cls | probe blocks | total drift mm | hold walk mm | first catchup res mm | first departure | bracket |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for seed, a in all_rows:
        print("| %s | %s | %s | %s | %s | %d | %.1f | %s | %s | %s | %s |" % (
            seed, short(a), a["arm"], a["outcome"], a["cls"], a["n_blk"], a["total"],
            "-" if a["hold_walk"] is None else "%.1f" % a["hold_walk"],
            "-" if a["first_catch_res"] is None else "%.1f" % a["first_catch_res"],
            fmt_dep(a), bracket_label(a)))
    print()

    # per-phase drift table (the P14-B shape)
    print("== A2. per-phase cumulative drift (mm, from the last hold row) ==")
    print()
    print("| seed | file | hold | probe1 | probe2 | probe3 | takeoff | carry | freeze sep/gap/delta | close-start off_z |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for seed, a in all_rows:
        by = {p["phase"]: p for p in a["phases"]}
        bc = ["%.1f" % b["d_max"] for b in a["blocks"]]
        while len(bc) < 3:
            bc.append("-")
        fr = a["freeze"]
        fr_txt = "-" if not fr else "%.1f/%.1f/%+.1f" % (
            fr["sep"] * 1000, fr["gap"] * 1000, fr["delta"] * 1000)
        co = "-" if not fr else "%+.1f" % (fr["start_off_z"] * 1000)
        print("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            seed, short(a),
            "-" if "hold" not in by else "%.1f" % by["hold"]["cum"],
            bc[0], bc[1], bc[2],
            "-" if "takeoff" not in by else "%.1f" % by["takeoff"]["cum"],
            "-" if "carry" not in by else "%.1f" % by["carry"]["cum"],
            fr_txt, co))
    print()

    # B. the drift separation (H1)
    print("== B. the class drift separation (H1, total cumulative, mm) ==")
    print()
    print("| class | n | total drift range (min/med/max) | >2 mm attempts |")
    print("| --- | --- | --- | --- |")
    for cls in ["ok", "carried", "B1", "B2"]:
        vals = [a["total"] for _, a in all_rows if a["cls"] == cls]
        if not vals:
            continue
        n_gt2 = sum(1 for v in vals if v > 2.0)
        print("| %s | %d | %s | %d |" % (cls, len(vals), stats(vals), n_gt2))
    print()

    # C. the first-departure bracket histogram (failures)
    print("== C. the first-departure bracket histogram (H1 failures) ==")
    print()
    hist = {}
    for seed, a in all_rows:
        if a["cls"] == "ok":
            continue
        lab = bracket_label(a)
        key = lab.split(" (")[0]
        hist.setdefault(key, []).append((seed, a, lab))
    for k in sorted(hist):
        print(f"- {k}: {len(hist[k])}")
        for seed, a, lab in hist[k]:
            print(f"    {seed} {short(a)}: {lab} | {fmt_dep(a)}")
    print()

    # G. the walk / lift / release table (H1)
    print("== G. the walk (hold), the probe-1 lift (dz), the release bracket (H1) ==")
    print()
    print("| seed | file | cls | hold walk mm | probe1 dz mm | walk onset (dfz>2) | release row (phase, t, dfz) |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for seed, a in all_rows:
        w = a["walk"]
        rel = a["release"]
        p1dz = "%.1f" % ((a["blocks"][0]["z1"] - a["blocks"][0]["z0"]) * 1000) if a["blocks"] else "-"
        wtxt = "-" if w is None else "%s t=%.3f" % (w["row"]["phase"], w["row"]["t"])
        rtxt = "-" if rel is None else "%s t=%.3f dfz=%.1f" % (
            rel["row"]["phase"], rel["row"]["t"], rel["dfz"])
        print("| %s | %s | %s | %s | %s | %s | %s |" % (
            seed, short(a), a["cls"],
            "-" if a["hold_walk"] is None else "%.1f" % a["hold_walk"],
            p1dz, wtxt, rtxt))
    print()

    # H. the candidate pre-outcome signals by class (H1)
    class_walk_table([a for _, a in all_rows], "H. the candidate signals by class (H1)")

    # curves (H1)
    for seed, a in all_rows:
        tdir = [d for s, l, d in SEEDS_H1 if s == seed][0]
        rows = json.load(open(P16I / tdir / a["file"]))["rows"]
        ref = a["ref"]
        out = curves_dir / f"{seed}_{a['file']}"
        with open(out.with_suffix(".csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["row", "phase", "t", "drift_mm", "force", "contacts"])
            for i, r in enumerate(rows):
                w.writerow([i, r["phase"], "%.5f" % r["t"],
                            "%.3f" % (dist(r["hand_rel"], ref) * 1000.0),
                            "%.3f" % r["force"], r["contacts"]])
    print(f"== curves written to {curves_dir} ({len(all_rows)} csv files) ==")
    print()

    # ---------------- the control (on disk, read-only) ---------------------- #
    seed_c, logname_c, tdir_c = CTRL
    parsed_c = parse_log(P14B / logname_c)
    files_c = sorted((P14B / tdir_c).glob("*.json"))
    ctrl_rows = classify(parsed_c["results"], parsed_c["atts"], parsed_c["wins"],
                         parsed_c, files_c, tdir_c, P14B)
    bad = [a["file"] for a in ctrl_rows if not a["pair"]["ok"]]
    print(f"== CTRL seed {seed_c}: {logname_c} ==")
    print(f"   [biarm] result lines: {len(parsed_c['results'])}; trace files: {len(files_c)}; "
          f"[run] attempt lines: {len(parsed_c['atts'])}; [carry] rows: {len(parsed_c['carries'])}")
    print(f"   pairing checks: {sum(1 for a in ctrl_rows if a['pair']['ok'])}/{len(ctrl_rows)} ok"
          + (f"; FAILED: {bad}" if bad else ""))
    c_ok = sum(1 for a in ctrl_rows if a["cls"] == "ok")
    c_car = sum(1 for a in ctrl_rows if a["cls"] == "carried")
    c_b1 = sum(1 for a in ctrl_rows if a["cls"] == "B1")
    c_b2 = sum(1 for a in ctrl_rows if a["cls"] == "B2")
    print(f"   class census: ok {c_ok} / carried {c_car} / B1 {c_b1} / B2 {c_b2}")
    print()
    class_walk_table(ctrl_rows, "H0. the candidate signals by class (CTRL s11)")
    corpus_table(ctrl_rows, "A0. the control master table (CTRL s11, 20 attempts)")

    # ---------------- the [arrive]/[boundary] rows (H1) --------------------- #
    print("== I. the [arrive] rows (H1) ==")
    print()
    print("| # | arm | idx | start mm | settled mm | ticks | dx | dy | dz |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for k, a in enumerate(parsed["arrives"], 1):
        print("| %d | %s | %d | %.1f | %.1f | %d | %+.1f | %+.1f | %+.1f |" % (
            k, a["side"], a["idx"], a["start"], a["settled"], a["ticks"],
            a["dx"], a["dy"], a["dz"]))
    print()
    print("== I2. the [boundary] rows (H1) ==")
    print()
    print("| # | arm | idx | end mm | reach_dn mm | reach_up mm | belt_margin mm |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for k, a in enumerate(parsed["boundaries"], 1):
        print("| %d | %s | %d | %.1f | %+.1f | %+.1f | %+.1f |" % (
            k, a["side"], a["idx"], a["end"], a["reach_dn"], a["reach_up"],
            a["belt_margin"]))
    print()
    st = [a["start"] for a in parsed["arrives"]]
    se = [a["settled"] for a in parsed["arrives"]]
    tk = [a["ticks"] for a in parsed["arrives"]]
    bm = [a["belt_margin"] for a in parsed["boundaries"]]
    rd = [a["reach_dn"] for a in parsed["boundaries"]]
    ru = [a["reach_up"] for a in parsed["boundaries"]]
    print("start= (the pre-arrival shortfall, like-for-like to CTRL end=): " + stats(st))
    print("settled= (the motion row's end= when H1 runs):                  " + stats(se))
    print("arrival ticks:                                                  " + stats([float(x) for x in tk]))
    print("belt_margin:                                                    " + stats(bm))
    print("reach_dn / reach_up:                                            " + stats(rd) + " / " + stats(ru))
    print()
    print("the same quantity on CTRL (the motion rows' end=): " + stats([a["end"] for a in parsed_c["ends"]]))
    print("H1 motion rows' end= (the settled gap):            " + stats([a["end"] for a in parsed["ends"]]))
    print()
    cw = [a["waited"] for a in parsed["descends"]]
    cwc = [a["waited"] for a in parsed_c["descends"]]
    print("the descent wait ticks (H1):    " + stats([float(x) for x in cw]))
    print("the descent wait ticks (CTRL):  " + stats([float(x) for x in cwc]))
    print()

    # ---------------- the falls --------------------------------------------- #
    print("== M. the falls (the `lowest payload point` rows) ==")
    print()
    for label, p in (("H1", parsed), ("CTRL", parsed_c)):
        neg = [a for a in p["clears"] if a["mm"] < 0]
        falls = [a for a in neg if a["mm"] <= -1000]
        part = [a for a in neg if -1000 < a["mm"] <= -100]
        small = [a for a in neg if -100 <= a["mm"] < 0]
        print(f"- {label}: clearance rows {len(p['clears'])}; negative {len(neg)}; "
              f"falls <=-1000: {len(falls)} rows / {len(set(a['line'] for a in falls))} attempts; "
              f"partials -100..-1000: {len(part)}; small -100..0: {len(small)}")
        for a in neg:
            print(f"    {label} line {a['line']}: {a['leg']} {a['mm']:+.0f} mm to the {a['surface']}")
    print()

    # ---------------- the catch-up exit residuals (log lines) --------------- #
    print("== N. the `dynamic catch-up: residual=` exit values ==")
    print()
    print("H1:   " + stats([a["residual"] for a in parsed["catches"]]))
    print("CTRL: " + stats([a["residual"] for a in parsed_c["catches"]]))
    print()


if __name__ == "__main__":
    main()
