#!/usr/bin/env python3
"""P40 phase 1 - the per-phase rate census (offline; reads logs only).

Answers two questions from *existing* logs, with no simulator:

  1. where the seconds of one sorting cycle go (per phase, sim seconds and the
     share of the cycle), for the two-line / bed / dense batteries and for the
     single-arm acceptance;
  2. the retention tax: what the carried-not-placed (cnp) and no-grasp attempts
     cost, and what the same attempts would have delivered if every attempt had
     converted (the retention-free ceiling).

Usage:
    python3 logs/p40/rate_census.py                  # the batteries of RATE_CENSUS.md
    python3 logs/p40/rate_census.py --log <file>     # one log, per-attempt dump
    python3 logs/p40/rate_census.py --check          # re-assert the documented numbers

Two traps this file exists to avoid:

* `[cycle] descent=` is **not** the descent. The `descent` mark is placed after
  the wait loop *and* the approach (`tasks.py:7710` hover mark, `tasks.py:8965`
  descent mark), so that segment is `wait + descent`. The wait is the
  `[task] dynamic descent: waited N ticks` row the same attempt prints; this
  file reports it as its own row and nets it out of `descent`.
* The two-line logs **interleave the two arms** (the arms run concurrently), so
  "everything between two attempt headers" is not one attempt. The `[cycle]`
  and `[biarm] result` rows are both printed at attempt *completion*, in the
  same order, so outcomes and phases are paired positionally there. `[run]
  attempt N: ...` (single arm) is paired by its own attempt number, which is
  0-based - the `[cycle]` row of the same attempt is **1-based**.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

DT = 1.0 / 120.0  # one control tick (control.py CONTROL_DT = 1/120 s)

# --------------------------------------------------------------------------- #
# The line shapes. Every number in RATE_CENSUS.md comes through one of these.
# --------------------------------------------------------------------------- #
CYCLE = re.compile(
    r"\[cycle\] attempt (?P<att>\d+): (?P<segs>[a-z0-9_=\.s ]+?) total=(?P<total>[\d.]+)s"
)
SEG = re.compile(r"(?P<name>[a-z0-9_]+)=(?P<val>[\d.]+)s")
WAITED = re.compile(r"\[task\] dynamic descent: waited (?P<ticks>\d+) ticks")
ARRIVAL = re.compile(r"\[task\] fruit at pick point:.*? after (?P<steps>\d+) steps")
PREPOSE = re.compile(r"\[task\] at pick pose after (?P<sec>[\d.]+) s")
APPROACH = re.compile(r"\[motion\] approach\(cartesian\): (?P<cm>[\d.]+) cm, (?P<n>\d+) samples")
CARRY = re.compile(r"\[motion\] carry (?P<leg>[a-z0-9_]+): (?P<cm>[\d.]+) cm, (?P<ticks>\d+) ticks")
CLOSE = re.compile(r"\[task\] dynamic close: sustained contact after (?P<ticks>\d+) ticks")
PLACELOW = re.compile(r"\[task\] place low: .*? (?P<ticks>\d+) ticks")
RUN_START = re.compile(r"\[run\] attempt (?P<att>\d+)(?: \((?P<arm>\w+)\))?: picking ")
RUN_SUM = re.compile(
    r"\[run\] attempt (?P<att>\d+)(?: \((?P<arm>\w+)\))?: grasped=(?P<g>\w+) "
    r"placed=(?P<p>\w+) lift=(?P<lift>[+-][\d.]+) m force=(?P<f>[\d.]+) N"
    r"(?: notes=\[(?P<notes>.*?)\])?(?: sim=(?P<span>[\d.]+)s| sim=(?P<sim0>[\d.]+)-(?P<sim1>[\d.]+)s)?"
)
BIARM_RESULT = re.compile(
    r"\[biarm\] result (?P<arm>\w+) index=(?P<idx>\d+) (?P<fruit>\w+) "
    r"grasped=(?P<g>\w+) placed=(?P<p>\w+) lift=(?P<lift>[+-][\d.]+) "
    r"force=(?P<f>[\d.]+) sim=(?P<span>[\d.]+)s(?: notes=\[(?P<notes>.*?)\])?"
)
STATS = re.compile(
    r"\[stats\] attempts=(?P<n>\d+) successes=(?P<s>\d+).*?sim=(?P<sim>[\d.]+)s total, "
    r"(?P<per>[\d.]+)s/attempt"
)
BIARM_BATCH = re.compile(
    r"\[biarm\] .*?(?P<n>\d+) attempts, (?P<s>\d+) successes, (?P<sim>[\d.]+)s sim span, "
    r"(?P<per>[\d.]+)s/attempt, (?P<per_success>[\d.]+)s/success, (?P<rate>[\d.]+) fruits/min"
)

#: The phase order the `[cycle]` marks produce (tasks.py `_cycle_mark` call
#: sites). `wait` is added by this file, not by the code.
PHASES = ["prepose", "hover", "wait", "descent", "close", "grip",
          "lift", "place", "release", "return", "end"]


def t(n: int | None) -> float | None:
    return None if n is None else float(n) * DT


# --------------------------------------------------------------------------- #
class Log:
    def __init__(self, path: str):
        self.path = path
        self.cycle: list[dict] = []          # file order (= completion order)
        self.waits: list[int] = []           # file order
        self.arrivals: list[int] = []        # `fruit at pick point ... after N steps`
        self.biarm: list[dict] = []          # file order (= completion order)
        self.runs: dict[int, dict] = {}      # single-arm, keyed by attempt number
        self.legs: dict[str, list[int]] = {} # leg name -> ticks, per attempt
        self.preposes: list[float] = []
        self.approaches: list[int] = []
        self.closes: list[int] = []
        self.place_lows: list[int] = []
        self.stats: dict | None = None
        self.batch: dict | None = None

    # -- outcome rows ------------------------------------------------------ #
    @property
    def two_line(self) -> bool:
        return bool(self.biarm)

    def outcomes(self) -> list[dict]:
        """One row per attempt: {arm, fruit, grasped, placed, span, force, notes}."""
        if self.two_line:
            return [
                {
                    "att": i,
                    "arm": r["arm"],
                    "fruit": r["fruit"],
                    "grasped": r["g"] == "True",
                    "placed": r["p"] == "True",
                    "span": float(r["span"]),
                    "force": float(r["f"]),
                    "notes": r["notes"] or "",
                }
                for i, r in enumerate(self.biarm)
            ]
        out = []
        for att in sorted(self.runs):
            r = self.runs[att]
            if "g" not in r or "p" not in r:
                continue  # a start row with no summary (truncated tail)
            out.append(
                {
                    "att": att,
                    "arm": r.get("arm", ""),
                    "fruit": r.get("fruit", ""),
                    "grasped": r["g"] == "True",
                    "placed": r["p"] == "True",
                    "span": float(r["span"]) if r.get("span") else None,
                    "force": float(r["f"]),
                    "notes": r.get("notes") or "",
                }
            )
        return out


def kind(row: dict) -> str:
    if row["placed"]:
        return "placed"
    if row["grasped"]:
        return "cnp"
    return "no-grasp"


def parse(path: str) -> Log:
    log = Log(path)
    leg_rows: dict[str, list[int]] = {}
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if "[fruit]" not in line:
                continue
            m = CYCLE.search(line)
            if m:
                segs = {s.group("name"): float(s.group("val")) for s in SEG.finditer(m.group("segs"))}
                segs["_total"] = float(m.group("total"))
                log.cycle.append(segs)
                continue
            m = BIARM_RESULT.search(line)
            if m:
                log.biarm.append(m.groupdict())
                continue
            m = RUN_SUM.search(line)
            if m:
                d = m.groupdict()
                if d.get("span") is None and d.get("sim0") is not None:
                    # the single-arm path prints the attempt as a *range*
                    # `sim=7.3-22.9s`; its span is the difference.
                    d["span"] = f"{float(d['sim1']) - float(d['sim0']):.1f}"
                log.runs[int(d["att"])] = d
                continue
            m = RUN_START.search(line)
            if m:
                att = int(m.group("att"))
                word = line.split("picking ", 1)[1].split()
                log.runs.setdefault(att, {})["fruit"] = word[0] if word else ""
                log.runs[att]["arm"] = m.group("arm") or ""
                continue
            m = WAITED.search(line)
            if m:
                log.waits.append(int(m.group("ticks")))
                continue
            m = ARRIVAL.search(line)
            if m:
                log.arrivals.append(int(m.group("steps")))
                continue
            m = PREPOSE.search(line)
            if m:
                log.preposes.append(float(m.group("sec")))
                continue
            m = APPROACH.search(line)
            if m:
                log.approaches.append(int(m.group("n")))
                continue
            m = CARRY.search(line)
            if m:
                leg_rows.setdefault(m.group("leg"), []).append(int(m.group("ticks")))
                continue
            m = CLOSE.search(line)
            if m:
                log.closes.append(int(m.group("ticks")))
                continue
            m = PLACELOW.search(line)
            if m:
                log.place_lows.append(int(m.group("ticks")))
                continue
            m = STATS.search(line)
            if m:
                log.stats = m.groupdict()
                continue
            m = BIARM_BATCH.search(line)
            if m:
                log.batch = m.groupdict()
                continue
    log.legs = leg_rows
    return log


# --------------------------------------------------------------------------- #
def mean(values) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def pair_cycles(log: Log) -> tuple[list[dict], list[dict], float]:
    """Pair each `[cycle]` row with its outcome row; return (cycles, outcomes, max|d|).

    Both rows are printed at attempt *completion* in the same order, so the
    pairing is positional. It is *checked*: the `[cycle]` total and the
    outcome's `sim=` span are the same interval measured two ways, so any
    pairing error shows up as a large |difference|. The function returns the
    worst one so `--check` can assert it.
    """
    rows = log.outcomes()
    worst = 0.0
    cycles, outs = [], []
    for i, cyc in enumerate(log.cycle):
        if i >= len(rows) or not rows[i]["span"]:
            continue
        worst = max(worst, abs(cyc["_total"] - rows[i]["span"]))
        cycles.append(cyc)
        outs.append(rows[i])
    return cycles, outs, worst


def _phase_means(cycles: list[dict], wait: float | None) -> dict[str, float]:
    sums: dict[str, float] = {}
    for p in PHASES:
        vals = [c[p] for c in cycles if p in c]
        if vals:
            sums[p] = sum(vals) / len(vals)
    if wait is not None and "descent" in sums:
        sums["descent"] = max(0.0, sums["descent"] - wait)
        sums["wait"] = wait
    return sums


def cycle_table(log: Log, label: str) -> list[str]:
    """The `[cycle]` table, split into placed / not-placed attempts.

    The split matters: a failing attempt pays the regrasp/probe retries inside
    the `grip` segment, so the *all* column's `grip` is not the cost of a
    healthy cycle.
    """
    cycles, outs, worst = pair_cycles(log)
    if not cycles:
        return []
    wait = mean([t(w) for w in log.waits]) if log.waits else None
    ok = [c for c, o in zip(cycles, outs) if o["placed"]]
    bad = [c for c, o in zip(cycles, outs) if not o["placed"]]
    cols = [("all", cycles), ("placed only", ok), ("not placed", bad)]
    means = {name: _phase_means(sub, wait) for name, sub in cols if sub}
    grand = {name: sum(c["_total"] for c in sub) for name, sub in cols if sub}
    out = [f"\n#### {label} - `[cycle]` decomposition "
           f"(all n={len(cycles)}, placed n={len(ok)}, not placed n={len(bad)}; "
           f"max |cycle total - sim span| = {worst:.2f} s)", "",
           "| phase | all (s) | share | placed only (s) | not placed (s) |",
           "| --- | --- | --- | --- | --- |"]
    for p in PHASES:
        if p not in means["all"]:
            continue
        cells = " | ".join(f"{means[k][p]:.2f}" if k in means and p in means[k] else " - "
                           for k in ("all", "placed only", "not placed"))
        out.append(f"| {p} | {cells} | {100.0 * means['all'][p] * len(cycles) / grand['all']:.1f} % |")
    out.append("| **total** | " + " | ".join(f"**{grand[k] / len([c for n, sub in cols if n == k for c in sub]):.2f}**"
                                             if k in grand else " - " for k in ("all", "placed only", "not placed"))
               + " | 100 % |")
    return out


def derived_table(log: Log, label: str, spans: list[float]) -> list[str]:
    """No `[cycle]` marks: derive the phases from the leg rows + the attempt span."""
    if log.cycle or not spans:
        return []
    mean_span = sum(spans) / len(spans)
    rows = []
    if log.preposes:
        rows.append(("prepose", "`[task] at pick pose after X s`", mean(log.preposes)))
    if log.waits:
        rows.append(("wait", "`[task] dynamic descent: waited N ticks`", mean([t(w) for w in log.waits])))
    if log.approaches:
        rows.append(("descent", "`[motion] approach(cartesian) N samples`", mean([t(a) for a in log.approaches])))
    if log.closes:
        rows.append(("close ramp", "`[task] dynamic close: N ticks`", mean([t(c) for c in log.closes])))
    if log.legs.get("grasp_lift"):
        rows.append(("lift", "`[motion] carry grasp_lift N ticks`", mean([t(v) for v in log.legs["grasp_lift"]])))
    place = [v for k, vals in log.legs.items() if k.startswith("place") for v in vals]
    if place:
        rows.append(("place", "`[motion] carry placeN N ticks`", mean([t(v) for v in place])))
    if log.place_lows:
        rows.append(("release", "`[task] place low: N ticks`", mean([t(v) for v in log.place_lows])))
    known = sum(r[2] for r in rows)
    out = [f"\n#### {label} - derived ({len(spans)} attempts, no `[cycle]` marks)", "",
           "| phase | source row | sim s (mean) | share |", "| --- | --- | --- | --- |"]
    for name, src, val in rows:
        out.append(f"| {name} | {src} | {val:.2f} | {100.0 * val / mean_span:.1f} % |")
    out.append(f"| **unattributed** | span - the rows above (hover/settle/release-fall/return) "
               f"| **{mean_span - known:.2f}** | {100.0 * (mean_span - known) / mean_span:.1f} % |")
    out.append(f"| **total** | `[run] ... sim=X s` | **{mean_span:.2f}** | 100 % |")
    return out


def descent_block(log: Log, label: str) -> list[str]:
    """What the `descent` segment is made of: arrival wait, handover wait, motion.

    The segment is `hover mark -> descent mark` (`tasks.py:7710` -> `tasks.py:8965`)
    and therefore contains three separate waits plus one motion leg. Splitting it
    is the point of this table: the motion is ~0.75 s and the rest is waiting.
    """
    if not log.cycle or not log.arrivals:
        return []
    n = len(log.cycle)
    desc = mean([c["descent"] for c in log.cycle if "descent" in c])
    wait = mean([t(w) for w in log.waits]) if log.waits else 0.0
    arrival = mean([t(a) for a in log.arrivals])
    approach = mean([t(a) for a in log.approaches]) if log.approaches else 0.0
    rest = desc - wait - arrival - approach
    out = [f"\n#### {label} - inside the `descent` segment", "",
           "| sub-block | source row | sim s | of the segment |", "| --- | --- | --- | --- |"]
    for name, src, val in (
        ("arrival wait", "`fruit at pick point ... after N steps`", arrival),
        ("handover wait", "`dynamic descent: waited N ticks`", wait),
        ("approach motion", "`approach(cartesian) N samples`", approach),
        ("track/axis/settle", "remainder", rest),
    ):
        out.append(f"| {name} | {src} | {val:.2f} | {100.0 * val / desc:.0f} % |")
    out.append(f"| **segment total** | `[cycle] descent=` | **{desc:.2f}** | 100 % |")
    return out


def retention_table(log: Log, label: str) -> list[str]:
    rows = log.outcomes()
    if not rows:
        return []
    # Older trees print `[run] attempt N: …` with no `sim=` span. The battery's
    # own `[stats] … X s/attempt` is the same quantity, so it is used as the
    # per-attempt span for those rows (and the table says so).
    filled = 0
    for r in rows:
        if not r["span"] and log.stats:
            r["span"] = float(log.stats["per"])
            filled += 1
    rows = [r for r in rows if r["span"]]
    note = (f"  *(per-attempt spans from `[stats] {log.stats['per']} s/attempt`: "
            f"{filled} of {len(rows)} rows carry no `sim=` field on this tree)*"
            if filled else "")
    n = len(rows)
    # The denominator is the battery's own sim span: on the two-line the two arms
    # work *concurrently*, so the sum of the per-attempt spans is ~2x the wall
    # (sim) span and dividing by it would halve the rate. `[stats] sim=X s total`
    # is the batch span and reproduces the log's own `fruits/min`.
    sum_span = sum(r["span"] for r in rows)
    span = float(log.stats["sim"]) if log.stats else sum_span
    mins = span / 60.0
    groups = {"placed": [], "cnp": [], "no-grasp": []}
    for r in rows:
        groups[kind(r)].append(r)
    placed = len(groups["placed"])
    rate = placed / mins
    ceiling = n / mins
    lost = sum(r["span"] for k in ("cnp", "no-grasp") for r in groups[k])
    lost_share = 100.0 * lost / max(sum_span, 1e-9)
    out = [f"\n#### {label} - retention", "",
           note] if note else [f"\n#### {label} - retention", ""]
    out += [
           f"* attempts **{n}**, placed **{placed}** ({100.0 * placed / n:.0f} %), "
           f"cnp **{len(groups['cnp'])}**, no-grasp **{len(groups['no-grasp'])}**",
           f"* sim span **{span:.1f} s** ({mins:.2f} min"
           + (f"; the {n} attempt spans sum to {sum_span:.1f} s because both arms run concurrently"
              if abs(sum_span - span) > 0.05 * span else "")
           + f") -> **{rate:.2f} placed/min**",
           f"* retention-free ceiling (every attempt converts in the same span): "
           f"**{ceiling:.2f} placed/min** ({ceiling - rate:+.2f})",
           f"* sim seconds on attempts that placed nothing: **{lost:.1f} s** "
           f"({lost_share:.1f} % of the per-arm attempt time)"]
    for k in ("cnp", "no-grasp"):
        vals = [r["span"] for r in groups[k]]
        if vals:
            out.append(f"* {k}: n={len(vals)}, mean **{sum(vals) / len(vals):.1f} s**, "
                       f"{sum(vals):.1f} s total")
    return out


def arm_table(log: Log, label: str) -> list[str]:
    rows = [r for r in log.outcomes() if r["arm"] and r["span"]]
    if len({r["arm"] for r in rows}) < 2:
        return []
    out = [f"\n#### {label} - per arm", "",
           "| arm | attempts | placed | cnp | no-grasp | mean span s |", "| --- | --- | --- | --- | --- | --- |"]
    for arm in sorted({r["arm"] for r in rows}):
        sub = [r for r in rows if r["arm"] == arm]
        out.append(f"| {arm} | {len(sub)} | {sum(1 for r in sub if r['placed'])} | "
                   f"{sum(1 for r in sub if kind(r) == 'cnp')} | "
                   f"{sum(1 for r in sub if kind(r) == 'no-grasp')} | "
                   f"{sum(r['span'] for r in sub) / len(sub):.1f} |")
    return out


# --------------------------------------------------------------------------- #
BATTERIES = [
    ("two-line, P39 control", "logs/p39/p3/twoline_C.log"),
    ("two-line, P32 bed A0", "logs/p32/A0_bed_twoline_1.log"),
    ("two-line, W7-A dense", "logs/w7/10_dense_twoline_1.log"),
    ("single arm, P39 acceptance C", "logs/p39/p3/accept_C.log"),
    ("single arm, P39 pear battery C", "logs/p39/p3/pear_C.log"),
    ("single arm, Gate-19 reference", "logs/g/20_rate_single_1.log"),
    ("single arm, pre-Gate-19 reference", "logs/biarm/rate_single_1.log"),
]


def report(label: str, path: str, verbose: bool = False) -> list[str]:
    if not os.path.exists(path):
        return [f"\n## {label}\n\n**MISSING** `{path}`"]
    log = parse(path)
    out = [f"\n## {label}  (`{path}`)"]
    if log.stats:
        out.append(f"* `[stats]`: {log.stats['n']} attempts, {log.stats['s']} successes, "
                   f"{log.stats['sim']} s span, {log.stats['per']} s/attempt")
    if log.batch:
        out.append(f"* `[biarm]`: {log.batch['n']} attempts, {log.batch['s']} successes, "
                   f"{log.batch['sim']} s span, {log.batch['per']} s/attempt, "
                   f"{log.batch['rate']} placed/min")
    spans = [r["span"] for r in log.outcomes() if r["span"]]
    out += cycle_table(log, label) or derived_table(log, label, spans)
    out += descent_block(log, label)
    out += retention_table(log, label)
    out += arm_table(log, label)
    if verbose:
        out.append("\n#### per attempt")
        for i, r in enumerate(log.outcomes()):
            cyc = log.cycle[i] if i < len(log.cycle) else {}
            out.append(f"* {i:2d} {r['arm']:5s} {r['fruit']:10s} {kind(r):9s} "
                       f"span={r['span']:.1f} force={r['force']:.2f} "
                       f"wait={t(log.waits[i]) if i < len(log.waits) else None} "
                       f"cycle={ {k: v for k, v in cyc.items() if k != '_total'} }")
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if os.path.basename(os.getcwd()) != os.path.basename(root):
        os.chdir(root)

    if args.log:
        print("\n".join(report(os.path.basename(args.log), args.log, verbose=True)))
        return 0
    for label, path in BATTERIES:
        print("\n".join(report(label, path)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
