#!/usr/bin/env python3
"""P103 readout: the sim-only perfect-detector re-grip, its ledger and its A/B.

    python3 logs/p103/p103_report.py ledge   logs/p103/T5.log ...
    python3 logs/p103/p103_report.py ab      logs/p103/{C,T}5.log ...
    python3 logs/p103/p103_report.py --same  REF CAND
    python3 logs/p103/p103_report.py --check logs/p103/T5.log ...

Three readouts, and they answer three different questions:

* `ledge`  - **the mechanism** (`logs/p103/PREREG.md` §6): every `[regrip]` leg
  with its trigger state, and the attempt it belongs to. The join is P102's:
  a side's k-th `grasp_lift` leg **is** that side's k-th attempt (an attempt
  that never closes on the fruit still takes its lift leg), so the k-th
  `grasp_lift` row for a side maps onto the k-th `[run] attempt N (side)` row.
  That join is *checked* here (one `[run]` row per `grasp_lift` per side) rather
  than assumed.
* `ab`     - the endpoints. Every rate, interval and wall figure is `p80lib`'s
  (`logs/p80/p80lib.py` -> `scripts/186_w6_report.py`), i.e. P80's definitions:
  a placement is the attempt's `t1`, the placement window is
  `t_last_place - t_first_place`, the batch span is `t_last_end - t_first_start`,
  and the wall comes from the `.stamps` stream. Nothing is re-derived here.
* `--same` - the sealed line-for-line comparison: the `[fruit]` stream must be
  byte-identical with this phase's own rows dropped.

The false-positive ledger falls out of `ledge`: a **held** leg is one whose
`[carry] clean_slip_max` stays under P74's 100 mm (the payload never left), so a
leg that tripped and still reads a held leg's slip is a false positive - and the
question is whether its attempt placed.

Exit 1 on a malformed row under `--check`. Read-only; nothing outside stdout.
"""

from __future__ import annotations

import importlib.util
import os
import re
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p80lib = _load("p80lib", os.path.join(ROOT, "logs/p80/p80lib.py"))

#: The rows this phase's own instrumentation adds, i.e. what `--same` drops
#: besides P84/P86/P95's sealed set. `[carry]`/`[regrip]` are the phase's read of
#: the leg; the sealed set covers the earlier phases' instruments.
SEALED = (
    "[fruit] [carry]",
    "[fruit] [regrip]",
    "[fruit] [diag] carry-assist",
    "[fruit] [biarm] scheduler:",
    "[fruit] [biarm] left: park",
    "[fruit] [biarm] right: park",
    # P100's park clock row (its own report drops it, and this phase's tree
    # carries the shipped 90/120 pair, so it is a constant row, not a behaviour)
    "[fruit] [biarm] park profile:",
    "[fruit] [ready]",
    "[task]   place trace",
)

CARRY = re.compile(
    r"\[fruit\] \[carry\] (?P<arm>\w+) (?P<leg>\w+): ticks=(?P<tick>\d+)/(?P<tot>\d+) "
    r"clean_slip_max=(?P<slip>[+\-\d.]+)mm .*?"
    r"force_min=(?P<fmin>[+\-\d.]+)N .*?dia=(?P<dia>[\d.]+) "
    r"sep_max=(?P<sep_max>[+\-\d.]+)(?:@t\d+)? "
    r"gap@sep_max=(?P<gap_max>[+\-\d.]+|n/a) "
    r"sep_min=(?P<sep_min>[+\-\d.]+|n/a) fmax=(?P<fmax>[+\-\d.]+)N")
REGRIP = re.compile(
    r"\[fruit\] \[regrip\] (?P<arm>\w+) (?P<leg>\w+) t=(?P<tick>\d+)/(?P<tot>\d+) "
    r"dc=(?P<dc>[\d.]+)mm slip=(?P<slip>[\d.]+)mm correction=(?P<corr>[\d.]+)mm "
    r"seat_f=(?P<sf>[\d.]+)N seat_edge=(?P<se>[+\-\d.]+)mm seat_frac=(?P<sfrac>[\d.]+)")
