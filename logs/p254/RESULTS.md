# P254 results: the return's blend clock is a **time/accuracy dial**, and the shipped one is near the sweet spot

**2026-11-25, `logs/p254/`.** One new default-off knob
(`FRUIT_CONTINUOUS_BLEND_ADAPT`), the transit decomposition, and an A/B at 0.12 on the
seeds the control already had. **Not adopted.**

---

## 1. Where the 263-tick return goes (measured, `FRUIT_CONTINUOUS_TRANSIT_DIAG=1`)

`_continuous_return` = `_lift_clear` (cap 150) + `_blend_to(90)` + `settle(60)`. One
0.12 cell, seed 903, 10 picks:

| part | measured |
|---|---|
| `lift_ticks` | **55-60** (and **172** on one, the long lift) |
| blend | **90** (fixed) |
| settle | **60** (fixed) |
| `gap_ticks` (pick boundary to boundary) | **265-270** |

So the return is **~205 ticks** and the remaining ~60 is the next pick's setup.

**And the fixed clock is wrong in both directions.** `total_moved` spans **0.36-2.30
rad**, so a fixed 90 ticks is ~6x the arithmetic on the small returns and *under*-timed
on the large ones: `blend_cmd_step` reaches **0.051 rad/tick** against the arm's
**0.0454** (5.445 rad/s at 120 Hz), and the arm ends up to **1.25 rad** from its own
goal (`blend_err`).

## 2. The knob: size the blend from the motion

`FRUIT_CONTINUOUS_BLEND_ADAPT=1` (default **off**, the shipped fixed 90/60 is byte for
byte) computes `ticks = clamp(1.875 * delta_q / (VMAX/120), MIN, MAX)` from **one
measured joint read per pick boundary** - the same read `_blend_to` takes for its own
start - with the min-jerk peak/average factor **1.875** and the arm's authored
**5.445 rad/s** (`maxJointVelocity` 312 deg/s, P44's census; `VMAX`/`MIN`/`MAX` are
env-overridable, strict parsing). Pinned by the `P254 blend adapt` selfcheck leg
(including the arithmetic executed at 0.36 and 2.30 rad).

## 3. The A/B at 0.12 (the seeds the control already had)

| | control (90+60) | adapt |
|---|---|---|
| placed | **16/20** (9/10, 7/10) | **18/20** (9/10, 9/10) |
| `gap_ticks` median | **268 / 296** | **237 / 245** |
| `blend_cmd_step` | 0.012-**0.051** | **0.045** on every row |
| `blend_err` (after the settle) | 0.11-0.41, worst **1.25** | **0.36-1.19** |
| blend ticks chosen | 90 (fixed) | **25-102** (adaptive) |

**The prediction was half wrong, and the half that survived is the useful one.**
`blend_cmd_step` lands exactly on the limit as designed and `gap_ticks` falls
**-31 ticks**, but **the end residual got *worse*, not better** (0.36-1.19 against
0.11-0.41 typical).

**That is the mechanism, stated properly**: `blend_err` is a **travel-time deficit, not
a tracking error**. The settle is the same 60 ticks in both arms, so fewer blend ticks
means less time for the arm to cover the same distance. **Which means 5.445 rad/s
over-estimates what this arm delivers at these poses** - the *correct* direction for the
long returns is **more** time, i.e. the opposite trade from the one the knob was built
to make.

## 4. Verdict: not adopted, and the shipped clock stands

* **The count is a draw** (16 -> 18 of 20, one draw each; no mechanism says otherwise -
  the 0.12 residual class is the pass-by/cadence one from P253, and adapt does not
  touch it).
* **The time saving is real and small**: 31 ticks of a 3 200-tick pick (**~1 %**), and
  it is bought with **+0.2-0.3 rad** of start-pose error for the next pick.
* **The accuracy side is not worth buying either**: the end residual is *already*
  tolerated - the 0.08 deployment cell reads **49/50 with 0.22-0.41 rad residuals**
  (P253) - so paying time to remove it has no endpoint.

**So the shipped fixed 90+60 is near the sweet spot**, and the honest statement of the
lever is a **dial**, not a win: `ADAPT` with `VMAX=5.445` trades accuracy for ~30
ticks; `ADAPT` with a *smaller* `VMAX` (e.g. 2.7, i.e. 2x the ticks) would restore the
residual at a time cost. **Neither direction is indicated by the data**, so nothing
ships and the knob stays a measurement instrument.

## 5. No-harm

`scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)** with the new `P254 blend adapt`
leg; `scripts/accept.sh` with every knob unset is **`fingerprint: matches
configs/motion_reference.json`** and its **459 `[fruit]` lines are 459/459 identical**
to `logs/p227/accept_final.log` - the knob is read only inside
`_continuous_return`, which the scripted acceptance never enters.

## 6. Pins

`rl_env.py` (the seven-line resolver + the one consumer, `TASKS_MD5` unchanged -
`tasks.py` `b68ac8d1`), `scripts/selfcheck.sh`; references **`61fb5202` / `61fb5202` /
`18b101bf`** untouched; ckpt `p227_panda156`. Evidence `logs/p254/`.
