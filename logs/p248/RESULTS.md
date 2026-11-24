# P248 results: the powered cell passes on quality, mechanism and cycle - the axis exit is a candidate default

**2026-11-25, `logs/p248/`.** 2 arms x 2 seeds x **20 episodes = 40 attempts per
arm**, identical instrumentation on both. `PREREG.md` pinned before the cells.

---

## 1. The cells

| | C (shipped 3-D norm) | **T (axis exit)** |
|---|---|---|
| **placed** | **38/40 = 95.0 %** | **40/40 = 100 %** |
| catch-up ticks (median) | **200** (35 of 40 > 100) | **21** (max 79; **0 of 40 > 100**) |
| `seat` median / p90 | **1.67 / 1.67 s** | **0.17 / 0.35 s** |
| `[cycle] total` median | **13.55 s** | **12.13 s** |
| episode ticks (mean) | 2053 -> **17.11 s/attempt** | 1888 -> **15.73 s/attempt** |
| runaways (`residual > 50 mm`) | **1** (1113.7 mm) | **0** |

## 2. The registered verdicts

* **P1 (quality non-inferiority) PASSES, and the direction is favourable**: T
  placed **40/40** against C's **38/40**. The bar was `T >= C - 2`; the observed
  difference is **+2**, which at n = 40 is **a draw, not an improvement** (Fisher
  p = 0.49) - so the claim is **"no quality cost at 40 attempts"**, not "better".
* **P2 (mechanism) PASSES on both numbers**: ticks median **21** (bar <= 45) and
  `seat` median **0.17 s** (bar <= 0.40), against 200 and 1.67 in the control.
  **35 of 40** control catches ran the full budget; **none** of the 40 treatment
  catches did.
* **P3 (cycle) PASSES with room**: `[cycle] total` **13.55 -> 12.13 s = -1.42 s**
  (bar >= 0.8) and the independent episode-ticks reading **-1.38 s/attempt**
  (17.11 -> 15.73). The two agree to 0.04 s.
* **P4 (the open class, reported not gated)**: the **control** arm carries the
  runaway (**1113.7 mm**), the treatment has **none**. That is one more confirmation
  of P246's conclusion: **the excursion is not the lever's** - it appears on the
  shipped command at the same rate it appears anywhere.

## 3. What the phase establishes

**The 1.44 s is real, it is 6.6 mm of vertical droop (P241), and the axis-aware
exit removes it at no quality cost in 40 attempts per arm, with the command
untouched and no excursion.** The three bars P243/P247 could only suggest from 26
attempts are now met at 40 per arm.

**What it does not establish**: that the flip is free. The knob is read at task
construction, so a default moves **every** path - the scripted acceptance, the
two-line session and the collector - and the record's price for that is the
**two-line gate (`scripts/190_twoline_gate.sh`), both motion references re-recorded
from same-batch runs, and every store re-baselined**. That is a separate, priced
step, and it is the **owner's decision** (the objective's owner, not this phase).

## 4. The recommendation, with its price

**Propose the flip**, on: 40/40 vs 38/40 (non-inferior), 200 -> 21 ticks on 40 of
40, cycle -1.42 s (-10.5 %), no excursion in the treatment arm.

**Price if taken**: two references re-recorded (both two-line-side files at
`61fb5202` today, plus the single-arm `18b101bf` is untouched by this knob only if
the scripted single arm is scoped out - which it is **not** today), the acceptance
re-based, the two-line gate re-run, and stores re-baselined. **A scoped form**
(`two_line`/`direct` only, the `_dynamic_profile` pattern P87/P88/P89 used) would
avoid the scripted acceptance entirely and is the cheaper flip - **named, not
built**.

## 5. Pins

No `src/` or `configs/` change; `tasks.py` **`9ce34845`**, `rl_env.py` unchanged by
this phase; references **`61fb5202` / `61fb5202` / `18b101bf`** untouched;
checkpoint `p227_panda156`. Evidence `logs/p248/{PREREG.md, C/, T/}`.
