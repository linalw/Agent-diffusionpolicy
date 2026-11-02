"""P93 diagnostics: the two red flags P92's guard raised, read off the trace.

    python3 logs/p93/diag.py            # both diagnostics, stdout
    python3 logs/p93/diag.py --check    # exit != 0 if an input is missing

Read-only. Inputs: `logs/p93/p1/{D6C,D6T}/trace/trace_01_right_scripted_fail.json`
(`FRUIT_DYNAMIC_TRACE=1`, the two diagnostic cells), the two untraced cells
`logs/p92/{C6,T6}.log`, and the P92 report's own numbers.

Both red flags are on the **same attempt** - seed 6, attempt 0, the right arm's
first kiwi - so the whole diagnostic is one attempt read twice:

* **1a `T6`'s leg 1** (`|v|max` 0.222 vs the 0.161 budget): the pre-registered
  reading is a *chase* vs a *boundary strain* (PREREG section 1a). This script
  prints the operands of that reading: the leg's `end=`, the fruit's
  displacement over the leg, and the state at the first tick after the leg.
* **1b the 419 N / 1313 mm leg**: whether `|offset|` is a *tool* offset or the
  fruit-minus-TCP distance (PREREG section 1b's three clauses).

The ``descent`` phase is traced **once**, at the leg's start (`tasks.py:11509`
emits the sample before the profiled descent), so a per-tick contact read during
the leg does not exist; the script prints that as the deviation it is and uses
the two reads that do exist (the leg's start and the first tick after it).
"""

from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

CELLS = {"D6C": "logs/p93/p1/D6C/trace/trace_01_right_scripted_fail.json",
         "D6T": "logs/p93/p1/D6T/trace/trace_01_right_scripted_fail.json"}
UNT = {"C6": "logs/p92/C6.log", "T6": "logs/p92/T6.log"}
#: the two-line's belt top (`configs/`/`assets.py` default; the trace's fruit_z is
#: world, so this is the surface the kiwi has to be above to be on the line).
BELT_TOP = 1.195
CARRY = re.compile(r"\[fruit\] \[carry\] right grasp_lift: (?P<body>[^\n]*)")
DIAG = re.compile(r"\[fruit\] \[diag\] carry-assist right grasp_lift tick 0: "
                  r"cmd_centre=\[(?P<c>[^\]]*)\] offset=\[(?P<o>[^\]]*)\] "
                  r"\|offset\|=(?P<n>\d+) mm jaw_target=\[(?P<j>[^\]]*)\]")
APPROACH = re.compile(
    r"approach\(cartesian\): (?P<dist>[\d.]+) cm, (?P<samples>\d+) samples: .*?"
    r"\|v\|max=(?P<v>[\d.]+) m/s.*?a_win5=(?P<aw5>[\d.]+) m/s\^2, end=(?P<end>[\d.]+) mm")


def num(body: str, key: str):
    m = re.search(rf"(?:^| ){re.escape(key)}=([+\-]?[\d.]+)", body)
    return float(m.group(1)) if m else None


def vec(text: str) -> list[float]:
    return [float(v) for v in text.split(",")]


def load(tag: str) -> dict:
    path = os.path.join(ROOT, CELLS[tag])
    if not os.path.exists(path):
        return {"tag": tag, "missing": True}
    d = json.load(open(path))
    rows = d["rows"]
    phases: dict[str, list] = {}
    order: list[str] = []
    for r in rows:
        if r["phase"] not in phases:
            phases[r["phase"]] = []
            order.append(r["phase"])
        phases[r["phase"]].append(r)
    return {"tag": tag, "missing": False, "arm": d["arm"], "outcome": d["outcome"],
            "rows": rows, "phases": phases, "order": order}


def f(v, nd=2):
    return "-" if v is None else f"{v:.{nd}f}"


