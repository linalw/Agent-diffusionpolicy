# Dynamic grasping of moving fruit: methods review (2024-2026)

Scope: fast closed-loop action-chunked policies, flow-matching/block-diffusion heads, dynamic-grasp
interception, fast correction. Context: scripted expert + 42-demo DDIM-16 policy (128 px RGB+depth+mask,
4.59 M params, ~12 ms/chunk on a 5090, re-plans every 4 steps at 20 Hz), belt encoder as state input,
v2 on-the-fly line 6/10 and grip-geometry-limited. *Italic = one-line assessment for this repo.*
## 1. Real-time / fast closed-loop action-chunked policies
- **RTC - Real-Time Chunking (Black et al., NeurIPS 2025; PI + LeRobot).** Run the next chunk's inference while executing the current one; "freeze" the `d` actions already consumed when inference finishes and *inpaint* the rest with soft (exponentially decaying) guidance toward the previous chunk. Inference-time only, no retraining, any diffusion/flow policy. Needs `d <= s <= H-d`, a differentiable denoiser (vector-Jacobian product per step), a chunk buffer + background thread, and a delay estimate. With π0.5 (H=50, 20 ms tick, 5 flow steps): baseline model latency 76 ms, RTC 97 ms, +10-20 ms LAN -> d≈6; robust to +100/+200 ms injected delay, while temporal ensembling (TE) oscillates into protective stops; TE also fails at d=0 on 12 dynamic Kinetix tasks because averaging multimodal actions is invalid; RTC ~20% faster than synchronous. Code: PI reference `Physical-Intelligence/real-time-chunking-kinetix`; productionized in LeRobot (`RTCConfig`: execution_horizon 8-12, max_guidance_weight 10, EXP schedule, `guided`/`trained` modes). https://arxiv.org/abs/2506.07339 , https://github.com/huggingface/lerobot/blob/main/docs/source/rtc.mdx
- **Training-time RTC (Black et al., Dec 2025).** Simulate the delay in training, condition on action prefixes, pay zero inference overhead; beats inference-time RTC at high delay on π0.6 real tasks. https://arxiv.org/abs/2512.05964
- **VLASH (Sun et al., Dec 2025, MIT).** Roll the *robot state* forward through the previous chunk to the execution-time state and fine-tune with temporal-offset augmentation. No runtime overhead or architecture change; max reaction latency cut up to 11.8x vs sync; Kinetix delay 4: 81.7% vs 51.2% naive async (RTC degrades faster at large delays because inpainting overhead widens the prediction-execution gap); with action quantization q=2, 1.5-2x physical speedup; π0.5 plays ping-pong/whack-a-mole. https://arxiv.org/abs/2512.01031 , https://github.com/mit-han-lab/vlash
- **A2C2 - Asynchronous Action Chunk Correction (Sendai et al., Sep 2025).** Lightweight correction head runs *every control step* on the latest observation, base-chunk action, chunk index and base features; base VLA frozen; orthogonal to RTC; +23 pt over RTC on Kinetix, +7 pt on LIBERO Spatial, minimal overhead. https://arxiv.org/abs/2509.23224
- **Schedules.** ACT temporal ensembling (exp-weighted overlap; inference every step) is the standard smoother but can average modes; Adaptive Action Chunking (CVPR 2026) sets horizon from action entropy; dynamic-horizon work varies it by task stage; LeRobot `n_action_steps` = 8 (DP), 10 (ACT), 50 (π0). RTC shows that *shorter* execution horizons strictly help once cross-chunk continuity exists. https://arxiv.org/abs/2304.13705 , https://arxiv.org/abs/2604.04161 , https://arxiv.org/abs/2606.11408 ; plain async inference: https://huggingface.co/blog/async-robot-inference
- *Repo: at 12 ms/chunk vs a 50 ms tick, RTC's latency case does not exist yet - but `--execute-steps 1` makes chunk-boundary continuity the blocker, exactly what RTC soft masking, training-time prefix conditioning, or A2C2 fix; cheapest policy-side win.*
## 2. Flow-matching and diffusion policy heads
- **Flow matching policies (π0, GR00T N1, SmolVLA).** Straight-line noise->action ODE vs curved DDPM; π0/π0.5 use 10 steps (LeRobot `num_inference_steps=10`), chunks 50/50/40; latency dominated by the backbone (π0 3B: 46 ms KV prefill alone on a 4090), not the sampler. https://arxiv.org/abs/2410.24164 , https://arxiv.org/abs/2503.14734 , https://arxiv.org/abs/2506.01844
- **Consistency/distilled samplers.** Consistency Policy (RSS 2024): distill a trained DP to 1-2 steps, order-of-magnitude faster at comparable success, laptop GPU; OneDP: one step, 1.5 Hz -> 62 Hz, 2-10% extra pretraining; FlowPolicy: consistency flow matching, one step, 7x on Adroit/MetaWorld; One-Step Flow Policy (Mar 2026): teacher-free self-distillation, >100x vs 100-step sampling, one step beats 10-step π0.5 on RoboTwin. Maturity: code for CP/FlowPolicy; OneDP project page only. https://arxiv.org/abs/2405.07503 , https://github.com/Aaditya-Prasad/Consistency-Policy , https://arxiv.org/abs/2410.21257 , https://research.nvidia.com/labs/dir/onedp/ , https://arxiv.org/abs/2412.04987 , https://github.com/zql-kk/FlowPolicy , https://arxiv.org/abs/2603.12480
- **Block diffusion.** BD3-LMs (ICLR 2025 oral): AR across blocks, parallel discrete denoising inside a block; interpolates AR and diffusion, keeps KV-cache reuse. https://arxiv.org/abs/2503.09573 , https://github.com/kuleshov-group/bd3lms
- **Block diffusion for actions (2026).** TBD-VLA (CoRL 2026): tokenized actions in temporal blocks, masked diffusion within, AR between; 0.087 s (H_a=8) / 0.117 s (H_a=12) latency on 2B vs 0.208 s π0.5; LIBERO 97.7%; temporal in-painting gives RTC for free (93.2% vs 72.3% at 4-step delay). BlockVLA: block-diffusion finetuning of AR OpenVLA, 2 denoise steps/block, 3.3x faster than full discrete diffusion (186.7 tok/s), 8x vs OpenVLA, 91.7% LIBERO. Both are *discrete-token* VLAs. https://arxiv.org/abs/2606.07895 , https://tbd-vla.github.io/ , https://arxiv.org/abs/2605.13382
- **Speculative/parallel decoding.** PD-VLA (IROS 2025) parallel-decodes chunks for AR VLAs; Spec-VLA (EMNLP 2025) spec-decodes action tokens; they cut token-by-token AR latency, not continuous chunk samplers. https://arxiv.org/abs/2503.02310 , https://arxiv.org/abs/2507.22424
- **Reactive flow frontier.** πR² (Jul 2026): diffusion-forcing schedule + split fast (proprioception, every tick) / slow (vision, async) conditioning; one denoise step per call, ~25 Hz replanning on an A5000 with 40 ms-fresh observations (4x base policy), +23% sim / +30% real. https://arxiv.org/abs/2607.26055
- *Repo: DDIM-16 at 12 ms is already far under the tick, so a faster sampler buys no control headroom; flow matching matters only as the substrate for RTC/πR²-style guidance or for >60 Hz control; block/speculative methods need discrete tokens and a large AR backbone this repo lacks.*
## 3. Dynamic grasping / moving-object interception
- **Akinola et al., IROS 2021 (cleanest ablation).** RNN predicts future pose over a 1-2 s horizon set by end-effector distance; reachability SDF filters grasps; a motion-conditioned net ranks grasp quality by speed/direction; trajectory seeded by the previous plan. 700 trials/setting: 0.75-0.95 success at 3-5 cm/s; removing prediction is the single biggest hit (UR5 0.87 -> 0.28-0.34), removing seeding 4-12%. Real conveyor 4.46 cm/s: 3/5-5/5. Code: https://github.com/jingxixu/dynamic-grasping , https://arxiv.org/abs/2103.10562
- **Chen et al., ICRA 2025.** Training-free global-to-local detection + static-to-dynamic planning, one in-hand RGBD; constant-velocity lead from two timed detections predicts positions at Δt=1 s, then commits only if `t_plan + t_move + t_approach < Δt`. 5.5 cm/s: SR 78-86%, ER 84-85%; 11 cm/s: SR 64-75%, ER 84-96%; high-speed failures are positional-tolerance (contact-geometry) failures. https://arxiv.org/abs/2502.05916
- **Conveyor RL (Machines 2025).** Vision-based RL pick-and-place on a moving belt: ~80% success at 0.03-0.07 m/s. https://www.mdpi.com/2075-1702/13/10/973
- **Catch It! (2024).** Mobile base + 6-DoF arm + 12-DoF hand, two-stage RL whole-body catching; ~80% sim success on thrown objects, sim-to-real sandbag catching with onboard sensing; learned reactive catching without an explicit predictor. https://arxiv.org/abs/2409.10319
- **High-speed intercept evidence.** Kim et al. (T-RO 2014): uneven objects caught up to 6.7 m/s with a 7-DoF arm; a ball system reports 44/50; above ~1 m/s, gripper closing time (<10 ms) and prediction dominate; EKF + learned motion-primitive graph intercepts thrown objects while avoiding obstacles. https://www.researchgate.net/publication/273391650 , https://arxiv.org/abs/2209.13628
- **Industrial practice.** FANUC iRPickTool/line tracking = encoder + vision: parts enter a FIFO, the encoder advances their positions, and the robot flying-picks at a trigger point without stopping the belt - deterministic feed-forward interception, no learning, exactly the encoder-plus-lead pattern the scripted line should copy. https://www.fanucamerica.com/products/software/robot/irpicktool
- **Learned dynamic mobile manipulation.** DynaMOMA (2026) predicts short-horizon grasp trajectories with anchor diffusion and drives a whole-body RL policy with an anticipation-guided reward; Islam et al. (RSS 2020) give constant-time replanning for conveyor picking. https://arxiv.org/abs/2606.25295 , https://www.roboticsproceedings.org/rss16/p025.pdf
- *Repo: the literature is unambiguous that prediction dominates at conveyor speeds and the encoder already provides the fruit velocity, so a constant-velocity intercept + earlier, velocity-matched close is near-free and directly measurable; the ICRA'25 time-budget check is portable.*
## 4. Fast trajectory correction
- **Residual RL on a frozen base.** RPL (2018) learns residuals over a nondifferentiable controller; ResiP (2024) adds residual RL to a BC assembly policy: 54% -> 98% round-table assembly, ~5-50% -> >95% overall; needs simulator rollouts + reward. https://arxiv.org/abs/1812.06298 , https://arxiv.org/abs/2407.16677 , https://residual-assembly.github.io/
- **Per-step correction heads (best fit).** A2C2 (above) is precisely a supervised residual policy on a chunked VLA running every tick; VLA-Corrector (NeurIPS 2026) adds an event-triggered detect-and-correct loop. https://github.com/ZJU-OmniAI/vla-corrector
- **Short-horizon MPC / whole-body control.** Whole-body MPC handles varying timelines; PAS-MPC tracks a moving object to a grasp pose under perception uncertainty; phase-map visual servoing + MPC gives high-precision dynamic tracking; classical IBVS reaches >1 kHz with fast cameras. MPC needs a model and runs 10-100 Hz. https://wbmpc.github.io/ , https://www.mdpi.com/2076-0825/15/2/77
- **Human-inspired predictive reaching.** The motor system compensates ~100 ms visuomotor delay with forward models predicting command consequences, so feedback corrects rather than initiates reaches (Desmurget & Grafton 2000; Wolpert & Flanagan). https://www.sciencedirect.com/science/article/pii/S1364661300015370 , https://wolpertlab.neuroscience.columbia.edu/sites/wolpertlab.neuroscience.columbia.edu/files/content/papers/WolFla09.pdf
- *Repo: a tiny correction head conditioned on (encoder fruit state, latest frame, chunk index) is the natural place to spend the 42 demos plus on-the-fly rollouts; fixes timing without touching the base policy or gripper mechanics.*
## Ranked shortlist (expected value / implementation cost)
1. **Encoder-fed predictive intercept in the scripted line** - constant-velocity lead from `encoder_speed`, earlier close trigger, close ramp matched to fruit speed (two-phase extent close). *High value / low cost, no model change; Akinola's ablation makes it the best-evidenced single factor; deliverable is a speed-vs-success curve.*
2. **Per-tick policy replanning with RTC-style chunk conditioning** - `--execute-steps 1` plus freeze/soft-mask prefix guidance (port LeRobot/kinetix, ~200 lines) or training-time prefix conditioning. *High value / low-medium cost; turns the 5 Hz open loop into 20 Hz and removes chunk-switch jerk; with d≈0 the win is continuity, not latency hiding.*
3. **VLASH-style future-state conditioning / offset fine-tune** - one fine-tune of the existing policy on the 42 demos with state-offset augmentation; zero runtime overhead; same misalignment RTC targets, no per-step autodiff. *Medium-high value / medium cost; 42 demos is the constraint.*
4. **A2C2-style per-tick correction head** - small supervised head on the frozen checkpoint, fed encoder + latest frame + chunk index; train on scripted dynamic runs and failures. *Medium-high value / medium cost; orthogonal to 2-3 and the best place to encode fruit motion.*
5. **Execution-schedule tuning + adaptive horizon** - sweep execute-steps and close-window; entropy/event-triggered horizon if fixed underperforms. *Medium value / low cost; do this before retraining anything.*
6. **Flow-matching head or 1-4-step consistency distillation** - only if control moves to 60-200 Hz or RTC guidance autodiff pushes inference near the tick. *Medium-low value / medium cost at 20 Hz, since 12 ms already fits.*
7. **Block diffusion / discrete-token VLA / speculative decoding** - gains are for discrete AR backbones with large pretraining; tokenizing this 4.59 M continuous policy still needs RTC's recipe for continuity. *Low value / high cost; skip.*
Cautions from repo evidence: policy runs are not samples (renderer-dependent variance), so every arm needs N runs and per-episode outcomes; new correction terms stay off by default when not under test; none of these fixes the gripper's contact geometry - they buy the time window in which a correct close can happen.

