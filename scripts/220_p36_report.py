"""P36 phase 2: the 2x2 report - the park's image x the proprio spoof.

    python3 scripts/220_p36_report.py logs/p36/A_ab
    python3 scripts/220_p36_report.py --self-test

Reads the `C{cell}_{run}.log` files `scripts/219_p36_cells.sh` writes (one
`[rl] episode ...` line per episode, `scripts/110_rl_rollout.py`'s format - the
parser is `113_rl_report.py`'s, imported rather than copied - plus the per-
episode `[spoof]` and `[park]` certificates) and prints the pre-registered
analysis of `logs/p36/PREREG.md` section 5.

**Two gates run before any outcome number.** (1) *Completeness* (H2): a run is
complete only with all four cells present and exactly 15 episodes in each; fewer
than **3** complete runs is a refusal, not a reading. (2) *The manipulation
check* (S1-S4, PREREG section 3), read from the batch's own rows: the proprio
substitution (the file's vector bitwise, the counterpart cell's live pose within
0.02 rad per join, the substitution really bites), `rest_same` everywhere, the
arm holding the cell's pose, and the image following the arm - with S4 restricted
to **right-active** episodes (the inference population; a left-active episode has
the right arm as its inactive side, where no park vector exists). The
manipulation gate also asserts its own **population** (M2): one `[park]` row per
episode, so `len(records) == 4 x 15 x n_runs` and at least one row per
cell-run - a dropped row refuses the read instead of shrinking the gate.

Then: the per-cell table (right / left / pooled, `ok` / `carried` / `no-grasp`)
with a Wilson interval on the right-arm carried rate; the two **main-effect 2x2
tables** on the right-arm carried class (image: cells {2,3} vs {1,4}; proprio:
{2,4} vs {1,3}) with exact two-sided Fisher p-values; the **interaction**
`(r2-r3)-(r4-r1)` with a within-stratum permutation p-value read as redundancy
vs synergy; the **effect fraction** `(r1-r_c)/(r1-r2)` crude **and
class-standardised**, with the full / partial / none bands; the class-
standardised right-arm `ok` rate beside the crude one; the failure reasons and
the cycle **restricted to the right arm**; model calls per attempt; the run-level
signs; the left-arm no-op population as the **noise floor**; and the
pre-registered reading (section 7) with the per-channel OOD asymmetry.

The design-valid leg is the **between-cell** contrast: the cells are independent
samples (the policy's actions diverge after the first call), so a per-episode
pairing is post-treatment-conditioned and is not used here at all.
"""

from __future__ import annotations

import argparse
import contextlib
import glob
import importlib.util
import io
import math
import os
import re
import statistics
import tempfile
from collections import Counter

import numpy as np

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CELLS = ("1", "2", "3", "4")
#: Cell 1 is the *scenario* of record plus the batch's four diags, not the
#: shipped default (`FRUIT_POLICY_TRIGGER_ACQ` is a default-off measurement
#: interface, AGENTS section 3b: instrumentation is part of the measurement).
CELL_ROLE = {
    "1": "ready / ready (control: P35 scenario + diags)",
    "2": "park / park (the lever)",
    "3": "park / ready-proprio (image probe)",
    "4": "ready / park-proprio (proprio probe)",
}
#: The arm's **physical** pose per cell (the image channel).
POSE_OF_CELL = {"1": "ready", "2": "back", "3": "back", "4": "ready"}
#: The pose the **observation** is written with per cell (None = live).
SPOOF_OF_CELL: dict[str, str | None] = {"1": None, "2": None, "3": "ready", "4": "back"}
#: The pre-registered bands on a channel cell's right-arm carried rate.
BAND_FULL = 0.10
BAND_NONE = 0.35
#: The pre-registered design: 3 runs x 15 episodes per cell.
EPISODES_PER_RUN = 15
MIN_RUNS = 3
#: The permutation's fixed seed (pre-registered).
PERM_SEED = 20261024
PERM_DRAWS = 5000
#: The dof index sets (`logs/33_dof.log`: the interleaved layout).
LEFT_IDX = "0,2,4,6,8,10,12"
RIGHT_IDX = "1,3,5,7,9,11,13"
#: S1's bar on the counterpart reproduction, and the substitution's floor.
S1_BAR = 0.02
S1_BITES = 0.30
#: S4's per-episode bar on the *ready* side (the parked side is exact).
S4_READY_SHARE = 0.90

SPOOF_FILE = os.path.join(REPO, "configs", "proprio_spoof.json")


