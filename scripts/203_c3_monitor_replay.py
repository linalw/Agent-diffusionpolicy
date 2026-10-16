#!/usr/bin/env python3
"""P7-1 L1: the C-3 carry monitor Phase-0 offline replay (pre-registered).

Reads the four W8-B trace corpora named in `logs/w8/B_RESULTS.md`, re-derives
the carry legs and their `clean_slip` classes with `logs/w8/B_metric.py`,
fits the pre-registered tiny logistic monitor on ONLINE-ONLY grip features
(finger separation, the two tactile forces, jaw velocity, contact count -
never the privileged payload pose), and reports Sentinel's critical-state F1
protocol (Normal excluded) plus the FP count on the fixed 33 clean legs.

Protocol frozen in `logs/p7/PREREG_CARRY_MONITOR.md`; nothing here may tune it:

  features  sep, sep-gap_cmd, dsep/dt, min(ft), sum(ft), contacts
  labels    per tick: clean_slip(t) > 2.0 mm (offline only, never a feature)
  model     logistic regression, per-fold standardization, zero init,
            full-batch GD lr=0.5, 3000 steps, L2 lambda=1e-3
  CV        leave-one-trace-out, threshold 0.5, persistence >= 2 ticks
  gate      macro-F1 >= 0.86  AND  FP <= 2 of 33 clean legs

Read-only: prints a report to stdout; writes nothing.

Usage:
    python3 scripts/203_c3_monitor_replay.py
    python3 scripts/203_c3_monitor_replay.py --skip-ablations
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import os

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPORA = [
    "logs/w7/B_traces_mech",
    "logs/w5/traces_dense",
    "logs/w8/B_traces_mech",
    "logs/w8/B_traces_mech_run1",
]
EXPECTED = {"held": 33, "escape": 31, "no-contact": 25, "jitter": 0}

FEATURES = ["sep", "pry", "vsep", "ft_min", "force", "contacts"]
TRIGGER = 0.002
PERSIST = 2
LAM = 1e-3
LR = 0.5
STEPS = 3000
GATE_F1 = 0.86
FP_CAP = 2
DT_NOM = 1.0 / 120.0


def load_b_metric():
    path = os.path.join(REPO, "logs", "w8", "B_metric.py")
    spec = importlib.util.spec_from_file_location("b_metric_p7", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def leg_ticks(bm, seg):
    """Per-tick (slip, six online features) for one carry leg.

    `slip` re-derives the W8-B metric with the same helpers (label side only);
    the six features read only row fields the live loop already has.
    """
    rot0 = bm.quat_matrix(seg[0]["quat"])
    ref = bm.rot_t_vec(rot0, bm.sub(seg[0]["fruit"], seg[0]["jaw"]))
    out = []
    prev_sep = None
    prev_t = None
    for i, r in enumerate(seg):
        rel = bm.rot_t_vec(bm.quat_matrix(r["quat"]), bm.sub(r["fruit"], r["jaw"]))
        slip = bm.norm(bm.sub(rel, ref))
        sep = float(r["sep"])
        gap = float(r.get("gap_cmd", 0.0))
        t = float(r.get("t", 0.0))
        if prev_sep is None or t <= prev_t:
            vsep = 0.0
        else:
            vsep = (sep - prev_sep) / (t - prev_t)
        ft = sorted(float(v) for v in (r.get("ft") or {}).values())
        ft_min = ft[0] if ft else 0.0
        out.append(
            (
                slip,
                (
                    sep,
                    sep - gap,
                    vsep,
                    ft_min,
                    float(r.get("force", 0.0)),
                    float(r.get("contacts", 0)),
                ),
            )
        )
        prev_sep = sep
        prev_t = t
    return out


def load_corpus(bm):
    """[(trace_id, [(classes, ticks), ...]), ...] plus per-leg records."""
    traces = []
    records = []
    for rel_dir in CORPORA:
        paths = sorted(glob.glob(os.path.join(REPO, rel_dir, "*.json")))
        paths = [p for p in paths if not p.endswith("_summary.json")]
        for path in paths:
            arm, outcome, rows = bm.load_rows(path)
            trace_id = os.path.join(rel_dir, os.path.basename(path))
            legs = []
            for seg in bm.legs(rows):
                if len(seg) < 2:
                    continue
                rec = bm.analyze_leg(seg, TRIGGER)
                ticks = leg_ticks(bm, seg)
                legs.append(
                    {
                        "class": rec["class"],
                        "ticks": ticks,
                        "trace": trace_id,
                        "corpus": rel_dir,
                        "arm": arm,
                        "outcome": outcome,
                        "n": len(seg),
                        "onset": rec["onset_row"],
                        "loss": rec["loss_row"],
                        "slip_max": rec["slip_max"],
                        "contacts_min": rec["contacts_min"],
                    }
                )
                records.append(legs[-1])
            if legs:
                traces.append((trace_id, legs))
    return traces, records


def fit_logreg(x, y):
    """Full-batch GD logistic regression; standardized features in, weights out."""
    mu = x.mean(axis=0)
    sd = x.std(axis=0)
    sd[sd < 1e-6] = 1e-6
    xs = (x - mu) / sd
    n, d = xs.shape
    w = np.zeros(d)
    b = 0.0
    for _ in range(STEPS):
        z = xs @ w + b
        p = 1.0 / (1.0 + np.exp(-z))
        g = p - y
        w -= LR * (xs.T @ g / n + LAM * w)
        b -= LR * float(g.mean())
    z = xs @ w + b
    p = 1.0 / (1.0 + np.exp(-z))
    eps = 1e-12
    loss = float(
        -np.mean(y * np.log(p + eps) + (1.0 - y) * np.log(1.0 - p + eps))
        + 0.5 * LAM * float(w @ w)
    )
    grad = float(np.max(np.abs(xs.T @ (p - y) / n + LAM * w)))
    return w, b, mu, sd, loss, grad


def predict_leg(w, b, mu, sd, ticks, feature_idx):
    """Leg decision: >= PERSIST consecutive ticks with z >= 0."""
    xs = (np.asarray([[t[1][i] for i in feature_idx] for t in ticks],
                     dtype=float) - mu) / sd
    z = xs @ w + b
    hot = z >= 0.0
    fire = None
    run = 0
    for i, h in enumerate(hot):
        run = run + 1 if h else 0
        if run >= PERSIST:
            fire = i - PERSIST + 1
            break
    return (fire is not None), fire, hot


def run_cv(traces, feature_idx=None, verbose=False):
    """Leave-one-trace-out CV; returns per-leg predictions and fold diagnostics."""
    idx = list(range(len(FEATURES))) if feature_idx is None else feature_idx
    preds = {}
    losses = []
    grads = []
    coeffs = []
    for held_id, held_legs in traces:
        train_x = []
        train_y = []
        for trace_id, legs in traces:
            if trace_id == held_id:
                continue
            for leg in legs:
                for slip, feat in leg["ticks"]:
                    train_x.append([feat[i] for i in idx])
                    train_y.append(1.0 if slip > TRIGGER else 0.0)
        x = np.asarray(train_x, dtype=float)
        y = np.asarray(train_y, dtype=float)
        w, b, mu, sd, loss, grad = fit_logreg(x, y)
        losses.append(loss)
        grads.append(grad)
        coeffs.append([w[j] for j in range(len(idx))])
        for leg in held_legs:
            pred, fire, hot = predict_leg(w, b, mu, sd, leg["ticks"], idx)
            preds[(held_id, id(leg))] = (pred, fire, hot)
        if verbose:
            print(f"  fold {held_id}: n_train={len(y)} loss={loss:.5f} "
                  f"grad={grad:.2e}")
    for trace_id, legs in traces:
        for leg in legs:
            leg["_pred"] = preds[(trace_id, id(leg))]
    return {
        "loss": float(np.mean(losses)),
        "grad": float(np.max(grads)),
        "coeffs": np.asarray(coeffs),
    }


def score(records):
    tp = fp = fn = tn = 0
    for leg in records:
        if leg["class"] not in ("held", "escape"):
            continue
        pred = leg["_pred"][0]
        if leg["class"] == "escape":
            tp += int(pred)
            fn += int(not pred)
        else:
            fp += int(pred)
            tn += int(not pred)
    prec_e = tp / (tp + fp) if tp + fp else 0.0
    rec_e = tp / (tp + fn) if tp + fn else 0.0
    prec_c = tn / (tn + fn) if tn + fn else 0.0
    rec_c = tn / (tn + fp) if tn + fp else 0.0
    f1_e = 2 * prec_e * rec_e / (prec_e + rec_e) if prec_e + rec_e else 0.0
    f1_c = 2 * prec_c * rec_c / (prec_c + rec_c) if prec_c + rec_c else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "prec_e": prec_e, "rec_e": rec_e, "f1_e": f1_e,
        "prec_c": prec_c, "rec_c": rec_c, "f1_c": f1_c,
        "macro": 0.5 * (f1_e + f1_c),
    }


def fmt_leg(leg):
    return (
        f"{leg['trace']:44s} {leg['arm']:5s} {leg['outcome']:4s} "
        f"n={leg['n']:3d} {leg['class']:10s} slip_max={leg['slip_max']*1000:8.2f}mm "
        f"cmin={leg['contacts_min']}"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-ablations", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    bm = load_b_metric()
    traces, records = load_corpus(bm)

    counts = {}
    for leg in records:
        counts[leg["class"]] = counts.get(leg["class"], 0) + 1
    print("== P7-1 L1 C-3 monitor replay: corpus ==")
    for corpus in CORPORA:
        sub = [l for l in records if l["corpus"] == corpus]
        cc = {}
        for leg in sub:
            cc[leg["class"]] = cc.get(leg["class"], 0) + 1
        print(f"  {corpus:28s} traces={len(set(l['trace'] for l in sub)):2d} "
              f"legs={len(sub):2d} " +
              " ".join(f"{k}={v}" for k, v in sorted(cc.items())))
    print(f"  total legs={len(records)} counts=" +
          " ".join(f"{k}={v}" for k, v in sorted(counts.items())) +
          "  (expected " + " ".join(f"{k}={v}" for k, v in sorted(EXPECTED.items())) + ")")
    ok = all(counts.get(k, 0) == v for k, v in EXPECTED.items()) and \
        sum(counts.values()) == sum(EXPECTED.values())
    if not ok:
        print("STOP: corpus invariant violated; the pre-registration is void "
              "(replay NO-GO by protocol).")
        return 2

    print("\n== leave-one-trace-out CV (frozen hyperparameters) ==")
    diag = run_cv(traces, verbose=args.verbose)
    s = score(records)
    print(f"  folds={len(traces)}  mean train loss={diag['loss']:.5f}  "
          f"max|grad|={diag['grad']:.2e}")
    print(f"  critical legs: clean={s['tn']+s['fp']} escape={s['tp']+s['fn']}")
    print(f"  TP={s['tp']} FP={s['fp']} FN={s['fn']} TN={s['tn']}")
    print(f"  escape:  P={s['prec_e']:.3f} R={s['rec_e']:.3f} F1={s['f1_e']:.3f}")
    print(f"  clean:   P={s['prec_c']:.3f} R={s['rec_c']:.3f} F1={s['f1_c']:.3f}")
    print(f"  macro-F1={s['macro']:.3f}  (gate >= {GATE_F1})")
    print(f"  FP on clean legs={s['fp']} of 33  (cap <= {FP_CAP})")
    gate = s["macro"] >= GATE_F1 and s["fp"] <= FP_CAP
    print(f"  GATE: {'PASS' if gate else 'FAIL'}")

    print("\n== per-corpus breakdown (out-of-fold) ==")
    for corpus in CORPORA:
        sub = [l for l in records if l["corpus"] == corpus and
               l["class"] in ("held", "escape")]
        ss = score(sub)
        print(f"  {corpus:28s} clean={ss['tn']+ss['fp']:2d} escape={ss['tp']+ss['fn']:2d} "
              f"TP={ss['tp']:2d} FP={ss['fp']:2d} FN={ss['fn']:2d} "
              f"F1e={ss['f1_e']:.3f} F1c={ss['f1_c']:.3f} macro={ss['macro']:.3f}")

    print("\n== detection latency (escape legs; ticks relative to the leg) ==")
    print(f"  {'trace':44s} {'class':10s} n   onset loss fire  fire-onset fire-loss remain")
    esc = [l for l in records if l["class"] == "escape"]
    for leg in sorted(esc, key=lambda l: (not l["_pred"][0], l["trace"])):
        pred, fire, hot = leg["_pred"]
        fire_s = "-" if fire is None else str(fire)
        d_onset = "-" if fire is None or leg["onset"] is None else f"{fire - leg['onset']:+d}"
        loss = leg["loss"]
        d_loss = "-"
        if fire is not None and loss is not None:
            d_loss = f"{fire - loss:+d}"
        remain = "-" if fire is None else str(leg["n"] - 1 - fire)
        state = "ESCAPE-FIRE" if pred else "MISS      "
        onset_s = "-" if leg["onset"] is None else str(leg["onset"])
        loss_s = "-" if loss is None else str(loss)
        print(f"  {leg['trace']:44s} {state} n={leg['n']:3d} o={onset_s:>3s} "
              f"l={loss_s:>3s} f={fire_s:>3s} dOnset={d_onset:>4s} "
              f"dLoss={d_loss:>4s} remain={remain:>4s}")
    det = [l for l in esc if l["_pred"][0]]
    before = after = across = 0
    for leg in det:
        if leg["loss"] is None:
            continue
        if leg["_pred"][1] < leg["loss"]:
            before += 1
        elif leg["_pred"][1] > leg["loss"]:
            after += 1
        else:
            across += 1
    print(f"  detected {len(det)}/{len(esc)} escapes; of the detected with a "
          f"contact-loss row: fired before loss={before}, at loss={across}, "
          f"after loss={after}")
    d_onset = [l["_pred"][1] - l["onset"] for l in det if l["_pred"][1] is not None
               and l["onset"] is not None]
    d_loss = [l["_pred"][1] - l["loss"] for l in det if l["_pred"][1] is not None
              and l["loss"] is not None]
    remain = [l["n"] - 1 - l["_pred"][1] for l in det if l["_pred"][1] is not None]
    if d_onset:
        print(f"  fire-onset: min={min(d_onset):+d} med={int(np.median(d_onset)):+d} "
              f"max={max(d_onset):+d} ticks (negative = fired before the 2 mm crossing)")
    if d_loss:
        print(f"  fire-loss:  min={min(d_loss):+d} med={int(np.median(d_loss)):+d} "
              f"max={max(d_loss):+d} ticks (negative = fired before contact loss)")
    if remain:
        print(f"  leg ticks left after fire: min={min(remain)} med={int(np.median(remain))} "
              f"max={max(remain)}")

    print("\n== per-attempt aggregation (an attempt = one trace; skip iff any leg fires) ==")
    by_trace = {}
    for leg in records:
        by_trace.setdefault(leg["trace"], []).append(leg)
    atp = afp = afn = atn = 0
    for trace_id, legs in by_trace.items():
        cls = [l["class"] for l in legs]
        if all(c == "no-contact" for c in cls):
            continue
        attempt_escape = any(c == "escape" for c in cls)
        fired = any(l["_pred"][0] for l in legs)
        if attempt_escape:
            atp += int(fired)
            afn += int(not fired)
        else:
            afp += int(fired)
            atn += int(not fired)
    print(f"  attempts: clean={atn + afp} escape={atp + afn} TP={atp} FP={afp} "
          f"FN={afn} TN={atn}")

    print("\n== clean-leg false positives (cap 2) ==")
    fps = [l for l in records if l["class"] == "held" and l["_pred"][0]]
    if not fps:
        print("  none")
    for leg in fps:
        print(f"  FP: " + fmt_leg(leg) + f"  fired@{leg['_pred'][1]}")
    clean_ticks = hot_ticks = 0
    for leg in records:
        if leg["class"] != "held":
            continue
        clean_ticks += leg["n"]
        hot_ticks += int(leg["_pred"][2].sum())
    print(f"  clean-leg tick-level pre-persistence hot fraction: "
          f"{hot_ticks}/{clean_ticks}" + (f" = {hot_ticks/clean_ticks:.4f}" if clean_ticks else ""))

    print("\n== tick-level critical-state F1 (Sentinel per-state readout; non-gating) ==")
    tt = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for leg in records:
        if leg["class"] not in ("held", "escape"):
            continue
        hot = leg["_pred"][2]
        for i, (slip, _f) in enumerate(leg["ticks"]):
            y = slip > TRIGGER
            h = bool(hot[i])
            if y and h:
                tt["tp"] += 1
            elif y and not h:
                tt["fn"] += 1
            elif h and not y:
                tt["fp"] += 1
            else:
                tt["tn"] += 1
    prec_e = tt["tp"] / (tt["tp"] + tt["fp"]) if tt["tp"] + tt["fp"] else 0.0
    rec_e = tt["tp"] / (tt["tp"] + tt["fn"]) if tt["tp"] + tt["fn"] else 0.0
    prec_c = tt["tn"] / (tt["tn"] + tt["fn"]) if tt["tn"] + tt["fn"] else 0.0
    rec_c = tt["tn"] / (tt["tn"] + tt["fp"]) if tt["tn"] + tt["fp"] else 0.0
    f1_e = 2 * prec_e * rec_e / (prec_e + rec_e) if prec_e + rec_e else 0.0
    f1_c = 2 * prec_c * rec_c / (prec_c + rec_c) if prec_c + rec_c else 0.0
    print(f"  ticks: seated tn={tt['tn']} fp={tt['fp']} | escaping tp={tt['tp']} fn={tt['fn']}")
    print(f"  escape ticks:  P={prec_e:.3f} R={rec_e:.3f} F1={f1_e:.3f}")
    print(f"  seated ticks:  P={prec_c:.3f} R={rec_c:.3f} F1={f1_c:.3f}")
    print(f"  macro-F1 (tick)={0.5 * (f1_e + f1_c):.3f}")

    print("\n== no-contact legs (excluded Normal analogue; informational) ==")
    nc = [l for l in records if l["class"] == "no-contact"]
    nc_fire = sum(1 for l in nc if l["_pred"][0])
    print(f"  {nc_fire} of {len(nc)} would fire (the live monitor blocks them "
          f"with a loaded-contact gate)")

    print("\n== attribution: standardized coefficients (mean over 55 folds) ==")
    mean_c = diag["coeffs"].mean(axis=0)
    std_c = diag["coeffs"].std(axis=0)
    for j, fname in enumerate(FEATURES):
        print(f"  {fname:10s} w={mean_c[j]:+.3f} (sd {std_c[j]:.3f})")

    if not args.skip_ablations:
        print("\n== drop-one-feature ablation (same CV; refit per fold) ==")
        base = s["macro"]
        print(f"  all features      macro={s['macro']:.3f} FP={s['fp']}")
        for j, fname in enumerate(FEATURES):
            idx = [k for k in range(len(FEATURES)) if k != j]
            for leg in records:
                leg.pop("_pred", None)
            run_cv(traces, feature_idx=idx)
            sj = score(records)
            print(f"  drop {fname:10s} macro={sj['macro']:.3f} "
                  f"(delta {sj['macro']-base:+.3f}) FP={sj['fp']} "
                  f"rec_e={sj['rec_e']:.3f} rec_c={sj['rec_c']:.3f}")
        print("  -- group probes (attribution extension, non-gating) --")
        for label, idx in (("geometry-only (drop tactile 3)", [0, 1, 2]),
                           ("tactile-only (drop geometry 3)", [3, 4, 5])):
            for leg in records:
                leg.pop("_pred", None)
            run_cv(traces, feature_idx=idx)
            sj = score(records)
            print(f"  {label:32s} macro={sj['macro']:.3f} FP={sj['fp']} "
                  f"rec_e={sj['rec_e']:.3f} rec_c={sj['rec_c']:.3f}")

    print("\n== reference rule (informational; not the gate) ==")
    # `contacts==0 or force<0.5` after the leg's first loaded tick, persistence 2.
    for leg in records:
        ticks = leg["ticks"]
        seen_loaded = False
        hot = []
        for slip, feat in ticks:
            if feat[4] >= 1.0:
                seen_loaded = True
            hot.append(seen_loaded and (feat[5] == 0.0 or feat[4] < 0.5))
        fire = None
        run = 0
        for i, h in enumerate(hot):
            run = run + 1 if h else 0
            if run >= PERSIST:
                fire = i - PERSIST + 1
                break
        leg["_pred"] = (fire is not None, fire, np.asarray(hot, dtype=bool))
    sr = score(records)
    print(f"  contacts/force rule: TP={sr['tp']} FP={sr['fp']} FN={sr['fn']} TN={sr['tn']} "
          f"macro={sr['macro']:.3f} F1e={sr['f1_e']:.3f}")
    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
