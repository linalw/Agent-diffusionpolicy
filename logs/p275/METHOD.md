# P275 方法：怎么量"还剩多少真值"，以及为什么判定不能看计数

## 1. 为什么需要一台"真值计数器"

owner 的约束是**四件允许**（实例掩码、深度、触觉力、箱号），其余不得用真值。
代码里 `spawner.position/velocity` 被读 **143 次**（`tasks.py` 102 + `rl_env.py` 41），
所以"已经没有真值了"这种话必须被**数出来**，不能靠读代码猜。

仪器：`FRUIT_TRUTH_AUDIT=1` 在 `FruitSpawner.position` / `.velocity` 各加一个
`_truth_read(kind)`，用 `sys._getframe(2).f_code.co_name` 记**调用者函数名**，
每个 episode 由 `rl_env._finalize` 打印一次累计表：

```
[truth] ep=3 simulator fruit-state reads so far: 4211
[truth] ep=3      1204  _grasp_carry_place_impl.position
[truth] ep=3       812  _carry_leg.velocity
...
```

* **默认关闭**，关闭时是一次 `dict` 判断，零物理影响；
* **只在审计格里开**（它会走帧栈，属于"每 tick 加工作"的一类，AGENTS §2 的规矩是
  不进性能格）；
* 表里出现**控制路径**的函数名 = 那处替换没生效（PREREG 的 F3）。

## 2. 抓取判定：为什么用"力 **且** 间距"

真值路径的两处判定都是仿真状态：

| 站点 | 出厂读法 |
|---|---|
| 探针后"抓到了吗"（决定要不要重抓） | `spawner.position(sample)[2] - z_before > 4 mm` |
| 计分标签 `grasped` | `peak_lift > 50 mm` |

`FRUIT_GRASP_JUDGE=force` 把两处都换成机器人自身传感：

```
held  ⇔  Σ tactile.normal_force ≥ 2 N   在窗口内(10 tick, 允许 1 次低点)
      且  _hand_separation(side) ≥ 20 mm
```

* **力**这一半来自实测分布：夹住的腿 `force_min` 9.6–9.9 N，逃逸腿 `0.00 N`；
* **间距**这一半是**必需的**，因为只用力的判据有一个已知误判：两垫片互夹
  （P103 的 `sep_min 0.2 mm` / `fmax` 最高 213 N / `closed 15 mm`）——空手也会读到大力的；
* 真值 `peak_lift` **仍在同一行打印**，作为**评估列**（`truth=held|lost`）。
  这不是控制输入，是评分；判定的保真度就是拿它当标签算的。

## 3. 判定的计数陷阱（本阶段最重要的读法）

传感判定要 `_step_sim` 若干 tick —— **它同时是一个 settle**。实测（0.12、seed 909/910）：

| 臂 | 判定窗口 | placed |
|---|---|---|
| 出厂（真值判定） | 0 tick | 30/40 = 75 % |
| 传感判定 | 10 tick | 38/40 = 95 % |
| 传感判定 | 1 tick | 36/40 = 90 % |

如果只看这张表，会得出"传感判定把成功率提高了 20 点"——**错的**。P262 已经量过：
`settle` 是下一段的**起步信用**，不是免费的。所以本阶段加了
`FRUIT_GRASP_JUDGE_SETTLE=<n>`：真值臂也能拿同样的 tick，A/B 才对得上。

**结论性的读法**：判定只在**保真度**上被评分（`sensors` vs `truth` 的逐次一致率），
计数属于 settle，不属于判定。

## 4. 去真值束（TFs）的构成

| 环节 | 出厂 | TFs |
|---|---|---|
| 策略目标（位置/速度/直径） | `spawner.position/velocity`（选择时快照，冻结） | `FRUIT_GOAL_SOURCE=perception`：头部 RGB-D → 掩码 → 球拟合 → 卡尔曼，每观测 tick 刷新并外推 |
| 到达触发 `t_arrive`/`dx`/`dy` | 同一真值 | 跟随 `perception`（`_fruit_for_trigger` 返回 `source=percept`） |
| 原语抓取前读数 | 102 处真值 | `FRUIT_PRIMITIVE_ESTIMATE=1`（18 处经 `_fruit_state`）+ `FRUIT_PRIMITIVE_PERCEPT=1`（接触期也渲染，否则估计器停在 10 s 前） |
| 抓取判定 | 真值 z / peak_lift | `FRUIT_GRASP_JUDGE=force` |
| 起始位姿 x | `spawner.position(...)[0]` | `FRUIT_START_ALIGN_FROM=percept`（末次观测的 x；无帧用带中心 x） |
| 直径（拟合失败时） | 静默回落真值 | `FRUIT_GOAL_NOMINAL_DIA=0.060` |
| **选哪一颗** | `select_target` 在真值状态上跑 | **未解决**：列进债务表（要一个"窗口内检测+轮询"的选择器，是下一阶段） |

## 5. 复现

```bash
# 三臂 × 两种子，10 连取，0.08
SEEDS="913 914" PICKS=10 SPEED=0.08 bash logs/p275/run_p275.sh
```

报告（只读结果行，`MISSING != 0`）：

```bash
python3 logs/p275/p275_report.py logs/p275b/*.log
```
