# P13 NO-HARM RESULTS (2026-10-19): the acceptance passes; the hybrid canary separates unexplainedly; the precautionary revert

## The acceptance (the scripted line): PASS

`logs/p13/70_accept.log`: **9/10 + `fingerprint: matches` + `logs/accept.log` 385/385** vs
`logs/p2d/90_accept.log` (0 diff) - the P13's changes never touched the scripted path.

## The hybrid canary (the policy loop): an unexplained separation -> the revert

| tree | samples (rate) | verdict |
| --- | --- | --- |
| **the P13 tree** (model.py a4de9cb1 / finetune.py 3bb1a062) | **2/10, 2/10, 4/10** | 3/3 FAIL (20-40 %, mean 27 %) |
| the pre-P13 tree (the parent's files) | **8/10, 6/10** | 2/2 PASS (60-80 %, mean 70 %) |

**The code paths are proven inert**: (a) the end-to-end forward bit-identity - the same
`moe_v12` + the same seeded inputs through the P13's and the parent's model.py give the SAME
output (`OUT_HASH 4a23a1d231bb34d201fba37a5186047f`, `sum -55.62229919433594` both);
(b) the runtime imports only `ConditionalUNet1D`; (c) `finetune.py` is imported only by
`scripts/111_rl_finetune.py` + `133_vlash_finetune.py` (the training scripts), never by the
canary's path; (d) the model.py's default path (`event_heads=False` -> `self.event=None`,
the keyword-defaulted param) adds no parameters, no RNG draws and no arithmetic.
**So the separation has NO identified mechanism**; the leading variance source is the hybrid
loop's known non-determinism (the RTX frames), but the observed ranges (20-40 % vs 60-80 %)
do not overlap at these small samples.

## The action: the precautionary revert (`489325c`)

The three files (`policy/model.py`, `policy/finetune.py`, `scripts/111_rl_finetune.py`) are
reverted to the parent (`63594c4`); the **ev1 checkpoint (`c2656cc2`) and the full P13 record
stay**; the code is preserved at `e078f43` (one `git show` away). The rationale: the ev1's
result is mechanism-only (not adopted), so the code need not ship; the unexplained canary
separation is a risk signal that outweighs the inert-code evidence; the two-line (the goal)
is unaffected either way. **The named decider for any re-entry: a >= 4-sample per-side canary
battery** (the ~80 min) - the current N=3-vs-N=2 is suggestive, not conclusive.

## The reverted-tree confirmation

`logs/p13/76_accept_policy_revert.log` (1 sample, launched after the revert): the record
completes the picture - 60-80 % means the anomaly tracked the code (despite the inertness
proof - a deeper mystery); 20-40 % means the anomaly is tree/state-level and the revert was
a precaution only.