REGRIP_END = re.compile(
    r"\[fruit\] \[regrip\] (?P<arm>\w+) (?P<leg>\w+) done fires=(?P<fires>\d+) "
    r"first_t=(?P<tick>\d+)/(?P<tot>\d+) first_dc=(?P<dc>[\d.]+)mm "
    r"first_correction=(?P<corr>[\d.]+)mm clean_slip_max=(?P<slip>[+\-\d.]+)mm "
    r"force_min=(?P<fmin>[+\-\d.]+)N")
RUN_PICK = re.compile(
    r"\[fruit\] \[run\] attempt (?P<n>\d+) \((?P<arm>\w+)\): picking (?P<fruit>\w+) "
    r"grade (?P<grade>\w+).*sim=(?P<t0>[\d.]+)-(?P<t1>[\d.]+)s")
RUN_OUT = re.compile(
    r"\[fruit\] \[run\] attempt (?P<n>\d+) \((?P<arm>\w+)\): grasped=(?P<g>True|False) "
    r"placed=(?P<p>True|False) lift=(?P<lift>[+\-\d.]+) m force=(?P<f>[\d.]+) N "
    r"sim=(?P<sim>[\d.]+)s notes=(?P<notes>\[.*\])")
BIARM_RESULT = re.compile(
    r"\[fruit\] \[biarm\] result (?P<arm>\w+) index=\d+ (?P<fruit>\w+) "
    r"grasped=(?P<g>True|False) placed=(?P<p>True|False)")

#: P74's "the payload has left" threshold, i.e. the boundary between a **held**
#: leg and an escape on this cell. A leg under it that tripped is a false
#: positive; a leg over it that did not trip is a missed detection.
ESCAPE_MM = 100.0

#: The two-line session's **P10-C carry monitor** confirm gate [mm]
#: (`_resolve_carry_monitor_knobs`: `FRUIT_CARRY_MONITOR_CONFIRM_MM` = 8.0 when the
#: env is unset in a two-line session). It is armed on **both** arms of this A/B,
#: and it is a bound on what a re-grip can buy: a leg whose `clean_slip_max` is at
#: or over this number marks the attempt for the monitor's leg-boundary skip, so
#: the place leg does not run and the attempt cannot place however well the pinch
#: is held. Recording it is what separates "the reaction did not hold the
#: payload" from "it held it and the attempt was truncated anyway".
MONITOR_CONFIRM_MM = 8.0


def read(path: str) -> dict:
    carry, fired, ended, picks, outs = [], [], [], [], {}
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for lineno, line in enumerate(fh):
            m = CARRY.search(line)
            if m:
                d = m.groupdict()
                carry.append({
                    "line": lineno,
                    "arm": d["arm"], "leg": d["leg"],
                    "tick": int(d["tick"]), "tot": int(d["tot"]),
                    "slip": float(d["slip"]), "fmin": float(d["fmin"]),
                    "dia": float(d["dia"]), "sep_max": float(d["sep_max"]),
                    "gap_max": float(d["gap_max"].replace("n/a", "nan")),
                    "sep_min": float(d["sep_min"].replace("n/a", "nan")),
                    "fmax": float(d["fmax"]),
                })
                continue
            m = REGRIP.search(line)
            if m:
                d = m.groupdict()
                fired.append({
                    "line": lineno,
                    "arm": d["arm"], "leg": d["leg"], "tick": int(d["tick"]),
                    "tot": int(d["tot"]), "dc": float(d["dc"]),
                    "slip": float(d["slip"]), "corr": float(d["corr"]),
                    "seat_f": float(d["sf"]), "seat_edge": float(d["se"]),
                    "seat_frac": float(d["sfrac"]),
                })
                continue
            m = REGRIP_END.search(line)
            if m:
                d = m.groupdict()
                ended.append({
                    "line": lineno,
                    "arm": d["arm"], "leg": d["leg"],
                    "fires": int(d["fires"]), "tick": int(d["tick"]),
                    "tot": int(d["tot"]), "dc": float(d["dc"]),
                    "corr": float(d["corr"]), "slip": float(d["slip"]),
                    "fmin": float(d["fmin"]),
                })
                continue
            m = RUN_PICK.search(line)
            if m:
                d = m.groupdict()
                picks.append({"n": int(d["n"]), "arm": d["arm"],
                              "fruit": d["fruit"], "grade": d["grade"],
                              "t0": float(d["t0"]), "t1": float(d["t1"])})
                continue
            m = RUN_OUT.search(line)
            if m:
                d = m.groupdict()
                outs[int(d["n"])] = {
                    "arm": d["arm"], "grasped": d["g"] == "True",
                    "placed": d["p"] == "True", "lift": float(d["lift"]),
                    "force": float(d["f"]), "span": float(d["sim"]),
                    "notes": d["notes"],
                }
    # the fruit/grade/window live on the `[run] ... picking` row, the outcome on
    # the `[run] ... grasped=` row; both carry the attempt index, so join there.
    for pick in picks:
        row = outs.setdefault(pick["n"], {})
        row.update({"arm": pick["arm"], "fruit": pick["fruit"],
                    "grade": pick["grade"], "t0": pick["t0"], "t1": pick["t1"]})
    return {"path": path, "carry": carry, "fired": fired, "ended": ended,
            "picks": picks, "outs": outs}


