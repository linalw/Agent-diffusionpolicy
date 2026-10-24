# P35 — The arm-park / camera sightline (the first-view lever that survived P34)

Started 2026-10-24 (owner: "继续", following the P34-B finding). Full delegated
authority; an Oracle gate per phase.

## 1. The measured facts (P34-B; do not re-discover)

- The output belt's first-view occlusion is real for the **outer-band x < 0.26**
  (44-48 % of the first calls) and for the right's pear at x 0.219 (the shipped
  visible fraction **0.000**; the 0.399/0.441/0.445 aims 0.115/0.131/0.077) -
  the occluder is the **inactive left arm at `ready`** (`link3` 127-199 px).
- The **left's own first view is fine** (the rendered 0.64-0.86; the shipped
  along 0.439 -> 0.893) - the Phase-2 "arm occlusion" was a **stale pre-reset
  frame** (the 10 episode-0s of 150).
- The store baseline: the left's first view 0.64-0.86; `demos_v11`'s supply x
  **0.323-0.348** (never the outer band); the decision zone's zero-mask: v11
  left 0.80 / p33 left 0.55.
- The reset pose: `q_r` = the grasp waypoint; the settle 20/60/120 null
  (<= 0.001 rad).

## 2. The plan

| # | Phase | Deliverable | Owner | Gate |
|---|-------|-------------|-------|------|
| 1 | The pre-registration + the sightline measurement | the candidate arm parks (the idle arm's pose) + the camera poses; the offline visibility maps (the outer-band x 0.19-0.26 + the right's pear 0.219; the arm's silhouettes); the rendered first-call masks (one episode per process - the stale-frame caveat); the endpoints/OOD costs; the chosen lever | @general | Oracle 1 (done) |
| 2 | The A/B | the chosen lever (the arm park first; the camera only if it wins the measurement) + the P33 endpoints + the no-harm | @general | Oracle 2 (measured, `logs/p35/B_RESULTS.md`) |
| 3 | The integration + the commits | the docs/commits | @general + orchestrator | Oracle 3 |

Oracle budget: 3 gates (1 initial + up to 2 re-reviews each).

**Phase-3 handoff (from phase 2).** The integration owns: (1) the `AGENTS.md`
section-2 line for the lever (`FRUIT_ARM_PARK` measured 25 -> 0 carried on the
right in the record batch, default off, **the mediator is not identified and the
recollection is the adoption gate** - the correct claim is "the park is a
measured interface lever; it removes the fruit's band occlusion", not "the
sightline is the mechanism") and the matching one in `README.md` /
`项目总结报告.md` if their current text
claims the sightline is unmeasured; (2) the commit of phase 1 + 2 together
(`rl_env.py` `FRUIT_ARM_PARK` + the P0-revised `FRUIT_PARK_DIAG`,
`configs/arm_parks.json`, `scripts/217_arm_park_map.py`, `logs/p35/*`); (3) the
decision register entry: the lever is measured and **not adopted** (a positive
still needs a recollection; the two channels it moves - the image and the
inactive-arm proprio - are not separated; and the M2b visibility bar's misses and
the park's 0.088 rad command residual are recorded). Note for the reviewer:
Gate 1's predicted pin `+250/-1, 4d18255e` does not match the actual diag (the
diff vs HEAD is **+424/-1** on `rl_env.py` and the file's md5 is `fd18bb1b`); the P0
revision adds the achieved-pose capture, the analytic projected-disc projector,
the worst-call/labelled row and the `band_frac` guard.

## 3. The levers (the candidates)

- **The inactive arm's park**: the `ready` pose -> a folded/side pose out of the
  camera's sightline (the arm's own pose; the policy's frames shift - a
  static-scene change, the sample/recollection caveat). The cheapest first test.
- **The camera**: the pose/mount (the OOD/recollection cost; the P33 lesson).
- **The fruit's outer-band x**: the supply's design (the reach band 0.18-0.39) -
  the P1c/density lane, not this one.

## 4. The risks

- The arm-park change shifts the policy's frames (the inactive arm is a static
  scene element; the same shift every frame - a sample, not a redesign).
- The outer-band x is the supply's design, not a free lever.
- The N/paired outcomes: the P33 protocol; the quantized-outcome rules.
- The stale-frame caveat: a first-view metric must read one episode per process.

## 5. The log

- 2026-10-24: the file; the plan; Phase 1 dispatched (the pre-registration + the
  sightline measurement).
- 2026-10-24 **Phase 1 measured** (`logs/p35/A_READ.md`, `PREREG.md`,
  `scripts/217_arm_park_map.py`, `logs/p35/park_probe.py` +
  `park_hold.py` + `park_render_probe.py`, 6 runs). The inactive **left** arm at
  `ready` covers **98 %** of a 58 mm fruit's disc at along +0.35 / 57 % at +0.40
  (mean 0.382 of the stream, depth-gated), and the park **`back`** (j1 -0.50 /
  j2 -0.60 / j4 -0.50 rad) takes the marginal cover to **0.002** with the hand
  0.287 m above the belt and a 0.0007 rad / 900-tick hold; proxies render
  0.378 -> 0.878 (the 68 mm pear at 0.219/+0.399) and 0.000 -> 0.953 (0.19/+0.35).
  The camera is priced and dominated (best `x -0.10`: cost 0.075 vs the park's
  0.002) - **the arm park is the lever; the camera is second**. The right arm
  covers 0.00 at `ready` and its `back` does not hold (0.174 rad), so the lever
  is left-only and its population is the right-arm episodes. **Correction:** the
  P34-B right-arm `first_rel` 0.077-0.131 is the pre-reset frame (belt 222/213 px
  in the bbox, fruit absent); the arm's real occlusion is at along +0.30..+0.45,
  not at the shipped first call (belt, `212` 0.00). Default off: `FRUIT_ARM_PARK`
  in `rl_env.py` + `configs/arm_parks.json`; selfcheck PASS. The A/B is
  pre-registered (right-arm paired carried class primary; the left as the no-op
  guard) and a positive still needs a recollection to ship. Oracle 1 next.
- 2026-10-24 **Phase 2 measured** (`logs/p35/B_RESULTS.md` + `B_PREREG_AMEND.md`
  + `B_ab/`, 10 runs + 6 smoke runs; `rl_env.py` `611b18d8` with the new
  default-off `FRUIT_PARK_DIAG` census). The A/B (N=5x15, seeds
  77/101/202/303/404, interleaved, `moe_v13s` `61da390a` on both arms, arm B =
  `FRUIT_ARM_PARK=back`): **pooled 29/75 -> 47/75**; the **right** arm
  28/57 -> 45/48 with its **carried class 26 -> 0**, no-grasp 3 -> 3, composite
  29 -> 3; the **left** (no-op guard) 1/18 -> 2/27 flat; per run B >= A in **5/5**
  seeds (4 strictly, p = 0.0625); exact-instance pairing 22 usable of 75,
  **8 B-only / 2 A-only (p = 0.0547)**, **carried 7 B-only / 1 A-only** (the bar
  met); outer band (x < 0.26) 4/24 -> 15/15; cycle -1.6 %. The manipulation check
  was **amended before the A/B** on its own smoke data (the pre-registered M1
  0.02 rad bar is below the reset teleport's own accuracy: `ready` 0.027-0.038,
  the park 0.090-0.102; and M2's "first band call" is the band's least-occluding
  edge, so the control passes it 23/57): the amended gate reads **M1' 48/48**
  (applied + stable, `|q-back|` 0.100 / `|q-ready|` 0.602, drift <= 0.012),
  **M2a' 48/48** (the arm's pixels in the fruit's bbox 0.000 at all 1645 band
  calls; control 1.125 x the fruit's, 1/57), **M2b' 48/48** (episode-median
  visibility 0.942 vs 0.423), the band's fully-hidden calls **51 % -> 1.0 %**;
  the within-batch no-op side agrees across arms (0.940/0.933). **The falsifier
  does not fire.** Adoption is **blocked as pre-registered**: one new failure
  reason (1/75, a runaway fruit at 6.2 -> 18.0 m, in the existing no-grasp class)
  and the park's 0.09-0.10 rad pose residual (> 0.02); and the positive is "this
  checkpoint on shifted inputs" (the park moves the image *and* the 7 inactive
  joints of the 25-D proprio), so shipping needs the **recollection** and its own
  A/B. No-harm: selfcheck PASS; acceptance (knob off) **6/10 + fingerprint
  matches**, **376/376 `[fruit]` identical** to `logs/p34/73_accept_no_harm.log`;
  tree md5s identical before/after the batch. Default off; no commits. Oracle 2
  next (phase 3 = the docs/commits, owner + orchestrator).
