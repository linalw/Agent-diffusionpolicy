#!/usr/bin/env python3
"""P8 B-lane offline: FP-fix retry search for the C-3 carry monitor (read-only).

Context
-------
The P7-2b battery killed the frozen C-3 monitor on K2 (5 clean-leg aborts on
19 clean attempts > cap 2) while the interval endpoint passed (-24.0 %, paired
33-0). The pre-registered next step was a JCAC-style second signal. This script
searches *bounded decision-rule fixes* offline: it does not refit the scorer in
a new way, does not touch the corpus and does not run a simulator.

It imports the frozen Phase-0 replay (`scripts/203_c3_monitor_replay.py`) and
reuses its corpus loader, its logistic fit and its leave-one-trace-out protocol,
so every variant is scored exactly like `logs/p7/C3_REPLAY.md`:

  * the six online features and the frozen fit (lr 0.5, 3000 steps, L2 1e-3);
  * labels from the W8-B clean_slip (> 2.0 mm, label-side only);
  * decisions evaluated per held-out leg (leave-one-trace-out);
  * the gate = macro-F1 >= 0.86 AND FP <= 2 of 33 clean legs.

Two scorings are reported:
  * `fold`    - the frozen leave-one-trace-out protocol (gate-comparable);
  * `deployed`- the all-data fit, whose constants are the ones embedded in the
                live monitor (P7-2c extract); the live-analogue readout.

Candidate families:
  (a) stricter persistence / decision margin on the existing score z;
  (b) conformal second signal (two cheap surrogates: a score-level clean-leg
      quantile and a per-feature one-sided force radius);
  (c) two-stage confirm: the frozen stage plus a force-asymmetry load floor
      `asym = force - 2*ft_min` (= |ft0 - ft1|) that must hold for the skip.

Read-only: prints a report to stdout; writes nothing. Deterministic.

Usage:
    python3 scripts/205_c3_fp_retry.py
"""

from __future__ import annotations

import importlib.util
import os

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


r203 = _load(os.path.join(REPO, "scripts", "203_c3_monitor_replay.py"),
             "c3_replay_203")
bm = _load(os.path.join(REPO, "logs", "w8", "B_metric.py"), "b_metric")

TRIGGER = r203.TRIGGER
PERSIST = r203.PERSIST


# ---------------------------------------------------------------- corpus ----

def build():
    traces, records = r203.load_corpus(bm)
    counts = {}
    for leg in records:
        counts[leg["class"]] = counts.get(leg["class"], 0) + 1
    expected = r203.EXPECTED
    ok = all(counts.get(k, 0) == v for k, v in expected.items()) and \
        sum(counts.values()) == sum(expected.values())
    per_trace = {}
    for leg in records:
        n = per_trace.get(leg["trace"], 0)
        leg["lid"] = f"{leg['corpus']}/{os.path.basename(leg['trace'])}#{n}"
        per_trace[leg["trace"]] = n + 1
        leg["feats"] = np.asarray([f for _, f in leg["ticks"]], dtype=float)
        leg["asym"] = np.maximum(
            0.0, leg["feats"][:, 4] - 2.0 * leg["feats"][:, 3])
        leg["z_fold"] = None
        leg["z_all"] = None

    # deployed constants (the live monitor's embedded scorer)
    xs = np.asarray([f for leg in records for _, f in leg["ticks"]],
                    dtype=float)
    ys = np.asarray([1.0 if slip > TRIGGER else 0.0
                     for leg in records for slip, _ in leg["ticks"]],
                    dtype=float)
    wA, bA, muA, sdA, lossA, gradA = r203.fit_logreg(xs, ys)
    for leg in records:
        leg["z_all"] = (leg["feats"] - muA) / sdA @ wA + bA

    # the live implementation's vsep convention (CONTROL_DT, not the row dt)
    for leg in records:
        zz = []
        prev = None
        for _slip, feat in leg["ticks"]:
            sep = float(feat[0])
            vsep = 0.0 if prev is None else (sep - prev) / r203.DT_NOM
            prev = sep
            x = np.asarray([feat[0], feat[1], vsep, feat[3], feat[4],
                            feat[5]], dtype=float)
            zz.append(float((x - muA) / sdA @ wA + bA))
        leg["z_live"] = np.asarray(zz)

    # frozen leave-one-trace-out fold models
    for held_id, held_legs in traces:
        tx, ty = [], []
        for trace_id, legs in traces:
            if trace_id == held_id:
                continue
            for leg in legs:
                for slip, feat in leg["ticks"]:
                    tx.append(feat)
                    ty.append(1.0 if slip > TRIGGER else 0.0)
        w, b, mu, sd, _lo, _gr = r203.fit_logreg(
            np.asarray(tx, dtype=float), np.asarray(ty, dtype=float))
        for leg in held_legs:
            leg["z_fold"] = (leg["feats"] - mu) / sd @ w + b
    return traces, records, counts, ok, (wA, bA, muA, sdA, lossA, gradA)


