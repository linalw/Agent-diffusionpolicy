"""Report the path-3b confirmation (`event` vs base, N=5 x 15) from its logs.

    python3 scripts/150_path3b_report.py logs/path3b

Reads the rate logs written by `scripts/147_path3_screen.sh` (run with
`ARMS="base event" RUNS=5 SEEDS="77 101 202 303 404"`) and prints the
pre-registered comparison of `logs/path3b/PREREGISTRATION.md`:

* per-run and pooled success, paired flips on the same (run, episode index)
  with the class-matched one-sided sign test;
* per-class table, median cycle time, normalised failure-reason signatures;
* the timing/report-on block (3 episodes per arm, `FRUIT_RTC_REPORT=1`): the
  executed-stream smoothness medians, decisions/s, `policy_ms/step`, the event
  horizon histogram, and the trigger fire-time distribution;
* the fixed criteria verdict: PASS if (C1 margin >= +5 pt AND C2 >= 4/5 runs
  non-negative AND C3 no new reason AND C4 strawberry guard) OR the alternative
  (class-matched sign test p <= 0.05 AND C3 AND C4).

The helpers (log grammar, pairing, known reasons) are shared with
`scripts/148_path3_report.py`, which path 3 used; only the criteria differ.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import statistics

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "path3_report", os.path.join(_HERE, "148_path3_report.py")
)
p3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p3)
_spec = importlib.util.spec_from_file_location(
    "rl_report", os.path.join(_HERE, "113_rl_report.py")
)
rl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rl)

#: Path-3b pre-registered criteria (`logs/path3b/PREREGISTRATION.md`).
MARGIN_PT = 5.0          # C1: pooled delta >= +5.0 pt
MIN_NONNEG_RUNS = 4      # C2: at least 4 of 5 per-run deltas >= 0
MIN_RUNS_EVALUABLE = 4   # below this the batch is inconclusive
STRAWBERRY_TOLERANCE = 1  # C4: strawberry failures(event) <= base + 1
SIGN_ALPHA = 0.05        # alternative: class-matched one-sided sign p <= 0.05


def report(directory: str) -> int:
    base_runs = p3.load_arm(directory, "base")
    event_runs = p3.load_arm(directory, "event")
    if not base_runs or not event_runs:
        print(f"need both base_*/ and event_*/ rate logs in {directory}")
        return 2
    base_all = [r for run in sorted(base_runs) for r in base_runs[run]]
    event_all = [r for run in sorted(event_runs) for r in event_runs[run]]
    ok_b = sum(1 for r in base_all if r["success"])
    ok_e = sum(1 for r in event_all if r["success"])
    rate_b = ok_b / len(base_all)
    rate_e = ok_e / len(event_all)
    delta_pt = (rate_e - rate_b) * 100

    better, worse, both_ok, both_fail, mismatched, deltas = p3.pair(
        base_runs, event_runs
    )
    p = rl.sign_test_p(better, worse)

    # Shared (run, index) episodes irrespective of class, for a dropped-run-safe
    # pooled delta (the primary number is the all-episode one when nothing is
    # dropped; both are reported).
    shared_ok_b = shared_ok_e = shared_n = 0
    run_counts = {}
    for run in sorted(set(base_runs) & set(event_runs)):
        left = {r["index"]: r for r in base_runs[run]}
        right = {r["index"]: r for r in event_runs[run]}
        sb = se = n = 0
        for index in sorted(set(left) & set(right)):
            sb += int(left[index]["success"])
            se += int(right[index]["success"])
            n += 1
        shared_ok_b += sb
        shared_ok_e += se
        shared_n += n
        run_counts[run] = (sb, se, n)
    delta_shared_pt = (
        (shared_ok_e - shared_ok_b) / shared_n * 100 if shared_n else float("nan")
    )

    print(f"=== path-3b confirmation: {directory}")
    print(f"base runs {sorted(base_runs)}: {ok_b}/{len(base_all)} ({rate_b:.1%})")
    print(f"event runs {sorted(event_runs)}: {ok_e}/{len(event_all)} ({rate_e:.1%})")
    print(f"pooled delta {delta_pt:+.1f} pt"
          + (f"; shared-episode delta {delta_shared_pt:+.1f} pt "
             f"({shared_n} episodes)" if shared_n else ""))

    print("\n--- per-run (class-matched pairs; all-episode counts in parentheses)")
    worst_run = 0
    nonneg = evaluable = 0
    all_runs = sorted(set(base_runs) & set(event_runs))
    for run in all_runs:
        b, c, n = deltas.get(run, (0, 0, 0))
        if n <= 0:
            print(f"  run {run}: no class-matched pairs (base "
                  f"{run_counts.get(run, (0, 0, 0))[2]} shared episodes)")
            continue
        evaluable += 1
        nonneg += int(c - b >= 0)
        worst_run = min(worst_run, c - b)
        sb, se, sn = run_counts.get(run, (0, 0, 0))
        print(f"  run {run}: base {b}/{n}  event {c}/{n}  delta {c - b:+d}"
              f"   (all: base {sb}/{sn}, event {se}/{sn})")
    print(f"  evaluable runs {evaluable}/{len(all_runs)}; runs with delta >= 0: "
          f"{nonneg}; worst matched-run delta {worst_run:+d}")

    print(f"\n  paired: {both_ok} both ok, {both_fail} both fail, "
          f"{better} event-only ok, {worse} base-only ok"
          + (f", {mismatched} excluded (class)" if mismatched else ""))
    print(f"  sign test (event better): p = {p:.4f} "
          f"(discordant {better + worse})")

    categories = sorted({r["category"] for r in base_all + event_all})
    print(f"  {'class':<12s} {'base':>8s} {'event':>8s}  delta")
    for category in categories:
        rb = [r for r in base_all if r["category"] == category]
        rc = [r for r in event_all if r["category"] == category]
        print(f"  {category:<12s} "
              f"{sum(1 for r in rb if r['success']):>3d}/{len(rb):<4d} "
              f"{sum(1 for r in rc if r['success']):>3d}/{len(rc):<4d} "
              f"{(p3.rate(rc) - p3.rate(rb)) * 100:+5.0f} pt")

    tb = statistics.median([r["ticks"] for r in base_all])
    te = statistics.median([r["ticks"] for r in event_all])
    print(f"  median cycle: base {tb:.0f} ticks, event {te:.0f} "
          f"({te / tb - 1:+.1%})")
    reasons_b = p3.reasons(base_all)
    reasons_e = p3.reasons(event_all)
    new_reasons = sorted(reasons_e - reasons_b - p3.KNOWN_REASONS)
    print(f"  failure reasons base: {sorted(reasons_b) or 'none'}")
    print(f"  failure reasons event: {sorted(reasons_e) or 'none'}")
    if new_reasons:
        print(f"  NEW reasons: {new_reasons}")
    for reason in sorted(reasons_e):
        count = sum(
            1 for r in event_all
            if not r["success"] and reason in
            {re.sub(r"[-+0-9.]+", "#", str(i)).strip()
             for i in _note_items(r["notes"])}
        )
        if count:
            print(f"    event note x{count}: {reason}")

    straw_b = [r for r in base_all if r["category"] == "strawberry"]
    straw_e = [r for r in event_all if r["category"] == "strawberry"]
    straw_fail_b = len(straw_b) - sum(1 for r in straw_b if r["success"])
    straw_fail_e = len(straw_e) - sum(1 for r in straw_e if r["success"])

    c1 = delta_pt >= MARGIN_PT
    c2 = evaluable >= MIN_RUNS_EVALUABLE and nonneg >= MIN_NONNEG_RUNS
    c3 = not new_reasons
    c4 = straw_fail_e <= straw_fail_b + STRAWBERRY_TOLERANCE
    alt = p <= SIGN_ALPHA
    primary = c1 and c2 and c3 and c4
    alternative = alt and c3 and c4
    verdict = "PASS" if (primary or alternative) else "FAIL"
    if evaluable < MIN_RUNS_EVALUABLE:
        verdict = "INCONCLUSIVE"

    print("\n=== pre-registered criteria (logs/path3b/PREREGISTRATION.md)")
    print(f"  C1 pooled delta >= +{MARGIN_PT:.1f} pt: {delta_pt:+.1f} -> "
          f"{'ok' if c1 else 'FAIL'}")
    print(f"  C2 runs non-negative >= {MIN_NONNEG_RUNS}/{len(all_runs)}: "
          f"{nonneg}/{evaluable} evaluable -> {'ok' if c2 else 'FAIL'}")
    print(f"  C3 no new failure reason: {'ok' if c3 else 'FAIL'}")
    print(f"  C4 strawberry failures event <= base + {STRAWBERRY_TOLERANCE}: "
          f"{straw_fail_e} vs {straw_fail_b} -> {'ok' if c4 else 'FAIL'}")
    print(f"  ALT class-matched one-sided sign p <= {SIGN_ALPHA}: {p:.4f} -> "
          f"{'ok' if alt else 'FAIL'}")
    print(f"  primary {primary}; alternative {alternative}")
    print(f"  VERDICT: {verdict}")
    if verdict == "PASS":
        print("  decision: event becomes the documented deployment "
              "configuration (logs/path3b/DEPLOY.md); canary + GUI demo next")
    elif verdict == "FAIL":
        print("  decision: the base (moe_v11 + trigger, event off) stands; "
              "negative reported, margin not moved")
    else:
        print("  decision: inconclusive batch; the base stands")

    _report_timing(directory, base_runs, event_runs, base_all, event_all)
    return 0 if verdict == "PASS" else 1


def _note_items(text: str):
    import ast

    text = text.strip()
    try:
        items = ast.literal_eval(text)
        if isinstance(items, str):
            items = [items]
    except (ValueError, SyntaxError):
        items = [text]
    return items


def _report_timing(directory, base_runs, event_runs, base_all, event_all) -> None:
    print("\n=== timing/report block (3 episodes/arm, FRUIT_RTC_REPORT=1; "
          "not in the rate table)")
    print(f"  {'arm':<8s} {'dec/s':>7s} {'policy_ms/step':>15s} "
          f"{'step':>7s} {'jerk':>7s} {'bound':>7s} {'within':>7s}")
    for arm in ("base", "event"):
        log = os.path.join(directory, f"timing_{arm}.log")
        if not os.path.exists(log):
            continue
        text = open(log, encoding="utf-8", errors="ignore").read()
        summary = None
        for match in p3.RTC_SUMMARY.finditer(text):
            summary = match
        meds = {name: float(med) for name, _, med, _, _ in p3.MED.findall(text)}
        policy_ms = [float(v) for v in p3.POLICY_STEP.findall(text)]
        chunks = h2 = h4 = h6 = 0
        cont = []
        for match in p3.EVENT_SUMMARY.finditer(text):
            chunks += int(match.group(1))
            h2 += int(match.group(2))
            h4 += int(match.group(3))
            h6 += int(match.group(4))
            cont.append(float(match.group(6)))
        dec = float(summary.group(4)) if summary else float("nan")
        pms = policy_ms[-1] if policy_ms else float("nan")
        print(f"  {arm:<8s} {dec:7.1f} {pms:15.2f} "
              f"{meds.get('step', float('nan')):7.4f} "
              f"{meds.get('jerk', float('nan')):7.4f} "
              f"{meds.get('boundary', float('nan')):7.4f} "
              f"{meds.get('within', float('nan')):7.4f}")
        if chunks:
            print(f"    [event] chunks={chunks} h2={h2} h4={h4} h6={h6} "
                  f"mean={(2 * h2 + 4 * h4 + 6 * h6) / max(chunks, 1):.2f} "
                  f"continuity_med={max(cont) if cont else float('nan'):.5f}")

    print("\n=== trigger fire-time distribution (episodes whose notes carry it)")
    print(f"  {'arm':<8s} {'fired':>7s} {'dy med':>8s} {'|dx| med':>9s} "
          f"{'t_arr med':>10s} {'finger med':>11s}")
    for arm, runs in (("base", base_runs), ("event", event_runs)):
        rows = [r for run in sorted(runs) for r in runs[run]]
        vals = []
        for r in rows:
            match = p3.TRIGGER.search(r["notes"])
            if match:
                vals.append((float(match.group(1)), abs(float(match.group(2))),
                             float(match.group(3)), float(match.group(4))))
        if not vals:
            continue
        columns = list(zip(*vals))
        print(f"  {arm:<8s} {len(vals):>3d}/{len(rows):<3d} "
              f"{statistics.median(columns[0]):8.2f} "
              f"{statistics.median(columns[1]):9.2f} "
              f"{statistics.median(columns[2]):10.3f} "
              f"{statistics.median(columns[3]):11.4f}")


def self_test() -> int:
    import contextlib
    import io
    import tempfile

    def line(index, category, ok, ticks=3000, notes="[]"):
        return (
            f"[fruit] [rl] episode {index}: {category} d=3.1cm bin=1 arm=right "
            f"success={ok} grasped=True placed={str(ok)} ticks={ticks} "
            f"decision=400 reward=0.9 notes={notes} presentation=direct ablate=none"
        )

    with tempfile.TemporaryDirectory() as tmp:
        # event wins by 5/15 in every run -> primary PASS (+5 pt is reached
        # with 9 vs 4 = +11.1 pt; use 5/15 vs 4/15 = +2 pt -> FAIL to check C1).
        for run in range(1, 6):
            with open(os.path.join(tmp, f"base_{run}.log"), "w") as fh:
                for i in range(15):
                    fh.write(line(i, "lychee", i >= 9) + "\n")
            with open(os.path.join(tmp, f"event_{run}.log"), "w") as fh:
                for i in range(15):
                    fh.write(line(i, "lychee", i >= 9 or i < 1) + "\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = report(tmp)
        text = out.getvalue()
        if code != 0 or "VERDICT: PASS" not in text:
            print("path-3b report self-test FAIL (pass case)")
            print(text)
            return 1
        # event one episode better in only one run -> C1/C2 fail, p = 1.0.
        for run in range(1, 6):
            with open(os.path.join(tmp, f"event_{run}.log"), "w") as fh:
                for i in range(15):
                    fh.write(line(i, "lychee", i >= 9 or (run == 1 and i == 8))
                             + "\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = report(tmp)
        text = out.getvalue()
        if code != 1 or "VERDICT: FAIL" not in text:
            print("path-3b report self-test FAIL (fail case)")
            print(text)
            return 1
    print("path3b report self-test PASS (pooled margin, run consistency, "
          "sign-test alternative)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", default="logs/path3b")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    return report(args.directory)


if __name__ == "__main__":
    raise SystemExit(main())
