#!/usr/bin/env python3
"""P14-B: the trace-run analysis (3 seed runs x 20 attempts = 60 attempts).

The three runs (logs/p14b/10_seed11_trace.log, 11_seed5_trace.log,
12_seed23_trace.log + the traces_s11/s5/s23 dirs) carry the two-line patch
battery at FRUIT_PHYSICS_REAL_MASS=1 with FRUIT_DYNAMIC_TRACE=1.  This tool
re-implements the GRIP_DIAGNOSTIC.md §2.4 readouts on those traces:

  * the per-row hand-frame payload drift |hand_rel - ref| [mm], ref = the LAST
    `hold` row (never the `grip` row - its hand_rel is junk, fruit=rest);
  * per phase (hold, probe cycles, takeoff, carry): the cumulative max and the
    local max drift, Fmin, contacts min (the trace_mine.py rule: the hold
    segment is included whole, so a hold-phase onset is visible);
  * the first departure: the first post-ref row with drift > 2 mm (the W8-B
    crossing scale) *and* the bracket - the last row <= 2 mm before it.  Same
    phase => the loss is inside that phase; different phase => the loss is
    inside the untraced gap between the two rows (the re-seat windows and the
    takeoff->carry gap have no trace call sites);
  * the probe sub-blocks (split by the t-jumps) and, for every untraced gap,
    the near-edge (last row before) and far-edge (first row after) states:
    was the payload still held at the near edge, already gone at the far edge;
  * the close freeze geometry (last close row: sep, gap_cmd, sep-gap_cmd,
    offset_z, hand_rel_z) and the close-start offset (first close row);
  * the carry block (drift, Fmin) plus the log's `[carry] grasp_lift` row
    (clean_slip_max, onset_row, loss_row) as the cross-check.

Pairing: the dump sequence NN in `trace_NN_<arm>_scripted_<outcome>.json` is the
global completion counter, so the NN-th file pairs with the NN-th `[biarm]
result` line; the file's own `arm`/`outcome` and the `[run] attempt N` window
containing the rows' t-range are the cross-checks (the [run] and [biarm] lines
agree on species / grasped / placed / lift).  The `[carry]` rows are paired per
arm: the k-th `grasp_lift` row of a side (log order) is that side's k-th
attempt in start order.

Writes the per-row drift curves to logs/p14b/curves/<seed>_<trace>.csv.

Run:  python3 -B logs/p14b/trace_p14b_analysis.py > logs/p14b/trace_p14b_tables.txt
"""
from __future__ import annotations

import csv
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # the repo root
P14B = ROOT / "logs" / "p14b"                        # the P14-B corpus (section F)
RUNB = Path(__file__).resolve().parent               # this adapter's run (logs/p17i)

SEEDS = [
    ("m2", "21_m2_trace.log", "traces_m2"),
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
CARRY_RE = re.compile(
    r"\[carry\] (\w+) (grasp_lift|place1): ticks=(\d+)/(\d+) clean_slip_max=([0-9.]+)mm "
    r"in-hand_vmax=([0-9.]+) onset_row=(\S+) force@onset=(\S+)N sep@onset=(\S+)mm "
    r"contacts@onset=(\S+) min_contacts=(\d+) force_min=([0-9.]+)N loss_row=(\S+) "
)


def dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def parse_log(path: Path):
    results, atts, wins, carries = [], [], [], []
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
    return results, atts, wins, carries


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
                total=total, n_blk=len(blocks))


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


