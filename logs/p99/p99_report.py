"""P99 report: the census table and the cross-lane pricing A/B.

    python3 logs/p99/p99_report.py            # the table (-> p99_report.txt)
    python3 logs/p99/p99_report.py --check    # the admissibility assertions

Cells:
  C5 C6   the shipped default, `FRUIT_BED_DIAG=2` + `FRUIT_BIARM_PARK_TRACE=1`
          (reporting only; replay target `logs/p94/{T5,T6}.log`)
  G5 G6   the same instrumentation plus `FRUIT_GRADE_ROUTING=0` (the V2
          grade-preference with any-grade fallback) - the **pricing** arm for
          the census's mechanism (i). Not an adoption candidate: one output
          belt per arm (left lane 0 = grade A, right lane 1 = grade B), so a
          cross-lane pick is a sort error.
"""
from __future__ import annotations

import re
import sys

import census


CELLS = [("C5", "logs/p99/C5.log", "logs/p94/T5.log", 5),
         ("C6", "logs/p99/C6.log", "logs/p94/T6.log", 6),
         ("G5", "logs/p99/G5.log", None, 5),
         ("G6", "logs/p99/G6.log", None, 6)]


def cell_row(rec):
    tl = census.timeline(rec)
    iv = census.interval(rec)
    rows = [r for a in ("left", "right") for r in tl[a] if "gap" in r]
    n = len(rows) or 1
    gate = sum(r["park_wait"] for r in rows) / n
    park = sum(r["park_move"] for r in rows) / n
    feed = sum(r["feed"] for r in rows) / n
    polls = sum(r["polls"] for r in rows)
    poll_s = 0.5 * polls / n
    span = sum(r["span"] for r in rows) / n
    drows = census.decision_rows(rec)
    w = [d["wait_s"] for d in drows if d["wait_s"] is not None]
    rg = [d["rule_gap_s"] for d in drows if d["rule_gap_s"] is not None]
    conv_i = sum(d["chosen_gap_s"] or 0.0 for d in drows)
    starved = [d for d in drows if d["starved"]]
    cross_only = [d for d in drows if d["cross_only"]]
    # the in-chain starved polls whose wait a cross-lane fruit could have filled
    def _first_attempt(arm):
        for s in rec["slots"][arm]:
            if not s["poll"]:
                return s["t"]
        return -1.0
    t0 = {a: _first_attempt(a) for a in ("left", "right")}
    chain_cross = [d for d in starved
                   if (d["cross_only"] or d["cross_earlier"])
                   and d["t"] >= t0[d["arm"]]]
    prime_cross = [d for d in starved
                   if (d["cross_only"] or d["cross_earlier"])
                   and d["t"] < t0[d["arm"]]]
    conv_ip = 0.5 * len(chain_cross)
    conv_prime = 0.5 * len(prime_cross)
    tgt = {}
    for line in open(rec["path"], errors="replace"):
        m = census.TARGET.search(line)
        if m:
            tgt[(m.group(4), m.group(2))] = tgt.get((m.group(4), m.group(2)), 0) + 1
    cross_lane = (sum(v for (a, g), v in tgt.items() if a == "left" and g != "A")
                  + sum(v for (a, g), v in tgt.items() if a == "right" and g != "B"))
    placed_l = sum(1 for r in rec["results"] if r["placed"] and r["arm"] == "left")
    placed_r = sum(1 for r in rec["results"] if r["placed"] and r["arm"] == "right")
    rel = 0
    rel_ok = 0
    rel_present = 0
    sim = None
    for line in open(rec["path"], errors="replace"):
        if "released at [" in line:
            rel += 1
            rel_ok += 1 if "placed=True" in line else 0
        if "place trace" in line:
            m = re.search(r"release_bottom=([+-]?[0-9.]+)mm", line)
            if m and float(m.group(1)) >= 0.0:
                rel_present += 1
        if line.startswith("[fruit] [stats]"):
            m = re.search(r"sim=([0-9.]+)s total", line)
            if m:
                sim = float(m.group(1))
    wall = None
    stamps = rec["path"].replace(".log", ".stamps")
    try:
        for line in open(stamps, errors="replace"):
            pass
        wall = float(line.split()[0])
    except Exception:  # noqa: BLE001 - the wall is a report, never a gate
        wall = None
    placed_span = iv["mean"] * (iv["n"] - 1) if iv["n"] > 1 else float("nan")
    return dict(
        tag=None, placed=sum(1 for r in rec["results"] if r["placed"]),
        attempts=len(rec["results"]), placed_l=placed_l, placed_r=placed_r,
        interval=iv["mean"], p90=iv.get("p90"), n=iv["n"],
        arm_l=census.interval(rec, "left")["mean"],
        arm_r=census.interval(rec, "right")["mean"],
        gate=gate, park=park, feed=feed, poll_s=poll_s, dead=gate + park + feed + poll_s,
        span=span, polls=polls,
        decisions=len(drows), starved=len(starved),
        cross_only=len(cross_only), conv_i=conv_i, conv_ii=sum(rg),
        conv_ip=conv_ip, conv_prime=conv_prime,
        chain_cross=len(chain_cross), prime_cross=len(prime_cross),
        conv_iii=sum(r["park_wait"] for r in rows),
        wait_mean=(sum(w) / len(w)) if w else float("nan"),
        window_le1=sum(1 for d in drows if d["window"] <= 1 and not d["starved"]),
        sel=sum(1 for d in drows if not d["starved"]),
        cross_lane=cross_lane, releases=rel, landing=rel_ok,
        payload_present=rel_present,
        sim=sim, wall=wall, placed_span=placed_span,
        window_rate=(60 * (iv["n"] - 1) / placed_span
                     if placed_span == placed_span and placed_span > 0 else float("nan")),
        batch_rate=(60 * sum(1 for r in rec["results"] if r["placed"]) / sim
                    if sim else float("nan")),
        wall_rate=(60 * sum(1 for r in rec["results"] if r["placed"]) / wall
                   if wall else float("nan")),
    )


