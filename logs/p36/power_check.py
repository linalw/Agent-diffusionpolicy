"""P36 phase 2: the power of the 2x2's main-effect tables, computed exactly.

    python3 logs/p36/power_check.py            # -> logs/p36/power_check.txt

The pre-registration's section 6 carried the wrong n. The design is 3 runs x 15
episodes per **cell**, and the inference population is the right-arm episodes
(~2/3 of them, the P35 right share 51/75 = 68 %), so a main-effect table pools
**two** cells per arm:

    n per main-effect arm ~= 2 x 30 = 60 (not 30, and not 45)

The test is the exact two-sided Fisher on `[[a, n1-a], [b, n2-b]]` at alpha
0.05, computed by full enumeration of both binomial samples (the same
`fisher_two_sided` the report uses, imported rather than copied). p1 = 0.49 is
the P35 control's right-arm carried rate (25/51).

Two readings of "carrier" are printed, because they are easy to confuse:

* **the probe cell's own carried rate** `r` - the design sees `r <= 0.18` at
  >= 80 % power;
* **the carrier fraction** `f = (p1 - r) / p1` - how much of the P35
  conversion (0.49 -> 0) the cell reproduces. At n = 60 / arm: f = 0.10 is not
  detectable (0.06), f = 0.50 reads 0.74, f = 0.70 reads 0.98, f = 0.80 reads
  1.00.

**The run clustering caveat.** The 60 episodes are 3 simulator runs of 15; the
policy loop is not reproducible across runs (AGENTS section 3b), and a run is
not a random draw from a common population - so the effective n is *below* 60
and these numbers are an **upper bound**. The run level (3/3 signs) is the
design's own consistency read and cannot reach p = 0.05 at three runs.
"""

from __future__ import annotations

import importlib.util
import math
import os

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
OUT = os.path.join(REPO, "logs", "p36", "power_check.txt")

_spec = importlib.util.spec_from_file_location(
    "p36_report", os.path.join(REPO, "scripts", "220_p36_report.py"))
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)

P1 = 0.49
ALPHA = 0.05
#: The quartet the phase-2 Gate-1 review fixed (>=).
QUARTET = (0.998, 0.977, 0.894, 0.724)
QUARTET_RATES = (0.10, 0.15, 0.20, 0.25)


def binom_pmf(n: int, p: float) -> list[float]:
    return [math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(n + 1)]


def power(n1: int, p1: float, n2: int, p2: float) -> float:
    """Exact power of the two-sided Fisher test over both binomial samples."""
    pa, pb = binom_pmf(n1, p1), binom_pmf(n2, p2)
    total = 0.0
    for a, wa in enumerate(pa):
        if wa < 1e-13:
            continue
        for b, wb in enumerate(pb):
            if wb < 1e-13:
                continue
            if R.fisher_two_sided(a, n1, b, n2) <= ALPHA:
                total += wa * wb
    return total


def main() -> int:
    lines = ["P36 phase 2 - the exact power of a main-effect table",
             "=" * 78,
             f"two-sided Fisher, alpha = {ALPHA}, p1 = {P1} (the P35 control's",
             "right-arm carried rate 25/51); n per arm = 60 = 2 cells x ~30",
             "right-arm episodes (the P35 right share 51/75 = 68 %)",
             "",
             f"  {'probe cell r':>12s} {'carrier f':>10s} {'power n=30':>11s} "
             f"{'n=45':>7s} {'n=60':>7s}"]
    rows = {}
    for r in (0.00, 0.05, 0.10, 0.15, 0.20, 0.245, 0.25, 0.30, 0.343, 0.40, 0.441):
        f = (P1 - r) / P1
        p30, p45, p60 = power(30, P1, 30, r), power(45, P1, 45, r), power(60, P1, 60, r)
        rows[r] = p60
        lines.append(f"  {r:12.3f} {f:10.2f} {p30:11.3f} {p45:7.3f} {p60:7.3f}")
    lines += [
        "",
        "  the pre-registered quartet (n = 60 / arm, the probe cell at",
        "  0.10 / 0.15 / 0.20 / 0.25 - the 80 / 69 / 59 / 49 % carriers):",
    ]
    ok = True
    for r, want in zip(QUARTET_RATES, QUARTET):
        got = rows[r]
        flag = "ok" if abs(round(got, 3) - want) < 1e-9 else "MISMATCH"
        if flag != "ok":
            ok = False
        lines.append(f"    r={r:.2f}: exact {got:.4f} -> {round(got, 3):.3f}  "
                     f"(the quartet's {want:.3f})  {flag}")
    lines += [
        "",
        "  at 80 % power the design sees a probe cell at r <= ~0.18 (carrier",
        "  f >= ~0.63); a 50 % carrier (r = 0.245) reads 0.74, a 30 % carrier",
        "  (r = 0.343) 0.31, a 10 % carrier (r = 0.441) 0.06 - which is why the",
        "  primary readout is the effect fraction with its band, not the p-value",
        "  alone.",
        "",
        "  CAVEAT (binding): the 60 episodes are 3 runs x 15; the policy loop is",
        "  not reproducible across runs, so the effective n is below 60 and these",
        "  powers are an upper bound. The run level cannot reach p = 0.05 at 3 runs.",
    ]
    text = "\n".join(lines) + "\n"
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text, end="")
    print(f"wrote {os.path.relpath(OUT, REPO)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
