#!/usr/bin/env python3
"""P37 phase 2: the park-recollection A/B report (the adoption gate).

    python3 logs/p37/p37_report.py --dir logs/p37/B_ab --a A --b B
    python3 logs/p37/p37_report.py --self-test

Read-only. Parses the `A_N.log` / `B_N.log` written by `scripts/112_rl_ab.sh`
for the P37 batch (both arms parked: A = `moe_v13s`, B = the park-collected
fine-tune) and prints the pre-registered analysis of `logs/p37/PREREG.md`
section 6, with the Gate-1 H1/H2 conditions of the phase-2 dispatch.

**Gate H2 - the manipulation check (gates the outcome read).** From the batch's
own `[park]` rows, on **right-active** episodes (the park's population: the park
moves the *inactive left* arm) that have >= 1 band call:

  * **M1-held** - the realized pose within 0.02 rad of the `q_settled` the reset
    achieved (`m1_hold_ok=1` **and** `m1_hold <= 0.02`), as in `logs/p35/`;
  * **M1-applied** - the row's **own `q`** is the park and not `ready`:
    `max|q-back| <= 0.15` AND `max|q-ready| >= 0.30` AND `drift <= 0.02`
    (references: `configs/arm_parks.json` `back`, `configs/waypoints.json`
    `left.ready`). This is `logs/p35/park_ab_report.py`'s `m1_prime` term
    **except** that it reads `q` (the first non-stale call's live pose), not
    `q_settled` - the dispatch's H2 wording;
  * **M2a** - the worst band call's arm term `max arm_frac < 0.10`
    (the `max_frac` field, i.e. `arm_px / target_px` over the band's calls).

Each term must hold on **>= 95 %** of that population (PREREG section 5), and
the batch must carry **one `[park]` row per episode** (a dropped row refuses the
read instead of shrinking the gate - the P36 M2 convention). If any term fails,
the batch is **void for the outcome**: the report refuses to print a verdict.
`arm_px = 0` is the **band census report only** (per-call, exact counts), not a
gate term.

**Gate H1 - the endpoints.**

  * **M1 the primary**: pooled **right-arm placed** non-inferiority,
    `ok_B/n_B >= ok_A/n_A - 0.10` (MARGIN; the pre-registered power table
    `logs/p37/power_check.txt`). The report also prints the **exact
    unconditional non-inferiority p** (sup over the nuisance rate at the null
    boundary `p_B = p_A - MARGIN`, full binomial enumeration) and the
    **Newcombe hybrid-score one-sided 95 % lower bound** on `p_B - p_A`; the
    *gate* is the pre-registered point rule, the p/interval are supporting.
  * **S1** the left arm's **noise floor** (a no-op for the park: the inactive
    right arm has no park vector) - class table + rate delta + exact-instance
    pairing, reported, not gated.
  * **S2** the **species- and diameter-tertile-standardised** right-arm placed
    rate (direct standardisation to arm A's right-arm stratum weights,
    renormalised over covered strata, P36's convention). If the crude and the
    standardised deltas **straddle the margin**, the read is **ambiguous**.
  * **S3** no **new failure reason** (113's number normalisation), with the
    **count and arm** of every novel reason. The **gate is the pooled reason set
    over both arms** (the pre-registered rule); the **right arm** - the
    primary's population - is printed beside it as a specifier, because the left
    arm is a no-op with its own large carried class. In the 2026-10-25 batch the
    one novelty is a right-arm event, so the two cuts agree.
  * **S4** cycle: pooled median ticks, `B <= A x 1.05`.
  * **S5** the manipulation check (H2) - it gates the read.

The **decision** is the PREREG's: the candidate is an **adoption candidate** iff
the primary passes and S3 and S4 pass (and the manipulation check passed); it is
**not adopted** here in any case (the shipped default `FRUIT_ARM_PARK` off is the
owner's phase-3 decision).

**The label is deliberately conservative.** A pass with `p_hat < 0.94` (the
preserved-state level the power table assumes) and/or a **near-zero behaviour
change** (the `119_rl_fidelity.py` paired action delta <= 0.01 rad on every
store) is printed as **"PASS inside the ambiguous band / no-op"**, *not* as
preservation: at this n the bar cannot distinguish a preserved checkpoint from
one that drifted a little, and a checkpoint the fine-tune barely moved cannot be
evidence about the recollection at all.

The fidelity readout: `--fidelity logs/p37/fidelity.txt` (written by
`scripts/119_rl_fidelity.py --base moe_v13s --candidate p37_park --data
datasets/rl_rollouts/p37_park --data datasets/demos_v11 ...`, the PREREG's
section 4 diagnostic). If the file is absent the report says so and no near-zero
claim is made; `--run-fidelity` generates it first (needs the lingbot python).

The episode parser is `scripts/113_rl_report.py`'s (imported, not copied); the
`[park]` row regex, the reference vectors and the class definition are
`logs/p35/park_ab_report.py`'s (imported). The report's own md5 and the md5s of
both are printed in the header so a batch's report is identifiable.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import importlib.util
import math
import os
import re
import statistics as st
import subprocess
import sys
import tempfile
from collections import Counter

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
P35 = os.path.join(REPO, "logs", "p35", "park_ab_report.py")
P113 = os.path.join(REPO, "scripts", "113_rl_report.py")


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PARKMOD = _load("p35_park_ab_report", P35)
RL = _load("rl_report_113", P113)
PARK = PARKMOD.PARK
CALL = PARKMOD.CALL
fnum = PARKMOD.fnum
qvec = PARKMOD.qvec
read_refs = PARKMOD.read_refs
klass = PARKMOD.klass
sign_test_p = PARKMOD.sign_test_p

#: Pre-registered constants (PREREG sections 5-6 + the phase-2 dispatch H1/H2).
MARGIN = 0.10
PRESERVED_P = 0.94
CYCLE_BAR = 1.05
MANIP_BAR = 0.95
M1_HOLD_MAX = 0.02
M1_APPLIED_BACK = 0.15
M1_APPLIED_READY = 0.30
DRIFT_MAX = 0.02
M2_MAX_FRAC = 0.10
NEAR_ZERO_ACTION = 0.01        # rad; the fidelity no-op bar (declared, H1)
EPISODES_PER_RUN = 15
MIN_RUNS = 5
Z_ONE_SIDED = 1.6448536269514722

FID_PAIRED = re.compile(
    r"paired delta \((\w+) - (\w+)\): median ([-+0-9.eE]+) rad, "
    r"(\d+) improved / (\d+) worse / (\d+) ties, sign p=([0-9.eE+-]+)"
)
FID_ACTION = re.compile(
    r"action delta \((\w+) - (\w+)\): max ([-+0-9.eE]+) rad, "
    r"finger max ([-+0-9.eE]+)"
)
FID_HEAD = re.compile(r"^=== fidelity on (\S+)")


# --------------------------------------------------------------------- math -- #
def wilson_one_sided(k: int, n: int, z: float = Z_ONE_SIDED,
                     lower: bool = True) -> float:
    """The one-sided Wilson score bound (Newcombe's hybrid-score ingredient)."""
    if n <= 0:
        return float("nan")
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half) if lower else min(1.0, centre + half)