def join_ledger(cell: dict) -> tuple[list[dict], list[str]]:
    """Map each carry leg to its attempt (P102's join), then to its fire/outcome."""
    legs = []
    order = {"left": 0, "right": 0}
    problems = []
    for row in cell["carry"]:
        row = dict(row)
        if row["leg"] == "grasp_lift":
            order[row["arm"]] += 1
            row["attempt_ord"] = order[row["arm"]]
        else:
            row["attempt_ord"] = order[row["arm"]]
        legs.append(row)
    # the `[run]` rows in order, per side: the k-th for a side is that side's
    # k-th attempt (checked, not assumed)
    by_arm = {}
    for n in sorted(cell["outs"]):
        by_arm.setdefault(cell["outs"][n]["arm"], []).append(n)
    for arm, ns in by_arm.items():
        if len(ns) != order.get(arm, 0):
            problems.append(
                f"{os.path.basename(cell['path'])}: {arm} has {order.get(arm, 0)} "
                f"grasp_lift legs but {len(ns)} `[run]` rows")
    for row in legs:
        ns = by_arm.get(row["arm"], [])
        k = row["attempt_ord"]
        row["attempt"] = ns[k - 1] if 0 < k <= len(ns) else None
        row["outcome"] = cell["outs"].get(row["attempt"]) if row["attempt"] is not None else None
        row["fire"] = None
        row["end"] = None
    # **The fire's leg**: a `[regrip]` row prints *inside* its leg, and the leg's
    # own `[carry]` row prints at its end, so the fire belongs to the first
    # `[carry]` row of the same `(arm, leg)` **after** it in the stream. That is
    # stream-position matching, not counting: the two arms' legs overlap, so a
    # count-based join would hand a fire to the other arm's leg.
    for fire in cell["fired"]:
        cand = [r for r in legs
                if r["line"] > fire["line"]
                and r["arm"] == fire["arm"] and r["leg"] == fire["leg"]]
        if cand:
            first = min(cand, key=lambda r: r["line"])
            if first["fire"] is None:
                first["fire"] = fire
            else:
                problems.append(
                    f"{os.path.basename(cell['path'])}: two fires for one leg "
                    f"{fire['arm']}/{fire['leg']}@{fire['tick']}")
        else:
            problems.append(
                f"{os.path.basename(cell['path'])}: fire with no leg "
                f"{fire['arm']}/{fire['leg']}@{fire['tick']}")
    for end in cell["ended"]:
        cand = [r for r in legs
                if r["line"] > end["line"]
                and r["arm"] == end["arm"] and r["leg"] == end["leg"]]
        if cand:
            min(cand, key=lambda r: r["line"])["end"] = end
    return legs, problems


def fmt(v, nd=2):
    return "-" if v is None else f"{v:.{nd}f}"


