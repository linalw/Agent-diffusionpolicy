# P263 results: `place` decomposed - and the blend's settle is **transferred, not saved**

**2026-11-25, `logs/p263/`.** Two second-level marks inside the place leg, one candidate
measurement, **nothing adopted**. **No `src/` change beyond the marks**, no `configs/`.

---

## 1. The decomposition

`place` = 3.00 s, and its three parts are now visible (`FRUIT_CYCLE_SUB=1`, 0.08, seed 905):

| segment | median | what it is |
|---|---|---|
| **`place_clear`** | **0.78 s** | the lift mark -> the end of the 0.10 m clear move (the clear's own 0.43 s from P259 plus the between-leg bookkeeping) |
| **`place_blend`** | **1.08 s** | the joint blend to `bin{i}_above`: **90 ticks + a 40-tick settle** (0.75 + 0.33) |
| **`place`** (remainder) | **1.14 s** | the Cartesian run to the bin (the `[motion]` row reads **5 cm / 81 ticks at `\|v\|cmd` 0.142**, so ~0.68 s is the leg and the rest is its tail) |

So the earlier "place 3.01" is clear 0.78 + blend 1.08 + Cartesian 1.14.

## 2. The blend's settle is **load-bearing**, and the measurement says why

The 40-tick settle (0.33 s) is the same shape as P262's `_settle_to_rest`, so it was the
obvious next candidate: `FRUIT_PLACE_BLEND_SETTLE=10` (20 picks x 2 seeds):

| | `place_blend` | `place` (Cartesian) | sum |
|---|---|---|---|
| control (settle 40) | **1.08 s** | **1.14 s** | 2.22 s |
| settle 10, s905 | **0.83 s** | **1.33 s** | 2.16 s |
| settle 10, s906 | 0.83 s | 1.33 s | 2.16 s |

**The blend loses the 0.25 s and the Cartesian leg takes 0.19 of it back** - because the
arm has not arrived at `bin_above` when the Cartesian run starts, so *that* leg pays the
residual. Net **-0.06 s on the block, and the attempt is a wash**: 9.71 s (the P262 recipe
cell, same size) against **9.71 / 9.75 s**.

**Both cells placed 20/20**, so this is not a quality trade either way - it is **no trade at
all**: the settle buys the next leg a settled start, and cutting it only moves the cost.
**Not adopted.** This is the third time the arc has measured the same shape (P237's
`seat`/`ramp`, P254's return blend, this), which is now a rule for this tree:

> A settle (or a blend's tail) is not a wait to delete: it is the **start-up credit** the
> next leg spends. Measure the pair, never the segment.

## 3. What is left in `place`

* `place_clear` **0.78 s**, of which **0.43** is the measured clear (P259) and **~0.35** is
  bookkeeping between the lift and the leg. P227p measured the clear as the pear's
  protection, so the 0.43 is insurance, not slack.
* `place_blend` **1.08 s** = 0.75 (the blend, already trimmed 150 -> 90 in P259, and whose
  own arithmetic floor is 15-95 ticks for the measured range) + the 0.33 settle that §2
  just showed is load-bearing.
* The Cartesian **1.14 s** runs at `|v|cmd` **0.142** for a **5 cm** move, i.e. the
  jerk-limited profile's own average (0.142/1.875 = 0.076 m/s) - not a cap in sight.

**So `place` is at its measured floor** with the shipped profile; the only untested lever
left there would be the place **profile's speed**, and P88/P227r already measured that
negative (a faster place clock loses payloads on the marginal fruit).

## 4. Where the cycle stands

**9.71 s** (P262), **-28.3 %** over the arc from 13.55 s, at ~99 % placed. The blocks with
any remaining headroom are `rel_low` **1.23** (the accompanied descent at the profile's own
0.30 m/s cap) and `close` **1.10** (whose speed R11-B/P18b measured *positively* - a slower
close converts the carried class - so shortening it is contraindicated).

## 5. No-harm

The two marks are gated on `FRUIT_CYCLE_SUB` **and** `FRUIT_CYCLE_REPORT`, which the
acceptance does not set: `scripts/accept.sh` is **`fingerprint: matches
configs/motion_reference.json`** with its **459 `[fruit]` lines 459/459 identical** to
`logs/p227/accept_final.log`; `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)**; the
P260 leg's pin was extended to the seven sub-marks.

## 6. Pins

`tasks.py` **`e733c1f8`** (the two marks), `rl_env.py` (`TASKS_MD5` follow),
`scripts/selfcheck.sh`; references **`61fb5202` / `61fb5202` / `18b101bf`** untouched;
ckpt `p227_panda156`. Evidence `logs/p263/`.