def newcombe_lower(k_b: int, n_b: int, k_a: int, n_a: int,
                   z: float = Z_ONE_SIDED) -> float:
    """One-sided lower bound on p_B - p_A (Newcombe method 10, hybrid score)."""
    if n_a <= 0 or n_b <= 0:
        return float("nan")
    p_b, p_a = k_b / n_b, k_a / n_a
    l_b = wilson_one_sided(k_b, n_b, z, lower=True)
    u_a = wilson_one_sided(k_a, n_a, z, lower=False)
    return (p_b - p_a) - math.sqrt((p_b - l_b) ** 2 + (u_a - p_a) ** 2)


def wald_lower(k_b: int, n_b: int, k_a: int, n_a: int,
               z: float = Z_ONE_SIDED) -> float:
    if n_a <= 0 or n_b <= 0:
        return float("nan")
    p_b, p_a = k_b / n_b, k_a / n_a
    se = math.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    return (p_b - p_a) - z * se


def wald_test(k_b: int, n_b: int, k_a: int, n_a: int,
              margin: float = MARGIN) -> tuple[float, float]:
    """The asymptotic non-inferiority z/p (supporting; the gate is the point rule)."""
    if n_a <= 0 or n_b <= 0:
        return float("nan"), float("nan")
    p_b, p_a = k_b / n_b, k_a / n_a
    se = math.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    if se == 0:
        return float("nan"), float("nan")
    z = (p_b - p_a + margin) / se
    p = 0.5 * math.erfc(z / math.sqrt(2.0))
    return z, p


_P_EXACT_CACHE: dict[tuple[int, int, int, int, float, int], float] = {}


def exact_noninferiority_p(k_b: int, n_b: int, k_a: int, n_a: int,
                           margin: float = MARGIN,
                           steps: int = 1000) -> float:
    """Exact unconditional one-sided p for H0: p_B - p_A <= -margin.

    The p-value is `sup over p_A` of `P(delta_hat >= delta_obs)` under
    `X_A ~ Bin(n_A, p_A)`, `X_B ~ Bin(n_B, max(0, p_A - margin))` - the null
    boundary is the worst case, so the test is exact unconditional up to the
    grid on the nuisance rate (1000 steps; the sup is flat near the optimum at
    these n). The comparison `k_B*n_A - k_A*n_B >= k_B_obs*n_A - k_A_obs*n_B`
    is exact integer arithmetic.
    """
    if n_a <= 0 or n_b <= 0:
        return float("nan")
    key = (k_b, n_b, k_a, n_a, float(margin), int(steps))
    if key in _P_EXACT_CACHE:
        return _P_EXACT_CACHE[key]
    obs = k_b * n_a - k_a * n_b          # delta_obs * n_A * n_B
    best = 0.0
    for step in range(int(steps) + 1):
        p_a = step / float(steps)
        p_b = p_a - margin
        if p_b < 0.0:
            continue
        pmf_a = [math.comb(n_a, k) * p_a ** k * (1.0 - p_a) ** (n_a - k)
                 for k in range(n_a + 1)]
        cum_a = []
        running = 0.0
        for value in pmf_a:
            running += value
            cum_a.append(running)
        total = 0.0
        for kb in range(n_b + 1):
            weight = math.comb(n_b, kb) * p_b ** kb * (1.0 - p_b) ** (n_b - kb)
            if weight == 0.0:
                continue
            # kA*nB <= kB*nA - obs  ->  kA <= floor((kB*nA - obs)/nB)
            k_max = (kb * n_a - obs) // n_b
            if k_max < 0:
                continue
            total += weight * cum_a[min(k_max, n_a)]
        if total > best:
            best = total
    best = min(1.0, best)
    _P_EXACT_CACHE[key] = best
    return best


def standardise(rows_a: list[dict], rows_b: list[dict], key) -> dict:
    """Direct standardisation of B to A's stratum weights (P36 convention).

    Returns the standardised B rate, A's own rate, coverage (A's weight mass
    carried into B), and the per-stratum table.
    """
    strata_a, strata_b = Counter(), Counter()
    ok_a, ok_b = Counter(), Counter()
    for row in rows_a:
        s = key(row)
        strata_a[s] += 1
        ok_a[s] += int(bool(row["success"] or row["placed"]))
    for row in rows_b:
        s = key(row)
        strata_b[s] += 1
        ok_b[s] += int(bool(row["success"] or row["placed"]))
    n_a = sum(strata_a.values())
    if not n_a:
        return {"rate": float("nan"), "rate_a": float("nan"),
                "coverage": float("nan"), "table": []}
    num = 0.0
    covered = 0
    table = []
    for s, weight in strata_a.items():
        n_b = strata_b.get(s, 0)
        rate_b = (ok_b[s] / n_b) if n_b else float("nan")
        table.append((s, strata_a[s], ok_a[s], n_b, ok_b[s], rate_b))
        if n_b:
            num += (weight / n_a) * (ok_b[s] / n_b)
            covered += weight
    coverage = covered / n_a
    return {"rate": (num * n_a / covered) if covered else float("nan"),
            "rate_a": sum(ok_a.values()) / n_a,
            "coverage": coverage, "table": table}


def tertile_key(bounds: list[float]):
    def key(row: dict) -> int:
        d = row["diameter"]
        return 0 if d <= bounds[0] else (1 if d <= bounds[1] else 2)
    return key


