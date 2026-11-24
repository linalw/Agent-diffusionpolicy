# P245 results: the per-tick subtraction is exonerated - and the remaining association has no mechanism

**2026-11-25, `logs/p245/`.** The control P244 named: `FRUIT_TRACK_DIAG=1` with the
residual's components computed **once, at the loop's exit** (no per-tick
subtraction) and the axis exit **off**. 12 attempts, both seeds.

---

## 1. The cells

| | value |
|---|---|
| catches | 12 |
| normal residuals | **6.5-6.7 mm at 200 ticks** (the shipped floor, P239) - two at 27-28 ticks |
| **excursion** | **54.5 mm** (`x=+39.2 y=-36.0 z=+12.2`), 200 ticks |
| placed | **5/6 + 6/6 = 11/12** |

**The excursion survives the instrument change.** P244 suspected the per-tick
`tip - desired_tip` subtraction of perturbing the first catch; it is computed at the
exit now, and a 54.5 mm excursion still appears - on **the same attempt as every
other one: seed 901, episode 0, the first catch of the run**.

**So the instrument is exonerated**, and P244's own suspicion is refuted by its own
control. That is the outcome the phase was for.

## 2. The association that is left, and why it is not a cause

Every excursion across P241-P245 is the **first catch of seed 901's run**:

| phase | seed-901 catch #0 | seed-902 catch #0 |
|---|---|---|
| P241 (shipped + field) | **41.6 mm** | 5.8 (fine) |
| P242 (`Z_FF`) | **419.1** | 5.8 (fine) |
| P243 (axis exit) | **97.2** | 7.1 (fine) |
| P244 (axis + trace) | **1079.4** | 7.1 (fine) |
| P245 (diag only) | **54.5** | 6.0 (fine) |

**5 of 5, all at seed 901's first attempt, none at seed 902's** - and P236-P240,
which ran seed 901 without `FRUIT_TRACK_DIAG`, show **0/6** at the same position.

That looks like a perfect separation, and **it has no mechanism**: on the direct
lane `_track_diag` gates exactly two things, and neither can reach the first
catch-up -

1. `_track_row` is called from **`note_result`** (`tasks.py:4071`), which the direct
   path never runs;
2. the `[catch]` row prints **after the loop it would have to perturb**.

A print issued after the fact cannot move the ticks before it. **So the association
is recorded as unexplained, not as a cause.** Five of five at p = 0.5 is 1 in 32 -
unlikely, and still not a mechanism.

## 3. What the arc establishes, with the excursion out of the way

| | |
|---|---|
| the catch-up's exit is a **6.6 mm vertical steady-state error** | P241, `(y=+0.5, z=-6.6)` |
| so the shipped loop exits on its **200-tick budget** | P239, 1.67 s |
| the **axis-aware exit** recovers **1.44 s** on 11 of 12 with the command untouched | P243 |
| the excursion is **not** the component field | this phase |
| the excursion is **not** the command offset (it appears with the shipped command) | P243/P245 |
| the excursion **is** seed 901's first catch in every cell that counts it | P241-P245 |

**So the 1.44 s recovery stands**, and the only open object on this axis is **seed
901's first catch**, which is a **scenario/initialisation** object, not a lever
object: it appears once per run, at the first episode, on one seed, and it costs
0-1 placement.

## 4. The next step, stated plainly

It is an **initialisation** question, and the instruments for it already exist:
`FRUIT_DIRECT_START_ALIGN` / the start-pose family (P227y/P227z), the reset's
teleport-plus-settle, and the tracker's first measurement (`FRUIT_TRACK_MEAS_WAIT`,
P135). The cheapest discriminator is a **1-episode cell per seed** with the cycle
report: the cycle's `descent` for episode 0 will show whether the arm started from
the family pose or from a teleport. **Not run in this phase** - the session's
remaining budget is better spent recording what is established than opening a sixth
sub-arc on one seed's first attempt.

## 5. Pins

`tasks.py` **`9ce34845`** (the components at the exit; no per-tick subtraction),
`rl_env.py` `TASKS_MD5` follow; references **`61fb5202` / `61fb5202` / `18b101bf`**
untouched; checkpoint `p227_panda156`. Evidence `logs/p245/diag12/`.
