"""P92 phase 1: the failure census of the shipped two-line cell, from the records.

    python3 logs/p92/census.py [--json]

Read-only: opens the same-tree logs, prints a table. No simulator.

Classification is per **attempt** and by that attempt's own evidence:

  success           placed=True.
  cnp               the payload was in the pinch and left it - the closed
                    loaded-slide class (`logs/p42/SIM_LIMIT.md`). Evidence on a
                    `grasp_lift`/`place*` leg: a `loss_row` (the tracker's onset),
                    `force_min == 0.00 N` after a real pinch (`fmax > 0`), a
                    `clean_slip_max > 100 mm`, or `sep_max` at the ~98 mm open
                    stop. Split by the onset leg (lift vs place*), because P75
                    measured both sites.
  never_held        the pads closed on air: the leg's `contacts@onset == 0`, its
                    `force@onset == 0.00 N` and its `fmax == 0.00 N`, i.e. no
                    pinch ever existed (P76 A3's exclusion, read positively).
  fell_off          the note names it (`fruit fell off the line`) - lost
                    upstream of the grasp.
  diverted          the *fruit* retired after 2 failed attempts (the reject
                    chute). Book-keeping over attempts, counted separately: it
                    is not a distinct attempt class.
  starved           a poll with no eligible fruit (`no eligible fruit; station
                    released`). Also a slot-level event, counted per attempt
                    window, not a failure class by itself.
  other             anything else, printed with its own row so it can be read.

The attempt boundary is the `[task] target ... with <arm> arm` line (attempt
start) and the `[biarm] result <arm> index=...` line (attempt end); the `[carry]`
rows between them that name that arm are the attempt's legs. The two-line arms
run concurrently, so the per-arm buffer is what associates them.

Duplicates: the same scenario was re-run for later phases' *controls* and those
replays are byte-identical by that phase's own proof. `--dedupe` (default) keeps
one log per (scenario, seed) cell and reports the replay count; `--all` pools
every row. The dedupe set is the shipped-cell census; the pre-P87 logs are a
different clock and are kept in their own block, never mixed.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

TARGET = re.compile(
    r"\[fruit\] \[task\] target (?P<fruit>\w+) \(grade (?P<grade>\w+), "
    r"(?P<dia>[\d.]+) cm\) with (?P<arm>left|right) arm"
)
RESULT = re.compile(
    r"\[fruit\] \[biarm\] result (?P<arm>left|right) index=(?P<index>\d+) "
    r"(?P<fruit>\w+) grasped=(?P<grasped>True|False) placed=(?P<placed>True|False) "
    r"lift=(?P<lift>[+\-\d.]+) force=(?P<force>[\d.]+) sim=(?P<span>[\d.]+)s "
    r"notes=(?P<notes>\[.*?\])"
)
CARRY = re.compile(
    r"\[fruit\] \[carry\] (?P<arm>left|right) (?P<leg>\w+): (?P<body>.*)$"
)
DIVERT = re.compile(
    r"\[fruit\] \[task\] diverting (?P<fruit>\w+) \(index (?P<index>\d+)\) "
    r"after (?P<n>\d+) failed attempts"
)
NOELIG = re.compile(r"\[fruit\] \[biarm\] (?P<arm>left|right): no eligible fruit")
ACQ = re.compile(r"\[fruit\] \[biarm\] (?P<arm>left|right): station acquired at t=")
WAITX = re.compile(r"\[fruit\] \[task\]\s+wait step=\d+ .*?fruit_x=(?P<x>[+\-][\d.]+)")
HANDOVER = re.compile(r"\[fruit\] \[task\]\s+intercept handover: .*?queue=(?P<q>\d+)")
STATS = re.compile(
    r"\[fruit\] \[stats\] attempts=(?P<att>\d+) successes=(?P<ok>\d+) "
    r"diverted=(?P<div>\d+) success_rate=(?P<rate>\d+)%"
)

#: the shipped-cell logs (P87's release trim onward) and the pre-P87 clock.
SHIPPED = {
    "p87/T5": "logs/p87/T5.log",
    "p87/T6": "logs/p87/T6.log",
    "p88/C5": "logs/p88/C5.log",
    "p88/C6": "logs/p88/C6.log",
    "p88/N5": "logs/p88/N5.log",
    "p89/C5": "logs/p89/C5.log",
    "p89/C6": "logs/p89/C6.log",
    "p91/C5": "logs/p91/C5.log",
    "p91/C6": "logs/p91/C6.log",
    "p91/N5": "logs/p91/N5.log",
}
PRE = {
    "p80/T20": "logs/p80/T20.log",
    "p80/T6": "logs/p80/T6.log",
    "p84/D5": "logs/p84/D5.log",
    "p84/D6": "logs/p84/D6.log",
}


def num(body: str, key: str):
    m = re.search(rf"(?:^| ){re.escape(key)}=([+\-]?[\d.]+)", body)
    return float(m.group(1)) if m else None


def parse_leg(body: str) -> dict:
    return {
        "clean_slip": num(body, "clean_slip_max"),
        "force_min": num(body, "force_min"),
        "fmax": num(body, "fmax"),
        "sep_max": num(body, "sep_max"),
        "sep_end": num(body, "sep_end"),
        "dia": num(body, "dia"),
        "loss_row": num(body, "loss_row"),
        "onset_row": num(body, "onset_row"),
        "contacts_onset": num(body, "contacts@onset"),
        "force_onset": num(body, "force@onset"),
        "gap_start": num(body, "gap_start"),
        "ticks": num(body, "ticks"),
    }


def classify(rec: dict) -> tuple[str, str, dict]:
    """-> (class, detail, evidence). `rec` carries the result + its legs."""
    legs = rec["legs"]
    lift = legs.get("grasp_lift")
    if rec["placed"]:
        return "success", "", {}
    notes = rec["notes"]
    if "fell off the line" in notes:
        return "fell_off", "", {}
    # evidence of a pinch that then failed (loaded slide)
    ev = {}
    slid = [lg for lg in legs.values() if lg["loss_row"] is not None]
    pinned = [lg for lg in legs.values() if (lg["fmax"] or 0) > 0]
    if rec["grasped"]:
        site = "lift" if (lift and lift["loss_row"] is not None) else "place"
        if slide := [lg for lg in legs.values() if lg["loss_row"] is not None]:
            pass
        lg = slide[0] if slide else (lift or {})
        return "cnp", site, {
            "slip": lg.get("clean_slip"),
            "force_min": lg.get("force_min"),
            "sep_max": lg.get("sep_max"),
            "dia": lg.get("dia"),
        }
    # not grasped: was there ever a pinch?
    if lift is not None:
        if lift["contacts_onset"] == 0 and (lift["fmax"] or 0) == 0.0:
            return "never_held", "", {
                "sep_end": lift["sep_end"], "dia": lift["dia"],
                "gap_start": lift["gap_start"],
            }
        if (lift["fmax"] or 0) > 0:
            # a pinch existed and the payload left it -> the closed class
            site = "lift" if lift["loss_row"] is not None else "place"
            return "cnp", site, {
                "slip": lift["clean_slip"],
                "force_min": lift["force_min"],
                "sep_max": lift["sep_max"],
                "dia": lift["dia"],
            }
        return "never_held", "", {
            "sep_end": lift["sep_end"], "dia": lift["dia"],
            "gap_start": lift["gap_start"], "note": "no pinch, no fmax",
        }
    return "other", "", {"note": ",".join(notes) or "no legs"}


def parse(path: str) -> dict:
    with open(path, "r", errors="replace") as fh:
        lines = fh.readlines()
    attempts: list[dict] = []
    legs: dict[str, dict] = {"left": {}, "right": {}}
    cur: dict[str, dict | None] = {"left": None, "right": None}
    stats = None
    noelig = {"left": 0, "right": 0}
    acquired = {"left": 0, "right": 0}
    diverts: list[dict] = []
    xs: list[float] = []
    queue: list[int] = []
    for ln in lines:
        if m := TARGET.search(ln):
            arm = m.group("arm")
            cur[arm] = {
                "fruit": m.group("fruit"),
                "grade": m.group("grade"),
                "dia_cm": float(m.group("dia")),
                "arm": arm,
                "legs": {},
                "x": None,
                "queue": None,
            }
            legs[arm] = cur[arm]["legs"]
            continue
        if m := WAITX.search(ln):
            for arm in ("left", "right"):
                if cur[arm] is not None and cur[arm]["x"] is None:
                    cur[arm]["x"] = float(m.group("x"))
            continue
        if m := HANDOVER.search(ln):
            for arm in ("left", "right"):
                if cur[arm] is not None and cur[arm]["queue"] is None:
                    cur[arm]["queue"] = int(m.group("q"))
            continue
        if m := CARRY.search(ln):
            arm = m.group("arm")
            if cur[arm] is not None:
                cur[arm]["legs"][m.group("leg")] = parse_leg(m.group("body"))
            continue
        if m := RESULT.search(ln):
            arm = m.group("arm")
            rec = cur[arm] or {
                "fruit": m.group("fruit"), "grade": "?", "dia_cm": None,
                "arm": arm, "legs": {}, "x": None, "queue": None,
            }
            rec.update(
                index=int(m.group("index")),
                grasped=m.group("grasped") == "True",
                placed=m.group("placed") == "True",
                lift=float(m.group("lift")),
                force=float(m.group("force")),
                span=float(m.group("span")),
                notes=m.group("notes"),
            )
            cls, detail, ev = classify(rec)
            rec.update(cls=cls, detail=detail, ev=ev, log=os.path.basename(path))
            attempts.append(rec)
            cur[arm] = None
            continue
        if m := NOELIG.search(ln):
            noelig[m.group("arm")] += 1
            continue
        if m := ACQ.search(ln):
            acquired[m.group("arm")] += 1
            continue
        if m := DIVERT.search(ln):
            diverts.append({"fruit": m.group("fruit"), "index": int(m.group("index")),
                            "n": int(m.group("n"))})
            continue
        if m := STATS.search(ln):
            stats = {"attempts": int(m.group("att")), "successes": int(m.group("ok")),
                     "diverted": int(m.group("div"))}
            continue
    for rec in attempts:
        xs.append(rec["x"])
        if rec["queue"] is not None:
            queue.append(rec["queue"])
    return {
        "path": path,
        "attempts": attempts,
        "stats": stats,
        "noelig": noelig,
        "acq": acquired,
        "diverts": diverts,
        "queue": queue,
    }


def fmt(v, nd=2):
    return "-" if v is None else f"{v:.{nd}f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true",
                    help="pool every log, including the byte-identical replays")
    ap.add_argument("--pre", action="store_true", help="the pre-P87 block only")
    args = ap.parse_args()
    table = PRE if args.pre else SHIPPED
    logs = {k: parse(os.path.join(ROOT, v)) for k, v in table.items()}

    # ---- per-log rows ---------------------------------------------------- #
    print("=" * 100)
    print("P92 CENSUS - the shipped two-line cell" if not args.pre
          else "P92 CENSUS - the pre-P87 clock (2.35 s release), separate block")
    print("=" * 100)
    print(f"{'log':10s} {'att':>3s} {'ok':>3s} {'cnp':>3s} {'never':>5s} "
          f"{'fell':>4s} {'other':>5s} {'cnp-l':>5s} {'cnp-p':>5s} {'div':>3s} "
          f"{'starve':>6s} {'acq':>3s}")
    pooled: list[dict] = []
    for tag, d in logs.items():
        cls = [a["cls"] for a in d["attempts"]]
        n = lambda c: cls.count(c)
        site = lambda s: sum(1 for a in d["attempts"]
                             if a["cls"] == "cnp" and a["detail"] == s)
        print(f"{tag:10s} {len(cls):3d} {n('success'):3d} {n('cnp'):3d} "
              f"{n('never_held'):5d} {n('fell_off'):4d} {n('other'):5d} "
              f"{site('lift'):5d} {site('place'):5d} {len(d['diverts']):3d} "
              f"{d['noelig']['left'] + d['noelig']['right']:6d} "
              f"{d['acq']['left'] + d['acq']['right']:3d}")
        pooled.extend(d["attempts"])

    # ---- the deduped (distinct scenario) census -------------------------- #
    if args.pre:
        cells = [
            ("seed 5", "p84/D5", "p80/T20 (no carry diag: 4 unclassifiable rows)"),
            ("seed 6", "p84/D6", "p80/T6 (no carry diag: 5 unclassifiable rows)"),
        ]
    else:
        cells = [
            ("seed 5", "p87/T5", "p88/C5,p89/C5,p91/C5,p91/N5,p88/N5"),
            ("seed 6", "p87/T6", "p88/C6,p89/C6,p91/C6"),
        ]
    print()
    print("-" * 100)
    print("DISTINCT CELLS (the replays are byte-identical by each phase's own proof)")
    print("-" * 100)
    distinct: list[dict] = []
    for label, keep, replays in cells:
        d = logs.get(keep)
        if d is None:
            print(f"{label}: missing {keep}")
            continue
        distinct.extend(d["attempts"])
        cls = [a["cls"] for a in d["attempts"]]
        ok = cls.count("success")
        print(f"{label} ({keep}): {ok}/{len(cls)} placed; cnp {cls.count('cnp')}, "
              f"never_held {cls.count('never_held')}, fell_off {cls.count('fell_off')}, "
              f"other {cls.count('other')}")
        print(f"        replays (same stream, dropped from the pool): {replays}")
    pool = pooled if args.all else distinct
    n = len(pool)
    fails = [a for a in pool if a["cls"] != "success"]
    print()
    print(f"POOLED ATTEMPTS: n={n}  placed={n - len(fails)} "
          f"({100 * (n - len(fails)) / n:.1f} %)  failed={len(fails)}")
    print()
    print(f"{'class':12s} {'n':>3s} {'share of failures':>18s} {'share of attempts':>18s}  addressable")
    print("-" * 100)
    order = ["cnp", "never_held", "fell_off", "other"]
    ADDR = {
        "cnp": "NO - closed class (logs/p42/SIM_LIMIT.md): hardware",
        "never_held": "YES - pre-contact acquisition (supply geometry / x)",
        "fell_off": "YES - supply tail (P38/P48 x census)",
        "other": "read the rows",
    }
    for c in order:
        k = sum(1 for a in fails if a["cls"] == c)
        if not k and c != "other":
            continue
        print(f"{c:12s} {k:3d} {100 * k / len(fails):17.1f}% {100 * k / n:17.1f}%  {ADDR[c]}")
    print(f"{'TOTAL':12s} {len(fails):3d} {100:17.1f}% {100 * len(fails) / n:17.1f}%")

    # ---- cnp site + mechanism ------------------------------------------- #
    print()
    print("cnp by onset leg:")
    for s in ("lift", "place"):
        rows = [a for a in fails if a["cls"] == "cnp" and a["detail"] == s]
        if not rows:
            continue
        slips = [r["ev"].get("slip") for r in rows]
        fmin = [r["ev"].get("force_min") for r in rows]
        print(f"  {s:6s} n={len(rows)}  clean_slip {fmt(min(slips), 1)}-{fmt(max(slips), 1)} mm"
              f"  force_min {fmt(min(fmin), 2)}-{fmt(max(fmin), 2)} N")

    # ---- never-held detail ---------------------------------------------- #
    print()
    print("never_held rows (the pads closed on air):")
    for a in fails:
        if a["cls"] != "never_held":
            continue
        ev = a["ev"]
        print(f"  {a['log']:10s} {a['arm']:5s} {a['fruit']:10s} {fmt(a['dia_cm'], 1)} cm "
              f"sep_end={fmt(ev.get('sep_end'), 1)} gap_start={fmt(ev.get('gap_start'), 1)} "
              f"lift={a['lift']:+.3f} x={fmt(a['x'], 3)} queue={a['queue']}")
    print()
    print("other rows:")
    for a in fails:
        if a["cls"] != "other":
            continue
        print(f"  {a['log']:10s} {a['arm']:5s} {a['fruit']:10s} {a['notes']}")

    # ---- the x and queue distributions ---------------------------------- #
    def pctl(vals, p):
        v = sorted(x for x in vals if x is not None)
        if not v:
            return None
        return v[min(len(v) - 1, int(p * len(v)))]

    xs = [a["x"] for a in pool if a["x"] is not None]
    print()
    print(f"delivered x at selection: n={len(xs)} min={fmt(min(xs), 4)} "
          f"p50={fmt(pctl(xs, 0.5), 4)} p90={fmt(pctl(xs, 0.9), 4)} max={fmt(max(xs), 4)}")
    fx = [a["x"] for a in fails if a["x"] is not None and a["cls"] != "cnp"]
    dx = [a["x"] for a in fails if a["x"] is not None and a["cls"] == "cnp"]
    print(f"  non-cnp failures x: {[round(v, 4) for v in fx]}")
    print(f"  cnp failures x:     {[round(v, 4) for v in dx]}")
    qs = [a["queue"] for a in pool if a["queue"] is not None]
    print(f"catchable queue at the handover: n={len(qs)} min={min(qs) if qs else '-'} "
          f"p50={pctl(qs, 0.5)} max={max(qs) if qs else '-'}")
    for lab, sel in (("success", lambda a: a["cls"] == "success"),
                     ("failure", lambda a: a["cls"] != "success")):
        q = [a["queue"] for a in pool if a["queue"] is not None and sel(a)]
        if q:
            print(f"  queue | {lab:8s} n={len(q):2d} mean={sum(q) / len(q):.2f} "
                  f"dist={sorted(q)}")
    # x bands against the designed band and the measured clean edge
    TOP, EDGE = 0.36, 0.39
    for lab, lo, hi in (("in the designed band (<=0.36)", None, TOP),
                        ("above the designed top (>0.36)", TOP, EDGE),
                        ("at/above the clean edge (>=0.39)", EDGE, 9.9)):
        rows = [a for a in pool if a["x"] is not None
                and (lo is None or a["x"] > lo) and a["x"] <= hi]
        bad = [a for a in rows if a["cls"] != "success"]
        print(f"  x {lab:34s}: n={len(rows):2d} failed={len(bad):2d} "
              f"({100 * len(bad) / len(rows) if rows else 0:.0f} %) "
              f"classes={[a['cls'] for a in bad]}")

    # ---- the collapsed-close signature ---------------------------------- #
    print()
    print("the close's frozen command at the lift's first tick (`gap_start`), "
          "against the fruit's width:")
    print(f"  {'log':10s} {'arm':5s} {'class':10s} {'site':5s} {'x':6s} {'dia':5s} "
          f"{'gap_start':>9s} {'gap-dia':>8s} {'sep_max':>7s} {'fmin':>5s}")
    rows = []
    for a in pool:
        lg = a["legs"].get("grasp_lift")
        if not lg or lg["gap_start"] is None or not lg["dia"]:
            continue
        rows.append((a, lg, lg["gap_start"] - lg["dia"]))
    for a, lg, dd in sorted(rows, key=lambda r: r[2]):
        print(f"  {a['log']:10s} {a['arm']:5s} {a['cls']:10s} {a['detail']:5s} "
              f"{fmt(a['x'], 3):6s} {lg['dia']:5.1f} {lg['gap_start']:9.1f} "
              f"{dd:+8.1f} {lg['sep_max']:7.1f} {fmt(lg['force_min']):>5s}")
    collapsed = [r for r in rows if r[2] <= -14.0]
    normal = [r for r in rows if r[2] > -14.0]
    cf = sum(1 for r in collapsed if r[0]["cls"] != "success")
    nf = sum(1 for r in normal if r[0]["cls"] != "success")
    print(f"  collapsed (gap-dia <= -14 mm): n={len(collapsed)} failed={cf}")
    print(f"  normal                        : n={len(normal)} failed={nf}")
    if collapsed and normal:
        # one-sided Fisher: P(all `cf` failures land in the collapsed set)
        from math import comb
        N, K, n = len(rows), cf + nf, len(collapsed)
        num = sum(comb(K, k) * comb(N - K, n - k) for k in range(cf, min(K, n) + 1))
        print(f"  Fisher (one-sided, all {cf} of the collapsed set failed) p = "
              f"{num / comb(N, n):.4f}")

    # ---- per arm / per species ------------------------------------------ #
    print()
    print("per arm:")
    for arm in ("left", "right"):
        rows = [a for a in pool if a["arm"] == arm]
        bad = [a for a in rows if a["cls"] != "success"]
        print(f"  {arm:5s} n={len(rows):2d} placed={len(rows) - len(bad):2d} "
              f"({100 * (len(rows) - len(bad)) / len(rows):.0f} %) "
              f"classes={{cnp: {sum(1 for a in bad if a['cls'] == 'cnp')}, "
              f"never_held: {sum(1 for a in bad if a['cls'] == 'never_held')}}}")
    print("per species:")
    for sp in sorted({a["fruit"] for a in pool}):
        rows = [a for a in pool if a["fruit"] == sp]
        bad = [a for a in rows if a["cls"] != "success"]
        print(f"  {sp:10s} n={len(rows):2d} failed={len(bad):2d} "
              f"({100 * len(bad) / len(rows):.0f} %) "
              f"{[a['cls'] for a in bad]}")

    # ---- the diversions ------------------------------------------------- #
    print()
    print("diversions (a *slot* retired after 2 failed attempts; the retry is the "
          "same pool slot, and its x says whether it was the same instance):")
    for tag, d in logs.items():
        for dv in d["diverts"]:
            attempts = [a for a in d["attempts"] if a["index"] == dv["index"]]
            why = ",".join(f"{a['arm']}:{a['cls']}:x={fmt(a['x'], 3)}" for a in attempts)
            print(f"  {tag:10s} {dv['fruit']:10s} index={dv['index']} "
                  f"after {dv['n']} attempts -> {why}")
    # ---- the acquisition anomaly lines ---------------------------------- #
    print()
    print("acquisition anomaly lines (arm-agnostic prints, so counted, not attributed):")
    for tag, path in table.items():
        text = open(os.path.join(ROOT, path), errors="replace").read()
        resid = [float(v) for v in re.findall(
            r"dynamic catch-up: residual=([\d.]+) mm", text)]
        big = [v for v in resid if v > 6.0]
        drift = re.findall(r"close: fruit drifted (\d+) mm", text)
        left = re.findall(r"fruit left the pick station during the close \((\d+) mm\)",
                          text)
        print(f"  {tag:10s} catch-up residuals n={len(resid)} >6mm={len(big)} "
              f"{sorted(round(v, 1) for v in big)}  drift_rows={drift}  "
              f"left_station_rows={left}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
