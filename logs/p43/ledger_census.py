#!/usr/bin/env python3
"""P43 phase 1 - the offline per-battery ledger census (reads logs only).

No simulator, no `src/` change. Reproduces every number in
`logs/p43/RATE_LEDGER.md` from the logs themselves.

    python3 logs/p43/ledger_census.py                 # the ledger's batteries
    python3 logs/p43/ledger_census.py --log <file>    # one battery

What it extracts, per battery:

* attempts / placed (the log's own terminal rows), the `[stats]` `sim` total,
  `s/attempt`, `placed/min` (`60 * placed / sim_span`) and the retention-free
  ceiling (`60 * attempts / sim_span`);
* the **retention tax** = the share of per-arm attempt time spent on attempts
  that placed nothing (sum of the not-placed attempts' own `sim=` spans over
  the sum of all spans) - the RATE_CENSUS definition;
* the arrival wait (`fruit at pick point ... after N steps`), the handover wait
  (`dynamic descent: waited N ticks`), the approach motion
  (`approach(cartesian) N samples`) and the re-seat row count;
* the `[cycle]` decomposition when the log carries it (`FRUIT_CYCLE_REPORT=1`),
  paired positionally with the outcome rows (the two-line logs interleave the
  arms, so a "block between two headers" is not one attempt).

`descent` in the `[cycle]` row is `wait + descent` (the mark sits after the wait
loop and the approach); this script nets the wait out and reports it apart.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

DT = 1.0 / 120.0


def lines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            yield ln.rstrip("\n")


def parse(path):
    out = {
        "file": path,
        "attempts": None,
        "placed": None,
        "sim_span": None,
        "biarm": None,
        "spans": [],          # (placed: bool, sim seconds)
        "waits": [],          # arrival wait, seconds
        "handover": [],       # handover wait, seconds
        "approach": [],       # approach motion, seconds
        "cycle": [],          # dict per [cycle] row
        "cycle_outcomes": [], # bool placed, positional
        "reseats": 0,
        "policy_decisions": [],
        "episodes": 0,
    }
    for ln in lines(path):
        if "[stats]" in ln:
            m = re.search(
                r"attempts=(\d+) successes=(\d+).*?sim=([0-9.]+)s total, "
                r"([0-9.]+)s/attempt", ln)
            if m:
                out["attempts"] = int(m.group(1))
                out["placed"] = int(m.group(2))
                out["sim_span"] = float(m.group(3))
        m = re.search(r"\[biarm\] \d+ pipelined slots, (\d+) attempts, "
                      r"(\d+) successes, ([0-9.]+)s sim span, "
                      r"([0-9.]+)s/attempt.*?([0-9.]+) fruits/min", ln)
        if m:
            out["biarm"] = {
                "attempts": int(m.group(1)),
                "placed": int(m.group(2)),
                "sim_span": float(m.group(3)),
                "s_per_attempt": float(m.group(4)),
                "fruits_per_min": float(m.group(5)),
            }
        m = re.search(r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+)"
                      r".*?sim=([0-9.]+)-([0-9.]+)s", ln)
        if m:
            out["spans"].append((m.group(3) == "True", float(m.group(5)) -
                                 float(m.group(4))))
        m = re.search(r"\[biarm\] result (\w+) index=\d+ .*?grasped=(\w+) "
                      r"placed=(\w+).*?sim=([0-9.]+)s", ln)
        if m:
            out["spans"].append((m.group(3) == "True", float(m.group(4))))
        m = re.search(r"fruit at pick point: .*?after (\d+) steps", ln)
        if m:
            out["waits"].append(int(m.group(1)) * DT)
        m = re.search(r"dynamic descent: waited (\d+) ticks", ln)
        if m:
            out["handover"].append(int(m.group(1)) * DT)
        m = re.search(r"\[motion\] approach\(cartesian\): .*?, (\d+) samples", ln)
        if m:
            out["approach"].append(int(m.group(1)) * DT)
        if "regrasp: re-seated" in ln:
            out["reseats"] += 1
        if "[cycle]" in ln:
            d = {}
            for key in ("prepose", "hover", "wait", "descent", "close", "grip",
                        "lift", "place", "release", "return", "end", "total"):
                mm = re.search(rf"(?:^|\s){key}=([0-9.]+)", ln)
                if mm:
                    d[key] = float(mm.group(1))
            if d:
                out["cycle"].append(d)
        m = re.search(r"\[biarm\] result .* placed=(\w+)", ln)
        if m:
            out["cycle_outcomes"].append(m.group(1) == "True")
        m = re.search(r"\[run\] attempt \d+: grasped=\w+ placed=(\w+)", ln)
        if m:
            out["cycle_outcomes"].append(m.group(1) == "True")
        m = re.search(r"\[rl\] episode \d+: .*? success=\w+ .*?ticks=(\d+) "
                      r"decision=(\d+)", ln)
        if m:
            out["policy_decisions"].append((int(m.group(1)), int(m.group(2))))
    return out


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def median(xs):
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def report(path):
    d = parse(path)
    name = os.path.basename(path)
    att = d["attempts"] if d["attempts"] is not None else d["biarm"]["attempts"]
    placed = d["placed"] if d["placed"] is not None else d["biarm"]["placed"]
    span = d["sim_span"] if d["sim_span"] is not None else d["biarm"]["sim_span"]
    out = [f"### {name}"]
    out.append(f"attempts={att} placed={placed} "
               f"({100.0 * placed / att:.0f} %) sim_span={span:.1f} s "
               f"s/attempt={span / att:.2f} placed/min={60.0 * placed / span:.2f} "
               f"ceiling={60.0 * att / span:.2f} "
               f"(+{60.0 * att / span - 60.0 * placed / span:.2f})")
    if d["spans"]:
        lost = sum(s for p, s in d["spans"] if not p)
        tot = sum(s for _, s in d["spans"])
        out.append(f"retention tax: {100.0 * lost / tot:.1f} % of per-arm attempt "
                   f"time on attempts that placed nothing "
                   f"({len(d['spans']) - sum(1 for p, _ in d['spans'] if p)} "
                   f"not-placed of {len(d['spans'])}; span sum {tot:.1f} s)")
    for label, xs in (("arrival wait", d["waits"]),
                      ("handover wait", d["handover"]),
                      ("approach motion", d["approach"])):
        if xs:
            out.append(f"{label}: mean {mean(xs):.2f} s median {median(xs):.2f} "
                       f"min {min(xs):.2f} max {max(xs):.2f} (n={len(xs)})")
    if d["reseats"] is not None:
        out.append(f"re-seat rows printed: {d['reseats']}")
    if d["cycle"]:
        keys = ["prepose", "hover", "descent", "close", "grip", "lift",
                "place", "release", "return", "end"]
        n = len(d["cycle"])
        out.append(f"[cycle] rows: {n} "
                   f"(paired outcomes: {len(d['cycle_outcomes'])})")
        # A phase key is only printed on the attempts that reach it (place and
        # release exist only on attempts that put the payload on the output
        # line), so each phase is averaged over the rows that carry it.
        counts = {k: sum(1 for c in d["cycle"] if k in c) for k in keys}
        cols = {k: (sum(c[k] for c in d["cycle"] if k in c) / counts[k]
                    if counts[k] else 0.0) for k in keys}
        hand = mean(d["handover"])
        if hand:
            cols["descent"] = cols["descent"] - hand  # net of the handover wait
        out.append("phase      " + "".join(f"{k:>9}" for k in keys))
        out.append("mean (s)   " + "".join(f"{cols[k]:9.2f}" for k in keys))
        out.append("n rows     " + "".join(f"{counts[k]:9d}" for k in keys))
        tot = sum(cols.values())
        out.append("share (%) " + "".join(f"{100.0 * cols[k] / tot:9.1f}"
                                          for k in keys))
        if len(d["cycle_outcomes"]) == n:
            for want, tag in ((True, "placed   "), (False, "not plac.")):
                idx = [i for i, p in enumerate(d["cycle_outcomes"]) if p == want]
                if not idx:
                    continue
                out.append(tag + " " + "".join(
                    f"{(sum(d['cycle'][i][k] for i in idx if k in d['cycle'][i]) / max(1, sum(1 for i in idx if k in d['cycle'][i]))):9.2f}"
                    for k in keys))
        # integrity: each row's own `total=` against the sum of its segments
        worst = 0.0
        for c in d["cycle"]:
            if "total" in c:
                worst = max(worst, abs(c["total"] - sum(
                    v for k, v in c.items() if k != "total")))
        out.append(f"cycle mean-of-rows total: {mean([c.get('total', 0.0) for c in d['cycle']]):.2f} s; "
                   f"worst segment-sum vs row total: {worst:.2f} s")
    if d["policy_decisions"]:
        ticks = [t for t, _ in d["policy_decisions"]]
        dec = [x for _, x in d["policy_decisions"]]
        out.append(f"policy episodes: {len(ticks)} ticks {min(ticks)}-{max(ticks)} "
                   f"decisions {min(dec)}-{max(dec)} "
                   f"ticks/decision {sum(ticks) / sum(dec):.2f}")
    return out


DEFAULT = [
    "logs/p41/p2/accept_profile.log",       # single arm, P41 profile (shipped)
    "logs/p42/p2/seat_accept.log",          # single arm, P42 seat instrument on
    "logs/p41/p2/pear_profile.log",         # pear, P41 profile
    "logs/p42/p2/seat_pear.log",            # pear, P42 seat instrument on
    "logs/p41/p3/accept_mf30.log",          # FRUIT_FINGER_MAXFORCE=30 (not adopted)
    "logs/p41/p2/twoline_profile.log",      # two-line, default branch (current tree)
    "logs/p40/p3/regrasp2_twoline.log",     # two-line, P40 branch (pre-P41 profile)
    "logs/p39/p3/twoline_C.log",            # two-line, pre-P40 control (farthest-upstream)
    "logs/p32/A0_bed_twoline_1.log",        # bed, pre-P40/P41 (no post-P41 run)
    "logs/g/20_rate_single_1.log",          # the only [cycle]-instrumented single arm
]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--log")
    args = ap.parse_args(argv)
    paths = [args.log] if args.log else DEFAULT
    for p in paths:
        if not os.path.exists(p):
            print(f"### {p}: MISSING")
            continue
        print("\n".join(report(p)))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
