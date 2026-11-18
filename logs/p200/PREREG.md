# P200 pre-registration: the selector's floor on the direct-policy lane

Written **before** any cell runs.

## The claim

P194-P199 localise the adopted recipe's residual to the **acquisition**: 12/12 latched
attempts placed, every failure is a fruit that was already level with or behind the hand
when the attempt began (the servo then chases it downstream for its whole window:
`aim y -0.242 -> -0.562` at the belt's own speed, jaw 500 mm behind, `hold` 536 mm). The
successful latches happen with the **true** fruit **84-144 mm upstream**, because the goal's
coast leads it.

The tree already has the knob that expresses "select earlier": `_dynamic_select_floor()`
= `_dynamic_pick_lead() + |v| * FRUIT_DYNAMIC_SELECT_S + 0.03`, with
`FRUIT_DYNAMIC_SELECT_S = 1.5 s` shipped (**a floor of ~0.40 m**). That value was
calibrated for the *scripted* line's 1.5 s pre-pose + transit; the direct lane's setup is
the **model's own approach**, which takes longer - measured, the arming happens with the
fruit at or behind the hand.

**The cell**: `FRUIT_DYNAMIC_SELECT_S` 1.5 (control) against **3.0 s** (a floor of
~0.58 m), which selects 0.18 m earlier.

## Cells

Seeds **808** and **303** (the two whose failure classes are documented), **6 episodes**
each, control and treatment in one batch = **24 episodes**. The recipe is the adopted one
(`docs/DIRECT_POLICY.md` §2) with nothing else changed.

## Endpoints and the rule

* **Primary**: pooled `placed` at 3.0 s >= **14/24** AND >= the control's pooled count.
* **Mechanism (the reason to believe it)**: the `[fire]` census's **fraction of latches
  with the true fruit upstream (`dy > 0`)** must rise against the control's.
* **Cost, reported not gated**: the *skipped*/starved selection count (a higher floor
  refuses more fruit; the record's P92/P93 measured that trade on the band).
* **Falsifiers**: pooled <= the control's; or the latch-upstream fraction does not rise;
  or the skipped count rises by more than the gain in placements.

## Not claimed

No rate (24 episodes, two seeds); no claim about the shipped defaults or any other
checkpoint; no claim that the floor is the *only* acquisition term.
