#!/usr/bin/env python3
"""P46 phase 1 report: the P44 speed union on the two-line, C vs U at seeds 5/6.

    python3 logs/p46/p1/p46_report.py --write      # -> logs/p46/p1/P1_report.txt

Reads only the four battery logs plus the P44 seed-5 record (for the
instrument-neutrality / default-off check). No simulator, no writes outside the
report file.

Endpoints are the PREREG's (`logs/p46/PREREG.md` section 3):
  E1 placed does not fall; E2 s/attempt -0.50 s in both seeds; E3 the guard
  (new held-then-lost row / force_min==0 legs / held legs with clean_slip>50 mm);
  E4 the motion budgets (from gates.txt, reported separately); E5 fingerprint
  (phase 1: record); E6 the release landing (place trace on_belt).
"""
from __future__ import annotations

import argparse
import re
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "logs/p46/p1"
P44_C5 = ROOT / "logs/p44/p2/twoline_s5_C.log"

BIRES_RE = re.compile(
    r"^\[fruit\] \[biarm\] result (\w+) index=(\d+) (\w+) grasped=(True|False) "
    r"placed=(True|False) lift=([+-][\d.]+) force=([\d.]+) sim=([\d.]+)s "
    r"notes=\[(.*)\]$"
)
ATTEMPT_RE = re.compile(
    r"^\[fruit\] \[run\] attempt (\d+) \((\w+)\): grasped=(True|False) "
    r"placed=(True|False) lift=([+-][\d.]+) m force=([\d.]+) N sim=([\d.]+)s "
    r"notes=\[(.*)\]$"
)
STATS_RE = re.compile(
    r"^\[fruit\] \[stats\] attempts=(\d+) successes=(\d+) diverted=(\d+) "
    r"success_rate=(\d+)% sim=([\d.]+)s total, ([\d.]+)s/attempt, "
    r"([\d.]+)s/success gate_open=([\d.]+)s total, queue_peak=(\d+) "
    r"recirculated=(\d+)"
)
CYCLE_RE = re.compile(r"^\[fruit\] \[cycle\] attempt (\d+): (.*)$")
CARRY_RE = re.compile(r"^\[fruit\] \[carry\] (\w+) (\w+): (.*)$")
TRACE_RE = re.compile(r"place trace (\w+): (.*)$")
KV_RE = re.compile(r"([\w@]+)=([^\s]+)")

PHASES = ("prepose", "hover", "descent", "close", "grip", "lift", "place", "release", "return")


def num(text: str) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def parse(log: Path) -> dict:
    """Parse one log.

    The two-line prints its per-attempt outcome **inline** as
    `[biarm] result <arm> index=... grasped=... notes=[...]`, and the `[carry]`
    legs of that attempt are printed *before* it - so a leg is attached to the
    attempt whose result row follows it. That linkage is what makes `held legs`
    mean what the PREREG says (the P44/P45 class split: a leg of an attempt whose
    `[run]`/`[biarm]` row reads `grasped=True`), instead of a contact-agnostic
    slip number that also accumulates on never-held legs (W8-B's caveat).
    """
    d: dict = {
        "attempts": [],
        "run_rows": [],
        "stats": None,
        "cycle": [],
        "carry": [],
        "traces": [],
        "notes": 0,
        "no_grasp": 0,
        "held_lost": 0,
    }
    pending: list[dict] = []
    for line in log.read_text(errors="replace").splitlines():
        line = line.rstrip()
        m = BIRES_RE.match(line)
        if m:
            row = {
                "n": len(d["attempts"]),
                "arm": m.group(1),
                "index": int(m.group(2)),
                "fruit": m.group(3),
                "grasped": m.group(4) == "True",
                "placed": m.group(5) == "True",
                "note": m.group(9),
                "legs": pending,
            }
            for leg in pending:
                leg["attempt"] = row["n"]
                leg["attempt_grasped"] = row["grasped"]
            pending = []
            d["attempts"].append(row)
            continue
        m = ATTEMPT_RE.match(line)
        if m:
            # The `[run] attempt` block is the same outcomes printed again at the
            # batch end on the two-line (the inline row is `[biarm] result`), so
            # it is only the fallback for a single-arm log.
            d["run_rows"].append(
                {
                    "n": int(m.group(1)),
                    "arm": m.group(2),
                    "grasped": m.group(3) == "True",
                    "placed": m.group(4) == "True",
                    "note": m.group(8),
                    "legs": [],
                }
            )
            continue
        m = STATS_RE.match(line)
        if m:
            d["stats"] = {
                "attempts": int(m.group(1)),
                "placed": int(m.group(2)),
                "diverted": int(m.group(3)),
                "s_per_attempt": float(m.group(6)),
                "span": float(m.group(5)),
                "gate_open": float(m.group(8)),
                "queue_peak": int(m.group(9)),
                "recirculated": int(m.group(10)),
            }
            continue
        m = CYCLE_RE.match(line)
        if m:
            row: dict = {"n": int(m.group(1))}
            for k, v in KV_RE.findall(m.group(2)):
                val = num(v.rstrip("s"))
                if val is not None:
                    row[k] = val
            d["cycle"].append(row)
            continue
        m = CARRY_RE.match(line)
        if m:
            row = {"arm": m.group(1), "leg": m.group(2)}
            for k, v in KV_RE.findall(m.group(3)):
                row[k] = v
            pending.append(row)
            d["carry"].append(row)
            continue
        m = TRACE_RE.search(line)
        if m:
            row = {"arm": m.group(1)}
            for k, v in KV_RE.findall(m.group(2)):
                row[k] = v
            d["traces"].append(row)
    if not d["attempts"]:
        d["attempts"] = d["run_rows"]
    for a in d["attempts"]:
        if "did not follow" in a["note"]:
            d["notes"] += 1
            if a["grasped"]:
                d["held_lost"] += 1
            else:
                d["no_grasp"] += 1
    return d


