#!/usr/bin/env python3
"""P15 Stage-M screen analysis: M1 (`FRUIT_CLOSE_LOAD_RATE=0.04`) + M2
(`FRUIT_CLOSE_CONTACT_LEAD=0.10`) vs the on-disk traced control (p14b s11).

Read-only.  Reuses the P14-B metric implementation verbatim
(`logs/p14b/trace_p14b_analysis.py`: the hold walk from the freeze, the probe-1
blocks/lift, the 2 mm first departure + bracket, the release bracket) and the
R11-B close readouts (`logs/r11/b_readout.py`: the freeze row = the first row
whose commanded gap stops moving for 3 consecutive ticks; the freeze-zone face
speed = the mean commanded gap-closing rate over the 4 ticks before it; the
first-contact row).  Adds the P15-specific actuation readouts (the fruit |v_y|
at the close-end/hold for the lead arm) and the K2 never-grasped signature
from the live `[carry]` rows.

Corpora:
  M0 control : logs/p14b/10_seed11_trace.log  + logs/p14b/traces_s11
  M1 (C1)    : logs/p15/10_m1_trace.log       + logs/p15/traces_m1
  M2 (lead)  : logs/p15/11_m2_trace.log       + logs/p15/traces_m2

Run:  python3 -B logs/p15/trace_p15_analysis.py > logs/p15/trace_p15_tables.txt
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "logs" / "p14b"))
from trace_p14b_analysis import analyze, bracket_label, dist, parse_log  # noqa: E402

CORPORA = [
    dict(label="M0", env="shipped (on-disk control)",
         log=ROOT / "logs/p14b/10_seed11_trace.log",
         traces=ROOT / "logs/p14b/traces_s11"),
    dict(label="M1", env="FRUIT_CLOSE_LOAD_RATE=0.04",
         log=ROOT / "logs/p15/10_m1_trace.log",
         traces=ROOT / "logs/p15/traces_m1"),
    dict(label="M2", env="FRUIT_CLOSE_CONTACT_LEAD=0.10",
         log=ROOT / "logs/p15/11_m2_trace.log",
         traces=ROOT / "logs/p15/traces_m2"),
]

WIN_RE = re.compile(
    r"\[run\] attempt (\d+) \((\w+)\): picking (\w+) grade (\w+) .* sim=([0-9.]+)-([0-9.]+)s"
)
CARRY_FULL_RE = re.compile(
    r"\[carry\] (left|right) (grasp_lift|place\d): ticks=(\d+)/(\d+) "
    r"clean_slip_max=([0-9.]+)mm in-hand_vmax=([0-9.]+) onset_row=(\S+) "
    r"force@onset=(\S+)N sep@onset=(\S+)mm contacts@onset=(\S+) min_contacts=(\d+) "
    r"force_min=([0-9.]+)N loss_row=(\S+)"
)
FREEZE_RE = re.compile(
    r"dynamic close: sustained contact after (\d+) ticks \(force=(-?[0-9.]+) N, "
    r"span=(-?[0-9.]+) mm\); freezing the closing command at ([0-9.]+) mm"
)


def parse_freeze_lines(path):
    """The primitive's own freeze lines (the true freeze tick/force/span)."""
    out = []
    for ln, line in enumerate(open(path), 1):
        m = FREEZE_RE.search(line)
        if m:
            out.append(dict(ticks=int(m.group(1)), force=float(m.group(2)),
                            span=float(m.group(3)), depth=float(m.group(4)), line=ln))
    return out


def parse_carry_full(path):
    """The full [carry] rows (with force@onset/contacts@onset, which the p14b
    parser drops)."""
    out = []
    for ln, line in enumerate(open(path), 1):
        m = CARRY_FULL_RE.search(line)
        if m:
            out.append(dict(side=m.group(1), leg=m.group(2), ticks=int(m.group(3)),
                            clean_slip_max=float(m.group(5)), onset_row=m.group(7),
                            force_onset=m.group(8), sep_onset=m.group(9),
                            contacts_onset=m.group(10), min_contacts=int(m.group(11)),
                            force_min=float(m.group(12)), loss_row=m.group(13), line=ln))
    return out


