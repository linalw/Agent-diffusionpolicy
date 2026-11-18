# P214 result - the mask-free wrist depth window is not usable

P213 removed the P135 annotator blocker: an RGB+depth wrist camera leaves the head's
instance mask alive. The next question was whether the wrist depth is usable **without**
a mask. The probe projects the head's estimate into the wrist frame, samples a 35-px
depth disk and fits a sphere. Seed 808, one episode (the probe was stopped after the
first; the result is categorical):

| row | value |
|---|---|
| head `[percept] err` on the same ticks | **1.74-2.13 mm** |
| wrist `[wrist-depth] err` | **44.3-61.8 mm** |
| wrist `fit_r` | 55.5-73.2 mm (a 6.5 cm fruit's radius is 32.5 mm) |
| wrist `rms` | 10.2-12.0 mm |
| wrist `px` | 908-3188 (the disk is full) |

The depth disk is dominated by the **hand/fingers**, not the fruit: a 55-73 mm sphere
with a 10-12 mm rms is the pad/forearm, and the fitted centre is 4-6 cm away. The P135
wrist-only 3.54 mm result used the **instance mask** to select the fruit; with no mask,
a local depth window cannot separate the fruit from the hand. The head estimate is
already 1.7-2.1 mm, so this path is not a gain.

**Verdict: the mask-free depth window fails.** The remaining second-view options are a
**colour segmenter** (the fruit is coloured, the hand is grey/black) or a learned
mask-free detector; neither is built. The probe is default-off and reporting-only; it
does not feed the goal or the policy. The P213 annotator finding stands.

**Pins.** `rl_env.py` **`9c41fd7a`**, `scripts/277_p214_wrist_depth_selftest.py`
**`8cf07989`**, `selfcheck.sh` **`798761bf`**; evidence `logs/p214/wrist_s808.log`
(69 `[wrist-depth]` rows). No default change.
