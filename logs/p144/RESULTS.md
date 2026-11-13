# P144 - the head camera, measured, and what a recollection does

The owner's brief: choose a camera placement on the **whole cycle** (approach, grasp,
place), then collect enough data, train and test.

## 1. The placement search (`logs/p143/camera_search.py`)

The scripted line is run for two attempts; every 8th tick the fruit's centre is
projected into each candidate camera and its **depth** read. The depth at the centre
pixel is the fruit's own surface, so `visible` is `shortfall <= radius + 20 mm`.

155 samples, one placed attempt and one failed:

| camera | eye -> target | **all** | approach | place |
|---|---|---|---|---|
| **head_now (shipped)** | `(0.05,0,2.00) -> (0.34,+0.22,1.10)` | **14.6 %** | 27.8 % | **0.0 %** |
| **down_x_160** | `(1.60,0,2.00) -> (0.34,0,1.15)` | **81.4 %** | **83.0 %** | **79.5 %** |
| **down_high** | `(1.20,0,2.30) -> (0.40,0,1.15)` | 78.8 % | 85.2 % | 71.1 % |
| down_x_140 | `(1.40,0,1.75) -> (0.34,0,1.20)` | 68.1 % | 56.8 % | 75.4 % |
| corner_neg | `(1.15,-0.95,1.95) -> (0.36,0.05,1.15)` | 56.5 % | 57.4 % | 55.7 % |
| down_x_120 | `(1.20,0.10,1.55) -> (0.30,0.02,1.18)` | 54.4 % | 52.3 % | 57.1 % |
| side_y_pos | `(0.34,1.30,1.70) -> (0.34,0,1.18)` | 53.0 % | **0.0 %** | 82.5 % |
| corner_pos | `(1.15,0.95,1.95) -> (0.36,0.05,1.15)` | 42.7 % | 25.9 % | 57.1 % |
| side_y_neg | `(0.34,-1.30,1.70) -> (0.34,0,1.18)` | 38.0 % | 59.3 % | 22.7 % |

**The shipped top-down camera sees the fruit 14.6 % of the cycle and 0 % of the
place** - the arm is between the lens and the fruit exactly when it matters (a
standalone probe measured a **31 mm** depth at the fruit's pixel at the grasp).
**A downstream camera at `(1.60, 0, 2.00)` aimed at `(0.34, 0, 1.15)` sees 81.4 %**,
and it is the only candidate that is good in **both** halves.

## 2. The camera becomes a measured option

`assets.head_camera_override(cfg)` + `FRUIT_HEAD_CAMERA`:

* unset -> the configuration's own pose, **byte-identical** (the acceptance is
  **7/10, `fingerprint: matches`, 459/459 `[fruit]` lines**);
* `down_x_160` / `down_high` / `down_x_140` -> the measured poses; an unknown name
  **raises**;
* the store manifest gains `scene.head_camera = {name, eye, target}` - a store
  recorded through a different camera is now identifiable (a manifest without the key
  predates P144).

## 3. The recollection and the retrain

* **45 episodes** through `down_x_160` (single arm, seed 3, 240x424, 103 attempts,
  **44 % success**, 482 MB) into `datasets/p144_down`;
* fine-tune from `moe_v13s` on that store, **`--base ""`** (the anchor `demos_v11` is
  the **old view**, so it must not be mixed), 8 epochs, loss 0.0198 ->
  `checkpoints/p144_down`;
* evaluation, 12 episodes (seeds 77/101/202), same camera: **0/12**.

## 4. The result is not attributable to the camera, and the control says why

| arm | camera | store | n | success | `gap_min` |
|---|---|---|---|---|---|
| shipped `moe_v13s` | top-down | `demos_v12` (two-line) | 24 | **9/24 = 37.5 %** | 147-155 mm |
| `p144_down` | **down_x_160** | 45 ep single-arm, **no anchor** | 12 | **0/12** | 147-228 mm |

The new checkpoint still **closes at the same distance** (147-155 mm on most
episodes), so the model's own close survived the new view - but it **places
nothing**. Three things changed at once: the camera, the store's **distribution**
(45 single-arm episodes at seed 3 instead of the two-line `demos_v12`) and the
**anchor** (none, instead of `demos_v11` at weight 1.0). **The camera cannot be
credited or blamed from this cell.**