def stats(vals):
    if not vals:
        return "-"
    return "n=%d  min %.1f / med %.1f / max %.1f" % (
        len(vals), min(vals), statistics.median(vals), max(vals))


def close_readouts(rows):
    """The R11-B close readouts, verbatim rules (b_readout.py:94-144)."""
    close = [r for r in rows if r["phase"] == "close"]
    if not close:
        return None
    fc = next((i for i, r in enumerate(close)
               if int(r.get("contacts", 0)) > 0 or float(r.get("force", 0.0)) >= 0.5), None)
    frz = None
    for i in range(len(close) - 3):
        g = float(close[i]["gap_cmd"])
        if all(abs(float(close[j]["gap_cmd"]) - g) < 1e-6 for j in (i + 1, i + 2)):
            frz = i
            break
    sp_frz = None
    if frz is not None and frz >= 1:
        k0 = max(0, frz - 4)
        span = sum(float(close[j - 1]["gap_cmd"]) - float(close[j]["gap_cmd"])
                   for j in range(k0 + 1, frz + 1))
        sp_frz = span / max(1, frz - k0) * 120 * 1000
    sp_fc = None
    if fc is not None and fc >= 1:
        k0 = max(1, fc - 5)
        span = sum(float(close[j - 1]["gap_cmd"]) - float(close[j]["gap_cmd"])
                   for j in range(k0, fc + 1))
        sp_fc = span / max(1, fc - k0 + 1) * 120 * 1000
    return dict(n=len(close), fc=fc, frz=frz, sp_frz=sp_frz, sp_fc=sp_fc,
                sep0=close[0]["sep"], sepend=close[-1]["sep"],
                gap0=close[0]["gap_cmd"], gapend=close[-1]["gap_cmd"])


def shear_readouts(rows):
    """The fruit's |v_y| at the close-end and across the hold; the hand's own
    y-velocity (from consecutive jaw rows) for the relative cross-check; and
    the hold-segment world displacement decomposition (hand vs payload), the
    K1 read (is the walk the hand's own settling motion?)."""
    out = {}
    close = [r for r in rows if r["phase"] == "close"]
    hold = [r for r in rows if r["phase"] == "hold"]
    if close:
        out["vy_closeend"] = close[-1]["fruit_vel"][1] * 1000  # mm/s
    if hold:
        vy = [r["fruit_vel"][1] * 1000 for r in hold]
        out["vy_hold_mean"] = sum(vy) / len(vy)
        out["vy_hold_absmax"] = max(abs(v) for v in vy)
        out["hold_t0"], out["hold_t1"] = hold[0]["t"], hold[-1]["t"]
        out["hold_dur"] = hold[-1]["t"] - hold[0]["t"]
        # the hand's own y-velocity over the hold (jaw deltas)
        hj = [(hold[i + 1]["jaw"][1] - hold[i]["jaw"][1]) /
              (hold[i + 1]["t"] - hold[i]["t"]) * 1000
              for i in range(len(hold) - 1)]
        out["hand_vy_hold_mean"] = sum(hj) / len(hj) if hj else None
        # the world displacement decomposition over the hold
        out["hand_dy"] = (hold[-1]["jaw"][1] - hold[0]["jaw"][1]) * 1000
        out["fruit_dy"] = (hold[-1]["fruit"][1] - hold[0]["fruit"][1]) * 1000
        out["hand_dx"] = (hold[-1]["jaw"][0] - hold[0]["jaw"][0]) * 1000
        out["fruit_dx"] = (hold[-1]["fruit"][0] - hold[0]["fruit"][0]) * 1000
        out["hand_dz"] = (hold[-1]["jaw"][2] - hold[0]["jaw"][2]) * 1000
        out["fruit_dz"] = (hold[-1]["fruit"][2] - hold[0]["fruit"][2]) * 1000
    return out


