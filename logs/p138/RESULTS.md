# P138 results - the recollection on the flipped tree

## 1. The store

| | |
|---|---|
| cell | the shipped **two-line**, the tracker on (`track=1(default)`), the P136 catch |
| episodes | **45** (left 23 / right 22) |
| windows | **8,847** |
| index audit (`106`) | `entries=45 files=45 index_frames=9612 file_frames=9612 unique_content=45 OK` |
| manifest | carries **`physics.tracking`** (`origin: default`, `mode: cv`, `gate 0.04`, `tau 0.3`) - a store recorded under the pre-P136 catch reads `origin: scope-off`/absent |
| wall | 2,444 s (24 shard-minutes at ~54 s/episode) |

The collector's own summary shows the two-line's stations working
(`[biarm] two-line scheduler: left y=+0.000, right y=-0.100`) and its right arm
starving at the end of the run (`no eligible fruit` after 634 s) - the same
drained-belt tail the record already documents.

## 2. The fine-tune

`moe_v13s` (`61da390a`) + `demos_v11` (50 episodes) + `p138_track` (45), 6 epochs,
lr 5e-5, `ones`, base-weight 1.0 -> **`checkpoints/p138_track/policy_best.pt`**
(`316f8dd3`). Final epoch: weighted loss **0.0205**, router **0.992**,
demo_val **0.0121** - the candidate learned the store (it does not sit at the
router's initial 0.82).

## 3. Fidelity (offline - a diagnostic, not a measurement)

`119_rl_fidelity`, 192 windows, DDIM-16, fixed per-window noise:

| slice | base `moe_v13s` | candidate `p138_track` |
|---|---|---|
| overall | 0.240 rad / fing 0.0016 / phase 93 % | **0.138 rad / 0.0008 / 94 %** |
| approach | 0.135 | **0.083** |
| grasp | 0.335 | **0.165** |
| lift | 0.275 | **0.179** |
| place | 0.297 | **0.173** |
| paired delta | - | **median -0.067 rad, 155 improved / 37 worse, sign p < 0.0001** |

So the candidate is **0.57x** the init's action error on this store's own windows.
That says the store was learned; it says nothing about the cell.

## 4. The canary (a smoke, not a rate)

Init vs candidate, the same interface (the hybrid, which P136 leaves on the
pre-tracker catch) and the same seed, 3 episodes each:

| arm | result | reasons |
|---|---|---|
| `moe_v13s` (init) | **2/3** | baseline only, PASS |
| `p138_track` (cand) | **2/3** | baseline only, PASS |

**No discrimination at n = 3** - the canary's recorded spread is 5-8/10, so three
episodes cannot separate the arms, and a tie is the only honest reading.

## 5. What is not done, and what it costs

* The **direct A/B** (`112_rl_ab.sh`, N = 5 x 15, the WS-4.2 protocol with the
  carried-class pairing) - **1.5-2 h**, and the tree already carries three nulls
  on this interface (W7-C/W8-A, R9, P37). Named, not run.
* A **150-200-episode store** for a rate - this one is 45, which is enough to
  learn (the fidelity says so) and not enough to call a rate.
* `accept_policy.sh`'s default checkpoint is **unchanged** (`moe_v12`): the
  candidate is an artefact, not a default.
