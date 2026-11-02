#!/usr/bin/env python3
"""P102 census: does a **spatial** tactile lead the force collapse?

`docs/PLATFORM_SURVEY.md` §5.1 registers the question. The tree's tactile channel
is two normal-force scalars and W5-C measured that where the force collapses the
payload is gone within 0-3 ticks, so a 2-scalar channel cannot be a reflex. The
survey's hypothesis: a **contact-patch** channel (the patch's centroid moving on
the pad) leads the collapse by enough to react. Its kill criterion is explicit:
**slip visible >= 10 ticks early on the majority of escapes, or `cnp` does not
fall >= 30 % -> kill**.

P102 step 1 built the patch channel as the default-off `FRUIT_TACTILE_PATCH`
(`tasks.tactile_patch_state`), one `[tactile]` row per pad per tick:

    [tactile] <side> <leg> pad=<0|1> t=<i> u= v= du= dv= dc= h= frac= edge=
              sep= gap= f= n= clean= dia=

`u`/`v` = the payload centre's projection on the pad's face (mm, from the finger
link origin), `du`/`dv` its displacement since the leg's first tick, `dc` that
displacement's norm, `frac` the share of the payload's equatorial disc still over
the pad's face rectangle, `edge` the signed distance from the centroid to the
nearest border, `f` **this pad's** normal force, `clean` the W8-B running
`clean_slip` (mm). All millimetres, all per pad.

**The reference tick is the seat, not the leg's first tick.** A `grasp_lift` leg
starts *before* the dynamic catch - the payload is caught 80-160 ticks in - so a
displacement measured from t=0 includes the catch's own approach (measured: a
13.7 mm reading on a leg that then held for 110 ticks). Every signal below is
therefore referenced to `t_seat` = the first tick the strong face reads > 1 N.
A leg that never reads > 1 N is **never-held** and is excluded (P76 A3).

Events, per leg:

  t_seat   first tick the strong face (max of the two pad forces) > 1 N
  t_2mm    first tick `clean` (relative to the seat) > 2 mm   - the survey's P1
           reference, verbatim ("detectable >= 10 ticks before clean_slip > 2 mm")
  t_force  first tick after which the strong face **stays** below 1 N for >= 5
           ticks - "the pinch is lost". The sustained form is required because
           the escape's own pry reads one face at 0.00 N for the whole leg
           (P75 2b), so a per-face drop would fire at the seat on the legs it is
           meant to detect.
  t_left   first tick `clean` > 100 mm - P74's "the payload has left"
           (the mechanism count, not the `> 800 mm` threshold)

Candidate signals, swept (all from the seat):

  dc > theta        5/10/20 % of the pad's half-length (`TACTILE_PAD_HALF_LONG` =
                    42.451 mm -> 2.12/4.25/8.49 mm), **and** the absolute
                    1/2/5/10 mm - a GelSight Mini's pad is 30x40 mm class, i.e. a
                    20 mm half-length -> 1/2/4 mm. Quoting both makes the pad-size
                    assumption visible instead of hiding it in a percentage.
  frac < phi*frac0  phi = 0.75, 0.50 - the patch's occupancy leaving the pad
  edge < 0          the centroid off the pad's face

An **escape leg** is P76 A3's definition: `clean_slip_max > 100 mm` **and**
`fmax > 0` (a pinch happened). A **held leg** is everything else that seated.
The false-positive read is the held legs at the same thresholds - a threshold
that trips a held leg is not a trigger.

Usage:
    python3 logs/p102/census.py logs/p102/T5.log logs/p102/T6.log
    python3 logs/p102/census.py --check ...          # assert the row grammar
    python3 logs/p102/census.py --same a.log b.log   # neutrality, streams equal

No simulator, no writes. Exit 1 on a malformed row under `--check`.
"""
from __future__ import annotations

import os
import re
import sys

#: `TACTILE_PAD_HALF_LONG` from `tasks.py`, pinned here so the % thresholds are
#: reproducible without importing the module (which needs Isaac Sim).
PAD_HALF_LONG = 0.084902 / 2.0
PCT_THRESHOLDS = (
    ("dc_5%", 0.05 * PAD_HALF_LONG * 1000.0),
    ("dc_10%", 0.10 * PAD_HALF_LONG * 1000.0),
    ("dc_20%", 0.20 * PAD_HALF_LONG * 1000.0),
)
ABS_THRESHOLDS = (("dc_1mm", 1.0), ("dc_2mm", 2.0),
                  ("dc_5mm", 5.0), ("dc_10mm", 10.0))