def _load_113():
    path = os.path.join(REPO, "scripts", "113_rl_report.py")
    spec = importlib.util.spec_from_file_location("rl_report_113", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RL = _load_113()


# --------------------------------------------------------------------- math -- #
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """The Wilson score interval for k/n (the pre-registered interval)."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def fisher_two_sided(a: int, n1: int, b: int, n2: int) -> float:
    """Exact two-sided Fisher for [[a, n1-a], [b, n2-b]] (hypergeometric).

    The two-sided p is the total probability of the tables **no more likely**
    than the observed one. The tolerance is *relative*: an absolute `+1e-12`
    (the first version's) counts every table whose probability is below
    1e-12 as "at least as extreme", which turns a 1e-15 tail into ~1e-12.
    """
    n = n1 + n2
    row1 = n1
    col1 = a + b
    lo = max(0, col1 - (n - row1))
    hi = min(col1, row1)
    denom = math.comb(n, col1)

    def hyp(x: int) -> float:
        return math.comb(row1, x) * math.comb(n - row1, col1 - x) / denom

    observed = hyp(a)
    cut = observed * (1.0 + 1e-9)
    return min(1.0, sum(hyp(x) for x in range(lo, hi + 1) if hyp(x) <= cut))


def band(rate: float) -> str:
    if rate != rate:
        return "n/a"
    if rate <= BAND_FULL:
        return "full"
    if rate < BAND_NONE:
        return "partial"
    return "none"


def _ticks(value: float) -> str:
    return "n/a" if value != value else f"{value:.0f}"


def _num(value: float) -> str:
    return "n/a" if value != value else f"{value:.1f}"


def _rate(k: int, n: int) -> float:
    return k / n if n else float("nan")


def did_value(rk: dict, rn: dict) -> float:
    """The interaction contrast `(r2-r3) - (r4-r1)`."""
    return ((_rate(rk["2"], rn["2"]) - _rate(rk["3"], rn["3"]))
            - (_rate(rk["4"], rn["4"]) - _rate(rk["1"], rn["1"])))


def _stratum(k_a: int, n_a: int, k_b: int, n_b: int) -> dict[int, float]:
    """The hypergeometric law of cell a's count given the stratum's total."""
    total, n = k_a + k_b, n_a + n_b
    lo, hi = max(0, total - (n - n_a)), min(total, n_a)
    denom = math.comb(n, total)
    return {x: math.comb(n_a, x) * math.comb(n - n_a, total - x) / denom
            for x in range(lo, hi + 1)}


def interaction_p(rk: dict, rn: dict, draws: int = PERM_DRAWS,
                  seed: int = PERM_SEED, criterion: str = "correct") -> float:
    """The within-stratum permutation p for the interaction.

    The cells of an image stratum are exchangeable under no interaction, so
    cells {2,3} and {1,4} are re-drawn from their pooled counts. The two-sided
    criterion is `|T*| >= |did|` - **not** `|T* - did| >= |did|`, which is
    centred on the observed value and therefore reads >= 0.5 on every table.
    `criterion="centred"` is the old (wrong) form, kept only so the self-test
    can pin the difference.
    """
    rng = np.random.RandomState(seed)
    did = did_value(rk, rn)
    hits = 0
    for _ in range(draws):
        tot23, n23 = rk["2"] + rk["3"], rn["2"] + rn["3"]
        k2 = rng.hypergeometric(tot23, n23 - tot23, rn["2"])
        d23 = _rate(k2, rn["2"]) - _rate(tot23 - k2, rn["3"])
        tot14, n14 = rk["1"] + rk["4"], rn["1"] + rn["4"]
        k4 = rng.hypergeometric(tot14, n14 - tot14, rn["4"])
        d41 = _rate(k4, rn["4"]) - _rate(tot14 - k4, rn["1"])
        t = d23 - d41
        if criterion == "correct":
            if abs(t) >= abs(did) - 1e-12:
                hits += 1
        elif abs(t - did) >= abs(did) - 1e-12:   # the pre-fix form (never use)
            hits += 1
    return (1 + hits) / (1 + draws)


def interaction_p_exact(rk: dict, rn: dict) -> float:
    """The same permutation p by exact enumeration (a self-test cross-check)."""
    did = did_value(rk, rn)
    total = 0.0
    for k2, w2 in _stratum(rk["2"], rn["2"], rk["3"], rn["3"]).items():
        d23 = _rate(k2, rn["2"]) - _rate(rk["2"] + rk["3"] - k2, rn["3"])
        for k4, w4 in _stratum(rk["4"], rn["4"], rk["1"], rn["1"]).items():
            d41 = _rate(k4, rn["4"]) - _rate(rk["1"] + rk["4"] - k4, rn["1"])
            if abs((d23 - d41)) >= abs(did) - 1e-12:
                total += w2 * w4
    return total


# ------------------------------------------------------------------- load ---- #
def classify(row: dict) -> str:
    if row["success"] or row["placed"]:
        return "ok"
    return "carried" if row["grasped"] else "no_grasp"


def _kv(line: str) -> dict[str, str]:
    """The `key=value` tokens of a `[spoof]`/`[park]` row (values are scalar)."""
    out: dict[str, str] = {}
    for token in line.split():
        if "=" in token:
            key, value = token.split("=", 1)
            if key.isidentifier():
                out[key] = value
    return out


def _floats(text: str) -> list[float]:
    if not text or text == "-":
        return []
    return [float(v) for v in text.split(",")]


SPOOF_ROW = re.compile(r"\[spoof\] episode (\d+) ")
PARK_ROW = re.compile(r"\[park\] episode (\d+) ")
PARK_CALL = re.compile(r"\[park\] call ep=(\d+) ")


def load(directory: str) -> dict[str, dict[int, dict]]:
    """cell -> run -> {episodes, spoof{ep}, park{ep}, calls{ep: [rows]}}."""
    cells: dict[str, dict[int, dict]] = {c: {} for c in CELLS}
    for path in sorted(glob.glob(os.path.join(directory, "C*_*.log"))):
        stem = os.path.basename(path)[:-4]
        found = re.fullmatch(r"C([1-4])_(\d+)", stem)
        if not found:
            continue
        spoof: dict[int, dict] = {}
        park: dict[int, dict] = {}
        calls: dict[int, list[dict]] = {}
        for line in open(path, encoding="utf-8", errors="ignore"):
            m = SPOOF_ROW.search(line)
            if m:
                spoof[int(m.group(1))] = _kv(line)
                continue
            m = PARK_ROW.search(line)
            if m:
                park[int(m.group(1))] = _kv(line)
                continue
            m = PARK_CALL.search(line)
            if m:
                calls.setdefault(int(m.group(1)), []).append(_kv(line))
        cells[found.group(1)][int(found.group(2))] = {
            "episodes": RL.parse(path),
            "spoof": spoof,
            "park": park,
            "calls": calls,
            "log": os.path.basename(path),
        }
    return cells


def counts(rows: list[dict]) -> dict[str, int]:
    c = Counter(classify(r) for r in rows)
    return {"n": len(rows), "ok": c["ok"], "carried": c["carried"],
            "no_grasp": c["no_grasp"]}


# -------------------------------------------------------------- completeness -- #
def completeness(cells: dict[str, dict[int, dict]]) -> dict:
    """H2: 3 complete runs, all four cells, 15 episodes in every cell-run."""
    per_cell = {c: sorted(cells[c]) for c in CELLS}
    runs = sorted(per_cell["1"])
    problems: list[str] = []
    for c in CELLS:
        if per_cell[c] != runs:
            problems.append(f"cell {c} has runs {per_cell[c]}, cell 1 has {runs}"
                            " (the cells must be the same run set)")
    if len(runs) < MIN_RUNS:
        problems.append(f"{len(runs)} run(s) present, {MIN_RUNS} required")
    short = []
    for c in CELLS:
        for run in per_cell[c]:
            n = len(cells[c][run]["episodes"])
            if n != EPISODES_PER_RUN:
                short.append(f"C{c}_{run}={n}")
    if short:
        problems.append("episodes per cell-run != "
                        f"{EPISODES_PER_RUN}: " + ", ".join(short))
    return {"ok": not problems, "runs": runs, "problems": problems,
            "episodes": {c: {r: len(cells[c][r]["episodes"]) for r in per_cell[c]}
                         for c in CELLS}}


def order_note(directory: str) -> list[str]:
    """The cell order the driver recorded (the randomised rotation)."""
    path = os.path.join(directory, "A_header.txt")
    if not os.path.isfile(path):
        return ["  cell order: NOT RECORDED (no A_header.txt) - the per-run order",
                "  is a time-of-batch confounder and cannot be read off the logs"]
    lines = [line.rstrip("\n") for line in open(path, encoding="utf-8")
             if "cell order" in line or "order:" in line]
    return ["  " + line.strip() for line in lines] or ["  cell order: not in the header"]


# ------------------------------------------------------------ manipulation -- #
def _poses() -> dict:
    import json
    with open(SPOOF_FILE, encoding="utf-8") as fh:
        return json.load(fh)["poses"]


def _fmt(values) -> str:
    return ",".join(f"{float(v):+.3f}" for v in values)


def manipulation(cells: dict[str, dict[int, dict]], runs: list[int]) -> dict:
    """S1-S4 of PREREG section 3, from the batch's own `[spoof]`/`[park]` rows."""
    poses = _poses()
    recs: list[dict] = []
    missing: list[str] = []
    for c in CELLS:
        for run in runs:
            entry = cells[c][run]
            for ep, park in entry["park"].items():
                spoof = entry["spoof"].get(ep)
                if spoof is None:
                    missing.append(f"C{c}_{run} ep{ep} has no [spoof] row")
                    continue
                recs.append({
                    "cell": c, "run": run, "ep": ep,
                    "arm": park.get("arm", "?"),
                    "inactive": park.get("inactive", "?"),
                    "park": park.get("park", "?"),
                    "m1_ok": int(park.get("m1_hold_ok", "-1")),
                    "m1_hold": float(park["m1_hold"]) if park.get("m1_hold", "-") != "-" else float("nan"),
                    "arm_px": int(park.get("arm_px", "-1")),
                    "band_calls": int(park.get("band_calls", "0")),
                    "q": _floats(park.get("q", "-")),
                    "s": spoof,
                    "call_rows": entry["calls"].get(ep, []),
                    "calls": int(park.get("calls", "0")),
                })

    def right(rec: dict) -> bool:
        return rec["arm"] == "right"

    fails: dict[str, list[str]] = {k: [] for k in ("S1", "S1c", "S2", "S3", "S4", "M2")}
    stat: list[dict] = []

    def note(name: str, good: int, total: int, detail: str, gated: bool = True) -> None:
        stat.append({"name": name, "good": good, "total": total,
                     "detail": detail, "gated": gated})

    # --- M2 (Gate 2): the record count is invariant ------------------------ #
    # Every episode writes exactly one `[park]` row (the manipulation
    # certificate), so the gate's population is fixed by the design: 4 cells x
    # 15 episodes x n_runs. A silently dropped row would otherwise shrink the
    # population and let the check pass on a subset of the batch - the gate
    # would be reading less than it claims to. Assert the count; also require
    # at least one row per cell-run so a whole cell-run cannot vanish unseen.
    expected = len(CELLS) * EPISODES_PER_RUN * len(runs)
    if len(recs) + len(missing) != expected:
        fails["M2"].append(
            f"{len(recs)} records (+{len(missing)} without a [spoof] row) != "
            f"{expected} = {len(CELLS)} cells x {EPISODES_PER_RUN} episodes x "
            f"{len(runs)} runs")
    per_cell_run = Counter((r["cell"], r["run"]) for r in recs)
    for c in CELLS:
        for run in runs:
            if per_cell_run[(c, run)] < 1:
                fails["M2"].append(f"C{c}_{run} has no `[park]` row")
    note("M2 records (one [park] row per episode)", len(recs), expected,
         f"{len(recs)} of {expected}"
         + (f"; {len(missing)} row(s) without a [spoof]" if missing else ""))

    # --- S1: the proprio substitution ------------------------------------- #
    # (a) the probe cells' right-active episodes must write the file's vector.
    for c in ("3", "4"):
        pose = SPOOF_OF_CELL[c]
        want = _fmt(poses[pose]["left"])
        rows = [r for r in recs if r["cell"] == c and right(r)]
        good = [r for r in rows
                if int(r["s"].get("applied", "0")) == 1
                and r["s"].get("side") == "left"
                and r["s"].get("idx") == LEFT_IDX
                and r["s"].get("obs") == want
                and float(r["s"].get("drift", "0")) > S1_BITES]
        note(f"S1 cell {c}", len(good), len(rows), f"the '{pose}' vector")
        for r in rows:
            if r not in good:
                fails["S1"].append(
                    f"C{c}_{r['run']} ep{r['ep']} (right): pose={r['s'].get('pose')} "
                    f"applied={r['s'].get('applied')} side={r['s'].get('side')} "
                    f"idx={r['s'].get('idx')} drift={r['s'].get('drift')} "
                    f"obs={r['s'].get('obs')} want {want}")
    # (b) the cells that must NOT substitute (and the `back` side with no vector).
    for c in ("1", "2", "4"):
        rows = [r for r in recs if r["cell"] == c and not right(r)]
        good = [r for r in rows
                if int(r["s"].get("applied", "0")) == 0
                and (r["s"].get("pre_md5") == r["s"].get("obs_md5"))]
        note(f"S1 no-op cell {c} (left-active)", len(good), len(rows),
             "applied=0, hashes equal")
        for r in rows:
            if r not in good:
                fails["S1"].append(
                    f"C{c}_{r['run']} ep{r['ep']} (left, inactive=right): expected "
                    f"applied=0 (no right-arm '{SPOOF_OF_CELL[c]}' vector)")
    rows = [r for r in recs if r["cell"] in ("1", "2") and right(r)]
    good = [r for r in rows if int(r["s"].get("applied", "0")) == 0
            and r["s"].get("pre_md5") == r["s"].get("obs_md5")]
    note("S1 no-op cells 1/2 (right-active)", len(good), len(rows),
         "no spoof requested")
    for r in rows:
        if r not in good:
            fails["S1"].append(f"C{r['cell']}_{r['run']} ep{r['ep']} (right): "
                               "a spoof ran in a no-spoof cell")
    # (c) cell 3's left-active rows write the right's *ready* vector: a no-op.
    rows = [r for r in recs if r["cell"] == "3" and not right(r)]
    good = [r for r in rows
            if int(r["s"].get("applied", "0")) == 1
            and r["s"].get("side") == "right"
            and r["s"].get("idx") == RIGHT_IDX
            and r["s"].get("obs") == _fmt(poses["ready"]["right"])
            and float(r["s"].get("drift", "1")) <= S1_BAR]
    note("S1 cell 3 no-op (left-active)", len(good), len(rows),
         "the right 'ready' vector, drift <= 0.02")
    for r in rows:
        if r not in good:
            fails["S1"].append(f"C3_{r['run']} ep{r['ep']} (left): the ready/right "
                               f"no-op write is off ({r['s'].get('obs')}, "
                               f"drift {r['s'].get('drift')})")

    # --- S1c: the probe's vector vs the *physical* counterpart's live pose -- #
    med = {}
    for c in ("1", "2"):
        qs = [r["q"] for r in recs if r["cell"] == c and right(r) and len(r["q"]) == 7]
        med[c] = [float(np.median([q[j] for q in qs])) for j in range(7)] if qs else []
        if qs:
            note(f"S1c counterpart {c} reset spread", len(qs), len(qs),
                 f"max |q - median| = "
                 f"{max(abs(q[j]-med[c][j]) for q in qs for j in range(7)):.4f} rad",
                 gated=False)
    for c, other in (("3", "1"), ("4", "2")):
        rows = [r for r in recs if r["cell"] == c and right(r)]
        if not med[other]:
            fails["S1c"].append(f"no counterpart live pose in cell {other}")
            continue
        devs = []
        for r in rows:
            obs = _floats(r["s"].get("obs", "-"))
            if len(obs) != 7:
                fails["S1c"].append(f"C{c}_{r['run']} ep{r['ep']}: no 7-value obs")
                continue
            dev = max(abs(obs[j] - med[other][j]) for j in range(7))
            devs.append(dev)
            if dev > S1_BAR:
                fails["S1c"].append(
                    f"C{c}_{r['run']} ep{r['ep']}: max |written - live(cell {other})| "
                    f"= {dev:.4f} rad > {S1_BAR}")
        note(f"S1c cell {c} vs {other}", sum(1 for d in devs if d <= S1_BAR),
             len(devs),
             f"median {statistics.median(devs):.4f} / max {max(devs):.4f} rad"
             if devs else "-")

    # --- S2: the rest of the observation ---------------------------------- #
    rows = [r for r in recs if int(r["s"].get("rest_same", "0")) == 1]
    note("S2 rest_same", len(rows), len(recs),
         "the 25-D with the 7 zeroed, before/after")
    for r in recs:
        if int(r["s"].get("rest_same", "0")) != 1:
            fails["S2"].append(f"C{r['cell']}_{r['run']} ep{r['ep']}: rest_same=0")

    # --- S3: the arm holds the cell's pose (the park) --------------------- #
    rows = [r for r in recs if right(r)]
    good = [r for r in rows if r["park"] == POSE_OF_CELL[r["cell"]] and r["m1_ok"] == 1]
    note("S3 right-active (the parked arm)", len(good), len(rows),
         "park == the cell's pose, M1 held")
    for r in rows:
        if r not in good:
            fails["S3"].append(f"C{r['cell']}_{r['run']} ep{r['ep']}: park={r['park']} "
                               f"(want {POSE_OF_CELL[r['cell']]}), m1_hold_ok={r['m1_ok']} "
                               f"({r['m1_hold']:+.3f} rad)")
    rows = [r for r in recs if not right(r)]
    good = [r for r in rows if r["m1_ok"] == 1]
    note("S3 left-active (the right arm, always ready)", len(good), len(rows),
         "no right-arm park vector: the no-op side", gated=False)

    # --- S4: the image is the arm's physical pose (band census) ----------- #
    for c in CELLS:
        rows = [r for r in recs if r["cell"] == c and right(r) and r["band_calls"] >= 1]
        excluded = [r for r in recs if r["cell"] == c and right(r) and r["band_calls"] < 1]
        if c in ("2", "3"):
            good = [r for r in rows if r["arm_px"] == 0]
        else:
            good = [r for r in rows if r["arm_px"] > 0]
        share = len(good) / len(rows) if rows else float("nan")
        note(f"S4 cell {c} (right-active)", len(good), len(rows),
             f"{share:.0%} of episodes, first band call arm_px "
             + ("= 0" if c in ("2", "3") else "> 0")
             + (f"; {len(excluded)} episode(s) with no band call excluded"
                if excluded else ""))
        need = len(rows) if c in ("2", "3") else int(math.ceil(S4_READY_SHARE * len(rows)))
        if len(good) < need or not rows:
            fails["S4"].append(
                f"C{c}: {len(good)}/{len(rows)} right-active episodes on the expected "
                f"side (need {need}); arm_px "
                + ",".join(str(r["arm_px"]) for r in rows[:12]))
    # The call-level census (reported, not gated: PREREG's S4 is the class).
    census = {}
    for c in CELLS:
        calls = [row for r in recs if r["cell"] == c and right(r) for row in r["call_rows"]]
        hit = sum(1 for row in calls if int(row.get("arm_px", "-1")) > 0)
        census[c] = (hit, len(calls))
    note("S4 call-level census (right-active)", 0, 0,
         "  ".join(f"cell {c}: {census[c][0]}/{census[c][1]} calls arm_px>0"
                   for c in CELLS), gated=False)
    # The no-op side: the right arm at ready contributes no bbox pixels either way.
    ncalls = [row for r in recs if not right(r) for row in r["call_rows"]]
    note("S4 no-op side (left-active)",
         sum(1 for row in ncalls if int(row.get("arm_px", "-1")) > 0), len(ncalls),
         "the right arm at ready: not in the target's disc bbox, all cells",
         gated=False)

    return {"fails": fails, "stat": stat, "records": len(recs),
            "missing": missing,
            "ok": not any(fails.values()) and not missing}


# ------------------------------------------------------------------ analyse -- #
def analyse(cells: dict[str, dict[int, dict]], runs: list[int]) -> dict:
    out: dict = {"runs": runs, "cells": {}, "per_run": {}, "warnings": []}
    pooled = {c: [r for run in runs for r in cells[c][run]["episodes"]] for c in CELLS}
    for c in CELLS:
        right = [r for r in pooled[c] if r["arm"] == "right"]
        left = [r for r in pooled[c] if r["arm"] == "left"]
        out["cells"][c] = {
            "all": counts(pooled[c]),
            "right": counts(right),
            "left": counts(left),
            "rows": pooled[c],
        }
    for run in runs:
        out["per_run"][run] = {
            c: counts([r for r in cells[c][run]["episodes"] if r["arm"] == "right"])
            for c in CELLS
        }

    r = {c: out["cells"][c]["right"] for c in CELLS}
    rk = {c: r[c]["carried"] for c in CELLS}
    rn = {c: r[c]["n"] for c in CELLS}
    rate = {c: _rate(rk[c], rn[c]) for c in CELLS}
    out["rate"] = rate
    out["ci"] = {c: wilson(rk[c], rn[c]) for c in CELLS}

    # The two pre-registered main-effect 2x2 tables on the carried class.
    image_a, image_n = rk["2"] + rk["3"], rn["2"] + rn["3"]
    image_b, image_n2 = rk["1"] + rk["4"], rn["1"] + rn["4"]
    prop_a, prop_n = rk["2"] + rk["4"], rn["2"] + rn["4"]
    prop_b, prop_n2 = rk["1"] + rk["3"], rn["1"] + rn["3"]
    out["image"] = {
        "a": (image_a, image_n), "b": (image_b, image_n2),
        "p": fisher_two_sided(image_a, image_n, image_b, image_n2),
        "effect": (rate["2"] + rate["3"]) / 2 - (rate["1"] + rate["4"]) / 2,
    }
    out["proprio"] = {
        "a": (prop_a, prop_n), "b": (prop_b, prop_n2),
        "p": fisher_two_sided(prop_a, prop_n, prop_b, prop_n2),
        "effect": (rate["2"] + rate["4"]) / 2 - (rate["1"] + rate["3"]) / 2,
    }

    # The interaction: point estimate + within-stratum permutation (M1).
    out["interaction"] = {
        "did": did_value(rk, rn),
        "p": interaction_p(rk, rn),
        "p_exact": interaction_p_exact(rk, rn),
    }

    # The effect fraction per cell (undefined when the lever does not replicate).
    base = rate["1"] - rate["2"]
    out["replicates"] = bool(base > 0.05)
    out["fraction"] = {
        c: ((rate["1"] - rate[c]) / base) if out["replicates"] else float("nan")
        for c in CELLS
    }
    out["band"] = {c: band(rate[c]) for c in CELLS}

    # The class-standardised right-arm rates (to cell 1's species mix): `ok`
    # (pre-registered) and `carried` (what the effect fraction is made of).
    mix1 = Counter(r["category"] for r in out["cells"]["1"]["rows"] if r["arm"] == "right")
    n1 = sum(mix1.values())
    std_ok, std_carried, cover = {}, {}, {}
    for c in CELLS:
        rows = [r for r in out["cells"][c]["rows"] if r["arm"] == "right"]
        per: dict[str, list[dict]] = {}
        for row in rows:
            per.setdefault(row["category"], []).append(row)
        num_ok = num_car = 0.0
        covered = 0
        for species, weight in mix1.items():
            if species in per:
                n = len(per[species])
                num_ok += (weight / n1) * (sum(1 for r in per[species]
                                               if classify(r) == "ok") / n)
                num_car += (weight / n1) * (sum(1 for r in per[species]
                                                  if classify(r) == "carried") / n)
                covered += weight
        scale = (n1 / covered) if covered else float("nan")
        std_ok[c] = num_ok * scale
        std_carried[c] = num_car * scale
        cover[c] = covered / n1 if n1 else float("nan")
    out["standardised"] = std_ok
    out["standardised_carried"] = std_carried
    out["coverage"] = cover
    base_std = std_carried["1"] - std_carried["2"]
    out["fraction_std"] = {
        c: ((std_carried["1"] - std_carried[c]) / base_std) if base_std > 0.05
        else float("nan")
        for c in CELLS
    }
    out["replicates_std"] = bool(base_std > 0.05)

    # Failure reasons and the cycle, **right arm only** (the inference population).
    out["reasons"] = {}
    right_rows = {c: [r for r in out["cells"][c]["rows"] if r["arm"] == "right"]
                  for c in CELLS}
    for c in CELLS:
        seen = set()
        for row in right_rows[c]:
            if classify(row) == "ok":
                continue
            text = row["notes"].strip("[]").strip()
            seen.add("empty note" if not text else re.sub(r"[-+0-9.]+", "#", text))
        out["reasons"][c] = seen
    out["new_reasons"] = {c: sorted(out["reasons"][c] - out["reasons"]["1"])
                          for c in CELLS if c != "1"}
    out["cycle"] = {}
    for c in CELLS:
        oks = [row for row in right_rows[c] if classify(row) == "ok"]
        out["cycle"][c] = {
            "all": statistics.median([row["ticks"] for row in right_rows[c]])
            if right_rows[c] else float("nan"),
            "ok": statistics.median([row["ticks"] for row in oks]) if oks else float("nan"),
        }

    # The run-level signs of each contrast.
    signs = {"image": [], "proprio": []}
    for run in runs:
        pr = out["per_run"][run]
        rr = {c: _rate(pr[c]["carried"], pr[c]["n"]) for c in CELLS}
        signs["image"].append((rr["2"] + rr["3"]) / 2 - (rr["1"] + rr["4"]) / 2)
        signs["proprio"].append((rr["2"] + rr["4"]) / 2 - (rr["1"] + rr["3"]) / 2)
    out["run_signs"] = signs

    # The noise floor: the same contrasts on the left (a no-op in all four cells).
    lk = {c: out["cells"][c]["left"]["carried"] for c in CELLS}
    ln = {c: out["cells"][c]["left"]["n"] for c in CELLS}
    out["left"] = {
        "rate": {c: _rate(lk[c], ln[c]) for c in CELLS},
        "image": ((_rate(lk["2"], ln["2"]) + _rate(lk["3"], ln["3"])) / 2
                  - (_rate(lk["1"], ln["1"]) + _rate(lk["4"], ln["4"])) / 2),
        "proprio": ((_rate(lk["2"], ln["2"]) + _rate(lk["4"], ln["4"])) / 2
                    - (_rate(lk["1"], ln["1"]) + _rate(lk["3"], ln["3"])) / 2),
        "did": did_value(lk, ln),
        "spread": (max(_rate(lk[c], ln[c]) for c in CELLS)
                   - min(_rate(lk[c], ln[c]) for c in CELLS)),
    }

    # Model calls per attempt (the `[park]` row's `calls=`), right arm.
    out["calls"] = {}
    for c in CELLS:
        vals = []
        for run in runs:
            for ep, park in cells[c][run]["park"].items():
                if park.get("arm") == "right" and park.get("calls", "-") != "-":
                    vals.append(int(park["calls"]))
        out["calls"][c] = {
            "n": len(vals),
            "median": statistics.median(vals) if vals else float("nan"),
            "min": min(vals) if vals else float("nan"),
            "max": max(vals) if vals else float("nan"),
        }

    out["reading"] = reading(out)
    return out


def reading(out: dict) -> str:
    """The pre-registered decision matrix (PREREG section 7)."""
    if not out["replicates"]:
        return "non-replication"
    img, prop = out["band"]["3"], out["band"]["4"]
    img_moves = img in ("full", "partial")
    prop_moves = prop in ("full", "partial")
    if img_moves and prop_moves:
        return "both"
    if img_moves:
        return "image-borne"
    if prop_moves:
        return "proprio-borne"
    return "not identified"


READING_TEXT = {
    "non-replication": (
        "the lever did not replicate (cell 1 -> cell 2's carried rate moved <= 0.05): "
        "no channel claim; the batch is a non-replication, diagnose the scenario first"),
    "image-borne": (
        "the image cell (3) converts and the proprio cell (4) does not: the park's win "
        "travels the image channel; which image statistic (the fruit's sightline is the "
        "leading, unseparated candidate) is not identified here; a recollection's own "
        "A/B is the shipping path"),
    "proprio-borne": (
        "the proprio cell (4) converts and the image cell (3) does not: the win is the "
        "7-joint input shift; a recollection that fixes only the image would not "
        "recover it"),
    "both": (
        "both single-channel cells convert: each channel suffices alone (redundant); "
        "the interaction and the fractions say which is larger; a recollection must "
        "fix both"),
    "not identified": (
        "neither single channel converts: a null probe is ambiguous (the channel is "
        "not the mediator, or the inconsistent pair destroys the response); the "
        "within-cell dose is the named discriminator, a new phase"),
}


# ------------------------------------------------------------------- report -- #
def render(out: dict, comp: dict, manip: dict, order: list[str]) -> None:
    runs = out["runs"]
    print(f"P36 2x2 - the park's image x the proprio spoof "
          f"({len(runs)} runs x 4 cells)")
    print("=" * 92)
    print(f"  runs: {runs}   right-arm inference population "
          f"(cell 1 = the P35 C-batch scenario + the four diags)")
    for line in order:
        print(line)
    for warning in out["warnings"]:
        print(f"  WARNING: {warning}")
    print()

    print("[1] COMPLETENESS (H2: 3 complete runs, 15 episodes per cell-run)")
    print()
    print("  PASS  every cell has runs " + ", ".join(str(r) for r in runs)
          + f" with {EPISODES_PER_RUN} episodes each")
    for c in CELLS:
        print(f"    cell {c}: "
              + ", ".join(f"run {r}={n}" for r, n in sorted(comp["episodes"][c].items())))
    print()

    print("[2] THE MANIPULATION CHECK (S1-S4; a failure blocks the outcome read)")
    print()
    for item in manip["stat"]:
        if item["total"] == 0:
            print(f"  info  {item['name']:44s} {item['detail']}")
            continue
        if not item["gated"]:
            flag = "info"
        else:
            flag = "PASS" if item["good"] == item["total"] else "FAIL"
        print(f"  {flag}  {item['name']:44s} {item['good']:3d}/{item['total']:<3d}  "
              f"{item['detail']}")
    for key, items in manip["fails"].items():
        for text in items[:6]:
            print(f"    FAIL {key}: {text}")
        if len(items) > 6:
            print(f"    FAIL {key}: ... {len(items) - 6} more")
    for text in manip["missing"][:6]:
        print(f"    FAIL rows: {text}")
    print(f"  => manipulation {'PASS' if manip['ok'] else 'FAIL'} "
          f"({manip['records']} episodes, 0 separate instrumented runs)")
    print()
    if not manip["ok"]:
        print("REFUSED: S1-S4 is an implementation failure - no outcome claim. The")
        print("cell table below is descriptive only; diagnose the reason above first")
        print("(PREREG section 3: 'no outcome claim, and the reason ... is diagnosed")
        print("before a re-run').")
        print()

    print("[3] THE CELLS (right = the lever's population; left = the no-op control)")
    print()
    print("  cell  role                                        right: ok carried n-grasp  n"
          " | left: ok/n carried/n | pooled ok/n")
    for c in CELLS:
        r, lf, al = out["cells"][c]["right"], out["cells"][c]["left"], out["cells"][c]["all"]
        print(f"  {c}     {CELL_ROLE[c]:47s} {r['ok']:4d} {r['carried']:6d} "
              f"{r['no_grasp']:6d} {r['n']:3d} | {lf['ok']:4d}/{lf['n']:<4d} "
              f"{lf['carried']:4d}/{lf['n']:<4d}  | {al['ok']:4d}/{al['n']:<4d}")
    print()
    print("  right-arm carried rate with the Wilson 95 % interval, the effect")
    print("  fraction (r1-r_c)/(r1-r2) and the pre-registered band:")
    print()
    for c in CELLS:
        lo, hi = out["ci"][c]
        frac = out["fraction"][c]
        ftext = "n/a" if frac != frac else f"{frac:+.2f}"
        tag = out["band"][c] if c in ("3", "4") else "reference"
        print(f"    cell {c}: {out['rate'][c]:.3f}  [{lo:.3f}, {hi:.3f}]   "
              f"fraction {ftext:5s}   band {tag}")
    print()

    print("[4] THE PRE-REGISTERED MAIN EFFECTS (right-arm carried class)")
    print()
    for key, label in (("image", "image  ((r2+r3)-(r1+r4))/2"),
                       ("proprio", "proprio ((r2+r4)-(r1+r3))/2")):
        e = out[key]
        (a, na), (b, nb) = e["a"], e["b"]
        print(f"  {label:32s} {a}/{na} vs {b}/{nb}   effect {e['effect']:+.3f}   "
              f"Fisher two-sided p = {e['p']:.4g}")
    print()
    i = out["interaction"]
    print(f"  interaction (secondary)          (r2-r3)-(r4-r1) = {i['did']:+.3f}   "
          f"within-stratum permutation p = {i['p']:.4f}")
    print(f"    ({PERM_DRAWS} draws, seed {PERM_SEED}, criterion |T*| >= |did|, "
          f"p = (1+count)/(1+B);")
    print(f"     the exact enumeration reads {i['p_exact']:.4f})")
    print("    a redundancy/synergy descriptor, not the channel test: NEGATIVE = the")
    print("    both-parked cell (2) beats the additive prediction (neither channel alone")
    print("    suffices); POSITIVE = the single-channel cells beat it (either suffices);")
    print("    0 = additive, and the main effects carry the read. It adds nothing")
    print("    MEASURABLE UNDER THE CEILING (a probe cell already at 0 carried bounds what")
    print("    the descriptor can see), and it is 1 of 3 contrasts. Because cell 2 enters")
    print("    both main-effect tables, a converting cell 2 with null probe cells moves")
    print("    each table by half the effect - read the cells, not the tables alone.")
    print()

    print("[5] THE COMPOSITION READ (right arm): crude vs class-standardised")
    print()
    print("  cell   crude ok   std ok   crude carried   std carried   fraction (crude / std)"
          "   weight covered")
    for c in CELLS:
        r = out["cells"][c]["right"]
        frac = out["fraction"][c]
        fs = out["fraction_std"][c]
        ftext = "n/a" if frac != frac else f"{frac:+.2f}"
        fstext = "n/a" if fs != fs else f"{fs:+.2f}"
        print(f"  {c}      {_rate(r['ok'], r['n']):.3f}    {out['standardised'][c]:.3f}    "
              f"{_rate(r['carried'], r['n']):.3f}          {out['standardised_carried'][c]:.3f}"
              f"         {ftext} / {fstext:<5s}          {out['coverage'][c]:.2f}")
    print("  per-class table (right arm; n per cell, ok / carried / no-grasp):")
    species = sorted({row["category"] for c in CELLS
                      for row in out["cells"][c]["rows"] if row["arm"] == "right"})
    for name in species:
        parts = []
        for c in CELLS:
            rows = [row for row in out["cells"][c]["rows"]
                    if row["arm"] == "right" and row["category"] == name]
            if not rows:
                parts.append(f"{c}: -")
                continue
            k = Counter(classify(row) for row in rows)
            parts.append(f"{c}: {len(rows)} {k['ok']}/{k['carried']}/{k['no_grasp']}")
        print(f"    {name:8s} " + " | ".join(parts))
    print()
    print("    (direct standardisation to cell 1's right-arm species mix; `fraction`")
    print("     uses the standardised *carried* rate, the quantity the primary")
    print("     endpoint is about - `coverage` < 1 means a species cell 1 had is")
    print("     absent in that cell and the rest is renormalised)")
    print()

    print("[6] THE SECONDARY ENDPOINTS (right arm unless stated)")
    print()
    for c in CELLS:
        r = out["cells"][c]["right"]
        cy = out["cycle"][c]
        ca = out["calls"][c]
        print(f"  cell {c}: composite (carried+no-grasp) {r['carried'] + r['no_grasp']}"
              f"/{r['n']}   pooled ok {out['cells'][c]['all']['ok']}"
              f"/{out['cells'][c]['all']['n']}   cycle all {_ticks(cy['all'])} / "
              f"ok-only {_ticks(cy['ok'])} ticks   model calls/attempt "
              f"{_num(ca['median'])} ({_num(ca['min'])}-{_num(ca['max'])}, n={ca['n']})")
    print()
    for c in ("2", "3", "4"):
        print(f"  new failure reasons vs cell 1 (right arm), cell {c}: "
              f"{out['new_reasons'][c] or 'none'}")
    print()
    print("  run-level signs (negative = the contrast helps; consistency, not a test):")
    for key in ("image", "proprio"):
        vals = out["run_signs"][key]
        neg = sum(1 for v in vals if v < 0)
        print(f"    {key:8s} {['%+.3f' % v for v in vals]}   negative in {neg}/{len(vals)} runs")
    print()
    print("  the noise floor - the LEFT arm, a no-op in all four cells:")
    print("    carried rate per cell "
          + "  ".join(f"{c}:{out['left']['rate'][c]:.3f}"
                      f"({out['cells'][c]['left']['carried']}/"
                      f"{out['cells'][c]['left']['n']})" for c in CELLS))
    print(f"    the same contrasts on the no-op population: image "
          f"{out['left']['image']:+.3f}, proprio {out['left']['proprio']:+.3f}, "
          f"interaction {out['left']['did']:+.3f}; cell spread {out['left']['spread']:.3f}")
    print()

    print("[7] THE PRE-REGISTERED READING")
    print()
    print(f"  reading: {out['reading'].upper()}")
    print(f"  {READING_TEXT[out['reading']]}")
    print()
    print("  The between-cell contrast is the design-valid leg (the cells diverge after")
    print("  the first call, so no per-episode pairing is used). Cells 3/4 are OOD input")
    print("  pairs: a positive names the channel and does not ship; a null is weak")
    print("  evidence (PREREG section 8). The asymmetry is measured")
    print("  (logs/p36/ood_proprio.txt): cell 3 writes the in-support ready proprio")
    print("  (max |z| = 0.59 of the 7 channels, direct store; 0.37 of the training")
    print("  store) under the parked image; cell 4 writes the parked proprio, whose")
    print("  j2 (-0.978 rad) is the ONLY one of the 7 channels outside the observed")
    print("  range of either store ([-0.777,+0.175] direct, [-0.792,+0.175] training);")
    print("  the other two >1.7-sigma channels (j1, j4) sit inside theirs, so the")
    print("  4-5 sigma summary is a pooled-population mixture statistic and the range")
    print("  violation is what the read rests on. So a cell-4 positive is the stronger")
    print("  read (the park's own proprio, alone, on an in-support image) and a cell-4")
    print("  null the weaker one (an out-of-range input may simply be ignored or")
    print("  unrepresented) - the caveat points at the proprio null, not at the image")
    print("  cell, i.e. the conservative direction.")


# ---------------------------------------------------------------- self-test -- #
READY = {"left": [-1.464, -0.375, 1.488, 1.315, -1.496, -0.588, 1.559],
         "right": [1.520, 0.330, -1.570, 1.269, 1.560, 0.620, -1.566]}
BACK = {"left": [-1.912, -0.978, 1.503, 0.818, -1.498, -0.586, 1.559]}


def _line(index: int, cls: str, arm: str, category: str = "apple",
          diameter: float = 6.0, ticks: int = 1000) -> str:
    success = cls == "ok"
    grasped = cls in ("ok", "carried")
    placed = cls == "ok"
    return (
        f"[fruit] [rl] episode {index}: {category} d={diameter:.1f}cm bin="
        f"{1 if arm == 'right' else 0} arm={arm} success={success} "
        f"grasped={grasped} placed={placed} ticks={ticks} decision=300 "
        f"reward=0.9 notes=[] presentation=direct ablate=none\n"
    )


def _manip_rows(index: int, cell: str, arm: str) -> str:
    """The `[spoof]` + `[park]` rows a batch episode of `cell`/`arm` writes."""
    inactive = "right" if arm == "left" else "left"
    parked = POSE_OF_CELL[cell]
    pose = SPOOF_OF_CELL[cell]
    q = BACK["left"] if parked == "back" else READY["left"]
    if inactive == "right":
        q = READY["right"]
    arm_px = 234 if (parked == "ready" and inactive == "left") else 0
    park = (
        f"[fruit] [park] episode {index} arm={arm} inactive={inactive} "
        f"park={parked} m1_hold=+0.002 m1_hold_ok=1 m1_cmd=+0.03 "
        f"m2_arm=0.000 m2_arm_ok=1 m2_rel=0.9 m2_rel_ok=1 m2_ok=1 m2_vis=0.9 "
        f"band=+0.397 band_x=+0.30 band_px=52 band_disc=158 band_vis=0.33 "
        f"arm_px={arm_px} band_frac=0.0 band_calls=25 stale_skipped=1 "
        f"worst_arm_at=+0.37 worst_vis_at=+0.37 min_frac=0.0 max_frac=4.5 "
        f"drift=+0.004 calls=73 q={_fmt(q)} q_settled={_fmt(q)} top=belt\n"
    )
    call = (f"[fruit] [park] call ep={index} n=1 along=+0.350 x=0.300 px=52 "
            f"disc=158 vis=0.33 rel=0.9 arm_px={arm_px} tgt_px=52 frac=0.0 ok=1\n")
    if pose is None:
        spoof = (f"[fruit] [spoof] episode {index} pose=- applied=0 side={inactive} "
                 f"idx=- live=- obs=- pre_md5=aaaa obs_md5=aaaa rest_md5=aaaa "
                 f"rest_same=1 calls=73 drift=-\n")
    elif inactive == "left":
        spoof = (
            f"[fruit] [spoof] episode {index} pose={pose} applied=1 side=left "
            f"idx={LEFT_IDX} live={_fmt(BACK['left'] if pose == 'ready' else READY['left'])} "
            f"obs={_fmt(READY['left'] if pose == 'ready' else BACK['left'])} "
            f"pre_md5=bbbb obs_md5=cccc rest_md5=dddd rest_same=1 calls=73 "
            f"drift=+0.6035\n")
    elif inactive == "right" and pose == "ready":
        spoof = (
            f"[fruit] [spoof] episode {index} pose=ready applied=1 side=right "
            f"idx={RIGHT_IDX} live={_fmt(READY['right'])} obs={_fmt(READY['right'])} "
            f"pre_md5=eeee obs_md5=ffff rest_md5=dddd rest_same=1 calls=73 "
            f"drift=+0.0059\n")
    else:   # `back` has no right-arm vector -> the no-op side
        spoof = (f"[fruit] [spoof] episode {index} pose={pose} applied=0 side=right "
                 f"idx=- live=- obs=- pre_md5=aaaa obs_md5=aaaa rest_md5=aaaa "
                 f"rest_same=1 calls=73 drift=-\n")
    return park + call + spoof


def _write_cell(directory: str, cell: str, run: int, carried: int,
                n_right: int = 10, n_left: int = 5) -> None:
    path = os.path.join(directory, f"C{cell}_{run}.log")
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(n_right):
            fh.write(_line(i, "carried" if i < carried else "ok", "right"))
            fh.write(_manip_rows(i, cell, "right"))
        for i in range(n_left):
            fh.write(_line(100 + i, "ok", "left"))
            fh.write(_manip_rows(100 + i, cell, "left"))


def _write_table(tmp: str, carried: list[int], runs: int = 3) -> None:
    for cell, k in zip(CELLS, carried):
        for run in range(1, runs + 1):
            _write_cell(tmp, cell, run, k)


def self_test() -> int:
    ok = True

    def check(name: str, got, want) -> None:
        nonlocal ok
        if got != want:
            print(f"self-test FAILED: {name}: got {got!r} want {want!r}")
            ok = False

    # The arithmetic.
    check("wilson 0/30 upper", round(wilson(0, 30)[1], 3), 0.114)
    check("wilson 25/51 lower", round(wilson(25, 51)[0], 3), 0.359)
    check("fisher saturated", fisher_two_sided(0, 30, 30, 30) < 1e-9, True)
    # The absolute-epsilon bug: [[0,58],[35,22]]'s exact tail is 8.8e-15, and
    # the pre-fix form read 8.1e-13 because it counted every table below 1e-12.
    check("fisher extreme tail", round(math.log10(fisher_two_sided(0, 58, 35, 57)), 1),
          -14.1)
    check("fisher null", round(fisher_two_sided(15, 30, 15, 30), 3), 1.0)
    check("band 0.05", band(0.05), "full")
    check("band 0.20", band(0.20), "partial")
    check("band 0.49", band(0.49), "none")

    # k = right-arm carried counts per 10-episode run, cells 1..4. The lever
    # replicates in every scenario except "nonrep" (cell 2 at the control level).
    scenarios = {
        "image": ([5, 0, 0, 5], "image-borne"),
        "proprio": ([5, 0, 5, 0], "proprio-borne"),
        "both": ([5, 0, 0, 0], "both"),
        "conjunction": ([5, 0, 5, 5], "not identified"),
        "nonrep": ([5, 5, 0, 5], "non-replication"),
    }
    for name, (carried, want) in scenarios.items():
        with tempfile.TemporaryDirectory() as tmp:
            _write_table(tmp, carried)
            cells = load(tmp)
            comp = completeness(cells)
            check(f"{name} complete", comp["ok"], True)
            manip = manipulation(cells, comp["runs"])
            check(f"{name} manipulation", manip["ok"], True)
            out = analyse(cells, comp["runs"])
            check(f"{name} reading", out["reading"], want)
            check(f"{name} n", out["cells"]["1"]["right"]["n"], 30)
            check(f"{name} left n", out["cells"]["1"]["left"]["n"], 15)
            check(f"{name} calls", out["cells"]["1"]["right"]["n"], 30)

    # The image scenario: cell 3 reproduces 100 % of the lever, cell 4 none;
    # the interaction is additive (0) - the main effect carries the read.
    with tempfile.TemporaryDirectory() as tmp:
        _write_table(tmp, [5, 0, 0, 5])
        cells = load(tmp)
        out = analyse(cells, completeness(cells)["runs"])
        check("image: cell 3 fraction", round(out["fraction"]["3"], 3), 1.0)
        check("image: cell 4 fraction", round(out["fraction"]["4"], 3), 0.0)
        check("image: effect negative", out["image"]["effect"] < -0.3, True)
        check("image: proprio effect zero", round(out["proprio"]["effect"], 6), 0.0)
        check("image: interaction additive", round(out["interaction"]["did"], 3), 0.0)
        check("image: additive interaction p ~ 1", out["interaction"]["p"] > 0.99, True)
    # The conjunction pattern: the both-parked cell converts, both probe cells do
    # not -> a negative (synergy) interaction and two half-size main effects.
    with tempfile.TemporaryDirectory() as tmp:
        _write_table(tmp, [5, 0, 5, 5])
        cells = load(tmp)
        out = analyse(cells, completeness(cells)["runs"])
        check("conjunction: interaction negative",
              round(out["interaction"]["did"], 3), -0.5)
        check("conjunction: image effect half",
              round(out["image"]["effect"], 3), -0.25)
        # M1: the fixed criterion must be *centred on zero*, and the sampled p
        # must agree with the exact enumeration. The pre-fix form is pinned to
        # read >= 0.5 on this table - that was the bug.
        rk = {c: out["cells"][c]["right"]["carried"] for c in CELLS}
        rn = {c: out["cells"][c]["right"]["n"] for c in CELLS}
        p_fixed = interaction_p(rk, rn)
        p_exact = interaction_p_exact(rk, rn)
        p_old = interaction_p(rk, rn, criterion="centred")
        check("M1: fixed p matches the exact enumeration",
              abs(p_fixed - p_exact) < 0.02, True)
        check("M1: fixed p is below 0.5 on the conjunction table", p_fixed < 0.5, True)
        check("M1: the pre-fix criterion reads >= 0.5", p_old > 0.5, True)
        print(f"    M1 pin: p_fixed={p_fixed:.4f} p_exact={p_exact:.4f} "
              f"p_pre-fix={p_old:.4f}")

    # H2: a short batch is refused, not read.
    with tempfile.TemporaryDirectory() as tmp:
        _write_table(tmp, [5, 0, 0, 5], runs=2)
        comp = completeness(load(tmp))
        check("H2: 2 runs refused", comp["ok"], False)
        check("H2: the reason names the run count",
              any("2 run(s) present" in p for p in comp["problems"]), True)
    with tempfile.TemporaryDirectory() as tmp:
        _write_table(tmp, [5, 0, 0, 5])
        os.remove(os.path.join(tmp, "C3_2.log"))
        comp = completeness(load(tmp))
        check("H2: a missing cell-run refused", comp["ok"], False)
    with tempfile.TemporaryDirectory() as tmp:
        _write_table(tmp, [5, 0, 0, 5])
        path = os.path.join(tmp, "C2_1.log")
        lines = open(path, encoding="utf-8").read().splitlines(True)
        keep = [ln for ln in lines if not ln.startswith("[fruit] [rl] episode 9:")]
        open(path, "w", encoding="utf-8").writelines(keep)
        comp = completeness(load(tmp))
        check("H2: 14 episodes refused", comp["ok"], False)
        check("H2: the short cell-run is named",
              any("C2_1=14" in p for p in comp["problems"]), True)

    # M2: the manipulation check must fail on a wrong image cell and on a wrong
    # vector - the gate has to be able to say no.
    with tempfile.TemporaryDirectory() as tmp:
        _write_table(tmp, [5, 0, 0, 5])
        path = os.path.join(tmp, "C2_1.log")
        text = open(path, encoding="utf-8").read()
        open(path, "w", encoding="utf-8").write(text.replace("arm_px=0", "arm_px=17", 1))
        cells = load(tmp)
        manip = manipulation(cells, completeness(cells)["runs"])
        check("M2: a parked cell with arm pixels fails S4",
              any("C2" in text for text in manip["fails"]["S4"]), True)
        check("M2: the gate closes", manip["ok"], False)
    with tempfile.TemporaryDirectory() as tmp:
        _write_table(tmp, [5, 0, 0, 5])
        path = os.path.join(tmp, "C3_1.log")
        text = open(path, encoding="utf-8").read()
        open(path, "w", encoding="utf-8").write(text.replace("-1.464,-0.375", "-1.364,-0.375", 1))
        cells = load(tmp)
        manip = manipulation(cells, completeness(cells)["runs"])
        check("M2: a wrong written vector fails S1", bool(manip["fails"]["S1"]), True)
        check("M2: the gate closes on it", manip["ok"], False)

    # M2 (Gate 2): the gate's population is invariant. A silently dropped
    # `[park]` row must refuse the read (exit 2), not shrink the population the
    # manipulation check runs on.
    with tempfile.TemporaryDirectory() as tmp:
        _write_table(tmp, [5, 0, 0, 5])
        path = os.path.join(tmp, "C2_1.log")
        lines = open(path, encoding="utf-8").read().splitlines(True)
        keep = [ln for ln in lines if not ln.startswith("[fruit] [park] episode 9 ")]
        check("M2: the row was removed", len(lines) - len(keep), 1)
        open(path, "w", encoding="utf-8").writelines(keep)
        with contextlib.redirect_stdout(io.StringIO()):
            code = report(tmp)
        check("M2: a dropped [park] row refuses with exit 2", code, 2)
        cells = load(tmp)
        manip = manipulation(cells, completeness(cells)["runs"])
        check("M2: the count invariance names the shortfall",
              any("records" in text for text in manip["fails"]["M2"]), True)
        check("M2: the gate closes on the shortfall", manip["ok"], False)
    print("self-test ok" if ok else "self-test failed")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("directory", nargs="?", default=os.path.join("logs", "p36", "A_ab"))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    return report(args.directory)


def report(directory: str) -> int:
    """The whole read of one batch directory; the exit code `main` returns."""
    cells = load(directory)
    if not any(cells[c] for c in CELLS):
        raise SystemExit(f"no C{{1-4}}_{{run}}.log in {directory}")
    comp = completeness(cells)
    manip = manipulation(cells, comp["runs"])
    order = order_note(directory)
    if not comp["ok"]:
        print(f"P36 2x2 - {directory}")
        print("=" * 92)
        for line in order:
            print(line)
        print()
        print("[1] COMPLETENESS (H2): REFUSED - no reading from this batch")
        for problem in comp["problems"]:
            print(f"    {problem}")
        print("    episodes per cell-run:")
        for c in CELLS:
            print(f"      cell {c}: "
                  + ", ".join(f"run {r}={n}" for r, n in sorted(comp["episodes"][c].items())))
        print()
        print("  The pre-registered design is 3 runs x 15 episodes per cell (PREREG")
        print("  section 6); a partial run is re-run with P36_ONLY=\"<cell>_<run>\".")
        return 2

    out = analyse(cells, comp["runs"])
    render(out, comp, manip, order)
    if not manip["ok"]:
        return 2
    return 0 if out["replicates"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
