#!/usr/bin/env python3
"""P38 phase 2: the lateral-refusal harness report (the attribution endpoint).

    python3 logs/p38/p2_report.py --m12 logs/p38/P2 --m3 logs/p38/P3
    python3 logs/p38/p2_report.py --self-test

Read-only. Parses the `M1_*.log` / `M2_*.log` / `M3_*.log` written by
`scripts/225_p38_batch.sh` and prints the pre-registered analysis of
`logs/p38/PREREG.md` + `logs/p38/PREREG_A1.md` (the Gate-1 amendment; where
they disagree the amendment governs).

**The endpoint is attribution, never elimination.** `no firable fruit` is a
named *failure* (`success=False`) and stays in the rate denominator
(`PREREG_A1.md` A1/A5); an episode the lever ends early is not a pass.

Sections
--------
**M1** (the forced band, arms A/B/C, 15 episodes each) - deterministic counts:
P1 attribution (the `lateral refuse:` note), P3 (the terminal class instead of
the 1500-tick timeout), the reseed boundedness (0 adopted / 4 scans), the
policy-close count (the second fire path, `direct_fire` - A1's measured
closure), and Fb' (an **intercept** fire in arm C).

**M2** (the mixed band, A/C x 3 seeds) - the conversion: the refused episodes
(A: the diag note; C: the first candidate refused) that fire, paired by
`(seed, episode)` **only if** the per-episode `(arm, category)` agreement is
100 % (A4); otherwise the unpaired Fisher exact. The McNemar exact test is
one-sided in the lever's direction.

**M3** (the shipped patch band, A/C x 5 seeds) - the safety endpoints in the
A3/A5 forms: right-arm placed non-inferiority gated on **run-level unanimity**
(fail iff all five per-pair deltas are negative *and* the pooled delta is
<= -0.10), the pooled delta with a Newcombe hybrid-score interval, the
note-level failure-reason sets with the attribution notes mapped to the single
class `lateral-refuse` (symmetric: an arm-only key either way fails), and the
**fired-only** cycle (the `no firable fruit` episodes are excluded from the
median and reported separately).

**G2** (`--g2`, the Gate-2 reruns, `logs/p38/G2/`) - **descriptive only, no new
endpoint**: the **DIAG=0/1 pair** on the M1 band (class counts, per-episode
agreement, and the DIAG=1-vs-DIAG=1 repeat beside it as the loop's own noise),
and the `[refuse] close: tick= dy=` rows that scope the END's closure (a close
latching after the fruit's departure is `PREREG_A1.md` falsifier #1).

Every table carries its own n; no rate is quoted across scenarios (M1/M2 are
probes, `PREREG.md` section 7).
"""
from __future__ import annotations

import argparse
import ast
import math
import os
import re
import statistics
from collections import Counter

RESULT = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(-?\d) arm=(\w+) "
    r"success=(\w+) grasped=(\w+) placed=(\w+) ticks=(\d+) decision=(\d+) "
    r"reward=([-+0-9.eE]+) notes=(\[.*\]) presentation"
)
REFUSE_LINE = re.compile(r"\[rl\] refuse: (.*)")
TRIGGER_LINE = re.compile(r"\[rl\] (trigger=.*)")
ROLLUP = re.compile(r"\[rl\] rollout success (\d+)/(\d+)")
REFUSE_ROW = re.compile(
    r"\[refuse\] episode (\d+): refusals=(\d+) adopted=(\d+) scans=(\d+) "
    r"empty=(\d+) off=(\d+) budget_left=(\d+) policy_close_seen=(\d+) "
    r"no_firable=(\d+)"
)
CLOSE_ROW = re.compile(r"\[refuse\] close: tick=(\d+) dy=([-+0-9.]+) m")

ATTR_PREFIXES = ("lateral refuse:", "reseed:", "no firable fruit:")
ATTR_KEY = "lateral-refuse"


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
def split_notes(notes) -> list[str]:
    """The episode's notes as a list of items (the printed list repr)."""
    if isinstance(notes, list):
        return [str(n) for n in notes]
    try:
        value = ast.literal_eval(notes)
    except (ValueError, SyntaxError):
        return [str(notes)]
    return [str(v) for v in value] if isinstance(value, list) else [str(value)]


def parse_log(path: str) -> dict:
    """One run's episodes + the interface lines (trigger / refuse / rollup)."""
    out = {"path": path, "episodes": [], "trigger": "", "refuse": "", "rollup": "",
           "rows": {}, "closes": []}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = CLOSE_ROW.search(line)
            if m:
                out["closes"].append({"tick": int(m.group(1)),
                                      "dy": float(m.group(2))})
                continue
            m = REFUSE_ROW.search(line)
            if m:
                out["rows"][int(m.group(1))] = {
                    "refusals": int(m.group(2)),
                    "adopted": int(m.group(3)),
                    "scans": int(m.group(4)),
                    "empty": int(m.group(5)),
                    "off": int(m.group(6)),
                    "budget_left": int(m.group(7)),
                    "policy_close_seen": int(m.group(8)) == 1,
                    "no_firable": int(m.group(9)) == 1,
                }
                continue
            m = RESULT.search(line)
            if m:
                out["episodes"].append(
                    {
                        "index": int(m.group(1)),
                        "category": m.group(2),
                        "bin": int(m.group(4)),
                        "arm": m.group(5),
                        "success": m.group(6) == "True",
                        "grasped": m.group(7) == "True",
                        "placed": m.group(8) == "True",
                        "ticks": int(m.group(9)),
                        "decision": int(m.group(10)),
                        "notes": split_notes(m.group(12)),
                    }
                )
                continue
            m = REFUSE_LINE.search(line)
            if m and not out["refuse"]:
                out["refuse"] = m.group(1).strip()
                continue
            m = TRIGGER_LINE.search(line)
            if m and not out["trigger"]:
                out["trigger"] = m.group(1).strip()
                continue
            m = ROLLUP.search(line)
            if m:
                out["rollup"] = f"{m.group(1)}/{m.group(2)}"
    for ep in out["episodes"]:
        ep["row"] = out["rows"].get(ep["index"], {})
    return out


