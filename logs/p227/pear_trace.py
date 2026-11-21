#!/usr/bin/env python3
"""P227q: read the pear close from `FRUIT_DYNAMIC_TRACE=1` rows.

    python3 logs/p227/pear_trace.py logs/dynamic_trace_*.json

For each attempt it prints, from the **close** rows:

  * `span0/span1` - the measured finger span at the close's start and end;
  * at the close's last tick, `dx`/`dy` - the fruit centre relative to the jaw
    midpoint, split into the **closing** axis (x) and the **plate-width** axis
    (the belt, y);
  * whether the pads could straddle the fruit: `|dx| < (sep + 6 mm)/2` (the
    6 mm pad-face gap measured in `pad_geometry.log`);
  * whether the fruit's plate-width offset stayed inside the 76 mm plate
    (`|dy| <= 38 mm`), and how far it drifted from the close's start to its end;
  * the contact force and per-sensor split at the last row.

The question it settles: does the pear fail because the pads **miss along the
belt** (dy out of the plate's band, or the fruit leaving that band during the
close) or because it is **squeezed out** (in the band, contact made, and the
fruit's offset growing while the span closes)?
"""
from __future__ import annotations

import json
import sys


def band(rows, phase):
    return [r for r in rows if r.get("phase") == phase]


def main(paths):
    for path in paths:
        try:
            rows = json.load(open(path, encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"{path}: unreadable ({exc})")
            continue
        close = band(rows, "close")
        carry = band(rows, "carry")
        if not close:
            print(f"{path}: no close rows ({len(rows)} total)")
            continue
        first, last = close[0], close[-1]
        fx0, fy0 = first["fruit"][0], first["fruit"][1]
        fx1, fy1 = last["fruit"][0], last["fruit"][1]
        jx1, jy1 = last["jaw"][0], last["jaw"][1]
        dx = (fx1 - jx1) * 1000.0
        dy = (fy1 - jy1) * 1000.0
        sep = last["sep"] * 1000.0
        half = (sep + 6.0) / 2.0
        straddles = abs(dx) < half
        in_band = abs(dy) <= 38.0
        # first row with contact
        contact = next((r for r in close if r["force"] >= 0.5 or r["contacts"] > 0), None)
        cdy = None if contact is None else (contact["fruit"][1] - contact["jaw"][1]) * 1000.0
        cdx = None if contact is None else (contact["fruit"][0] - contact["jaw"][0]) * 1000.0
        fmax = max((r["force"] for r in close), default=0.0)
        # the load-carrying phase (after contact) - the span and the offsets
        print(
            f"{path}: close_rows={len(close)} carry_rows={len(carry)} "
            f"sep {first['sep'] * 1000:.1f} -> {sep:.1f} mm  "
            f"fruit dx {dx:+.1f} dy {dy:+.1f} mm  "
            f"straddle={'YES' if straddles else 'no'} (|dx|<{half:.1f}) "
            f"in_plate_band={'YES' if in_band else 'no'}"
        )
        if contact is not None:
            print(
                f"    first contact: t={contact['t']:.3f} force={contact['force']:.2f} "
                f"sep={contact['sep'] * 1000:.1f} mm  dx={cdx:+.1f} dy={cdy:+.1f} mm  "
                f"ft={contact.get('ft')}"
            )
        # drift of the plate-width offset across the close
        print(
            f"    fruit y {fy0:+.4f} -> {fy1:+.4f} (drift {(fy1 - fy0) * 1000:+.1f} mm)  "
            f"force_max={fmax:.2f} N  sep_min={min(r['sep'] for r in close) * 1000:.1f} mm  "
            f"ft_last={last.get('ft')}"
        )


if __name__ == "__main__":
    main(sys.argv[1:] or [])
