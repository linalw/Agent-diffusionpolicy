# P210 pre-registration - temporal ensembling of the overlap

P209 measured that executing 2 of the 4-waypoint chunk doubles the re-plan boundaries
and makes the command tail **worse** (p95 0.101 -> 0.182, residual p95 0.110 -> 0.409,
count 4/6 -> 2/6). The classical remedy is not a shorter horizon but **averaging the
overlapping predictions**: the new chunk's first 2 waypoints and the previous chunk's
unexecuted `prev[2:4]` describe the same future ticks. ACT reports +3.3 points; RTC warns
that naive averaging can be worse when the policy is not parametric.

**Cell.** The P207 R5 recipe, `--execute-steps 2`, `FRUIT_POLICY_ENSEMBLE=0.5`, seed 808,
6 episodes. Controls are the same-batch P209 cells: E4 (execute 4) 4/6 and E2 (execute 2,
no ensemble) 2/6.

**Endpoints.** Emitted p95/max and >0.10 fraction, measured p95, the cap's binding and
residual, the close-latch tick, and the placed count. Falsifiers: F1 the tail does not
fall below E2 -> the average is inert; F2 placed <= 2/6 -> the overlap blend costs the
task; F3 the blend is worse than E4 on both the tail and the count -> keep E4.

A 6-episode count is a branch draw. A pass earns a seed-303 repeat and the full
WS-4.2 cell; no default is flipped.