def trace_contact_readout(rows):
    """The attempt-level contact state (for the K2 never-grasped read)."""
    mx_f = max((r["force"] for r in rows), default=0.0)
    mx_c = max((r["contacts"] for r in rows), default=0)
    # the max over the close..hold span (the capture window)
    cap = [r for r in rows if r["phase"] in ("close", "hold")]
    cap_f = max((r["force"] for r in cap), default=0.0)
    cap_c = max((r["contacts"] for r in cap), default=0)
    return dict(max_force=mx_f, max_contacts=mx_c, cap_force=cap_f, cap_contacts=cap_c)


def never_grasped_signature(carry_row):
    """The R11-B stage-P signature: the payload never held from the leg's first
    tick - onset_row in {1,2,3}, force@onset == 0, contacts@onset == 0."""
    if carry_row is None:
        return None
    try:
        onset = int(carry_row["onset_row"])
    except (TypeError, ValueError):
        return False
    try:
        f0 = float(carry_row["force_onset"])
    except (TypeError, ValueError):
        return False
    c0 = carry_row["contacts_onset"]
    return onset <= 3 and f0 == 0.0 and c0 == "0"


def analyze_corpus(c):
    results, atts, wins, carries = parse_log(c["log"])
    carries_full = parse_carry_full(c["log"])
    files = sorted(c["traces"].glob("*.json"))
    gl_by_side, atts_by_side = {}, {}
    for cr in carries_full:
        if cr["leg"] == "grasp_lift":
            gl_by_side.setdefault(cr["side"], []).append(cr)
    for cand in atts:
        atts_by_side.setdefault(cand["side"], []).append(cand)
    for side in atts_by_side:
        atts_by_side[side].sort(key=lambda x: x["att"])

    rows_out = []
    mismatches = []
    for k, f in enumerate(files):
        a = analyze(f)
        if a is None:
            continue
        rows = json.load(open(f))["rows"]
        res = results[k] if k < len(results) else None
        # pairing checks
        if res is None or a["arm"] != res["side"] or (a["outcome"] == "ok") != res["placed"]:
            mismatches.append((f.name, "arm/outcome", a["arm"], a["outcome"],
                               None if res is None else (res["side"], res["placed"])))
            continue
        att = None
        for cand in atts:
            if (cand["side"] == res["side"] and cand["grasped"] == res["grasped"]
                    and cand["placed"] == res["placed"]
                    and abs(cand["lift"] - res["lift"]) < 1e-6):
                win = [w for w in wins if w["att"] == cand["att"] and w["side"] == cand["side"]]
                if win and win[0]["species"] == res["species"]:
                    att = cand
                    break
        a["pair"] = dict(k=k + 1, res=res, att=att)
        a["species"] = res["species"]
        a["side"] = res["side"]
        a["grasped"] = res["grasped"]
        a["placed"] = res["placed"]
        a["att_num"] = att["att"] if att else None
        a["cls"] = ("ok" if a["outcome"] == "ok"
                    else "carried" if res["grasped"] and not res["placed"]
                    else "B1" if a["n_blk"] >= 2 else "B2")
        a["close"] = close_readouts(rows)
        a["shear"] = shear_readouts(rows)
        a["contact"] = trace_contact_readout(rows)
        # the [carry] grasp_lift row by rank within the side
        a["carry_log"] = None
        if att is not None:
            rank = [x["att"] for x in atts_by_side[att["side"]]].index(att["att"])
            gl = gl_by_side.get(att["side"], [])
            if rank < len(gl):
                a["carry_log"] = gl[rank]
        a["never_grasped"] = never_grasped_signature(a["carry_log"])
        rows_out.append(a)

    census = {}
    for a in rows_out:
        census[a["cls"]] = census.get(a["cls"], 0) + 1
    return dict(c=c, results=results, files=files, rows=rows_out,
                mismatches=mismatches, census=census,
                n_results=len(results), n_files=len(files),
                freeze_lines=parse_freeze_lines(c["log"]))


def short(a):
    return (a["file"].replace("trace_", "").replace("_scripted", "").replace(".json", ""))


