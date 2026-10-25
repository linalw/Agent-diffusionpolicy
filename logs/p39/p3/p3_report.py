#!/usr/bin/env python3
"""P39 phase 3 - the measurement report (per arm, per battery).

Re-uses `logs/p39/left_corpus.py`'s parser (the phase-1 corpus parser) so the
class census and the per-leg numbers are the *same* code path the F-6 pins were
generated with, and adds what phase 3 needs:

  * the raw / filtered `[fruit]` counts (A2.2 filter: drop `[attitude]`, drop
    the pre-A2.2 `finger tip delta` build print) - `filter_stream.counts`;
  * the class census per arm (`placed` / `cnp` / `no-grasp`) and the starvation
    rows (`no eligible fruit`);
  * the frame-free band: carry legs with in-hand `|v|max` > 0.34 m/s (§1.2);
  * the failure-reason sets, digit-normalised, for the new-reason test;
  * the place-leg `clearance:` rows (the outcome's physical witness);
  * the post-release servo `F_min` (0.00 N on the cnp legs, > 2 N on placed);
  * the `47` probe's jaw floor + finger AABB z-extents (N4 / N4b);
  * the `[attitude]` rows verbatim (the mechanism readout).

    python3 logs/p39/p3/p3_report.py            # every battery + the verdict block
    python3 logs/p39/p3/p3_report.py pear accept
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
sys.path.insert(0, str(HERE))

import filter_stream  # noqa: E402

_spec = importlib.util.spec_from_file_location("left_corpus", ROOT / "logs/p39/left_corpus.py")
left_corpus = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(left_corpus)

BAND = 0.34  # m/s, PREREG section 1.2

BATTERIES: dict[str, dict[str, str]] = {
    "pear": {"C": "pear_C.log", "S": "pear_S.log", "F1": "pear_F1.log"},
    "accept": {"C": "accept_C.log", "S": "accept_S.log", "F1": "accept_F1.log"},
    "probe47": {"C": "probe47_C.log", "S": "probe47_S.log", "F1": "probe47_F1.log"},
    "mech": {"C": "mech_C.log", "S": "mech_S.log", "F1": "mech_F1.log"},
    "twoline": {"C": "twoline_C.log", "S": "twoline_S.log", "F1": "twoline_F1.log"},
}
TITLES = {
    "pear": "Pear battery (PRIMARY) - `FRUIT_SUPPLY_SPECIES=pear ATTEMPTS=10 SEED=5`",
    "accept": "Acceptance - `SKIP_SELFCHECK=1 scripts/accept.sh` (10 attempts, motion gate, fingerprint)",
    "probe47": "`47` probe - `scripts/47_robot_collision.py`",
    "mech": "Mechanism batch - the acceptance scenario + `FRUIT_CARRY_ATTITUDE=1`",
    "twoline": "Two-line gate - `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 ATTEMPTS=10 SEED=5`",
}

RE_JAW = re.compile(r"after driving down: jaw \[([-+0-9.eE]+), ([-+0-9.eE]+), ([-+0-9.eE]+)\]")
RE_SEP = re.compile(r"jaw centre now \[([^\]]+)\] sep=([0-9.]+)")
RE_LINK = re.compile(r"\s+(openarm_left_\w+)\s+y=\[([-+0-9.]+),([-+0-9.]+)\] z=\[([0-9.-]+),([0-9.]+)\]")
RE_ATT = re.compile(r"\[attitude\] (.*)$")
RE_STATS = re.compile(r"\[fruit\] \[stats\].*$")


def norm_note(text: str) -> str:
    """Digit-normalise a note so `attempt 3` / `x=0.17` collide (the 113 rule)."""
    return re.sub(r"[-+]?\d+(?:\.\d+)?", "#", text.strip())


def census(rows: list[dict]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for arm in ("left", "right"):
        sel = [r for r in rows if r["arm"] == arm]
        out[arm] = {
            "attempts": len(sel),
            "placed": sum(1 for r in sel if r["placed"]),
            "cnp": sum(1 for r in sel if left_corpus.classify(r) == "cnp"),
            "no-grasp": sum(1 for r in sel if left_corpus.classify(r) == "no-grasp"),
        }
    return out


def band_legs(rows: list[dict], arm: str) -> dict[str, list[tuple[str, str, float]]]:
    """Carry legs with in-hand |v|max > BAND, split lift/place."""
    over: dict[str, list[tuple[str, str, float]]] = {"lift": [], "place": []}
    for r in rows:
        if r["arm"] != arm:
            continue
        for name, d in r["legs"].items():
            if d["in_hand"] <= BAND:
                continue
            slot = "lift" if name == "grasp_lift" else "place"
            over[slot].append((f"attempt {r['attempt']}", left_corpus.classify(r), d["in_hand"]))
    return over


def report_battery(name: str) -> dict:
    logs = {arm: HERE / rel for arm, rel in BATTERIES[name].items()}
    present = {arm: p for arm, p in logs.items() if p.exists() and p.stat().st_size > 0}
    print(f"\n## {TITLES[name]}\n")
    if not present:
        print("(no logs yet)\n")
        return {}
    print("| arm | log |")
    print("|---|---|")
    for arm, p in present.items():
        print(f"| {arm} | `{p.relative_to(ROOT)}` |")
    print()

    print("### `[fruit]` stream counts (A2.2: raw / `[attitude]` / filtered)\n")
    print("| arm | raw | `[attitude]` | build print | filtered |")
    print("|---|---|---|---|---|")
    counts = {}
    for arm, p in present.items():
        raw, att, filt = filter_stream.counts(str(p))
        counts[arm] = (raw, att, filt)
        print(f"| {arm} | {raw} | {att} | {raw - att - filt} | **{filt}** |")
    print()

    parsed: dict[str, list[dict]] = {}
    for arm, p in present.items():
        left_corpus.starved.clear()
        parsed[arm] = left_corpus.parse(str(p))
        starved = [i for (_p, i) in left_corpus.starved]
        c = census(parsed[arm])
        print(f"**{arm}** - {len(parsed[arm])} scored attempts, starvation slots: "
              f"{starved if starved else 'none'}\n")
        print("| arm | attempts | placed | cnp | no-grasp |")
        print("|---|---|---|---|---|")
        for side in ("left", "right"):
            d = c[side]
            print(f"| {side} | {d['attempts']} | {d['placed']} | {d['cnp']} | {d['no-grasp']} |")
        print()

    print("### Per-attempt rows (parser = `logs/p39/left_corpus.py`)\n")
    print("| arm | # | side | fruit | dia cm | grip-dia mm | close F N | close t | lift | "
          "in-hand lift | in-hand place | place cm/t | clear(place) | outcome |")
    print("|" + "---|" * 14)
    for arm, rows in parsed.items():
        for r in rows:
            grip = ""
            if r["grip_cm"] is not None and r["fruit_cm"] is not None:
                grip = f"{(r['grip_cm'] - r['fruit_cm']) * 10:+.2f}"
            lift = r["legs"].get("grasp_lift", {})
            place = r["legs"].get("place0") or r["legs"].get("place1") or {}
            clear = r["clear"].get("place0") or r["clear"].get("place1") or ("", "")
            clr = f"{clear[0]:+d} {clear[1]}" if isinstance(clear[0], int) else ""
            lift_s = f"{r['lift']:+.3f}" if r["lift"] is not None else ""
            print(f"| {arm} | {r['attempt']} | {r['arm'] or '?'} | {r['species']} {r['grade']} | "
                  f"{r['dia_cm'] if r['dia_cm'] is not None else ''} | {grip} | "
                  f"{r['close_force'] if r['close_force'] is not None else ''} | "
                  f"{r['close_ticks'] if r['close_ticks'] is not None else ''} | "
                  f"{lift_s} | {lift.get('in_hand', '')} | {place.get('in_hand', '')} | "
                  f"{place.get('dist_cm', '')}/{place.get('ticks', '')} | {clr} | "
                  f"{left_corpus.classify(r)} |")
    print()

    print(f"### The frame-free band - carry legs with in-hand `|v|max` > {BAND} m/s\n")
    print("| arm | side | lift legs over | place legs over | legs listed (attempt/class/|v|max) |")
    print("|---|---|---|---|---|")
    bands = {}
    for arm, rows in parsed.items():
        for side in ("left", "right"):
            over = band_legs(rows, side)
            bands[(arm, side)] = over
            listing = ", ".join(
                f"{a}({c})={v:.3f}" for slot in ("lift", "place") for (a, c, v) in over[slot]
            ) or "-"
            print(f"| {arm} | {side} | {len(over['lift'])} | {len(over['place'])} | {listing} |")
    print()

    print("### Failure reasons (digit-normalised notes) + `F_min`\n")
    print("| arm | reasons | placed servo F_min | cnp servo F_min |")
    print("|---|---|---|---|")
    reasons: dict[str, set[str]] = {}
    for arm, rows in parsed.items():
        rs = {norm_note(r["notes"]) for r in rows if r["notes"].strip()}
        reasons[arm] = rs
        placed_fm = [r["servo_fmin"] for r in rows if r["placed"] and r["servo_fmin"] is not None]
        cnp_fm = [r["servo_fmin"] for r in rows
                  if left_corpus.classify(r) == "cnp" and r["servo_fmin"] is not None]
        pf = f"{min(placed_fm):.2f}-{max(placed_fm):.2f} N (n={len(placed_fm)})" if placed_fm else "-"
        cf = f"{min(cnp_fm):.2f}-{max(cnp_fm):.2f} N (n={len(cnp_fm)})" if cnp_fm else "-"
        print(f"| {arm} | {'; '.join(sorted(rs)) if rs else '(none)'} | {pf} | {cf} |")
    print()

    for arm, p in present.items():
        stats = [ln.rstrip() for ln in p.read_text(errors="replace").splitlines()
                 if RE_STATS.search(ln)]
        summary = [ln.rstrip() for ln in p.read_text(errors="replace").splitlines()
                   if "[fruit] [run] summary" in ln]
        if stats or summary:
            print(f"**{arm}** headline:")
            for ln in stats + summary:
                print(f"  {ln}")
            print()

    if name == "probe47":
        print("### `47` probe reading\n")
        print("| arm | jaw floor z (m) | finger links' AABB z | sep (m) |")
        print("|---|---|---|---|")
        floors = {}
        for arm, p in present.items():
            text = p.read_text(errors="replace")
            m = RE_JAW.search(text)
            links = RE_LINK.findall(text)
            sep = RE_SEP.search(text)
            floor = float(m.group(3)) if m else None
            floors[arm] = floor
            zs = ", ".join(f"{n.split('_')[-2]}: [{float(z0):.4f},{float(z1):.4f}]"
                           for (n, _y0, _y1, z0, z1) in links) or "-"
            print(f"| {arm} | {floor:.4f} | {zs} | {sep.group(2) if sep else '-'} |")
        print()
        pair = [a for a in ("S", "F1", "C") if a in floors]
        if "S" in floors and "F1" in floors:
            d = (floors["F1"] - floors["S"]) * 1000.0
            print(f"- **N4**: F1 - S = **{d:+.2f} mm** (delta = -4.000 mm; "
                  f"implied cos(theta) = {d / -4.0:.3f})")
        if "C" in floors and "S" in floors:
            d = (floors["S"] - floors["C"]) * 1000.0
            ok = abs(d) <= 1.5
            print(f"- **N4b**: S - C = **{d:+.2f} mm** ({'PASS' if ok else 'FAIL'} the +/-1.5 mm bar)")
        print()

    if name == "mech":
        print("### `[attitude]` summary (numeric)\n")
        print("`dz` is the model-free achieved standoff (pads' z minus the fruit's z, world); "
              "`lip` is `tip*cos(tilt) - dz`, i.e. **model-derived** (it carries the 80.5 mm base "
              "+ delta), so it is only comparable at equal tilt. A `dz` > 100 mm means the "
              "payload is out of the grip by the leg's end (the escape label).\n")
        print("| arm | side/leg | n | tilt deg | dz mm | lip mm | rows with dz > 100 mm |")
        print("|---|---|---|---|---|---|---|")
        rows_by_arm: dict[str, list[dict]] = {}
        for arm, p in present.items():
            parsed_rows = []
            for text in (m.group(1) for m in (RE_ATT.search(ln) for ln in
                                              p.read_text(errors="replace").splitlines()) if m):
                g = lambda pat: (re.search(pat, text).group(1)  # noqa: E731
                                 if re.search(pat, text) else None)
                parsed_rows.append({
                    "leg": text.split(":")[0],
                    "tilt": float(g(r"tilt=([0-9.]+)deg") or "nan"),
                    "dz": float(g(r"pad_fruit_dz=([-+0-9.]+)mm") or "nan"),
                    "lip": float(g(r"lip=([-+0-9.]+)mm") or "nan"),
                })
            rows_by_arm[arm] = parsed_rows
            keys = sorted({r["leg"] for r in parsed_rows})
            for key in keys:
                sel = [r for r in parsed_rows if r["leg"] == key]
                d = [r["dz"] for r in sel]
                t = [r["tilt"] for r in sel]
                li = [r["lip"] for r in sel]
                print(f"| {arm} | {key} | {len(sel)} | {min(t):.1f}-{max(t):.1f} | "
                      f"{min(d):+.1f}..{max(d):+.1f} | {min(li):+.1f}..{max(li):+.1f} | "
                      f"{sum(x > 100 for x in d)} |")
        print()
        print("### `[attitude]` rows (verbatim, one per carry leg per attempt)\n")
        for arm, p in present.items():
            print(f"**{arm}**\n")
            rows = [m.group(1) for m in (RE_ATT.search(ln) for ln in
                                         p.read_text(errors="replace").splitlines()) if m]
            print("| # | side/leg | tilt deg | tool_axis | tip mm | pad_fruit_dz mm | lip mm | corner 16.65/30.5 |")
            print("|---|---|---|---|---|---|---|---|")
            for i, text in enumerate(rows, 1):
                m_tilt = re.search(r"tilt=([0-9.]+)deg", text)
                m_axis = re.search(r"tool_axis=\(([^)]+)\)", text)
                m_tip = re.search(r"tip=([-+0-9.]+)mm", text)
                m_dz = re.search(r"pad_fruit_dz=([-+0-9.]+)mm", text)
                m_lip = re.search(r"lip=([-+0-9.]+)mm", text)
                m_corner = re.search(r"corner drop 16\.65\*sin\(tilt\)=([-+0-9.]+)mm / "
                                     r"30\.5\*sin\(tilt\)=([-+0-9.]+)mm", text)
                leg = text.split(":")[0]
                print(f"| {i} | {leg} | {m_tilt.group(1) if m_tilt else '?'} | "
                      f"{m_axis.group(1) if m_axis else '?'} | {m_tip.group(1) if m_tip else '?'} | "
                      f"{m_dz.group(1) if m_dz else '?'} | {m_lip.group(1) if m_lip else '?'} | "
                      f"{m_corner.group(1) + ' / ' + m_corner.group(2) if m_corner else '?'} |")
            print()

    if name == "accept":
        print("### The motion gate's own lines\n")
        for arm, p in present.items():
            lines = [ln.rstrip() for ln in p.read_text(errors="replace").splitlines()
                     if ln.startswith("===") or "motion gate" in ln or "fingerprint:" in ln
                     or ln.startswith("PASS") or ln.startswith("FAIL") or "success rate" in ln]
            print(f"**{arm}**")
            for ln in lines:
                print(f"  {ln}")
            print()
    return parsed


def verdict(parsed_by_battery: dict[str, dict[str, list[dict]]]) -> None:
    print("\n## Verdict fields (A1.3 / A2.6)\n")
    pear = parsed_by_battery.get("pear") or {}
    accept = parsed_by_battery.get("accept") or {}

    def left_counts(rows):
        sel = [r for r in rows if r["arm"] == "left"]
        return (len(sel),
                sum(1 for r in sel if r["placed"]),
                sum(1 for r in sel if left_corpus.classify(r) == "cnp"),
                sum(1 for r in sel if left_corpus.classify(r) == "no-grasp"))

    if {"C", "S", "F1"} <= set(pear):
        print("### (a)-(c) the primary, pear battery\n")
        print("| arm | left attempts | left placed | left cnp | left no-grasp | composite (cnp+no-grasp) | right placed |")
        print("|---|---|---|---|---|---|---|")
        for arm in ("C", "S", "F1"):
            n, pl, cnp, ng = left_counts(pear[arm])
            rp = sum(1 for r in pear[arm] if r["arm"] == "right" and r["placed"])
            print(f"| {arm} | {n} | {pl} | {cnp} | {ng} | **{cnp + ng}** | {rp} |")
        print()
        n_c = left_counts(pear["C"])
        n_s, n_f = left_counts(pear["S"]), left_counts(pear["F1"])
        inv = (n_s[0] == n_f[0])
        print(f"- (a) left-attempt count invariant S vs F1: **{'YES' if inv else 'NO'}** "
              f"(S {n_s[0]}, F1 {n_f[0]}) - the verdict is evaluable only if YES")
        if n_s[0] == n_f[0]:
            comp_s, comp_f = n_s[2] + n_s[3], n_f[2] + n_f[3]
            print(f"- (b) F1 vs S: composite {comp_s} -> {comp_f} "
                  f"(**{'falls' if comp_f < comp_s else 'does not fall'}**, "
                  f"delta {comp_f - comp_s:+d}); placed {n_s[1]} -> {n_f[1]} "
                  f"({n_f[1] - n_s[1]:+d}) - the pre-registered bar is a fall >= 2 "
                  f"with placed rising by at least the fall")
        rs = {a: {norm_note(r['notes']) for r in pear[a] if r['notes'].strip()}
              for a in ("C", "S", "F1")}
        for arm in ("S", "F1"):
            new = rs[arm] - rs["C"]
            print(f"- (c) new failure reasons {arm} vs C: {sorted(new) if new else 'none'}")
        print()

    if {"C", "S", "F1"} <= set(accept):
        print("### (e) N1 - the acceptance's placed count and the fingerprint\n")
        print("| arm | placed | left | right | attempts |")
        print("|---|---|---|---|---|")
        placed = {}
        for arm in ("C", "S", "F1"):
            rows = accept[arm]
            placed[arm] = sum(1 for r in rows if r["placed"])
            lo = sum(1 for r in rows if r["arm"] == "left")
            ro = sum(1 for r in rows if r["arm"] == "right")
            print(f"| {arm} | {placed[arm]}/{len(rows)} | {lo} | {ro} | {len(rows)} |")
        print()
        for arm in ("S", "F1"):
            ok = placed[arm] >= placed["C"] - 1
            print(f"- N1 margin {arm}: placed {placed[arm]} vs C {placed['C']} -> "
                  f"**{'PASS' if ok else 'FAIL'}** (bar: >= C - 1 = {placed['C'] - 1})")
        print()

    print("### (d) the secondary band, both batteries\n")
    print("| battery | arm | left lift legs > 0.34 | left place legs > 0.34 | left total |")
    print("|---|---|---|---|---|")
    for name, parsed in parsed_by_battery.items():
        if name not in ("pear", "accept"):
            continue
        for arm in ("C", "S", "F1"):
            if arm not in parsed:
                continue
            over = band_legs(parsed[arm], "left")
            print(f"| {name} | {arm} | {len(over['lift'])} | {len(over['place'])} | "
                  f"**{len(over['lift']) + len(over['place'])}** |")
    print()


def main(argv: list[str]) -> int:
    wanted = argv[1:] or [b for b in BATTERIES]
    parsed_by_battery = {}
    for name in wanted:
        if name not in BATTERIES:
            print(f"unknown battery {name!r}; known: {list(BATTERIES)}")
            return 2
        out = report_battery(name)
        if out:
            parsed_by_battery[name] = out
    verdict(parsed_by_battery)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