def ledger(paths: list[str]) -> int:
    print("=" * 118)
    print("P103 - the trigger ledger (one row per leg that re-seated)")
    print("=" * 118)
    rc = 0
    for path in paths:
        cell = read(path)
        legs, problems = join_ledger(cell)
        for p in problems:
            print(f"  JOIN-PROBLEM {p}")
            rc = 1
        fires = [r for r in legs if r["fire"]]
        print(f"\n## {os.path.basename(path)}  carry legs {len(legs)}  "
              f"re-seated legs {len(fires)}  "
              f"re-seat ticks {sum((r['end'] or {}).get('fires', 0) for r in fires)}")
        if fires:
            print("  arm   leg         attempt fruit       t/tot    dc_mm corr_mm "
                  "seat_f seat_edge seat_frac fires slip_max outcome")
            for r in fires:
                end = r["end"] or {}
                out = r["outcome"] or {}
                print(
                    f"  {r['arm']:5s} {r['leg']:11s} {str(r['attempt']):>7s} "
                    f"{out.get('fruit', '-'):10s} "
                    f"{r['fire']['tick']:>4d}/{r['fire']['tot']:<4d} "
                    f"{r['fire']['dc']:6.2f} {r['fire']['corr']:7.2f} "
                    f"{r['fire']['seat_f']:6.2f} {r['fire']['seat_edge']:+8.1f} "
                    f"{r['fire']['seat_frac']:9.3f} {end.get('fires', 0):5d} "
                    f"{r['slip']:8.1f} "
                    f"{'PLACED' if out.get('placed') else ('cnp' if out.get('grasped') else 'no-grasp')}")
        # the conversions
        placed = [r for r in fires if (r["outcome"] or {}).get("placed")]
        print(f"  -> conversions: {len(placed)}/{len(fires)} re-seated legs ended placed")
        under = [r for r in fires if r["slip"] < MONITOR_CONFIRM_MM]
        slips = ", ".join(f"{r['slip']:.1f}" for r in fires)
        print(f"  -> under the P10-C monitor's {MONITOR_CONFIRM_MM:.1f} mm confirm "
              f"gate (a place leg then runs): {len(under)}/{len(fires)}"
              + (f"   clean_slip_max on re-seated legs: {slips}" if fires else ""))
        # the false positives: a leg that tripped and stayed held (slip < 100 mm)
        fp = [r for r in fires if r["slip"] < ESCAPE_MM]
        print(f"  -> false positives (tripped, payload never left, slip < "
              f"{ESCAPE_MM:.0f} mm): {len(fp)}"
              + ("" if not fp else f" - placed {sum(1 for r in fp if (r['outcome'] or {}).get('placed'))}/{len(fp)}"))
        # the missed detections: an escape that never tripped. P76 A3's class
        # rule applies - an escape needs a **pinch** (`fmax > 0`), so a
        # `never_held` leg (the hand closed on air; its `clean_slip` is the arm's
        # own motion) is not a missed detection, it is unreachable by any pad.
        esc = [r for r in legs if r["slip"] > ESCAPE_MM and r["fmax"] > 0.0]
        nev = [r for r in legs if r["slip"] > ESCAPE_MM and r["fmax"] == 0.0]
        print(f"  -> never-held legs with slip > {ESCAPE_MM:.0f} mm (no pinch, "
              f"unreachable by any pad): {len(nev)}")
        missed = [r for r in esc if not r["fire"]]
        print(f"  -> escapes (slip > {ESCAPE_MM:.0f} mm) {len(esc)}, of which "
              f"never tripped {len(missed)}")
        for r in missed:
            print(f"     MISSED {r['arm']} {r['leg']} attempt {r['attempt']} "
                  f"slip={r['slip']:.1f}mm fmin={r['fmin']:.2f}N "
                  f"fmax={r['fmax']:.2f}N sep_max={r['sep_max']:.1f} "
                  f"gap@sep_max={r['gap_max']:.1f}")
    return rc