def notes_matching(ep: dict, *needles: str) -> list[str]:
    return [n for n in ep["notes"] if any(k in n for k in needles)]


def is_refused(ep: dict) -> bool:
    return bool(notes_matching(ep, "lateral refuse:"))


def is_no_firable(ep: dict) -> bool:
    return bool(notes_matching(ep, "no firable fruit:"))


def is_timeout(ep: dict) -> bool:
    return bool(notes_matching(ep, "timeout:"))


def is_policy_close(ep: dict) -> bool:
    return bool(notes_matching(ep, "policy closed on the fruit", "expert closed"))


def is_intercept(ep: dict) -> bool:
    return bool(notes_matching(ep, "intercept trigger", "presented intercept"))


def fired(ep: dict) -> bool:
    """Did the scripted primitive run? (either fire path, or a policy close)"""
    return bool(is_intercept(ep) or is_policy_close(ep) or ep["grasped"]
                or ep["placed"] or notes_matching(ep, "timeout:") == [] and ep["ticks"] < 1500 * 4)


def adoptions(ep: dict) -> tuple[int, int]:
    """(adopted, scans) from the reseed notes."""
    adopted = len(notes_matching(ep, "reseed: adopted"))
    scans = 0
    for note in notes_matching(ep, "reseed:"):
        m = re.search(r"in (\d+) scan", note)
        if m:
            scans += int(m.group(1))
    return adopted, scans