# ------------------------------------------------------------- rules --------

def fire_run(hot, persist):
    run = 0
    for i, h in enumerate(hot):
        run = run + 1 if h else 0
        if run >= persist:
            return i - persist + 1
    return None


def load_mask(leg, af):
    """contacts == 0 (loss is itself evidence) OR asym >= af."""
    return (leg["feats"][:, 5] == 0.0) | (leg["asym"] >= af)


def rule_margin(z, leg, thr=0.0, persist=PERSIST):
    return fire_run(z >= thr, persist)


def rule_load(z, leg, thr=0.0, af=4.0, persist=PERSIST):
    hot = (z >= thr) & load_mask(leg, af)
    return fire_run(hot, persist)


def rule_confirm(z, leg, af=4.0, m=2, thr=0.0, persist=PERSIST):
    """Frozen stage-1 fire, then m consecutive load ticks at/after the fire."""
    f0 = fire_run(z >= thr, persist)
    if f0 is None:
        return None
    run = 0
    for i in range(f0, len(z)):
        run = run + 1 if load_mask(leg, af)[i] else 0
        if run >= m:
            return i
    return None


def live_replay(leg, thr=0.0, af=None, persist=PERSIST):
    """The real `_CarryMonitorLeg` semantics: `min_contacts` includes the
    current tick, so a contacts==0 tick closes the gate for the rest of the
    leg; z uses the live `vsep` convention (`z_live`)."""
    minc = 10
    run = 0
    z = leg["z_live"]
    for i in range(len(z)):
        c = int(leg["feats"][i, 5])
        minc = min(minc, c)
        hot = z[i] >= thr
        if af is not None:
            hot = hot and (c == 0 or leg["asym"][i] >= af)
        if not hot:
            run = 0
            continue
        if minc <= 0:
            run = 0
            continue
        run += 1
        if run >= persist:
            return i - persist + 1
    return None


# ----------------------------------------------------------- evaluation -----

def score(fires, records):
    tp = fp = fn = tn = 0
    lost_clean = []
    for leg in records:
        if leg["class"] not in ("held", "escape"):
            continue
        f = fires[leg["lid"]]
        if leg["class"] == "escape":
            tp += int(f is not None)
            fn += int(f is None)
        else:
            fp += int(f is not None)
            tn += int(f is None)
            if f is not None:
                lost_clean.append(leg["lid"])
    prec_e = tp / (tp + fp) if tp + fp else 0.0
    rec_e = tp / (tp + fn) if tp + fn else 0.0
    prec_c = tn / (tn + fn) if tn + fn else 0.0
    rec_c = tn / (tn + fp) if tn + fp else 0.0
    f1_e = 2 * prec_e * rec_e / (prec_e + rec_e) if prec_e + rec_e else 0.0
    f1_c = 2 * prec_c * rec_c / (prec_c + rec_c) if prec_c + rec_c else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "f1_e": f1_e, "f1_c": f1_c, "macro": 0.5 * (f1_e + f1_c),
            "fp_legs": lost_clean}