def tertile_bounds(rows: list[dict]) -> list[float]:
    values = sorted(row["diameter"] for row in rows)
    if len(values) < 3:
        return [float("inf"), float("inf")]
    return [values[len(values) // 3], values[(2 * len(values)) // 3]]


# --------------------------------------------------------------------- load -- #
def read_dir(directory: str, label: str) -> dict[int, dict]:
    """{run: {"eps": [...], "park": {ep: row}, "calls": {ep: [row]}}}."""
    out: dict[int, dict] = {}
    for path in sorted(glob.glob(os.path.join(directory, f"{label}_*.log"))):
        stem = os.path.basename(path)[:-4]
        try:
            run = int(stem.rsplit("_", 1)[1])
        except (IndexError, ValueError):
            continue
        rec = {"eps": RL.parse(path), "park": {}, "calls": {}, "path": path}
        for line in open(path, encoding="utf-8", errors="replace"):
            m = PARK.search(line)
            if m:
                rec["park"][int(m.group(1))] = {
                    "arm": m.group(2), "inactive": m.group(3), "park": m.group(4),
                    "m1_hold": fnum(m.group(5)), "m1_hold_ok": int(m.group(6)),
                    "m1_cmd": fnum(m.group(7)),
                    "m2_arm": fnum(m.group(8)), "m2_arm_ok": int(m.group(9)),
                    "m2_rel": fnum(m.group(10)), "m2_rel_ok": int(m.group(11)),
                    "m2_ok": int(m.group(12)), "m2_vis": fnum(m.group(13)),
                    "band": fnum(m.group(14)), "band_x": fnum(m.group(15)),
                    "band_px": int(m.group(16)), "band_disc": fnum(m.group(17)),
                    "band_vis": fnum(m.group(18)), "arm_px": int(m.group(19)),
                    "band_frac": fnum(m.group(20)), "band_calls": int(m.group(21)),
                    "stale_skipped": int(m.group(22)),
                    "worst_arm_at": fnum(m.group(23)),
                    "worst_vis_at": fnum(m.group(24)),
                    "min_frac": fnum(m.group(25)), "max_frac": fnum(m.group(26)),
                    "drift": fnum(m.group(27)), "calls": int(m.group(28)),
                    "q": m.group(29), "q_settled": m.group(30),
                    "top": m.group(31),
                }
                continue
            m = CALL.search(line)
            if m:
                rec["calls"].setdefault(int(m.group(1)), []).append({
                    "px": int(m.group(5)), "arm_px": int(m.group(9)),
                })
        out[run] = rec
    return out


def plate(e: dict) -> bool:
    return bool(e.get("success") or e.get("placed"))


# ---------------------------------------------------------------- H2: check -- #
def m1_applied(row: dict, ready: list[float], back: list[float]) -> tuple[float, float, float, int]:
    """(d_back, d_ready, drift, pass) from the row's own `q` (H2's wording).

    `logs/p35/park_ab_report.py`'s `m1_prime` reads `q_settled` first; this
    reads `q` (the first non-stale call's live pose) and falls back to
    `q_settled` only when `q` is absent (and says so through `source`).
    """
    q = qvec(row.get("q") or "")
    if len(q) != 7:
        q = qvec(row.get("q_settled") or "")
    if len(q) != 7:
        return float("nan"), float("nan"), float("nan"), 0
    d_back = max(abs(a - b) for a, b in zip(q, back))
    d_ready = max(abs(a - b) for a, b in zip(q, ready))
    drift = row["drift"]
    ok = int(d_back <= M1_APPLIED_BACK and d_ready >= M1_APPLIED_READY
             and drift == drift and drift <= DRIFT_MAX)
    return d_back, d_ready, drift, ok


def _manipulation_one(records: list[dict], ready: list[float],
                      back: list[float]) -> dict:
    """H2 on one arm's records: M1-held + M1-applied + M2a (banded right-active)."""
    right = [r for r in records if r["arm"] == "right"]
    banded = [r for r in right if r["park"]["band_calls"] > 0]
    not_banded = [r for r in right if r["park"]["band_calls"] <= 0]
    holds = [r for r in banded
             if r["park"]["m1_hold_ok"] == 1
             and r["park"]["m1_hold"] == r["park"]["m1_hold"]
             and r["park"]["m1_hold"] <= M1_HOLD_MAX]
    applied, applied_terms = [], []
    for r in banded:
        d_back, d_ready, drift, good = m1_applied(r["park"], ready, back)
        applied_terms.append((r, d_back, d_ready, drift, good))
        if good:
            applied.append(r)
    m2 = [r for r in banded
          if r["park"]["max_frac"] == r["park"]["max_frac"]
          and 0.0 <= r["park"]["max_frac"] < M2_MAX_FRAC]
    conjunction = [r for r in banded if r in holds and r in applied and r in m2]
    # the per-call band census (reported, NOT gated - arm_px = 0 is not a bar)
    census = {"calls": 0, "hidden": 0, "arm_any": 0}
    for r in right:
        for call in r["calls"]:
            census["calls"] += 1
            census["hidden"] += int(call["px"] == 0)
            census["arm_any"] += int(call["arm_px"] > 0)
    ok = bool(banded) and all(
        (len(sel) / len(banded)) >= MANIP_BAR
        for sel in (holds, applied, m2)
    )
    return {
        "ok": ok, "right": len(right), "banded": len(banded),
        "not_banded": len(not_banded), "holds": len(holds),
        "applied": len(applied), "m2": len(m2),
        "conjunction": len(conjunction),
        "d_back": [t[1] for t in applied_terms],
        "d_ready": [t[2] for t in applied_terms],
        "drift": [t[3] for t in applied_terms],
        "max_frac": [r["park"]["max_frac"] for r in banded],
        "band_calls": [r["park"]["band_calls"] for r in banded],
        "census": census,
    }


def manipulation(arms: dict[str, dict[int, dict]], runs: list[int],
                 ready: list[float], back: list[float]) -> dict:
    """H2 per arm and pooled; the gate is the conjunction on **each** arm.

    Both arms are parked in the P37 batch, so a broken arm may not hide behind
    the other: the per-arm bar (>= 95 % on each term, PREREG section 5) is the
    gate, and a missing `[park]` row anywhere refuses the read (the P36 M2
    count-invariance convention).
    """
    per_arm: dict[str, dict] = {}
    missing: list[str] = []
    inactive_right = 0
    all_records: list[dict] = []
    for label, arm in arms.items():
        records: list[dict] = []
        for run in runs:
            for e in arm[run]["eps"]:
                park = arm[run]["park"].get(e["index"])
                if park is None:
                    missing.append(f"{label}_{run} ep{e['index']}")
                    continue
                rec = {"label": label, "run": run, "ep": e["index"],
                       "arm": e["arm"], "park": park,
                       "calls": arm[run]["calls"].get(e["index"], [])}
                records.append(rec)
                if rec["arm"] == "right" and park["inactive"] != "left":
                    inactive_right += 1
        per_arm[label] = _manipulation_one(records, ready, back)
        all_records.extend(records)
    pooled = _manipulation_one(all_records, ready, back)
    ok = (bool(pooled["banded"]) and not missing and inactive_right == 0
          and all(item["ok"] for item in per_arm.values()))
    return {"ok": ok, "per_arm": per_arm, "pooled": pooled, "records":
            len(all_records), "missing": missing, "inactive_right": inactive_right}


# ------------------------------------------------------------- endpoints ----- #
def reasons(rows: list[dict]) -> set[str]:
    out = set()
    for row in rows:
        if plate(row):
            continue
        text = (row.get("notes") or "[]").strip("[]").strip()
        out.add("empty note" if not text else re.sub(r"[-+0-9.]+", "#", text))
    return out


def novelty(rows_a: list[dict], rows_b: list[dict]) -> dict:
    """The new-reason set diff with the count and the arm of every novel reason."""
    set_a, set_b = reasons(rows_a), reasons(rows_b)
    new = sorted(set_b - set_a)
    counts: dict[str, Counter] = {reason: Counter() for reason in new}
    episodes = {reason: [] for reason in new}
    for row in rows_b:
        if plate(row):
            continue
        text = (row.get("notes") or "[]").strip("[]").strip()
        key = "empty note" if not text else re.sub(r"[-+0-9.]+", "#", text)
        if key in counts:
            counts[key][row["arm"]] += 1
            episodes[key].append((row["run"], row["index"], row["arm"]))
    return {"a": set_a, "b": set_b, "new": new, "counts": counts,
            "episodes": episodes}


def cycle_med(rows: list[dict]) -> float:
    return st.median([r["ticks"] for r in rows]) if rows else float("nan")


def pairs(arms: dict[str, dict[int, dict]], runs: list[int],
          la: str, lb: str, want_arm: str | None = None) -> dict:
    """Exact-instance pairing (run + episode + species + diameter + arm)."""
    counts = Counter()
    trans: dict[tuple[str, str], list[tuple]] = {}
    for run in runs:
        ea = {e["index"]: e for e in arms[la][run]["eps"]}
        eb = {e["index"]: e for e in arms[lb][run]["eps"]}
        for ep in sorted(set(ea) & set(eb)):
            a, b = ea[ep], eb[ep]
            if want_arm and (a["arm"] != want_arm or b["arm"] != want_arm):
                counts["excluded"] += 1
                continue
            if (a["category"] != b["category"]
                    or round(a["diameter"], 3) != round(b["diameter"], 3)
                    or a["arm"] != b["arm"]):
                counts["excluded"] += 1
                continue
            oa, ob = plate(a), plate(b)
            key = ("both_ok" if oa and ob else "a_only" if oa else
                   "b_only" if ob else "both_fail")
            counts[key] += 1
            trans.setdefault((klass(a), klass(b)), []).append((run, ep, a, b))
    n = counts["b_only"] + counts["a_only"]
    return {"counts": counts, "trans": trans, "p": sign_test_p(counts["b_only"],
                                                               counts["a_only"]),
            "usable": sum(counts[k] for k in ("both_ok", "both_fail", "b_only",
                                              "a_only"))}


# ---------------------------------------------------------------- fidelity --- #
def parse_fidelity(path: str) -> dict:
    """{data: {paired_median, improved, worse, ties, sign_p, action_max}}."""
    if not path or not os.path.isfile(path):
        return {}
    out: dict[str, dict] = {}
    current = None
    for line in open(path, encoding="utf-8", errors="replace"):
        m = FID_HEAD.search(line)
        if m:
            current = m.group(1)
            out.setdefault(current, {})
            continue
        if current is None:
            continue
        m = FID_PAIRED.search(line)
        if m:
            out[current].update({
                "paired_median": float(m.group(3)),
                "improved": int(m.group(4)), "worse": int(m.group(5)),
                "ties": int(m.group(6)), "sign_p": float(m.group(7)),
            })
            continue
        m = FID_ACTION.search(line)
        if m:
            out[current].update({"action_max": float(m.group(3)),
                                 "finger_max": float(m.group(4))})
    return out


def near_zero(fidelity: dict) -> tuple[bool, str]:
    values = [v["action_max"] for v in fidelity.values() if "action_max" in v]
    if not values:
        return False, "not measured"
    worst = max(values)
    if worst <= NEAR_ZERO_ACTION:
        return True, f"max |delta action| = {worst:.3e} rad <= {NEAR_ZERO_ACTION}"
    return False, f"max |delta action| = {worst:.3f} rad > {NEAR_ZERO_ACTION}"


def run_fidelity(path: str, base: str, cand: str, python: str,
                 windows: int = 192) -> int:
    cmd = [python, os.path.join(REPO, "scripts", "119_rl_fidelity.py"),
           "--base", base, "--candidate", cand,
           "--data", "datasets/rl_rollouts/p37_park",
           "--data", "datasets/demos_v11",
           "--windows", str(windows), "--ddim", "16",
           "--out", path]
    print(f"  running: {' '.join(cmd)}", flush=True)
    return subprocess.call(cmd, cwd=REPO)


# ------------------------------------------------------------------ report --- #
def analyse(directory: str, a_label: str, b_label: str) -> dict:
    arms = {a_label: read_dir(directory, a_label),
            b_label: read_dir(directory, b_label)}
    runs = sorted(set(arms[a_label]) & set(arms[b_label]))
    problems: list[str] = []
    if len(runs) < MIN_RUNS:
        problems.append(f"{len(runs)} run(s) present, {MIN_RUNS} required "
                        "(the pre-registered N = 5)")
    for label in (a_label, b_label):
        for run in runs:
            n = len(arms[label][run]["eps"])
            if n != EPISODES_PER_RUN:
                problems.append(f"{label}_{run}: {n} episodes != {EPISODES_PER_RUN}")
    ready, back = read_refs()
    manip = manipulation(arms, runs, ready, back) if runs else {}
    pooled = {label: [dict(e, run=run) for run in runs
                      for e in arms[label][run]["eps"]]
              for label in (a_label, b_label)}
    right = {label: [e for e in pooled[label] if e["arm"] == "right"]
             for label in (a_label, b_label)}
    left = {label: [e for e in pooled[label] if e["arm"] == "left"]
            for label in (a_label, b_label)}

    k_a = sum(1 for e in right[a_label] if plate(e))
    k_b = sum(1 for e in right[b_label] if plate(e))
    n_a, n_b = len(right[a_label]), len(right[b_label])
    delta = (k_b / n_b - k_a / n_a) if n_a and n_b else float("nan")
    primary_pass = bool(n_a and n_b and delta >= -MARGIN)
    p_exact = exact_noninferiority_p(k_b, n_b, k_a, n_a)
    lo_new = newcombe_lower(k_b, n_b, k_a, n_a)
    lo_wald = wald_lower(k_b, n_b, k_a, n_a)
    z_wald, p_wald = wald_test(k_b, n_b, k_a, n_a)

    # S2: standardisation (species, diameter tertiles) to A's weights.
    species = standardise(right[a_label], right[b_label],
                          key=lambda row: row["category"])
    bounds = tertile_bounds(right[a_label] + right[b_label])
    diam = standardise(right[a_label], right[b_label], key=tertile_key(bounds))
    crude_delta = delta
    std_delta = (species["rate"] - species["rate_a"]
                 if species["rate"] == species["rate"] else float("nan"))
    diam_delta = (diam["rate"] - diam["rate_a"]
                  if diam["rate"] == diam["rate"] else float("nan"))
    passes = [crude_delta >= -MARGIN]
    for value in (std_delta, diam_delta):
        if value == value:
            passes.append(value >= -MARGIN)
    straddle = len(set(passes)) > 1

    # S3: the new-reason set diff (pooled is the gate; the right arm is reported).
    nov = novelty(pooled[a_label], pooled[b_label])
    nov_right = novelty(right[a_label], right[b_label])
    s3_pass = not nov["new"]

    # S4: the cycle (pooled is the pre-registered cut; the right arm is reported).
    cyc_a, cyc_b = cycle_med(pooled[a_label]), cycle_med(pooled[b_label])
    cyc_a_r, cyc_b_r = cycle_med(right[a_label]), cycle_med(right[b_label])
    s4_pass = bool(cyc_a == cyc_a and cyc_a > 0 and cyc_b <= CYCLE_BAR * cyc_a)

    return {
        "arms": arms, "runs": runs, "problems": problems, "manip": manip,
        "pooled": pooled, "right": right, "left": left,
        "k_a": k_a, "n_a": n_a, "k_b": k_b, "n_b": n_b,
        "rate_a": (k_a / n_a) if n_a else float("nan"),
        "rate_b": (k_b / n_b) if n_b else float("nan"),
        "delta": delta, "primary_pass": primary_pass,
        "p_exact": p_exact, "lo_newcombe": lo_new, "lo_wald": lo_wald,
        "z_wald": z_wald, "p_wald": p_wald,
        "species": species, "diam": diam, "bounds": bounds,
        "crude_delta": crude_delta, "std_delta": std_delta,
        "diam_delta": diam_delta, "straddle": straddle,
        "novelty": nov, "novelty_right": nov_right, "s3_pass": s3_pass,
        "cycle_a": cyc_a, "cycle_b": cyc_b,
        "cycle_a_right": cyc_a_r, "cycle_b_right": cyc_b_r, "s4_pass": s4_pass,
        "pairs_right": pairs(arms, runs, a_label, b_label, "right"),
        "pairs_left": pairs(arms, runs, a_label, b_label, "left"),
    }


def label_and_decision(out: dict, fidelity: dict) -> dict:
    """The label (conservative) and the pre-registered adoption decision."""
    manip_ok = bool(out["manip"].get("ok"))
    nz, nz_text = near_zero(fidelity)
    reasons: list[str] = []
    if out["primary_pass"] and out["rate_b"] == out["rate_b"]:
        if out["rate_b"] < PRESERVED_P:
            reasons.append(f"p_hat = {out['rate_b']:.3f} < {PRESERVED_P:.2f}")
    if out["primary_pass"] and nz:
        reasons.append("near-zero behaviour change (" + nz_text + ")")
    if not manip_ok:
        label = "VOID for the outcome (S5 manipulation check FAILED)"
    elif not out["primary_pass"]:
        label = "NOT PRESERVED (primary FAIL: the recollection erases the park's win)"
    elif reasons:
        label = "PASS inside the ambiguous band / no-op (" + "; ".join(reasons) + ")"
    else:
        label = "PASS (preservation candidate)"
    adoption = bool(manip_ok and out["primary_pass"] and out["s3_pass"]
                    and out["s4_pass"])
    return {"label": label, "reasons": reasons, "near_zero": nz,
            "near_zero_text": nz_text, "adoption": adoption}


def _md5(path: str) -> str:
    return hashlib.md5(open(path, "rb").read()).hexdigest() if os.path.isfile(path) else "?"


def render(out: dict, a_label: str, b_label: str, fidelity_path: str,
           fidelity: dict, verdict: dict) -> None:
    runs = out["runs"]
    print("P37 - the park-collected recollection vs the base (both arms parked)")
    print("=" * 92)
    print(f"  dir runs: {runs}")
    print(f"  report md5 {_md5(os.path.abspath(__file__))} | "
          f"113_rl_report.py {_md5(P113)} | logs/p35/park_ab_report.py {_md5(P35)}")
    print(f"  arm A = baseline ({a_label}); arm B = candidate ({b_label})")
    print()

    print("[0] COMPLETENESS / the realized n")
    print()
    if out["problems"]:
        for problem in out["problems"]:
            print(f"  FAIL {problem}")
        print("  REFUSED: the batch is not the pre-registered design.")
        print()
        return
    for label in (a_label, b_label):
        eps, right, left = out["pooled"][label], out["right"][label], out["left"][label]
        print(f"  {label}: {len(eps)} episodes over {len(runs)} runs "
              f"(right n={len(right)}, left n={len(left)})")
    print(f"  realized n (primary): A {out['n_a']} / B {out['n_b']} right-arm episodes")
    print()

    print("[1] S5 / GATE H2 - the manipulation check (gates the outcome read)")
    print()
    m = out["manip"]
    print(f"  [park] rows: {m['records']} for "
          f"{len(out['pooled'][a_label]) + len(out['pooled'][b_label])} episodes | "
          f"rows whose inactive side is right {m['inactive_right']} | missing "
          f"{len(m['missing'])}")
    if m["missing"]:
        for text in m["missing"][:6]:
            print(f"    FAIL missing [park] row: {text}")
    for label in (a_label, b_label):
        item = m["per_arm"][label]
        print(f"  arm {label}: right-active {item['right']} (with a band call "
              f"{item['banded']}, without {item['not_banded']})")
        for name, good, total in (
            ("M1-held  (<=0.02 rad vs q_settled)", item["holds"], item["banded"]),
            ("M1-applied (|q-back|<=0.15, |q-ready|>=0.30, drift<=0.02)",
             item["applied"], item["banded"]),
            ("M2a  (max band arm_frac < 0.10)", item["m2"], item["banded"]),
            ("the conjunction (all three)", item["conjunction"], item["banded"]),
        ):
            share = (good / total * 100.0) if total else float("nan")
            flag = "PASS" if total and good / total >= MANIP_BAR else "FAIL"
            print(f"    {flag}  {name:58s} {good:3d}/{total:<3d} ({share:5.1f} %)")
        vals = [v for v in item["d_back"] if v == v]
        vals2 = [v for v in item["d_ready"] if v == v]
        drifts = [v for v in item["drift"] if v == v]
        if vals and vals2 and drifts:
            print(f"           |q-back| median {st.median(vals):.3f} "
                  f"(max {max(vals):.3f}) | |q-ready| median "
                  f"{st.median(vals2):.3f} (min {min(vals2):.3f}) | drift max "
                  f"{max(drifts):.3f} rad")
        if item["band_calls"]:
            print(f"           band calls per episode median "
                  f"{st.median(item['band_calls']):.0f} "
                  f"({min(item['band_calls'])}-{max(item['band_calls'])}) | "
                  f"max_frac median {st.median(item['max_frac']):.3f} "
                  f"(max {max(item['max_frac']):.3f})")
        c = item["census"]
        if c["calls"]:
            print(f"           census (REPORT ONLY, arm_px = 0 is not a bar): "
                  f"{c['calls']} band calls | fully hidden {c['hidden']}/"
                  f"{c['calls']} = {100.0 * c['hidden'] / c['calls']:.1f}% | "
                  f"any inactive-arm pixel {c['arm_any']}/{c['calls']} = "
                  f"{100.0 * c['arm_any'] / c['calls']:.1f}%")
    print(f"  => manipulation {'PASS' if m['ok'] else 'FAIL'} (bar "
          f"{MANIP_BAR:.0%} on each term, per arm, one [park] row per episode)")
    print()
    if not m["ok"]:
        print("REFUSED: the manipulation gate is a precondition - no outcome claim.")
        print("The tables below are descriptive only; diagnose the failed term first")
        print("(PREREG section 5: 'the batch is void for the outcome').")
        print()

    print("[2] M1 - THE PRIMARY (pooled right-arm placed; the park's population)")
    print()
    print(f"  A: {out['k_a']}/{out['n_a']} = {out['rate_a']:.3f} | "
          f"B: {out['k_b']}/{out['n_b']} = {out['rate_b']:.3f} | "
          f"delta (B-A) {out['delta']:+.3f} vs the non-inferiority margin "
          f"{-MARGIN:+.2f}")
    print(f"  exact unconditional non-inferiority p = {out['p_exact']:.4f} "
          f"(sup over the nuisance rate at p_B = p_A - {MARGIN:.2f}; discrete and "
          f"conservative at this n)")
    print(f"  one-sided 95% lower bound on delta: Newcombe {out['lo_newcombe']:+.3f} | "
          f"Wald {out['lo_wald']:+.3f} (z = {out['z_wald']:.2f}, "
          f"p = {out['p_wald']:.4f})")
    print("         at ~50 right-arm episodes/arm the interval is about the margin")
    print("         wide even under exact equality (Newcombe -0.105 and Wald p 0.048")
    print("         at 45/50 vs 45/50) - supporting, not the gate; the")
    print("         pre-registered point rule's power is the power table's 99.1 %.")
    print(f"  => primary {'PASS' if out['primary_pass'] else 'FAIL'} "
          f"(pre-registered rule: delta >= {-MARGIN:+.2f}; the p/interval are "
          f"supporting, not the gate)")
    print()

    print("[3] the right-arm class table and the P33 exact-instance pairing")
    print()
    for label in (a_label, b_label):
        rows = out["right"][label]
        cls = Counter(klass(r) for r in rows)
        print(f"  {label}: n={len(rows)} ok={cls['ok']} carried-not-placed={cls['carried']} "
              f"no-grasp={cls['no-contact']} other={cls['other']} | composite="
              f"{cls['carried'] + cls['no-contact']}")
    p = out["pairs_right"]
    print(f"  paired (right, exact fruit): usable {p['usable']} "
          f"(excluded {p['counts']['excluded']}) | both_ok {p['counts']['both_ok']} "
          f"both_fail {p['counts']['both_fail']} B-only {p['counts']['b_only']} "
          f"A-only {p['counts']['a_only']} | one-sided sign p={p['p']:.4f}")
    conv_b = len(p["trans"].get(("carried", "ok"), []))
    conv_a = len(p["trans"].get(("ok", "carried"), []))
    print(f"  carried-class conversions: B-only {conv_b}, A-only {conv_a} "
          f"- PRE-REGISTERED DEGENERATE: the park's own arm read 0/50 carried "
          f"(P35) and the store 0/58, so this endpoint has almost no events under "
          f"the park; reported, not gated")
    print()

    print("[4] S1 - the left noise floor (a no-op for the park: no right-arm park vector)")
    print()
    for label in (a_label, b_label):
        rows = out["left"][label]
        cls = Counter(klass(r) for r in rows)
        print(f"  {label}: n={len(rows)} ok={cls['ok']} carried={cls['carried']} "
              f"no-grasp={cls['no-contact']}")
    ka = sum(1 for r in out["left"][a_label] if plate(r))
    kb = sum(1 for r in out["left"][b_label] if plate(r))
    print(f"  left ok A {ka}/{len(out['left'][a_label])} vs B {kb}/"
          f"{len(out['left'][b_label])}"
          f" | delta {((kb / len(out['left'][b_label])) if out['left'][b_label] else float('nan')) - ((ka / len(out['left'][a_label])) if out['left'][a_label] else float('nan')):+.3f}"
          f" - a ONE-SIDED floor at the ceiling (1-3 ok per arm); reported, not gated")
    pl = out["pairs_left"]
    print(f"  paired (left, exact fruit): usable {pl['usable']} | B-only "
          f"{pl['counts']['b_only']} A-only {pl['counts']['a_only']} | sign "
          f"p={pl['p']:.4f}")
    print()

    print("[5] S2 - the standardised right-arm placed rate (crude vs standardised)")
    print()
    print(f"  crude: A {out['rate_a']:.3f} / B {out['rate_b']:.3f} -> delta "
          f"{out['crude_delta']:+.3f} ({'pass' if out['crude_delta'] >= -MARGIN else 'fail'})")
    for name, key, result, delta in (
        ("species", "species", out["species"], out["std_delta"]),
        ("diameter tertiles", "diam", out["diam"], out["diam_delta"]),
    ):
        print(f"  {name}: A {result['rate_a']:.3f} / B {result['rate']:.3f} -> delta "
              f"{delta:+.3f} ({'pass' if delta >= -MARGIN else 'fail'}) | "
              f"coverage {result['coverage']:.2f}")
        for stratum, n_a, ok_a, n_b, ok_b, rate_b in result["table"]:
            print(f"      {str(stratum)[:20]:20s} A {ok_a:2d}/{n_a:<2d}  "
                  f"B {ok_b:2d}/{n_b:<2d}  B rate "
                  f"{'n/a' if rate_b != rate_b else f'{rate_b:.2f}'}")
    if key == "diam":
        print(f"      (tertile cuts {out['bounds'][0]:.2f} / {out['bounds'][1]:.2f} cm, "
              f"pooled right-arm diameters)")
    print(f"  => {'AMBIGUOUS: the crude and the standardised deltas straddle the margin'
                   if out['straddle'] else 'the crude and standardised deltas agree on the margin'}")
    print()

    print("[6] S3 - new failure reasons (113's number normalisation)")
    print()
    for label in (a_label, b_label):
        seen = out["novelty"]["b" if label == b_label else "a"]
        print(f"  {label}: {sorted(seen) or 'none'}")
    if out["novelty"]["new"]:
        for reason in out["novelty"]["new"]:
            counts = out["novelty"]["counts"][reason]
            eps = out["novelty"]["episodes"][reason]
            print(f"  NEW in {b_label}: {reason!r} | count "
                  f"{sum(counts.values())} (left {counts['left']}, right "
                  f"{counts['right']}) | ep {eps[:6]}")
    else:
        print(f"  NEW in {b_label}: none")
    print(f"  => S3 {'PASS' if out['s3_pass'] else 'FAIL'}"
          f" (right-arm-only set: {sorted(out['novelty_right']['new']) or 'none'})")
    print()

    print("[7] S4 - cycle (pooled median simulated ticks; B <= A x 1.05)")
    print()
    print(f"  pooled: A {out['cycle_a']:.0f} / B {out['cycle_b']:.0f} ticks -> "
          f"{(out['cycle_b'] / out['cycle_a'] - 1) * 100:+.1f}%")
    print(f"  right arm (the inference population): A {out['cycle_a_right']:.0f} / "
          f"B {out['cycle_b_right']:.0f} ticks -> "
          f"{(out['cycle_b_right'] / out['cycle_a_right'] - 1) * 100:+.1f}%")
    print(f"  => S4 {'PASS' if out['s4_pass'] else 'FAIL'} (bar <= +5.0%)")
    print()

    print("[8] the fidelity readout (119_rl_fidelity.py; diagnostic, not a gate)")
    print()
    if not fidelity:
        print(f"  no fidelity file at {fidelity_path} - not measured "
              f"(no near-zero claim is made)")
    else:
        for data, row in fidelity.items():
            if "paired_median" in row:
                print(f"  {data}: paired delta median {row['paired_median']:+.4f} rad "
                      f"({row['improved']} improved / {row['worse']} worse / "
                      f"{row['ties']} ties, sign p={row['sign_p']:.4f})"
                      + (f" | max |delta action| {row['action_max']:.3e} rad"
                         if "action_max" in row else ""))
            else:
                print(f"  {data}: (no paired line parsed)")
        print(f"  => behaviour change: {verdict['near_zero_text']}")
    print()

    print("[9] M1-M4 SUMMARY AND THE PRE-REGISTERED DECISION")
    print()
    print(f"  M1  observed delta {out['delta']:+.3f} | one-sided 95% lower bound "
          f"(Newcombe) {out['lo_newcombe']:+.3f} | exact p {out['p_exact']:.4f} | "
          f"realized n A {out['n_a']} / B {out['n_b']} | "
          f"{'PASS' if out['primary_pass'] else 'FAIL'}")
    print(f"  M2  standardised right rate: crude {out['crude_delta']:+.3f}, "
          f"species {out['std_delta']:+.3f}, diameter {out['diam_delta']:+.3f} -> "
          f"{'AMBIGUOUS (straddles the margin)' if out['straddle'] else 'consistent'}")
    print(f"  M3  new reasons in B: {len(out['novelty']['new'])}"
          + (f" -> {[(r, sum(out['novelty']['counts'][r].values()),
                        dict(out['novelty']['counts'][r])) for r in out['novelty']['new']]}"
             if out["novelty"]["new"] else "")
          + f" | S3 {'PASS' if out['s3_pass'] else 'FAIL'}")
    print(f"  M4  S4 cycle {'PASS' if out['s4_pass'] else 'FAIL'} | "
          f"S5 manipulation {'PASS' if out['manip'].get('ok') else 'FAIL'}")
    print()
    print(f"  LABEL: {verdict['label']}")
    print(f"  adoption candidate: {'YES' if verdict['adoption'] else 'NO'} "
          f"(primary {'pass' if out['primary_pass'] else 'fail'}, S3 "
          f"{'pass' if out['s3_pass'] else 'fail'}, S4 "
          f"{'pass' if out['s4_pass'] else 'fail'}, manipulation "
          f"{'pass' if out['manip'].get('ok') else 'fail'})")
    print("  NOT ADOPTED here in any case: the shipped default `FRUIT_ARM_PARK` off is")
    print("  the owner's phase-3 decision; a pass licenses that decision, it does not")
    print("  flip it. A pass is a preservation result at this n, not evidence that")
    print("  training under the park improves anything over the base (PREREG section 7).")