def main(argv):
    check = "--check" in argv
    rows = {}
    ok = True
    for tag, path, ref, seed in CELLS:
        try:
            rec = census.parse(path)
        except FileNotFoundError:
            continue
        if not rec["results"]:
            continue
        r = cell_row(rec)
        r["tag"] = tag
        r["seed"] = seed
        rows[tag] = r
    if check:
        print("== admissibility")
        for tag, path, ref, seed in CELLS:
            if ref is None:
                continue
            A = census._strip(path)
            B = census._strip(ref)
            same = A == B
            print(f"   {tag} vs {ref}: {len(A)}/{len(B)} [fruit] lines, "
                  f"{'IDENTICAL' if same else 'DIFFERS'}")
            ok = ok and same
        for tag in ("C5", "C6"):
            r = rows[tag]
            print(f"   {tag}: cross-lane fruit {r['cross_lane']}/{r['attempts']} "
                  f"(pure routing -> 0)")
            ok = ok and r["cross_lane"] == 0
        for tag in rows:
            r = rows[tag]
            # P86's landing convention: the criterion is "every payload PRESENT
            # at the release landed on a belt" (`release_bottom >= 0`); an
            # upstream-lost trace (`release_bottom = -184 mm`) released nothing
            # and is reported separately, never counted as a landing failure.
            print(f"   {tag}: landing {r['landing']}/{r['payload_present']} "
                  f"payload-present releases placed on a belt "
                  f"({r['releases']} release rows)")
            ok = ok and r["landing"] == r["payload_present"]
        print("   PASS" if ok else "   FAIL")
        return 0 if ok else 1

    def table(tags, title):
        print(f"\n== {title}")
        print(f"{'cell':5s} {'ok':>4s} {'L/R':>5s} {'interval':>8s} {'p90':>6s} "
              f"{'armL':>6s} {'armR':>6s} {'dead':>5s} {'gate':>5s} {'park':>5s} "
              f"{'feed':>5s} {'poll':>5s} {'span':>6s} {'polls':>5s}")
        for t in tags:
            r = rows[t]
            print(f"{t:5s} {r['placed']:4d} {r['placed_l']:2d}/{r['placed_r']:<2d} "
                  f"{r['interval']:8.2f} {r['p90']:6.2f} {r['arm_l']:6.2f} "
                  f"{r['arm_r']:6.2f} {r['dead']:5.2f} {r['gate']:5.2f} "
                  f"{r['park']:5.2f} {r['feed']:5.2f} {r['poll_s']:5.2f} "
                  f"{r['span']:6.2f} {r['polls']:5d}")

    table(["C5", "C6"], "the shipped default (the census cells)")
    print("\n== the candidate read (per decision, both arms) -- seconds per PLACEMENT")
    print(f"{'cell':5s} {'dec':>4s} {'star':>5s} {'cross':>6s} {'win<=1':>7s} "
          f"{'arr_w':>6s} {'(i)':>6s} {'(i-prime)':>9s} {'(ii)':>6s} {'(iii)':>6s} "
          f"{'sum':>6s} {'prime':>6s} {'%int':>5s}")
    tot = dict(i=0.0, ip=0.0, ii=0.0, iii=0.0, prime=0.0)
    n_pl = 0
    for t in ("C5", "C6"):
        r = rows[t]
        pl = max(1, r["n"])
        n_pl += pl
        s = r["conv_i"] + r["conv_ip"] + r["conv_ii"] + r["conv_iii"]
        print(f"{t:5s} {r['decisions']:4d} {r['starved']:5d} {r['cross_only']:6d} "
              f"{r['window_le1']:3d}/{r['sel']:<3d} {r['wait_mean']:6.2f} "
              f"{r['conv_i'] / pl:6.3f} {r['conv_ip'] / pl:9.3f} "
              f"{r['conv_ii'] / pl:6.3f} {r['conv_iii'] / pl:6.3f} "
              f"{s / pl:6.3f} {r['conv_prime'] / pl:6.3f} "
              f"{100 * (s / pl) / r['interval']:5.1f}")
        for k, v in (("i", r["conv_i"]), ("ip", r["conv_ip"]),
                     ("ii", r["conv_ii"]), ("iii", r["conv_iii"]),
                     ("prime", r["conv_prime"])):
            tot[k] += v
    s = tot["i"] + tot["ip"] + tot["ii"] + tot["iii"]
    print(f"{'pool':5s} {'':4s} {'':5s} {'':6s} {'':7s} {'':6s} "
          f"{tot['i'] / n_pl:6.3f} {tot['ip'] / n_pl:9.3f} "
          f"{tot['ii'] / n_pl:6.3f} {tot['iii'] / n_pl:6.3f} "
          f"{s / n_pl:6.3f} {tot['prime'] / n_pl:6.3f}")
    print(f"   (i) cross-lane in-attempt arrival = {tot['i'] / n_pl:.3f} s/placement; "
          f"(i-prime) in-chain starved polls with a cross-lane fruit = "
          f"{tot['ip'] / n_pl:.3f}; (ii) delay-aware = {tot['ii'] / n_pl:.3f}; "
          f"(iii) joint / park-gate = {tot['iii'] / n_pl:.3f}")
    print(f"   candidate planning total (i)+(i-prime) = "
          f"{(tot['i'] + tot['ip']) / n_pl:.3f} s/placement "
          f"= {100 * ((tot['i'] + tot['ip']) / n_pl) / (0.5 * (rows['C5']['interval'] + rows['C6']['interval'])):.1f}% "
          f"of the mean interval")
    print(f"   batch-prime polls of the same kind: {tot['prime']:.1f}s once per "
          f"batch = {tot['prime'] / n_pl:.3f} s/placement")

    if "G5" in rows and rows["G5"]["attempts"]:
        table(["C5", "C6", "G5", "G6"],
              "the pricing A/B (G = FRUIT_GRADE_ROUTING=0)")
        print("\n== the delivered side, both denominators + the wall")
        print(f"{'cell':5s} {'ok':>3s} {'sim':>6s} {'span':>7s} {'interval':>8s} "
              f"{'window/m':>8s} {'batch/m':>7s} {'wall':>7s} {'wall/m':>6s} "
              f"{'wall/pick':>9s}")
        for t in ("C5", "G5", "C6", "G6"):
            r = rows.get(t)
            if not r:
                continue
            print(f"{t:5s} {r['placed']:3d} {r['sim']:6.1f} {r['placed_span']:7.1f} "
                  f"{r['interval']:8.2f} {r['window_rate']:8.2f} {r['batch_rate']:7.2f} "
                  f"{r['wall']:7.1f} {r['wall_rate']:6.2f} "
                  f"{r['wall'] / max(1, r['placed']):9.1f}")
        print("\n== the cross-lane price")
        print(f"{'seed':>4s} {'arm':>4s} {'placed':>6s} {'interval':>8s} "
              f"{'armL':>6s} {'armR':>6s} {'dead':>5s} {'polls':>5s} "
              f"{'cross-lane':>10s}")
        for s in (5, 6):
            for pre in ("C", "G"):
                t = f"{pre}{s}"
                r = rows.get(t)
                if not r:
                    continue
                print(f"{s:4d} {pre:>4s} {r['placed']:6d} {r['interval']:8.2f} "
                      f"{r['arm_l']:6.2f} {r['arm_r']:6.2f} {r['dead']:5.2f} "
                      f"{r['polls']:5d} {r['cross_lane']:4d}/{r['attempts']:<5d}")
        for s in (5, 6):
            c, g = rows.get(f"C{s}"), rows.get(f"G{s}")
            if not (c and g):
                continue
            print(f"   seed {s}: interval {c['interval']:.2f} -> {g['interval']:.2f} "
                  f"({g['interval'] - c['interval']:+.2f}s, "
                  f"{100 * (g['interval'] - c['interval']) / c['interval']:+.1f}%), "
                  f"placed {c['placed']} -> {g['placed']}, "
                  f"sort errors {g['cross_lane']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
