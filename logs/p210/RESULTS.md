# P210 result - temporal ensembling rescues execute-2, but does not beat execute-4

Seed 808, 6 episodes per arm, P207 R5 recipe, the only differences the execution
horizon and `FRUIT_POLICY_ENSEMBLE` (0.5 = the new chunk's weight in the overlap):

| arm | placed | emitted p95 / max | >0.10 | residual p95 / max | binding |
|---|---|---|---|---|---|
| E4 (control, execute 4) | **4/6** | **0.101 / 0.182** | **5.2 %** | **0.110 / 0.626** | 25.2 % |
| E2 (execute 2, no ensemble) | 2/6 | 0.182 / 0.182 | 15.5 % | 0.409 / 2.021 | 45.4 % |
| **E2T (execute 2 + alpha 0.5)** | **4/6** | 0.122 / 0.182 | 6.5 % | 0.153 / 1.533 | 24.7 % |

**The classical remedy works in the direction it should**: averaging the overlapping
predictions recovers the execute-2 count (2/6 -> 4/6) and pulls the command tail and the
cap's residual back to near the execute-4 control. The mechanism is the overlap: the new
chunk's first two waypoints and the previous chunk's unexecuted `prev[2:4]` describe the
same future ticks, so a fresh stochastic sample no longer replaces the old prediction at
every boundary.

**But it does not beat execute 4.** The full 4-waypoint chunk is already a coherent
prediction; re-planning at 15 Hz and averaging in the older half costs the tail
(0.122 against 0.101) and the extra model calls, with no count gain (4/6 = 4/6). F3 fires
by its letter (E2T is worse than E4 on the tail and equal on the count): **keep E4**.

No source default changed; the knob is opt-in and the code path is off when unset. The
P209 negative and this positive-but-not-better result close the **chunk-length lane**:
the remaining smoothness lever is not a shorter horizon, and the remaining success
residual is the small-fruit/right-arm class, not the execution horizon.

**Pins.** `rl_env.py` **`8ec7c03e`**, `scripts/273_p210_ensemble_selftest.py`
**`b30c3660`**, `selfcheck.sh` **`2b88c0d2`**; evidence `logs/p210/E2T_s808.log` and
`logs/p210/manifests/p210_E2T_s808.json`. No default flipped, no reference moved.