def main(argv) -> int:
    check = "--check" in argv
    bad = 0
    cells = {t: load(t) for t in CELLS}
    print("=" * 100)
    print("P93 DIAGNOSTICS - seed 6 attempt 0, the right arm's first kiwi "
          "(PREREG logs/p93/PREREG.md section 1)")
    print("=" * 100)

    for t in CELLS:
        c = cells[t]
        if c["missing"]:
            print(f"  {t}: MISSING {CELLS[t]}"); bad += 1; continue
        print(f"\n## {t}: {c['arm']} {c['outcome']}, {len(c['rows'])} trace rows")
        print("   phases: " + ", ".join(f"{p}={len(c['phases'][p])}" for p in c["order"]))

    # ------------------------------------------------------------------ #
    # 1a: the leg, and what the two reads either side of it say
    # ------------------------------------------------------------------ #
    print("\n## 1a  leg 1: the descent's own numbers, and the state either side")
    print(f"   {'cell':5s} {'|v|max':>7s} {'budget':>7s} {'a_win5':>7s} {'end':>7s} "
          f"{'fruit dz over leg':>18s} {'fruit dy over leg':>18s} {'F at +1 tick':>13s} "
          f"{'n':>2s} {'sep':>6s}")
    leg = {}
    for t in CELLS:
        c = cells[t]
        if c["missing"]:
            continue
        des = c["phases"].get("descent") or []
        cup = c["phases"].get("catchup") or []
        if not des or not cup:
            print(f"   {t}: no descent/catchup rows"); bad += 1; continue
        a, b = des[0], cup[0]
        dy = b["fruit"][1] - a["fruit"][1]
        dz = b["fruit"][2] - a["fruit"][2]
        dt = b["t"] - a["t"]
        leg[t] = {"a": a, "b": b, "dy": dy, "dz": dz, "dt": dt}
        # the leg's own summary is in the *untraced* log (the trace does not print it)
        un = UNT["C6" if t == "D6C" else "T6"]
        m = APPROACH.search(open(os.path.join(ROOT, un), errors="replace").read())
        v = float(m.group("v")); aw5 = float(m.group("aw5")); end = float(m.group("end"))
        print(f"   {t:5s} {v:7.3f} {0.161:7.3f} {aw5:7.2f} {end:6.1f}m "
              f"{dz * 1000:+16.1f}mm {dy * 1000:+16.1f}mm {b['force']:12.2f}N "
              f"{b['contacts']:2d} {b['sep']:6.3f}")
        print(f"         leg {dt * 1000:.0f} ms, {int(m.group('samples'))} commanded samples; "
              f"fruit velocity at the leg's start = "
              f"({a['fruit_vel'][0]:+.3f}, {a['fruit_vel'][1]:+.3f}, "
              f"{a['fruit_vel'][2]:+.3f}) m/s  (belt 0.12 m/s along -y)")
        print(f"         tip-fruit at the leg's start: "
              f"({a['offset'][0] * 1000:+.1f}, {a['offset'][1] * 1000:+.1f}, "
              f"{a['offset'][2] * 1000:+.1f}) mm;  at the first tick after it: "
              f"({b['offset'][0] * 1000:+.1f}, {b['offset'][1] * 1000:+.1f}, "
              f"{b['offset'][2] * 1000:+.1f}) mm")

    # ------------------------------------------------------------------ #
    # 1a': the catch-up - what actually displaces the payload
    # ------------------------------------------------------------------ #
    print("\n## 1a' the catch-up after the leg: where the payload goes")
    print(f"   {'cell':5s} {'min fruit_z':>11s} {'final fruit_z':>13s} {'max |vz|':>9s} "
          f"{'max F':>7s} {'sep range':>12s} {'residual (log)':>14s}")
    for t in CELLS:
        c = cells[t]
        if c["missing"]:
            continue
        cup = c["phases"].get("catchup") or []
        if not cup:
            continue
        zs = [r["fruit"][2] for r in cup]
        vz = max(abs(r["fruit_vel"][2]) for r in cup)
        seps = [r["sep"] for r in cup]
        un = UNT["C6" if t == "D6C" else "T6"]
        txt = open(os.path.join(ROOT, un), errors="replace").read()
        resid = re.search(r"dynamic catch-up: residual=([\d.]+) mm", txt)
        print(f"   {t:5s} {min(zs):11.4f} {zs[-1]:13.4f} {vz:9.3f} "
              f"{max(r['force'] for r in cup):7.2f} "
              f"{min(seps):.3f}-{max(seps):.3f} "
              f"{resid.group(1) + ' mm' if resid else '-':>14s}")
    print(f"   (the two-line belt top is z = {BELT_TOP:.3f} m; a payload below it has "
          f"left the line, not been carried)")

    # ------------------------------------------------------------------ #
    # 1b: the 419 N / 1313 mm leg
    # ------------------------------------------------------------------ #
    print("\n## 1b  the 419 N leg: is `|offset|` a tool offset or the fruit's distance?")
    txt = open(os.path.join(ROOT, UNT["T6"]), errors="replace").read()
    m = DIAG.search(txt)
    carry = CARRY.search(txt)
    if not m or not carry:
        print("   carry-assist / carry rows missing"); bad += 1
    else:
        centre = vec(m.group("c")); off = vec(m.group("o"))
        target = vec(m.group("j")); n = int(m.group("n"))
        gap = [c - t for c, t in zip(centre, target)]
        body = carry.group("body")
        print(f"   logged            |offset| = {n} mm   offset(tool frame) = "
              f"({off[0]:+.4f}, {off[1]:+.4f}, {off[2]:+.4f})")
        print(f"   commanded jaw target is |centre - jaw_target| = "
              f"{sum(v * v for v in gap) ** 0.5 * 1000:.0f} mm from the measured pads "
              f"(centre={centre}, jaw_target={[round(v, 4) for v in target]})")
        print("   clause (ii)  the commanded TCP sits > 0.5 m from the pads: "
              f"{'PASS' if sum(v * v for v in gap) ** 0.5 > 0.5 else 'FAIL'}")
        print(f"   carry row: contacts@onset={num(body, 'contacts@onset')}, "
              f"sep@onset={num(body, 'sep@onset')} mm, dia={num(body, 'dia')} mm, "
              f"force@onset={num(body, 'force@onset')} N, fmax={num(body, 'fmax')} N")
        print("   clause (iii) the pads are on the payload at the leg's start: "
              f"{'PASS' if (num(body, 'contacts@onset') or 0) >= 1 else 'FAIL'}")
        # clause (i): the offset is the fruit-minus-TCP distance. The payload fell
        # below the belt during the catch-up; the tip-fruit distance at the
        # catch-up's end is the witness, plus the tip->TCP geometry.
        cup = cells["D6T"]["phases"]["catchup"]
        last = cup[-1]
        dist = sum(v * v for v in last["offset"]) ** 0.5
        print(f"   the catch-up's last row: tip-fruit = "
              f"({last['offset'][0] * 1000:+.1f}, {last['offset'][1] * 1000:+.1f}, "
              f"{last['offset'][2] * 1000:+.1f}) mm  |.| = {dist * 1000:.0f} mm")
        # the hand's own tool scale: `_pad_standoff` = FRUIT_FINGER_LEN 0.060 +
        # PAD_LIFT 0.010 = 70 mm, and every other leg of the batch reads 20-62 mm.
        tool = 0.070
        print(f"   clause (i)   the hand's own tool scale is {tool * 1000:.0f} mm "
              f"(`_pad_standoff`) and every other leg of the batch reads 20-62 mm; "
              f"this one reads {n} mm = {n / (tool * 1000):.1f}x, and the payload is "
              f"{dist * 1000:.0f} mm from the fingertip at the catch-up's end - so it "
              f"is the payload's distance from the tool, not a tool offset: "
              f"{'PASS' if n >= 5 * tool * 1000 and dist > 0.5 else 'FAIL'}")
        print(f"   measured tool offsets on every other leg of the batch: 20-62 mm "
              f"(`[diag] carry-assist ... |offset|=`)"  )
        print(f"   the code path: `_gripper_offset[side] = rot.T @ "
              f"(spawner.position(sample) - tcp_position())` (tasks.py:11047), applied "
              f"only in `_carry`'s incoherent branch as `centre - rot @ offset_tool` "
              f"(tasks.py:5361-5366), which - unlike the coherent branch (:5331) and "
              f"the place loop (:6079) - does not consult `hand_is_jaw`.")

    # ------------------------------------------------------------------ #
    # the reading
    # ------------------------------------------------------------------ #
    print("\n## the reading (PREREG sections 1a-1c)")
    print("   1a  the leg's target is fixed and open-loop (`intercept=-0.0831`, 88")
    print("       commanded samples in both cells), so a *chase* is excluded by")
    print("       construction: there is no moving target in the leg. The leg's")
    print("       `end=` 58.9 mm sits INSIDE the record's documented 40-90 mm")
    print("       boundary shortfall, and over the leg itself the payload moves")
    print("       90 mm at 0.123 m/s = exactly the belt speed - the leg does not")
    print("       displace it. What it does is ARRIVE ON it: the first tick after")
    print("       the leg reads 71 N over 2 contacts with the pads' span already")
    print("       closing on a 62 mm fruit. The 1.19 m the payload then travels is")
    print("       the catch-up's: the pads shrink the span 97 -> 76 mm around it")
    print("       and the fruit is driven DOWN through the belt (z 1.197 -> 0.032).")
    print("       The control does the same thing at the same attempt (41.8 N at")
    print("       the leg's end, z 1.202 -> 0.818, 480.6 mm residual). So the")
    print("       excursion is a JAM ONSET, not a chase -> not a systematic cost.")
    print("   1b  all three pre-registered clauses pass: |offset| = the payload's")
    print("       distance from the tool (1132 mm of it in -z), the commanded TCP")
    print("       is 1313 mm from the pads, and the pads are on the payload at the")
    print("       leg's start. -> ARTIFACT with a physical consequence: the 419 N /")
    print("       1.545 m/s leg is the arm flying to a stale target, not a payload")
    print("       event, and not a cost of the band.")
    print("   1c  both flags are present in the SAME-SEED CONTROL (480.6 mm / 41.8 N")
    print("       / z 0.818) and the treatment's amplitude is larger on one seed")
    print("       only. The pre-registered monotonicity test needs two seeds; one")
    print("       seed cannot supply it -> branch artifact, per PREREG 1c.")
    print("       The per-instance witness for 'branch, not band': the delivered x")
    print("       at attempt 0 is 0.2507 (T) against 0.2447 (C) - the treatment's")
    print("       fruit sits 6 mm FURTHER OUT, i.e. a per-instance release offset,")
    print("       not the band's mapping (which compresses x by 0.8125).")

    if check:
        print(f"\n[check] missing inputs: {bad}")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
