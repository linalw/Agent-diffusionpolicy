#!/usr/bin/env python3
"""P129 report - the two benches, and the kill evaluation.

    python3 logs/p129/p129_report.py                 # both benches
    python3 logs/p129/p129_report.py --check         # the registered clauses
    python3 logs/p129/p129_report.py --same A B      # [fruit]-stream identity

Reads only the fixtures' own rows (`logs/p129/fixture_pinch.log`,
`logs/p129/fixture_ring_*.log`) - nothing is re-derived from a summary.
"""

from __future__ import annotations

import argparse
import os
import re
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PINCH = "logs/p129/fixture_pinch.log"
A0_ROW = re.compile(
    r"^\s*(?P<t>[0-9]\.[0-9]+)\s+(?P<pad>[0-9.]+)\s+(?P<n>\d+)\s+"
    r"(?P<sum>[0-9.]+)\s+(?P<f2>[0-9.]+|nan)\s+(?P<fx>[0-9.]+|nan)\s+"
    r"(?P<mu>[0-9.]+|nan)\s+(?P<err>[+-][0-9.]+|\+nan)"
)
A1_ROW = re.compile(
    r"^\s*(?P<profile>\w+)\s+(?P<fruit>\w+)\s+(?P<d>[0-9.]+)\s+(?P<pair>[0-9.]+)\s+"
    r"(?P<pads>\d+)\s+(?P<cq>[0-9.]+)\s+(?P<co>[0-9.]+)\s+(?P<dz>[+-][0-9.]+)\s+"
    r"(?P<lat>[0-9.]+)\s+(?P<f2>[0-9.]+|nan)\s+(?P<fx>[0-9.]+|nan)\s+(?P<fmax>[0-9.]+)\s+"
    r"(?P<span>[+-][0-9.]+)"
)
CELL = re.compile(
    r"\[p129r\] cell (?P<kind>\w+) pair=(?P<pair>[0-9.]+) k=\s*(?P<k>[0-9.]+) "
    r"freeze=(?P<fr>\d) (?P<ball>\w+)\s+off0=\s*(?P<o0>[+-]?[0-9.]+) "
    r"off_end=\s*(?P<oe>[+-]?[0-9.]+) d_off=\s*(?P<do>[+-]?[0-9.]+) "
    r"pads=(?P<pads>\d+)/(?P<n>\d+) f=\[(?P<f>[^\]]*)\]"
)

PROFILES = ("flat", "pair06", "pair08", "pair10", "pair12")


def pinch_rows():
    if not os.path.exists(PINCH):
        return [], []
    a0, a1 = [], []
    for line in open(PINCH, errors="replace"):
        line = line.rstrip("\n")
        m = A0_ROW.match(line)
        if m:
            a0.append({k: float(m[k]) if k != "n" else int(m[k]) for k in
                       ("t", "pad", "n", "sum", "f2", "fx", "mu", "err")})
            continue
            continue
        m = A1_ROW.match(line)
        if m:
            a1.append({k: (float(m[k]) if k not in ("profile", "fruit") else m[k])
                       for k in ("profile", "fruit", "d", "pair", "pads", "cq", "co",
                                 "dz", "lat", "f2", "fx", "fmax", "span")})
    return a0, a1


def ring_rows(kind):
    path = f"logs/p129/fixture_ring_{kind}.log"
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, errors="replace"):
        m = CELL.search(line)
        if m:
            out.append({k: (float(m[k]) if k not in ("kind", "ball", "f") else m[k])
                        for k in ("kind", "pair", "k", "fr", "ball", "o0", "oe", "do",
                                  "pads", "n", "f")})
    return out


def med(xs):
    xs = [x for x in xs if isinstance(x, float)]
    return st.median(xs) if xs else float("nan")


