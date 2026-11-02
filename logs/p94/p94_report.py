"""P94 report: the fix's endpoints, the prefix identity, the budgets, the wall.

    python3 logs/p94/p94_report.py                  # -> logs/p94/p94_report.txt
    python3 logs/p94/p94_report.py --same A B       # one prefix/identity pair

Read-only. Reads the phase's records, `logs/p92/census.py`'s classifier (through
`logs/p94/census.py`) and `logs/p80/p80lib.py`'s throughput metrics.

**F2 (the prefix identity).** A treatment cell must be line-for-line identical to
its same-seed control on the `[fruit]` stream up to the **first `carry-assist`
row whose reading is above the bound** - the first leg the guard acts on. The
guard changes one command on one leg and draws no RNG, so any difference before
that row would be attributable to the tree, not the fix. The simulator's own
startup lines carry wall-clock timestamps, so the comparison is on the `[fruit]`
stream (the project's convention since `logs/p82`), not the raw file.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "logs", "p80"))

import census as p94  # noqa: E402
import p80lib  # noqa: E402

BOUND_MM = 200
#: seeds and their control records (the pre-fix cells), and the tag prefix.
SEEDS = [
    (5, "logs/p92/C5.log", "T5"),
    (6, "logs/p92/C6.log", "T6"),
    (101, "logs/p93/C101.log", "T101"),
    (202, "logs/p93/C202.log", "T202"),
]
DIAG = re.compile(
    r"\[diag\] carry-assist (?:left|right) (?:\w+) tick 0: "
    r"cmd_centre=\[(?P<centre>[^\]]+)\] offset=\[[^\]]+\] \|offset\|=(?P<mag>\d+) mm "
    r"jaw_target=\[(?P<target>[^\]]+)\]"
)


def fruit_lines(path: str) -> list[str]:
    with open(os.path.join(ROOT, path), encoding="utf-8", errors="ignore") as fh:
        return [ln.rstrip("\n") for ln in fh if ln.startswith("[fruit]")]


def guarded_index(lines: list[str]) -> int | None:
    """Index of the first `carry-assist` row the guard acted on (None = never)."""
    for i, ln in enumerate(lines):
        m = DIAG.search(ln)
        if not m:
            continue
        if int(m.group("mag")) <= BOUND_MM:
            continue
        centre = [float(v) for v in m.group("centre").replace(" ", "").split(",")]
        target = [float(v) for v in m.group("target").replace(" ", "").split(",")]
        if max(abs(a - b) for a, b in zip(centre, target)) <= 1e-6:
            return i
    return None


def compare(a: str, b: str) -> dict:
    """Longest common `[fruit]` prefix of a and b, and b's first guarded index."""
    la, lb = fruit_lines(a), fruit_lines(b)
    n = 0
    for x, y in zip(la, lb):
        if x != y:
            break
        n += 1
    return {
        "a": a, "b": b, "common": n, "len_a": len(la), "len_b": len(lb),
        "guarded": guarded_index(lb),
        "identical": n == len(la) == len(lb),
    }


def f(v, nd=2):
    return "-" if v is None else f"{v:.{nd}f}"


