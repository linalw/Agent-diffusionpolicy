# P45 frontier note — a live survey at last (the two earlier attempts died on TLS/ECONNRESET)

Surveyed 2026-10-27 with the network available. Every claim carries a source; the
"measured vs claimed" split is explicit. Nothing here changes a shipped default.

## 1. ForceDelta-VLA — verified against the abstract (arXiv 2609.18242v2, 23 Oct 2026)

**What it actually is.** A *correction-distillation* framework. It builds an
explicit **force-correction target** from **paired predictions of a frozen
teacher** - the same teacher run in its force-conditioned and its
force-agnostic mode - so the correction is what the force channel *changes*. A
separate **delay-correction target** accounts for the reference-action mismatch
and the change in reference state. Training uses **asynchronous schedule replay**
with the cached task context available at execution. The resulting **lightweight
policy adjusts the reference actions from recent force history and robot state**,
reacting to contact changes **between reference-action updates without
regenerating complete action chunks**.

**Measured** (the abstract's own numbers): **82.2 %** mean success over nine
single-arm and bimanual contact-rich tasks vs **54.4 %** for ForceVLA; the
**Stage-1 temporal teacher alone reads 70.6 %**; the complete system lowers the
**mean peak contact force by ~26 %** on successful trials on both platforms.
**Claimed** (not in the abstract, from the earlier P40 read): a 2.43 ms correction
head, wrench from joint-torque estimates at 100 Hz, no wrist F/T.

**What transfers to this project.** The shape, not the model: a **bounded pose
residual driven by a force/tactile derivative, evaluated between the slow
reference's updates**. This tree already logs the inputs at 120 Hz (`[attitude]`,
`[carry]` force rows, `FRUIT_GRIP_EFFORT`). **What does not**: the distillation
itself needs a *frozen force-aware teacher plus a force-agnostic twin* and paired
demonstrations - a retraining of scale this project has measured as
no-gain three times (P33/P37/R9). The honest use here is a **hand-written
residual** on the carry, which is exactly the "named remedy" P44 registered when
its speed union showed a branch-dependent class cost.

## 2. Eka VFA — still not verifiable

No paper, no architecture, no control rate surfaced in this pass either. The
"vision-force-action + a force-sensitive gripper trained by sim RL" framing and
the 1,500 ops/hr / >95 % figures remain **company claims**; nothing from it is
quotable as measured. (The P40 review reached the same conclusion.)

## 3. The 2026 speed frontier, the parts that are verifiable

* **Time-optimal execution of action-chunk policies, beyond demonstration speed**
  (Kim et al., **ICLR 2026**, `proceedings.iclr.cc/paper_files/paper/2026/
  file/fab80bb9...-Paper-Conference.pdf`). The title states the claim - a policy's
  chunks can be re-timed faster than the demonstrations - which is the same axis
  as this project's P44 speed cells (a *kinematic* re-timing, not a new policy).
  **The PDF exceeded the fetch limit, so no numbers are quoted here.** It is a
  pointer for the policy loop.
* **Delta robots**: "commonly exceed **100 picks per minute** for light parts"
  and "up to **200 picks/min**, accelerations up to **~10 G**"
  (`evsint.com`, `swoer.com`, 2026 - vendor pages, **claims**). Context only: a
  parallel-kinematic architecture, not a serial arm. This cell reads **2.39
  placed/min** single-arm and **4.90** two-line - the gap is the architecture and
  the task, not a tuning constant.
* **"Future-aware AI doubles robot speed in pick-and-place"**
  (`techxplore.com`, 2026-07) - a press item; a pointer, no quotable number.

## 4. The payload-mass question

One targeted search found **no measured study** of "a lighter payload is flung
out of a parallel jaw at release"; what the search returns is aerial jamming
grippers and space payloads - off-topic. The physics is elementary and is the
census's (`logs/p45/MASS_CENSUS.md`): with a **grip-set** normal force,
`mu*N` is constant in `m`, so the **slip ratio is proportional to m** (a lighter
fruit *does* buy slip margin: 0.370 -> 0.185 -> 0.093 at 0.5x/0.25x on the worst
fruit), while the **fling** (`v = J/m`) and the **roll-out** (`alpha = 2.5 mu N /
(m R)`) both scale **1/m** - a lighter fruit flies 2x/4x faster and walks out
2x/4x faster. The delta-robot marketing's "light parts, >100 picks/min" is about
*accelerating* a light part, not about *holding* it.

## 5. Ranked, testable for this repo

1. **The mass x speed battery** (running, `logs/p45/p2/`) - the owner's question,
   with the fling restricted to in-hand payloads and the walk read arm-vs-control.
2. **Adopt one speed cell with its own pre-registration** - S1 (place 0.52, clean
   at both seeds, 5.3 %) or the **two-line union** (class-identical, 11 %); each
   needs the two reference re-records.
3. **A hand-written ForceDelta-shaped residual** on the carry - only if (1) shows
   the speed re-opens the class, and only as the bounded pose residual the
   abstract describes; **not** a distillation.
4. **The ICLR 2026 chunk re-timing** - a policy-loop *wall* lever only; this
   tree's loop is primitive-bound (84 % of the wall), so its ceiling is the
   remaining 16 %.
5. A **delta-style parallel kinematic** - out of scope (a different robot).

## 6. Not transferable, stated once

The VLA-scale distillation (no paired teacher; three recollections measured
no-gain), Eka's unverifiable numbers, and the delta robot's pick rates
(architecture). Nothing in this note is a reason to re-open the grip class or the
park.
