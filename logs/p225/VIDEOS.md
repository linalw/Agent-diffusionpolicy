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