def section_cells() -> dict:
    print("=" * 104)
    print("1. THE CELLS - placed, classes, and the commanded-jump census (E1-E3)")
    print("=" * 104)
    print(f"  bound {BOUND_MM} mm; 'read' = |_gripper_offset|, 'applied' = the command's jump")
    print(f"{'cell':<5} {'seed':>4} {'att':>4} {'ok':>3} {'rate':>6} {'cnp':>4} {'never':>5} "
          f"{'legs':>4} {'read max':>8} {'>bnd':>5} {'applied max':>11} {'guarded':>7}")
    out = {}
    seed_of = {"C5": 5, "T5": 5, "N5": 5, "P5": 5, "C6": 6, "T6": 6,
               "C101": 101, "T101": 101, "C202": 202, "T202": 202}
    cells = ["C5", "T5", "C6", "T6", "C101", "T101", "C202", "T202", "N5", "P5"]
    for tag in cells:
        path = f"logs/p94/{tag}.log" if tag not in ("C5", "C6", "C101", "C202") else {
            "C5": "logs/p92/C5.log", "C6": "logs/p92/C6.log",
            "C101": "logs/p93/C101.log", "C202": "logs/p93/C202.log"}[tag]
        if not os.path.exists(os.path.join(ROOT, path)):
            continue
        rec = p94.parse(os.path.join(ROOT, path))
        rows = p94.leg_rows(tag, 0, "x", os.path.join(ROOT, path))
        s = p94.summary(rows)
        counts: dict[str, int] = {}
        for att in rec["attempts"]:
            counts[att["cls"]] = counts.get(att["cls"], 0) + 1
        ok = sum(1 for a in rec["attempts"] if a["placed"])
        out[tag] = {"seed": seed_of.get(tag), "attempts": len(rec["attempts"]), "placed": ok,
                    "classes": counts, "offsets": s, "path": path}
        print(f"{tag:<5} {seed_of.get(tag, '-'):>4} {len(rec['attempts']):>4} {ok:>3} "
              f"{f(ok / max(1, len(rec['attempts']))):>6} "
              f"{counts.get('cnp', 0):>4} {counts.get('never_held', 0):>5} {s['n']:>4} "
              f"{s['read_max'] if s['read_max'] is not None else -1:>8} "
              f"{s['over_bound']:>5} {s['applied_max'] if s['applied_max'] is not None else -1:>11.3f} "
              f"{s['guarded']:>7}")

    print()
    print("  per seed, control -> fix (E3: no seed may lose a placement)")
    for seed, cpath, ttag in SEEDS:
        ctag = os.path.splitext(os.path.basename(cpath))[0]
        c = out.get(ctag)
        t = out.get(ttag)
        if not c or not t:
            print(f"  seed {seed}: (missing)")
            continue
        print(f"  {seed:>4}  placed {c['placed']:>2}/{c['attempts']} -> {t['placed']:>2}/{t['attempts']} "
              f"| cnp {c['classes'].get('cnp', 0)} -> {t['classes'].get('cnp', 0)} "
              f"| never {c['classes'].get('never_held', 0)} -> {t['classes'].get('never_held', 0)} "
              f"| applied max {c['offsets']['applied_max'] * 1000:.0f} -> "
              f"{t['offsets']['applied_max'] * 1000:.0f} mm")
    return out


def section_throughput(out: dict) -> None:
    print()
    print("=" * 104)
    print("2. THE DELIVERED SIDE (E4: interval both ways, both denominators, wall) - report only")
    print("=" * 104)
    print("  window = placement window; batch = first attempt start -> last attempt end;")
    print("  wall = the stamp stream; wall/min = 60 * placed / wall.")
    print(f"  {'cell':<5} {'ok':>3} {'interval':>8} {'p90':>6} {'window':>7} {'batch':>6} "
          f"{'wall':>7} {'wall/pick':>9} {'wall/min':>8} {'sim':>6} {'w/sim':>6}")
    for tag, cell in out.items():
        m = p80lib.metrics(os.path.join(ROOT, cell["path"]))
        st = m["stats"]
        print(f"  {tag:<5} {m['placed']:>3} {f(m['pooled']['mean']):>8} "
              f"{f(m['pooled']['p90'], 1):>6} {f(m['window_rate']):>7} "
              f"{f(m['batch_rate']):>6} {f(st['wall'], 1):>7} "
              f"{f(st['wall_per_pick'], 1):>9} "
              f"{f(None if not st['wall'] else 60.0 * m['placed'] / st['wall']):>8} "
              f"{f(st['sim_total'], 1):>6} {f(st['wall_over_sim']):>6}")
    print("  per-arm interval (the overlap is where a two-line delta hides):")
    for tag, cell in out.items():
        m = p80lib.metrics(os.path.join(ROOT, cell["path"]))
        parts = []
        for arm, a in sorted(m["per_arm"].items()):
            parts.append(f"{arm} {a['placed']}/{a['attempts']} int {f(a['interval_mean'])}s")
        print(f"  {tag:<5} " + " | ".join(parts))


def section_prefix() -> bool:
    print()
    print("=" * 104)
    print("4. THE PREFIX IDENTITY (F2, the registered falsifier)")
    print("=" * 104)
    print("  a treatment cell must be identical to its control's `[fruit]` stream up to")
    print("  the FIRST carry-assist row whose reading is above the bound.")
    ok = True
    for seed, cpath, ttag in SEEDS:
        tpath = f"logs/p94/{ttag}.log"
        if not os.path.exists(os.path.join(ROOT, tpath)):
            print(f"  seed {seed}: (missing {tpath})")
            ok = False
            continue
        r = compare(cpath, tpath)
        g = r["guarded"]
        if g is None:
            verdict = "INERT end-to-end" if r["identical"] else "DIFFERS (no guarded leg!)"
            good = r["identical"]
        else:
            verdict = ("prefix holds (first difference IS the guarded leg)"
                       if r["common"] == g else f"prefix BROKEN (diff at {r['common']}, guard at {g})")
            good = r["common"] == g
        ok = ok and good
        print(f"  seed {seed:>3}: {r['common']:>4}/{r['len_b']} common, guarded at "
              f"{'-' if g is None else g}, {r['len_a']} control lines -> {verdict}")
    for label, a, b in (
        ("tree check N5 vs C5", "logs/p92/C5.log", "logs/p94/N5.log"),
        ("post-flip P5 vs T5", "logs/p94/T5.log", "logs/p94/P5.log"),
    ):
        if os.path.exists(os.path.join(ROOT, b)):
            r = compare(a, b)
            print(f"  {label}: {r['common']}/{r['len_b']} common, guarded at {r['guarded']} -> "
                  f"{'IDENTICAL' if r['identical'] else 'DIFFERS'}")
        else:
            print(f"  {label}: (missing {b})")
    return ok