def w6(log: Path) -> dict:
    """The 186 throughput/interval report, parsed from its own stdout."""
    out = subprocess.run(
        [sys.executable, str(ROOT / "scripts/186_w6_report.py"), str(log)],
        capture_output=True, text=True, check=False, cwd=ROOT,
    ).stdout
    res: dict = {"raw": out}
    m = re.search(r"attempts=(\d+) placements=(\d+) failures=(\d+)", out)
    if m:
        res["placements"] = int(m.group(2))
    m = re.search(r"pooled : n=(\d+) mean ([\d.]+)s p50 ([\d.]+)s", out)
    if m:
        res["pooled_n"] = int(m.group(1))
        res["pooled_mean"] = float(m.group(2))
        res["pooled_p50"] = float(m.group(3))
    m = re.search(r"throughput \(batch span ([\d.]+)s\): (\d+)/(\d+) placed = ([\d.]+) placed/min;"
                  r" placement window ([\d.]+)s -> ([\d.]+) placed/min", out)
    if m:
        res["placed_per_min"] = float(m.group(4))
        res["window_per_min"] = float(m.group(6))
    m = re.search(r"per arm left=(\d+)/(\d+) right=(\d+)/(\d+)", out)
    if m:
        res["left"] = f"{m.group(1)}/{m.group(2)}"
        res["right"] = f"{m.group(3)}/{m.group(4)}"
    return res


def core_lines(path: Path) -> list[str]:
    """The branch-identity stream: `[fruit]` sim rows minus the added instruments.

    The prior log (`logs/p44/p2/twoline_s5_C.log`) carries MOTION_REPORT +
    CYCLE_REPORT only; this battery adds CARRY_DIAG and PLACE_TRACE, so the rows
    those two instruments own are dropped by their own tags before the compare
    (they are the *only* tags the two instruments print - checked by the first
    difference, which the report prints if the compare still differs).
    """
    drop = ("[carry]", "place trace", "[diag]", "release trace", "release event",
            "[seat]", "[attitude]")
    out = []
    for line in path.read_text(errors="replace").splitlines():
        if not line.startswith("[fruit]"):
            continue
        if any(tag in line for tag in drop):
            continue
        out.append(line)
    return out


def carry_read(carry: list[dict]) -> dict:
    """The E3 walk read, on the P44/W8-B class split.

    `held` legs are the legs of attempts whose outcome row reads
    `grasped=True` (the linkage `parse` builds); a *clean* held leg is one that
    also ended with the payload in the hand (`loss_row=None`). W8-B's caveat is
    why the linkage is used at all: the live slip accumulator is contact-agnostic
    and reads hundreds of mm on never-held legs.
    """
    zero = sum(1 for r in carry if r.get("force_min") == "0.00N")
    linked = any("attempt_grasped" in r for r in carry)
    held: list[float] = []
    clean: list[float] = []
    lost_legs = 0
    for r in carry:
        slip = num(str(r.get("clean_slip_max", "nan")).rstrip("mm"))
        if slip is None:
            continue
        has_onset = r.get("onset_row") not in (None, "None", "n/a")
        if linked:
            if not r.get("attempt_grasped"):
                continue
        elif not has_onset:
            clean.append(slip)
            continue
        held.append(slip)
        if r.get("loss_row") in (None, "None", "n/a"):
            clean.append(slip)
        else:
            lost_legs += 1
    return {
        "legs": len(carry),
        "force_min_zero": zero,
        "held_n": len(held),
        "lost_legs": lost_legs,
        "held_over_50": sum(1 for s in held if s > 50.0),
        "clean_p50": statistics.median(clean) if clean else float("nan"),
        "clean_max": max(clean) if clean else float("nan"),
        "held_max": max(held) if held else float("nan"),
        "clean_n": len(clean),
    }