## 5. Decision rate and motion smoothness (2026-10 update, librarian; condensed)

Current budget: DDIM-16 ~26 ms/chunk, execute-steps 4 -> 30 Hz decisions (33.3 ms period at
120 Hz physics, ~78 % duty). The interleaved RTC runner means execute-steps 1 still implies
d~4 at 26 ms: the action switch rate rises, the sampler cost still sets the decision rate.

**Theory**: RTC's sweep shows the solve rate strictly increasing as the execution horizon
shrinks *once cross-chunk continuity exists* (naive async and temporal ensembling do not
benefit; TE oscillates into protective stops). With long observation context (12-20 frames)
an execution horizon of 1 is optimal - long open-loop chunks mainly compensate a
non-Markovian expert with short context (arXiv 2608.15938); the repo's `obs_horizon=2` is the
likely blocker for very short horizons. Chunking's measured benefit is non-Markovian
expressivity + implicit ensembling, not temporal consistency (arXiv 2608.02547).
Event-triggered replanning: DVAC (denoising-variance prefix, -43 % replans, LIBERO +3.3)
arXiv 2606.03847; ChunkTrust (spectral stability, +6.8 pt on pi0.5) arXiv 2609.39754.
Industrial: encoder line tracking with a trigger/FIFO is exactly the repo's trigger; 1 kHz
loops run on the servo/intercept channel, not the learned policy.