# ----------------------------------------------------------------- self-test - #
READY_L = [-1.464, -0.375, 1.488, 1.315, -1.496, -0.588, 1.559]
BACK_L = [-1.912, -0.978, 1.503, 0.818, -1.498, -0.586, 1.559]


def _fmt(values) -> str:
    return ",".join(f"{float(v):+.3f}" for v in values)


def _ep(index: int, arm: str, ok: bool, category: str = "apple",
        diameter: float = 6.0, ticks: int = 1000, notes: str = "[]") -> str:
    return (
        f"[fruit] [rl] episode {index}: {category} d={diameter}cm bin=1 "
        f"arm={arm} success={ok} grasped={ok or index % 2 == 0} "
        f"placed={ok} ticks={ticks} decision=300 reward=0.9 notes={notes} "
        f"presentation=direct ablate=none\n"
    )


def _park(index: int, arm: str, park: str = "back", q=None,
          max_frac: float = 0.0, band_calls: int = 25, arm_px: int = 0,
          drift: float = 0.004) -> str:
    inactive = "right" if arm == "left" else "left"
    q = q or (BACK_L if inactive == "left" else READY_L)
    return (
        f"[fruit] [park] episode {index} arm={arm} inactive={inactive} park={park} "
        f"m1_hold=+0.004 m1_hold_ok=1 m1_cmd=+0.088 m2_arm={max_frac:.3f} "
        f"m2_arm_ok={int(max_frac < M2_MAX_FRAC)} m2_rel=0.897 m2_rel_ok=1 "
        f"m2_ok=1 m2_vis=1.085 band=+0.397 band_x=+0.219 band_px=184 "
        f"band_disc=158 band_vis=1.161 arm_px={arm_px} band_frac=0.000 "
        f"band_calls={band_calls} stale_skipped=1 worst_arm_at=+0.397 "
        f"worst_vis_at=+0.321 min_frac=0.000 max_frac={max_frac:.3f} "
        f"drift={drift:+.3f} calls=80 q={_fmt(q)} q_settled={_fmt(q)} top=belt\n"
    )


