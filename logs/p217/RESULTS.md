# P217 control - the **scripted** line grasps 5/6 lychees; the small-fruit failure is the policy

The decisive control for P215/P216: the same hand, the same 3.1-3.4 cm lychee-only pool,
the shipped **scripted** dynamic catch (single arm, `FRUIT_BIARM=0`,
`FRUIT_SUPPLY_SPECIES=lychee`, seed 808, 6 attempts):

| line | placed | force on placed legs |
|---|---:|---|
| **scripted dynamic catch** | **5/6 = 83 %** | 9.65-10.61 N |
| learned direct, 60 N cap (P215) | 1/6 | - |
| learned direct, 20 N cap (P215) | 1/6 | - |
| learned direct, two-sided close (P216) | 0/4 partial, `fired=0` at 0.65-1.18 m | - |

The one scripted failure is `grasped=True placed=False` at **29.00 N** (a carry/place
escape), not a small-fruit acquisition. The 5 successes lift 0.312-0.382 m at 9.65-10.61 N.

**This corrects the hardware reading of P215.** The hand can hold a 3.1 cm lychee at the
shipped **10 N**; the learned policy with 20-60 N never reaches it (`fired=0`, fruit
0.65-1.18 m behind). The small-fruit residual is the **policy's approach/phase**, not
force, not pad geometry and not the second view. The next spend is a policy fix: a
size-aware phase gate/retrain, a cartesian action, or a **size-conditioned handover** to
the scripted primitive (the 5/6 line) while the learned policy keeps the large fruit.

The scripted control is a class mechanism, not the shipped mix; the hand's success on a
3 cm object at 10 N is the point. Evidence `logs/p216/scripted_lychee.log`.
