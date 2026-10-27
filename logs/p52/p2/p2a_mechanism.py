"""P52 phase 2 lane A: the paired mechanism read (T0 vs TG).

    python3 logs/p52/p2/p2a_mechanism.py [--dir logs/p52/p2 --a A --b B]

A = T0 (the shipped direct env) · B = TG (`FRUIT_POLICY_TIME_SCALE=1.5
FRUIT_POLICY_RETIME_GATE=1`).

`p2a_report.py` answers the pre-registered endpoints. This tool answers the
**mechanism** question the endpoints cannot: the re-timing's total effect is a
sum of two parts, and they live in different phases of the episode -

    ticks = decision  +  (ticks - decision)
             ^policy       ^scripted primitive + finalisation

so a *paired* per-episode split says where the saved ticks came from. Pairs are
same run + same episode index + **placed in both arms**; the episode's fruit is
the same whenever the two arms' spawn set did not diverge, and the script reports
how many pairs keep the same (species, diameter) so the reader can see how much
of the pairing is exact.

Nothing here is a rate: every number is a count or a tick count on one arm pair
of a non-reproducible loop (AGENTS.md section 3b).
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import statistics as st

EPISODE = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(-?\d+) arm=(\w+) "
    r"success=(\w+) grasped=(\w+) placed=(\w+) ticks=(\d+)(?: decision=(\d+))?"
)


RETIME = re.compile(
    r"\[retime\] episode (\d+): s=([0-9.]+) gate=(\d+) decisions=(\d+) gated=(\d+)"
)


def load(directory: str, label: str) -> dict[int, list[dict]]:
    runs: dict[int, list[dict]] = {}
    for path in sorted(glob.glob(os.path.join(directory, f"{label}_[0-9].log"))):
        run = int(os.path.basename(path)[:-4].rsplit("_", 1)[1])
        rows = []
        for line in open(path, encoding="utf-8", errors="ignore"):
            gate = RETIME.search(line)
            if gate:
                rows.append({"retime": True,
                             "decisions": int(gate.group(4)),
                             "gated": int(gate.group(5))})
                continue
            found = EPISODE.search(line)
            if not found:
                continue
            rows.append(
                {
                    "retime": False,
                    "index": int(found.group(1)),
                    "category": found.group(2),
                    "diameter": float(found.group(3)),
                    "arm": found.group(5),
                    "placed": found.group(8) == "True",
                    "ticks": int(found.group(9)),
                    "decision": int(found.group(10)) if found.group(10) else None,
                }
            )
        runs[run] = rows
    return runs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="logs/p52/p2")
    ap.add_argument("--a", default="A")
    ap.add_argument("--b", default="B")
    ap.add_argument("--a-name", default="T0")
    ap.add_argument("--b-name", default="TG")
    args = ap.parse_args()

    arms = {args.a: load(args.dir, args.a), args.b: load(args.dir, args.b)}
    runs = sorted(set(arms[args.a]) & set(arms[args.b]))
    names = {args.a: args.a_name, args.b: args.b_name}
    print("=" * 78)
    print(f"P52 lane A mechanism: the episode is policy phase + scripted phase")
    print("=" * 78)

    for label in (args.a, args.b):
        rows = [r for run in runs for r in arms[label][run]
                if r.get("placed") and not r.get("retime")]
        pol = [r["decision"] for r in rows if r["decision"]]
        tot = [r["ticks"] for r in rows]
        scr = [r["ticks"] - r["decision"] for r in rows if r["decision"]]
        print(f"  {names[label]}: placed n={len(rows)}  "
              f"ticks mean {st.mean(tot):.1f} median {st.median(tot):.0f} | "
              f"policy mean {st.mean(pol):.1f} | scripted mean {st.mean(scr):.1f}")

    print()
    print("  paired placed episodes (same run + index, placed in both arms):")
    pairs = []
    for run in runs:
        index_a = {r["index"]: r for r in arms[args.a][run] if not r.get("retime")}
        index_b = {r["index"]: r for r in arms[args.b][run] if not r.get("retime")}
        for index in sorted(set(index_a) & set(index_b)):
            ra, rb = index_a[index], index_b[index]
            if not (ra["placed"] and rb["placed"]):
                continue
            same = (ra["category"], ra["diameter"]) == (rb["category"], rb["diameter"])
            pairs.append((run, index, ra, rb, same))
    print(f"    n pairs = {len(pairs)}  "
          f"same (species, diameter) = {sum(1 for p in pairs if p[4])}")
    if pairs:
        dt = [p[3]["ticks"] - p[2]["ticks"] for p in pairs]
        dp = [p[3]["decision"] - p[2]["decision"] for p in pairs]
        ds = [(p[3]["ticks"] - p[3]["decision"]) - (p[2]["ticks"] - p[2]["decision"])
              for p in pairs]
        base = st.mean([p[2]["ticks"] for p in pairs])

        def spread(values: list[float]) -> str:
            sd = st.pstdev(values) if len(values) > 1 else 0.0
            sem = sd / max(1.0, len(values) ** 0.5)
            return f"sd {sd:.1f} sem {sem:.1f}"

        for label, values in (("ticks (total)", dt), ("policy phase", dp),
                              ("scripted phase", ds)):
            print(f"    {label:16s} mean {st.mean(values):+8.1f}  "
                  f"median {st.median(values):+6.0f}  {spread(values)}  "
                  f"n<0 {sum(1 for v in values if v < 0)}/{len(values)}  "
                  f"({st.mean(values) / base:+.1%} of {names[args.a]}'s "
                  f"placed-episode ticks)")
        exact = [p for p in pairs if p[4]]
        if exact:
            de = [p[3]["ticks"] - p[2]["ticks"] for p in exact]
            print(f"    same-fruit subset (n={len(exact)}): "
                  f"total {st.mean(de):+.1f} ticks ({spread(de)}), "
                  f"policy {st.mean([p[3]['decision'] - p[2]['decision'] for p in exact]):+.1f} "
                  f"ticks  [no power at this n - the sd of a single pair is ~70 ticks]")

    # ---- the arithmetic the measurement is checked against ---------------- #
    print()
    print("  The arithmetic (all inputs measured, no free parameters):")
    for label in (args.a, args.b):
        rows = [r for run in runs for r in arms[label][run]
                if r.get("placed") and not r.get("retime")]
        pol = [r["decision"] for r in rows if r["decision"]]
        tot = [r["ticks"] for r in rows]
        if pol and tot:
            share = st.median(pol) / st.median(tot)
            print(f"    {names[label]}: the policy phase is {share:.1%} of a placed "
                  f"episode ({st.median(pol):.0f}/{st.median(tot):.0f} ticks)")
    rows = [r for run in runs for r in arms[args.a][run]
            if r.get("placed") and not r.get("retime")]
    pol_a = [r["decision"] for r in rows if r["decision"]]
    tot_a = [r["ticks"] for r in rows]
    gated = None
    retime = [row for run in runs for row in arms[args.b][run] if row.get("retime")]
    if retime:
        dec = sum(r["decisions"] for r in retime)
        gat = sum(r["gated"] for r in retime)
        gated = gat / dec if dec else None
    if pol_a and tot_a and gated is not None:
        ceiling = st.median(pol_a) * (1.0 - 1.0 / 1.5)          # a 1.5x on the whole phase
        expected = ceiling * (1.0 - gated)                     # only the ungated share moves
        print(f"    a 1.5x on the WHOLE policy phase could save at most "
              f"{ceiling:.0f} ticks = {ceiling / st.median(tot_a):.1%} of the episode")
        print(f"    with the gate at {gated:.1%} duty, the ungated "
              f"{(1 - gated):.0%} can move -> {expected:.0f} ticks "
              f"= {expected / st.median(tot_a):.1%}")
        print(f"    the pre-registered bar was 8 % = {0.08 * st.median(tot_a):.0f} ticks: "
              f"{'reachable' if ceiling >= 0.08 * st.median(tot_a) else 'UNREACHABLE by construction'}")

    print()
    print("  Reading: the time-scale can only touch the *policy phase*, and that")
    print("  phase is a rendezvous with a 0.120 m/s belt (its floor is 2.08-2.23 s).")
    print("  The scripted primitive owns the rest of the episode and is not a policy")
    print("  lever at all - so a policy-side speed-up is bounded by the policy share.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