def main():
    corpora = [analyze_corpus(c) for c in CORPORA]

    # ---------------- A. pairing verification ----------------
    print("== A. the pairing (completion counter NN <-> NN-th [biarm] result) ==")
    print()
    for cc in corpora:
        c = cc["c"]
        print(f"-- {c['label']} ({c['env']}): {cc['n_files']} trace files, "
              f"{cc['n_results']} [biarm] results, {len(cc['mismatches'])} mismatches; "
              f"census {cc['census']}")
    print()

    # ---------------- B. per-attempt master tables ----------------
    print("== B. the per-attempt master tables ==")
    print()
    for cc in corpora:
        c = cc["c"]
        print(f"-- {c['label']}: {c['env']} --")
        print()
        print("| # | file | arm | species | out | cls | blocks | hold walk mm | walk m/s | probe1 dz mm | first dep | bracket | total mm | freeze row/spd mm/s | close n | close-end vy mm/s | hold vy mean | [carry] onset/F/c/clean_slip |")
        print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for a in cc["rows"]:
            cl = a["carry_log"]
            cl_txt = "-" if cl is None else "%s/%s/%s/%.1f" % (
                cl["onset_row"], cl["force_onset"], cl["contacts_onset"], cl["clean_slip_max"])
            frz = a["close"]
            frz_txt = "-" if not frz else "%s/%.0f" % (
                frz["frz"], frz["sp_frz"]) if frz["sp_frz"] is not None else "%s/-" % frz["frz"]
            sp = a["shear"]
            ve = "%.0f" % sp.get("vy_closeend") if sp.get("vy_closeend") is not None else "-"
            vh = "%.0f" % sp.get("vy_hold_mean") if sp.get("vy_hold_mean") is not None else "-"
            ws = "-"
            if a["hold_walk"] is not None and sp.get("hold_dur"):
                ws = "%.3f" % (a["hold_walk"] / 1000.0 / sp["hold_dur"])
            p1dz = "%.1f" % ((a["blocks"][0]["z1"] - a["blocks"][0]["z0"]) * 1000) if a["blocks"] else "-"
            fd = a["fd"]
            fd_txt = "-" if fd is None else "%s t=%.2f d=%.1f" % (
                fd["row"]["phase"], fd["row"]["t"], fd["drift"])
            print("| %d | %s | %s | %s | %s | %s | %d | %s | %s | %s | %s | %s | %.1f | %s | %d | %s | %s | %s |" % (
                a["pair"]["k"], short(a), a["side"], a["species"], a["outcome"], a["cls"],
                a["n_blk"], "-" if a["hold_walk"] is None else "%.1f" % a["hold_walk"],
                ws, p1dz, fd_txt, bracket_label(a), a["total"], frz_txt,
                frz["n"] if frz else 0, ve, vh, cl_txt))
        print()

    # ---------------- C. hold-walk distributions ----------------
    print("== C. the hold-walk distributions (mm; from the freeze) ==")
    print()
    print("| corpus | class | n | hold walk min/med/max | >12.8 (ok ceiling) | >20 (gap zone) | >31.9 (B1 floor) |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for cc in corpora:
        c = cc["c"]
        for cls in ["ok", "carried", "B1", "B2", "no-grasp (B1+B2)", "all"]:
            vals = []
            for a in cc["rows"]:
                if cls == "all":
                    pass
                elif cls == "no-grasp (B1+B2)":
                    if a["cls"] not in ("B1", "B2"):
                        continue
                elif a["cls"] != cls:
                    continue
                if a["hold_walk"] is not None:
                    vals.append(a["hold_walk"])
            if not vals:
                continue
            n12 = sum(1 for v in vals if v > 12.8)
            n20 = sum(1 for v in vals if v > 20.0)
            n32 = sum(1 for v in vals if v > 31.9)
            print("| %s | %s | %d | %s | %d | %d | %d |" % (
                c["label"], cls, len(vals), stats(vals), n12, n20, n32))
    print()
    print("-- the per-attempt hold walks (all attempts, all corpora) --")
    print()
    print("| corpus | # | file | arm | species | cls | hold walk mm | walk m/s | probe1 dz |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for cc in corpora:
        c = cc["c"]
        for a in sorted(cc["rows"], key=lambda x: -x["hold_walk"] if x["hold_walk"] is not None else 0):
            sp = a["shear"]
            ws = "-"
            if a["hold_walk"] is not None and sp.get("hold_dur"):
                ws = "%.3f" % (a["hold_walk"] / 1000.0 / sp["hold_dur"])
            p1dz = "%.1f" % ((a["blocks"][0]["z1"] - a["blocks"][0]["z0"]) * 1000) if a["blocks"] else "-"
            print("| %s | %d | %s | %s | %s | %s | %.1f | %s | %s |" % (
                c["label"], a["pair"]["k"], short(a), a["side"], a["species"], a["cls"],
                a["hold_walk"], ws, p1dz))
    print()

    # ---------------- D. probe-1 first departures ----------------
    print("== D. the probe-1 first departures (the 2 mm rule, phase-bracketed;")
    print("   the W5-C convention: a pre-probe walk is labelled hold (walk pre-probe)) ==")
    print()
    print("| corpus | class | n | hold (pre-probe) | probe-1 | probe-2+ | takeoff | gap | carry | none |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for cc in corpora:
        c = cc["c"]
        for cls in ["ok", "carried", "B1", "B2", "no-grasp (B1+B2)", "all"]:
            sel = [a for a in cc["rows"]
                   if cls == "all"
                   or (cls == "no-grasp (B1+B2)" and a["cls"] in ("B1", "B2"))
                   or a["cls"] == cls]
            if not sel:
                continue
            hist = {"hold": 0, "probe1": 0, "probe2": 0, "takeoff": 0, "gap": 0,
                    "carry": 0, "none": 0}
            for a in sel:
                lab = bracket_label(a)
                if lab.startswith("none"):
                    hist["none"] += 1
                elif lab.startswith("hold") or lab.startswith("takeoff_probe (no predecessor)"):
                    hist["hold"] += 1
                elif lab.startswith("probe block 1"):
                    hist["probe1"] += 1
                elif lab.startswith("probe block"):
                    hist["probe2"] += 1
                elif lab.startswith("takeoff_probe"):
                    hist["probe2"] += 1
                elif lab.startswith("takeoff"):
                    hist["takeoff"] += 1
                elif lab.startswith("gap"):
                    hist["gap"] += 1
                elif lab.startswith("carry"):
                    hist["carry"] += 1
            print("| %s | %s | %d | %d | %d | %d | %d | %d | %d | %d |" % (
                c["label"], cls, len(sel), hist["hold"], hist["probe1"], hist["probe2"],
                hist["takeoff"], hist["gap"], hist["carry"], hist["none"]))
    print()
    print("-- the no-grasp first departures in detail --")
    print()
    print("| corpus | # | file | arm | species | cls | first departure | bracket |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for cc in corpora:
        c = cc["c"]
        for a in cc["rows"]:
            if a["cls"] == "ok":
                continue
            fd = a["fd"]
            fd_txt = "-" if fd is None else "%s t=%.3f d=%.1f F=%.2f c=%d" % (
                fd["row"]["phase"], fd["row"]["t"], fd["drift"],
                fd["row"]["force"], fd["row"]["contacts"])
            print("| %s | %d | %s | %s | %s | %s | %s | %s |" % (
                c["label"], a["pair"]["k"], short(a), a["side"], a["species"], a["cls"],
                fd_txt, bracket_label(a)))
    print()

    # ---------------- E. the actuation readouts ----------------
    print("== E. the actuation readouts ==")
    print()
    print("| corpus | n | freeze row (R11-B rule) min/med/max | speed@freeze mm/s min/med/max | first-contact row min/med/max | speed@fc mm/s min/med/max | close rows min/med/max |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for cc in corpora:
        c = cc["c"]
        frz, spf, fcs, spc, ncl = [], [], [], [], []
        for a in cc["rows"]:
            cl = a["close"]
            if not cl:
                continue
            ncl.append(cl["n"])
            if cl["frz"] is not None:
                frz.append(cl["frz"])
            if cl["sp_frz"] is not None:
                spf.append(cl["sp_frz"])
            if cl["fc"] is not None:
                fcs.append(cl["fc"])
            if cl["sp_fc"] is not None:
                spc.append(cl["sp_fc"])
        print("| %s | %d | %s | %s | %s | %s | %s |" % (
            c["label"], len(cc["rows"]), stats(frz), stats(spf), stats(fcs), stats(spc), stats(ncl)))
    print()
    print("-- the shear readouts (fruit |v_y|, mm/s) --")
    print()
    print("| corpus | class | n | close-end vy min/med/max | hold mean vy min/med/max | hold |vy| max min/med/max | hand vy mean min/med/max |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for cc in corpora:
        c = cc["c"]
        for cls in ["ok", "carried", "B1", "B2", "no-grasp (B1+B2)", "all"]:
            sel = [a for a in cc["rows"]
                   if cls == "all"
                   or (cls == "no-grasp (B1+B2)" and a["cls"] in ("B1", "B2"))
                   or a["cls"] == cls]
            if not sel:
                continue
            ve = [a["shear"]["vy_closeend"] for a in sel if "vy_closeend" in a["shear"]]
            vh = [a["shear"]["vy_hold_mean"] for a in sel if "vy_hold_mean" in a["shear"]]
            va = [a["shear"]["vy_hold_absmax"] for a in sel if "vy_hold_absmax" in a["shear"]]
            hv = [a["shear"]["hand_vy_hold_mean"] for a in sel
                  if a["shear"].get("hand_vy_hold_mean") is not None]
            print("| %s | %s | %d | %s | %s | %s | %s |" % (
                c["label"], cls, len(sel), stats(ve), stats(vh), stats(va), stats(hv)))
    print()
    print("-- the hold-segment world displacement decomposition (the K1 read: hand vs payload) --")
    print()
    print("| corpus | # | file | arm | species | cls | hold walk mm (relative) | hand dy mm | fruit dy mm | hand dx mm | fruit dx mm | hand dz mm | fruit dz mm |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for cc in corpora:
        c = cc["c"]
        for a in sorted(cc["rows"], key=lambda x: -(x["hold_walk"] or 0)):
            sp = a["shear"]
            if "hand_dy" not in sp:
                continue
            print("| %s | %d | %s | %s | %s | %s | %s | %+.1f | %+.1f | %+.1f | %+.1f | %+.1f | %+.1f |" % (
                c["label"], a["pair"]["k"], short(a), a["side"], a["species"], a["cls"],
                "-" if a["hold_walk"] is None else "%.1f" % a["hold_walk"],
                sp["hand_dy"], sp["fruit_dy"], sp["hand_dx"], sp["fruit_dx"],
                sp["hand_dz"], sp["fruit_dz"]))
    print()

    # ---------------- E2. the true freeze lines ----------------
    print("== E2. the primitive's own freeze lines (the true freeze tick; the actuation check) ==")
    print()
    print("| corpus | freeze lines (of 20 attempts) | ticks min/med/max | ticks >= 40 | force at freeze min/med/max N | pathological (span < 0) |")
    print("| --- | --- | --- | --- | --- | --- |")
    for cc in corpora:
        c = cc["c"]
        fl = cc["freeze_lines"]
        if not fl:
            continue
        ticks = [x["ticks"] for x in fl]
        forces = [x["force"] for x in fl]
        late = sum(1 for t in ticks if t >= 40)
        weird = sum(1 for x in fl if x["span"] < 0)
        print("| %s | %d | n=%d  min %d / med %.1f / max %d | %d | n=%d  min %.2f / med %.2f / max %.2f | %d |" % (
            c["label"], len(fl), len(ticks), min(ticks), statistics.median(ticks), max(ticks),
            late, len(forces), min(forces), statistics.median(forces), max(forces), weird))
    print()
    print("-- the freeze ticks in log order --")
    for cc in corpora:
        c = cc["c"]
        print("%s: %s" % (c["label"], ", ".join(str(x["ticks"]) for x in cc["freeze_lines"])))
    print()

    # ---------------- F. the K2 check ----------------
    print("== F. the K2 never-grasped check ==")
    print()
    print("| corpus | n | R11-B signature (onset<=3, F=0, c=0) | of which no-grasp attempts | max force == 0 over the trace | max contacts == 0 over close+hold |")
    print("| --- | --- | --- | --- | --- | --- |")
    for cc in corpora:
        c = cc["c"]
        sig = [a for a in cc["rows"] if a["never_grasped"]]
        sig_ng = [a for a in sig if a["cls"] in ("B1", "B2")]
        f0 = [a for a in cc["rows"] if a["contact"]["max_force"] == 0.0]
        c0 = [a for a in cc["rows"] if a["contact"]["cap_contacts"] == 0]
        print("| %s | %d | %d | %d | %d | %d |" % (
            c["label"], len(cc["rows"]), len(sig), len(sig_ng), len(f0), len(c0)))
    print()
    print("-- the signature attempts in detail --")
    print()
    print("| corpus | # | file | arm | species | cls | [carry] onset/F/c/clean_slip | max force | cap force/contacts |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for cc in corpora:
        c = cc["c"]
        for a in cc["rows"]:
            if not a["never_grasped"]:
                continue
            cl = a["carry_log"]
            cl_txt = "%s/%s/%s/%.1f" % (cl["onset_row"], cl["force_onset"],
                                        cl["contacts_onset"], cl["clean_slip_max"]) if cl else "-"
            print("| %s | %d | %s | %s | %s | %s | %s | %.2f | %.2f/%d |" % (
                c["label"], a["pair"]["k"], short(a), a["side"], a["species"], a["cls"],
                cl_txt, a["contact"]["max_force"], a["contact"]["cap_force"],
                a["contact"]["cap_contacts"]))
    print()

    # ---------------- G. the outcome census ----------------
    print("== G. the outcome census and the gate arithmetic ==")
    print()
    print("| corpus | env | ok | carried | no-grasp | B1 | B2 |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for cc in corpora:
        c = cc["c"]
        cen = cc["census"]
        print("| %s | %s | %d | %d | %d | %d | %d |" % (
            c["label"], c["env"], cen.get("ok", 0), cen.get("carried", 0),
            cen.get("B1", 0) + cen.get("B2", 0), cen.get("B1", 0), cen.get("B2", 0)))
    print()
    print("-- the release bracket histogram (descriptive) --")
    print()
    for cc in corpora:
        c = cc["c"]
        hist = {}
        for a in cc["rows"]:
            rel = a["release"]
            if rel is None:
                continue
            key = rel["row"]["phase"]
            hist.setdefault(key, []).append((a, rel))
        print(f"-- {c['label']} --")
        for k in sorted(hist):
            print(f"  {k}: {len(hist[k])}  " +
                  ", ".join("%s/%s" % (short(a), a["cls"]) for a, _ in hist[k]))
    print()

    # ---------------- H. the walk-once-more read: the control's hold-walk attempts ----------------
    print("== H. the control's three hold-walk attempts, tracked per corpus ==")
    print()
    print("(the control's hold-walk B1s: att 1 left orange 38.1, att 6 left tomato 31.9, att 8 left orange 54.8 mm;")
    print(" the branch moved between corpora, so the honest tracking is by fruit+arm at the same seed where present)")
    print()
    for cc in corpora:
        c = cc["c"]
        print(f"-- {c['label']} --")
        for a in cc["rows"]:
            if a["cls"] == "ok" and a["hold_walk"] is not None and a["hold_walk"] <= 12.8:
                continue
            print("   %2d %-6s %-8s %-6s walk %7.1f mm  %s" % (
                a["pair"]["k"], a["side"], a["species"], a["cls"], a["hold_walk"], a["outcome"]))
    print()


if __name__ == "__main__":
    main()
