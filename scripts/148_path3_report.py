"""Report the path-3 frontier screen from `scripts/147_path3_screen.sh` logs.

    python3 scripts/148_path3_report.py logs/path3

Parses the `[rl] episode ...` lines (same grammar as `113_rl_report.py`, which
is imported) per arm, then prints the pre-registered comparison of every
candidate against the base: per-run table, pooled rate, paired flips on the
same (run, episode index) with the sign test, per-class table, median cycle
time, failure reasons, and the criterion evaluation of
`logs/path3/PREREGISTRATION.md` (pooled >= base + 8 pt; no run below by >2/15;
no new failure reason; strawberry not regressed by more than 1/6). It also
summarises the timing/report-on block (one 3-episode report-on log per arm) with
the executed-stream medians, decision rate and, for the event arm, the horizon
histogram.
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import math
import os
import re
import statistics

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "rl_report", os.path.join(_HERE, "113_rl_report.py")
)
rl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rl)

MARGIN = 0.08
RUN_TOLERANCE = 2  # episodes per 15
STRAWBERRY_TOLERANCE = 1  # episode difference relative to 1/6 of the class

RTC_SUMMARY = re.compile(
    r"\[rtc\] summary: steps=(\d+) chunks=(\d+) decisions=(\d+) "
    r"decisions/s=([\d.]+) switches=(\d+)"
)
MED = re.compile(r"(\w+) rad n=(\d+) med=([\d.]+) p90=([\d.]+) max=([\d.]+)")
POLICY_STEP = re.compile(r"policy_ms/step ([\d.]+)")
EVENT_SUMMARY = re.compile(
    r"\[event\] chunks=(\d+) h2=(\d+) h4=(\d+) h6=(\d+) mean=([\d.]+) "
    r"continuity_med=([\d.]+)"
)
TRIGGER = re.compile(
    r"intercept trigger \(dy=([-+0-9.]+)cm, dx=([-+0-9.]+)cm, "
    r"t_arrive=([0-9.]+)s.*finger=([0-9.]+)\)"
)


def load_arm(directory: str, arm: str) -> dict[int, list[dict]]:
    runs: dict[int, list[dict]] = {}
    for path in sorted(glob.glob(os.path.join(directory, f"{arm}_*.log"))):
        stem = os.path.basename(path)[:-4]
        suffix = stem[len(arm) + 1 :]
        if not suffix.isdigit():
            continue
        rows = rl.parse(path)
        if rows:
            runs[int(suffix)] = rows
    return runs


def rate(rows: list[dict]) -> float:
    return (sum(1 for r in rows if r["success"]) / len(rows)) if rows else 0.0


def pair(base: dict[int, list[dict]], cand: dict[int, list[dict]]):
    better = worse = both_ok = both_fail = mismatched = 0
    deltas = {}
    for run in sorted(set(base) & set(cand)):
        left = {r["index"]: r for r in base[run]}
        right = {r["index"]: r for r in cand[run]}
        ok_b = ok_c = matched = 0
        for index in sorted(set(left) & set(right)):
            a, b = left[index], right[index]
            if a["category"] != b["category"]:
                mismatched += 1
                continue
            matched += 1
            ok_b += int(a["success"])
            ok_c += int(b["success"])
            if a["success"] and b["success"]:
                both_ok += 1
            elif a["success"] and not b["success"]:
                worse += 1
            elif not a["success"] and b["success"]:
                better += 1
            else:
                both_fail += 1
        deltas[run] = (ok_b, ok_c, matched)
    return better, worse, both_ok, both_fail, mismatched, deltas


def reasons(rows: list[dict]) -> set[str]:
    """Per-note failure signatures (numbers normalised), not whole note lists.

    A failure's `notes` is a Python list literal; comparing whole lists makes
    every extra note look like a new reason. Each note is normalised
    individually (`[-+0-9.]+` -> `#`), and the check below additionally treats
    the failure classes already on record in the repo as known.
    """
    import ast

    out: set[str] = set()
    for r in rows:
        if r["success"]:
            continue
        text = r["notes"].strip()
        try:
            items = ast.literal_eval(text)
            if isinstance(items, str):
                items = [items]
        except (ValueError, SyntaxError):
            items = [text]
        for item in items:
            signature = re.sub(r"[-+0-9.]+", "#", str(item)).strip()
            out.add("empty note" if not signature else signature)
    return out


#: Failure classes already on record in this repo (AGENTS section 2 and the
#: WORKLOG): the base arm's own reasons plus these are not "new" for C3.
KNOWN_REASONS = {
    "intercept trigger (dy=#cm, dx=#cm, t_arrive=#s, speed=#m/s/encoder, frame=station, finger=#)",
    "policy closed on the fruit (finger=#, |jaw#fruit|xy=#cm)",
    "expert closed on the fruit (finger=#, |jaw#fruit|xy=#cm)",
    "fruit did not follow the gripper",
    "fruit left the pick station during the close (# mm)",
    "cross#lane station fruit (index #) placed on lane #",
    "timeout: no grasp within # ticks",
    "non#finite policy action",
    "left station",
}


def report(directory: str, base_label: str = "base") -> int:
    arms = ["base", "track", "event", "vlash", "a2c2", "combo"]
    data = {arm: load_arm(directory, arm) for arm in arms}
    if not data.get(base_label):
        print(f"no {base_label}_*/ logs in {directory}")
        return 2
    base_runs = sorted(data[base_label])
    base_all = [r for run in base_runs for r in data[base_label][run]]
    base_rate = rate(base_all)
    print(f"=== path-3 screen: {directory}")
    print(f"base runs {base_runs}: "
          f"{sum(1 for r in base_all if r['success'])}/{len(base_all)} "
          f"({base_rate:.0%})")

    verdicts = {}
    for arm in arms:
        if arm == base_label:
            continue
        runs = sorted(data.get(arm, {}))
        if not runs:
            print(f"\n--- {arm}: no rate runs found")
            verdicts[arm] = "missing"
            continue
        rows = [r for run in runs for r in data[arm][run]]
        cand_rate = rate(rows)
        better, worse, both_ok, both_fail, mismatched, deltas = pair(
            data[base_label], data[arm]
        )
        p = rl.sign_test_p(better, worse)
        delta_pt = (cand_rate - base_rate) * 100
        shared = sorted(deltas)
        worst_run = min((c - b for b, c, _ in deltas.values()), default=0)
        new_reasons = sorted(reasons(rows) - reasons(base_all) - KNOWN_REASONS)
        straw_b = [r for r in base_all if r["category"] == "strawberry"]
        straw_c = [r for r in rows if r["category"] == "strawberry"]
        straw_delta = (
            (rate(straw_c) - rate(straw_b)) if straw_b and straw_c else 0.0
        )
        c1 = delta_pt >= MARGIN * 100
        c2 = worst_run >= -RUN_TOLERANCE
        c3 = not new_reasons
        # strawberry: no more than `tolerance` episodes worse in the pooled table
        c4 = len(straw_c) - sum(1 for r in straw_c if r["success"]) <= (
            len(straw_b) - sum(1 for r in straw_b if r["success"]) + STRAWBERRY_TOLERANCE
        )
        passed = c1 and c2 and c3 and c4
        verdicts[arm] = "PASS" if passed else "DROP"

        print(f"\n--- {arm}: pooled {sum(1 for r in rows if r['success'])}/{len(rows)} "
              f"({cand_rate:.0%})  delta {delta_pt:+.1f} pt")
        for run in shared:
            b, c, n = deltas[run]
            print(f"  run {run}: base {b}/{n}  {arm} {c}/{n}  delta {c - b:+d}")
        print(f"  paired: {both_ok} both ok, {both_fail} both fail, "
              f"{better} {arm}-only ok, {worse} base-only ok"
              + (f", {mismatched} excluded (class)" if mismatched else ""))
        print(f"  sign test ({arm} better): p = {p:.4f} (discordant {better + worse})")
        categories = sorted({r["category"] for r in base_all + rows})
        print(f"  {'class':<12s} {'base':>8s} {arm:>8s}  delta")
        for category in categories:
            rb = [r for r in base_all if r["category"] == category]
            rc = [r for r in rows if r["category"] == category]
            print(f"  {category:<12s} "
                  f"{sum(1 for r in rb if r['success']):>3d}/{len(rb):<4d} "
                  f"{sum(1 for r in rc if r['success']):>3d}/{len(rc):<4d} "
                  f"{(rate(rc) - rate(rb)) * 100:+5.0f} pt")
        tb = statistics.median([r["ticks"] for r in base_all])
        tc = statistics.median([r["ticks"] for r in rows])
        print(f"  median cycle: base {tb:.0f} ticks, {arm} {tc:.0f} ({tc / tb - 1:+.1%})")
        print(f"  failure reasons base: {sorted(reasons(base_all)) or 'none'}")
        print(f"  failure reasons {arm}: {sorted(reasons(rows)) or 'none'}")
        if new_reasons:
            print(f"  NEW reasons: {new_reasons}")
        print(f"  criteria: C1 pooled >= +8 pt: {delta_pt:+.1f} -> {'ok' if c1 else 'FAIL'}; "
              f"C2 worst run >= -2: {worst_run:+d} -> {'ok' if c2 else 'FAIL'}; "
              f"C3 no new reason: {'ok' if c3 else 'FAIL'}; "
              f"C4 strawberry delta {straw_delta:+.0%} -> {'ok' if c4 else 'FAIL'}")
        print(f"  VERDICT: {verdicts[arm]}")

    print("\n=== timing/report block (3 episodes, report on; not in the rate table)")
    print(f"  {'arm':<8s} {'dec/s':>7s} {'policy_ms/step':>15s} "
          f"{'step':>7s} {'jerk':>7s} {'bound':>7s} {'within':>7s}")
    timing = {}
    for arm in arms:
        log = os.path.join(directory, f"timing_{arm}.log")
        if not os.path.exists(log):
            continue
        text = open(log, encoding="utf-8", errors="ignore").read()
        summary = None
        for match in RTC_SUMMARY.finditer(text):
            summary = match  # last one (the run-level summary)
        meds = {name: float(med) for name, _, med, _, _ in MED.findall(text)}
        policy_ms = [float(v) for v in POLICY_STEP.findall(text)]
        chunks = h2 = h4 = h6 = 0
        cont = []
        for match in EVENT_SUMMARY.finditer(text):
            chunks += int(match.group(1))
            h2 += int(match.group(2))
            h4 += int(match.group(3))
            h6 += int(match.group(4))
            cont.append(float(match.group(6)))
        timing[arm] = {
            "dec": float(summary.group(4)) if summary else float("nan"),
            "policy": policy_ms[-1] if policy_ms else float("nan"),
            "step": meds.get("step", float("nan")),
            "jerk": meds.get("jerk", float("nan")),
            "bound": meds.get("boundary", float("nan")),
            "within": meds.get("within", float("nan")),
        }
        row = timing[arm]
        print(f"  {arm:<8s} {row['dec']:7.1f} {row['policy']:15.2f} "
              f"{row['step']:7.4f} {row['jerk']:7.4f} {row['bound']:7.4f} "
              f"{row['within']:7.4f}")
        if chunks:
            print(f"    [event] chunks={chunks} h2={h2} h4={h4} h6={h6} "
                  f"mean={(2 * h2 + 4 * h4 + 6 * h6) / max(chunks, 1):.2f} "
                  f"continuity_med={max(cont) if cont else float('nan'):.5f}")

    print("\n=== trigger fire-time distribution (episodes whose notes carry the trigger)")
    print(f"  {'arm':<8s} {'fired':>7s} {'dy med':>8s} {'|dx| med':>9s} "
          f"{'t_arr med':>10s} {'finger med':>11s}")
    for arm in arms:
        runs_arm = data.get(arm, {})
        if not runs_arm:
            continue
        rows = [r for run in runs_arm for r in runs_arm[run]]
        vals = []
        for r in rows:
            match = TRIGGER.search(r["notes"])
            if match:
                vals.append(
                    (
                        float(match.group(1)),
                        abs(float(match.group(2))),
                        float(match.group(3)),
                        float(match.group(4)),
                    )
                )
        if not vals:
            continue
        columns = list(zip(*vals))
        print(
            f"  {arm:<8s} {len(vals):>3d}/{len(rows):<3d} "
            f"{statistics.median(columns[0]):8.2f} "
            f"{statistics.median(columns[1]):9.2f} "
            f"{statistics.median(columns[2]):10.3f} "
            f"{statistics.median(columns[3]):11.4f}"
        )

    print("\n=== pre-registered decision rule")
    passing = [arm for arm, v in verdicts.items() if v == "PASS"]
    if passing:
        best = max(passing, key=lambda arm: rate(
            [r for run in data[arm] for r in data[arm][run]]
        ))
        print(f"  passing arms: {passing}; best single: {best}")
        print(f"  next: N=5 x 15 for {best}"
              + (" (combination = base + " + "+".join(passing) + ")"
                 if len(passing) > 1 else ""))
    else:
        print("  no arm passed: the base (moe_v11 + trigger) stands; all four "
              "frontier components are measured non-wins in this batch")
    return 0


def self_test() -> int:
    import contextlib
    import io
    import tempfile

    def line(index, category, diameter, ok, ticks, notes="[]"):
        return (
            f"[fruit] [rl] episode {index}: {category} d={diameter}cm bin=1 arm=right "
            f"success={ok} grasped=True placed={str(ok)} ticks={ticks} "
            f"decision=400 reward=0.9 notes={notes} presentation=direct ablate=none"
        )

    with tempfile.TemporaryDirectory() as tmp:
        for run in (1, 2, 3):
            with open(os.path.join(tmp, f"base_{run}.log"), "w") as fh:
                for i in range(15):
                    fh.write(line(i, "lychee", "3.1", i >= 9, 700 + i) + "\n")
            with open(os.path.join(tmp, f"track_{run}.log"), "w") as fh:
                for i in range(15):
                    fh.write(line(i, "lychee", "3.1", i >= 7, 690 + i) + "\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = report(tmp)
        text = out.getvalue()
        if code != 0 or "VERDICT: PASS" not in text or "track" not in text:
            print("path3 report self-test FAIL")
            print(text)
            return 1
    print("path3 report self-test PASS (pairing, criteria, verdicts)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", default="logs/path3")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    return report(args.directory)


if __name__ == "__main__":
    raise SystemExit(main())
