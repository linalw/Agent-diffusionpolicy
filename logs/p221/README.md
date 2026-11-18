# P221 video - one continuous episode, 6 lychees, 5/6

`logs/p221_video.sh` runs `scripts/121_policy_video.py --episodes 1 --continuous 6
--seed 808` with:

```bash
FRUIT_POLICY_TARGET_RATE=5.45 FRUIT_POLICY_JOINT_CLAMP=1
FRUIT_CLOSE_RAMP_DY_LO=-0.02
FRUIT_SMALL_HANDOVER=1 FRUIT_SUPPLY_SPECIES=lychee FRUIT_DIRECT_FEED=1
```

Output: **5/6 placed, 77.0 s, 2309 frames**; the `[cont] pick 2/6 ... 6/6` rows prove
the scripted skill's finalize continues the episode; every small attempt is
`decision=0` (the learned model is not used). The failure is one 3.7 cm lychee.

Archived at
`/media/ubuntu/66A27065A2703B9D/project/Agent-diffusionpolicy/log/video/p221_continuous_small_5of6_s808/`
(observer / head / gripper / overhead / side_by_side + `video.json` + montage + README).
This is a **hybrid/scripted-skill** continuous demo, not a learned small-fruit policy;
the learned continuous P204 is 2/6 and the mixed continuous seed-303 cell is 4/6.