FRAC_THRESHOLDS = (("frac_0.75", 0.75), ("frac_0.50", 0.50))
SIGNALS = ([t for t, _ in PCT_THRESHOLDS] + [t for t, _ in ABS_THRESHOLDS]
           + [t for t, _ in FRAC_THRESHOLDS] + ["edge_lt0"])

ROW = re.compile(
    r"\[tactile\] (?P<side>\w+) (?P<leg>\w+) pad=(?P<pad>\d) t=(?P<t>\d+) "
    r"u=(?P<u>[-+0-9.]+) v=(?P<v>[-+0-9.]+) "
    r"du=(?P<du>[-+0-9.]+) dv=(?P<dv>[-+0-9.]+) dc=(?P<dc>[-+0-9.]+) "
    r"h=(?P<h>[-+0-9.]+) frac=(?P<frac>[0-9.]+) edge=(?P<edge>[-+0-9.]+) "
    r"sep=(?P<sep>[-+0-9.]+) gap=(?P<gap>[-+0-9.]+) f=(?P<f>[-+0-9.]+) "
    r"n=(?P<n>\d+) clean=(?P<clean>[-+0-9.]+) dia=(?P<dia>[-+0-9.]+)"
)
CARRY = re.compile(
    r"\[carry\] (?P<side>\w+) (?P<leg>\w+): ticks=(?P<ticks>\d+)/\d+ "
    r"clean_slip_max=(?P<slip>[-+0-9.]+)mm"
)
RUN = re.compile(
    r"\[run\]\s+(?P<fruit>\w+)\s+arm=(?P<arm>\w+)\s+grasped=(?P<g>\w+)\s+"
    r"placed=(?P<p>\w+)"
)
#: the bimanual driver's form, printed after the whole batch:
#: `[run] attempt 3 (left): grasped=True placed=False lift=... notes=[...]`
RUN_POST = re.compile(
    r"\[run\] attempt (?P<n>\d+) \((?P<arm>\w+)\): grasped=(?P<g>\w+) "
    r"placed=(?P<p>\w+)"
)


def parse(path):
    """Per-side leg instances; a `[carry]` row closes the leg it belongs to."""
    legs, live, counter, runs = [], {}, {}, []
    for line in open(path, errors="replace"):
        m = ROW.search(line)
        if m:
            d = m.groupdict()
            side = d["side"]
            cur = live.get(side)
            if cur is None or cur["leg"] != d["leg"]:
                counter[side] = counter.get(side, 0) + 1
                cur = {"side": side, "leg": d["leg"], "rows": {0: [], 1: []},
                       "slip_max": None, "order": counter[side], "path": path}
                live[side] = cur
                legs.append(cur)
            cur["rows"][int(d["pad"])].append({
                "t": int(d["t"]), "u": float(d["u"]), "v": float(d["v"]),
                "du": float(d["du"]), "dv": float(d["dv"]), "dc": float(d["dc"]),
                "h": float(d["h"]), "frac": float(d["frac"]),
                "edge": float(d["edge"]), "sep": float(d["sep"]),
                "gap": float(d["gap"]), "f": float(d["f"]), "n": int(d["n"]),
                "clean": float(d["clean"]), "dia": float(d["dia"]),
            })
            continue
        m = CARRY.search(line)
        if m:
            side, leg = m.group("side"), m.group("leg")
            cur = live.get(side)
            if cur is not None and cur["leg"] == leg:
                cur["slip_max"] = float(m.group("slip"))
                live[side] = None
            continue
        m = RUN.search(line)
        if m:
            runs.append(m.groupdict())
            continue
        m = RUN_POST.search(line)
        if m:
            runs.append({"post": True, "arm": m.group("arm"),
                         "g": m.group("g"), "p": m.group("p")})
    # per-arm attempt index: the k-th `grasp_lift` a side takes IS its k-th
    # attempt (an attempt that loses the payload at the lift has no place leg),
    # and the driver prints one outcome row per attempt in the same order.
    for side in ("left", "right"):
        k = 0
        for leg in legs:
            if leg["side"] != side:
                continue
            if leg["leg"] == "grasp_lift":
                k += 1
            leg["attempt"] = k
    outcomes = {}
    for side in ("left", "right"):
        rows = [r for r in runs if r.get("post") and r.get("arm") == side]
        for i, r in enumerate(rows, start=1):
            outcomes[(side, i)] = r
    for leg in legs:
        leg["outcome"] = outcomes.get((leg["side"], leg["attempt"]))
        leg["path"] = path
        leg["arm_attempt"] = leg["attempt"]
    return legs, runs
    return legs, runs