**Smoothness**: temporal ensembling is the losing baseline on dynamic tasks; soft/training-time
RTC reduce high-delay delta and jerk ~9-10 % vs hard RTC (arXiv 2605.25537). Velocity-aware
representations: B-spline knot+control-point policies (arXiv 2607.09648), delta actions
dominate absolute for modern backbones (arXiv 2602.23408), GEM's tracking/interaction split
(arXiv 2508.14042). Metrics to standardise: jaw-TCP **SPARC** + the existing boundary-jump
script (`scripts/124_rtc_boundary.py`).

**Heads that buy rate**: for a 4.59 M conv UNet the drop-in is **consistency distillation**
(Consistency Policy arXiv 2405.07503; OneDP 1.5 -> 62 Hz arXiv 2410.21257; MP1 MeanFlow 1 NFE
6.8 ms arXiv 2507.10543; FlowPolicy arXiv 2412.04987). Block/speculative decoding needs
tokenized actions or a large AR backbone - does not transfer.

**Per-step correction**: A2C2 (a correction head every control step, base frozen; +23 pt over
RTC on Kinetix) arXiv 2509.23224; DCDP (dynamic features, +19 % dynamic-PushT) arXiv 2603.01953;
ResiP residual RL (54 -> 98 %) arXiv 2407.16677. Two-tier references: piR^2 ~25 Hz one-denoise
(arXiv 2607.26055), FiS-VLA 117.7 Hz fast path (arXiv 2506.01953).