**The control that isolates it** is the same recipe on the **old** camera: 45
single-arm episodes through the shipped pose, `--base ""`, 8 epochs, 12 episodes. It
was not run (~2 h) and is the next cell.

## 5. What is settled regardless

* the **placement question is answered** - 14.6 % -> 81.4 % visible, with the place
  phase going 0 % -> 79.5 %;
* the **cost of a camera change is now one env var plus a recollection** (the
  override, the provenance key, and 45 episodes in ~30 min);
* the policy's condition is `goal` (truth) + image, so the occlusion costs
  **appearance**; a camera that sees the fruit is worth having only if the appearance
  channel is what limits the task, which the control above decides.

## 6. The control: the same recipe on the **shipped** camera is also 0/12

`logs/p144/run_control.sh`: 45 single-arm episodes through the **top-down** pose
(same seed 3, same **103 attempts**, 44 % success), fine-tune from `moe_v13s` with
`--base ""`, 8 epochs, 12 episodes.

| arm | camera | n | success | `grasped` | `gap_min` |
|---|---|---|---|---|---|
| shipped `moe_v13s` (no retrain) | top-down | 24 | **9/24 = 37.5 %** | 13/24 | 147-155 mm |
| `p144_down` (retrained) | **down_x_160** | 12 | **0/12** | 2/12 | 147-228 mm |
| **`p144_up` (retrained, control)** | **top-down** | 12 | **0/12** | **0/12** | 141-228 mm |

**Both retrained arms are 0/12 and the control does not even grasp** - so the cell
measured the **recipe**, not the camera: fine-tuning from `moe_v13s` on 45
single-arm episodes with **no anchor** overwrites the policy that made the shipped
checkpoint work (it grasps 13/24), and it does so identically through either view.

**This is the answer to "does the camera matter at this recipe": no measurable
effect, because neither retrained arm can grasp.** The camera question is therefore
still open, and the cheapest way to close it needs **no training at all** (section 7).

## 7. Zero-shot: the shipped checkpoint through a camera it never saw

`moe_v13s` was trained on the top-down view. Running it **unchanged** through
`down_x_160` isolates "does this model use the image at all":

* if it reads near 9/24, the view is irrelevant to the policy (the goal carries the
  truth position) and a camera project has no lever;
* if it collapses, the view matters and a **proper** recollection - same distribution
  as the shipped store (two-line), **with** the anchor - is the price.

## 8. Zero-shot through the new camera: 4/12 - the same as the old view

`moe_v13s` **unchanged** through a camera it never trained on (`down_x_160`), 12
episodes, seeds 77/101/202:

| arm | camera | training | n | success | `grasped` | `gap_close` behaviour |
|---|---|---|---|---|---|---|
| **`moe_v13s`** | **top-down (trained)** | - | 24 | **9/24 = 37.5 %** | 13/24 | 147-155 mm |
| **`moe_v13s`** | **down_x_160 (unseen)** | - | 12 | **4/12 = 33.3 %** | **7/12** | 149-150 mm |
| `p144_down` | down_x_160 | 45 ep, no anchor | 12 | 0/12 | 2/12 | 147-228 mm |
| `p144_up` | top-down | 45 ep, no anchor | 12 | 0/12 | 0/12 | 141-228 mm |

**The shipped checkpoint works through a view it has never seen**, at the same rate
within noise (33 % against 37.5 %), still closes at 149-150 mm, and grasps 7 of 12.
So **the policy's behaviour is not limited by the camera** - which is what its
conditioning implies: the `goal` is the **truth** position, velocity and diameter, and
the image only contributes appearance.

**The camera question is therefore closed as a policy lever**:

* the **placement** is measured and much better (14.6 % -> **81.4 %** of the cycle
  visible, the place phase 0 % -> 79.5 %);
* it **does not move the task** (4/12 unseen against 9/24 trained), and it is worth
  having for **watching and for the video artifacts**, not for the success rate;
* the 0/12 arms were **destroyed by the recipe** (45 single-arm episodes, no anchor),
  on either camera - so no conclusion about the view can come from them, and none is
  drawn.

**What would make the view matter**: a policy conditioned on the image *only* (no
truth goal) - i.e. the perception lane of P135 - where the occlusion that P135 measured
(48 -> 22 px at the grasp) and the 31 mm depth at the fruit's pixel become binding.
That is a different interface, and its instrument (the tracker at 1.98 mm) already
exists.
