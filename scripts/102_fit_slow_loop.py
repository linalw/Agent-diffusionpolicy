"""Fit the slow loop's learned prior from candidate-level decision logs.

    python3 scripts/102_fit_slow_loop.py --log logs/decisions_rule.jsonl \
        --out logs/slow_loop_weights.json

The decision log (written by `SlowLoopAgent.record_outcome`) stores, per attempt,
the feature vector of the *chosen* candidate and whether the attempt succeeded.
The fit is a strongly ridge-regularised logistic regression over those rows, in
numpy: with tens of rows and eight features an unregularised fit would memorise,
so lambda is large and the script also prints simple per-bucket success rates,
which are the honest signal at this sample size.

The output JSON (`coef`, `intercept`, `n`, `train_acc`) is what
`FRUIT_SLOW_WEIGHTS=<path>` loads into the scorer.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

FEATURES = ("bias", "diameter", "dx", "y", "mass", "grade_A", "prior_rate", "prior_n")


def load_rows(paths: list[str]) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    rows, labels, raw = [], [], []
    for path in paths:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                features = record.get("features")
                if not features:
                    continue
                rows.append(
                    [
                        1.0,
                        (float(features["diameter"]) - 0.05) / 0.02,
                        float(np.clip(features["dx"], -0.3, 1.6)) / 0.4,
                        float(features["y"]) / 0.05,
                        (float(features["mass"]) - 0.08) / 0.08,
                        1.0 if features["grade"] == "A" else 0.0,
                        float(features.get("prior_rate", 0.5)) - 0.5,
                        np.log1p(float(features.get("prior_n", 0.0))) / 3.0,
                    ]
                )
                labels.append(1.0 if record["success"] else 0.0)
                raw.append(record)
    return np.asarray(rows, dtype=float), np.asarray(labels, dtype=float), raw


def fit_logistic(x: np.ndarray, y: np.ndarray, lam: float = 10.0, steps: int = 800,
                 lr: float = 0.5) -> tuple[np.ndarray, float]:
    n, d = x.shape
    coef = np.zeros(d)
    for _ in range(steps):
        z = np.clip(x @ coef, -30, 30)
        p = 1.0 / (1.0 + np.exp(-z))
        grad = x.T @ (p - y) / n + lam * np.r_[0.0, coef[1:]] / n
        coef -= lr * grad
    z = np.clip(x @ coef, -30, 30)
    p = 1.0 / (1.0 + np.exp(-z))
    accuracy = float(((p > 0.5) == (y > 0.5)).mean()) if n else 0.0
    return coef, accuracy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", nargs="+", default=["logs/decisions_rule.jsonl"])
    parser.add_argument("--out", default="logs/slow_loop_weights.json")
    args = parser.parse_args()

    x, y, raw = load_rows(args.log)
    if len(y) == 0:
        print("no decision rows found")
        return 1
    coef, accuracy = fit_logistic(x, y)

    print(f"rows={len(y)} successes={int(y.sum())} train_acc={accuracy * 100:.0f}%")
    print("coefficients (standardised features):")
    for name, value in zip(FEATURES, coef):
        print(f"  {name:>11}: {value:+.3f}")

    # The honest signal at this sample size: per-bucket success rates.
    print("per-bucket success rates:")
    for key, buckets in (
        ("diameter", [(0.0, 0.04), (0.04, 0.055), (0.055, 0.09)]),
        ("dx", [(-0.3, 0.1), (0.1, 0.4), (0.4, 1.6)]),
    ):
        for low, high in buckets:
            rows = [r for r in raw if low <= float(r["features"][key]) < high]
            if rows:
                ok = sum(1 for r in rows if r["success"])
                print(f"  {key} [{low:.2f},{high:.2f}): {ok}/{len(rows)}")

    payload = {
        "coef": coef.tolist(),
        "intercept": 0.0,
        "features": list(FEATURES),
        "n": int(len(y)),
        "train_acc": accuracy,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"wrote {args.out} (load with FRUIT_SLOW_WEIGHTS={args.out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
