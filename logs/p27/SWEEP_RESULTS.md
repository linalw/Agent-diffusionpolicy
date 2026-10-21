# P27 results: the belt-speed premise, the sweep, and the shipped speed (2026-10-21)

Status: **the owner's premise is not supported as stated: the encoder is a *schedule parameter*,
not a model adaptation; the policy never sees the belt speed; and the slower side reads
speed-FLAT, not better.** "Does not degrade down to 0.08" is supported; "improves" is not. The
0.15 is negative on the single-arm acceptance and the two-line patch on the current tree, so the
shipped speed is **0.12** (the P26 flip to 0.15 reverted, `c35775a`).

## 1. The audit (P27-A, `logs/p27/SPEED_ADAPT_AUDIT.md`)

* **The encoder is not a measurement in this build.** With the cleats off (the shipped default)
  `Conveyor.step` returns before the encoder update, so `encoder_speed == cfg.belt_speed`; the
  runner's own stats line self-reports `no cleats to measure travel`. What the value feeds is the
  **schedule**: `should_fire`'s `t_arrive = dy/v <= lead`, the catch lead, the selector floor, the
  descent deadline, the ACQ reach - every term `v x (fixed seconds)`.
* **A slower belt gives the hand no extra time.** The handover starts 1.325 s before arrival at
  every speed by construction; the fixed-seconds form cancels the speed out of the *time* budget.
* **The policy never sees the speed**: the observation is 2x128x128 RGB-D(+mask) + 25-D proprio
  + 8-D goal; the only speed-correlated scalar is `goal[3:6]` (the target's measured velocity at
  selection, the 0.06-centred normaliser). The learned close is a *distance* criterion. In the
  shipped policy handover the primitive is the indexed pick (the belt stopped).
* **The escape is not belt-fed**: the dominant direct failure (carried-not-placed) is a
  hand-frame slide of 17.9-957 mm (median 278 mm) over ~0.21 s; the belt can feed at most
  `v x 0.21 s` = 24 mm at 0.12 / 17 mm at 0.08 (<= 10 %).

## 2. The direct/policy sweep (the belt speeds, seed 77, 15 episodes each, the ACQ env)

| speed | placed | no-grasp | carried | close-start \|y\| p50 | median escape | belt-fed share |
| --- | --- | --- | --- | --- | --- | --- |
| 0.08 | **6/15** | 1 | 8 | 3.3 mm | 270 mm | 6-11 % |
| 0.10 | **6/15** | 0 | 9 | 3.3 mm | 298 mm | 6-11 % |
| 0.12 (training) | 2/15 | 1 | 12 | 3.7 mm | 279 mm | 6-11 % |
| 0.15 | **5/15** | 0 | 10 | 2.9 mm | 251 mm | 6-11 % |

**No pairwise Fisher test reaches p < 0.215** (the 0.12 point is the low draw; the record's own
0.12 at seed 77 reads 4/15). The honest read: **speed-flat within the draw.** The dominant
failure is the carried class at every speed (8-12/15), the belt-fed share of the escape is 6-11 %
everywhere - the mechanism the audit predicted. The close-start sits at 3.3-3.7 mm (no material
speed trend; the 0.15's 2.9 is a draw).

## 3. The 2x2 isolation (the single-arm acceptance) and the two-line

| belt | flip | acceptance |
| --- | --- | --- |
| 0.12 | off (shipped) | **9/10** |
| 0.12 | on | 7/10 |
| 0.15 | off | **5/9** |
| 0.15 | on | 3/9 |

The belt alone costs -4 at 0.15 (the flip -2; together -6). The two-line patch at 0.15 on the
current tree: **34/60** (s11 10, s5 12, s23 12) vs the 0.12 mass base **45/60** (11/17/17). The
two-line scripted curve (seed 11, 20 attempts each): **0.08 13/20** (nc 4, carried 3),
0.10 11/20, 0.12 11/20 (the mass base), 0.15 10/20 - **the slow side is >= the training
speed (weakly, +2 at 0.08) and the fast side < (-1)**. The scripted catch benefits where the
policy cannot: the capture physics (a slower fruit, a wider catch window, less momentum in
the loaded slide); the schedule's fixed-seconds form cancels the speed out of the handover
timing, so the gain is physical. Single runs per point; the +2 is at branch scale, reported,
not gated.

## 4. The verdict and the named fixes

**Shipped speed: 0.12** (the default restored; the sweep env sets speeds explicitly for tests).
The owner's premise, made precise by this phase: to get a *model* adaptation the build needs
(a) a real encoder (the cleats on, or a measured surface speed) and (b) a speed channel in the
policy's observations with training across speeds - today "the encoder adapts" means the
`FRUIT_BELT_SPEED` value is threaded through the schedule, and the policy is blind. The measured
slow-side facts are the *costs* (a 1.5x arrival cadence, a longer hover wait, a 1.5x recycle
loop) against a flat success.

**Provenance gap found and to fix**: no run or collection manifest records the belt speed (the
goal's `vy` is the only witness). The collector's manifest should carry `supply.belt_speed` (the
W7-B guardrail pattern) before any speed-scoped dataset is collected.

## 5. Provenance

* The audit: `logs/p27/SPEED_ADAPT_AUDIT.md`; the sweep: `logs/p27/{20..23}_direct_*.log`,
  `{30,31}_twoline_*.log` (chain `run_p27.sh`; driver `90_driver.log`); the read
  `logs/p27/read_sweep.py`.
* The isolation/acceptance: `logs/p27/10_acc_012_flip.log`, `11_acc_015_noflip.log`; the P26's
  `logs/p26/10_accept_015.log` (3/9) and the patch `logs/p26/2*_patch015_seed*.log`.
* Pins: `tasks.py` `b54b5406`, `assets.py` (0.12 restored), `rl_env.py` followed.
