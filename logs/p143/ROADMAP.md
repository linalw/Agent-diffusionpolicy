# P143 - the roadmap to "the model does approach -> grasp -> place"

Owner's brief: give the model a target fruit and it should approach, grasp and
place by itself; plan autonomously, collect as much data as the effect needs.

## Where it stands (all measured)

| cell | `gap_min` | success |
|---|---|---|
| `moe_v13s`, shipped direct | 140 mm | 0 |
| DAgger 24 ep, expert-driven store (base 1.0) | 63 mm | 0 |
| DAgger 24 ep (base 0.3, 8 ep) | 73.5 mm | **1/12** |
| DAgger 36 ep, expert-driven store | 107 mm | 0 |
| hybrid canary (`handoff`) | - | **8/10** |
| direct + `arrival` (external fire) | - | 3/4 |

Two facts structure everything below:

1. **The model does close** (finger 0.005-0.016); it closes at **13-15 cm** on the
   baseline and reaches 1-6 cm after DAgger.
2. **The handover gate is a 6 cm conjunction** (`finger < 0.030` **and**
   `|jaw-fruit| < 0.06`). The **primitive can catch from 26 cm** - that is what
   `arrival` does every time it fires. So the gate, not the primitive and not the
   grasp, is the binding interface term for the model's own close.

## The plan

| # | cell | why | cost |
|---|---|---|---|
| **R1** | **on-policy DAgger store** (`--expert-window 0`: the expert never takes over, labels still recorded) | the 24/36-ep stores are 92-95 % expert ticks, i.e. behaviour cloning; this one is the policy's own distribution | 24 ep, ~1.5 h (**running**) |
| **R2** | fine-tune R1 (base 0.3, 8 ep) + eval 12 | does an on-policy store beat 63 mm / 1-of-12? | 10 + 20 min |
| **R3** | **relax the close gate** (`FRUIT_POLICY_CLOSE_DIST` 0.06 -> 0.15) on the **baseline** checkpoint | the model closes at 13 cm and the primitive catches from 26; if a 15 cm gate converts those closes into grasps, the interface - not the model - was the blocker | 1 code line + 20 min |
| **R4** | whichever of R2/R3 wins, **iterate**: collect with the improved policy (DAgger round 2), retrain, re-evaluate `gap_min` **and** `grasped` | the standard loop; each round is 1.5-2 h | as needed |
| **R5** | only if R3 fails: teach the gate itself (a learned "close" head), or move the handover to the primitive and stop asking the policy for the close | last resort, documented in P142/P143 | - |

**Success criterion for the phase**: `grasped` and `success` on the direct loop
with **no** external trigger and **no** teleport, at n >= 12, with `gap_min`
reported beside them. A rate needs 45+ episodes; the phase reports the counts and
the mechanism until then.

## Read rules

* `gap_min` and the success count rank candidates differently at n = 12 (measured:
  base 0.3 is worse on the median and better on the count) - quote both.
* Every store's value is bounded by its **expert-tick share**: above ~90 % the
  store is behaviour cloning whatever it is called.
* The policy camera (424x240) is the model's input and never moves; the raised
  `overhead.mp4` is a separate validation camera.