# --------------------------------------------------------------------------- #
# exact statistics (no scipy in this environment)
# --------------------------------------------------------------------------- #
def _log_comb(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def binom_cdf(k: int, n: int, p: float = 0.5) -> float:
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return sum(math.exp(_log_comb(n, i) + i * math.log(p) + (n - i) * math.log1p(-p))
               for i in range(k + 1))


def mcnemar_exact(b: int, c: int, one_sided_direction: str = "greater") -> tuple[float, float]:
    """Exact McNemar. `b` = discordant in the lever's favour, `c` = against.

    Returns (one-sided p in the lever's direction, two-sided p).
    """
    n = b + c
    if n == 0:
        return 1.0, 1.0
    upper = 1.0 - binom_cdf(b - 1, n)
    lower = binom_cdf(b, n)
    one = upper if one_sided_direction == "greater" else lower
    two = min(1.0, 2.0 * min(upper, lower))
    return one, two


def fisher_exact(a: int, b: int, c: int, d: int, one_sided: str = "greater") -> float:
    """One-sided Fisher exact for [[a, b], [c, d]] (a = converted/refused)."""
    n1, n2 = a + b, c + d
    total = n1 + n2
    row = a + c
    rows = range(0, min(n1, row) + 1)
    def prob(x: int) -> float:
        return math.exp(
            _log_comb(row, x) + _log_comb(total - row, n1 - x) - _log_comb(total, n1)
        )
    observed = prob(a)
    if one_sided == "greater":
        p = sum(prob(x) for x in rows if x >= a and prob(x) <= observed + 1e-12)
        p = sum(prob(x) for x in rows if x >= a)
    else:
        p = sum(prob(x) for x in rows if x <= a)
    return min(1.0, p)


def sign_test(pos: int, neg: int) -> float:
    """One-sided sign test p for "more negatives than positives" (harm)."""
    n = pos + neg
    if n == 0:
        return 1.0
    return 1.0 - binom_cdf(neg - 1, n)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def newcombe_diff(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float]:
    """Newcombe hybrid-score interval for p2 - p1 (method 10)."""
    p1, p2 = (k1 / n1 if n1 else 0.0), (k2 / n2 if n2 else 0.0)
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p2 - p1
    lo = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return lo, hi


# --------------------------------------------------------------------------- #
# reporting helpers
# --------------------------------------------------------------------------- #
def rate(k: int, n: int) -> str:
    return f"{k}/{n} ({k / n:.0%})" if n else "0/0 (-)"


def median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else float("nan")


def reason_set(episodes: list[dict]) -> set[str]:
    """The note-level failure-reason set, attribution mapped to one class.

    `PREREG_A1.md` A5: each note item is one key, digit-normalised; the three
    attribution notes reduce to `lateral-refuse`; a success contributes nothing.
    """
    keys: set[str] = set()
    for ep in episodes:
        if ep["success"]:
            continue
        items = ep["notes"] or ["empty note"]
        for note in items:
            if any(note.startswith(p) or p in note for p in ATTR_PREFIXES):
                keys.add(ATTR_KEY)
                continue
            keys.add(re.sub(r"[-+0-9.]+", "#", note))
    return keys


def load_dir(path: str, prefix: str) -> dict[str, dict]:
    out = {}
    if not os.path.isdir(path):
        return out
    for name in sorted(os.listdir(path)):
        if not name.startswith(prefix) or not name.endswith(".log"):
            continue
        label = name[: -len(".log")]
        out[label] = parse_log(os.path.join(path, name))
    return out


# --------------------------------------------------------------------------- #
# M1
# --------------------------------------------------------------------------- #
def report_m1(runs: dict[str, dict]) -> dict:
    print("=" * 78)
    print("M1 - the forced refusal (lateral 0): attribution, the terminal class, the bound")
    print("=" * 78)
    table = {}
    for arm in ("A", "B", "C"):
        run = runs.get(f"M1_{arm}")
        if not run:
            print(f"  arm {arm}: MISSING")
            continue
        eps = run["episodes"]
        rows = [e.get("row", {}) for e in eps]
        row = {
            "n": len(eps),
            "refused": sum(1 for e in eps if is_refused(e)),
            "no_firable": sum(1 for e in eps if is_no_firable(e)),
            "timeout": sum(1 for e in eps if is_timeout(e)),
            "fell_off": sum(1 for e in eps if notes_matching(e, "fell off the line")),
            "policy_close": sum(1 for e in eps if is_policy_close(e)),
            "intercept": sum(1 for e in eps if is_intercept(e)),
            "adopted": sum(r.get("adopted", 0) for r in rows),
            "scans": sum(r.get("scans", 0) for r in rows),
            "empty": sum(r.get("empty", 0) for r in rows),
            "off": sum(r.get("off", 0) for r in rows),
            "max_scans": max((r.get("scans", 0) for r in rows), default=0),
            "ticks_median": median([e["ticks"] for e in eps]),
            "ticks_median_end": median([e["ticks"] for e in eps if is_no_firable(e)]),
            "placed": sum(1 for e in eps if e["placed"]),
            "x": [float(m.group(1)) for e in eps
                  for m in [re.search(r"fruit x=([-+0-9.]+)", n)
                            for n in notes_matching(e, "lateral refuse:")]
                  if m],
        }
        table[arm] = row
        span = (f"x {min(row['x']):.3f}..{max(row['x']):.3f} m" if row["x"] else "x -")
        print(f"  arm {arm}: n={row['n']} refused={row['refused']} "
              f"no_firable={row['no_firable']} timeout={row['timeout']} "
              f"fell_off={row['fell_off']} policy_close={row['policy_close']} "
              f"intercept={row['intercept']} placed={row['placed']} {span}")
        print(f"    adopted={row['adopted']} scans={row['scans']} "
              f"(max/episode {row['max_scans']}; empty {row['empty']}, "
              f"off-lateral {row['off']}) median_ticks={row['ticks_median']:.0f} "
              f"median_ticks@end={row['ticks_median_end']:.0f}")
        print(f"    interface: {run['refuse'] or '(no refuse line)'}")

    endpoints = {}
    if "A" in table and "B" in table and "C" in table:
        n = table["A"]["n"]
        # P1: the attribution incidence. The diag is ON in *every* arm (the
        # run-neutral instrument, PREREG section 2), so the endpoint is that the
        # predicate is live on every episode of every arm - A proves it costs
        # nothing behaviourally, B/C that it survives the levers.
        p1 = (table["A"]["refused"], table["B"]["refused"], table["C"]["refused"])
        print(f"\n  P1 attribution (the `lateral refuse:` note): A {p1[0]}/{n}, "
              f"B {p1[1]}/{n}, C {p1[2]}/{n}")
        endpoints["P1"] = (p1[0] == n and p1[1] == n and p1[2] == n)
        print(f"       {'PASS' if endpoints['P1'] else 'FAIL'} "
              f"(the diag is ON in every arm: the predicate must fire on all "
              f"{n} episodes of each; PREREG's M1 table's 'A 0/15' is the "
              f"internal inconsistency the amendment corrects)")
        # P3: the terminal class replaces the *unnamed* end.
        p3 = (table["A"]["timeout"], table["B"]["timeout"], table["C"]["timeout"])
        print(f"  P3 terminal class: timeouts A {p3[0]}, B {p3[1]}, C {p3[2]}; "
              f"no_firable B {table['B']['no_firable']}, C {table['C']['no_firable']}")
        print(f"       A's terminals: timeout {table['A']['timeout']}, "
              f"fell-off {table['A']['fell_off']}, close {table['A']['policy_close']}, "
              f"placed {table['A']['placed']}")
        covered = table["B"]["no_firable"] + table["C"]["no_firable"]
        endpoints["P3"] = (p3[1] == 0 and p3[2] == 0 and covered > 0)
        print(f"       {'PASS' if endpoints['P3'] else 'FAIL'} "
              f"(the named class must absorb the unnamed ends at a shorter "
              f"cycle; A's median {table['A']['ticks_median']:.0f} ticks)")
        # The reseed bound + Fb'.
        print(f"  reseed bound: C adopted {table['C']['adopted']} over "
              f"{table['C']['scans']} scan(s), max {table['C']['max_scans']}/episode "
              f"(<= 4 per refusal), budget `RESEED_MAX`=2")
        fb = table["C"]["intercept"]
        print(f"  Fb' (an intercept fire in arm C on a below-gate candidate): "
              f"{fb} intercept fire(s) - "
              f"{'FIRED (falsifier)' if fb else 'clean'}")
        endpoints["Fb"] = fb == 0
        pc = (table["A"]["policy_close"], table["B"]["policy_close"],
              table["C"]["policy_close"])
        print(f"  the second fire path (A1): policy closes A {pc[0]}, B {pc[1]}, "
              f"C {pc[2]} - {('the closure is not total: the END population is '
                               'the complement' if any(pc) else
                               'no close on the band')}")
        tick_bar = (table["B"]["ticks_median_end"] <= 600
                    and table["C"]["ticks_median_end"] <= 600)
        print(f"  the END tick bar (median <= 600 on the named class): "
              f"{'PASS' if tick_bar else 'FAIL'} "
              f"(A {table['A']['ticks_median']:.0f}, "
              f"B {table['B']['ticks_median_end']:.0f}, "
              f"C {table['C']['ticks_median_end']:.0f})")
        endpoints["ticks"] = tick_bar
    return endpoints


