# P220 pre-registration - the small-fruit handover inside a continuous episode

P218/P219 placed the small class with the scripted skill (`FRUIT_SMALL_HANDOVER=1`) in the
per-episode loop; P204/P206 showed the continuous loop (`FRUIT_DIRECT_CONTINUOUS=6`) is a
different path, because a pick's `_finalize` has to start the next pick instead of ending
the episode. The question is whether the scripted skill's finalize also continues.

**Cell.** One continuous episode, 6 picks, seed 505, the P207 R5 recipe + small handover;
`--episodes 1 --continuous 6`. The control is P204's learned continuous 2/6
(`logs/video_p204`). Endpoints: the `[cont] pick k/6` rows (does the handover return to the
next pick?), the total placed, and the ticks. Falsifiers: F1 the episode ends at the first
small fruit (`[cont]` summary with picks < 6); F2 no small fruit appears in the 6 picks
(the route is untested); F3 the placed count falls below the learned continuous 2/6.
No default change; the continuous mode is opt-in.
