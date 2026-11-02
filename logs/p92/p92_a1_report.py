"""P92/A1 report: the force servo's contact gate, against the C5/C6 controls.

    python3 logs/p92/p92_a1_report.py            # all sections
    python3 logs/p92/p92_a1_report.py --check    # exit 1 if a section is missing

Read-only. Endpoints, guards and the decision rule are `logs/p92/PREREG_A1.md`;
the class split is `logs/p92/census.py` and the servo read is
`logs/p92/chase.py`, so this report cannot drift from the census.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import census  # noqa: E402
import chase  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "p80lib", os.path.join(ROOT, "logs/p80/p80lib.py"))
p80lib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p80lib)

PAIRS = (("C5", "R5", 5), ("C6", "R6", 6))
#: PREREG_A1 section 2/3
BAR_PLACED = 30
FORCE_FLOOR = 9.0
CNP_MAX = {"C5": 2, "C6": 7}
DIAG = re.compile(r"\[task\] force reentry: (?P<body>.*)$")
LANDING = re.compile(
    r"\[task\]   place trace \w+: release_bottom=(?P<bottom>[+\-\d.]+)mm .*?"
    r"on_belt=(?P<ok>True|False)")


def md5(path: str):
    p = os.path.join(ROOT, path)
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
        return {"tag": tag, "missing": True}
    d = census.parse(path)
    m = p80lib.metrics(path)
    servo = chase.read(path)
    cls = [a["cls"] for a in d["attempts"]]
    for i, r in enumerate(servo):
        r["cls"] = cls[i] if i < len(cls) else "?"
    text = open(path, errors="replace").read()
    diag = [ln for ln in text.splitlines() if "force reentry:" in ln]
    traces = [{"bottom": float(t["bottom"]), "on_belt": t["ok"] == "True"}
              for t in LANDING.finditer(text)]
    return {"tag": tag, "missing": False, "attempts": d["attempts"], "cls": cls,
            "metrics": m, "servo": servo, "diag": diag, "landing": traces,
            "stats": d["stats"]}


def held_force(c: dict):
    """`force_min` median over the held legs (the P41 plateau guard)."""
    vals = []
    for a in c["attempts"]:
        for name, lg in a["legs"].items():
            if (lg["fmax"] or 0.0) > 0.0 and lg["force_min"] is not None:
                vals.append(lg["force_min"])
    if not vals:
        return None, 0
    vals.sort()
    return vals[len(vals) // 2], len(vals)


def main(argv) -> int:
    check = "--check" in argv
    bad = 0
    cells = {}
    for c_tag, r_tag, _ in PAIRS:
        cells[c_tag] = cell(c_tag)
        cells[r_tag] = cell(r_tag)
    print("=" * 100)
    print("P92/A1 - the force servo's contact gate (PREREG_A1)")
    print("=" * 100)

    print("\n## 0 provenance")
    for hdr in ("header.txt", "header_r.txt"):
        path = os.path.join(HERE, hdr)
        if not os.path.exists(path):
            print(f"  {hdr} MISSING"); bad += 1
            continue
        for pinned, name in re.findall(r"^([0-9a-f]{32})  (\S+)$",
                                       open(path).read(), re.M):
            now = md5(name)
            if now is None:
                continue
            if now != pinned:
                print(f"  {name:52s} CHANGED {pinned[:8]} -> {now[:8]}"); bad += 1
    print(f"  PREREG_A1.md md5 {open(os.path.join(HERE, 'PREREG_A1.md5')).read().split()[0]}")
    print(f"  chase.py     md5 {md5('logs/p92/chase.py')}")

    # ---- 1 the chase set ------------------------------------------------- #
    print("\n## 1 the servo's closure per attempt (primary mechanism: PREREG_A1 s2)")
    print(f"  {'cell':5s} {'att':>3s} {'placed':>6s} {'closed>0':>8s} {'chased-fail':>11s} "
          f"{'never':>5s} {'cnp':>4s} {'other':>5s}")
    for tag in ("C5", "R5", "C6", "R6"):
        c = cells[tag]
        if c["missing"]:
            print(f"  {tag}: MISSING"); bad += 1
            continue
        chased = [r for r in c["servo"] if (r["closed"] or 0.0) > 0.0]
        cf = [r for r in chased if not r["placed"]]
        print(f"  {tag:5s} {len(c['cls']):3d} {c['cls'].count('success'):6d} "
              f"{len(chased):8d} {len(cf):11d} {c['cls'].count('never_held'):5d} "
              f"{c['cls'].count('cnp'):4d} "
              f"{len(c['cls']) - c['cls'].count('success') - c['cls'].count('never_held') - c['cls'].count('cnp'):5d}")
    for tag in ("C5", "R5", "C6", "R6"):
        c = cells[tag]
        if c["missing"] or not c["diag"]:
            continue
        print(f"  {tag} reentry diag rows: {len(c['diag'])}  e.g. "
              f"{c['diag'][0].split('[task] ')[-1]}")

    # ---- 2 the primary and the pair -------------------------------------- #
    print("\n## 2 the primary (the placed count) and the per-seed pair")
    pooled_c = pooled_r = 0
    for c_tag, r_tag, seed in PAIRS:
        c, r = cells[c_tag], cells[r_tag]
        if c["missing"] or r["missing"]:
            continue
        pc, pr = c["cls"].count("success"), r["cls"].count("success")
        pooled_c += pc
        pooled_r += pr
        chased_c = sum(1 for x in c["servo"] if (x["closed"] or 0.0) > 0.0)
        chased_r = sum(1 for x in r["servo"] if (x["closed"] or 0.0) > 0.0)
        print(f"  seed {seed}: placed {pc} -> {pr} ({pr - pc:+d})   chase set "
              f"{chased_c} -> {chased_r}   never-held "
              f"{c['cls'].count('never_held')} -> {r['cls'].count('never_held')}   "
              f"cnp {c['cls'].count('cnp')} -> {r['cls'].count('cnp')}")
    print(f"  pooled placed {pooled_c} -> {pooled_r} (bar >= {BAR_PLACED}): "
          f"{'PASS' if pooled_r >= BAR_PLACED else 'FAIL'}")
    if pooled_r < BAR_PLACED:
        bad += 1

    # ---- 3 the guards ---------------------------------------------------- #
    print("\n## 3 guards (PREREG_A1 s3)")
    ok = True
    for tag in ("C5", "R5", "C6", "R6"):
        c = cells[tag]
        if c["missing"]:
            continue
        med, n = held_force(c)
        g1 = (med is not None and med >= FORCE_FLOOR)
        print(f"  G1 held-leg force  {tag}: median force_min {f(med)} N over n={n} held legs "
              f"(>= {FORCE_FLOOR} N): {'PASS' if g1 else 'FAIL'}")
        ok &= g1
    for c_tag, r_tag, _ in PAIRS:
        c, r = cells[c_tag], cells[r_tag]
        if r["missing"]:
            continue
        bound = CNP_MAX[c_tag]
        got = r["cls"].count("cnp")
        print(f"  G2 cnp must not rise  {r_tag}: {got} (bound {bound}) "
              f"{'PASS' if got <= bound else 'FAIL'}")
        ok &= got <= bound
    for tag in ("R5", "R6"):
        c = cells[tag]
        if c["missing"]:
            continue
        guest = [x for x in c["landing"] if x["bottom"] >= 0.0]
        off = [x for x in guest if not x["on_belt"]]
        print(f"  G4 landing {tag}: {len(guest)} payload-present, on belt "
              f"{len(guest) - len(off)}/{len(guest)} {'PASS' if not off else 'FAIL'}")
        ok &= not off
        print(f"  G6 attempts {tag}: {len(c['cls'])} (bar 20) "
              f"{'PASS' if len(c['cls']) == 20 else 'FAIL'}")
        ok &= len(c["cls"]) == 20
        entries = sum(int(v) for ln in c["diag"]
                      for v in re.findall(r"entries=(\d+)", ln))
        gated = sum(int(v) for ln in c["diag"]
                    for v in re.findall(r"gated=(\d+)", ln))
        print(f"  G7 the gate engages {tag}: entries={entries} gated_ticks={gated} "
              f"{'PASS' if entries > 0 and gated > 0 else 'FAIL'}")
        ok &= entries > 0 and gated > 0
    reasons = {}
    for tag in ("R5", "R6"):
        c = cells[tag]
        if c["missing"]:
            continue
        for k, v in c["metrics"]["reasons"].items():
            reasons[k] = reasons.get(k, 0) + v
    print(f"  G3 reasons (treatment): {reasons or 'none'}")
    for tag in ("R5", "R6"):
        bud = os.path.join(HERE, f"{tag}.budgets")
        if os.path.exists(bud):
            text = open(bud, errors="replace").read()
            legs = [ln for ln in text.splitlines()
                    if re.match(r"^ +\d+ +[\d.]+c", ln)]
            over = [ln for ln in legs if not ln.rstrip().endswith(" ok")]
            fp = re.search(r"fingerprint: (matches|DIFFERS)", text)
            print(f"  G5 budgets {tag}: {len(legs)} descent legs, {len(over)} over budget "
                  f"({'PASS' if not over else 'FAIL'}) | fingerprint "
                  f"{fp.group(1) if fp else 'n/a'} (recorded, not gated: D3)")
            ok &= not over
        else:
            print(f"  G5 budgets {tag}: MISSING (run logs/p92/gates.sh)")
            bad += 1

    # ---- 4 the delivered side -------------------------------------------- #
    print("\n## 4 the interval and the wall (P80/186; both denominators)")
    print(f"  {'cell':5s} {'pooled int':>10s} {'p90':>6s} {'L int':>6s} {'R int':>6s} "
          f"{'win/min':>7s} {'batch/min':>9s} {'wall s':>7s} {'placed/min wall':>15s}")
    for tag in ("C5", "R5", "C6", "R6"):
        c = cells[tag]
        if c["missing"]:
            continue
        m = c["metrics"]
        s, arm = m["stats"], m["per_arm"]
        wpm = (60.0 * m["placed"] / s["wall"]) if s["wall"] else None
        print(f"  {tag:5s} {f(m['pooled']['mean']):>10s} {f(m['pooled']['p90']):>6s} "
              f"{f(arm.get('left', {}).get('interval_mean')):>6s} "
              f"{f(arm.get('right', {}).get('interval_mean')):>6s} "
              f"{f(m['window_rate']):>7s} {f(m['batch_rate']):>9s} "
              f"{f(s['wall'], 1):>7s} {f(wpm):>15s}")

    # ---- 5 the verdict --------------------------------------------------- #
    print("\n## 5 the verdict (PREREG_A1 s4)")
    adopt = pooled_r >= BAR_PLACED and ok
    print(f"  placed {pooled_c} -> {pooled_r} (bar {BAR_PLACED}) | guards "
          f"{'all PASS' if ok else 'a guard FAILED'} -> "
          f"{'ADOPT' if adopt else 'NOT ADOPTED'}")
    if check:
        print(f"\n[check] missing/changed sections: {bad}")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