# --------------------------------------------------------------------------- #
# M2
# --------------------------------------------------------------------------- #
def refused_terminal(ep: dict) -> str:
    """The terminal of a refused episode, in the mechanism's own terms."""
    if is_no_firable(ep):
        return "no_firable"
    if is_policy_close(ep):
        return "close-chase"
    if notes_matching(ep, "fell off the line"):
        return "fell-off"
    if is_timeout(ep):
        return "timeout"
    return "other"


def report_m2(runs: dict[str, dict]) -> dict:
    print()
    print("=" * 78)
    print("M2 - the mixed refusal (lateral 0.06): the conversion (A2d)")
    print("=" * 78)
    index = {}
    for label in sorted(runs):
        if not label.startswith("M2_"):
            continue
        arm, run = label.split("_")[1], label.split("_")[2]
        index.setdefault(run, {})[arm] = runs[label]
    rows = []
    paired = 0
    agree = 0
    for run, arms in sorted(index.items()):
        for arm in ("A", "C"):
            if arm not in arms:
                continue
            eps = arms[arm]["episodes"]
            ref = [e for e in eps if is_refused(e)]
            adopted = [e for e in eps if notes_matching(e, "reseed: adopted")]
            conv = [e for e in adopted if is_intercept(e) or e["grasped"]]
            rows.append({
                "run": run, "arm": arm, "n": len(eps), "refused": len(ref),
                "adopted": len(adopted), "converted": len(conv),
                "placed_ref": sum(1 for e in ref if e["placed"]),
                "no_firable": sum(1 for e in eps if is_no_firable(e)),
                "timeout": sum(1 for e in eps if is_timeout(e)),
                "placed": sum(1 for e in eps if e["placed"]),
                "carried": sum(1 for e in eps if e["grasped"] and not e["placed"]),
                "scans": sum(e.get("row", {}).get("scans", 0) for e in eps),
                "max_scans": max((e.get("row", {}).get("scans", 0) for e in eps),
                                 default=0),
                "max_adopted": max((e.get("row", {}).get("adopted", 0) for e in eps),
                                   default=0),
                "terms": Counter(refused_terminal(e) for e in ref),
                "eps": eps, "ref": ref,
            })
            if not arms[arm]["refuse"]:
                print(f"  WARNING {arm} run {run}: no `[rl] refuse:` line")
        if "A" in arms and "C" in arms:
            a_eps = {e["index"]: e for e in arms["A"]["episodes"]}
            c_eps = {e["index"]: e for e in arms["C"]["episodes"]}
            for idx in sorted(set(a_eps) & set(c_eps)):
                paired += 1
                if (a_eps[idx]["arm"], a_eps[idx]["category"]) == (
                    c_eps[idx]["arm"], c_eps[idx]["category"]
                ):
                    agree += 1
    print("  run arm   n refused adopted converted placed_ref  scans max  "
          "refused-episode terminals")
    for row in rows:
        terms = ",".join(f"{k}:{v}" for k, v in sorted(row["terms"].items())) or "-"
        print(f"  {row['run']:<3} {row['arm']:<4} {row['n']:>3} {row['refused']:>7} "
              f"{row['adopted']:>7} {row['converted']:>9} {row['placed_ref']:>10} "
              f"{row['scans']:>6} {row['max_scans']:>3}  {terms}")
    a = [r for r in rows if r["arm"] == "A"]
    c = [r for r in rows if r["arm"] == "C"]
    endpoints = {}
    if a and c:
        nr_a = sum(r["refused"] for r in a)
        nr_c = sum(r["refused"] for r in c)
        ad_c = sum(r["adopted"] for r in c)
        pl_a = sum(r["placed_ref"] for r in a)
        pl_c = sum(r["placed_ref"] for r in c)
        print(f"\n  refused episodes: A {nr_a}, C {nr_c} "
              f"({sum(r['n'] for r in a)} / {sum(r['n'] for r in c)} episodes)")
        print(f"  A's refused terminals: "
              f"{dict(Counter(refused_terminal(e) for r in a for e in r['ref']))}")
        print(f"  C's refused terminals: "
              f"{dict(Counter(refused_terminal(e) for r in c for e in r['ref']))}")
        bounds = (max(r["max_scans"] for r in c) <= 4
                  and max(r["max_adopted"] for r in c) <= 2)
        inc = ad_c / max(1, nr_c)
        print(f"  P2a-ii supply limit (reported): adoption among refused "
              f"{ad_c}/{nr_c} = {inc:.0%}; the lane is starved ~46 % of the ticks "
              f"(`starvation right` 44.5-62.3 %, logs/p38/z1_supply_m1.log)")
        # P2a-i: the lever's correctness on the scans that DID return a candidate.
        non_empty = sum(r["scans"] for r in c) - sum(
            e.get("row", {}).get("empty", 0) for r in c for e in r["eps"])
        adopted_eps = [e for r in c for e in r["eps"]
                       if notes_matching(e, "reseed: adopted")]
        fired_adopted = sum(1 for e in adopted_eps
                            if is_intercept(e) or e["grasped"] or e["placed"])
        adopt_rate = ad_c / max(1, non_empty)
        fire_rate = fired_adopted / max(1, len(adopted_eps))
        print(f"  P2a-i correctness: scans returning a candidate {non_empty}, "
              f"adopted {ad_c} ({adopt_rate:.0%}, bar 80 %); adopted episodes that "
              f"fired on the new candidate {fired_adopted}/{len(adopted_eps)} "
              f"({fire_rate:.0%}, bar 80 %); bounds ok {bounds}")
        p2a = bounds and non_empty > 0 and adopt_rate >= 0.80 and fire_rate >= 0.80
        if non_empty == 0:
            p2a = None
            print("  P2a-i: UNEXERCISED (no scan ever returned a candidate - the "
                  "lever cannot act in this harness; the finding is reported)")
        else:
            print(f"  P2a-i: {'PASS' if p2a else 'FAIL'}")
        endpoints["P2"] = p2a
        one_f = fisher_exact(pl_c, nr_c - pl_c, pl_a, nr_a - pl_a, "greater")
        print(f"  P2b (reported, not gated): placed among refused A {rate(pl_a, nr_a)} "
              f"vs C {rate(pl_c, nr_c)}, one-sided Fisher p={one_f:.4f}")
        pairing_ok = paired > 0 and agree == paired
        print(f"  per-episode (arm, category) agreement: {agree}/{paired} - "
              f"{'paired table valid' if pairing_ok else 'PAIRING BROKEN -> unpaired (A4)'}")
        conv = [e for r in c for e in r["eps"] if notes_matching(e, "reseed: adopted")]
        a_eps = [e for r in a for e in r["eps"]]
        car_conv = sum(1 for e in conv if e["grasped"] and not e["placed"])
        car_a = sum(1 for e in a_eps if e["grasped"] and not e["placed"])
        fe = bool(conv) and car_conv / len(conv) > car_a / max(1, len(a_eps))
        print(f"  Fe (a conversion trades a no-fire for a grip failure): carried "
              f"among converted {rate(car_conv, len(conv))} vs A overall "
              f"{rate(car_a, len(a_eps))} - {'Fe FIRES (not adopted)' if fe else 'clean'}")
        endpoints["Fe"] = not fe
    return endpoints


