# P28-D results (the fine-tune + the counterfactual read)

- The multi-speed fine-tune: datasets/ss_multi (67 eps: ss008 25 @0.08, ss012 25 @0.12, ss015 17
  @0.15 - the 0.15 store's collection rate was 17/75 = 23%, an imbalance recorded); the recipe:
  from checkpoints/moe_v13s, --base datasets/demos_v11, 6 epochs, lr 5e-5, weight_mode ones,
  FRUIT_OBS_SPEED=1; the widen 25->26 (the zero column, the normaliser entry (0.12, 0.05)).
  Results: weighted 0.0170, router_acc 0.993 -> checkpoints/spd_v1/policy_best.pt.
- THE COUNTERFACTUAL-CHANNEL READ (logs/p29/counterfactual_speed.py): the trained model responds to
  the speed column - 0.12 -> 0.08 max|delta| 2.4181e-02 (mean 1.68e-3), 0.12 -> 0.15 1.81e-02
  (mean 1.25e-3), vs the B0's 0.0. The channel is NOT inert -> the A/B is warranted.
