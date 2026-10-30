#!/usr/bin/env python3
"""P68 mechanism table: why the wrist hold does not keep the payload.

Reporting only, off the `[carry]` rows the p68 cell already printed (no new run,
no new instrument). Three candidate signatures, per left place leg:

* `q_step_max` - the largest per-tick command step. The leg's cap is
  `FRUIT_CARRY_STEP` = 0.03 rad/tick; a value **at** the cap on every leg means
  the IK spends its whole step budget, i.e. the pinned rotation is fighting the
  position command rather than riding along with it.
* `q_margin` / `q_cmd_margin` - the measured (resp. commanded) joint-limit
  margin and its binding joint. `-0.000` = the arm is *at* a joint limit.
* `res_end` / `dz_end` - the achieved TCP error against the leg's own target.
* `hold_drift` / `drift_on` - the commanded-vs-achieved wrist angle and the
  first tick it passes 10 deg (the hold window is 120 ticks; the climb 121).

    python3 logs/p68/mechanism.py
"""

from __future__ import annotations

import importlib.util
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P68 = ROOT / "logs/p68/p68_report.py"

ARMS = {
    "A (hold)": ("logs/p68/pop2/A_77.log", "logs/p68/pop2/A_101.log"),
    "B (none)": ("logs/p67/B2_77.log", "logs/p68/pop2/B_101.log"),
}

_RE_QS = re.compile(r"q_step_max=([\d.]+)")
_RE_QM = re.compile(r"q_margin=([+-]?[\d.]+)@(j\d+)/t(\d+)")
_RE_QCM = re.compile(r"q_cmd_margin=([+-]?[\d.]+)@(j\d+)")
_RE_RES = re.compile(r"res_end=([\d.]+|n/a)mm dz_end=([+-][\d.]+|-?n/a)mm")
_RE_VMAX = re.compile(r"in-hand_vmax=([\d.]+)")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def spread(vals, nd=2, unit="") -> str:
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return "n/a"
    if len(vals) == 1:
        return f"{vals[0]:.{nd}f}{unit}"
    return f"{statistics.median(vals):.{nd}f}{unit} [{vals[0]:.{nd}f}..{vals[-1]:.{nd}f}]"


def main() -> int:
    p68 = load_module(P68, "p68_report")
    p4 = p68.load_p4()
    print("# P68 mechanism - the wrist hold's own signature on the left place legs")
    print("# hold window 120 ticks, climb 121 ticks, FRUIT_CARRY_STEP cap 0.03 rad/tick\n")
    for arm, paths in ARMS.items():
        legs = []
        for path in paths:
            legs += p68.load(str(ROOT / path), p4)["legs"]
        qs, qm, qcm, res, dz, vm = [], [], [], [], [], []
        at_cap = 0
        at_limit = 0
        for leg in legs:
            line = leg["line"]
            m = _RE_QS.search(line)
            if m:
                qs.append(float(m.group(1)))
                at_cap += abs(float(m.group(1)) - 0.03) < 1e-9
            m = _RE_QM.search(line)
            if m:
                qm.append(float(m.group(1)))
                at_limit += float(m.group(1)) <= 1e-3
            m = _RE_QCM.search(line)
            if m:
                qcm.append((float(m.group(1)), m.group(2)))
            m = _RE_RES.search(line)
            if m:
                res.append(float(m.group(1)))
                dz.append(float(m.group(2)))
            m = _RE_VMAX.search(line)
            if m:
                vm.append(float(m.group(1)))
        held = [l for l in legs if (l.get("clean_slip") or 0) <= 50.0]
        print(f"{arm}: left place legs n={len(legs)} | held n={len(held)} "
              f"| lost n={len(legs) - len(held)}")
        print(f"  q_step_max   {spread(qs, 4)} rad/tick | at the 0.03 cap on {at_cap}/{len(qs)} legs")
        print(f"  q_margin     {spread(qm, 3)} rad | at a limit (<= 0.001) on {at_limit}/{len(qm)} legs")
        j = {}
        for _, jn in qcm:
            j[jn] = j.get(jn, 0) + 1
        print(f"  q_cmd_margin binding joint: "
              + ", ".join(f"{k}={v}" for k, v in sorted(j.items())))
        print(f"  res_end      {spread(res, 1, ' mm')} | dz_end {spread(dz, 1, ' mm')}")
        print(f"  in-hand vmax {spread(vm, 3, ' m/s')}")
        holds = [l["hold_max"] for l in legs if not l["no_hold"]]
        dons = [l["drift_on"] for l in legs if l["drift_on"] is not None]
        if holds:
            print(f"  hold         installed {len(holds)}/{len(legs)}; "
                  f"hold_drift max {spread(holds, 1, ' deg')}; "
                  f"first >10 deg at tick {spread(dons, 0)} of the 121-tick climb")
        else:
            print("  hold         not installed on any leg (the knob was unset)")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
