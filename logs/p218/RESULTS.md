# P218 result - the size-conditioned scripted skill places 5/6 lychees

The learned policy never approaches a 3.1-3.4 cm fruit (P216: `[fire] fired=0` at
0.65-1.18 m); the shipped scripted catch places 5/6 lychees at 9.65-10.61 N (P217).
`FRUIT_SMALL_HANDOVER=1` routes a fruit at/below 0.040 m to `_run_scripted()` (the same
`task.run` as `--ablate scripted`); larger fruit keep the learned policy.

Lychee-only supply, seed 808, 6 episodes:

| route | placed | policy decisions |
|---|---:|---:|
| learned direct, 60 N (P215) | 1/6 | 1269-1382 |
| scripted dynamic catch (P217) | 5/6 | - |
| **small handover (P218)** | **5/6** | **0 per small attempt** |

The `[rl] episode` rows read `decision=0` on the five small-handover attempts, i.e. the
learned model was not used; the scripted `task.run` owned them. The one failure is the
first 3.1 cm lychee. The handover fires, the count matches the scripted control, and the
learned policy is untouched for larger fruit.

**This is a hybrid, stated as such**: the learned model owns the large-fruit decisions and
the scripted skill owns the <= 4 cm class. It is not a learned small-fruit policy. The
default stays off; the class route is a recipe setting.

**Pins.** `rl_env.py` **`bd1bf141`**, `scripts/280_p218_small_handover_selftest.py`
**`24c8bfad`**, `selfcheck.sh` **`a9314fe9`**; evidence `logs/p218/SH_s808.log`. No default
change.
