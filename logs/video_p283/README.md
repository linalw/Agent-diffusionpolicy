# 演示视频：腕部相机装在**垫片外侧** + 补光（P281/P282 的部署形态）

**2026-11-26，seed 913，0.08 m/s，连续 8 次取放 → 2/8 放置**
（**这一格抽到了 3 颗梨**——P283 的普查里梨是 12 % 那一类；同一配置的两种子判决是 **13/20 = 65 %**）。

## 三条片子

| 文件 | 内容 | 规格 |
|---|---|---|
| `observer.mp4` | 第三人称，叠加 `[primitive]` / `\|jaw-fruit\|xy` / `T=` / `t(pick)=` | 115.5 s @15 fps，1733 帧，960×540 |
| `gripper.mp4` | 取料站上方近景（`--views close`）| 同上 |
| **`wrist.mp4`** | **腕部相机自己的画面**（垫片外侧、朝内、带环光）——**没有叠加**，因为 `colour` 模式不产出掩码 | 1200 帧 @30 fps，480×848 |

`stills/`：`observer_t26s.jpg`（整格亮起来的俯视）、`gripper_t26s.jpg`（抓取瞬间）、
**`wrist_t12s.jpg` / `wrist_t26s.jpg`**（腕部视角：**果子占满画面、垫片只在四角**，而不是遮挡）。

## 录制命令（= P282 判决用的 A 臂）

```bash
FRUIT_ARM_KIND=franka FRUIT_OUTPUT_BINS=1 FRUIT_BIARM=0 FRUIT_CAMERA_RES=240,424 \
FRUIT_BELT_SPEED=0.08 FRUIT_DIRECT_START_ALIGN=family \
FRUIT_START_FAMILY=configs/start_pose_family_panda.json \
FRUIT_POLICY_ACTION_HOLD=4 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TARGET_RATE=5.45 \
FRUIT_POLICY_JOINT_CLAMP=1 FRUIT_EVAL_LATENCY=auto FRUIT_CONTINUOUS_TRANSIT=1 \
FRUIT_SKIP_LATE=0 FRUIT_RELEASE_PAD_HOLD=1 FRUIT_RELEASE_FINGER_HOLD=1 \
FRUIT_SETTLE_EPS=0.01 FRUIT_CYCLE_REPORT=1 FRUIT_TRUTH_AUDIT=1 \
  `# 决策层去真值 + 腕部（垫片外侧）+ 补光` \
FRUIT_GOAL_SOURCE=perception FRUIT_PRIMITIVE_ESTIMATE=1 FRUIT_PRIMITIVE_PERCEPT=1 \
FRUIT_GRASP_JUDGE=force FRUIT_GRASP_JUDGE_TICKS=10 \
FRUIT_START_ALIGN_FROM=percept FRUIT_SELECT_FROM=percept \
FRUIT_WRIST=colour FRUIT_WRIST_MOUNT=pad \
FRUIT_LIGHT_DOME=2.0 FRUIT_LIGHT_WRIST=600 \
FRUIT_WRIST_DUMP=logs/video_p283/wrist FRUIT_WRIST_DUMP_MAX=600 \
  scripts/run.sh scripts/121_policy_video.py \
    --ckpt checkpoints/p227_panda156/policy_best.pt --episodes 1 --continuous 8 \
    --seed 913 --capture-every 2 --views observer,close \
    --frames-dir logs/video_p283/frames --out-dir logs/video_p283 --horizon 10000

# 腕部片（无叠加）
python3 logs/p279/make_wrist_clip.py logs/video_p283/wrist \
  --out logs/video_p283/wrist.mp4 --fps 30 --scale 2 --no-mask
```

## 这一格在演示什么

1. **整格是亮的**（`FRUIT_LIGHT_DOME=2`）——P280 §4b 说过"场景这么暗"，现在对比明显。
2. **腕部视角里看到的是果子，不是手**（`wrist_*.jpg`）：P280 的普查在**下颌**挂载下是
   "机器人挡 25–56 %、遮挡/果子 10.4×"，垫片外侧挂载是 **8.7 % / 2.67×**。
3. **失败也是真的失败**：这一格 6 次没放上，其中 3 颗是梨——P283 的物种普查说梨在去真值下是
   12 %，而且**失败形态是"合拢时宽度就是错的"**（垫片停在 23–43 mm，果实 62–70 mm）。

## 不能从片子读出来的

* **不是速率**：8 次一格是分支；同一配置的判决是 **13/20 = 65 %**（P282 的 A 臂）。
* **不是"无真值"**：决策层（目标/触发/选果/起始/果径/判定）+ 腕部测量是**测量**；
  接触段的其它读数仍是仿真真值（`docs/TRUTH_AUDIT.md`）。
* **不是实时**：回路内决策延迟 `FRUIT_EVAL_LATENCY=auto` 解析到 4–8 tick（66 ms 量级）。
* **腕部片没有掩码**：`colour` 模式不产出掩码；要看得见掩码请看 `logs/video_p279/`
  （那是 `learned`，p90 18 mm，但放置比 colour 少 2 次——P282）。

## 位置

- 工作副本：`logs/video_p283/{observer.mp4, gripper.mp4, wrist.mp4, video.json, stills/}`
- 归档（mp4 不入 git）：
  `/media/ubuntu/66A27065A2703B9D/project/Agent-diffusionpolicy/log/video/p283_pad_light_colour_s913/`
- 策略 `checkpoints/p227_panda156/policy_best.pt`（`6ec25f54`）