def bench_a(a0, a1):
    print("== bench A0 - the pair friction, measured (flat cube, 4.90 N/face) ==")
    print("target  pad_mu   n   sumN    F2mm   Fexit   mu_meas   err")
    for r in a0:
        print(f"{r['t']:6.2f} {r['pad']:7.2f} {r['n']:3d} {r['sum']:6.2f} "
              f"{r['f2']:7.2f} {r['fx']:7.2f} {r['mu']:9.3f} {r['err']:+6.3f}")
    if a0:
        errs = [r["err"] for r in a0 if r["err"] == r["err"]]
        print(f"  -> max |err| {max(abs(e) for e in errs):.3f}; "
              f"pair < 1 at targets <= 0.8: "
              f"{all(r['mu'] < 1.0 for r in a0 if r['t'] <= 0.8)}")

    print("\n== bench A1 - the pinch by pair friction (medians of 3, mm / N) ==")
    print("profile  fruit       d[mm] pair  pads  creep_g creep_op  load(dz) lateral"
          "   F2mm   Fexit")
    for prof in PROFILES:
        for fruit in ("pear", "orange", "strawberry", "lychee"):
            rr = [r for r in a1 if r["profile"] == prof and r["fruit"] == fruit]
            if not rr:
                continue
            print(f"{prof:8s} {fruit:10s} {med([r['d'] for r in rr]):6.1f} "
                  f"{med([r['pair'] for r in rr]):5.2f} {int(med([float(r['pads']) for r in rr])):4d} "
                  f"{med([r['co'] for r in rr]):8.2f} {med([r['co'] for r in rr]):8.2f} "
                  f"{med([r['dz'] for r in rr]):+8.3f} {med([r['lat'] for r in rr]):7.2f} "
                  f"{med([r['f2'] for r in rr]):7.2f} {med([r['fx'] for r in rr]):7.2f}")
    print("\n  ratio to the shipped control (flat), by fruit:")
    for fruit in ("pear", "orange", "strawberry", "lychee"):
        base = [r for r in a1 if r["profile"] == "flat" and r["fruit"] == fruit]
        if not base:
            continue
        b = med([r["fx"] for r in base])
        line = f"  {fruit:10s} Fexit"
        for prof in PROFILES[1:]:
            rr = [r for r in a1 if r["profile"] == prof and r["fruit"] == fruit]
            if not rr:
                continue
            v = med([r["fx"] for r in rr])
            line += f"  {prof}={v / b:.2f}x" if v == v and b else f"  {prof}=n/a"
        print(line)
    retained = {}
    for prof in PROFILES:
        rr = [r for r in a1 if r["profile"] == prof]
        held = [r for r in rr if r["pads"] >= 2]
        retained[prof] = (len(held), len(rr))
    print("\n  retention (cells with >= 2 loaded pads): "
          + ", ".join(f"{p} {a}/{b}" for p, (a, b) in retained.items()))
    return retained