def conv(pairs: list[tuple[str, str]]) -> int:
    """The **conversions**: every leg the treatment re-seated, beside the same
    attempt index on the same seed's control.

    The control column is a **descriptor, not a pairing**: the branches diverge
    as soon as the action moves a command, so the same index is the same
    *instance* only while the streams still agree (the fruit and the grade). The
    column says which, per row.
    """
    print("=" * 118)
    print("P103 - the conversions (treatment re-seated legs vs the same-index control)")
    print("=" * 118)
    tot = placed = 0
    for cpath, tpath in pairs:
        cc, tc = read(cpath), read(tpath)
        cl, _ = join_ledger(cc)
        tl, probs = join_ledger(tc)
        for p in probs:
            print(f"  JOIN-PROBLEM {p}")
        by_c = {r["attempt"]: r for r in cl if r["leg"] == "grasp_lift"}
        fires = [r for r in tl if r["fire"]]
        print(f"\n## seed {_names(tpath)[1:]}  ({_names(cpath)} vs {_names(tpath)})  "
              f"re-seated legs {len(fires)}")
        if not fires:
            continue
        print("  attempt  arm   leg         fruit(T)  placed(T)  fruit(C)  placed(C)  "
              "same instance  first_dc  fires")
        for r in fires:
            out = r["outcome"] or {}
            c = by_c.get(r["attempt"]) or {}
            cout = c.get("outcome") or {}
            same = (out.get("fruit") == cout.get("fruit"))
            tot += 1
            placed += 1 if out.get("placed") else 0
            print(f"  {str(r['attempt']):>7s}  {r['arm']:5s} {r['leg']:11s} "
                  f"{out.get('fruit', '-'):9s} "
                  f"{'PLACED' if out.get('placed') else 'fail':>9s}  "
                  f"{cout.get('fruit', '-'):9s} "
                  f"{('PLACED' if cout.get('placed') else 'fail'):>9s}  "
                  f"{'yes' if same else 'no':>13s}  "
                  f"{r['fire']['dc']:8.2f} "
                  f"{(r['end'] or {}).get('fires', 0):5d}")
    print(f"\n  -> {placed}/{tot} re-seated legs ended placed")
    return 0


def _names(path: str) -> str:
    return os.path.basename(path).replace(".log", "")