# --------------------------------------------------------------------------- #
# M3
# --------------------------------------------------------------------------- #
def report_m3(runs: dict[str, dict]) -> dict:
    print()
    print("=" * 78)
    print("M3 - the shipped patch band: the safety endpoints (A3/A5 forms)")
    print("=" * 78)
    index = {}
    for label in sorted(runs):
        if not label.startswith("M3_"):
            continue
        arm, run = label.split("_")[1], label.split("_")[2]
        index.setdefault(run, {})[arm] = runs[label]
    endpoints = {}
    pairs = []
    print("  run arm   n  right_n right_placed right_rate  left_placed  "
          "refused no_firable  fired_cycle")
    per_arm = {"A": [], "C": []}
    for run, arms in sorted(index.items()):
        for arm in ("A", "C"):
            if arm not in arms:
                continue
            eps = arms[arm]["episodes"]
            right = [e for e in eps if e["arm"] == "right"]
            left = [e for e in eps if e["arm"] == "left"]
            fired_eps = [e for e in eps if fired(e) and not is_no_firable(e)]
            per_arm[arm].extend(eps)
            print(f"  {run:<3} {arm:<4} {len(eps):>3}  {len(right):>7} "
                  f"{sum(1 for e in right if e['placed']):>11} "
                  f"{sum(1 for e in right if e['placed']) / max(1, len(right)):>9.1%} "
                  f"{sum(1 for e in left if e['placed']):>11} "
                  f"{sum(1 for e in eps if is_refused(e)):>7} "
                  f"{sum(1 for e in eps if is_no_firable(e)):>9} "
                  f"{median([e['ticks'] for e in fired_eps]):>10.0f}")
            if not arms[arm]["refuse"]:
                print(f"      WARNING {arm} run {run}: no `[rl] refuse:` line")
        if "A" in arms and "C" in arms:
            ra = [e for e in arms["A"]["episodes"] if e["arm"] == "right"]
            rc = [e for e in arms["C"]["episodes"] if e["arm"] == "right"]
            fa = [e for e in arms["A"]["episodes"]
                  if fired(e) and not is_no_firable(e)]
            fc = [e for e in arms["C"]["episodes"]
                  if fired(e) and not is_no_firable(e)]
            pairs.append({
                "run": run,
                "delta": (sum(1 for e in rc if e["placed"]) / max(1, len(rc)))
                - (sum(1 for e in ra if e["placed"]) / max(1, len(ra))),
                "cycle": (median([e["ticks"] for e in fc])
                          / max(1.0, median([e["ticks"] for e in fa])) - 1.0),
                "ra": len(ra), "rc": len(rc),
            })
    if not pairs:
        print("  no complete A/C pairs")
        return endpoints

    print("\n  per-seed-pair deltas (C - A):")
    for p in pairs:
        print(f"    run {p['run']}: right placed delta {p['delta']:+.3f} "
              f"(n {p['ra']}/{p['rc']}), fired-only cycle {p['cycle']:+.1%}")
    ra = [e for e in per_arm["A"] if e["arm"] == "right"]
    rc = [e for e in per_arm["C"] if e["arm"] == "right"]
    ka = sum(1 for e in ra if e["placed"])
    kc = sum(1 for e in rc if e["placed"])
    d = kc / max(1, len(rc)) - ka / max(1, len(ra))
    lo, hi = newcombe_diff(ka, len(ra), kc, len(rc))
    print(f"\n  P4 right-arm placed: A {rate(ka, len(ra))} vs C {rate(kc, len(rc))}, "
          f"delta {d:+.3f} [95 % Newcombe {lo:+.3f}, {hi:+.3f}]")
    all_neg = all(p["delta"] < 0 for p in pairs)
    gate_fail = all_neg and d <= -0.10
    raw_fail = d <= -0.10
    print(f"  A3 gate: all five pairs negative? {all_neg}; pooled delta {d:+.3f} "
          f"<= -0.10? {raw_fail} -> "
          f"{'FAIL (consistent harm)' if gate_fail else 'PASS'}")
    print(f"       (the original point rule alone would read "
          f"{'FAIL' if raw_fail else 'PASS'} - the 1-sd false-fail it replaces)")
    endpoints["P4"] = not gate_fail
    # Exposure.
    ref = [e for e in per_arm["A"] + per_arm["C"] if is_refused(e)]
    print(f"  exposure: {len(ref)} refused episode(s) in "
          f"{len(per_arm['A']) + len(per_arm['C'])} = "
          f"{(len(ref) / max(1, len(per_arm['A']) + len(per_arm['C']))):.2%} "
          f"(patch-band expectation 0.31-0.77 %)")
    # P5: the note-level reason sets, symmetric.
    set_a, set_c = reason_set(per_arm["A"]), reason_set(per_arm["C"])
    only_a = sorted(set_a - set_c)
    only_c = sorted(set_c - set_a)
    print(f"  P5 reason sets (note level, attribution -> `{ATTR_KEY}`):")
    print(f"       A only: {only_a or 'none'}")
    print(f"       C only: {only_c or 'none'}")
    endpoints["P5"] = not only_a and not only_c
    print(f"       {'PASS' if endpoints['P5'] else 'FAIL'}")
    # P6: the fired-only cycle, run level.
    cyc = [p["cycle"] for p in pairs]
    all_up = all(c > 0.05 for c in cyc)
    print(f"  P6 fired-only cycle: per-pair {['%+.1f%%' % (100 * c) for c in cyc]}, "
          f"pooled {median([e['ticks'] for e in per_arm['C'] if fired(e) and not is_no_firable(e)]) / max(1.0, median([e['ticks'] for e in per_arm['A'] if fired(e) and not is_no_firable(e)])) - 1:+.1%}")
    print(f"       A3 gate (fail iff all five pairs > +5 %): "
          f"{'FAIL' if all_up else 'PASS'}")
    endpoints["P6"] = not all_up
    print(f"  `no firable fruit` episodes: A "
          f"{sum(1 for e in per_arm['A'] if is_no_firable(e))}, C "
          f"{sum(1 for e in per_arm['C'] if is_no_firable(e))} "
          f"(excluded from the cycle median, kept in the rate denominator)")
    return endpoints


