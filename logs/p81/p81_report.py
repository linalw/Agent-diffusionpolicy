"""P81 report: the two-line's scheduler on the single arm's shipped supply.

    python3 logs/p81/p81_report.py            # reads logs/p80 and logs/p81

Read-only (opens logs, prints). It borrows P80's parser (`logs/p80/p80lib.py`,
which itself borrows `scripts/186_w6_report.py`'s W6/P33 metric definitions), so
P81's numbers are computed by the same code as P80's and are directly
comparable. Sections:

  0  provenance: the PREREG md5, the header pins against the tree now
  1  the package-off proof (the `[supply]` row; `A:0.375` must be absent)
  2  the arms at a glance: E1-E3, E8, E10 and the starved polls
  3  per-arm: idle, lock-on, starvation, the class split
  4  the decision rule (PREREG section 4), clause by clause, with the verdict
  5  the per-log tables (`scripts/186_w6_report.py`, `scripts/175_twoline_report.py`)
  6  the motion gates and the accept probe as recorded

Exit 0 when every input the decision needs is readable; 1 otherwise (a missing
arm is printed as missing, never inferred).
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "logs/p80"))
import p80lib  # noqa: E402

#: tag -> (label, seed, role). S = single arm, C = package-on control,
#: P = the P81 arm. The S/C logs are P80's records (same tree md5s, PREREG s1).
ARMS = {
    "S20": ("single, shipped", 5, "S"),
    "T20": ("two-line + package", 5, "C"),
    "Tp5": ("two-line, package OFF", 5, "P"),
    "S6": ("single, shipped", 6, "S"),
    "T6": ("two-line + package", 6, "C"),
    "Tp6": ("two-line, package OFF", 6, "P"),
}
SEEDS = (5, 6)
SPAN_BAR = 11.0          # PREREG D1.1
INT_BAR = 12.0           # PREREG D1.2 (literal; the relative form is same-seed control)
CLK_LO, CLK_HI = 1.75, 2.00  # PREREG D1.3
POLL_FACTOR = 1.25       # PREREG D2 S-poll
IDLE_FACTOR = 1.50       # PREREG D2 S-idle


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


def path_of(tag: str) -> str:
    """The P81 arms live in logs/p81; the P80 controls are read in place."""
    if tag.startswith("Tp"):
        return os.path.join(HERE, f"{tag}.log")
    return os.path.join(ROOT, "logs/p80", f"{tag}.log")


def read(tag: str) -> dict | None:
    path = path_of(tag)
    return p80lib.metrics(path) if os.path.exists(path) else None


def retries(tag: str) -> dict:
    path = path_of(tag)
    if not os.path.exists(path):
        return {}
    return p80lib.w6.parse(path)["retries"]


def polls(m: dict, tag: str) -> int | None:
    r = retries(tag)
    return sum(r.values()) if r else None


def per_arm_classes(tag: str) -> dict:
    """Per-arm placed / carried-not-placed / never-grasped from the result rows."""
    path = path_of(tag)
    if not os.path.exists(path):
        return {}
    data = p80lib.w6.parse(path)
    out = {}
    for arm, rows in data["results"].items():
        cell = {"placed": 0, "cnp": 0, "never": 0}
        for row in rows:
            if row["placed"]:
                cell["placed"] += 1
            elif row["grasped"]:
                cell["cnp"] += 1
            else:
                cell["never"] += 1
        out[arm] = cell
    return out


def window_rate(m):
    return m["window_rate"]


def batch_per_attempt(m):
    return (m["batch_span"] / m["attempts"]) if m["attempts"] else None


def clock_ratio(s: dict, p: dict):
    a, b = batch_per_attempt(s), batch_per_attempt(p)
    return (a / b) if a and b else None


def attempt_span(m: dict):
    """Mean `t1-t0` over the executed attempts (the two-line's `[stats] sim` is
    the union span, not this sum - so it has to be read off the run windows)."""
    rows = [r for r in p80lib.rows_of(m["path"])
            if not r.get("no_fruit") and r.get("t0", 0) > 0 and r.get("t1", 0) > 0]
    xs = [r["t1"] - r["t0"] for r in rows]
    return (sum(xs) / len(xs)) if xs else None


def concurrency(m: dict):
    """Mean arms busy in an attempt = sum of the per-attempt spans / batch span."""
    mean = attempt_span(m)
    n = m["attempts"]
    return (n * mean / m["batch_span"]) if (mean and m["batch_span"]) else None


def section_provenance() -> None:
    print("=" * 78)
    print("0. PROVENANCE")
    print("=" * 78)
    prereg = os.path.join(HERE, "PREREG.md")
    pin_path = os.path.join(HERE, "PREREG.md5")
    if os.path.exists(pin_path):
        pinned = open(pin_path, encoding="utf-8").read().split()[0]
        now = md5(prereg)
        print(f"  PREREG.md md5 {pinned} (pinned before the runs)  now {now}  "
              f"{'UNCHANGED' if pinned == now else 'CHANGED - edited after the runs'}")
    header = os.path.join(HERE, "header.txt")
    if os.path.exists(header):
        for line in open(header, encoding="utf-8"):
            if line.startswith("# arm") or line.startswith("# controls"):
                print(f"  {line.rstrip()}")
    print("  tree now (a mismatch against header.txt means the tree moved):")
    for name in ("src/fruit_sorting/tasks.py", "src/fruit_sorting/bimanual.py",
                 "src/fruit_sorting/fruits.py", "configs/motion_reference.json",
                 "configs/motion_reference_twoline.json"):
        print(f"    {md5(os.path.join(ROOT, name))}  {name}")
    print("  instruments: logs/p81/stamp.py = the byte copy of logs/p80/stamp.py "
          f"({md5(os.path.join(HERE, 'stamp.py'))})")


def section_supply() -> bool:
    print()
    print("=" * 78)
    print("1. THE PACKAGE-OFF PROOF (PREREG E0 / F1)")
    print("=" * 78)
    ok = True
    for tag in ("Tp5", "Tp6"):
        path = os.path.join(HERE, f"{tag}.log")
        if not os.path.exists(path):
            print(f"  {tag}: MISSING -> the proof is not available")
            ok = False
            continue
        rows = [line.rstrip() for line in open(path, encoding="utf-8", errors="ignore")
                if "[supply]" in line and "wave=" in line]
        bad = [line for line in open(path, encoding="utf-8", errors="ignore")
               if "A:0.375" in line]
        for line in rows:
            print(f"  {tag}: {line.strip()}")
        wave_off = any("wave=off" in line for line in rows)
        grades = any("grades=A:0.5,B:0.3,C:0.2" in line for line in rows)
        print(f"  {tag}: wave=off {wave_off}; shipped 50/30/20 {grades}; "
              f"A:0.375 rows {len(bad)}")
        if not (wave_off and grades and not bad):
            print(f"  {tag}: FAIL F1 - the package was not provably disabled")
            ok = False
    return ok


def section_glance(got: dict) -> None:
    print()
    print("=" * 78)
    print("2. THE ARMS AT A GLANCE (PREREG section 2)")
    print("=" * 78)
    print("  clock = batch sim span / executed attempt (P80's 1.88 identity).")
    print("  window rate = 60 / pooled interval mean; batch rate = 60*placed/batch span.")
    head = (f"  {'arm':<4} {'what':<24} {'seed':>4} {'att':>3} {'placed':>6} "
            f"{'s/att':>6} {'int mean':>8} {'p90':>6} {'win/min':>7} {'bat/min':>7} "
            f"{'bp/att':>6} {'wall/pick':>9} {'w/sim':>5} {'wall/min':>8} {'polls':>5} {'pol/att':>7}")
    print(head)
    for tag, (label, seed, role) in ARMS.items():
        m = got.get(tag)
        if m is None or not m["attempts"]:
            print(f"  {tag:<4} {label:<24} {seed:>4} MISSING")
            continue
        st = m["stats"]
        n_polls = polls(m, tag)
        wall_rate = (60.0 * m["placed"] / st["wall"]) if st.get("wall") else None
        print(f"  {tag:<4} {label:<24} {seed:>4} {m['attempts']:>3} "
              f"{m['placed']:>3}/{m['attempts']:<2} "
              f"{f(st['per_attempt']):>6} {f(m['pooled']['mean']):>8} "
              f"{f(m['pooled']['p90']):>6} {f(m['window_rate']):>7} "
              f"{f(m['batch_rate']):>7} {f(batch_per_attempt(m)):>6} "
              f"{f(st['wall_per_pick'], 1):>9} {f(st['wall_over_sim']):>5} "
              f"{f(wall_rate):>8} "
              f"{n_polls if n_polls is not None else 'n/a':>5} "
              f"{f(n_polls / m['attempts'] if n_polls is not None else None):>7}")
    print()
    print("  clock ratio (S / Tp), the same ratio for the package-on control, and the")
    print("  decomposition batch-rate ratio = clock ratio x count ratio:")
    for seed in SEEDS:
        s = got.get("S20" if seed == 5 else "S6")
        p = got.get("Tp5" if seed == 5 else "Tp6")
        c = got.get("T20" if seed == 5 else "T6")
        if s and p:
            r = clock_ratio(s, p)
            rc = clock_ratio(s, c) if c else None
            cnt_p = (p["placed"] / p["attempts"]) / (s["placed"] / s["attempts"])
            cnt_c = ((c["placed"] / c["attempts"]) / (s["placed"] / s["attempts"])
                     if c else None)
            rate_p = p["batch_rate"] / s["batch_rate"]
            rate_c = c["batch_rate"] / s["batch_rate"] if c else None
            print(f"    seed {seed}: clock S/Tp {f(r)}x (control {f(rc)}x); "
                  f"count Tp/S {f(cnt_p)}x (control {f(cnt_c)}x); "
                  f"batch rate Tp/S {f(rate_p)}x (control {f(rate_c)}x); "
                  f"s/attempt S {f(s['stats']['per_attempt'])} / Tp "
                  f"{f(p['stats']['per_attempt'])} / C "
                  f"{f(c['stats']['per_attempt']) if c else 'n/a'}")
            print(f"             mean attempt span S {f(attempt_span(s))} / Tp "
                  f"{f(attempt_span(p))} / C {f(attempt_span(c))}s; concurrency "
                  f"S {f(concurrency(s))} / Tp {f(concurrency(p))} / C "
                  f"{f(concurrency(c))} arms busy")
    print("  pooled (counts summed, ratios from the per-seed means):")
    try:
        s5, s6 = got["S20"], got["S6"]
        p5, p6 = got["Tp5"], got["Tp6"]
        c5, c6 = got["T20"], got["T6"]
        clk_tp = ((clock_ratio(s5, p5) + clock_ratio(s6, p6)) / 2.0)
        clk_c = ((clock_ratio(s5, c5) + clock_ratio(s6, c6)) / 2.0)
        print(f"    placed Tp {p5['placed'] + p6['placed']}/{p5['attempts'] + p6['attempts']} "
              f"vs S {s5['placed'] + s6['placed']}/{s5['attempts'] + s6['attempts']} "
              f"vs C {c5['placed'] + c6['placed']}/{c5['attempts'] + c6['attempts']}; "
              f"clock mean {f(clk_tp)}x (control {f(clk_c)}x)")
        def wall(m):
            return m["stats"]["wall"]
        print(f"    pooled batch rate  S "
              f"{f(60*(s5['placed']+s6['placed'])/(s5['batch_span']+s6['batch_span']))} / Tp "
              f"{f(60*(p5['placed']+p6['placed'])/(p5['batch_span']+p6['batch_span']))} / C "
              f"{f(60*(c5['placed']+c6['placed'])/(c5['batch_span']+c6['batch_span']))} placed/min")
        print(f"    pooled wall rate   S "
              f"{f(60*(s5['placed']+s6['placed'])/(wall(s5)+wall(s6)))} / Tp "
              f"{f(60*(p5['placed']+p6['placed'])/(wall(p5)+wall(p6)))} / C "
              f"{f(60*(c5['placed']+c6['placed'])/(wall(c5)+wall(c6)))} placed/min")
        print(f"    pooled window rate S "
              f"{f((s5['window_rate']+s6['window_rate'])/2)} / Tp "
              f"{f((p5['window_rate']+p6['window_rate'])/2)} / C "
              f"{f((c5['window_rate']+c6['window_rate'])/2)} placed/min "
              f"(mean of the seeds' 60/interval)")
    except KeyError:
        print("    (missing arm - pooled line not printed)")
    print()
    print("  starved polls: the two-line worker re-polls every ~0.5 s and parks; the")
    print("  package-on control has 44 (seed 5) / 33 (seed 6), so the literal PREREG")
    print("  '> 0' is informative only against that baseline (PREREG R4).")


def section_per_arm(got: dict) -> None:
    print()
    print("=" * 78)
    print("3. PER-ARM: idle, lock-on, starvation, and the class split")
    print("=" * 78)
    for tag, (label, seed, role) in ARMS.items():
        m = got.get(tag)
        if not m:
            continue
        print(f"  == {tag} ({label}, seed {seed})")
        r = retries(tag)
        for arm, a in sorted(m["per_arm"].items()):
            print(f"     {arm:<5}: placed {a['placed']}/{a['attempts']}  "
                  f"interval {f(a['interval_mean'])}s  "
                  f"idle {f(None if a['idle_frac'] is None else 100*a['idle_frac'], 0)}%  "
                  f"polls {r.get(arm, 'n/a')}")
        lock = ", ".join(
            f"{arm} {f(v['mean'])}s (p90 {f(v['p90'])}, {v['retries_total']} polls)"
            for arm, v in sorted(m["lock_on"].items()))
        if lock:
            print(f"     lock-on: {lock}")
        cls = ", ".join(f"{k} {v}" for k, v in sorted(m["classes"].items()))
        print(f"     classes: {cls}")
        pac = per_arm_classes(tag)
        if pac and any(sum(c.values()) for c in pac.values()):
            print("     classes by arm: " + ", ".join(
                f"{arm} placed {c['placed']} / cnp {c['cnp']} / never {c['never']}"
                for arm, c in sorted(pac.items())))
        if m["reasons"]:
            print("     reasons: " + "; ".join(
                f"{k} x{v}" for k, v in sorted(m["reasons"].items())))
        split = m["arm_split"]
        if split:
            print("     by summary arm: " + ", ".join(
                f"{arm} {c['placed']}/{c['attempts']} ({f(100*c['rate'], 1)}%)"
                for arm, c in sorted(split.items())))
        print(f"     lost slots (no eligible fruit on a slot): {m['pending_slots']}")


def section_decision(got: dict) -> dict:
    print()
    print("=" * 78)
    print("4. THE DECISION RULE (PREREG section 4) - clause by clause")
    print("=" * 78)
    out = {"d1": True, "fires": []}
    for seed in SEEDS:
        s = got.get("S20" if seed == 5 else "S6")
        p = got.get("Tp5" if seed == 5 else "Tp6")
        c = got.get("T20" if seed == 5 else "T6")
        if not (s and p and c):
            print(f"  seed {seed}: missing S/Tp/control -> D1 not evaluable")
            out["d1"] = False
            out["fires"].append(f"seed {seed}: missing arm")
            continue
        r_clk = clock_ratio(s, p)
        poll_p = polls(p, "Tp5" if seed == 5 else "Tp6")
        poll_c = polls(c, "T20" if seed == 5 else "T6")
        pa_p = poll_p / p["attempts"]
        pa_c = poll_c / c["attempts"]
        idle_c = {a: c["per_arm"][a]["idle_frac"] for a in c["per_arm"]}
        idle_p = {a: p["per_arm"][a]["idle_frac"] for a in p["per_arm"]}
        win_s, win_p = window_rate(s), window_rate(p)
        c1 = p["stats"]["per_attempt"] <= SPAN_BAR
        c2 = (p["pooled"]["mean"] <= INT_BAR) or (p["pooled"]["mean"] <= c["pooled"]["mean"])
        c3 = r_clk is not None and CLK_LO <= r_clk <= CLK_HI
        c4 = win_p > win_s
        sp = pa_p >= POLL_FACTOR * pa_c
        si = any(idle_p[a] >= IDLE_FACTOR * idle_c[a]
                 for a in idle_p if a in idle_c and idle_c[a] is not None)
        print(f"  seed {seed}")
        print(f"    D1.1 s/attempt {f(p['stats']['per_attempt'])} <= {SPAN_BAR}: "
              f"{'PASS' if c1 else 'FAIL'}")
        print(f"    D1.2 interval {f(p['pooled']['mean'])}s <= {INT_BAR}s or <= control "
              f"{f(c['pooled']['mean'])}s: {'PASS' if c2 else 'FAIL'}")
        print(f"    D1.3 clock ratio {f(r_clk)} in [{CLK_LO}, {CLK_HI}]: "
              f"{'PASS' if c3 else 'FAIL'}")
        print(f"    D1.4 window {f(win_p)} > single {f(win_s)}: "
              f"{'PASS' if c4 else 'FAIL'}")
        print(f"    D2.S-poll polls/attempt {f(pa_p)} vs control {f(pa_c)} "
              f"(bar {f(POLL_FACTOR * pa_c)}): {'FIRES' if sp else 'no'}")
        print(f"    D2.S-idle " + ", ".join(
            f"{a} {f(100*idle_p[a], 0)}% vs {f(100*idle_c[a], 0)}% "
            f"(bar {f(100*IDLE_FACTOR*idle_c[a], 0)}%)"
            for a in sorted(idle_p) if a in idle_c)
              + f": {'FIRES' if si else 'no'}")
        ws = (60.0 * s["placed"] / s["stats"]["wall"]) if s["stats"].get("wall") else None
        wp = (60.0 * p["placed"] / p["stats"]["wall"]) if p["stats"].get("wall") else None
        print(f"    report-only: wall placed/min single {f(ws)} vs Tp {f(wp)} "
              f"({f(wp / ws if ws else None)}x) - the harness column, not a D1 clause")
        if not (c1 and c2 and c3 and c4):
            out["d1"] = False
            out["fires"].append(
                f"seed {seed}: D1 "
                + ",".join(k for k, v in (("span", c1), ("interval", c2),
                                          ("clock", c3), ("rate", c4)) if not v))
        if sp:
            out["fires"].append(f"seed {seed}: S-poll")
        if si:
            out["fires"].append(f"seed {seed}: S-idle")
    print()
    if out["d1"] and not out["fires"]:
        print("  VERDICT: D1 - the clock is the scheduler's own on this supply")
    elif out["d1"]:
        print("  VERDICT: D2 - the clock clauses hold but a starvation clause fires: "
              + "; ".join(out["fires"]))
    else:
        print("  VERDICT: D2 - the package is required: " + "; ".join(out["fires"]))
    return out


def section_tables() -> None:
    print()
    print("=" * 78)
    print("5. THE PER-LOG TABLES (scripts/186_w6_report.py, scripts/175_twoline_report.py)")
    print("=" * 78)
    for tag in ARMS:
        path = path_of(tag)
        if not os.path.exists(path):
            continue
        print()
        out = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts/186_w6_report.py"), path],
            capture_output=True, text=True)
        print(out.stdout.rstrip())
    print()
    print("-- 175: the two-line starvation / steady-state / routing read --")
    twoline = [path_of(t) for t in ("Tp5", "Tp6", "T20", "T6")
               if os.path.exists(path_of(t))]
    if twoline:
        out = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts/175_twoline_report.py"), *twoline],
            capture_output=True, text=True)
        print(out.stdout.rstrip())


def section_gates() -> None:
    print()
    print("=" * 78)
    print("6. THE MOTION GATES AND THE ACCEPT PROBE (as recorded)")
    print("=" * 78)
    for name in ("Tp5.budgets", "Tp6.budgets", "Tp5.gate", "Tp6.gate",
                 "accept.gate"):
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            print(f"  {name}: MISSING")
            continue
        print(f"  -- {name}")
        lines = open(path, encoding="utf-8", errors="ignore").read().splitlines()
        keep = [ln for ln in lines
                if ln.strip().startswith(("worst:", "success:", "fingerprint:",
                                          "FAIL:", "PASS", "190:", "  - ", "note:"))]
        print("\n".join("    " + ln.strip() for ln in keep) if keep else "    (no summary rows)")


def main() -> int:
    got = {}
    for tag in ARMS:
        m = read(tag)
        if m is not None:
            got[tag] = m
    section_provenance()
    proof = section_supply()
    section_glance(got)
    section_per_arm(got)
    decision = section_decision(got)
    section_tables()
    section_gates()
    print()
    print("=" * 78)
    complete = all(t in got for t in ("S20", "T20", "Tp5", "S6", "T6", "Tp6"))
    print(f"  inputs complete: {complete}; package-off proof: {proof}; "
          f"verdict: {'D1' if decision['d1'] and not decision['fires'] else 'D2'}")
    return 0 if (complete and proof) else 1


if __name__ == "__main__":
    raise SystemExit(main())
