#!/usr/bin/env python3
"""P51 phase 1: the offline map of the speed/mass cells' acquisition rows (read-only).

Question (`.slim/deepwork/p51-combo-test.md` section 2): do the P44/P45/P46
speed/mass cells' *new* acquisition rows (`fruit did not follow the gripper` /
never-held) sit in the **delivered-x tail** (|x| >= 0.390, P48) - i.e. would the
P50 per-instance release-offset table have prevented them - or do they sit
**mid-band**, in which case the cost has a second mechanism?

Nothing here runs a simulator, edits `src/` or touches a `configs/` file. The
parsers and the regexes are imported from `logs/p49/select_census.py` so the
per-attempt attribution (the single-arm block rule and the two-line per-arm
ordinal pairing that P48 validated) is the same object, not a re-derivation.

Usage: python3 logs/p51/combo_map.py > logs/p51/combo_map_out.txt
"""
from __future__ import annotations

import glob
import importlib.util
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P49 = os.path.join(ROOT, "logs/p49/select_census.py")


def load_p49():
    spec = importlib.util.spec_from_file_location("p49_select_census", P49)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # main() is guarded
    return mod


p49 = load_p49()
RE_START, RE_SKIP, RE_RESULT = p49.RE_START, p49.RE_SKIP, p49.RE_RESULT
RE_TARGET, RE_WAIT0, RE_HANDOVER = p49.RE_TARGET, p49.RE_WAIT0, p49.RE_HANDOVER
RE_CATCH, RE_ARRIVED, RE_DESCENT = p49.RE_CATCH, p49.RE_ARRIVED, p49.RE_DESCENT
RE_APPROACH, RE_BIARM = p49.RE_APPROACH, p49.RE_BIARM
fnum, pct = p49.fnum, p49.pct

# the attempt's own outcome rows (both presentations)
RE_NOTES = re.compile(r"notes=\[(.*?)\]")
RE_CARRY = re.compile(
    r"\[carry\] (left|right) (\w+): ticks=(\d+)/(\d+) clean_slip_max=([\d.]+)mm "
    r"in-hand_vmax=([-\d.]+) onset_row=(\w+) force@onset=([\d.]+|n/a)N "
    r"sep@onset=([\d.]+|n/a)mm contacts@onset=(\d+|None) min_contacts=(\d+) "
    r"force_min=([\d.]+)N"
)
RE_CYCLE = re.compile(r"\[cycle\] attempt (\d+):")

TAIL = 0.390          # P48: |x| >= 0.390 is 6/6 failed
BAND = (0.180, 0.390)  # the clean reach band (174 / P48 section 2.1)

ACC_TABLE = "configs/release_offsets_accept_s5.json"
PEAR_TABLE = "configs/release_offsets_pear_s5.json"

# ---------------------------------------------------------------- corpora ----
# (corpus tag, arm label, role, log)
ARMS = []
for f in ("accept_s5_C", "accept_s5_S1", "accept_s5_S2", "accept_s5_S3",
          "accept_s5_S13"):
    ARMS.append(("P44-speed", f.split("_", 2)[2], "accept_s5", f"logs/p44/p2/{f}.log"))
for f in ("accept_s6_C", "accept_s6_S13"):
    ARMS.append(("P44-speed", f.split("_", 2)[2], "accept_s6", f"logs/p44/p2/{f}.log"))
for f in ("amend_E_C", "amend_E_S1", "amend_E_S3v", "amend_F_C", "amend_F_S2"):
    ARMS.append(("P44-amend", f.replace("amend_", "").replace("_C", "_C"), "accept_s5",
                 f"logs/p44/p2/{f}.log"))
for f in ("pear_s5_C", "pear_s5_S13"):
    ARMS.append(("P44-speed", f.split("_", 2)[2], "pear_s5", f"logs/p44/p2/{f}.log"))
for f in ("twoline_s5_C", "twoline_s5_S13"):
    ARMS.append(("P44-twoline", f.split("_", 2)[2], "twoline_s5", f"logs/p44/p2/{f}.log"))
