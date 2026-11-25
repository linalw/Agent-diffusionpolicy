# P261 results: the lift height reached **only the left arm** - aligning the right is **-0.55 s at 79/80**

**2026-11-25, `logs/p261/`.** A **structural asymmetry** found, measured and shipped as the
direct lane's default.

---

## 1. The find

The `[cycle]` block labels are counter-intuitive and cost this phase a wrong first read:
`grip` is **not** the load leg - it is the belt-break ramp (0.78 s) plus
`_settle_to_rest` (0.79 s), and **`lift` *is* the `grasp_lift` leg**. Two added
second-level marks (`lift_takeoff`, `lift_settle`) made that unambiguous.

With them, the leg splits **by arm**, in two independent cells:

| | `grasp_lift` ticks | `[motion]` distance |
|---|---|---|
| **right** | **177-191** | **25 cm** |
| **left** | **100** | **9 cm** |

Same commanded pose, half the travel - because **P66/P71's lift-height offset reaches only
the left arm**: `resolve_lift_dz` returns `{"left": dz}`, and `lift_dz_for` gives the right
`None`, i.e. the shipped `belt_top + 0.28` base while the left rides the measured `0.20 m`
rung. **And the right serves 62.5 % of the pool** (grades B and C), so the cell was
spending ~0.5 s on most picks for a height nobody had measured.

## 2. The knob and the cell

`FRUIT_LIFT_DZ_BOTH` (P261): one helper `_lift_dz_arms(dz)` returns the arm set, **default
both** since this phase, `=0` the left-only resolution P66/P71 built. Strict parsing.

| arm | placed | `lift` block | attempt `total` |
|---|---|---|---|
| control (left-only, P260's recipe) | 20/20 | **1.25 s** | **10.49 s** |
| both, s905 | **20/20** | **1.20 s** | **9.96 s** |
| both, s906 | **20/20** | 1.20 s | **9.89 s** |
| both, s907 (via the recipe, default) | **20/20** | 1.20 s | 10.03 s |
| both, s908 (via the recipe, default) | 19/20 | 1.20 s | 9.98 s |

**79/80 = 98.8 % placed, cycle median 9.97 s (-0.52 s, -5 %).** The right's leg reads
**93-100 ticks**, i.e. **exactly the left's**.

**Is it safe?** The right's `place` transit now clears the belt by **`clr = +104 mm`**
(`clr_edge` +104 too) - P71 measured **+14..+50 mm** on the left at the same rung, so the
right is the *more* comfortable side, not the marginal one. The single loss is the
long-standing grasp class.

## 3. Why the default is free of collateral

`resolve_lift_dz` returns `(None, False)` for **every presentation but `direct`**, so the
scripted single arm, the two-line session, the collector and the hybrid canary run with no
target arithmetic at all. Proved: `scripts/accept.sh` is **`fingerprint: matches
configs/motion_reference.json`** with its **459 `[fruit]` lines 459/459 identical** to
`logs/p227/accept_final.log`.

**Provenance needs no new field**: the manifest's `scene.lift.dz` is already a
`{arm: m}` map, so a left-only store and a both-arms store are distinguishable
by its keys (the concern that prompted a look was unfounded - nothing was added).

## 4. Two pins were re-pinned to the new shape (not to a new meaning)

* `236` (P66) now sets `FRUIT_LIFT_DZ_BOTH=0` **inside its `main`** and keeps asserting
  the left-only resolution it was written for (the rung as the direct default, the shipped
  height as the explicit restore) - P261's own leg asserts the both-arms default.
* The new `P261 lift dz both` leg pins the one helper, the both-by-default return, the
  left-only restore, and that **both return sites go through the helper** (three
  references: the definition and two calls).

## 5. Where the cycle now is

| phase | attempt cycle | change |
|---|---|---|
| arc start | 13.55 s | - |
| P249 | 12.13 s | axis-aware catch exit |
| P258 | 11.43 s | duplicated clearance |
| P259 | 10.85 s | over-timed place blend |
| P260 | 10.49 s | release holds |
| **P261** | **9.97 s** | **the right arm's 16 cm of unmeasured lift** |

**-26.4 % over the arc** at 98.8 % placed. **Honest caveat unchanged**: `gap` is bimodal
per cell, so throughput is a **range** (~4.6-4.8 picks/min at 0.08), never a point from
one cell.

## 6. Pins

`rl_env.py` (`_lift_dz_arms`, the two call sites), `scripts/236_p66_lift_selftest.py`
(the explicit left-only restore for that leg), `scripts/selfcheck.sh`; `tasks.py`
unchanged by this phase (`6e1600ac`, the P261 sub-marks); references **`61fb5202` /
`61fb5202` / `18b101bf`** untouched; ckpt `p227_panda156`. Evidence `logs/p261/`.
