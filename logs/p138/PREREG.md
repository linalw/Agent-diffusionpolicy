# P138 pre-registration - the recollection on the flipped tree

**Written before the fine-tune's behaviour was read** (the store and the fidelity
had run: the store is the input, the fidelity is offline). Recorded as such.

## 0. Why a recollection at all

P136 moved the scripted cell's branch (`459 [fruit]` lines vs 421) by making the
prediction-gated handover the default. Every demonstration store on the tree
predates it, so a store recorded now is a *different cell*: the named next step
after a scripted change is a recollection + a fine-tune, and the store's manifest
must say which catch it was recorded under (it does: `physics.tracking`).

## 1. The scope and the endpoint

* The store: the shipped **two-line** cell, the tracker on (the default), 45
  episodes, seed 901, `datasets/p138_track` (gitignored; provenance in `logs/`).
* The fine-tune: the lineage recipe (`111_rl_finetune`, `moe_v13s` init,
  `demos_v11` base, 6 epochs, lr 5e-5, `ones`, base-weight 1.0).
* **Endpoint 1 (offline, diagnostic only)**: `119_rl_fidelity` - the paired action
  error of the candidate against the init on the store's own windows. The record
  is explicit that fidelity is a *diagnostic, not a measurement*: a candidate that
  is closer to the demonstrations is a candidate that learned the store, not one
  that performs better.
* **Endpoint 2 (behavioural, a smoke)**: the hybrid canary, init vs candidate,
  the same seed, 3 episodes each. **At n = 3 this cannot resolve the canary's
  recorded 5-8/10 spread**, so a tie is the expected result and is reported as
  "no discrimination at this n", never as "no gain".

## 2. What would justify a rate claim

The record's own convention: the direct A/B (`scripts/112_rl_ab.sh`, N = 5 x 15,
the WS-4.2 protocol) with the carried-class pairing, and the canary at its own
10-episode gate. Both are **named and not run** here - the A/B alone is 1.5-2 h of
wall clock and the tree already carries three nulls on this interface
(W7-C/W8-A, R9, P37). A 45-episode store is also below the 150-200 the lineage
recollections used, so a *rate* from it would be a branch of a thin store.

## 3. Not claimed

No rate, no adoption, no change to `accept_policy.sh`'s default checkpoint. The
deliverables are the store + the checkpoint + the fidelity + the canary smoke, with
the A/B cost named.
