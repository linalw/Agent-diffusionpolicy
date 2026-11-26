# 演示视频：学习式腕部分割器（P279 的部署形态）

**2026-11-26，seed 913，0.08 m/s，连续 8 次取放 → 3/8 放置**（一格分支，不是速率）。

## 三条片子

| 文件 | 内容 | 时长 / 帧 |
|---|---|---|
| `observer.mp4` | 第三人称，带叠加信息（`[primitive]`、`|jaw-fruit|xy`、`t(pick)`、`T=`）| 112.4 s @15 fps，1686 帧，960×540 |
| `gripper.mp4` | 取料站上方近景（`--views close`），看抓取瞬间 | 同上 |
| **`wrist.mp4`** | **腕部相机自己的画面 + 分割器预测**（红色掩码 + 黄色轮廓；顶部绿条 = 掩码覆盖率，3–60 % 是有用区间）| 1198 帧 @30 fps，240×424 |

`stills/` 里抽了帧，**`wrist_t22s.jpg` 是最好的一帧**：一颗番茄被掩码精确包住，
左边的青柠**没被框**——说明网络是按**实例**分的，不是按颜色。

## 录制命令（与 P279 的判决配方同一套）

```bash
FRUIT_ARM_KIND=franka FRUIT_OUTPUT_BINS=1 FRUIT_BIARM=0 FRUIT_CAMERA_RES=240,424 \
FRUIT_BELT_SPEED=0.08 FRUIT_DIRECT_START_ALIGN=family \
FRUIT_START_FAMILY=configs/start_pose_family_panda.json \
FRUIT_POLICY_ACTION_HOLD=4 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TARGET_RATE=5.45 \
FRUIT_POLICY_JOINT_CLAMP=1 FRUIT_EVAL_LATENCY=auto FRUIT_CONTINUOUS_TRANSIT=1 \
FRUIT_SKIP_LATE=0 FRUIT_RELEASE_PAD_HOLD=1 FRUIT_RELEASE_FINGER_HOLD=1 \
FRUIT_SETTLE_EPS=0.01 FRUIT_CYCLE_REPORT=1 \
  `# 下面这一行就是 P279：决策层去真值 + 腕部学习式分割器` \
FRUIT_GOAL_SOURCE=perception FRUIT_PRIMITIVE_ESTIMATE=1 FRUIT_PRIMITIVE_PERCEPT=1 \
FRUIT_GRASP_JUDGE=force FRUIT_GRASP_JUDGE_TICKS=10 \
FRUIT_START_ALIGN_FROM=percept FRUIT_SELECT_FROM=percept \
FRUIT_WRIST=learned FRUIT_WRIST_DUMP=logs/video_p279/wrist FRUIT_WRIST_DUMP_MAX=600 \
  scripts/run.sh scripts/121_policy_video.py \
    --ckpt checkpoints/p227_panda156/policy_best.pt --episodes 1 --continuous 8 \
    --seed 913 --capture-every 2 --views observer,close \
    --frames-dir logs/video_p279/frames --out-dir logs/video_p279 --horizon 10000
```

腕部叠加片由 `logs/p279/make_wrist_clip.py logs/video_p279/wrist --out logs/video_p279/wrist.mp4` 生成
（`FRUIT_WRIST=learned` 每次测量会写 `wrist_<side>_<i>.ppm`（网络看到的 RGB）+ `_pred.npy`（掩码））。

## 这一段要看的、和不能看的

**看**：
1. `wrist.mp4` 里掩码**跟得住**果子（P279 的验证 IoU 0.976，部署里 p50 6–9 mm）；
2. 掩码**只框一颗**（同框的青柠不被框）——它是按实例学的，不是颜色阈值；
3. 掩码**经常很小或没有**（绿条短、甚至只有边缘几条像素）——**那不是网络坏了**，
   是**垫片挡在相机与果子之间**。这正是 P279 的结论：精度够、可见率不够。

**不能看**：
- **不是速率**：8 次取放的一格是分支（P279 的两种子判决是 11/20 = 55 %）；
- **不是"无真值"**：这是**决策层去真值**（目标/触发/选果/起始/果径/判定）+
  **腕部学习式掩码**；接触段的其它读数仍是仿真真值（`docs/TRUTH_AUDIT.md`）；
- **不是实时**：回路内决策延迟 66 ms（`FRUIT_EVAL_LATENCY=auto`）。

## 位置

- 工作副本：`logs/video_p279/{observer.mp4, gripper.mp4, wrist.mp4, video.json, stills/}`
- 归档（mp4 不入 git）：
  `/media/ubuntu/66A27065A2703B9D/project/Agent-diffusionpolicy/log/video/p279_learned_seg_s913/`
- 检查点：`checkpoints/p227_panda156/policy_best.pt`（md5 `6ec25f54`）；
  分割器 `checkpoints/wrist_seg.pt`（md5 `f91093da`，val IoU **0.976**）
