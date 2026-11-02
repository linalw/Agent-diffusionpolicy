"""P92 report: the failure census, the supply-band change, and the guards.

    python3 logs/p92/p92_report.py              # all sections, stdout
    python3 logs/p92/p92_report.py --check      # exit != 0 if any section is missing

Read-only (opens `logs/p92/*.log`, the p80/p86/p91 records, the header). The
endpoints, the guards and the decision rule are `logs/p92/PREREG.md`'s
(section numbers below are that document's). The class split is
`logs/p92/census.py`'s classifier, so the census and this report cannot drift:
a `cnp` is a payload that left a pinch that existed, a `never_held` is a close
that never made one, and the attempt's own `[carry]` row is the evidence.

Wall and interval definitions are `logs/p80/p80lib.py`'s (which borrows
`scripts/186_w6_report.py`): a placement is the attempt's `t1`; the placement
window is `t_last - t_first` so `60/pooled_interval_mean` is the window rate;
the batch span is `t_last_end - t_first_start`; the wall is
`[run] attempt 0` -> `[fruit] DONE` on the per-line stamp stream.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import sys
from math import comb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import census  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "p80lib", os.path.join(ROOT, "logs/p80/p80lib.py"))
p80lib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p80lib)

CELLS = ("C5", "T5", "C6", "T6")
TREAT = {"T5", "T6"}
#: the record each C cell must replay (`[fruit]` stream, this phase adds no rows)
CONTROL = {"C5": "logs/p91/C5.log", "C6": "logs/p91/C6.log"}
#: the per-seed 20-attempt two-line reference (P87 moved the clock; P80/P86 wrote
#: these two from their own 20-attempt cells, and `configs/` is a 10-attempt file)
REF20 = {"5": "logs/p80/motion_reference_twoline_p80_20.json",
         "6": "logs/p86/motion_reference_twoline_C6_20.json"}
#: the PREREG's own numbers
PRED = {"never_held": {5: 0, 6: 1}, "placed": {5: 17, 6: 12},
        "pooled_never_held": 1, "pooled_placed_lo": 29}
LANDING = re.compile(
    r"\[task\]   place trace \w+: release_bottom=(?P<bottom>[+\-\d.]+)mm .*?"
    r"on_belt=(?P<ok>True|False)")
LATERAL = re.compile(r"\[fruit\] \[supply\].*?lateral x=(?P<xmin>[\d.]+)-(?P<xmax>[\d.]+) m")


def md5(path: str):
    p = os.path.join(ROOT, path) if not os.path.isabs(path) else path
    if not os.path.exists(p):
        return None
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def f(v, nd=2):
    return "-" if v is None else f"{v:.{nd}f}"


def cell(tag: str) -> dict:
    path = os.path.join(HERE, f"{tag}.log")
    if not os.path.exists(path):
        return {"tag": tag, "path": path, "missing": True}
    d = census.parse(path)
    m = p80lib.metrics(path)
    text = open(path, errors="replace").read()
    lat = LATERAL.search(text)
    traces = [{"bottom": float(t["bottom"]), "on_belt": t["ok"] == "True"}
              for t in LANDING.finditer(text)]
    diverts = [ln for ln in text.splitlines() if "diverting" in ln]
    return {
        "tag": tag, "path": path, "missing": False,
        "attempts": d["attempts"], "stats": d["stats"], "noelig": d["noelig"],
        "diverts": diverts, "lateral": (float(lat["xmin"]), float(lat["xmax"])) if lat else None,
        "landing": traces, "metrics": m,
        "cls": [a["cls"] for a in d["attempts"]],
    }


def counts(c: dict, name: str) -> int:
    return c["cls"].count(name)


def xstats(c: dict) -> dict:
    xs = [a["x"] for a in c["attempts"] if a["x"] is not None]
    xs_sorted = sorted(xs)
    n = len(xs_sorted)
    return {"n": n,
            "min": xs_sorted[0] if n else None,
            "p50": xs_sorted[int(0.5 * n)] if n else None,
            "max": xs_sorted[-1] if n else None,
            "n_gt_036": sum(1 for v in xs if v > 0.36),
            "n_gt_039": sum(1 for v in xs if v >= 0.39)}


ORIGIN = re.compile(r"(\(explicit\)|\(two-line\)|\(default\)|\(scope-off\))")


def _norm(line: str) -> str:
    """Drop a profile row's `origin` label: it names where the clock came from,
    not the clock. P87 recorded the same difference as its own deviation A1."""
    return ORIGIN.sub("(origin)", line)


def replay_ok(tag: str) -> tuple[bool, str]:
    """The C cell's `[fruit]` stream against its record (no new rows this phase)."""
    rec = os.path.join(ROOT, CONTROL[tag])
    cur = os.path.join(HERE, f"{tag}.log")
    if not os.path.exists(rec):
        return False, "record missing"
    a = [ln for ln in open(rec, errors="replace").read().splitlines()
         if "fruit]" in ln]
    b = [ln for ln in open(cur, errors="replace").read().splitlines()
         if "fruit]" in ln]
    if len(a) != len(b):
        return False, f"line count {len(a)} vs {len(b)}"
    same = sum(1 for x, y in zip(a, b) if x == y)
    norm = sum(1 for x, y in zip(a, b) if _norm(x) == _norm(y))
    if same == len(a):
        return True, f"{same}/{len(a)} lines byte-identical"
    d = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    return norm == len(a), (
        f"{norm}/{len(a)} identical modulo a profile row's origin label "
        f"({len(d)} raw diff, first at line {d[0] + 1}): "
        f"{a[d[0]].strip()[:90] if d else ''}")