- 2026-10-24 **Gate 1 blocked phase 2 on the check's instrument; the P0 revision +
  the record batch are measured** (`logs/p35/C_RESULTS.md`, `C_PREREG_AMEND.md`,
  `C_ab/`; `rl_env.py` `fd18bb1b`, **+424/-1** vs HEAD, selfcheck PASS, 2-episode
  pilot/arm). The five P0 fixes: M1 vs the **achieved settled** pose (held
  50/50; the command residual 0.088 reported - the shipped `ready` is 0.037 from
  its own command, so a 0.04 rad command bar would fail the shipped reset too);
  M2 over **+0.30..+0.40** at the band's **worst** call; the bbox = the
  **projected disc** (`r_px = f r / sqrt(d^2-r^2)`), not the visible-mask
  extent; the **stale first call skipped**; the diag documented + re-pinned.
  Record batch (N=5x15): pooled **24/75 -> 49/75**; right **23/51 -> 47/50**, its
  carried class **25 -> 0**; composite 28 -> 3; left (no-op) 1/24 -> 2/25; **B > A
  in 5/5 runs, all strict (p = 0.031)** - the design-valid leg, with the
  class/size-standardised 94.9 %/94.1 % against 52.3 %/45.2 %; exact pairs 22
  usable, **8 B-only / 0 A-only (p=0.0039)** (conditioned on a post-treatment
  variable - the streams diverge), carried **7-0**; outer band 6-0 (p=0.0156);
  `C_pairs.txt`'s same-species set **24 pairs, 8/1** (the extra A-only is a
  different fruit, 6.5 vs 6.1 cm); **no new failure reason**; cycle -3.5 % on
  different outcome mixes. The check in exact counts: band calls fully hidden
  **856/1257 = 68.1 % -> 0/1236 = 0.0 %**, inactive-arm pixels inside the fruit's
  **disc bbox 100 % -> 0 %** (worst ratio 333 -> 0), M1-applied **0/51 ->
  50/50**, M2a **0/51 -> 50/50**; the no-op side agrees across arms (11.1 %/9.0 %
  hidden). **The gate of record is M1 + M2a; M2b (rel >= 0.85 at the worst call)
  is a recorded report at 36/50 = 72 %**, misses all `arm_px=0` with `vis`
  0.57-1.02 (2 >= 0.98, 3 >= 0.97) on 22-47 px masks - the **running** `px*d^2`
  maximum plus small-mask raster drift (the belt is the largest instance), not an
  occluder. **`PREREG.md` §5's literal 0.02 rad arm-pose block is failed** by the
  0.088 command residual; the conclusion is unchanged. Verdict: the falsifier
  does not fire; **the park is a measured interface lever and the check shows it
  removes the fruit's band occlusion; the mediator (image vs the 7 proprio
  channels) is not identified - the control's invisible-fruit successes argue
  against a simple perception bottleneck** (9 of 23 right successes `px=0` at
  every band call; 0.84 vs 0.60 median fully-hidden share). **Default off, not
  adopted** (a recollection is the gate). **The named mechanism test is the 2x2
  input spoof** - the proprio-spoof (the park's joints in the obs, the arm *not*
  moved) x the image-spoof (the arm moved, the `ready` proprio) at small N; a
  recollection fixes both channels and can erase a checkpoint-specific
  input-shift win, so it should not be the first spend. No-harm: selfcheck PASS,
  acceptance 6/10 + fingerprint matches (its exit=1 is the expected rate-only
  result), **376/376 `[fruit]` identical** (re-verified after the driver's
  premature `cat` at 14:22 vs the 14:25 file). `C_attribution.py`'s `frac=-1`
  pass bug fixed (`max(frac) >= 0`): A's arm term is 0/51, not 11/51 (the 11 were
  the never-visible rows). Two of my own instrument bugs were caught and fixed
  before the record batch (bbox-π disc area; a `ZeroDivisionError` in the row).
  Oracle 2 re-review next.