def bench_b(rows_by_kind):
    for kind, rows in rows_by_kind.items():
        if not rows:
            continue
        print(f"\n== bench B ({kind}) - the ring: centring and the pad count ==")
        print("pair  k        freeze  ball    off0   off_end  d_off   pads  fmax")
        for r in sorted(rows, key=lambda r: (r["pair"], r["k"], r["fr"], r["ball"], r["o0"])):
            print(f"{r['pair']:5.2f} {r['k']:8.0f} {int(r['fr']):6d} {r['ball']:7s} "
                  f"{r['o0']:6.2f} {r['oe']:8.2f} {r['do']:+7.2f} {int(r['pads']):3d}/"
                  f"{int(r['n'])}")
        print("\n  the class table, by pair x k x protocol (counts over the 8 cells:")
        print("  2 prisms x 4 arrivals;  clean = all pads loaded and off_end <= 1.5 mm)")
        print("  pair  k        freeze  clean  centred-unloaded  frozen-off  all-pads  off20")
        keys = sorted({(r["pair"], r["k"], r["fr"]) for r in rows})
        for pair, k, fr in keys:
            rr = [r for r in rows if r["pair"] == pair and r["k"] == k and r["fr"] == fr]
            n = rr[0]["n"]
            clean = sum(1 for r in rr if int(r["pads"]) == int(n) and r["oe"] <= 1.5)
            unl = sum(1 for r in rr if int(r["pads"]) < int(n) and r["oe"] <= 1.5)
            froz = sum(1 for r in rr if int(r["pads"]) < int(n) and r["oe"] > 1.5)
            allp = sum(1 for r in rr if int(r["pads"]) == int(n))
            far = [r for r in rr if r["o0"] >= 19.0]
            off20 = med([r["oe"] for r in far]) if far else float("nan")
            print(f"  {pair:5.2f} {k:8.0f} {int(fr):6d} {clean:6d} {unl:16d} "
                  f"{froz:11d} {allp:9d} {off20:6.2f}")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--same", nargs=2)
    args = ap.parse_args()

    if args.same:
        a, b = args.same
        la = [l for l in open(a, errors="replace") if l.startswith("[fruit]")]
        lb = [l for l in open(b, errors="replace") if l.startswith("[fruit]")]
        n = min(len(la), len(lb))
        same = sum(1 for i in range(n) if la[i] == lb[i])
        print(f"{same}/{n} identical ({len(la)} vs {len(lb)} lines)")
        return 0 if same == n and len(la) == len(lb) else 1

    a0, a1 = pinch_rows()
    rows = {k: ring_rows(k) for k in ("cage4", "cage3")}
    if not a0 and not a1 and not any(rows.values()):
        print("no rows - run the benches first (logs/p129/run_p129_pinch.sh, "
              "logs/p129/run_p129_ring.sh)")
        return 2
    retained = bench_a(a0, a1)
    bench_b(rows)

    if not args.check:
        return 0

    print("\n== the kill ==")
    ok = True
    # K1: the pair is controllable below 1 at the working force.
    low = [r for r in a0 if r["t"] <= 0.8]
    k1 = bool(low) and any(r["mu"] >= 1.0 for r in low)
    print(f"  K1 the material cannot be made (pair >= 1 at t <= 0.8): "
          f"{'FIRES' if k1 else 'does not fire'}"
          + (" (measured " + ", ".join(f"{r['mu']:.2f}" for r in low) + ")"
             if low else " (no cell)"))
    ok = ok and not k1
    # K2: the shipped pair already encloses under a full close, from >= 10 mm.
    r4 = rows.get("cage4") or []
    ctrl = [r for r in r4 if r["pair"] >= 1.3 and r["k"] >= 1e5 and r["fr"] == 0.0
            and r["o0"] >= 9.0]
    k2 = bool(ctrl) and all(int(r["pads"]) == int(r["n"]) and r["oe"] <= 1.5 for r in ctrl)
    print(f"  K2 the material is not needed (the shipped pair encloses under a full "
          f"close): {'FIRES' if k2 else 'does not fire'}"
          + (f" ({sum(1 for r in ctrl if int(r['pads']) == int(r['n']))}/{len(ctrl)}"
             f" control cells all-pads, off_end <= 1.5)" if ctrl else " (no control cell)"))
    ok = ok and not k2
    # K3: the line's first-contact freeze denies the enclosure at every mu.
    far = [r for r in r4 if r["fr"] == 1.0 and r["o0"] >= 9.0]
    k3 = bool(far) and all(int(r["pads"]) < int(r["n"]) for r in far)
    print(f"  K3 the protocol denies the enclosure at every mu: "
          f"{'FIRES' if k3 else 'is not uniform'} "
          f"({sum(1 for r in far if int(r['pads']) < int(r['n']))}/{len(far)} freeze cells"
          f" at >= 10 mm lack a pad)")
    print(f"\n  -> {'NO KILL - a cell is licensed' if ok else 'KILL - publish the negative, no cell'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