def ab(pairs: list[tuple[str, str]]) -> int:
    print("=" * 118)
    print("P103 - the A/B on the survey's P2/P3  (every rate/interval/wall is p80lib's)")
    print("=" * 118)
    print(f"\n{'cell':6s} {'seed':>5s} {'arm':>3s} {'placed':>7s} {'cnp':>4s} "
          f"{'nograsp':>8s} {'fmin0':>6s} {'s/att':>6s} {'int_mean':>9s} "
          f"{'win':>6s} {'batch':>6s} {'wall/pick':>10s} {'pl/min_wall':>11s}")
    rows = {}
    for cpath, tpath in pairs:
        seed = re.search(r"(\d+)$", _names(cpath))
        seed = seed.group(1) if seed else "?"
        for arm, path in (("C", cpath), ("T", tpath)):
            m = p80lib.metrics(path)
            cell = read(path)
            legs, _ = join_ledger(cell)
            fmin0 = sum(1 for r in legs if r["fmin"] == 0.0)
            st_ = m["stats"]
            wall_per = st_.get("wall_per_pick")
            pl_min = (60.0 / wall_per) if wall_per else None
            rows[(seed, arm)] = {
                "m": m, "fmin0": fmin0, "placed": m["placed"],
                "cnp": m["classes"].get("carried-not-placed", 0),
                "nog": m["classes"].get("never-grasped", 0),
                "att": m["attempts"],
            }
            print(f"{_names(path):6s} {seed:>5s} {arm:>3s} "
                  f"{m['placed']:3d}/{m['attempts']:<3d} "
                  f"{m['classes'].get('carried-not-placed', 0):4d} "
                  f"{m['classes'].get('never-grasped', 0):8d} {fmin0:6d} "
                  f"{st_.get('per_attempt') or 0:6.2f} "
                  f"{fmt(m['pooled']['mean']):>9s} "
                  f"{fmt(m['window_rate']):>6s} {fmt(m['batch_rate']):>6s} "
                  f"{fmt(wall_per):>10s} {fmt(pl_min):>11s}")
    # pooled per arm
    print("\n  pooled (all seeds)")
    for arm in ("C", "T"):
        keys = [k for k in rows if k[1] == arm]
        att = sum(rows[k]["att"] for k in keys)
        placed = sum(rows[k]["placed"] for k in keys)
        cnp = sum(rows[k]["cnp"] for k in keys)
        nog = sum(rows[k]["nog"] for k in keys)
        fmin0 = sum(rows[k]["fmin0"] for k in keys)
        iv = [rows[k]["m"]["pooled"]["mean"] for k in keys]
        win = [rows[k]["m"]["window_rate"] for k in keys]
        bat = [rows[k]["m"]["batch_rate"] for k in keys]
        print(f"  {arm}: placed {placed}/{att} = {100.0 * placed / att:.1f}%  "
              f"cnp {cnp}  never-grasped {nog}  force_min==0 legs {fmin0}  "
              f"interval mean-of-seeds {st.fmean(iv):.2f}s  "
              f"window {st.fmean(win):.2f}  batch {st.fmean(bat):.2f} placed/min")
    # the survey's two clauses
    seeds = sorted({k[0] for k in rows})
    c_pl = sum(rows[(s, 'C')]['placed'] for s in seeds)
    t_pl = sum(rows[(s, 'T')]['placed'] for s in seeds)
    c_att = sum(rows[(s, 'C')]['att'] for s in seeds)
    t_att = sum(rows[(s, 'T')]['att'] for s in seeds)
    c_cnp = sum(rows[(s, 'C')]['cnp'] for s in seeds)
    t_cnp = sum(rows[(s, 'T')]['cnp'] for s in seeds)
    print("\n  P2a (the survey's literal form, seeds 5+6 only):")
    ks = [s for s in seeds if s in ("5", "6")]
    if ks:
        cp = sum(rows[(s, 'C')]['placed'] for s in ks)
        tp = sum(rows[(s, 'T')]['placed'] for s in ks)
        cc = sum(rows[(s, 'C')]['cnp'] for s in ks)
        tc = sum(rows[(s, 'T')]['cnp'] for s in ks)
        ca = sum(rows[(s, 'C')]['att'] for s in ks)
        ta = sum(rows[(s, 'T')]['att'] for s in ks)
        print(f"    cnp {cc} -> {tc}  (bar: <= 4 of 40)      "
              f"placed {cp}/{ca} -> {tp}/{ta}  "
              f"({100.0 * tp / ta - 100.0 * cp / ca:+.1f} points, bar +8)")
    print("  P2b (pooled, all seeds):")
    dp = 100.0 * t_pl / t_att - 100.0 * c_pl / c_att
    print(f"    cnp {c_cnp} -> {t_cnp} ({100.0 * (t_cnp - c_cnp) / max(c_cnp, 1):+.0f} %, "
          f"bar <= -30 %)   placed {c_pl}/{c_att} -> {t_pl}/{t_att} ({dp:+.1f} points, bar +8)")
    print("  P3 (the price):")
    iv_c = st.fmean([rows[(s, 'C')]['m']['pooled']['mean'] for s in seeds])
    iv_t = st.fmean([rows[(s, 'T')]['m']['pooled']['mean'] for s in seeds])
    print(f"    interval pooled {iv_c:.2f} -> {iv_t:.2f} s "
          f"({100.0 * (iv_t - iv_c) / iv_c:+.1f} %, bar <= +5 %)")
    for s in seeds:
        c = rows[(s, 'C')]['m']
        t = rows[(s, 'T')]['m']
        print(f"    seed {s:>3s}: {c['pooled']['mean']:.2f} -> {t['pooled']['mean']:.2f} s "
              f"({100.0 * (t['pooled']['mean'] - c['pooled']['mean']) / c['pooled']['mean']:+.1f} %)  "
              f"window {fmt(c['window_rate'])} -> {fmt(t['window_rate'])}  "
              f"batch {fmt(c['batch_rate'])} -> {fmt(t['batch_rate'])}")
        for arm in ("left", "right"):
            ci = c["per_arm"].get(arm, {}).get("interval_mean")
            ti = t["per_arm"].get(arm, {}).get("interval_mean")
            if ci and ti:
                print(f"      {arm:5s} interval {ci:6.2f} -> {ti:6.2f} s "
                      f"({100.0 * (ti - ci) / ci:+.1f} %)")
    # G5: the reason keys
    print("\n  G5 - the failure-reason keys (treatment must be a subset of control)")
    for s in seeds:
        cr = set(rows[(s, 'C')]['m']['reasons'])
        tr = set(rows[(s, 'T')]['m']['reasons'])
        new = sorted(tr - cr)
        print(f"    seed {s:>3s}: control {sorted(cr)}")
        print(f"             treatment {sorted(tr)}"
              + (f"   NEW: {new}" if new else "   (no new key)"))
    # G6: accounting
    print("\n  G6 - accounting (placed + cnp + never-grasped == attempts?)")
    for (s, arm), r in sorted(rows.items()):
        cls = r["m"]["classes"]
        tot = sum(cls.values())
        ok = tot == r["att"]
        print(f"    {s:>3s} {arm}: attempts {r['att']}  classes {cls}  "
              + ("OK" if ok else "MISMATCH"))
    return 0


