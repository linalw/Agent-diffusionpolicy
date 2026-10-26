# P41 phase 4 (close-out) — evidence index

| file | what it is |
|---|---|
| `accept_policy_profile.log` | the A1 hybrid policy canary under the shipped profile (10 episodes, `moe_v12`, fixed pre-v9 supply) — the simulator log |
| `accept_policy_claim.log` | the same run's gate verdict (the claimed run's stdout): **7/10 = 70 %**, 2 grip losses + 1 pick-station escape, FAIL on the reason clause only |
| `a4_drive_read.py` / `a4_drive_read_out.txt` | the A4 stage check: the raw `drive:linear:physics:maxForce` attribute is the API's own, `joint2` (drive-less mimic) answers `None`, the readers leave its applied schemas alone, `DriveAPI.Get` is **inert** on this USD/lib, the 30 N write still lands, 0 failures |
| `a4_prefix_compare.txt` | A4's inertness end to end: the post-fix one-attempt acceptance's build header and attempt-0 physics stream are **65/65 `[fruit]` lines identical** to the pre-fix control `logs/p41/p3/accept_control.log` |
| `build_print_default.log` | the one-attempt scripted run behind that comparison (`ATTEMPTS=1 SEED=5 FRUIT_MOTION_REPORT=1`) |
| `collect_manifest_smoke.log` | the A2 collector shard smoke (`FRUIT_EPISODES=1`, out to /tmp): the `physics` block with the runtime read-back, `matches=True maxForce=10.0N` |
| `rl_manifest_smoke.log` | the A2 direct-env smoke (`110_rl_rollout.py --episodes 1 --ablate zero`, out to /tmp): the manifest is written with the same `physics` block |
| `physics_block_smoke.json` | both blocks, extracted (collector shard + direct rollout) with the relevant source pins |
| `96_motion_check.txt` | `python3 scripts/96_motion_check.py` on the final tree: all checks passed |

`logs/p41/selfcheck.log` (one level up) is the final-tree `scripts/selfcheck.sh`
run: **PASS, 0 failures, 1 skipped**.
