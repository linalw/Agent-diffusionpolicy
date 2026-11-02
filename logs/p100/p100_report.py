#!/usr/bin/env python3
"""P100 report: the park return's fixed clock, measured on both arms.

    python3 logs/p100/p100_report.py                 # every cell it finds
    python3 logs/p100/p100_report.py --blocks        # the park block table only
    python3 logs/p100/p100_report.py --clearance     # the X5 clearance census
    python3 logs/p100/p100_report.py --same A.log B.log   # line identity
    python3 logs/p100/p100_report.py --check         # the gates, exit 1 on fail

Read-only, offline. Four layers, each reusing the record's own parser rather
than re-deriving it:

* **the park block** - `[ready]` rows (P9-A's pure-reporting row, `FRUIT_READY_DIAG=1`)
  give the block's decomposition `catch_up + lift + blend + settle` in ticks,
  `q_step` (the ramp's peak *commanded* per-tick joint step) and `post_err` (the
  achieved residual). The `park moving -> park done` interval from
  `FRUIT_BIARM_PARK_TRACE=1` is the same block in wall-clock sim seconds and is
  printed beside it as the cross-check (`ticks / 120`).
* **the slot wait split and the interval** - `logs/p99/census.py`'s `timeline`
  and `interval`, the derivations P99 validated to the digit against the
  published records.
* **the delivered side** - `logs/p80/p80lib.py`'s `metrics`: the pooled and
  per-arm interval, both `placed/min` denominators, `placed/min wall` from the
  per-line stamps, the per-arm idle fraction and the class/reason ledger.
* **the clearance census** - the JSONL `FRUIT_BIARM_TRACE=1` appends (`min_m`
  per sample): the exact minimum, the count and share below 30 mm and 10 mm, the
  link pairs, and the contiguous `< 30 mm` bands.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.join(ROOT, "logs", "p100")


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p80lib = _load("p80lib", os.path.join(ROOT, "logs/p80/p80lib.py"))
p99 = _load("p99census", os.path.join(ROOT, "logs/p99/census.py"))

CONTROL_DT = 1.0 / 120.0

READY = re.compile(
    r"\[ready\] (?P<arm>\w+) skip=(?P<skip>\d+) staged=(?P<staged>\d+) "
    r"pre_err=(?P<pre>[0-9.]+) dg=(?P<dg>[0-9.]+) catch_up=(?P<cu>\d+) "
    r"lift=(?P<lift>\d+) blend=(?P<blend>\d+) settle=(?P<settle>\d+) "
    r"ramp_err=(?P<ramp>[0-9.]+) q_step=(?P<qs>[0-9.]+) "
    r"post_err=(?P<post>[0-9.]+) rec=(?P<rec>\d+)"
)
PROFILE = re.compile(r"\[biarm\] park profile: (?P<label>\S+) scope=(?P<scope>\S+) "
                     r"blend=(?P<blend>\d+) settle=(?P<settle>\d+) "
                     r"\((?P<ticks>\d+) ticks; shipped (?P<shipped>\d+), "
                     r"saved (?P<saved>-?\d+)\)")
LANDING = re.compile(
    r"place low.*?release_bottom=(?P<bottom>[+-]?[0-9.]+)\s*mm.*?on_belt=(?P<on>\w+)"
)
#: `FRUIT_PLACE_TRACE=1` rows (`[fruit] [place-trace] ...`) - the release row
#: carries the landing verdict; its exact wording is the P82/P86 one and is
#: parsed defensively here (only the payload-present rows matter).
RELEASE_ON = re.compile(r"on_belt=(?P<on>True|False)")
RELEASE_BOTTOM = re.compile(r"release_bottom=(?P<bottom>[+-]?[0-9.]+)")

CELLS = ("C5", "T5", "C6", "T6", "C101", "T101", "C202", "T202")
SEEDS = (("5", "C5", "T5"), ("6", "C6", "T6"),
         ("101", "C101", "T101"), ("202", "C202", "T202"))


def park_rows(path: str) -> tuple[list[dict], list[dict]]:
    """(`[ready]` rows taken **inside a park**, the pre-session prime rows).

    The pairing is sequential, not positional: a `[ready]` row belongs to a park
    iff its arm has an open `park moving` marker (`FRUIT_BIARM_PARK_TRACE=1`).
    The driver's own pre-session prime transit prints the same `[ready]` row with
    no park around it, and those two rows are **not** the block under test - so
    they are returned separately rather than mixed into the block statistics.
    """
    parks, prime = [], []
    open_park: dict[str, bool] = {"left": False, "right": False}
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            m = re.search(r"\[biarm\] (\w+): park (moving|done)", line)
            if m:
                open_park[m.group(1)] = m.group(2) == "moving"
                continue
            m = READY.search(line)
            if not m:
                continue
            ticks = int(m.group("cu")) + int(m.group("lift")) \
                + int(m.group("blend")) + int(m.group("settle"))
            row = {
                "arm": m.group("arm"),
                "skip": int(m.group("skip")),
                "catch_up": int(m.group("cu")),
                "lift": int(m.group("lift")),
                "blend": int(m.group("blend")),
                "settle": int(m.group("settle")),
                "ticks": ticks,
                "q_step": float(m.group("qs")),
                "post_err": float(m.group("post")),
                "ramp_err": float(m.group("ramp")),
                "rec": int(m.group("rec")),
            }
            if open_park.get(row["arm"]):
                parks.append(row)
                open_park[row["arm"]] = False
            else:
                prime.append(row)
    return parks, prime


def profile_row(path: str) -> dict | None:
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            m = PROFILE.search(line)
            if m:
                return {k: (int(v) if k in ("blend", "settle", "ticks",
                                            "shipped", "saved") else v)
                        for k, v in m.groupdict().items()}
    return None


def park_blocks(path: str) -> list[dict]:
    """The `park moving -> park done` blocks, in order (trace cross-check)."""
    parks: dict[str, list[float]] = {"left": [], "right": []}
    started: dict[str, float | None] = {"left": None, "right": None}
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            m = re.search(r"\[biarm\] (\w+): park (moving|done) t=([0-9.]+)s", line)
            if not m:
                continue
            arm, event, t = m.group(1), m.group(2), float(m.group(3))
            if event == "moving":
                started[arm] = t
            elif started[arm] is not None:
                parks[arm].append(t - started[arm])
                started[arm] = None
    return [v for arm in ("left", "right") for v in parks[arm]]


def landing(path: str) -> dict:
    present = on = lost = 0
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            bottom = RELEASE_BOTTOM.search(line)
            if not bottom:
                continue
            value = float(bottom.group("bottom"))
            verdict = RELEASE_ON.search(line)
            if value < 0:
                lost += 1
                continue
            present += 1
            if verdict and verdict.group("on") == "True":
                on += 1
    return {"present": present, "on_belt": on, "upstream_lost": lost}


def block_stats(rows: list[dict]) -> dict:
    runs = [r for r in rows if r["skip"] == 0]
    if not runs:
        return {"n": 0}
    return {
        "n": len(runs),
        "ticks_mean": sum(r["ticks"] for r in runs) / len(runs),
        "blend": sorted({r["blend"] for r in runs}),
        "settle": sorted({r["settle"] for r in runs}),
        "fixed": sum(r["blend"] + r["settle"] for r in runs) / len(runs),
        "q_step_max": max(r["q_step"] for r in runs),
        "post_err_max": max(r["post_err"] for r in runs),
        "rec": sum(r["rec"] for r in runs),
    }


def clearance(path: str) -> dict:
    rows = []
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("{"):
                continue
            import json
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    if not rows:
        return {"n": 0}
    mins = [r["min_m"] for r in rows]
    best = min(rows, key=lambda r: r["min_m"])
    under30 = sum(1 for v in mins if v < 0.030)
    under10 = sum(1 for v in mins if v < 0.010)
    bands = []
    for r in rows:
        if r["min_m"] >= 0.030:
            continue
        if bands and r["t"] - bands[-1]["t1"] < 0.5:
            bands[-1]["t1"] = r["t"]
            bands[-1]["min"] = min(bands[-1]["min"], r["min_m"])
        else:
            bands.append({"t0": r["t"], "t1": r["t"], "min": r["min_m"]})
    return {
        "n": len(rows),
        "min": best["min_m"],
        "min_t": best["t"],
        "min_pair": f"{best['left_link']} vs {best['right_link']}",
        "under30": under30,
        "under30_frac": under30 / len(rows),
        "under10": under10,
        "bands": bands,
    }


def _f(value, nd=2, width=0):
    if value is None or value != value:
        return f"{'-':>{width}}"
    return f"{value:{width}.{nd}f}"


def same_without_ready(a: str, b: str) -> int:
    def stream(path):
        """The `[fruit]` physics stream minus the two instrumentation classes.

        Three reporting classes are dropped, and none of them is a physics row:
        `[ready]` is P100's own (`FRUIT_READY_DIAG=1`, the park block's
        decomposition), `[biarm] park profile:` is P100's own resolution row, and
        `[bed-sel]` is P99's whole selector-reporting block (`FRUIT_BED_DIAG=2`;
        this phase's cells run the shipped `0`, so the class is absent here).
        P99 already proved its block neutral by replaying `logs/p94/{T5,T6}` at
        974/974 and 970/970, so the chain to the record holds. Dropping them is
        the convention P96 set ("the phase's own rows dropped").
        """
        out = []
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if not line.startswith("[fruit]"):
                    continue
                if "[ready]" in line:
                    continue
                if "[bed-sel]" in line:
                    continue
                if "[biarm] park profile:" in line:
                    continue
                out.append(line.rstrip("\n"))
        return out

    left, right = stream(a), stream(b)
    if left == right:
        print(f"  {os.path.basename(a)} vs {os.path.basename(b)}: "
              f"{len(left)}/{len(right)} [fruit] lines, IDENTICAL (no [ready] rows)")
        return 0
    first = next((i for i, (x, y) in enumerate(zip(left, right)) if x != y),
                 min(len(left), len(right)))
    print(f"  {os.path.basename(a)} vs {os.path.basename(b)}: DIFFERS at line "
          f"{first} ({len(left)} vs {len(right)} lines)")
    for i in range(max(0, first - 1), min(first + 2, len(left), len(right))):
        print(f"    A{i}: {left[i][:150]}")
        print(f"    B{i}: {right[i][:150]}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cells", nargs="*")
    ap.add_argument("--blocks", action="store_true")
    ap.add_argument("--clearance", action="store_true")
    ap.add_argument("--same", nargs=2)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if args.same:
        return same_without_ready(*args.same)

    if args.clearance:
        print("P100 clearance census (FRUIT_BIARM_TRACE=1, invasive: report only)")
        print("=" * 96)
        for tag in ("X5C", "X5T"):
            path = os.path.join(HERE, f"{tag}.jsonl")
            if not os.path.exists(path):
                print(f"  {tag}: missing")
                continue
            c = clearance(path)
            print(f"  {tag}: {c['n']} samples, min {c['min'] * 1000:5.1f} mm at "
                  f"t={c['min_t']:.2f}s ({c['min_pair']})")
            print(f"        < 30 mm {c['under30']:5d} ({c['under30_frac'] * 100:4.1f} %)   "
                  f"< 10 mm {c['under10']:4d}   bands(<30 mm) {len(c['bands'])}")
            for band in c["bands"]:
                print(f"        band t={band['t0']:7.2f}-{band['t1']:7.2f}s "
                      f"({band['t1'] - band['t0']:5.2f}s) min {band['min'] * 1000:5.1f} mm")
        return 0

    failures = 0
    summary = []
    for seed, ctag, ttag in SEEDS:
        rows = {}
        for tag in (ctag, ttag):
            path = os.path.join(HERE, f"{tag}.log")
            if not os.path.exists(path):
                rows[tag] = None
                continue
            m = p80lib.metrics(path)
            rec = p99.parse(path)
            tl = p99.timeline(rec)
            guards = [r for arm in ("left", "right") for r in tl[arm]]
            rows[tag] = {
                "metrics": m,
                "ready": park_rows(path)[0],
                "prime": park_rows(path)[1],
                "profile": profile_row(path),
                "blocks": park_blocks(path),
                "landing": landing(path),
                "interval": p99.interval(rec),
                "dead": {
                    "gate": sum(r["park_wait"] for r in guards) / max(1, len(guards)),
                    "park": sum(r["park_move"] for r in guards) / max(1, len(guards)),
                    "feed": sum(r.get("feed", 0.0) for r in guards) / max(1, len(guards)),
                    "poll": sum(0.5 * r["polls"] for r in guards) / max(1, len(guards)),
                },
            }
        summary.append((seed, ctag, ttag, rows))

    print("P100 - the park return's fixed clock")
    print("=" * 96)
    for seed, ctag, ttag, rows in summary:
        control, treat = rows[ctag], rows[ttag]
        print(f"\n### seed {seed}")
        if control is None or treat is None:
            print("  (a cell is missing)")
            failures += 1
            continue
        for tag in (ctag, ttag):
            r = rows[tag]
            prof = r["profile"]
            b = block_stats(r["ready"])
            print(f"  {tag}: profile {prof['label'] if prof else 'MISSING'} "
                  f"blend={prof['blend'] if prof else '-'} "
                  f"settle={prof['settle'] if prof else '-'} "
                  f"saved={prof['saved'] if prof else '-'} ticks")
            print(f"       park blocks n={b.get('n', 0)} "
                  f"ticks mean={_f(b.get('ticks_mean'), 1)} "
                  f"(fixed {_f(b.get('fixed'), 1)}: blend {b.get('blend')} "
                  f"+ settle {b.get('settle')})")
            print(f"       trace blocks (s): "
                  f"{' '.join(f'{v:.2f}' for v in r['blocks'])}")
            print(f"       q_step max={b.get('q_step_max', 0):.4f} rad/tick  "
                  f"post_err max={b.get('post_err_max', 0):.4f} rad  "
                  f"rec={b.get('rec', 0)}")
            m = r["metrics"]
            pooled = m["pooled"]
            print(f"       interval pooled mean={_f(pooled['mean'])} "
                  f"p50={_f(pooled['p50'])} p90={_f(pooled['p90'])} n={pooled['n']}  "
                  f"(p99: {_f(r['interval']['mean'])})")
            print(f"       placed {m['placed']}/{m['attempts']}  "
                  f"window {_f(m['window_rate'])}  batch {_f(m['batch_rate'])}  "
                  f"wall/pick {_f(m['stats']['wall_per_pick'])} s  "
                  f"placed/min wall "
                  f"{_f(60.0 / m['stats']['wall_per_pick'] if m['stats']['wall_per_pick'] else None)}")
            print(f"       dead time/attempt: gate {_f(r['dead']['gate'])} "
                  f"park {_f(r['dead']['park'])} feed {_f(r['dead']['feed'])} "
                  f"poll {_f(r['dead']['poll'])}")
            idle = {arm: v["idle_frac"] for arm, v in m["per_arm"].items()}
            arms = {arm: (v["placed"], v["attempts"], v["interval_mean"])
                    for arm, v in m["per_arm"].items()}
            print(f"       per arm: "
                  + "  ".join(f"{a} {p}/{n} i={_f(i)} idle={_f(idle[a] * 100, 1)}%"
                              for a, (p, n, i) in arms.items()))
            print(f"       s/attempt {_f(m['stats']['per_attempt'])}  "
                  f"attempts/placement "
                  f"{_f(m['attempts'] / m['placed'] if m['placed'] else None)}  "
                  f"pooled p50 {_f(pooled['p50'])}")
            print(f"       classes {m['classes']}  reasons {m['reasons']}")
            print(f"       landing {r['landing']}")
        pb = block_stats(control["ready"])
        pt = block_stats(treat["ready"])
        d_ticks = pt.get("fixed", 0) - pb.get("fixed", 0)
        cb = sorted(control["blocks"])
        tb = sorted(treat["blocks"])
        print(f"  DELTA: fixed clock {d_ticks:+.0f} ticks = {d_ticks * CONTROL_DT:+.3f} s"
              f"   park block mean "
              f"{_f((sum(cb) / len(cb)) if cb else None)} -> "
              f"{_f((sum(tb) / len(tb)) if tb else None)}")
        print(f"         interval "
              f"{_f(control['metrics']['pooled']['mean'])} -> "
              f"{_f(treat['metrics']['pooled']['mean'])}"
              f"  window {_f(control['metrics']['window_rate'])} -> "
              f"{_f(treat['metrics']['window_rate'])}"
              f"  batch {_f(control['metrics']['batch_rate'])} -> "
              f"{_f(treat['metrics']['batch_rate'])}")
        ci, ti = control['metrics'], treat['metrics']
        print(f"         attempts/placement "
              f"{_f(ci['attempts'] / ci['placed'] if ci['placed'] else None)} -> "
              f"{_f(ti['attempts'] / ti['placed'] if ti['placed'] else None)}"
              f"   s/attempt {_f(ci['stats']['per_attempt'])} -> "
              f"{_f(ti['stats']['per_attempt'])}"
              f"   placed/min wall "
              f"{_f(60.0 / ci['stats']['wall_per_pick'] if ci['stats']['wall_per_pick'] else None)} -> "
              f"{_f(60.0 / ti['stats']['wall_per_pick'] if ti['stats']['wall_per_pick'] else None)}")
        # -- the registered clauses --
        ok_block = abs(d_ticks + 75) <= 6
        ok_pose = pt.get("post_err_max", 0) <= 0.05 and pt.get("rec", 0) == 0
        ok_step = pt.get("q_step_max", 0) <= 0.15
        ok_iv = (treat["metrics"]["pooled"]["mean"] or 9e9) < \
                (control["metrics"]["pooled"]["mean"] or 0)
        new_keys = set(treat["metrics"]["reasons"]) - set(control["metrics"]["reasons"])
        ok_land = treat["landing"]["on_belt"] == treat["landing"]["present"]
        print(f"  P1 block {d_ticks:+.0f} ticks ({'PASS' if ok_block else 'FAIL'})"
              f"  P1b pose {'PASS' if ok_pose else 'FAIL'}"
              f"  P1b q_step {'PASS' if ok_step else 'FAIL'}"
              f"  P2 interval {'PASS' if ok_iv else 'FAIL'}"
              f"  P4 new keys {sorted(new_keys) if new_keys else 'none'}"
              f"  P5 landing {'PASS' if ok_land else 'FAIL'}")
        failures += sum(0 if ok else 1 for ok in (ok_block, ok_pose, ok_step, ok_iv, ok_land))
        if new_keys:
            failures += 1
    print()
    print(f"clauses failing: {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
