#!/usr/bin/env python3
"""P75 report: the place legs of the two recorded cells, one row each.

    python3 logs/p75/p75_report.py logs/p75/direct/A_77.log logs/p75/direct/A_101.log

Prints, per episode: the arm/species, the place leg's own `[carry]` numbers
(`clean_slip_max`, `onset_row`, `loss_row`, `sep_end`), the leg's **first-tick**
state from the `[place-trace]` rows (`sep`, `gap`, the two tactile faces, the
contact count), the preceding lift's `clean_slip_max` and `pad_fruit_dz`, and the
class from `scripts/242_p75_classify.py`. Then the 2x2 that the phase is really
asking for: does the first-tick pinch state predict the escape?

`escape` = `place clean_slip_max > 100 mm` (the P74 "mechanism count": a payload
that left the pinch), which is independent of the trace and of the classifier.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

EP_RE = re.compile(
    r"\[rl\] episode (?P<n>\d+): (?P<species>\w+) (?:grade=(?P<grade>\w+) )?d=(?P<d>[\d.]+)cm "
    r"bin=(?P<bin>\d+) arm=(?P<arm>\w+)"
)
EP_RES_RE = re.compile(
    r"\[rl\] episode (?P<n>\d+): .* success=(?P<ok>\w+) grasped=(?P<g>\w+) "
    r"placed=(?P<p>\w+)"
)


def load_classifier():
    path = Path(__file__).resolve().parents[2] / "scripts/242_p75_classify.py"
    spec = importlib.util.spec_from_file_location("p75_classify", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def main(argv: list[str]) -> int:
    mod = load_classifier()
    for name in argv:
        path = Path(name)
        episodes: dict[int, dict] = {}
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            # The result line matches EP_RE too (it carries species/d/bin/arm),
            # so it is tested FIRST or it would overwrite the header record.
            m = EP_RES_RE.search(line)
            if m is not None:
                ep = episodes.setdefault(int(m.group("n")), {})
                ep.update(
                    ok=m.group("ok") == "True",
                    grasped=m.group("g") == "True",
                    placed=m.group("p") == "True",
                )
                continue
            m = EP_RE.search(line)
            if m is not None:
                ep = episodes.setdefault(int(m.group("n")), {})
                ep.update(
                    species=m.group("species"),
                    grade=m.group("grade") or "",
                    d=float(m.group("d")),
                    arm=m.group("arm"),
                )
        groups = mod.legs(path)
        print(f"== {path}  ({len(groups)} traced place legs, {len(episodes)} episodes)")
        print(
            f"  {'ep':>3} {'arm':5s} {'species':10s} {'d':>4} {'slipmax':>8} "
            f"{'onset':>5} {'loss':>4} {'sep_end':>7} "
            f"| {'t0 sep':>6} {'gap':>5} {'f0':>5} {'f1':>5} {'n':>1} "
            f"| {'lift slip':>9} {'lift dz':>7} | {'bd':>2} {'class':>5} {'outcome'}"
        )
        cells = {(True, True): 0, (True, False): 0, (False, True): 0, (False, False): 0}
        for i, leg in enumerate(groups):
            row = leg["row"] or {}
            t0 = leg["ticks"][0]
            res = mod.classify(leg["ticks"])
            ep = episodes.get(leg.get("ep", -1), {})
            slip_max = float(row.get("slip") or 0.0)
            escape = slip_max > 100.0
            bd = bool(res.get("boundary_open"))
            if leg["side"] == "left":
                cells[(bd, escape)] += 1
            outcome = (
                "placed"
                if ep.get("placed")
                else ("cnp" if ep.get("grasped") else "no-grasp")
            )
            print(
                f"  {leg.get('ep', -1):3d} {leg['side']:5s} {ep.get('species', '?'):10s} "
                f"{ep.get('d', 0):4.1f} {slip_max:8.1f} "
                f"{str(row.get('onset_row')):>5} {str(row.get('loss_row')):>4} "
                f"{str(row.get('sep_end')):>7} "
                f"| {res['sep0']:6.1f} {t0['gap']:5.1f} {t0['f0']:5.2f} "
                f"{t0['f1']:5.2f} {t0['n']:1d} "
                f"| {str(leg['lift'] and (leg['lift'] or {}).get('slip')):>9} "
                f"{str(leg.get('lift_dz')):>7} "
                f"| {int(bd):2d} {res['cls']:>5} {outcome}"
            )
        print(
            f"  left-arm 2x2 (boundary-pried x escape>100mm): "
            f"pried+escape={cells[(True, True)]} pried+held={cells[(True, False)]} "
            f"normal+escape={cells[(False, True)]} normal+held={cells[(False, False)]}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