def leg_motion(path: str) -> dict:
    """Per carry leg: the arm's own `|v|max`/`|a|max` beside the leg's `res_end`.

    The `[carry]` row and the leg's `[motion]` row are matched on (leg name, tick
    count): the motion row follows its leg's carry row and both print the leg's
    own tick count, so a two-arm interleave cannot cross them.
    """
    import re as _re
    rows: list[dict] = []
    pending: list[dict] = []
    carry_re = _re.compile(
        r"\[carry\] (?P<arm>left|right) (?P<leg>\w+): ticks=(?P<t1>\d+)/(?P<t2>\d+) (?P<body>.*)$"
    )
    motion_re = _re.compile(
        r"\[motion\] carry (?P<leg>\w+): .*?, (?P<ticks>\d+) ticks,.*?\|v\|max=(?P<v>[\d.]+) "
        r"m/s, \|a\|max=(?P<a>[\d.]+) m/s\^2.*?a_win5=(?P<w>[\d.]+) m/s\^2"
    )
    with open(os.path.join(ROOT, path), encoding="utf-8", errors="ignore") as fh:
        for ln in fh:
            m = carry_re.search(ln)
            if m:
                body = m.group("body")
                row = {
                    "arm": m.group("arm"), "leg": m.group("leg"),
                    "ticks": int(m.group("t1")),
                    "res_end": p94.p92.num(body, "res_end"),
                    "tilt_max": p94.p92.num(body, "tilt_max"),
                    "hold_drift": p94.p92.num(body, "hold_drift"),
                    "clean_slip": p94.p92.num(body, "clean_slip_max"),
                    "force_min": p94.p92.num(body, "force_min"),
                }
                rows.append(row)
                pending.append(row)
                continue
            m = motion_re.search(ln)
            if m:
                for row in reversed(pending):
                    if row["leg"] == m.group("leg") and row["ticks"] == int(m.group("ticks")):
                        row.update(v_max=float(m.group("v")), a_max=float(m.group("a")),
                                   a_win5=float(m.group("w")))
                        pending.remove(row)
                        break
    return rows


def section_guarded(cells: dict) -> None:
    print()
    print("=" * 104)
    print("3. THE GUARDED LEGS - the reading it refused, and the arm's own motion")
    print("=" * 104)
    print("  `before` is the same (cell-family, attempt, arm, leg) in the pre-fix control;")
    print("  `-` means the branch had already moved there (the stream diverged upstream).")
    print("  |v|max / |a|max are the *arm's* (the `[motion] carry` row), never in-hand.")
    motion = {}
    for tag, cell in cells.items():
        motion[tag] = leg_motion(cell["path"])
    for seed, cpath, ttag in SEEDS:
        ctag = os.path.splitext(os.path.basename(cpath))[0]
        if ctag not in cells or ttag not in cells:
            continue
        crow = p94.leg_rows(ctag, seed, "control", cells[ctag]["path"])
        trow = p94.leg_rows(ttag, seed, "fix", cells[ttag]["path"])
        # ordinal within the cell, so the [carry] row can be matched positionally
        for i, r in enumerate(trow):
            if r["read"] <= BOUND_MM:
                continue
            mt = motion[ttag][i] if i < len(motion[ttag]) else {}
            match = "match" if (mt.get("arm"), mt.get("leg")) == (r["arm"], r["leg"]) else "MISMATCH"
            ctrl = next((c for c in crow if (c["attempt"], c["arm"], c["leg"])
                         == (r["attempt"], r["arm"], r["leg"]) and c["read"] > BOUND_MM), None)
            cm = {}
            if ctrl is not None:
                k = crow.index(ctrl)
                cm = motion[ctag][k] if k < len(motion[ctag]) else {}
            print(f"  {ttag} att {r['attempt']:>2} {r['arm']:<5} {r['leg']:<10} "
                  f"read {r['read']:>5} mm -> applied {r['applied'] * 1000:>6.1f} mm  "
                  f"({r['class']}, {match})")
            print(f"        fix : |v|max {f(mt.get('v_max'), 3)}  |a|max {f(mt.get('a_max'), 2)}  "
                  f"a_win5 {f(mt.get('a_win5'), 2)}  res_end {f(mt.get('res_end'), 1)} mm  "
                  f"tilt_max {f(mt.get('tilt_max'), 1)} deg")
            if cm:
                print(f"        ctrl: |v|max {f(cm.get('v_max'), 3)}  |a|max {f(cm.get('a_max'), 2)}  "
                      f"a_win5 {f(cm.get('a_win5'), 2)}  res_end {f(cm.get('res_end'), 1)} mm  "
                      f"tilt_max {f(cm.get('tilt_max'), 1)} deg")
            else:
                print("        ctrl: -")


