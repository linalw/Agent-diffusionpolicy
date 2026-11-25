# 演示视频：单臂分拣单元的部署形态（2026-11-25）

**一条命令录的**（配方 = `scripts/290_single_arm_continuous.sh` 的同一套）：

```bash
FRUIT_ARM_KIND=franka FRUIT_OUTPUT_BINS=1 FRUIT_BIARM=0 FRUIT_CAMERA_RES=240,424 \
FRUIT_BELT_SPEED=0.08 FRUIT_DIRECT_START_ALIGN=family \
FRUIT_START_FAMILY=configs/start_pose_family_panda.json \
FRUIT_POLICY_ACTION_HOLD=4 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TARGET_RATE=5.45 \
FRUIT_POLICY_JOINT_CLAMP=1 FRUIT_EVAL_LATENCY=auto FRUIT_CONTINUOUS_TRANSIT=1 \
FRUIT_SKIP_LATE=0 FRUIT_RELEASE_PAD_HOLD=1 FRUIT_RELEASE_FINGER_HOLD=1 \
FRUIT_SETTLE_EPS=0.01 FRUIT_CYCLE_REPORT=1 \
  scripts/run.sh scripts/121_policy_video.py \
    --ckpt checkpoints/p227_panda156/policy_best.pt --episodes 1 --continuous 10 \
    --seed 907 --capture-every 2 --views observer,overhead \
    --frames-dir logs/video_single_arm/frames --out-dir logs/video_single_arm --horizon 12000
```

## 结果

| 项 | 值 |
|---|---|
| **连续取放** | **10/10 放置**（一个 episode，无按集重置） |
| 时长 / 帧 | **130.9 s @ 15 fps**，1964 帧，960×540 |
| 视角 | `observer`（带标注的第三人称）+ `overhead`（俯视，含两条出料线） |
| 检查点 | `checkpoints/p227_panda156/policy_best.pt`，md5 **`6ec25f54`** |
| 皮带 | 0.08 m/s（目标起点；实测 0.06–0.18 全 91–92 %） |
| 与交付数一致 | 40 连取两格 **80/80**（P274）；20 连取 **139/140 = 99.3 %**（P261/P262） |

## 文件位置

- 工作副本：`logs/video_single_arm/{observer.mp4,overhead.mp4,video.json}`
- **归档**（mp4 不入 git）：
  `/media/ubuntu/66A27065A2703B9D/project/Agent-diffusionpolicy/log/video/deploy_0.08_cont10_s907/`

## 看点（按时间轴）

1. **0–3 s**：臂在等待位姿，果子随带进入选择窗；模型开始接近（不是瞬移，`FRUIT_CONTINUOUS_TRANSIT=1`）。
2. **每次取放**：追够 → 闭合（约 1.1 s 的坡道，**故意慢**）→ 破带起飞 → 静止 → 抬升 → 转位 → 伴降到箱底之上 39 mm → 垫/指依次松开 → 返回航段。
3. **集间**：返回走的是真实航段（263 tick ≈ 2.2 s），**不是瞬移**；`gap` 集中在 257–270 tick。
4. **周期**：画面里一次取放 ≈ **9.7 s**（块表见 `docs/SYSTEM_DIAGRAM.md` §3）。

## 不能从这段视频读出来的事

- **不是速率**：这是**一个** episode，10 次；交付率见 P274 的两个 40 连取格与 P261/P262 的 139/140。
- **不是"实时"**：回路内决策延迟 66 ms = 8 mm（`FRUIT_EVAL_LATENCY=auto`），不是离线台的 26.4 ms。
- **不含 0.12 及以上**：0.12 的部署率是 72.5–85 %，两类失败已定名（P273），本视频只演示 0.08。
