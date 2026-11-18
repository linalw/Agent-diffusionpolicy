# P209 pre-registration - execute half the predicted chunk

**Question.** The policy predicts a 4-waypoint chunk and the adopted recipe executes all
four (`--execute-steps 4`, one decision per 16 control ticks at `ACTION_HOLD=4`). The
action-chunk literature's measured rule is *predict long, execute about half*: the later
waypoints of a chunk are less informed by the current state, and the actuator gets no
feedback until the whole chunk is spent. Does executing **2 of 4** improve the command
tail / success under the P207 5.45 rad/s cap?

**Cells.** The P207 R5 recipe (`FRUIT_POLICY_TARGET_RATE=5.45`,
`FRUIT_POLICY_JOINT_CLAMP=1`, release endpoint, same servos), one simulator session per
arm:

| arm | `--execute-steps` | ticks per decision |
|---|---|---|
| E4 (control) | 4 | 16 (7.5 Hz) |
| E2 | 2 | 8 (15 Hz) |

Seed 808, 6 episodes per arm. If the mechanism moves and the count is not worse, repeat
at seed 303. The policy checkpoint is unchanged; this is a receding-horizon execution
choice, not a retrain.

**Mechanism endpoints.** Emitted per-waypoint step p95/max, the fraction of steps above
0.10 rad, the measured step p95, the cap's binding fraction and residual, and the
close-latch tick relative to the first policy tick. The wall cost is the extra model
calls: one `act` is ~26 ms at DDIM 16, so E2 doubles the inference duty; report it, do
not gate on it.

**Delivery.** Placed count (6 episodes = a branch draw; report only), the per-class
ledger, and the attempt span (ticks). Falsifiers: F1 the command tail does not move ->
executing half is inert; F2 placed falls by 2 or more at both seeds -> not adopted;
F3 the wall/sim ratio rises by more than 40 % with no success or smoothness gain.

**Read rule.** The chunk is trained at 4 waypoints; executing 2 is a standard receding
horizon, but the model's own later waypoints may carry information the first two do not.
No default is flipped; `--execute-steps` is a run parameter.