def section_leg_table(cells: dict) -> None:
    """The before/after per-leg table, matched on (attempt, arm, leg, fruit)."""
    lines = []
    lines.append("P94 LEG TABLE - the reading and the applied jump, per leg, control vs fix")
    lines.append("  matched on (attempt, arm, leg, fruit); `-` = the branch had no such leg")
    lines.append("  read = |_gripper_offset| (mm); applied = |jaw_target - cmd_centre| (mm)")
    lines.append("")
    hdr = (f"{'seed':>4} {'att':>3} {'arm':<5} {'leg':<10} {'fruit':<10} "
           f"{'read c':>6} {'read f':>6} {'appl c':>7} {'appl f':>7} {'cls c':<10} {'cls f':<10} {'flag'}")
    for seed, cpath, ttag in SEEDS:
        ctag = os.path.splitext(os.path.basename(cpath))[0]
        if ctag not in cells or ttag not in cells:
            continue
        crow = p94.leg_rows(ctag, seed, "control", cells[ctag]["path"])
        trow = p94.leg_rows(ttag, seed, "fix", cells[ttag]["path"])
        key = lambda r: (r["attempt"], r["arm"], r["leg"], r["fruit"])  # noqa: E731
        cidx = {key(r): r for r in crow}
        tidx = {key(r): r for r in trow}
        lines.append("")
        lines.append(f"seed {seed}  ({ctag} -> {ttag})   {len(crow)} control legs, {len(trow)} fix legs, "
                     f"{len(set(cidx) & set(tidx))} matched")
        lines.append(hdr)
        lines.append("-" * len(hdr))
        for k in sorted(set(cidx) | set(tidx)):
            c = cidx.get(k)
            t = tidx.get(k)
            flag = ""
            if c and t:
                if c["read"] > BOUND_MM:
                    flag = "GUARDED" if t["applied"] <= 1.0 else "NOT GUARDED"
                elif abs(c["applied"] - t["applied"]) > 1.0:
                    flag = "MOVED (F1 FAIL)"
                else:
                    flag = "unchanged"
            else:
                flag = "unpaired"
            lines.append(
                f"{seed:>4} {k[0]:>3} {k[1]:<5} {k[2]:<10} {k[3]:<10} "
                f"{(c['read'] if c else '-'):>6} {(t['read'] if t else '-'):>6} "
                f"{(round(c['applied'] * 1000, 1) if c else '-'):>7} "
                f"{(round(t['applied'] * 1000, 1) if t else '-'):>7} "
                f"{(c['class'] if c else '-'):<10} {(t['class'] if t else '-'):<10} {flag}")
    text = "\n".join(lines)
    with open(os.path.join(HERE, "leg_table.txt"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    moved = [ln for ln in lines if "MOVED (F1 FAIL)" in ln]
    guarded = [ln for ln in lines if "GUARDED" in ln]
    # Treatment legs above the bound that have no control counterpart (the branch
    # had already moved): they are not "pairs", but they are guarded legs.
    unpaired_guarded = []
    for seed, cpath, ttag in SEEDS:
        ctag = os.path.splitext(os.path.basename(cpath))[0]
        if ctag not in cells or ttag not in cells:
            continue
        crow = p94.leg_rows(ctag, seed, "control", cells[ctag]["path"])
        trow = p94.leg_rows(ttag, seed, "fix", cells[ttag]["path"])
        key = lambda r: (r["attempt"], r["arm"], r["leg"], r["fruit"])  # noqa: E731
        ck = set(map(key, crow))
        for t in trow:
            if t["read"] > BOUND_MM and key(t) not in ck:
                unpaired_guarded.append(
                    f"{seed:>4} {t['attempt']:>3} {t['arm']:<5} {t['leg']:<10} {t['fruit']:<10} "
                    f"read {t['read']:>5} applied {t['applied'] * 1000:>5.1f} {t['class']:<10} "
                    f"GUARDED (unpaired - the branch had moved)")
    print()
    print("=" * 104)
    print("5. THE PER-LEG TABLE (F1: no leg below the bound may move)")
    print("=" * 104)
    print(f"  written to logs/p94/leg_table.txt: {len(lines)} lines")
    print(f"  legs the guard acted on (reading above the bound, applied 0): "
          f"{len(guarded) + len(unpaired_guarded)}")
    for ln in guarded:
        print(f"    {ln}")
    for ln in unpaired_guarded:
        print(f"    {ln}")
    print(f"  legs below the bound whose applied jump moved (F1): {len(moved)}"
          + ("" if not moved else "  <== F1 FAILS"))
    for ln in moved[:8]:
        print(f"    {ln}")


def section_accept() -> None:
    """The acceptance A/B: the gate of record's own pair (diag on in both arms)."""
    pre, fix = "logs/p94/accept_ab_pre.log", "logs/p94/accept_ab_fix.log"
    print()
    print("=" * 104)
    print("6. THE ACCEPTANCE A/B (the gate of record, diag on in both arms)")
    print("=" * 104)
    if not (os.path.exists(os.path.join(ROOT, pre)) and os.path.exists(os.path.join(ROOT, fix))):
        print("  (missing the pair)")
        return
    r = compare(pre, fix)
    print(f"  pre-fix (`FRUIT_CARRY_OFFSET_MAX=0`) -> fix (unset): {r['common']}/{r['len_b']} "
          f"common `[fruit]` lines, first guarded row at {r['guarded']}")
    for tag, path in (("pre-fix", pre), ("fix", fix)):
        rec = p94.parse(os.path.join(ROOT, path))
        ok = sum(1 for a in rec["attempts"] if a["placed"])
        print(f"  {tag:<8} {ok}/{len(rec['attempts'])} placed, "
              f"cnp {sum(1 for a in rec['attempts'] if a['cls'] == 'cnp')}, "
              f"never_held {sum(1 for a in rec['attempts'] if a['cls'] == 'never_held')}")
    for tag, path in (("pre-fix", pre), ("fix", fix)):
        rows = p94.leg_rows(tag, 5, tag, os.path.join(ROOT, path))
        big = [x for x in rows if x["read"] > BOUND_MM]
        print(f"  {tag:<8} legs={len(rows)}  readings {min(x['read'] for x in rows)}-"
              f"{max(x['read'] for x in rows)} mm  above bound {len(big)}  "
              f"applied max {max(x['applied'] for x in rows) * 1000:.1f} mm")
        for x in big:
            print(f"           att {x['attempt']:>2} {x['arm']:<5} {x['leg']:<10} "
                  f"{x['fruit']:<9} read {x['read']:>5} applied {x['applied'] * 1000:>6.1f} "
                  f"({x['class']})")


def section_budgets() -> None:
    print()
    print("=" * 104)
    print("7. THE MOTION BUDGETS (E5) and the gates")
    print("=" * 104)
    for path in sorted(glob.glob(os.path.join(HERE, "*.budgets"))):
        with open(path, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
        legs = re.findall(r"^ +(\d+) +(\d+\.\d+)c", text, re.M)
        over = [ln for ln in text.splitlines()
                if re.match(r"^ +\d+ +\d+\.\d+c", ln) and not ln.rstrip().endswith("ok")]
        fp = re.search(r"fingerprint: (matches|DIFFERS)", text)
        cone = re.search(r"worst held-grip cone: ([\d.]+x) budget", text)
        print(f"  {os.path.basename(path):<14} {len(legs):>3} descent legs, "
              f"{len(over)} over budget | {cone.group(1) if cone else 'cone n/a'} | "
              f"{'fp ' + fp.group(1) if fp else 'fp n/a'}")
        for ln in over:
            print(f"      {ln.strip()}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--same", nargs=2, metavar=("A", "B"))
    args = ap.parse_args()
    if args.same:
        r = compare(*args.same)
        print(json.dumps(r, indent=1))
        return 0
    out = section_cells()
    section_throughput(out)
    section_guarded(out)
    ok = section_prefix()
    section_leg_table(out)
    section_accept()
    section_budgets()
    print()
    print(f"  F2 (prefix identity) on every treatment cell: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