def evaluate(records, zkey, rule):
    fires = {}
    for leg in records:
        if leg["class"] not in ("held", "escape"):
            continue
        fires[leg["lid"]] = rule(leg[zkey], leg)
    return fires, score(fires, records)


def latency(fires, base, records):
    """Over the 31 escapes: same/later/earlier/never vs the frozen rule."""
    same = later = never = 0
    deltas = []
    remain = []
    for leg in records:
        if leg["class"] != "escape":
            continue
        f0 = base[leg["lid"]]
        f1 = fires[leg["lid"]]
        if f0 is None:
            continue
        if f1 is None:
            never += 1
            continue
        d = f1 - f0
        deltas.append(d)
        if d == 0:
            same += 1
        elif d > 0:
            later += 1
        remain.append(leg["n"] - 1 - f1)
    return {"same": same, "later": later, "never": never,
            "delta": (min(deltas), float(np.median(deltas)), max(deltas))
            if deltas else (0, 0, 0),
            "remain_med": int(np.median(remain)) if remain else None}


# ------------------------------------------------------------- helpers ------

def binding_margin(z, persist):
    if len(z) < persist:
        return None
    return max(min(z[i:i + persist]) for i in range(len(z) - persist + 1))


def best_load_window(leg, z):
    """max over 2-consecutive z>=0 windows of min(load) with the rule's
    contacts==0 exemption (a loss tick makes the window automatically valid)."""
    c = leg["feats"][:, 5]
    best = None
    for i in range(len(z) - 1):
        if z[i] >= 0.0 and z[i + 1] >= 0.0:
            if c[i] == 0 or c[i + 1] == 0:
                v = 1e9
            else:
                v = min(leg["asym"][i], leg["asym"][i + 1])
            best = v if best is None else max(best, v)
    return best


def joint_af(leg, z, tau):
    """max over 2-windows with min(z) >= tau of min(asym) (contacts==0 -> inf)."""
    best = None
    c = leg["feats"][:, 5]
    for i in range(len(z) - 1):
        if z[i] >= tau and z[i + 1] >= tau:
            a = 1e9 if (c[i] == 0 or c[i + 1] == 0) else \
                min(leg["asym"][i], leg["asym"][i + 1])
            best = a if best is None else max(best, a)
    return best


def legmax(z):
    return float(np.max(z)) if len(z) else -1e9