def first(xs, pred, start=0):
    for i in range(start, len(xs)):
        if pred(xs[i]):
            return i
    return None


def analyse(leg):
    """One leg's per-tick series plus its event times (leg-local tick indices)."""
    if not leg["rows"][0]:
        return None
    have = [p for p in (0, 1) if leg["rows"][p]]
    s0 = leg["rows"][have[0]]
    f_by_t = {}
    for p in have:
        for row in leg["rows"][p]:
            f_by_t.setdefault(row["t"], {})[p] = row["f"]
    faces, strong = [], []
    for row in s0:
        per = f_by_t.get(row["t"], {})
        pair = (per.get(0, 0.0), per.get(1, 0.0))
        faces.append(pair)
        strong.append(max(pair))

    # The seat needs BOTH a loaded pinch and the patch *on the pad*: a failed
    # catch reads force on a flank while the payload is hundreds of mm off the
    # face (measured: u = +318 mm, edge -287 mm, sep 21.8 mm under a 39.5 mm
    # command on a 68.9 mm fruit - the hand closed on air), and a `clean_slip`
    # displacement there is the arm carrying an empty hand, not a slide.
    t_seat = first(
        range(len(strong)),
        lambda i: strong[i] > 1.0
        and s0[i]["edge"] > -PAD_HALF_LONG * 1000.0,
    )
    out = {
        "side": leg["side"], "leg": leg["leg"], "order": leg["order"],
        "path": leg["path"], "ticks": len(s0),
        "slip_max": leg["slip_max"], "dia": s0[0]["dia"],
        "fmax": max(strong), "fmin": min(strong),
        "t_seat": t_seat, "faces": faces, "strong": strong,
        "series": s0, "t": {},
    }
    if t_seat is None:
        out["seated"] = False
        return out
    out["seated"] = True

    # Everything referenced to the seat.
    for r in s0[t_seat:]:
        r["clean_rel"] = r["clean"] - s0[t_seat]["clean"]
    out["clean_seat"] = s0[t_seat]["clean"]
    out["f_seat"] = strong[t_seat]
    out["frac0"] = s0[t_seat]["frac"]
    out["u_seat"] = s0[t_seat]["u"]
    out["v_seat"] = s0[t_seat]["v"]

    # Sustained pinch loss: the strong face below 1 N for >= 5 consecutive ticks.
    n = len(strong)
    t_force = None
    for i in range(t_seat, n):
        if strong[i] < 1.0 and all(strong[j] < 1.0 for j in range(i, min(n, i + 5))):
            t_force = i
            break
    out["t_force"] = t_force
    out["force_before"] = (
        sorted(strong[max(0, t_force - 10):t_force])[max(0, (min(10, t_force) - 1) // 2)]
        if t_force is not None else None
    )
    out["t_2mm"] = first(s0, lambda r: r["clean_rel"] > 2.0, t_seat)
    out["t_left"] = first(s0, lambda r: r["clean_rel"] > 100.0, t_seat)
    out["t_static"] = first(s0, lambda r: r["dc"] > 0.5, t_seat)
    out["dc_max"] = max(r["dc"] for r in s0[t_seat:])
    out["frac_min"] = min(r["frac"] for r in s0[t_seat:])
    out["edge_min"] = min(r["edge"] for r in s0[t_seat:])
    out["clean_max"] = max(r["clean_rel"] for r in s0[t_seat:])
    out["v_span"] = (max(r["v"] for r in s0[t_seat:])
                     - min(r["v"] for r in s0[t_seat:]))

    for tag, thr in PCT_THRESHOLDS + ABS_THRESHOLDS:
        out["t"][tag] = first(s0, lambda r, x=thr: r["dc"] > x, t_seat)
    for tag, phi in FRAC_THRESHOLDS:
        out["t"][tag] = first(s0, lambda r, x=phi * out["frac0"]: r["frac"] < x, t_seat)
    out["t"]["edge_lt0"] = first(s0, lambda r: r["edge"] < 0.0, t_seat)

    # A tick-of-event offset from the seat, for readability in the tables.
    out["n"] = {k: (None if v is None else v - t_seat) for k, v in out["t"].items()}
    for k in ("t_force", "t_2mm", "t_left", "t_static"):
        out["n" + k.replace("t_", "t_")] = (
            None if out[k] is None else out[k] - t_seat
        )
    return out


def is_escape(a):
    """P76 A3 + the seat: a pinch happened **on the pad**, then the payload left.

    `slip_max > 100 mm` alone is not enough on this cell: a failed catch reads a
    force on the fruit's flank with the payload 300+ mm off the pad face, and
    its `clean_slip` is the arm carrying an empty hand. So the leg must also have
    **seated** - a loaded pinch with the patch on the pad (`t_seat` is not None,
    which already requires `edge > -half_long`) - and then lost it
    (`fmax > 0`, the A3 pinch clause, and `clean > 100 mm` *after* the seat).
    """
    if not a.get("seated"):
        return False
    if a["fmax"] <= 0.0:
        return False
    return a["clean_max"] > 100.0


def lead(a, key):
    """`t_force - t_signal` in ticks: positive = the signal fires first."""
    t = a["t"][key]
    if t is None or a["t_force"] is None:
        return None
    return a["t_force"] - t


def lead_left(a, key):
    t = a["t"][key]
    if t is None or a["t_left"] is None:
        return None
    return a["t_left"] - t


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def fmt(x, nd=1):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def report(paths, lead_only=False):
    all_legs, runs = [], []
    for p in paths:
        legs, r = parse(p)
        all_legs += legs
        runs += r
    arms = []
    for leg in all_legs:
        a = analyse(leg)
        if a:
            a["attempt"] = leg.get("attempt")
            a["outcome"] = leg.get("outcome")
            a["path"] = leg.get("path")
            arms.append(a)
    seated = [a for a in arms if a["seated"]]
    esc = [a for a in seated if is_escape(a)]
    held = [a for a in seated if not is_escape(a)]

    print("=" * 112)
    print("P102 - the spatial tactile channel vs the force collapse")
    print("=" * 112)
    print(f"\n## 0 population  ({', '.join(os.path.basename(p) for p in paths)})")
    print(f"  carry legs {len(arms)}   seated {len(seated)}   "
          f"never-held {len(arms) - len(seated)}   "
          f"escape (A3: slip_max > 100 mm AND fmax > 0) {len(esc)}   "
          f"held {len(held)}")
    post = [r for r in runs if r.get("post")]
    print(f"  attempts {len(post)}: "
          f"placed {sum(1 for r in post if r['p'] == 'True')}, "
          f"grasped-not-placed "
          f"{sum(1 for r in post if r['g'] == 'True' and r['p'] != 'True')}, "
          f"no-grasp {sum(1 for r in post if r['g'] != 'True')}")
    per = {}
    for a in esc:
        per[a["side"]] = per.get(a["side"], 0) + 1
    print(f"  escapes per arm {per}   legs per arm "
          f"{ {s: sum(1 for a in seated if a['side'] == s) for s in ('left', 'right')} }")

    print("\n## 0b the attempt join (does the class the sensor would fix own the failures?)")
    by_att = {}
    for a in arms:
        key = (os.path.basename(a.get("path") or "?"), a["side"], a["attempt"])
        d = by_att.setdefault(key, {"outcome": a["outcome"], "legs": []})
        d["legs"].append(a)
    counts = {}
    for key, d in sorted(by_att.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] or 0)):
        oc = d["outcome"] or {}
        placed = oc.get("p") == "True"
        cls = []
        if placed:
            cls.append("placed")
        elif oc.get("g") != "True":
            cls.append("no-grasp")
        else:
            cls.append("cnp")
        n_esc = sum(1 for a in d["legs"] if is_escape(a))
        nev = sum(1 for a in d["legs"] if not a["seated"])
        cls.append(f"seated-escapes={n_esc}")
        cls.append(f"never-held-legs={nev}")
        k = "placed" if placed else ("no-grasp" if oc.get("g") != "True" else "cnp")
        counts.setdefault(k, []).append((n_esc, nev))
        print(f"  {key[0]:8s} {key[1]:5s} attempt {key[2]:>2}: {' '.join(cls)}")
    print()
    for k, rows in counts.items():
        with_esc = sum(1 for n_esc, _ in rows if n_esc)
        print(f"  {k:9s} {len(rows):>2} attempts; {with_esc} carry a seated escape leg; "
              f"{sum(1 for _, nev in rows if nev)} carry a never-held leg")

    print("\n## 1 per leg (offsets are ticks from the seat; `.` = never)")
    print(f"  {'arm':5s} {'leg':9s} {'dia':>4} {'tick':>4} {'seat':>4} {'f@seat':>6} "
          f"{'fmax':>5} {'t_2mm':>5} {'t_force':>7} {'t_left':>6} {'slip':>7} "
          f"{'dc_max':>6} {'frac0':>5} {'fracmn':>6} {'edgemn':>6}")
    for a in arms:
        if not a["seated"]:
            print(f"  {a['side']:5s} {a['leg']:9s} {a['dia']:4.1f} {a['ticks']:>4} "
                  f"{'--':>4} {'--':>6} {a['fmax']:5.2f} {'--':>5} {'--':>7} {'--':>6} "
                  f"{fmt(a['slip_max']):>7} {'--':>6} {'--':>5} {'--':>6} {'--':>6}"
                  f"   NEVER-HELD")
            continue
        print(f"  {a['side']:5s} {a['leg']:9s} {a['dia']:4.1f} {a['ticks']:>4} "
              f"{a['t_seat']:>4} {a['f_seat']:6.2f} {a['fmax']:5.2f} "
              f"{fmt(a['nt_2mm'], 0):>5} {fmt(a['nt_force'], 0):>7} "
              f"{fmt(a['nt_left'], 0):>6} {fmt(a['slip_max']):>7} "
              f"{a['dc_max']:6.2f} {a['frac0']:5.3f} {a['frac_min']:6.3f} "
              f"{a['edge_min']:6.1f}{'   ESCAPE' if is_escape(a) else ''}")

    print("\n## 2 the lead, per escape leg, against `t_force` (ticks; empty = the "
          "signal never fired, `0`/`-n` = at or after the collapse)")
    print(f"  {'arm/leg':16s} " + " ".join(f"{k:>9s}" for k in SIGNALS))
    for a in esc:
        print(f"  {a['side'] + ' ' + a['leg']:16s} "
              + " ".join(f"{fmt(lead(a, k), 0):>9s}" for k in SIGNALS))

    print("\n## 3 the distribution over the escape legs")
    print(f"  {'signal':>10} {'fired':>6} {'med':>5} {'min':>5} {'max':>5} "
          f"{'>=10t':>6} {'>=1t':>6} {'<=0':>4}   vs t_left: {'med':>5} {'>=10t':>6}")
    for k in SIGNALS:
        L = [lead(a, k) for a in esc]
        grp = [x for x in L if x is not None]
        LL = [lead_left(a, k) for a in esc]
        gl = [x for x in LL if x is not None]
        n10 = sum(1 for x in grp if x >= 10)
        n1 = sum(1 for x in grp if x >= 1)
        late = sum(1 for x in grp if x <= 0)
        print(f"  {k:>10} {len(grp):>3}/{len(esc):<2} {fmt(median(grp), 0):>5} "
              f"{fmt(min(grp) if grp else None, 0):>5} "
              f"{fmt(max(grp) if grp else None, 0):>5} "
              f"{n10:>6} {n1:>6} {late:>4}   {'':>13} {fmt(median(gl), 0):>5} "
              f"{sum(1 for x in gl if x >= 10):>6}")

    print("\n## 4 the false-positive read (held legs, same thresholds)")
    print(f"  {'signal':>10} {'tripped':>8} {'rate':>7}")
    for k in SIGNALS:
        n = sum(1 for a in held if a["t"][k] is not None)
        print(f"  {k:>10} {n:>8} {n / max(1, len(held)):7.2%}")

    print("\n## 5 the quiet-signal read (how much the patch moves on a held leg)")
    if held:
        dc = [a["dc_max"] for a in held]
        ed = [a["edge_min"] for a in held]
        fr = [a["frac_min"] - a["frac0"] for a in held]
        print(f"  dc_max over the leg:  median {median(dc):.2f} mm, max {max(dc):.2f} mm")
        print(f"  frac drop:            median {median(fr):.3f}, min {min(fr):.3f}")
        print(f"  edge_min:             median {median(ed):.1f} mm, min {min(ed):.1f} mm")

    print("\n## 5b which held legs trip (a release artefact is not a slip)")
    for k in SIGNALS:
        rows = [a for a in held if a["t"][k] is not None]
        if not rows:
            continue
        for a in rows:
            print(f"  {k:>10}  {a['side']:5s} {a['leg']:9s} dc_max={a['dc_max']:7.2f} mm "
                  f"clean_max={a['clean_max']:7.1f} mm  "
                  f"{'ESCAPE-class clean but < 100' if a['clean_max'] > 20 else ''}")

    if lead_only:
        print("\n## 6 the walk window of every escape leg (the lead-time table)")
        for a in esc:
            _window(a, "escape")
    else:
        print("\n## 6 the tick-by-tick window (escape with an in-leg notice, "
              "then a held control)")
        cand = [a for a in esc if a["t_force"] is not None]
        if cand:
            _window(max(cand, key=lambda a: a["t_force"]), "escape")
        if held:
            _window(sorted(held, key=lambda a: -a["t_seat"])[0], "held")

    print("\n## 7 the walk profile: how slow is the slide before the pinch is lost?")
    print("  (the number that decides whether a 30 Hz pad - 33 ms/frame - can resolve it)")
    print(f"  {'arm/leg':16s} {'t_2mm':>6} {'t_force':>7} {'notice':>7} {'notice s':>9} "
          f"{'rate mm/s':>10} {'dc@2mm':>7} {'dc@loss':>7} {'frac@2mm':>9} "
          f"{'edge@2mm':>9}")
    for a in esc:
        if a["t_2mm"] is None or a["t_force"] is None:
            continue
        i0, i1 = a["t_2mm"], a["t_force"]
        notice = i1 - i0
        dc1 = a["series"][i1]["dc"]
        # the slide's mean rate over the notice window, in mm/s (120 Hz control)
        rate = (dc1 - a["series"][i0]["dc"]) / max(1, notice) * 120.0
        print(f"  {a['side'] + ' ' + a['leg']:16s} {i0:>6} {i1:>7} {notice:>7} "
              f"{notice / 120.0:9.3f} {rate:10.1f} "
              f"{a['series'][i0]['dc']:7.2f} {dc1:7.2f} "
              f"{a['series'][i0]['frac']:9.3f} "
              f"{a['series'][i0]['edge']:9.1f}")
    notices = [a["t_force"] - a["t_2mm"] for a in esc
               if a["t_2mm"] is not None and a["t_force"] is not None]
    if notices:
        print(f"  notice over the {len(notices)} escapes: median {median(notices):.0f} ticks "
              f"({median(notices) / 120.0:.2f} s), min {min(notices)} "
              f"({min(notices) / 120.0:.2f} s), max {max(notices)} "
              f"({max(notices) / 120.0:.2f} s)")
        print(f"  a 30 Hz pad gets {median(notices) / 120.0 * 30:.0f} frames at the median, "
              f"{min(notices) / 120.0 * 30:.0f} at the minimum; a 60 Hz pad "
              f"{median(notices) / 120.0 * 60:.0f} / {min(notices) / 120.0 * 60:.0f}")

    if lead_only:
        return 0
    print("\n## 8 is the centroid channel independent of the shipped `clean_slip`?")
    print("  `dc` is the in-plane part of the same 3-D displacement the `[carry]` row\n"
          "  prints as `clean_slip`. If dc ~ clean the spatial channel adds no timing\n"
          "  information; only `frac`/`edge` (a function of the same u,v) is new.")
    for a in esc + held:
        post = [r for r in a["series"][a["t_seat"]:] if r["clean_rel"] > 0.01]
        if not post:
            continue
        ratios = sorted(min(1.0, r["dc"] / r["clean_rel"]) for r in post)
        med = ratios[len(ratios) // 2]
        print(f"  {a['side']:5s} {a['leg']:9s} "
              f"{'ESCAPE' if is_escape(a) else 'held  '}  "
              f"dc/clean median {med:.3f}, min {ratios[0]:.3f}, "
              f"max {ratios[-1]:.3f}  (n={len(post)} ticks with clean > 0.01 mm)")
    return 0


def _window(a, tag):
    """The money table: the whole walk from its first 2 mm to the loss."""
    tf = a["t_force"]
    s = a["series"]
    if tf is None:
        lo, hi = a["t_seat"], min(len(s) - 1, a["t_seat"] + 6)
        step = 1
    else:
        lo = max(a["t_seat"], (a["t_2mm"] if a["t_2mm"] is not None else tf) - 2)
        hi = min(len(s) - 1, tf + 6)
        span = hi - lo
        step = 1 if span <= 40 else max(1, span // 20)
    print(f"\n  [{tag}] {a['side']} {a['leg']} dia={a['dia']:.1f} mm "
          f"f@seat={a['f_seat']:.2f} N  seat=t{a['t_seat']} "
          f"t_2mm={a['t_2mm']} t_force={tf} t_left={a['t_left']} "
          f"slip_max={fmt(a['slip_max'])} mm"
          + ("  (no sustained force loss: a held leg)"
             if tf is None else
             f"  notice={tf - a['t_2mm']} ticks ({(tf - a['t_2mm']) / 120.0:.2f} s)"))
    print("    (du = across the finger, the plate's 61 mm side; dv = down it, "
          "the 84.9 mm side)")
    print(f"    {'t':>4} {'dc':>7} {'du':>7} {'dv':>7} {'frac':>6} {'edge':>7} "
          f"{'f_pad0':>7} {'f_pad1':>7} {'sep':>6} {'clean':>7}")
    idx = list(range(lo, hi + 1, step))
    for must in (lo, a["t_2mm"], tf, hi):
        if must is not None and lo <= must <= hi and must not in idx:
            idx.append(must)
    for i in sorted(set(idx)):
        r = s[i]
        print(f"    {i:>4} {r['dc']:7.2f} {r['du']:7.2f} {r['dv']:7.2f} "
              f"{r['frac']:6.3f} {r['edge']:7.1f} "
              f"{a['faces'][i][0]:7.2f} {a['faces'][i][1]:7.2f} "
              f"{r['sep']:6.1f} {r['clean']:7.1f}")


def same(a_path, b_path):
    """Neutrality: the two logs' `[fruit]` stream identical with `[tactile]` dropped.

    The `[fruit]`-prefixed stream IS the scripted line's own report (`say()`
    prefixes every row with `[fruit]`), so this covers the `[carry]` diag, the
    `[place-trace]` rows and every motion/cycle row - the P75/P95/P96 convention,
    widened past the `[fruit]`-only replay because a new row is what this phase
    adds. The Isaac startup chatter is never byte-identical (timestamps, PIDs,
    free memory), so it is not part of the comparison - exactly as every replay
    in this repo does it.
    """
    def strip(path):
        return [ln for ln in open(path, errors="replace").read().splitlines()
                if ln.startswith("[fruit]") and "[tactile]" not in ln]

    a, b = strip(a_path), strip(b_path)
    if len(a) != len(b):
        print(f"  DIFFERS: line count {len(a)} vs {len(b)}")
        return 1
    bad = [(i, x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y]
    if bad:
        i, x, y = bad[0]
        print(f"  DIFFERS: {len(bad)}/{len(a)} lines; first at {i + 1}")
        print(f"    A: {x.strip()[:130]}")
        print(f"    B: {y.strip()[:130]}")
        return 1
    print(f"  SAME: {len(a)}/{len(a)} `[fruit]` lines identical with `[tactile]` dropped")
    return 0


def main(argv):
    paths = [a for a in argv[1:] if not a.startswith("--")]
    if "--same" in argv:
        return same(paths[0], paths[1])
    if "--check" in argv:
        bad = 0
        for p in paths:
            for line in open(p, errors="replace"):
                if "[tactile]" in line and not ROW.search(line):
                    print(f"  MALFORMED {p}: {line.strip()[:100]}")
                    bad += 1
        print(f"  {bad} malformed row(s) in {len(paths)} log(s)")
        return 1 if bad else 0
    if not paths:
        print(__doc__)
        return 1
    return report(paths, lead_only="--lead" in argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
