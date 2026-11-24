# P240 results: the catch-up's residual is not a following *lag* - the lead does not move it, and a larger lead runs away

**2026-11-24, `logs/p240/`.** Measurement only (env knob). **P1 falsified.**

---

## 1. The cells

`v=0.08`, `FRUIT_CYCLE_REPORT=1` + `FRUIT_TRACK_DIAG=1`, seed 901 x 3.

| arm | `FRUIT_DIRECT_CATCH_LEAD` | `[catch] residual` | `catch ticks` | `seat` | placed |
|---|---|---|---|---|---|
| C | 0.25 (shipped) | 6.7 / 6.6 / 6.7 mm | 200 / 200 / 200 | 1.67 x3 | **3/3** |
| T | **0.33** (+82 ms) | **102.3** / 6.6 / 6.7 mm | 200 / 200 / 200 | 1.67 x3 | 2/3 |

## 2. P1 falsified, and the way it failed says what the residual is

The lead was moved by exactly the measured lag (6.6 mm / 0.08 m/s = 82 ms).
**The residual did not move at all** (6.6 and 6.7 mm on the two attempts that
behaved), and **one attempt ran away to 102.3 mm**, cost a placement, and kept
`seat` at its 1.67 s cap.

**So the residual is not a time lag in the belt direction.** A pure following lag
would shrink when the lead is extended; this one is invariant to it, which means
its dominant component is somewhere the lead does not touch - and the loop breaks
on the **norm** of a 3-D error.

## 3. The hypothesis this leaves, and its instrument

The stop point is `fruit + [0, 0, standoff]` (P227o's fix: the arm's own
`_pad_standoff`, 42 mm on this hand). **A 6.6 mm error there is a z error as
easily as a y one** - the hand's vertical tracking at the grasp aim, which is the
direction the lead cannot influence. That is consistent with everything measured:

* the residual is a **floor** (6.6-6.7 mm) that no lead change moves;
* it is **0.6 mm above** a tolerance that was set at a round 6 mm;
* the loop therefore always exits on its budget, and (P239) `seat` is bimodal only
  because two attempts happened to cross 5.7-5.8 mm.

**The instrument is one field**: print the residual's **components** in the
`[catch]` row (`residual=6.6mm (x=.. y=.. z=..)`). It is one subtraction on arrays
the row already has, and it decides between "the lead is still wrong" (y) and "the
hand cannot reach the commanded standoff" (z). **Not added in this phase** - it is
the next cell's first step, and adding it here would have meant guessing again.

## 4. What the phase does close

* **The lead is not the lever**: +82 ms of lead leaves the residual identical and
  the block at its cap, while overshooting on one attempt (102.3 mm, 2/3 placed).
  The docstring's own sentence ("a 0.18 s lead left the tip riding ~6-7 mm behind
  the fruit") is a **description of the floor**, not a prescription for its cure -
  the 6-7 mm is reproduced at two different leads.
* **The reach cap is load-bearing**: `FRUIT_DIRECT_CATCH_MAX = 0.035 m` downstream
  is what the overshoot ran into, and it is why the failure appears as a runaway
  rather than a gentle bias.

## 5. The cycle picture is unchanged

`seat` 1.67 s on 6 of 6 attempts here (all three seeds' attempts in both arms),
i.e. the 1.44 s tax stands. Its cause is now narrowed to **an error component that
the belt-direction lead does not touch**, with a one-line instrument named.

## 6. Pins

No `src/` change; `tasks.py` **`e72b2c7c`**, `rl_env.py` unchanged by this phase;
references **`61fb5202` / `61fb5202` / `18b101bf`** untouched; checkpoint
`p227_panda156`. Evidence `logs/p240/{PREREG.md, C/, T/}`.