def main():
    curves_dir = RUNB / "curves"
    curves_dir.mkdir(exist_ok=True)
    all_rows = []
    for seed, logname, tdir in SEEDS:
        log = RUNB / logname
        results, atts, wins, carries = parse_log(log)
        files = sorted((RUNB / tdir).glob("*.json"))
        print(f"== seed {seed}: {logname} ==")
        print(f"   [biarm] result lines: {len(results)}; trace files: {len(files)}; "
              f"[run] attempt lines: {len(atts)}; [carry] rows: {len(carries)}")
        if len(results) != len(files):
            print("   !! count mismatch - pairing is not 1:1")
        # per-arm [carry] grasp_lift rows, log order; per-arm attempts in start
        # order (the [run] attempt numbering is global start order)
        gl_by_side = {}
        for c in carries:
            if c["leg"] == "grasp_lift":
                gl_by_side.setdefault(c["side"], []).append(c)
        atts_by_side = {}
        for cand in atts:
            atts_by_side.setdefault(cand["side"], []).append(cand)
        for side in atts_by_side:
            atts_by_side[side].sort(key=lambda c: c["att"])
        print(f"   [carry] grasp_lift rows per side: "
              f"{ {s: len(v) for s, v in gl_by_side.items()} }; "
              f"attempts per side: { {s: len(v) for s, v in atts_by_side.items()} }")
        print()
        print("| # | file | arm | out | side= | out= | win= | species= | [run] att | species | lift | log [carry] clean_slip |")
        print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        seed_rows = []
        for k, f in enumerate(files):
            a = analyze(f)
            if a is None:
                continue
            rows = json.load(open(f))["rows"]
            res = results[k] if k < len(results) else None
            att = None
            if res is not None:
                for cand in atts:
                    if (cand["side"] == res["side"] and cand["grasped"] == res["grasped"]
                            and cand["placed"] == res["placed"]
                            and abs(cand["lift"] - res["lift"]) < 1e-6):
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
            # [carry] pairing: the rank of this attempt among its side's
            # attempts in start order -> that rank's grasp_lift row
            a["carry_log"] = None
            if att is not None:
                rank = [c["att"] for c in atts_by_side[att["side"]]].index(att["att"])
                gl = gl_by_side.get(att["side"], [])
                if rank < len(gl):
                    a["carry_log"] = gl[rank]
            seed_rows.append((seed, a))
            cl = a["carry_log"]
            print("| %d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %+.3f | %s |" % (
                k + 1, short(a), a["arm"], a["outcome"],
                "ok" if res and a["arm"] == res["side"] else "NO",
                "ok" if res and (a["outcome"] == "ok") == res["placed"] else "NO",
                "ok" if all(v for n, v in checks if n == "window") else "NO",
                "ok" if all(v for n, v in checks if n == "species") else "NO",
                att["att"] if att else "?",
                res["species"] if res else "?",
                res["lift"] if res else 0.0,
                ("%.1f" % cl["clean_slip_max"]) if cl else "?",
            ))
        print()
        all_rows.extend(seed_rows)

    # ------------------------------------------------------------------ #
    # the per-attempt master table
    print("== A. the per-attempt table (60 attempts) ==")
    print()
    print("| seed | file | arm | out | cls | probe blocks | total drift mm | first departure (row) | bracket | carry Fmin | carry drift | [carry] clean_slip |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for seed, a in all_rows:
        cl = a["carry_log"]
        print("| %s | %s | %s | %s | %s | %d | %.1f | %s | %s | %s | %s | %s |" % (
            seed, short(a), a["arm"], a["outcome"], a["cls"], a["n_blk"], a["total"],
            fmt_dep(a), bracket_label(a),
            "-" if a["carry_fmin"] is None else "%.2f" % a["carry_fmin"],
            "-" if a["carry_drift"] is None else "%.1f" % a["carry_drift"],
            "-" if cl is None else "%.1f" % cl["clean_slip_max"],
        ))
    print()

    # per-phase drift table
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
            fr_txt, co,
        ))
    print()

    # ------------------------------------------------------------------ #
    # the distributions
    def stats(vals):
        if not vals:
            return "-"
        return "n=%d  min %.1f / med %.1f / max %.1f" % (
            len(vals), min(vals), statistics.median(vals), max(vals))

    print("== B. the ok-vs-fail drift separation (total cumulative, mm) ==")
    print()
    print("| seed | class | n | total drift range (min/med/max) | >2 mm attempts |")
    print("| --- | --- | --- | --- | --- |")
    for seed in ["s11", "s5", "s23", "pooled"]:
        for cls in ["ok", "carried", "B1", "B2", "fail(all)"]:
            vals = []
            for s, a in all_rows:
                if seed != "pooled" and s != seed:
                    continue
                if cls == "fail(all)":
                    if a["cls"] == "ok":
                        continue
                elif a["cls"] != cls:
                    continue
                vals.append(a["total"])
            if not vals:
                continue
            n_gt2 = sum(1 for v in vals if v > 2.0)
            print("| %s | %s | %d | %s | %d |" % (seed, cls, len(vals), stats(vals), n_gt2))
    print()

    # first-departure bracket histogram for the failures
    print("== C. the first-departure bracket histogram (failures) ==")
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

    # the bracket detail (every untraced gap with a departure or a clean hold)
    print("== D. the untraced-gap brackets (near edge -> far edge) ==")
    print()
    print("| seed | file | gap | dt s | near: drift/F/c | far: drift/F/c | disp mm | verdict |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for seed, a in all_rows:
        for g in a["gaps"]:
            if g["d_a"] <= 2.0 and g["d_b"] <= 2.0:
                verdict = "held through"
            elif g["d_a"] <= 2.0 < g["d_b"]:
                verdict = "** LOST in window"
            else:
                verdict = "already >2mm before"
            tag = "" if a["cls"] == "ok" else " **"
            print("| %s | %s%s | %s->%s | %.3f | %.1f / %.2f / %d | %.1f / %.2f / %d | %.1f | %s |" % (
                seed, short(a), tag, g["a_phase"], g["b_phase"], g["dt"],
                g["d_a"], g["f_a"], g["c_a"], g["d_b"], g["f_b"], g["c_b"],
                g["disp"], verdict))
    print()

    # per-failure decomposition (the W5-C style)
    print("== E. per-failure phase decomposition (cum/local/Fmin/cmin) ==")
    for seed, a in all_rows:
        if a["cls"] == "ok":
            continue
        print(f"\n-- {seed} {short(a)} ({a['arm']}, {a['cls']}) --")
        for p in a["phases"]:
            print("   %-14s rows=%4d cum=%9.1f local=%9.1f Fmin=%6.2f cmin=%d t=%.2f..%.2f" % (
                p["phase"], p["n"], p["cum"], p["local"], p["fmin"], p["cmin"], p["t0"], p["t1"]))
        if a["takeoff_z"]:
            print("   takeoff z: %.4f -> %.4f" % a["takeoff_z"])
        for b in a["blocks"]:
            print("   probe block n=%d t=%.2f..%.2f dz=%+.1fmm dmax=%.1f dlast=%.1f Fmin=%.2f cmin=%d" % (
                b["n"], b["t0"], b["t1"], (b["z1"] - b["z0"]) * 1000, b["d_max"], b["d_last"],
                b["fmin"], b["cmin"]))
    print()

    # ------------------------------------------------------------------ #
    # G. the walk / lift / release table
    print("== G. the walk (hold), the probe-1 lift (dz), the release bracket ==")
    print()
    print("| seed | file | cls | hold walk mm | probe1 dz mm | walk onset (dfz>2) | release row (phase, t, dfz) | near edge (phase, F, c, dfz) |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for seed, a in all_rows:
        w = a["walk"]
        rel = a["release"]
        p1dz = "%.1f" % ((a["blocks"][0]["z1"] - a["blocks"][0]["z0"]) * 1000) if a["blocks"] else "-"
        wtxt = "-" if w is None else "%s t=%.3f" % (w["row"]["phase"], w["row"]["t"])
        rtxt = "-" if rel is None else "%s t=%.3f dfz=%.1f" % (
            rel["row"]["phase"], rel["row"]["t"], rel["dfz"])
        ntxt = "-"
        if rel is not None and rel["prev"] is not None:
            p = rel["prev"]
            gap = rel["row"]["t"] - p["t"] > 0.02
            ndfz = dist(p["hand_rel"], a["fr_rel"]) * 1000
            ntxt = "%s F=%.2f c=%d dfz=%.1f%s" % (
                p["phase"], p["force"], p["contacts"], ndfz, " [gap]" if gap else "")
        print("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            seed, short(a), a["cls"],
            "-" if a["hold_walk"] is None else "%.1f" % a["hold_walk"],
            p1dz, wtxt, rtxt, ntxt))
    print()

    # H. the class distributions of the two candidate signals
    print("== H. the candidate pre-outcome signals by class ==")
    print()
    print("| class | n | hold walk mm (min/med/max) | probe1 dz mm (min/med/max) | probe1 dmax mm (min/med/max) |")
    print("| --- | --- | --- | --- | --- |")
    for cls in ["ok", "carried", "B1", "B2"]:
        hw, dz, dm = [], [], []
        for seed, a in all_rows:
            if a["cls"] != cls:
                continue
            if a["hold_walk"] is not None:
                hw.append(a["hold_walk"])
            if a["blocks"]:
                dz.append((a["blocks"][0]["z1"] - a["blocks"][0]["z0"]) * 1000)
                dm.append(a["blocks"][0]["d_max"])
        print("| %s | %d | %s | %s | %s |" % (cls, len(hw), stats(hw), stats(dz), stats(dm)))
    print()

    # the curves
    for seed, a in all_rows:
        tdir = [d for s, l, d in SEEDS if s == seed][0]
        rows = json.load(open(RUNB / tdir / a["file"]))["rows"]
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

    # ------------------------------------------------------------------ #
    # the W5-C comparison
    print()
    print("== F. the W5-C corpus comparison (same analysis, trace_mine.py) ==")
    sys.path.insert(0, str(P14B))
    from trace_mine import analyze as w5_analyze  # noqa: E402
    corpora = [
        ("p14b s11", P14B / "traces_s11"),
        ("p14b s5", P14B / "traces_s5"),
        ("p14b s23", P14B / "traces_s23"),
        ("w5 cfg0", ROOT / "logs/w5/traces_dense"),
        ("w5 cfg1", ROOT / "logs/w5/30_traces_fs0"),
        ("w5 cfg2", ROOT / "logs/w5/30_traces_fs0sq0"),
        ("w5 cfg3", ROOT / "logs/w5/30_traces_track02"),
        ("w5 cfg4", ROOT / "logs/w5/30_traces_lockx"),
    ]
    print()
    print("| corpus | n | ok drift mm (min/med/max) | fail drift mm (min/med/max) | fail onsets (first_dep phases) |")
    print("| --- | --- | --- | --- | --- |")
    for label, d in corpora:
        if not d.exists():
            continue
        oks, fails, onsets = [], [], []
        for f in sorted(d.glob("*.json")):
            a = w5_analyze(f)
            if a is None:
                continue
            tot = max((cum for ph, n, cum, local, fmin, cmin in a["phases"]), default=0.0)
            if a["outcome"] == "ok":
                oks.append(tot)
            else:
                fails.append(tot)
                fd = a["first_dep"]
                onsets.append("-" if fd is None else fd[1]["phase"])
        print("| %s | %d | %s | %s | %s |" % (
            label, len(oks) + len(fails), stats(oks), stats(fails),
            ", ".join(sorted(set(onsets))) if onsets else "-"))


if __name__ == "__main__":
    main()