def same(a_path: str, b_path: str) -> int:
    """Sealed line-for-line comparison of the `[fruit]` stream."""
    def stream(path):
        out = []
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if not line.startswith("[fruit]"):
                    continue
                if any(line.startswith(tag) for tag in SEALED):
                    continue
                out.append(line.rstrip("\n"))
        return out

    a, b = stream(a_path), stream(b_path)
    if a == b:
        print(f"SAME: {len(a)}/{len(a)} `[fruit]` lines identical with the sealed "
              f"rows dropped\n      {a_path}\n      {b_path}")
        return 0
    n = min(len(a), len(b))
    first = next((i for i in range(n) if a[i] != b[i]), n)
    print(f"DIFFERS: {len(a)} vs {len(b)} lines, first difference at {first}")
    for i in range(max(0, first - 2), min(n, first + 4)):
        print(f"  A[{i}] {a[i][:160]}")
        print(f"  B[{i}] {b[i][:160]}")
    return 1


PLACE_TRACE = re.compile(
    r"\[task\]   place trace (?P<arm>\w+): release_bottom=(?P<bottom>[+\-\d.]+)mm "
    r"impact=(?P<impact>[+\-\d.]+)m/s bounce=(?P<bounce>[+\-\d.]+)mm .*?"
    r"on_belt=(?P<on_belt>True|False)")

CHECK_PATTERNS = (CARRY, REGRIP, REGRIP_END)


def landing(paths: list[str]) -> int:
    """G3: every release that still had the payload lands on the belt.

    `release_bottom` is the payload's lowest point above the output belt top at
    the release. A row with `release_bottom < 0` never had the payload by then
    (the upstream-lost class P86/P87 report separately, the `-184 mm` rows), so
    it is counted apart and not gated.
    """
    rc = 0
    for path in paths:
        on = off = lost = 0
        worst = None
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                m = PLACE_TRACE.search(line)
                if not m:
                    continue
                bottom = float(m.group("bottom"))
                if bottom < 0.0:
                    lost += 1
                    continue
                if m.group("on_belt") == "True":
                    on += 1
                else:
                    off += 1
                    worst = (bottom, m.group("impact"), line.strip()[:120])
        total = on + off
        ok = off == 0
        rc = rc or (0 if ok else 1)
        print(f"  {os.path.basename(path):10s} payload-present releases {total:3d}: "
              f"on_belt {on:3d}, off {off:3d}"
              f"   (upstream-lost rows: {lost})"
              + ("" if ok else f"   OFF-BELT: {worst}"))
    return rc


def check(paths: list[str]) -> int:
    bad = 0
    for path in paths:
        carry = fired = ended = 0
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if "[carry]" in line and "[fruit]" in line:
                    carry += 1
                    if not CARRY.search(line):
                        print(f"BAD carry row: {line[:200]}")
                        bad += 1
                elif "[regrip]" in line and " done " not in line:
                    fired += 1
                    if not REGRIP.search(line):
                        print(f"BAD regrip row: {line[:200]}")
                        bad += 1
                elif "[regrip]" in line:
                    ended += 1
                    if not REGRIP_END.search(line):
                        print(f"BAD regrip-done row: {line[:200]}")
                        bad += 1
        print(f"  {os.path.basename(path):10s} carry={carry:3d} regrip={fired:3d} "
              f"regrip-done={ended:3d}")
        if fired and fired != ended:
            print(f"  WARN {path}: {fired} first-fire rows vs {ended} done rows "
                  f"(a fire whose leg never reached the row)")
    print("OK" if not bad else f"{bad} malformed rows")
    return 0 if not bad else 1


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    if cmd == "--same":
        return same(argv[1], argv[2])
    if cmd == "--check":
        return check(argv[1:])
    if cmd == "--landing":
        return landing(argv[1:])
    if cmd == "ledge":
        return ledger(argv[1:])
    if cmd == "conv":
        paths = argv[1:]
        if len(paths) < 2:
            print("conv needs pairs: C T [C T ...]")
            return 2
        return conv([(paths[i], paths[i + 1]) for i in range(0, len(paths), 2)])
    if cmd == "ab":
        paths = argv[1:]
        if len(paths) < 2:
            print("ab needs pairs: C T [C T ...]")
            return 2
        pairs = [(paths[i], paths[i + 1]) for i in range(0, len(paths), 2)]
        return ab(pairs)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