def main():
    traces, records, counts, ok, dpl = build()
    wA, bA, muA, sdA, lossA, gradA = dpl

    print("=" * 78)
    print("P8 B-lane: C-3 carry-monitor FP-fix retry (offline, frozen protocol)")
    print("=" * 78)
    print("\n== corpus (frozen Phase-0; 203 loader + W8-B labels) ==")
    for corpus in r203.CORPORA:
        sub = [l for l in records if l["corpus"] == corpus]
        cc = {}
        for leg in sub:
            cc[leg["class"]] = cc.get(leg["class"], 0) + 1
        print(f"  {corpus:28s} traces={len(set(l['trace'] for l in sub)):2d} "
              f"legs={len(sub):2d} " +
              " ".join(f"{k}={v}" for k, v in sorted(cc.items())))
    print(f"  total counts={counts} expected={r203.EXPECTED} "
          f"invariant={'OK' if ok else 'VIOLATED'}")
    if not ok:
        print("STOP: corpus invariant violated; the frozen gate is void.")
        return 2
    print(f"  deployed scorer (all-data fit): loss={lossA:.5f} "
          f"max|grad|={gradA:.2e}")
    print(f"  deployed w={np.round(wA, 3)} b={bA:+.4f}")

    esc = [l for l in records if l["class"] == "escape"]
    cln = [l for l in records if l["class"] == "held"]
    by_lid = {l["lid"]: l for l in records}

    # ------------------------------------------------------------- variants
    V = []
    V.append(("frozen", "a", lambda z, l: rule_margin(z, l, 0.0, 2)))
    V.append(("persist3", "a", lambda z, l: rule_margin(z, l, 0.0, 3)))
    V.append(("persist5", "a", lambda z, l: rule_margin(z, l, 0.0, 5)))
    for m in (0.5, 0.75, 1.0, 1.106, 1.25, 1.5):
        V.append((f"margin{m}", "a",
                  (lambda m: lambda z, l: rule_margin(z, l, m, 2))(m)))
    V.append(("margin1.0+p3", "a", lambda z, l: rule_margin(z, l, 1.0, 3)))
    for af in (2.58, 2.75, 3.0, 3.5, 3.75, 4.0, 4.32, 4.5):
        V.append((f"force{af}", "c",
                  (lambda af: lambda z, l: rule_load(z, l, 0.0, af, 2))(af)))
    for tau, af in ((0.75, 4.0), (1.0, 3.5), (1.0, 4.0), (1.0, 4.32)):
        V.append((f"joint{tau}/{af}", "c",
                  (lambda t, a: lambda z, l: rule_load(z, l, t, a, 2))(tau, af)))
    for af, m in ((3.5, 2), (4.0, 2), (4.0, 3)):
        V.append((f"confirm{af}/m{m}", "c",
                  (lambda a, mm: lambda z, l: rule_confirm(z, l, a, mm))(
                      af, m)))

    def run_all(zkey):
        out = {}
        for name, cat, rule in V:
            fires, st = evaluate(records, zkey, rule)
            out[name] = (cat, rule, fires, st)
        return out

    fold = run_all("z_fold")
    dep = run_all("z_all")

    print("\n== variant table: fold (gate-comparable) and deployed (live-"
          "analogue) ==")
    print(f"{'variant':18s} {'cat':3s} | fold TP FP FN TN  F1e   F1c  macro"
          f" | deployed TP FP FN TN | clean legs firing")
    base_fires = fold["frozen"][2]
    for name, cat, rule in V:
        _, _, fires, st = fold[name]
        _, _, _, sd = dep[name]
        moved = [l for l in st["fp_legs"]]
        moved_s = ",".join(m.split("/")[-1] for m in moved) or "-"
        print(f"{name:18s} {cat:3s} |      {st['tp']:2d} {st['fp']:2d} "
              f"{st['fn']:2d} {st['tn']:2d}  {st['f1_e']:.3f} {st['f1_c']:.3f} "
              f"{st['macro']:.3f} |            {sd['tp']:2d} {sd['fp']:2d} "
              f"{sd['fn']:2d} {sd['tn']:2d} | {moved_s}")

    # --------------------------------------------------- margins / latency
    print("\n== latency vs frozen (31 escapes; fold scoring) ==")
    print(f"{'variant':18s} {'same':>4s} {'later':>5s} {'never':>5s} "
          f"delta min/med/max      median remainder")
    for name in ("margin0.75", "margin1.0", "margin1.106", "force2.58",
                 "force3.5", "force3.75", "force4.0", "joint1.0/4.0",
                 "confirm4.0/m2"):
        _, _, fires, _ = fold[name]
        lat = latency(fires, base_fires, records)
        print(f"{name:18s} {lat['same']:4d} {lat['later']:5d} "
              f"{lat['never']:5d} {str(lat['delta']):22s} {lat['remain_med']}")
    lat0 = latency(base_fires, base_fires, records)
    print(f"{'frozen':18s} {lat0['same']:4d} {lat0['later']:5d} "
          f"{lat0['never']:5d} {str(lat0['delta']):22s} {lat0['remain_med']}")

    # --------------------------------------------------- binding frontier
    print("\n== margin-family boundary (fire = 2-consecutive z >= tau) ==")
    for tag, zkey, p in (("fold P2", "z_fold", 2), ("fold P3", "z_fold", 3),
                         ("deployed P2", "z_all", 2),
                         ("deployed P3", "z_all", 3)):
        e = [(l, binding_margin(l[zkey], p)) for l in esc]
        c = [(l, binding_margin(l[zkey], p)) for l in cln]
        emin = min(e, key=lambda t: t[1])
        cmax = max(c, key=lambda t: t[1])
        print(f"  {tag:12s} escape binding min={emin[1]:+.3f} ({emin[0]['lid']})"
              f"   clean max={cmax[1]:+.3f} ({cmax[0]['lid']})")

    print("\n== force-floor boundary (hot = z>=0 and [contacts==0 or "
          "asym>=af], P2) ==")
    e = [(l, best_load_window(l, l["z_fold"])) for l in esc]
    e = [(l, b) for l, b in e if b is not None]
    c = [(l, best_load_window(l, l["z_fold"])) for l in cln]
    c = [(l, b) for l, b in c if b is not None]
    emin = min(e, key=lambda t: t[1])
    cmax = max(c, key=lambda t: t[1])
    print(f"  fold: escape binding min={emin[1]:.2f} ({emin[0]['lid']})   "
          f"clean max={cmax[1]:.2f} ({cmax[0]['lid']})")
    for tau in (0.0, 0.5, 0.75, 0.9, 1.0, 1.05, 1.1, 1.106, 1.2):
        vals = []
        for l in esc:
            a = joint_af(l, l["z_fold"], tau)
            if a is None:
                vals.append((l, None))
            else:
                vals.append((l, a))
        okv = [(l, a) for l, a in vals if a is not None]
        if not okv:
            print(f"  joint frontier tau={tau:5.3f}: no escape keeps a window")
            continue
        wmin = min(okv, key=lambda t: t[1])
        print(f"  joint frontier tau={tau:5.3f}: max feasible af="
              f"{wmin[1]:6.2f} (binding {wmin[0]['lid']})")

    print("\n== the recommended fixed rule (frozen z>=0 + load floor 3.5 N, "
          "P2) ==")
    print("  hot(t) = z(t) >= 0 AND [contacts(t)==0 OR asym(t) >= 3.5 N]; "
          "asym = force - 2*ft_min = |ft0 - ft1|")
    _, _, ff, fst = fold["force3.5"]
    _, _, fd, fdst = dep["force3.5"]
    print(f"  fold 203-protocol: TP={fst['tp']} FP={fst['fp']} "
          f"FN={fst['fn']} TN={fst['tn']} macro={fst['macro']:.3f}")
    print(f"  deployed no-gate : TP={fdst['tp']} FP={fdst['fp']} "
          f"FN={fdst['fn']} TN={fdst['tn']} macro={fdst['macro']:.3f}")
    lb = {leg["lid"]: live_replay(leg, 0.0, None) for leg in records}
    lf = {leg["lid"]: live_replay(leg, 0.0, 3.5) for leg in records}
    fnl = [leg for leg in esc if lf[leg["lid"]] is None]
    print(f"  live implementation (embedded consts, CONTROL_DT vsep, "
          f"running-min gate): TP={31 - len(fnl)} FN={len(fnl)}")
    for leg in fnl:
        print(f"    FN {leg['lid']}  frozen-tick={lb[leg['lid']]} "
              f"loss={leg['loss']}")
    print(f"  clean legs firing under the fixed rule: "
          f"{fst['fp_legs'] if fst['fp_legs'] else 'none'}")
    moved_off = [l for l in cln if base_fires[l["lid"]] is not None and
                 ff[l["lid"]] is None]
    print(f"  clean legs that STOP firing: {[l['lid'] for l in moved_off]}")
    moved_on = [l for l in cln if base_fires[l["lid"]] is None and
                ff[l["lid"]] is not None]
    print(f"  clean legs that START firing: {[l['lid'] for l in moved_on]}")

    print("\n  per-escape detail (fold): frozen tick -> fixed tick, load "
          "margin at the fire window")
    print(f"  {'leg':58s} {'froz':>4s} {'fixed':>5s} {'delta':>5s} "
          f"{'remain':>6s}  {'load_min':>8s}")
    lslacks = []
    for leg in esc:
        f0 = base_fires[leg["lid"]]
        f1 = ff[leg["lid"]]
        d = "-" if (f0 is None or f1 is None) else f"{f1 - f0:+d}"
        rem = "-" if f1 is None else leg["n"] - 1 - f1
        c = leg["feats"][:, 5]
        lm = "n/a"
        if f1 is not None:
            vals = [1e9 if c[i] == 0 else leg["asym"][i]
                    for i in range(f1, f1 + 2)]
            m = min(vals)
            lm = "loss" if m > 1e8 else f"{m:.2f}"
            if m <= 1e8:
                lslacks.append(m - 3.5)
        print(f"  {leg['lid']:58s} {str(f0):>4s} {str(f1):>5s} {d:>5s} "
              f"{str(rem):>6s}  {lm:>8s}")
    if lslacks:
        print(f"  tightest load margin over fired windows: "
              f"{min(lslacks):+.2f} N")

    print("\n== live-convention grid (embedded consts, CONTROL_DT vsep, "
          "running-min loaded-contact gate) ==")
    print("   the convention of the real `_CarryMonitorLeg`; delta is vs "
          "that rule's own frozen fires")
    grid = [("frozen", 0.0, None)]
    grid += [(f"force{af}", 0.0, af)
             for af in (2.58, 2.75, 3.0, 3.5, 3.75, 4.0, 4.32)]
    grid += [(f"margin{m}", m, None) for m in (0.75, 1.0)]
    grid += [(f"joint{t}/{af}", t, af)
             for t, af in ((0.75, 4.0), (1.0, 3.5), (1.0, 4.0))]
    for name, thr, af in grid:
        tp = fn = fp = tn = 0
        fnlegs = []
        lat = []
        rem = []
        for leg in records:
            f = live_replay(leg, thr, af)
            if leg["class"] == "escape":
                tp += int(f is not None)
                fn += int(f is None)
                if f is None:
                    fnlegs.append((leg["lid"], lb[leg["lid"]], leg["loss"]))
                else:
                    rem.append(leg["n"] - 1 - f)
                    if lb[leg["lid"]] is not None:
                        lat.append(f - lb[leg["lid"]])
            elif leg["class"] == "held":
                fp += int(f is not None)
                tn += int(f is None)
        dmed = int(np.median(lat)) if lat else 0
        dmax = max(lat) if lat else 0
        later = sum(1 for d in lat if d > 0)
        rmed = int(np.median(rem)) if rem else None
        print(f"  {name:16s} TP={tp:2d} FP={fp} FN={fn} TN={tn:2d} | "
              f"delta p50={dmed:+d} max={dmax:+d} later={later} "
              f"| remainder p50={rmed}")
        if fnlegs:
            print("      FN: " + ", ".join(
                f"{l.split('/')[-1]} (froz={fb}, loss={loss})"
                for l, fb, loss in fnlegs))

    # --------------------------------------------------- conformal family
    print("\n== family (b): conformal second-signal surrogates ==")
    # b1: score-level, per-fold quantile from the OTHER clean legs (max).
    taus = {}
    for trace_id, legs in traces:
        pool = [leg for tr, legs2 in traces if tr != trace_id
                for leg in legs2 if leg["class"] == "held"]
        taus[trace_id] = max(legmax(l["z_fold"]) for l in pool)
    tor = [taus[l["trace"]] for l in records if l["class"] in
           ("held", "escape")]
    print(f"  b1 per-fold tau from other clean legs: min={min(tor):+.2f} "
          f"median={np.median(tor):+.2f} max={max(tor):+.2f}")
    print(f"  b1 tau for the w8-mech trace_10 fold = "
          f"{taus[[t for t in traces if 'w8/B_traces_mech/trace_10' in t[0]][0][0]]:+.2f}"
          f"  (the FP legs' own trace)")
    # b1 readout: base fire AND legmax >= tau
    fp_b1 = tp_b1 = 0
    for leg in records:
        if leg["class"] not in ("held", "escape"):
            continue
        f = base_fires[leg["lid"]]
        okk = f is not None and legmax(leg["z_fold"]) >= taus[leg["trace"]]
        if leg["class"] == "escape":
            tp_b1 += int(okk)
        else:
            fp_b1 += int(okk)
        if okk:
            pass
    print(f"  b1 readout (base fire AND legmax >= tau): "
          f"TP={tp_b1}/31 FP={fp_b1}/33  -> no FP reduction")
    print(f"  b1 deployed analogue: tau = max clean legmax "
          f"(deployed z) = {max(legmax(l['z_all']) for l in cln):+.2f} "
          f"(fold: {max(legmax(l['z_fold']) for l in cln):+.2f}) - the FP "
          f"legs define the tail")
    # b2: per-feature one-sided force radius from clean legs
    radii = []
    for leg in cln:
        f = leg["feats"]
        m = (f[:, 5] <= 1.0) & (f[:, 3] <= 0.05)
        if m.any():
            radii.extend(leg["asym"][m].tolist())
    print(f"  b2 clean one-sided (contacts<=1, ft_min<=0.05) asym radius: "
          f"max={max(radii):.2f} N over {len(radii)} ticks "
          f"(2 legs, trace_10) -> equals the force2.58 grid point")

    # --------------------------------------------------- confirm readouts
    print("\n== family (c) confirm-at-fire vs the merged predicate ==")
    for name in ("confirm3.5/m2", "confirm4.0/m2", "confirm4.0/m3",
                 "force3.5", "force4.0"):
        _, _, fires, st = fold[name]
        lat = latency(fires, base_fires, records)
        print(f"  {name:16s} fold TP={st['tp']} FP={st['fp']} FN={st['fn']} "
              f"macro={st['macro']:.3f} | later={lat['later']} "
              f"never={lat['never']} remain_med={lat['remain_med']}")

    # --------------------------------------------------- live anchors
    print("\n== live anchors (P7-2b battery; B_RESULTS section 3.3) ==")
    anchors = [
        ("run4 ep8 kiwi", 1.16, 3.26, 138),
        ("run4 ep9 tomato", 1.04, 2.12, 0),
        ("run5 ep0 tomato", 0.91, 1.51, 0),
        ("run5 ep3 peach", 0.74, 1.79, 0),
        ("run5 ep12 peach", 0.74, 1.81, 0),
    ]
    print("  (z_fire = the observed fire-tick z under the deployed constants; "
          "force_min = the leg minimum, an UPPER bound on nothing "
          "(force@fire >= force_min); both from the p7c [carry] lines)")
    print(f"  {'variant':18s} {'z<thr':>6s} {'fmin<af':>8s} {'joint':>6s} "
          f"note")
    for name, cat, rule in V:
        if "+p" in name:
            continue
        thr = None
        af = None
        if name.startswith("margin") and not name.startswith("margin1.0+p"):
            thr = float(name[len("margin"):].split("+")[0])
        elif name.startswith("force"):
            af = float(name[len("force"):])
        elif name.startswith("joint"):
            thr, af = (float(x) for x in name[len("joint"):].split("/"))
        elif name.startswith("confirm"):
            af = float(name[len("confirm"):].split("/")[0])
        if name.startswith("margin") or name.startswith("joint") or \
                name.startswith("force") or name.startswith("confirm"):
            zb = sum(1 for _, z, fmin, _ in anchors if thr is not None
                     and z < thr)
            fb = sum(1 for _, z, fmin, _ in anchors if af is not None
                     and fmin < af)
            if thr is not None and af is not None:
                jb = sum(1 for _, z, fmin, _ in anchors
                         if z < thr or fmin < af)
                note = "stationary-hold assumption for force@fire"
            elif thr is not None:
                jb = zb
                note = "blocked at the observed fire site only"
            else:
                jb = fb
                note = "force_min is a lower bound; stationary-hold assumption"
            print(f"  {name:18s} {zb:>6d} {fb:>8d} {jb:>6d} {note}")
    print("\nNOTE: the offline corpus cannot reproduce the live FP class: under")
    print("the DEPLOYED constants the corpus clean max legmax is "
          f"{max(legmax(l['z_all']) for l in cln):-.2f} and the frozen rule has")
    print("FP=0/33, yet the live battery's clean holds fired at z 0.74-1.16.")
    print("Every live-FP estimate above is conditional; the battery measures.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
