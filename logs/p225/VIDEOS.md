# P225 videos (on the media drive; the MP4s are not in git)

All clips use the **P225 no-scripted-skill recipe** (the small/right handover
routes off, the nearest-above-floor selector, `FRUIT_SCORE_ENDPOINT=release`,
the contact/place servos, `checkpoints/p177_full`), 0.12 m/s, camera 240x424.
Each directory holds `observer.mp4`, `head.mp4`, `gripper.mp4`, `overhead.mp4`,
`side_by_side.mp4` and `video.json`.

| clip | seed | outcome | duration | path |
|---|---:|---|---:|---|
| `p225_p177_continuous` | 303 | **6 picks, 5 placed** | **62.6 s** | `/media/ubuntu/66A27065A2703B9D/project/Agent-diffusionpolicy/log/video/p225_p177_continuous` |
| `p225_p177_demo` | 77 | 2/6 separate picks | `video.json` | `.../p225_p177_demo` |
| `p225_p177_demo_s303` | 303 | 1/6 separate picks | `video.json` | `.../p225_p177_demo_s303` |
| `p177_adopted` (pre-P225) | - | 4/6 | `video.json` | `.../p177_adopted` |

The continuous clip is the strong one: one episode, six picks back to back
(no reset between picks), **5/6 placed in 59.2 s of simulated time / 62.6 s of
clip**, per-pick **9.9 s** - inside the 12 s target. The two separate-pick
demos are weaker (2/6, 1/6): the video render (three extra cameras) moves the
head frames and the perception branch, and the direct loop is not
bit-reproducible. The pre-P225 `p177_adopted` (4/6) is the better demo clip;
the continuous is the current recipe.

Reproduce: `logs/p225/video_cont.sh` (continuous) and
`logs/p225/video_demo.sh` (separate picks), `OUT_DIR=...`.

## Final-recipe clips (2026-11-20, 0.15 m/s)

Both use the recipe of `RESULTS.md` 4g-4l: `p177_full` (md5
`3a019eb8`), the small-fruit perception floor (<= 4 cm -> 12 px), the carry
force scoped > 4 cm, the sphere fit, the **two-sided close gate**
(`FRUIT_CLOSE_RAMP_DY_LO=-0.02`), the contact/place servos and **no scripted
skill route** (`FRUIT_SMALL_HANDOVER=0`, `FRUIT_HANDOVER_SIDE=`).

| clip | seed | belt | outcome | per-pick | duration | path |
|---|---:|---:|---|---:|---:|---|
| **`p225_final_cont_s303`** | 303 | 0.15 | **6 picks, 5 placed (83 %)** | **9.5 s** | **47.9 s** | `/media/ubuntu/66A27065A2703B9D/project/Agent-diffusionpolicy/log/video/p225_final_cont_s303` |
| **`p225_final_demo_s77`** | 77 | 0.15 | **4/6 separate picks** | 9.9-12.2 s (4 successes) | 64.1 s | `.../video/p225_final_demo_s77` |
| `p225_final_demo_s101` | 101 | 0.15 | 4/6 separate picks | 9.6-10.4 s (4 successes) | 66.9 s | `.../video/p225_final_demo_s101` |

The continuous clip is the one to show: one episode, six picks back to back
(`gap_ticks=[70,70,70,100,100]` = 0.58-0.83 s between picks), **5/6 placed in
47.3 s of simulated time**, i.e. **9.5 s per placed fruit** at a **0.15 m/s**
belt - inside the 12 s target and above the 55 % bar. The one miss is a 3.6 cm
lychee (`grasped=False`, the small-fruit approach class); the five placements
are pear / pear / pear / pear / pear-tomato-lychee mix as the `[cont]` rows show
(`placed_so_far=5` at pick 6/6). The six picks are orange, peach, pear, pear,
lychee, pear - **four pears + one orange + one peach placed**, and the miss is
the 3.6 cm lychee (`grasped=False`, the small-fruit approach class).

The **separate-pick demos read 4/6 on both seeds** while the *same* seeds read
**8/8 and 7/8 in the plain 8-episode cells** - the video render (three extra
cameras plus the per-frame capture) moves the head frames the policy conditions
on, which is the branch the record already names for every clip. Quote a video's
outcome as the clip's own, not as the recipe's rate.

Both clips: `observer.mp4` (the annotated cell view), `overhead.mp4` (the raised
view with both output lanes - the one to watch for placements), `gripper.mp4`
(the pick close-up), `head.mp4` (the policy's input) and `side_by_side.mp4`
(observer + head), H.264/yuv420p, 30 fps, with `video.json` (checkpoint md5,
camera, per-episode rows) and the constructor manifest.

Reproduce:

```bash
OUT_DIR=.../p225_final_cont_s303 BELT=0.15 SEED=303 PICKS=6 logs/p225/video_cont.sh
OUT_DIR=.../p225_final_demo_s77  BELT=0.15 SEED=77  EP=6    logs/p225/video_demo.sh
```