# --------------------------------------------------------------------------- #
# G2 - the Gate-2 DIAG=0/1 pair (descriptive, not a new endpoint)
# --------------------------------------------------------------------------- #
def outcome_key(ep: dict) -> str:
    """The episode's class in the report's own terms (for the pair compare)."""
    if is_no_firable(ep):
        return "no_firable"
    if ep["placed"]:
        return "placed"
    if ep["grasped"]:
        return "carried"
    if is_policy_close(ep):
        return "close-chase"
    if notes_matching(ep, "fell off the line"):
        return "fell-off"
    if is_timeout(ep):
        return "timeout"
    return "other"


def _pair_agree(a: dict, b: dict) -> dict:
    """Agreement between two runs on the same band, by episode index."""
    ae, be = {e["index"]: e for e in a["episodes"]}, {e["index"]: e for e in b["episodes"]}
    shared = sorted(set(ae) & set(be))
    fruit = sum(1 for i in shared
                if (ae[i]["arm"], ae[i]["category"]) == (be[i]["arm"], be[i]["category"]))
    out = sum(1 for i in shared if outcome_key(ae[i]) == outcome_key(be[i]))
    return {"n": len(shared), "fruit": fruit, "out": out,
            "a": Counter(outcome_key(ae[i]) for i in shared),
            "b": Counter(outcome_key(be[i]) for i in shared)}