def _write_arm(directory: str, label: str, run: int, right_ok: int,
               right_n: int = 10, left_ok: int = 1, left_n: int = 5,
               ticks: int = 1000, species: list[str] | None = None,
               notes: str = "[]", broken_frac: bool = False) -> None:
    path = os.path.join(directory, f"{label}_{run}.log")
    species = species or ["apple"] * right_n
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(right_n):
            ok = i < right_ok
            fh.write(_ep(i, "right", ok, species[i % len(species)],
                         ticks=ticks, notes=notes if not ok else "[]"))
            fh.write(_park(i, "right", max_frac=0.5 if broken_frac and i == 0 else 0.0))
        for i in range(left_n):
            ok = i < left_ok
            fh.write(_ep(100 + i, "left", ok, ticks=ticks))
            fh.write(_park(100 + i, "left"))


def self_test() -> int:
    ok = True

    def check(name, got, want):
        nonlocal ok
        if got != want:
            print(f"self-test FAILED: {name}: got {got!r} want {want!r}")
            ok = False

    # --- the arithmetic ----------------------------------------------------- #
    check("wilson 0/30 upper", round(wilson_one_sided(0, 30, lower=False), 3), 0.083)
    # The non-inferiority p is a *tail at the null boundary*: it is small when B
    # is non-inferior (delta >> -margin) and large when B is inferior.
    check("exact p: preserved < inferior",
          exact_noninferiority_p(9, 10, 9, 10) < exact_noninferiority_p(4, 10, 9, 10),
          True)
    check("exact p: a crushed B reads ~1",
          exact_noninferiority_p(0, 10, 10, 10) > 0.99, True)
    check("exact p: a clearly better B reads small",
          exact_noninferiority_p(10, 10, 4, 10) < 0.05, True)
    check("newcombe direction (better B has the higher bound)",
          newcombe_lower(9, 10, 9, 10) > newcombe_lower(4, 10, 9, 10), True)
    check("newcombe at n=100 preserved sits inside ~the margin",
          newcombe_lower(45, 50, 45, 50) > -0.11, True)
    # ...and it is only ~the margin wide: at 50/arm the interval cannot exclude
    # -0.10 under exact equality (Newcombe -0.1045, Wald p 0.048). Reported, not
    # the gate - the pre-registered rule is the point comparison.
    check("newcombe at n=100 equality is ~the margin",
          -0.12 < newcombe_lower(45, 50, 45, 50) < -MARGIN, True)
    check("newcombe at n=100 erasure destroys the margin",
          newcombe_lower(23, 50, 45, 50) < -MARGIN, True)
    check("wald p agrees in direction",
          wald_test(45, 50, 45, 50)[1] < wald_test(23, 50, 45, 50)[1], True)

    # --- the report on a synthetic batch ------------------------------------ #
    with tempfile.TemporaryDirectory() as tmp:
        # 1: preserved + p_hat = 0.9 < 0.94 -> the ambiguous band, primary PASS.
        for run in range(1, 6):
            _write_arm(tmp, "A", run, 9)
            _write_arm(tmp, "B", run, 9)
        out = analyse(tmp, "A", "B")
        check("scenario 1 problems", out["problems"], [])
        check("scenario 1 manip", out["manip"]["ok"], True)
        check("scenario 1 n", (out["n_a"], out["n_b"]), (50, 50))
        check("scenario 1 delta", round(out["delta"], 3), 0.0)
        check("scenario 1 primary", out["primary_pass"], True)
        check("scenario 1 s3", out["s3_pass"], True)
        check("scenario 1 s4", out["s4_pass"], True)
        verdict = label_and_decision(out, {})
        check("scenario 1 label", verdict["label"].startswith(
            "PASS inside the ambiguous band"), True)
        check("scenario 1 adoption candidate", verdict["adoption"], True)

        # 2: erasure (B 4/10 vs A 9/10) -> primary FAIL, not adopted.
        with tempfile.TemporaryDirectory() as tmp2:
            for run in range(1, 6):
                _write_arm(tmp2, "A", run, 9)
                _write_arm(tmp2, "B", run, 4)
            out2 = analyse(tmp2, "A", "B")
            check("scenario 2 primary", out2["primary_pass"], False)
            verdict2 = label_and_decision(out2, {})
            check("scenario 2 label", verdict2["label"].startswith("NOT PRESERVED"), True)
            check("scenario 2 adoption", verdict2["adoption"], False)
            check("scenario 2 exact p large", out2["p_exact"] > 0.5, True)

        # 3: a broken manipulation term on ONE arm voids the read.
        with tempfile.TemporaryDirectory() as tmp3:
            for run in range(1, 6):
                _write_arm(tmp3, "A", run, 9)
                _write_arm(tmp3, "B", run, 9, broken_frac=True)
            out3 = analyse(tmp3, "A", "B")
            check("scenario 3 per-arm A", out3["manip"]["per_arm"]["A"]["ok"], True)
            check("scenario 3 per-arm B", out3["manip"]["per_arm"]["B"]["ok"], False)
            check("scenario 3 manip", out3["manip"]["ok"], False)
            check("scenario 3 label",
                  label_and_decision(out3, {})["label"].startswith("VOID"), True)
        # 4: M1-applied must catch a `ready` pose (the park not applied).
        with tempfile.TemporaryDirectory() as tmp4:
            for run in range(1, 6):
                _write_arm(tmp4, "A", run, 9)
                _write_arm(tmp4, "B", run, 9)
            for run in range(1, 6):
                path = os.path.join(tmp4, f"B_{run}.log")
                text = open(path, encoding="utf-8").read()
                text = text.replace(f"q={_fmt(BACK_L)}", f"q={_fmt(READY_L)}")
                open(path, "w", encoding="utf-8").write(text)
            out4 = analyse(tmp4, "A", "B")
            check("scenario 4 M1-applied catches ready", out4["manip"]["ok"], False)

        # 5: a new failure reason blocks the adoption candidate.
        with tempfile.TemporaryDirectory() as tmp5:
            for run in range(1, 6):
                _write_arm(tmp5, "A", run, 9)
                _write_arm(tmp5, "B", run, 9, notes="[-7.3cm lateral miss]")
            out5 = analyse(tmp5, "A", "B")
            check("scenario 5 s3", out5["s3_pass"], False)
            check("scenario 5 novelties", len(out5["novelty"]["new"]), 1)
            counts = list(out5["novelty"]["counts"].values())[0]
            check("scenario 5 novelty count right", counts["right"], 5)
            verdict5 = label_and_decision(out5, {})
            check("scenario 5 adoption", verdict5["adoption"], False)

        # 6: the standardisation straddle -> AMBIGUOUS.
        with tempfile.TemporaryDirectory() as tmp6:
            for run in range(1, 6):
                # A: 2 apple ok + 8 pear (4 ok) = 6/10; B: 8 apple ok + 2 pear 0.
                path_a = os.path.join(tmp6, f"A_{run}.log")
                path_b = os.path.join(tmp6, f"B_{run}.log")
                with open(path_a, "w", encoding="utf-8") as fh:
                    for i in range(2):
                        fh.write(_ep(i, "right", True, "apple"))
                        fh.write(_park(i, "right"))
                    for i in range(8):
                        fh.write(_ep(2 + i, "right", i < 4, "pear"))
                        fh.write(_park(2 + i, "right"))
                    for i in range(5):
                        fh.write(_ep(100 + i, "left", i < 1))
                        fh.write(_park(100 + i, "left"))
                with open(path_b, "w", encoding="utf-8") as fh:
                    for i in range(8):
                        fh.write(_ep(i, "right", True, "apple"))
                        fh.write(_park(i, "right"))
                    for i in range(2):
                        fh.write(_ep(8 + i, "right", False, "pear"))
                        fh.write(_park(8 + i, "right"))
                    for i in range(5):
                        fh.write(_ep(100 + i, "left", i < 1))
                        fh.write(_park(100 + i, "left"))
            out6 = analyse(tmp6, "A", "B")
            check("scenario 6 crude passes", out6["crude_delta"] >= -MARGIN, True)
            check("scenario 6 species fails", out6["std_delta"] < -MARGIN, True)
            check("scenario 6 straddle", out6["straddle"], True)

        # 7: near-zero behaviour change -> the no-op label (p_hat high).
        with tempfile.TemporaryDirectory() as tmp7:
            for run in range(1, 6):
                _write_arm(tmp7, "A", run, 10)
                _write_arm(tmp7, "B", run, 10)
            out7 = analyse(tmp7, "A", "B")
            fid = {"datasets/x": {"action_max": 1e-7, "paired_median": 0.0}}
            verdict7 = label_and_decision(out7, fid)
            check("scenario 7 no-op label", "no-op" in verdict7["label"], True)
            check("scenario 7 preservation candidate without a no-op",
                  "ambiguous" not in label_and_decision(
                      out7, {"datasets/x": {"action_max": 0.5}})["label"], True)

        # 8: a short batch is refused, not read (the pre-registered N = 5).
        with tempfile.TemporaryDirectory() as tmp8:
            for run in range(1, 3):
                _write_arm(tmp8, "A", run, 9)
                _write_arm(tmp8, "B", run, 9)
            out8 = analyse(tmp8, "A", "B")
            check("scenario 8 refuses 2 runs", bool(out8["problems"]), True)

    # --- the fidelity parser ------------------------------------------------ #
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "fid.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("=== fidelity on datasets/rl_rollouts/p37_park\n")
            fh.write("  paired delta (cand - base): median -0.0123 rad, "
                     "3 improved / 4 worse / 5 ties, sign p=0.5000\n")
            fh.write("  action delta (cand - base): max 3.000e-02 rad, "
                     "finger max 1.000e-03\n")
            fh.write("=== fidelity on datasets/demos_v11\n")
            fh.write("  paired delta (cand - base): median +0.0004 rad, "
                     "1 improved / 2 worse / 9 ties, sign p=0.7500\n")
        fid = parse_fidelity(path)
        check("fidelity two blocks", len(fid), 2)
        check("fidelity action max",
              round(fid["datasets/rl_rollouts/p37_park"]["action_max"], 3), 0.03)
        check("fidelity paired median",
              round(fid["datasets/rl_rollouts/p37_park"]["paired_median"], 4), -0.0123)
        check("fidelity near-zero false", near_zero(fid)[0], False)
        check("fidelity missing file", parse_fidelity(os.path.join(tmp, "none")), {})

    if not ok:
        print("p37 report self-test FAIL")
        return 1
    print("p37 report self-test PASS (parser, H2 terms, primary, straddle, S3, "
          "S4, label, fidelity)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default="logs/p37/B_ab")
    parser.add_argument("--a", default="A")
    parser.add_argument("--b", default="B")
    parser.add_argument("--fidelity", default="logs/p37/fidelity.txt")
    parser.add_argument("--run-fidelity", action="store_true",
                        help="generate the fidelity file first (needs the lingbot python)")
    parser.add_argument("--python", default=os.environ.get(
        "LINGBOT", "/home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python"))
    parser.add_argument("--base", default="checkpoints/moe_v13s/policy_best.pt")
    parser.add_argument("--candidate", default="checkpoints/p37_park/policy_best.pt")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.run_fidelity:
        code = run_fidelity(args.fidelity, args.base, args.candidate, args.python)
        if code != 0:
            print(f"  fidelity run exited {code} - continuing without it")
    fidelity = parse_fidelity(args.fidelity)
    out = analyse(args.dir, args.a, args.b)
    verdict = label_and_decision(out, fidelity)
    render(out, args.a, args.b, args.fidelity, fidelity, verdict)
    if out["problems"] or not out["manip"].get("ok"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
