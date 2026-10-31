"""Timestamp stdin lines with the elapsed seconds since the first line.

    scripts/run.sh scripts/20_pick_place.py 2>&1 | tee LOG | python3 -u stamp.py > LOG.stamps

Why: the scripted line prints no clock of its own (the `[fruit]` rows carry the
*simulated* time only), so the wall side of a throughput reading has to come from
the stream. `say()` flushes every line, so the elapsed values are real per-line
timestamps and not a buffer flush. The plain `tee` branch keeps the canonical log
byte-identical to a `>` redirect, so every existing parser still reads it.
"""

import sys
import time

start = time.monotonic()
out = sys.stdout
for line in sys.stdin:
    out.write(f"{time.monotonic() - start:10.3f} {line}")
    out.flush()