**Ranked shortlist for this repo** (gain/cost; the librarian's falsifier in parentheses):
1. **RTC on + execute-steps sweep 4 -> 2 -> 1** (boundary jump + seeded per-episode outcomes).
2. **A2C2/DCDP-style per-tick correction head on the frozen checkpoint** (fixed-seed A/B at
   execute-steps 4; if the fire-to-close timing distribution and outcomes are unchanged it adds
   nothing) - the only genuine 120 Hz reactivity without shrinking the sampler.
3. **Distill DDIM-16 to a 1-4 step head** (Consistency Policy / FlowPolicy recipe; teacher =
   the current checkpoint) - 26 ms -> ~3-7 ms is what unlocks 60-120 Hz; compare the student vs
   the teacher on chunk fidelity *and* the per-episode outcome distribution; a wide-strawberry
   regression kills it. 42-63 demos is the risk.
4. **Event-triggered replanning** (DVAC/ChunkTrust; check whether clean-action variance
   separates the approach/intercept/carry phases, AUC > 0.5).
5. **B-spline / delta-action targets** (SPARC + executed-stream boundary jump).
6. **SAIL-style faster-than-demo execution** (time-scale the existing min-jerk until |a|max
   reaches the cone budget; the repo's own evidence says the tracker/contact is the limit).
7. **Block/speculative decoding** - skip (needs tokenized actions).

Cross-cutting falsifier: none of these buys contact geometry - if the finger-extent failures
do not move, the gain is real but not the one the sorter needs. Protocol: N runs per arm,
per-episode outcomes, distributions not single numbers.