def report_g2(runs: dict[str, dict], m1_runs: dict[str, dict] | None = None) -> None:
    print()
    print("=" * 78)
    print("G2 - the Gate-2 DIAG=0/1 pair (M1 band, SEED=5): descriptive only")
    print("=" * 78)
    d0, d1 = runs.get("G2_diag0"), runs.get("G2_diag1")
    if not d0 or not d1:
        print("  missing a run (need G2_diag0 and G2_diag1)")
        return
    for label, run in (("diag0", d0), ("diag1", d1)):
        eps = run["episodes"]
        print(f"  {label}: n={len(eps)} refused={sum(1 for e in eps if is_refused(e))} "
              f"close={sum(1 for e in eps if is_policy_close(e))} "
              f"timeout={sum(1 for e in eps if is_timeout(e))} "
              f"fell_off={sum(1 for e in eps if notes_matching(e, 'fell off the line'))} "
              f"placed={sum(1 for e in eps if e['placed'])} "
              f"median_ticks={median([e['ticks'] for e in eps]):.0f} "
              f"classes={dict(sorted(Counter(outcome_key(e) for e in eps).items()))}")
    agrees = _pair_agree(d0, d1)
    print(f"\n  per-episode agreement diag0 vs diag1: fruit (arm, category) "
          f"{agrees['fruit']}/{agrees['n']}, outcome class {agrees['out']}/{agrees['n']}")
    print(f"       diag0 classes {dict(sorted(agrees['a'].items()))}")
    print(f"       diag1 classes {dict(sorted(agrees['b'].items()))}")
    noise = ""
    base = (m1_runs or {}).get("M1_A")
    if base and base.get("episodes"):
        n1 = _pair_agree(base, d1)
        noise = (f"  the DIAG=1 vs DIAG=1 repeat (the recorded `M1_A` vs this "
                 f"`G2_diag1`, both DIAG only) reads fruit {n1['fruit']}/{n1['n']}, "
                 f"outcome class {n1['out']}/{n1['n']} - that is the loop's own "
                 f"run-to-run noise, and the pair above must be read against it")
        print("\n" + noise)
    # The END's H1 scoping: the close tick's own dy on this band.
    closes = d1.get("closes") or []
    print(f"\n  the learned close's tick (diag1's `[refuse] close:` rows): "
          f"{len(closes)} row(s)")
    for c in closes:
        where = ("BEFORE the departure" if c["dy"] > -0.05
                 else "AFTER the departure (PREREG_A1 falsifier #1)")
        print(f"       tick={c['tick']} dy={c['dy']:+.3f} m -> {where}")
    if closes:
        after = [c for c in closes if c["dy"] <= -0.05]
        nearest = min(closes, key=lambda c: abs(c["dy"] + 0.05))
        if after:
            print(f"       the END's closure: {len(after)} of {len(closes)} close(s) "
                  f"latched AFTER the departure -> PREREG_A1 falsifier #1 FIRES: "
                  f"C3 is not a total closure, `no firable fruit` over-claims, and a "
                  f"flip needs a re-registered definition or a post-departure grace "
                  f"window (the shipped-band readout is owed in the B-arm batch)")
        else:
            print(f"       the END's closure holds on this band: all {len(closes)} "
                  f"close(s) before the departure (nearest to the gate: "
                  f"dy={nearest['dy']:+.3f} m); the falsifier is an A close later "
                  f"than the departure, and it is owed on the shipped band (the "
                  f"B-arm batch)")
    else:
        print("       no close on this band in diag1: nothing to scope (an "
              "elsewhere-run close is unmeasured by construction)")


