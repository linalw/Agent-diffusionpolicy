# P265 results: the 0.12 catch failures are **upstream arrivals** - and P264's "scheduling" reading is corrected

**2026-11-25, `logs/p265/`.** A diagnostic cell at 0.12 that corrects one sentence of P264
and names the mechanism. **No `src/` change.**

---

## 1. The correction, first

P264 wrote that the 12 pass-by losses are *"a scheduling property (the fruit reaches the
station while the arm is still on the previous pick)"*. **That is wrong, and the code says
so**: an episode ends on `fruit fell off the line` only when the **selected** fruit is
0.25 m below the belt top (`_episode_events`) - so the class is **the selected fruit was
missed in the catch and rode off the end**, not a fruit the selector should have refused.
The scheduling guard P264 proposed therefore has nothing to act on here.

## 2. What the catch actually does at 0.12

Two 10-pick cells at 0.12 with `FRUIT_TRACK_DIAG=1` (the `[catch]` rows carry ticks and the
residual's components):

| cluster | ticks | residual | components |
|---|---|---|---|
| **converged** (19 of 18 rows shown, both cells) | **20-28** | **7.8-8.8 mm** | `x ~ 0`, `y ~ -5.8`, `z ~ -6.5` |
| **stalled** | **200** | **10.6 / 12.8 / 27.9 / 28.7 / 37.6 mm** | **`y` POSITIVE** (+10.6 .. +37.6), `x ~ 0`, `z ~ -6.7` |
| one runaway | 200 | 1633 mm | a lost/recycled body (the P251 artefact) |

**The signature is unambiguous: the stalls are the rows where the hand is *upstream* of the
fruit** (`y > 0`, i.e. behind it on a belt that drives `-y`), and the converged ones all
have the hand **downstream** (`y ~ -5.8`). So:

* the fast cases are "the fruit arrives into the pads" (`y` slightly negative, the lead
  working as designed);
* the stalls are "**the pads are behind the fruit and cannot overtake the belt**" - at
  0.12 m/s the fruit moves 1 mm/tick, so a 30 mm deficit is 200 ticks of chasing, exactly
  the budget.

**And that is speed-dependent, which is why 0.08 does not show it**: at 0.08 the belt moves
0.67 mm/tick, so the same 30 mm deficit closes inside the budget (P243's cells: 21-42
ticks on 27 of 28).

## 3. So the 0.12 lever is the **arrival side**, with a known narrow window

The descent must end with the pads **at or just downstream of** the fruit. The knob that
moves it is `FRUIT_DYNAMIC_DESCEND_MARGIN` (the shipped **0.15 s**), and this cell's
measured window is the same one P109 mapped on the two-line:

* **more margin** -> the arm arrives further upstream -> **this failure**;
* **less margin** -> `past_aim` -> P109 measured a **bistable** outcome (converge, or run
  away to 233-269 mm) that cost **5 of 79** attempts and the placed count at **4 of 4
  seeds**.

So the window is real and narrow, and **the shipped 0.15 is already on the safe side of
it** - which is why the failure here is the *opposite* one (upstream, not past).

**What would move it without re-entering P109's bistability**: a **bounded downstream bias
with a guard**, i.e. aim a few millimetres past the fruit *and* abort/refuse when the
catch-up's `y` residual is positive and not shrinking (the loop currently spends the whole
200-tick budget on that case). That is a *reaction*, not a bias - and this record has
measured reactions before to be worth **−0 ticks but +15 % interval** when they re-draw the
slot loop (P103), so its registration must carry that price.

## 4. What this leaves as the 0.12 story

| | |
|---|---|
| converged catches | 20-28 ticks, 7.8-8.8 mm, `y ~ -5.8` (downstream) |
| stalled catches | 200 ticks, `y` **+10.6..+37.6** (upstream) - **the whole class** |
| the lever | the **descent's arrival side**, window narrow (P109), shipped 0.15 already safe |
| the mechanism sentence | **at 0.12 the pads must not end up behind the fruit: the arm cannot overtake the belt, and 200 ticks is not enough to try** |

## 5. Pins

No `src/` or `configs/` change (the tree is P263's: `tasks.py` `e733c1f8`, references
**`61fb5202` / `61fb5202` / `18b101bf`**, ckpt `p227_panda156`); `scripts/selfcheck.sh`
**PASS (0 failures, 1 skipped)**; `accept.sh` stands at P263's **459/459 +
`fingerprint: matches`**. Evidence `logs/p265/`.