def fisher_2x2(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact for [[a, b], [c, d]] (sum of tables <= p_obs)."""
    from math import comb
    n = a + b + c + d
    r1, r2, c1 = a + b, c + d, a + c
    lo, hi = max(0, c1 - r2), min(r1, c1)

    def prob(k: int) -> float:
        return comb(r1, k) * comb(r2, c1 - k) / comb(n, c1)

    p_obs = prob(a)
    return sum(prob(k) for k in range(lo, hi + 1) if prob(k) <= p_obs * (1 + 1e-9))


def main(argv) -> int:
    check = "--check" in argv
    bad = 0
    cells = {t: cell(t) for t in CELLS}
    print("=" * 100)
    print("P92 - the scenario-side loss: the supply band's top (PREREG logs/p92/PREREG.md)")
    print("=" * 100)

    # ---- 0 provenance ----------------------------------------------------- #
    print("\n## 0 provenance")
    hdr = os.path.join(HERE, "header.txt")
    if not os.path.exists(hdr):
        print("  header.txt MISSING"); bad += 1
    else:
        text = open(hdr).read()
        for path, pinned in re.findall(r"^([0-9a-f]{32})  (\S+)$", text, re.M):
            now = md5(pinned)
            if now is None:
                print(f"  {pinned:56s} ABSENT (pinned {pinned})"); bad += 1
            elif now != path:
                print(f"  {pinned:56s} CHANGED {path[:8]} -> {now[:8]}"); bad += 1
    pre = open(os.path.join(HERE, "PREREG.md5")).read().split()[0]
    print(f"  PREREG.md  md5 {pre}  "
          f"({'matches file' if md5('logs/p92/PREREG.md') == pre else 'CHANGED'})")
    print(f"  census.py  md5 {md5('logs/p92/census.py')}")

    # ---- 1 the manipulation ---------------------------------------------- #
    print("\n## 1 the manipulation (PREREG section 1: the band and the delivered x)")
    for t in CELLS:
        c = cells[t]
        if c["missing"]:
            print(f"  {t}: MISSING"); bad += 1; continue
        x = xstats(c)
        print(f"  {t}: supply lateral x={f(c['lateral'][0])}-{f(c['lateral'][1])} m  "
              f"delivered n={x['n']:2d} min={f(x['min'], 4)} p50={f(x['p50'], 4)} "
              f"max={f(x['max'], 4)}  >0.36: {x['n_gt_036']}  >=0.39: {x['n_gt_039']}")
    cap_ok = all((xstats(cells[t])["max"] or 0) <= 0.362 for t in TREAT
                 if not cells[t]["missing"])
    print(f"  F1 (the band took effect: treatment delivered max <= 0.362 m): "
          f"{'PASS' if cap_ok else 'FAIL'}")
    if not cap_ok:
        bad += 1

    # ---- 2 the census and the primary ------------------------------------ #
    print("\n## 2 the failure census (PREREG section 2; primary = the never-held class)")
    print(f"  {'cell':5s} {'att':>3s} {'placed':>6s} {'cnp':>4s} {'never':>5s} "
          f"{'other':>5s} {'divert':>6s} {'starve':>6s} {'s/att':>6s}")
    for t in CELLS:
        c = cells[t]
        if c["missing"]:
            continue
        m = c["metrics"]
        other = len(c["cls"]) - counts(c, "success") - counts(c, "cnp") - counts(c, "never_held")
        print(f"  {t:5s} {len(c['cls']):3d} {counts(c, 'success'):6d} "
              f"{counts(c, 'cnp'):4d} {counts(c, 'never_held'):5d} {other:5d} "
              f"{len(c['diverts']):6d} "
              f"{c['noelig']['left'] + c['noelig']['right']:6d} "
              f"{f(m['stats']['per_attempt']):>6s}")
    pooled = {}
    for arm in ("control", "treatment"):
        tags = ("C5", "C6") if arm == "control" else ("T5", "T6")
        have = [cells[t] for t in tags if not cells[t]["missing"]]
        pooled[arm] = {
            "n": sum(len(c["cls"]) for c in have),
            "placed": sum(c["cls"].count("success") for c in have),
            "never": sum(c["cls"].count("never_held") for c in have),
            "cnp": sum(c["cls"].count("cnp") for c in have),
        }
    print(f"  control   (C5+C6): {pooled['control']['placed']}/{pooled['control']['n']} "
          f"placed; never-held {pooled['control']['never']}, cnp {pooled['control']['cnp']}")
    print(f"  treatment (T5+T6): {pooled['treatment']['placed']}/{pooled['treatment']['n']} "
          f"placed; never-held {pooled['treatment']['never']}, cnp {pooled['treatment']['cnp']}")
    # the pair, per seed
    for t, seed in (("T5", 5), ("T6", 6)):
        c = cells[t]
        if c["missing"]:
            continue
        got = counts(c, "never_held")
        print(f"  seed {seed}: never-held {got} (predicted {PRED['never_held'][seed]}) "
              f"placed {counts(c, 'success')} (predicted {PRED['placed'][seed]})")
    pooled_never = pooled["treatment"]["never"]
    pooled_placed = pooled["treatment"]["placed"]
    complete = pooled["treatment"]["n"] == 40
    print(f"  PRIMARY (pooled never-held {pooled['control']['never']} -> {pooled_never}, "
          f"predicted {PRED['pooled_never_held']}; placed >= {PRED['pooled_placed_lo']}): "
          f"{'PASS' if pooled_never <= 1 and pooled_placed >= PRED['pooled_placed_lo'] else 'FAIL'}"
          f"{'' if complete else ' [treatment incomplete]'}")
    if complete and pooled["control"]["n"] == 40:
        cc, cn = pooled["control"]["n"], pooled["control"]["never"]
        tc, tn = pooled["treatment"]["n"], pooled["treatment"]["never"]
        print(f"  Fisher 2x2 (never-held vs the rest, two-sided; reported, never the "
              f"decision): control {cn}/{cc - cn} vs treatment {tn}/{tc - tn} -> "
              f"p = {fisher_2x2(cn, cc - cn, tn, tc - tn):.4f}")
    else:
        print("  Fisher 2x2: not computable until both arms are complete")

    # ---- 3 the paired read ----------------------------------------------- #
    print("\n## 3 the paired read (same slot, same species and diameter)")
    for c_tag, t_tag in (("C5", "T5"), ("C6", "T6")):
        c, t = cells[c_tag], cells[t_tag]
        if c["missing"] or t["missing"]:
            continue
        pairs = [(a, b) for a, b in zip(c["attempts"], t["attempts"])
                 if a["fruit"] == b["fruit"] and a["dia_cm"] == b["dia_cm"]]
        same_fruit = len(pairs)
        both = sum(1 for a, b in pairs if a["cls"] == "success" and b["cls"] == "success")
        c_only = sum(1 for a, b in pairs if a["cls"] == "success" and b["cls"] != "success")
        t_only = sum(1 for a, b in pairs if a["cls"] != "success" and b["cls"] == "success")
        print(f"  {c_tag}/{t_tag}: {same_fruit}/20 slots carry the same fruit; "
              f"both placed {both}, control-only {c_only}, treatment-only {t_only}")
        for a, b in pairs:
            if a["cls"] != b["cls"]:
                print(f"     slot {a['fruit']:10s} {a['dia_cm']:.1f} cm  "
                      f"{a['cls']:10s}(x={f(a['x'], 3)}) -> {b['cls']:10s}(x={f(b['x'], 3)})")

    # ---- 4 the interval and the wall ------------------------------------- #
    print("\n## 4 the delivered interval and the wall (both denominators, P80/186)")
    print(f"  {'cell':5s} {'pooled int':>10s} {'p90':>6s} {'L int':>6s} {'R int':>6s} "
          f"{'win/min':>7s} {'batch/min':>9s} {'wall s':>7s} {'placed/min wall':>15s}")
    for t in CELLS:
        c = cells[t]
        if c["missing"]:
            continue
        m = c["metrics"]
        s = m["stats"]
        arm = m["per_arm"]
        wpm = (60.0 * m["placed"] / s["wall"]) if s["wall"] else None
        print(f"  {t:5s} {f(m['pooled']['mean']):>10s} {f(m['pooled']['p90']):>6s} "
              f"{f(arm.get('left', {}).get('interval_mean')):>6s} "
              f"{f(arm.get('right', {}).get('interval_mean')):>6s} "
              f"{f(m['window_rate']):>7s} {f(m['batch_rate']):>9s} "
              f"{f(s['wall'], 1):>7s} {f(wpm):>15s}")

    # ---- 5 the guards ---------------------------------------------------- #
    print("\n## 5 guards")
    ok = True
    cnps = {t: counts(cells[t], "cnp") for t in CELLS if not cells[t]["missing"]}
    cnp_ok = all(cnps.get(t, 0) <= bound for t, bound in (("T5", 2), ("T6", 7))) \
        and all(t in cnps for t in ("T5", "T6"))
    print(f"  G1 cnp must not rise: C5 {cnps.get('C5')} T5 {cnps.get('T5')} / "
          f"C6 {cnps.get('C6')} T6 {cnps.get('T6')} -> "
          f"{'PASS' if cnp_ok else ('incomplete' if len(cnps) < 4 else 'FAIL')}")
    ok &= cnp_ok
    for t in CELLS:
        c = cells[t]
        if c["missing"]:
            continue
        guest = [x for x in c["landing"] if x["bottom"] >= 0.0]
        off = [x for x in guest if not x["on_belt"]]
        print(f"  G2 landing {t}: {len(guest)} payload-present releases, "
              f"on belt {len(guest) - len(off)}/{len(guest)} "
              f"({'PASS' if not off else 'FAIL'})")
        ok &= not off
    reasons = {}
    for t in TREAT:
        c = cells[t]
        if c["missing"]:
            continue
        for k, v in c["metrics"]["reasons"].items():
            reasons.setdefault(k, 0)
            reasons[k] += v
    print(f"  G4 reasons (treatment, pooled): {reasons or 'none'}")
    for t in TREAT:
        c = cells[t]
        if c["missing"]:
            continue
        gate = os.path.join(HERE, f"{t}.gate")
        bud = os.path.join(HERE, f"{t}.budgets")
        if os.path.exists(bud):
            text = open(bud, errors="replace").read()
            legs = [ln for ln in text.splitlines()
                    if re.match(r"^ +\d+ +[\d.]+c", ln)]
            over = [ln for ln in legs if not ln.rstrip().endswith(" ok")]
            fp = re.search(r"fingerprint: (matches|DIFFERS)", text)
            print(f"  G3 budgets {t}: {len(legs)} descent legs, {len(over)} over budget "
                  f"({'PASS' if not over else 'FAIL'}) | fingerprint "
                  f"{fp.group(1) if fp else 'n/a'} (recorded, not gated: no post-P87 "
                  f"20-attempt reference exists)")
            ok &= not over
        else:
            print(f"  G3 budgets {t}: budgets file missing (run logs/p92/gates.sh)")
    for t in ("C5", "C6"):
        if cells[t]["missing"]:
            continue
        same, how = replay_ok(t)
        print(f"  G5 the control replays its record ({t} vs {CONTROL[t]}): {how} "
              f"({'PASS' if same else 'FAIL'})")
        ok &= same
    complete_cells = [t for t in CELLS if not cells[t]["missing"]
                      and len(cells[t]["cls"]) == 20]
    short = [t for t in CELLS if not cells[t]["missing"]
             and cells[t]["cls"] and len(cells[t]["cls"]) != 20]
    print(f"  G6 attempts: {len(complete_cells)}/4 cells at 20 attempts"
          f"{'' if not short else ' - short: ' + ','.join(short)} "
          f"{'PASS' if len(complete_cells) == 4 and not short else 'incomplete'}")
    ok &= len(complete_cells) == 4 and not short
    for t in CELLS:
        c = cells[t]
        if c["missing"]:
            continue
        for ln in c["diverts"]:
            print(f"    {t} diversion: {ln.split('[task] ')[-1]}")

    # ---- 6 the verdict --------------------------------------------------- #
    print("\n## 6 the verdict (PREREG section 4's rule, applied to the numbers above)")
    adopt = (pooled_never <= 1 and pooled_placed >= PRED["pooled_placed_lo"] and ok
             and all(counts(cells[t], "success") >= PRED["placed"][int(t[1])] - 1
                     for t in TREAT if not cells[t]["missing"]))
    print(f"  never-held {pooled_never} (bar <= 1) | placed {pooled_placed} "
          f"(bar >= {PRED['pooled_placed_lo']}) | guards {'all PASS' if ok else 'a guard FAILED'}")
    print(f"  -> {'ADOPT' if adopt else 'NOT ADOPTED'}")
    if check:
        print(f"\n[check] missing/changed sections: {bad}")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
