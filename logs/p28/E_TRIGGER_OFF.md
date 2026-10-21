# P28-E (first pass): the TRIGGER=off cells — the model's autonomy gap (2026-10-21)

The Gate-A B1 fix ("move the primary cells to TRIGGER=off so the model's own close is the fire
path") was run. Result: **all six cells 0/15** (A = moe_v13s 25-D, B = spd_v1 26-D; 0.08/0.12/0.15),
with the failure reasons 'timeout: no grasp', 'policy closed on the fruit', 'fruit fell off the
line'.

**The measurement**: with the scripted arrival trigger disabled, the learned close gate fires on
almost no attempt (the Gate-A's fire-path census: 2/60), so the episodes time out before any
capture. The model's own close is NOT a viable fire path in this interface — the trigger carries
the firing. **The owner's "model adaptation" premise is blocked by the interface's autonomy, not
by the speed channel**: with no model-side actuator on the fire path, no observation channel can
change the outcome.
This is a clean, repeatable interface finding (both arms, all speeds, the same three reasons).
The speed-channel test therefore re-scopes to the shipped interface (FRUIT_POLICY_TRIGGER=arrival
+ the ACQ env), where both fire paths exist ('either path may fire the scripted primitive') and
the model's close is an additional path - the cells that can register a channel effect.
