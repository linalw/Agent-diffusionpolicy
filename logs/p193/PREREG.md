# P193 pre-registration: verification of the adopted direct-policy recipe at fresh seeds

Written **before** any cell is run. The rule below is the one that will be applied; a cell
that misses it is recorded as a miss, not re-read.

## The claim under test

`docs/DIRECT_POLICY.md` §3: the adopted recipe places **68.8 %** (22/32) over four seeds
(303, 505, 606, 707), with two of those fresh for the setting. The whole lane's history in
this record is that a fresh-seed pair gives back part of a gain, so the number to verify is
**the pooled rate at seeds never used in this lane**, not the best cell.

## The recipe (pinned; nothing else changes)

`checkpoints/p177_full`, `FRUIT_IMAGE_FOVEA=64`, `FRUIT_DIRECT_START=wait`,
`FRUIT_DIRECT_START_ALIGN=family`, `FRUIT_SKILL_LIFT_RAMP=1`, `FRUIT_CLOSE_RAMP_DY=0.014`,
`FRUIT_POLICY_PHASE=perception` + `checkpoints/p146_phase/phase.pt`,
`FRUIT_POLICY_ACTION_HOLD=4`, `--execute-steps 4 --horizon 2600`, the shipped mixed supply,
plus:

```
FRUIT_CONTACT_SERVO=1 FRUIT_CONTACT_SERVO_LEAD=0.10 FRUIT_CONTACT_SERVO_LEAD_RIGHT=0.20
FRUIT_PLACE_SERVO=1 FRUIT_PLACE_SERVO_VMAX=0.20 FRUIT_FINGER_MAXFORCE_DIRECT=60
FRUIT_SCORE_ENDPOINT=release
```

## The cells

Seeds **808** and **909** (neither used anywhere in this lane), 8 episodes each = **16**.
The loop is not reproducible, so every count is a branch draw; the pooled read is the
statement.

## Endpoints and the decision rule

* **Primary**: pooled `placed` over the 16. **Verified** iff pooled >= **10/16 (62.5 %)** -
  i.e. the interval's floor, not the point estimate - **and** neither seed below **3/8**.
* **Secondary (reported, not gated)**: per-arm `placed`/`grasped`; the failure-reason
  classes; the attempt tick p50 (the throughput price); `[close]` `xy`/`dz`.
* **Falsifier**: a pooled read <= 8/16 (50 %, P182's per-arm-lead rung) means the 68.8 % was
  a draw of the same family and the record must say so.
* **Not a rate**: even a pass is a 16-episode pooled count; a formal certificate needs
  P93's ~364 attempts/arm and is a separate registration.

## What is deliberately *not* claimed

No claim about the shipped defaults (nothing was flipped), about the scripted line (it never
constructs `SortingRLEnv`), or about a checkpoint other than `p177_full`.

## Second, separate question in the same batch (declared, not gated)

`FRUIT_FINGER_FACE=v2` (a **recessed groove across the plate**, i.e. a valley running along
the belt) on the all-right arm, 4 episodes at seed 202: the hypothesis is that it cradles a
payload that arrives at `dlat` 19-26 mm, which is the right arm's term. Prior against it:
the `p3face` phase measured `v2` as worse than flat on the **scripted** line (3/10 vs 6/10)
and P132 closed the pad *shape* family on a static pull - but neither measured `dlat`
containment on the direct path. Reported as a direction only; **not adopted** without a
four-seed read.
