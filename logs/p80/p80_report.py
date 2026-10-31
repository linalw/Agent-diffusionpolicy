"""P80 report: the cell's throughput on the shipped tree, and the two levers.

    python3 logs/p80/p80_report.py            # reads logs/p80/*.log, writes stdout

Read-only (opens logs, prints). Sections:

  0  provenance: the header pins against the tree now, the PREREG md5
  1  the arms at a glance - every endpoint of PREREG section 2 in one table
  2  the per-log tables (`scripts/186_w6_report.py`, the W6/P33 definitions)
  3  the two-line question (the 1.25x placement-window bar, non-inferiority,
     and the seed-6 pair when it exists)
  4  the union question (R2's licence, the span and interval deltas, V's read)
  5  the wall/sim split
  6  the class split per arm (counts - reported, never gated)
  7  the motion gates as they were recorded
  8  the verdicts, written from the rules in PREREG section 4

Exit status 0 when every section it needs was readable; 1 otherwise (a missing
arm is printed as missing, never inferred).
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import p80lib  # noqa: E402

#: the arms in reporting order, with the env each carries (for the table label)
ARMS = {
    "S20": "single, shipped",
    "T20": "two-line",
    "U20": "single + FRUIT_SPEED_ALL=1",
    "V20": "two-line + FRUIT_SPEED_ALL=1",
    "S6": "single, shipped (seed 6)",
    "T6": "two-line (seed 6)",
    "U6": "single + speed union (seed 6)",
    "V6": "two-line + speed union (seed 6)",
    "S10": "the acceptance (10 attempts, gate arm)",
    "T10": "two-line (10 attempts, gate arm)",
}
#: the 20-attempt throughput arms (the ones the decisions read)
THROUGHPUT = ("S20", "T20", "U20", "V20", "S6", "T6", "U6", "V6")
BAR_TWOLINE = 1.25


def md5(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def f(v, nd=2):
    return p80lib.fmt(v, nd)


def have(tag):
    return os.path.exists(os.path.join(HERE, f"{tag}.log"))


def read(tag):
    path = os.path.join(HERE, f"{tag}.log")
    return p80lib.metrics(path) if os.path.exists(path) else None


def pct(a, b):
    """`a` relative to `b`, in percent."""
    if a is None or b in (None, 0):
        return None
    return 100.0 * (a - b) / b


def section_provenance() -> None:
    print("=" * 78)
    print("0. PROVENANCE")
    print("=" * 78)
    prereg = os.path.join(HERE, "PREREG.md")
    pinned = open(os.path.join(HERE, "PREREG.md5"), encoding="utf-8").read().split()[0]
    now = md5(prereg)
    print(f"  PREREG.md md5 {pinned} (pinned before the runs)  now {now}  "
          f"{'UNCHANGED' if pinned == now else 'CHANGED - the registration was edited after the runs'}")
    header = os.path.join(HERE, "header.txt")
    if os.path.exists(header):
        for line in open(header, encoding="utf-8"):
            if line.startswith("# 20-attempt") or line.startswith("# rails"):
                print(f"  {line.rstrip()}")
    print("  tree now (a mismatch against header.txt means the tree moved):")
    for name in ("src/fruit_sorting/tasks.py", "src/fruit_sorting/bimanual.py",
                 "src/fruit_sorting/assets.py", "configs/motion_reference.json",
                 "configs/motion_reference_twoline.json"):
        print(f"    {md5(os.path.join(ROOT, name))}  {name}")


def section_glance() -> dict:
    print()
    print("=" * 78)
    print("1. THE ARMS AT A GLANCE (PREREG section 2's endpoints)")
    print("=" * 78)
    print("  placement-window rate = 60 / pooled interval mean (186's identity, P3).")
    print("  batch rate = placed / (t_last_end - t_first_start). Both printed; never mixed.")
    head = (f"  {'arm':<4} {'what':<34} {'att':>3} {'placed':>6} {'s/att':>6} "
            f"{'sim':>7} {'wall/pick':>9} {'w/sim':>5} {'wall/min':>8} | "
            f"{'int mean':>8} {'p90':>7} {'win/min':>7} {'batch/min':>9}")
    print(head)
    got = {}
    for tag in ARMS:
        m = read(tag)
        if m is None or not m["attempts"]:
            print(f"  {tag:<4} {ARMS[tag]:<34} {'MISSING' if m is None else 'IN PROGRESS'}")
            continue
        got[tag] = m
        st = m["stats"]
        wall_rate = (60.0 * m["placed"] / st["wall"]) if st["wall"] else None
        print(f"  {tag:<4} {ARMS[tag]:<34} {m['attempts']:>3} "
              f"{m['placed']:>3}/{m['attempts']:<2} "
              f"{f(st['per_attempt']):>6} {f(m['batch_span'], 1):>7} "
              f"{f(st['wall_per_pick'], 1):>9} {f(st['wall_over_sim'], 2):>5} "
              f"{f(wall_rate):>8} | "
              f"{f(m['pooled']['mean']):>8} {f(m['pooled']['p90']):>7} "
              f"{f(m['window_rate']):>7} {f(m['batch_rate']):>9}")
    print()
    print("  per-arm split (the arm is set by the fruit's grade, so the pool is a supply draw):")
    s = got.get("S20")
    mix = ({arm: c["attempts"] for arm, c in s["arm_split"].items()} if s else None)
    for tag in ARMS:
        m = got.get(tag)
        if not m:
            continue
        cells = []
        for arm, a in sorted(m["per_arm"].items()):
            cells.append(f"{arm} {a['placed']}/{a['attempts']}, "
                         f"int {f(a['interval_mean'])}s, "
                         f"idle {f(None if a['idle_frac'] is None else 100*a['idle_frac'], 0)}%")
        print(f"    {tag:<4} {'; '.join(cells)}")
        split = m["arm_split"]
        if split:
            text = ", ".join(f"{arm} {c['placed']}/{c['attempts']} "
                             f"({f(100*c['rate'], 1)}%)" for arm, c in sorted(split.items()))
            line = f"         by the summary's arm: {text}"
            if mix:
                st = p80lib.standardised_rate(m, mix)
                if st["rate"] is not None:
                    line += (f"; standardised to S's mix "
                             f"({', '.join(f'{a} {100*v:.0f}%' for a, v in st['shares'].items())})"
                             f" -> {f(100*st['rate'], 1)}%")
            print(line)
        lock = ", ".join(f"{arm} lock-on {f(v['mean'])}s (p90 {f(v['p90'])}, "
                         f"{v['retries_total']} retries)"
                         for arm, v in sorted(m["lock_on"].items()))
        if lock:
            print(f"         {lock}")
        if m["pending_slots"]:
            print(f"         starved slots (no eligible fruit): {m['pending_slots']}")
    return got


def section_tables() -> None:
    print()
    print("=" * 78)
    print("2. THE PER-LOG TABLES (scripts/186_w6_report.py - the W6/P33 definitions)")
    print("=" * 78)
    for tag in ARMS:
        if not have(tag):
            continue
        print()
        out = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts/186_w6_report.py"),
             os.path.join(HERE, f"{tag}.log")],
            capture_output=True, text=True)
        print(out.stdout.rstrip())


def section_twoline(got: dict) -> dict:
    print()
    print("=" * 78)
    print("3. THE TWO-LINE QUESTION (PREREG 4b - the standing 1.25x bar)")
    print("=" * 78)
    verdict = {"ratio": None, "ratio6": None, "default": False}
    s, t = got.get("S20"), got.get("T20")
    if not s or not t:
        print("  S20 or T20 missing -> the question is not answerable")
        return verdict
    r_win = (t["window_rate"] / s["window_rate"]) if s["window_rate"] else None
    r_batch = (t["batch_rate"] / s["batch_rate"]) if s["batch_rate"] else None
    r_int = (s["pooled"]["mean"] / t["pooled"]["mean"]) if t["pooled"]["mean"] else None
    verdict["ratio"] = r_win
    print(f"  placement window: S {f(s['window_rate'])} vs T {f(t['window_rate'])} placed/min "
          f"-> {f(r_win)}x   (bar {BAR_TWOLINE}x)")
    print(f"  batch span      : S {f(s['batch_rate'])} vs T {f(t['batch_rate'])} placed/min "
          f"-> {f(r_batch)}x   (cross-branch reference only)")
    print(f"  pooled interval : S {f(s['pooled']['mean'])} vs T {f(t['pooled']['mean'])}s mean "
          f"-> {f(r_int)}x shorter; p90 {f(s['pooled']['p90'])} vs {f(t['pooled']['p90'])}s")
    print(f"  per attempt     : S {f(s['stats']['per_attempt'])} vs T "
          f"{f(t['stats']['per_attempt'])}s")
    print(f"  placed          : S {s['placed']}/{s['attempts']} vs T "
          f"{t['placed']}/{t['attempts']}  (counts are attractor reads, PREREG R0)")
    if s["arm_split"] and t["arm_split"]:
        mix = {arm: c["attempts"] for arm, c in s["arm_split"].items()}
        st_s = p80lib.standardised_rate(s, mix)
        st_t = p80lib.standardised_rate(t, mix)
        if st_s["rate"] is not None and st_t["rate"] is not None:
            shares = ", ".join(f"{a} {100*v:.0f}%" for a, v in st_s["shares"].items())
            arm_s = ", ".join(f"{a} {c['placed']}/{c['attempts']}"
                              for a, c in sorted(s["arm_split"].items()))
            arm_t = ", ".join(f"{a} {c['placed']}/{c['attempts']}"
                              for a, c in sorted(t["arm_split"].items()))
            print(f"  arm-standardised: S {f(100*st_s['rate'], 1)}% vs T "
                  f"{f(100*st_t['rate'], 1)}% at S's mix ({shares}); "
                  f"per-arm S {arm_s} / T {arm_t}")
    noninferior = t["placed"] >= s["placed"] - 1
    print(f"  non-inferiority : T.placed >= S.placed - 1 -> "
          f"{'PASS' if noninferior else 'FAIL'} ({t['placed']} vs {s['placed']})")
    live = {
        "S": (s["window_rate"], s["placed"]),
    }
    s6, x6 = got.get("S6"), None
    for cand in ("T6", "U6", "V6"):
        if got.get(cand):
            x6 = (cand, got[cand])
            break
    if s6 and x6:
        cand, m6 = x6
        if cand == "T6" and s6["window_rate"] and m6["window_rate"]:
            r6 = m6["window_rate"] / s6["window_rate"]
            verdict["ratio6"] = r6
            print(f"  seed 6          : S {f(s6['window_rate'])} vs T {f(m6['window_rate'])} "
                  f"placed/min -> {f(r6)}x; interval {f(s6['pooled']['mean'])} vs "
                  f"{f(m6['pooled']['mean'])}s; placed {s6['placed']}/{s6['attempts']} vs "
                  f"{m6['placed']}/{m6['attempts']} "
                  f"(seed-6 non-inferiority: {'PASS' if m6['placed'] >= s6['placed'] - 1 else 'FAIL'} "
                  f"- the count advantage does not replicate)")
        else:
            print(f"  seed 6          : the seed-6 pair is S6 + {cand} "
                  f"(the mover was not the two-line - see section 4)")
    seed6_ok = verdict["ratio6"] is not None and verdict["ratio6"] >= BAR_TWOLINE
    bar5 = r_win is not None and r_win >= BAR_TWOLINE
    has6 = verdict["ratio6"] is not None
    verdict["default"] = bool(bar5 and noninferior and seed6_ok)
    print()
    if verdict["default"]:
        print("  -> the two-line MEETS the registered default rule (bar + non-inferior + seed 6).")
    elif bar5 and noninferior and not has6:
        print("  -> seed 5 meets the bar and the count is non-inferior, but the seed-6 pair is")
        print("     not measured: one sample, keep opt-in (PREREG 4b condition 3).")
    elif bar5 and noninferior:
        print("  -> seed 5 meets the bar but the seed-6 pair does not confirm it: one sample,")
        print("     keep opt-in (PREREG 4b condition 3).")
    elif bar5:
        print("  -> the bar is met but the count is not non-inferior: keep opt-in.")
    else:
        print(f"  -> the two-line does NOT meet the {BAR_TWOLINE}x bar: keep opt-in.")
    return verdict


def section_union(got: dict) -> dict:
    print()
    print("=" * 78)
    print("4. THE UNION QUESTION (PREREG 4c - the interval/time claim, never the count)")
    print("=" * 78)
    out = {"span_delta": None, "interval_pct": None, "pays": False}
    s, u = got.get("S20"), got.get("U20")
    if not s or not u:
        print("  S20 or U20 missing -> not answerable")
        return out
    d_span = (s["stats"]["per_attempt"] - u["stats"]["per_attempt"]
              if s["stats"]["per_attempt"] and u["stats"]["per_attempt"] else None)
    d_int = u["pooled"]["mean"] - s["pooled"]["mean"] if u["pooled"]["mean"] else None
    rel = pct(u["pooled"]["mean"], s["pooled"]["mean"])
    out["span_delta"] = d_span
    out["interval_pct"] = rel
    print(f"  s/attempt       : S {f(s['stats']['per_attempt'])} -> U "
          f"{f(u['stats']['per_attempt'])}  (delta {f(d_span)}s; bar >= 1.0 s)")
    print(f"  pooled interval : S {f(s['pooled']['mean'])} -> U {f(u['pooled']['mean'])}s "
          f"({f(rel, 1)}%; bar <= -10 %)")
    print(f"  p90 interval    : S {f(s['pooled']['p90'])} -> U {f(u['pooled']['p90'])}s")
    print(f"  placement window: S {f(s['window_rate'])} -> U {f(u['window_rate'])} placed/min")
    print(f"  placed (reported only, PREREG R1): S {s['placed']}/{s['attempts']} -> U "
          f"{u['placed']}/{u['attempts']}")
    if s["arm_split"] and u["arm_split"]:
        mix = {arm: c["attempts"] for arm, c in s["arm_split"].items()}
        st_s = p80lib.standardised_rate(s, mix)
        st_u = p80lib.standardised_rate(u, mix)
        if st_s["rate"] is not None and st_u["rate"] is not None:
            arm_s = ", ".join(f"{a} {c['placed']}/{c['attempts']}"
                              for a, c in sorted(s["arm_split"].items()))
            arm_u = ", ".join(f"{a} {c['placed']}/{c['attempts']}"
                              for a, c in sorted(u["arm_split"].items()))
            print(f"  arm-standardised: S {f(100*st_s['rate'], 1)}% -> U "
                  f"{f(100*st_u['rate'], 1)}% at S's mix; per-arm S {arm_s} / U {arm_u}")
            print("  (the pooled count moves with the grade draw: A -> the left arm, and the "
                  "left is the closed cnp class - P43/P59/P60)")
    print(f"  class split     : S {s['classes']} -> U {u['classes']}")
    pays = bool((d_span is not None and d_span >= 1.0)
                or (rel is not None and rel <= -10.0))
    out["pays"] = pays
    print(f"  licence (R2)    : {'PASS -> V is spent' if pays else 'FAIL -> V is not spent'}")
    if os.path.exists(os.path.join(HERE, "licence.txt")):
        print("  licence.py said:")
        for line in open(os.path.join(HERE, "licence.txt"), encoding="utf-8"):
            print(f"    {line.rstrip()}")
    v = got.get("V20")
    if v:
        print()
        print(f"  V (two-line + union): s/attempt {f(v['stats']['per_attempt'])}, "
              f"interval {f(v['pooled']['mean'])}s, window {f(v['window_rate'])} placed/min, "
              f"placed {v['placed']}/{v['attempts']}")
        t = got.get("T20")
        if t:
            print(f"    vs T20: s/attempt {f(t['stats']['per_attempt'])} -> "
                  f"{f(v['stats']['per_attempt'])} "
                  f"({f((t['stats']['per_attempt'] or 0) - (v['stats']['per_attempt'] or 0))}s), "
                  f"interval {f(t['pooled']['mean'])} -> {f(v['pooled']['mean'])}s, "
                  f"window rate {f(pct(v['window_rate'], t['window_rate']), 1)}%")
    # the mover / seed-6 pair
    if os.path.exists(os.path.join(HERE, "mover.txt")):
        print()
        print("  the mover read (PREREG R3):")
        for line in open(os.path.join(HERE, "mover.txt"), encoding="utf-8"):
            print(f"    {line.rstrip()}")
    s6 = got.get("S6")
    for cand in ("T6", "U6", "V6"):
        m6 = got.get(cand)
        if not (s6 and m6):
            continue
        print()
        print(f"  seed 6, {cand} vs S6: s/attempt {f(s6['stats']['per_attempt'])} -> "
              f"{f(m6['stats']['per_attempt'])} "
              f"(delta {f((s6['stats']['per_attempt'] or 0) - (m6['stats']['per_attempt'] or 0))}s); "
              f"interval {f(s6['pooled']['mean'])} -> {f(m6['pooled']['mean'])}s "
              f"({f(pct(m6['pooled']['mean'], s6['pooled']['mean']), 1)}%); "
              f"placed {s6['placed']}/{s6['attempts']} -> {m6['placed']}/{m6['attempts']} "
              f"(reported, R0)")
    return out


def section_wall(got: dict) -> None:
    print()
    print("=" * 78)
    print("5. WALL vs SIM (PREREG 4d - a harness fact, reported, never gated)")
    print("=" * 78)
    print("  wall = `[run] attempt 0` -> `[fruit] DONE` on the stamp stream; sim = the batch")
    print("  span over the same interval. `app clock` is the whole process (Isaac boot in).")
    print("  `wall/min` = 60 * placed / wall: the operator's placements per wall minute.")
    print(f"  {'arm':<4} {'attempts':>8} {'wall':>7} {'wall/pick':>9} {'sim/pick':>8} "
          f"{'w/sim':>6} {'wall/min':>8} {'app clock':>9}")
    for tag in THROUGHPUT + ("S10", "T10"):
        m = got.get(tag)
        if not m:
            continue
        st = m["stats"]
        print(f"  {tag:<4} {m['attempts']:>8} {f(st['wall'], 1):>7} "
              f"{f(st['wall_per_pick'], 1):>9} "
              f"{f(None if not m['attempts'] else (m['batch_span'] or 0) / m['attempts'], 1):>8} "
              f"{f(st['wall_over_sim'], 2):>6} "
              f"{f(None if not st['wall'] else 60.0 * m['placed'] / st['wall'], 2):>8} "
              f"{f(st['app_clock'], 1):>9}")


def section_classes(got: dict) -> None:
    print()
    print("=" * 78)
    print("6. CLASS SPLIT PER ARM (counts - reported, never gated; PREREG R0)")
    print("=" * 78)
    for tag in THROUGHPUT + ("S10", "T10"):
        m = got.get(tag)
        if not m:
            continue
        print(f"  {tag:<4} {m['classes']}")
        if m["reasons"]:
            for reason, n in sorted(m["reasons"].items(), key=lambda kv: -kv[1]):
                print(f"        {n}x {reason}")


def section_gates() -> None:
    print()
    print("=" * 78)
    print("7. THE MOTION GATES AS RECORDED (PREREG section 1 / E9)")
    print("=" * 78)
    for tag, path in (("G-S10", "S10.gate"), ("G-T10", "T10.gate")):
        p = os.path.join(HERE, path)
        if not os.path.exists(p):
            print(f"  {tag}: no gate file")
            continue
        print(f"  {tag} ({path}):")
        for line in open(p, encoding="utf-8", errors="ignore"):
            if any(key in line for key in ("fingerprint", "PASS", "FAIL", "success",
                                           "budget", "FAIL:")):
                print(f"    {line.rstrip()}")
    p = os.path.join(HERE, "T20.reference")
    if os.path.exists(p):
        print("  T20's own 20-attempt reference (logs/p80/, the shipped configs/ file untouched):")
        for line in open(p, encoding="utf-8", errors="ignore"):
            if "wrote fingerprint" in line or "NOT writing" in line or "success" in line:
                print(f"    {line.rstrip()}")
    for name in ("V20.gate",):
        p = os.path.join(HERE, name)
        if os.path.exists(p):
            print(f"  {name}:")
            for line in open(p, encoding="utf-8", errors="ignore"):
                if any(key in line for key in ("fingerprint", "PASS", "FAIL")):
                    print(f"    {line.rstrip()}")


def section_verdicts(glance: dict, two: dict, union: dict) -> None:
    print()
    print("=" * 78)
    print("8. VERDICTS (the rules of PREREG section 4, applied verbatim)")
    print("=" * 78)
    s, t = glance.get("S20"), glance.get("T20")
    if s and t:
        print(f"  (a) today: the shipped single arm places {s['placed']}/{s['attempts']} = "
              f"{f(s['window_rate'])} placed/min (window) / {f(s['batch_rate'])} (batch), "
              f"inter-placement interval {f(s['pooled']['mean'])}s mean / {f(s['pooled']['p90'])}s p90, "
              f"{f(s['stats']['per_attempt'])}s/attempt.")
        print(f"      the two-line (opt-in) places {t['placed']}/{t['attempts']} = "
              f"{f(t['window_rate'])} (window) / {f(t['batch_rate'])} (batch), "
              f"interval {f(t['pooled']['mean'])}s / {f(t['pooled']['p90'])}s p90, "
              f"{f(t['stats']['per_attempt'])}s/attempt.")
    print()
    if two.get("ratio") is not None:
        state = "MEETS" if two["default"] else "does NOT meet"
        print(f"  (b) two-line default: {state} the registered rule - placement-window ratio "
              f"{f(two['ratio'])}x (bar {BAR_TWOLINE}x), seed-6 ratio "
              f"{f(two['ratio6'])}x. Read it with the wall lines below and RESULTS.md 7b: the "
              f"registered letter passes, the count advantage does not replicate.")
        s, t = glance.get("S20"), glance.get("T20")
        s6, t6 = glance.get("S6"), glance.get("T6")
        if s and t and s["stats"]["wall"] and t["stats"]["wall"]:
            print("      on the wall: placed/min "
                  f"{f(60*s['placed']/s['stats']['wall'])} -> "
                  f"{f(60*t['placed']/t['stats']['wall'])}")
            if s6 and t6 and s6["stats"]["wall"] and t6["stats"]["wall"]:
                print("                   seed 6 "
                      f"{f(60*s6['placed']/s6['stats']['wall'])} -> "
                      f"{f(60*t6['placed']/t6['stats']['wall'])}; "
                      f"pooled {f(60*(s['placed']+s6['placed'])/(s['stats']['wall']+s6['stats']['wall']))} -> "
                      f"{f(60*(t['placed']+t6['placed'])/(t['stats']['wall']+t6['stats']['wall']))}")
            if s6 and t6 and s["batch_span"] and t["batch_span"]:
                sim_s = (s["batch_span"] + s6["batch_span"])
                sim_t = (t["batch_span"] + t6["batch_span"])
                print("      pooled over both seeds: sim placed/min "
                      f"{f(60*(s['placed']+s6['placed'])/sim_s)} -> "
                      f"{f(60*(t['placed']+t6['placed'])/sim_t)} "
                      f"({f((t['placed']+t6['placed'])/sim_t / ((s['placed']+s6['placed'])/sim_s))}x), "
                      "count "
                      f"{s['placed']+s6['placed']}/{s['attempts']+s6['attempts']} -> "
                      f"{t['placed']+t6['placed']}/{t['attempts']+t6['attempts']}")
    print()
    if union.get("span_delta") is not None:
        s, u = glance.get("S20"), glance.get("U20")
        print(f"  (c) the speed union: clock {'PASS' if union['pays'] else 'FAIL'} "
              f"(s/attempt delta {f(union['span_delta'])}s, bar 1.0; pooled interval "
              f"{f(union['interval_pct'], 1)}%, bar -10%)")
        if s and u:
            print(f"      throughput: window {f(s['window_rate'])} -> {f(u['window_rate'])} "
                  f"placed/min ({f(pct(u['window_rate'], s['window_rate']), 1)}%), batch "
                  f"{f(s['batch_rate'])} -> {f(u['batch_rate'])} "
                  f"({f(pct(u['batch_rate'], s['batch_rate']), 1)}%) - the placed count "
                  f"{s['placed']}/{s['attempts']} -> {u['placed']}/{u['attempts']} is the "
                  "closed class + the grade draw, so the union is a cycle-time lever, "
                  "not a throughput lever at this seed.")
    print()
    walls = [(tag, glance[tag]["stats"]["wall_over_sim"]) for tag in ("S20", "T20", "U20", "V20")
             if glance.get(tag) and glance[tag]["stats"]["wall_over_sim"]]
    if walls:
        print("  (d) wall/sim: " + ", ".join(f"{tag} {f(v, 2)}x" for tag, v in walls)
              + " - the harness share of the wall is outside every sim-time lever in this phase.")
        s, t = glance.get("S20"), glance.get("T20")
        if s and t and s["stats"]["wall_over_sim"] and t["stats"]["wall_over_sim"]:
            print(f"      the two-line's wall per simulated second is "
                  f"{f(t['stats']['wall_over_sim'] / s['stats']['wall_over_sim'], 2)}x the single "
                  f"arm's, so a sim-time ratio r becomes a wall ratio r / "
                  f"{f(t['stats']['wall_over_sim'] / s['stats']['wall_over_sim'], 2)}: "
                  f"sim/pick {f((s['batch_span']/s['attempts']) / (t['batch_span']/t['attempts']), 2)}x "
                  f"-> wall/pick "
                  f"{f(s['stats']['wall_per_pick'] / t['stats']['wall_per_pick'], 2)}x.")
            print(f"      per placement the wall ratio is "
                  f"{f((s['stats']['wall']/s['placed']) / (t['stats']['wall']/t['placed']), 2)}x "
                  f"({f(s['stats']['wall']/s['placed'], 1)} vs "
                  f"{f(t['stats']['wall']/t['placed'], 1)} s/placement) - and that is the "
                  f"count difference, not the clock.")


def main() -> int:
    section_provenance()
    glance = section_glance()
    section_tables()
    two = section_twoline(glance)
    union = section_union(glance)
    section_wall(glance)
    section_classes(glance)
    section_gates()
    section_verdicts(glance, two, union)
    missing = [tag for tag in THROUGHPUT if tag not in glance]
    if missing:
        print()
        print(f"  note: arms not run: {', '.join(missing)} "
              f"(V is conditional on R2; the seed-6 arm on R3)")
    print()
    print("  report done")
    return 0 if "S20" in glance else 1


if __name__ == "__main__":
    raise SystemExit(main())
