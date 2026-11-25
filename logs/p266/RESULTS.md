# P266 results: the stall guard cannot separate a slow convergence from a stall - and P265's y-sign reading is corrected

**2026-11-25, `logs/p266/`.** One default-off guard (PREREG pinned first), four cells, and
**two corrections** - one to this phase's own hypothesis, one to P265.

---

## 1. The guard, and why P1 fails

`FRUIT_CATCH_STALL_TICKS=60` (default 0): after `n` ticks, if the hand is **upstream** and
the residual has improved by **less than 0.5 mm** over those `n` ticks, the catch-up breaks.
`n = 60` is 2x the slowest converged catch measured (28), so a catch that would have made it
cannot be truncated by construction.

**Cells** (0.12, `FRUIT_TRACK_DIAG=1`, 20 picks x 2 seeds per arm):

| arm | placed | catches | `catch ticks` >= 100 |
|---|---|---|---|
| **C** (shipped) | **12/20 + 12/20 = 24/40** | 34 | **11** |
| **T** (guard) | **18/20 + 16/20 = 34/40** | 38 | **7** |

**P1 fails by its registered letter**: the stalled catches do **not** fall to <= 70 ticks -
T still carries **200-tick rows**. So the guard does not do the thing it was registered to
do.

## 2. It fails because there are **two** classes, and only one is a stall

The rows split by **magnitude**, not by sign:

| class | ticks | residual | `y` | outcome |
|---|---|---|---|---|
| **slow-but-converged** | **101-187** | **8.7-8.9 mm** (the normal value) | **+5.6..+6.0** (just outside the 6 mm axis window) | **places** |
| **true stall** | **200** | **47-55 mm** (one 1424 mm lost body) | **+47..+55** | **fails** |

Per arm: **C 10 true stalls and 1 slow-converged; T 3 true stalls and 4 slow-converged.**

**So the guard fires on the *slow-but-converged* class** (the residual plateaus at 8.8 mm
because `y` sits 0.0-0.1 mm outside the 6 mm exit), truncating a chase that **would have
placed** - and it **cannot** touch the true stalls, because those start 47-55 mm behind and
are genuinely chasing.

## 3. Correction to P265

P265 read the class as "**the hand is upstream (`y` positive) and cannot overtake**" and
used y's sign as the signature. **That is wrong**: the *normal* converged residual is
`y ~ +-5.8` (the sign varies with the approach side), so a positive `y` is what a **healthy**
catch looks like. What separates is the **magnitude**: **47-55 mm** is a stall, **5.8-8.9 mm**
is converged. P265's `157`/`187`-tick rows would have been called stalls; they are
**successes**.

**What survives from P265**: at 0.12 the arm's y-speed is the binding term (a 47 mm deficit
is 200 ticks of chasing - measured, and P243's 0.08 cells close the same deficit inside the
budget), and the arrival side is the lever. **What does not**: that the *sign* of `y` names
the class.

## 4. The count difference is a **branch**, and the phase says so

C 24/40 against T 34/40 is nominally p ~ 0.04, and it is **not attributable**: the two arms'
fruit sequences are identical for the **first 6 picks** and then re-draw (the guard changes
one catch's tick count, which changes the slot timing, which re-draws the supply). With P1
failing, the honest reading is the record's oldest one: **a count delta across a branch is
not the lever's**.

**So the guard is not adopted.** It is not *harmful* (T placed more, and the truncations are
on attempts that place), but its mechanism is a **clock on successes**, not a rescue, and it
was registered as the latter.

## 5. What the two classes actually need

| class | what it needs | status |
|---|---|---|
| **slow-but-converged** (8.8 mm, `y` a tenth of a mm outside 6) | an exit that does not wait for `y` to cross the last 0.1 mm | **a cheap candidate**: `FRUIT_DYNAMIC_CATCH_TOL` 6 -> 7 mm would exit these at tick ~20. Risk named: **P48 measured 6 mm as the grasp/no-grasp boundary**, so the test must carry the count |
| **true stall** (47-55 mm behind) | the **arrival side** (P109's window: more margin -> further upstream; less -> the bistable runaway) or a faster y-axis | **hardware / controller**, not a guard |

**So the guard closes, and the named next step is the tolerance**, which is a *different*
lever from the one P265 proposed.

## 6. No-harm

The knob is default-off and adds no `notes` entry (pinned): `scripts/accept.sh` is
**`fingerprint: matches configs/motion_reference.json`** with its **459 `[fruit]` lines
459/459 identical** to `logs/p227/accept_final.log`; `scripts/selfcheck.sh` **PASS (0
failures, 1 skipped)** with the new `P266 catch stall guard` leg.

## 7. Pins

`tasks.py` **`835ce78f`** (the guard + the knob), `rl_env.py` (`TASKS_MD5` follow),
`scripts/selfcheck.sh`, `logs/p266/PREREG.md`; references **`61fb5202` / `61fb5202` /
`18b101bf`** untouched; ckpt `p227_panda156`. Evidence `logs/p266/`.
