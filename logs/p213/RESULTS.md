# P213 probe - the two-camera conflict is the instance annotator, not the second camera

P135's two-camera build concluded "mere authorship of a second annotated camera takes the
first one's instance mask away" and listed a scene-pipeline fix as the blocker. This probe
separates the **camera** from the **annotator**: the wrist pair is authored with
`FRUIT_WRIST_ANNOTATORS=rgb,distance_to_image_plane` (no instance mask), and the head keeps
its own `rgb,distance_to_image_plane,instance_id_segmentation`.

Two episodes, same recipe, same seed 808; the head camera's own `[percept]` counters:

| arm | wrist cameras | head ep0 frames / rejected | head ep1 frames / rejected |
|---|---|---|---|
| head only | 0 | 18 / 300 | 255 / 12 |
| wrist RGB+depth | 2 | **18 / 300** | **271 / 12** |

The head's mask survives **identically** at episode 0 and within the branch at episode 1
(255 vs 271 is the attempt's own timing, not a mask loss). The P135 defect is the second
**instance_id_segmentation** render product, not the second camera. `FRUIT_WRIST_ANNOTATORS`
(default = the head's list) is the knob; unset is P135's list byte for byte.

**Not yet a policy result.** The direct env does not read the wrist sensor, and with no
instance mask there is no `_mask` to segment. The next step, if the owner wants a second
view, is a **goal-guided depth window** (project the head estimate into the wrist frame,
fit the depth patch) or a colour segmenter; neither is built. The probe only removes the
P135 blocker and says the head does not lose its mask.

**Pins.** `scene.py` **`a766b770`**, `scripts/276_p213_wrist_annotators_selftest.py`
**`4bcabbbd`**, `selfcheck.sh` **`cd9e728d`**; evidence `logs/p213/{head_s808.log,
wrist_s808.log}` and their manifests. `rl_env.py` is the P212 tree `b7a2698a`; no default
flipped.
