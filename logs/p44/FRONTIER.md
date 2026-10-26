# P44 frontier note — what the web would not give us, and what the local record already fixes

**Status: the two live-research attempts failed on infrastructure** (a TLS
`UNKNOWN_CERTIFICATE_VERIFICATION_ERROR`, then an `ECONNRESET` from the search
tool), so this file is the **local record plus the census**, not a fresh survey.
It is written so the plan does not depend on the missing survey, and so a later
reader knows exactly what is unverified.

## 1. What the local record already establishes (citation: `logs/p40/LIT_REVIEW.md`)

- **ForceDelta-VLA** (arXiv 2609.18242): a *frozen* force-aware VLA plus a
  separate **2.43 ms** correction head that consumes a **force delta** and a
  **delay delta** and emits an **additive pose residual**; the gripper command
  comes from the reference, not from the head. The wrench is estimated from
  joint torques at 100 Hz. Measured 82.2 % vs 54.4 % (ForceVLA) over 9 real
  tasks; the ablation that matters here: a *separate* correction head beats a
  combined head by 15-17.5 points.
- **Eka VFA**: a company product (vision-force-action + a force-sensitive
  gripper, trained by sim RL). **No paper, no architecture, no control rate** -
  the 1,500 ops/hr and >95 % are claims. Nothing from it is quotable as measured.
- Slip/reflex latencies: human reactive grip 60-80 ms; tactile slip caught at
  21-31 mm of slip; FORTE <100 ms; event-camera incipient slip 44.1 ms - the
  project's own escape gives **~208 ms** (25 ticks) from the 2 mm crossing to
  contact loss, i.e. a reflex has ~2-3x margin.
- RTC/VLASH: +200 ms robustness and 20 % fewer *wall* seconds at equal score;
  raising the policy rate to 100 Hz raises jitter failures 5.0 -> 21.8 %.

## 2. What the census adds, and it changes the framing

`logs/p44/CAP_CENSUS.md` measures every cap. The decisive lines:

- **The joint velocity limits cannot help**: the tightest is `maxJointVelocity`
  312 deg/s = 5.45 rad/s, **2.1x** the fastest reference (j4/j7 carry 0.79-0.84
  m/s against a 0.38 m/s lever). Unreachable.
- **The joint effort limits cannot help**: the tightest `maxForce` 7 N·m leaves a
  2.4x margin, and the drive is already a torque source at the measured ~30 mrad.
- **The arm drive gains cannot help**: every leg is **tick-clocked by its
  profile** (reproduced to +-1.4 %), so bandwidth changes tracking, never
  duration; measured null on the descent (`logs/165`).
- **The friction cone does not bind** on `lift` (a = 1.0 of 1.962) or `place`
  (1.089 of 4.273). (This corrects the P44 opening note, which assumed a
  cone-limited carry.)
- **The time is in the profiles and three open-loop holds**: `place` 3.35 s
  (22.3 %) of which 3.16 s is one jerk-limited profile at `v_max` 0.35
  (recoverable **1.09-1.38 s**); `release` 2.04 s (13.6 %) of which **1.57 s is
  three open-loop holds** (20 + 120 + 48 ticks, recoverable **0.63-1.02 s**);
  `lift` 1.82 s (12.1 %) of which 1.37 s is the profile at `v_max` 0.30
  (recoverable **0.23-0.56 s**). Together **48 % of the cycle**, and the caps
  inside them are **6.10 s**.

## 3. The fusion, as this project can actually test it

- **The "VFA half"** (fast whole-action) = the three blocks above: raise the
  place/lift profile limits and cut the release's open-loop holds. Measured,
  cheap, and **not** a hardware lock - it is the profile and the clocks.
- **The "ForceDelta half"** (fast hand micro-corrections) has **no target left**:
  it exists to correct a force/pose residual on a *contact-rich* segment, and
  this project's only such segment is the carry, whose failure class is closed
  (`SIM_LIMIT.md`) with the cone not binding. The honest use of it is as a
  **guard**: if the faster place/lift re-opens a slip, a bounded force-derived
  pose residual is the named remedy; the phase-2 battery tests whether that is
  needed.
- **The "no-lock" question is answered by the census**: the caps have 2.1x
  (velocity) and 2.4x (effort) headroom and the gains do not set duration, so
  **raising them buys nothing**; what looks like a lock is a **profile choice**.

## 4. Unverified and not claimed

The 2026 frontier beyond `logs/p40/LIT_REVIEW.md` (fast/slow hierarchies,
force-conditioned policies, RTC successors, throughput benchmarks) was **not**
surveyed here because of the tool failures. Nothing in the plan below depends on
it; a later lane can add it.