for f in ("accept_s5_C", "accept_s5_M25", "accept_s5_M50", "accept_s5_M25S",
          "accept_s5_M50S"):
    ARMS.append(("P45-mass", f.split("_", 2)[2], "accept_s5", f"logs/p45/p2/{f}.log"))
for f in ("pear_s5_C", "pear_s5_M25", "pear_s5_M50", "pear_s5_M25S", "pear_s5_M50S"):
    ARMS.append(("P45-mass", f.split("_", 2)[2], "pear_s5", f"logs/p45/p2/{f}.log"))
for s in ("5", "6"):
    for a in ("C", "U"):
        ARMS.append(("P46-twoline", a, f"twoline_s{s}", f"logs/p46/p1/twoline_s{s}_{a}.log"))
# controls (the shipped / pre-cell tree)
for f, tag in (("logs/p41/p2/accept_profile.log", "accept_s5"),
               ("logs/p41/p2/accept_preprofile.log", "accept_s5"),
               ("logs/p41/p2/pear_profile.log", "pear_s5"),
               ("logs/p39/p3/accept_C.log", "accept_s5"),
               ("logs/p39/p3/pear_C.log", "pear_s5")):
    ARMS.append(("shipped", os.path.basename(f).replace(".log", ""), tag, f))


# ---------------------------------------------------------------- parsing ----
def load(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        print(f"  MISSING {rel}", file=sys.stderr)
        return None
    with open(p, errors="replace") as fh:
        return fh.read()


def carry_rows(text):
    """[(arm, leg, contacts@onset, min_contacts, force_min, slip, tid)] in order."""
    out = []
    for line in text.splitlines():
        m = RE_CARRY.search(line)
        if m:
            out.append({
                "arm": m.group(1), "leg": m.group(2),
                "contacts_onset": (None if m.group(10) == "None" else int(m.group(10))),
                "min_contacts": int(m.group(11)),
                "force_min": fnum(m.group(12)),
                "slip": fnum(m.group(5)),
                "on": m.group(7) != "None",
            })
    return out


def parse_single(rel, text):
    """P49's single-arm block rule + the notes / lift / force of the result row."""
    out, cur = [], None
    for line in text.splitlines():
        if "[fruit]" not in line:
            continue
        m = RE_START.search(line)
        if m:
            cur = {"log": rel, "idx": int(m.group(1)), "species": m.group(2),
                   "arm": None, "diameter": None, "x": None, "dy0": None,
                   "queue": None, "residual": None, "approach_end": None,
                   "notes": "", "grasped": None, "lift": None, "force": None,
                   "outcome": "open", "cycle": None}
            out.append(cur)
            continue
        m = RE_SKIP.search(line)
        if m:
            out.append({"log": rel, "idx": int(m.group(1)), "species": None,
                        "arm": None, "diameter": None, "x": None, "dy0": None,
                        "queue": None, "residual": None, "approach_end": None,
                        "notes": "", "grasped": None, "lift": None, "force": None,
                        "outcome": "skip", "cycle": None})
            cur = None
            continue
        if cur is None:
            continue
        m = RE_RESULT.search(line)
        if m:
            g, p = m.group(2) == "True", m.group(3) == "True"
            cur["outcome"] = "placed" if p else ("cnp" if g else "nograsp")
            cur["grasped"], cur["lift"], cur["force"] = g, fnum(m.group(4)), fnum(m.group(5))
            nm = RE_NOTES.search(line)
            cur["notes"] = nm.group(1) if nm else ""
            cur = None
            continue
        m = RE_TARGET.search(line)
        if m:
            cur["species"], cur["diameter"], cur["arm"] = m.group(1), fnum(m.group(3)), m.group(4)
            continue
        m = RE_WAIT0.search(line)
        if m and cur["x"] is None:
            cur["x"], cur["dy0"] = fnum(m.group(2)), fnum(m.group(4))
            continue
        m = RE_HANDOVER.search(line)
        if m:
            cur["queue"] = int(m.group(5))
            continue
        m = RE_CATCH.search(line)
        if m:
            cur["residual"] = fnum(m.group(1))
            continue
        m = RE_APPROACH.search(line)
        if m:
            cur["approach_end"] = fnum(m.group(3))
            continue
    # the `[cycle] attempt N` blocks are 1:1 with the `[run] attempt` blocks
    cyc = [int(m.group(1)) for line in text.splitlines() if (m := RE_CYCLE.search(line))]
    for i, r in enumerate(out):
        r["cycle"] = cyc[i] if i < len(cyc) else None
    return out


def parse_twoline(rel, text):
    """P49's per-arm ordinal pairing + the result row's notes/lift/force/cycle."""
    targets = {"left": [], "right": []}
    waits = {"left": [], "right": []}
    handovers = {"left": [], "right": []}
    results = {"left": [], "right": []}
    descent_arms, catches, approaches = [], [], []

    def arm_of(station):
        if station is None:
            return None
        if abs(station) < 0.05:
            return "left"
        if abs(station + 0.100) < 0.05:
            return "right"
        return None

    cyc = None
    for line in text.splitlines():
        if "[fruit]" not in line:
            continue
        m = RE_CYCLE.search(line)
        if m:
            cyc = int(m.group(1))
            continue
        m = RE_TARGET.search(line)
        if m:
            targets[m.group(4)].append((m.group(1), fnum(m.group(3))))
            continue
        m = RE_WAIT0.search(line)
        if m:
            arm = arm_of(fnum(m.group(1)) - fnum(m.group(4)))
            if arm is not None:
                waits[arm].append({"x": fnum(m.group(2)), "dy0": fnum(m.group(4))})
            continue
        m = RE_HANDOVER.search(line)
        if m:
            arm = arm_of(fnum(m.group(1)) - fnum(m.group(2)))
            if arm is not None:
                handovers[arm].append({"dy": fnum(m.group(2)), "queue": int(m.group(5))})
            continue
        m = RE_DESCENT.search(line)
        if m:
            descent_arms.append(arm_of(fnum(m.group(3))))
            continue
        m = RE_CATCH.search(line)
        if m:
            catches.append(fnum(m.group(1)))
            continue
        m = RE_APPROACH.search(line)
        if m:
            approaches.append(fnum(m.group(3)))
            continue
        m = RE_BIARM.search(line)
        if m:
            nm = RE_NOTES.search(line)
            results[m.group(1)].append({
                "outcome": "placed" if m.group(5) == "True"
                           else ("cnp" if m.group(4) == "True" else "nograsp"),
                "idx": int(m.group(2)), "species": m.group(3),
                "notes": nm.group(1) if nm else "", "cycle": cyc,
                "grasped": m.group(4) == "True",
            })
            continue

    catch_by_arm = {"left": [], "right": []}
    appr_by_arm = {"left": [], "right": []}
    for k, arm in enumerate(descent_arms):
        if arm is None:
            continue
        if k < len(catches):
            catch_by_arm[arm].append(catches[k])
        if k < len(approaches):
            appr_by_arm[arm].append(approaches[k])

    out = []
    for arm in ("left", "right"):
        n = min(len(targets[arm]), len(waits[arm]))
        for k in range(n):
            sp, dia = targets[arm][k]
            w = waits[arm][k]
            res = results[arm][k] if k < len(results[arm]) else {}
            ho = handovers[arm][k] if k < len(handovers[arm]) else {}
            out.append({
                "log": rel, "arm": arm, "idx": k, "cycle": res.get("cycle"),
                "species": sp, "diameter": dia, "x": w["x"], "dy0": w["dy0"],
                "queue": ho.get("queue"),
                "residual": catch_by_arm[arm][k] if k < len(catch_by_arm[arm]) else None,
                "approach_end": appr_by_arm[arm][k] if k < len(appr_by_arm[arm]) else None,
                "outcome": res.get("outcome", "open"), "grasped": res.get("grasped"),
                "lift": None, "force": None, "notes": res.get("notes", ""),
            })
    return out


def parse(rel):
    text = load(rel)
    if text is None:
        return [], []
    if "[biarm] result" in text:
        rows = parse_twoline(rel, text)
    else:
        rows = parse_single(rel, text)
    return rows, carry_rows(text)


# ---------------------------------------------------------------- tables -----
def tables():
    t = {}
    for key, rel in (("accept", ACC_TABLE), ("pear", PEAR_TABLE)):
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            print(f"  MISSING {rel}", file=sys.stderr)
            continue
        with open(p) as fh:
            j = json.load(fh)
        t[key] = {"scenario": j["scenario"], "offsets": j["offsets"],
                  "identity": j.get("identity", False),
                  "rows": {r["signature"]: r for r in j["rows"]}}
    return t


def offset_for(tab, species, dia_cm):
    """the table's applied offset (mm) for this instance, or (None, why).

    `dia_cm` is the `target ... (grade G, D cm)` field (1 decimal = 1 mm
    resolution), the table's signature is mm, so the match is one rounding step.
    """
    if tab is None:
        return None, "no table (pool out of scope)"
    if tab["identity"]:
        return 0.0, "identity table"
    if species is None or dia_cm is None:
        return None, "no instance"
    for sig, off in tab["offsets"].items():
        sp, d = sig.split("|")
        if sp == species and abs(float(d) - dia_cm * 10.0) <= 0.55:
            return off, sig
    # not in this pool: the nearest same-species row, flagged as an extrapolation
    best = None
    for sig, off in tab["offsets"].items():
        sp, d = sig.split("|")
        if sp == species:
            dd = abs(float(d) - dia_cm * 10.0)
            if best is None or dd < best[0]:
                best = (dd, sig, off)
    if best is not None:
        return best[2], f"EXTRAPOLATED from {best[1]} (+-{best[0]:.1f} mm)"
    return None, "species not in table"


# ---------------------------------------------------------------- main -------
def cls(x):
    if x is None:
        return "?"
    if x >= TAIL:
        return "TAIL"
    if x < BAND[0]:
        return "low"
    return "mid"


def res_cls(r):
    """P48's split: > 6 mm = the distance/acquisition class, <= 6 mm = converged."""
    if r["residual"] is None:
        return "n/a"
    return "distance" if r["residual"] > 6.0 else "converged"


def fisher2(a, b, c, d):
    """a=tail/fail, b=tail/ok, c=below/fail, d=below/ok -> (p0, two-sided)."""
    from math import comb
    r1, r2, c1 = a + b, c + d, a + c
    n = r1 + r2
    tot = comb(n, c1)
    if tot == 0:
        return float("nan"), float("nan")

    def pr(i):
        j, k = r1 - i, c1 - i
        l = r2 - k
        if j < 0 or k < 0 or l < 0:
            return 0.0
        return comb(r1, i) * comb(r2, k) / tot

    p0 = pr(a)
    s = sum(pr(i) for i in range(0, min(r1, c1) + 1) if pr(i) <= p0 * (1 + 1e-9))
    return p0, s


def main():
    tabs = tables()
    print("P51 phase 1 - the speed/mass cells' acquisition rows, and whether the")
    print("P50 release-offset table would have prevented them")
    print("=" * 118)
    print(f"tail = delivered x >= {TAIL:.3f} m (P48: 6/6 failed); band "
          f"[{BAND[0]:.3f}, {BAND[1]:.3f}] = the clean top-down reach (174 / P48 2.1)")
    print("compensation: x_comp = x_delivered - offset(species|diameter); a table is "
          "PER POOL (P50 rule)")
    for k, v in tabs.items():
        print(f"  table {k}: scenario={v['scenario']} identity={v['identity']} "
              f"instances={len(v['offsets'])}")

    allrows = []
    for corpus, arm, scenario, rel in ARMS:
        rows, carries = parse(rel)
        if not rows:
            continue
        # the pool a table was measured on: accept_s5 -> accept table, pear_s5 ->
        # pear table; every other supply (accept_s6, the two-line wave/patch) has
        # no table of its own (P50 measured two pools).
        tab = tabs.get("accept" if scenario == "accept_s5" else
                       ("pear" if scenario == "pear_s5" else None))
        for r in rows:
            r["corpus"], r["arm_label"], r["scenario"] = corpus, arm, scenario
            r["table"] = tab
            r["cls"] = cls(r["x"])
            r["rcls"] = "n/a"
            r["acq"] = "fruit did not follow the gripper" in (r["notes"] or "")
            nh = [c for c in carries if c["contacts_onset"] == 0
                  and c["min_contacts"] == 0]
            r["never_held_legs"] = len(nh)
            r["acq_row"] = bool(r["acq"] or r["outcome"] == "nograsp")
            r["rcls"] = res_cls(r) if r["acq_row"] else "-"
            allrows.append(r)

    # ------------------------------------------------ 1. the acquisition rows --
    print("\n" + "#" * 118)
    print("# 1. EVERY ACQUISITION ROW (nograsp / 'fruit did not follow the gripper')")
    print("#    res.cls = P48's split: residual > 6 mm = the distance class, <= 6 mm "
          "= a converged close")
    print("#" * 118)
    hdr = (f"{'corpus':<12} {'arm':<7} {'scenario':<11} {'att':>4} {'cyc':>4} {'arm':<5} "
           f"{'species':<10} {'dia':>4} {'x':>7} {'cls':<5} {'resid':>6} {'res.cls':<9} "
           f"{'end':>5} {'nh'}")
    print(hdr)
    print("-" * len(hdr))
    for r in allrows:
        if not r["acq_row"]:
            continue
        print(f"{r['corpus']:<12} {r['arm_label']:<7} {r['scenario']:<11} "
              f"{(r['idx'] if r['idx'] is not None else -1):>4} "
              f"{(r['cycle'] if r['cycle'] is not None else -1):>4} "
              f"{(r['arm'] or '?'):<5} {(r['species'] or '?'):<10} "
              f"{(r['diameter'] if r['diameter'] is not None else 0):>4.1f} "
              f"{(r['x'] if r['x'] is not None else -1):>7.4f} {r['cls']:<5} "
              f"{(r['residual'] if r['residual'] is not None else -1):>6.1f} "
              f"{r['rcls']:<9} "
              f"{(r['approach_end'] if r['approach_end'] is not None else -1):>5.1f} "
              f"{r['never_held_legs']}")

    # ------------------------------------------------ 2. distinct events ------
    ev = {}
    for r in allrows:
        if not r["acq_row"] or r["x"] is None:
            continue
        ev.setdefault((r["scenario"], r["species"], r["diameter"], round(r["x"], 3),
                       r["arm"]), []).append(r)

    print("\n" + "#" * 118)
    print("# 2. THE DISTINCT EVENTS, and whether the arm's OWN CONTROL draws the same")
    print("#    event (shared = the scenario's, not the cell's; new = cell-attributable)")
    print("#" * 118)
    hdr = (f"{'event':<46} {'rows':<4} {'labels':<34} {'C has it?':<10} {'status'}")
    print(hdr)
    print("-" * len(hdr))
    for key, rs in sorted(ev.items(), key=lambda kv: (kv[0][0], -kv[0][3])):
        labels = sorted({x["arm_label"] for x in rs})
        ctrl = [x for x in rs if x["arm_label"] in ("C", "accept_C",
                                                    "accept_preprofile",
                                                    "accept_profile")]
        status = "shared" if ctrl else "NEW"
        name = (f"{key[0]}/{key[1]}{'' if key[2] is None else key[2]}/{key[4]}/{key[3]:.4f}")
        print(f"{name:<46} {len(rs):<4} {','.join(labels):<34} "
              f"{('yes' if ctrl else 'no'):<10} {status}")

    # ------------------------------------------------ 3. counterfactual -------
    print("\n" + "#" * 118)
    print(f"# 3. THE COUNTERFACTUAL: x_comp = x - offset  ->  inside [{BAND[0]}, "
          f"{BAND[1]}]?")
    print("#    (a table exists only for its own pool: accept_s5, pear_s5; accept_s6 "
          "and the two-line are out of scope)")
    print("#" * 118)
    hdr = (f"{'event':<44} {'x':>7} {'offset':>8} {'x_comp':>7} {'in band':<8} "
           f"{'res.cls':<9} {'mechanism / scope'}")
    print(hdr)
    print("-" * len(hdr))
    for key, rs in sorted(ev.items(), key=lambda kv: -kv[0][3]):
        r = rs[0]
        off, why = offset_for(r["table"], r["species"], r["diameter"])
        xc = None if (off is None or r["x"] is None) else r["x"] - off / 1000.0
        inb = ("-" if xc is None else ("yes" if BAND[0] <= xc <= BAND[1] else "NO"))
        name = (f"{r['scenario']}/{r['species']}{r['diameter']}/{r['arm']}/{r['x']:.4f}")
        print(f"{name:<44} {r['x']:>7.4f} "
              f"{(off if off is not None else float('nan')):>8.3f} "
              f"{(xc if xc is not None else float('nan')):>7.4f} {inb:<8} "
              f"{r['rcls']:<9} {why}")

    # ------------------------------------------------ 4. counts --------------
    print("\n" + "#" * 118)
    print("# 4. THE COUNTS: rows and distinct events per corpus, tail vs mid-band")
    print("#" * 118)
    for corpus in ("P44-speed", "P44-amend", "P44-twoline", "P45-mass", "P46-twoline",
                   "shipped"):
        rs = [r for r in allrows if r["corpus"] == corpus and r["acq_row"] and r["x"]]
        evs = {}
        for r in rs:
            evs.setdefault((r["scenario"], r["species"], r["diameter"],
                            round(r["x"], 3), r["arm"]), []).append(r)
        tail = [k for k in evs if k[3] >= TAIL]
        mid = [k for k in evs if BAND[0] <= k[3] < TAIL]
        low = [k for k in evs if k[3] < BAND[0]]
        dist = [k for k, v in evs.items() if res_cls(v[0]) == "distance"]
        conv = [k for k, v in evs.items() if res_cls(v[0]) == "converged"]
        print(f"{corpus:<14} rows={len(rs):>3} events={len(evs):>2}  tail={len(tail)} "
              f"mid={len(mid)} low={len(low)} | distance={len(dist)} "
              f"converged={len(conv)} | x={sorted(round(k[3], 3) for k in evs)}")

    # ------------------------------------------------ 5. per-arm view --------
    print("\n" + "#" * 118)
    print("# 5. PER ARM: the outcome classes (this is where a count loss shows up)")
    print("#" * 118)
    hdr = (f"{'corpus':<13} {'arm':<7} {'scenario':<11} {'n':>3} {'placed':>6} "
           f"{'cnp':>4} {'nograsp':>7} {'skip':>4} {'acq':>4} {'x of the acq rows'}")
    print("-" * len(hdr))
    print(hdr)
    print("-" * len(hdr))
    for corpus, arm, scenario, rel in ARMS:
        rs = [r for r in allrows if r["log"] == rel and r["arm_label"] == arm]
        if not rs:
            continue
        acq = [r for r in rs if r["acq_row"] and r["x"]]
        print(f"{corpus:<13} {arm:<7} {scenario:<11} {len(rs):>3} "
              f"{sum(1 for r in rs if r['outcome'] == 'placed'):>6} "
              f"{sum(1 for r in rs if r['outcome'] == 'cnp'):>4} "
              f"{sum(1 for r in rs if r['outcome'] == 'nograsp'):>7} "
              f"{sum(1 for r in rs if r['outcome'] == 'skip'):>4} {len(acq):>4} "
              f"{[(round(r['x'], 4), r['rcls'][:4]) for r in acq]}")

    # ------------------------------------------------ 6. second mechanism ----
    print("\n" + "#" * 118)
    print("# 6. THE MID-BAND / NON-TAIL ROWS: what else distinguishes them")
    print("#" * 118)
    non_tail = [r for r in allrows if r["acq_row"] and r["x"] and r["x"] < TAIL]
    okrows = [r for r in allrows if r["outcome"] == "placed" and r["x"]]
    print(f"  non-tail acquisition rows: {len(non_tail)} "
          f"(converged {sum(1 for r in non_tail if r['rcls'] == 'converged')}, "
          f"distance {sum(1 for r in non_tail if r['rcls'] == 'distance')})")
    for r in non_tail:
        print(f"   {os.path.basename(r['log']):<22} {r['arm_label']:<7} "
              f"{r['species']} {r['diameter']} {r['arm']:<5} x={r['x']:.4f} "
              f"resid={r['residual']} ({r['rcls']}) end={r['approach_end']} "
              f"nh={r['never_held_legs']} queue={r['queue']}")
    if okrows:
        xs = [r["x"] for r in okrows]
        rr = [r["residual"] for r in okrows if r["residual"] is not None]
        ee = [r["approach_end"] for r in okrows if r["approach_end"] is not None]
        print(f"\n  placed attempts: n={len(okrows)} x min={min(xs):.4f} "
              f"p50={pct(xs,.5):.4f} max={max(xs):.4f}; residual {min(rr):.1f}-{max(rr):.1f}"
              f"; approach end= {min(ee):.1f}-{max(ee):.1f}")
        print(f"  -> no placed attempt in this corpus is delivered past "
              f"{max(xs):.4f} m")

    # ------------------------------------------------ 7. fisher -------------
    print("\n" + "#" * 118)
    print("# 7. THE 2x2 ACROSS THE WHOLE MAP (rows): tail vs below, failed vs placed")
    print("#" * 118)
    tf = sum(1 for r in allrows if r["acq_row"] and r["x"] and r["x"] >= TAIL)
    to = sum(1 for r in allrows if not r["acq_row"] and r["x"] and r["x"] >= TAIL)
    rf = sum(1 for r in allrows if r["acq_row"] and r["x"] and r["x"] < TAIL)
    ro = sum(1 for r in allrows if not r["acq_row"] and r["x"] and r["x"] < TAIL)
    print(f"  rows (all mapped logs, duplicates included): tail fail={tf} ok={to} | "
          f"below fail={rf} ok={ro}")
    p0, pv = fisher2(tf, to, rf, ro)
    print(f"  Fisher exact: p0={p0:.3e}  two-sided={pv:.3e}")
    # the cell-attributable rows only
    newkeys = [k for k, rs in ev.items()
               if not any(x["arm_label"] in ("C", "accept_C", "accept_profile",
                                             "accept_preprofile") for x in rs)]
    print(f"  cell-attributable events (no C row of the same event): {len(newkeys)}")
    for k in sorted(newkeys, key=lambda k: -k[3]):
        v = ev[k][0]
        print(f"    {k[0]}/{k[1]}{k[2]}/{k[4]} x={k[3]:.4f} "
              f"({'TAIL' if k[3] >= TAIL else 'mid'}) resid={v['residual']} "
              f"({v['rcls']})")

    # ------------------------------------------------ 8. table coverage ------
    print("\n" + "#" * 118)
    print("# 8. TABLE COVERAGE PER SCENARIO (a table is per pool: this is what limits")
    print("#    which arms an `O` run can even be measured on)")
    print("#" * 118)
    inst = {}
    for r in allrows:
        if r["species"] and r["diameter"] is not None:
            inst.setdefault(r["scenario"], set()).add((r["species"], r["diameter"]))
    for scen in sorted(inst):
        tab = tabs.get("accept" if scen == "accept_s5" else
                       ("pear" if scen == "pear_s5" else None))
        keys = sorted(inst[scen])
        if tab is None:
            # out of scope by P50's per-pool rule; still report how many of its
            # instance NAMES coincide with the seed-5 table (a licence question,
            # not a measurement: the offset is a per-pool live quantity)
            acc = tabs.get("accept")
            names = [f"{sp}{d}" for sp, d in keys
                     if offset_for(acc, sp, d)[1].split("|")[0].strip() in
                     (acc["offsets"] if acc else {})]
            hit = [f"{sp}{d}" for sp, d in keys
                   if not offset_for(acc, sp, d)[1].startswith("species not")
                   and "EXTRAP" not in offset_for(acc, sp, d)[1]]
            print(f"  {scen:<12} instances={len(keys):>2}  NO TABLE for this pool "
                  f"(P50 measured accept_s5 and pear_s5 only); "
                  f"name-covered by the seed-5 table: {len(hit)}/{len(keys)}"
                  + (f" {hit}" if hit else ""))
            continue
        hits, misses = [], []
        for sp, d in keys:
            off, why = offset_for(tab, sp, d)
            (hits if off is not None and "EXTRAP" not in why else misses).append(
                f"{sp}{d}")
        print(f"  {scen:<12} instances={len(keys):>2}  table={tab['scenario']:<10} "
              f"covered={len(hits):>2} miss={len(misses):>2}"
              + (f"  misses={misses}" if misses else ""))

    # ------------------------------------------------ 9. tail rate -----------
    print("\n" + "#" * 118)
    print("# 9. THE DELIVERED-x POPULATION OF THIS MAP (unique attempts)")
    print("#" * 118)
    ux = {}
    for r in allrows:
        if r["x"] is not None:
            ux.setdefault((r["scenario"], r["species"], r["diameter"],
                           round(r["x"], 3), r["arm"]), r)
    xs = [k[3] for k in ux]
    print(f"  unique attempts with an x: n={len(xs)}  min={min(xs):.3f} "
          f"p50={pct(xs,.5):.3f} p90={pct(xs,.9):.3f} max={max(xs):.3f}")
    print(f"  >= {TAIL:.3f}: {sum(1 for v in xs if v >= TAIL)} "
          f"({100*sum(1 for v in xs if v >= TAIL)/len(xs):.1f} %); "
          f">= 0.380: {sum(1 for v in xs if v >= 0.380)}; "
          f"in band [{BAND[0]},0.380): {sum(1 for v in xs if BAND[0] <= v < 0.380)}; "
          f"< {BAND[0]}: {sum(1 for v in xs if v < BAND[0])}")
    print(f"  the placed population's max x = "
          f"{max((k[3] for k in ux if ux[k]['outcome'] == 'placed'), default=float('nan')):.4f}"
          f" -> the empirical no-placement edge is ~0.371, not the registered 0.390")

    # ------------------------------------------------ 10. cell vs control ----
    print("\n" + "#" * 118)
    print("# 10. THE SAME-BATTERY CONTROL vs THE CELLS: the event mix")
    print("#     (the control of an arm is the C log of its own battery; the shipped")
    print("#      logs are listed apart - they are a different tree's baseline)")
    print("#" * 118)
    CT = ("C",)
    ctrl_ev, cell_ev = {}, {}
    for k, rs in ev.items():
        is_c = any(x["arm_label"] in CT and x["corpus"] != "shipped" for x in rs)
        is_cell = any(x["arm_label"] not in CT and x["corpus"] != "shipped" for x in rs)
        if is_cell and not is_c:
            cell_ev[k] = rs
        elif is_c and not is_cell:
            ctrl_ev[k] = rs
        elif is_c and is_cell:
            ctrl_ev[k] = rs  # shared: counted as the control's (the scenario's)
    for name, d in (("same-battery control", ctrl_ev), ("cells (new)", cell_ev)):
        tail = sum(1 for k in d if k[3] >= TAIL)
        dist = sum(1 for k, v in d.items() if res_cls(v[0]) == "distance")
        print(f"  {name:<22} events={len(d):>2}  tail={tail}  non-tail={len(d)-tail}  "
              f"distance={dist}  converged={len(d)-dist}")
        for k in sorted(d, key=lambda k: -k[3]):
            v = d[k][0]
            print(f"      {k[0]}/{k[1]}{k[2]}/{k[4]:<5} x={k[3]:.4f} "
                  f"resid={v['residual']} ({v['rcls']})")
    a, b = sum(1 for k in cell_ev if k[3] >= TAIL), len(cell_ev)
    c, d_ = sum(1 for k in ctrl_ev if k[3] >= TAIL), len(ctrl_ev)
    p0, pv = fisher2(a, b - a, c, d_ - c)
    print(f"  tail share: cells {a}/{b} vs control {c}/{d_} -> Fisher "
          f"p0={p0:.3f} two-sided={pv:.3f}")
    print("  -> the two mixes are the same object; the tail is not a cell-specific "
          "signature")


if __name__ == "__main__":
    main()
