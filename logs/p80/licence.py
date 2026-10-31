"""P80 R2: does the speed union pay on this tree? (PREREG section 3 R2 / 4c)

    python3 logs/p80/licence.py            # reads logs/p80/{S20,U20}.log

Licensed iff U's `s/attempt` falls >= 1.0 s below S's (P44's registered E1 bar)
OR U's pooled inter-placement interval mean falls >= 10 % below S's. Prints the
numbers it used (so a later reader can re-check the arithmetic) and exits 0 when
licensed, 1 otherwise. Writes logs/p80/licence.txt.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p80lib  # noqa: E402

S = os.path.join(HERE, "S20.log")
U = os.path.join(HERE, "U20.log")
s, u = p80lib.metrics(S), p80lib.metrics(U)

d_span = None
if s["stats"]["per_attempt"] and u["stats"]["per_attempt"]:
    d_span = s["stats"]["per_attempt"] - u["stats"]["per_attempt"]
d_interval = None
rel_interval = None
if s["pooled"]["mean"] and u["pooled"]["mean"]:
    d_interval = s["pooled"]["mean"] - u["pooled"]["mean"]
    rel_interval = d_interval / s["pooled"]["mean"]

span_ok = d_span is not None and d_span >= 1.0
interval_ok = rel_interval is not None and rel_interval >= 0.10
licensed = bool(span_ok or interval_ok)

lines = [
    "P80 R2 licence - does the speed union pay? (PREREG section 3 R2, 4c)",
    f"  S20: s/attempt {p80lib.fmt(s['stats']['per_attempt'])}  "
    f"pooled interval mean {p80lib.fmt(s['pooled']['mean'])}s  "
    f"placed {s['placed']}/{s['attempts']}",
    f"  U20: s/attempt {p80lib.fmt(u['stats']['per_attempt'])}  "
    f"pooled interval mean {p80lib.fmt(u['pooled']['mean'])}s  "
    f"placed {u['placed']}/{u['attempts']}",
    f"  d_s/attempt = {p80lib.fmt(d_span)}s   (bar: >= 1.0 s)  -> "
    f"{'PASS' if span_ok else 'fail'}",
    f"  d_interval = {p80lib.fmt(d_interval)}s = "
    f"{p80lib.fmt(None if rel_interval is None else 100.0 * rel_interval, 1)}% "
    f"(bar: >= 10 %)  -> {'PASS' if interval_ok else 'fail'}",
    f"  V is {'LICENSED - run the two-line arm on the union' if licensed else 'NOT licensed - V is not spent'}",
]
text = "\n".join(lines)
print(text)
with open(os.path.join(HERE, "licence.txt"), "w", encoding="utf-8") as fh:
    fh.write(text + "\n")
sys.exit(0 if licensed else 1)
