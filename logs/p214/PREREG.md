# P214 probe - a mask-free wrist depth read guided by the head estimate

P213 showed that an RGB+depth wrist camera leaves the head's instance mask alive; the
blocker was the second instance annotator. The next question is whether the wrist depth
is usable **without** a mask. The probe projects the head's own estimate
(`_percept_pos`) into the wrist camera, samples a disk of depth pixels around the
projection, fits a sphere and prints `[wrist-depth]` with the fit's error against the
truth. It is a **bench**: it does not feed the goal or the policy.

Cell: the P207 R5 recipe, `FRUIT_WRIST_CAMERA=1`,
`FRUIT_WRIST_ANNOTATORS=rgb,distance_to_image_plane`, `FRUIT_WRIST_DEPTH_PROBE=1`,
`FRUIT_PERCEPTION_DIAG=1`, seed 808, 2 episodes. The head-only control is P213's head cell.

Endpoints: the wrist `err` vs the head `err` on the same ticks; the wrist `px` (the depth
points in the disk), `fit_r`, `rms`; and whether the head's `[percept]` counters survive
the extra wrist render. A pass (wrist err <= head err on the same tick, px >= 30, head
frames not lost) earns an integration cell; a fail closes the mask-free second view.