- 2026-10-24 **Gate 2 applied (the nine findings), and P35 committed.** F1: the
  claim is now "**the park is a measured interface lever; the check shows it
  removes the fruit's band occlusion; the mediator (image vs the 7 proprio
  channels) is not identified** - the control's invisible-fruit successes argue
  against a simple perception bottleneck" (WORKLOG headings + the phase-2
  paragraph, `C_RESULTS.md` §0/§3, `B_RESULTS.md`, this file, `AGENTS.md` §2,
  `README.md`); the **named mechanism test is the 2x2 input spoof**
  (proprio-spoof x image-spoof, small N), with the note that a recollection can
  erase a checkpoint-specific input-shift win and so is not the first spend. F2:
  "inside the **disc's bbox**" + the exact counts (68.1 % -> 0 %, 100 % -> 0 %,
  `C_attribution`'s `arm 40/51, never-visible 11`). F3: the design-valid leg is
  the **run-level 5/5 (p = 0.031)** + the standardised counts; the **exact pairing
  is conditioned on a post-treatment variable**; `C_pairs.txt` labelled as the
  **same-species 24-pair, 8/1** set (the extra A-only a different fruit, 6.5 vs
  6.1 cm) against the exact **22-pair 8/0**; `112_rl_ab.sh`'s **A-then-B fixed
  order** noted. F4: `vis >= 0.98` on **2** of the misses (3 at >= 0.97). F5:
  `C_attribution.py` no longer lets `frac = -1` pass the arm term
  (`max(frac) >= 0`), re-run: A 0/51, not 11/51, with the docstring corrected to
  +0.30..+0.40. F6: the **gate of record is M1 + M2a**; M2b is a recorded report
  at 36/50 = 72 %; `PREREG.md` §5's literal 0.02 rad command-residual block is
  **failed** by the 0.088 and the conclusion (not adopted) stands. F7: `rel`
  divides by a **running** `px*d^2` maximum, and the misses are small-mask raster
  drift (22-47 px) with the belt/frame where present - `park_ab_report.py`'s
  docstring corrected too. F8: `C_noharm_outer.log` annotated (exit=1 = the
  expected rate-only 6/10; the premature `cat` at 14:22 vs the 14:25 file; the
  identity re-verified 376/376). F9: the diff pin is **+424/-1**, `fd18bb1b`
  matches, `scripts/217_arm_park_map.py` / `logs/p35/park_ab_report.py` /
  `logs/p35/C_attribution.py` pinned, `logs/p35/` force-added. F10: the cycle's
  **mix** labelled (45 % vs 94 % success) with the **class/size-standardised
  94.9 %/94.1 %** quoted, the per-class deltas labelled as different
  denominators, and `113`'s "B PASSES" marked a **P33-era harness readout**.
  Committed as "P35: the inactive-arm park removes the band occlusion; …"
  (default off, not adopted; the mechanism discriminator is the named next).