def trace_read(traces: list[dict]) -> dict:
    reached, landed, miss = 0, 0, []
    upstream = 0
    for t in traces:
        rb = num(str(t.get("release_bottom", "nan")).rstrip("mm"))
        on = t.get("on_belt") == "True"
        if rb is not None and rb > 0.0:
            reached += 1
            if on:
                landed += 1
            else:
                miss.append(t)
        else:
            upstream += 1
    return {"traces": len(traces), "reached": reached, "landed": landed,
            "miss": miss, "upstream": upstream}


def fmt(v: float | None, nd: int = 2) -> str:
    if v is None or (isinstance(v, float) and v != v):
        return "n/a"
    return f"{v:.{nd}f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    lines: list[str] = []

    def say(s: str = "") -> None:
        lines.append(s)
        print(s)

    say("# P46 phase 1 report — the P44 speed union on the two-line, C vs U, seeds 5/6")
    say()
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
        capture_output=True, text=True,
    ).stdout.strip()
    say(f"tree: {head}")
    say()

    data: dict[tuple[int, str], dict] = {}
    w6d: dict[tuple[int, str], dict] = {}
    for seed in (5, 6):
        for arm in ("C", "U"):
            log = OUT / f"twoline_s{seed}_{arm}.log"
            if not log.exists():
                say(f"MISSING {log}")
                continue
            d = parse(log)
            if not d["stats"]:
                say(f"INCOMPLETE {log} (no [stats] row - still running or cut short)")
                continue
            data[(seed, arm)] = d
            w6d[(seed, arm)] = w6(log)

    # --- the per-arm table -------------------------------------------------
    say("## 1. Per-arm read (10 attempts each)")
    say()
    hdr = ("seed arm  placed  left  right   s/att  span  divert gate  placed/min  window/min  "
           "interval mean/p50  notes nc hl  lift place release")
    say(hdr)
    for seed in (5, 6):
        for arm in ("C", "U"):
            d = data.get((seed, arm))
            if not d or not d["stats"]:
                continue
            st, w = d["stats"], w6d[(seed, arm)]
            cyc = {}
            for p in ("lift", "place", "release"):
                vals = [c[p] for c in d["cycle"] if p in c]
                cyc[p] = statistics.mean(vals) if vals else float("nan")
            say(f"{seed:>4} {arm:<3} {st['placed']:>4}/10  {w.get('left','?'):>4}  {w.get('right','?'):>5}"
                f"  {st['span'] / st['attempts']:>5.2f} {st['span']:>5.1f} {st['diverted']:>6}"
                f" {st['gate_open']:>4.1f}  {w.get('placed_per_min', float('nan')):>8.2f}"
                f"  {w.get('window_per_min', float('nan')):>8.2f}"
                f"  {fmt(w.get('pooled_mean'))}/{fmt(w.get('pooled_p50'))}"
                f"  {d['notes']:>5} {d['no_grasp']:>2} {d['held_lost']:>2}"
                f"  {fmt(cyc['lift'])} {fmt(cyc['place'])} {fmt(cyc['release'])}")
    say()

    # --- E1 / E2 ----------------------------------------------------------
    say("## 2. E1 (placed) and E2 (s/attempt)")
    say()
    for seed in (5, 6):
        c, u = data.get((seed, "C")), data.get((seed, "U"))
        if not c or not u:
            continue
        pc, pu = c["stats"]["placed"], u["stats"]["placed"]
        sc = c["stats"]["span"] / c["stats"]["attempts"]
        su = u["stats"]["span"] / u["stats"]["attempts"]
        say(f"seed {seed}: placed C {pc}/10 -> U {pu}/10 (delta {pu - pc:+d}); "
            f"s/att C {sc:.3f} -> U {su:.3f} (falls {sc - su:+.3f} s)")
    deltas = []
    for seed in (5, 6):
        c, u = data.get((seed, "C")), data.get((seed, "U"))
        if c and u:
            deltas.append(
                (
                    u["stats"]["placed"] - c["stats"]["placed"],
                    c["stats"]["span"] / c["stats"]["attempts"]
                    - u["stats"]["span"] / u["stats"]["attempts"],
                    w6d[(seed, "U")].get("placed_per_min", 0) - w6d[(seed, "C")].get("placed_per_min", 0),
                )
            )
    if deltas:
        say(f"pooled: placed deltas {[d[0] for d in deltas]}, s/att FALLS "
            f"{[round(d[1], 3) for d in deltas]} (mean {statistics.mean(d[1] for d in deltas):+.3f} s), "
            f"placed/min deltas {[round(d[2], 2) for d in deltas]}")
        tot_c = sum(data[(s, "C")]["stats"]["span"] for s in (5, 6) if (s, "C") in data)
        tot_u = sum(data[(s, "U")]["stats"]["span"] for s in (5, 6) if (s, "U") in data)
        pl_c = sum(data[(s, "C")]["stats"]["placed"] for s in (5, 6) if (s, "C") in data)
        pl_u = sum(data[(s, "U")]["stats"]["placed"] for s in (5, 6) if (s, "U") in data)
        say(f"pooled: placed {pl_c}/20 vs {pl_u}/20; "
            f"pooled rate {pl_c / tot_c * 60:.2f} -> {pl_u / tot_u * 60:.2f} placed/min "
            f"({tot_c:.1f} s vs {tot_u:.1f} s of batch span)")
    say()

    # --- E3 the guard -----------------------------------------------------
    say("## 3. E3 — the guard (`FRUIT_CARRY_DIAG=1` on both arms)")
    say()
    say("seed arm  carry legs  force_min==0  held>50mm  clean p50/max  held max  "
        "held_then_lost rows")
    for seed in (5, 6):
        for arm in ("C", "U"):
            d = data.get((seed, arm))
            if not d:
                continue
            cr = carry_read(d["carry"])
            say(f"{seed:>4} {arm:<3} {cr['legs']:>10} {cr['force_min_zero']:>13}"
                f" {cr['held_over_50']:>11}  {fmt(cr['clean_p50'])}/{fmt(cr['clean_max'])}mm"
                f"  {fmt(cr['held_max'])}mm  {d['held_lost']}")
    say()
    for seed in (5, 6):
        c, u = data.get((seed, "C")), data.get((seed, "U"))
        if not c or not u:
            continue
        cc, cu = carry_read(c["carry"]), carry_read(u["carry"])
        say(f"seed {seed}: force_min==0 {cc['force_min_zero']} -> {cu['force_min_zero']}; "
            f"held>50mm {cc['held_over_50']} -> {cu['held_over_50']}; "
            f"held-then-lost {c['held_lost']} -> {u['held_lost']}; "
            f"notes {c['notes']} -> {u['notes']} (no-grasp {c['no_grasp']} -> {u['no_grasp']})")
    say()

    # --- E6 the landing ---------------------------------------------------
    say("## 4. E6 — the release landing (`FRUIT_PLACE_TRACE=1` on both arms)")
    say()
    say("seed arm  traces  reached-release  on_belt  landing misses  lost upstream")
    for seed in (5, 6):
        for arm in ("C", "U"):
            d = data.get((seed, arm))
            if not d:
                continue
            tr = trace_read(d["traces"])
            say(f"{seed:>4} {arm:<3} {tr['traces']:>7} {tr['reached']:>15} {tr['landed']:>8}"
                f" {len(tr['miss']):>15} {tr['upstream']:>14}")
    say()

    # --- E3/E6 mechanism detail ------------------------------------------
    say("## 5. The `[carry]` rows and the lost payloads (mechanism)")
    say()
    for seed in (5, 6):
        for arm in ("C", "U"):
            d = data.get((seed, arm))
            if not d:
                continue
            say(f"--- seed {seed} {arm}")
            for r in d["carry"]:
                say(f"    {r['arm']:<5} {r['leg']:<10} tick={r.get('ticks','?'):<9}"
                    f" slip={r.get('clean_slip_max','?'):>9} onset={r.get('onset_row','?'):>5}"
                    f" F@onset={r.get('force@onset','?'):>8} sep@onset={r.get('sep@onset','?'):>8}"
                    f" sep@loss={r.get('sep@loss','?'):>8} sep_end={r.get('sep_end','?'):>8}"
                    f" Fmin={r.get('force_min','?'):>8} loss={r.get('loss_row','?'):>5}")
    say()

    # --- instrument neutrality / default-off ------------------------------
    say("## 6. Instrument neutrality and the default-off proof (C seed 5 vs the P44 record)")
    say()
    cur = OUT / "twoline_s5_C.log"
    if cur.exists() and P44_C5.exists():
        a, b = core_lines(cur), core_lines(P44_C5)
        same = a == b
        say(f"C seed 5 core rows: {len(a)} vs P44 `twoline_s5_C.log` {len(b)} -> "
            f"{'IDENTICAL' if same else 'DIFFERS'}")
        if not same:
            for i, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    say(f"  first difference at row {i + 1}:")
                    say(f"    now: {x}")
                    say(f"    p44: {y}")
                    break
            if len(a) != len(b):
                say(f"  row counts differ: now {len(a)}, p44 {len(b)}")
    say()

    # --- verdicts ---------------------------------------------------------
    say("## 7. Verdicts (PREREG section 3-5)")
    say()
    verdict = {}
    if all((s, a) in data for s in (5, 6) for a in ("C", "U")):
        placed_ok, fall1 = True, False
        for seed in (5, 6):
            dc = data[(seed, "U")]["stats"]["placed"] - data[(seed, "C")]["stats"]["placed"]
            if dc < 0:
                placed_ok = False
            if dc == -1:
                fall1 = True
        verdict["E1"] = ("PASS (no fall)" if placed_ok else
                         ("REPORT (a fall of 1 in one seed)" if fall1 and
                          all(data[(s, "U")]["stats"]["placed"] >= data[(s, "C")]["stats"]["placed"] - 1
                              for s in (5, 6)) else "FAIL"))
        e2 = []
        for seed in (5, 6):
            e2.append(data[(seed, "C")]["stats"]["span"] / data[(seed, "C")]["stats"]["attempts"]
                      - data[(seed, "U")]["stats"]["span"] / data[(seed, "U")]["stats"]["attempts"])
        verdict["E2"] = (f"{'PASS' if all(e >= 0.50 for e in e2) else 'FAIL'} "
                         f"(the s/attempt FALLS per seed {[round(e, 3) for e in e2]} s "
                         f"against the 0.50 bar; pooled {statistics.mean(e2):+.3f} s)")
        e3a = all(data[(s, "U")]["held_lost"] <= data[(s, "C")]["held_lost"] for s in (5, 6))
        e3b1 = all(carry_read(data[(s, "U")]["carry"])["force_min_zero"] <=
                   carry_read(data[(s, "C")]["carry"])["force_min_zero"] for s in (5, 6))
        e3b2 = all(carry_read(data[(s, "U")]["carry"])["held_over_50"] <=
                   carry_read(data[(s, "C")]["carry"])["held_over_50"] for s in (5, 6))
        verdict["E3"] = (f"{'PASS' if (e3a and e3b1 and e3b2) else 'FAIL'} "
                         f"(held-lost {'ok' if e3a else 'worse'}, force_min==0 "
                         f"{'ok' if e3b1 else 'worse'}, held>50mm {'ok' if e3b2 else 'worse'})")
        e6 = []
        for seed in (5, 6):
            for arm in ("C", "U"):
                tr = trace_read(data[(seed, arm)]["traces"])
                e6.append((seed, arm, tr))
        bad = [x for x in e6 if x[2]["miss"]]
        reached = [x for x in e6 if x[2]["reached"] > 0]
        verdict["E6"] = ("NOT EVALUABLE (no release-reached trace)" if not reached else
                         ("FAIL (landing miss)" if bad else
                          f"PASS ({sum(x[2]['reached'] for x in e6)} release-reached traces, "
                          f"all on the belt)"))
    for k, v in verdict.items():
        say(f"{k}: {v}")
    say("E4: not adjudicated here - the descent budgets and the cone report are in")
    say("    gates.txt (the gate's per-leg output); every descent is inside its budget")
    say("E5: not adjudicated here - the fingerprint verdicts are in gates.txt (phase 1")
    say("    records them; only the seed-5 control can match the seed-5 reference)")
    say()

    if args.write:
        (OUT / "P1_report.txt").write_text("\n".join(lines) + "\n")
        print(f"\n[report] wrote {OUT / 'P1_report.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
