# P224 demo clip - six sorts, 5/6

`logs/p224_video.sh` runs `scripts/121_policy_video.py --episodes 6 --seed 303` with the
P207 R5 recipe + `FRUIT_POLICY_JOINT_CLAMP=1` + `FRUIT_CLOSE_RAMP_DY_LO=-0.02` +
`FRUIT_SMALL_HANDOVER=1`.

Output: **5/6 placed, 57.3 s, 1719 frames**. The 3.0 cm lychee is the scripted small route
(`decision=0`); the learned large path is 4/4; the one failure is a 7.0 cm right apple on
the learned path. Archived at
`/media/ubuntu/66A27065A2703B9D/project/Agent-diffusionpolicy/log/video/p224_demo_hybrid_5of6_s303/`.

The continuous effect clip is `p221_continuous_small_5of6_s808/` (one episode, six
lychees, 5/6, 77.0 s).
