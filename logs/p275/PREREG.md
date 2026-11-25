# P275 预注册：真值债务的清单与去真值单元的代价

**2026-11-25。** owner 约束：**除实例掩码、深度、触觉力、箱号外，其余都不得使用仿真真值**；
成功率可以降，但要**真能部署**；位置、速度、果径、抓取成功必须由测量/模型给出。

## 0. 时序诚实声明

本阶段先做了两件**探路**（不是注册的判决格），在本文写定之前：

| 探路 | 内容 | 结果 |
|---|---|---|
| J-探路 | `FRUIT_GRASP_JUDGE=force`（10 tick 窗口）在 0.12 的 seed 909/910 | 38/40 = 95 %，判定与真值 **38/38 一致** |
| J-探路2 | 同上但 `TICKS=1` | 36/40 = 90 % |

**这两格不能当判决**：判定的窗口本身是 `_step_sim`，等于给闭合之后加了一个 settle（P262 的读法：
settle 是下一段的起步信用）。计数从 0.12 的 75 % 跳到 95 % 是**该 settle 的**，不是判定的。
因此本阶段补了 `FRUIT_GRASP_JUDGE_SETTLE`（默认 0），让**真值判定臂也能拿到同样的 tick**，
把 A/B 的 tick 数对齐。

## 1. 问题

1. **抓取成功**能否只用`触觉力 + 指间距`判断？保真度（与真值标签的一致率）是多少、错在哪一类？
2. 把**目标、触发、抓取前读数、抓取判定、起始位姿 x** 全部换成测量后，单元还能做多少次？
3. 换完之后**还剩哪些**仿真真值读？要一张**按调用点**的表，而不是一句"基本没有了"。

## 2. 仪器

* `FRUIT_GRASP_JUDGE=truth|force`（默认 `truth` = 出厂逐字节不变）。`force` 用
  `tactile.read().normal_force >= FRUIT_GRASP_JUDGE_FORCE`（默认 2 N，实测夹持 9.6–9.9 N、
  逃逸腿 0.00 N）**且** `_hand_separation(side) >= FRUIT_GRASP_JUDGE_SPAN`（默认 20 mm，
  排除"两垫片互夹"：P103 的 `sep_min 0.2 mm / fmax 213 N`）。窗口
  `FRUIT_GRASP_JUDGE_TICKS`（默认 10），允许一次低点（`n-1` 约定）。
  **判定站有两处**：探针后的"抓到了吗"（决定要不要重试）与抬升后的计分标签。两处都换。
  真值 `peak_lift` 仍在同一行打印，作为**评估列**——这是合法的评分真值，不作控制输入。
* `FRUIT_GRASP_JUDGE_SETTLE=<n>`（默认 0）：真值臂的匹配 settle，只为对齐 tick。
* `FRUIT_TRUTH_AUDIT=1`：在 `FruitSpawner.position/velocity` 上按**调用者函数名**计数，
  每个 episode 打印一次累计表。关闭时是一次字典判断，零开销。
* `FRUIT_GOAL_NOMINAL_DIA`（默认 0.060）：感知模式下**拟合没给半径时**的直径，
  取代原先静默回落到真值直径的漏点。
* `FRUIT_START_ALIGN_FROM=truth|percept`（默认 `truth`）：起始位姿族的 x 来源。

## 3. 单元

同一套部署配方（`scripts/290_single_arm_continuous.sh`），0.08 m/s，每格 10–20 连取，
seeds 913/914（TFs）与 909/910（0.12 判定对齐；控制组同批）。三个臂：

| 臂 | 环境 |
|---|---|
| **C** | 出厂（目标/触发/原语/判定/起始 x 全真值）+ `AUDIT=1` |
| **J** | `GRASP_JUDGE=force TICKS=10` + `AUDIT=1` |
| **Jm** | `GRASP_JUDGE=force TICKS=10` + 控制 `GRASP_JUDGE_SETTLE=10`（tick 对齐） |
| **TFs** | 目标+触发 `GOAL_SOURCE=perception`、原语 `PRIMITIVE_ESTIMATE=1 PRIMITIVE_PERCEPT=1`、判定 `force`、起始 x `percept` + `AUDIT=1` |

## 4. 端点与判决

| 端点 | 读法 | 判决 |
|---|---|---|
| **P1 判定保真度** | 表 2：`sensors` vs `truth`，逐次 | **准入**：无"说抓到了其实没抓到"（FP = 0）。FP > 0 即不可用（会把空手送去放料）|
| **P2 去真值代价** | TFs 的 placed/attempts 对 C | **报数，不设杠**。这是能力测量，不是通过/失败 |
| **P3 债务表** | 表 3 的调用点与次数 | **必须给全**；`MISSING != 0`（没有 `[truth]` 行 = 没测到）|
| **P4 无伤** | `accept.sh` 459/459 + `fingerprint: matches`；`selfcheck.sh` PASS | 硬门 |

**不采纳任何默认**：本阶段所有旋钮默认关闭，出厂路径逐字节不变。

## 5. 预先声明的证伪

* **F1**：`force` 判定在**没抓住**的腿上读 `held`（FP > 0）→ 判定不可用，回到 `truth`，
  并记录该类的力/间距签名。
* **F2**：TFs 的成功率**高于** C → 说明"去真值"在这格没有代价，但也说明这不可能是真的
  （测量不该比真值更准）→ 先怀疑仪器（判定/估计器是否漏读真值），再报。
* **F3**：`[truth]` 表里出现**控制路径**的函数（`_grasp_carry_place_impl`、`_run_impl`、
  `_fruit_for_trigger`、`_aligned_start`）→ 该处的替换没生效，逐个修。
* **F4**：TFs 尝试**在第一次闭合前就失败**（`no graspable fruit` / `fired=0`）→ 感知链路
  根本没接上，报为链路缺陷而不是成功率。

## 6. 不声称

* 不声称"去真值后仍 99 %"：99.3 % 是**真值喂目标 + 真值喂接触**的上界。
* 不声称选择器（选哪一颗）已经去真值：`select_target` 仍在真值状态上跑，本阶段把它
  **列进债务表**而不是假装解决。
* 不声称速率：10–20 连取一格是一次分支（P93）。