# --------------------------------------------------------------------------- #
# decision
# --------------------------------------------------------------------------- #
def decision(m1: dict, m2: dict, m3: dict) -> None:
    print()
    print("=" * 78)
    print("the decision rule (PREREG section 6 + PREREG_A1)")
    print("=" * 78)
    p1, p3 = m1.get("P1"), m1.get("P3")
    fb = m1.get("Fb", True)
    p2, fe = m2.get("P2"), m2.get("Fe", True)
    p4, p5, p6 = m3.get("P4"), m3.get("P5"), m3.get("P6")
    print(f"  P1 attribution {p1}  P2 conversion {p2}  P3 terminal {p3}  "
          f"P4 safety {p4}  P5 reasons {p5}  P6 cycle {p6}")
    print(f"  falsifiers: Fb' {'FIRED' if not fb else 'clean'}  "
          f"Fe {'FIRED' if not fe else 'clean'}  "
          f"(Fa: the diag note absent from M1; Fc': an intercept fire on a "
          f"refused M2-A candidate; Ff: a cross-lane adoption - all reported "
          f"in the tables above)")
    safety_ok = bool(p4) and bool(p5) and bool(p6)
    if p1 and p2 and p3 and safety_ok and fb and fe:
        print("  VERDICT: adopt-recommended (phase 3 may flip, owner sign-off)")
    elif p1 and p3 and safety_ok and fb and (not p2 or not fe):
        if p2 is None:
            print("  VERDICT: B-only-recommended (attribution + terminal class "
                  "hold; the re-selection never saw a candidate, so its endpoint "
                  "is unexercised - not a failure of the lever's logic, a "
                  "property of the harness: the feeder does not advance inside "
                  "an episode)")
        else:
            print("  VERDICT: B-only-recommended (attribution + terminal class "
                  "hold; the conversion does not)")
    else:
        print("  VERDICT: not adopted (a pre-registered endpoint failed)")


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #
def self_test() -> int:
    failures = 0

    def check(name, cond, detail=""):
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}{(' - ' + detail) if detail else ''}")

    line = (
        "[rl] episode 7: kiwi d=4.5cm bin=1 arm=right success=False grasped=False "
        "placed=False ticks=412 decision=380 reward=0.0000 "
        "notes=['lateral refuse: fruit x=0.150 |dx|=0.183 > lateral 0.160 "
        "(station x=0.333 -> x >= 0.173 admitted; x frozen, permanent)', "
        "'no firable fruit: the trigger refuses (candidate x=0.150, "
        "|dx|=0.183 > lateral 0.160; x >= 0.173 admitted) and the learned close "
        "never fired (best |jaw-fruit|=21.4cm) through dy=-0.052 m (the fruit "
        "passed the station); x drift 0.4mm since the latch'] "
        "presentation=direct ablate=none"
    )
    m = RESULT.search(line)
    check("the result line parses", m is not None)
    notes = split_notes(m.group(12))
    ep = {
        "index": 7, "category": "kiwi", "bin": 1, "arm": "right",
        "success": False, "grasped": False, "placed": False,
        "ticks": 412, "decision": 380, "notes": notes,
    }
    check("notes split into items", len(notes) == 2 and notes[0].startswith("lateral refuse:"))
    check("the refusal predicate", is_refused(ep) and is_no_firable(ep)
          and not is_timeout(ep) and not is_policy_close(ep))
    x = [float(mm.group(1)) for n in notes_matching(ep, "lateral refuse:")
         for mm in [re.search(r"fruit x=([-+0-9.]+)", n)]]
    check("the refused x is read", x == [0.150], str(x))
    check("a closing note is a policy close",
          is_policy_close({"notes": ["policy closed on the fruit (finger=0.0210, "
                                     "|jaw-fruit|xy=5.9cm)"]}))
    check("an intercept note is an intercept",
          is_intercept({"notes": ["intercept trigger (dy=+11.0cm, ...)"]}))
    check("adoptions/scans parse",
          adoptions({"notes": ["reseed: no firable candidate in 4 scan(s) "
                               "(lane 1, 1 refusal(s) so far)"]}) == (0, 4))
    # exact tests
    check("McNemar 8-0 one-sided p = 1/256", abs(mcnemar_exact(8, 0)[0] - 1 / 256) < 1e-12,
          f"{mcnemar_exact(8, 0)[0]:.6f}")
    check("McNemar 5-0 p = 1/32", abs(mcnemar_exact(5, 0)[0] - 1 / 32) < 1e-12)
    check("McNemar symmetric ties give p=1", abs(mcnemar_exact(3, 3)[0] - 0.65625) < 1e-9,
          f"{mcnemar_exact(3, 3)[0]:.5f}")
    check("Fisher 10/10 vs 0/10 is small", fisher_exact(10, 0, 0, 10) < 1e-4,
          f"{fisher_exact(10, 0, 0, 10):.2e}")
    check("Fisher identity case ~1", fisher_exact(5, 5, 5, 5) > 0.5,
          f"{fisher_exact(5, 5, 5, 5):.3f}")
    check("sign test 0-5 (all negative)", abs(sign_test(0, 5) - 1 / 32) < 1e-12,
          f"{sign_test(0, 5):.6f}")
    check("sign test 2-3", abs(sign_test(2, 3) - 0.5) < 1e-9, f"{sign_test(2, 3):.4f}")
    lo, hi = wilson(4, 5)
    check("Wilson bounds bracket the point", lo < 0.8 < hi, f"{lo:.3f}..{hi:.3f}")
    lo, hi = newcombe_diff(20, 47, 20, 47)
    check("Newcombe zero-delta interval brackets 0", lo < 0 < hi, f"{lo:+.3f}..{hi:+.3f}")
    # reason mapping
    eps = [
        {"success": False, "notes": ["lateral refuse: ...", "timeout: no grasp within 1500 ticks"]},
        {"success": True, "notes": ["intercept trigger (...)"]},
        {"success": False, "notes": ["carried not placed: fruit left the hand"]},
    ]
    keys = reason_set(eps)
    check("reason set maps the attribution notes to one class",
          ATTR_KEY in keys and "timeout: no grasp within # ticks" in keys
          and len(keys) == 3, str(sorted(keys)))
    # the Gate-2 close row + the pair's outcome classes
    close = CLOSE_ROW.search("2026-10-25 16:02:11 [fruit] [refuse] close: tick=418 "
                             "dy=-0.152 m (station frame; <= -0.05 is past the "
                             "departure) |jaw-fruit|xy=5.9cm")
    check("the `[refuse] close:` row parses", close is not None
          and int(close.group(1)) == 418 and abs(float(close.group(2)) + 0.152) < 1e-9)
    check("outcome classes separate the END's",
          outcome_key({"success": False, "placed": False, "grasped": False,
                       "notes": ["no firable fruit: ..."]}) == "no_firable"
          and outcome_key({"success": False, "placed": False, "grasped": False,
                           "notes": ["lateral refuse: ...", "fruit fell off the line"]})
          == "fell-off"
          and outcome_key({"success": False, "placed": False, "grasped": True,
                           "notes": ["fruit did not follow the gripper"]}) == "carried")
    # the A3 gate arithmetic
    def gate(deltas, pooled):
        return all(d < 0 for d in deltas) and pooled <= -0.10
    check("A3 gate: five negative + pooled -0.12 fails", gate([-0.02] * 5, -0.12))
    check("A3 gate: one positive passes", not gate([-0.3, -0.3, -0.3, -0.3, 0.1], -0.22))
    check("A3 gate: small negative delta passes", not gate([-0.01] * 5, -0.03))
    print(f"[p2 report self-test] {'OK' if failures == 0 else f'{failures} FAILURES'}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m12", default="logs/p38/P2")
    parser.add_argument("--m3", default="logs/p38/P3")
    parser.add_argument("--g2", default="logs/p38/G2")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()

    runs = {}
    runs.update(load_dir(args.m12, "M1_"))
    runs.update(load_dir(args.m12, "M2_"))
    runs.update(load_dir(args.m3, "M3_"))
    if not runs:
        print("no logs found; run scripts/225_p38_batch.sh first")
        return 1
    m1 = report_m1(runs) if any(k.startswith("M1_") for k in runs) else {}
    m2 = report_m2(runs) if any(k.startswith("M2_") for k in runs) else {}
    m3 = report_m3(runs) if any(k.startswith("M3_") for k in runs) else {}
    if m1 or m2 or m3:
        decision(m1, m2, m3)
    g2 = load_dir(args.g2, "G2_")
    if g2:
        report_g2(g2, {k: v for k, v in runs.items() if k.startswith("M1_")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
